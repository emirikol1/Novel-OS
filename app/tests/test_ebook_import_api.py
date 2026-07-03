"""API tests for ebook import preview and job submission."""

from __future__ import annotations

from tests.test_api import _client


def test_ebook_preview_upload(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    staging.mkdir()
    monkeypatch.setattr("import_staging.staging_root", lambda: staging)
    sample = (
        "Title: Mini\nAuthor: Tester\n\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK MINI ***\n\n"
        "CHAPTER I.\nTOC\n\nCHAPTER II.\nTOC\n\n"
        "CHAPTER I.\n\n" + " ".join(f"w{i}" for i in range(80)) + "\n\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK MINI ***\n"
    )
    c = _client(tmp_path)
    resp = c.post(
        "/api/import/ebook/preview",
        content=sample.encode("utf-8"),
        headers={"X-Filename": "mini.txt", "Content-Type": "text/plain"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["upload_id"]
    assert body["title"] == "Mini"
    assert body["chapters"]
    assert body["total_words"] > 0


def test_ebook_import_job_no_extract(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    staging.mkdir()
    monkeypatch.setattr("import_staging.staging_root", lambda: staging)
    from import_staging import save_upload  # noqa: E402

    text = "word " * 300
    upload_id, _ = save_upload(text.encode("utf-8"), "flat.txt")

    c = _client(tmp_path)
    resp = c.post(
        "/api/import/ebook",
        json={
            "upload_id": upload_id,
            "title": "Flat Novel",
            "genre": "Test",
            "no_extract": True,
        },
    )
    assert resp.status_code == 202
    job = resp.json()
    assert job["project_id"]
