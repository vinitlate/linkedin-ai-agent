# agent_core.py
import os
import json
from datetime import datetime
from dotenv import load_dotenv

from openai_shared import llm
from trend_agent import trending_topic_of_week_value

load_dotenv()

MEMORY_PATH = os.getenv("AGENT_MEMORY_PATH", "agent_memory.json")


def load_memory() -> dict:
    if not os.path.exists(MEMORY_PATH):
        return {
            "profile": {
                "name": "Vinit",
                "niche": "Data Engineering & AI",
                "audience": "junior/upcoming engineers",
                "tone_rules": [
                    "sound practical, not hype-y",
                    "clear and normal, not tacky",
                    "avoid excessive emojis",
                    "use simple examples",
                ],
            },
            "history": [],
            "best_practices": {
                "post_length": "120-220 words",
                "structure": ["hook", "problem", "insight", "example", "takeaway", "question"],
            },
        }

    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(memory: dict) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)


def plan_post(topic: str, memory: dict, model: str) -> dict:
    profile = memory["profile"]
    best = memory["best_practices"]

    prompt = f"""
You are a LinkedIn content strategist + data engineering mentor.

Context:
- Creator: {profile["name"]}
- Niche: {profile["niche"]}
- Target audience: {profile["audience"]}
- Tone rules: {profile["tone_rules"]}
- Preferred post length: {best["post_length"]}
- Preferred structure: {best["structure"]}

Task:
Create a plan for a LinkedIn post about: "{topic}"

Return STRICT JSON with keys:
- "angles": [3 distinct angles]
- "best_angle": one chosen angle
- "outline": list of bullet points following the preferred structure
- "hook_options": [5 short hooks]
- "example": a simple, concrete example relevant to data engineering/AI
- "cta_question": one question to ask at the end
"""
    content, used_model = llm(
        [
            {"role": "system", "content": "Return only valid JSON. No markdown."},
            {"role": "user", "content": prompt},
        ],
        model=model,
    )

    try:
        plan = json.loads(content)
        plan["_meta"] = {"used_model": used_model}
        return plan
    except json.JSONDecodeError:
        return {"error": "Model returned non-JSON", "raw": content, "_meta": {"used_model": used_model}}


def write_post(topic: str, plan: dict, memory: dict, model: str) -> tuple[str, str]:
    profile = memory["profile"]
    best = memory["best_practices"]

    prompt = f"""
Write a LinkedIn post draft using this plan.

Creator profile:
- Name: {profile["name"]}
- Niche: {profile["niche"]}
- Audience: {profile["audience"]}
- Tone rules: {profile["tone_rules"]}
- Target length: {best["post_length"]}

Topic: {topic}

Plan (JSON):
{json.dumps(plan, indent=2)}

Requirements:
- Clear, practical, not hype-y
- No hashtags (we can add later)
- Minimal to zero emojis (default: none)
- End with the provided CTA question
"""
    return llm(
        [
            {"role": "system", "content": "You write in crisp LinkedIn style."},
            {"role": "user", "content": prompt},
        ],
        model=model,
    )


def compress_post(post: str, target_words=(160, 200), model: str = "") -> tuple[str, str]:
    lo, hi = target_words
    prompt = f"""
Rewrite the LinkedIn post to be {lo}-{hi} words.
Keep the same meaning.
Keep one concrete example.
Keep the final question.
Remove fluff. No hashtags.

POST:
{post}
"""
    return llm(
        [
            {"role": "system", "content": "Return only the rewritten post text."},
            {"role": "user", "content": prompt},
        ],
        model=model,
    )


def run_agent(topic: str, model: str, do_compress: bool = True) -> dict:
    memory = load_memory()

    plan = plan_post(topic, memory, model=model)
    if "error" in plan:
        return {"ok": False, "error": plan["error"], "raw": plan.get("raw"), "meta": plan.get("_meta")}

    post, write_used_model = write_post(topic, plan, memory, model=model)

    compress_used_model = None
    if do_compress:
        post, compress_used_model = compress_post(post, model=model)

    meta = {
        "requested_model": model,
        "plan_used_model": plan.get("_meta", {}).get("used_model"),
        "write_used_model": write_used_model,
        "compress_used_model": compress_used_model,
    }

    run_record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "topic": topic,
        "plan": plan,
        "post": post,
        "feedback": None,
        "_meta": meta,
    }

    memory["history"].append(run_record)
    save_memory(memory)

    return {"ok": True, "plan": plan, "post": post, "meta": meta}


