from __future__ import annotations

import json
import re
from typing import Any, Type, TypeVar
from pydantic import BaseModel, ValidationError

from src.domain.exceptions import AgentException

T = TypeVar("T", bound=BaseModel)


class StructuredOutputException(AgentException):
    """Raised when JSON parsing or schema validation fails."""
    pass


def clean_json_markdown(text: str) -> str:
    """Extract JSON content from markdown code blocks or raw text."""
    if not text:
        return ""
    cleaned = text.strip()
    # Remove markdown code fence ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return cleaned


def repair_json_string(json_str: str) -> str:
    """Attempt basic repairs on malformed JSON strings."""
    s = json_str.strip()
    # Fix trailing commas in objects or arrays: {"a": 1,} -> {"a": 1}
    s = re.sub(r",\s*([\}\]])", r"\1", s)
    # Convert single-quoted keys/strings to double quotes if simple
    # e.g., {'key': 'val'} -> {"key": "val"}
    s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', s)
    return s


class JSONSchemaGrammarEngine:
    """Engine for validating, repairing, and enforcing structured output from LLMs."""

    def parse_and_validate(
        self,
        raw_text: str,
        schema: dict[str, Any] | None = None,
        pydantic_model: Type[T] | None = None,
        auto_repair: bool = True,
    ) -> Any:
        """
        Extract, parse, and validate JSON output.
        If pydantic_model is given, returns an instance of that model.
        If schema is given, returns validated dict.
        """
        cleaned_text = clean_json_markdown(raw_text)

        if not cleaned_text:
            raise StructuredOutputException("Received empty text for structured output parsing")

        try:
            data = json.loads(cleaned_text)
        except json.JSONDecodeError as initial_err:
            if not auto_repair:
                raise StructuredOutputException(f"Invalid JSON output: {initial_err}") from initial_err
            
            repaired_text = repair_json_string(cleaned_text)
            try:
                data = json.loads(repaired_text)
            except json.JSONDecodeError as repair_err:
                raise StructuredOutputException(
                    f"Failed to parse JSON after auto-repair attempt: {repair_err}. Raw text: {raw_text[:200]}"
                ) from repair_err

        # Validate against Pydantic model if provided
        if pydantic_model is not None:
            try:
                if isinstance(data, dict):
                    return pydantic_model.model_validate(data)
                elif isinstance(data, list):
                    return [pydantic_model.model_validate(item) for item in data]
                else:
                    raise StructuredOutputException(f"Data type {type(data)} not valid for Pydantic model")
            except ValidationError as val_err:
                raise StructuredOutputException(
                    f"Pydantic schema validation failed for {pydantic_model.__name__}: {val_err}"
                ) from val_err

        # Validate against dictionary JSON schema if provided
        if schema is not None and isinstance(data, dict):
            required_keys = schema.get("required", [])
            for key in required_keys:
                if key not in data:
                    raise StructuredOutputException(
                        f"JSON output missing required schema field: '{key}'"
                    )

        return data

    def build_format_instruction(
        self,
        schema: dict[str, Any] | None = None,
        pydantic_model: Type[BaseModel] | None = None,
    ) -> str:
        """Construct system prompt instructions to guide the model toward structured JSON formatting."""
        if pydantic_model is not None:
            model_schema = pydantic_model.model_json_schema()
            return (
                f"You MUST respond ONLY with a valid JSON object matching the following JSON Schema:\n"
                f"```json\n{json.dumps(model_schema, indent=2)}\n```\n"
                f"Do NOT include any commentary outside the JSON object."
            )
        elif schema is not None:
            return (
                f"You MUST respond ONLY with a valid JSON object matching the following structure:\n"
                f"```json\n{json.dumps(schema, indent=2)}\n```\n"
                f"Do NOT include any commentary outside the JSON object."
            )
        else:
            return "You MUST respond ONLY with a valid JSON object."
