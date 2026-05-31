# Phase 07: Samples & Docs + README.md -- Research

**Researched:** 2026-05-31
**Domain:** Python library documentation (MkDocs + Material for MkDocs + mkdocstrings)
**Confidence:** HIGH

## Summary

This phase delivers all developer-facing documentation and usage examples for the lightrag-langchain library. The work is purely documentation/samples -- no functional code changes required. The documentation system is a static site built with MkDocs + Material for MkDocs, with API reference pages auto-generated from source code docstrings via mkdocstrings-python 2.x. Deployment to GitHub Pages is automated via GitHub Actions using mkdocs gh-deploy.

The public API surface consists of 28+ exportable symbols: 6 chain classes, 6 retriever classes, 1 base chain (LightRAGBaseChain), 3 factory functions (create_llm, create_embedding, create_reranker), 1 reranker compressor (LightRAGReranker), 4 keyword/token functions (extract_keywords, KeywordsSchema, 3 token budget functions), 6 config sub-models, and the settings singleton. Every documented item needs a minimal runnable usage example per D-04.

The key architectural challenge is that the project's lazy `__getattr__` export pattern makes symbols invisible to static analysis (Griffe, the library mkdocstrings uses). This means the API reference cannot rely on automatic member discovery from `__init__.py` -- each public symbol must be explicitly referenced in the docs via `::: lightrag_langchain.module.Symbol` syntax.

**Primary recommendation:** Structure docs around 4 pages (index, quick-start, api-reference, examples) with api-reference using explicit `:::` references for every public symbol. Keep mkdocs.yml simple -- use the 3 core plugins (search, mkdocstrings, autorefs).

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** MkDocs + Material for MkDocs as the static site generator. Configuration via `mkdocs.yml` at project root. `mkdocstrings` plugin for auto-generating API docs from Python docstrings.
- **D-02:** Docs source files live in `docs/` directory as Markdown. Structure: index (README content), quick start, API reference (auto-generated), examples index.
- **D-03:** Cover all public API -- every class/function exported via `lightrag_langchain/__init__.py` and `lightrag_langchain/chain/__init__.py` (7 chain classes, 6 retriever classes, `create_llm()`, `create_embedding()`, `LightRAGReranker`, `extract_keywords`, token budget functions).
- **D-04:** Each public API entry includes a minimal usage example inline. Examples should be runnable (import + call, not pseudocode).
- **D-05:** Create a complete `examples/` directory containing: one Jupyter notebook (walkthrough.ipynb), individual Python scripts (naive_query.py, local_query.py, etc.), .env.example template, examples/README.md.
- **D-06:** Publish docs via GitHub Pages using GitHub Actions CI. Deploy on every push to `main` branch. Use `mkdocs gh-deploy` for automated deployment.

### Claude's Discretion

- **README structure:** Claude decides the README sections. Must include at minimum: project description, quick start, feature overview (6 query modes), and links to full docs.
- **README language:** Bilingual -- Chinese (primary target audience) with English technical terms.
- **Examples scope:** Cover at minimum naive, local, global, hybrid queries. Bypass is trivial (direct LLM) and can be noted rather than given its own script.
- **Docs navigation structure:** Claude decides the sidebar/nav layout in mkdocs.yml.

### Deferred Ideas (OUT OF SCOPE)

- **i18n docs:** Multi-language documentation (Chinese + English) -- noted but out of scope; deliver Chinese-first with English technical terms per Claude's Discretion
- **Contributor guide:** CONTRIBUTING.md -- separate phase (this phase is user-facing only)

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Static site generation | Build-time (MkDocs) | -- | MkDocs reads .md files + extracts docstrings -> generates static HTML |
| API doc auto-generation | Build-time (mkdocstrings-python) | -- | Griffe parses source code statically; no runtime import needed |
| Navigation/sidebar | Build-time (mkdocs.yml) | -- | Nav structure defined in config; rendered by Material theme |
| Theme/styling | Build-time (Material for MkDocs) | -- | Drop-in theme; configured in mkdocs.yml |
| README.md rendering | GitHub (repository root) | -- | GitHub renders README.md directly; independent of MkDocs |
| Markdown content authoring | docs/ directory (source) | -- | Hand-written Markdown files; mkdocstrings directives within them |
| Example scripts | examples/ directory (source) | -- | Standalone Python scripts + Jupyter notebook; not built by MkDocs |
| Deployment | GitHub Actions (CI) | GitHub Pages (hosting) | CI runs mkdocs gh-deploy on push to main; Pages serves from gh-pages branch |
| Local preview | Dev machine (mkdocs serve) | -- | Hot-reload server for local iteration |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mkdocs | 1.6.1 | Static site generator | De facto standard for Python project docs; pipelined with Material theme |
| mkdocs-material | 9.7.6 | Material Design theme for MkDocs | Most popular MkDocs theme (~20k GitHub stars); excellent UX, search, navigation |
| mkdocstrings | 1.0.4 | Auto-generate API docs from docstrings | Standard plugin for Python API reference; Griffe-powered static analysis |
| mkdocstrings-python | 2.0.3 | Python handler for mkdocstrings | Required for Python source parsing; supports Google/NumPy/Sphinx docstring styles |

