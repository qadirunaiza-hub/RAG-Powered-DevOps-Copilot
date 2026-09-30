# RAG-Powered DevOps Copilot

An AI assistant that answers DevOps questions using Retrieval-Augmented Generation (RAG) over your own documentation — not the LLM's training data.

---

## Architecture

```
INGESTION PIPELINE  (run once per document)
─────────────────────────────────────────────────────────────────
  PDF / MD / TXT
       │
       ▼
  document_processor.py
  ┌─────────────────┐
  │  load_document  │  ← extract raw text from any format
  │  clean_text     │  ← normalize whitespace, remove artifacts
  │  chunk_text     │  ← split into 800-char overlapping chunks
  └────────┬────────┘
           │  list of {text, source, chunk_index}
           ▼
  embeddings.py
  ┌──────────────────────────┐
  │  SentenceTransformer     │  ← all-MiniLM-L6-v2 (local, free)
  │  embed_batch(texts)      │  ← 384-dimensional vectors
  └────────┬─────────────────┘
           │  list of float[384]
           ▼
  vector_store.py
  ┌──────────────────────────┐
  │  ChromaDB (on disk)      │  ← persistent HNSW index
  │  upsert(ids, embeddings) │
  └──────────────────────────┘


QUERY PIPELINE  (real-time, per question)
─────────────────────────────────────────────────────────────────
  User Question
       │
       ▼ embeddings.py
  embed(question) → float[384]
       │
       ▼ vector_store.py
  search(query_embedding, top_k=5)
  "cosine distance to every stored vector → return top 5"
       │
       ▼  [{text, source, similarity}, ...]
  ┌───────────────────────────────────────────────┐
  │             llm_client.py                     │
  │                                               │
  │  SYSTEM: You are a DevOps expert...           │
  │                                               │
  │  USER:                                        │
  │  === KNOWLEDGE BASE CONTEXT ===               │
  │  [Source 1: docker_guide.md | 78%]            │
  │  When a container fails to start...           │
  │  [Source 2: kubernetes_guide.md | 64%]        │
  │  CrashLoopBackOff occurs when...              │
  │                                               │
  │  === QUESTION ===                             │
  │  Why is my container failing to start?        │
  └───────────────────┬───────────────────────────┘
                      │ Claude API (claude-haiku-4-5)
                      ▼
           Answer + Sources + Confidence
```

### Key Design Decisions

| Component | Choice | Why |
|-----------|--------|-----|
| Embedding model | all-MiniLM-L6-v2 | Local, free, 384-dim, good quality |
| Vector DB | ChromaDB | Persistent, zero-config, Python-native |
| LLM | Claude Haiku 4.5 | Fast, cheap, good at Q&A |
| Chunk size | 800 chars (~200 words) | Long enough for context, short enough to be specific |
| Overlap | 150 chars | Prevents losing info at chunk boundaries |
| Confidence threshold | 40% similarity | Below this, warn the user |

---

## Project Structure

```
rag-devops-copilot/
├── app.py                      # Streamlit UI — upload, chat, citations
├── requirements.txt
├── .env.example                # API key template
│
├── rag/
│   ├── document_processor.py   # load → clean → chunk
│   ├── embeddings.py           # SentenceTransformer wrapper
│   ├── vector_store.py         # ChromaDB read/write
│   ├── retriever.py            # ingest files + retrieve for a query
│   ├── llm_client.py           # prompt construction + Claude API call
│   └── pipeline.py             # end-to-end coordinator
│
├── evaluation/
│   └── evaluate.py             # 6 test questions, keyword-based pass/fail
│
└── docs/                       # sample knowledge base (ingest these first)
    ├── docker_troubleshooting.md
    ├── kubernetes_guide.md
    ├── cicd_guide.md
    └── devops_runbook.md
```

---

## Setup

### 1. Clone and install

```bash
cd /home/unaizaqadir/rag-devops-copilot
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt   # first run downloads the embedding model (~80MB)
```

### 2. Set your API key

```bash
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY=sk-ant-...
```

Get an API key at: console.anthropic.com

### 3. Run the app

```bash
streamlit run app.py
# Opens http://localhost:8501
```

### 4. Ingest the sample docs

In the sidebar, upload each file from the `docs/` folder:
- `docker_troubleshooting.md`
- `kubernetes_guide.md`
- `cicd_guide.md`
- `devops_runbook.md`

Then ask a question!

---

## Usage

### Example questions (after ingesting the sample docs)

- *"Why is my Docker container failing to start?"*
- *"What causes a Kubernetes pod to enter CrashLoopBackOff?"*
- *"How do I troubleshoot a failed CI/CD pipeline?"*
- *"How do I investigate high CPU usage on a Linux server?"*
- *"What is the difference between RollingUpdate and Recreate deployment strategies?"*

### Reading the confidence indicator

| Color | Range | Meaning |
|-------|-------|---------|
| Green | ≥ 60% | High confidence — strong match in the knowledge base |
| Orange | 40–60% | Medium confidence — partial match |
| Red | < 40% | Low confidence — knowledge base may not cover this topic |

When confidence is red, the copilot will say so clearly rather than hallucinate.

---

## Running Evaluation

After ingesting the sample docs:

```bash
python -m evaluation.evaluate
```

Runs 6 test questions and checks:
1. Retrieval confidence (similarity score ≥ 30%)
2. Keyword hit rate in the answer (≥ 40% of expected keywords present)

---

## Concepts Explained

### What is RAG?

Without RAG: LLM uses only its training data → may hallucinate for your specific docs.
With RAG: retrieve relevant text from your docs → give it to the LLM as context → LLM answers from your docs.

### Why embeddings?

"Why is my container failing?" and "Docker startup error" share no words but mean the same thing. Keyword search fails. Embeddings capture meaning — both map to similar 384-dimensional vectors, so a similarity search finds the right chunk even without matching words.

### Why chunks instead of full documents?

- LLMs have context limits (tokens).
- Smaller chunks are more precise — a 200-word chunk about exit code 137 scores higher for a relevant query than a 10-page document that mentions it once.
- Smaller chunks produce better embeddings (the model focuses on one concept).

### The confidence score

`confidence = average cosine similarity of top-5 retrieved chunks`

Cosine similarity measures the angle between two vectors. A score of 1.0 means identical direction (same meaning). A score near 0 means unrelated topics. The threshold at 0.40 was calibrated empirically on the sample docs.

---

## Extending the Copilot

- **Add your own docs:** Upload any PDF, Markdown, or text file via the sidebar.
- **Change the LLM:** Set `LLM_MODEL=claude-sonnet-5` in `.env` for higher quality answers.
- **Add more sample docs:** Place `.md` or `.txt` files in `docs/` and ingest them.
- **Tune chunking:** Adjust `chunk_size` and `overlap` in `pipeline.py` for your document type.
