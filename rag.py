"""
RAG (Retrieval Augmented Generation) Knowledge Base

Lightweight knowledge retrieval using keyword matching over markdown files.
Loads .md files from the knowledge/ folder, splits by ## headers into chunks,
and finds the most relevant chunks for a given user query.

No external dependencies — uses Python's built-in difflib and re modules.
"""

import os
import re
import logging
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Tuple

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Simple RAG engine over markdown files in the knowledge/ folder."""

    def __init__(self, knowledge_dir: str = "knowledge"):
        self.knowledge_dir = Path(knowledge_dir)
        self.chunks: List[dict] = []  # {"text": ..., "source": ..., "header": ...}
        self._file_mtimes: dict = {}  # Track file modification times
        self._load()

    def _load(self):
        """Load and chunk all markdown files from the knowledge directory."""
        if not self.knowledge_dir.exists():
            logger.warning(f"Knowledge directory not found: {self.knowledge_dir}")
            return

        self.chunks = []
        self._file_mtimes = {}
        file_count = 0

        for md_file in sorted(self.knowledge_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                self._file_mtimes[str(md_file)] = md_file.stat().st_mtime
                file_chunks = self._chunk_markdown(content, md_file.stem)
                self.chunks.extend(file_chunks)
                file_count += 1
            except Exception as e:
                logger.error(f"Failed to load {md_file}: {e}")

        logger.info(
            f"Knowledge base loaded: {len(self.chunks)} chunks from {file_count} files"
        )

    def _chunk_markdown(self, content: str, source: str) -> List[dict]:
        """Split markdown content into chunks by ## headers."""
        chunks = []
        # Split by ## headers (keep the header with the content)
        sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Extract header if present
            header_match = re.match(r"^##\s+(.+)$", section, re.MULTILINE)
            header = header_match.group(1).strip() if header_match else source

            # Skip very short chunks (likely just a header with no content)
            if len(section) < 30:
                continue

            chunks.append({"text": section, "source": source, "header": header})

        # If no ## headers found, treat the whole file as one chunk
        if not chunks and len(content.strip()) >= 30:
            # Extract # title if present
            title_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else source
            chunks.append({"text": content.strip(), "source": source, "header": title})

        return chunks

    def reload_if_changed(self):
        """Reload knowledge base if any files have been modified."""
        if not self.knowledge_dir.exists():
            return

        needs_reload = False
        current_files = set(str(f) for f in self.knowledge_dir.glob("*.md"))
        cached_files = set(self._file_mtimes.keys())

        # Check for new or deleted files
        if current_files != cached_files:
            needs_reload = True
        else:
            # Check modification times
            for md_file in self.knowledge_dir.glob("*.md"):
                cached_mtime = self._file_mtimes.get(str(md_file), 0)
                if md_file.stat().st_mtime != cached_mtime:
                    needs_reload = True
                    break

        if needs_reload:
            logger.info("Knowledge base files changed, reloading...")
            self._load()

    def _score_chunk(self, query: str, chunk: dict) -> float:
        """Score a chunk's relevance to the query using keyword + fuzzy matching."""
        query_lower = query.lower()
        text_lower = chunk["text"].lower()
        header_lower = chunk["header"].lower()

        score = 0.0

        # 1. Exact keyword matches (strongest signal)
        query_words = set(re.findall(r"\w{3,}", query_lower))  # Words 3+ chars
        text_words = set(re.findall(r"\w{3,}", text_lower))
        
        if query_words:
            keyword_overlap = len(query_words & text_words) / len(query_words)
            score += keyword_overlap * 0.6  # 60% weight

        # 2. Header relevance (if query words appear in the header)
        header_words = set(re.findall(r"\w{3,}", header_lower))
        if query_words and header_words:
            header_overlap = len(query_words & header_words) / len(query_words)
            score += header_overlap * 0.25  # 25% weight

        # 3. Fuzzy sequence matching (catches partial/typo matches)
        fuzzy_score = SequenceMatcher(None, query_lower, header_lower).ratio()
        score += fuzzy_score * 0.15  # 15% weight

        return score

    def search(self, query: str, top_k: int = 3, threshold: float = 0.15) -> str:
        """
        Search the knowledge base for chunks relevant to the query.

        Args:
            query: The user's question
            top_k: Maximum number of chunks to return
            threshold: Minimum relevance score (0-1) to include a chunk

        Returns:
            Formatted string of relevant knowledge, or empty string if nothing relevant
        """
        if not self.chunks:
            return ""

        # Reload if files changed
        self.reload_if_changed()

        # Score all chunks
        scored: List[Tuple[float, dict]] = []
        for chunk in self.chunks:
            score = self._score_chunk(query, chunk)
            if score >= threshold:
                scored.append((score, chunk))

        # Sort by score descending, take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored[:top_k]

        if not top_chunks:
            return ""

        # Format as context string
        parts = []
        for score, chunk in top_chunks:
            parts.append(chunk["text"])

        result = "\n\n---\n\n".join(parts)
        logger.debug(
            f"RAG: query='{query[:50]}...' matched {len(top_chunks)} chunks "
            f"(scores: {[f'{s:.2f}' for s, _ in top_chunks]})"
        )
        return result
