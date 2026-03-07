"""Summary formatting, trackable extraction, and conviction scoring."""

import re
from typing import Any

# Known field labels for robust extraction (order matters for lookahead)
_BRAINSTORM_LABELS = [
    "Idea",
    "Actionable Opportunity",
    "Underwritten Catalyst/Event",
    "Underwritten Catalyst",
    "Catalyst",
    "Supporting Arguments",
]
_CRITIC_LABELS = [
    "Counterarguments",
    "Constructive Suggestions",
    "Revised Actionable Opportunity",
]


def _parse_idea_blocks(text: str) -> list[dict[str, str]]:
    """Parse numbered idea blocks from brainstorm or critic text."""
    blocks: list[dict[str, str]] = []
    # Split by numbered items: 1., 2., 1), 2), or **1.** etc.
    pattern = r"\n\s*(?:\d+[\.\)]\s*|\*\*\d+\.\*\*\s*)"
    parts = re.split(pattern, text.strip())
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        # Skip short preamble (intro text before first idea)
        if i == 0 and len(part) < 30 and not re.search(
            r"(?:idea|actionable|catalyst|supporting|counterarguments|suggestions)\s*:",
            part,
            re.IGNORECASE,
        ):
            continue
        blocks.append({"raw": part})
    return blocks


def _extract_field(
    block: str,
    label: str,
    next_labels: list[str] | None = None,
) -> str:
    """Extract content after a field label. Handles markdown, bullets, varied formatting."""
    # Build regex for label: allow - * ** before, optional : after
    label_esc = re.escape(label)
    # Patterns: "Idea:", "- Idea:", "**Idea:**", "Idea :", "* Idea:"
    label_pattern = rf"(?:^|\n)\s*[\-\*•]?\s*\*{{0,2}}\s*{label_esc}\s*\*{{0,2}}\s*:\s*"
    # Content until next label or bullet or numbered item
    next_pat = r"(?=\n\s*[\-\*•]\s*\w|\n\s*\d+[\.\)]|\n\s*\*\*\d+\.|$)"
    if next_labels:
        next_label_alt = "|".join(re.escape(l) for l in next_labels)
        next_pat = rf"(?=\n\s*[\-\*•]?\s*\*{{0,2}}\s*(?:{next_label_alt})\s*:|{next_pat})"
    patterns = [
        rf"{label_pattern}(.+?){next_pat}",
        rf"{label_pattern}(.+)",
        rf"(?:^|\n)\s*{label_esc}\s*:\s*(.+?)(?=\n\s*[\-\*•]\s|\n\s*\d+\.|$)",
        rf"{label_esc}\s*:\s*(.+?)(?=\n\s*[\-\*•]\s|\n\s*\d+\.|$)",
        rf"{label_esc}\s*:\s*(.+)",
    ]
    for pat in patterns:
        try:
            m = re.search(pat, block, re.DOTALL | re.IGNORECASE)
            if m:
                content = m.group(1).strip()
                # Strip leading markdown artifacts (*, **)
                content = re.sub(r"^\*+\s*", "", content)
                if content and len(content) > 1:
                    return content
        except re.error:
            continue
    # Fallback: line-based extraction for "Label: content" (single or multi-line)
    lines = block.split("\n")
    for i, line in enumerate(lines):
        m = re.search(
            rf"[\-\*•]?\s*\*{{0,2}}\s*{re.escape(label)}\s*\*{{0,2}}\s*:\s*(.+)",
            line,
            re.IGNORECASE,
        )
        if m:
            content = m.group(1).strip()
            # Append continuation lines until next field label
            j = i + 1
            field_start = re.compile(
                r"^\s*[\-\*•]\s*(?:Idea|Actionable|Underwritten|Catalyst|Supporting|"
                r"Counterarguments|Constructive|Revised)\s*:",
                re.IGNORECASE,
            )
            while j < len(lines) and lines[j].strip() and not field_start.match(lines[j]):
                content += " " + lines[j].strip()
                j += 1
            if content:
                content = re.sub(r"^\*+\s*", "", content)
                return content
    return ""


