"""Topic → filesystem-safe slug."""
import argparse
import re
import sys
import unicodedata

MAX_LEN = 60


def slugify(text: str) -> str:
    if not text or not text.strip():
        raise ValueError("Empty input")

    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()

    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    trimmed = cleaned.strip("-")

    if not trimmed:
        raise ValueError(f"No alphanumerics in input: {text!r}")

    if len(trimmed) > MAX_LEN:
        trimmed = trimmed[:MAX_LEN].rstrip("-")

    return trimmed


def main() -> int:
    parser = argparse.ArgumentParser(description="Topic → slug")
    parser.add_argument("text", help="Text to slugify")
    args = parser.parse_args()
    try:
        print(slugify(args.text))
        return 0
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
