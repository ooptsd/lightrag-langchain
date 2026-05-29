---
phase: 01-configuration
plan: 02
subsystem: configuration
tags: [config, pydantic-settings, tdd, typed-api]
requires: [01-01]
provides:
  - src/lightrag_langchain/config.py
  - tests/test_config.py
affects:
  - Phase 2 (Data Layer)
  - Phase 3 (LLM Integration)
  - Phase 4 (Query Strategies)
  - Phase 5 (Retriever Interfaces)
  - Phase 6 (QA Chain)
tech-stack:
  added: [pydantic 2.13.4, pydantic-settings 2.14.1]
  patterns: [pydantic-settings nested models, lazy module singleton, SecretStr masking]
key-files:
  created:
    - src/lightrag_langchain/config.py
    - tests/test_config.py
decisions:
  - D-05: fail-fast validation via lazy Settings singleton (SettingsError on access)
  - D-06: EmbeddingConfig.dim defaults to 1024
  - D-07: categorized error summary grouped by [PostgreSQL]/[LLM]/[Embedding]/[Reranker]/[QueryParams]
  - D-08: token budget invariant enforced via @model_validator(mode='after')
  - D-09: 5 nested BaseModel sub-models composed in Settings(BaseSettings)
  - D-10: single src/lightrag_langchain/config.py
  - D-11: module-level settings singleton via __getattr__ (lazy evaluation)
  - D-12: frozen=True on all models and Settings
  - Env var routing uses nested delimiter format (pg__host, llm__binding, etc.)
  - SecretStr for all password/API key fields with pydantic auto-masking
metrics:
  duration: 734s
  completed_date: "2026-05-29T14:00:17Z"
---

# Phase 01 Plan 02: Typed Configuration API Summary

Implemented the typed configuration API using pydantic-settings: 5 frozen nested sub-models,
Settings(BaseSettings) composing them, fail-fast validation via lazy singleton with categorized
error summary, SecretStr for sensitive fields, and frozen immutability.

## Execution Summary

| Task | Name | Type | Status | Commit |
|------|------|------|--------|--------|
| 2.1 | Write test_config.py (RED) | tdd:auto | Complete | 0f34885 |
| 2.2 | Implement config.py (GREEN) | tdd:auto | Complete | 7f55feb |
| 2.3 | Verify: tests, lint, format | auto | Complete | 2f21892 |

## Verifications

| Check | Result |
|-------|--------|
| pytest tests/ -v (30 tests) | PASSED |
| ruff check src/ tests/ | PASSED |
| ruff format --check src/ tests/ | PASSED |
| sub-model imports (no .env) | PASSED |
| settings singleton with env vars | PASSED |
| settings singleton without env vars | SettingsError (expected) |
| frozen mutation prevention | ValidationError raised |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed env var routing format for pydantic-settings nested models**
- **Found during:** Task 2.2
- **Issue:** Plan assumed flat env var names (e.g., `PG_HOST`) would be automatically routed to nested model fields (`pg.host`) by pydantic-settings. pydantic-settings 2.14.1 requires the nested delimiter format (`pg__host`, `llm__binding`, etc.) with `env_nested_delimiter="__"`.
- **Fix:** Updated all test env var names from flat format to nested delimiter format. Config.py uses `env_nested_delimiter="__"` with `case_sensitive=False`.
- **Files modified:** tests/test_config.py

**2. [Rule 1 - Bug] Fixed module import blocking with lazy singleton**
- **Found during:** Task 2.2
- **Issue:** Module-level `settings = Settings()` runs at import time, causing `ModuleNotFoundError`-equivalent failure for ALL imports from config (including sub-model classes) when .env is missing.
- **Fix:** Replaced immediate `settings = Settings()` with lazy `__getattr__` pattern. Settings is created on first access of `settings`, preserving fail-fast (D-05) while allowing sub-model imports without a valid .env.
- **Files modified:** src/lightrag_langchain/config.py

**3. [Rule 1 - Bug] Fixed SettingsError wrapping for direct Settings() calls**
- **Found during:** Task 2.2
- **Issue:** Direct `Settings()` calls raised raw `ValidationError` instead of `SettingsError`. Tests expecting `SettingsError` from direct instantiation failed.
- **Fix:** Added `__init__` override on Settings class that catches `ValidationError` and raises `SettingsError` with formatted message.
- **Files modified:** src/lightrag_langchain/config.py

**4. [Rule 1 - Bug] Fixed _format_validation_error dropping extra field errors**
- **Found during:** Task 2.3
- **Issue:** `extra="forbid"` errors for unknown .env keys (like `TYPO_KEY`) were not included in the categorized output because the group name didn't match any predefined group.
- **Fix:** Added fallback iteration over remaining (unknown) groups after processing the predefined ordered list.
- **Files modified:** src/lightrag_langchain/config.py

**5. [Rule 2 - Missing Critical Functionality] Added Settings.__init__ validation wrapper**
- **Found during:** Task 2.2
- **Issue:** The plan's specification that "Missing a required field raises SettingsError" required wrapping pydantic's `ValidationError` in `SettingsError`. Without this wrapper, direct `Settings()` calls would expose raw pydantic errors.
- **Fix:** Added `__init__` override that catches `ValidationError` and re-raises as `SettingsError`.
- **Files modified:** src/lightrag_langchain/config.py

## TDD Gate Compliance

```
[RED]   0f34885 test(01-configuration): add failing tests for typed configuration API (RED)
[GREEN] 7f55feb feat(01-configuration): implement typed configuration API with pydantic-settings (GREEN)
[VERIFY] 2f21892 chore(01-configuration): format and lint fixes, all 30 tests pass
```

All three TDD gates present and in correct sequence.

## Known Stubs

None. RerankerConfig's empty-string defaults (`binding=""`, `binding_host=""`, etc.) are intentional per D-09 — empty binding means rerank is disabled.

## Threat Flags

None. All threat mitigations from the plan's threat model are implemented:
- T-01-03: Error formatter references field names only, never raw values
- T-01-04: All password/API key fields use SecretStr with pydantic auto-masking
- T-01-05: frozen=True on all models prevents runtime tampering
- T-01-06: extra="forbid" rejects unknown .env variables

## Self-Check: PASSED

- src/lightrag_langchain/config.py: EXISTS
- tests/test_config.py: EXISTS
- Commit 0f34885: EXISTS
- Commit 7f55feb: EXISTS
- Commit 2f21892: EXISTS