def _extract_brainstorm_fields(block: str) -> dict[str, str]:
    """Extract Idea, Action, Catalyst, Args from a brainstorm block."""
    return {
        "idea": _extract_field(
            block, "Idea", ["Actionable Opportunity"]
        ) or _extract_field(block, "idea", ["Actionable Opportunity"]),
        "action": _extract_field(
            block,
            "Actionable Opportunity",
            ["Underwritten Catalyst/Event", "Underwritten Catalyst", "Supporting Arguments"],
        ) or _extract_field(
            block,
            "actionable opportunity",
            ["Underwritten Catalyst/Event", "Underwritten Catalyst", "Supporting Arguments"],
        ),
        "catalyst": _extract_field(
            block, "Underwritten Catalyst/Event", ["Supporting Arguments"]
        ) or _extract_field(block, "Underwritten Catalyst", ["Supporting Arguments"])
        or (
            _extract_field(block, "Catalyst", ["Supporting Arguments"])
            if "Underwritten Catalyst" not in block
            else ""
        ),
        "args": _extract_field(block, "Supporting Arguments")
        or _extract_field(block, "supporting arguments"),
    }


def _extract_critic_fields(block: str) -> dict[str, str]:
    """Extract Counterarguments, Suggestions, Revised from a critic block."""
    return {
        "counterarguments": _extract_field(
            block, "Counterarguments", ["Constructive Suggestions"]
        ) or _extract_field(block, "counterarguments", ["Constructive Suggestions"]),
        "suggestions": _extract_field(
            block, "Constructive Suggestions", ["Revised Actionable Opportunity"]
        ) or _extract_field(
            block, "constructive suggestions", ["Revised Actionable Opportunity"]
        ),
        "revised": _extract_field(block, "Revised Actionable Opportunity")
        or _extract_field(block, "revised actionable opportunity"),
    }


def format_exec_summary(brainstorm: str, critic: str) -> str:
    """Produce Markdown table summary with Pros and Cons paired for easy evaluation."""
    brainstorm_blocks = _parse_idea_blocks(brainstorm)
    critic_blocks = _parse_idea_blocks(critic)

    rows: list[str] = []
    for i, b_block in enumerate(brainstorm_blocks):
        n = i + 1
        b_fields = _extract_brainstorm_fields(b_block.get("raw", ""))
        c_fields = (
            _extract_critic_fields(critic_blocks[i].get("raw", ""))
            if i < len(critic_blocks)
            else {}
        )

        # Pros cell: Pro Idea N: for parser compatibility, then structured fields
        # Use first line of idea in case extraction captured multiple lines
        idea_val = (b_fields.get("idea") or "").split("\n")[0].strip()
        pro_parts: list[str] = []
        if idea_val:
            pro_parts.append(f"**Idea:** {idea_val}")
        if b_fields.get("action"):
            pro_parts.append(f"**Action:** {b_fields['action']}")
        if b_fields.get("catalyst"):
            pro_parts.append(f"**Catalyst:** {b_fields['catalyst']}")
        if b_fields.get("args"):
            pro_parts.append(f"**Args:** {b_fields['args']}")
        pro_cell = f"Pro Idea {n}:\n\n" + "\n\n".join(pro_parts) if pro_parts else f"Pro Idea {n}:"

        # Cons cell: structured fields
        con_parts: list[str] = []
        if c_fields.get("counterarguments"):
            con_parts.append(f"**Counterarguments:** {c_fields['counterarguments']}")
        if c_fields.get("suggestions"):
            con_parts.append(f"**Suggestions:** {c_fields['suggestions']}")
        if c_fields.get("revised"):
            con_parts.append(f"**Revised:** {c_fields['revised']}")
        con_cell = "\n\n".join(con_parts) if con_parts else "—"

        # Escape pipe chars in cells for Markdown table
        def _escape_pipe(s: str) -> str:
            return s.replace("|", "\\|").replace("\n", "<br>")

        rows.append(f"| {n} | {_escape_pipe(pro_cell)} | {_escape_pipe(con_cell)} |")

    header = "| Idea | Pros | Cons |\n|:----:|------|------|"
    return "\n".join([header] + rows)


def _normalize_table_cell(text: str) -> str:
    """Normalize table cell content: <br> to newline, unescape pipes."""
    return text.replace("<br>", "\n").replace("\\|", "|")


