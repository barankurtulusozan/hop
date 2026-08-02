"""
Domain models and exception hierarchy for Structured Tool & Function Calling.

Nothing in this file may import an external vendor SDK (openai, anthropic, etc).
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine
from pydantic import BaseModel, ConfigDict, Field

from src.domain.exceptions import LLMException


class ToolDefinition(BaseModel):
    """
    Vendor-agnostic definition of a callable tool.

    Adapters map `parameters_schema` to their vendor-specific schema formats
    (e.g., OpenAI `parameters` vs. Anthropic `input_schema`).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    handler: Callable[..., Any] | Callable[..., Coroutine[Any, Any, Any]] | None = Field(
        default=None, exclude=True
    )


class ToolCall(BaseModel):
    """Domain model representing an LLM's request to execute a tool."""

    model_config = ConfigDict(frozen=True)

    call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Domain model representing the outcome of a tool execution."""

    model_config = ConfigDict(frozen=True)

    call_id: str
    tool_name: str
    result: Any = None
    error: str | None = None
    is_error: bool = False
    duration_ms: float = 0.0


class ToolException(LLMException):
    """Base class for all domain-level tool execution errors."""

    def __init__(self, message: str, *, tool_name: str | None = None, retryable: bool = False):
        super().__init__(message, provider=None, retryable=retryable)
        self.tool_name = tool_name


class ToolNotFoundError(ToolException):
    """Raised when an LLM requests execution of a tool that is not in the registry."""

    def __init__(self, tool_name: str):
        super().__init__(f"Tool '{tool_name}' is not registered in the tool registry.", tool_name=tool_name, retryable=False)


class ToolValidationError(ToolException):
    """Raised when LLM-provided arguments fail Pydantic schema validation."""

    def __init__(self, tool_name: str, validation_error: str):
        super().__init__(
            f"Validation failed for tool '{tool_name}': {validation_error}",
            tool_name=tool_name,
            retryable=True,  # Retryable via LLM self-correction re-prompting!
        )
        self.validation_error = validation_error


class ToolExecutionError(ToolException):
    """Raised when a tool handler encounters an unhandled exception inside the sandbox."""

    def __init__(self, tool_name: str, cause: str):
        super().__init__(
            f"Tool '{tool_name}' failed during execution: {cause}",
            tool_name=tool_name,
            retryable=True,
        )
        self.cause = cause
