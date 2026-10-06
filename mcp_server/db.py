"""
SQLite Database module for student progress and spaced repetition review schedule.
Handles:
- Table `progress`: (id, student_id, topic, score, total, percentage, difficulty, timestamp)
- Table `review_schedule`: (id, student_id, topic, repetitions, interval_days, ease_factor, next_review_date, last_reviewed)
- SM-2 based interval calculations
- Weak topic analytics
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "tutor_progress.db"
)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Returns a SQLite connection with row factory enabled."""
    path = db_path or os.getenv("SQLITE_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database schema if not present."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Progress Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        topic TEXT NOT NULL,
        score REAL NOT NULL,
        total INTEGER NOT NULL,
        percentage REAL NOT NULL,
        difficulty TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Spaced Repetition Table (SuperMemo SM-2 adaptation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        topic TEXT NOT NULL,
        repetitions INTEGER DEFAULT 0,
        interval_days INTEGER DEFAULT 1,
        ease_factor REAL DEFAULT 2.5,
        next_review_date TEXT NOT NULL,
        last_reviewed DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, topic)
    );
    """)

    conn.commit()
    conn.close()


def calculate_sm2_interval(
    repetitions: int,
    interval_days: int,
    ease_factor: float,
    percentage: float
) -> tuple[int, int, float, str]:
    """
    Computes SM-2 spaced repetition updates based on performance percentage (0.0 to 1.0).
    Quality grade q (0 to 5):
      q >= 3 is a pass (percentage >= 0.60)
    Returns: (new_repetitions, new_interval_days, new_ease_factor, next_review_date_str)
    """
    # Map percentage to 0..5 quality score
    if percentage >= 0.90:
        q = 5
    elif percentage >= 0.75:
        q = 4
    elif percentage >= 0.60:
        q = 3
    elif percentage >= 0.40:
        q = 2
    elif percentage >= 0.20:
        q = 1
    else:
        q = 0

    if q >= 3:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = max(1, int(round(interval_days * ease_factor)))
        new_reps = repetitions + 1
    else:
        new_reps = 0
        new_interval = 1

    # Update ease factor: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ef = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ef = max(1.3, round(new_ef, 2))

    next_date = datetime.utcnow() + timedelta(days=new_interval)
    next_date_str = next_date.strftime("%Y-%m-%d")

    return new_reps, new_interval, new_ef, next_date_str


def save_progress_record(
    student_id: str,
    topic: str,
    score: float,
    total: int,
    difficulty: str = "medium",
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stores a quiz attempt in SQLite and updates the SM-2 review schedule.
    """
    init_db(db_path)
    percentage = (score / total) * 100.0 if total > 0 else 0.0
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO progress (student_id, topic, score, total, percentage, difficulty)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id, topic, score, total, round(percentage, 2), difficulty))

    # Fetch existing SM-2 schedule
    cursor.execute("""
        SELECT repetitions, interval_days, ease_factor FROM review_schedule
        WHERE student_id = ? AND topic = ?
    """, (student_id, topic))
    row = cursor.fetchone()

    if row:
        reps = row["repetitions"]
        interval = row["interval_days"]
        ef = row["ease_factor"]
    else:
        reps = 0
        interval = 1
        ef = 2.5

    new_reps, new_interval, new_ef, next_review_str = calculate_sm2_interval(
        reps, interval, ef, percentage / 100.0
    )

    cursor.execute("""
        INSERT INTO review_schedule (student_id, topic, repetitions, interval_days, ease_factor, next_review_date, last_reviewed)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(student_id, topic) DO UPDATE SET
            repetitions = excluded.repetitions,
            interval_days = excluded.interval_days,
            ease_factor = excluded.ease_factor,
            next_review_date = excluded.next_review_date,
            last_reviewed = CURRENT_TIMESTAMP
    """, (student_id, topic, new_reps, new_interval, new_ef, next_review_str))

    conn.commit()
    conn.close()

    return {
        "student_id": student_id,
        "topic": topic,
        "score": score,
        "total": total,
        "percentage": round(percentage, 2),
        "difficulty": difficulty,
        "next_review_date": next_review_str,
        "interval_days": new_interval
    }


def get_weak_topics_query(
    student_id: str,
    limit: int = 5,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Returns the student's lowest-scoring topics (average percentage, attempts, last attempted).
    Topics with lower average scores are returned first.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.topic,
            ROUND(AVG(p.percentage), 2) AS avg_percentage,
            COUNT(p.id) AS attempts,
            MAX(p.timestamp) AS last_attempted,
            COALESCE(rs.next_review_date, 'Not scheduled') AS next_review_date
        FROM progress p
        LEFT JOIN review_schedule rs
            ON p.student_id = rs.student_id AND p.topic = rs.topic
        WHERE p.student_id = ?
        GROUP BY p.topic
        ORDER BY avg_percentage ASC, attempts DESC
        LIMIT ?
    """, (student_id, limit))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "topic": r["topic"],
            "avg_percentage": float(r["avg_percentage"]),
            "attempts": int(r["attempts"]),
            "last_attempted": str(r["last_attempted"]),
            "next_review_date": str(r["next_review_date"])
        }
        for r in rows
    ]


def get_student_history(
    student_id: str,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Returns all quiz attempts for a student ordered by timestamp ascending."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, student_id, topic, score, total, percentage, difficulty, timestamp
        FROM progress
        WHERE student_id = ?
        ORDER BY timestamp ASC
    """, (student_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "student_id": r["student_id"],
            "topic": r["topic"],
            "score": float(r["score"]),
            "total": int(r["total"]),
            "percentage": float(r["percentage"]),
            "difficulty": r["difficulty"],
            "timestamp": str(r["timestamp"])
        }
        for r in rows
    ]
