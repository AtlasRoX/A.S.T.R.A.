"""Tiny helpers for the NASA fetch scripts.

Standard library only: the fetch scripts run on a developer machine with
`uv run --no-project python -I scripts/fetch/<name>.py`, never on the spacecraft.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Identify the client plainly. CCMC's DONKI API answers HTTP 403 to a User-Agent that carries an
# e-mail address (checked 2026-11-09), so keep this free of contact details.
USER_AGENT = "astra-fetch/1.0 (NASA Space Apps 2026 prototype)"
TIMEOUT_S = 120

# engine/data/nasa/  (repo root is the parent of scripts/)
ROOT = Path(__file__).resolve().parents[2]
NASA_DIR = ROOT / "engine" / "data" / "nasa"


def _load_env_file() -> None:
    """Read scripts/.env (git-ignored) into os.environ, without overriding variables already set."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def get_url(url: str, params: dict[str, Any] | None = None) -> str:
    """Fetch a URL and return the body as text. Raises on any HTTP or network error."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - fixed NASA endpoints
        return resp.read().decode("utf-8", errors="replace")


def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """Fetch a URL and parse it as JSON."""
    return json.loads(get_url(url, params))


def write_json(rel_path: str, payload: Any) -> Path:
    """Write a fixture under engine/data/nasa/ and return its path."""
    path = NASA_DIR / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    kb = path.stat().st_size / 1024
    print(f"wrote {path.relative_to(ROOT)} ({kb:.1f} KB)")
    if kb > 500:
        print(f"WARNING: {rel_path} is over the 500 KB fixture budget")
    return path


def write_text(rel_path: str, text: str) -> Path:
    path = NASA_DIR / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.1f} KB)")
    return path


def die(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")
