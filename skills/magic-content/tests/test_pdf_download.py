"""Tests for pdf_download.py — fetch PDFs with graceful per-URL failure."""
from unittest.mock import MagicMock, patch

import pytest

from pdf_download import download_pdfs


def _mock_response(*, status: int = 200, content: bytes = b"%PDF-1.4 fake"):
    resp = MagicMock()
    resp.status_code = status
    resp.content = content
    resp.iter_content = lambda chunk_size=8192: [content]
    resp.raise_for_status = lambda: (
        _ for _ in ()).throw(Exception(f"HTTP {status}")) if status >= 400 else None
    return resp


@patch("pdf_download.requests.get")
def test_downloads_one_pdf(mock_get, tmp_path):
    mock_get.return_value = _mock_response()

    result = download_pdfs(
        urls=[{"url": "https://e.com/a.pdf", "title": "A"}],
        dest=tmp_path,
    )

    assert len(result["downloaded"]) == 1
    assert result["failed"] == []
    saved = tmp_path / result["downloaded"][0]["path"].split("/")[-1]
    assert saved.exists()
    assert saved.read_bytes().startswith(b"%PDF")


@patch("pdf_download.requests.get")
def test_marks_failures_but_continues(mock_get, tmp_path):
    def side_effect(url, **_):
        if "bad" in url:
            r = MagicMock()
            r.raise_for_status = lambda: (_ for _ in ()).throw(
                Exception("HTTP 404"))
            return r
        return _mock_response()

    mock_get.side_effect = side_effect

    result = download_pdfs(
        urls=[
            {"url": "https://e.com/good.pdf", "title": "G"},
            {"url": "https://e.com/bad.pdf",  "title": "B"},
        ],
        dest=tmp_path,
    )

    assert len(result["downloaded"]) == 1
    assert len(result["failed"]) == 1
    assert "bad.pdf" in result["failed"][0]["url"]


@patch("pdf_download.requests.get")
def test_unique_filenames_on_collision(mock_get, tmp_path):
    mock_get.return_value = _mock_response()

    result = download_pdfs(
        urls=[
            {"url": "https://a.com/paper.pdf", "title": "A"},
            {"url": "https://b.com/paper.pdf", "title": "B"},
        ],
        dest=tmp_path,
    )

    paths = {entry["path"] for entry in result["downloaded"]}
    assert len(paths) == 2  # no overwrite
