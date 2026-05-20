"""Postgres-backed LangGraph checkpointer (Supabase-hosted)."""
from __future__ import annotations

import os
from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

_CONNECTION_KWARGS = {"autocommit": True, "prepare_threshold": 0}
_checkpointer: Optional[PostgresSaver] = None


def get_checkpointer() -> PostgresSaver:
    """Return the cached PostgresSaver, building it (and creating tables) on first call."""
    global _checkpointer
    if _checkpointer is None:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            raise RuntimeError("Missing env var: SUPABASE_DB_URL")
        pool = ConnectionPool(db_url, kwargs=_CONNECTION_KWARGS, open=True)
        saver = PostgresSaver(pool)
        saver.setup()
        _checkpointer = saver
    return _checkpointer
