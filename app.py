"""Streamlit web app for the Investment Idea Generator."""

import re

import pandas as pd
import streamlit as st
from src.llm_analysts import brainstorm_ideas, critique_ideas
from src.summary_generator import (
    format_exec_summary,
    parse_trackable_elements,
    extract_arguments_from_summary,
    calculate_conviction,
)


def _parse_pro_con_pairs(summary: str) -> list[tuple[str, str]]:
    """Parse summary into (pro_line, con_line) pairs."""
    pairs: list[tuple[str, str]] = []
    # Split by "Pro Idea N:"
    pro_pattern = re.compile(r"Pro Idea \d+:", re.IGNORECASE)
    matches = list(pro_pattern.finditer(summary))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(summary)
        block = summary[start:end].strip()
        # Split block into Pro and Con lines
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        pro_line = lines[0] if lines else ""
        con_line = ""
        for line in lines[1:]:
            if re.match(r"^Con\s*:", line, re.IGNORECASE):
                con_line = line
                break
        pairs.append((pro_line, con_line))
    return pairs


st.title("Investment Idea Generator")

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
    with st.spinner("Generating..."):
        try:
            brainstorm = brainstorm_ideas(theme)
            critic = critique_ideas(brainstorm)
            summary = format_exec_summary(brainstorm, critic)
            st.session_state.summary = summary
            st.session_state.trackables = parse_trackable_elements(summary)
            st.session_state.arguments_list = extract_arguments_from_summary(summary)
        except (RuntimeError, ValueError, Exception) as e:
            st.error(str(e))

# Display executive summary (Pro/Con in columns)
if st.session_state.summary:
    st.subheader("Executive Summary")
    pairs = _parse_pro_con_pairs(st.session_state.summary)
    if pairs:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Pros**")
            for i, (pro, _) in enumerate(pairs):
                st.markdown(f"- **Idea {i + 1}:** {pro}")
        with col2:
            st.markdown("**Cons**")
            for i, (_, con) in enumerate(pairs):
                con_text = re.sub(r"^Con\s*:\s*", "", con, flags=re.IGNORECASE)
                st.markdown(f"- **Idea {i + 1}:** {con_text}")
    else:
        st.markdown(st.session_state.summary)

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
    st.write(f"**Conviction Score: {score}/10**")