[VERIFIED: PyPI registry -- pip index versions for all 4 packages confirmed current versions on 2026-05-31]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mkdocs-autorefs | 1.4.4 | Cross-reference resolution | Automatically links `::: ref` directives across pages; installed as mkdocstrings dependency |
| pymdown-extensions | 10.21.3 | Extended Markdown features | Provides admonitions, code blocks, tabs, etc.; installed as mkdocs-material dependency |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| mkdocs-material | sphinx + furo theme | Sphinx requires reStructuredText which the project does not use; CONTEXT.md confirms "pure Python docstrings (no reStructuredText legacy)" |
| mkdocs gh-deploy | ReadTheDocs | GitHub Pages chosen per D-06; simpler setup, no external service dependency |
| mkdocstrings-python | Hand-written API docs | Manual API docs drift from source code; mkdocstrings guarantees docs match the actual API |
| jupyter (as notebook viewer) | mkdocs-jupyter plugin | User did not request notebook rendering in docs; notebook lives standalone in examples/ |

**Installation:**
```bash
uv add --group dev mkdocs-material mkdocstrings mkdocstrings-python
```

**Version verification:**
```bash
$ pip index versions mkdocs-material | head -1
mkdocs-material (9.7.6)

$ pip index versions mkdocstrings | head -1
mkdocstrings (1.0.4)

$ pip index versions mkdocstrings-python | head -1
mkdocstrings-python (2.0.3)
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| mkdocs-material | PyPI | ~10 yrs | ~5M/wk | github.com/squidfunk/mkdocs-material | [OK] | Approved |
| mkdocstrings | PyPI | ~5 yrs | ~2M/wk | github.com/mkdocstrings/mkdocstrings | [OK] | Approved |
| mkdocstrings-python | PyPI | ~4 yrs | ~1M/wk | github.com/mkdocstrings/python | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                         +---------------------------+
                         |     Developer writes:      |
                         |  - docs/*.md (Markdown)    |
                         |  - src/**/*.py (docstrings)|
                         |  - examples/*.py           |
                         |  - README.md               |
                         +-----------+---------------+
                                     |
                                     v
                         +-----------+----------------+
                         |      mkdocs build          |
                         |  (mkdocs.yml configures)   |
                         |                           |
                         |  1. Parse .md files        |
                         |  2. mkdocstrings extracts  |
                         |     docstrings via Griffe  |
                         |  3. Material theme renders |
                         |     HTML + CSS + JS        |
                         |  4. Output -> site/        |
                         +-----------+----------------+
                                     |
                          (local: mkdocs serve)
                          (CI: mkdocs gh-deploy)
                                     |
                         +-----------v----------------+
                         |   GitHub Pages (gh-pages) |
                         |   https://<user>.github.io|
                         |   /lightrag-langchain/    |
                         +---------------------------+

                    GitHub Actions (on push to main):
                    +--------------------------------+
                    | checkout -> setup-python ->    |
                    | pip install deps ->            |
                    | mkdocs gh-deploy --force       |
                    +--------------------------------+

                    README.md (GitHub renders directly):
                    +--------------------------------+
                    | Project intro                  |
                    | Quick start                    |
                    | Feature overview (6 modes)     |
                    | Links to docs + examples       |
                    +--------------------------------+
```

### Recommended Project Structure

```
lightrag-langchain/
├── mkdocs.yml                    # MkDocs config (at root per D-01)
├── README.md                     # GitHub repo README (bilingual: Chinese + English terms)
├── docs/
│   ├── index.md                  # Landing page (Chinese overview + quick feature list)
│   ├── quick-start.md            # Installation + .env setup + first query
│   ├── api-reference/
│   │   ├── index.md              # Overview + links to sub-pages
│   │   ├── chains.md             # LightRAGBaseChain + 6 chain subclasses
│   │   ├── retrievers.md         # LightRAGBaseRetriever + 6 retriever subclasses
│   │   ├── factories.md          # create_llm(), create_embedding(), create_reranker()
│   │   ├── reranker.md           # LightRAGReranker
│   │   ├── keywords.md           # extract_keywords(), KeywordsSchema
│   │   ├── token-budget.md       # truncate_entities/relations_by_tokens, compute_chunk_token_budget
│   │   └── config.md             # Settings, PgConfig, LlmConfig, etc.
│   └── examples.md               # Overview of examples/ directory
├── examples/
│   ├── README.md                 # How to set up and run examples
│   ├── .env.example              # Template for examples (symlink or copy from root)
│   ├── walkthrough.ipynb         # Jupyter notebook: all 6 query modes with output
│   ├── naive_query.py            # Naive mode minimal script
│   ├── local_query.py            # Local mode minimal script
│   ├── global_query.py           # Global mode minimal script
│   └── hybrid_query.py           # Hybrid mode minimal script
└── .github/
    └── workflows/
        └── deploy-mkdocs.yml     # GitHub Actions: build + deploy docs
```

