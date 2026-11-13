"""Messlauf: alle Zahlen für README, Vorführung und Bewertung kommen aus diesem einen Lauf.

    docker compose up -d --wait pruefer gegenstellen && docker compose run --rm messen

Schreibt nach nachweis/<datum>/: ergebnis.json, die erzeugten SysML-Texte, die Berichte, das Übertragungsprotokoll,
BERICHT.md; dazu demo/daten.js für die Vorführung im Browser. Die Skalierung (10-, 100-fach) vervielfältigt die
Beispielbausteine und ist als simuliert gekennzeichnet.
"""
from __future__ import annotations

import copy
import datetime
import inspect
import json
import os
import platform
import resource
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from bruecke import abbilden as ab
from bruecke import adapter as ad
from bruecke import einheiten, rueckweg, vergleich
from bruecke.adapter import KiAssistenz, Modellverwaltung, Wissensgraph, als_rdf
from bruecke.kern import Lauf, Vorgang, http
from bruecke.lauf import anforderungen, bausteine, pruefen, uebertragen, zugangstest

PRUEFER = os.environ.get("PRUEFER", "http://pruefer:8100")
GEGEN = os.environ.get("GEGENSTELLEN", "http://gegenstellen:8200")
BSP = Path("beispiele")
HEUTE = datetime.date.today().isoformat()
AUS = Path("nachweis") / HEUTE
AUS.mkdir(parents=True, exist_ok=True)
PROT = AUS / "protokoll.jsonl"
PROT.unlink(missing_ok=True)


def gegen(pfad, daten=None):
    return http("POST" if daten is not None else "GET", f"{GEGEN}{pfad}",
                json.dumps(daten).encode() if daten is not None else None)[1]


def vorgaenge(lauf: Lauf, ab_index=0):
    return [{"ziel": e.vorgang.ziel, "baustein": e.vorgang.baustein_id, "version": e.vorgang.version,
             "ergebnis": e.ergebnis, "versuche": e.versuche, "meldung": e.meldung} for e in lauf.ergebnisse[ab_index:]]


def demonstrator(name, ausser=frozenset()):
    bs = bausteine(BSP / name, set(ausser))
    paket = ab.paketname(name)
    t = time.perf_counter()
    text, bericht = ab.abbilden(paket, bs, anforderungen(BSP, name))
    t_ab = time.perf_counter() - t
    x = pruefen(PRUEFER, text)
    rw = rueckweg.pruefen(x["elemente"], paket, bs, bericht)
    return bs, paket, text, bericht, x, rw, t_ab


def zeilen(obj) -> int:
    return len([z for z in inspect.getsource(obj).splitlines() if z.strip() and not z.strip().startswith("#")])


def regelzeilen(datei: Path) -> int:
    return len([z for z in datei.read_text(encoding="utf-8").splitlines() if z.strip() and not z.strip().startswith("#")])


