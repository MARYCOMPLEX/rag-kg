#!/usr/bin/env python
"""Export the FastAPI OpenAPI schema to docs/openapi.json.

Run with `uv run python scripts/export_openapi.py`. Idempotent — only
writes when the resulting JSON differs, so it plays well with CI's
`git diff --exit-code` check.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from apps.api.main import app  # noqa: PLC0415 — script-only entry

    schema = app.openapi()
    payload = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    out = ROOT / "docs" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.exists() and out.read_text(encoding="utf-8") == payload:
        print(f"openapi: no change ({len(payload)} bytes)")
        return 0
    out.write_text(payload, encoding="utf-8")
    print(f"openapi: wrote {out} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
