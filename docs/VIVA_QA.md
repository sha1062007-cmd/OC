# Comprehensive Viva Q&A Guide: Adaptive Study Tutor

This document contains 15 in-depth technical questions and answers designed for academic viva voce examinations and technical evaluations.

---

### Q1: Why did you choose LangGraph instead of traditional linear chains or generic ReAct agents?
**Answer:**
Traditional LangChain chains are Directed Acyclic Graphs (DAGs) and cannot naturally handle cyclical execution. A true adaptive tutor requires an **agentic loop**—evaluating student answers, determining if mastery is below threshold, re-teaching missed subtopics, and generating a fresh quiz with adjusted difficulty. LangGraph models the agent as a finite-state machine (`StateGraph`) with cyclic edges, state persistence, checkpointing, and human-in-the-loop pause/resume semantics (`interrupt`), which are essential for pedagogical workflows.

---

### Q2: How is the conditional mastery loop implemented in your LangGraph graph?
**Answer:**
In `app/graph.py`, after the `Evaluator` node grades a quiz, execution passes to a conditional edge defined by `route_evaluator(state)`.
- If `score < mastery_threshold` (default 0.70) **AND** `iteration_count < max_iterations` (default 3), it routes back to `Explainer`.
- The `Explainer` node reads the diagnostic feedback (`missed_subtopics`) from the evaluation state, re-explains the material using new analogies, and forwards state to `QuizMaster` for a fresh test.
- Once `score >= mastery_threshold` or `iteration_count >= 3`, the edge branches to `progress_summary`, terminating the cycle.

---

### Q3: How do you prevent infinite loops in the adaptive learning cycle?
**Answer:**
We implement a hard iteration ceiling guardrail (`max_iterations = 3`, configurable in `.env`). On every evaluation pass, `iteration_count` is incremented. The conditional routing function evaluates both conditions simultaneously:
```python
if score < threshold and iteration_count < max_iterations:
    return "explainer"
return "progress_summary"
```
Even if a student repeatedly fails, the loop safely terminates after 3 cycles and generates an actionable study summary, scheduling the topic for spaced repetition.

---

### Q4: What is the Model Context Protocol (MCP) and what role does it play here?
**Answer:**
MCP is an open standard introduced by Anthropic that standardizes how AI agents discover and execute tools across distinct process boundaries. In this project, `mcp_server/server.py` implements a standalone FastMCP server exposing three core capabilities:
1. `generate_quiz(topic, n, difficulty)`: LLM-driven MCQ creation with strict Pydantic JSON schema validation and retries.
2. `save_progress(student_id, topic, score, total)`: Stores attempts in SQLite.
3. `get_weak_topics(student_id, limit)`: Aggregates student analytics.
Decoupling tools through MCP allows independent scaling, external client access, and modular tool swapping.

---

### Q5: How does the agent communicate with the MCP server?
**Answer:**
Communication uses the standard `mcp` Python SDK with stdio transport. For high-speed in-process execution during Streamlit and CLI sessions, we provide a direct binding helper (`call_tool_direct`) while maintaining full compliance with FastMCP decorators (`@mcp.tool()`), allowing the server to run as an independent background microservice via `python mcp_server/server.py`.

---

### Q6: How does the RAG pipeline guarantee that explanations are grounded and hallucination-free?
**Answer:**
Grounding is enforced across three layers:
1. **Curriculum Ingestion (`rag/ingest.py`):** Ingests verified NCERT textbook chapters and splits them into discrete chunks with metadata tags: `source_file`, `chapter`, and exact `page`.
2. **Citation Injection (`rag/retriever.py`):** Returns chunks with mandatory citation strings formatted as `[Source: filename, p.X]`.
3. **Guardrail Node (`app/guardrails.py`):** Before the LLM generates an explanation, `verify_syllabus_grounding()` inspects retrieval similarity scores. If no syllabus chunks are retrieved, the agent refuses to speculate and explicitly notifies the student rather than hallucinating.

---

