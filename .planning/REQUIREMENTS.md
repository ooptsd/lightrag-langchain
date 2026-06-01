# Requirements: lightrag-langchain v2.0

**Defined:** 2026-06-01
**Core Value:** 用户可以通过 Langchain 标准 API，从 LightRAG 已构建的知识图谱数据库中执行六种查询模式的检索和问答，无需启动 LightRAG 服务。

## v2.0 Requirements

### CI — 持续集成与交付

- [ ] **CI-01**: 创建 GitHub repo `lightrag-langchain` 并推送代码
- [ ] **CI-02**: GitHub Actions workflow 在 tag push（`v*`）时自动构建 wheel + sdist 并发布到 PyPI
- [ ] **CI-03**: GitHub Pages 部署文档页面 — 保持现有 `deploy-mkdocs.yml` 从源码 `mkdocs build` 方式部署到 GitHub Pages

## Out of Scope

| Feature | Reason |
|---------|--------|
| PR test/lint CI gate | 本次只做 tag→build→publish + Pages deploy，不做 PR gate |
| TestPyPI 中转发布 | 直接发布到 PyPI，不做 TestPyPI staging |
| 多平台 matrix build | v2.0 只需 linux wheel + sdist |
| PyPI OIDC Trusted Publisher | 如 PyPI 支持则优先，否则用 API Token |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CI-01 | Phase 8 | Pending |
| CI-02 | Phase 8 | Pending |
| CI-03 | Phase 8 | Pending |

**Coverage:**
- v2.0 requirements: 3 total
- Mapped to phases: 3/3 (100%)
- Orphans: 0

---
*Requirements defined: 2026-06-01*
*Traceability updated: 2026-06-01 — Phase 8 mapped*
