# trend_agent.py
import re
import time
from datetime import datetime, timezone
from collections import Counter
from typing import Any

import feedparser
from rapidfuzz import fuzz

from openai_shared import llm


# --- RSS sources: mix of high-frequency + high-signal ---
RSS_FEEDS: dict[str, str] = {
    # High-frequency aggregators
    "HN Frontpage": "https://hnrss.org/frontpage",
    "HN Newest (>=50 pts)": "https://hnrss.org/newest?points=50",

    # Research stream
    "arXiv cs.AI": "https://rss.arxiv.org/rss/cs.AI",
    "arXiv cs.LG": "https://rss.arxiv.org/rss/cs.LG",
    "arXiv cs.CL": "https://rss.arxiv.org/rss/cs.CL",

    # Practical engineering
    "AWS Big Data": "https://aws.amazon.com/blogs/big-data/feed/",
    "AWS ML": "https://aws.amazon.com/blogs/machine-learning/feed/",

    # High-signal (lower frequency)
    "OpenAI": "https://openai.com/blog/rss.xml",
    "Google AI": "https://blog.google/technology/ai/rss/",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index/",
    "The Verge AI": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
}

# Weight sources so arXiv/HN doesn’t drown everything
SOURCE_WEIGHTS: dict[str, float] = {
    "HN Frontpage": 1.10,
    "HN Newest (>=50 pts)": 1.00,
    "arXiv cs.AI": 0.85,
    "arXiv cs.LG": 0.85,
    "arXiv cs.CL": 0.85,
    "AWS Big Data": 1.05,
    "AWS ML": 1.05,
    "OpenAI": 1.20,
    "Google AI": 1.15,
    "Ars Technica": 1.00,
    "The Verge AI": 1.00,
}

STOPWORDS = set("""
a an the and or to of in for on with from by how why what is are vs
this that these those your you we i it as at be been being into over
new launch launches released release update updates announces announcement
""".split())

AI_DE_KEYWORDS = [
    "agent", "agents", "llm", "rag", "retrieval", "vector", "embedding", "embeddings",
    "fine-tuning", "finetuning", "evaluation", "evals", "inference",
    "latency", "throughput", "tool calling", "function calling",
    "data pipeline", "pipelines", "streaming", "kafka", "spark", "airflow", "dbt",
    "warehouse", "lakehouse", "delta", "iceberg",
    "observability", "monitoring", "idempotent", "idempotency",
    "governance", "lineage",
]


def _clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains_keywords(text: str) -> bool:
    t = _clean(text)
    return any(k in t for k in AI_DE_KEYWORDS)


def fetch_headlines(max_items_per_feed: int = 30) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for e in feed.entries[:max_items_per_feed]:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            published = getattr(e, "published_parsed", None)

            if not title:
                continue

            if published:
                dt = datetime.fromtimestamp(time.mktime(published), tz=timezone.utc)
            else:
                dt = datetime.now(tz=timezone.utc)

            items.append({
                "source": source,
                "title": title,
                "link": link,
                "published_utc": dt.isoformat(),
                "published_ts": dt.timestamp(),
                "weight": SOURCE_WEIGHTS.get(source, 1.0),
            })
    return items


def cluster_topics(items: list[dict[str, Any]], similarity_threshold: int = 82) -> list[list[dict[str, Any]]]:
    clusters: list[list[dict[str, Any]]] = []
    for item in items:
        t = _clean(item["title"])
        placed = False
        for c in clusters:
            rep = _clean(c[0]["title"])
            if fuzz.token_set_ratio(t, rep) >= similarity_threshold:
                c.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])
    return clusters


def score_cluster_signal(cluster: list[dict[str, Any]], now_ts: float) -> float:
    """
    Signal score = frequency + recency, with source weights + keyword boost.
    Used only to rank candidates (not final selection).
    """
    freq = len(cluster)

    recency = 0.0
    for it in cluster:
        age_days = max(0.0, (now_ts - it["published_ts"]) / 86400.0)
        recency += (0.85 ** age_days) * float(it.get("weight", 1.0))

    rep_title = cluster[0]["title"]
    keyword_boost = 1.20 if _contains_keywords(rep_title) else 1.0

    return (freq * 1.2 + recency) * keyword_boost


