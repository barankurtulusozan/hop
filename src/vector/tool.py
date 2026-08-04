from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel, Field

from src.vector.pipeline import DenseRetriever


class VectorSearchInput(BaseModel):
    query: str = Field(description="Search query or question to retrieve relevant domain knowledge.")
    top_k: int = Field(default=3, description="Maximum number of relevant context snippets to retrieve.")


def create_vector_search_tool(
    retriever: DenseRetriever,
    tool_name: str = "search_knowledge_base",
    description: str = "Search the vector knowledge base for relevant context and document snippets.",
) -> tuple[str, str, Callable[..., Any]]:
    """Factory creating a registered tool function tuple (name, description, handler) for ToolRegistry."""

    async def search_knowledge_base(query: str, top_k: int = 3) -> str:
        results = await retriever.retrieve(query=query, top_k=top_k)
        if not results:
            return "No relevant information found in the knowledge base."

        snippets: list[dict[str, Any]] = []
        for i, res in enumerate(results, 1):
            text = res.payload.get("text", "")
            doc_id = res.payload.get("doc_id", res.id)
            snippets.append(
                {
                    "rank": i,
                    "score": round(res.score, 4),
                    "doc_id": doc_id,
                    "text": text,
                }
            )
        return json.dumps(snippets, indent=2)

    search_knowledge_base.__name__ = tool_name
    search_knowledge_base.__doc__ = description

    return tool_name, description, search_knowledge_base
