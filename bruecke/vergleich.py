"""Vergleich zweier Stände desselben Bausteins: was ist neu, was ist weg, welcher Wert hat sich geändert.

Verglichen wird über Baustein-ID und qualifizierte Namen, nie über Element-IDs des Werkzeugs (die sind bei jedem
Einlesen neu).
"""
from __future__ import annotations

from .rueckweg import index, literale


def _flach(b: dict) -> dict[str, str]:
    aus = {}
    for k, v in b.items():
        if k in ("attribute",):
            for a in v:
                aus[f"attribute.{a['name']}"] = f"{a['wert']} {a.get('einheit', '')}".strip()
        elif k in ("schnittstellen", "zustaende", "funktionen"):
            for x in v:
                schl = x.get("id") or x["name"]
                aus[f"{k}.{schl}"] = x.get("bedingung") or x.get("art") or x.get("text") or "ja"
        elif k == "erfuellt":
            for r in v:
                aus[f"erfuellt.{r}"] = "ja"
        elif k == "semantik":
            aus["semantik"] = v["iri"]
        else:
            aus[k] = str(v)
    return aus


def quellstaende(alt: dict, neu: dict) -> dict:
    """Vergleich auf Ebene der Bausteinbeschreibungen."""
    if alt["baustein_id"] != neu["baustein_id"]:
        raise ValueError("Verschiedene Bausteine; Vergleich nur innerhalb einer Baustein-ID")
    a, n = _flach(alt), _flach(neu)
    return {"baustein": neu["baustein_id"], "von": str(alt["version"]), "nach": str(neu["version"]),
            "neu": sorted(set(n) - set(a)), "weg": sorted(set(a) - set(n)),
            "geaendert": {k: [a[k], n[k]] for k in sorted(set(a) & set(n)) if a[k] != n[k]}}


def modellstaende(alt: list[dict], neu: list[dict], wurzel: str) -> dict:
    """Vergleich zweier JSON-Exporte des Werkzeugs (benannte Elemente und Literalwerte)."""
    ia, qa = index(alt)
    ib, qb = index(neu)
    la, lb = literale(ia), literale(ib)
    qa = {k for k in qa if k.startswith(wurzel)}
    qb = {k for k in qb if k.startswith(wurzel)}
    geaendert = {k: [sorted(la.get(k, [])), sorted(lb.get(k, []))]
                 for k in sorted(set(la) | set(lb)) if k.startswith(wurzel) and sorted(la.get(k, [])) != sorted(lb.get(k, []))}
    return {"elemente_alt": len(ia), "elemente_neu": len(ib), "neu": sorted(qb - qa), "weg": sorted(qa - qb),
            "geaendert": geaendert, "gleiche_element_ids": len(set(ia) & set(ib))}