### Q7: Why did you choose 800–1000 characters with 150-character overlap for RAG chunking?
**Answer:**
Educational textbooks contain tightly coupled definitions, formulas, and examples. A chunk of 800–1000 characters represents approximately 150–200 words (1–2 paragraphs), which captures an entire conceptual unit (e.g., Newton's Third Law definition and action-reaction properties) without overflowing the vector embedding space. The 150-character overlap prevents sentences and formula derivations from being split across chunk boundaries.

---

### Q8: Under what exact conditions is Tavily web search triggered instead of RAG?
**Answer:**
To preserve curriculum alignment and prevent distraction, web search is used strictly as a **supplementary fallback**:
1. When RAG retrieval confidence is low (`similarity < 0.25`), indicating that syllabus coverage is sparse.
2. During re-teaching cycles (`iteration_count > 0`), when real-world multimedia demonstrations and videos are required to clarify persistent misconceptions.
3. When the user explicitly requests real-world or industry examples.
All web snippets are segregated in prompts under untrusted data delimiters and presented with the label `"Supplementary (web)"`.

---

### Q9: How is student memory persisted across sessions?
**Answer:**
We implement dual-layer persistence:
1. **LangGraph State Checkpointing:** We attach `SqliteSaver` to the compiled graph with `thread_id = student_id`. All conversation turns, current quiz state, and variables survive application restarts.
2. **Relational Analytics Storage:** Every quiz score is committed to SQLite table `progress`. Long-term analytics survive independently of agent context windows.

---

### Q10: How does your Spaced Repetition algorithm (SM-2) work?
**Answer:**
We implement the SuperMemo SM-2 spaced repetition algorithm in `mcp_server/db.py`:
- Performance percentage is mapped to a 0–5 quality grade $q$.
- A passing grade ($q \ge 3$, percentage $\ge 60\%$) increments repetitions:
  - Repetition 1: 1 day
  - Repetition 2: 6 days
  - Subsequent repetitions: $I(n) = I(n-1) \times \text{EaseFactor}$
- The Ease Factor (EF) is updated dynamically based on score:
  $$\text{EF}' = \text{EF} + (0.1 - (5 - q) \times (0.08 + (5 - q) \times 0.02))$$
- If the student scores poorly ($q < 3$), repetitions reset to 0, and the topic is scheduled for immediate 24-hour review.

---

### Q11: How do you defend against Prompt Injection?
**Answer:**
We enforce four distinct defenses in `app/guardrails.py`:
1. **Pattern Sanitization:** Strips known jailbreak patterns (`"ignore previous instructions"`, `"system prompt"`, `"developer mode"`).
2. **Untrusted Data Boundary Wrapping:** Retrieved textbook and web text are wrapped in strict XML tags (`<SYLLABUS_TEXTBOOK_DATA>...</SYLLABUS_TEXTBOOK_DATA>`).
3. **System Directives:** System prompts instruct the LLM to treat all enclosed context strictly as reference data and never as executable instructions.
4. **Content Moderation:** Filters inappropriate or harmful keywords on both inputs and outputs.

---

### Q12: Why is the Answer Stripping guardrail critical during quizzes?
**Answer:**
In many naive LLM quiz applications, the model outputs the correct answers alongside the questions, ruining the test. In our system, `QuizMaster` calls `generate_quiz`, which produces full MCQs with `correct_answer` and `explanation`. Before sending anything to the student or rendering the UI, `strip_quiz_answers_for_student()` strips the `correct_answer` and `explanation` keys. The answers are stored securely in internal graph state and only released to the student after the `Evaluator` node has graded their submission.

---

### Q13: How does Mock Mode (`MOCK_LLM=true`) work and why is it important?
**Answer:**
For examiners, CI/CD pipelines, and offline evaluation, requiring active API keys from paid providers can cause friction. When `MOCK_LLM=true` (or when no keys are found in `.env`), the system substitutes a deterministic `MockChatModel` and local semantic hashing embeddings. Every test, routing edge, and sample query passes with 100% determinism in under 2 seconds, with zero external network dependencies.

---

### Q14: How are structured JSON outputs validated in `generate_quiz`?
**Answer:**
We define a Pydantic schema `QuizCollectionSchema` containing nested `QuizQuestionSchema` models. The generator runs with a retry loop (up to 3 attempts): it parses the LLM output, validates field types, verifies that each question has exactly 4 options, and ensures `correct_answer` is a valid option. If an attempt fails, it retries with an error-correction prompt, and falls back to a curated question bank if retries are exhausted.

---

### Q15: What are the main limitations of this system and how could it be improved in future work?
**Answer:**
- **Multimodal Content:** Current textbook parsing extracts textual descriptions; diagrams and mathematical formula images could be enhanced using multimodal vision models (e.g. Gemini 1.5 Pro).
- **Subjective Answer Grading:** The current evaluator evaluates multiple-choice questions; integrating semantic rubrics for open-ended essay answers is a natural next step.
- **Audio Voice Interface:** Adding Whisper speech-to-text and ElevenLabs text-to-speech would enable conversational oral viva practice.
