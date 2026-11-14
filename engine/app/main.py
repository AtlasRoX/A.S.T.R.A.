"""ASTRA Core HTTP API (FastAPI).

Run locally:  uv run uvicorn app.main:app --port 8000 --reload
Docs:         http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import agent, assistant
from .catalog import public_catalog
from .live_sim import LiveSimulatorRunner
from .nasa import Registry, RegistryError
from .nasa import load as load_registry
from .official import official_resources
from .seed import seed
from .services import Engine, EngineError
from .sim import Simulator
from .store import Store

DB_PATH = os.environ.get("ASTRA_DB", str(Path(__file__).resolve().parent.parent / "data" / "astra.db"))


# ---------------------------------------------------------------- request models
class ReadingIn(BaseModel):
    metric: str
    value: float | None = None
    value2: float | None = None
    meta: dict[str, Any] | None = None
    task_id: str | None = None
    env: str | None = None

class AdvanceIn(BaseModel):
    seconds: float = Field(gt=0, le=7 * 86400)

class PerkApproveIn(BaseModel):
    week: int = Field(ge=1)
    days: int = Field(ge=1, le=7)


class ChatTurn(BaseModel):
    role: str
    content: str = Field(max_length=8000)


class AssistantIn(BaseModel):
    crew_id: str
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    env: str | None = None
    page: str | None = Field(default=None, max_length=200)


class MessageIn(BaseModel):
    crew_id: str
    text: str = Field(min_length=1, max_length=600)
    env: str | None = None

class EmergencyStartIn(BaseModel):
    crew_id: str
    patient_id: str
    protocol_id: str
    env: str | None = None

class EmergencyFinishIn(BaseModel):
    crew_id: str
    track: str | None = None
    completed: bool
    duration_s: float = Field(ge=0)
    steps: list[dict[str, Any]] = []
    is_drill: bool = False
    env: str | None = None

class SolarReplayIn(BaseModel):
    event_id: str | None = None

class SimLiveStartIn(BaseModel):
    scenario: str = "nominal"
    interval_s: float = Field(default=30.0, ge=5.0, le=3600.0)
    crew_id: str | None = None

class AttentionAckIn(BaseModel):
    crew_id: str

class AttentionResolveIn(BaseModel):
    crew_id: str
    note: str


def create_app(db_path: str = DB_PATH) -> FastAPI:
    store = Store(db_path)
    if store.meta_get("seeded") != "1":
        seed(store)
    # The NASA registry is read-only and local: it never touches the network. If the manifest
    # is missing we still start, so the crew-facing app keeps working; the /nasa/sources route
    # then reports the problem.
    try:
        nasa = load_registry()
    except RegistryError:
        nasa = Registry(strict=False)
    engine = Engine(store, nasa)
    simulator = Simulator(nasa)
    live_sim = LiveSimulatorRunner(store, escalate=engine.escalate_simulated)
    # Background telemetry: simulated readings for the whole crew (marked as simulated) start with the engine, so
    # every screen has live data and nobody has to start it from a page. ASTRA_LIVE_SIM=off turns it off (the tests
    # do); ASTRA_LIVE_SIM_INTERVAL sets the seconds between readings.
    if os.environ.get("ASTRA_LIVE_SIM", "on").strip().lower() not in ("off", "0", "false", "no"):
        try:
            interval = float(os.environ.get("ASTRA_LIVE_SIM_INTERVAL", "60"))
        except ValueError:
            interval = 60.0
        live_sim.start("nominal", interval, all_crew=True, advance_clock=False, raise_alerts=False)

    app = FastAPI(title="ASTRA Core", version="1.0.0",
                  description="Onboard health engine for long-duration crews: rules, personal baselines, "
                  "escalation, routine, gamification and delay-aware comms.")
    app.state.engine = engine
    app.state.live_sim = live_sim
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"], allow_headers=["*"],
    )

    # On a public host, only the web server may call ASTRA Core: it sends ASTRA_ENGINE_TOKEN in x-astra-token.
    # /health stays open for uptime checks. Unset locally, so development and the tests are unchanged.
    token = os.environ.get("ASTRA_ENGINE_TOKEN", "").strip()
    if token:
        @app.middleware("http")
        async def _require_token(request: Request, call_next):  # type: ignore[no-untyped-def]
            if request.url.path != "/health" and not secrets.compare_digest(
                    request.headers.get("x-astra-token", ""), token):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return await call_next(request)

    @app.exception_handler(EngineError)
    async def _engine_error(_: Request, exc: EngineError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    # ---------------------------------------------------------------- routes
    # HEAD too: uptime monitors (e.g. UptimeRobot) check with HEAD requests.
    @app.api_route("/health", methods=["GET", "HEAD"])
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "astra-core", "clock": engine.clock()}

    @app.get("/catalog")
    def catalog() -> dict[str, Any]:
        # The environments carry today's signal delay (from JPL Horizons) and dose source, so
        # every page that lists them shows the same numbers as the dashboard.
        cat = public_catalog()
        cat["environments"] = [engine.env(e["id"]) for e in cat["environments"]]
        return cat

    @app.get("/clock")
    def clock() -> dict[str, Any]:
        return engine.clock()

    @app.post("/clock/advance")
    def advance(body: AdvanceIn) -> dict[str, Any]:
        store.advance(body.seconds)
        return engine.clock()

    @app.post("/clock/skip-to-conjunction")
    def skip_to_conjunction() -> dict[str, Any]:
        """Demo control: move the mission clock to the start of the solar-conjunction warning."""
        target = engine.conjunction_warning_met()
        if target is None:
            raise EngineError(404, "The Horizons data has no solar conjunction in it")
        now = engine.now()
        if target <= now:
            raise EngineError(409, "The mission clock is already at or past the conjunction warning")
        store.advance(target - now)
        return engine.clock()

    @app.post("/admin/reset")
    def reset() -> dict[str, Any]:
        seed(store)
        # A reset clears any active solar replay, so the demo always starts from a clean state.
        store.meta_set("solar_event", "")
        return {"ok": True, "clock": engine.clock()}

    # ---------------------------------------------------------------- NASA data
    @app.get("/nasa/sources")
    def nasa_sources() -> dict[str, Any]:
        sources = nasa.sources()
        return {
            "sources": sources,
            "counts": {
                "total": len(sources),
                "ready": sum(1 for s in sources if s.get("status") == "ready"),
                "pending": sum(1 for s in sources if s.get("status") == "pending"),
                "slots_pending": sum(1 for s in sources if s.get("slot") and s.get("status") != "ready"),
            },
            "data_dir": str(nasa.data_dir),
        }

    @app.get("/nasa/sources/{source_id}")
    def nasa_source(source_id: str) -> dict[str, Any]:
        src = nasa.source(source_id)
        if src is None:
            raise EngineError(404, f"Unknown NASA source '{source_id}'")
        return {"source": src}

    @app.get("/nasa/official")
    def nasa_official() -> dict[str, Any]:
        # The five official challenge resources (slots A-C) and ASTRA's risk map built on them.
        return official_resources(nasa)

    @app.get("/nasa/cabin")
    def nasa_cabin(env: str | None = None) -> dict[str, Any]:
        return engine.cabin(env)

    @app.get("/nasa/inspiration4")
    def nasa_inspiration4() -> dict[str, Any]:
        return engine.inspiration4()

    @app.get("/nasa/solar/events")
    def nasa_solar_events() -> dict[str, Any]:
        # A replay that has run its course is no longer "active" (its dose still counts in /radiation).
        event = engine._solar_event()
        if event and engine.now() - float(event.get("started_met", 0.0)) >= float(event.get("duration_s", 0.0)):
            event = None
        return {"events": engine._donki_events(), "active": event}

    @app.post("/nasa/replay/solar/stop")
    def nasa_replay_solar_stop() -> dict[str, Any]:
        """Stop the replay and clear its extra dose. Everything else in the demo is left alone."""
        return engine.stop_solar_replay()

    @app.post("/nasa/replay/solar")
    def nasa_replay_solar(body: SolarReplayIn | None = None) -> dict[str, Any]:
        event_id = body.event_id if body else None
        state = engine.start_solar_replay(event_id)
        return {"ok": True, "event": state}

    # ---------------------------------------------------------------- simulator
    @app.get("/sim/scenarios")
    def sim_scenarios() -> dict[str, Any]:
        return {"scenarios": simulator.summaries()}

    @app.get("/sim/scenarios/{scenario_id}")
    def sim_scenario(scenario_id: str) -> dict[str, Any]:
        scenario = simulator.scenario(scenario_id)
        if scenario is None:
            raise EngineError(404, f"Unknown scenario '{scenario_id}'")
        return {"scenario": scenario}

    @app.get("/sim/live/status")
    def sim_live_status() -> dict[str, Any]:
        return live_sim.status()

    @app.post("/sim/live/start")
    def sim_live_start(body: SimLiveStartIn | None = None) -> dict[str, Any]:
        scenario = body.scenario if body else "nominal"
        interval_s = body.interval_s if body else 30.0
        crew_id = body.crew_id if body else None
        return live_sim.start(scenario, interval_s, crew_id)

    @app.post("/sim/live/stop")
    def sim_live_stop() -> dict[str, Any]:
        return live_sim.stop()

    @app.post("/sim/live/tick")
    def sim_live_tick() -> dict[str, Any]:
        return live_sim.tick()

    @app.get("/crew")
    def crew(env: str | None = None) -> dict[str, Any]:
        return engine.crew_overview(env)

    @app.get("/attention")
    def attention(env: str | None = None) -> dict[str, Any]:
        return engine.attention(None, env)

    @app.get("/crew/{crew_id}/attention")
    def crew_attention(crew_id: str, env: str | None = None) -> dict[str, Any]:
        return engine.attention(crew_id, env)

    @app.post("/attention/{key:path}/ack")
    def attention_ack(key: str, body: AttentionAckIn) -> dict[str, Any]:
        return engine.ack_attention(key, body.crew_id)

    @app.post("/attention/{key:path}/resolve")
    def attention_resolve(key: str, body: AttentionResolveIn) -> dict[str, Any]:
        return engine.resolve_attention(key, body.crew_id, body.note)

    @app.get("/crew/{crew_id}/dashboard")
    def dashboard(crew_id: str, env: str | None = None) -> dict[str, Any]:
        return engine.dashboard(crew_id, env)

    @app.get("/crew/{crew_id}/profile")
    def profile(crew_id: str) -> dict[str, Any]:
        return engine.profile(crew_id)

    @app.get("/assistant/notifications")
    def assistant_notifications(crew_id: str, env: str | None = None) -> dict[str, Any]:
        engine.crew(crew_id)
        return assistant.notifications(engine, crew_id, env)

    @app.post("/assistant/chat")
    def assistant_chat(body: AssistantIn) -> StreamingResponse:
        engine.crew(body.crew_id)  # 404 for an unknown crew member before streaming starts
        history = [t.model_dump() for t in body.history]
        return StreamingResponse(assistant.chat(engine, body.crew_id, body.env, body.question, history, body.page),
                                 media_type="application/x-ndjson")

    @app.post("/agent/crew-watch/run")
    def agent_run(env: str | None = None) -> dict[str, Any]:
        return agent.run(engine, env)

    @app.get("/agent/crew-watch")
    def agent_last() -> dict[str, Any]:
        return {"last": agent.last(engine)}

    @app.get("/crew/{crew_id}/exercise")
    def exercise(crew_id: str, env: str | None = None) -> dict[str, Any]:
        return engine.exercise(crew_id, env)

    @app.post("/crew/{crew_id}/perks/approve")
    def approve_perk(crew_id: str, body: PerkApproveIn) -> dict[str, Any]:
        return engine.approve_perk(crew_id, body.week, body.days)

    @app.get("/crew/{crew_id}/game")
    def game(crew_id: str, env: str | None = None) -> dict[str, Any]:
        return engine.game_hub(crew_id, env)

    @app.get("/crew/{crew_id}/routine")
    def routine(crew_id: str, env: str | None = None) -> dict[str, Any]:
        return engine.routine(crew_id, env)

    @app.get("/crew/{crew_id}/series/{metric}")
    def series(crew_id: str, metric: str, days: int = 14) -> dict[str, Any]:
        return engine.series(crew_id, metric, days)

    @app.post("/crew/{crew_id}/evaluate")
    def evaluate(crew_id: str, body: ReadingIn) -> dict[str, Any]:
        return engine.evaluate(crew_id, body.metric, body.value, body.value2, body.meta, body.env, body.task_id)

    @app.post("/crew/{crew_id}/readings")
    def save(crew_id: str, body: ReadingIn) -> dict[str, Any]:
        return engine.save_reading(crew_id, body.metric, body.value, body.value2, body.meta, body.task_id, body.env)

    @app.get("/comms")
    def comms(env: str | None = None, crew_id: str | None = None) -> dict[str, Any]:
        return engine.comms(env, crew_id)

    @app.post("/comms/messages")
    def message(body: MessageIn) -> dict[str, Any]:
        return engine.send_message(body.crew_id, body.text, body.env)

    @app.post("/emergencies")
    def emergency_start(body: EmergencyStartIn) -> dict[str, Any]:
        return engine.start_emergency(body.crew_id, body.patient_id, body.protocol_id, body.env)

    @app.post("/emergencies/{emergency_id}/finish")
    def emergency_finish(emergency_id: int, body: EmergencyFinishIn) -> dict[str, Any]:
        return engine.finish_emergency(
            emergency_id, body.crew_id, body.track, body.completed, body.duration_s,
            body.steps, body.is_drill, body.env
        )

    return app


app = create_app()
