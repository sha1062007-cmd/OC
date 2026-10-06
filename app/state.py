"""
Shared State definition for the Adaptive Study Tutor LangGraph Agent.
Contains all required fields from the specification:
- student_id: str
- messages: List[Dict[str, Any]]
- intent: str ("explain" | "quiz" | "review" | "plan")
- topic: str
- difficulty: str ("easy" | "medium" | "hard")
- retrieved_context: List[Dict[str, Any]]
- explanation: str
- quiz: Dict[str, Any]
- student_answers: Dict[str, str]
- score: float
- weak_topics: List[Dict[str, Any]]
- iteration_count: int
- mastery_threshold: float
- max_iterations: int
- revision_plan: str
- exam_days_left: int
"""

from typing import TypedDict, List, Dict, Any, Optional


class TutorState(TypedDict, total=False):
    student_id: str
    messages: List[Dict[str, Any]]
    intent: str
    topic: str
    difficulty: str
    retrieved_context: List[Dict[str, Any]]
    explanation: str
    quiz: Optional[Dict[str, Any]]
    student_answers: Optional[Dict[str, str]]
    score: float
    weak_topics: List[Dict[str, Any]]
    iteration_count: int
    mastery_threshold: float
    max_iterations: int
    revision_plan: str
    exam_days_left: int
    supplementary_web: Optional[List[Dict[str, str]]]
    evaluation_feedback: Optional[str]
    quiz_completed: bool


def create_initial_state(
    student_id: str = "demo_student",
    user_message: str = "",
    topic: str = "",
    mastery_threshold: float = 0.70,
    max_iterations: int = 3
) -> TutorState:
    """Helper to initialize fresh state dictionary with sensible defaults."""
    messages = []
    if user_message:
        messages.append({"role": "user", "content": user_message})

    return {
        "student_id": student_id,
        "messages": messages,
        "intent": "explain",
        "topic": topic,
        "difficulty": "medium",
        "retrieved_context": [],
        "explanation": "",
        "quiz": None,
        "student_answers": {},
        "score": 0.0,
        "weak_topics": [],
        "iteration_count": 0,
        "mastery_threshold": mastery_threshold,
        "max_iterations": max_iterations,
        "revision_plan": "",
        "exam_days_left": 7,
        "supplementary_web": [],
        "evaluation_feedback": "",
        "quiz_completed": False
    }
