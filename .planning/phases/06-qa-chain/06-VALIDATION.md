---
phase: 6
slug: qa-chain
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-31
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.x |
| **Config file** | pyproject.toml (tool.pytest.ini_options) |
| **Quick run command** | `pytest tests/ -x -q --no-header` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --no-header`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| *(populated during planning)* | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_chain_base.py` — stubs for CHAIN-01 (base chain pipeline)
- [ ] `tests/test_chain_dispatch.py` — stubs for CHAIN-01 (6 chain subclasses)
- [ ] `tests/test_chain_stream.py` — stubs for CHAIN-02 (astream)
- [ ] `tests/test_chain_keywords.py` — stubs for CHAIN-03 (pre-provided keywords)
- [ ] `tests/conftest.py` — chain-specific fixtures (mock retriever, mock llm)

*Existing infrastructure: pytest + pytest-asyncio configured. conftest.py fixtures for mock PGVectorStore/PGGraphStore already exist.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| *to be determined during planning* | | | |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
