"""
LangGraph Orchestration Graph for Adaptive Study Tutor.
Implements the exact state machine and conditional edges:
- Entry: Planner
- Routing by intent: Explainer | Quiz Master | Revision Planner
- Human-in-the-loop / student answers between Quiz Master and Evaluator
- Conditional Mastery Loop:
    If score < mastery_threshold (default 70%) AND iteration_count < max_iterations (default 3):
      -> Loop back to Explainer (re-teach weak subtopics)
      -> New Quiz Master (fresh questions, adjusted difficulty)
    Else:
      -> Progress Summary -> END
- Memory persistence across sessions via LangGraph SqliteSaver checkpointer (thread_id = student_id)
"""

import os
import sys
import sqlite3
from typing import Literal, Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.state import TutorState
from app.nodes.planner import planner_node
from app.nodes.explainer import explainer_node
from app.nodes.quiz_master import quiz_master_node
from app.nodes.evaluator import evaluator_node
from app.nodes.revision_planner import revision_planner_node
from mcp_server.server import call_tool_direct

DEFAULT_CHECKPOINT_DB = os.path.join(PROJECT_ROOT, "data", "checkpoints.db")


def progress_summary_node(state: TutorState) -> TutorState:
    """
    Final node reached when mastery is achieved or max iterations are reached.
    Generates a clean session progress summary.
    """
    score = state.get("score", 0.0)
    pct = round(score * 100.0, 1)
    threshold = state.get("mastery_threshold", 0.70)
    topic = state.get("topic", "General Science")
    iterations = state.get("iteration_count", 1)
    student_id = state.get("student_id", "demo_student")

    mastered = score >= threshold
    status_str = "Mastery Achieved!" if mastered else "Session Complete (Target for Spaced Review)"

    # Fetch updated weakness / review schedule from MCP
    try:
        import json
        raw_weak = call_tool_direct("get_weak_topics", student_id=student_id, limit=3)
        weak_list = json.loads(raw_weak).get("weak_topics", [])
        schedule_info = "Next review scheduled via SM-2 spaced repetition."
        for w in weak_list:
            if w.get("topic") == topic:
                schedule_info = f"Next spaced repetition review date: **{w.get('next_review_date', 'Tomorrow')}**"
                break
    except Exception:
        schedule_info = "Next spaced repetition review scheduled."

    summary_text = f"""### Session Progress Summary: {topic}
- **Student ID:** `{student_id}`
- **Overall Mastery Status:** **{status_str}**
- **Final Quiz Score:** **{pct}%** (Mastery Threshold: {int(threshold*100)}%)
- **Total Learning Cycles:** {iterations} iteration(s)
- **Spaced Repetition:** {schedule_info}

*Tip: Type 'What topics am I weak in?' to see your full history, or 'Make me a revision plan' to prepare for upcoming exams.*"""

    messages = state.get("messages", [])
    new_messages = messages + [{"role": "assistant", "content": summary_text}]

    return {
        **state,
        "messages": new_messages
    }


# Routing Functions
def route_planner(state: TutorState) -> Literal["explainer", "quiz_master", "revision_planner"]:
    """Routes based on intent classified by the Planner."""
    intent = state.get("intent", "explain")
    if intent == "quiz":
        return "quiz_master"
    elif intent in ("review", "plan"):
        return "revision_planner"
    return "explainer"


def route_explainer(state: TutorState) -> Literal["quiz_master", "__end__"]:
    """
    If in an active adaptive mastery cycle (iteration_count > 0), route to Quiz Master for a re-test.
    Otherwise, standard explanation ends turn.
    """
    iteration = state.get("iteration_count", 0)
    if iteration > 0 and state.get("quiz") is not None:
        return "quiz_master"
    return "__end__"


def route_evaluator(state: TutorState) -> Literal["explainer", "progress_summary"]:
    """
    The Core Adaptive Mastery Loop:
    If score < mastery_threshold AND iteration_count < max_iterations:
      -> Loop back to Explainer (re-teach weak subtopics)
    Else:
      -> Route to Progress Summary -> END
    """
    score = state.get("score", 1.0)
    threshold = state.get("mastery_threshold", 0.70)
    iteration = state.get("iteration_count", 1)
    max_iter = state.get("max_iterations", 3)

    if score < threshold and iteration < max_iter:
        return "explainer"
    return "progress_summary"


def build_tutor_graph(checkpointer: Optional[Any] = None) -> Any:
    """
    Constructs and compiles the StateGraph for Adaptive Study Tutor.
    """
    builder = StateGraph(TutorState)

    # 1. Register Nodes
    builder.add_node("planner", planner_node)
    builder.add_node("explainer", explainer_node)
    builder.add_node("quiz_master", quiz_master_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("revision_planner", revision_planner_node)
    builder.add_node("progress_summary", progress_summary_node)

    # 2. Entry Point
    builder.set_entry_point("planner")

    # 3. Edges from Planner
    builder.add_conditional_edges(
        "planner",
        route_planner,
        {
            "explainer": "explainer",
            "quiz_master": "quiz_master",
            "revision_planner": "revision_planner",
        }
    )

    # 4. Edges from Explainer (conditional for adaptive mastery loop)
    builder.add_conditional_edges(
        "explainer",
        route_explainer,
        {
            "quiz_master": "quiz_master",
            "__end__": END
        }
    )

    # 5. Quiz Master to Evaluator edge
    # Note: In human-in-the-loop workflows, interrupt can be handled here or by UI state machine
    builder.add_edge("quiz_master", "evaluator")

    # 6. Edges from Evaluator (Core Conditional Mastery Loop)
    builder.add_conditional_edges(
        "evaluator",
        route_evaluator,
        {
            "explainer": "explainer",
            "progress_summary": "progress_summary",
        }
    )

    # 7. Terminal Edges
    builder.add_edge("revision_planner", END)
    builder.add_edge("progress_summary", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


def get_sqlite_checkpointer(db_path: Optional[str] = None) -> SqliteSaver:
    """Returns a thread-safe SqliteSaver checkpointer instance."""
    path = db_path or DEFAULT_CHECKPOINT_DB
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    return SqliteSaver(conn)


# Compiled application instance with default SQLite checkpointer
def get_tutor_app(with_persistence: bool = True):
    if with_persistence:
        try:
            checkpointer = get_sqlite_checkpointer()
            return build_tutor_graph(checkpointer=checkpointer)
        except Exception as e:
            print(f"[Graph] Warning initializing SQLite checkpointer ({e}), using memory.")
    return build_tutor_graph()
