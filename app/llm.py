"""
LLM Provider and Tool Integrations for Adaptive Study Tutor.
Supports:
- Multi-provider dynamic switching: Anthropic, Google Gemini, OpenAI
- Automatic detection based on available environment API keys
- Deterministic mock mode (MOCK_LLM=true or when zero keys are found)
- Startup key check helper explaining how to acquire and configure each key
- Tavily web search integration for supplementary real-world context
"""

import os
import sys
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def check_api_keys(verbose: bool = True) -> Dict[str, bool]:
    """
    Inspects environment variables for provider keys.
    Prints status and exact fix instructions if keys are missing.
    """
    keys = {
        "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY") and not os.getenv("ANTHROPIC_API_KEY").startswith("your_")),
        "GOOGLE_API_KEY": bool(os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_API_KEY").startswith("your_")),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_API_KEY").startswith("your_")),
        "TAVILY_API_KEY": bool(os.getenv("TAVILY_API_KEY") and not os.getenv("TAVILY_API_KEY").startswith("your_")),
    }

    if verbose:
        print("\n" + "=" * 65)
        print("  ADAPTIVE STUDY TUTOR - API KEY STATUS CHECK")
        print("=" * 65)
        any_llm = keys["ANTHROPIC_API_KEY"] or keys["GOOGLE_API_KEY"] or keys["OPENAI_API_KEY"]

        for k, found in keys.items():
            status = "[FOUND]" if found else "[MISSING]"
            print(f"  {k:<22} : {status}")

        mock_mode = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
        if not any_llm:
            if not mock_mode:
                print("\n  [INFO] No active LLM API keys detected.")
                print("  -> Setting MOCK_LLM=true so the system runs smoothly offline.")
                os.environ["MOCK_LLM"] = "true"
            print("  -> Running in deterministic Mock Mode (No paid APIs required).")
            print("  -> To connect real AI, add one of the following to your .env:")
            print("     - Google Gemini (Free tier): https://aistudio.google.com")
            print("     - Anthropic Claude:          https://console.anthropic.com")
            print("     - OpenAI:                    https://platform.openai.com")
        else:
            provider = detect_active_provider(keys)
            print(f"\n  [ACTIVE LLM PROVIDER] -> {provider.upper()}")

        if not keys["TAVILY_API_KEY"]:
            print("  [NOTE] TAVILY_API_KEY is missing. Web search fallback will use")
            print("         curated science educational resources (Free key at https://tavily.com).")
        print("=" * 65 + "\n")

    return keys


def detect_active_provider(keys: Optional[Dict[str, bool]] = None) -> str:
    """Selects the LLM provider based on explicit env setting or available keys."""
    preferred = os.getenv("LLM_PROVIDER", "").lower().strip()
    if keys is None:
        keys = check_api_keys(verbose=False)

    if preferred == "anthropic" and keys.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if preferred == "google" and keys.get("GOOGLE_API_KEY"):
        return "google"
    if preferred == "openai" and keys.get("OPENAI_API_KEY"):
        return "openai"

    # Default to whichever key is set
    if keys.get("GOOGLE_API_KEY"):
        return "google"
    if keys.get("OPENAI_API_KEY"):
        return "openai"
    if keys.get("ANTHROPIC_API_KEY"):
        return "anthropic"

    return "mock"


