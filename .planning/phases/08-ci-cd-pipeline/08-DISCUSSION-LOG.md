# Phase 8: CI/CD Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 08-ci-cd-pipeline
**Areas discussed:** PyPI 认证方式, GitHub repo 设置, 版本号策略

---

## PyPI 认证方式

| Option | Description | Selected |
|--------|-------------|----------|
| API Token | PyPI API Token 存为 GitHub Secret PYPI_API_TOKEN，传入 pypa/gh-action-pypi-publish | ✓ |
| OIDC Trusted Publisher | PyPI 配置 Trusted Publisher，workflow 用 OIDC 自动获取 token | |

**User's choice:** API Token (推荐)
**Notes:** 用户选择标准 API Token 方式。GitHub Secret 名: `PYPI_API_TOKEN`。需用户自行在 PyPI 网页生成 token 并添加到 repo Settings → Secrets。

---

## GitHub repo 设置

| Option | Description | Selected |
|--------|-------------|----------|
| Public | 开源项目，任何人可查看 | ✓ |
| Private | 仅授权用户可访问 | |

**User's choice:** Public repo，个人账号，名称 `lightrag-langchain`
**Notes:** 用户自行创建 repo（GitHub Web UI 或 `gh repo create`）。创建后需配置 `PYPI_API_TOKEN` secret。

---

## 版本号策略

| Option | Description | Selected |
|--------|-------------|----------|
| 手动同步 | 每次 release 前手动更新 pyproject.toml version | |
| CI 从 tag 提取 | CI 从 git tag 提取版本号并注入 pyproject.toml | ✓ |
| hatch-vcs | hatchling 从 git tag 自动读取 | |

**User's choice:** CI 从 tag 提取并注入（如 `v1.0.0` → `1.0.0`）
**Notes:** 已有本地 tag `v1.0` 对应版本 `1.0.0`。构建前 CI 提取版本并注入 pyproject.toml。

---

## Claude's Discretion

- Workflow 文件名和结构
- `pypa/gh-action-pypi-publish` 具体版本
- Python 版本和构建工具配置

## Deferred Ideas

None
