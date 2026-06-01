# Phase 8: CI/CD Pipeline - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

## Phase Boundary

Phase 8 将 lightrag-langchain 项目发布到 GitHub，并建立自动化的 tag→build→PyPI publish pipeline 和 GitHub Pages 文档部署。

## Implementation Decisions

### PyPI 认证
- **D-01:** 使用 PyPI API Token 认证。Token 存为 GitHub Secret `PYPI_API_TOKEN`，workflow 通过 `${{ secrets.PYPI_API_TOKEN }}` 传入 `pypa/gh-action-pypi-publish@release/v1` 的 `password` 字段。需用户自行在 PyPI 网页生成 API Token 并添加到 GitHub repo Settings → Secrets。

### GitHub Repo
- **D-02:** Public repo，创建在用户个人账号下，名称 `lightrag-langchain`。由用户自行通过 GitHub Web UI 或 `gh repo create` 创建。需在 repo Settings 中添加 `PYPI_API_TOKEN` secret。

### 版本号策略
- **D-03:** CI 从 git tag 提取版本号（如 `v1.0.0` → `1.0.0`），在构建前注入 `pyproject.toml` 的 `version` 字段。本地已有的 `v1.0` tag 对应版本 `1.0.0`。

### Workflow 触发
- **D-04:** tag push（匹配 `v*` pattern）触发 PyPI publish workflow。push main 触发 GitHub Pages deploy（保持现有 `deploy-mkdocs.yml`）。
- **D-05:** GitHub Pages 保持现有 `deploy-mkdocs.yml` 方式 — push main 时从源码 `mkdocs gh-deploy --force` 部署。不修改此 workflow。

### Claude's Discretion
- Workflow 文件名和内部结构由实现者决定
- `pypa/gh-action-pypi-publish` 的具体版本和配置参数
- Python 版本和构建工具的具体配置

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase artifacts
- `.planning/ROADMAP.md` — Phase 8 scope, success criteria
- `.planning/REQUIREMENTS.md` — CI-01 (GitHub repo), CI-02 (tag→PyPI), CI-03 (Pages docs)

### Existing CI assets
- `.github/workflows/deploy-mkdocs.yml` — 现有 GitHub Pages deploy workflow（保持不动）
- `pyproject.toml` — hatchling build system config, project metadata, version field

### Standards
- No external specs — standard GitHub Actions + PyPI publish pattern

## Existing Code Insights

### Reusable Assets
- `pyproject.toml`: hatchling build backend, project metadata, dependencies 已就绪
- `.github/workflows/deploy-mkdocs.yml`: 已有 Pages deploy workflow, 展示项目 GitHub Actions 模式
- `site/`: MkDocs 预构建静态文件（workflow 从源码重新构建，不直接用此目录）

### Established Patterns
- Workflow 使用 `actions/checkout@v4` + `actions/setup-python@v5` + `actions/cache@v4` 标准组合

### Integration Points
- 新 `publish.yml` workflow 独立于现有 `deploy-mkdocs.yml`，互不影响
- `pyproject.toml` 的 `version` 字段由 CI 注入，不改变本地开发流程

## Specific Ideas

- 用户希望 tag `v1.0` 作为首次 PyPI 发布的触发 tag
- 构建产物: wheel (.whl) + sdist (.tar.gz)
- 发布目标: PyPI (非 TestPyPI)

## Deferred Ideas

None — discussion stayed within phase scope.

---
*Phase: 8-CI/CD Pipeline*
*Context gathered: 2026-06-01*
