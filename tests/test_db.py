"""Unit tests for agent.db — Supabase client + papers/files CRUD."""
from unittest.mock import MagicMock, patch

import pytest


def test_missing_env_var_raises_runtime_error(monkeypatch):
    """get_client() must fail loudly with the exact missing var name."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    # Re-import to reset the module-level cache.
    import importlib

    import agent.db as db
    importlib.reload(db)

    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        db.get_client()


def test_get_client_caches_singleton(monkeypatch):
    """Repeated get_client() calls return the same client object."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    import importlib

    import agent.db as db
    importlib.reload(db)

    fake_client = MagicMock()
    with patch("agent.db.create_client", return_value=fake_client) as create:
        first = db.get_client()
        second = db.get_client()

    assert first is second
    assert create.call_count == 1
