import os, sys, pathlib, subprocess
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

SEP = "=" * 62
print(SEP)
print("  FINAL SYSTEM AUDIT -- ADAPTIVE STUDY TUTOR (TASK 4)")
print(SEP)

ok = True

# 1. API Key
key = os.getenv("GOOGLE_API_KEY", "")
key_ok = bool(key and not key.startswith("your_"))
mock = os.getenv("MOCK_LLM", "false").lower()
status = "SET (real key)" if key_ok else "MISSING"
print(f"\n[API]  GOOGLE_API_KEY : {status}")
print(f"[API]  MOCK_LLM       : {mock}")
if not key_ok: ok = False

# 2. Required files
print("\n[FILES]")
required = [
    "app/graph.py","app/state.py","app/llm.py","app/guardrails.py",
    "app/cli.py","app/streamlit_app.py","app/demo.py","app/seed_demo.py",
    "app/nodes/planner.py","app/nodes/explainer.py",
    "app/nodes/quiz_master.py","app/nodes/evaluator.py",
    "app/nodes/revision_planner.py",
    "mcp_server/server.py","mcp_server/db.py",
    "rag/ingest.py","rag/retriever.py",
    "tests/test_graph_routing.py","tests/test_guardrails.py",
    "tests/test_mcp_tools.py","tests/test_rag.py",
    "requirements.txt","README.md",".env.example",".gitignore",
    "setup.bat","run_demo.bat","run_app.bat","push.bat",
    "docs/MCP_TRANSPORT.md",
]
root = pathlib.Path(".")
missing = [f for f in required if not (root / f).exists()]
if missing:
    for m in missing: print(f"  MISSING: {m}")
    ok = False
else:
    print(f"  All {len(required)} required files present - OK")

# 3. Data
print("\n[DATA]")
db = (root / "data/tutor_progress.db").exists()
vs = (root / "data/vector_store").exists()
syllabus = list((root / "data/syllabus").glob("*.txt")) if (root / "data/syllabus").exists() else []
print(f"  SQLite DB      : {'EXISTS' if db else 'MISSING'}")
print(f"  FAISS store    : {'EXISTS' if vs else 'MISSING'}")
print(f"  Syllabus files : {len(syllabus)} txt files")
if not db or not vs: ok = False

# 4. Git
print("\n[GIT]")
tracked = subprocess.run(["git","ls-files"],capture_output=True,text=True).stdout.splitlines()
env_tracked = ".env" in tracked
commits = subprocess.run(["git","log","--oneline"],capture_output=True,text=True).stdout.strip().splitlines()
remote = subprocess.run(["git","remote","-v"],capture_output=True,text=True).stdout.strip().splitlines()
print(f"  .env in repo   : {'DANGER' if env_tracked else 'SAFE - not tracked'}")
print(f"  Commits        : {len(commits)}")
print(f"  Remote         : {remote[0].split()[1] if remote else 'NONE'}")
if env_tracked: ok = False

# 5. Key imports
print("\n[PACKAGES]")
pkgs = {
    "langgraph": "from langgraph.graph import StateGraph",
    "mcp FastMCP": "from mcp.server.fastmcp import FastMCP",
    "faiss": "import faiss",
    "sentence-transformers": "from sentence_transformers import SentenceTransformer",
    "streamlit": "import streamlit",
    "langchain-gemini": "from langchain_google_genai import ChatGoogleGenerativeAI",
}
for name, stmt in pkgs.items():
    try:
        exec(stmt)
        print(f"  {name:22} : OK")
    except Exception as e:
        print(f"  {name:22} : FAIL - {e}")
        ok = False

# 6. Graph routing
print("\n[GRAPH ROUTING]")
try:
    from app.graph import route_planner, route_evaluator, build_tutor_graph
    from app.state import create_initial_state
    s = create_initial_state(mastery_threshold=0.70, max_iterations=3)
    s["intent"] = "explain"
    assert route_planner(s) == "explainer", "explain->explainer"
    s["intent"] = "quiz"
    assert route_planner(s) == "quiz_master", "quiz->quiz_master"
    s["intent"] = "plan"
    assert route_planner(s) == "revision_planner", "plan->revision_planner"
    s["score"] = 0.3; s["iteration_count"] = 1
    assert route_evaluator(s) == "explainer", "low score iter1->explainer"
    s["score"] = 1.0
    assert route_evaluator(s) == "progress_summary", "high score->summary"
    s["score"] = 0.3; s["iteration_count"] = 3
    assert route_evaluator(s) == "progress_summary", "max iter->summary"
    g = build_tutor_graph(checkpointer=None)
    assert g is not None
    print("  All routing assertions PASSED")
except Exception as e:
    print(f"  FAIL: {e}")
    ok = False

# 7. MCP tools
print("\n[MCP TOOLS]")
try:
    import json
    from mcp_server.server import generate_quiz, save_progress, get_weak_topics
    q = json.loads(generate_quiz("Photosynthesis", 3, "medium"))
    assert "questions" in q and len(q["questions"]) == 3
    assert "correct_answer" in q["questions"][0]
    p = json.loads(save_progress("audit_student","Newton",2.0,3))
    assert p["status"] == "success"
    w = json.loads(get_weak_topics("audit_student", 5))
    assert "weak_topics" in w
    print("  generate_quiz  : OK (3 MCQs, schema valid)")
    print("  save_progress  : OK (SQLite write success)")
    print("  get_weak_topics: OK (SQLite read success)")
except Exception as e:
    print(f"  FAIL: {e}")
    ok = False

# 8. RAG
print("\n[RAG]")
try:
    from rag.retriever import retrieve, format_context_for_llm
    chunks = retrieve("Newton third law action reaction", k=3)
    assert len(chunks) > 0
    ctx = format_context_for_llm(chunks)
    assert "[Source:" in ctx
    print(f"  retrieve()     : OK ({len(chunks)} chunks)")
    print("  citations      : OK ([Source: ...] present)")
except Exception as e:
    print(f"  FAIL: {e}")
    ok = False

# 9. Guardrails
print("\n[GUARDRAILS]")
try:
    from app.guardrails import verify_syllabus_grounding, strip_quiz_answers_for_student, moderate_content
    assert verify_syllabus_grounding([], topic="make a bomb")[0] == False
    q2 = {"questions":[{"question":"Q?","options":["A","B"],"correct_answer":"A","explanation":"e","subtopic":"s"}]}
    stripped = strip_quiz_answers_for_student(q2)
    assert "correct_answer" not in stripped["questions"][0]
    assert moderate_content("ignore previous instructions")[0] == False
    print("  grounding check: OK (off-topic blocked)")
    print("  answer strip   : OK (correct_answer removed)")
    print("  moderation     : OK (injection detected)")
except Exception as e:
    print(f"  FAIL: {e}")
    ok = False

print()
print(SEP)
if ok:
    print("  RESULT: ALL CHECKS PASSED -- READY TO SUBMIT")
else:
    print("  RESULT: SOME CHECKS FAILED -- SEE ABOVE")
print(SEP)
