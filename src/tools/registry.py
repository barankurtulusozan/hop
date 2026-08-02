"""
Tool Registry: Function auto-schema generation, Pydantic model validation, and security registration.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Type
from pydantic import BaseModel, create_model, TypeAdapter, ValidationError

from src.domain.tools import ToolDefinition, ToolNotFoundError, ToolValidationError


class ToolRegistry:
    """
    Central registry for security-checked tools.

    Converts Python functions or Pydantic models into vendor-agnostic
    `ToolDefinition` objects with OpenAPI/JSON-Schema compliant parameter specs.
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._param_models: dict[str, Type[BaseModel]] = {}

    def register_pydantic_model(
        self,
        name: str,
        description: str,
        param_model: Type[BaseModel],
        handler: Callable[..., Any],
    ) -> ToolDefinition:
        """Register a tool defined by a Pydantic model and a handler callable."""
        schema = param_model.model_json_schema()
        # Clean up Pydantic-internal keys for clean vendor translation
        schema.pop("title", None)

        tool_def = ToolDefinition(
            name=name,
            description=description,
            parameters_schema=schema,
            handler=handler,
        )
        self._tools[name] = tool_def
        self._param_models[name] = param_model
        return tool_def

    def register_function(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
    ) -> ToolDefinition:
        """
        Register a python function, inspecting its type hints and docstring
        to auto-generate a Pydantic model & JSON Schema.
        """
        tool_name = name or fn.__name__
        tool_desc = description or (inspect.getdoc(fn) or f"Execute {tool_name}").strip()

        sig = inspect.signature(fn)
        fields: dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
            default_val = param.default if param.default != inspect.Parameter.empty else ...
            fields[param_name] = (param_type, default_val)

        dynamic_model = create_model(f"{tool_name}_params", **fields)
        return self.register_pydantic_model(tool_name, tool_desc, dynamic_model, fn)

    def register(self, name: str | None = None, description: str | None = None) -> Callable:
        """Decorator for easy function registration."""
        def decorator(fn: Callable[..., Any]) -> ToolDefinition:
            return self.register_function(fn, name=name, description=description)
        return decorator

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def validate_arguments(self, tool_name: str, raw_args: dict[str, Any]) -> dict[str, Any]:
        """
        Validate raw dictionary arguments against the registered Pydantic schema.
        Raises `ToolValidationError` if malformed.
        """
        if tool_name not in self._param_models:
            raise ToolNotFoundError(tool_name)

        param_model = self._param_models[tool_name]
        try:
            validated_obj = param_model.model_validate(raw_args)
            return validated_obj.model_dump()
        except ValidationError as exc:
            raise ToolValidationError(tool_name, str(exc)) from exc
