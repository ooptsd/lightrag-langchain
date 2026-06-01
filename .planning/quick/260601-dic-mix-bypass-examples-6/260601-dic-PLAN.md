---
phase: quick
plan: 260601-dic
description: "添加 mix 和 bypass 查询示例脚本，补全 examples 目录覆盖全部 6 种查询模式"
type: execute
wave: 1
depends_on: []
files_modified:
  - examples/mix_query.py
  - examples/bypass_query.py
  - examples/README.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "examples/ 目录下存在可运行的 mix_query.py 脚本，演示 Mix 模式"
    - "examples/ 目录下存在可运行的 bypass_query.py 脚本，演示 Bypass 模式"
    - "examples/README.md 查询模式表格包含全部 6 种模式的独立脚本条目"
  artifacts:
    - path: "examples/mix_query.py"
      provides: "Mix 模式独立查询脚本"
      min_lines: 50
    - path: "examples/bypass_query.py"
      provides: "Bypass 模式独立查询脚本"
      min_lines: 30
    - path: "examples/README.md"
      provides: "更新后的示例目录说明文档"
      check_contains:
        - "mix_query.py"
        - "bypass_query.py"
  key_links:
    - from: "examples/mix_query.py"
      to: "lightrag_langchain.MixChain"
      via: "from lightrag_langchain import MixChain"
      pattern: "MixChain"
    - from: "examples/bypass_query.py"
      to: "lightrag_langchain.BypassChain"
      via: "from lightrag_langchain import BypassChain"
      pattern: "BypassChain"
---

<objective>
补全 examples 目录的独立查询示例脚本，覆盖全部 6 种 LightRAG 查询模式。

当前状态：examples/ 目录有 naive_query.py / local_query.py / global_query.py / hybrid_query.py 四个独立脚本 + walkthrough.ipynb (含全部 6 种模式)。缺少 mix_query.py 和 bypass_query.py 独立脚本。

目的：为 Mix 和 Bypass 模式提供可独立运行的 Python 脚本，与现有 4 个脚本保持统一结构和风格。
输出：examples/mix_query.py, examples/bypass_query.py, 更新的 examples/README.md
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
# 现有示例脚本模式 (pattern reference)
@examples/naive_query.py
@examples/hybrid_query.py
@examples/global_query.py
@examples/local_query.py

# 现有 README (需要更新)
@examples/README.md

# walkthrough notebook 中的 mix/bypass 用法
@examples/walkthrough.ipynb

