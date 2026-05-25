"""Manifest read/write for raw/notebooklm/<slug>/manifest.json."""
import argparse
import json
import sys
from pathlib import Path
from typing import Any


def resolve_slug_dir(raw_root: Path, slug: str) -> Path:
    """Return slug dir path, suffixing -2/-3/... on collision. Does not create."""
    candidate = raw_root / slug
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = raw_root / f"{slug}-{n}"
        if not candidate.exists():
            return candidate
        n += 1


def write_manifest(
    *,
    raw_root: Path,
    topic: str,
    slug: str,
    queries: list[str],
    sources: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    notebook_id: str,
    date: str,
) -> Path:
    """Write manifest.json under a fresh (collision-suffixed) slug dir."""
    out_dir = resolve_slug_dir(raw_root, slug)
    out_dir.mkdir(parents=True, exist_ok=False)

    final_slug = out_dir.name
    payload = {
        "topic": topic,
        "slug": final_slug,
        "date": date,
        "notebook_id": notebook_id,
        "queries_used": queries,
        "sources": sources,
        "artifacts": artifacts,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    return out_dir


def read_manifest(slug_dir: Path) -> dict[str, Any]:
    """Read manifest.json from an existing slug dir."""
    path = slug_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No manifest at {path}")
    return json.loads(path.read_text())


def _cmd_write(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.input_json).read_text())
    out = write_manifest(
        raw_root=Path(args.raw_root),
        topic=payload["topic"],
        slug=payload["slug"],
        queries=payload["queries"],
        sources=payload["sources"],
        artifacts=payload["artifacts"],
        notebook_id=payload["notebook_id"],
        date=payload["date"],
    )
    print(json.dumps({"slug_dir": str(out), "slug": out.name}))
    return 0


def _cmd_read(args: argparse.Namespace) -> int:
    data = read_manifest(Path(args.slug_dir))
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manifest write/read")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pw = sub.add_parser("write")
    pw.add_argument("--raw-root", required=True,
                    help="Path to raw/notebooklm/ directory")
    pw.add_argument("--input-json", required=True,
                    help="JSON file with topic/slug/queries/sources/artifacts/notebook_id/date")
    pw.set_defaults(func=_cmd_write)

    pr = sub.add_parser("read")
    pr.add_argument("--slug-dir", required=True)
    pr.set_defaults(func=_cmd_read)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
