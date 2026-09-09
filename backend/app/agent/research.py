"""Optional Tavily-backed web research tool for program rules and dollar bands."""
from __future__ import annotations

from strands import tool

from ..config import TAVILY_API_KEY


@tool
def web_search(query: str) -> str:
    """Search the web for program rules, compensation bands, or filing requirements."""
    if not TAVILY_API_KEY:
        return "(web search unavailable; rely on general knowledge)"
    try:
        import httpx

        r = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 4},
            timeout=20,
        )
        r.raise_for_status()
        chunks = []
        for item in r.json().get("results", [])[:4]:
            chunks.append(f"- {item.get('title', '')}: {item.get('content', '')[:280]}")
        return "\n".join(chunks) or "(no results)"
    except Exception as exc:  # noqa: BLE001
        return f"(web search failed: {exc}; rely on general knowledge)"