class MockChatModel:
    """
    Deterministic Mock LLM for offline testing, CI/CD, and fast demonstrations.
    Provides predictable structured outputs and responses.
    """
    def __init__(self, model_name: str = "mock-tutor-v1"):
        self.model_name = model_name

    def invoke(self, messages_or_prompt: Any) -> Any:
        # Extract prompt string
        if isinstance(messages_or_prompt, list):
            prompt = " ".join([m.content if hasattr(m, "content") else str(m) for m in messages_or_prompt])
        elif hasattr(messages_or_prompt, "to_messages"):
            prompt = str(messages_or_prompt.to_messages())
        else:
            prompt = str(messages_or_prompt)

        prompt_lower = prompt.lower()

        # Check for structured planner classification
        if "classify" in prompt_lower or "planner" in prompt_lower or "intent" in prompt_lower:
            if "quiz" in prompt_lower or "test" in prompt_lower:
                topic = "photosynthesis" if "photo" in prompt_lower else "Newton's Third Law"
                content = f'{{"intent": "quiz", "topic": "{topic}", "difficulty": "medium", "exam_days_left": 7, "reasoning": "Student explicitly asked for a quiz."}}'
            elif "weak" in prompt_lower or "progress" in prompt_lower or "report" in prompt_lower:
                content = '{"intent": "review", "topic": "All Weak Topics", "difficulty": "medium", "exam_days_left": 7, "reasoning": "Student inquired about weak areas."}'
            elif "plan" in prompt_lower or "schedule" in prompt_lower or "revision" in prompt_lower:
                content = '{"intent": "plan", "topic": "Comprehensive Science Exam", "difficulty": "medium", "exam_days_left": 7, "reasoning": "Student requested a revision plan."}'
            else:
                topic = "Newton's Third Law" if ("newton" in prompt_lower or "force" in prompt_lower) else "Photosynthesis"
                content = f'{{"intent": "explain", "topic": "{topic}", "difficulty": "medium", "exam_days_left": 7, "reasoning": "Conceptual explanation requested."}}'
            return type("MockResponse", (), {"content": content})()

        # Check for Evaluation node
        if "evaluat" in prompt_lower or "grade" in prompt_lower:
            content = """### Quiz Evaluation & Feedback
**Overall Score:** 3 / 3 (100%) - Excellent Mastery!
- **Question 1:** Correct! You accurately identified that action and reaction act on two different bodies.
- **Question 2:** Correct! Action and reaction forces are equal in magnitude and opposite in direction.
- **Question 3:** Correct! A swimmer pushing water backward propels forward due to Newton's Third Law.
*Mastery achieved! Great job mastering this topic.*"""
            return type("MockResponse", (), {"content": content})()

        # Check for Revision Planner
        if "revision plan" in prompt_lower or "study plan" in prompt_lower:
            content = """### 7-Day Personalized Revision Plan (SM-2 Spaced Repetition)
- **Day 1 (Priority 1 - High Weakness):** Newton's Third Law of Motion & Action-Reaction Pairs. *Review [Source: ncert_class9_ch9_force_and_laws_of_motion.txt, p.118]*.
- **Day 2 (Practice):** Solve 10 numerical problems on momentum and recoil of guns.
- **Day 3 (Priority 2 - Biological Processes):** Photosynthesis Light Reactions & Stomatal Regulation. *Review [Source: ncert_class10_ch6_life_processes_photosynthesis.txt, p.96-99]*.
- **Day 4 (Spaced Repetition Review 1):** Quick 5-question flash quiz on Newton's Laws.
- **Day 5 (Priority 3):** Chemical equations of photosynthesis and raw materials.
- **Day 6 (Full Mock Test):** Combined 25-question diagnostic covering both Physics and Biology.
- **Day 7 (Pre-Exam Polish):** Formula review, diagram practice (Chloroplast & Force vectors), light reading."""
            return type("MockResponse", (), {"content": content})()

        # Default Explainer response with textbook citations
        if "newton" in prompt_lower or "force" in prompt_lower:
            content = """### Understanding Newton's Third Law of Motion

Newton's Third Law states:
> *"To every action, there is an equal and opposite reaction."* [Source: ncert_class9_ch9_force_and_laws_of_motion.txt, p.118]

#### Core Conceptual Principles:
1. **Paired Forces:** Forces always occur in matched action-reaction pairs; a solitary isolated force cannot exist in nature.
2. **Two Different Bodies:** Action and reaction forces act simultaneously on **two distinct interacting bodies** [Source: ncert_class9_ch9_force_and_laws_of_motion.txt, p.118]. Because they act on different objects, they **never cancel each other out**.
3. **Equal & Opposite:** The magnitude of force exerted by Body A on Body B is identical to that exerted by Body B on Body A, but in the opposite direction.

#### Classic Real-World Examples:
- **Swimming:** When you swim, your hands push water backwards (*action*). The water simultaneously exerts an equal forward force on your body (*reaction*).
- **Recoil of a Gun:** The gunpowder explosion accelerates the bullet forward (*action*). The bullet exerts an equal backwards force on the gun (*reaction*). Because the gun has significantly more mass than the bullet, its backward acceleration is much smaller ($a = F/m$) [Source: ncert_class9_ch9_force_and_laws_of_motion.txt, p.118]."""
            return type("MockResponse", (), {"content": content})()

        content = """### Conceptual Explanation
Based on the syllabus:
Photosynthesis is the autotrophic process where green plants synthesize glucose from carbon dioxide and water using solar energy trapped by chlorophyll [Source: ncert_class10_ch6_life_processes_photosynthesis.txt, p.95-97]."""
        return type("MockResponse", (), {"content": content})()


