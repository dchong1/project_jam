"""Streamlit web app for the Investment Idea Generator."""

import html
import os
import re

import streamlit as st

from src.config import ANALYST_ARCHETYPES, resolve_archetype
from src.llm_analysts import generate_ideas_combined
from src.summary_generator import (
    format_exec_summary,
    parse_trackable_elements,
    extract_arguments_from_summary,
    calculate_conviction,
)
from src.idea_exporter import export_to_notion


def _parse_table_row(line: str) -> tuple[str, str, str] | None:
    """Parse a markdown table row into (idea_num, pros, cons). Returns None if invalid."""
    if not line.startswith("|") or not line.endswith("|"):
        return None
    # Split on | that is not preceded by backslash (escaped pipe in cell content)
    parts = re.split(r"(?<!\\)\|", line)
    # Expect: ["", "idea", "pros", "cons", ""] or ["", "idea", "pros", "cons"]
    if len(parts) < 4:
        return None
    idea_num = parts[1].strip()
    pros = parts[2].strip()
    cons = parts[3].strip()
    return (idea_num, pros, cons)


def _summary_to_html(summary: str) -> str:
    """Convert markdown table summary to HTML with side-by-side Pro/Con cards."""
    # Normalize line endings and filter empty lines
    lines = [ln.strip() for ln in summary.replace("\r\n", "\n").split("\n") if ln.strip()]
    if not lines or not lines[0].startswith("|") or "Pros" not in lines[0]:
        return f"<div class='exec-summary'>{summary}</div>"

    def _cell_to_html(cell: str) -> str:
        # Restore pipe chars, preserve <br> for line breaks, escape HTML, then bold
        unescaped = cell.replace("\\|", "|")
        # Use placeholder so html.escape doesn't turn <br> into &lt;br&gt;
        placeholder = "\u0001BR\u0001"
        with_placeholder = unescaped.replace("<br>", placeholder)
        safe = html.escape(with_placeholder).replace(placeholder, "<br>")
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)

    cards_html = []
    for line in lines[2:]:  # Skip header and separator
        parsed = _parse_table_row(line)
        if parsed:
            idea_num, pros_raw, cons_raw = parsed
            # Extract header for the blue bar: prefer **Header:**, fallback to **Idea:**, then Idea N
            header_match = re.search(
                r"Header\s*:\s*\*\*\s*([^<]+?)(?=<br>)",
                pros_raw,
                re.IGNORECASE,
            )
            if header_match:
                header_text = header_match.group(1).strip()
            else:
                idea_name_match = re.search(
                    r"Idea\s*:\s*\*\*\s*([^<]+?)(?=<br>|\n)",
                    pros_raw,
                    re.IGNORECASE,
                )
                header_text = idea_name_match.group(1).strip() if idea_name_match else f"Idea {idea_num}"
            if not header_text:
                header_text = f"Idea {idea_num}"
            # Strip "Pro Idea N:" prefix and **Header:** line from Pros content (keep header bar only)
            pros_raw = re.sub(r"^Pro Idea \d+:\s*(?:<br>|\n)*\s*", "", pros_raw)
            pros_raw = re.sub(
                r"(?:<br>|\n)*\s*\*\*Header\*\*\s*:\s*[^<]+(?:<br>|\n)*",
                "",
                pros_raw,
                count=1,
                flags=re.IGNORECASE,
            )
            pros = _cell_to_html(pros_raw)
            cons = _cell_to_html(cons_raw)
            cards_html.append(
                f'<div class="idea-row">'
                f'<div class="idea-header">{html.escape(header_text)}</div>'
                f'<div class="pro-con-container">'
                f'<div class="pro-card"><div class="pro-label">✓ Pros</div><div class="pro-content">{pros}</div></div>'
                f'<div class="con-card"><div class="con-label">✗ Cons</div><div class="con-content">{cons}</div></div>'
                f'</div></div>'
            )
    if not cards_html:
        return f"<div class='exec-summary'>{summary}</div>"

    return f'<div class="exec-summary-cards">{"".join(cards_html)}</div>'


