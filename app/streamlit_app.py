"""
Streamlit Web Application for Adaptive Study Tutor.
Features:
- Premium modern UI with interactive chat and study assistant
- In-chat interactive quiz answering with radio selection
- Visual Adaptive Mastery Loop indicator (attempts, re-teach trigger on <70% score)
- Progress Analytics Dashboard: Score trend chart (Plotly), Weak Topics table, SM-2 dates
- Personalized Study Plan generator
- Memory persistence across sessions with student_id threading
"""

import os
import sys
import json
import streamlit as st
import pandas as pd
import plotly.express as px

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.graph import get_tutor_app
from app.state import create_initial_state
from app.llm import check_api_keys, detect_active_provider
from app.seed_demo import seed_demo_student_history
from mcp_server.server import call_tool_direct
from mcp_server.db import get_student_history, get_weak_topics_query
from app.nodes.evaluator import evaluator_node
from app.nodes.explainer import explainer_node
from app.nodes.quiz_master import quiz_master_node
from app.graph import route_evaluator, progress_summary_node

# Page configuration
st.set_page_config(
    page_title="Adaptive Study Tutor | AI Learning System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1E88E5, #7E57C2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #666;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #1E88E5;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if "student_id" not in st.session_state:
    st.session_state.student_id = "demo_student"
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "👋 **Hello! I'm your Adaptive Study Tutor.**\n\nI can help you:\n- **Explain concepts** with verified textbook citations (`Explain Newton's third law with an example`)\n- **Quiz you** interactively on syllabus topics (`Quiz me on photosynthesis`)\n- **Diagnose weak areas** from your quiz records (`What topics am I weak in?`)\n- **Generate revision plans** with spaced repetition (`Make me a revision plan for next week`)\n\nWhat would you like to learn today?"
        }
    ]
if "active_quiz" not in st.session_state:
    st.session_state.active_quiz = None
if "quiz_state" not in st.session_state:
    st.session_state.quiz_state = None


