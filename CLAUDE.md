<!-- GSD:project-start source:PROJECT.md -->
## Project

**lightrag-langchain**

基于 Langchain 框架的 LightRAG 查询层，直接读取 LightRAG 已处理好的 PostgreSQL 知识图谱数据库，复刻全部六种查询模式（naive / local / global / hybrid / mix / bypass），提供标准 Langchain Retriever + Chain 接口。脱离 LightRAG 运行时独立运行，只做查询不做数据写入。

**Core Value:** 用户可以通过 Langchain 标准 API，从 LightRAG 已构建的知识图谱数据库中执行六种查询模式的检索和问答，无需启动 LightRAG 服务。

### Constraints

- **Python**: >= 3.12
- **Langchain**: >= 1.2.3
- **数据库**: PostgreSQL，需要 pgvector 和 Apache AGE 扩展
- **只读**: 不执行任何 CREATE / INSERT / UPDATE / DELETE 操作
- **配置方式**: 所有配置通过 .env 文件，不硬编码
- **LLM 中立**: 支持所有 OpenAI 兼容 API 的 LLM provider
- **Embedding 中立**: 支持 OpenAI 兼容 API 的 embedding provider
- **Reranker 中立**: 支持多种 reranker（aliyun / cohere / jina）
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| framework-selection | "INVOKE THIS SKILL at the START of any LangChain/LangGraph/Deep Agents project, before writing any agent code. Determines which framework layer is right for the task: LangChain, LangGraph, Deep Agents, or a combination. Must be consulted before other agent skills." | `.claude/skills/framework-selection/SKILL.md` |
| langchain-dependencies | "INVOKE THIS SKILL when setting up a new project or when asked about package versions, installation, or dependency management for LangChain, LangGraph, LangSmith, or Deep Agents. Covers required packages, minimum versions, environment requirements, versioning best practices, and common community tool packages for both Python and TypeScript." | `.claude/skills/langchain-dependencies/SKILL.md` |
| langchain-fundamentals | Create LangChain agents with create_agent, define tools, and use middleware for human-in-the-loop and error handling. | `.claude/skills/langchain-fundamentals/SKILL.md` |
| langchain-middleware | "INVOKE THIS SKILL when you need human-in-the-loop approval, custom middleware, or structured output. Covers HumanInTheLoopMiddleware for human approval of dangerous tool calls, creating custom middleware with hooks, Command resume patterns, and structured output with Pydantic/Zod." | `.claude/skills/langchain-middleware/SKILL.md` |
| langchain-rag | "INVOKE THIS SKILL when building ANY retrieval-augmented generation (RAG) system. Covers document loaders, RecursiveCharacterTextSplitter, embeddings (OpenAI), and vector stores (Chroma, FAISS, Pinecone)." | `.claude/skills/langchain-rag/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
