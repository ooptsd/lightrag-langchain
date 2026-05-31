---
phase: 07
slug: samples-docs-readme-md
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-31
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + mkdocs build |
| **Config file** | pyproject.toml (pytest), mkdocs.yml (docs build) |
| **Quick run command** | `uv run pytest tests/ -q` |
| **Full suite command** | `uv run pytest tests/ -v && uv run mkdocs build --strict` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -q`
- **After every plan wave:** Run full suite (tests + `mkdocs build --strict`)
- **Before `/gsd-verify-work`:** Full suite must be green, mkdocs build must pass
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | DOCS-README | N/A | N/A | docs | `test -f README.md` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | DOCS-MKDOCS | N/A | N/A | docs | `uv run mkdocs build --strict` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 1 | DOCS-API | N/A | N/A | docs | `grep -c ':::' docs/api/*.md` | ❌ W0 | ⬜ pending |
| 07-01-04 | 01 | 1 | DOCS-EXAMPLES | N/A | N/A | integration | `uv run python examples/*.py` | ❌ W0 | ⬜ pending |
| 07-01-05 | 01 | 1 | DOCS-GH-PAGES | N/A | N/A | ci | `test -f .github/workflows/docs.yml` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `mkdocs.yml` — MkDocs configuration at project root
- [ ] `docs/index.md` — Landing page (distinct from README.md)
- [ ] `docs/api/` — API reference directory structure
- [ ] `mkdocs-material` + `mkdocstrings` + `mkdocstrings-python` added to dev dependencies
- [ ] `.github/workflows/docs.yml` — GitHub Actions deploy workflow

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GitHub Pages URL accessible | DOCS-GH-PAGES | Requires GitHub repo settings config | After first deploy: open `https://<user>.github.io/lightrag-langchain/` and verify navigation |
| Jupyter notebook output cells | DOCS-EXAMPLES | .ipynb output is visual | Open `examples/walkthrough.ipynb`, run all cells, verify outputs render correctly |
| README.md bilingual quality | DOCS-README | Language quality is subjective | Native Chinese speaker reviews README for clarity and accuracy |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
