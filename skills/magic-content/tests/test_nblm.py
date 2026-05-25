"""Tests for nblm.py — CLI wrapper over notebooklm."""
import json
from unittest.mock import MagicMock, patch

import pytest

from nblm import (
    create_notebook, add_sources, wait_for_sources,
    generate_artifacts, download_artifacts, AuthExpiredError,
)


def _ok(stdout: str, stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = stderr
    return r


def _fail(stderr: str, returncode: int = 1) -> MagicMock:
    r = MagicMock()
    r.returncode = returncode
    r.stdout = ""
    r.stderr = stderr
    return r


@patch("nblm.subprocess.run")
def test_create_returns_notebook_id(mock_run):
    mock_run.return_value = _ok(json.dumps({"notebook_id": "nb-123"}))
    nb_id = create_notebook("magic-test")
    assert nb_id == "nb-123"
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "notebooklm"
    assert "create" in cmd
    assert "magic-test" in " ".join(cmd)


@patch("nblm.subprocess.run")
def test_auth_expired_raises(mock_run):
    mock_run.return_value = _fail("Authentication expired. Run notebooklm login.")
    with pytest.raises(AuthExpiredError):
        create_notebook("magic-test")


@patch("nblm.subprocess.run")
def test_add_sources_categorizes_results(mock_run):
    mock_run.return_value = _ok(json.dumps({"source_id": "s-1"}))
    sources = [
        {"type": "url",     "value": "https://e.com"},
        {"type": "youtube", "value": "https://youtu.be/x"},
        {"type": "file",    "value": "/tmp/a.pdf"},
    ]
    out = add_sources("nb-123", sources)
    assert len(out["added"]) == 3
    assert out["failed"] == []


@patch("nblm.subprocess.run")
def test_add_sources_failure_continues_batch(mock_run):
    mock_run.side_effect = [
        _ok(json.dumps({"source_id": "s-1"})),
        _fail("Network error"),
        _ok(json.dumps({"source_id": "s-3"})),
    ]
    sources = [
        {"type": "url", "value": "https://a.com"},
        {"type": "url", "value": "https://b.com"},
        {"type": "url", "value": "https://c.com"},
    ]
    out = add_sources("nb-123", sources)
    assert len(out["added"]) == 2
    assert len(out["failed"]) == 1


@patch("nblm.time.sleep")
@patch("nblm.subprocess.run")
def test_wait_polls_until_ready(mock_run, _sleep):
    mock_run.side_effect = [
        _ok(json.dumps({"sources": [{"status": "processing"}]})),
        _ok(json.dumps({"sources": [{"status": "ready"}]})),
    ]
    out = wait_for_sources("nb-123", timeout=10, poll_interval=0)
    assert out["ready"] is True


@patch("nblm.time.monotonic")
@patch("nblm.time.sleep")
@patch("nblm.subprocess.run")
def test_wait_times_out(mock_run, _sleep, mock_clock):
    mock_clock.side_effect = [0, 1, 2, 3, 999]  # eventually exceeds timeout
    mock_run.return_value = _ok(json.dumps({"sources": [{"status": "processing"}]}))
    out = wait_for_sources("nb-123", timeout=5, poll_interval=0)
    assert out["ready"] is False
    assert out["error"] == "timeout"


@patch("nblm.subprocess.run")
def test_generate_invokes_per_type(mock_run):
    mock_run.return_value = _ok(json.dumps({"artifact_id": "a-1"}))
    out = generate_artifacts("nb-123", ["briefing", "audio"])
    assert mock_run.call_count == 2
    assert len(out["artifacts"]) == 2
    types = [a["type"] for a in out["artifacts"]]
    assert types == ["briefing", "audio"]


@patch("nblm.subprocess.run")
def test_download_returns_files(mock_run, tmp_path):
    mock_run.return_value = _ok(json.dumps({
        "files": [
            {"type": "briefing", "path": str(tmp_path / "briefing.md"),
             "mime": "text/markdown"},
        ],
    }))
    out = download_artifacts("nb-123", tmp_path)
    assert len(out["files"]) == 1
    assert out["files"][0]["type"] == "briefing"
