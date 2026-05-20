"""Supabase client + papers/files CRUD + Storage I/O."""
from __future__ import annotations

import os
from datetime import datetime, timezone
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
    """Delete a paper, its files (metadata + Storage), and LangGraph checkpoints.

    Cleans, in order:
      1. Storage blobs listed in paper_files for this thread.
      2. LangGraph orphan rows in checkpoint_writes / checkpoint_blobs / checkpoints
         (no FK to papers, must be cleaned separately).
      3. The papers row (paper_files rows cascade via FK ON DELETE CASCADE).

    Assumes LangGraph's checkpoint tables live in the `public` schema and are
    exposed by PostgREST (the default `langgraph-checkpoint-postgres` setup).
    A LangGraph upgrade that renames the tables or moves them to another schema
    would make these deletes silently no-op — orphan checkpoint rows would
    return. Re-verify by checking checkpoint row counts after a delete.
    """
    client = get_client()
    files = (client.table(_FILES_TABLE)
             .select("storage_path")
             .eq("paper_id", thread_id)
             .execute())
    paths = [row["storage_path"] for row in (files.data or [])]
    if paths:
        client.storage.from_(_BUCKET).remove(paths)
    # LangGraph checkpoint tables — same Postgres DB, no FK to papers, so we
    # wipe them through the SDK. Order: writes → blobs → checkpoints.
    for tbl in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        client.table(tbl).delete().eq("thread_id", thread_id).execute()
    client.table(_PAPERS_TABLE).delete().eq("id", thread_id).execute()


def upload_file(thread_id: str, uploaded_file) -> str:
    """Upload a Streamlit UploadedFile to Storage and record metadata.

    Returns the storage path of the uploaded blob.
    """
    payload = uploaded_file.getvalue()
    storage_path = f"{thread_id}/{uploaded_file.name}"

    client = get_client()
    client.storage.from_(_BUCKET).upload(
        path=storage_path,
        file=payload,
        file_options={"upsert": "true"},
    )
    client.table(_FILES_TABLE).upsert(
        {
            "paper_id": thread_id,
            "file_name": uploaded_file.name,
            "file_size": len(payload),
            "storage_path": storage_path,
        },
        on_conflict="paper_id,file_name",
    ).execute()
    return storage_path


def list_paper_files(thread_id: str) -> list[dict]:
    """Return all file rows for a paper, oldest upload first."""
    response = (get_client().table(_FILES_TABLE)
                .select("*")
                .eq("paper_id", thread_id)
                .order("uploaded_at")
                .execute())
    return response.data or []


def download_file(storage_path: str) -> bytes:
    """Download a blob from Storage by its path."""
    return get_client().storage.from_(_BUCKET).download(storage_path)
