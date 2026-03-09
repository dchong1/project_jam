"""Streamlit web app for the Investment Idea Generator."""

import html
import re

import pandas as pd
import streamlit as st

from src.config import ANALYST_ARCHETYPES, resolve_archetype
from src.llm_analysts import generate_ideas_combined
from src.summary_generator import (
    format_exec_summary,
    parse_trackable_elements,
    extract_arguments_from_summary,
    calculate_conviction,
)


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
            pros = _cell_to_html(pros_raw)
            cons = _cell_to_html(cons_raw)
            cards_html.append(
                f"""
                <div class="idea-row">
                    <div class="idea-header">Idea {idea_num}</div>
                    <div class="pro-con-container">
                        <div class="pro-card">
                            <div class="pro-label">✓ Pros</div>
                            <div class="pro-content">{pros}</div>
                        </div>
                        <div class="con-card">
                            <div class="con-label">✗ Cons</div>
                            <div class="con-content">{cons}</div>
                        </div>
                    </div>
                </div>
                """
            )
    if not cards_html:
        return f"<div class='exec-summary'>{summary}</div>"

    return f'<div class="exec-summary-cards">{"".join(cards_html)}</div>'


# Page config (must be first Streamlit command)
st.set_page_config(
    page_title="Investment Idea Generator",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Nordic theme: minimal, sleek, arctic-inspired palette
_NORDIC_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

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

    .stApp {
        background: var(--nord6) !important;
    }

    [data-testid="stAppViewContainer"] {
        background: var(--nord6) !important;
    }

    [data-testid="stHeader"] {
        background: rgba(255,255,255,0.8) !important;
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
        background: var(--nord10) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        padding: 0.5rem 1.25rem !important;
        transition: background 0.2s ease;
    }

    .stButton > button:hover {
        background: var(--nord9) !important;
    }

    .stSelectbox > div > div {
        border-radius: 6px !important;
        border-color: var(--nord4) !important;
    }

    .stTextInput > div > div > input {
        border-radius: 6px !important;
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
        align-items: start;
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
        border-radius: 6px;
        font-weight: 600;
        font-family: 'Inter', system-ui, sans-serif;
    }
</style>
"""
st.markdown(_NORDIC_CSS, unsafe_allow_html=True)

st.title("Investment Idea Generator")

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

if st.button("Generate Ideas"):
    try:
        resolved = resolve_archetype(archetype) if archetype else None
        if resolved:
            persona = ANALYST_ARCHETYPES.get(resolved, {}).get("display_name", "analyst")
            st.write(f"Thinking as {persona}...")
        else:
            st.write("Thinking...")

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
        st.write("Finalising executive summary...")
        summary = format_exec_summary(brainstorm, critic)
        st.session_state.summary = summary
        st.session_state.trackables = parse_trackable_elements(summary)
        st.session_state.arguments_list = extract_arguments_from_summary(summary)
    except (RuntimeError, ValueError, Exception) as e:
        st.error(str(e))

# Display executive summary (tabular Pro/Con)
if st.session_state.summary:
    st.subheader("Executive Summary")
    st.markdown(
        _summary_to_html(st.session_state.summary),
        unsafe_allow_html=True,
    )

# Display trackable elements
if st.session_state.trackables:
    st.subheader("Trackable Elements")
    df = pd.DataFrame(st.session_state.trackables)
    st.dataframe(df, use_container_width=True)

# Weighting and conviction score
if st.session_state.arguments_list:
    st.subheader("Weighting")
    args_list = st.session_state.arguments_list
    weights_list = []
    for i in range(len(args_list)):
        w = st.slider(
            f"Weight for Idea {i + 1}",
            min_value=1,
            max_value=10,
            value=5,
            key=f"weight_{i}",
        )
        weights_list.append(w)
    score = calculate_conviction(args_list, weights_list)
    st.markdown(
        f'<p class="conviction-badge">Conviction Score: {score}/10</p>',
        unsafe_allow_html=True,
    )