# Sidebar
with st.sidebar:
    st.markdown("### 🎓 Student Profile")
    student_id = st.text_input("Student ID", value=st.session_state.student_id)
    if student_id != st.session_state.student_id:
        st.session_state.student_id = student_id
        st.session_state.active_quiz = None
        st.rerun()

    st.divider()

    # System Diagnostics
    st.markdown("### ⚙️ System Status")
    keys = check_api_keys(verbose=False)
    provider = detect_active_provider(keys)
    mock_mode = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")

    if mock_mode or provider == "mock":
        st.warning("⚡ **Mock LLM Mode**: Active (Deterministic offline demo)")
    else:
        st.success(f"🟢 **Provider**: {provider.upper()}")

    st.caption("RAG Store: `FAISS (MiniLM-L6-v2)`")
    st.caption("MCP Server: `FastMCP (stdio)`")
    st.caption("Checkpointer: `SqliteSaver`")

    st.divider()

    # Quick Actions
    st.markdown("### ⚡ Quick Actions")
    if st.button("🌱 Seed Demo Student History", use_container_width=True):
        seed_demo_student_history(st.session_state.student_id)
        st.success("Seeded sample quiz attempts for demo!")
        st.rerun()

    if st.button("🔄 Reset Chat Session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.active_quiz = None
        st.session_state.quiz_state = None
        st.rerun()

    st.divider()
    st.markdown("### 📚 Quick Prompts")
    if st.button("📖 Explain Newton's Third Law", use_container_width=True):
        st.session_state.prompt_to_submit = "Explain Newton's third law with an example."
    if st.button("📝 Quiz Me on Photosynthesis", use_container_width=True):
        st.session_state.prompt_to_submit = "Quiz me on photosynthesis."
    if st.button("📊 What topics am I weak in?", use_container_width=True):
        st.session_state.prompt_to_submit = "What topics am I weak in?"
    if st.button("📅 Make Revision Plan", use_container_width=True):
        st.session_state.prompt_to_submit = "Make me a revision plan for my exam next week."


# Main Layout Tabs
tab_chat, tab_analytics, tab_plan = st.tabs(["💬 Tutor Chat", "📊 Progress & Weak Topics", "🗓️ Revision Plan"])

# TAB 1: Chat Interface
with tab_chat:
    st.markdown('<div class="main-title">Adaptive Study Tutor</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Personalized syllabus coaching with RAG citations, MCP tools & adaptive mastery loops</div>', unsafe_allow_html=True)

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Handle Active Quiz State Machine (Human-in-the-loop answering)
    if st.session_state.active_quiz is not None:
        q_data = st.session_state.active_quiz.get("questions", [])
        st.info("📝 **Active Quiz in Progress! Select your answers below:**")

        with st.form("quiz_answer_form"):
            user_selected_answers = {}
            for idx, q in enumerate(q_data):
                st.markdown(f"**Question {idx+1}:** {q['question']}")
                opts = q.get("options", [])
                choice = st.radio(
                    f"Select answer for Q{idx+1}:",
                    options=opts,
                    key=f"quiz_opt_{idx}",
                    index=0
                )
                # Extract choice letter ('A', 'B', 'C', 'D')
                letter = choice[0] if choice else "A"
                user_selected_answers[str(idx)] = letter
                st.markdown("---")

            submit_quiz = st.form_submit_button("Submit Quiz Answers", use_container_width=True)

            if submit_quiz:
                # Student submitted answers
                state = st.session_state.quiz_state
                state["student_answers"] = user_selected_answers

                # Evaluate with Evaluator Node
                state = evaluator_node(state)
                eval_msg = state.get("messages", [])[-1]["content"]
                st.session_state.messages.append({"role": "assistant", "content": eval_msg})

                # Check mastery loop routing
                route_decision = route_evaluator(state)
                score_pct = int(state.get("score", 0.0) * 100)

                if route_decision == "explainer":
                    st.warning(f"⚠️ **Score ({score_pct}%) below mastery threshold (70%).** Triggering adaptive re-teaching...")
                    # Re-teach
                    state = explainer_node(state)
                    reteach_msg = state.get("messages", [])[-1]["content"]
                    st.session_state.messages.append({"role": "assistant", "content": reteach_msg})

                    # Present fresh quiz
                    state = quiz_master_node(state)
                    requiz_msg = state.get("messages", [])[-1]["content"]
                    st.session_state.messages.append({"role": "assistant", "content": requiz_msg})

                    # Keep quiz active for second attempt
                    st.session_state.active_quiz = state.get("quiz")
                    st.session_state.quiz_state = state
                else:
                    # Mastery achieved or max iterations reached
                    state = progress_summary_node(state)
                    summary_msg = state.get("messages", [])[-1]["content"]
                    st.session_state.messages.append({"role": "assistant", "content": summary_msg})

                    st.session_state.active_quiz = None
                    st.session_state.quiz_state = None

                st.rerun()

    # Input Box
    prompt = st.chat_input("Ask a question, request a quiz, or ask about weak topics...")
    if "prompt_to_submit" in st.session_state and st.session_state.prompt_to_submit:
        prompt = st.session_state.prompt_to_submit
        st.session_state.prompt_to_submit = None

    if prompt:
        # Append user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Build Graph and Invoke
        app = get_tutor_app(with_persistence=True)
        config = {"configurable": {"thread_id": st.session_state.student_id}}
        init_state = create_initial_state(
            student_id=st.session_state.student_id,
            user_message=prompt
        )

        with st.spinner("Processing with LangGraph Agent..."):
            out_state = app.invoke(init_state, config=config)

        quiz = out_state.get("quiz")
        if quiz and not out_state.get("quiz_completed"):
            # A quiz was generated and awaits student answers
            st.session_state.active_quiz = quiz
            st.session_state.quiz_state = out_state
            last_msg = out_state.get("messages", [])[-1]["content"]
            st.session_state.messages.append({"role": "assistant", "content": last_msg})
        else:
            last_msg = out_state.get("messages", [])[-1]["content"]
            st.session_state.messages.append({"role": "assistant", "content": last_msg})

        st.rerun()


# TAB 2: Analytics & Weak Topics Dashboard
with tab_analytics:
    st.subheader(f"📊 Progress Analytics for Student `{st.session_state.student_id}`")

    # Fetch records from SQLite
    history = get_student_history(st.session_state.student_id)
    weak_topics = get_weak_topics_query(st.session_state.student_id, limit=6)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Quizzes Attempted", len(history))
    with col2:
        avg_score = round(sum([h["percentage"] for h in history]) / len(history), 1) if history else 0.0
        st.metric("Overall Average Score", f"{avg_score}%")
    with col3:
        st.metric("Active Topics Tracked", len(weak_topics))

    st.markdown("---")

    col_chart, col_weak = st.columns([3, 2])

    with col_chart:
        st.markdown("#### 📈 Quiz Performance Trend")
        if history:
            df = pd.DataFrame(history)
            fig = px.line(
                df,
                x="timestamp",
                y="percentage",
                color="topic",
                markers=True,
                title="Score Progression Across Attempts (%)",
                labels={"percentage": "Score (%)", "timestamp": "Date & Time"},
                template="plotly_white"
            )
            fig.add_hline(y=70, line_dash="dash", line_color="green", annotation_text="Mastery (70%)")
            fig.update_yaxes(range=[0, 105])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No attempts recorded yet. Take a quiz or click 'Seed Demo Student History' to view trends!")

    with col_weak:
        st.markdown("#### 🎯 Weak Topics & Review Schedule")
        if weak_topics:
            for w in weak_topics:
                pct = w["avg_percentage"]
                status_color = "red" if pct < 60 else ("orange" if pct < 75 else "green")
                st.markdown(f"**{w['topic']}**")
                st.progress(min(1.0, max(0.0, pct / 100.0)))
                st.caption(f"Average: **{pct}%** ({w['attempts']} attempts) | 📅 Review: **{w['next_review_date']}**")
                st.markdown("---")
        else:
            st.info("No weak topics detected.")

    st.markdown("#### 📋 Detailed Quiz History Table")
    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True)


# TAB 3: Revision Plan
with tab_plan:
    st.subheader(f"🗓️ Spaced Repetition Revision Plan for `{st.session_state.student_id}`")
    exam_days = st.slider("Days remaining until examination:", min_value=1, max_value=14, value=7)

    if st.button("Generate Dynamic Study Schedule", type="primary"):
        from app.nodes.revision_planner import revision_planner_node
        dummy_state = create_initial_state(
            student_id=st.session_state.student_id,
            user_message=f"Make me a revision plan for my exam in {exam_days} days."
        )
        dummy_state["exam_days_left"] = exam_days
        plan_out = revision_planner_node(dummy_state)
        st.markdown(plan_out["revision_plan"])
    else:
        st.info("Adjust your exam timeline and click 'Generate Dynamic Study Schedule' to create a prioritized timetable.")
