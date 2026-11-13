"""Ein Lauf der Bausteinbrücke: abbilden -> im Werkzeug prüfen -> Rückweg -> an die drei Gegenstellen übertragen.

    python -m bruecke.lauf beispiele/roboterarm --pruefer http://pruefer:8100 --gegenstellen http://gegenstellen:8200
"""
from __future__ import annotations

import argparse
import datetime
import json
import time
from pathlib import Path

from . import abbilden as ab
from . import rueckweg
from .adapter import KiAssistenz, Modellverwaltung, Wissensgraph, als_rdf
from .kern import Lauf, Vorgang, http


def bausteine(ordner: Path, ausser: set[str] = frozenset()) -> list[dict]:
    return [ab.lade(p) for p in sorted(Path(ordner).glob("*.yaml")) if p.name not in ausser]


def anforderungen(beispiele: Path, demonstrator: str) -> list[dict]:
    return ab.lade(Path(beispiele) / "anforderungen.yaml").get(demonstrator, [])


def pruefen(pruefer: str, text: str, export: bool = True) -> dict:
    code, antwort = http("POST", f"{pruefer}/export" if export else f"{pruefer}/pruefen",
                         json.dumps({"text": text}).encode(), zeit=600)
    if code != 200:
        raise RuntimeError(f"Prüfdienst HTTP {code}")
    return antwort


def zugangstest(gegenstellen: str) -> list[dict]:
    """Zugangstest: je Gegenstelle ein lesender Zugriff; Antwort, Dauer und Datum werden festgehalten."""
    aus = []
    for name, pfad in (("KI-Assistenz", "/ki/bausteine/B-XX"), ("Gegenstellen-Stand", "/_stand")):
        t = time.perf_counter()
        try:
            code, a = http("GET", gegenstellen + pfad)
            aus.append({"ziel": name, "erreichbar": True, "http": code, "antwort": a,
                        "dauer_ms": round((time.perf_counter() - t) * 1000, 1)})
        except Exception as e:  # noqa: BLE001
            aus.append({"ziel": name, "erreichbar": False, "fehler": str(e)})
    return aus


def uebertragen(lauf: Lauf, gegenstellen: str, bs: list[dict], text: str, vorgaenger: dict | None = None):
    ki, mm, kg = KiAssistenz(gegenstellen), Modellverwaltung(gegenstellen), Wissensgraph(gegenstellen)
    for b in bs:
        v = str(b["version"])
        lauf.senden(ki, Vorgang(ki.ziel, b["baustein_id"], v, "baustein schreiben", KiAssistenz.nutzlast(b, text)))
        vg = (vorgaenger or {}).get(b["baustein_id"])
        lauf.senden(mm, Vorgang(mm.ziel, b["baustein_id"], v, "stand anlegen",
                                Modellverwaltung.nutzlast(b, text, vg)))
        lauf.senden(kg, Vorgang(kg.ziel, b["baustein_id"], v, "knoten schreiben", als_rdf(b), "text/turtle"))
    return lauf


def ein_demonstrator(beispiele: Path, demonstrator: str, pruefer: str, gegenstellen: str | None, protokoll: Path,
                     ausser: set[str] = frozenset()) -> dict:
    bs = bausteine(Path(beispiele) / demonstrator, ausser)
    paket = ab.paketname(demonstrator)
    t0 = time.perf_counter()
    text, bericht = ab.abbilden(paket, bs, anforderungen(beispiele, demonstrator))
    t_abbilden = time.perf_counter() - t0
    werkzeug = pruefen(pruefer, text)
    rw = rueckweg.pruefen(werkzeug.get("elemente", []), paket, bs, bericht) if werkzeug["ok"] else None
    erg = {"demonstrator": demonstrator, "paket": paket, "bausteine": [f"{b['baustein_id']} {b['version']}" for b in bs],
           "text": text, "bericht": bericht, "zusammenfassung": ab.zusammenfassung(bericht),
           "werkzeug": {k: werkzeug[k] for k in ("ok", "meldungen", "dauer_s", "kernel")},
           "rueckweg": rw, "dauer_abbilden_s": round(t_abbilden, 4)}
    if gegenstellen:
        lauf = uebertragen(Lauf(protokoll), gegenstellen, bs, text)
        erg["uebertragung"] = {"ampel": lauf.ampel(), "zaehlung": lauf.zaehlen(),
                               "vorgaenge": [{"ziel": e.vorgang.ziel, "baustein": e.vorgang.baustein_id,
                                              "version": e.vorgang.version, "ergebnis": e.ergebnis,
                                              "versuche": e.versuche, "meldung": e.meldung} for e in lauf.ergebnisse]}
    return erg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ordner")
    ap.add_argument("--pruefer", default="http://pruefer:8100")
    ap.add_argument("--gegenstellen", default="")
    ap.add_argument("--protokoll", default=f"aus/protokoll-{datetime.date.today()}.jsonl")
    a = ap.parse_args()
    ordner = Path(a.ordner)
    erg = ein_demonstrator(ordner.parent, ordner.name, a.pruefer, a.gegenstellen or None, Path(a.protokoll))
    print(erg["text"])
    print(json.dumps({k: v for k, v in erg.items() if k not in ("text", "bericht")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
