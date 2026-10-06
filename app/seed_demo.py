"""
Seed Demo Data Script:
Inserts realistic diagnostic quiz history for a student (`demo_student`) into SQLite.
Allows 'What topics am I weak in?' and revision planning to showcase immediate
analytics without needing manual quiz completions first.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mcp_server.db import init_db, save_progress_record, get_weak_topics_query, get_student_history


def seed_demo_student_history(student_id: str = "demo_student") -> None:
    """Populates realistic historical quiz attempts for demo_student."""
    print(f"[Seed Demo] Initializing database and seeding history for '{student_id}'...")
    init_db()

    # Clear existing demo records if any to make seeding idempotent
    from mcp_server.db import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM progress WHERE student_id = ?", (student_id,))
    c.execute("DELETE FROM review_schedule WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()

    sample_attempts = [
        # Weak topic 1: Newton's Third Law
        {"topic": "Newton's Third Law of Motion", "score": 1.0, "total": 3, "difficulty": "hard"},
        # Weak topic 2: Photosynthesis Light Reactions
        {"topic": "Photosynthesis - Light Reactions & Water Splitting", "score": 2.0, "total": 4, "difficulty": "medium"},
        # Moderate topic 3: Conservation of Momentum
        {"topic": "Conservation of Momentum & Collisions", "score": 2.0, "total": 3, "difficulty": "medium"},
        # Strong topic 4: Balanced & Unbalanced Forces
        {"topic": "Balanced & Unbalanced Forces", "score": 3.0, "total": 3, "difficulty": "easy"},
        # Strong topic 5: Chloroplast Structure
        {"topic": "Chloroplast & Stomatal Regulation", "score": 4.0, "total": 4, "difficulty": "easy"},
    ]

    for item in sample_attempts:
        save_progress_record(
            student_id=student_id,
            topic=item["topic"],
            score=item["score"],
            total=item["total"],
            difficulty=item["difficulty"]
        )
        pct = (item["score"] / item["total"]) * 100
        print(f"  + Seeded: {item['topic']} -> {item['score']}/{item['total']} ({pct:.0f}%)")

    # Verify seeded weak topics
    weak = get_weak_topics_query(student_id=student_id, limit=5)
    print("\n[Seed Demo] Verified Top Weak Topics in SQLite:")
    for idx, w in enumerate(weak, start=1):
        print(f"  {idx}. {w['topic']:<45} | Avg: {w['avg_percentage']}% | Review: {w['next_review_date']}")

    print("\n[Seed Demo] Success: Demo history successfully seeded! Ready for instant queries.")


if __name__ == "__main__":
    seed_demo_student_history()
