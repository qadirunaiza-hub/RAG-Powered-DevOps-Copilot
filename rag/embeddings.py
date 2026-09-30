"""
Embeddings: Convert text → dense numeric vector.

What is happening inside the model?
  The sentence transformer passes text through a BERT-style encoder (12 layers
  of attention). The final hidden state is mean-pooled into a single vector.
  The model was trained with contrastive learning: pairs of similar sentences
  are pushed together; dissimilar pairs are pushed apart.

Model: all-MiniLM-L6-v2
  - 384-dimensional output
  - 80 MB on disk — runs on CPU without a GPU
  - Downloads automatically from HuggingFace on first use (~5 seconds)
  - No API key needed; runs locally and free
"""

from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # SentenceTransformer downloads the model weights on first instantiation
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        """
        Embed a single string.

        normalize_embeddings=True scales the vector to unit length (magnitude = 1).
        This makes cosine similarity equivalent to dot product, which is faster
        and is what ChromaDB's cosine-space index expects.
        """
        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed many strings in one forward pass (much faster than one-by-one).
        batch_size=32 means 32 strings pass through the model simultaneously.
        """
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        return vectors.tolist()
