import streamlit as st
import requests
import json
import random
from datetime import datetime
import os
import time

# -------------------------
# CONFIGURATION - OpenAI API Key
# -------------------------
def get_api_key():
    """Get API key from multiple sources"""
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        try:
            api_key = st.secrets.get("OPENAI_API_KEY")
        except (FileNotFoundError, KeyError):
            pass
    
    return api_key

API_KEY = get_api_key()

if not API_KEY:
    st.error("🚨 No API key found!")
    st.warning("""
    **Please add your OpenAI API key using ONE of these methods:**
    
    **Method 1: Streamlit Secrets (For local development)**
    
    Create `.streamlit/secrets.toml` in your project root:
    ```toml
    OPENAI_API_KEY = "sk-proj-your-openai-api-key-here"
    ```
    
    **Method 2: Environment Variable**
    ```bash
    export OPENAI_API_KEY="sk-proj-your-openai-api-key-here"
    ```
    
    Get your API key at: https://platform.openai.com/api-keys
    
    ⚠️ **IMPORTANT:** Make sure you have:
    1. Added credits to your OpenAI account
    2. Set up billing at https://platform.openai.com/account/billing
    """)
    st.stop()

# OpenAI API endpoint
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# -------------------------
# Rate Limiting Configuration
# -------------------------
RATE_LIMIT_CONFIG = {
    "requests_per_minute": 3,
    "min_delay_seconds": 20,
    "max_retries": 3,
    "retry_delay": 30
}

