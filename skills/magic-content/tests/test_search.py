"""Tests for search.py — merge WebSearch + yt-dlp into normalized JSON."""
import json
from unittest.mock import patch

import pytest

from search import merge_results, enrich_youtube


def test_merge_normalizes_all_channels(
    sample_websearch_youtube, sample_websearch_web, sample_websearch_pdf
):
    out = merge_results(
        topic="transformer attention",
        queries=["q1", "q2"],
        youtube_results=sample_websearch_youtube,
        web_results=sample_websearch_web,
        pdf_results=sample_websearch_pdf,
        max_per_channel=10,
        enriched_youtube=None,
    )

    assert out["topic"] == "transformer attention"
    assert out["queries"] == ["q1", "q2"]
    assert len(out["youtube"]) == 2
    assert all("url" in v and "title" in v for v in out["youtube"])
    assert all(v["source"] == "search" for v in out["youtube"])
    assert len(out["web"]) == 1
    assert len(out["pdf"]) == 1


def test_merge_caps_at_max_per_channel():
    many = [
        {"url": f"https://youtu.be/v{i}", "title": f"video {i}"}
        for i in range(40)
    ]
    out = merge_results(
        topic="t", queries=[],
        youtube_results=many, web_results=[], pdf_results=[],
        max_per_channel=5, enriched_youtube=None,
    )
    assert len(out["youtube"]) == 5


def test_merge_dedupes_by_url(sample_websearch_youtube):
    duped = sample_websearch_youtube + sample_websearch_youtube
    out = merge_results(
        topic="t", queries=[],
        youtube_results=duped, web_results=[], pdf_results=[],
        max_per_channel=10, enriched_youtube=None,
    )
    urls = [v["url"] for v in out["youtube"]]
    assert len(urls) == len(set(urls))


def test_merge_applies_youtube_enrichment(sample_websearch_youtube):
    enriched = {
        "https://www.youtube.com/watch?v=abc123": {
            "channel": "3Blue1Brown", "duration": 1234, "view_count": 50000,
        },
    }
    out = merge_results(
        topic="t", queries=[],
        youtube_results=sample_websearch_youtube, web_results=[], pdf_results=[],
        max_per_channel=10, enriched_youtube=enriched,
    )
    abc = next(v for v in out["youtube"] if v["url"].endswith("abc123"))
    assert abc["channel"] == "3Blue1Brown"
    assert abc["duration_sec"] == 1234
    assert abc["views"] == 50000
    assert abc["source"] == "yt-dlp"


@patch("search.subprocess.run")
def test_enrich_youtube_calls_ytdlp(mock_run):
    mock_run.return_value.stdout = json.dumps({
        "channel": "C", "duration": 100, "view_count": 1,
    })
    mock_run.return_value.returncode = 0
    out = enrich_youtube(["https://youtu.be/x"])
    assert "https://youtu.be/x" in out
    assert out["https://youtu.be/x"]["channel"] == "C"


@patch("search.subprocess.run", side_effect=FileNotFoundError("yt-dlp"))
def test_enrich_youtube_missing_ytdlp_returns_empty(mock_run):
    out = enrich_youtube(["https://youtu.be/x"])
    assert out == {}


@patch("search.subprocess.run")
def test_enrich_youtube_skips_failed_urls(mock_run):
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = "ERROR: video unavailable"
    out = enrich_youtube(["https://youtu.be/bad"])
    assert out == {}
