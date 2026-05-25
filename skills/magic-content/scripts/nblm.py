"""Wrapper over the already-authenticated `notebooklm` CLI.

Discovered CLI surface (Step 1 — verified against the installed CLI):

    notebooklm create TITLE [--json]
        Positional title; no --name flag.
        Returns {"notebook": {"id": "...", "title": "...", ...}}.

    notebooklm source add CONTENT [-n/--notebook NB] [--type ...] [--title ...]
                                   [--mime-type ...] [--json]
        Positional content; type auto-detected (url / text / file / youtube).

    notebooklm source list [-n/--notebook NB] [--json]
        Returns {"notebook_id", "sources": [{"id","status","title",...}]}.
        Status values seen: "ready", "processing" (others may appear).

    notebooklm source wait SOURCE_ID [-n/--notebook NB] [--timeout N] [--json]
        Per-source wait — not used here; we poll `source list` for whole-batch.

    notebooklm generate <type> [DESCRIPTION] [-n/--notebook NB] [--json]
                                [--wait/--no-wait] [--format ...]
        <type> is a subcommand: audio, video, slide-deck, quiz, flashcards,
        infographic, data-table, mind-map, report, cinematic-video.
        Note: "briefing" is NOT a CLI type — it maps to `report --format
        briefing-doc`. We pass the requested type through verbatim and let
        unknown types fail loudly (the wrapper does not silently rewrite).
        Defaults to --no-wait so generation is async; poll via artifact wait.

    notebooklm download <type> [OUTPUT_PATH] [-n/--notebook NB]
                                [--latest|--earliest|--all] [--json] [--force]
        <type> is a subcommand. OUTPUT_PATH is a positional file or directory.
        For --all, OUTPUT_PATH must be a directory.

Adaptations from the original plan:
- create_notebook: title is positional, not --name.
- add_sources: uses `source add` (subgroup) with positional content,
  -n/--notebook, --type. No separate --url/--file flags.
- wait_for_sources: polls `source list --json` and checks every source's
  status == "ready". (Real CLI also has `source wait <id>` per-source; we
  prefer batch polling for the whole-notebook semantic the tests expect.)
- generate_artifacts: invokes `generate <type>` (subcommand), not
  `generate --type <t>`. Returns whatever JSON the CLI emits per type.
- download_artifacts: the CLI requires a per-type subcommand. To download
  "all artifacts of a notebook" we iterate over a fixed list of artifact
  types and call `download <type> --all <dest> --json --force` for each,
  swallowing per-type "no artifacts" failures. The tests stub a single
  call returning {"files": [...]}, so we keep a single-call codepath when
  a `types` argument is supplied; default behavior for the CLI entrypoint
  walks all types.

Output convention: every public function returns a Python dict.
On hard failure: raises NblmError or AuthExpiredError.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

POLL_INTERVAL = 5
DEFAULT_TIMEOUT = 300

# Artifact types supported by `notebooklm download <type>`.
_DOWNLOADABLE_TYPES = (
    "audio", "video", "slide-deck", "infographic", "report",
    "mind-map", "data-table", "quiz", "flashcards", "cinematic-video",
)


class NblmError(RuntimeError):
    pass


class AuthExpiredError(NblmError):
    """Raised when the CLI reports an authentication failure."""


_AUTH_MARKERS = (
    "authentication expired",
    "not authenticated",
    "please run notebooklm login",
    "auth required",
)


def _run(cmd: list[str], *, timeout: int = 60) -> dict[str, Any]:
    """Run a notebooklm CLI command. Raises on auth/failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError as e:
        raise NblmError(
            f"`notebooklm` CLI not found on PATH: {e}. "
            "Install with: pip install notebooklm-py"
        )

    stderr_lower = (result.stderr or "").lower()
    if any(marker in stderr_lower for marker in _AUTH_MARKERS):
        raise AuthExpiredError(
            "NotebookLM authentication expired. Run: notebooklm login"
        )

    if result.returncode != 0:
        raise NblmError(
            f"notebooklm failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"_raw_stdout": result.stdout}


def create_notebook(name: str) -> str:
    """Create a notebook, return its ID. `name` becomes the notebook title."""
    out = _run(["notebooklm", "create", name, "--json"])
    # Real CLI returns {"notebook": {"id": "...", ...}}; older / mocked
    # shape may return {"notebook_id": "..."} or {"id": "..."}.
    nb_id = (
        out.get("notebook_id")
        or out.get("id")
        or (out.get("notebook") or {}).get("id")
    )
    if not nb_id:
        raise NblmError(f"create did not return a notebook_id: {out}")
    return nb_id


def add_sources(
    notebook_id: str, sources: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Add each source individually via `source add`; collect added/failed.

    Each source dict: {"type": "url"|"youtube"|"file"|"text", "value": str,
                       optional "title": str}.
    """
    added: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for src in sources:
        kind = src.get("type", "url")
        value = src["value"]
        cmd = [
            "notebooklm", "source", "add", value,
            "-n", notebook_id, "--type", kind, "--json",
        ]
        if src.get("title"):
            cmd += ["--title", src["title"]]
        try:
            out = _run(cmd, timeout=120)
            added.append({"input": src, "result": out})
        except NblmError as e:
            failed.append({"input": src, "error": str(e)})
    return {"added": added, "failed": failed}


def wait_for_sources(
    notebook_id: str, *, timeout: int = DEFAULT_TIMEOUT,
    poll_interval: int = POLL_INTERVAL,
) -> dict[str, Any]:
    """Poll `source list` until every source reports status == 'ready'."""
    start = time.monotonic()
    while True:
        out = _run([
            "notebooklm", "source", "list", "-n", notebook_id, "--json",
        ])
        sources = out.get("sources", [])
        if sources and all(s.get("status") == "ready" for s in sources):
            return {"ready": True}

        if time.monotonic() - start > timeout:
            return {"ready": False, "error": "timeout",
                    "notebook_id": notebook_id}
        time.sleep(poll_interval)


def generate_artifacts(
    notebook_id: str, types: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Trigger generation for each artifact type via `generate <type>`.

    Generation is async on NotebookLM's side; this returns the artifact IDs
    (when present) so the caller can poll/download later.
    """
    artifacts: list[dict[str, Any]] = []
    for t in types:
        out = _run([
            "notebooklm", "generate", t,
            "-n", notebook_id, "--json", "--no-wait",
        ], timeout=120)
        artifacts.append({
            "type": t,
            "id": out.get("artifact_id") or out.get("id"),
            "raw": out,
        })
    return {"artifacts": artifacts}


def download_artifacts(
    notebook_id: str, dest: Path, types: list[str] | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Download artifacts of `notebook_id` into `dest`.

    The real CLI requires a per-type subcommand. If `types` is provided with
    a single entry the wrapper makes a single CLI call (matching the test
    stub). Otherwise it walks all known downloadable types and merges any
    `files` lists each invocation reports.
    """
    dest.mkdir(parents=True, exist_ok=True)

    if types is not None and len(types) == 1:
        out = _run([
            "notebooklm", "download", types[0], str(dest),
            "-n", notebook_id, "--all", "--json", "--force",
        ], timeout=600)
        return {"files": out.get("files", [])}

    walk = types or list(_DOWNLOADABLE_TYPES)
    files: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for t in walk:
        try:
            out = _run([
                "notebooklm", "download", t, str(dest),
                "-n", notebook_id, "--all", "--json", "--force",
            ], timeout=600)
        except NblmError:
            # No artifacts of this type, or per-type CLI error: skip.
            continue
        for f in out.get("files", []):
            key = f.get("path") or json.dumps(f, sort_keys=True)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            files.append(f)
    return {"files": files}


# ---- CLI ----

def _err_json(e: Exception) -> dict[str, str]:
    if isinstance(e, AuthExpiredError):
        return {"error": "auth_expired", "hint": "run: notebooklm login"}
    return {"error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="notebooklm CLI wrapper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("create")
    pc.add_argument("--name", required=True)

    pa = sub.add_parser("add-sources")
    pa.add_argument("--notebook", required=True)
    pa.add_argument("--sources-json", required=True,
                    help="JSON file: list of {type, value}")

    pw = sub.add_parser("wait")
    pw.add_argument("--notebook", required=True)
    pw.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)

    pg = sub.add_parser("generate")
    pg.add_argument("--notebook", required=True)
    pg.add_argument("--types", required=True,
                    help="Comma-separated artifact types")

    pd = sub.add_parser("download")
    pd.add_argument("--notebook", required=True)
    pd.add_argument("--dest", required=True)
    pd.add_argument("--types", default=None,
                    help="Comma-separated artifact types (default: all)")

    args = parser.parse_args()

    try:
        if args.cmd == "create":
            print(json.dumps({"notebook_id": create_notebook(args.name)}))
        elif args.cmd == "add-sources":
            sources = json.loads(Path(args.sources_json).read_text())
            print(json.dumps(add_sources(args.notebook, sources), indent=2))
        elif args.cmd == "wait":
            print(json.dumps(
                wait_for_sources(args.notebook, timeout=args.timeout)
            ))
        elif args.cmd == "generate":
            types = [t.strip() for t in args.types.split(",") if t.strip()]
            print(json.dumps(generate_artifacts(args.notebook, types), indent=2))
        elif args.cmd == "download":
            types = None
            if args.types:
                types = [t.strip() for t in args.types.split(",") if t.strip()]
            print(json.dumps(
                download_artifacts(args.notebook, Path(args.dest), types),
                indent=2,
            ))
        return 0
    except (NblmError, AuthExpiredError) as e:
        print(json.dumps(_err_json(e)), file=sys.stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