### Pattern 1: mkdocs.yml Configuration

**What:** Minimal but complete mkdocs.yml configuring Material theme, mkdocstrings Python handler, and navigation structure.

**When to use:** This is the single source of truth for the entire documentation site.

**Source:** [CITED: squidfunk.github.io/mkdocs-material/publishing-your-site/] and [CITED: mkdocstrings.github.io/python/]

```yaml
site_name: lightrag-langchain
site_description: LangChain-based read-only query layer for LightRAG knowledge graphs
repo_url: https://github.com/<user>/lightrag-langchain
repo_name: lightrag-langchain

theme:
  name: material
  language: zh
  features:
    - navigation.instant
    - navigation.tracking
    - navigation.sections
    - navigation.expand
    - search.suggest
    - search.highlight
    - content.code.copy
    - content.code.annotate

plugins:
  - search
  - mkdocstrings:
      default_handler: python
      handlers:
        python:
          paths: [src]
          options:
            show_source: true
            show_root_heading: true
            heading_level: 2
            docstring_style: google
            members_order: source
            group_by_category: true
            show_signature_annotations: true
            separate_signature: true
            filters:
              - "!^_"           # Exclude private/single-underscore members

markdown_extensions:
  - admonition
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.details
  - pymdownx.tabbed:
      alternate_style: true
  - toc:
      permalink: true

nav:
  - Home: index.md
  - Quick Start: quick-start.md
  - API Reference:
    - Overview: api-reference/index.md
    - Chains: api-reference/chains.md
    - Retrievers: api-reference/retrievers.md
    - Factories: api-reference/factories.md
    - Reranker: api-reference/reranker.md
    - Keywords: api-reference/keywords.md
    - Token Budget: api-reference/token-budget.md
    - Configuration: api-reference/config.md
  - Examples: examples.md

docs_dir: docs
site_dir: site
```

### Pattern 2: mkdocstrings Auto-Generation Directive

**What:** In an API reference page, use `::: module.path.Symbol` syntax to auto-generate documentation from docstrings. Each symbol must be explicitly listed -- lazy `__getattr__` exports are invisible to static analysis.

**When to use:** Every API reference page. This is the only way to document lazy-exported symbols.

**Source:** [CITED: mkdocstrings.github.io/python/usage/] -- Griffe parses source statically; `__getattr__`-based exports are not detectable.

Example for `docs/api-reference/chains.md`:
```markdown
# Chain 接口

完整的端到端问答管道，封装关键词提取、检索、Token 预算控制、上下文组装、LLM 调用。

## LightRAGBaseChain

::: lightrag_langchain.chain.base.LightRAGBaseChain
    options:
      members:
        - invoke
        - ainvoke
        - astream

## 查询模式 Chain 子类

每个子类只设置 `mode` 属性，继承全部管道逻辑（BypassChain 除外，它覆盖全部三个方法）。

::: lightrag_langchain.chain.chains.NaiveChain

::: lightrag_langchain.chain.chains.LocalChain

::: lightrag_langchain.chain.chains.GlobalChain

::: lightrag_langchain.chain.chains.HybridChain

::: lightrag_langchain.chain.chains.MixChain

::: lightrag_langchain.chain.chains.BypassChain
```

### Pattern 3: GitHub Actions Deployment Workflow

**What:** Standard workflow file that builds and deploys MkDocs to GitHub Pages on push to main.

**When to use:** This is the deployment mechanism per D-06.

