"""Streamlit web app — Project Jam Matrix / CRT terminal UI (green phosphor on black)."""

from __future__ import annotations

import html
import inspect
import os
import re
import time

import streamlit as st

from src.config import ANALYST_ARCHETYPES, EXA_API_KEY, GROK_API_KEY, GROK_MODEL_FAST
from src.context_retrieval import fetch_web_context_markdown
from src.idea_exporter import export_to_notion
from src.llm_analysts import generate_ideas_combined
from src.summary_generator import (
    calculate_conviction,
    extract_arguments_from_summary,
    format_exec_summary,
    parse_trackable_elements,
)


def _strip_md_for_terminal(text: str) -> str:
    """Light markdown cleanup (used for raw brainstorm snippets)."""
    if not text:
        return ""
    t = text.replace("\r\n", "\n")
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    lines_out: list[str] = []
    for line in t.split("\n"):
        ln = line.strip()
        if ln.startswith("|") and ln.endswith("|"):
            ln = re.sub(r"\|+", " · ", ln).replace("─", "-")
        lines_out.append(line.rstrip())
    return "\n".join(lines_out).strip()


def _format_readable_cell(cell: str) -> str:
    """Turn <br> inside a table cell into indented line breaks (tables are one line per row in source)."""
    c = cell.strip()
    c = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n       ", c)
    return c


