# 3-Minute Live Demonstration Walkthrough

This script provides an exact 3-minute presentation script you can follow when presenting or screen-recording your project for marks.

---

### Minute 0:00 – 0:45: Project Overview & System Setup
1. **Introduction:**
   - *"Hello! Today I am presenting the Adaptive Study Tutor—an agentic educational assistant built on LangGraph, FastMCP, SQLite, and persistent RAG."*
   - *"Unlike simple chat bots that just summarize text, this system acts as a true tutor: it explains concepts with verifiable textbook citations, quizzes the student, diagnoses weak areas, and features a conditional feedback loop that automatically adapts the curriculum."*
2. **Terminal Verification:**
   - Open PowerShell / Command Prompt and show that all 18 pytest tests pass:
     ```cmd
     test.bat
     ```
   - Highlight: *"All 18 unit tests pass in under 2 seconds, verifying our MCP tools, guardrails, and LangGraph routing edges."*

---

### Minute 0:45 – 1:45: Launching the App & Demonstrating the 4 Queries
1. **Launch Web UI:**
   ```cmd
   run_app.bat
   ```
   - Notice the Streamlit interface opens in your browser at `http://localhost:8501`.
2. **Query 1: Verified Textbook Explanation with Citations:**
   - Type or click: `"Explain Newton's third law with an example."`
   - Point to the response on screen:
     - *"Notice the verified citation: `[Source: ncert_class9_ch9_force_and_laws_of_motion.txt, p.118]`."*
     - *"Notice also the supplementary web resource labeled clearly as `Supplementary (web)` from our Tavily integration."*
3. **Query 2: The Core Agentic Loop (Low Score -> Re-teach -> Re-quiz):**
   - Click: `"Quiz me on photosynthesis."`
   - Point out that **answers are strictly stripped** from the quiz form.
   - Intentionally select a low-scoring option (e.g. choose wrong answers for Q2 and Q3) and click **Submit Quiz Answers**.
   - Show the result:
     - *"The Evaluator graded the quiz at 33%—below our 70% mastery threshold."*
     - *"Notice that the conditional edge automatically activated! The tutor did NOT just give up: it looped back to the Explainer node, re-taught the missed concept of photolysis and stomata, and immediately generated a fresh re-test."*
   - Now submit the correct answers to show mastery achieved!

---

### Minute 1:45 – 2:30: Weak Topics Diagnostics & Spaced Repetition
1. **Query 3: Diagnosing Weak Areas:**
   - Click: `"What topics am I weak in?"` or switch to the **Progress & Weak Topics** tab.
   - Point to the **Performance Trend Chart** and the **Weak Topics list**:
     - *"Our MCP tool `get_weak_topics` queries SQLite to calculate average percentages and attempts."*
     - *"Notice that each topic has an automatically computed `Next Review Date` calculated using the SuperMemo SM-2 spaced repetition algorithm."*

---

### Minute 2:30 – 3:00: Spaced Repetition Revision Plan & Conclusion
1. **Query 4: Generating Personalized Revision Plan:**
   - Switch to the **Revision Plan** tab (or type: `"Make me a revision plan for my exam next week."`).
   - Click **Generate Dynamic Study Schedule**.
   - Show the generated day-by-day timetable:
     - *"The Revision Planner prioritizes the student's weakest topics first, spreads them over the 7 days before the exam, integrates active recall quizzes on spaced intervals, and links every study block directly to syllabus chapter pages."*
2. **Closing:**
   - *"In summary: we have implemented the full LangGraph orchestration graph, an official FastMCP server, local vector RAG with citations, persistent memory via SqliteSaver, and robust guardrails. Thank you!"*
