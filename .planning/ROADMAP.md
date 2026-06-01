# Roadmap: lightrag-langchain

## Milestones

- ✅ **v1.0** — 初始发布：7 phases, 23 plans (shipped 2026-06-01)
- 🔵 **v2.0** — CI集成：GitHub Actions tag→build→PyPI publish (active)

## Phases

<details>
<summary>✅ v1.0 (Phases 1-7) — SHIPPED 2026-06-01</summary>

- [x] **Phase 1: Configuration** (2/2 plans) — completed 2026-05-29
- [x] **Phase 2: Data Layer** (4/4 plans) — completed 2026-05-30
- [x] **Phase 3: LLM Integration** (5/5 plans) — completed 2026-05-30
- [x] **Phase 4: Query Strategies** (3/3 plans) — completed 2026-05-30
- [x] **Phase 5: Retriever Interfaces** (3/3 plans) — completed 2026-05-30
- [x] **Phase 6: QA Chain** (3/3 plans) — completed 2026-05-31
- [x] **Phase 7: Samples & Docs + README.md** (3/3 plans) — completed 2026-05-31

</details>

<details open>
<summary>🔵 v2.0 (Phase 8)</summary>

- [ ] **Phase 8: CI/CD Pipeline** — GitHub repo + tag→PyPI publish + GitHub Pages docs

</details>

## Phase Details

### Phase 8: CI/CD Pipeline
**Goal**: The project is on GitHub with automated tag-based PyPI publishing and GitHub Pages documentation deployment
**Depends on**: Nothing (standalone CI infrastructure phase)
**Requirements**: CI-01, CI-02, CI-03
**Success Criteria** (what must be TRUE):
  1. The `lightrag-langchain` GitHub repository exists with full commit history, tags, and all v1.0 source code pushed
  2. Pushing a `v*` tag (e.g., `v2.0.0`) triggers a GitHub Actions workflow that builds wheel + sdist and publishes to PyPI without manual intervention
  3. The published package is installable via `pip install lightrag-langchain` and matches the tagged version with all imports working
  4. Pushing to the main branch automatically deploys the MkDocs documentation site to GitHub Pages at a publicly accessible URL
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Configuration | v1.0 | 2/2 | Complete | 2026-05-29 |
| 2. Data Layer | v1.0 | 4/4 | Complete | 2026-05-30 |
| 3. LLM Integration | v1.0 | 5/5 | Complete | 2026-05-30 |
| 4. Query Strategies | v1.0 | 3/3 | Complete | 2026-05-30 |
| 5. Retriever Interfaces | v1.0 | 3/3 | Complete | 2026-05-30 |
| 6. QA Chain | v1.0 | 3/3 | Complete | 2026-05-31 |
| 7. Samples & Docs + README | v1.0 | 3/3 | Complete | 2026-05-31 |
| 8. CI/CD Pipeline | v2.0 | 0/0 | Not started | - |
