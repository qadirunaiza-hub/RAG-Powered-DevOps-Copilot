"""
Vector Store: Persist and search embeddings with ChromaDB.

What is ChromaDB?
  A local vector database that stores (id, embedding, text, metadata) tuples.
  Internally it builds an HNSW index (Hierarchical Navigable Small Worlds) —
  a graph-based approximate nearest-neighbor structure that can search millions
  of vectors in milliseconds.

PersistentClient saves to disk so the knowledge base survives app restarts.

Cosine distance in ChromaDB:
  distance = 1 - cosine_similarity
  → distance 0.0  means identical  (similarity 1.0 = 100%)
  → distance 0.5  means somewhat different  (similarity 0.5 = 50%)
  → distance 1.0  means orthogonal  (similarity 0.0 = 0%)
"""

import chromadb


class VectorStore:
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "devops_kb",
    ):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, chunks: list[dict], embeddings: list[list[float]]):
        """
        Store chunks in ChromaDB. Each chunk needs a unique ID.

        IDs are deterministic: "<source>__chunk_<index>".
        upsert = insert if new, replace if already exists (safe to re-ingest).
        """
        ids = [f"{c['source']}__chunk_{c['chunk_index']}" for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """
        Return the top_k most similar chunks.

        ChromaDB returns results sorted by distance (lowest first = most similar).
        We convert distance → similarity so the UI shows a percentage.
        """
        available = self.count()
        if available == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, available),
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "text": doc,
                "source": meta["source"],
                "chunk_index": meta["chunk_index"],
                "similarity": round(1.0 - dist, 4),  # cosine distance → similarity
            })
        return hits

    def count(self) -> int:
        """Number of chunks currently stored."""
        return self.collection.count()

    def reset(self):
        """Delete all stored chunks (drop and recreate the collection)."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