def summarize_cluster(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    titles = [it["title"] for it in cluster]
    links = [it["link"] for it in cluster if it.get("link")]
    sources = sorted({it["source"] for it in cluster})

    tokens: list[str] = []
    for t in titles:
        for w in _clean(t).split():
            if w not in STOPWORDS and len(w) > 2:
                tokens.append(w)
    common_terms = [w for w, _ in Counter(tokens).most_common(10)]

    return {
        "representative_title": titles[0],
        "sources": sources,
        "links": links[:6],
        "cluster_size": len(cluster),
        "common_terms": common_terms,
        "sample_titles": titles[:5],
    }


def pick_most_teachable_topic(candidates: list[dict[str, Any]], model: str) -> dict[str, Any]:
    """
    Uses the SAME model passed from UI to choose the most valuable/teachable topic.
    """
    content, used_model = llm(
        [
            {"role": "system", "content": "Return only valid JSON. No markdown."},
            {
                "role": "user",
                "content": (
                    "You are a mentor for junior AI and data engineers.\n"
                    "Pick ONE topic that will produce the most valuable LinkedIn post this week.\n\n"
                    "Selection criteria (in order):\n"
                    "1) Teachable: allows clear explanation with a concrete example\n"
                    "2) Practical: connects to production/system design tradeoffs\n"
                    "3) Relevant: AI agents, RAG, inference, evals, data pipelines, streaming, monitoring\n"
                    "4) Not just news: avoid funding/PR unless it enables a real technical lesson\n\n"
                    "Return STRICT JSON with keys:\n"
                    "- chosen_index (int)\n"
                    "- chosen_topic (string)\n"
                    "- why_value (2-4 bullets)\n"
                    "- teaching_frame: {concept, common_misconception, practical_example_idea, takeaway}\n\n"
                    f"Candidates:\n{candidates}"
                ),
            },
        ],
        model=model,
    )

    try:
        result = __import__("json").loads(content)
    except Exception:
        result = {
            "chosen_index": 0,
            "chosen_topic": candidates[0]["representative_title"] if candidates else "",
            "why_value": ["Fallback selection due to non-JSON response."],
            "teaching_frame": {
                "concept": "Explain the topic clearly",
                "common_misconception": "People misunderstand what it means in practice",
                "practical_example_idea": "Use a simple system example",
                "takeaway": "What juniors should remember",
            },
            "_raw": content,
        }

    result["_meta"] = {"used_model": used_model}
    return result


def trending_topic_of_week_value(
    top_k: int = 6,
    min_cluster_size: int = 1,
    model: str = "",
) -> dict[str, Any]:
    """
    Value-first trend agent:
    1) Fetch headlines
    2) Cluster
    3) Score by signal -> top K candidates
    4) Use LLM (same model as UI) to pick most teachable candidate
    """
    if not model:
        return {"ok": False, "error": "Model must be provided."}

    items = fetch_headlines()
    if not items:
        return {"ok": False, "error": "No headlines found from RSS feeds."}

    now_ts = datetime.now(tz=timezone.utc).timestamp()
    clusters = cluster_topics(items)

    scored: list[tuple[float, list[dict[str, Any]]]] = []
    for c in clusters:
        if len(c) < min_cluster_size:
            continue
        scored.append((score_cluster_signal(c, now_ts), c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_clusters = [c for _, c in scored[:top_k]]
    candidates = [summarize_cluster(c) for c in top_clusters]

    if not candidates:
        return {"ok": False, "error": "No candidate topics after clustering/scoring."}

    selection = pick_most_teachable_topic(candidates, model=model)

    idx = int(selection.get("chosen_index", 0))
    idx = max(0, min(idx, len(candidates) - 1))
    chosen = candidates[idx]

    return {
        "ok": True,
        "chosen": chosen,
        "candidates": candidates,
        "selection": selection,
    }