def main():
    erg = {"datum": HEUTE, "zeit": datetime.datetime.now().isoformat(timespec="seconds"),
           "rechner": f"{platform.machine()}, {os.cpu_count()} Kerne, Python {platform.python_version()}",
           "hinweis": "Synthetische Beispielbausteine; Gegenstellen nachgebildet (simuliert); Werkzeugprüfung mit der "
                      "OMG-SysML-v2-Pilotimplementierung."}
    gegen("/_zuruecksetzen", {})
    erg["zugangstest"] = zugangstest(GEGEN)

    # 1. Erster Stand beider Demonstratoren: abbilden, im Werkzeug prüfen, Rückweg, übertragen
    stand1 = {}
    lauf = Lauf(PROT, pause_s=0.05)
    for name, ausser in (("roboterarm", {"greifermodul-1.3.0.yaml"}), ("flurfoerderfahrzeug", set())):
        bs, paket, text, bericht, x, rw, t_ab = demonstrator(name, ausser)
        (AUS / f"{name}-stand1.sysml").write_text(text, encoding="utf-8")
        n0 = len(lauf.ergebnisse)
        t = time.perf_counter()
        uebertragen(lauf, GEGEN, bs, text)
        stand1[name] = {"bs": bs, "text": text, "x": x}
        erg.setdefault("demonstratoren", {})[name] = {
            "paket": paket, "bausteine": [f"{b['baustein_id']} {b['name']} {b['version']}" for b in bs],
            "bericht": bericht, "zusammenfassung": ab.zusammenfassung(bericht),
            "werkzeug": {"ok": x["ok"], "warnungen": [m for m in x["meldungen"] if "WARNING" in m],
                         "fehler": [m for m in x["meldungen"] if "ERROR" in m], "dauer_s": x["dauer_s"],
                         "kernel": x["kernel"]},
            "rueckweg": {k: rw[k] for k in ("elemente", "benannt", "geprueft", "wiedergefunden", "verloren")},
            "dauer_abbilden_s": round(t_ab, 4), "dauer_uebertragen_s": round(time.perf_counter() - t, 3),
            "uebertragung": vorgaenge(lauf, n0)}
    erg["lauf1"] = {"ampel": lauf.ampel(), "zaehlung": lauf.zaehlen()}

    # 2. Neue Version des Greifermoduls: Vergleich in der Quelle und im Werkzeug, Übertragung mit Versionskette
    alt_bs, alt_x = stand1["roboterarm"]["bs"], stand1["roboterarm"]["x"]
    bs2, paket2, text2, bericht2, x2, rw2, _ = demonstrator("roboterarm", {"greifermodul-1.2.0.yaml"})
    (AUS / "roboterarm-stand2.sysml").write_text(text2, encoding="utf-8")
    gm1 = next(b for b in alt_bs if b["baustein_id"] == "B-GM")
    gm2 = next(b for b in bs2 if b["baustein_id"] == "B-GM")
    nochmal = pruefen(PRUEFER, stand1["roboterarm"]["text"])
    ids = lambda xx: {e["identity"]["@id"] for e in xx["elemente"]}  # noqa: E731
    lauf2 = Lauf(PROT, pause_s=0.05)
    uebertragen(lauf2, GEGEN, [gm2], text2, vorgaenger={"B-GM": "1.2.0"})
    erg["neue_version"] = {
        "quelle": vergleich.quellstaende(gm1, gm2),
        "werkzeug_baustein": vergleich.modellstaende(alt_x["elemente"], x2["elemente"], "Roboterarm::Greifermodul"),
        "werkzeug_zustaende": vergleich.modellstaende(alt_x["elemente"], x2["elemente"],
                                                      "Roboterarm::GreifermodulZustaende"),
        "werkzeug_ok": x2["ok"], "rueckweg": {k: rw2[k] for k in ("geprueft", "wiedergefunden")},
        "zusammenfassung": ab.zusammenfassung(bericht2),
        "element_ids": {"gesamt": len(ids(alt_x)), "gleich_bei_zweitem_einlesen": len(ids(alt_x) & ids(nochmal)),
                        "gleich_alt_neu": len(ids(alt_x) & ids(x2))},
        "uebertragung": vorgaenge(lauf2), "ampel": lauf2.ampel()}
    code, a = KiAssistenz(GEGEN).lesen("B-GM")
    code9, a9 = KiAssistenz(GEGEN).lesen("B-GM", "9.9.9")
    erg["assistenz"] = {"aktuell": {"http": code, "version": a.get("version"), "notiz": a.get("aenderungsnotiz")},
                        "unbekannte_version": {"http": code9, "meldung": a9.get("meldung")}}

    # 3. Störfälle
    lauf3 = Lauf(PROT, pause_s=0.05)
    mm, kg = Modellverwaltung(GEGEN), Wissensgraph(GEGEN)
    parallel = {**copy.deepcopy(gm2), "version": "1.3.1"}
    konflikt = lauf3.senden(mm, Vorgang(mm.ziel, "B-GM", "1.3.1", "stand anlegen",
                                        Modellverwaltung.nutzlast(parallel, text2, "1.2.0")))
    ga = next(b for b in alt_bs if b["baustein_id"] == "B-GA")
    ga2 = {**copy.deepcopy(ga), "version": "2.0.1", "vorgaenger": "2.0.0"}
    ga2["attribute"][0]["wert"] = 14
    vor = gegen("/_stand")
    gegen("/_stoerung", {"ziel": "graph", "art": "aus", "anzahl": 3})
    t = time.perf_counter()
    aus = lauf3.senden(kg, Vorgang(kg.ziel, "B-GA", "2.0.1", "knoten schreiben", als_rdf(ga2)))
    t_aus = time.perf_counter() - t
    ampel_aus = lauf3.ampel()
    nach_aus = gegen("/_stand")
    lauf4 = Lauf(PROT, pause_s=0.05)
    nachgeholt = lauf4.senden(kg, Vorgang(kg.ziel, "B-GA", "2.0.1", "knoten schreiben", als_rdf(ga2)))
    gegen("/_stoerung", {"ziel": "modell", "art": "antwort_verloren", "anzahl": 1})
    verloren = lauf4.senden(mm, Vorgang(mm.ziel, "B-GA", "2.0.1", "stand anlegen",
                                        Modellverwaltung.nutzlast(ga2, stand1["roboterarm"]["text"].replace(
                                            "nennmoment :> ISQ::torque = 12", "nennmoment :> ISQ::torque = 14"))))
    wiederholt = lauf4.senden(mm, Vorgang(mm.ziel, "B-GA", "2.0.1", "stand anlegen",
                                          Modellverwaltung.nutzlast(ga2, stand1["roboterarm"]["text"].replace(
                                              "nennmoment :> ISQ::torque = 12", "nennmoment :> ISQ::torque = 14"))))
    ftf = stand1["flurfoerderfahrzeug"]["bs"]
    ls = next(b for b in ftf if b["baustein_id"] == "B-LS")
    ki = KiAssistenz(GEGEN)
    kaputt = {**KiAssistenz.nutzlast(gm2, text2), "version": "1.3"}
    ungueltig = lauf4.senden(ki, Vorgang(ki.ziel, "B-GM", "1.3", "baustein schreiben", kaputt))
    nach = gegen("/_stand")
    erg["stoerfaelle"] = {
        "paralleler_stand": {"ergebnis": konflikt.ergebnis, "meldung": konflikt.meldung},
        "gegenstelle_aus": {"ergebnis": aus.ergebnis, "versuche": aus.versuche, "dauer_s": round(t_aus, 2),
                            "ampel": ampel_aus,
                            "geschrieben": nach_aus["schreibvorgaenge"]["graph"] - vor["schreibvorgaenge"]["graph"]},
        "nachgeholt": {"ergebnis": nachgeholt.ergebnis, "versuche": nachgeholt.versuche},
        "antwort_verloren": {"ergebnis": verloren.ergebnis, "versuche": verloren.versuche},
        "nochmal_gesendet": {"ergebnis": wiederholt.ergebnis},
        "unbekannter_begriff": next(v for v in erg["demonstratoren"]["flurfoerderfahrzeug"]["uebertragung"]
                                    if v["baustein"] == ls["baustein_id"] and v["ziel"].startswith("Wissensgraph")),
        "vor_dem_senden_abgelehnt": {"ergebnis": ungueltig.ergebnis, "meldung": ungueltig.meldung},
        "stand_gegenstellen": nach,
        "dubletten": {z: nach["schreibvorgaenge"][z] - nach["gespeichert"][z] for z in ("ki", "modell", "graph")}}

    # 4. KMU-Bewertung: Aufwand, Ressourcen, Skalierung (vervielfältigt = simuliert)
    skal = []
    for faktor in (1, 10, 100):
        bs = []
        for k in range(faktor):
            for b in stand1["roboterarm"]["bs"] + stand1["flurfoerderfahrzeug"]["bs"]:
                c = copy.deepcopy(b)
                if k:
                    c["baustein_id"] += f"-{k}"
                    c["name"] += f"K{k}"
                    for f in c.get("funktionen", []):
                        f["id"] += f"-{k}"
                        f["name"] += f"K{k}"
                bs.append(c)
        anf = anforderungen(BSP, "roboterarm") + anforderungen(BSP, "flurfoerderfahrzeug")
        t = time.perf_counter()
        text, bericht = ab.abbilden("Skalierung", bs, anf)
        t_ab = time.perf_counter() - t
        x = pruefen(PRUEFER, text)
        t = time.perf_counter()
        rw = rueckweg.pruefen(x["elemente"], "Skalierung", bs, bericht) if "elemente" in x else {"geprueft": 0,
                                                                                              "wiedergefunden": 0}
        t_rw = time.perf_counter() - t
        gegen("/_zuruecksetzen", {})
        ls_ = Lauf(Path("/tmp/skalierung.jsonl"), pause_s=0.01)
        t = time.perf_counter()
        uebertragen(ls_, GEGEN, bs, text)
        t_ue = time.perf_counter() - t
        skal.append({"faktor": faktor, "bausteine": len(bs), "angaben": len(bericht), "zeilen_sysml": text.count("\n"),
                     "werkzeug_ok": x["ok"], "export_ok": "elemente" in x, "export_fehler": x.get("export_fehler", ""),
                     "elemente": len(x.get("elemente", [])),
                     "dauer_abbilden_s": round(t_ab, 3), "dauer_werkzeug_s": x["dauer_s"],
                     "dauer_rueckweg_s": round(t_rw, 3), "dauer_uebertragen_s": round(t_ue, 2),
                     "vorgaenge": len(ls_.ergebnisse), "ampel": ls_.ampel(),
                     "rueckweg": f"{rw['wiedergefunden']}/{rw['geprueft']}",
                     "meldungen": [m for m in x["meldungen"] if "WARNING" not in m][:3],
                     "simuliert": faktor > 1})
        if faktor == 100:  # dieselben 600 Bausteine, aufgeteilt in Pakete zu je 60 (wie Teilsysteme)
            t = time.perf_counter()
            dauer, ok_alle, gef, gepr, elem = 0.0, True, 0, 0, 0
            for i in range(0, len(bs), 60):
                teil = bs[i:i + 60]
                tx, be = ab.abbilden(f"Teil{i // 60}", teil, anf)
                xx = pruefen(PRUEFER, tx)
                dauer += xx["dauer_s"]
                ok_alle &= xx["ok"] and "elemente" in xx
                if "elemente" in xx:
                    r = rueckweg.pruefen(xx["elemente"], f"Teil{i // 60}", teil, be)
                    gef, gepr, elem = gef + r["wiedergefunden"], gepr + r["geprueft"], elem + r["elemente"]
            skal.append({"faktor": 100, "bausteine": len(bs), "pakete": len(bs) // 60, "werkzeug_ok": ok_alle,
                         "elemente": elem, "dauer_werkzeug_s": round(dauer, 2),
                         "dauer_gesamt_s": round(time.perf_counter() - t, 2), "rueckweg": f"{gef}/{gepr}",
                         "simuliert": True})
    erg["skalierung"] = skal
    erg["aufwand"] = {
        "regel_komponente_zeilen": regelzeilen(Path("bruecke/regeln/komponente.yaml")),
        "regel_sensor_zeilen": regelzeilen(Path("bruecke/regeln/sensor.yaml")),
        "einheitentabelle_zeilen": len(einheiten.EINHEITEN),
        "adapter_zeilen": {"KI-Assistenz": zeilen(ad.KiAssistenz), "Modellverwaltung": zeilen(ad.Modellverwaltung),
                           "Wissensgraph": zeilen(ad.Wissensgraph)},
        "kern_zeilen": len([z for z in Path("bruecke/kern.py").read_text().splitlines() if z.strip()]),
        "speicher_mb_client": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "abhaengigkeiten": ["pyyaml (MIT)", "rdflib (BSD-3)", "pyshacl (Apache-2.0)", "jsonschema (MIT)",
                            "OMG SysML v2 Pilotimplementierung (EPL-2.0)"],
        "lizenzkosten_je_arbeitsplatz_eur": 0}

    # 5. Tests
    gegen("/_zuruecksetzen", {})
    t = time.perf_counter()
    subprocess.run(["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={AUS}/tests.xml"],
                   capture_output=True, text=True)
    s = ET.parse(AUS / "tests.xml").getroot().find("testsuite")
    erg["tests"] = {k: int(s.get(k)) for k in ("tests", "failures", "errors", "skipped")}
    erg["tests"]["dauer_s"] = round(time.perf_counter() - t, 1)
    erg["tests"]["namen"] = [c.get("name") for c in s.iter("testcase")]

    (AUS / "ergebnis.json").write_text(json.dumps(erg, ensure_ascii=False, indent=2), encoding="utf-8")
    demo = {k: erg[k] for k in ("datum", "neue_version", "assistenz", "stoerfaelle", "skalierung", "aufwand", "tests")}
    demo["demonstratoren"] = {k: {**v, "text": stand1[k]["text"]} for k, v in erg["demonstratoren"].items()}
    demo["neue_version"]["text"] = text2
    Path("demo/daten.js").write_text("window.DATEN = " + json.dumps(demo, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(json.dumps({k: erg[k] for k in ("lauf1", "assistenz", "stoerfaelle", "skalierung", "tests")},
                     ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
