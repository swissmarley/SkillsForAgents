"""Tests for manifest.py — read/write run manifest with collision suffixing."""
import json

import pytest

from manifest import resolve_slug_dir, write_manifest, read_manifest


@pytest.fixture
def basic_inputs(tmp_raw_dir):
    return {
        "raw_root": tmp_raw_dir,
        "topic": "Transformer Attention",
        "slug": "transformer-attention",
        "queries": ["transformer attention mechanism"],
        "sources": [
            {"type": "youtube", "url": "https://youtu.be/x", "title": "T"},
            {"type": "web",     "url": "https://e.com",      "title": "E"},
        ],
        "artifacts": [
            {"type": "briefing", "file": "briefing.md"},
        ],
        "notebook_id": "nb-123",
        "date": "2026-05-08",
    }


def test_resolve_slug_dir_no_collision(tmp_raw_dir):
    resolved = resolve_slug_dir(tmp_raw_dir, "topic-x")
    assert resolved.name == "topic-x"
    assert not resolved.exists()  # not created yet, just resolved


def test_resolve_slug_dir_with_collision(tmp_raw_dir):
    (tmp_raw_dir / "topic-x").mkdir()
    resolved = resolve_slug_dir(tmp_raw_dir, "topic-x")
    assert resolved.name == "topic-x-2"


def test_resolve_slug_dir_with_multiple_collisions(tmp_raw_dir):
    (tmp_raw_dir / "topic-x").mkdir()
    (tmp_raw_dir / "topic-x-2").mkdir()
    (tmp_raw_dir / "topic-x-3").mkdir()
    resolved = resolve_slug_dir(tmp_raw_dir, "topic-x")
    assert resolved.name == "topic-x-4"


def test_write_creates_manifest_json(basic_inputs):
    out_dir = write_manifest(**basic_inputs)
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["topic"] == "Transformer Attention"
    assert data["slug"] == "transformer-attention"
    assert data["notebook_id"] == "nb-123"
    assert data["date"] == "2026-05-08"
    assert len(data["sources"]) == 2
    assert data["queries_used"] == ["transformer attention mechanism"]


def test_write_collision_suffixes_slug(basic_inputs, tmp_raw_dir):
    write_manifest(**basic_inputs)
    out_dir2 = write_manifest(**basic_inputs)
    assert out_dir2.name == "transformer-attention-2"
    data2 = json.loads((out_dir2 / "manifest.json").read_text())
    assert data2["slug"] == "transformer-attention-2"


def test_read_returns_dict(basic_inputs):
    out_dir = write_manifest(**basic_inputs)
    data = read_manifest(out_dir)
    assert data["topic"] == "Transformer Attention"


def test_read_missing_manifest_raises(tmp_raw_dir):
    empty = tmp_raw_dir / "no-manifest-here"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        read_manifest(empty)