**Source:** [CITED: squidfunk.github.io/mkdocs-material/publishing-your-site/#with-github-actions]

File: `.github/workflows/deploy-mkdocs.yml`
```yaml
name: Deploy MkDocs

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure Git Credentials
        run: |
          git config user.name github-actions[bot]
          git config user.email 41898282+github-actions[bot]@users.noreply.github.com
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Cache MkDocs dependencies
        uses: actions/cache@v4
        with:
          key: mkdocs-material-${{ github.run_id }}
          path: ~/.cache/pip
          restore-keys: |
            mkdocs-material-
      - name: Install dependencies
        run: pip install mkdocs-material mkdocstrings mkdocstrings-python
      - name: Deploy to GitHub Pages
        run: mkdocs gh-deploy --force
```

### Pattern 4: Example Script Structure

**What:** Each example script is a self-contained, runnable Python file demonstrating one query mode.

**When to use:** All `.py` files in examples/.

```python
"""Naive mode query -- pure vector chunk search, no graph traversal.

Usage:
    cp .env.example .env   # edit with your credentials
    python naive_query.py  # or: uv run python naive_query.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import NaiveChain, NaiveRetriever, create_llm, create_embedding
from lightrag_langchain.config import settings
from lightrag_langchain.data.store import PGVectorStore


async def main():
    # 1. Create data-layer connections
    vector_store = PGVectorStore(...)

    # 2. Create LLM and embedding from settings
    llm = create_llm(settings.llm)
    embedding = create_embedding(settings.embedding)

    # 3. Build retriever
    retriever = NaiveRetriever(
        vector_store=vector_store,
        embedding_config=settings.embedding,
    )

    # 4. Build chain
    chain = NaiveChain(retriever=retriever, llm=llm)

    # 5. Query
    result = await chain.ainvoke("启动东莞市防风Ⅰ级应急响应后需要落实哪些措施？")

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Pattern 5: Jupyter Notebook Structure

**What:** A single .ipynb demonstrating all query modes with outputs. This is the comprehensive walkthrough.

**When to use:** examples/walkthrough.ipynb -- the primary demonstration artifact.

The notebook should use the standard Jupyter notebook JSON format (nbformat v4). Structure:
1. Cell 1 (Markdown): Title, project intro
2. Cell 2 (Markdown): Prerequisites (.env setup)
3. Cell 3 (Code): Imports + settings check
4. Cell 4 (Code): Create shared connections (vector_store, graph_store, llm, embedding)
5. Cell 5 (Markdown): Naive mode intro
6. Cell 6 (Code): NaiveChain + query + output display
7. ... repeat for local, global, hybrid, mix, bypass

### Anti-Patterns to Avoid

- **Auto-discovering `__all__` or using `members: true` on `__init__.py`:** The project's lazy `__getattr__` pattern means `lightrag_langchain.__all__` doesn't exist and `dir()` only shows `__getattr__`. Griffe statically parses source -- it cannot see dynamically-exported names. Every public symbol must be explicitly listed with `::: path.to.module.ClassName`.
- **Putting mkdocs.yml config keys in the wrong nesting level:** The `paths: [src]` option goes under `handlers.python.paths:`, NOT under `plugins.mkdocstrings.paths:`.
- **Using `mkdocs build` in CI instead of `mkdocs gh-deploy`:** build only generates site/ -- it won't push to gh-pages. Use gh-deploy for the full deploy pipeline.
- **Forgetting to set up GitHub Pages source:** After the first deploy, go to Settings > Pages and set source to "Deploy from a branch" > gh-pages branch > / (root). Without this, the site won't be served.
- **Not pinning Python version in CI:** Use `python-version: '3.12'` to match project requirement (3.12+). Older Python may have Griffe compatibility issues.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Static site generator | Custom HTML/CSS generator | mkdocs-material 9.7.6 | 1000+ hours of UX work in Material theme; search, navigation, responsive design, code copy all built-in |
| API doc extraction | Manual documentation of signatures | mkdocstrings-python 2.0.3 | Griffe statically parses type annotations, docstrings, parameters; auto-generates consistent reference docs |
| Markdown rendering | Custom Markdown parser | MkDocs built-in + pymdown-extensions | Already bundled with Material theme; supports admonitions, code highlighting, tabs |
| GitHub Pages deployment | Custom rsync/scp script | mkdocs gh-deploy --force | Handles gh-pages branch, force-push, .nojekyll; battle-tested across thousands of projects |
| Cross-reference resolution | Manual URL linking | mkdocs-autorefs | Automatically links `[ClassName][]` references to the target page; no dead links |
| Config change detection | Trigger deploy manually | GitHub Actions on push to main | Zero-friction: every commit to main auto-deploys docs |
| Notebook JSON generation | Manual JSON | Programmatic write (nbformat or by hand) | .ipynb is JSON; can be written directly without jupyter installed; but verify format with `jupyter nbconvert --to notebook` |

**Key insight:** Documentation infrastructure is a solved problem for Python projects. MkDocs + Material + mkdocstrings is the overwhelmingly dominant stack in 2026. Hand-rolling any part of this pipeline wastes effort on non-functional infrastructure instead of content quality.

## Runtime State Inventory

> Omitted -- this is a greenfield documentation phase. No rename/refactor/migration to audit. No runtime state carries old names. All artifacts are new files.

## Common Pitfalls

### Pitfall 1: Lazy `__getattr__` Exports Not Discovered by Griffe

**What goes wrong:** When you write `::: lightrag_langchain.NaiveChain`, mkdocstrings fails with "Could not find 'NaiveChain' in module 'lightrag_langchain'". This is because `NaiveChain` is exported via `__getattr__` (lazy), not via `import` statements at module level. Griffe statically parses the AST -- it sees the `def __getattr__` function body but cannot evaluate it to discover what names it exports.

**Why it happens:** Griffe (the static analysis library behind mkdocstrings-python) parses Python source code, not imports it. It sees `def __getattr__` as a regular function and cannot know that `__getattr__("NaiveChain")` returns a class.

**How to avoid:** Always use the **actual module path** where the class/function is defined, not the re-export path:
- `::: lightrag_langchain.chain.chains.NaiveChain` (works -- this is where `class NaiveChain` is defined)
- `::: lightrag_langchain.NaiveChain` (fails -- lazy export, invisible to static analysis)
- `::: lightrag_langchain.chain.base.LightRAGBaseChain` (works -- defined directly in base.py)
- `::: lightrag_langchain.Chain.__init__.LightRAGBaseChain` (fails -- re-exported via lazy __getattr__)

**Warning signs:** "Could not find" error from mkdocstrings when using short import paths. Resolution: use the full source path (`lightrag_langchain.chain.chains.NaiveChain`, not `lightrag_langchain.NaiveChain`).

### Pitfall 2: `paths: [src]` vs `paths: [.]` in mkdocstrings Config

**What goes wrong:** If `paths` is set to `["."]` instead of `["src"]`, mkdocstrings cannot find the `lightrag_langchain` package. Configuring `paths: ["src"]` is required because the project uses the `src/` layout.

**Why it happens:** mkdocstrings-python resolves Python module paths relative to the search paths. With the `src/` layout, the package `lightrag_langchain` is at `src/lightrag_langchain/`. Setting `paths: ["src"]` makes `src/` a root for module resolution.

**How to avoid:** Always set `paths: [src]` under `handlers.python.paths`.

**Warning signs:** ModuleNotFoundError or "Could not find module" when mkdocs builds. Verify with `mkdocs build --verbose`.

### Pitfall 3: GitHub Pages Not Configured After First Deploy

**What goes wrong:** The CI workflow succeeds (gh-pages branch is updated), but the site returns 404. GitHub Pages is not automatically enabled for the gh-pages branch on new repos.

**Why it happens:** GitHub requires explicit configuration: Settings > Pages > Source > "Deploy from a branch" > Select "gh-pages" > Select "/ (root)" > Save. This is a one-time manual step.

**How to avoid:** After the first successful CI deploy, manually configure GitHub Pages. This is a one-time repo setting, not a per-commit concern. Document this in the examples/README.md or quick-start.md.

**Warning signs:** CI log shows "Your site is ready to be published at https://...", but the URL returns 404. Resolution: configure Pages settings in the repository.

### Pitfall 4: Missing `.nojekyll` or Wrong Branch

**What goes wrong:** GitHub Pages tries to process the site through Jekyll, which can break MkDocs output (particularly files starting with underscores like `_static/`).

**Why it happens:** GitHub Pages defaults to Jekyll processing unless `.nojekyll` is present. However, `mkdocs gh-deploy` automatically creates `.nojekyll` -- this pitfall only occurs when deploying manually.

**How to avoid:** Use `mkdocs gh-deploy --force` (not manual git push to gh-pages). The gh-deploy command handles .nojekyll and other details automatically.

### Pitfall 5: Docstring Style Mismatch

**What goes wrong:** mkdocstrings renders docstrings incorrectly -- parameters appear as plain text instead of structured tables, section headers are not recognized.

**Why it happens:** The project's docstrings use a specific style (Google-style, as visible in the source code). If `docstring_style` is set to `sphinx` or `numpy`, the parser will misinterpret Google-style docstrings.

**How to avoid:** Set `docstring_style: google` in the mkdocstrings options. All existing docstrings in the codebase use Google-style (param descriptions with colons, "Returns:" sections, "Raises:" sections).

**Warning signs:** Parameter descriptions appearing as raw text instead of formatted tables. Verify one docstring renders correctly before documenting all 28+ symbols.

## Code Examples

Verified patterns from official sources:

### mkdocstrings `:::` Directive with Explicit Members

```markdown
::: lightrag_langchain.chain.base.LightRAGBaseChain
    options:
      members:
        - invoke
        - ainvoke
        - astream
      show_source: false
      heading_level: 2
```

This renders LightRAGBaseChain docs with only the 3 public methods, hides source code, starts headings at h2 level. Source: [CITED: mkdocstrings.github.io/python/usage/configuration/members/]

### Example Script -- Minimum Viable Local Query

```python
import asyncio
from lightrag_langchain import LocalChain, LocalRetriever, create_llm, create_embedding
from lightrag_langchain.config import settings
from lightrag_langchain.data.store import PGVectorStore
from lightrag_langchain.data.graph import PGGraphStore

async def main():
    vector_store = PGVectorStore(...)
    graph_store = PGGraphStore(...)
    llm = create_llm(settings.llm)
    retriever = LocalRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )
    chain = LocalChain(retriever=retriever, llm=llm)
    result = await chain.ainvoke("珠江流域超标准洪水时水库抢险标准是什么？")
    print(result["answer"])