def _format_readable_exec_text(text: str) -> str:
    """Executive summary as plain, paragraph-friendly terminal text (minimal markdown noise)."""
    if not text:
        return ""
    t = text.replace("\r\n", "\n")
    t = re.sub(r"```[\w]*\n?", "", t)
    t = re.sub(r"```\s*$", "", t)
    t = re.sub(r"(?m)^#{1,6}\s*", "", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"__([^_]+)__", r"\1", t)
    t = re.sub(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^>\s*", "", t, flags=re.MULTILINE)

    lines = t.split("\n")
    out: list[str] = []
    prev_was_idea_row = False
    for raw in lines:
        line = raw.strip()
        if not line:
            out.append("")
            prev_was_idea_row = False
            continue
        if re.match(r"^[\|\s:\-–—]+$", line) and re.search(r"[-–—]{2,}", line):
            continue
        if line.startswith("|") and line.endswith("|"):
            parts = [p.strip() for p in re.split(r"(?<!\\)\|", line) if p.strip()]
            if not parts:
                continue
            low0 = parts[0].lower()
            if low0 in ("pros", "idea", "cons", "ideas"):
                joined = " · ".join(parts)
                out.append(joined)
                out.append("")
                prev_was_idea_row = False
                continue
            if re.match(r"^\d+$", parts[0]):
                if prev_was_idea_row:
                    out.append("")
                    out.append("")
                fmt_cells = [_format_readable_cell(p) for p in parts]
                idea_no = fmt_cells[0]
                pro_block = fmt_cells[1] if len(fmt_cells) > 1 else ""
                con_block = fmt_cells[2] if len(fmt_cells) > 2 else ""
                out.append(f"  ─── Idea {idea_no} ───")
                if pro_block:
                    out.append(f"  PRO  {pro_block}")
                if con_block:
                    out.append(f"  CON  {con_block}")
                out.append("")
                prev_was_idea_row = True
                continue
            if prev_was_idea_row:
                out.append("")
            fmt_parts = [_format_readable_cell(p) for p in parts]
            out.append("  " + " · ".join(fmt_parts))
            prev_was_idea_row = False
            continue
        prev_was_idea_row = False
        line = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", line)
        out.append(line)

    merged = "\n".join(out)
    merged = re.sub(r"\n{4,}", "\n\n\n", merged)
    return merged.strip()


def _follow_up_suggestions(theme: str) -> list[str]:
    t = (theme or "").strip() or "current theme"
    return [
        f">> scan catalysts :: {t}",
        f">> run comps :: {t}",
        f">> policy vector :: {t}",
        f">> stress bear :: {t}",
    ]


def _build_matrix_session_log(
    *,
    theme: str,
    summary: str | None,
    trackables: list[dict],
    critic: str,
    brainstorm: str,
    conviction_score: float | None,
) -> str:
    """Compose one scrolling terminal log: exec summary, trackables, [RISK]-tagged critic, conviction."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("  PROJECT JAM // MATRIX TERMINAL — SESSION LOG")
    lines.append(f"  QUERY: {theme}")
    lines.append("=" * 72)

    if summary:
        lines.append("")
        lines.append("=== EXEC SUMMARY ===")
        lines.append(_format_readable_exec_text(summary))

    if trackables:
        lines.append("")
        lines.append("=== TRACKABLES // GRID ===")
        for t in trackables:
            idea_display = t.get("idea_name") or f"Idea {t.get('idea_id', '')}"
            lines.append(
                f"  [ROW] {idea_display} | sym={t.get('ticker') or '—'} | "
                f"cat={t.get('catalyst') or '—'} | t={t.get('timeline') or '—'} | "
                f"m={t.get('metric') or '—'}"
            )

    if critic.strip():
        lines.append("")
        lines.append("=== CRITIC STREAM // MARK WITH [RISK] ===")
        for ln in critic.splitlines():
            s = ln.rstrip()
            if s:
                lines.append(f"  [RISK] {s}")
            else:
                lines.append("")
    elif brainstorm.strip():
        lines.append("")
        lines.append("=== BRAINSTORM (no critic delimiter) ===")
        lines.append(_strip_md_for_terminal(brainstorm[:4000]))
        if len(brainstorm) > 4000:
            lines.append("  [... truncated ...]")

    if conviction_score is not None:
        lines.append("")
        lines.append("=== CONVICTION ===")
        lines.append(f"  PORTFOLIO_SCORE: {conviction_score}/10")

    lines.append("")
    lines.append("=" * 72)
    lines.append("  END OF TRANSMISSION")
    return "\n".join(lines)


def _push_query_history(theme: str) -> None:
    h: list[str] = list(st.session_state.query_history)
    t = theme.strip()
    if not t:
        return
    if t in h:
        h.remove(t)
    h.insert(0, t)
    st.session_state.query_history = h[:15]


def _render_generate_ideas_button() -> bool:
    """Primary action: explicit label so users know it runs idea generation."""
    sig = inspect.signature(st.button)
    gen_kw: dict[str, str | object] = {
        "key": "execute_query",
    }
    if "type" in sig.parameters:
        gen_kw["type"] = "primary"
    return bool(st.button("▶ GENERATE INVESTMENT IDEAS", **gen_kw))


def _render_notion_export_button(theme: str) -> None:
    sig = inspect.signature(st.button)
    export_kw: dict[str, str | object] = {
        "key": "export_notion",
    }
    if "type" in sig.parameters:
        export_kw["type"] = "primary"
    if st.button("⬆ PUSH SESSION TO NOTION", **export_kw):
        try:
            msg = export_to_notion(
                st.session_state.summary,
                st.session_state.trackables,
                theme,
            )
            st.success(msg)
        except (ValueError, RuntimeError) as e:
            st.error(str(e))


def _terminal_pre(content: str, *, max_h: str = "520px") -> str:
    esc = html.escape(content)
    return (
        f'<pre class="matrix-terminal-pane matrix-stream" style="max-height:{max_h}">{esc}</pre>'
    )


# --- Page config (must be first Streamlit command) ---
st.set_page_config(
    page_title="Project Jam Matrix Terminal",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Matrix / CRT CSS ---
# Phosphor green on pure black; white for labels/inputs; scanlines + glow; faint "rain" via gradients.
_MATRIX_CRT_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');

    :root {
        --mx-bg: #000000;
        --mx-green: #00ff41;
        --mx-green-bright: #00ff00;
        --mx-input: #ffffff;
        --mx-fs: 15px;
        --mx-fs-sm: 13px;
    }

    html, body, .stApp {
        font-family: "JetBrains Mono", ui-monospace, monospace !important;
        font-size: var(--mx-fs) !important;
        color: var(--mx-green) !important;
        background-color: var(--mx-bg) !important;
        text-shadow: 0 0 2px rgba(0, 255, 65, 0.35);
    }

    [data-testid="stAppViewContainer"] {
        background-color: var(--mx-bg) !important;
        background-image:
            repeating-linear-gradient(
                0deg,
                transparent,
                transparent 2px,
                rgba(0, 255, 65, 0.03) 2px,
                rgba(0, 255, 65, 0.03) 3px
            ),
            linear-gradient(rgba(0, 255, 65, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 65, 0.04) 1px, transparent 1px) !important;
        background-size: 100% 100%, 24px 24px, 24px 24px !important;
        position: relative !important;
    }

    [data-testid="stAppViewContainer"]::before {
        content: "";
        pointer-events: none;
        position: absolute;
        inset: 0;
        background: repeating-linear-gradient(
            0deg,
            transparent,
            transparent 3px,
            rgba(0, 0, 0, 0.5) 3px,
            rgba(0, 0, 0, 0.5) 4px
        );
        opacity: 0.22;
        z-index: 9999;
    }

    [data-testid="stHeader"] {
        background: var(--mx-bg) !important;
        border-bottom: 1px solid var(--mx-green) !important;
    }
    [data-testid="stDecoration"] { display: none; }

    h1, h2, h3, h4, label, .stMarkdown, .stMarkdown p, span {
        font-family: "JetBrains Mono", ui-monospace, monospace !important;
        color: var(--mx-green) !important;
    }

    .matrix-header-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: var(--mx-green) !important;
        text-shadow: 0 0 8px rgba(0, 255, 65, 0.55);
        margin: 0 0 4px 0;
    }
    .matrix-header-sub {
        font-size: var(--mx-fs-sm);
        color: var(--mx-input) !important;
        letter-spacing: 0.2em;
        margin: 0 0 8px 0;
        opacity: 0.95;
    }
    .matrix-status-line {
        font-size: var(--mx-fs-sm);
        color: var(--mx-green) !important;
        border: 1px solid var(--mx-green);
        padding: 6px 10px;
        margin-bottom: 10px;
        background: rgba(0, 255, 65, 0.04);
        text-shadow: 0 0 6px rgba(0, 255, 65, 0.4);
    }
    .matrix-section-label {
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--mx-green) !important;
        border-bottom: 1px solid var(--mx-green);
        margin: 12px 0 6px 0;
        padding-bottom: 2px;
        text-shadow: 0 0 4px rgba(0, 255, 65, 0.45);
    }
    .matrix-query-hint {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 4px;
        font-size: var(--mx-fs-sm);
        color: var(--mx-input) !important;
    }
    .matrix-cursor {
        display: inline-block;
        width: 0.55em;
        height: 1.1em;
        background: var(--mx-green);
        margin-left: 2px;
        vertical-align: text-bottom;
        animation: matrix-blink 1s step-end infinite;
        box-shadow: 0 0 4px var(--mx-green);
    }
    @keyframes matrix-blink {
        50% { opacity: 0; }
    }

    .matrix-terminal-pane, .matrix-stream {
        font-family: "JetBrains Mono", monospace !important;
        font-size: var(--mx-fs-sm) !important;
        line-height: 1.52;
        color: var(--mx-green) !important;
        background: var(--mx-bg) !important;
        border: 1px solid var(--mx-green);
        padding: 12px;
        margin: 0;
        overflow: auto;
        white-space: pre-wrap;
        word-break: break-word;
        text-shadow: 0 0 5px rgba(0, 255, 65, 0.35);
        box-shadow: inset 0 0 24px rgba(0, 255, 65, 0.06);
    }

    .stTextInput label, .stSelectbox label, .stCheckbox label {
        color: var(--mx-input) !important;
        font-size: var(--mx-fs-sm) !important;
    }
    .stTextInput input {
        background: var(--mx-bg) !important;
        color: var(--mx-input) !important;
        border: 1px solid var(--mx-green) !important;
        border-radius: 0 !important;
        font-family: "JetBrains Mono", monospace !important;
        caret-color: var(--mx-green);
    }
    .stTextInput input:focus {
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.35) !important;
    }
    div[data-baseweb="select"] > div {
        background: var(--mx-bg) !important;
        border-color: var(--mx-green) !important;
        color: var(--mx-green) !important;
    }
    .stSlider label { color: var(--mx-green) !important; font-size: var(--mx-fs-sm) !important; }
    .stSlider [data-baseweb="slider"] [role="slider"] {
        background-color: var(--mx-green) !important;
    }
    .stSlider [data-testid="stTickBar"] {
        background: rgba(0, 255, 65, 0.2) !important;
    }

    .stButton > button {
        font-family: "JetBrains Mono", monospace !important;
        border-radius: 3px !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        border: 2px solid #00ff41 !important;
        text-transform: none !important;
        transition: transform 0.06s ease, box-shadow 0.12s ease !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(180deg, #3dff6e 0%, #00ff41 38%, #00cc35 100%) !important;
        color: var(--mx-bg) !important;
        text-shadow: 0 1px 0 rgba(255, 255, 255, 0.22) !important;
        border: 2px solid #00ff88 !important;
        border-bottom: 5px solid #006633 !important;
        border-right: 3px solid #008844 !important;
        box-shadow:
            0 5px 0 #001a0d,
            0 8px 18px rgba(0, 255, 65, 0.28),
            inset 0 1px 0 rgba(255, 255, 255, 0.28) !important;
    }
    .stButton > button[kind="primary"]:hover {
        filter: brightness(1.06) !important;
        box-shadow:
            0 5px 0 #001a0d,
            0 10px 22px rgba(0, 255, 65, 0.38),
            inset 0 1px 0 rgba(255, 255, 255, 0.32) !important;
    }
    .stButton > button[kind="primary"]:active {
        transform: translateY(3px) !important;
        border-bottom-width: 2px !important;
        box-shadow:
            0 2px 0 #001a0d,
            0 4px 10px rgba(0, 255, 65, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    }
    .stButton > button[kind="secondary"] {
        background: var(--mx-bg) !important;
        color: var(--mx-green) !important;
    }

    .matrix-export-zone-title {
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--mx-input) !important;
        margin: 16px 0 6px 0;
        padding: 8px 10px;
        border: 1px dashed rgba(0, 255, 65, 0.45);
        background: rgba(0, 255, 65, 0.04);
    }
    .matrix-export-zone-desc {
        font-size: var(--mx-fs-sm);
        color: rgba(255, 255, 255, 0.82) !important;
        line-height: 1.45;
        margin: 0 0 10px 0;
        padding: 0 4px;
    }

    div[data-testid="stNotification"], .stAlert {
        background: var(--mx-bg) !important;
        border: 1px solid var(--mx-green) !important;
        color: var(--mx-green) !important;
        font-family: "JetBrains Mono", monospace !important;
    }

    .matrix-conviction-panel {
        border: 1px solid var(--mx-green);
        padding: 10px;
        background: rgba(0, 255, 65, 0.05);
        margin-top: 6px;
    }
    .matrix-conviction-score {
        color: var(--mx-green);
        font-weight: 700;
        font-size: 1.05rem;
        text-shadow: 0 0 6px rgba(0, 255, 65, 0.5);
    }
    .matrix-conviction-bar {
        height: 6px;
        background: rgba(0, 255, 65, 0.15);
        margin-top: 8px;
    }
    .matrix-conviction-fill {
        height: 100%;
        background: var(--mx-green);
        box-shadow: 0 0 8px var(--mx-green);
    }

    .stCodeBlock, pre:not(.matrix-terminal-pane):not(.matrix-stream) {
        background: var(--mx-bg) !important;
        border: 1px solid var(--mx-green) !important;
        color: var(--mx-green) !important;
    }

    div[data-testid="stStatusWidget"] label { color: var(--mx-green) !important; }

    div[data-testid="column"] { padding-top: 0.1rem; padding-bottom: 0.1rem; }
</style>
"""

st.markdown(_MATRIX_CRT_CSS, unsafe_allow_html=True)

# --- Session defaults ---
if "summary" not in st.session_state:
    st.session_state.summary = None
if "trackables" not in st.session_state:
    st.session_state.trackables = []
if "arguments_list" not in st.session_state:
    st.session_state.arguments_list = []
if "last_gen_latency_s" not in st.session_state:
    st.session_state.last_gen_latency_s = None
if "last_brainstorm" not in st.session_state:
    st.session_state.last_brainstorm = ""
if "last_critic" not in st.session_state:
    st.session_state.last_critic = ""
if "query_history" not in st.session_state:
    st.session_state.query_history = []

# --- Archetype options (same mapping as before) ---
_archetype_labels: list[str] = ["0. Default (no preference)"]
_archetype_from_label: dict[str, str | None] = {"0. Default (no preference)": None}
for _i, _key in enumerate(ANALYST_ARCHETYPES.keys(), start=1):
    _data = ANALYST_ARCHETYPES[_key]
    _lbl = f"{_i}. {_data['display_name']} ({', '.join(_data['aliases'])})"
    _archetype_labels.append(_lbl)
    _archetype_from_label[_lbl] = _data["display_name"]

hist_col, center_col, right_col = st.columns([0.22, 0.48, 0.30])

terminal_slot = None
with hist_col:
    st.markdown(
        '<p class="matrix-section-label">Query history</p>',
        unsafe_allow_html=True,
    )
    for hi, q in enumerate(st.session_state.query_history):
        short = (q[:52] + "…") if len(q) > 52 else q
        if st.button(short, key=f"hist_{hi}", help=q):
            st.session_state.theme_input = q
    if not st.session_state.query_history:
        st.caption("No prior queries.")

with center_col:
    st.markdown(
        '<p class="matrix-header-title">PROJECT JAM // MATRIX TERMINAL</p>'
        '<p class="matrix-header-sub">QUERY INTERFACE v0.1</p>',
        unsafe_allow_html=True,
    )
    _lat_ms = "—"
    if st.session_state.last_gen_latency_s is not None:
        _lat_ms = str(int(round(st.session_state.last_gen_latency_s * 1000)))
    _grok_st = "GROK ONLINE" if GROK_API_KEY else "GROK OFFLINE"
    st.markdown(
        f'<div class="matrix-status-line">'
        f"{_grok_st} • LATENCY: {_lat_ms} ms • SESSION ACTIVE"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="matrix-query-hint"><span>query&gt;</span><span class="matrix-cursor"></span></div>',
        unsafe_allow_html=True,
    )
    q1, q2 = st.columns([3, 1])
    with q1:
        theme_input = st.text_input(
            " ",
            placeholder="natural language investment query...",
            label_visibility="collapsed",
            key="theme_input",
        )
    with q2:
        execute_clicked = _render_generate_ideas_button()
    st.caption(
        "Enter a theme above, then click **Generate investment ideas** — "
        "Grok streams raw output, then the pane below shows a cleaned session log."
    )
    row2_1, row2_2 = st.columns([2, 1])
    with row2_1:
        archetype_choice = st.selectbox(
            "Archetype",
            options=_archetype_labels,
            key="archetype_select",
        )
    with row2_2:
        use_web_context = st.checkbox(
            "Exa context",
            value=True,
            help="Fetches recent snippets; set EXA_API_KEY.",
            key="use_web_context",
        )

    terminal_slot = st.empty()

theme = theme_input.strip() if isinstance(theme_input, str) else ""
if not theme:
    theme = "AI in healthcare"

if use_web_context and not EXA_API_KEY:
    st.caption("EXA_API_KEY not set; run continues without web snippets.")

with right_col:
    st.markdown(
        '<p class="matrix-section-label">Conviction // weights</p>',
        unsafe_allow_html=True,
    )
    if st.session_state.arguments_list:
        args_list = st.session_state.arguments_list
        cols = st.columns(min(len(args_list), 3))
        weights_list: list[int] = []
        for i in range(len(args_list)):
            with cols[i % len(cols)]:
                w = st.slider(
                    f"Idea {i + 1}",
                    min_value=1,
                    max_value=10,
                    value=5,
                    key=f"weight_{i}",
                )
            weights_list.append(w)
        _conviction_score = calculate_conviction(args_list, weights_list)
        pct = (_conviction_score / 10) * 100
        st.markdown(
            f'<div class="matrix-conviction-panel">'
            f'<div class="matrix-conviction-score">PORTFOLIO CONVICTION: {_conviction_score}/10</div>'
            f'<div class="matrix-conviction-bar">'
            f'<div class="matrix-conviction-fill" style="width:{pct}%"></div></div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Generate ideas once to unlock conviction sliders.")

    st.markdown(
        '<p class="matrix-section-label">Suggested follow-ups</p>',
        unsafe_allow_html=True,
    )
    for s in _follow_up_suggestions(theme):
        st.markdown(f"`{html.escape(s)}`")

    st.markdown(
        '<p class="matrix-export-zone-title">Notion — push this session</p>'
        "<p class=\"matrix-export-zone-desc\">"
        "This is an <strong>action area</strong>, not just a heading. "
        "The button uploads your <strong>executive summary</strong> and "
        "<strong>trackable rows</strong> to Notion. "
        "Set <code>NOTION_API_KEY</code> and <code>NOTION_DATABASE_ID</code> in <code>.env</code>."
        "</p>",
        unsafe_allow_html=True,
    )
    if st.session_state.summary and st.session_state.trackables is not None:
        _render_notion_export_button(theme)
    else:
        st.caption("Run **Generate investment ideas** first to enable Notion push.")

# --- Generation (stream into terminal_slot) ---
if execute_clicked and terminal_slot is not None:
    try:
        prefetch: str | None = None
        t0 = time.perf_counter()
        with st.status("NEURAL LINK // STREAMING", expanded=True) as gen_status:
            if use_web_context:
                if EXA_API_KEY:
                    gen_status.write("[+] Pulling Exa context...")
                    prefetch = fetch_web_context_markdown(theme)
                    gen_status.write("[+] Context packet received." if prefetch else "[!] Empty context; proceeding.")
                else:
                    prefetch = ""
                    gen_status.write("[!] EXA_API_KEY missing; skip RAG.")
            gen_status.write("[+] Uplink: Grok combined stream...")
            combined_stream = generate_ideas_combined(
                theme,
                archetype=_archetype_from_label[archetype_choice],
                stream=True,
                use_web_context=use_web_context,
                retrieval_context=prefetch if use_web_context else None,
            )
            full_text = ""
            for chunk in combined_stream:
                full_text += chunk
                terminal_slot.markdown(
                    _terminal_pre(full_text, max_h="380px"),
                    unsafe_allow_html=True,
                )
            gen_status.write("[+] Stream complete.")

        st.session_state.last_gen_latency_s = time.perf_counter() - t0
        parts = full_text.split("===CRITIC===", 1)
        brainstorm = parts[0].strip() if parts else ""
        critic = parts[1].strip() if len(parts) > 1 else ""

        st.session_state.last_brainstorm = brainstorm
        st.session_state.last_critic = critic

        summary = format_exec_summary(brainstorm, critic)
        if os.getenv("DEBUG_BRAINSTORM"):
            with open("debug_brainstorm.txt", "w") as f:
                f.write(brainstorm)
        st.session_state.summary = summary
        st.session_state.trackables = parse_trackable_elements(summary)
        st.session_state.arguments_list = extract_arguments_from_summary(summary)
        _push_query_history(theme)
        st.rerun()
    except (RuntimeError, ValueError, Exception) as e:
        st.error(str(e))

# --- Fill terminal with composed log ---
if terminal_slot is not None:
    _sc_log: float | None = None
    if st.session_state.arguments_list:
        _w = [
            st.session_state.get(f"weight_{i}", 5)
            for i in range(len(st.session_state.arguments_list))
        ]
        _sc_log = calculate_conviction(st.session_state.arguments_list, _w)

    if st.session_state.summary:
        _log = _build_matrix_session_log(
            theme=theme,
            summary=st.session_state.summary,
            trackables=st.session_state.trackables or [],
            critic=st.session_state.last_critic or "",
            brainstorm=st.session_state.last_brainstorm or "",
            conviction_score=_sc_log,
        )
        terminal_slot.markdown(_terminal_pre(_log, max_h="560px"), unsafe_allow_html=True)
    elif not execute_clicked:
        _boot = (
            "PROJECT JAM MATRIX KERNEL\n"
            "----------------------------\n"
            "  Awaiting query. Enter theme, choose archetype, then click\n"
            "  « Generate investment ideas » on the right of the input row.\n"
            "  Model: "
            + GROK_MODEL_FAST
            + "\n"
        )
        terminal_slot.markdown(_terminal_pre(_boot, max_h="200px"), unsafe_allow_html=True)
