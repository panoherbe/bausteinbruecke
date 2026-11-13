"""Das Testszenario „eine Bausteinänderung erreicht alle Werkzeuge“ und die Störfälle, automatisch und wiederholbar.

„Eine Bausteinänderung erreicht alle Gegenstellen“: Das Greifermodul geht von 1.2.0 auf 1.3.0 (neue maximale
Greifkraft, neuer Zustand „quittiert“). Braucht den OMG-Prüfdienst und die nachgebildeten Gegenstellen
(`docker compose run --rm test`).
"""
import copy
import json
import os
from pathlib import Path

import pytest

from bruecke import abbilden as ab
from bruecke import rueckweg, vergleich
from bruecke.adapter import KiAssistenz, Modellverwaltung, Wissensgraph, als_rdf
from bruecke.kern import ABGELEHNT, KONFLIKT, OFFEN, SCHON_DA, UEBERTRAGEN, UNGUELTIG, Lauf, Vorgang, http
from bruecke.lauf import anforderungen, bausteine, pruefen, uebertragen

PRUEFER = os.environ.get("PRUEFER", "http://pruefer:8100")
GEGEN = os.environ.get("GEGENSTELLEN", "http://gegenstellen:8200")
BSP = Path(__file__).parent.parent / "beispiele"


def stand():
    return http("GET", f"{GEGEN}/_stand")[1]


def stoerung(ziel, art, anzahl):
    http("POST", f"{GEGEN}/_stoerung", json.dumps({"ziel": ziel, "art": art, "anzahl": anzahl}).encode())


@pytest.fixture(autouse=True)
def leer():
    http("POST", f"{GEGEN}/_zuruecksetzen", b"{}")


@pytest.fixture
def lauf(tmp_path):
    return Lauf(tmp_path / "protokoll.jsonl", pause_s=0.01)


@pytest.fixture(scope="module")
def ra():
    alt = bausteine(BSP / "roboterarm", {"greifermodul-1.3.0.yaml"})
    neu = bausteine(BSP / "roboterarm", {"greifermodul-1.2.0.yaml"})
    anf = anforderungen(BSP, "roboterarm")
    t1, b1 = ab.abbilden("Roboterarm", alt, anf)
    t2, b2 = ab.abbilden("Roboterarm", neu, anf)
    return {"alt": alt, "neu": neu, "t1": t1, "t2": t2, "b1": b1, "b2": b2,
            "x1": pruefen(PRUEFER, t1), "x2": pruefen(PRUEFER, t2)}


def gm(bs):
    return next(b for b in bs if b["baustein_id"] == "B-GM")


# --- Abbildung und Rückweg --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("demonstrator", ["roboterarm", "flurfoerderfahrzeug"])
def test_abbildung_ist_im_werkzeug_gueltig_und_kommt_vollstaendig_zurueck(demonstrator):
    bs = bausteine(BSP / demonstrator, {"greifermodul-1.3.0.yaml"})
    paket = ab.paketname(demonstrator)
    text, bericht = ab.abbilden(paket, bs, anforderungen(BSP, demonstrator))
    x = pruefen(PRUEFER, text)
    assert x["ok"], x["meldungen"]
    assert not [m for m in x["meldungen"] if "WARNING" in m]
    rw = rueckweg.pruefen(x["elemente"], paket, bs, bericht)
    assert rw["wiedergefunden"] == rw["geprueft"] > 40, rw["verloren"]


def test_bericht_nennt_jede_angabe_und_verschweigt_nichts(ra):
    s = {(e["baustein"], e["feld"]): e["status"] for e in ra["b1"]}
    assert s[("B-GM", "cad_datei")] == ab.NICHT
    assert s[("B-GM", "erfuellt.R-12")] == ab.OFFEN
    assert s[("B-GM", "zustaende.stoerung")] == ab.UMGEWANDELT
    assert s[("B-GA", "attribute.maxDrehzahl")] == ab.UMGEWANDELT
    assert s[("B-KM", "messgroesse")] == ab.UMGEWANDELT
    for b in ra["alt"]:  # jedes Feld der Quelle taucht im Bericht auf
        felder = {e["feld"].split(".")[0] for e in ra["b1"] if e["baustein"] == b["baustein_id"]}
        assert set(b) <= felder | {"attribute", "schnittstellen", "zustaende", "funktionen", "erfuellt"}
    assert ab.zusammenfassung(ra["b1"])["ampel"] == "gelb"


