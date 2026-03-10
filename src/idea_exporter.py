"""Export investment ideas to Notion database."""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import NOTION_API_KEY, NOTION_DATABASE_ID
from .llm_analysts import generate_keywords_for_ideas


def _parse_table_row(line: str) -> tuple[str, str, str] | None:
    """Parse a markdown table row into (idea_num, pros, cons). Returns None if invalid."""
    if not line.startswith("|") or not line.endswith("|"):
        return None
    parts = re.split(r"(?<!\\)\|", line)
    if len(parts) < 4:
        return None
    idea_num = parts[1].strip()
    pros = parts[2].strip()
    cons = parts[3].strip()
    return (idea_num, pros, cons)


def _normalize_cell(text: str) -> str:
    """Normalize table cell: <br> to newline, unescape pipes."""
    return text.replace("<br>", "\n").replace("\\|", "|")


def _extract_from_pros(pros: str, label: str) -> str:
    """Extract content after **Label:** in pros text."""
    normalized = _normalize_cell(pros)
    pattern = rf"(\*\*)?{re.escape(label)}(\*\*)?\s*:\s*(.+?)(?=\n\s*(\*\*)?\w|\s*$)"
    m = re.search(pattern, normalized, re.DOTALL | re.IGNORECASE)
    if m:
        content = m.group(3).strip()
        content = re.sub(r"^\*+\s*|\s*\*+\s*$", "", content)
        return content.split("\n")[0].strip()
    return ""


def _parse_summary_to_rows(summary: str) -> list[dict[str, Any]]:
    """Parse exec summary markdown table into list of idea dicts (idea_num, pros, cons)."""
    lines = [ln.strip() for ln in summary.replace("\r\n", "\n").split("\n") if ln.strip()]
    if not lines or not lines[0].startswith("|") or "Pros" not in lines[0]:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[2:]:  # Skip header and separator
        parsed = _parse_table_row(line)
        if parsed:
            idea_num, pros, cons = parsed
            # Strip "Pro Idea N:" prefix from pros
            pros_clean = re.sub(
                r"^Pro Idea \d+:\s*(?:<br>|\n)*\s*", "", pros, flags=re.IGNORECASE
            )
            title = _extract_from_pros(pros_clean, "Idea")
            action = _extract_from_pros(pros_clean, "Action")
            if not title:
                title = pros_clean.split("\n")[0][:200] or f"Idea {idea_num}"
            rows.append(
                {
                    "idea_num": idea_num,
                    "title": title,
                    "action": action,
                    "pros": _normalize_cell(pros_clean),
                    "cons": _normalize_cell(cons),
                }
            )
    return rows


def _build_idea_rows(
    summary: str,
    trackables: list[dict[str, Any]],
    theme: str,
) -> list[dict[str, Any]]:
    """Build full idea rows with trackables, UUIDs, and keywords."""
    parsed = _parse_summary_to_rows(summary)
    if not parsed:
        return []

    track_by_num: dict[int, dict[str, Any]] = {
        t["idea_id"]: t for t in trackables if "idea_id" in t
    }

    for row in parsed:
        num = int(row["idea_num"]) if row["idea_num"].isdigit() else 0
        t = track_by_num.get(num, {})
        row["ticker"] = t.get("ticker") or ""
        row["catalyst"] = t.get("catalyst") or ""
        row["timeline"] = t.get("timeline") or ""
        row["metric"] = t.get("metric") or ""
        row["theme"] = theme
        row["idea_id"] = str(uuid.uuid4())

    # Generate keywords via LLM
    summaries = [r["pros"][:400] for r in parsed]
    keywords_list = generate_keywords_for_ideas(summaries)
    for i, row in enumerate(parsed):
        row["keywords"] = keywords_list[i] if i < len(keywords_list) else []

    return parsed


def _to_notion_properties(row: dict[str, Any], export_date: str) -> dict[str, Any]:
    """Convert idea row to Notion API properties format."""
    def rich_text(content: str) -> dict:
        return {"rich_text": [{"text": {"content": (content or "")[:2000]}}]}

    def title_content(content: str) -> dict:
        return {"title": [{"text": {"content": (content or "Untitled")[:2000]}}]}

    def multi_select(keywords: list[str]) -> dict:
        return {"multi_select": [{"name": k[:100]} for k in keywords[:5] if k]}

    def date_content(iso_date: str) -> dict:
        return {"date": {"start": iso_date}}

    return {
        "idea_id": rich_text(row.get("idea_id", "")),
        "Title": title_content(row.get("title", "")),
        "Theme": rich_text(row.get("theme", "")),
        "Ticker": rich_text(row.get("ticker", "")),
        "Action": rich_text(row.get("action", "")),
        "Catalyst": rich_text(row.get("catalyst", "")),
        "Timeline": rich_text(row.get("timeline", "")),
        "Metric": rich_text(row.get("metric", "")),
        "Pros": rich_text(row.get("pros", "")),
        "Cons": rich_text(row.get("cons", "")),
        "Keywords": multi_select(row.get("keywords", [])),
        "Date": date_content(export_date),
    }


def export_to_notion(
    summary: str,
    trackables: list[dict[str, Any]],
    theme: str,
    database_id: str | None = None,
) -> str:
    """Export ideas to Notion database. Returns success message or raises error."""
    if not NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is not set. Add it to .env")
    db_id = database_id or NOTION_DATABASE_ID
    if not db_id:
        raise ValueError("NOTION_DATABASE_ID is not set. Add it to .env or pass database_id")

    from notion_client import Client

    rows = _build_idea_rows(summary, trackables, theme)
    if not rows:
        raise ValueError("No ideas to export from summary")

    export_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    client = Client(auth=NOTION_API_KEY)

    created = 0
    for row in rows:
        props = _to_notion_properties(row, export_date)
        try:
            client.pages.create(
                parent={"database_id": db_id.strip()},
                properties=props,
            )
            created += 1
        except Exception as e:
            raise RuntimeError(f"Failed to create Notion page for idea {row.get('idea_num')}: {e}") from e

    return f"Exported {created} idea(s) to Notion."
