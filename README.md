# Enterprise AI Platform Core

A production-grade, resilient, vendor-agnostic LLM Orchestrator & Agentic Execution Platform built using **Hexagonal Architecture (Ports & Adapters)**.

Designed for long-term maintainability, zero vendor lock-in, fail-fast production safety, defensive schema validation, and self-correcting tool execution loops.

---

## 🏛️ Architectural Highlights

```
                                  ┌───────────────────────────┐
                                  │      Application Code     │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │   LLMOrchestrator Pipeline│
                                  │ ┌───────────────────────┐ │
                                  │ │ Exponential Backoff   │ │
                                  │ │ Circuit Breaker (CB)  │ │
                                  │ │ Timeout Protection    │ │
                                  │ │ Structured JSON Logger│ │
                                  │ └───────────────────────┘ │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │    LLMProvider (Port)     │
                                  └──────┬──────────────┬─────┘
                                         │              │
                    ┌────────────────────┘              └────────────────────┐
                    ▼                                                        ▼
         ┌─────────────────────┐                                  ┌─────────────────────┐
         │    OpenAIAdapter    │                                  │   AnthropicAdapter  │
         └──────────┬──────────┘                                  └──────────┬──────────┘
                    ▼                                                        ▼
         ┌─────────────────────┐                                  ┌─────────────────────┐
         │     OpenAI SDK      │                                  │    Anthropic SDK    │
         └─────────────────────┘                                  └─────────────────────┘
```

1. **Hexagonal Ports & Adapters**: Core domain models (`CompletionRequest`, `CompletionResponse`, `Message`, `Role`) and the `LLMProvider` port have **zero vendor SDK dependencies**. OpenAI and Anthropic SDKs are completely isolated inside `src/adapters/`.
2. **Production Resilience Engine**:
   - **Exponential Backoff with Full Jitter**: AWS Architecture algorithm preventing thundering herd problems during rate limit spikes (`429`).
   - **Per-Provider Circuit Breaker**: State machine (`CLOSED` $\rightarrow$ `OPEN` $\rightarrow$ `HALF_OPEN`) fast-failing requests when upstream providers encounter consecutive outages.
   - **Per-Request Timeout Safety**: Wraps requests in `asyncio.timeout` and translates timeouts into retryable HTTP 504 errors.
   - **Structured JSON Telemetry**: stdlib `logging` formatted into valid JSON lines for Datadog/CloudWatch aggregation.
3. **Structured Tool Engine & Security Sandbox**:
   - **Auto-Schema Generator & Registry**: Converts Python type hints and Pydantic models into OpenAPI/JSON-Schema compliant tool definitions.
   - **Defensive Pydantic Validation Boundary**: Validates raw LLM arguments before handler execution, preventing schema injection and type crashes.
   - **Sandboxed Execution Engine**: Traps all tool execution exceptions, enforces per-tool timeouts, and runs synchronous handlers off the main event loop via `asyncio.to_thread`.
   - **Agentic Auto-Correction Loop**: Catches malformed tool parameters and constructs corrective `Role.TOOL` turns to re-prompt the LLM automatically.

---

## 📂 Repository Structure

```
/hop
├── pyproject.toml                         # Build system, dependencies, & pytest config
├── README.md                              # Platform documentation & quickstart
├── docs/                                  # Persistent Architectural Memory & ADRs
│   ├── adrs/
│   │   ├── ADR-0001-llm-provider-abstraction.md
│   │   └── ADR-0002-tool-schema-normalization-and-execution-sandbox.md
│   └── architecture_memory.md
├── src/                                   # Enterprise AI Platform Core
│   ├── py.typed                            # PEP 561 package typing marker
│   ├── config.py                          # Immutable settings & SecretStr containers
│   ├── domain/                            # Hexagonal Port Boundary (Zero SDK imports)
│   │   ├── exceptions.py                  # Standardized domain exception hierarchy
│   │   ├── interfaces.py                  # LLMProvider abstract interface
│   │   ├── models.py                      # CompletionRequest/Response, Messages
│   │   └── tools.py                       # ToolDefinition, ToolCall, ToolResult
│   ├── tools/                             # Tool Subsystem & Security Sandbox
│   │   ├── registry.py                    # ToolRegistry & auto-schema generator
│   │   └── executor.py                    # Sandboxed ToolExecutor
│   ├── adapters/                          # Vendor Adapters (OpenAI, Anthropic, Mock)
│   │   ├── mock_adapter.py
│   │   ├── openai_adapter.py
│   │   └── anthropic_adapter.py
│   └── orchestrator/                      # Execution & Reliability Subsystems
│       ├── circuit_breaker.py             # CircuitBreaker state machine
│       ├── pipeline.py                    # LLMOrchestrator pipeline
│       └── tool_runner.py                 # ToolOrchestrator & self-correction loop
└── tests/                                 # Unit & Resilience Integration Suite
    ├── unit/
    └── integration/
```

---

## 📜 Architecture Decision Records (ADRs)

- [ADR-0001: LLM Provider Abstraction via Hexagonal Ports & Adapters](docs/adrs/ADR-0001-llm-provider-abstraction.md)
- [ADR-0002: Tool Schema Normalization & Sandboxed Execution Engine](docs/adrs/ADR-0002-tool-schema-normalization-and-execution-sandbox.md)

---

## ⚡ Quickstart & Installation

### Prerequisites
Python 3.11+ required.

```bash
# Clone repository
git clone https://github.com/user/hop.git
cd hop

# Install package with all optional dependencies in editable mode
pip install -e ".[all]"
```

### Running Tests

```bash
# Run unit and integration test suite
python -m pytest tests/ -v
```

---

## 💻 Example Usage

```python
import asyncio
from src.config import Settings
from src.adapters.openai_adapter import OpenAIAdapter
from src.orchestrator.pipeline import LLMOrchestrator
from src.domain.models import CompletionRequest, Message, Role
from src.tools.registry import ToolRegistry
from src.tools.executor import ToolExecutor
from src.orchestrator.tool_runner import ToolOrchestrator

# 1. Register a security-checked tool
registry = ToolRegistry()

@registry.register(name="get_stock_price", description="Retrieve real-time stock price")
def get_stock_price(ticker: str) -> float:
    return 142.50

# 2. Initialize platform orchestrator
settings = Settings.from_env()
openai_adapter = OpenAIAdapter(settings.providers.openai)
llm = LLMOrchestrator(
    providers={"openai": openai_adapter},
    default_provider="openai",
    retry_config=settings.retry,
)

tool_executor = ToolExecutor(registry)
tool_orch = ToolOrchestrator(llm, tool_executor)

# 3. Execute completion with tools and auto-correction
async def main():
    req = CompletionRequest(
        messages=[Message(role=Role.USER, content="What is AAPL stock price?")],
        model="gpt-4o",
        tools=registry.list_tools(),
    )
    response, tool_results = await tool_orch.run_with_tools(req)
    print("Final Answer:", response.content)
    print("Executed Tools:", tool_results)

if __name__ == "__main__":
    asyncio.run(main())
```
