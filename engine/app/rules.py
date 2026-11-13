"""Pure health-rule functions: classification, personal baselines, trends, escalation and insights.

No I/O here, so every rule is easy to unit-test and explain.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from statistics import fmean, pstdev
from typing import Any

from .catalog import ACTIVE_CONTEXTS, CABIN, METRIC_BY_ID, RED_FLAG_SYMPTOMS

RANK = {"ok": 0, "watch": 1, "act": 2}

# Which direction is "worse" for each metric. Used so a reading that is unusually *good*
# (e.g. more exercise, higher SpO2) never raises a personal-baseline flag.
WORSE: dict[str, str] = {
    "hr": "both", "bp": "up", "spo2": "down", "resp": "up", "temp": "up", "glucose": "both",
    "hydration": "down", "mass": "down", "sleep": "down", "mood": "down", "reaction": "up",
    "exercise": "down", "vision": "up", "symptoms": "up", "nutrition": "down",
}
PERSONAL_Z = 3.0  # |z| at or beyond this, in the worse direction, is "unusual for you"


def worst(statuses: Iterable[str]) -> str:
    out = "ok"
    for s in statuses:
        if RANK.get(s, 0) > RANK[out]:
            out = s
    return out


def _within(v: float, rng: Sequence[float]) -> bool:
    return rng[0] <= v <= rng[1]


def _grade(v: float, ok: Sequence[float], watch: Sequence[float]) -> str:
    if _within(v, ok):
        return "ok"
    if _within(v, watch):
        return "watch"
    return "act"


def relative_change(value: float, ref: float | None) -> float:
    if not ref:
        return 0.0
    return (value - ref) / ref * 100.0


def context_of(meta: dict[str, Any] | None) -> str | None:
    """The measurement context stored with a reading (None means resting / not recorded)."""
    return (meta or {}).get("context")


def is_active(metric_id: str, meta: dict[str, Any] | None) -> bool:
    """True when the reading was taken after exertion and the metric has bands for that."""
    return bool(METRIC_BY_ID[metric_id].get("active")) and context_of(meta) in ACTIVE_CONTEXTS


def bands(metric_id: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """The ranges that apply to this reading: the resting ones, or the post-exertion ones."""
    m = METRIC_BY_ID[metric_id]
    base = {"ok": m["ok"], "watch": m["watch"], "ok2": m.get("ok2"), "watch2": m.get("watch2"),
            "red": m.get("red") or {}}
    if is_active(metric_id, meta):
        base.update(m["active"])
    return base


def classify(metric_id: str, value: float, value2: float | None = None, ref: float | None = None,
             meta: dict[str, Any] | None = None) -> str:
    """Classify one reading as ok / watch / act using the ranges for its context."""
    m = METRIC_BY_ID[metric_id]
    b = bands(metric_id, meta)
    v = relative_change(value, ref) if m.get("rule") == "relative" else value
    status = _grade(v, b["ok"], b["watch"])
    if metric_id == "bp" and value2 is not None:
        status = worst([status, _grade(value2, b["ok2"], b["watch2"])])
    if metric_id == "symptoms" and red_flags(metric_id, value, value2, meta):
        status = "act"
    return status


def absolute_band(metric_id: str, ref: float | None = None,
                  meta: dict[str, Any] | None = None) -> dict[str, list[float] | None]:
    """Normal (ok) and watch ranges in the metric's own unit, for the reading's context."""
    m = METRIC_BY_ID[metric_id]
    if m.get("rule") == "relative":
        r = ref or 0.0
        conv = lambda rng: [round(r * (1 + rng[0] / 100), 2), round(r * (1 + rng[1] / 100), 2)]  # noqa: E731
        return {"ok": conv(m["ok"]), "watch": conv(m["watch"]), "ok2": None, "watch2": None}
    b = bands(metric_id, meta)
    return {"ok": list(b["ok"]), "watch": list(b["watch"]), "ok2": b["ok2"], "watch2": b["watch2"]}


def axis_for(metric_id: str, ref: float | None = None) -> list[float]:
    m = METRIC_BY_ID[metric_id]
    if m.get("axis"):
        return list(m["axis"])
    r = ref or 70.0
    return [round(r * 0.92, 1), round(r * 1.04, 1)]


def red_flags(metric_id: str, value: float, value2: float | None = None,
              meta: dict[str, Any] | None = None) -> list[str]:
    """Reasons that skip straight to the flight surgeon (tier 2)."""
    m = METRIC_BY_ID[metric_id]
    red = bands(metric_id, meta)["red"]
    out: list[str] = []
    if "below" in red and value < red["below"]:
        out.append(f"{m['label']} below {red['below']} {m['unit']}".strip())
    if "above" in red and value > red["above"]:
        out.append(f"{m['label']} above {red['above']} {m['unit']}".strip())
    if value2 is not None and "above2" in red and value2 > red["above2"]:
        out.append(f"Diastolic above {red['above2']} mmHg")
    if metric_id == "symptoms" and meta:
        flagged = [s for s in meta.get("items", []) if s in RED_FLAG_SYMPTOMS]
        out.extend(f"Red-flag symptom: {s.replace('_', ' ')}" for s in flagged)
    return out


# ------------------------------------------------------------------------------------------
# Personal baseline, deviation and trend
# ------------------------------------------------------------------------------------------
def baseline(values: Sequence[float], min_sd: float) -> dict[str, float] | None:
    if not values:
        return None
    mean = fmean(values)
    sd = pstdev(values) if len(values) > 1 else 0.0
    return {"mean": mean, "sd": max(sd, min_sd), "n": float(len(values))}


def zscore(value: float, base: dict[str, float] | None) -> float | None:
    if not base:
        return None
    return (value - base["mean"]) / base["sd"]


def is_worse_direction(metric_id: str, z: float) -> bool:
    d = WORSE.get(metric_id, "both")
    return d == "both" or (d == "up" and z > 0) or (d == "down" and z < 0)


def slope_per_day(points: Sequence[tuple[float, float]]) -> float:
    """Least-squares slope of (day, value) points."""
    if len(points) < 2:
        return 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx, my = fmean(xs), fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den


def trend_label(metric_id: str, slope: float, min_sd: float) -> dict[str, str]:
    change_week = slope * 7
    if abs(change_week) < min_sd:
        return {"direction": "stable", "quality": "neutral"}
    direction = "rising" if change_week > 0 else "falling"
    d = WORSE.get(metric_id, "both")
    if d == "both":
        quality = "neutral"
    else:
        worse = (d == "up" and direction == "rising") or (d == "down" and direction == "falling")
        quality = "worsening" if worse else "improving"
    return {"direction": direction, "quality": quality}


def persistence(daily_statuses_newest_first: Sequence[str]) -> dict[str, int]:
    """Consecutive days (newest first) at watch-or-worse, and at act."""
    watch_days = 0
    for s in daily_statuses_newest_first:
        if RANK[s] >= 1:
            watch_days += 1
        else:
            break
    act_days = 0
    for s in daily_statuses_newest_first:
        if s == "act":
            act_days += 1
        else:
            break
    return {"watch_days": watch_days, "act_days": act_days}


def escalation_tier(status: str, flags: Sequence[str], persist: dict[str, int]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    if flags:
        return 2, list(flags)
    if status == "act" and persist["act_days"] >= 2:
        return 2, [f"Act result for {persist['act_days']} days in a row"]
    if status == "act":
        return 1, ["Act result"]
    if status == "watch" and persist["watch_days"] >= 3:
        reasons.append(f"Watch result for {persist['watch_days']} days in a row")
        return 1, reasons
    return 0, reasons


# ------------------------------------------------------------------------------------------
# Insights (pattern rules across metrics)
# ------------------------------------------------------------------------------------------
def _st(snap: dict[str, Any], k: str) -> str:
    return snap.get(k, {}).get("status", "ok")


def _val(snap: dict[str, Any], k: str) -> float | None:
    return snap.get(k, {}).get("value")


def _recent(snap: dict[str, Any], k: str, n: int) -> list[float]:
    return [v for _, v in snap.get(k, {}).get("recent", [])][-n:]


def _fmt(v: float | None, d: int = 1) -> str:
    return "-" if v is None else f"{v:.{d}f}"


def insights(snap: dict[str, Any]) -> list[dict[str, Any]]:
    """Cross-metric patterns. `snap[metric]` holds status, value, baseline mean, slope, recent points."""
    out: list[dict[str, Any]] = []
    covered: set[str] = set()

    sleep3 = _recent(snap, "sleep", 3)
    sleep_avg = fmean(sleep3) if sleep3 else None
    mind_off = _st(snap, "mood") != "ok" or _st(snap, "reaction") != "ok"
    if (_st(snap, "sleep") != "ok" or (sleep_avg is not None and sleep_avg < 6.8)) and mind_off:
        b = snap.get("sleep", {}).get("baseline")
        out.append({
            "id": "sleep_debt", "severity": worst([_st(snap, "sleep"), _st(snap, "mood"), _st(snap, "reaction")]),
            "title": "Sleep-debt pattern",
            "body": f"Sleep averaged {_fmt(sleep_avg)} h over the last 3 nights"
            + (f" (your baseline is {_fmt(b)} h)" if b else "")
            + f". Mood ({_fmt(_val(snap, 'mood'), 0)}/5) and reaction time ({_fmt(_val(snap, 'reaction'), 0)} ms) "
            "moved with it. These usually recover together, so fix sleep first.",
            "metrics": ["sleep", "mood", "reaction"], "organ": "brain",
            "actions": ["Protect tonight's 8.5-hour sleep window", "No caffeine after 14:00",
                        "Re-test reaction time tomorrow", "Tell the Commander before critical tasks"],
        })
        covered |= {"sleep", "mood", "reaction"}

    t = snap.get("temp", {})
    temp_up = _st(snap, "temp") != "ok" or (
        t.get("value") is not None and t.get("baseline") is not None and t["value"] - t["baseline"] >= 0.5)
    hr = snap.get("hr", {})
    hr_up = hr.get("value") is not None and hr.get("baseline") is not None and hr["value"] - hr["baseline"] >= 8
    sym_items = set(snap.get("symptoms", {}).get("items", []))
    resp_sym = bool(sym_items & {"sore_throat", "cough", "fatigue"})
    if temp_up and (_st(snap, "resp") != "ok" or hr_up or resp_sym):
        out.append({
            "id": "infection", "severity": "act" if _st(snap, "temp") == "act" else "watch",
            "title": "Possible early infection",
            "body": f"Temperature {_fmt(_val(snap, 'temp'))} °C is rising together with "
            + ("breathing rate" if _st(snap, "resp") != "ok" else "heart rate" if hr_up else "symptoms")
            + ". In a sealed habitat, catching this early protects the whole crew.",
            "metrics": ["temp", "resp", "hr", "symptoms"], "organ": "immune",
            "actions": ["Re-check temperature in 2 hours", "Inform the Crew Medical Officer",
                        "Limit close contact and share no utensils", "Drink fluids and rest"],
        })
        covered |= {"temp", "resp", "hr", "symptoms"}

    bp = snap.get("bp", {})
    bp_rising = (bp.get("slope", 0) >= 1.0 and bp.get("value") is not None and bp.get("baseline") is not None
                 and bp["value"] - bp["baseline"] >= 6)
    if "bp" not in covered and (_st(snap, "bp") != "ok" or bp_rising):
        rise = bp.get("slope", 0) * 7
        hr_note = (" Resting heart rate is up as well." if _st(snap, "hr") != "ok" else "")
        out.append({
            "id": "bp_drift", "severity": worst([_st(snap, "bp"), "watch"]),
            "title": "Blood pressure drifting up",
            "body": f"Systolic pressure has risen about {rise:+.0f} mmHg over 7 days.{hr_note} Fluid shift, salt, "
            "stress and less aerobic work can all contribute. If Watch lasts 3 days, the CMO is alerted "
            "automatically.",
            "metrics": ["bp", "hr"], "organ": "heart",
            "actions": ["Re-measure tonight after 5 minutes of rest", "Go easy on salt", "Keep the aerobic exercise"],
        })
        covered |= {"bp", "hr"}

    if _st(snap, "vision") != "ok":
        out.append({
            "id": "sans", "severity": _st(snap, "vision"), "title": "Possible SANS sign",
            "body": "Your last vision check reported a change. Fluid shift can raise pressure behind the eyes, "
            "so the CMO should review it, and the ground may request an eye ultrasound.",
            "metrics": ["vision"], "organ": "eyes",
            "actions": ["Repeat the Amsler check tomorrow", "Tell the Crew Medical Officer", "Note any headaches"],
        })
        covered.add("vision")

    ex3 = _recent(snap, "exercise", 3)
    if "exercise" not in covered and (_st(snap, "exercise") != "ok" or sum(1 for v in ex3 if v < 120) >= 2):
        out.append({
            "id": "deconditioning", "severity": _st(snap, "exercise") if _st(snap, "exercise") != "ok" else "watch",
            "title": "Exercise below the 2-hour target",
            "body": f"You logged {_fmt(_val(snap, 'exercise'), 0)} min last session. Bones lose mass quickly without "
            "loading, so make up a resistive block today.",
            "metrics": ["exercise", "mass"], "organ": "musculo",
            "actions": ["Book a resistive block today", "Prioritise hips, legs and spine",
                        "Train with a crewmate for accountability"],
        })
        covered.add("exercise")

    hy3 = _recent(snap, "hydration", 3)
    if "hydration" not in covered and (_st(snap, "hydration") != "ok" or sum(1 for v in hy3 if v < 2.0) >= 2):
        out.append({
            "id": "kidney", "severity": _st(snap, "hydration") if _st(snap, "hydration") != "ok" else "watch",
            "title": "Low fluids: kidney-stone risk",
            "body": f"Fluid intake was {_fmt(_val(snap, 'hydration'))} L. Calcium released from bones in "
            "weightlessness makes kidney stones more likely when fluids are low.",
            "metrics": ["hydration"], "organ": "kidneys",
            "actions": ["Drink 500 ml in the next hour", "Keep a drink bag in sight", "Report flank pain"],
        })
        covered.add("hydration")

    if "mass" not in covered and _st(snap, "mass") != "ok":
        out.append({
            "id": "weight_loss", "severity": _st(snap, "mass"), "title": "Losing body mass",
            "body": f"Body mass is {snap['mass'].get('change_pct', 0):+.1f}% from your mission reference. "
            "Appetite often drops in space, and muscle shrinks without gravity.",
            "metrics": ["mass", "exercise"], "organ": "metabolism",
            "actions": ["Eat the full planned menu plus snacks", "Keep resistive exercise",
                        "Review the diet plan with ground nutrition"],
        })
        covered.add("mass")

    for k, s in snap.items():
        if k in covered or s.get("status", "ok") == "ok":
            continue
        m = METRIC_BY_ID[k]
        if s.get("personal"):
            title = f"{m['label']}: unusual for you"
            body = (f"{_fmt(s.get('value'), m['decimals'])} {m['unit']} is inside the normal range but far from your "
                    f"personal baseline ({_fmt(s.get('baseline'), m['decimals'])} {m['unit']}). Measure again later "
                    "and note how you feel.")
        else:
            title, body = f"{m['label']}: {s['status'].capitalize()}", m["guide"][s["status"]]
        out.append({"id": f"metric_{k}", "severity": s["status"], "title": title, "body": body, "metrics": [k],
                    "organ": m["organ"], "actions": []})

    if not out:
        out.append({
            "id": "all_clear", "severity": "ok", "title": "All systems nominal",
            "body": "Every indicator is inside your normal range and close to your personal baseline. "
            "Keep the routine going, and enjoy the view.",
            "metrics": [], "organ": None, "actions": ["Keep your sleep window", "Finish today's checks"],
        })
    out.sort(key=lambda i: -RANK[i["severity"]])
    for i in out:
        i.setdefault("sources", insight_sources(i))
    return out


# The NASA documents behind each insight. Insights that name several metrics list the union of
# those metrics' sources, so the "Evidence" link always points at something real.
INSIGHT_SOURCES: dict[str, list[str]] = {
    "sleep_debt": ["hrp_sleep", "hrp_cog"],
    "infection": ["hrp_immuno", "hrp_microbe"],
    "bp_drift": ["hrp_cardio", "std3001v1"],
    "sans": ["hrp_sans"],
    "deconditioning": ["hrp_bone", "hrp_dynload"],
    "kidney": ["hrp_renal"],
    "weight_loss": ["hrp_food"],
    "cabin_air": ["std3001v2", "ochmo_tb004", "osdr_eda"],
    "all_clear": ["hrp_illness"],
}


def insight_sources(insight: dict[str, Any]) -> list[str]:
    """The source ids behind an insight."""
    ids = INSIGHT_SOURCES.get(insight["id"], [])
    if not ids and insight["id"].startswith("metric_"):
        ids = METRIC_BY_ID.get(insight["id"][len("metric_"):], {}).get("sources", [])
    return list(ids)


# ------------------------------------------------------------------------------------------
# Readiness
# ------------------------------------------------------------------------------------------
CRITICAL_FOR_EVA = ("hr", "bp", "spo2", "resp", "temp", "reaction", "symptoms")


def readiness(statuses: dict[str, str], insight_list: Sequence[dict[str, Any]], overdue: int) -> int:
    score = 100.0
    for s in statuses.values():
        score -= {"ok": 0, "watch": 5, "act": 14}[s]
    score -= sum(4 for i in insight_list if i["severity"] == "act")
    score -= min(overdue, 5)
    return int(max(0, min(100, round(score))))


def eva_readiness(statuses: dict[str, str], sleep_value: float | None) -> dict[str, Any]:
    reasons: list[str] = []
    level = "go"
    for k in CRITICAL_FOR_EVA:
        s = statuses.get(k, "ok")
        if s == "act":
            level = "nogo"
            reasons.append(f"{METRIC_BY_ID[k]['label']} is in Act")
        elif s == "watch" and level != "nogo":
            level = "caution"
            reasons.append(f"{METRIC_BY_ID[k]['label']} is in Watch")
    if sleep_value is not None:
        if sleep_value < 5.5:
            level = "nogo"
            reasons.append(f"Only {sleep_value:.1f} h sleep")
        elif sleep_value < 6.5 and level == "go":
            level = "caution"
            reasons.append(f"Short sleep ({sleep_value:.1f} h)")
    if not reasons:
        reasons.append("All EVA-critical indicators nominal")
    return {"status": level, "reasons": reasons}


# ------------------------------------------------------------------------------------------
# Laboratory values (Inspiration4 reference)
# ------------------------------------------------------------------------------------------
# This is an ASTRA display rule, not a clinical one: a value inside the dataset's own reference
# range is Nominal, a value within 10% of the range edge is Watch, and anything further out is
# Act. The reference ranges are the ones the NASA OSDR dataset ships with.
LAB_TOLERANCE = 0.10


def classify_lab(value: float, ref_low: float | None, ref_high: float | None) -> str:
    """Classify a lab value against its reference range.

    Inside the range: ok. Within 10% of a range edge: watch. Further out: act.
    """
    if ref_low is None and ref_high is None:
        return "ok"
    if ref_low is not None and value < ref_low:
        edge = ref_low
        if value >= edge * (1.0 - LAB_TOLERANCE):
            return "watch"
        return "act"
    if ref_high is not None and value > ref_high:
        edge = ref_high
        if value <= edge * (1.0 + LAB_TOLERANCE):
            return "watch"
        return "act"
    return "ok"


# ------------------------------------------------------------------------------------------
# Cabin air (CO2)
# ------------------------------------------------------------------------------------------
def cabin_status(co2_1h: float, co2_7d: float) -> str:
    """Classify the cabin CO2 against the NASA limits.

    Act:  the one-hour average is at or above 3.0 mmHg (NASA-STD-3001 Vol 2, [V2 6004]).
    Watch: the 7-day average is at or above 2.5 mmHg (OCHMO-TB-004).
    Otherwise Nominal.
    """
    if co2_1h >= CABIN["act_1h_mmhg"]:
        return "act"
    if co2_7d >= CABIN["watch_7d_mmhg"]:
        return "watch"
    return "ok"


def cabin_insight(cabin: dict[str, Any], headache_crew: list[str]) -> dict[str, Any] | None:
    """The "it's the air, not you" insight.

    Fires when at least two crew members reported a headache in the last 24 hours *and* the
    cabin CO2 is Watch or worse. The actions point at the scrubber and the airflow, not at
    medicine: the cause is the cabin, so that is what has to be fixed.
    """
    if len(headache_crew) < 2:
        return None
    status = cabin.get("status", "ok")
    if status == "ok":
        return None
    names = ", ".join(headache_crew)
    return {
        "id": "cabin_air",
        "severity": status,
        "title": "It's the air, not you",
        # Both averages against their own limits: Act comes from the 1-hour average, Watch from the 7-day one.
        "body": f"{len(headache_crew)} crew members reported a headache in the last 24 hours "
                f"({names}), and the cabin CO2 is at the {status.capitalize()} level: "
                f"{cabin.get('co2_1h_mmhg', 0):.2f} mmHg over the last hour (limit {CABIN['act_1h_mmhg']}) and "
                f"{cabin.get('co2_7d_mmhg', 0):.2f} mmHg over 7 days (limit {CABIN['watch_7d_mmhg']}). "
                f"NASA-STD-3001 and the OCHMO carbon dioxide brief link headaches to CO2 in this range. "
                f"This is a habitat problem, not a personal one: fix the air, not the crew.",
        "metrics": ["symptoms"],
        "organ": "lungs",
        "actions": list(CABIN["actions"]["act" if status == "act" else "watch"]),
        "sources": list(CABIN["sources"]),
    }

