"""The source registry: the manifest of NASA sources and the fixtures behind them.

Every NASA number ASTRA shows comes from a fixture file listed in `manifest.json`. A source
entry names the agency, what it is used for, which hazards it touches and where it came from,
so the UI can show a citation next to every value and the team can re-fetch the data.

The data directory defaults to `engine/data/nasa/` and can be pointed elsewhere with the
`ASTRA_NASA_DATA` environment variable (the tests use this to load a small fixture set).
"""

from __future__ import annotations

import csv
import json
import os
import threading
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "nasa"
DATA_DIR_ENV = "ASTRA_NASA_DATA"

ROLES = ("threshold", "context", "replay", "evidence")
STATUSES = ("ready", "pending", "error")
SLOTS = ("A", "B", "C")


class RegistryError(RuntimeError):
    """Raised when the manifest or one of its fixtures is missing or malformed."""


def default_data_dir() -> Path:
    """The data directory: `ASTRA_NASA_DATA` if set, otherwise the committed fixtures."""
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override).expanduser().resolve() if override else DEFAULT_DATA_DIR


class Registry:
    """Reads `manifest.json` and the fixture files it points at."""

    def __init__(self, data_dir: Path | str | None = None, *, strict: bool = True) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        self.manifest_path = self.data_dir / "manifest.json"
        self._lock = threading.RLock()
        self._cache: dict[str, Any] = {}
        if not self.manifest_path.exists():
            if strict:
                raise RegistryError(f"NASA manifest not found: {self.manifest_path}")
            self.manifest: dict[str, Any] = {"version": 1, "sources": []}
            return
        try:
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RegistryError(f"NASA manifest is not valid JSON: {self.manifest_path}: {exc}") from exc
        self._by_id = {s["id"]: s for s in self.manifest.get("sources", [])}
        self._validate(strict=strict)

    # ------------------------------------------------------------------ validation
    def _validate(self, *, strict: bool) -> None:
        for src in self.manifest.get("sources", []):
            sid = src.get("id")
            if not sid:
                raise RegistryError("Every manifest source needs an 'id'")
            if src.get("role") not in ROLES:
                raise RegistryError(f"Source '{sid}' has an unknown role '{src.get('role')}' (expected one of {ROLES})")
            if src.get("status") not in STATUSES:
                raise RegistryError(f"Source '{sid}' has an unknown status '{src.get('status')}'")
            slot = src.get("slot")
            if slot is not None and slot not in SLOTS:
                raise RegistryError(f"Source '{sid}' has an unknown slot '{slot}' (expected one of {SLOTS})")
            if src.get("status") == "ready" and strict:
                for rel in src.get("files", []):
                    if not (self.data_dir / rel).exists():
                        raise RegistryError(
                            f"NASA source '{sid}' is marked ready but its file is missing: {self.data_dir / rel}"
                        )

    # ------------------------------------------------------------------ accessors
    def sources(self) -> list[dict[str, Any]]:
        """The manifest entries, plus whether each one's files are actually on disk."""
        out = []
        for src in self.manifest.get("sources", []):
            entry = dict(src)
            entry["files_ok"] = all((self.data_dir / rel).exists() for rel in src.get("files", []))
            out.append(entry)
        return out

    def source(self, source_id: str) -> dict[str, Any] | None:
        """One manifest entry by id, or None."""
        src = self._by_id.get(source_id)
        if src is None:
            return None
        entry = dict(src)
        entry["files_ok"] = all((self.data_dir / rel).exists() for rel in src.get("files", []))
        return entry

    def _resolve(self, source_id: str, file: str) -> Path:
        src = self._by_id.get(source_id)
        if src is None:
            raise RegistryError(f"Unknown NASA source '{source_id}'")
        if file not in src.get("files", []):
            raise RegistryError(f"File '{file}' is not listed for NASA source '{source_id}'")
        path = self.data_dir / file
        if not path.exists():
            raise RegistryError(f"NASA fixture is missing: {path}")
        return path

    def json(self, source_id: str, file: str) -> Any:
        """Parse a JSON fixture (cached in memory)."""
        key = f"json:{source_id}:{file}"
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            path = self._resolve(source_id, file)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RegistryError(f"NASA fixture is not valid JSON: {path}: {exc}") from exc
            self._cache[key] = data
            return data

    def csv(self, source_id: str, file: str) -> list[dict[str, Any]]:
        """Read a CSV fixture as a list of row dicts (cached in memory)."""
        key = f"csv:{source_id}:{file}"
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            path = self._resolve(source_id, file)
            with path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self._cache[key] = rows
            return rows

    def has(self, source_id: str, file: str) -> bool:
        """Whether a fixture exists, without raising."""
        src = self._by_id.get(source_id)
        if src is None or file not in src.get("files", []):
            return False
        return (self.data_dir / file).exists()


def load(data_dir: Path | str | None = None, *, strict: bool = True) -> Registry:
    """Load the registry (from `data_dir`, or the default / `ASTRA_NASA_DATA` location)."""
    return Registry(data_dir, strict=strict)