# Chain/Retriever 类定义和 __init__.py 导出
@src/lightrag_langchain/__init__.py
@src/lightrag_langchain/chain/chains.py
@src/lightrag_langchain/retriever/retrievers.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: 创建 mix_query.py 和 bypass_query.py 示例脚本</name>
  <files>examples/mix_query.py, examples/bypass_query.py</files>
  <action>
    创建两个独立查询示例脚本，遵循现有 4 个脚本的统一结构（以 hybrid_query.py 为主要模板）：

    **examples/mix_query.py** — Mix 模式独立脚本：
    - 文件头 docstring：描述 Mix 模式（Hybrid + chunk vector search，融合图知识和原始文本块，适用于最大覆盖全量检索）
    - 文件头 Usage 注释：`cp ../.env.example ../.env` 和 `uv run python examples/mix_query.py`
    - sys.path.insert 将项目根目录加入路径
    - 导入：`MixChain, MixRetriever, create_llm, create_embedding` from `lightrag_langchain`，`settings` from `lightrag_langchain.config`，`PGGraphStore` from `lightrag_langchain.data.graph`，`PGVectorStore` from `lightrag_langchain.data.store`
    - async main() 按 5 步结构：(1) 创建 vector_store + graph_store 数据连接、(2) 创建 llm + embedding、(3) 构建 MixRetriever(需要 vector_store + graph_store + embedding_config)、(4) 构建 MixChain、(5) 执行查询并打印结果
    - 使用与 walkthrough.ipynb 一致的示例问题："洪水防汛应急响应的完整体系是什么？"
    - 输出格式与其他脚本一致：打印 mode、keywords、sources 数量、answer

    **examples/bypass_query.py** — Bypass 模式独立脚本：
    - 文件头 docstring：描述 Bypass 模式（跳过所有检索，直接 LLM 调用，适用于无需外部知识的纯对话场景）
    - 文件头 Usage 注释：`cp ../.env.example ../.env` 和 `uv run python examples/bypass_query.py`
    - sys.path.insert 将项目根目录加入路径
    - 导入：`BypassChain, BypassRetriever, create_llm, create_embedding` from `lightrag_langchain`，`settings` from `lightrag_langchain.config`，`PGVectorStore` from `lightrag_langchain.data.store`（Bypass 不需要 graph_store）
    - async main() 按简化步骤：(1) 创建 vector_store 连接（BypassRetriever 构造函数需要 vector_store，虽然内部不使用）、(2) 创建 llm + embedding、(3) 构建 BypassRetriever(需要 vector_store + embedding_config)、(4) 构建 BypassChain、(5) 执行查询并打印结果
    - 使用与 walkthrough.ipynb 一致的示例问题："请简要介绍中国的应急管理体系。"
    - 输出格式与其他脚本一致：打印 mode、keywords（bypass 模式下 keywords 为空列表）、sources 数量（bypass 模式下为 0）、answer

    **关键对齐点：**
    - 不硬编码密码，使用 `settings.pg.password.get_secret_value()`
    - 使用 `settings.embedding.dim` 作为 embedding_dim
    - 每个脚本末尾 `asyncio.run(main())`
    - 遵循现有 scripts 的注释风格（中文描述 + 英文技术术语）
  </action>
  <verify>
    <automated>python -c "import ast; ast.parse(open('examples/mix_query.py').read()); print('mix_query.py: syntax OK')" &amp;&amp; python -c "import ast; ast.parse(open('examples/bypass_query.py').read()); print('bypass_query.py: syntax OK')"</automated>
  </verify>
  <done>mix_query.py 和 bypass_query.py 语法正确，结构对齐现有示例脚本模式，包含所有必需导入和步骤</done>
</task>

<task type="auto">
  <name>Task 2: 更新 examples/README.md 表格和说明</name>
  <files>examples/README.md</files>
  <action>
    更新 examples/README.md 以反映全部 6 种模式都有独立脚本：

    1. **查询模式表格**：在 hybrid_query.py 行后添加 mix_query.py 和 bypass_query.py 两行：
       - `| `mix_query.py` | Mix | hybrid 检索 + chunks_vdb 向量搜索，融合图知识和原始文本块 |`
       - `| `bypass_query.py` | Bypass | 跳过所有检索，直接调用 LLM |`

    2. **删除或更新 Bypass 注释**：README 末尾有 "Bypass 模式 跳过检索直接调用 LLM，无需独立脚本，其演示在 walkthrough.ipynb 中。" — 将此句改为："全部 6 种查询模式均有独立 Python 脚本；`walkthrough.ipynb` 提供完整的交互式演示。"

    3. **更新表格字数**：表格已有 4 个脚本条目 + walkthrough.ipynb，添加 2 个后变为 6 个脚本 + 1 个 notebook = 7 行（不含表头）

    保持 README 整体结构和风格不变。
  </action>
  <verify>
    <automated>grep -c "mix_query.py" examples/README.md &amp;&amp; grep -c "bypass_query.py" examples/README.md &amp;&amp; ! grep -q "无需独立脚本" examples/README.md</automated>
  </verify>
  <done>README.md 表格包含全部 6 种查询模式的独立脚本条目，Bypass "无需独立脚本" 的旧描述已更新</done>
</task>

</tasks>

<verification>
所有文件语法检查通过，README.md 表格完整覆盖 6 种模式。
</verification>

<success_criteria>
- examples/mix_query.py 文件存在且语法正确，可独立运行演示 Mix 模式
- examples/bypass_query.py 文件存在且语法正确，可独立运行演示 Bypass 模式
- examples/README.md 查询模式表格列出全部 6 种模式的独立脚本
</success_criteria>

<output>
Create `.planning/quick/260601-dic-mix-bypass-examples-6/260601-dic-SUMMARY.md` when done
</output>
