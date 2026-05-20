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


# ---------- papers CRUD ----------

@pytest.fixture
def patched_client(monkeypatch):
    """Return a MagicMock standing in for the Supabase client, with env vars set."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    import importlib

    import agent.db as db
    importlib.reload(db)

    client = MagicMock()
    with patch("agent.db.create_client", return_value=client):
        # warm the cache
        db.get_client()
        yield client, db


def test_create_paper_inserts_row(patched_client):
    client, db = patched_client
    db.create_paper("abc-123", "Photosynthesis", "term")

    client.table.assert_called_with("papers")
    insert = client.table.return_value.insert
    insert.assert_called_once()
    row = insert.call_args[0][0]
    assert row["id"] == "abc-123"
    assert row["topic"] == "Photosynthesis"
    assert row["mode"] == "term"
    insert.return_value.execute.assert_called_once()


def test_update_paper_topic_updates_row(patched_client):
    client, db = patched_client
    db.update_paper_topic("abc-123", "New Topic")

    client.table.assert_called_with("papers")
    update = client.table.return_value.update
    update.assert_called_once()
    args = update.call_args[0][0]
    assert args["topic"] == "New Topic"
    assert "updated_at" in args
    update.return_value.eq.assert_called_with("id", "abc-123")


def test_mark_complete_sets_status_and_output(patched_client):
    client, db = patched_client
    db.mark_complete("abc-123", "# Final paper\n\n## Intro\n…")

    client.table.assert_called_with("papers")
    update = client.table.return_value.update
    args = update.call_args[0][0]
    assert args["status"] == "complete"
    assert args["final_output"].startswith("# Final paper")
    update.return_value.eq.assert_called_with("id", "abc-123")


def test_get_paper_returns_row(patched_client):
    client, db = patched_client
    fake_row = {"id": "abc-123", "topic": "X", "mode": "term", "status": "complete",
                "final_output": "# X", "created_at": "now", "updated_at": "now"}
    response = MagicMock()
    response.data = [fake_row]
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = response

    got = db.get_paper("abc-123")
    assert got == fake_row


def test_get_paper_returns_none_when_missing(patched_client):
    client, db = patched_client
    response = MagicMock()
    response.data = []
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = response

    assert db.get_paper("missing") is None


def test_list_papers_returns_rows_ordered(patched_client):
    client, db = patched_client
    rows = [{"id": "a", "topic": "A"}, {"id": "b", "topic": "B"}]
    response = MagicMock()
    response.data = rows
    client.table.return_value.select.return_value.order.return_value.execute.return_value = response

    got = db.list_papers()
    assert got == rows
    client.table.return_value.select.assert_called_with("*")
    client.table.return_value.select.return_value.order.assert_called_with(
        "updated_at", desc=True
    )


def test_delete_paper_cascades_to_files_and_storage(patched_client):
    client, db = patched_client
    # paper_files rows for this paper
    files_response = MagicMock()
    files_response.data = [{"storage_path": "abc/file1.pdf"},
                           {"storage_path": "abc/file2.csv"}]
    (client.table.return_value.select.return_value
        .eq.return_value.execute.return_value) = files_response

    db.delete_paper("abc-123")

    # Storage purge
    client.storage.from_.assert_any_call("paper-files")
    client.storage.from_.return_value.remove.assert_called_with(
        ["abc/file1.pdf", "abc/file2.csv"]
    )

    # Cascade deletes the papers row (and paper_files via FK ON DELETE CASCADE)
    client.table.assert_any_call("papers")
    delete = client.table.return_value.delete
    delete.return_value.eq.assert_called_with("id", "abc-123")


# ---------- files + storage ----------

class _FakeUploadedFile:
    """Stand-in for a streamlit.runtime.uploaded_file_manager.UploadedFile."""
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload
        self.size = len(payload)
    def getvalue(self) -> bytes:
        return self._payload


def test_upload_file_writes_blob_and_inserts_row(patched_client):
    client, db = patched_client
    f = _FakeUploadedFile("notes.pdf", b"%PDF-1.7 fake")

    path = db.upload_file("abc-123", f)

    assert path == "abc-123/notes.pdf"

    # Storage call
    client.storage.from_.assert_any_call("paper-files")
    client.storage.from_.return_value.upload.assert_called_once()
    upload_args = client.storage.from_.return_value.upload.call_args
    assert upload_args.kwargs.get("path") == "abc-123/notes.pdf" \
        or upload_args.args[0] == "abc-123/notes.pdf"

    # Metadata upsert (NOT insert, so re-uploads don't create duplicate rows)
    client.table.assert_any_call("paper_files")
    upsert = client.table.return_value.upsert
    row = upsert.call_args[0][0]
    assert row["paper_id"] == "abc-123"
    assert row["file_name"] == "notes.pdf"
    assert row["file_size"] == len(b"%PDF-1.7 fake")
    assert row["storage_path"] == "abc-123/notes.pdf"
    assert upsert.call_args.kwargs.get("on_conflict") == "paper_id,file_name"
    upsert.return_value.execute.assert_called_once()


def test_list_paper_files_returns_rows_in_upload_order(patched_client):
    client, db = patched_client
    rows = [{"file_name": "a.pdf"}, {"file_name": "b.pdf"}]
    response = MagicMock()
    response.data = rows
    (client.table.return_value.select.return_value
        .eq.return_value.order.return_value.execute.return_value) = response

    got = db.list_paper_files("abc-123")
    assert got == rows
    client.table.return_value.select.return_value.eq.assert_called_with(
        "paper_id", "abc-123"
    )
    client.table.return_value.select.return_value.eq.return_value.order \
        .assert_called_with("uploaded_at")


def test_download_file_returns_blob_bytes(patched_client):
    client, db = patched_client
    client.storage.from_.return_value.download.return_value = b"%PDF-blob"

    blob = db.download_file("abc-123/notes.pdf")
    assert blob == b"%PDF-blob"
    client.storage.from_.assert_any_call("paper-files")
    client.storage.from_.return_value.download.assert_called_with("abc-123/notes.pdf")
