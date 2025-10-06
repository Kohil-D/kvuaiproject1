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
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a helpful quiz generator that returns only valid JSON responses."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 1500
    }

    try:
        response = requests.post(OPENAI_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code == 429:
            return None, "Rate limit exceeded. Please wait a moment and try again."
        
        if response.status_code == 401:
            return None, "❌ Invalid API Key. Please check your configuration."
        
        if response.status_code == 403:
            return None, "❌ Access Denied. Please ensure billing is set up at https://platform.openai.com/account/billing"
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            return None, f"API Error {response.status_code}: {error_message}"

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
        return None, "⏱️ Request timed out."
    except requests.exceptions.RequestException as e:
        return None, f"🌐 Network error: {str(e)}"
    except Exception as e:
        return None, f"❌ Unexpected error: {str(e)}"

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
        "total_questions_answered": 0,
        "total_correct_answers": 0
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
# CSS Styling
# -------------------------
st.markdown("""
<style>
    .stApp {
        background: #0f172a;
        color: #f1f5f9;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .api-badge {
        position: fixed;
        top: 10px;
        left: 10px;
        background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 600;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }
    
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
    
    .mini-stat {
        background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 0.5rem;
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
    
    .history-item {
        background: #1e293b;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #10b981;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# API Usage Badge (Top Left)
st.markdown(f'<div class="api-badge">🤖 API Calls: {st.session_state.api_calls_made}</div>', unsafe_allow_html=True)

# -------------------------
# Sidebar Navigation
# -------------------------
with st.sidebar:
    st.title("📌NAV")
    
    st.markdown("---")
    
    # Navigation Buttons
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.page = "main"
        st.session_state.show_results = False
        st.rerun()
    
    if st.button("📚 My Quizzes", use_container_width=True):
        st.session_state.page = "quiz_library"
        st.rerun()
    
    if st.button("📊 Statistics", use_container_width=True):
        st.session_state.page = "stats"
        st.rerun()
    
    if st.button("📜 History", use_container_width=True):
        st.session_state.page = "history"
        st.rerun()
    
    st.markdown("---")
    
    # Quick Stats
    st.subheader("📈 Quick Stats")
    
    accuracy = 0
    if st.session_state.total_questions_answered > 0:
        accuracy = (st.session_state.total_correct_answers / st.session_state.total_questions_answered) * 100
    
    st.markdown(f"""
    <div class='mini-stat'>
        <div style='font-size: 1.5rem; font-weight: bold; color: #10b981;'>{len(st.session_state.saved_quizzes)}</div>
        <div style='font-size: 0.8rem; color: #cbd5e1;'>Total Quizzes</div>
    </div>
    <div class='mini-stat'>
        <div style='font-size: 1.5rem; font-weight: bold; color: #10b981;'>{st.session_state.total_questions_answered}</div>
        <div style='font-size: 0.8rem; color: #cbd5e1;'>Questions Answered</div>
    </div>
    <div class='mini-stat'>
        <div style='font-size: 1.5rem; font-weight: bold; color: #10b981;'>{accuracy:.1f}%</div>
        <div style='font-size: 0.8rem; color: #cbd5e1;'>Overall Accuracy</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Settings
    st.subheader("⚙️ Settings")
    num_q = st.slider("Questions per quiz", 3, 10, st.session_state.num_questions)
    st.session_state.num_questions = num_q
    
    st.markdown("---")
    
    # Quick Actions
    st.subheader("⚡ Quick Actions")
    
    if st.button("🗑️ Clear All Data", use_container_width=True):
        if st.session_state.paragraphs or st.session_state.saved_quizzes:
            st.session_state.paragraphs = []
            st.session_state.saved_quizzes = {}
            st.session_state.quiz_history = []
            st.success("🗑️ All data cleared!")
            st.rerun()
    
    if st.button("🔄 Reset Stats", use_container_width=True):
        st.session_state.api_calls_made = 0
        st.session_state.total_questions_answered = 0
        st.session_state.total_correct_answers = 0
        st.success("📊 Stats reset!")
        st.rerun()
    
    if st.session_state.saved_quizzes:
        if st.button("🎲 Random Quiz", use_container_width=True):
            random_idx = random.choice(list(st.session_state.saved_quizzes.keys()))
            st.session_state.current_quiz_index = random_idx
            st.session_state.user_answers = {}
            st.session_state.show_results = False
            st.session_state.page = "quiz"
            st.rerun()
    
    st.markdown("---")
    st.caption("💡 Powered by OpenAI GPT-4o-mini")
    st.caption("app.version-2.04.46")
    st.caption("🏎️Created by Kohil and Team in the supervision of Jitumani Das sir (ai Team KVU)")
    st.caption(" TEAM - 1. Kohil
                       2. Adarsh
                       3. Nihersa
                       4. Rituraj ")
# -------------------------
# MAIN PAGE
# -------------------------
if st.session_state.page == "main":
    # Hero Section
    st.markdown("""
    <div style='text-align: center; padding: 2rem 0 1rem 0;'>
        <h1 style='font-size: 3rem; font-weight: 800; background: linear-gradient(135deg, #10b981 0%, #34d399 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem;'>
            Smart Study Partner
        </h1>
        <p style='font-size: 1.2rem; color: #94a3b8; margin-bottom: 2rem;'>
            Turn your notes into powerful learning tools with AI-powered quizzes
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Feature highlights
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style='text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #1e293b 0%, #334155 100%); border-radius: 12px; border: 1px solid #10b981;'>
            <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>⚡</div>
            <h3 style='color: #10b981; margin-bottom: 0.5rem;'>Instant Generation</h3>
            <p style='color: #cbd5e1; font-size: 0.9rem;'>Create quizzes in seconds from any text</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #1e293b 0%, #334155 100%); border-radius: 12px; border: 1px solid #10b981;'>
            <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🎯</div>
            <h3 style='color: #10b981; margin-bottom: 0.5rem;'>Smart Questions</h3>
            <p style='color: #cbd5e1; font-size: 0.9rem;'>AI generates relevant, challenging questions</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #1e293b 0%, #334155 100%); border-radius: 12px; border: 1px solid #10b981;'>
            <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>📊</div>
            <h3 style='color: #10b981; margin-bottom: 0.5rem;'>Track Progress</h3>
            <p style='color: #cbd5e1; font-size: 0.9rem;'>Monitor your learning journey</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Input section with enhanced design
    st.markdown("""
    <div style='background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 2rem; border-radius: 16px; border: 2px solid #10b981; box-shadow: 0 8px 24px rgba(16, 185, 129, 0.2);'>
        <h2 style='color: #10b981; margin-bottom: 1rem; display: flex; align-items: center;'>
            <span style='font-size: 1.5rem; margin-right: 0.5rem;'>📝</span>
            Create Your Quiz
        </h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='margin-top: -1rem;'>", unsafe_allow_html=True)
    user_input = st.text_area(
        "Paste your study material below",
        height=180,
        placeholder="📚 Paste your notes, textbook paragraphs, or any study material here...\n\n💡 Tip: The more detailed your text, the better the questions!\n\n✨ Supports up to 2000 characters",
        max_chars=2000,
        key="main_input",
        label_visibility="collapsed"
    )
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Character counter
    char_count = len(user_input) if user_input else 0
    progress_color = "#10b981" if char_count < 1800 else "#f59e0b" if char_count < 2000 else "#ef4444"
    st.markdown(f"""
    <div style='text-align: right; color: {progress_color}; font-size: 0.85rem; margin-top: -0.5rem; margin-bottom: 1rem;'>
        {char_count} / 2000 characters
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("➕ Save Material", key="add_para", use_container_width=True):
            if user_input and user_input.strip():
                st.session_state.paragraphs.append(user_input.strip())
                st.success("✅ Material saved successfully!")
                st.rerun()
            else:
                st.warning("⚠️ Please enter some text first!")
    
    with col2:
        generate_disabled = not (user_input and user_input.strip())
        if st.button("⚡ Generate Quiz Now", key="add_gen", use_container_width=True, type="primary", disabled=generate_disabled):
            st.session_state.paragraphs.append(user_input.strip())
            idx = len(st.session_state.paragraphs) - 1
            
            with st.spinner("🤖 AI is crafting your questions..."):
                quiz, error = generate_quiz(user_input.strip(), st.session_state.num_questions)
            
            if error:
                st.error(f"❌ {error}")
            elif quiz:
                st.session_state.saved_quizzes[idx] = quiz
                st.session_state.api_calls_made += 1
                st.success(f"✅ Generated {len(quiz)} questions! Scroll down to take the quiz.")
                st.rerun()
    
    with col3:
        if st.session_state.paragraphs:
            if st.button("🗑️ Clear All", key="clear_all", use_container_width=True):
                st.session_state.paragraphs = []
                st.session_state.saved_quizzes = {}
                st.success("🗑️ All cleared!")
                st.rerun()
    
    # Saved paragraphs
    if st.session_state.paragraphs:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader(f"📚 My Study Materials ({len(st.session_state.paragraphs)})")
        
        for i, para in enumerate(st.session_state.paragraphs):
            para_preview = para[:120] + "..." if len(para) > 120 else para
            
            if i in st.session_state.saved_quizzes:
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    st.markdown(f"**✅ Material {i+1}:** {para_preview}")
                    st.caption(f"{len(st.session_state.saved_quizzes[i])} questions ready • {len(para)} characters")
                with col2:
                    if st.button("📖 Take", key=f"take_quiz_{i}", use_container_width=True):
                        st.session_state.current_quiz_index = i
                        st.session_state.user_answers = {}
                        st.session_state.show_results = False
                        st.session_state.page = "quiz"
                        st.rerun()
                with col3:
                    if st.button("🔄 Regen", key=f"regen_quiz_{i}", use_container_width=True):
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
                with col4:
                    if st.button("🗑️", key=f"del_{i}", use_container_width=True):
                        del st.session_state.paragraphs[i]
                        if i in st.session_state.saved_quizzes:
                            del st.session_state.saved_quizzes[i]
                        st.success("🗑️ Deleted!")
                        st.rerun()
            else:
                col1, col2, col3 = st.columns([4, 1, 1])
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
                            st.success("Quiz ready!")
                            st.rerun()
                with col3:
                    if st.button("🗑️", key=f"del2_{i}", use_container_width=True):
                        del st.session_state.paragraphs[i]
                        st.success("🗑️ Deleted!")
                        st.rerun()
            
            st.markdown("---")
        
        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# QUIZ LIBRARY PAGE
# -------------------------
elif st.session_state.page == "quiz_library":
    st.title("📚 My Quiz Library")
    st.markdown("### All your generated quizzes in one place!")
    
    if st.button("🏠 Go Home", use_container_width=True):
        st.session_state.page = "main"
        st.rerun()
    
    if not st.session_state.saved_quizzes:
        st.info("No quizzes generated yet. Go to Home and create some!")
    else:
        st.markdown(f"**Total Quizzes:** {len(st.session_state.saved_quizzes)}")
        
        for idx, quiz in st.session_state.saved_quizzes.items():
            para_preview = st.session_state.paragraphs[idx][:100] + "..." if len(st.session_state.paragraphs[idx]) > 100 else st.session_state.paragraphs[idx]
            
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"### 📖 Quiz {idx+1}")
                st.markdown(f"**Questions:** {len(quiz)}")
                st.markdown(f"**Source:** {para_preview}")
            
            with col2:
                if st.button(f"▶️ Take", key=f"lib_take_{idx}", use_container_width=True):
                    st.session_state.current_quiz_index = idx
                    st.session_state.user_answers = {}
                    st.session_state.show_results = False
                    st.session_state.page = "quiz"
                    st.rerun()
                
                if st.button(f"🗑️ Delete", key=f"libdel_{idx}", use_container_width=True):
                    del st.session_state.saved_quizzes[idx]
                    del st.session_state.paragraphs[idx]
                    st.success("🗑️ Quiz deleted!")
                    st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# STATISTICS PAGE
# -------------------------
elif st.session_state.page == "stats":
    st.title("📊 Your Statistics")
    
    accuracy = 0
    if st.session_state.total_questions_answered > 0:
        accuracy = (st.session_state.total_correct_answers / st.session_state.total_questions_answered) * 100
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class='stats-box'>
            <div class='stats-number'>{st.session_state.api_calls_made}</div>
            <div class='stats-label'>API Calls Made</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class='stats-box'>
            <div class='stats-number'>{len(st.session_state.saved_quizzes)}</div>
            <div class='stats-label'>Quizzes Generated</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class='stats-box'>
            <div class='stats-number'>{len(st.session_state.quiz_history)}</div>
            <div class='stats-label'>Quizzes Taken</div>
        </div>
        """, unsafe_allow_html=True)
    
    col4, col5 = st.columns(2)
    
    with col4:
        st.markdown(f"""
        <div class='stats-box'>
            <div class='stats-number'>{st.session_state.total_questions_answered}</div>
            <div class='stats-label'>Total Questions Answered</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class='stats-box'>
            <div class='stats-number'>{accuracy:.1f}%</div>
            <div class='stats-label'>Overall Accuracy</div>
        </div>
        """, unsafe_allow_html=True)
    
    if st.session_state.quiz_history:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📈 Performance Over Time")
        
        scores = [h['score'] for h in st.session_state.quiz_history]
        avg_score = sum(scores) / len(scores)
        
        st.markdown(f"**Average Score:** {avg_score:.1f}%")
        st.markdown(f"**Best Score:** {max(scores):.1f}%")
        st.markdown(f"**Latest Score:** {scores[-1]:.1f}%")
        
        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# HISTORY PAGE
# -------------------------
elif st.session_state.page == "history":
    st.title("📜 Quiz History")
    
    if st.button("🏠 Go Home", use_container_width=True):
        st.session_state.page = "main"
        st.rerun()
    
    if not st.session_state.quiz_history:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.info("📝 No quiz history yet. Complete a quiz to see your progress!")
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
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.subheader("### Recent Attempts")
        for i, rec in enumerate(reversed(st.session_state.quiz_history)):
            idx = len(st.session_state.quiz_history) - i
            st.markdown(f"""
            <div class='history-item'>
                <h4>📝 Attempt #{idx}</h4>
                <p><strong>Date:</strong> {rec['date']}</p>
                <p><strong>Quiz:</strong> Material {rec.get('quiz_index', 'Unknown') + 1}</p>
                <p><strong>Score:</strong> {rec['correct']}/{rec['total']} ({rec['score']:.1f}%)</p>
            </div>
            """, unsafe_allow_html=True)
        
        if st.button("🗑️ Clear History", key="clear_history", use_container_width=True):
            st.session_state.quiz_history = []
            st.success("History cleared!")
            st.rerun()

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
            # Count answered questions accurately
            answered = sum(1 for i in range(len(quiz)) if st.session_state.user_answers.get(i) is not None)
            
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
            
            if st.button("📚 My Quizzes", key="quiz_lib_sidebar", use_container_width=True):
                st.session_state.page = "quiz_library"
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
                    
                    # Update answer immediately when selected
                    if answer is not None:
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
                
                # Update global stats
                st.session_state.total_questions_answered += total
                st.session_state.total_correct_answers += score
                
                # Add to history (avoid duplicates)
                if not any(h.get("date") == datetime.now().strftime("%Y-%m-%d %H:%M") and h.get("quiz_index") == st.session_state.current_quiz_index for h in st.session_state.quiz_history):
                    st.session_state.quiz_history.append({
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "score": percentage,
                        "correct": score,
                        "total": total,
                        "quiz_index": st.session_state.current_quiz_index
                    })
                
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
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("🔄 Retake", key="try_again", use_container_width=True):
                        st.session_state.user_answers = {}
                        st.session_state.show_results = False
                        st.rerun()
                
                with col2:
                    if st.button("📚 My Quizzes", key="results_lib", use_container_width=True):
                        st.session_state.page = "quiz_library"
                        st.session_state.show_results = False
                        st.rerun()
                
                with col3:
                    if st.button("🏠 Home", key="results_home", use_container_width=True):
                        st.session_state.page = "main"
                        st.session_state.show_results = False
                        st.rerun()






