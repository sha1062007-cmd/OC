"""
Tests for LangGraph orchestration and conditional edge routing:
- Intent classification routing (explain | quiz | review | plan)
- The Adaptive Mastery Loop:
    Low score -> re-explain -> new quiz
    High score -> progress summary -> end
    Max iterations limit reached -> end
"""

import pytest
from app.graph import route_planner, route_evaluator, route_explainer, build_tutor_graph
from app.state import create_initial_state


def test_planner_routing_by_intent():
    """Verify route_planner maps intents to correct initial nodes."""
    # Intent: explain
    state_explain = create_initial_state(user_message="Explain Newton's third law")
    state_explain["intent"] = "explain"
    assert route_planner(state_explain) == "explainer"

    # Intent: quiz
    state_quiz = create_initial_state(user_message="Quiz me on photosynthesis")
    state_quiz["intent"] = "quiz"
    assert route_planner(state_quiz) == "quiz_master"

    # Intent: plan
    state_plan = create_initial_state(user_message="Make me a revision plan")
    state_plan["intent"] = "plan"
    assert route_planner(state_plan) == "revision_planner"

    # Intent: review
    state_review = create_initial_state(user_message="What topics am I weak in?")
    state_review["intent"] = "review"
    assert route_planner(state_review) == "revision_planner"


def test_evaluator_conditional_loop_low_score():
    """Verify low score below threshold (< 0.70) triggers adaptive loop back to Explainer."""
    state_low_score = create_initial_state(
        topic="Newton's Third Law",
        mastery_threshold=0.70,
        max_iterations=3
    )
    # Student scored 1 out of 3 = 0.33, on iteration 1
    state_low_score["score"] = 0.33
    state_low_score["iteration_count"] = 1

    decision = route_evaluator(state_low_score)
    assert decision == "explainer", "Low score on attempt 1 must route to Explainer for re-teaching!"


def test_evaluator_conditional_loop_mastery_achieved():
    """Verify high score (>= 0.70) terminates mastery loop with progress_summary."""
    state_mastery = create_initial_state(
        topic="Newton's Third Law",
        mastery_threshold=0.70,
        max_iterations=3
    )
    # Student scored 3 out of 3 = 1.0
    state_mastery["score"] = 1.0
    state_mastery["iteration_count"] = 1

    decision = route_evaluator(state_mastery)
    assert decision == "progress_summary", "Mastery score must route to progress_summary -> END!"


def test_evaluator_max_iterations_ceiling():
    """Verify that when max iterations (3) is reached, loop halts even if score is low."""
    state_capped = create_initial_state(
        topic="Newton's Third Law",
        mastery_threshold=0.70,
        max_iterations=3
    )
    # Student scored 0.40 but is already on iteration 3
    state_capped["score"] = 0.40
    state_capped["iteration_count"] = 3

    decision = route_evaluator(state_capped)
    assert decision == "progress_summary", "Max iterations ceiling must terminate loop to prevent infinite recursion!"


def test_explainer_routing_during_adaptive_loop():
    """Verify that Explainer routes to Quiz Master during an active loop, but ends on regular explanation."""
    # Case 1: Initial explanation from user prompt (iteration 0, no quiz yet)
    state_initial = create_initial_state(user_message="Explain photosynthesis")
    state_initial["iteration_count"] = 0
    state_initial["quiz"] = None
    assert route_explainer(state_initial) == "__end__"

    # Case 2: In-loop re-teaching (iteration 1, quiz exists)
    state_in_loop = create_initial_state(topic="Photosynthesis")
    state_in_loop["iteration_count"] = 1
    state_in_loop["quiz"] = {"questions": []}
    assert route_explainer(state_in_loop) == "quiz_master", "Re-teaching must route to Quiz Master for re-testing!"


def test_end_to_end_graph_compilation():
    """Verify that StateGraph compiles cleanly with all registered nodes and edges."""
    compiled_app = build_tutor_graph(checkpointer=None)
    assert compiled_app is not None
