"""
RAG Pipeline: End-to-end coordinator.

This is the single class the Streamlit app and evaluation script interact with.
It wires together: EmbeddingModel → VectorStore → Retriever → LLMClient.

ingest(file_path)       → adds a document to the knowledge base
query(question, history) → full RAG cycle; returns answer + metadata
"""

import os
from rag.embeddings import EmbeddingModel
from rag.vector_store import VectorStore
from rag.retriever import Retriever
from rag.llm_client import LLMClient, CONFIDENCE_THRESHOLD


class RAGPipeline:
    def __init__(
        self,
        persist_dir: str = "./chroma_db",
        llm_model: str = None,
    ):
        self.embedder = EmbeddingModel()
        self.store = VectorStore(persist_directory=persist_dir)
        self.retriever = Retriever(self.embedder, self.store)
        model = llm_model or os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")
        self.llm = LLMClient(model=model)

    def ingest(self, file_path: str, original_name: str = None) -> int:
        """
        Add a document to the knowledge base.
        Returns the number of chunks created.
        """
        return self.retriever.ingest(file_path, original_name=original_name)

    def query(
        self,
        question: str,
        history: list[dict] = None,
        top_k: int = 5,
    ) -> dict:
        """
        Full RAG query pipeline.

        Step 1: Retrieve — embed the question, find top_k similar chunks
        Step 2: Score    — compute average similarity as confidence [0, 1]
        Step 3: Generate — build RAG prompt + call Claude
        Step 4: Compile  — return structured result dict

        Returns:
          answer        : LLM-generated response string
          sources       : unique source filenames used
          chunks        : raw retrieved chunk dicts (text, source, similarity)
          confidence    : average similarity score [0.0, 1.0]
          low_confidence: True when confidence < CONFIDENCE_THRESHOLD (0.40)
          doc_count     : total chunks currently in the knowledge base
        """
        history = history or []

        # Step 1: Retrieve
        chunks = self.retriever.retrieve(question, top_k=top_k)

        # Step 2: Score
        if chunks:
            confidence = round(sum(c["similarity"] for c in chunks) / len(chunks), 4)
        else:
            confidence = 0.0
        low_confidence = confidence < CONFIDENCE_THRESHOLD

        # Step 3: Generate
        answer = self.llm.generate(
            query=question,
            chunks=chunks,
            history=history,
            low_confidence=low_confidence,
        )

        # Step 4: Compile
        sources = list(dict.fromkeys(c["source"] for c in chunks))  # ordered dedup

        return {
            "answer": answer,
            "sources": sources,
            "chunks": chunks,
            "confidence": confidence,
            "low_confidence": low_confidence,
            "doc_count": self.store.count(),
        }

    def document_count(self) -> int:
        return self.store.count()

    def reset_knowledge_base(self):
        """Remove all chunks from the vector store."""
        self.store.reset()
