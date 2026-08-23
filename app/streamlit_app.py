import json
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from agent.agent import run_turn
from agent.state import SessionState

st.set_page_config(page_title="ParcelPilot Support", page_icon="📦")


def _ensure_data_ingested() -> None:
    """
    Auto-runs ingestion on first startup if the SQLite DB or Chroma
    collection isn't there yet — e.g. on a fresh deploy where
    data/processed/ (gitignored, since it's generated output) never made
    it into the repo, or a fresh `git clone` where nobody's run the two
    ingestion commands manually yet. Idempotent: does nothing once both
    exist and are populated.
    """
    import sqlite3

    from ingestion.ingest_documents import CHROMA_DIR, COLLECTION_NAME
    from ingestion.ingest_documents import ingest as ingest_docs
    from ingestion.ingest_excel import DB_PATH as SQLITE_DB_PATH
    from ingestion.ingest_excel import ingest as ingest_excel

    db_needs_build = True
    if SQLITE_DB_PATH.exists():
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            count = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            conn.close()
            db_needs_build = count == 0
        except sqlite3.OperationalError:
            db_needs_build = True

    chroma_needs_build = True
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(COLLECTION_NAME)
        chroma_needs_build = collection.count() == 0
    except Exception:
        chroma_needs_build = True

    if not db_needs_build and not chroma_needs_build:
        return

    with st.spinner("First-time setup: loading ParcelPilot data (this only happens once)..."):
        if db_needs_build:
            ingest_excel("data/raw/operational_data.xlsx")
        if chroma_needs_build:
            ingest_docs("data/raw/documents/")


_ensure_data_ingested()

st.title("📦 ParcelPilot Support Agent")

# --- mock login (swap for real auth later) ---
ACCOUNTS = ["ACCT-001 (Northstar Logistics)", "ACCT-002 (LumenWorks)"]
if "session" not in st.session_state:
    st.session_state.session = None

with st.sidebar:
    st.subheader("Logged in as")
    choice = st.selectbox("Account", ACCOUNTS)
    account_id = choice.split(" ")[0]
    if st.button("Start / switch session"):
        st.session_state.session = SessionState(current_account_id=account_id)
        st.session_state.chat_history = []

if st.session_state.session is None:
    st.info("Choose an account and click 'Start / switch session' to begin.")
    st.stop()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def _render_tool_trace(trace: list[dict]) -> None:
    """Shows which tool(s) were called this turn, with args and results —
    satisfies the assessment's 'interface should show which tool is being
    used' requirement, and is invaluable for debugging retrieval misses."""
    if not trace:
        return
    with st.expander(f"🔧 {len(trace)} tool call(s) this turn", expanded=False):
        for call in trace:
            st.markdown(f"**`{call['name']}`**")
            st.code(json.dumps(call["arguments"], indent=2), language="json")
            st.caption("Result:")
            st.code(json.dumps(call["result"], indent=2, default=str), language="json")


for role, text, trace in st.session_state.chat_history:
    with st.chat_message(role):
        if role == "assistant":
            _render_tool_trace(trace)
        st.markdown(text)

if prompt := st.chat_input("Ask about an order, policy, or issue..."):
    st.session_state.chat_history.append(("user", prompt, []))
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer, trace = run_turn(prompt, st.session_state.session)
        _render_tool_trace(trace)
        st.markdown(answer)

    st.session_state.chat_history.append(("assistant", answer, trace))
