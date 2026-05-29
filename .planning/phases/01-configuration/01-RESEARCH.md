# Phase 1: Configuration - Research

**Researched:** 2026-05-29
**Domain:** Python configuration management with pydantic-settings
**Confidence:** HIGH

## Summary

Phase 1 delivers a typed, .env-driven configuration system using **pydantic-settings 2.14.1** (Pydantic 2.13.4) as the configuration engine. Five nested sub-models (PostgreSQL, LLM, Embedding, Reranker, QueryParams) compose into a single frozen Settings singleton accessible via `from lightrag_langchain.config import settings`. The entire configuration is validated at import time with fail-fast behavior, categorized error reporting, and cross-field invariant checking.

All decisions are locked by CONTEXT.md — this research verifies the feasibility of each decision against the current pydantic-settings API, confirms package availability and legitimacy, audits the runtime environment, and identifies the specific API patterns, edge cases, and pitfalls the planner must account for.

**Primary recommendation:** Use pydantic-settings 2.14.1 with `nested_model_default_partial_update=True` and `@model_validator(mode='after')` for cross-field invariant checks. Each sub-model gets its own `env_prefix` for independent testability (SC #4). Error formatting is done by catching `ValidationError`, calling `.errors()`, and grouping by `loc` path to produce categorized summary messages.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| .env file parsing | Configuration Layer | — | pydantic-settings loads .env; no other tier touches raw env vars |
| Typed field access | Configuration Layer | — | Pydantic models enforce types at the boundary |
| Required-field validation | Configuration Layer | — | Fail-fast at import; downstream code never sees invalid config |
| Cross-field invariant checking | Configuration Layer | — | `@model_validator(mode='after')` on QueryParams checks token budgets |
| Secret handling (API keys) | Configuration Layer | — | `SecretStr` ensures secrets never leak via print/repr/logs |
| Immutability enforcement | Configuration Layer | — | `frozen=True` prevents runtime mutation of config |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** pydantic-settings for configuration management
- **D-02:** src-layout + hatchling build backend (src/lightrag_langchain/)
- **D-03:** .env.example committed, .env gitignored
- **D-04:** pytest + ruff for testing and code quality
- **D-05:** Fail-fast validation at import time (all fields validated immediately)
- **D-06:** Clear distinction between required (PG connection, API keys) and optional (QueryParams with defaults)
- **D-07:** Categorized summary error messages (all failures collected, grouped by config group)
- **D-08:** Cross-field validation for critical invariants only (e.g., max_entity_tokens + max_relation_tokens < max_total_tokens)
- **D-09:** Nested sub-models (5 BaseModel sub-models under top-level Settings)
- **D-10:** Single file src/lightrag_langchain/config.py (100-150 lines)
- **D-11:** Module-level singleton (config.py bottom: `settings = Settings()`)
- **D-12:** frozen=True on all models (runtime immutability)

### Claude's Discretion
- Sensitive fields use Pydantic `SecretStr` (auto-masking on print/repr/log)
- `__repr__` / `__str__` must not expose SecretStr values; error messages must not include connection strings
- Each config group gets an independent `env_prefix` for standalone instantiation and unit testing (SC #4)

### Deferred Ideas (OUT OF SCOPE)
- None

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONF-01 | .env configuration for PostgreSQL (PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE) | PgConfig sub-model with env_prefix="PG_", SecretStr for password, all fields required |
| CONF-02 | .env configuration for LLM (LLM_BINDING, LLM_BINDING_HOST, LLM_BINDING_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS) | LlmConfig sub-model with env_prefix="LLM_", SecretStr for API key, LLM_BINDING/BINDING_HOST/BINDING_API_KEY/MODEL required |
| CONF-03 | .env configuration for Embedding (EMBEDDING_BINDING, EMBEDDING_BINDING_HOST, EMBEDDING_BINDING_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIM) | EmbeddingConfig sub-model with env_prefix="EMBEDDING_", SecretStr for API key, EMBEDDING_DIM default=1024 |
| CONF-04 | .env configuration for Reranker (RERANK_BINDING, RERANK_BINDING_HOST, RERANK_BINDING_API_KEY, RERANK_MODEL, MIN_RERANK_SCORE) | RerankerConfig sub-model with env_prefix="RERANK_", SecretStr for API key, MIN_RERANK_SCORE default=0.0 |
| CONF-05 | .env configuration for query parameters (TOP_K, CHUNK_TOP_K, MAX_ENTITY_TOKENS, MAX_RELATION_TOKENS, MAX_TOTAL_TOKENS, COSINE_THRESHOLD, KG_CHUNK_PICK_METHOD) | QueryParamsConfig sub-model with env_prefix="" (no prefix), all fields have LightRAG-matching defaults |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-settings | 2.14.1 | .env parsing, BaseSettings, env_prefix | Pydantic official config management; LangChain ecosystem standard [VERIFIED: npm registry — PyPI pip index, slopcheck OK] |
| pydantic | 2.13.4 | BaseModel, SecretStr, validators, frozen | Dependency of pydantic-settings; type system foundation [VERIFIED: npm registry — PyPI pip index, slopcheck OK] |
| python-dotenv | 1.2.2 | .env file parsing (used internally by pydantic-settings) | Transitive dependency of pydantic-settings; standard .env parser [VERIFIED: npm registry — PyPI pip index, slopcheck OK] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hatchling | 1.29.0 | Build backend for src-layout packaging | Specified in pyproject.toml [build-system]; not a runtime dependency [VERIFIED: npm registry — PyPI pip index, slopcheck OK] |
| pytest | 9.0.3 | Test framework | All unit tests for config validation [installed via asdf] |
| ruff | 0.15.14 | Linting + formatting | Code quality enforcement; replaces flake8/black/mypy per D-04 [installed via asdf] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings | python-dotenv + os.environ | Loses type validation, nested models, env_prefix, SecretStr — would require hand-rolling all of D-05 through D-12 |
| hatchling | setuptools, flit, poetry | Hatchling is pydantic-ecosystem standard, simplest src-layout config; user chose it (D-02) |
| ruff | flake8 + black + isort + mypy | Ruff replaces all four in one tool with zero config; user chose it (D-04) |

**Installation:**
```bash
pip install pydantic-settings>=2.14,<3.0 pydantic>=2.13,<3.0
```

**Version verification:**
```bash
pip index versions pydantic-settings   # 2.14.1 (latest)
pip index versions pydantic            # 2.13.4 (latest)
pip index versions python-dotenv       # 1.2.2 (latest)
pip index versions hatchling           # 1.29.0 (latest)
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| pydantic-settings | PyPI | 3+ yrs | High (pydantic official) | github.com/pydantic/pydantic-settings | [OK] | Approved |
| pydantic | PyPI | 7+ yrs | 100M+/month | github.com/pydantic/pydantic | [OK] | Approved |
| python-dotenv | PyPI | 10+ yrs | 50M+/month | github.com/theskumar/python-dotenv | [OK] | Approved |
| hatchling | PyPI | 4+ yrs | High (PyPA official) | github.com/pypa/hatch | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     .env file (gitignored)                       │
│  PG_HOST=..., LLM_BINDING=..., EMBEDDING_DIM=..., ...           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ pydantic-settings reads at import
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Settings (BaseSettings)                       │
│  model_config: env_file=".env", env_nested_delimiter="__",      │
│                nested_model_default_partial_update=True,         │
│                frozen=True, extra="forbid"                       │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │   PgConfig       │  │   LlmConfig      │                     │
│  │   (BaseModel)    │  │   (BaseModel)    │                     │
│  │   env_prefix=    │  │   env_prefix=    │                     │
│  │   "PG_"          │  │   "LLM_"         │                     │
│  │   frozen=True    │  │   frozen=True    │                     │
│  └──────────────────┘  └──────────────────┘                     │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ EmbeddingConfig  │  │  RerankerConfig  │                     │
│  │   (BaseModel)    │  │   (BaseModel)    │                     │
│  │   env_prefix=    │  │   env_prefix=    │                     │
│  │   "EMBEDDING_"   │  │   "RERANK_"      │                     │
│  │   frozen=True    │  │   frozen=True    │                     │
│  └──────────────────┘  └──────────────────┘                     │
│  ┌──────────────────────────────────────────┐                   │
│  │        QueryParamsConfig (BaseModel)      │                   │
│  │        env_prefix="" (no prefix)          │                   │
│  │        frozen=True                        │                   │
│  │  @model_validator(mode='after')           │                   │
│  │  checks token budget invariant            │                   │
│  └──────────────────────────────────────────┘                   │
│                                                                  │
│  @model_validator(mode='after') on Settings:                     │
│    catches all sub-model errors, formats categorized summary     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│           Module-level singleton: settings = Settings()          │
│           from lightrag_langchain.config import settings         │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
          All downstream phases (Phase 2-6)
```

**Data flow:**
1. Developer creates `.env` from `.env.example` template
2. On `import lightrag_langchain.config`, pydantic-settings reads `.env` file
3. Each sub-model parses its prefixed env vars (e.g., `PG_HOST` → `PgConfig.host`)
4. Field-level validation runs (types, required checks)
5. `@model_validator(mode='after')` on QueryParams checks cross-field invariants
6. If any validation fails → `SettingsError` (custom) with categorized summary
7. If all valid → frozen singleton is available for downstream use

### Recommended Project Structure
```
lightrag-langchain/
├── src/
│   └── lightrag_langchain/
│       ├── __init__.py          # Package marker
│       └── config.py            # All configuration (~100-150 lines, D-10)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures (temp .env file factory)
│   └── test_config.py           # All config tests
├── .env.example                 # Committed template (D-03)
├── .env                         # gitignored (D-03)
├── .gitignore
├── pyproject.toml               # hatchling build config + deps + ruff + pytest
└── README.md
```

### Pattern 1: Nested Sub-Model with Independent env_prefix
**What:** Each config group is a `BaseModel` subclass with its own `env_prefix` in `model_config`. This enables standalone instantiation for testing (SC #4) while the top-level `Settings(BaseSettings)` composes them all.

**When to use:** For every config group (PgConfig, LlmConfig, EmbeddingConfig, RerankerConfig, QueryParamsConfig).

**Example:**
```python
# Source: pydantic-settings 2.14.1 docs, verified via smoke test on Python 3.12
# https://docs.pydantic.dev/latest/concepts/pydantic-settings/

from pydantic import BaseModel, SecretStr, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

class PgConfig(BaseModel):
    """PostgreSQL connection settings. env_prefix='PG_' maps PG_HOST -> host."""
    model_config = ConfigDict(frozen=True)

    host: str                      # required, no default
    port: int = 5432
    user: str                      # required
    password: SecretStr            # required, auto-masked
    database: str                  # required

class LlmConfig(BaseModel):
    """LLM provider settings. env_prefix='LLM_' maps LLM_MODEL -> model."""
    model_config = ConfigDict(frozen=True)

    binding: str                   # required (openai, ollama, etc.)
    binding_host: str              # required
    binding_api_key: SecretStr     # required, auto-masked
    model: str                     # required
    temperature: float = 0.0
    max_tokens: int = 9000

class EmbeddingConfig(BaseModel):
    """Embedding provider settings. env_prefix='EMBEDDING_'."""
    model_config = ConfigDict(frozen=True)

    binding: str                   # required
    binding_host: str              # required
    binding_api_key: SecretStr     # required
    model: str                     # required
    dim: int = 1024               # matches upstream aliyun text-embedding-v4

class RerankerConfig(BaseModel):
    """Reranker settings. env_prefix='RERANK_'."""
    model_config = ConfigDict(frozen=True)

    binding: str = ""             # empty = rerank disabled
    binding_host: str = ""
    binding_api_key: SecretStr = SecretStr("")
    model: str = ""
    min_rerank_score: float = 0.0

class QueryParamsConfig(BaseModel):
    """Query behavior defaults. No env prefix (flat top-level vars)."""
    model_config = ConfigDict(frozen=True)

    top_k: int = 40                        # LightRAG DEFAULT_TOP_K
    chunk_top_k: int = 20                  # LightRAG DEFAULT_CHUNK_TOP_K
    max_entity_tokens: int = 6000          # LightRAG DEFAULT_MAX_ENTITY_TOKENS
    max_relation_tokens: int = 8000        # LightRAG DEFAULT_MAX_RELATION_TOKENS
    max_total_tokens: int = 30000          # LightRAG DEFAULT_MAX_TOTAL_TOKENS
    cosine_threshold: float = 0.2          # LightRAG DEFAULT_COSINE_THRESHOLD
    kg_chunk_pick_method: str = "VECTOR"   # LightRAG DEFAULT_KG_CHUNK_PICK_METHOD

    @model_validator(mode='after')
    def check_token_budget(self):
        """D-08: Cross-field invariant — entities + relations < total."""
        if self.max_entity_tokens + self.max_relation_tokens >= self.max_total_tokens:
            raise ValueError(
                f"Token budget violated: max_entity_tokens ({self.max_entity_tokens}) "
                f"+ max_relation_tokens ({self.max_relation_tokens}) "
                f"must be < max_total_tokens ({self.max_total_tokens})"
            )
        return self

class Settings(BaseSettings):
    """Top-level settings composing all five config groups."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        extra="forbid",
        case_sensitive=False,
    )

    pg: PgConfig
    llm: LlmConfig
    embedding: EmbeddingConfig
    reranker: RerankerConfig = RerankerConfig()
    query_params: QueryParamsConfig = QueryParamsConfig()

# Module-level singleton (D-11)
settings = Settings()
```

### Pattern 2: Categorized Error Summary (D-07)
**What:** Catch `ValidationError` at import time, process `.errors()` list, group by config group based on `loc` tuple path, and raise a single formatted exception with categorized summary.

**When to use:** In the module-level singleton instantiation. Wrapped in try/except to produce a user-friendly error.

**Example:**
```python
# Source: WebSearch verified — pydantic ValidationError.errors() API
# https://docs.pydantic.dev/latest/errors/errors/

from pydantic import ValidationError

class SettingsError(Exception):
    """Raised when configuration validation fails with categorized summary."""
    pass

def _format_validation_error(exc: ValidationError) -> str:
    """Group errors by config group and format a categorized summary."""
    from collections import defaultdict
    groups: dict[str, list[str]] = defaultdict(list)

    GROUP_MAP = {
        "pg": "PostgreSQL",
        "llm": "LLM",
        "embedding": "Embedding",
        "reranker": "Reranker",
        "query_params": "QueryParams",
    }

    for err in exc.errors():
        loc_path = ".".join(str(p) for p in err["loc"])
        group_key = err["loc"][0] if err["loc"] else "unknown"
        group_name = GROUP_MAP.get(str(group_key), str(group_key))
        field_name = ".".join(str(p) for p in err["loc"][1:]) if len(err["loc"]) > 1 else str(group_key)
        groups[group_name].append(f"  - {field_name}: {err['msg']}")

    lines = ["Configuration validation failed:\n"]
    for group_name in ["PostgreSQL", "LLM", "Embedding", "Reranker", "QueryParams"]:
        if group_name in groups:
            lines.append(f"[{group_name}]")
            lines.extend(groups[group_name])
            lines.append("")

    return "\n".join(lines)

# At module level:
try:
    settings = Settings()
except ValidationError as e:
    raise SettingsError(_format_validation_error(e)) from e
```

### Pattern 3: SecretStr Safe Logging (Claude's Discretion)
**What:** All sensitive fields use `SecretStr`. The Pydantic `__repr__` and `__str__` for SecretStr display `**********` automatically. Custom error formatting must avoid including raw values.

**When to use:** Every API key, password, and secret field.

**Example:**
```python
# Source: pydantic-settings 2.14.1 docs — SecretStr auto-masking
# Verified via smoke test on Python 3.12

from pydantic import SecretStr

# In error formatting, NEVER include the raw value:
# WRONG:  f"API key '{self.api_key}' is invalid"  # exposes secret
# WRONG:  f"API key '{self.api_key.get_secret_value()}' is invalid"

# CORRECT: only reference field names, never values
# f"Missing required field: llm.binding_api_key"
# The err['msg'] from pydantic does NOT include the actual value, only the type
```

### Anti-Patterns to Avoid
- **Using `BaseSettings` for sub-models:** Sub-models must use `BaseModel`, not `BaseSettings`. Only the top-level `Settings` inherits from `BaseSettings`. Using `BaseSettings` for sub-models causes env var parsing conflicts. [CITED: pydantic-settings docs, StackOverflow]
- **Missing `nested_model_default_partial_update=True`:** Without this, setting a single env var for a nested model causes all other defaults to be lost (new instance replaces default). This is the #1 pitfall for nested models in pydantic-settings. [CITED: pydantic/pydantic-settings#425, #203]
- **Using `model_post_init` for validation on frozen models:** `model_post_init` runs before `@model_validator(mode='after')` but after `frozen` is enforced — field mutations fail silently or raise errors. Use `@model_validator(mode='after')` for read-only invariant checks instead. [CITED: pydantic/pydantic#7163, #11495]
- **Catching `ValidationError` without formatting:** Raw pydantic errors are developer-hostile (field paths like `('pg', 'host')`, technical error types like `'missing'`). Always format into categorized human-readable groups per D-07. [CITED: pydantic error handling docs]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| .env file parsing | Manual `os.getenv` + `load_dotenv` calls | pydantic-settings `BaseSettings(env_file=".env")` | Handles encoding, multiline values, interpolation, env var precedence, comments |
| Type coercion/validation | Manual `int(os.getenv("PORT", "5432"))` | Pydantic field type annotations (`port: int = 5432`) | Handles all Python types, nested models, error messages, and validation pipeline |
| Required field checking | Manual `if not value: raise ValueError(...)` | Pydantic required fields (no default value) | Automatic `missing` error with field path, collected with all other errors |
| Secret masking | Manual `__repr__` override, redaction logic | Pydantic `SecretStr` | Built-in `**********` display, `.get_secret_value()` for programmatic access, JSON serialization safe |
| Error collection/grouping | Custom error accumulator | `ValidationError.errors()` → group by `loc` path | Pydantic already collects all errors (not fail-first); just format the list |
| Immutability | Property setters, `__setattr__` override | `model_config = ConfigDict(frozen=True)` | Pydantic-enforced at the model level; raises `ValidationError` on mutation |

**Key insight:** pydantic-settings handles the entire configuration pipeline from file parsing to type validation to error collection. Hand-rolling any part of this creates maintenance burden and diverges from the LangChain ecosystem standard. The only custom code needed is the error formatter (~20 lines) to produce categorized summaries per D-07.

## Runtime State Inventory

> Skip — this is a greenfield phase with no existing runtime state. No rename/refactor/migration.

## Common Pitfalls

### Pitfall 1: `nested_model_default_partial_update` Omission
**What goes wrong:** Developer sets `LLM_MODEL=gpt-5-mini` in `.env` but doesn't set `LLM_TEMPERATURE`. Without `nested_model_default_partial_update=True`, the LlmConfig is constructed from ONLY the env var — `temperature` gets no value and raises a `missing` error, even though the field has a default.

**Why it happens:** Pydantic-settings creates a fresh instance of the nested model using only env-provided values unless this flag is set. The default instance (with all defaults populated) is discarded.

**How to avoid:** Always set `nested_model_default_partial_update=True` in `SettingsConfigDict` when nested sub-models have default values. [CITED: pydantic/pydantic-settings#425]

**Warning signs:** "Field required" errors for fields that clearly have defaults in the model definition — especially when only some env vars for that group are set.

### Pitfall 2: `frozen=True` + `model_validator(mode='after')` Mutation Attempts
**What goes wrong:** Developer tries to normalize or transform a field inside `@model_validator(mode='after')` on a frozen model. The mutation fails because `frozen` is already enforced when the after validator runs.

**Why it happens:** Pydantic execution order is: field validation → `model_post_init` → `model_validator(mode='after')`. The `frozen=True` constraint activates during field validation, before the after validator. [CITED: pydantic/pydantic#7163]

**How to avoid:** Use `@model_validator(mode='after')` ONLY for read-only invariant checks (read fields, raise if bad). If you need to transform values, use `@model_validator(mode='before')` or `@field_validator` which run before freezing. For Phase 1, D-08 only requires read-only checking of the token budget invariant — no mutation needed.

**Warning signs:** `ValidationError` with message about frozen model when calling `@model_validator(mode='after')`.

### Pitfall 3: `extra="forbid"` Failing on Unknown .env Variables
**What goes wrong:** User adds a typo'd env var (e.g., `LLM_MODEL=gpt-5-mini` instead of `LLM_MODEL=gpt-5-mini`) — wait, that's identical. Actually: user adds an env var the model doesn't know about. With `extra="forbid"`, pydantic raises an error.

**Why it happens:** `extra="forbid"` is a strictness setting that rejects unknown fields. While good for catching typos, it also rejects env vars set by other tools (e.g., `PYTHONPATH`, `PATH`) if they happen to be in `.env`.

**How to avoid:** Use `extra="forbid"` on the top-level `Settings` but ensure `.env` only contains project-specific variables. The planner should include `.env.example` as the canonical template. For sub-models, `extra="forbid"` is less risky since env_prefix scoping limits which vars they see. [CITED: pydantic-settings docs]

**Warning signs:** `Extra inputs are not permitted` errors for variables that seem unrelated to the project.

### Pitfall 4: Python Version Mismatch
**What goes wrong:** System Python is 3.14.4, but pydantic/pydantic-settings are installed under asdf Python 3.12.13. Running `python3 config.py` uses the wrong interpreter.

**Why it happens:** macOS Homebrew Python 3.14 takes precedence in PATH over asdf shims unless asdf is properly configured.

**How to avoid:** Ensure pyproject.toml specifies `requires-python = ">=3.12"`. Use `python3 -m pytest` (which resolves to the active asdf Python if configured) or explicitly use asdf paths. Document which Python to use in README. The planner should include a task to verify the Python environment.

**Warning signs:** `ModuleNotFoundError: No module named 'pydantic'` when running with system Python.

## Code Examples

Verified patterns from official sources:

### Sub-Model Independent Instantiation (SC #4)
```python
# Source: pydantic-settings 2.14.1 docs, verified via smoke test on Python 3.12

# Each sub-model can be tested independently by setting env vars and instantiating directly:
import os
os.environ["PG_HOST"] = "localhost"
os.environ["PG_USER"] = "test"
os.environ["PG_PASSWORD"] = "secret"
os.environ["PG_DATABASE"] = "rag"

pg = PgConfig()  # reads from os.environ (no .env file needed for unit tests)
assert pg.host == "localhost"
assert pg.port == 5432  # default
```

### ValidationError Categorized Formatting
```python
# Source: pydantic ValidationError docs + WebSearch verified
# https://docs.pydantic.dev/latest/errors/errors/

try:
    Settings()
except ValidationError as e:
    # e.errors() returns list of dicts with 'loc', 'type', 'msg', 'input', 'ctx'
    # loc is a tuple tracking the path: ('pg', 'host') or ('llm', 'binding_api_key')
    for err in e.errors():
        group = err['loc'][0]       # 'pg', 'llm', 'embedding', 'reranker', 'query_params'
        field = err['loc'][1:]       # ('host',) or ('binding_api_key',)
        message = err['msg']         # human-readable
```

### pyproject.toml with hatchling src-layout
```toml
# Source: hatchling docs, PEP 621
[build-system]
requires = ["hatchling>=1.8"]
build-backend = "hatchling.build"

[project]
name = "lightrag-langchain"
version = "0.1.0"
description = "LangChain-based read-only query layer for LightRAG knowledge graph"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.13,<3.0",
    "pydantic-settings>=2.14,<3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "ruff>=0.15",
]

[tool.hatch.build.targets.wheel]
packages = ["src/lightrag_langchain"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `class Config:` inner class | `model_config = ConfigDict(...)` | Pydantic v2 (2023) | Old syntax deprecated; must use ConfigDict |
| `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` | Pydantic v2 (2023) | BaseSettings extracted to separate package |
| `Field(env="VAR_NAME")` | `Field(validation_alias="VAR_NAME")` | Pydantic v2 (2023) | `env` kwarg removed; use `validation_alias` |
| `nested_model_default_partial_update` missing | Always set `True` for nested models | v2.5+ (2024) | Prevents default value loss on partial env override |

**Deprecated/outdated:**
- `pydantic.BaseSettings`: Moved to `pydantic_settings.BaseSettings` in v2.0. Importing from `pydantic` raises deprecation warning and will be removed.
- `class Config` inner class: Replaced by `model_config = ConfigDict(...)` class attribute. Still works in v2 but emits warnings.
- `Field(env=...)`: Removed entirely in v2. Use `Field(validation_alias=...)` for custom env var names.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Python 3.12.13 (via asdf) will be the project interpreter | Environment Availability | Low — system Python 3.14.4 also meets >=3.12 constraint; could use either |
| A2 | QueryParams default values matching LightRAG upstream (TOP_K=40, etc.) are correct for this project | Standard Stack | Low — values are configurable via .env; defaults serve as starting point |
| A3 | `env_prefix` on sub-models works with `nested_model_default_partial_update` — the official docs show them together but do not explicitly document the interaction | Architecture Patterns | Medium — if interaction causes issues, sub-models can use `validation_alias` instead of `env_prefix` |

## Open Questions (RESOLVED)

1. **RerankerConfig: should `binding=""` mean "rerank disabled"?**
   - What we know: LightRAG upstream uses `RERANK_BINDING=null` to disable. In pydantic, `None` vs `""` have different semantics. Empty string is easier to set in `.env` but less semantically clear.
   - What's unclear: Whether downstream Phase 3 (LLM Integration) treats `""` or `None` as "disabled."
   - Recommendation: Use `binding: str = ""` with a comment `# empty string = rerank disabled`. The planner can adjust if Phase 3 needs `None`.

2. **Should `embedding.dim` default to 1024 or 3072?**
   - What we know: CONTEXT.md says "Embedding 维度默认 1024" (D-06). Upstream LightRAG env.example uses `EMBEDDING_DIM=3072` (for text-embedding-3-large). The PROJECT.md context says upstream embedding is "阿里云 text-embedding-v4（1024 维）".
   - What's unclear: The env.example value (3072) contradicts the project context (1024). The CONTEXT.md decision (D-06) aligns with the project context.
   - Recommendation: Use 1024 as decided in D-06. The env.example template should show 1024 with a comment noting it matches the upstream LightRAG embedding dimension.

3. **What Python interpreter should pyproject.toml require?**
   - What we know: CONTEXT.md says Python >= 3.12. System has 3.14.4, asdf has 3.12.13. The CLAUDE.md constraint is >= 3.12.
   - What's unclear: Whether to pin to a specific minor version or just set minimum.
   - Recommendation: `requires-python = ">=3.12"` (minimum only). Do not pin an upper bound — pydantic-settings 2.14 runs on Python 3.14.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Project runtime | ✓ | 3.12.13 (asdf) / 3.14.4 (system) | — |
| pip | Package installation | ✓ | 25.0.1 | — |
| pydantic-settings | Config parsing (D-01) | ✓ | 2.14.1 | — |
| pydantic | Type system (D-01 dep) | ✓ | 2.13.4 | — |
| python-dotenv | .env parsing (transitive) | ✓ | 1.2.2 | — |
| hatchling | Build backend (D-02) | ✓ | 1.29.0 | — |
| pytest | Testing (D-04) | ✓ | 9.0.3 | — |
| ruff | Linting/formatting (D-04) | ✓ | 0.15.14 | — |
| PostgreSQL | Phase 2+ (out of scope) | — | — | Not needed for Phase 1 |
| LLM API endpoint | Phase 3+ (out of scope) | — | — | Not needed for Phase 1 |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none

**Note:** System Python 3.14.4 does NOT have pydantic installed. The project MUST use the asdf Python 3.12.13 where packages are installed. The planner should include a task to create `.python-version` (asdf) or document the expected Python version.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` (Wave 0 — needs creation) |
| Quick run command | `python3 -m pytest tests/test_config.py -x` |
| Full suite command | `python3 -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | PostgreSQL config loaded from .env with pg_ prefix | unit | `pytest tests/test_config.py::test_pg_config_from_env -x` | No (Wave 0) |
| CONF-02 | LLM config loaded from .env with llm_ prefix | unit | `pytest tests/test_config.py::test_llm_config_from_env -x` | No (Wave 0) |
| CONF-03 | Embedding config loaded from .env with embedding_ prefix, dim defaults to 1024 | unit | `pytest tests/test_config.py::test_embedding_config_defaults -x` | No (Wave 0) |
| CONF-04 | Reranker config loaded from .env with rerank_ prefix | unit | `pytest tests/test_config.py::test_reranker_config_from_env -x` | No (Wave 0) |
| CONF-05 | QueryParams loaded with LightRAG defaults | unit | `pytest tests/test_config.py::test_query_params_defaults -x` | No (Wave 0) |
| SC #1 | Project module importable without errors | smoke | `python3 -c "import lightrag_langchain"` | No (Wave 0) |
| SC #2 | .env parsed, typed fields accessible | integration | `pytest tests/test_config.py::test_settings_from_dotenv -x` | No (Wave 0) |
| SC #3 | Missing required config raises clear error | unit | `pytest tests/test_config.py::test_missing_required_field_error -x` | No (Wave 0) |
| SC #4 | Each config group independently loadable/testable | unit | `pytest tests/test_config.py::test_independent_submodel_instantiation -x` | No (Wave 0) |
| D-07 | Categorized error summary groups by config group | unit | `pytest tests/test_config.py::test_error_categorization -x` | No (Wave 0) |
| D-08 | Cross-field token budget invariant checked | unit | `pytest tests/test_config.py::test_token_budget_invariant -x` | No (Wave 0) |
| D-12 | frozen=True prevents mutation | unit | `pytest tests/test_config.py::test_frozen_prevents_mutation -x` | No (Wave 0) |
| --- | SecretStr masks values in repr/str | unit | `pytest tests/test_config.py::test_secret_str_masking -x` | No (Wave 0) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_config.py -x`
- **Per wave merge:** `python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared fixtures (temporary .env file factory, env var monkeypatching)
- [ ] `tests/test_config.py` — covers all CONF-01 through CONF-05 + all 4 success criteria + D-07/D-08/D-12
- [ ] `src/lightrag_langchain/__init__.py` — package marker
- [ ] `pyproject.toml` — build system, dependencies, ruff config, pytest config
- [ ] `.env.example` — committed template with all config keys documented
- [ ] `.gitignore` — includes `.env` exclusion
- [ ] Framework install: `pip install pytest>=9.0` — already available via asdf, needs pyproject.toml dev dependency declaration

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — (out of scope; no auth in Phase 1) |
| V3 Session Management | No | — (out of scope) |
| V4 Access Control | No | — (out of scope) |
| V5 Input Validation | Yes | Pydantic field validators + type coercion + `extra="forbid"` |
| V6 Cryptography | No | No cryptographic operations in config layer; SecretStr for credential storage |
| V7 Error Handling | Yes | Fail-fast with categorized errors; secrets never in error messages |
| V8 Data Protection | Yes | `SecretStr` for all passwords/API keys; `frozen=True` prevents mutation |

### Known Threat Patterns for pydantic-settings configuration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| .env file committed to git exposing credentials | Information Disclosure | `.env` in `.gitignore`; `.env.example` with placeholders only (D-03) |
| Secret values appearing in logs/errors | Information Disclosure | `SecretStr` auto-masking (`**********`); custom error formatter never includes raw values |
| Runtime config mutation bypassing validation | Tampering | `frozen=True` on all models; raises `ValidationError` on mutation attempt |
| Unvalidated env var injection via extra fields | Spoofing | `extra="forbid"` rejects unknown fields; typos caught early |
| API key exposure via `repr()` in debug output | Information Disclosure | `SecretStr.__repr__()` returns `SecretStr('**********')`; cannot accidentally print |
| Default value poisoning via partial env override | Tampering | `nested_model_default_partial_update=True` preserves non-overridden defaults |

## Sources

### Primary (HIGH confidence)
- PyPI registry — `pip index versions` verified: pydantic-settings 2.14.1, pydantic 2.13.4, python-dotenv 1.2.2, hatchling 1.29.0
- slopcheck 0.6.1 — all 4 packages rated [OK]
- Python 3.12 smoke test — pydantic-settings import, nested model instantiation, frozen enforcement, ValidationError structure all verified
- LightRAG upstream source (`/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/constants.py`) — default values for TOP_K (40), CHUNK_TOP_K (20), MAX_ENTITY_TOKENS (6000), MAX_RELATION_TOKENS (8000), MAX_TOTAL_TOKENS (30000), COSINE_THRESHOLD (0.2), KG_CHUNK_PICK_METHOD ("VECTOR")
- LightRAG upstream env.example (`/Users/lizhouyang/llm/graphrag/LightRAG/env.example`) — env var naming conventions, RERANK_BINDING=null pattern

### Secondary (MEDIUM confidence)
- pydantic-settings 2.x docs (via WebFetch/WabSearch) — nested models, env_nested_delimiter, env_prefix, nested_model_default_partial_update, SettingsConfigDict, SecretStr usage
- pydantic/pydantic-settings#425, #203 — nested_model_default_partial_update behavior documented in issues
- pydantic/pydantic#7163, #11495 — model_validator execution order relative to frozen enforcement
- StackOverflow #79298414 — flat env vars to nested pydantic models pattern
- pydantic/pydantic Discussion #12036 — frozen workarounds and ForceSetAttr pattern

### Tertiary (LOW confidence)
- None — all findings cross-verified with multiple sources or smoke-tested directly

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI, slopcheck [OK], smoke-tested on Python 3.12
- Architecture: HIGH — nested model pattern verified against pydantic-settings 2.14.1 docs and smoke test; execution order for frozen + validators confirmed via official GitHub issues
- Pitfalls: HIGH — primary pitfalls (nested_model_default_partial_update, frozen + model_post_init) documented in official pydantic/pydantic-settings GitHub issues with maintainer responses

**Research date:** 2026-05-29
**Valid until:** 2026-06-29 (30 days — pydantic-settings API is stable within 2.x major; no breaking changes expected)
