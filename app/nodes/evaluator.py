"""
Evaluator Node:
Grades the student's quiz answers against the answer key.
Provides per-question feedback and conceptual explanations.
Computes percentage score, calls MCP `save_progress` to store progress in SQLite
and update the SM-2 spaced repetition schedule.
Updates iteration_count for the adaptive mastery loop.
"""

import json
from typing import Dict, Any, List
from app.state import TutorState
from mcp_server.server import call_tool_direct


def evaluator_node(state: TutorState) -> TutorState:
    """
    Grades submitted answers, stores results in SQLite via MCP save_progress,
    and formats comprehensive diagnostic feedback.
    """
    quiz = state.get("quiz") or {}
    questions = quiz.get("questions", [])
    student_answers = state.get("student_answers", {})
    student_id = state.get("student_id", "demo_student")
    topic = state.get("topic", "General Science")
    difficulty = state.get("difficulty", "medium")
    iteration_count = state.get("iteration_count", 0) + 1

    total = len(questions)
    correct_count = 0
    feedback_lines = []
    missed_subtopics = []

    if total == 0:
        score_ratio = 1.0
        feedback_lines.append("No active questions to evaluate.")
    else:
        feedback_lines.append(f"### Evaluation & Detailed Feedback (Attempt {iteration_count})")

        for idx, q in enumerate(questions):
            ans_key = str(idx)
            # Find answer provided by student for this question index
            user_ans = student_answers.get(ans_key) or student_answers.get(str(idx + 1)) or ""
            # Clean up user answer to single letter
            user_clean = user_ans.strip().upper()
            if len(user_clean) > 1 and user_clean.startswith(("A", "B", "C", "D")):
                user_clean = user_clean[0]

            correct_letter = q.get("correct_answer", "").strip().upper()
            if len(correct_letter) > 1 and correct_letter.startswith(("A", "B", "C", "D")):
                correct_letter = correct_letter[0]

            is_correct = (user_clean == correct_letter) and bool(user_clean)

            if is_correct:
                correct_count += 1
                status_icon = "CORRECT"
                feedback_lines.append(
                    f"- **Q{idx+1}: {status_icon}** (Your answer: {user_clean})\n"
                    f"  *Explanation:* {q.get('explanation', '')}"
                )
            else:
                status_icon = "INCORRECT"
                missed_subtopics.append(q.get("subtopic", topic))
                feedback_lines.append(
                    f"- **Q{idx+1}: {status_icon}** (Your answer: {user_clean or 'None'}, Correct: {correct_letter})\n"
                    f"  *Key Concept & Explanation:* {q.get('explanation', '')}"
                )

        score_ratio = correct_count / total

    pct = round(score_ratio * 100.0, 1)
    mastery_threshold = state.get("mastery_threshold", 0.70)
    mastered = score_ratio >= mastery_threshold

    summary_header = f"\n**Final Score:** {correct_count} / {total} ({pct}%)\n"
    if mastered:
        summary_status = "**Result:** Mastery Threshold Achieved! Excellent understanding of core principles."
    else:
        summary_status = f"**Result:** Score below mastery threshold ({int(mastery_threshold*100)}%). Triggering adaptive re-teaching of weak subtopics..."

    feedback_lines.append(summary_header + summary_status)
    eval_text = "\n".join(feedback_lines)

    # Call MCP save_progress tool to record score and update spaced repetition
    try:
        call_tool_direct(
            "save_progress",
            student_id=student_id,
            topic=topic,
            score=float(correct_count),
            total=total,
            difficulty=difficulty
        )
    except Exception as e:
        print(f"[Evaluator] Warning: Could not call MCP save_progress: {e}")

    messages = state.get("messages", [])
    new_messages = messages + [{"role": "assistant", "content": eval_text}]

    # Format feedback for potential re-teaching in Explainer node
    missed_summary = f"Missed concepts: {', '.join(set(missed_subtopics))}" if missed_subtopics else "All concepts answered correctly."

    return {
        **state,
        "score": score_ratio,
        "iteration_count": iteration_count,
        "evaluation_feedback": missed_summary,
        "messages": new_messages,
        "quiz_completed": True
    }
