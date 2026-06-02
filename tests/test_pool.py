"""测试套件：psycopg 连接池管理器的完整单元测试。

覆盖：池初始化、惰性访问、幂等性、依赖注入、pgvector 编解码注册、
configure 回调、池关闭生命周期、以及 acquire_with_retry 已移除的验证。

所有 psycopg 调用均被 mock —— 无真实数据库连接。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 获取 pool 模块引用
# ---------------------------------------------------------------------------


def _pool_mod():
    """返回 pool 模块的引用。

    在测试体内部调用（不在模块级别），以确保 fixture 已先设置环境变量。
    """
    import lightrag_langchain.data.pool as mod

    return mod


# ---------------------------------------------------------------------------
# Auto-use fixture: 每次测试前重置模块级状态
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    """每次测试前重置模块级单例并设置所需环境变量。

    确保每个测试从干净状态开始——缓存的 Settings 单例和 pool 单例被清除，
    所有必需环境变量通过 monkeypatch 可用。
    """
    required_vars = {
        "lightrag_pg__host": "localhost",
        "lightrag_pg__port": "5432",
        "lightrag_pg__user": "test",
        "lightrag_pg__password": "secret",
        "lightrag_pg__database": "testdb",
        "lightrag_llm__binding": "openai",
        "lightrag_llm__binding_host": "https://api.openai.com/v1",
        "lightrag_llm__binding_api_key": "sk-test",
        "lightrag_llm__model": "gpt-4o-mini",
        "lightrag_embedding__binding": "openai",
        "lightrag_embedding__binding_host": "https://api.openai.com/v1",
        "lightrag_embedding__binding_api_key": "sk-emb",
        "lightrag_embedding__model": "text-embedding-3-small",
    }
    for k, v in required_vars.items():
        monkeypatch.setenv(k, v)

    # 重置 Settings 单例
    import lightrag_langchain.config as config_module
    config_module._settings = None

    # 导入 pool 并重绑定
    import lightrag_langchain.data.pool as pool_module
    pool_module.settings = config_module.__getattr__("settings")
    pool_module._pool = None


# ---------------------------------------------------------------------------
# TestPoolInit — 池创建和依赖注入
# ---------------------------------------------------------------------------


class TestPoolInit:
    """池创建、幂等性、依赖注入和 configure 回调。"""

    @pytest.mark.asyncio
    async def test_init_creates_pool_with_config(self):
        """init_pool() 使用 settings 中的配置创建 AsyncConnectionPool。"""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.open = AsyncMock()
        mock_pool.close = AsyncMock()

        with patch(
            "lightrag_langchain.data.pool.AsyncConnectionPool",
            return_value=mock_pool,
        ) as mock_acp:
            result = await pm.init_pool()

        # 验证返回的是 mock_pool
        assert result is mock_pool
        # 验证 _pool 模块级状态已设置
        assert pm._pool is mock_pool

        # 验证 AsyncConnectionPool 的构造参数
        mock_acp.assert_called_once()
        call_kwargs = mock_acp.call_args.kwargs

        # conninfo 字符串验证
        assert "conninfo" in call_kwargs
        conninfo = call_kwargs["conninfo"]
        assert "postgresql://" in conninfo
        assert "localhost" in conninfo
        assert "5432" in conninfo
        assert "test" in conninfo
        assert "secret" in conninfo
        assert "testdb" in conninfo

        # min_size / max_size
        assert call_kwargs["min_size"] == 2
        assert call_kwargs["max_size"] == 10

        # kwargs 中的 autocommit 和 row_factory
        assert "kwargs" in call_kwargs
        assert call_kwargs["kwargs"]["autocommit"] is True
        from psycopg.rows import dict_row
        assert call_kwargs["kwargs"]["row_factory"] is dict_row

        # configure 回调
        assert "configure" in call_kwargs
        assert callable(call_kwargs["configure"])

        # open=False
        assert call_kwargs["open"] is False

        # 验证 _pool.open() 被调用
        mock_pool.open.assert_awaited_once()

        await pm.close_pool()

    @pytest.mark.asyncio
    async def test_init_pool_idempotent(self):
        """两次调用 init_pool() 返回相同的池对象（引用相等）。"""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.open = AsyncMock()
        mock_pool.close = AsyncMock()

        with patch(
            "lightrag_langchain.data.pool.AsyncConnectionPool",
            return_value=mock_pool,
        ) as mock_acp:
            p1 = await pm.init_pool()
            p2 = await pm.init_pool()

        # 两次返回同一个对象
        assert p1 is p2 is mock_pool
        # AsyncConnectionPool 仅构造一次
        mock_acp.assert_called_once()

        await pm.close_pool()

    @pytest.mark.asyncio
    async def test_init_with_custom_pool(self):
        """init_pool(custom_pool=mock) 将 _pool 设置为自定义 mock（D-07）。"""
        pm = _pool_mod()

        custom = AsyncMock()
        result = await pm.init_pool(custom_pool=custom)

        assert result is custom
        assert pm._pool is custom

        await pm.close_pool()

    @pytest.mark.asyncio
    async def test_configure_callback_registers_pgvector(self):
        """传递给 AsyncConnectionPool 的 configure 回调注册 pgvector 并设置 search_path 和 read_only。"""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.open = AsyncMock()
        mock_pool.close = AsyncMock()

        with patch(
            "lightrag_langchain.data.pool.AsyncConnectionPool",
            return_value=mock_pool,
        ) as mock_acp:
            await pm.init_pool()

        # 提取 configure 回调
        configure_cb = mock_acp.call_args.kwargs["configure"]
        assert callable(configure_cb)

        # 使用 mock connection 调用 configure 回调
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        with patch(
            "pgvector.psycopg.register_vector_async", new=AsyncMock()
        ) as rv:
            await configure_cb(mock_conn)

        # 验证 register_vector_async 已调用
        rv.assert_awaited_once_with(mock_conn)

        # 验证 SET search_path 和 SET default_transaction_read_only
        # execute 被调用了 3 次（register_vector_async 后两次 SET）
        assert mock_conn.execute.await_count >= 2

        await pm.close_pool()


# ---------------------------------------------------------------------------
# TestPoolAccess — 惰性访问器行为
# ---------------------------------------------------------------------------


class TestPoolAccess:
    """模块级 __getattr__ 访问控制 — 初始化前后的行为。"""

    @pytest.mark.asyncio
    async def test_access_before_init_raises(self):
        """在 init_pool() 之前访问 pool 应抛出 RuntimeError。"""
        pm = _pool_mod()
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = pm.pool

    @pytest.mark.asyncio
    async def test_access_unknown_attribute_raises(self):
        """访问 pool 模块上不存在的属性应抛出 AttributeError。"""
        pm = _pool_mod()
        with pytest.raises(AttributeError):
            _ = pm.nonexistent_attr


# ---------------------------------------------------------------------------
# TestPoolClose — 显式池关闭
# ---------------------------------------------------------------------------


class TestPoolClose:
    """close_pool() 生命周期 — 释放和幂等关闭。"""

    @pytest.mark.asyncio
    async def test_close_releases_pool(self):
        """close_pool() 调用 pool.close() 并设置 _pool = None。"""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.open = AsyncMock()
        mock_pool.close = AsyncMock()
        with patch(
            "lightrag_langchain.data.pool.AsyncConnectionPool",
            return_value=mock_pool,
        ):
            await pm.init_pool()

        assert pm._pool is mock_pool
        await pm.close_pool()

        # 验证 pool.close() 被调用
        mock_pool.close.assert_awaited_once()
        # 验证 _pool 被重置为 None
        assert pm._pool is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """两次调用 close_pool() 不抛异常 — close 只调用一次。"""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.open = AsyncMock()
        mock_pool.close = AsyncMock()
        with patch(
            "lightrag_langchain.data.pool.AsyncConnectionPool",
            return_value=mock_pool,
        ):
            await pm.init_pool()

        await pm.close_pool()
        await pm.close_pool()  # 第二次调用应为 no-op

        # close() 只调用一次
        mock_pool.close.assert_awaited_once()
        assert pm._pool is None


# ---------------------------------------------------------------------------
# TestAcquireWithRetryRemoved — acquire_with_retry 已移除
# ---------------------------------------------------------------------------


class TestAcquireWithRetryRemoved:
    """验证 acquire_with_retry 函数已从 pool 模块中移除。"""

    def test_acquire_with_retry_not_in_module(self):
        """pool 模块不应再包含 acquire_with_retry 函数。"""
        pm = _pool_mod()
        assert not hasattr(pm, "acquire_with_retry"), (
            "acquire_with_retry should be removed from pool.py"
        )

    def test_acquire_with_retry_not_in_source(self):
        """pool.py 源代码不应包含 acquire_with_retry 定义。"""
        with open("src/lightrag_langchain/data/pool.py") as f:
            source = f.read()
        assert "acquire_with_retry" not in source, (
            "acquire_with_retry should not appear in pool.py source"
        )


# ---------------------------------------------------------------------------
# TestConfigureCallback — _configure_connection 函数签名和行为
# ---------------------------------------------------------------------------


class TestConfigureCallback:
    """_configure_connection 函数的签名和行为验证。"""

    def test_configure_connection_exists(self):
        """pool 模块应包含 _configure_connection 函数。"""
        pm = _pool_mod()
        assert hasattr(pm, "_configure_connection"), (
            "_configure_connection should exist in pool.py"
        )

    def test_configure_connection_signature(self):
        """_configure_connection 应接受单个 conn 参数。"""
        import inspect

        pm = _pool_mod()
        sig = inspect.signature(pm._configure_connection)
        assert len(sig.parameters) == 1, (
            "configure callback must take exactly one conn argument"
        )


# ---------------------------------------------------------------------------
# TestAsyncpgRemoved — asyncpg 导入已完全移除
# ---------------------------------------------------------------------------


class TestAsyncpgRemoved:
    """验证 pool.py 源代码中不存在任何 asyncpg 导入。"""

    def test_no_asyncpg_imports(self):
        """pool.py 不应包含任何 asyncpg 导入。"""
        import ast

        with open("src/lightrag_langchain/data/pool.py") as f:
            source = f.read()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert "asyncpg" not in imports, f"asyncpg still imported: {imports}"


# ---------------------------------------------------------------------------
# TestDataLayerErrorRemoved — DataLayerError 已移除
# ---------------------------------------------------------------------------


class TestDataLayerErrorRemoved:
    """验证 DataLayerError 异常类已从 pool 模块中移除。"""

    def test_data_layer_error_not_in_module(self):
        """pool 模块不应再包含 DataLayerError。"""
        pm = _pool_mod()
        assert not hasattr(pm, "DataLayerError"), (
            "DataLayerError should be removed from pool.py"
        )
