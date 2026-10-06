"""
Unit tests for the MCP Server tools:
- generate_quiz(topic, n, difficulty)
- save_progress(student_id, topic, score, total)
- get_weak_topics(student_id, limit)
"""

import json
import os
import tempfile
import pytest

from mcp_server.server import generate_quiz, save_progress, get_weak_topics
from mcp_server.db import init_db, save_progress_record, get_weak_topics_query, calculate_sm2_interval


@pytest.fixture(autouse=True)
def isolated_test_db(monkeypatch):
    """Provides a fresh isolated temporary SQLite database for each test."""
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test_tutor.db")
    monkeypatch.setenv("SQLITE_DB_PATH", temp_db)
    init_db(temp_db)
    yield temp_db
    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except Exception:
            pass


def test_generate_quiz_schema_and_options():
    """Verify generate_quiz produces valid JSON with 4 options and required keys."""
    raw_quiz = generate_quiz(topic="Newton's Third Law", n=3, difficulty="medium")
    data = json.loads(raw_quiz)

    assert "questions" in data
    assert len(data["questions"]) == 3

    for q in data["questions"]:
        assert "question" in q and len(q["question"]) > 5
        assert "options" in q
        assert len(q["options"]) == 4
        assert "correct_answer" in q
        assert q["correct_answer"] in ["A", "B", "C", "D"]
        assert "explanation" in q
        assert "subtopic" in q


def test_save_progress_and_sm2_calculation():
    """Verify save_progress correctly computes percentage and schedules SM-2 review."""
    student_id = "test_student_1"
    topic = "Photosynthesis"

    # 1. First attempt: High score (3/3 = 100%)
    res_json = save_progress(student_id=student_id, topic=topic, score=3.0, total=3, difficulty="medium")
    res = json.loads(res_json)
    assert res["status"] == "success"
    rec = res["saved_record"]
    assert rec["percentage"] == 100.0
    assert "next_review_date" in rec

    # 2. Second attempt: Low score (1/4 = 25%) should reset interval to 1 day
    res2_json = save_progress(student_id=student_id, topic="Recoil Physics", score=1.0, total=4, difficulty="hard")
    rec2 = json.loads(res2_json)["saved_record"]
    assert rec2["percentage"] == 25.0
    assert rec2["interval_days"] == 1


def test_get_weak_topics_ordering():
    """Verify get_weak_topics returns lowest scoring topics first."""
    student_id = "weak_test_student"

    # Seed 3 topics with different percentages
    save_progress(student_id=student_id, topic="Strong Topic", score=10.0, total=10) # 100%
    save_progress(student_id=student_id, topic="Medium Topic", score=7.0, total=10)   # 70%
    save_progress(student_id=student_id, topic="Weak Topic", score=3.0, total=10)     # 30%

    raw_weak = get_weak_topics(student_id=student_id, limit=3)
    data = json.loads(raw_weak)
    weak_list = data["weak_topics"]

    assert len(weak_list) == 3
    # Weakest (30%) must be first
    assert weak_list[0]["topic"] == "Weak Topic"
    assert weak_list[0]["avg_percentage"] == 30.0
    # Strongest (100%) must be last
    assert weak_list[2]["topic"] == "Strong Topic"
    assert weak_list[2]["avg_percentage"] == 100.0


def test_sm2_algorithm_math():
    """Verify SuperMemo SM-2 interval expansion on success and reset on failure."""
    # Repetition 0 with high score -> interval 1
    reps, interval, ef, _ = calculate_sm2_interval(0, 1, 2.5, 1.0)
    assert reps == 1
    assert interval == 1

    # Repetition 1 with high score -> interval 6
    reps2, interval2, ef2, _ = calculate_sm2_interval(reps, interval, ef, 1.0)
    assert reps2 == 2
    assert interval2 == 6

    # Failure (0.2 score) -> resets reps to 0 and interval to 1
    reps_fail, interval_fail, _, _ = calculate_sm2_interval(reps2, interval2, ef2, 0.2)
    assert reps_fail == 0
    assert interval_fail == 1
