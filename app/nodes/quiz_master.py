"""
Quiz Master Node:
Calls the MCP `generate_quiz` tool to create curriculum-aligned questions.
Enforces the Answer Stripping Guardrail: NEVER reveals correct answers or explanations
to the student before evaluation.
Adjusts difficulty dynamically during adaptive mastery loops.
"""

import json
from typing import Dict, Any, List
from app.state import TutorState
from mcp_server.server import call_tool_direct
from app.guardrails import strip_quiz_answers_for_student


def quiz_master_node(state: TutorState) -> TutorState:
    """
    Generates a quiz using the FastMCP tool and formats questions without answers.
    """
    topic = state.get("topic", "Newton's Third Law")
    difficulty = state.get("difficulty", "medium")
    iteration_count = state.get("iteration_count", 0)

    # Adjust difficulty if looping
    if iteration_count > 1:
        difficulty = "medium"  # Reinforce fundamental concepts

    # Number of questions per quiz (default 3)
    n_questions = 3

    # Call MCP generate_quiz tool
    try:
        raw_quiz_json = call_tool_direct(
            "generate_quiz",
            topic=topic,
            n=n_questions,
            difficulty=difficulty
        )
        full_quiz_data = json.loads(raw_quiz_json)
    except Exception as e:
        print(f"[QuizMaster] Error calling MCP generate_quiz: {e}")
        full_quiz_data = {
            "questions": [
                {
                    "question": f"What is a primary principle of {topic}?",
                    "options": ["A) Equal and opposite action-reaction", "B) One-way force", "C) Zero resistance", "D) None of these"],
                    "correct_answer": "A",
                    "explanation": "Action and reaction forces are always equal and opposite.",
                    "subtopic": topic
                }
            ]
        }

    # Guardrail: Strip answers before presenting questions to student
    student_facing_quiz = strip_quiz_answers_for_student(full_quiz_data)

    # Format presentation string
    presentation_lines = [
        f"### Quiz: {topic} (Difficulty: {difficulty.capitalize()})",
        f"*Answer the {len(student_facing_quiz['questions'])} questions below (select A, B, C, or D):*\n"
    ]

    for idx, q in enumerate(student_facing_quiz["questions"], start=1):
        presentation_lines.append(f"**Q{idx}. {q['question']}**")
        for opt in q["options"]:
            presentation_lines.append(f"  {opt}")
        presentation_lines.append("")

    presentation_text = "\n".join(presentation_lines)

    messages = state.get("messages", [])
    new_messages = messages + [{"role": "assistant", "content": presentation_text}]

    # Store full quiz data (with answers kept securely in state for Evaluator only)
    return {
        **state,
        "quiz": full_quiz_data,
        "difficulty": difficulty,
        "messages": new_messages
    }
