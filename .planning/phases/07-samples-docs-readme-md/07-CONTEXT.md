# Phase 7: Samples & Docs + README.md — Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers all developer-facing documentation for the lightrag-langchain library: a comprehensive README.md, API documentation via MkDocs + Material, and a complete `examples/` directory demonstrating all 6 query modes. The goal is to make the library immediately usable by any developer familiar with LangChain — they can read the README to understand what the library does, browse API docs for reference, and copy-paste from examples to start building.

</domain>

<decisions>
## Implementation Decisions

### Documentation Tooling
- **D-01:** MkDocs + Material for MkDocs as the static site generator. Configuration via `mkdocs.yml` at project root. `mkdocstrings` plugin for auto-generating API docs from Python docstrings.
- **D-02:** Docs source files live in `docs/` directory as Markdown. Structure: index (README content), quick start, API reference (auto-generated), examples index.

### API Documentation Depth
- **D-03:** Cover all public API — every class/function exported via `lightrag_langchain/__init__.py` and `lightrag_langchain/chain/__init__.py` (7 chain classes, 6 retriever classes, `create_llm()`, `create_embedding()`, `LightRAGReranker`, `extract_keywords`, token budget functions).
- **D-04:** Each public API entry includes a minimal usage example inline. Examples should be runnable (import + call, not pseudocode).

### Samples
- **D-05:** Create a complete `examples/` directory containing:
  - One Jupyter notebook (`walkthrough.ipynb`) demonstrating all 6 query modes with output
  - Individual Python scripts (`naive_query.py`, `local_query.py`, etc.) for quick copy-paste
  - `.env.example` template specific to the examples
  - A brief `examples/README.md` explaining how to set up and run

### Deployment
- **D-06:** Publish docs via GitHub Pages using GitHub Actions CI. Deploy on every push to `main` branch (docs-only workflow). Use `mkdocs gh-deploy` for automated deployment.

### Claude's Discretion
- **README structure:** Claude decides the README sections. Must include at minimum: project description, quick start (install + .env setup + 3-line example), feature overview (6 query modes), and links to full docs.
- **README language:** Bilingual — Chinese (primary target audience) with English technical terms.
- **Examples scope:** Cover at minimum naive, local, global, hybrid queries. Bypass is trivial (direct LLM) and can be noted rather than given its own script.
- **Docs navigation structure:** Claude decides the sidebar/nav layout in mkdocs.yml.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Foundation
- `.planning/PROJECT.md` — What this library is, core value, constraints, key decisions
- `.planning/ROADMAP.md` — Phase structure, dependencies, and Phase 7 definition
- `.planning/REQUIREMENTS.md` — All requirements (especially CHAIN-*, RETR-*, LLM-*)

### Source Code (for accurate API docs and examples)
- `src/lightrag_langchain/__init__.py` — All public exports (chain classes, retriever classes, factories)
- `src/lightrag_langchain/chain/base.py` — LightRAGBaseChain API surface
- `src/lightrag_langchain/chain/chains.py` — 6 chain subclass definitions
- `src/lightrag_langchain/retriever/retrievers.py` — 6 retriever subclass definitions
- `src/lightrag_langchain/config.py` — Settings and .env configuration model

### LangChain Ecosystem
- LangChain official docs: https://docs.langchain.com/ — reference for doc style conventions
- MkDocs Material docs: https://squidfunk.github.io/mkdocs-material/ — theme configuration reference
- mkdocstrings docs: https://mkdocstrings.github.io/ — API doc auto-generation configuration

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Lazy export pattern:** `__init__.py` uses `__getattr__` to defer expensive imports. Examples must show `from lightrag_langchain import NaiveChain` (lazy form), not direct module imports.
- **Settings singleton:** All examples MUST call `settings` from `lightrag_langchain.config` after `.env` is loaded. Initialization check prevents import without `.env`.
- **6 chain/retriever classes:** Each with `mode` attribute and `invoke()`/`ainvoke()`/`astream()` methods — consistent API surface to document.

### Established Patterns
- Pure Python docstrings (no reStructuredText legacy). Current code uses simple descriptive docstrings — mkdocstrings will extract and render them as-is.
- Project uses `pyproject.toml` — no `setup.py` or `setup.cfg`. MKDocs config will be in `mkdocs.yml`.

### Integration Points
- `.env.example` already exists — examples will reference it. No need to create a new config template.
- `tests/` directory has comprehensive mock-based tests — examples should use the same pattern for self-contained demos (inline mocks or instructions for real services).
- `uv.lock` and `pyproject.toml` — any new dependencies (mkdocs, mkdocs-material, mkdocstrings) must be added to the dev dependencies group.

</code_context>

<specifics>
## Specific Ideas

- User explicitly chose "全部 public + 使用示例" for API docs depth — every documented item needs a runnable code snippet
- User explicitly chose "完整 examples/ 目录" — not a single notebook or scattered scripts, but a structured directory
- GitHub Pages was the preferred deployment choice — no ReadTheDocs complexity needed

</specifics>

<deferred>
## Deferred Ideas

- **i18n docs:** Multi-language documentation (Chinese + English) — noted but out of scope; deliver Chinese-first with English technical terms per Claude's Discretion
- **Contributor guide:** CONTRIBUTING.md — separate phase (this phase is user-facing only)

</deferred>

---

*Phase: 07-samples-docs-readme-md*
*Context gathered: 2026-05-31*
