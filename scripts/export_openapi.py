"""Fetch the live OpenAPI schema from a running openzync-core instance.

Regenerate the checked-in snapshot used for SDK↔backend drift review::

    python scripts/export_openapi.py [--base-url http://localhost:8000]
                                     [--out src/openzync/_openapi.json]

Never imported at runtime — developer tooling only.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "src" / "openzync" / "_openapi.json"


def main() -> None:
    """Fetch ``/openapi.json`` from core and write it to the snapshot path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/openapi.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 — local dev tool
            schema = json.load(resp)
    except OSError as exc:
        print(f"cannot reach core at {url}: {exc}", file=sys.stderr)
        print("is openzync-core running (make dev)?", file=sys.stderr)
        raise SystemExit(1) from exc

    out = Path(args.out)
    out.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {out} ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
