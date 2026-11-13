"""Nachgebildete Gegenstellen für Tests und Vorführung (simuliert, keine echten Werkzeuge).

Sie verhalten sich so, wie es die Integration aushalten muss: sie prüfen, lehnen mit Grund ab, melden Konflikte und
lassen sich gezielt stören. In einem Projekt treten an ihre Stelle die echten Zugänge der Werkzeuge.

  /ki/bausteine          POST Baustein, GET /ki/bausteine/<id>?version=aktuell|x.y.z
  /modell/staende        POST neuer Stand mit Vorgänger; paralleler Stand -> 409, nichts wird überschrieben
  /graph/tripel          POST Turtle; unbekannter Begriff -> 422 (offene Referenz), sonst je Kennung+Version einmal
  /_stoerung             POST {"ziel": "ki|modell|graph", "art": "aus|antwort_verloren", "anzahl": n}
  /_stand                GET  Zähler: gespeicherte Objekte und echte Schreibvorgänge je Ziel (Dublettenprüfung)
  /_zuruecksetzen        POST alles leeren
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from rdflib import Graph, URIRef

SY = "https://example.org/bausteine/"
BEGRIFFE = {f"{SY}begriff/{b}" for b in ("Greifer", "Antrieb", "Kamera", "Steuerrechner", "Roboterarm")}
_sperre = threading.Lock()


def _neu():
    return {"ki": {}, "modell": {}, "graph": Graph(), "schluessel": {"ki": {}, "modell": {}, "graph": {}},
            "schreibvorgaenge": {"ki": 0, "modell": 0, "graph": 0}, "stoerung": {}}


S = _neu()


def _sv(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


class H(BaseHTTPRequestHandler):
    def _antwort(self, code: int, daten: dict):
        roh = json.dumps(daten, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def log_message(self, *a):
        pass

    def _stoerung(self, ziel: str, phase: str) -> bool:
        s = S["stoerung"].get(ziel)
        if s and s["anzahl"] > 0 and s["art"] == phase:
            s["anzahl"] -= 1
            return True
        return False

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        if u.path == "/_stand":
            with _sperre:
                ki = sum(len(v) for v in S["ki"].values())
                modell = sum(len(v["staende"]) for v in S["modell"].values())
                knoten = len(set(S["graph"].subjects(URIRef(f"{SY}bausteinId"), None)))
                return self._antwort(200, {"gespeichert": {"ki": ki, "modell": modell, "graph": knoten},
                                           "schreibvorgaenge": S["schreibvorgaenge"]})
        if u.path.startswith("/ki/bausteine/"):
            bid = u.path.rsplit("/", 1)[1]
            version = parse_qs(u.query).get("version", ["aktuell"])[0]
            staende = S["ki"].get(bid, {})
            if not staende:
                return self._antwort(404, {"meldung": f"Baustein {bid} unbekannt"})
            if version == "aktuell":
                version = max(staende, key=_sv)
            if version not in staende:
                return self._antwort(404, {"meldung": f"Version {version} von {bid} unbekannt; bekannt: "
                                                      f"{', '.join(sorted(staende, key=_sv))}. Keine Ersatzantwort."})
            b = staende[version]
            frueher = sorted((v for v in staende if _sv(v) < _sv(version)), key=_sv)
            notiz = ""
            if frueher:
                alt = {a["name"]: a["wert"] for a in staende[frueher[-1]]["attribute"]}
                neu = {a["name"]: a["wert"] for a in b["attribute"]}
                aend = [f"{k} {alt.get(k)} → {neu[k]}" for k in neu if alt.get(k) != neu[k]]
                zneu = sorted(set(b["zustaende"]) - set(staende[frueher[-1]]["zustaende"]))
                notiz = f"Neu gegenüber {frueher[-1]}: " + "; ".join(aend + [f"Zustand „{z}“" for z in zneu])
            return self._antwort(200, {**b, "aenderungsnotiz": notiz})
        self._antwort(404, {"meldung": "unbekannter Pfad"})

    def do_POST(self):  # noqa: N802
        global S
        u = urlparse(self.path)
        roh = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        schl = self.headers.get("Idempotency-Key", "")
        if u.path == "/_zuruecksetzen":
            with _sperre:
                S = _neu()
            return self._antwort(200, {"ok": True})
        if u.path == "/_stoerung":
            d = json.loads(roh)
            S["stoerung"][d["ziel"]] = {"art": d.get("art", "aus"), "anzahl": int(d.get("anzahl", 1))}
            return self._antwort(200, {"ok": True})
        ziel = {"/ki/bausteine": "ki", "/modell/staende": "modell", "/graph/tripel": "graph"}.get(u.path)
        if not ziel:
            return self._antwort(404, {"meldung": "unbekannter Pfad"})
        if self._stoerung(ziel, "aus"):
            return self._antwort(503, {"meldung": "Gegenstelle nicht erreichbar (simuliert)"})
        with _sperre:
            if schl and schl in S["schluessel"][ziel]:
                code, antwort = S["schluessel"][ziel][schl]
                return self._antwort(200, {**antwort, "schon_vorhanden": True})
            code, antwort = getattr(self, f"_{ziel}")(roh)
            if code in (200, 201) and schl:
                S["schluessel"][ziel][schl] = (code, antwort)
        if self._stoerung(ziel, "antwort_verloren"):  # geschrieben, aber die Antwort kommt nicht an
            return self._antwort(503, {"meldung": "Antwort verloren (simuliert)"})
        self._antwort(code, antwort)

    def _ki(self, roh):
        b = json.loads(roh)
        S["ki"].setdefault(b["baustein_id"], {})[b["version"]] = b
        S["schreibvorgaenge"]["ki"] += 1
        return 201, {"meldung": f"{b['baustein_id']} {b['version']} gespeichert"}

    def _modell(self, roh):
        d = json.loads(roh)
        e = S["modell"].setdefault(d["baustein_id"], {"kopf": "", "staende": {}})
        if d["version"] in e["staende"]:
            if e["staende"][d["version"]]["sha256"] == d["sha256"]:
                return 200, {"meldung": "Stand schon vorhanden", "schon_vorhanden": True}
            return 409, {"meldung": f"Version {d['version']} gibt es schon mit anderem Inhalt; nichts überschrieben"}
        if e["kopf"] and d["vorgaenger"] != e["kopf"]:
            return 409, {"meldung": f"Paralleler Stand: aktueller Kopf ist {e['kopf']}, Ihr Vorgänger "
                                    f"{d['vorgaenger'] or '(keiner)'}; nichts überschrieben, bitte zusammenführen"}
        e["staende"][d["version"]] = d
        e["kopf"] = d["version"]
        S["schreibvorgaenge"]["modell"] += 1
        return 201, {"meldung": f"Stand {d['version']} angelegt (Vorgänger {d['vorgaenger'] or '–'})"}

    def _graph(self, roh):
        g = Graph().parse(data=roh.decode("utf-8"), format="turtle")
        unbekannt = sorted({str(o) for o in g.objects(None, URIRef(f"{SY}begriff")) if str(o) not in BEGRIFFE})
        if unbekannt:
            return 422, {"meldung": f"Begriff im Wissensgraph unbekannt: {', '.join(unbekannt)} (offene Referenz an die Zuständigen "
                                    f"des Wissensgraphen); nichts geschrieben"}
        for t in g:
            S["graph"].add(t)
        S["schreibvorgaenge"]["graph"] += 1
        return 201, {"meldung": f"{len(g)} Tripel übernommen"}


if __name__ == "__main__":
    print("Gegenstellen bereit (simuliert) auf :8200", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8200), H).serve_forever()
