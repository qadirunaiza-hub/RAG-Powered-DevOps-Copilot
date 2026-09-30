"""
LLM Client: Build the RAG prompt and call Claude.

The four-part RAG prompt:
  1. System message  — role, constraints, behavior rules
  2. Context block   — retrieved chunks with source + similarity score
  3. History         — recent conversation turns (for follow-up questions)
  4. Current question

The LLM has no database access. It only reads the text we provide.
Every piece of information in the answer must come from the context block.

Confidence threshold: below 40% average similarity, the retrieved chunks
are likely off-topic. We tell the LLM to flag this to the user.
"""

import os
import anthropic

CONFIDENCE_THRESHOLD = 0.40


def _system_prompt() -> str:
    return """You are a DevOps Copilot — an expert AI assistant for Docker, Kubernetes, CI/CD pipelines, Linux systems, and deployment practices.

You answer questions ONLY using the knowledge base context provided in each message. Follow these rules strictly:

1. If the context contains sufficient information, answer clearly and specifically with actionable steps.
2. If the context is insufficient or has low relevance, say explicitly: "My knowledge base does not contain enough information about this. Please upload relevant documentation."
3. Never fabricate commands, configuration values, error codes, or facts not present in the context.
4. Always end your response with a 'Sources:' section listing the filenames you drew from.
5. For troubleshooting questions, use numbered steps.
6. Be concise — skip preamble and filler phrases."""


def _build_context_block(chunks: list[dict], low_confidence: bool) -> str:
    """Format retrieved chunks into the context block injected into the prompt."""
    if not chunks:
        return "No relevant documents were found in the knowledge base."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Source {i}: {chunk['source']} | Relevance: {chunk['similarity']:.0%}]\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(parts)

    confidence_warning = ""
    if low_confidence:
        confidence_warning = (
            "\n\nWARNING: The retrieved chunks have low relevance scores. "
            "The knowledge base may not adequately cover this question. "
            "Be transparent about this uncertainty in your answer."
        )

    return context + confidence_warning


def _build_messages(
    query: str,
    chunks: list[dict],
    history: list[dict],
    low_confidence: bool,
) -> list[dict]:
    """Assemble the messages list: history + current RAG-augmented user turn."""
    messages = []

    # Include recent conversation history (last 6 turns = 3 question-answer pairs)
    for turn in history[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    context_block = _build_context_block(chunks, low_confidence)
    user_content = (
        f"=== KNOWLEDGE BASE CONTEXT ===\n{context_block}\n\n"
        f"=== QUESTION ===\n{query}\n\n"
        f"Answer based only on the context above. End with a 'Sources:' section."
    )
    messages.append({"role": "user", "content": user_content})
    return messages


class LLMClient:
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def generate(
        self,
        query: str,
        chunks: list[dict],
        history: list[dict] = None,
        low_confidence: bool = False,
    ) -> str:
        """
        Generate an answer using retrieved chunks as context.

        query        : the user's current question
        chunks       : top-k retrieved chunks from the vector store
        history      : prior conversation turns for follow-up context
        low_confidence: whether to warn the LLM about weak retrieval
        """
        messages = _build_messages(
            query=query,
            chunks=chunks,
            history=history or [],
            low_confidence=low_confidence,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=_system_prompt(),
            messages=messages,
        )
        return response.content[0].text
