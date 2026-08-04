from __future__ import annotations

import re
from typing import Sequence

from src.domain.exceptions import ChunkingException
from src.domain.vector import Chunk, Document


class RecursiveCharacterTextSplitter:
    """Recursively splits documents into chunks using separator priorities while keeping chunk overlap."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Sequence[str] | None = None,
    ):
        if chunk_size <= 0:
            raise ChunkingException(f"chunk_size must be > 0, got {chunk_size}")
        if chunk_overlap < 0:
            raise ChunkingException(f"chunk_overlap must be >= 0, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ChunkingException(
                f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = list(separators) if separators is not None else ["\n\n", "\n", " ", ""]

    def _split_text_with_separators(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text else []

        if not separators:
            # Character fallback split
            return [
                text[i : i + self.chunk_size]
                for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
            ]

        separator = separators[0]
        next_separators = separators[1:]

        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)

        good_splits: list[str] = []
        for s in splits:
            if len(s) > self.chunk_size:
                sub_splits = self._split_text_with_separators(s, next_separators)
                good_splits.extend(sub_splits)
            else:
                good_splits.append(s)

        return good_splits

    def split_text(self, text: str) -> list[str]:
        if not text:
            return []

        raw_splits = self._split_text_with_separators(text, self.separators)

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for split in raw_splits:
            split_len = len(split)
            if current_length + split_len > self.chunk_size and current_chunk:
                combined = "".join(current_chunk)
                chunks.append(combined)

                # Keep overlap from end of current_chunk
                overlap_acc: list[str] = []
                overlap_len = 0
                for item in reversed(current_chunk):
                    if overlap_len + len(item) <= self.chunk_overlap:
                        overlap_acc.insert(0, item)
                        overlap_len += len(item)
                    else:
                        break
                current_chunk = overlap_acc
                current_length = overlap_len

            current_chunk.append(split)
            current_length += split_len

        if current_chunk:
            chunks.append("".join(current_chunk))

        return chunks

    def split_document(self, document: Document) -> list[Chunk]:
        raw_chunks = self.split_text(document.content)
        chunks: list[Chunk] = []

        cursor = 0
        for idx, text in enumerate(raw_chunks):
            start_pos = document.content.find(text, cursor)
            if start_pos == -1:
                start_pos = cursor
            end_pos = start_pos + len(text)
            cursor = max(cursor, start_pos + 1)

            chunk_id = f"{document.id}_chunk_{idx}"
            chunk_metadata = dict(document.metadata)
            chunk_metadata.update(
                {
                    "doc_id": document.id,
                    "chunk_index": idx,
                    "start_char": start_pos,
                    "end_char": end_pos,
                }
            )

            chunks.append(
                Chunk(
                    id=chunk_id,
                    doc_id=document.id,
                    text=text,
                    metadata=chunk_metadata,
                    start_char=start_pos,
                    end_char=end_pos,
                    chunk_index=idx,
                )
            )

        return chunks
