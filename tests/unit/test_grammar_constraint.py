import pytest
from pydantic import BaseModel, Field
from src.agent.grammar import (
    JSONSchemaGrammarEngine,
    StructuredOutputException,
    clean_json_markdown,
    repair_json_string,
)


class UserProfile(BaseModel):
    user_id: str
    age: int = Field(ge=0)
    email: str
    is_active: bool = True


def test_clean_json_markdown():
    markdown_text = """
Here is the result:
```json
{
    "name": "HOP",
    "version": "1.0.0"
}
```
Thank you!
"""
    cleaned = clean_json_markdown(markdown_text)
    assert cleaned == '{\n    "name": "HOP",\n    "version": "1.0.0"\n}'


def test_repair_json_string():
    malformed = "{'name': 'HOP', 'version': '1.0.0',}"
    repaired = repair_json_string(malformed)
    assert repaired == '{"name": "HOP", "version": "1.0.0"}'


def test_parse_and_validate_pydantic():
    engine = JSONSchemaGrammarEngine()
    raw_response = """
```json
{
    "user_id": "usr_9981",
    "age": 28,
    "email": "user@example.com",
    "is_active": true
}
```
"""
    profile = engine.parse_and_validate(raw_response, pydantic_model=UserProfile)
    assert isinstance(profile, UserProfile)
    assert profile.user_id == "usr_9981"
    assert profile.age == 28


def test_parse_and_validate_pydantic_invalid():
    engine = JSONSchemaGrammarEngine()
    raw_response = '{"user_id": "usr_123", "age": -5, "email": "invalid"}'
    with pytest.raises(StructuredOutputException):
        engine.parse_and_validate(raw_response, pydantic_model=UserProfile)


def test_parse_and_validate_dict_schema():
    engine = JSONSchemaGrammarEngine()
    schema = {"type": "object", "required": ["status", "code"]}
    raw_text = '{"status": "ok", "code": 200}'
    data = engine.parse_and_validate(raw_text, schema=schema)
    assert data["status"] == "ok"
    assert data["code"] == 200


def test_build_format_instruction():
    engine = JSONSchemaGrammarEngine()
    instruction = engine.build_format_instruction(pydantic_model=UserProfile)
    assert "JSON Schema" in instruction
    assert "user_id" in instruction
