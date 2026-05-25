"""Download PDFs to a temp dir; per-URL failure does not abort the batch."""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

CHUNK = 8192
TIMEOUT_SEC = 30


def _safe_filename(url: str, taken: set[str]) -> str:
    base = Path(urlparse(url).path).name or "doc.pdf"
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    candidate = base
    n = 2
    while candidate in taken:
        stem = base[:-4]
        candidate = f"{stem}-{n}.pdf"
        n += 1
    return candidate


def download_pdfs(
    *, urls: list[dict[str, Any]], dest: Path
) -> dict[str, list[dict[str, Any]]]:
    dest.mkdir(parents=True, exist_ok=True)
    taken: set[str] = set()
    downloaded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for entry in urls:
        url = entry["url"]
        try:
            resp = requests.get(url, stream=True, timeout=TIMEOUT_SEC,
                                headers={"User-Agent": "magic-content/0.1"})
            resp.raise_for_status()
            filename = _safe_filename(url, taken)
            taken.add(filename)
            path = dest / filename
            with path.open("wb") as f:
                for chunk in resp.iter_content(CHUNK):
                    if chunk:
                        f.write(chunk)
            downloaded.append({
                "url": url,
                "title": entry.get("title"),
                "path": str(path),
                "size_bytes": path.stat().st_size,
            })
        except Exception as e:
            failed.append({"url": url, "error": str(e)})

    return {"downloaded": downloaded, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Download PDFs to a dest dir")
    parser.add_argument("--urls-json", required=True,
                        help="JSON file: list of {url, title}")
    parser.add_argument("--dest", required=True, help="Destination directory")
    args = parser.parse_args()

    urls = json.loads(Path(args.urls_json).read_text())
    result = download_pdfs(urls=urls, dest=Path(args.dest))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result["failed"] or result["downloaded"] else 1


if __name__ == "__main__":
    sys.exit(main())