def run_weekly_trend_to_post(model: str, do_compress: bool = True) -> dict:
    """
    Uses the SAME model from UI for:
    - Trend selection (LLM value filter)
    - Post plan
    - Post write
    - Post compress
    """
    trend = trending_topic_of_week_value(top_k=6, model=model)
    if not trend.get("ok"):
        return {"ok": False, "error": trend.get("error", "Trend agent failed"), "trend": trend}

    chosen = trend["chosen"]
    selection = trend.get("selection", {})
    frame = selection.get("teaching_frame", {})

    enriched_topic = (
        f"{chosen['representative_title']}\n\n"
        f"Teaching frame:\n"
        f"- Concept: {frame.get('concept')}\n"
        f"- Common misconception: {frame.get('common_misconception')}\n"
        f"- Practical example idea: {frame.get('practical_example_idea')}\n"
        f"- Takeaway: {frame.get('takeaway')}\n"
        f"\nSources: {', '.join(chosen.get('sources', []))}\n"
        f"Common terms: {', '.join(chosen.get('common_terms', [])[:8])}"
    )

    result = run_agent(enriched_topic, model=model, do_compress=do_compress)
    if result.get("ok"):
        result["trend"] = trend
        result.setdefault("meta", {})
        result["meta"]["trend_used_model"] = selection.get("_meta", {}).get("used_model")

    return result


def add_feedback(feedback: dict) -> None:
    memory = load_memory()
    if not memory.get("history"):
        raise RuntimeError("No history found. Run the agent at least once.")
    memory["history"][-1]["feedback"] = feedback
    save_memory(memory)


def update_profile_settings(updated_profile: dict, updated_best_practices: dict | None = None) -> None:
    memory = load_memory()

    if "name" not in updated_profile or not updated_profile["name"].strip():
        raise ValueError("Profile name cannot be empty.")
    if "niche" not in updated_profile or not updated_profile["niche"].strip():
        raise ValueError("Niche cannot be empty.")
    if "audience" not in updated_profile or not updated_profile["audience"].strip():
        raise ValueError("Audience cannot be empty.")

    tone_rules = updated_profile.get("tone_rules", [])
    if not isinstance(tone_rules, list):
        raise ValueError("tone_rules must be a list of strings.")
    tone_rules = [r.strip() for r in tone_rules if isinstance(r, str) and r.strip()]

    memory["profile"] = {
        "name": updated_profile["name"].strip(),
        "niche": updated_profile["niche"].strip(),
        "audience": updated_profile["audience"].strip(),
        "tone_rules": tone_rules,
    }

    if updated_best_practices:
        post_length = updated_best_practices.get("post_length", memory["best_practices"].get("post_length", "120-220 words"))
        structure = updated_best_practices.get("structure", memory["best_practices"].get("structure", []))

        if not isinstance(structure, list) or not all(isinstance(s, str) for s in structure):
            raise ValueError("Structure must be a list of strings.")

        structure = [s.strip() for s in structure if s.strip()]
        memory["best_practices"]["post_length"] = str(post_length).strip()
        memory["best_practices"]["structure"] = structure

    save_memory(memory)


def list_available_chat_models() -> list[str]:
    """
    Fetch models from OpenAI and return a filtered list of chat-capable models.
    """
    # Use the shared client via openai_shared
    from openai_shared import get_client

    client = get_client()
    models = client.models.list()
    model_ids = [m.id for m in models.data]

    filtered = [
        m for m in model_ids
        if any(prefix in m for prefix in ["gpt-4", "gpt-4.1", "gpt-4o", "gpt-5"])
        and "audio" not in m
        and "realtime" not in m
        and "vision" not in m
    ]

    return sorted(filtered)