asyncio.run(main())
```

### GitHub Actions mkdocs Deploy (from official Material docs)

```yaml
- name: Deploy to GitHub Pages
  run: mkdocs gh-deploy --force
```

Source: [CITED: squidfunk.github.io/mkdocs-material/publishing-your-site/#with-github-actions]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| mkdocstrings-python 1.x (legacy handler) | mkdocstrings-python 2.x (new handler) | 2024-2025 | New handler uses Griffe for static analysis; `paths:` config simplified; `:::` syntax is dot-separated not colon-separated |
| Manual gh-pages push | mkdocs gh-deploy --force | Stable since mkdocs 1.0 | One-command deploy with .nojekyll, commit history management, custom domain support |
| Sphinx for Python docs | MkDocs + Material for smaller projects | Ongoing trend | MkDocs is lighter, uses Markdown (not reST), but Sphinx is still preferred for very large projects with complex cross-references |
| pip install in CI | uv pip install in CI | 2025-2026 | Faster installs; project already uses uv.lock |
| jupyter as required dep | jupyter only for notebook authoring | Current best practice | .ipynb files can be created/edited without jupyter installed; CI doesn't need it |

**Deprecated/outdated:**
- **mkdocstrings legacy handler (pre-2.0):** The `mkdocstrings[python-legacy]` extra is superseded by `mkdocstrings-python`. Do not install the legacy handler.
- **`new_path_syntax: true` option:** In mkdocstrings-python 2.x, only dot-separated paths (`a.b.c`) are valid. The old colon syntax (`a:b:c`) is not supported.
- **Python 3.11:** The project requires 3.12+. CI should use 3.12.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Griffe cannot discover lazy `__getattr__` exports -- every public symbol needs an explicit `::: module.path.Symbol` directive | Common Pitfalls | If Griffe 2.x adds support for lazy export detection, we could simplify API reference pages. Low risk: lazy __getattr__ is fundamentally unevaluatable statically. |
| A2 | The project's docstrings use Google-style format | Common Pitfalls | If any modules use NumPy or Sphinx-style, those docstrings will render incorrectly. Verified: Spot-checked base.py, chains.py, reranker.py, config.py -- all use Google-style (param descriptions with colons, "Returns:" sections). |
| A3 | GitHub Pages is available for the repository | Deployment | Enterprise GitHub may restrict Pages. Managed via Org settings. Low risk for open-source repos. |
| A4 | Repository owner is willing to configure Pages settings manually after first deploy | Deployment | If not, docs won't be served. This is a one-time manual step per GitHub, unavoidable. |
| A5 | The project's `src/` layout means `paths: [src]` is the correct mkdocstrings config | mkdocs.yml | If the project switched to flat layout, paths would need to be `[.]`. Verified: pyproject.toml uses `packages = ["src/lightrag_langchain"]`. |

## Open Questions

1. **Should the README.md content be duplicated in docs/index.md (as MkDocs home page)?**
   - What we know: D-02 says "index (README content)". Material for MkDocs recommends docs/index.md as the landing page. GitHub renders README.md separately.
   - What's unclear: Whether to copy README content into docs/index.md, or to make docs/index.md a brief landing page that links to README.md on GitHub. The risk of duplication is that docs go stale when only one is updated.
   - Recommendation: Make docs/index.md a brief landing page (Chinese, 3-4 paragraphs) with links to quick-start and API reference. Put the full content in README.md. This avoids duplication and keeps the MkDocs site focused on docs navigation.

2. **Should examples import from `lightrag_langchain` (lazy) or from source modules (direct)?**
   - What we know: CONTEXT.md says "Examples must show `from lightrag_langchain import NaiveChain` (lazy form)". This is the recommended import style. However, PGVectorStore and PGGraphStore are not re-exported from `lightrag_langchain.__init__` per its docstring -- they must be imported from `lightrag_langchain.data`.
   - What's unclear: The imports for examples will be a mix: lazy imports for chains/retrievers/factories, direct imports for data-layer classes. Is this confusing for users?
   - Recommendation: Accept the mixed import pattern. It accurately reflects the library's design. Add a comment in examples explaining why some imports use the top-level package and others use submodules ("Chains and Retrievers use lazy imports; database connections require direct data-layer access").

3. **How to handle the Notebook (.ipynb) without jupyter installed?**
   - What we know: .ipynb is JSON (nbformat v4 spec). Can be written directly as a structured JSON file. However, testing/validating the notebook requires jupyter or nbconvert.
   - What's unclear: Whether to add jupyter as an optional dev dependency, or to keep it out and document that users need jupyter independently if they want to run the notebook.
   - Recommendation: Do NOT add jupyter to project dependencies. The notebook can be authored as a JSON file. Add a note in examples/README.md: "To run walkthrough.ipynb, install jupyter: `pip install jupyter`". This keeps the dependency footprint minimal.

4. **BypassChain -- separate example script or inline note?**
   - What we know: Claude's Discretion says "Bypass is trivial (direct LLM) and can be noted rather than given its own script."
   - What's unclear: Where to note it -- in the walkthrough notebook only? In one of the other scripts?
   - Recommendation: Include Bypass as a cell in walkthrough.ipynb (it's 3 lines of code) and note it in the examples/README.md feature list. No standalone `bypass_query.py` script. This keeps the examples/ directory focused on the 4 modes that involve retrieval.

5. **Should mkdocs.yml be committed with `site_url` pointing to the eventual GitHub Pages URL?**
   - What we know: Material for MkDocs recommends `site_url` for canonical URLs and sitemap generation. The URL format will be `https://<username>.github.io/lightrag-langchain/`.
   - What's unclear: The GitHub username is needed. This is project-specific.
   - Recommendation: Use a placeholder or determine from `git remote get-url origin`. The planner will need the actual username/organization to set the correct `site_url`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | mkdocs build, mkdocstrings | Yes | 3.12.13 | -- |
