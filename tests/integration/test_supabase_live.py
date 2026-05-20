"""End-to-end Supabase smoke test. Auto-skipped when SUPABASE_URL is unset.

This actually hits Supabase. Run after you've created the project and bucket:
  pytest tests/integration -v
"""
import os
import uuid

import pytest

if not os.getenv("SUPABASE_URL"):
    pytest.skip("SUPABASE_URL not set — skipping live Supabase test",
                allow_module_level=True)

from agent import db  # noqa: E402


class _Blob:
    def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload
        self.size = len(payload)
    def getvalue(self) -> bytes:
        return self._payload


def test_full_paper_lifecycle():
    thread_id = str(uuid.uuid4())

    db.create_paper(thread_id, topic="(untitled)", mode="term")
    try:
        db.update_paper_topic(thread_id, "Photosynthesis")
        path = db.upload_file(thread_id, _Blob("notes.txt", b"hello supabase"))
        assert path == f"{thread_id}/notes.txt"

        files = db.list_paper_files(thread_id)
        assert len(files) == 1
        assert files[0]["file_name"] == "notes.txt"

        blob = db.download_file(path)
        assert blob == b"hello supabase"

        db.mark_complete(thread_id, "# Done")
        paper = db.get_paper(thread_id)
        assert paper["status"] == "complete"
        assert paper["topic"] == "Photosynthesis"
        assert paper["final_output"] == "# Done"

        listed = db.list_papers()
        assert any(p["id"] == thread_id for p in listed)
    finally:
        db.delete_paper(thread_id)
