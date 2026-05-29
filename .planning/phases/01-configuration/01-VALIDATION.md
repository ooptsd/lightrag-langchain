---
phase: 01
slug: configuration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 9.0 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` (Wave 0 — needs creation) |
| **Quick run command** | `python3 -m pytest tests/test_config.py -x` |
| **Full suite command** | `python3 -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_config.py -x`
- **After every plan wave:** Run `python3 -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | CONF-01 | — | N/A | unit | `pytest tests/test_config.py::test_pg_config_from_env -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | CONF-02 | — | N/A | unit | `pytest tests/test_config.py::test_llm_config_from_env -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | CONF-03 | — | N/A | unit | `pytest tests/test_config.py::test_embedding_config_defaults -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | CONF-04 | — | N/A | unit | `pytest tests/test_config.py::test_reranker_config_from_env -x` | ❌ W0 | ⬜ pending |
| 01-01-05 | 01 | 1 | CONF-05 | — | N/A | unit | `pytest tests/test_config.py::test_query_params_defaults -x` | ❌ W0 | ⬜ pending |
| 01-01-06 | 01 | 1 | SC #1 | — | N/A | smoke | `python3 -c "import lightrag_langchain"` | ❌ W0 | ⬜ pending |
| 01-01-07 | 01 | 1 | SC #2 | — | N/A | integration | `pytest tests/test_config.py::test_settings_from_dotenv -x` | ❌ W0 | ⬜ pending |
| 01-01-08 | 01 | 1 | SC #3 | — | N/A | unit | `pytest tests/test_config.py::test_missing_required_field_error -x` | ❌ W0 | ⬜ pending |
| 01-01-09 | 01 | 1 | SC #4 | — | N/A | unit | `pytest tests/test_config.py::test_independent_submodel_instantiation -x` | ❌ W0 | ⬜ pending |
| 01-01-10 | 01 | 1 | D-07 | — | N/A | unit | `pytest tests/test_config.py::test_error_categorization -x` | ❌ W0 | ⬜ pending |
| 01-01-11 | 01 | 1 | D-08 | — | N/A | unit | `pytest tests/test_config.py::test_token_budget_invariant -x` | ❌ W0 | ⬜ pending |
| 01-01-12 | 01 | 1 | D-12 | — | N/A | unit | `pytest tests/test_config.py::test_frozen_prevents_mutation -x` | ❌ W0 | ⬜ pending |
| 01-01-13 | 01 | 1 | — | — | SecretStr masks values in repr/str | unit | `pytest tests/test_config.py::test_secret_str_masking -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared fixtures (temporary .env file factory, env var monkeypatching)
- [ ] `tests/test_config.py` — covers all CONF-01 through CONF-05 + all 4 success criteria + D-07/D-08/D-12
- [ ] `src/lightrag_langchain/__init__.py` — package marker
- [ ] `pyproject.toml` — build system, dependencies, ruff config, pytest config
- [ ] `.env.example` — committed template with all config keys documented
- [ ] `.gitignore` — includes `.env` exclusion
- [ ] Framework install: `pip install pytest>=9.0` — needs pyproject.toml dev dependency declaration

---

## Manual-Only Verifications

None — all phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
