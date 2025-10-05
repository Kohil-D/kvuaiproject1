import streamlit as st
import requests
import json
import random
from datetime import datetime

# -------------------------
# CONFIGURATION - OpenAI API Key
# -------------------------
try:
    API_KEY = st.secrets["OPENAI_API_KEY"]
except:
    st.error("🚨 No API key found!")
    st.warning("""
    **Please create `.streamlit/secrets.toml` with your OpenAI API key:**
    
    ```
    OPENAI_API_KEY = "sk-your-openai-api-key-here"
    ```
    
    Get your API key at: https://platform.openai.com/api-keys
    """)
    st.stop()

# OpenAI API endpoint
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# -------------------------
# Backend: OpenAI Quiz Generator
# -------------------------
def generate_quiz(text, num_questions=5):
    """Generate quiz questions using OpenAI API"""
    if not text or not text.strip():
        return None, "Please provide text to generate questions from."
    
    if not API_KEY:
        return None, "API key is required."
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # Optimized prompt for OpenAI
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
        "model": "gpt-3.5-turbo",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful quiz generator that returns only valid JSON responses."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.5,
        "max_tokens": 2048
    }

    try:
        response = requests.post(OPENAI_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            
            if response.status_code == 401:
                return None, "❌ Invalid API key. Please check your OpenAI API key."
            elif response.status_code == 429:
                return None, "⏳ Rate limit exceeded. Please wait a moment and try again."
            elif response.status_code == 403:
                return None, "❌ Access denied. Check your API key permissions."
            else:
                return None, f"❌ API Error {response.status_code}: {error_message}"

        result = response.json()
        
        # Extract text from OpenAI's response structure
        try:
            generated_text = result['choices'][0]['message']['content']
        except (KeyError, IndexError):
            return None, "Failed to parse OpenAI response structure."
        
        # Clean markdown formatting if present
        generated_text = generated_text.strip()
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
            # Try to extract JSON if wrapped in text
            import re
            match = re.search(r'\{.*\}', generated_text, re.DOTALL)
            if match:
                try:
                    quiz_data = json.loads(match.group())
                except:
                    return None, "Failed to parse quiz response. Please try again."
            else:
                return None, "Failed to parse quiz response. Please try again."

        quiz_questions = quiz_data.get("quiz", [])
        
        if not quiz_questions:
            return None, "No questions generated. Try with more detailed text."
        
        # Shuffle options while preserving correct answer
        for q in quiz_questions:
            if "options" in q and "answer" in q and "question" in q:
                correct = q["answer"]
                random.shuffle(q["options"])
                q["answer"] = correct
            else:
                return None, "Invalid question format received."

        return quiz_questions, None
        
    except requests.exceptions.Timeout:
        return None, "⏱️ Request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return None, f"🌐 Network error: {str(e)}"
    except Exception as e:
        return None, f"❌ Unexpected error: {str(e)}"

# -------------------------
# Initialize Session State
# -------------------------
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        "page": "main",
        "paragraphs": [],
        "saved_quizzes": {},
        "current_quiz_index": None,
        "user_answers": {},
        "show_results": False,
        "quiz_history": [],
        "dark_mode": True,
        "num_questions": 5,
        "api_calls_made": 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# -------------------------
# Page Configuration
# -------------------------
st.set_page_config(
    page_title="📘 Smart Study Partner - OpenAI",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# Dynamic Theme System
# -------------------------
def get_colors():
    """Get color scheme based on dark/light mode"""
    if st.session_state.dark_mode:
        return {
            'bg_primary': '#0f172a',
            'bg_secondary': '#1e293b',
            'bg_card': '#1e293b',
            'bg_card_hover': '#334155',
            'text_primary': '#f1f5f9',
            'text_secondary': '#cbd5e1',
            'text_tertiary': '#94a3b8',
            'accent_primary': '#10b981',
            'accent_secondary': '#34d399',
            'border_color': '#334155',
            'shadow': 'rgba(0, 0, 0, 0.5)',
        }
    else:
        return {
            'bg_primary': '#f1f5f9',
            'bg_secondary': '#ffffff',
            'bg_card': '#ffffff',
            'bg_card_hover': '#f8fafc',
            'text_primary': '#0f172a',
            'text_secondary': '#1e293b',
            'text_tertiary': '#475569',
            'accent_primary': '#059669',
            'accent_secondary': '#10b981',
            'border_color': '#cbd5e1',
            'shadow': 'rgba(0, 0, 0, 0.15)',
        }

colors = get_colors()

# -------------------------
# CSS Styling
# -------------------------
st.markdown(f"""
<style>
    .stApp {{
        background: {colors['bg_primary']};
        color: {colors['text_primary']};
    }}
    
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    
    .card {{
        background: {colors['bg_card']};
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid {colors['border_color']};
        box-shadow: 0 4px 12px {colors['shadow']};
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
    }}
    
    .card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 16px {colors['shadow']};
    }}
    
    .question-box {{
        background: {colors['bg_card']};
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid {colors['accent_primary']};
        border: 1px solid {colors['border_color']};
        margin-bottom: 1.5rem;
        color: {colors['text_primary']};
    }}
    
    .stats-box {{
        background: {colors['bg_card']};
        padding: 1.5rem;
        border-radius: 12px;
        border: 2px solid {colors['accent_primary']};
        text-align: center;
        margin-bottom: 1rem;
    }}
    
    .stats-number {{
        font-size: 2rem;
        font-weight: bold;
        color: {colors['accent_primary']};
    }}
    
    .stats-label {{
        font-size: 0.9rem;
        color: {colors['text_secondary']};
        font-weight: 500;
    }}
    
    .stButton > button {{
        background: linear-gradient(135deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%);
        color: white;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
        width: 100%;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
    }}
    
    .stProgress > div > div > div > div {{
        background: linear-gradient(90deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%);
    }}
    
    .stRadio > div > label {{
        background: {colors['bg_secondary']};
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: 2px solid {colors['border_color']};
        margin-bottom: 0.5rem;
        color: {colors['text_primary']};
        cursor: pointer;
        transition: all 0.2s ease;
    }}
    
    .stRadio > div > label:hover {{
        border-color: {colors['accent_primary']};
        background: {colors['bg_card_hover']};
        transform: translateX(4px);
    }}
    
    .stTextArea > div > div > textarea,
    .stTextInput > div > div > input {{
        background: {colors['bg_secondary']};
        color: {colors['text_primary']};
        border: 1px solid {colors['border_color']};
        border-radius: 8px;
    }}
    
    section[data-testid="stSidebar"] {{
        background: {colors['bg_secondary']};
        border-right: 1px solid {colors['border_color']};
    }}
    
    h1, h2, h3, h4, h5, h6 {{
        color: {colors['text_primary']};
    }}
    
    p {{
        color: {colors['text_secondary']};
    }}
    
    .score-card {{
        background: linear-gradient(135deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%);
        padding: 2rem;
        border-radius: 16px;
        text-align: center;
        color: white;
        margin: 2rem 0;
    }}
    
    .openai-badge {{
        background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 1rem;
    }}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Sidebar Navigation
# -------------------------
with st.sidebar:
    st.title("📌 Navigation")
    
    # OpenAI Badge
    st.markdown('<div class="openai-badge">🤖 Powered by OpenAI GPT-3.5</div>', unsafe_allow_html=True)
    
    # Theme toggle
    if st.button("🌙 Dark" if not st.session_state.dark_mode else "☀️ Light", key="theme_btn", use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()
    
    st.markdown("---")
    
    # Settings
    st.subheader("⚙️ Settings")
    num_q = st.slider("Questions per quiz", 3, 15, st.session_state.num_questions, key="num_q_slider")
    st.session_state.num_questions = num_q
    
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
    
    st.info("💡 **Tip:** Each quiz generation uses 1 API call. Retaking quizzes is free!")
    
    st.markdown("---")
    
    # Navigation buttons
    if st.button("🏠 Home", key="nav_home", use_container_width=True):
        st.session_state.page = "main"
        st.session_state.show_results = False
        st.rerun()
    
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
    st.markdown('<div class="openai-badge">🤖 Powered by OpenAI GPT-3.5 Turbo</div>', unsafe_allow_html=True)
    
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
    
    # Saved paragraphs - Simplified view
    if st.session_state.paragraphs:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"📚 My Study Materials ({len(st.session_state.paragraphs)})")
        
        for i, para in enumerate(st.session_state.paragraphs):
            # Create a compact card for each paragraph
            para_preview = para[:120] + "..." if len(para) > 120 else para
            
            # Check if quiz already generated
            if i in st.session_state.saved_quizzes:
            # Saved paragraphs - Simplified view
if st.session_state.paragraphs:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader(f"📚 My Study Materials ({len(st.session_state.paragraphs)})")
    
    for i, para in enumerate(st.session_state.paragraphs):
        para_preview = para[:120] + "..." if len(para) > 120 else para
        
        # Check if quiz already generated
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
                if st.button("🔄", key=f"regen_quiz_{i}", use_container_width=True, help="Regenerate quiz"):
                    del st.session_state.saved_quizzes[i]
                    with st.spinner("🤖 Regenerating..."):
                        quiz, error = generate_quiz(para, st.session_state.num_questions)
                    
                    if error:
                        st.error(f"{error}")
                    elif quiz:
                        st.session_state.saved_quizzes[i] = quiz
                        st.session_state.api_calls_made += 1
                        st.success("New quiz ready!")
                        st.rerun()
        else:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**📄 Material {i+1}:** {para_preview}")
                st.caption(f"Ready to generate • {len(para)} characters")
            with col2:
                if st.button("⚡ Generate", key=f"gen_quiz_{i}", use_container_width=True, type="primary"):
                    with st.spinner("🤖 Creating quiz..."):
                        quiz, error = generate_quiz(para, st.session_state.num_questions)
                    
                    if error:
                        st.error(f"{error}")
                    elif quiz:
                        st.session_state.saved_quizzes[i] = quiz
                        st.session_state.api_calls_made += 1
                        st.success("Quiz ready! Click 'Take Quiz' to start.")
                        st.rerun()
        
        # Optional: Show full text in expander below
        if len(para) > 120:
            with st.expander(f"View full text"):
                st.text(para)
        
        st.markdown("---")
    
    st.markdown("</div>", unsafe_allow_html=True)  
        
        
# -------------------------
# QUIZ LIBRARY PAGE
# -------------------------
elif st.session_state.page == "quiz_library":
    st.title("📚 My Quiz Library")
    st.markdown("### All your generated quizzes in one place!")
    
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
            # Progress
            answered = len([k for k in st.session_state.user_answers.keys() if st.session_state.user_answers[k] is not None])
            st.markdown(f"""
            <div class='stats-box'>
                <div class='stats-number'>{answered}/{len(quiz)}</div>
                <div class='stats-label'>Answered</div>
            </div>
            """, unsafe_allow_html=True)
            st.progress(answered / len(quiz))
            
            # Submit button
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
                # Quiz questions
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
                # Results
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
                
                # Score card
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
                
                # Save to history
                if not any(h.get("date") == datetime.now().strftime("%Y-%m-%d %H:%M") and h.get("quiz_index") == st.session_state.current_quiz_index for h in st.session_state.quiz_history):
                    st.session_state.quiz_history.append({
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "score": percentage,
                        "correct": score,
                        "total": total,
                        "quiz_index": st.session_state.current_quiz_index
                    })
                
                # Action buttons
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
        
        # Summary stats
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
