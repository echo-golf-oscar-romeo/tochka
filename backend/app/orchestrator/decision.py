"""Rule-based methodology selection.

The LLM picks tools at runtime. *Choosing* demand model and analytical archetype
is rule-based for now — deterministic, debuggable, defensible to judges. The
LLM only asks the clarifying question when these rules can't decide alone.
"""

from __future__ import annotations

from app.models.analysis import Archetype, DemandModel
from app.models.network import Network

# POI-type keyword → (default demand model, default archetypes)
_RULES: dict[str, tuple[DemandModel, list[Archetype]]] = {
    "branch": (DemandModel.PEOPLE_DRIVEN, [Archetype.DIAGNOSE, Archetype.EXPAND]),
    "bank":   (DemandModel.PEOPLE_DRIVEN, [Archetype.DIAGNOSE, Archetype.EXPAND]),
    "atm":    (DemandModel.FLOW_DRIVEN, [Archetype.DIAGNOSE, Archetype.RATIONALISE]),
    "store":  (DemandModel.PEOPLE_DRIVEN, [Archetype.DIAGNOSE, Archetype.EXPAND]),
    "shop":   (DemandModel.PEOPLE_DRIVEN, [Archetype.DIAGNOSE, Archetype.EXPAND]),
    "outlet": (DemandModel.PEOPLE_DRIVEN, [Archetype.DIAGNOSE, Archetype.EXPAND]),
    "clinic": (DemandModel.VISIT_DRIVEN, [Archetype.DIAGNOSE, Archetype.EXPAND]),
    "centre": (DemandModel.CATCHMENT_FIXED, [Archetype.DIAGNOSE]),
    "school": (DemandModel.CATCHMENT_FIXED, [Archetype.DIAGNOSE]),
}


def classify_poi_type(network: Network) -> str:
    """Return a single lowercased keyword guess by scanning the network."""
    text = " ".join([loc.name for loc in network.locations]).lower()
    for keyword in _RULES:
        if keyword in text:
            return keyword
    return "unknown"


def pick_methodology(network: Network,
                     user_intent: str | None,
                     clarification_answer: str | None) -> tuple[DemandModel, list[Archetype], str]:
    """Return (demand_model, archetypes, poi_type)."""
    poi = classify_poi_type(network)
    if poi in _RULES:
        dm, arch = _RULES[poi]
    else:
        dm, arch = DemandModel.PEOPLE_DRIVEN, [Archetype.DIAGNOSE]

    # Intent overrides — accept hints from user_intent or clarification_answer.
    hint = " ".join(filter(None, [user_intent, clarification_answer])).lower()
    if "expand" in hint or "open" in hint:
        if Archetype.EXPAND not in arch:
            arch.append(Archetype.EXPAND)
    if "close" in hint or "merge" in hint or "rationalise" in hint or "rationalize" in hint:
        if Archetype.RATIONALISE not in arch:
            arch.append(Archetype.RATIONALISE)
    if "sme" in hint:
        dm = DemandModel.FLOW_DRIVEN
    if "retail" in hint and poi in ("branch", "bank"):
        dm = DemandModel.PEOPLE_DRIVEN

    return dm, arch, poi


def needs_clarification(poi_type: str, user_intent: str | None) -> bool:
    """True when we'd benefit from one user question before deciding."""
    if user_intent:
        return False
    return poi_type in ("branch", "bank")    # only banks ambiguous between retail and SME for now
