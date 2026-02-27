# openai_shared.py
import os
from openai import OpenAI


def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Put it in .env or export it.")
    return OpenAI(api_key=api_key)


def llm(messages, model: str) -> tuple[str, str]:
    """
    Shared LLM helper: returns (content, used_model)
    """
    if not model or not isinstance(model, str):
        raise ValueError("model must be a non-empty string")

    client = get_client()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    used_model = getattr(resp, "model", model)
    return resp.choices[0].message.content, used_model