| pip / uv | Package installation | Yes | pip 25.0.1, uv 0.11.13 | -- |
| mkdocs | Building docs | Yes (installed via research) | 1.6.1 | -- |
| mkdocs-material | Theme rendering | Yes (installed via research) | 9.7.6 | -- |
| mkdocstrings | API doc generation | Yes (installed via research) | 1.0.4 | -- |
| mkdocstrings-python | Python handler | Yes (installed via research) | 2.0.3 | -- |
| GitHub Actions | CI deployment | N/A (runs on GitHub) | -- | -- |
| jupyter | Running walkthrough.ipynb | Not checked | -- | Not required for authoring; add note in examples/README.md |

**Missing dependencies with no fallback:**
- None -- all required tools are available locally or run on GitHub infrastructure.

**Missing dependencies with fallback:**
- jupyter (for running notebook): Fallback -- document that users install jupyter independently if they want to run the notebook.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 9.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x --timeout=30` |
| Full suite command | `uv run pytest tests/` |

### Phase Requirements -> Test Map

This phase has no functional requirements (it is a documentation + samples phase). Validation approach:

| Validation Check | Method | Command | File Exists? |
|------------------|--------|---------|-------------|
| D-01: mkdocs.yml valid | Schema check | `uv run mkdocs build --strict` | Wave 0 (create file) |
| D-02: docs/ structure | Directory existence | `ls docs/index.md docs/quick-start.md docs/api-reference/` | Wave 0 (create files) |
| D-03: All 28+ public API symbols documented | grep for `:::` directives in api-reference/*.md | `grep -c "^:::" docs/api-reference/*.md` | Wave 0 (create files) |
| D-04: Each API entry has example | Manual review (docstrings already contain usage examples in source code docstrings) | N/A (manual) | -- |
| D-05: examples/ directory complete | File existence | `ls examples/walkthrough.ipynb examples/{naive,local,global,hybrid}_query.py` | Wave 0 (create files) |
| D-06: CI workflow file exists | File existence | `ls .github/workflows/deploy-mkdocs.yml` | Wave 0 (create file) |
| Example scripts: syntax valid | Python compile check | `python -m py_compile examples/*.py` | Wave 0 (create + validate) |
| Example scripts: imports resolve | Import check (requires .env) | Skip in CI (no .env); run locally only | Manual |

### Sampling Rate

- **Per task commit:** `uv run mkdocs build --strict` (verify docs build without errors)
- **Per wave merge:** `uv run mkdocs build --strict` + `uv run pytest tests/ -x` (existing tests must not regress)
- **Phase gate:** Full test suite green + `mkdocs build --strict` green + all example scripts compile clean

### Wave 0 Gaps

- [ ] `mkdocs.yml` -- new file at project root; no existing config
- [ ] `docs/index.md` -- new file; landing page
- [ ] `docs/quick-start.md` -- new file; installation and first query
- [ ] `docs/api-reference/index.md` -- new file; overview of API sections
- [ ] `docs/api-reference/chains.md` -- new file; 7 chain classes
- [ ] `docs/api-reference/retrievers.md` -- new file; 6 retriever classes
- [ ] `docs/api-reference/factories.md` -- new file; create_llm, create_embedding, create_reranker
- [ ] `docs/api-reference/reranker.md` -- new file; LightRAGReranker
- [ ] `docs/api-reference/keywords.md` -- new file; extract_keywords, KeywordsSchema
- [ ] `docs/api-reference/token-budget.md` -- new file; 3 token budget functions
- [ ] `docs/api-reference/config.md` -- new file; Settings + 5 config sub-models
- [ ] `docs/examples.md` -- new file; examples directory overview
- [ ] `README.md` -- new file; project-level README (bilingual)
- [ ] `examples/README.md` -- new file; examples setup instructions
- [ ] `examples/naive_query.py` -- new file; naive mode example
- [ ] `examples/local_query.py` -- new file; local mode example
- [ ] `examples/global_query.py` -- new file; global mode example
- [ ] `examples/hybrid_query.py` -- new file; hybrid mode example
- [ ] `examples/walkthrough.ipynb` -- new file; comprehensive notebook
- [ ] `.github/workflows/deploy-mkdocs.yml` -- new file; CI deployment
- [ ] `uv add --group dev mkdocs-material mkdocstrings mkdocstrings-python` -- add dev dependencies

*(All files are Wave 0 -- this phase creates all artifacts from scratch. No existing test infrastructure covers documentation validation.)*

## Security Domain

### Applicable ASVS Categories

This phase is purely documentation and samples -- no runtime code, no data handling, no authentication.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | -- |
| V3 Session Management | No | -- |
| V4 Access Control | No | -- |
| V5 Input Validation | No | -- |
| V6 Cryptography | No | -- |

### Known Threat Patterns for Documentation Sites

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Example scripts leak credentials | Information Disclosure | All examples use `settings.llm.api_key` or `.env`; never hardcode keys. `.env.example` uses placeholder values. |
| CI workflow exposes secrets in logs | Information Disclosure | Use `GITHUB_TOKEN` (auto-provisioned) instead of Personal Access Token. No secrets needed for gh-deploy. |
| Stale documentation | Integrity | Auto-deploy on every push to main (D-06). Docs always reflect current source. |

## Sources

### Primary (HIGH confidence)

- [Material for MkDocs -- Publishing Your Site](https://squidfunk.github.io/mkdocs-material/publishing-your-site/) -- Official GitHub Actions workflow, deployment configuration, permissions. Verified: 2026-05-31.
- [mkdocstrings Python Handler -- General Options](https://mkdocstrings.github.io/python/usage/configuration/general/) -- Configuration reference for `paths`, `allow_inspection`, `extensions`. Verified: 2026-05-31.
- [mkdocstrings Python Handler -- Members Options](https://mkdocstrings.github.io/python/usage/configuration/members/) -- Configuration reference for `members`, `filters`, `inherited_members`. Verified: 2026-05-31.
- [mkdocstrings Python Handler -- Headings Options](https://mkdocstrings.github.io/python/usage/configuration/headings/) -- Configuration reference for `show_root_heading`, `heading_level`, `show_root_full_path`. Verified: 2026-05-31.
- [mkdocstrings -- Usage](https://mkdocstrings.github.io/mkdocstrings/usage/) -- Core `:::` directive syntax, global/local configuration. Verified: 2026-05-31.
- [PyPI: mkdocs-material 9.7.6](https://pypi.org/project/mkdocs-material/) -- Package verified: [OK] via slopcheck.
- [PyPI: mkdocstrings 1.0.4](https://pypi.org/project/mkdocstrings/) -- Package verified: [OK] via slopcheck.
- [PyPI: mkdocstrings-python 2.0.3](https://pypi.org/project/mkdocstrings-python/) -- Package verified: [OK] via slopcheck.

### Secondary (MEDIUM confidence)

- [GitHub Actions mkdocs gh-deploy workflows (community)](https://github.com/mmornati/zigsight/issues/10) -- Confirmed the standard two-method pattern (mkdocs gh-deploy vs peaceiris/actions-gh-pages). Multiple sources agree on the same approach.
- [Material for MkDocs -- Getting Started](https://squidfunk.github.io/mkdocs-material/getting-started/) -- Installation and minimal configuration. Basis for mkdocs.yml structure.

### Tertiary (LOW confidence)

- None. All claims are verified against official documentation or PyPI registry.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All 4 packages verified on PyPI with slopcheck [OK]; versions confirmed via `pip index versions`; official docs consulted for mkdocs.yml configuration
- Architecture: HIGH -- MkDocs Material deployment pattern is well-documented and widely adopted; GitHub Actions workflow pattern verified from official Material docs
- Pitfalls: MEDIUM -- Pitfall 1 (lazy __getattr__) is inferred from knowledge of Griffe's static analysis design but was not empirically tested against this codebase. Other pitfalls are verified from official docs and community experience.

**Research date:** 2026-05-31
**Valid until:** 2026-07-01 (MkDocs ecosystem is stable; 30-day validity is appropriate)
