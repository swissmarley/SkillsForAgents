"""Normalize and merge discovery results from WebSearch + yt-dlp."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def enrich_youtube(urls: list[str]) -> dict[str, dict[str, Any]]:
    """Run `yt-dlp --skip-download --print-json` per URL.

    Returns a dict {url: {channel, duration, view_count}} for URLs that
    yt-dlp could resolve. Missing yt-dlp → empty dict (graceful fallback).
    Per-URL errors are skipped silently (warned to stderr).
    """
    enriched: dict[str, dict[str, Any]] = {}
    for url in urls:
        try:
            result = subprocess.run(
                ["yt-dlp", "--skip-download", "--print-json",
                 "--no-warnings", url],
                capture_output=True, text=True, timeout=15,
            )
        except FileNotFoundError:
            print("warning: yt-dlp not installed; skipping enrichment",
                  file=sys.stderr)
            return {}
        except subprocess.TimeoutExpired:
            print(f"warning: yt-dlp timed out for {url}", file=sys.stderr)
            continue

        if result.returncode != 0 or not result.stdout.strip():
            print(f"warning: yt-dlp failed for {url}: {result.stderr.strip()}",
                  file=sys.stderr)
            continue

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue

        enriched[url] = {
            "channel": data.get("channel"),
            "duration": data.get("duration"),
            "view_count": data.get("view_count"),
        }
    return enriched


def _normalize_youtube(
    raw: list[dict[str, Any]],
    enriched: dict[str, dict[str, Any]] | None,
    cap: int,
) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    out: list[dict[str, Any]] = []
    for entry in raw:
        url = entry.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        item = {
            "url": url,
            "title": entry.get("title", ""),
            "channel": None,
            "duration_sec": None,
            "views": None,
            "source": "search",
        }
        if enriched and url in enriched:
            e = enriched[url]
            item["channel"] = e.get("channel")
            item["duration_sec"] = e.get("duration")
            item["views"] = e.get("view_count")
            item["source"] = "yt-dlp"
        out.append(item)
        if len(out) >= cap:
            break
    return out


def _normalize_simple(
    raw: list[dict[str, Any]], cap: int, snippet_key: str = "snippet"
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for entry in raw:
        url = entry.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({
            "url": url,
            "title": entry.get("title", ""),
            "snippet": entry.get(snippet_key, ""),
        })
        if len(out) >= cap:
            break
    return out


def _normalize_pdf(raw: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for entry in raw:
        url = entry.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({
            "url": url,
            "title": entry.get("title", ""),
            "size_hint": entry.get("size_hint"),
        })
        if len(out) >= cap:
            break
    return out


def merge_results(
    *,
    topic: str,
    queries: list[str],
    youtube_results: list[dict[str, Any]],
    web_results: list[dict[str, Any]],
    pdf_results: list[dict[str, Any]],
    max_per_channel: int,
    enriched_youtube: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "queries": queries,
        "youtube": _normalize_youtube(youtube_results, enriched_youtube, max_per_channel),
        "web": _normalize_simple(web_results, max_per_channel),
        "pdf": _normalize_pdf(pdf_results, max_per_channel),
    }


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge discovery results")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pm = sub.add_parser("merge")
    pm.add_argument("--topic", required=True)
    pm.add_argument("--queries-json", required=True,
                    help="JSON file: list of query strings")
    pm.add_argument("--youtube-results", required=True)
    pm.add_argument("--web-results", required=True)
    pm.add_argument("--pdf-results", required=True)
    pm.add_argument("--enrich-youtube", action="store_true")
    pm.add_argument("--max-per-channel", type=int, default=10)

    args = parser.parse_args()

    if args.cmd == "merge":
        yt = _read_json(args.youtube_results)
        web = _read_json(args.web_results)
        pdf = _read_json(args.pdf_results)
        queries = _read_json(args.queries_json)
        enriched = None
        if args.enrich_youtube:
            urls = [e["url"] for e in yt if "url" in e]
            enriched = enrich_youtube(urls)
        out = merge_results(
            topic=args.topic, queries=queries,
            youtube_results=yt, web_results=web, pdf_results=pdf,
            max_per_channel=args.max_per_channel,
            enriched_youtube=enriched,
        )
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
