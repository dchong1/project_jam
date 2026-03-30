"""Recent web snippets for Brainstormer prompts via Exa (optional)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _snippet_from_result(result: Any, max_chars: int) -> str:
    text = getattr(result, "text", None) or ""
    if not text.strip():
        highlights = getattr(result, "highlights", None)
        if highlights:
            text = " ".join(str(h) for h in highlights)
    if not text.strip():
        summary = getattr(result, "summary", None)
        if summary:
            text = str(summary)
    text = text.strip().replace("\r\n", "\n")
    if len(text) > max_chars:
        cut = text[:max_chars].rsplit(" ", 1)[0]
        text = cut + "…" if cut else text[:max_chars] + "…"
    return text


def _build_search_query(theme: str) -> str:
    theme = theme.strip()
    return (
        f"{theme} stock market investment companies earnings "
        "regulatory FDA SEC M&A news catalyst"
    )


def fetch_web_context_markdown(theme: str) -> str:
    """Return a markdown block for the Brainstormer prompt, or '' if disabled or on error."""
    from .config import (  # noqa: PLC0415
        EXA_API_KEY,
        EXA_NUM_RESULTS,
        EXA_RECENCY_DAYS,
        EXA_TEXT_MAX_CHARACTERS,
    )

    if not EXA_API_KEY or not theme.strip():
        return ""

    try:
        from exa_py import Exa  # noqa: PLC0415
    except ImportError:
        return ""

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=EXA_RECENCY_DAYS)

    try:
        exa = Exa(api_key=EXA_API_KEY)
        response = exa.search(
            _build_search_query(theme),
            num_results=EXA_NUM_RESULTS,
            start_published_date=start.isoformat(),
            end_published_date=end.isoformat(),
            contents={
                "text": {
                    "maxCharacters": min(EXA_TEXT_MAX_CHARACTERS + 300, 12000),
                }
            },
        )
    except Exception:
        return ""

    results = getattr(response, "results", None) or []
    lines: list[str] = []
    seen_urls: set[str] = set()
    idx = 0

    for r in results:
        url = getattr(r, "url", None) or getattr(r, "id", "") or ""
        if url in seen_urls:
            continue
        body = _snippet_from_result(r, EXA_TEXT_MAX_CHARACTERS)
        if not body:
            continue
        seen_urls.add(url)
        idx += 1
        title = getattr(r, "title", None) or "Untitled"
        pub = getattr(r, "published_date", None) or getattr(r, "publishedDate", None)
        pub_s = f" ({pub})" if pub else ""
        lines.append(f"**[{idx}]** {title}{pub_s}\nURL: {url}\n{body}")

    if not lines:
        return ""

    header = (
        "### Recent web sources (third-party snippets; not verified)\n"
        "Use these for timely names, events, and themes when helpful. "
        "Prefer facts that appear below; cite the bracket number [n] when you rely on a source. "
        "If a detail is not in the sources, say so or mark it as a hypothesis. "
        "If sources conflict, note the tension briefly.\n\n"
    )
    return header + "\n\n".join(lines) + "\n"
