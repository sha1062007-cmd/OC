"""
Guardrails Module for Adaptive Study Tutor.
Enforces:
1. Syllabus Grounding Check: refuses or flags ungrounded topics when RAG has zero relevant syllabus match.
2. Quiz Answer Stripping: strips correct_answer and explanation before presenting quiz to student.
3. Age-Appropriate Content Moderation: filters inappropriate content on input and output.
4. Prompt-Injection Resistance: sanitizes input text, prevents prompt leak, treats retrieved context strictly as data.
"""

import re
from typing import List, Dict, Any, Tuple

# Blocklist for basic age-inappropriate content
INAPPROPRIATE_KEYWORDS = [
    "nsfw", "violence", "hate", "weapon", "kill", "porn", "bomb",
    "hack", "bypass", "exploit", "jailbreak", "override instructions",
    "ignore previous instructions", "disregard system"
]

# Injection phrases to sanitize
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s*prompt",
    r"you\s+are\s+now\s+dan",
    r"developer\s+mode",
    r"reveal\s+(all\s+)?(keys|passwords|instructions)"
]


def moderate_content(text: str) -> Tuple[bool, str]:
    """
    Checks if text is safe and age-appropriate.
    Returns (is_safe, reason).
    """
    if not text:
        return True, "Empty text"

    text_lower = text.lower()
    for word in INAPPROPRIATE_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
            return False, f"Flagged inappropriate content: contains '{word}'"

    return True, "Safe"


def sanitize_input_prompt_injection(user_input: str) -> str:
    """
    Neutralizes potential prompt injection patterns in user query.
    """
    sanitized = user_input
    for pattern in INJECTION_PATTERNS:
        sanitized = re.sub(pattern, "[FILTERED_INSTRUCTION]", sanitized, flags=re.IGNORECASE)
    return sanitized.strip()


def strip_quiz_answers_for_student(quiz_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    CRITICAL GUARDRAIL: Strips 'correct_answer' and 'explanation' fields
    from quiz data before presenting questions to the student.
    Ensures answers are never revealed prematurely during the quiz.
    """
    if not quiz_data or "questions" not in quiz_data:
        return quiz_data

    sanitized_questions = []
    for q in quiz_data["questions"]:
        sanitized_questions.append({
            "question": q.get("question", ""),
            "options": q.get("options", []),
            "subtopic": q.get("subtopic", "")
            # Notice: 'correct_answer' and 'explanation' are completely omitted!
        })

    return {"questions": sanitized_questions}


def verify_syllabus_grounding(retrieved_chunks: List[Dict[str, Any]], topic: str) -> Tuple[bool, str]:
    """
    Verifies that the requested topic has grounded reference in the syllabus.
    If no chunks are found or score is too low, flags the topic.
    """
    if not retrieved_chunks:
        return False, (
            f"The topic '{topic}' was not found in your syllabus textbook. "
            f"As an AI tutor grounded strictly in your curriculum, I cannot provide an unverified explanation. "
            f"Please verify if this topic is part of your course syllabus or upload the relevant chapter."
        )

    max_score = max([c.get("score", 0.0) for c in retrieved_chunks])
    if max_score < 0.05:
        return False, (
            f"The topic '{topic}' has very low similarity with the enrolled syllabus chapters. "
            f"Please ensure it matches your NCERT or course materials."
        )

    return True, "Sufficient syllabus grounding detected."


def wrap_data_as_untrusted(data_text: str, label: str = "CONTEXT_DATA") -> str:
    """
    Wraps external or retrieved data in clear data boundaries to prevent prompt injection.
    """
    return f"<{label}>\n{data_text}\n</{label}>\n"
