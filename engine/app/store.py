"""SQLite persistence and the mission clock.

The mission clock (MET, mission elapsed time) is stored as an anchor: the MET at a given real
moment. It keeps ticking in real time and can be fast-forwarded for demos.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DAY_S = 86400

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL, metric TEXT NOT NULL,
  value REAL NOT NULL, value2 REAL, meta TEXT,
  met_s REAL NOT NULL, day INTEGER NOT NULL,
  task_id TEXT, source TEXT NOT NULL DEFAULT 'manual'
);
CREATE INDEX IF NOT EXISTS ix_readings_crew_day ON readings (crew_id, day);
CREATE INDEX IF NOT EXISTS ix_readings_crew_metric_time ON readings (crew_id, metric, met_s);
CREATE TABLE IF NOT EXISTS xp_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, crew_id TEXT NOT NULL,
  amount INTEGER NOT NULL, reason TEXT NOT NULL, met_s REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS badges (
  crew_id TEXT NOT NULL, badge_id TEXT NOT NULL, met_s REAL NOT NULL,
  PRIMARY KEY (crew_id, badge_id)
);
CREATE TABLE IF NOT EXISTS packets (
  id INTEGER PRIMARY KEY AUTOINCREMENT, crew_id TEXT NOT NULL,
  kind TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 0,
  title TEXT NOT NULL, body TEXT NOT NULL, reply TEXT NOT NULL,
  created_met REAL NOT NULL, delay_s REAL NOT NULL, env_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS emergencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT, crew_id TEXT NOT NULL, patient_id TEXT NOT NULL,
  protocol_id TEXT NOT NULL, track TEXT, completed INTEGER NOT NULL,
  duration_s REAL NOT NULL, steps TEXT NOT NULL, met_s REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attention_acks (
  key TEXT PRIMARY KEY, crew_id TEXT NOT NULL, state TEXT NOT NULL,
  by_crew_id TEXT, at_met REAL, resolved_by TEXT, resolved_at REAL, note TEXT
);
"""


