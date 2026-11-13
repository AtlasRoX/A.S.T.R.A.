"""The official challenge resources (manifest slots A, B and C), joined to what ASTRA does with them.

The Space Apps 2026 Resources tab lists five documents: three NASA Human Research Program pages
(the five hazards, the risks, the ongoing research) and two Canadian Space Agency articles. None of
them is machine-readable, so they were transcribed into small fixtures under
`engine/data/nasa/official/` (see the manifest notes). This module reads those fixtures and adds the
names of the ASTRA metrics and body systems each risk or study points at, so the UI can show a risk
map that is always in step with the catalog.

Pure reading: no network, no medical logic.
"""

from __future__ import annotations

from typing import Any

from .catalog import METRIC_BY_ID, ORGAN_BY_ID
from .nasa import Registry, RegistryError

FILES = {
    "slot-a": "official/hrp.json",
    "slot-b": "official/hrp_research.json",
    "slot-c": "official/csa.json",
}
LEVELS = ("monitored", "supported", "partial")


def _load(nasa: Registry | None, sid: str) -> dict[str, Any] | None:
    if nasa is None or not nasa.has(sid, FILES[sid]):
        return None
    try:
        data = nasa.json(sid, FILES[sid])
    except RegistryError:
        return None
    return data if isinstance(data, dict) else None


def _names(ids: list[str], table: dict[str, dict[str, Any]], key: str) -> list[dict[str, str]]:
    """Known ids with their display names; an id the catalog does not know is dropped."""
    return [{"id": i, "label": table[i][key]} for i in ids if i in table]


def official_resources(nasa: Registry | None) -> dict[str, Any]:
    """The five official resources and ASTRA's coverage of them, or `available: False`."""
    hrp, research, csa = (_load(nasa, sid) for sid in ("slot-a", "slot-b", "slot-c"))
    if not (hrp and research and csa):
        return {"available": False}

    risks = []
    for r in hrp.get("risks", []):
        a = r.get("astra", {})
        risks.append({
            **{k: r.get(k) for k in ("id", "category", "title", "url", "summary", "hazards", "roadmap_source")},
            "level": a.get("level") if a.get("level") in LEVELS else "partial",
            "how": a.get("how", ""),
            "metrics": _names(a.get("metrics", []), METRIC_BY_ID, "label"),
            "organs": _names(a.get("organs", []), ORGAN_BY_ID, "name"),
            "features": a.get("features", []),
        })
    by_level = {lvl: sum(1 for r in risks if r["level"] == lvl) for lvl in LEVELS}

    risk_titles = {r["id"]: r["title"] for r in risks}
    studies = []
    for st in research.get("studies", []):
        a = st.get("astra", {})
        studies.append({
            **{k: st.get(k) for k in ("id", "group", "name", "url", "summary")},
            "risks": [{"id": k, "title": risk_titles[k]} for k in st.get("risks", []) if k in risk_titles],
            "metrics": _names(a.get("metrics", []), METRIC_BY_ID, "label"),
            "link": a.get("link"),
            "how": a.get("how", ""),
        })

    resources = [
        *[{**p, "agency": "NASA", "slot": "A"} for p in hrp.get("pages", [])],
        {"id": "hrp_research", "title": "Ongoing HRP Research in Space", "url": research.get("url"),
         "challenge_note": research.get("challenge_note"), "agency": "NASA", "slot": "B"},
        *[{**p, "agency": "CSA", "slot": "C"} for p in csa.get("pages", [])],
    ]

    return {
        "available": True,
        "listed_on": hrp.get("listed_on"),
        "retrieved": hrp.get("retrieved"),
        "resources": resources,
        "hazards": hrp.get("hazards", []),
        "compound_note": hrp.get("compound_note", ""),
        "levels": hrp.get("coverage_levels", {}),
        "categories": hrp.get("categories", []),
        "risks": risks,
        "coverage": {"total": len(risks), **by_level},
        "research": {"groups": research.get("groups", []), "studies": studies},
        "csa": {k: csa.get(k) for k in ("radiation_facts", "instruments", "body_effects", "body_effects_url",
                                       "earth_benefits")},
        "sources": [s for s in (nasa.source(sid) for sid in FILES) if s] if nasa else [],
    }
