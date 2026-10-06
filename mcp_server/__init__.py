"""MCP Server package for Adaptive Study Tutor."""
from .db import init_db, save_progress_record, get_weak_topics_query, get_student_history

__all__ = ["init_db", "save_progress_record", "get_weak_topics_query", "get_student_history"]
