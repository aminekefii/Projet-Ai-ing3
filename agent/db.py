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


from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_paper(thread_id: str, topic: str, mode: str) -> None:
    """Insert a new paper row in 'in_progress' status."""
    get_client().table(_PAPERS_TABLE).insert({
        "id": thread_id,
        "topic": topic,
        "mode": mode,
        "status": "in_progress",
    }).execute()


def update_paper_topic(thread_id: str, topic: str) -> None:
    """Update the topic (called once the user types it in)."""
    get_client().table(_PAPERS_TABLE).update({
        "topic": topic,
        "updated_at": _now_iso(),
    }).eq("id", thread_id).execute()


def mark_complete(thread_id: str, final_output: str) -> None:
    """Mark a paper complete and save its finalized Markdown."""
    get_client().table(_PAPERS_TABLE).update({
        "status": "complete",
        "final_output": final_output,
        "updated_at": _now_iso(),
    }).eq("id", thread_id).execute()


def get_paper(thread_id: str) -> Optional[dict]:
    """Return the paper row, or None if not found."""
    response = (get_client().table(_PAPERS_TABLE)
                .select("*")
                .eq("id", thread_id)
                .execute())
    return response.data[0] if response.data else None


def list_papers() -> list[dict]:
    """Return all paper rows, most recently updated first."""
    response = (get_client().table(_PAPERS_TABLE)
                .select("*")
                .order("updated_at", desc=True)
                .execute())
    return response.data or []


def delete_paper(thread_id: str) -> None:
    """Delete a paper, its file metadata (via ON DELETE CASCADE), and its Storage blobs."""
    client = get_client()
    files = (client.table(_FILES_TABLE)
             .select("storage_path")
             .eq("paper_id", thread_id)
             .execute())
    paths = [row["storage_path"] for row in (files.data or [])]
    if paths:
        client.storage.from_(_BUCKET).remove(paths)
    client.table(_PAPERS_TABLE).delete().eq("id", thread_id).execute()
