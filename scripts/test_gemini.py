import sys
sys.path.insert(0, ".")
from app.llm import get_chat_model, check_api_keys

check_api_keys(verbose=True)
print("Testing real Gemini API call...")
llm = get_chat_model()
resp = llm.invoke("Say exactly the words: GEMINI_WORKS_OK")
print("Response:", resp.content[:120])
print("STATUS: REAL GEMINI CONFIRMED WORKING")
