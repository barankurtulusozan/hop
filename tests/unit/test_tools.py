import asyncio
import pytest
from pydantic import BaseModel, Field

from src.domain.tools import ToolCall, ToolNotFoundError, ToolValidationError
from src.tools.executor import ToolExecutor
from src.tools.registry import ToolRegistry


def sample_calculator(a: int, b: int) -> int:
    """Add two integers together."""
    return a + b


class WeatherQuery(BaseModel):
    city: str = Field(..., description="Target city name")
    unit: str = Field(default="celsius", pattern="^(celsius|fahrenheit)$")


def get_weather(city: str, unit: str = "celsius") -> str:
    return f"Weather in {city}: 22° {unit}"


def test_registry_function_auto_schema_generation():
    registry = ToolRegistry()
    tool_def = registry.register_function(sample_calculator, name="add", description="Add numbers")

    assert tool_def.name == "add"
    assert tool_def.description == "Add numbers"
    assert "properties" in tool_def.parameters_schema
    assert "a" in tool_def.parameters_schema["properties"]
    assert "b" in tool_def.parameters_schema["properties"]


def test_registry_pydantic_model_registration():
    registry = ToolRegistry()
    tool_def = registry.register_pydantic_model("get_weather", "Query weather", WeatherQuery, get_weather)

    assert tool_def.name == "get_weather"
    assert tool_def.parameters_schema["properties"]["city"]["type"] == "string"


def test_registry_argument_validation_success_and_failure():
    registry = ToolRegistry()
    registry.register_function(sample_calculator, name="add")

    # Valid args
    valid = registry.validate_arguments("add", {"a": 5, "b": 10})
    assert valid == {"a": 5, "b": 10}

    # Invalid args (string instead of int)
    with pytest.raises(ToolValidationError):
        registry.validate_arguments("add", {"a": "invalid", "b": 10})


@pytest.mark.asyncio
async def test_executor_sandbox_success():
    registry = ToolRegistry()
    registry.register_function(sample_calculator, name="add")
    executor = ToolExecutor(registry)

    call = ToolCall(call_id="call-1", tool_name="add", arguments={"a": 10, "b": 20})
    result = await executor.execute(call)

    assert result.is_error is False
    assert result.result == 30
    assert result.error is None
    assert result.duration_ms >= 0.0


@pytest.mark.asyncio
async def test_executor_sandbox_handles_validation_error():
    registry = ToolRegistry()
    registry.register_function(sample_calculator, name="add")
    executor = ToolExecutor(registry)

    call = ToolCall(call_id="call-2", tool_name="add", arguments={"a": "bad_type"})
    result = await executor.execute(call)

    assert result.is_error is True
    assert result.result is None
    assert "Validation failed" in result.error


@pytest.mark.asyncio
async def test_executor_sandbox_handles_handler_exception():
    def crashing_tool(x: int) -> int:
        raise ValueError("Database connection lost")

    registry = ToolRegistry()
    registry.register_function(crashing_tool, name="crash")
    executor = ToolExecutor(registry)

    call = ToolCall(call_id="call-3", tool_name="crash", arguments={"x": 1})
    result = await executor.execute(call)

    assert result.is_error is True
    assert "Database connection lost" in result.error


@pytest.mark.asyncio
async def test_executor_sandbox_handles_timeout():
    async def slow_tool() -> str:
        await asyncio.sleep(0.5)
        return "done"

    registry = ToolRegistry()
    registry.register_function(slow_tool, name="slow")
    executor = ToolExecutor(registry)

    call = ToolCall(call_id="call-4", tool_name="slow", arguments={})
    result = await executor.execute(call, timeout_seconds=0.05)

    assert result.is_error is True
    assert "timed out" in result.error
