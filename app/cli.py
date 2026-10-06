"""
Interactive CLI interface for Adaptive Study Tutor.
Supports:
- Chat-based explanation with citations
- Interactive multi-choice quizzes with grading and feedback
- Weak topics progress queries
- Personalized revision planning
- Memory persistence via SqliteSaver checkpointer (thread_id = student_id)
"""

import sys
import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.graph import get_tutor_app
from app.llm import check_api_keys
from app.state import create_initial_state
from mcp_server.server import call_tool_direct


def run_cli():
    print("=" * 68)
    print("      ADAPTIVE STUDY TUTOR - COMMAND LINE INTERFACE")
    print("=" * 68)

    check_api_keys(verbose=True)

    student_id = input("Enter your Student ID (default 'demo_student'): ").strip() or "demo_student"
    print(f"\nWelcome, Student '{student_id}'! Session memory is active.")
    print("Sample commands you can enter:")
    print("  1. Explain Newton's third law with an example.")
    print("  2. Quiz me on photosynthesis.")
    print("  3. What topics am I weak in?")
    print("  4. Make me a revision plan for my exam next week.")
    print("  (Type 'quit' or 'exit' to stop)\n")

    app = get_tutor_app(with_persistence=True)
    config = {"configurable": {"thread_id": student_id}}

    while True:
        try:
            user_input = input(f"\n[{student_id}] > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Session ended. All progress saved in SQLite.")
            break

        # Check for direct weak topics command
        if user_input.lower() in ("what topics am i weak in?", "what topics am i weak in", "weak topics", "my weak topics"):
            raw_weak = call_tool_direct("get_weak_topics", student_id=student_id, limit=5)
            data = json.loads(raw_weak)
            weak_list = data.get("weak_topics", [])
            print("\n" + "=" * 55)
            print(f"  Weak Topics Analysis for: {student_id}")
            print("=" * 55)
            if not weak_list:
                print("  No quiz history found yet. Try 'Quiz me on photosynthesis'!")
            else:
                for idx, w in enumerate(weak_list, start=1):
                    print(f"  {idx}. {w['topic']}")
                    print(f"     Average Score: {w['avg_percentage']}% | Attempts: {w['attempts']}")
                    print(f"     Next Spaced Review: {w['next_review_date']}")
            print("=" * 55)
            continue

        initial_state = create_initial_state(
            student_id=student_id,
            user_message=user_input
        )

        # Execute graph
        print("\nThinking...")
        try:
            # Run graph nodes
            state = app.invoke(initial_state, config=config)

            # Check if quiz was presented and needs student answers
            quiz = state.get("quiz")
            if quiz and not state.get("quiz_completed"):
                questions = quiz.get("questions", [])
                print("\n" + state.get("messages", [])[-1]["content"])
                answers = {}
                print("\nPlease submit your answers:")
                for idx, q in enumerate(questions):
                    ans = input(f"  Your answer for Q{idx+1} (A/B/C/D): ").strip().upper()
                    answers[str(idx)] = ans

                # Now evaluate the quiz with the submitted answers
                state["student_answers"] = answers
                from app.nodes.evaluator import evaluator_node
                state = evaluator_node(state)
                eval_content = state.get("messages", [])[-1]["content"]
                print("\n" + eval_content)

                # Check conditional mastery edge
                from app.graph import route_evaluator, progress_summary_node
                route_decision = route_evaluator(state)
                if route_decision == "explainer":
                    print("\n[Adaptive Loop Triggered] Score below threshold! Re-teaching weak concepts...")
                    from app.nodes.explainer import explainer_node
                    from app.nodes.quiz_master import quiz_master_node
                    state = explainer_node(state)
                    print("\n" + state.get("messages", [])[-1]["content"])
                    state = quiz_master_node(state)
                    print("\n" + state.get("messages", [])[-1]["content"])
                else:
                    state = progress_summary_node(state)
                    print("\n" + state.get("messages", [])[-1]["content"])
            else:
                # Normal explanation, review, or plan output
                last_msg = state.get("messages", [])[-1]["content"]
                print("\n" + last_msg)

        except Exception as e:
            print(f"\n[Error executing request: {e}]")


if __name__ == "__main__":
    run_cli()
