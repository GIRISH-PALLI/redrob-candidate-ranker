"""Streamlit dashboard for browsing the ranked candidate submission."""

from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


APP_TITLE = "Redrob Candidate Ranker"
DEFAULT_CSV = Path("submission.csv")


@st.cache_data
def load_submission(csv_path: str) -> list[dict[str, str]]:
    """Load the ranked submission CSV into a list of row dictionaries."""
    path = Path(csv_path)
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _top_row_score(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "0"
    return rows[0].get("score", "0")


st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 1.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(APP_TITLE)
st.caption("Browse the validated top-100 ranking output from submission.csv.")

submission_path = st.sidebar.text_input("Submission CSV", value=str(DEFAULT_CSV))
rows = load_submission(submission_path)

if not rows:
    st.warning("No submission CSV found. Generate submission.csv first, then refresh the app.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Rows loaded", len(rows))
col2.metric("Top rank", rows[0].get("candidate_id", "-"))
col3.metric("Top score", _top_row_score(rows))

search = st.sidebar.text_input("Search candidate_id / reasoning", value="")
max_rows = st.sidebar.slider("Rows to show", min_value=10, max_value=min(100, len(rows)), value=min(25, len(rows)))

filtered_rows = rows
if search:
    query = search.lower()
    filtered_rows = [
        row for row in rows
        if query in row.get("candidate_id", "").lower() or query in row.get("reasoning", "").lower()
    ]

display_rows = filtered_rows[:max_rows]

st.subheader("Ranked Candidates")
st.dataframe(display_rows, use_container_width=True, hide_index=True)

st.subheader("Top Candidate Details")
top = rows[0]
detail_col1, detail_col2 = st.columns(2)
detail_col1.write(f"**Candidate ID:** {top.get('candidate_id', '-')}")
detail_col1.write(f"**Rank:** {top.get('rank', '-')}")
detail_col1.write(f"**Score:** {top.get('score', '-')}")
detail_col2.write(f"**Reasoning:** {top.get('reasoning', '-')}")