# -------------------------
# Backend: OpenAI Quiz Generator with Rate Limiting
# -------------------------
def generate_quiz(text, num_questions=5):
    """Generate quiz questions using OpenAI API with rate limiting"""
    if not text or not text.strip():
        return None, "Please provide text to generate questions from."
    
    if not API_KEY:
        return None, "API key is required."
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    prompt = f"""Create exactly {num_questions} multiple-choice questions from the following text.

IMPORTANT: Return ONLY valid JSON in this EXACT format with no additional text:

{{
  "quiz": [
    {{
      "question": "What is the main topic?",
      "options": ["a) Option 1", "b) Option 2", "c) Option 3", "d) Option 4"],
      "answer": "b) Option 2",
      "explanation": "Brief explanation here"
    }}
  ]
}}

Rules:
- Create clear questions based ONLY on the text below
- Each question must have exactly 4 options (a, b, c, d)
- Only ONE correct answer per question
- Include brief explanations
- Return ONLY the JSON, no markdown, no extra text

Text to analyze:
{text[:2000]}"""

    data = {
        "model": "gpt-4o-mini",  # Using newer model instead of gpt-3.5-turbo
        "messages": [
            {"role": "system", "content": "You are a helpful quiz generator that returns only valid JSON responses."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 1500  # Reduced from 2048
    }

    # Retry logic
    for attempt in range(RATE_LIMIT_CONFIG["max_retries"]):
        try:
            response = requests.post(OPENAI_URL, headers=headers, json=data, timeout=30)
            
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', RATE_LIMIT_CONFIG["retry_delay"])
                try:
                    retry_after = int(retry_after)
                except:
                    retry_after = RATE_LIMIT_CONFIG["retry_delay"]
                
                if attempt < RATE_LIMIT_CONFIG["max_retries"] - 1:
                    st.warning(f"⏳ Rate limit hit from OpenAI. Waiting {retry_after} seconds... (Attempt {attempt + 1}/{RATE_LIMIT_CONFIG['max_retries']})")
                    time.sleep(retry_after)
                    continue
                else:
                    return None, f"""⏳ **OpenAI Rate Limit Exceeded**
                    
Your OpenAI API is being throttled. This means:

1. **No Credits/Billing**: You need to add payment method
2. **Free Tier Exhausted**: Daily/monthly quota used up
3. **Too Many Requests**: Hitting OpenAI's rate limits

**Solutions:**
✅ Add credits: https://platform.openai.com/account/billing/overview
✅ Check usage: https://platform.openai.com/usage
✅ Wait a few minutes and try again
✅ Reduce questions to 3-5 per quiz

**Make sure:**
- Your API key is valid
- Billing is set up
- You have available credits
"""
            
            if response.status_code == 401:
                return None, """❌ **Invalid API Key**

Your API key is not working. Please check:

1. Copy your key again from: https://platform.openai.com/api-keys
2. Make sure it starts with 'sk-proj-' or 'sk-'
3. Update your `.streamlit/secrets.toml` file:
   ```
   OPENAI_API_KEY = "sk-proj-your-actual-key"
   ```
4. Restart the Streamlit app
"""
            
            if response.status_code == 403:
                return None, """❌ **Access Denied - No Billing Setup**
                
Your API key exists but has no access. This means:

**You MUST set up billing first:**
1. Go to: https://platform.openai.com/account/billing/overview
2. Click "Add payment method"
3. Add a credit/debit card
4. Add at least $5 in credits
5. Wait 5-10 minutes for activation

**Note:** Even with a valid API key, you CANNOT use the API without adding a payment method and credits.

Check your account status: https://platform.openai.com/account/billing/overview
"""
            
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                
                # Show detailed error
                return None, f"""❌ **OpenAI API Error {response.status_code}**

{error_message}

**Common Issues:**
- 401: Invalid API key
- 403: No billing/credits set up
- 429: Rate limit or quota exceeded
- 500: OpenAI server error (try again)

**Check:**
1. API Key: https://platform.openai.com/api-keys
2. Billing: https://platform.openai.com/account/billing/overview
3. Usage: https://platform.openai.com/usage

**Full error:** {error_data}
"""

            result = response.json()
            generated_text = result['choices'][0]['message']['content'].strip()
            
            # Clean markdown
            if generated_text.startswith('```json'):
                generated_text = generated_text[7:]
            if generated_text.startswith('```'):
                generated_text = generated_text[3:]
            if generated_text.endswith('```'):
                generated_text = generated_text[:-3]
            generated_text = generated_text.strip()

            try:
                quiz_data = json.loads(generated_text)
            except json.JSONDecodeError:
                import re
                match = re.search(r'\{.*\}', generated_text, re.DOTALL)
                if match:
                    try:
                        quiz_data = json.loads(match.group())
                    except:
                        return None, "Failed to parse quiz response."
                else:
                    return None, "Failed to parse quiz response."

            quiz_questions = quiz_data.get("quiz", [])
            
            if not quiz_questions:
                return None, "No questions generated. Try with more detailed text."
            
            for q in quiz_questions:
                if "options" in q and "answer" in q and "question" in q:
                    correct = q["answer"]
                    random.shuffle(q["options"])
                    q["answer"] = correct
                else:
                    return None, "Invalid question format received."

            return quiz_questions, None
            
        except requests.exceptions.Timeout:
            if attempt < RATE_LIMIT_CONFIG["max_retries"] - 1:
                time.sleep(5)
                continue
            return None, "⏱️ Request timed out."
        except requests.exceptions.RequestException as e:
            return None, f"🌐 Network error: {str(e)}"
        except Exception as e:
            return None, f"❌ Unexpected error: {str(e)}"
    
    return None, "Failed after multiple retries."

# -------------------------
# Initialize Session State
# -------------------------
def init_session_state():
    defaults = {
        "page": "main",
        "paragraphs": [],
        "saved_quizzes": {},
        "current_quiz_index": None,
        "user_answers": {},
        "show_results": False,
        "quiz_history": [],
        "num_questions": 5,
        "api_calls_made": 0,
        "last_api_call": 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# -------------------------
# Page Configuration
# -------------------------
st.set_page_config(
    page_title="📘 Smart Study Partner",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# CSS Styling - Dark Mode Only
# -------------------------
st.markdown("""
<style>
    .stApp {
        background: #0f172a;
        color: #f1f5f9;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .card {
        background: #1e293b;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #334155;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
    }
    
    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.5);
    }
    
    .question-box {
        background: #1e293b;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #10b981;
        border: 1px solid #334155;
        margin-bottom: 1.5rem;
        color: #f1f5f9;
    }
    
    .stats-box {
        background: #1e293b;
        padding: 1.5rem;
        border-radius: 12px;
        border: 2px solid #10b981;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .stats-number {
        font-size: 2rem;
        font-weight: bold;
        color: #10b981;
    }
    
    .stats-label {
        font-size: 0.9rem;
        color: #cbd5e1;
        font-weight: 500;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
        color: white;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
        width: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
    }
    
    .stButton > button:disabled {
        background: #475569;
        cursor: not-allowed;
        transform: none;
    }
    
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
    }
    
    .stRadio > div > label {
        background: #1e293b;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: 2px solid #334155;
        margin-bottom: 0.5rem;
        color: #f1f5f9;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .stRadio > div > label:hover {
        border-color: #10b981;
        background: #334155;
        transform: translateX(4px);
    }
    
    .stTextArea > div > div > textarea,
    .stTextInput > div > div > input {
        background: #1e293b;
        color: #f1f5f9;
        border: 1px solid #334155;
        border-radius: 8px;
    }
    
    section[data-testid="stSidebar"] {
        background: #1e293b;
        border-right: 1px solid #334155;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #f1f5f9;
    }
    
    p {
        color: #cbd5e1;
    }
    
    .score-card {
        background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
        padding: 2rem;
        border-radius: 16px;
        text-align: center;
        color: white;
        margin: 2rem 0;
    }
    
    .rate-limit-warning {
        background: #451a03;
        border-left: 4px solid #f59e0b;
        padding: 1rem;
        border-radius: 8px;
        color: #fbbf24;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Sidebar Navigation
# -------------------------
with st.sidebar:
    st.title("📌 Navigation")
    
    # Rate Limit Warning
    if st.session_state.last_api_call > 0:
        elapsed = time.time() - st.session_state.last_api_call
        if elapsed < RATE_LIMIT_CONFIG["min_delay_seconds"]:
            wait_time = int(RATE_LIMIT_CONFIG["min_delay_seconds"] - elapsed)
            st.markdown(f"""
            <div class='rate-limit-warning'>
                ⏳ <strong>Rate Limit Protection</strong><br>
                Wait {wait_time}s before next generation
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Settings
    st.subheader("⚙️ Settings")
    num_q = st.slider("Questions per quiz", 3, 10, min(st.session_state.num_questions, 10), 
                      help="Fewer questions = less API usage", key="num_q_slider")
    st.session_state.num_questions = num_q
    
    st.info("💡 **Tip:** Start with 3-5 questions to avoid rate limits!")
    
    st.markdown("---")
    
    # API Usage Stats
    st.subheader("📊 API Usage")
    st.markdown(f"""
    <div class='stats-box'>
        <div class='stats-number'>{st.session_state.api_calls_made}</div>
        <div class='stats-label'>API Calls Made</div>
    </div>
    <div class='stats-box'>
        <div class='stats-number'>{len(st.session_state.saved_quizzes)}</div>
        <div class='stats-label'>Quizzes Generated</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.warning("⚠️ **Free Tier:** 3 requests/min. Wait 20s between generations.")
    
    with st.expander("📖 Rate Limit Help"):
        st.markdown("""
        **Why am I seeing rate limits?**
        
        Free OpenAI accounts have strict limits.
        
        **Solutions:**
        1. Add credits: https://platform.openai.com/account/billing
        2. Wait 20-30 seconds between generations
        3. Generate fewer questions (3-5 instead of 10+)
        4. Reuse existing quizzes (no API calls!)
        
        **Check usage:** https://platform.openai.com/usage
        """)
    
    st.markdown("---")
    
    # Navigation buttons
    if st.session_state.saved_quizzes:
        if st.button("📚 My Quizzes", key="nav_quizzes", use_container_width=True):
            st.session_state.page = "quiz_library"
            st.rerun()
    
    if st.session_state.quiz_history:
        if st.button("📊 View History", key="nav_history", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()
    
    st.markdown("---")
    
    # Overall Stats
    if st.session_state.quiz_history:
        avg_score = sum(h["score"] for h in st.session_state.quiz_history) / len(st.session_state.quiz_history)
        st.markdown(f"""
        <div class='stats-box'>
            <div class='stats-number'>{len(st.session_state.quiz_history)}</div>
            <div class='stats-label'>Quizzes Completed</div>
        </div>
        <div class='stats-box'>
            <div class='stats-number'>{avg_score:.1f}%</div>
            <div class='stats-label'>Average Score</div>
        </div>
        """, unsafe_allow_html=True)

# -------------------------
# MAIN PAGE
# -------------------------
if st.session_state.page == "main":
    st.title("📘 Smart Study Partner")
    st.markdown("### Transform your study materials into interactive quizzes!")
    
    # Rate limit info
    st.info("⏳ **Rate Limit Info:** Wait 20 seconds between quiz generations to avoid errors!")
    
    # Input section
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    user_input = st.text_area(
        "📥 Paste Your Study Material",
        height=200,
        placeholder="Enter your paragraph, notes, or study material here (up to 2000 characters)...",
        max_chars=2000,
        key="main_input"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Add Paragraph", key="add_para", use_container_width=True):
            if user_input and user_input.strip():
                st.session_state.paragraphs.append(user_input.strip())
                st.success("✅ Paragraph added!")
                st.rerun()
            else:
                st.warning("⚠️ Please enter some text first!")
    
    with col2:
        if st.session_state.paragraphs:
            if st.button("🗑️ Clear All", key="clear_all", use_container_width=True):
                st.session_state.paragraphs = []
                st.session_state.saved_quizzes = {}
                st.success("🗑️ All cleared!")
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Saved paragraphs
    if st.session_state.paragraphs:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"📚 My Study Materials ({len(st.session_state.paragraphs)})")
        
        for i, para in enumerate(st.session_state.paragraphs):
            para_preview = para[:120] + "..." if len(para) > 120 else para
            
            if i in st.session_state.saved_quizzes:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**✅ Material {i+1}:** {para_preview}")
                    st.caption(f"{len(st.session_state.saved_quizzes[i])} questions ready • {len(para)} characters")
                with col2:
                    if st.button("📖 Take Quiz", key=f"take_quiz_{i}", use_container_width=True):
                        st.session_state.current_quiz_index = i
                        st.session_state.user_answers = {}
                        st.session_state.show_results = False
                        st.session_state.page = "quiz"
                        st.rerun()
                with col3:
                    # No more local rate limiting
                    if st.button("🔄", key=f"regen_quiz_{i}", use_container_width=True, help="Regenerate quiz"):
                        del st.session_state.saved_quizzes[i]
                        with st.spinner("🤖 Regenerating..."):
                            quiz, error = generate_quiz(para, st.session_state.num_questions)
                        
                        if error:
                            st.error(f"{error}")
                        elif quiz:
                            st.session_state.saved_quizzes[i] = quiz
                            st.session_state.api_calls_made += 1
                            st.session_state.last_api_call = time.time()  # Record successful call
                            st.success("New quiz ready!")
                            st.rerun()
            else:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**📄 Material {i+1}:** {para_preview}")
                    st.caption(f"Ready to generate • {len(para)} characters")
                with col2:
                    # No more local rate limiting - just check button state
                    if st.button("⚡ Generate", key=f"gen_quiz_{i}", use_container_width=True, type="primary"):
                        with st.spinner("🤖 Creating quiz..."):
                            quiz, error = generate_quiz(para, st.session_state.num_questions)
                        
                        if error:
                            st.error(f"{error}")
                        elif quiz:
                            st.session_state.saved_quizzes[i] = quiz
                            st.session_state.api_calls_made += 1
                            st.session_state.last_api_call = time.time()  # Record successful call
                            st.success("Quiz ready! Click 'Take Quiz' to start.")
                            st.rerun()
            
            st.markdown("---")
        
        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# QUIZ LIBRARY PAGE
# -------------------------
elif st.session_state.page == "quiz_library":
    st.title("📚 My Quiz Library")
    st.markdown("### All your generated quizzes in one place!")
    st.success("💡 **No API calls needed** - Retake any quiz unlimited times for FREE!")
    
    if not st.session_state.saved_quizzes:
        st.info("No quizzes generated yet. Go to Home and create some!")
        if st.button("🏠 Go Home", key="lib_home"):
            st.session_state.page = "main"
            st.rerun()
    else:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        
        for idx, quiz in st.session_state.saved_quizzes.items():
            para_preview = st.session_state.paragraphs[idx][:100] + "..." if len(st.session_state.paragraphs[idx]) > 100 else st.session_state.paragraphs[idx]
            
            with st.expander(f"📖 Quiz {idx+1} - {len(quiz)} questions"):
                st.markdown(f"**Source:** {para_preview}")
                
                if st.button(f"▶️ Take This Quiz", key=f"lib_take_{idx}", use_container_width=True):
                    st.session_state.current_quiz_index = idx
                    st.session_state.user_answers = {}
                    st.session_state.show_results = False
                    st.session_state.page = "quiz"
                    st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# QUIZ PAGE
# -------------------------
elif st.session_state.page == "quiz":
    if st.session_state.current_quiz_index is None or st.session_state.current_quiz_index not in st.session_state.saved_quizzes:
        st.warning("⚠️ No quiz selected. Please go back and select a quiz.")
        if st.button("🏠 Go to Home", key="quiz_home_btn"):
            st.session_state.page = "main"
            st.rerun()
    else:
        quiz = st.session_state.saved_quizzes[st.session_state.current_quiz_index]
        
        col_main, col_side = st.columns([3, 1])
        
        with col_side:
            answered = len([k for k in st.session_state.user_answers.keys() if st.session_state.user_answers[k] is not None])
            st.markdown(f"""
            <div class='stats-box'>
                <div class='stats-number'>{answered}/{len(quiz)}</div>
                <div class='stats-label'>Answered</div>
            </div>
            """, unsafe_allow_html=True)
            st.progress(answered / len(quiz))
            
            if st.button("✅ Submit Quiz", key="submit_btn", use_container_width=True, disabled=(answered < len(quiz))):
                st.session_state.show_results = True
                st.rerun()
            
            if st.button("🔄 Reset", key="reset_btn", use_container_width=True):
                st.session_state.user_answers = {}
                st.session_state.show_results = False
                st.rerun()
            
            if st.button("🏠 Home", key="quiz_home_sidebar", use_container_width=True):
                st.session_state.page = "main"
                st.session_state.show_results = False
                st.rerun()
        
        with col_main:
            if not st.session_state.show_results:
                st.title("🎮 Quiz Time!")
                st.success("💡 **No API calls used!** Retake this quiz unlimited times!")
                
                for i, q in enumerate(quiz):
                    st.markdown(f"<div class='question-box'>", unsafe_allow_html=True)
                    st.markdown(f"**Question {i+1}**")
                    st.markdown(f"### {q['question']}")
                    
                    current = st.session_state.user_answers.get(i)
                    
                    answer = st.radio(
                        "Select your answer:",
                        options=q["options"],
                        index=None if current is None else (q["options"].index(current) if current in q["options"] else None),
                        key=f"radio_{i}",
                        label_visibility="collapsed"
                    )
                    
                    st.session_state.user_answers[i] = answer
                    st.markdown("</div>", unsafe_allow_html=True)
            
            else:
                st.title("📊 Quiz Results")
                
                score = 0
                total = len(quiz)
                
                for i, q in enumerate(quiz):
                    user_ans = st.session_state.user_answers.get(i)
                    correct_ans = q["answer"]
                    
                    if user_ans == correct_ans:
                        score += 1
                    
                    st.markdown(f"<div class='question-box'>", unsafe_allow_html=True)
                    
                    if user_ans == correct_ans:
                        st.success(f"✅ Question {i+1}: Correct!")
                    else:
                        st.error(f"❌ Question {i+1}: Incorrect")
                    
                    st.markdown(f"**{q['question']}**")
                    st.markdown(f"**Your answer:** {user_ans if user_ans else 'No answer'}")
                    
                    if user_ans != correct_ans:
                        st.markdown(f"**Correct answer:** {correct_ans}")
                    
                    if "explanation" in q and q["explanation"]:
                        with st.expander("💡 Explanation"):
                            st.info(q["explanation"])
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                
                percentage = (score / total) * 100
                
                if percentage >= 80:
                    emoji = "🏆"
                    message = "Excellent work!"
                elif percentage >= 60:
                    emoji = "👍"
                    message = "Good job!"
                else:
                    emoji = "📚"
                    message = "Keep studying!"
                
                st.markdown(f"""
                <div class='score-card'>
                    <h1>{emoji}</h1>
                    <h2>{message}</h2>
                    <h1 style='font-size: 3rem;'>{score}/{total}</h1>
                    <h3>{percentage:.1f}% Score</h3>
                </div>
                """, unsafe_allow_html=True)
                
                if not any(h.get("date") == datetime.now().strftime("%Y-%m-%d %H:%M") and h.get("quiz_index") == st.session_state.current_quiz_index for h in st.session_state.quiz_history):
                    st.session_state.quiz_history.append({
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "score": percentage,
                        "correct": score,
                        "total": total,
                        "quiz_index": st.session_state.current_quiz_index
                    })
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔄 Retake Quiz (FREE!)", key="try_again", use_container_width=True):
                        st.session_state.user_answers = {}
                        st.session_state.show_results = False
                        st.rerun()
                
                with col2:
                    if st.button("🏠 Back Home", key="results_home", use_container_width=True):
                        st.session_state.page = "main"
                        st.session_state.show_results = False
                        st.rerun()

# -------------------------
# HISTORY PAGE
# -------------------------
elif st.session_state.page == "history":
    st.title("📊 Quiz History")
    if not st.session_state.quiz_history:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.info("📝 No quiz history yet. Complete a quiz to see your progress!")
        if st.button("🏠 Go to Home", key="history_home", use_container_width=True):
            st.session_state.page = "main"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class='stats-box'>
                <div class='stats-number'>{len(st.session_state.quiz_history)}</div>
                <div class='stats-label'>Total Attempts</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            avg = sum(h["score"] for h in st.session_state.quiz_history) / len(st.session_state.quiz_history)
            st.markdown(f"""
            <div class='stats-box'>
                <div class='stats-number'>{avg:.1f}%</div>
                <div class='stats-label'>Average Score</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            best = max(h["score"] for h in st.session_state.quiz_history)
            st.markdown(f"""
            <div class='stats-box'>
                <div class='stats-number'>{best:.1f}%</div>
                <div class='stats-label'>Best Score</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("### Recent Attempts")
        for i, rec in enumerate(reversed(st.session_state.quiz_history)):
            idx = len(st.session_state.quiz_history) - i
            with st.expander(f"Attempt {idx} - {rec['date']} - Score: {rec['score']:.1f}%"):
                st.markdown(f"**Quiz:** Paragraph {rec.get('quiz_index', 'Unknown') + 1}")
                st.markdown(f"**Score:** {rec['correct']}/{rec['total']} ({rec['score']:.1f}%)")
                st.progress(rec['score'] / 100)
        if st.button("🗑️ Clear History", key="clear_history", use_container_width=True):
            st.session_state.quiz_history = []
            st.success("History cleared!")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)




