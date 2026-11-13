"""The offline copy of the emergency protocols must match the catalog."""

from __future__ import annotations

import json
from pathlib import Path

from app.catalog import PROTOCOLS

COPY = Path(__file__).resolve().parents[2] / "web" / "public" / "emergency-protocols.json"


def test_offline_copy_matches_the_catalog():
    assert COPY.is_file(), "run: cd engine && uv run python ../scripts/export_protocols.py"
    assert json.loads(COPY.read_text(encoding="utf-8")) == json.loads(json.dumps(PROTOCOLS)), (
        "web/public/emergency-protocols.json is out of date: re-run scripts/export_protocols.py"
    )


def test_every_protocol_has_readable_steps():
    for proto in PROTOCOLS:
        steps = [*proto["pre"], *[s for t in proto["tracks"] for s in t["steps"]], *proto["post"]]
        assert steps, proto["id"]
        for step in steps:
            assert step["title"], (proto["id"], step)
