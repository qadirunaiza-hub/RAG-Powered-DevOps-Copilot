"""
RAG-Powered DevOps Copilot — Streamlit UI

Sidebar: upload documents, track knowledge base size, clear the KB
Main:    chat interface with confidence indicator and source citations
"""

import os
import tempfile
import shutil
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from rag.pipeline import RAGPipeline

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DevOps Copilot",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Pipeline (cached once per session) ────────────────────────────────────────
@st.cache_resource
def get_pipeline() -> RAGPipeline:
    return RAGPipeline()

pipeline = get_pipeline()

# ── Session state defaults ─────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ DevOps Copilot")
    st.caption("Powered by RAG + Claude")

    st.divider()

    # Knowledge base status
    doc_count = pipeline.document_count()
    if doc_count == 0:
        st.warning("Knowledge base is empty")
    else:
        st.success(f"Knowledge base: **{doc_count}** chunks")

    # Document upload
    st.subheader("Upload Documentation")
    uploaded_file = st.file_uploader(
        "PDF, Markdown, or Text file",
        type=["pdf", "md", "txt"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        if st.button("Ingest Document", type="primary", use_container_width=True):
            with st.spinner(f"Processing {uploaded_file.name}..."):
                # Save to a temp dir with the original filename preserved
                tmp_dir = tempfile.mkdtemp()
                tmp_path = os.path.join(tmp_dir, uploaded_file.name)
                try:
                    with open(tmp_path, "wb") as f:
                        f.write(uploaded_file.read())
                    n_chunks = pipeline.ingest(tmp_path, original_name=uploaded_file.name)
                    st.success(f"Added **{n_chunks}** chunks from `{uploaded_file.name}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

    st.divider()

    # Example questions as clickable buttons
    st.subheader("Example Questions")
    examples = [
        "Why is my Docker container failing to start?",
        "What causes CrashLoopBackOff in Kubernetes?",
        "How do I troubleshoot a failed CI/CD pipeline?",
        "How do I investigate high CPU usage?",
        "What is a rolling update deployment strategy?",
    ]
    for i, q in enumerate(examples):
        if st.button(q, key=f"example_{i}", use_container_width=True):
            st.session_state["prefill"] = q

    st.divider()

    # Clear knowledge base
    if st.button("Clear Knowledge Base", type="secondary", use_container_width=True):
        pipeline.reset_knowledge_base()
        st.session_state.messages = []
        st.rerun()

def _render_metadata(meta: dict, key_suffix: str):
    """Render confidence badge, sources, and optional chunk viewer."""
    conf = meta["confidence"]
    col1, col2 = st.columns([1, 3])

    with col1:
        if conf >= 0.60:
            st.markdown(f"**Confidence:** :green[{conf:.0%}]")
        elif conf >= 0.40:
            st.markdown(f"**Confidence:** :orange[{conf:.0%}]")
        else:
            st.markdown(f"**Confidence:** :red[{conf:.0%}]")

    with col2:
        if meta["sources"]:
            st.markdown(f"**Sources:** `{'`, `'.join(meta['sources'])}`")

    if meta["low_confidence"]:
        st.warning(
            "Low retrieval confidence — the knowledge base may not cover this topic well. "
            "Consider uploading more relevant documentation."
        )

    if meta["chunks"]:
        with st.expander(f"View {len(meta['chunks'])} retrieved chunks", expanded=False):
            for i, chunk in enumerate(meta["chunks"], 1):
                st.markdown(
                    f"**Chunk {i}** — `{chunk['source']}` "
                    f"({chunk['similarity']:.0%} match)"
                )
                st.text(chunk["text"])
                if i < len(meta["chunks"]):
                    st.divider()


# ── Main area ──────────────────────────────────────────────────────────────────
st.title("RAG-Powered DevOps Copilot")
st.caption("Ask questions about Docker, Kubernetes, CI/CD, and Linux — answers drawn from your uploaded documentation.")

if pipeline.document_count() == 0:
    st.info(
        "**Get started:** Upload documentation using the sidebar. "
        "Sample docs are in the `docs/` folder of this project. "
        "Try uploading `docker_troubleshooting.md`, `kubernetes_guide.md`, "
        "`cicd_guide.md`, and `devops_runbook.md`."
    )

# ── Render conversation history ────────────────────────────────────────────────
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "meta" in msg:
            _render_metadata(msg["meta"], key_suffix=str(idx))


# ── Chat input ─────────────────────────────────────────────────────────────────
chat_input = st.chat_input("Ask a DevOps question...")

# Resolve prefill from sidebar example buttons
question_to_ask = chat_input
if not question_to_ask and "prefill" in st.session_state:
    question_to_ask = st.session_state["prefill"]
    del st.session_state["prefill"]

if question_to_ask:
    if pipeline.document_count() == 0:
        st.warning("Please upload at least one document before asking a question.")
        st.stop()

    # Render user message
    with st.chat_message("user"):
        st.markdown(question_to_ask)
    st.session_state.messages.append({"role": "user", "content": question_to_ask})

    # Build history for the LLM (all prior turns, without metadata)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
    ]

    # RAG query
    with st.chat_message("assistant"):
        with st.spinner("Searching knowledge base..."):
            result = pipeline.query(question_to_ask, history=history)

        st.markdown(result["answer"])
        meta = {
            "confidence": result["confidence"],
            "low_confidence": result["low_confidence"],
            "sources": result["sources"],
            "chunks": result["chunks"],
        }
        _render_metadata(meta, key_suffix="new")

    # Store with metadata for re-rendering in conversation history
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "meta": meta,
    })