def day_of(met_s: float) -> int:
    return int(met_s // DAY_S) + 1


def met_of(day: int, seconds_of_day: float) -> float:
    return (day - 1) * DAY_S + seconds_of_day


def hhmm_to_s(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 3600 + int(m) * 60


def utc_of(met_s: float, launch_utc: str) -> datetime:
    """The real UTC moment a mission-elapsed time falls on.

    `met_s` counts seconds since launch; `launch_utc` is the ISO-8601 launch timestamp, which
    anchors the mission clock to the real calendar.
    """
    launch = datetime.fromisoformat(launch_utc.replace("Z", "+00:00"))
    return launch + timedelta(seconds=met_s)


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---- query helper: one shared connection, so every access (reads too) goes through the lock ----
    def _all(self, sql: str, args: tuple[Any, ...] | list[Any] = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    def _one(self, sql: str, args: tuple[Any, ...] | list[Any] = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute(sql, args).fetchone()

    # ---- meta & clock -----------------------------------------------------------------------
    def meta_get(self, key: str, default: str | None = None) -> str | None:
        row = self._one("SELECT value FROM meta WHERE key = ?", (key,))
        return row["value"] if row else default

    def meta_set(self, key: str, value: str) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self.conn.commit()

    def set_clock(self, met_s: float) -> None:
        self.meta_set("clock_met", repr(float(met_s)))
        self.meta_set("clock_real", repr(time.time()))

    def met_now(self) -> float:
        with self.lock:
            met = float(self.meta_get("clock_met", "0") or 0)
            real = float(self.meta_get("clock_real", repr(time.time())) or time.time())
        return met + (time.time() - real)

    def advance(self, seconds: float) -> float:
        with self.lock:
            now = self.met_now() + seconds
            self.set_clock(now)
        return now

    # ---- readings -----------------------------------------------------------------------------
    def add_reading(self, crew_id: str, metric: str, value: float, value2: float | None,
                    meta: dict[str, Any] | None, met_s: float, task_id: str | None,
                    source: str = "manual") -> int:
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO readings (crew_id, metric, value, value2, meta, met_s, day, task_id, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (crew_id, metric, value, value2, json.dumps(meta) if meta else None, met_s, day_of(met_s),
                 task_id, source),
            )
            self.conn.commit()
            return int(cur.lastrowid or 0)

    def add_readings_bulk(self, rows: list[tuple[Any, ...]]) -> None:
        with self.lock:
            self.conn.executemany(
                "INSERT INTO readings (crew_id, metric, value, value2, meta, met_s, day, task_id, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            self.conn.commit()

    def recent_real_values(self, crew_id: str, metric: str, limit: int = 5) -> list[tuple[float, float | None]]:
        """The newest (value, value2) pairs of one metric that a person (or the seed) recorded, not the simulator."""
        rows = self._all(
            "SELECT value, value2 FROM readings WHERE crew_id = ? AND metric = ? AND source != 'sim' "
            "ORDER BY met_s DESC, id DESC LIMIT ?",
            (crew_id, metric, limit),
        )
        return [(float(r["value"]), None if r["value2"] is None else float(r["value2"])) for r in rows]

    def prune_sim_readings(self, before_met_s: float) -> int:
        """Delete simulated readings older than before_met_s: background telemetry keeps a rolling window."""
        with self.lock:
            cur = self.conn.execute("DELETE FROM readings WHERE source = 'sim' AND met_s < ?", (before_met_s,))
            self.conn.commit()
            return int(cur.rowcount or 0)

    def readings(self, crew_id: str, since_day: int, until_met: float | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM readings WHERE crew_id = ? AND day >= ?"
        args: list[Any] = [crew_id, since_day]
        if until_met is not None:
            q += " AND met_s <= ?"
            args.append(until_met)
        q += " ORDER BY met_s ASC, id ASC"
        rows = self._all(q, args)
        out = []
        for r in rows:
            d = dict(r)
            d["meta"] = json.loads(d["meta"]) if d["meta"] else None
            out.append(d)
        return out

    # ---- xp & badges ----------------------------------------------------------------------------
    def add_xp(self, crew_id: str, amount: int, reason: str, met_s: float) -> None:
        with self.lock:
            self.conn.execute("INSERT INTO xp_events (crew_id, amount, reason, met_s) VALUES (?, ?, ?, ?)",
                              (crew_id, amount, reason, met_s))
            self.conn.commit()

    def xp_events(self, crew_id: str, limit: int = 60) -> list[dict[str, Any]]:
        """The XP ledger, newest first: every award with its reason and mission time."""
        rows = self._all("SELECT id, amount, reason, met_s FROM xp_events WHERE crew_id = ? "
                         "ORDER BY met_s DESC, id DESC LIMIT ?", (crew_id, limit))
        return [dict(r) for r in rows]

    def xp_reason_exists(self, crew_id: str, reason: str) -> bool:
        row = self._one("SELECT 1 FROM xp_events WHERE crew_id = ? AND reason = ? LIMIT 1", (crew_id, reason))
        return row is not None

    def xp_sum(self, crew_id: str) -> int:
        row = self._one("SELECT COALESCE(SUM(amount), 0) AS s FROM xp_events WHERE crew_id = ?", (crew_id,))
        return int(row["s"]) if row else 0

    def add_badge(self, crew_id: str, badge_id: str, met_s: float) -> bool:
        with self.lock:
            cur = self.conn.execute("INSERT OR IGNORE INTO badges (crew_id, badge_id, met_s) VALUES (?, ?, ?)",
                                    (crew_id, badge_id, met_s))
            self.conn.commit()
            return cur.rowcount > 0

    def stored_badges(self, crew_id: str) -> set[str]:
        rows = self._all("SELECT badge_id FROM badges WHERE crew_id = ?", (crew_id,))
        return {r["badge_id"] for r in rows}

    def badge_events(self, crew_id: str, since_met: float) -> list[dict[str, Any]]:
        """Badges earned since a mission time, with the moment each was earned."""
        rows = self._all("SELECT badge_id, met_s FROM badges WHERE crew_id = ? AND met_s >= ? ORDER BY met_s DESC",
                         (crew_id, since_met))
        return [dict(r) for r in rows]

    # ---- packets ----------------------------------------------------------------------------------
    def add_packet(self, crew_id: str, kind: str, priority: int, title: str, body: str, reply: str,
                   created_met: float, delay_s: float, env_id: str) -> int:
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO packets (crew_id, kind, priority, title, body, reply, created_met, delay_s, env_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (crew_id, kind, priority, title, body, reply, created_met, delay_s, env_id),
            )
            self.conn.commit()
            return int(cur.lastrowid or 0)

    def packets(self, crew_id: str | None = None, limit: int = 40) -> list[dict[str, Any]]:
        if crew_id:
            rows = self._all("SELECT * FROM packets WHERE crew_id = ? ORDER BY created_met DESC, id DESC LIMIT ?",
                             (crew_id, limit))
        else:
            rows = self._all("SELECT * FROM packets ORDER BY created_met DESC, id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    # ---- emergencies -------------------------------------------------------------------------------
    def add_emergency(self, crew_id: str, patient_id: str, protocol_id: str, track: str | None,
                      completed: bool, duration_s: float, steps: list[dict[str, Any]], met_s: float) -> int:
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO emergencies "
                "(crew_id, patient_id, protocol_id, track, completed, duration_s, steps, met_s) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (crew_id, patient_id, protocol_id, track, int(completed), duration_s, json.dumps(steps), met_s),
            )
            self.conn.commit()
            return int(cur.lastrowid or 0)

    def finish_emergency(self, emergency_id: int, track: str | None, completed: bool, duration_s: float,
                         steps: list[dict[str, Any]]) -> dict[str, Any] | None:
        with self.lock:
            self.conn.execute(
                "UPDATE emergencies SET track = ?, completed = ?, duration_s = ?, steps = ? WHERE id = ?",
                (track, int(completed), duration_s, json.dumps(steps), emergency_id),
            )
            self.conn.commit()
        row = self._one("SELECT * FROM emergencies WHERE id = ?", (emergency_id,))
        return dict(row) if row else None

    # ---- attention ---------------------------------------------------------------------------------
    def attention_ack(self, key: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM attention_acks WHERE key = ?", (key,))
        return dict(row) if row else None

    def attention_acks(self, crew_id: str | None = None) -> list[dict[str, Any]]:
        if crew_id:
            rows = self._all("SELECT * FROM attention_acks WHERE crew_id = ? OR crew_id = 'all'", (crew_id,))
        else:
            rows = self._all("SELECT * FROM attention_acks")
        return [dict(r) for r in rows]

    def set_attention_open(self, key: str, crew_id: str) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR IGNORE INTO attention_acks (key, crew_id, state) VALUES (?, ?, 'open')",
                (key, crew_id),
            )
            self.conn.commit()

    def set_attention_ack(self, key: str, crew_id: str, by_crew_id: str, met_s: float) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO attention_acks (key, crew_id, state, by_crew_id, at_met) "
                "VALUES (?, ?, 'acknowledged', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "state = 'acknowledged', by_crew_id = excluded.by_crew_id, at_met = excluded.at_met",
                (key, crew_id, by_crew_id, met_s),
            )
            self.conn.commit()

    def set_attention_resolved(self, key: str, crew_id: str, resolved_by: str, met_s: float,
                               note: str | None = None) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO attention_acks (key, crew_id, state, by_crew_id, at_met, resolved_by, resolved_at, note) "
                "VALUES (?, ?, 'resolved', NULL, NULL, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "state = 'resolved', resolved_by = excluded.resolved_by, "
                "resolved_at = excluded.resolved_at, note = excluded.note",
                (key, crew_id, resolved_by, met_s, note),
            )
            self.conn.commit()

    def attention_unresolved(self, crew_id: str | None = None) -> list[dict[str, Any]]:
        if crew_id:
            q = ("SELECT * FROM attention_acks WHERE (crew_id = ? OR crew_id = 'all') "
                 "AND state IN ('open', 'acknowledged')")
            rows = self._all(q, (crew_id,))
        else:
            rows = self._all("SELECT * FROM attention_acks WHERE state IN ('open', 'acknowledged')")
        return [dict(r) for r in rows]

    def attention_history(self, crew_id: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
        if crew_id:
            rows = self._all(
                "SELECT * FROM attention_acks WHERE (crew_id = ? OR crew_id = 'all') AND state = 'resolved' "
                "ORDER BY resolved_at DESC LIMIT ?",
                (crew_id, limit),
            )
        else:
            rows = self._all(
                "SELECT * FROM attention_acks WHERE state = 'resolved' ORDER BY resolved_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in rows]

    # ---- maintenance -------------------------------------------------------------------------------
    def wipe(self) -> None:
        with self.lock:
            for t in ("readings", "xp_events", "badges", "packets", "emergencies", "attention_acks", "meta"):
                self.conn.execute(f"DELETE FROM {t}")  # noqa: S608 - fixed table names
            self.conn.commit()
