"""
Retriever: Coordinates document ingestion and query retrieval.

Ingestion flow:
  file path → process_document() → embed all chunks → store in ChromaDB

Retrieval flow:
  query string → embed query → cosine search in ChromaDB → top-k chunks
"""

from rag.document_processor import process_document
from rag.embeddings import EmbeddingModel
from rag.vector_store import VectorStore


class Retriever:
    def __init__(self, embedding_model: EmbeddingModel, vector_store: VectorStore):
        self.embedder = embedding_model
        self.store = vector_store

    def ingest(
        self,
        file_path: str,
        original_name: str = None,
        chunk_size: int = 800,
        overlap: int = 150,
    ) -> int:
        """
        Process a document and store its chunks.
        Returns the number of chunks created.
        """
        chunks = process_document(
            file_path,
            chunk_size=chunk_size,
            overlap=overlap,
            original_name=original_name,
        )
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = self.embedder.embed_batch(texts)  # one GPU/CPU pass for all chunks
        self.store.add_documents(chunks, embeddings)
        return len(chunks)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Embed the query and find the most similar chunks in the vector store.
        Returns chunks ranked by similarity (highest first).
        """
        if self.store.count() == 0:
            return []

        query_embedding = self.embedder.embed(query)
        return self.store.search(query_embedding, top_k=top_k)
