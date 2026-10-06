"""
Planner Node:
Classifies the request intent (explain | quiz | review | plan) from the user's message
AND the student's history (calls get_weak_topics MCP tool).
Extracts topic, difficulty, and exam timeline.
Outputs structured classification.
"""

import json
import os
import re
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.state import TutorState
from app.llm import get_chat_model
from mcp_server.server import call_tool_direct
from app.guardrails import moderate_content, sanitize_input_prompt_injection


class PlannerOutput(BaseModel):
    intent: str = Field(description="One of: 'explain', 'quiz', 'review', 'plan'")
    topic: str = Field(description="The primary topic identified")
    difficulty: str = Field(default="medium", description="Difficulty: 'easy', 'medium', or 'hard'")
    exam_days_left: int = Field(default=7, description="Number of days until the exam, default 7")
    reasoning: str = Field(default="", description="Reasoning for this classification")


def planner_node(state: TutorState) -> TutorState:
    """
    Analyzes user message and student weak topics to plan subsequent routing.
    """
    messages = state.get("messages", [])
    user_message = state.get("user_query", "").strip()
    if not user_message:
        for m in reversed(messages):
            if m.get("role") == "user":
                user_message = m.get("content", "")
                break

    # Guardrail: Check content moderation
    is_safe, reason = moderate_content(user_message)
    if not is_safe:
        return {
            **state,
            "intent": "explain",
            "explanation": f"I cannot assist with this request. Moderation policy flag: {reason}.",
            "messages": messages + [{"role": "assistant", "content": f"Safety Notice: {reason}."}]
        }

    # Sanitize input against prompt injection
    sanitized_query = sanitize_input_prompt_injection(user_message)

    # Fetch weak topics from MCP to give the planner context
    student_id = state.get("student_id", "demo_student")
    try:
        raw_weak = call_tool_direct("get_weak_topics", student_id=student_id, limit=5)
        weak_data = json.loads(raw_weak)
        weak_topics = weak_data.get("weak_topics", [])
    except Exception as e:
        weak_topics = []

    weak_summary = ", ".join([f"{w['topic']} (Avg: {w['avg_percentage']}%)" for w in weak_topics]) if weak_topics else "None recorded yet"

    # Fast deterministic classification for common keywords
    q_lower = sanitized_query.lower()

    if any(k in q_lower for k in ["quiz me", "test me", "start quiz", "give me a quiz", "mcq"]):
        intent = "quiz"
    elif any(k in q_lower for k in ["what topics am i weak in", "weak topics", "my weak areas", "where am i weak"]):
        intent = "review"
    elif any(k in q_lower for k in ["revision plan", "study plan", "exam plan", "revision schedule"]):
        intent = "plan"
    elif any(k in q_lower for k in ["explain", "teach me", "what is", "how does", "tell me about"]):
        intent = "explain"
    else:
        intent = "explain"

    # Extract days left if mentioned (e.g. "exam next week" -> 7 days, "in 3 days" -> 3)
    exam_days = 7
    days_match = re.search(r"(\d+)\s+days?", q_lower)
    if days_match:
        exam_days = int(days_match.group(1))
    elif "next week" in q_lower:
        exam_days = 7
    elif "tomorrow" in q_lower:
        exam_days = 1

    # Dynamic and comprehensive topic extraction from query
    extracted_topic = ""
    # 1. Physics: Force and Laws of Motion
    if any(k in q_lower for k in ["third law", "action and reaction", "action-reaction"]):
        extracted_topic = "Newton's Third Law of Motion"
    elif any(k in q_lower for k in ["second law", "f = ma", "rate of change of momentum"]):
        extracted_topic = "Newton's Second Law of Motion"
    elif any(k in q_lower for k in ["first law", "inertia", "law of inertia"]):
        extracted_topic = "Newton's First Law of Motion (Inertia)"
    elif any(k in q_lower for k in ["momentum", "collision", "recoil"]):
        extracted_topic = "Conservation of Momentum"
    elif any(k in q_lower for k in ["balanced", "unbalanced"]):
        extracted_topic = "Balanced and Unbalanced Forces"
    elif "friction" in q_lower:
        extracted_topic = "Friction and Motion"
    elif "newton" in q_lower or "force" in q_lower:
        extracted_topic = "Force and Laws of Motion"

    # 2. Biology: Life Processes & Photosynthesis
    elif any(k in q_lower for k in ["stomata", "stoma", "guard cell", "gaseous exchange"]):
        extracted_topic = "Stomata and Gaseous Exchange"
    elif any(k in q_lower for k in ["chloroplast", "chlorophyll"]):
        extracted_topic = "Chloroplasts and Chlorophyll"
    elif any(k in q_lower for k in ["light reaction", "photolysis", "water split"]):
        extracted_topic = "Photosynthesis - Light Reactions"
    elif any(k in q_lower for k in ["autotroph", "heterotroph"]):
        extracted_topic = "Autotrophic Nutrition"
    elif any(k in q_lower for k in ["photo", "photosynthesis"]):
        extracted_topic = "Photosynthesis"

    # 3. Dynamic regex extraction for arbitrary syllabus topics
    if not extracted_topic:
        topic_match = re.search(
            r"(?:explain|quiz me on|teach me about|what is|what are|tell me about|how does|notes on)\s+(?:the\s+)?(.+?)(?:\s+with\s+|\s+in\s+detail|\s+please|\?|$)",
            sanitized_query,
            re.IGNORECASE
        )
        if topic_match:
            candidate = topic_match.group(1).strip()
            candidate = re.sub(r"[^\w\s-]", "", candidate).strip()
            if len(candidate) > 2:
                extracted_topic = candidate.title()

    if not extracted_topic:
        if weak_topics and intent in ("quiz", "plan"):
            extracted_topic = weak_topics[0]["topic"]
        else:
            extracted_topic = state.get("topic") or "General Science"

    # LLM classification confirmation
    llm = get_chat_model()
    try:
        if hasattr(llm, "with_structured_output"):
            structured_llm = llm.with_structured_output(PlannerOutput)
            prompt = f"""You are a syllabus curriculum planner.
Classify the user intent into one of: 'explain', 'quiz', 'review', 'plan', and identify the scientific topic.
User Query: "{sanitized_query}"
Student's Weak Topics History: {weak_summary}
Candidate Topic: {extracted_topic}
Days left until exam: {exam_days}"""
            result = structured_llm.invoke(prompt)
            return {
                **state,
                "intent": result.intent,
                "topic": result.topic or extracted_topic,
                "difficulty": result.difficulty or state.get("difficulty", "medium"),
                "exam_days_left": result.exam_days_left or exam_days,
                "weak_topics": weak_topics
            }
    except Exception:
        pass

    return {
        **state,
        "intent": intent,
        "topic": extracted_topic,
        "difficulty": state.get("difficulty", "medium"),
        "exam_days_left": exam_days,
        "weak_topics": weak_topics
    }
