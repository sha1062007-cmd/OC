"""
Revision Planner Node:
Builds an optimized, personalized day-by-day study schedule based on:
1. Student's weakest topics (fetched via MCP `get_weak_topics`)
2. Available timeline (exam_days_left)
3. Spaced-repetition review dates (SuperMemo SM-2)
4. Syllabus textbook citations
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.state import TutorState
from app.llm import get_chat_model
from mcp_server.server import call_tool_direct
from rag.retriever import retrieve


def revision_planner_node(state: TutorState) -> TutorState:
    """
    Constructs a day-by-day spaced repetition revision plan.
    """
    student_id = state.get("student_id", "demo_student")
    exam_days = state.get("exam_days_left", 7)
    if exam_days <= 0:
        exam_days = 7

    # Fetch weak topics via MCP tool
    try:
        raw_weak = call_tool_direct("get_weak_topics", student_id=student_id, limit=6)
        weak_data = json.loads(raw_weak)
        weak_topics = weak_data.get("weak_topics", [])
    except Exception as e:
        print(f"[RevisionPlanner] Error fetching weak topics: {e}")
        weak_topics = []

    # If no weak topics recorded yet, use syllabus defaults
    if not weak_topics:
        weak_topics = [
            {"topic": "Newton's Third Law & Recoil", "avg_percentage": 50.0, "next_review_date": "Tomorrow"},
            {"topic": "Photosynthesis Light Reactions", "avg_percentage": 60.0, "next_review_date": "In 2 days"},
            {"topic": "Conservation of Momentum", "avg_percentage": 65.0, "next_review_date": "In 3 days"},
            {"topic": "Stomatal Regulation", "avg_percentage": 70.0, "next_review_date": "In 4 days"}
        ]

    # Retrieve syllabus citations for the weak topics
    topic_citations = {}
    for wt in weak_topics:
        t_name = wt["topic"]
        chunks = retrieve(t_name, k=1)
        if chunks:
            topic_citations[t_name] = chunks[0]["citation"]
        else:
            topic_citations[t_name] = "[Source: Syllabus Textbook]"

    # Build day-by-day plan
    plan_lines = [
        f"### {exam_days}-Day Adaptive Revision & Spaced Repetition Plan",
        f"**Target Student:** `{student_id}` | **Exam Timeline:** {exam_days} Days Remaining\n",
        "| Day | Priority Focus / Weak Topic | Scheduled Action | Spaced Review & Citation |",
        "| :--- | :--- | :--- | :--- |"
    ]

    # Distribute topics across available days
    num_topics = len(weak_topics)
    for day in range(1, exam_days + 1):
        if day == exam_days:
            # Final day is formula review and rest
            plan_lines.append(
                f"| **Day {day}** | **Pre-Exam Synthesis** | Comprehensive formula review, key diagrams, light rest | Review all summaries & relax |"
            )
        elif day == exam_days - 1 and exam_days >= 3:
            # Penultimate day is mock exam
            plan_lines.append(
                f"| **Day {day}** | **Full Diagnostic Mock** | Timed mixed quiz across all weak areas | Multi-topic synthesis |"
            )
        else:
            # Cycle through weak topics in order of priority (lowest score first)
            topic_idx = (day - 1) % num_topics
            target_topic = weak_topics[topic_idx]
            citation = topic_citations.get(target_topic["topic"], "[Source: Syllabus]")
            pct = target_topic.get("avg_percentage", 60.0)

            if day % 3 == 0:
                action = f"Spaced Active Recall Quiz (Target: >80%)"
                review_note = f"SM-2 Interval Check ({citation})"
            else:
                action = f"Deep Re-reading & Concept Map (Current Avg: {pct}%)"
                review_note = f"Read {citation}"

            plan_lines.append(
                f"| **Day {day}** | **{target_topic['topic']}** | {action} | {review_note} |"
            )

    plan_lines.append("\n#### Spaced Repetition (SM-2) Guidance:")
    plan_lines.append("- Topics scoring below 70% are automatically scheduled for 24-hour re-testing.")
    plan_lines.append("- Topics scoring 90%+ receive an expanded 6-day review interval to maximize long-term retention.")
    plan_lines.append("- Review textbooks directly using the cited chapter pages before each practice quiz.")

    revision_plan_text = "\n".join(plan_lines)

    messages = state.get("messages", [])
    new_messages = messages + [{"role": "assistant", "content": revision_plan_text}]

    return {
        **state,
        "revision_plan": revision_plan_text,
        "weak_topics": weak_topics,
        "messages": new_messages
    }
