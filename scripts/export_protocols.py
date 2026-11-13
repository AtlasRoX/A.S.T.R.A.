"""Export the emergency protocols to web/public/emergency-protocols.json.

The web app shows these read-only when ASTRA Core is not running, so the crew can still read the
steps. The file is a copy of engine/app/catalog.py PROTOCOLS: change the catalog, then re-run

    cd engine && uv run python ../scripts/export_protocols.py

An engine test (tests/test_offline_protocols.py) fails if the copy is out of date.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from app.catalog import PROTOCOLS  # noqa: E402

OUT = ROOT / "web" / "public" / "emergency-protocols.json"


def main() -> None:
    OUT.write_text(json.dumps(PROTOCOLS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.1f} KB, {len(PROTOCOLS)} protocols)")


if __name__ == "__main__":
    main()
