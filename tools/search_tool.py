from typing import Any


_LOCAL_CORPUS = [
    {
        "title": "KazenAI enforcement primitives",
        "summary": "BudgetExceeded and LoopDetected are raised before runaway work continues.",
        "keywords": {"kazenai", "budget", "loop", "enforcement", "agent"},
    },
    {
        "title": "Recursive task risk",
        "summary": "Recursive prompts can cause repeated tool calls unless loop limits are enforced.",
        "keywords": {"recursive", "recursion", "loop", "search", "agent"},
    },
    {
        "title": "Local demo search",
        "summary": "This demo uses a deterministic local corpus so scenarios run without network access.",
        "keywords": {"demo", "local", "search", "scenario", "test"},
    },
]


def search_tool(query: str, **kwargs: Any) -> dict[str, Any]:
    """
    Deterministic local search with a deliberate recursive-risk fixture.
    """
    terms = {part.strip(".,:;!?()[]{}'\"").lower() for part in query.split()}
    if "recursive" in terms or "recursion" in terms:
        return {
            "result": (
                "Recursive task risk: repeated searches can spiral. "
                f"Suggested next query: {query}"
            ),
            "tool": "search_tool",
            "triggered_loop": True,
            "next_query": query,
        }

    scored: list[tuple[int, str, str]] = []
    for item in _LOCAL_CORPUS:
        score = len(terms & item["keywords"])
        if score:
            scored.append((score, item["title"], item["summary"]))
    if not scored:
        scored.append((0, "Local demo search", "No exact local match; query was recorded for review."))
    scored.sort(reverse=True)
    top = scored[0]
    return {
        "result": f"{top[1]}: {top[2]}",
        "tool": "search_tool",
        "triggered_loop": False,
        "matches": len(scored),
    }