def test_falscher_text_wird_vom_werkzeug_abgelehnt():
    x = pruefen(PRUEFER, "package Kaputt { part def A { attribute x :> ISQ::gibtsNicht = 1; } }")
    assert not x["ok"]


# --- Schritt 1: Mapping der neuen Version ---------------------------------------------------------------------------

def test_schritt1_neue_version_genau_die_aenderungen(ra):
    d = vergleich.quellstaende(gm(ra["alt"]), gm(ra["neu"]))
    assert d["geaendert"] == {"attribute.maxGreifkraft": ["140 N", "160 N"], "version": ["1.2.0", "1.3.0"]}
    assert d["neu"] == ["vorgaenger", "zustaende.quittiert"] and d["weg"] == []


def test_schritt1_im_werkzeug_gleiche_aenderungen_und_baustein_id(ra):
    d = vergleich.modellstaende(ra["x1"]["elemente"], ra["x2"]["elemente"], "Roboterarm::Greifermodul")
    assert "Roboterarm::GreifermodulZustaende::quittiert" in vergleich.modellstaende(
        ra["x1"]["elemente"], ra["x2"]["elemente"], "Roboterarm::GreifermodulZustaende")["neu"]
    assert d["geaendert"]["Roboterarm::Greifermodul::maxGreifkraft"] == [["140"], ["160"]]
    assert d["weg"] == []
    _, qn = rueckweg.index(ra["x2"]["elemente"])
    assert qn["Roboterarm::Greifermodul"]["declaredShortName"] == "B-GM"


def test_werkzeug_vergibt_bei_jedem_einlesen_neue_element_ids(ra):
    """Darum hängt Identität an Baustein-ID und Version, nie an Werkzeug-IDs."""
    nochmal = pruefen(PRUEFER, ra["t1"])
    a = {e["identity"]["@id"] for e in ra["x1"]["elemente"]}
    b = {e["identity"]["@id"] for e in nochmal["elemente"]}
    assert len(a & b) < len(a) * 0.1


# --- Schritt 2: Varianten in der Modellverwaltung -------------------------------------------------------------------------

def test_schritt2_paralleler_stand_meldet_konflikt_und_ueberschreibt_nichts(ra, lauf):
    uebertragen(lauf, GEGEN, ra["alt"], ra["t1"])
    neu = gm(ra["neu"])
    uebertragen(lauf, GEGEN, [neu], ra["t2"], vorgaenger={"B-GM": "1.2.0"})
    parallel = {**copy.deepcopy(neu), "version": "1.3.1"}
    mm = Modellverwaltung(GEGEN)
    e = lauf.senden(mm, Vorgang(mm.ziel, "B-GM", "1.3.1", "stand anlegen",
                                Modellverwaltung.nutzlast(parallel, ra["t2"], "1.2.0")))
    assert e.ergebnis == KONFLIKT and "nichts überschrieben" in e.meldung
    assert stand()["gespeichert"]["modell"] == 4  # GA, GM 1.2.0, KM, GM 1.3.0
    assert lauf.ampel() == "gelb"


# --- Schritt 3: Wissensgraph ------------------------------------------------------------------------------------------

