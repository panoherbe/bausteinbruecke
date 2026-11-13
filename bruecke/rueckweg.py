"""Rückweg: liest den JSON-Export der OMG-Pilotimplementierung und sucht jede übertragene Angabe wieder.

Der Export ist die Form, in der ein Werkzeug den Stand über die SysML-v2-API liefert (je Element `identity.@id` und
`payload`). Was dort nicht wiederzufinden ist, gilt als verloren und steht im Bericht. Element-IDs zählen dabei nicht:
das Werkzeug vergibt sie bei jedem Einlesen neu (gemessen); Identität tragen Baustein-ID, Version und qualifizierte Namen.
"""
from __future__ import annotations

import collections

from .abbilden import NICHT, OFFEN, _kamel, _text


def index(elemente: list[dict]) -> tuple[dict, dict]:
    by_id = {e["identity"]["@id"]: e["payload"] for e in elemente}
    by_qn = {}
    for i, p in by_id.items():
        if p.get("qualifiedName") and p.get("declaredName"):
            by_qn[p["qualifiedName"]] = p
    return by_id, by_qn


def literale(by_id: dict) -> dict[str, list[str]]:
    """Literalwerte unter ihrem nächsten benannten Besitzer."""
    aus = collections.defaultdict(list)
    for p in by_id.values():
        if p.get("@type", "").startswith("Literal") and "value" in p:
            o, schritte = p.get("owner"), 0
            while o and schritte < 15:
                q = by_id.get(o["@id"], {})
                if q.get("qualifiedName") and q.get("declaredName"):
                    aus[q["qualifiedName"]].append(str(p["value"]))
                    break
                o, schritte = q.get("owner"), schritte + 1
    return aus


def _gleich(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def pruefen(elemente: list[dict], paket: str, bausteine: list[dict], bericht: list[dict]) -> dict:
    by_id, by_qn = index(elemente)
    lit = literale(by_id)
    typen = collections.Counter(p.get("@type") for p in by_id.values())
    quelle = {(b["baustein_id"], str(b["version"])): b for b in bausteine}
    ergebnisse = []
    satisfy_soll = sum(1 for e in bericht if e["feld"].startswith("erfuellt.") and e["status"] not in (NICHT, OFFEN))
    for e in bericht:
        if e["status"] in (NICHT, OFFEN):
            continue
        b = quelle[(e["baustein"], e["version"])]
        name, feld = b["name"], e["feld"]
        pd = by_qn.get(f"{paket}::{name}", {})
        werte = lit.get(f"{paket}::{name}", [])
        if feld in ("baustein_id", "name", "typ"):
            ok = pd.get("@type") == "PartDefinition" and pd.get("declaredShortName") == b["baustein_id"]
        elif feld in ("version", "ebene", "vorgaenger"):
            ok = str(b.get(feld, "")) in werte
        elif feld == "semantik":
            ok = b["semantik"]["iri"] in werte and b["semantik"]["begriff"] in werte
        elif feld == "beschreibung" or feld == "messgroesse":
            doc = [p for p in by_id.values() if p.get("@type") == "Documentation"
                   and (p.get("owner") or {}).get("@id") == (pd.get("elementId") or "")]
            text = _text(b.get(feld, "")).strip()
            ok = bool(pd) and any(text in " ".join((d.get("body") or "").split()) for d in doc)
        elif feld.startswith("attribute."):
            a = next(x for x in b["attribute"] if x["name"] == feld.split(".", 1)[1])
            w = lit.get(f"{paket}::{name}::{a['name']}", [])
            ok = any(_gleich(x, a["wert"]) for x in w)
        elif feld.startswith("schnittstellen."):
            ok = by_qn.get(f"{paket}::{name}::{feld.split('.', 1)[1]}", {}).get("@type") == "PortUsage"
        elif feld.startswith("zustaende."):
            ok = by_qn.get(f"{paket}::{name}Zustaende::{feld.split('.', 1)[1]}", {}).get("@type") == "StateUsage"
        elif feld.startswith("funktionen."):
            fid = feld.split(".", 1)[1]
            f = next(x for x in b["funktionen"] if x["id"] == fid)
            p = by_qn.get(f"{paket}::Funktionen::{f['name']}", {})
            ok = p.get("@type") == "ActionUsage" and p.get("declaredShortName") == fid
        elif feld.startswith("erfuellt."):
            rid = feld.split(".", 1)[1]
            anf = [p for p in by_id.values() if p.get("@type") == "RequirementUsage" and p.get("declaredShortName") == rid]
            ok = (by_qn.get(f"{paket}::{_kamel(paket)}::{_kamel(name)}") is not None and len(anf) == 1
                  and typen.get("SatisfyRequirementUsage", 0) == satisfy_soll)
        else:
            ok = False
        ergebnisse.append({**e, "wiedergefunden": bool(ok)})
    gefunden = sum(r["wiedergefunden"] for r in ergebnisse)
    return {"elemente": len(by_id), "benannt": len(by_qn), "geprueft": len(ergebnisse), "wiedergefunden": gefunden,
            "verloren": [r for r in ergebnisse if not r["wiedergefunden"]],
            "typen": dict(typen.most_common(10))}
