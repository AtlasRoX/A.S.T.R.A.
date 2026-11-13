"""Live Simulation Engine for ASTRA.

Simulates real telemetry and astronaut physiology in real time (e.g. every 10s, 30s, or 60s),
persisting readings into SQLite so the live mission dashboard dynamically updates.
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from collections.abc import Callable
from statistics import median
from typing import Any

from .catalog import CREW, METRIC_BY_ID
from .store import Store

# Background telemetry keeps simulated readings for this long (mission seconds), so a long-running engine does
# not pile up a reading a minute per crew member forever. Real (manual and seeded) readings are never pruned.
SIM_KEEP_S = 24 * 3600.0

logger = logging.getLogger("astra.live_sim")

SCENARIOS: dict[str, dict[str, Any]] = {
    "nominal": {
        "id": "nominal",
        "name": "Nominal Vitals & Biometrics",
        "kicker": "Baseline circadian variance",
        "description": (
            "Continuous telemetry with natural physiological variance and sensor jitter "
            "around personal baselines."
        ),
    },
    "exercise": {
        "id": "exercise",
        "name": "Exercise Exertion & Recovery",
        "kicker": "Physical exertion protocol",
        "description": (
            "Multi-phase workout block: heart rate and blood pressure ramp up during peak cardio exertion, "
            "followed by physiological recovery."
        ),
    },
    "cabin_co2": {
        "id": "cabin_co2",
        "name": "Cabin CO2 Scrubber Anomaly",
        "kicker": "NASA ISS Environmental Telemetry",
        "description": (
            "Cabin CO2 climbs past NASA's 3.0 mmHg one-hour limit (Act), causing crew headache symptoms, "
            "before scrubber remediation."
        ),
    },
    "solar_storm": {
        "id": "solar_storm",
        "name": "Solar Particle Storm",
        "kicker": "NASA DONKI Space Weather",
        "description": (
            "A coronal mass ejection drives ionizing radiation rate past warning limits, switching EVA readiness "
            "to No-Go and triggering shelter alerts."
        ),
    },
}


class LiveSimulatorRunner:
    def __init__(self, store: Store, escalate: Callable[[str, list[str]], Any] | None = None) -> None:
        self.store = store
        # Called after each tick with (crew_id, metric ids written), so the rules can raise alerts.
        self.escalate = escalate
        self.active: bool = False
        self.scenario: str = "nominal"
        self.interval_s: float = 30.0
        self.step: int = 0
        # One crew member, or None for the whole crew (the background telemetry started with the engine).
        self.crew_id: str | None = "kenji"
        # Demo runs push the mission clock 60 s per tick to show change fast; background telemetry does not.
        self.advance_clock: bool = True
        # Demo scenarios send packets to the CMO and the ground like real readings. Background telemetry does not:
        # it jitters around each person's own level, so a value sitting at a threshold would page the CMO every few
        # minutes. Real readings (and deliberate scenarios) raise alerts; the background feed only shows data.
        self.raise_alerts: bool = True
        self.last_tick_time: float = 0.0
        self.next_tick_time: float = 0.0
        self.last_event: str = "Simulator idle"
        self.updated_metrics: list[str] = []

        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, scenario: str = "nominal", interval_s: float = 30.0, crew_id: str | None = None, *,
              all_crew: bool = False, advance_clock: bool = True, raise_alerts: bool = True) -> dict[str, Any]:
        with self._lock:
            if scenario not in SCENARIOS:
                scenario = "nominal"
            self.scenario = scenario
            self.interval_s = max(5.0, min(interval_s, 3600.0))
            if all_crew:
                self.crew_id = None
            elif crew_id:
                self.crew_id = crew_id
            self.advance_clock = advance_clock
            self.raise_alerts = raise_alerts
            self.step = 0
            self.active = True
            self.last_tick_time = time.time()
            self.next_tick_time = self.last_tick_time + self.interval_s
            self._stop_event.clear()

            # Execute first step immediately so the user sees results right away
            self._execute_tick()

            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run_loop, daemon=True, name="astra-live-sim")
                self._thread.start()

            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self.active = False
            self._stop_event.set()
            # Clean up transient overrides
            self.store.meta_set("cabin_sim_co2", "")
            self.store.meta_set("sim_rad_rate", "")
            self._clear_sim_solar_event()
            self.last_event = "Simulation paused"
            return self.status()

    def tick(self) -> dict[str, Any]:
        """Manually trigger one tick immediately."""
        with self._lock:
            res = self._execute_tick()
            self.last_tick_time = time.time()
            self.next_tick_time = self.last_tick_time + self.interval_s
            return res

    def status(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            rem = max(0.0, self.next_tick_time - now) if self.active else 0.0
            return {
                "active": self.active,
                "scenario": self.scenario,
                "scenario_info": SCENARIOS.get(self.scenario, SCENARIOS["nominal"]),
                "scenarios": list(SCENARIOS.values()),
                "interval_s": self.interval_s,
                "step": self.step,
                "crew_id": self.crew_id,
                "countdown_s": round(rem, 1),
                "last_event": self.last_event,
                "updated_metrics": list(self.updated_metrics),
            }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(0.5)
            with self._lock:
                if not self.active:
                    break
                now = time.time()
                if now >= self.next_tick_time:
                    try:
                        self._execute_tick()
                    except Exception as e:
                        logger.exception("Error executing simulation tick: %s", e)
                        self.last_event = f"Error: {e}"
                    self.last_tick_time = now
                    self.next_tick_time = now + self.interval_s

    def _execute_tick(self) -> dict[str, Any]:
        self.step += 1
        # Demo runs advance the mission clock 60 s per tick; background telemetry stays on the real clock.
        new_met = self.store.advance(60.0) if self.advance_clock else self.store.met_now()
        self.updated_metrics = []

        # Keep a rolling window of simulated readings (every 30 ticks is plenty; real readings are never touched).
        if self.step % 30 == 1:
            try:
                self.store.prune_sim_readings(new_met - SIM_KEEP_S)
            except Exception:  # noqa: BLE001 - housekeeping must never stop the telemetry
                logger.exception("Could not prune old simulated readings")

        scenario = self.scenario
        if scenario == "exercise":
            self._tick_exercise(new_met)
        elif scenario == "cabin_co2":
            self._tick_cabin_co2(new_met)
        elif scenario == "solar_storm":
            self._tick_solar_storm(new_met)
        else:
            self._tick_nominal(new_met)

        if self.escalate is not None and self.raise_alerts:
            # Nominal telemetry covers the whole crew when no one is picked; the event scenarios follow one person.
            if self.crew_id:
                targets = [self.crew_id]
            elif scenario == "nominal":
                targets = [c["id"] for c in CREW]
            else:
                targets = ["kenji"]
            written = [m for m in self.updated_metrics if m in METRIC_BY_ID]
            for cid in targets:
                try:
                    self.escalate(cid, written)
                except Exception:  # noqa: BLE001 - alerting must never stop the simulation
                    logger.exception("Could not run the rules over simulated readings")

        return self.status()

    def _clear_sim_solar_event(self) -> None:
        """Remove the simulator's storm, but never a replay of a real DONKI event someone started."""
        raw = self.store.meta_get("solar_event")
        if not raw:
            return
        try:
            event_id = json.loads(raw).get("event_id")
        except (json.JSONDecodeError, AttributeError):
            return
        if event_id == "SIM-CME-LIVE":
            self.store.meta_set("solar_event", "")

    def _baseline(self, cid: str, metric: str, default: float) -> tuple[float, float | None]:
        """The crew member's own recent level: the median of their last 5 NON-simulated readings, or a default.

        Nominal telemetry jitters around this, so the simulation keeps a crew member's story (for example Kenji's
        rising blood pressure) instead of generic numbers, while one unusual entry (a typo or a test value such
        as 200 bpm) does not turn into minute-by-minute telemetry.
        """
        recent = self.store.recent_real_values(cid, metric, 5)
        if not recent:
            return default, None
        second = [v2 for _, v2 in recent if v2 is not None]
        return float(median(v for v, _ in recent)), (float(median(second)) if second else None)

    # ---------------------------------------------------------------- Scenarios
    def _tick_nominal(self, met_now: float) -> None:
        """Realistic sensor variance and circadian jitter around baseline."""
        target_crew = [self.crew_id] if self.crew_id else [c["id"] for c in CREW]
        summary_parts = []

        for cid in target_crew:
            hr0, _ = self._baseline(cid, "hr", 64.0)
            sys0, dia0 = self._baseline(cid, "bp", 116.0)
            temp0, _ = self._baseline(cid, "temp", 36.9)
            resp0, _ = self._baseline(cid, "resp", 15.0)
            gluc0, _ = self._baseline(cid, "glucose", 84.0)
            hr = int(round(hr0 + random.gauss(0, 1.8)))
            sys = int(round(sys0 + random.gauss(0, 2.5)))
            dia = int(round((dia0 if dia0 is not None else 76.0) + random.gauss(0, 1.8)))
            temp = round(temp0 + random.gauss(0, 0.06), 2)
            resp = int(round(resp0 + random.gauss(0, 0.8)))
            gluc = round(gluc0 + random.gauss(0, 2.0), 1)

            self.store.add_reading(cid, "hr", float(hr), None, None, met_now, None, source="sim")
            self.store.add_reading(cid, "bp", float(sys), float(dia), None, met_now, None, source="sim")
            self.store.add_reading(cid, "temp", temp, None, None, met_now, None, source="sim")
            self.store.add_reading(cid, "resp", float(resp), None, None, met_now, None, source="sim")
            self.store.add_reading(cid, "glucose", gluc, None, None, met_now, None, source="sim")

            summary_parts.append(f"HR {hr} bpm · BP {sys}/{dia} · {temp}°C")

        self.updated_metrics = ["hr", "bp", "temp", "resp", "glucose"]
        self.last_event = f"Step {self.step}: Nominal telemetry ({summary_parts[0]})"

    def _tick_exercise(self, met_now: float) -> None:
        """Multi-phase workout block: exertion curve followed by physiological recovery."""
        cid = self.crew_id or "kenji"
        phase = (self.step - 1) % 8

        # Curve: [Warmup, Ramp, Peak, Sustained, Cooldown, Recovery 1, Recovery 2, Rest]
        curve = [
            {"hr": 98, "sys": 124, "dia": 80, "resp": 18, "temp": 37.0, "ctx": "after_exercise",
             "lbl": "Warmup initiated"},
            {"hr": 122, "sys": 134, "dia": 82, "resp": 22, "temp": 37.2, "ctx": "after_exercise",
             "lbl": "Aerobic zone reached"},
            {"hr": 148, "sys": 148, "dia": 86, "resp": 26, "temp": 37.4, "ctx": "after_exercise",
             "lbl": "Peak exertion (148 bpm)"},
            {"hr": 154, "sys": 152, "dia": 88, "resp": 28, "temp": 37.5, "ctx": "after_exercise",
             "lbl": "High-intensity sprint"},
            {"hr": 128, "sys": 138, "dia": 82, "resp": 22, "temp": 37.3, "ctx": "after_exercise",
             "lbl": "Active cooldown"},
            {"hr": 104, "sys": 128, "dia": 78, "resp": 18, "temp": 37.1, "ctx": "after_exercise",
             "lbl": "Heart rate recovery underway"},
            {"hr": 82, "sys": 120, "dia": 76, "resp": 16, "temp": 37.0, "ctx": "rest",
             "lbl": "Vitals normalizing"},
            {"hr": 65, "sys": 116, "dia": 76, "resp": 15, "temp": 36.9, "ctx": "rest",
             "lbl": "Resting baseline restored"},
        ]
        cur = curve[phase]
        ctx_meta = {"context": cur["ctx"]}

        self.store.add_reading(cid, "hr", float(cur["hr"]), None, ctx_meta, met_now, None, source="sim")
        self.store.add_reading(cid, "bp", float(cur["sys"]), float(cur["dia"]), ctx_meta, met_now, None, source="sim")
        self.store.add_reading(cid, "resp", float(cur["resp"]), None, ctx_meta, met_now, None, source="sim")
        self.store.add_reading(cid, "temp", float(cur["temp"]), None, None, met_now, None, source="sim")
        self.store.add_reading(cid, "exercise", float(30 + phase * 12), None, None, met_now, "exercise", source="sim")

        self.updated_metrics = ["hr", "bp", "resp", "temp", "exercise"]
        self.last_event = (
            f"Step {self.step} (Workout {phase + 1}/8): {cur['lbl']} — "
            f"HR {cur['hr']} bpm, BP {cur['sys']}/{cur['dia']}"
        )

    def _tick_cabin_co2(self, met_now: float) -> None:
        """NASA ISS EDA CO2 curve: elevated CO2 crossing Watch/Act thresholds with headache symptom."""
        cid = self.crew_id or "kenji"
        phase = (self.step - 1) % 7

        # CO2 curve in mmHg. NASA-STD-3001 Vol 2 caps the one-hour average at 3.0 mmHg (Act); the labels
        # below follow the same rule the app applies (rules.cabin_status), not invented limits.
        co2_curve = [
            (2.4, False, "CO2 normal at 2.4 mmHg"),
            (2.9, False, "CO2 rising at 2.9 mmHg, just under the 3.0 mmHg limit"),
            (3.4, True, "Act: CO2 at 3.4 mmHg is above the 3.0 mmHg limit · Mild headache"),
            (4.6, True, "Act: CO2 at 4.6 mmHg · Throbbing headache reported"),
            (3.6, True, "Scrubber working · CO2 dropping to 3.6 mmHg, still above the limit"),
            (2.9, False, "CO2 back under the limit at 2.9 mmHg · Symptoms clearing"),
            (2.2, False, "CO2 nominal at 2.2 mmHg · Atmosphere nominal"),
        ]
        co2_val, has_headache, desc = co2_curve[phase]

        # Set persistent override for cabin telemetry
        self.store.meta_set("cabin_sim_co2", str(co2_val))

        # Log symptom check
        sym_items = ["headache"] if has_headache else []
        self.store.add_reading(
            cid, "symptoms", 1.0 if has_headache else 0.0, None,
            {"items": sym_items}, met_now, None, source="sim"
        )
        # Log respiration reaction
        resp_rate = 15 if not has_headache else 20 if co2_val > 4.5 else 18
        self.store.add_reading(cid, "resp", float(resp_rate), None, None, met_now, None, source="sim")

        self.updated_metrics = ["cabin", "symptoms", "resp"]
        self.last_event = f"Step {self.step}: {desc}"

    def _tick_solar_storm(self, met_now: float) -> None:
        """NASA DONKI space weather solar particle event."""
        phase = (self.step - 1) % 6

        # Rates: [0.68 normal, 4.8 warning, 19.5 peak Act, 16.2 sustained, 5.0 tail, 0.70 clear]
        storm_curve = [
            (0.68, "ok", "go", "Quiet Sun background: 0.68 mSv/day · EVA Go"),
            (4.8, "watch", "caution", "CME arrival shock: 4.8 mSv/day · EVA Caution"),
            (19.5, "act", "nogo", "PEAK STORM FLUX: 19.5 mSv/day · EVA NO-GO · Storm shelter active"),
            (16.2, "act", "nogo", "Sustained high proton flux: 16.2 mSv/day · Storm shelter advised"),
            (5.0, "watch", "caution", "Proton flux subsiding: 5.0 mSv/day · EVA Caution"),
            (0.70, "ok", "go", "Storm passed: 0.70 mSv/day · EVA restored to Go"),
        ]
        rate, status, eva, desc = storm_curve[phase]

        self.store.meta_set("sim_rad_rate", str(rate))
        if status != "ok":
            ev = {
                "event_id": "SIM-CME-LIVE",
                "started_met": met_now - (phase * 600),
                "duration_s": 7200.0,
                "peak_flux": 1450.0,
                "current_rate_msv_day": rate,
                "dose_so_far_msv": round(phase * 0.22, 3),
                "status": status,
                "eva_status": eva,
                "label": f"Solar Particle Storm ({rate} mSv/day)",
            }
            self.store.meta_set("solar_event", json.dumps(ev))
        else:
            self.store.meta_set("solar_event", "")

        self.updated_metrics = ["radiation", "eva"]
        self.last_event = f"Step {self.step}: {desc}"