def parse_trackable_elements(summary: str) -> list[dict[str, Any]]:
    """Extract catalysts, timelines, metrics as list of dicts."""
    elements: list[dict[str, Any]] = []
    idea_id = 0
    normalized = _normalize_table_cell(summary)

    # Split by "Pro Idea N:"
    pro_pattern = r"Pro Idea (\d+):"
    for m in re.finditer(pro_pattern, normalized, re.IGNORECASE):
        idea_id = int(m.group(1))
        start = m.end()
        next_m = re.search(pro_pattern, normalized[start:], re.IGNORECASE)
        end = start + next_m.start() if next_m else len(normalized)
        block = normalized[start:end]

        # Extract Catalyst (standalone "**Catalyst:**" or "Catalyst:", not "Underwritten Catalyst")
        catalyst_m = re.search(
            r"(?<!Underwritten )(?:\*\*)?Catalyst(?:\*\*)?\s*:\s*([^|]+?)(?=\n\s*(?:\*\*)?Args\s*:|\s*\|\s*Args:|\s*Con:|\s*\|\s*|$)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        catalyst = ""
        if catalyst_m:
            catalyst = re.sub(r"^\s*\*+\s*|\s*\*+\s*$", "", catalyst_m.group(1).strip())

        # Extract Action (stop at Catalyst, Args, table separator, or Con)
        action_m = re.search(
            r"(?:\*\*)?Action(?:\*\*)?\s*:\s*([^|]+?)(?=\n\s*(?:\*\*)?(?:Catalyst|Args)\s*:|\s*\|\s*(?:Catalyst|Args):|\s*Con:|\s*\|\s*|$)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        action = ""
        if action_m:
            action = re.sub(r"^\s*\*+\s*|\s*\*+\s*$", "", action_m.group(1).strip())

        # Timeline patterns: Q1-Q4 YYYY, YYYY, N-N months, etc.
        timeline_patterns = [
            r"Q[1-4]\s*\d{4}",
            r"\d{4}",
            r"\d+\s*-\s*\d+\s*(?:months?|years?)",
            r"\d+\s*(?:months?|years?)",
        ]
        timeline = ""
        for pat in timeline_patterns:
            t = re.search(pat, block + " " + action + " " + catalyst)
            if t:
                timeline = t.group(0)
                break

        # Metric patterns: >N%, N% YoY, etc.
        metric_patterns = [
            r">\s*\d+(?:\.\d+)?\s*%",
            r"\d+(?:\.\d+)?\s*%\s*(?:YoY|yoy|growth)?",
            r"\d+(?:\.\d+)?x",
        ]
        metric = ""
        for pat in metric_patterns:
            mt = re.search(pat, block + " " + catalyst)
            if mt:
                metric = mt.group(0)
                break

        # Ticker: Long [TICKER] or common stock symbols (2-5 uppercase letters)
        ticker_m = re.search(
            r"(?:Long|Short)\s+([A-Z]{2,5})\b",
            action + " " + block,
            re.IGNORECASE,
        )
        ticker = ticker_m.group(1).upper() if ticker_m else ""

        elements.append(
            {
                "idea_id": idea_id,
                "catalyst": catalyst or None,
                "timeline": timeline or None,
                "metric": metric or None,
                "ticker": ticker or None,
            }
        )

    return elements


def extract_arguments_from_summary(summary: str) -> list[str]:
    """Extract supporting arguments from summary for conviction scoring."""
    args_list: list[str] = []
    normalized = _normalize_table_cell(summary)
    # Match "Args:" (not "Arguments") before Con, Counterarguments, table separator, or next Pro Idea
    for m in re.finditer(
        r"(?:\*\*)?Args(?!uments)(?:\*\*)?\s*:\s*([^|]+?)(?=\s*Con:|\s*Counterarguments:|\s*\|\s*|\s*Pro Idea \d+:|$)",
        normalized,
        re.DOTALL | re.IGNORECASE,
    ):
        arg = re.sub(r"^\s*\*+\s*|\s*\*+\s*$", "", m.group(1).strip())
        if arg:
            args_list.append(arg)
    return args_list


def calculate_conviction(arguments_list: list[str], weights_list: list[int]) -> float:
    """Compute weighted conviction score (0-10 scale)."""
    if not arguments_list or not weights_list:
        return 0.0
    # Clamp weights to 1-10
    clamped = [max(1, min(10, w)) for w in weights_list[: len(arguments_list)]]
    # Pad or trim to match
    while len(clamped) < len(arguments_list):
        clamped.append(5)  # default weight
    clamped = clamped[: len(arguments_list)]
    # Normalized score: sum(weights) / (len * 10) gives 0-1, scale to 0-10
    total = sum(clamped)
    max_possible = len(clamped) * 10
    return round((total / max_possible) * 10, 2) if max_possible > 0 else 0.0