def _trackables_to_html(trackables: list[dict]) -> str:
    """Convert trackable elements to research-style HTML table."""
    if not trackables:
        return ""
    rows = []
    for t in trackables:
        idea_display = t.get("idea_name") or f"Idea {t.get('idea_id', '')}"
        ticker = t.get("ticker") or "—"
        catalyst = html.escape(str(t.get("catalyst") or "—"))
        timeline = t.get("timeline") or "—"
        metric = t.get("metric") or "—"
        ticker_class = ' class="ticker"' if ticker and ticker != "—" else ""
        rows.append(
            f"<tr>"
            f'<td style="font-weight:600">{html.escape(str(idea_display))}</td>'
            f"<td{ticker_class}>{html.escape(str(ticker))}</td>"
            f"<td>{catalyst}</td>"
            f"<td>{html.escape(str(timeline))}</td>"
            f"<td>{html.escape(str(metric))}</td>"
            f"</tr>"
        )
    table = (
        '<table class="trackable-table">'
        "<thead><tr>"
        "<th>Ideas</th><th>Ticker</th><th>Catalyst</th><th>Timeline</th><th>Metric</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    return table


# Page config (must be first Streamlit command)
st.set_page_config(
    page_title="- Ideas Generators -",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Nordic theme: clean, minimalist, arctic-inspired palette
_NORDIC_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=DM+Serif+Display&display=swap');

    :root {
        --nord0: #2E3440;
        --nord1: #3B4252;
        --nord3: #4C566A;
        --nord4: #D8DEE9;
        --nord5: #E5E9F0;
        --nord6: #ECEFF4;
        --nord8: #88C0D0;
        --nord9: #81A1C1;
        --nord10: #5E81AC;
    }

    /* Hero section */
    .hero-container {
        text-align: center;
        padding: 2rem 0 1rem;
        max-width: 640px;
        margin: 0 auto;
    }
    .hero-title {
        font-family: 'DM Serif Display', Georgia, serif !important;
        font-size: 2.25rem;
        font-weight: 400;
        color: var(--nord0);
        margin-bottom: 0.75rem;
    }
    .hero-description {
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 0.8rem;
        font-style: italic;
        line-height: 1.6;
        color: var(--nord3);
    }
    .hero-image {
        margin: 1.5rem auto 0.5rem;
        border-radius: 12px;
        overflow: hidden;
        max-width: 640px;
        width: 100%;
        aspect-ratio: 21 / 9;
        object-fit: cover;
    }

    /* Report-style section headers */
    .report-section-title {
        font-size: 0.75rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--nord0);
        font-weight: 600;
        margin-bottom: 0.5rem;
        padding-bottom: 0.25rem;
        border-bottom: 2px solid var(--nord4);
    }

    .stApp {
        background: var(--nord6) !important;
    }

    [data-testid="stAppViewContainer"] {
        background: var(--nord6) !important;
    }

    [data-testid="stHeader"] {
        background: rgba(255,255,255,0.9) !important;
        border-bottom: 1px solid var(--nord4);
    }

    h1, h2, h3 {
        font-family: 'Inter', system-ui, sans-serif !important;
        color: var(--nord0) !important;
        font-weight: 600 !important;
    }

    .stMarkdown, p, label, span {
        font-family: 'Inter', system-ui, sans-serif !important;
        color: var(--nord1) !important;
    }

    div[data-testid="stMetric"] {
        background: #FFFFFF !important;
        border: 1px solid var(--nord4);
        border-radius: 8px;
        padding: 1rem;
    }

    .stButton > button {
        font-family: 'Inter', system-ui, sans-serif !important;
        background: #FFFFFF !important;
        color: var(--nord0) !important;
        border: 1px solid var(--nord4) !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        padding: 0.5rem 1.25rem !important;
        transition: background 0.2s ease;
    }

    .stButton > button:hover {
        background: var(--nord5) !important;
    }

    /* Center Generate Ideas button: target vertical block inside button column */
    div[data-testid="column"]:has(.stButton) div[data-testid="stVerticalBlock"] {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
    }

    .stSelectbox > div > div {
        border-radius: 8px !important;
        border-color: var(--nord4) !important;
    }

    .stTextInput > div > div > input {
        border-radius: 8px !important;
        border-color: var(--nord4) !important;
    }

    .stSlider > div > div {
        background: var(--nord4) !important;
    }

    /* Executive summary table styling */
    .exec-summary-table {
        border-collapse: separate !important;
        border-spacing: 0 !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid var(--nord4) !important;
        font-family: 'Inter', system-ui, sans-serif !important;
        width: 100%;
    }
    .exec-summary-table th {
        background: var(--nord10) !important;
        color: #FFFFFF !important;
        padding: 0.75rem 1rem !important;
        font-weight: 600 !important;
        text-align: left !important;
    }
    .exec-summary-table td {
        padding: 1rem !important;
        border-bottom: 1px solid var(--nord4) !important;
        background: #FFFFFF !important;
        vertical-align: top !important;
    }
    .exec-summary-table tr:nth-child(even) td {
        background: var(--nord6) !important;
    }

    /* Side-by-side Pro/Con card layout */
    .exec-summary-cards {
        display: flex;
        flex-direction: column;
        flex-wrap: nowrap;
        align-items: stretch;
        gap: 1.5rem;
        font-family: 'Inter', system-ui, sans-serif !important;
        width: 100%;
    }
    .idea-row {
        display: block;
        width: 100%;
        min-width: 0;
        flex-shrink: 0;
        background: #FFFFFF;
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid var(--nord4);
        box-shadow: 0 2px 8px rgba(46, 52, 64, 0.06);
    }
    .idea-header {
        background: var(--nord10);
        color: #FFFFFF;
        padding: 0.5rem 1rem;
        font-weight: 600;
        font-size: 0.95rem;
    }
    .pro-con-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0;
        min-height: 120px;
        align-items: stretch;
    }
    .pro-card {
        padding: 1rem 1.25rem;
        background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
        border-right: 1px solid var(--nord4);
    }
    .con-card {
        padding: 1rem 1.25rem;
        background: linear-gradient(135deg, #fef2f2 0%, #fff1f2 100%);
    }
    .pro-label, .con-label {
        font-weight: 600;
        font-size: 0.85rem;
        margin-bottom: 0.5rem;
    }
    .pro-label { color: #059669; }
    .con-label { color: #dc2626; }
    .pro-content, .con-content {
        font-size: 0.9rem;
        line-height: 1.5;
        color: var(--nord1);
    }
    .pro-content strong, .con-content strong {
        color: var(--nord0);
    }
    @media (max-width: 768px) {
        .pro-con-container {
            grid-template-columns: 1fr;
        }
        .pro-card { border-right: none; border-bottom: 1px solid var(--nord4); }
    }

    .stMarkdown table {
        border-collapse: separate !important;
        border-spacing: 0 !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid var(--nord4) !important;
        font-family: 'Inter', system-ui, sans-serif !important;
    }

    .stMarkdown th {
        background: var(--nord10) !important;
        color: #FFFFFF !important;
        padding: 0.75rem 1rem !important;
        font-weight: 600 !important;
        text-align: left !important;
    }

    .stMarkdown td {
        padding: 1rem !important;
        border-bottom: 1px solid var(--nord4) !important;
        background: #FFFFFF !important;
    }

    .stMarkdown tr:nth-child(even) td {
        background: var(--nord6) !important;
    }

    /* Conviction score badge */
    .conviction-badge {
        display: inline-block;
        background: var(--nord10);
        color: #FFFFFF;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        font-family: 'Inter', system-ui, sans-serif;
    }

    /* Trackable Elements table */
    .trackable-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.875rem;
        font-family: 'Inter', system-ui, sans-serif;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid var(--nord4);
    }
    .trackable-table th {
        background: var(--nord10);
        color: #fff;
        padding: 0.6rem 1rem;
        text-align: left;
        font-weight: 600;
    }
    .trackable-table td {
        padding: 0.6rem 1rem;
        border-bottom: 1px solid var(--nord4);
    }
    .trackable-table tr:nth-child(even) td {
        background: var(--nord6);
    }
    .trackable-table .ticker {
        font-family: ui-monospace, monospace;
        font-weight: 600;
    }

    /* Conviction Level panel */
    .conviction-panel {
        background: #fff;
        border: 1px solid var(--nord4);
        border-radius: 8px;
        padding: 1.25rem;
        margin-top: 0.5rem;
    }
    .conviction-score-box {
        background: var(--nord10);
        color: #fff;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 1.1rem;
        margin-top: 1rem;
    }
    .conviction-bar {
        height: 8px;
        background: var(--nord4);
        border-radius: 4px;
        overflow: hidden;
        margin-top: 0.5rem;
    }
    .conviction-bar-fill {
        height: 100%;
        background: var(--nord10);
        border-radius: 4px;
        transition: width 0.2s ease;
    }

    /* Loading bar */
    .loading-bar-container {
        width: 100%;
        height: 3px;
        background: var(--nord4);
        border-radius: 2px;
        overflow: hidden;
        margin: 0.5rem 0 1rem;
    }
    .loading-bar-fill {
        height: 100%;
        width: 30%;
        background: var(--nord10);
        border-radius: 2px;
        animation: loading-slide 1.2s ease-in-out infinite;
    }
    @keyframes loading-slide {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(400%); }
    }
</style>
"""
st.markdown(_NORDIC_CSS, unsafe_allow_html=True)

# Hero section: centered title, description, and image
# Alternative Unsplash images (swap HERO_IMAGE_URL):
# Stock chart, analytics dashboard, laptop charts, abstract growth, clean workspace
HERO_IMAGE_URL = "https://images.unsplash.com/photo-1509443513700-bdc1caaf67e5?ixlib=rb-4.1.0&q=85&fm=jpg&crop=entropy&cs=srgb&w=4800"
MODEL_DESCRIPTION = (
    "Brainstormer generates ideas; critic refines. Produces pros/cons summary, "
    "trackable elements, and tunable conviction."
)

st.markdown(
    f'<div class="hero-container">'
    f'<h1 class="hero-title">- Ideas Generators -</h1>'
    f'<p class="hero-description">{MODEL_DESCRIPTION}</p>'
    f'<img src="{HERO_IMAGE_URL}" class="hero-image" alt="Investment analytics" />'
    f"</div>",
    unsafe_allow_html=True,
)

st.divider()

archetype_options = ["Default (no preference)"] + [
    f"{data['display_name']} ({', '.join(data['aliases'])})"
    for data in ANALYST_ARCHETYPES.values()
]
archetype_labels = {opt: None if opt == "Default (no preference)" else opt.split(" (")[0] for opt in archetype_options}
archetype_choice = st.selectbox(
    "Analyst style",
    options=archetype_options,
    key="archetype_select",
)
archetype = archetype_labels.get(archetype_choice)

theme_input = st.text_input(
    "Investment theme",
    value="",
    placeholder="AI in healthcare",
    key="theme_input",
)
theme = theme_input.strip() or "AI in healthcare"

# Initialize session state if needed
if "summary" not in st.session_state:
    st.session_state.summary = None
if "trackables" not in st.session_state:
    st.session_state.trackables = []
if "arguments_list" not in st.session_state:
    st.session_state.arguments_list = []

_, btn_col, _ = st.columns([2, 1, 2])
with btn_col:
    generate_clicked = st.button("Generate Ideas", key="generate_ideas")
if generate_clicked:
    loading_placeholder = st.empty()
    loading_placeholder.markdown(
        '<div class="loading-bar-container"><div class="loading-bar-fill"></div></div>',
        unsafe_allow_html=True,
    )
    try:
        combined_stream = generate_ideas_combined(
            theme, archetype=archetype, stream=True
        )
        full_text = ""
        output_placeholder = st.empty()
        for chunk in combined_stream:
            full_text += chunk
            output_placeholder.markdown(full_text)
        parts = full_text.split("===CRITIC===", 1)
        brainstorm = parts[0].strip() if parts else ""
        critic = parts[1].strip() if len(parts) > 1 else ""

        output_placeholder.empty()
        loading_placeholder.empty()
        summary = format_exec_summary(brainstorm, critic)
        if os.getenv("DEBUG_BRAINSTORM"):
            with open("debug_brainstorm.txt", "w") as f:
                f.write(brainstorm)
        st.session_state.summary = summary
        st.session_state.trackables = parse_trackable_elements(summary)
        st.session_state.arguments_list = extract_arguments_from_summary(summary)
    except (RuntimeError, ValueError, Exception) as e:
        loading_placeholder.empty()
        st.error(str(e))

# Display executive summary (tabular Pro/Con)
if st.session_state.summary:
    st.markdown(
        '<p class="report-section-title">Executive Summary</p>',
        unsafe_allow_html=True,
    )
    summary_html = _summary_to_html(st.session_state.summary)
    if hasattr(st, "html"):
        st.html(summary_html)
    else:
        st.markdown(summary_html, unsafe_allow_html=True)

# Display trackable elements
if st.session_state.trackables:
    st.markdown(
        '<p class="report-section-title">Trackable Elements</p>',
        unsafe_allow_html=True,
    )
    trackables_html = _trackables_to_html(st.session_state.trackables)
    if hasattr(st, "html"):
        st.html(trackables_html)
    else:
        st.markdown(trackables_html, unsafe_allow_html=True)

# Conviction Level
if st.session_state.arguments_list:
    st.markdown(
        '<p class="report-section-title">Conviction Level</p>',
        unsafe_allow_html=True,
    )
    args_list = st.session_state.arguments_list
    weights_list = []
    cols = st.columns(min(len(args_list), 4))
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
    score = calculate_conviction(args_list, weights_list)
    pct = (score / 10) * 100
    conviction_html = (
        f'<div class="conviction-panel">'
        f'<div class="conviction-score-box">Portfolio Conviction: {score}/10</div>'
        f'<div class="conviction-bar"><div class="conviction-bar-fill" style="width:{pct}%"></div></div>'
        f"</div>"
    )
    st.markdown(conviction_html, unsafe_allow_html=True)

# Export to Notion
if st.session_state.summary and st.session_state.trackables is not None:
    st.markdown(
        '<p class="report-section-title">Export</p>',
        unsafe_allow_html=True,
    )
    if st.button("Export to Notion", key="export_notion"):
        try:
            msg = export_to_notion(
                st.session_state.summary,
                st.session_state.trackables,
                theme,
            )
            st.success(msg)
        except (ValueError, RuntimeError) as e:
            st.error(str(e))