def test_schritt3_graph_kennt_nachfolger_und_lehnt_unbekannte_begriffe_ab(ra, lauf):
    kg = Wissensgraph(GEGEN)
    neu = gm(ra["neu"])
    assert kg.pruefe(als_rdf(neu)) == ""
    assert lauf.senden(kg, Vorgang(kg.ziel, "B-GM", "1.3.0", "knoten", als_rdf(neu))).ergebnis == UEBERTRAGEN
    ls = bausteine(BSP / "flurfoerderfahrzeug")
    scanner = next(b for b in ls if b["baustein_id"] == "B-LS")
    e = lauf.senden(kg, Vorgang(kg.ziel, "B-LS", "1.0.0", "knoten", als_rdf(scanner)))
    assert e.ergebnis == ABGELEHNT and "offene Referenz" in e.meldung


def test_schritt3_gegenstelle_aus_wird_offen_und_spaeter_ohne_dublette_nachgeholt(ra, lauf, tmp_path):
    kg = Wissensgraph(GEGEN)
    v = Vorgang(kg.ziel, "B-GM", "1.2.0", "knoten", als_rdf(gm(ra["alt"])))
    stoerung("graph", "aus", 3)
    assert lauf.senden(kg, v).ergebnis == OFFEN and lauf.ampel() == "rot"
    assert stand()["schreibvorgaenge"]["graph"] == 0
    zweiter = Lauf(tmp_path / "p2.jsonl", pause_s=0.01)
    assert zweiter.senden(kg, v).ergebnis == UEBERTRAGEN
    assert zweiter.senden(kg, v).ergebnis == SCHON_DA
    assert stand()["schreibvorgaenge"]["graph"] == 1


def test_antwort_verloren_wiederholung_schreibt_nicht_doppelt(ra, lauf):
    mm = Modellverwaltung(GEGEN)
    stoerung("modell", "antwort_verloren", 1)
    b = gm(ra["alt"])
    e = lauf.senden(mm, Vorgang(mm.ziel, "B-GM", "1.2.0", "stand anlegen", Modellverwaltung.nutzlast(b, ra["t1"])))
    assert e.ergebnis == SCHON_DA and e.versuche == 2
    assert stand()["schreibvorgaenge"]["modell"] == 1 and stand()["gespeichert"]["modell"] == 1


# --- Schritt 4: Assistenz liest den aktuellen Stand ------------------------------------------------------------------

def test_schritt4_assistenz_bekommt_aktuellen_stand_mit_notiz_und_keine_ersatzantwort(ra, lauf):
    uebertragen(lauf, GEGEN, ra["alt"], ra["t1"])
    uebertragen(lauf, GEGEN, [gm(ra["neu"])], ra["t2"], vorgaenger={"B-GM": "1.2.0"})
    ki = KiAssistenz(GEGEN)
    code, a = ki.lesen("B-GM")
    assert code == 200 and a["version"] == "1.3.0"
    assert "maxGreifkraft 140 → 160" in a["aenderungsnotiz"] and "quittiert" in a["aenderungsnotiz"]
    code, a = ki.lesen("B-GM", "9.9.9")
    assert code == 404 and "Keine Ersatzantwort" in a["meldung"]


# --- Prüfung vor dem Senden -------------------------------------------------------------------------------------------

def test_ungueltige_nutzlast_wird_nicht_gesendet(ra, lauf):
    ki = KiAssistenz(GEGEN)
    kaputt = {**KiAssistenz.nutzlast(gm(ra["alt"]), ra["t1"]), "version": "1.3"}
    e = lauf.senden(ki, Vorgang(ki.ziel, "B-GM", "1.3", "baustein schreiben", kaputt))
    assert e.ergebnis == UNGUELTIG and "Schema" in e.meldung
    assert stand()["schreibvorgaenge"]["ki"] == 0 and lauf.ampel() == "rot"


def test_protokoll_hat_eine_zeile_je_vorgang_ohne_zugangsdaten(ra, lauf):
    uebertragen(lauf, GEGEN, ra["alt"], ra["t1"])
    zeilen = [json.loads(z) for z in lauf.protokoll.read_text(encoding="utf-8").splitlines()]
    assert len(zeilen) == 9 and all(z["ergebnis"] == UEBERTRAGEN for z in zeilen)
    assert not any(w in lauf.protokoll.read_text().lower() for w in ("passwort", "token", "authorization"))
