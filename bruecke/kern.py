"""Gemeinsamer Adapterkern: einmal gebaut, von allen Adaptern genutzt.

Für jeden Vorgang (Baustein, Version, Operation, Ziel):
  1. Prüfung   - die Nutzlast wird gegen das vereinbarte Schema geprüft, bevor etwas gesendet wird
  2. Schlüssel - aus Baustein-ID, Version, Operation und Ziel; die Gegenstelle schreibt einen Schlüssel nur einmal
  3. Wiederholung - nicht erreichbar: wenige Versuche mit wachsender Pause, danach „offen“ im Protokoll; der nächste Lauf holt ihn nach
  4. Protokoll - eine Zeile je Vorgang (JSON Lines), maschinenlesbar; Zugangsdaten stehen nie darin
Ampel der Übertragung je Lauf (nicht zu verwechseln mit der Ampel des Berichts): grün = alles übertragen; gelb = vollständig, aber mit gemeldeten Hinweisen (Konflikt, offene Referenz);
rot = mindestens ein Vorgang offen. Teilergebnisse gelten nie als Erfolg.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

UEBERTRAGEN, SCHON_DA, KONFLIKT, ABGELEHNT, OFFEN, UNGUELTIG = (
    "übertragen", "schon vorhanden (keine Dublette)", "Konflikt gemeldet", "abgelehnt mit Grund", "offen",
    "vor dem Senden abgelehnt")


@dataclass
class Vorgang:
    ziel: str
    baustein_id: str
    version: str
    operation: str
    nutzlast: dict | str
    art: str = "application/json"

    @property
    def schluessel(self) -> str:
        roh = f"{self.ziel}|{self.baustein_id}|{self.version}|{self.operation}"
        return hashlib.sha256(roh.encode()).hexdigest()[:16]


@dataclass
class Ergebnis:
    vorgang: Vorgang
    ergebnis: str
    versuche: int
    code: int | None = None
    meldung: str = ""


class NichtErreichbar(Exception):
    pass


def http(methode: str, url: str, daten: bytes | None = None, art: str = "application/json",
         kopf: dict | None = None, zeit: float = 5.0) -> tuple[int, dict]:
    anfrage = urllib.request.Request(url, data=daten, method=methode,
                                     headers={"Content-Type": art, **(kopf or {})})
    try:
        with urllib.request.urlopen(anfrage, timeout=zeit) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code in (502, 503, 504):
            raise NichtErreichbar(f"HTTP {e.code}") from e
        try:
            return e.code, json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise NichtErreichbar(str(e)) from e


@dataclass
class Lauf:
    protokoll: Path
    versuche: int = 3
    pause_s: float = 0.2
    lauf_id: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    ergebnisse: list[Ergebnis] = field(default_factory=list)

    def senden(self, adapter, vorgang: Vorgang) -> Ergebnis:
        fehler = adapter.pruefe(vorgang.nutzlast)
        if fehler:
            return self._merke(Ergebnis(vorgang, UNGUELTIG, 0, None, fehler))
        for n in range(1, self.versuche + 1):
            try:
                code, antwort = adapter.uebertragen(vorgang)
            except NichtErreichbar as e:
                if n == self.versuche:
                    return self._merke(Ergebnis(vorgang, OFFEN, n, None, f"nicht erreichbar ({e}); im Protokoll als offen"))
                time.sleep(self.pause_s * 2 ** (n - 1))
                continue
            if code in (200, 201):
                art = SCHON_DA if antwort.get("schon_vorhanden") else UEBERTRAGEN
                return self._merke(Ergebnis(vorgang, art, n, code, antwort.get("meldung", "")))
            if code == 409:
                return self._merke(Ergebnis(vorgang, KONFLIKT, n, code, antwort.get("meldung", "")))
            return self._merke(Ergebnis(vorgang, ABGELEHNT, n, code, antwort.get("meldung", "")))
        raise AssertionError("unerreichbar")

    def _merke(self, e: Ergebnis) -> Ergebnis:
        self.ergebnisse.append(e)
        zeile = {"lauf": self.lauf_id, "zeit": datetime.datetime.now().isoformat(timespec="milliseconds"),
                 "ziel": e.vorgang.ziel, "schluessel": e.vorgang.schluessel, "baustein": e.vorgang.baustein_id,
                 "version": e.vorgang.version, "operation": e.vorgang.operation, "ergebnis": e.ergebnis,
                 "versuche": e.versuche, "code": e.code, "meldung": e.meldung}
        self.protokoll.parent.mkdir(parents=True, exist_ok=True)
        with self.protokoll.open("a", encoding="utf-8") as f:
            f.write(json.dumps(zeile, ensure_ascii=False) + "\n")
        return e

    def ampel(self) -> str:
        arten = {e.ergebnis for e in self.ergebnisse}
        if arten & {OFFEN, UNGUELTIG}:
            return "rot"
        if arten & {KONFLIKT, ABGELEHNT}:
            return "gelb"
        return "grün"

    def zaehlen(self) -> dict:
        z: dict[str, int] = {}
        for e in self.ergebnisse:
            z[e.ergebnis] = z.get(e.ergebnis, 0) + 1
        return z


class Adapter:
    """Basis: Schema prüfen. Die Unterklassen sagen nur, wohin und wie übertragen wird."""
    ziel = ""
    schema: dict = {}

    def __init__(self, basis: str):
        self.basis = basis.rstrip("/")

    def pruefe(self, nutzlast) -> str:
        try:
            jsonschema.validate(nutzlast, self.schema)
        except jsonschema.ValidationError as e:
            return f"Schema: {e.message}"
        return ""

    def uebertragen(self, v: Vorgang) -> tuple[int, dict]:
        raise NotImplementedError
