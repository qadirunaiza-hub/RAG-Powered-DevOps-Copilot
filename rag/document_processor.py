"""
Document Processor: Load → Clean → Chunk

Why chunking?
  LLMs have context limits (~4k-200k tokens). A 100-page document can't
  fit in one prompt. We split it into small, semantically coherent pieces
  and only retrieve the relevant ones at query time.

Why overlap?
  A concept near the end of chunk N may continue in chunk N+1.
  Overlap (sharing characters between adjacent chunks) ensures the
  retriever can find that concept from either direction.
"""

import re
from pathlib import Path
from pypdf import PdfReader


def load_pdf(file_path: str) -> str:
    """Extract text from all pages. Prefix each page so the LLM knows the source location."""
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append(f"[Page {i + 1}]\n{text.strip()}")
    return "\n\n".join(pages)


def load_markdown(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def load_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def load_document(file_path: str) -> str:
    """Route to the correct loader based on file extension."""
    ext = Path(file_path).suffix.lower()
    loaders = {
        ".pdf": load_pdf,
        ".md": load_markdown,
        ".markdown": load_markdown,
        ".txt": load_text,
    }
    if ext not in loaders:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: pdf, md, txt")
    return loaders[ext](file_path)


def clean_text(text: str) -> str:
    """
    Normalize text before chunking.
    - Remove non-printable characters (encoding artifacts, control chars)
    - Collapse runs of blank lines to two newlines
    - Collapse horizontal whitespace runs to a single space
    """
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E -￿]", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """
    Split text into overlapping fixed-size chunks.

    Algorithm:
      1. Take `chunk_size` characters starting from `start`.
      2. Try to break at the last sentence boundary (. ! ? newline) in the
         final 20% of the chunk — avoids mid-sentence cuts.
      3. Move `start` forward by (chunk_size - overlap) to create the
         overlap window between adjacent chunks.

    chunk_size: ~200 words (800 chars)
    overlap:    ~40 words (150 chars) — enough to carry context across a boundary
    """
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Look for a sentence boundary in the last 20% of the chunk window
        if end < text_len:
            search_from = end - chunk_size // 5
            best_break = -1
            for i in range(end, search_from, -1):
                if text[i] in (".", "\n", "!", "?"):
                    best_break = i + 1
                    break
            if best_break > 0:
                end = best_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Advance by (chunk_size - overlap); if we hit the end, stop
        start = end - overlap if end < text_len else text_len

    return chunks


def process_document(
    file_path: str,
    chunk_size: int = 800,
    overlap: int = 150,
    original_name: str = None,
) -> list[dict]:
    """
    Full pipeline: load → clean → chunk → annotate with metadata.

    Returns a list of chunk dicts:
      text        : the chunk content
      source      : filename (for citation)
      chunk_index : position within the document
    """
    raw_text = load_document(file_path)
    cleaned = clean_text(raw_text)
    chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)

    # Use provided name (preserves original filename when saved to a temp path)
    source_name = original_name or Path(file_path).name

    return [
        {"text": chunk, "source": source_name, "chunk_index": i}
        for i, chunk in enumerate(chunks)
    ]
