"""Unit tests for agent.checkpointer — Postgres-backed LangGraph checkpointer."""
from unittest.mock import MagicMock, patch

import pytest


def test_missing_db_url_raises(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    import importlib

    import agent.checkpointer as cp
    importlib.reload(cp)

    with pytest.raises(RuntimeError, match="SUPABASE_DB_URL"):
        cp.get_checkpointer()


def test_get_checkpointer_returns_postgres_saver_singleton(monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://u:p@h/db")

    import importlib

    import agent.checkpointer as cp
    importlib.reload(cp)

    fake_saver = MagicMock()
    fake_pool = MagicMock()

    with patch("agent.checkpointer.ConnectionPool", return_value=fake_pool) as pool_cls, \
         patch("agent.checkpointer.PostgresSaver", return_value=fake_saver) as saver_cls:
        first = cp.get_checkpointer()
        second = cp.get_checkpointer()

    assert first is fake_saver
    assert first is second
    assert pool_cls.call_count == 1
    assert saver_cls.call_count == 1
    fake_saver.setup.assert_called_once()
