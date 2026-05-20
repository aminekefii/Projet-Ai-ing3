"""Supabase client + papers/files CRUD + Storage I/O."""
from __future__ import annotations

import os
from typing import Optional

from supabase import Client, create_client

_PAPERS_TABLE = "papers"
_FILES_TABLE = "paper_files"
_BUCKET = "paper-files"

_client: Optional[Client] = None


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def get_client() -> Client:
    """Return the cached Supabase client, building it on first call."""
    global _client
    if _client is None:
        url = _require_env("SUPABASE_URL")
        key = _require_env("SUPABASE_SERVICE_KEY")
        _client = create_client(url, key)
    return _client