def get_chat_model(temperature: float = 0.2):
    """Factory creating configured ChatModel instance or MockChatModel."""
    is_mock = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
    provider = detect_active_provider()

    if is_mock or provider == "mock":
        return MockChatModel()

    try:
        if provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = os.getenv("GOOGLE_API_KEY")
            return ChatGoogleGenerativeAI(
                model="gemini-3.8-flash",
                temperature=temperature,
                google_api_key=api_key
            )
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=temperature,
                api_key=api_key
            )
        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            return ChatAnthropic(
                model="claude-3-haiku-20240307",
                temperature=temperature,
                api_key=api_key
            )
    except Exception as e:
        print(f"[LLM Factory] Error initializing {provider} model ({e}). Using mock model fallback.")
        return MockChatModel()

    return MockChatModel()


def search_supplementary_web(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    Supplementary Tavily web search used ONLY when textbook explanation needs
    real-world multimedia examples, demonstrations, or low RAG relevance.
    Labels results clearly as 'Supplementary (web)'.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if api_key and not api_key.startswith("your_"):
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            res = client.search(query=query, max_results=max_results)
            results = []
            for item in res.get("results", []):
                results.append({
                    "title": item.get("title", "Supplementary Resource"),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:280],
                    "label": "Supplementary (web)"
                })
            return results
        except Exception as e:
            print(f"[Tavily Search] Web search error: {e}")

    # Fallback curated supplementary web references
    q_lower = query.lower()
    if "newton" in q_lower or "force" in q_lower:
        return [
            {
                "title": "NASA - Newton's Laws of Motion in Spaceflight",
                "url": "https://www.grc.nasa.gov/www/k-12/rocket/newton.html",
                "snippet": "Newton's Third Law explains rocket propulsion: hot exhaust gas accelerates downward (action), pushing the rocket upward into orbit (reaction).",
                "label": "Supplementary (web)"
            },
            {
                "title": "Khan Academy - Action and Reaction Forces Explained",
                "url": "https://www.khanacademy.org/science/physics/forces-newtons-laws",
                "snippet": "Visual demonstrations of swimming, jumping, and skateboards showing why equal-and-opposite forces never cancel out.",
                "label": "Supplementary (web)"
            }
        ]
    elif "photo" in q_lower or "plant" in q_lower:
        return [
            {
                "title": "Nature Education - Photosynthesis in Chloroplasts",
                "url": "https://www.nature.com/scitable/topicpage/photosynthetic-cells-14025371",
                "snippet": "High-resolution electron micrographs illustrating the light-dependent reactions across thylakoid membrane protein complexes.",
                "label": "Supplementary (web)"
            }
        ]

    return [
        {
            "title": f"Educational Reference on {query}",
            "url": "https://en.wikipedia.org/wiki/" + query.replace(" ", "_"),
            "snippet": f"General overview and practical applications related to {query}.",
            "label": "Supplementary (web)"
        }
    ]
