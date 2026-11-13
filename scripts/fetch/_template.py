"""Template for a new NASA fetch script.

Copy this file, rename it to the source id, and fill in the three steps below.
Keep it standard-library only, and never invent a number: if the endpoint does
not answer, fail loudly and leave a TODO(verify) in the manifest note.

Run from the repo root (astra/):
    uv run --no-project python -I scripts/fetch/<name>.py
"""

from __future__ import annotations

from _common import die, get_json, write_json  # noqa: F401 - sibling import, run with -I


def main() -> None:
    # 1. Fetch. Record the exact request URL so the manifest can point at it.
    url = "https://example.nasa.gov/api"
    payload = get_json(url)

    # 2. Reduce to a small fixture: pick the fields ASTRA actually reads.
    rows = [
        {"date": "YYYY-MM-DD", "value": 0.0}
        for row in payload.get("items", [])[:10]
    ]

    # 3. Write it under engine/data/nasa/<source-id>/ and update manifest.json.
    write_json("<source-id>/<file>.json", rows)


if __name__ == "__main__":
    main()
