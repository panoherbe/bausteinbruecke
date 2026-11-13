"""Bausteinbeschreibung (YAML) -> SysML-v2-Textnotation, mit Bericht für jede einzelne Angabe.

Jede Angabe landet in genau einer von vier Spalten:
  übernommen        steht unverändert im Modell
  umgewandelt       steht im Modell, aber in anderer Form (Regel und Grund im Bericht)
  nicht abbildbar   steht nicht im Modell (Grund im Bericht; die Quelle bleibt unverändert)
  offene Referenz   verweist auf etwas, das es im Zielstand (noch) nicht gibt
Nichts fällt still weg: Felder ohne Regel landen als „nicht abbildbar“ im Bericht.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .einheiten import EINHEITEN

REGELN = Path(__file__).parent / "regeln"
UEBERNOMMEN, UMGEWANDELT, NICHT, OFFEN = "übernommen", "umgewandelt", "nicht abbildbar", "offene Referenz"


def regel(typ: str) -> dict:
    """Regel eines Bausteintyps; „erbt“ übernimmt die Felder einer anderen Regel."""
    r = yaml.safe_load((REGELN / f"{typ}.yaml").read_text(encoding="utf-8"))
    if r.get("erbt"):
        basis = regel(r["erbt"])
        r["felder"] = {**basis["felder"], **r["felder"]}
    return r


def lade(pfad: Path) -> dict:
    return yaml.safe_load(Path(pfad).read_text(encoding="utf-8"))


def _kamel(name: str) -> str:
    return name[:1].lower() + name[1:]


def _text(s: str) -> str:
    """Text für doc-Kommentare und Strings: keine Kommentarenden, keine Anführungszeichen."""
    return str(s).replace("*/", "* /").replace('"', "'")


def _zahl(w) -> str:
    return repr(w) if isinstance(w, float) else str(w)


def abbilden(paket: str, bausteine: list[dict], anforderungen: list[dict]) -> tuple[str, list[dict]]:
    """Ein SysML-v2-Paket für einen Demonstrator und der Bericht dazu."""
    bericht: list[dict] = []
    anf = {a["id"]: a for a in anforderungen}

    def melde(b, feld, status, ziel, grund=""):
        bericht.append({"baustein": b["baustein_id"], "version": str(b["version"]), "name": b["name"], "feld": feld,
                        "status": status, "ziel": ziel, "grund": grund})

    ports, zustandsdefs, defs, nutzungen, satisfy, allocate, funktionen = set(), [], [], [], [], [], []
    benutzte_anf: dict[str, dict] = {}
    for b in bausteine:
        r = regel(b["typ"])
        felder = r["felder"]
        name, kurz = b["name"], b["baustein_id"]
        for feld in b:
            if feld not in felder:
                melde(b, feld, NICHT, "–", f"Für „{feld}“ ist keine Abbildung vereinbart; die Angabe bleibt in der "
                                          f"Quelle ({b[feld]}) und steht hier im Bericht.")
        zeilen = [f"    part def <'{kurz}'> {name} {{"]
        zeilen.append(f"        metadata Herkunft {{ bausteinId = \"{kurz}\"; version = \"{b['version']}\"; "
                      f"ebene = \"{b.get('ebene', '')}\"; vorgaenger = \"{b.get('vorgaenger', '')}\"; }}")
        for f in ("baustein_id", "name", "version", "typ", "ebene"):
            melde(b, f, UEBERNOMMEN, felder[f]["ziel"])
        if b.get("vorgaenger"):
            melde(b, "vorgaenger", UEBERNOMMEN, felder["vorgaenger"]["ziel"])
        if b.get("semantik"):
            s = b["semantik"]
            zeilen.append(f"        metadata Semantik {{ begriff = \"{_text(s['begriff'])}\"; iri = \"{s['iri']}\"; }}")
            melde(b, "semantik", UEBERNOMMEN, felder["semantik"]["ziel"], s["iri"])
        doc = _text(b.get("beschreibung", ""))
        if b.get("beschreibung"):
            melde(b, "beschreibung", UEBERNOMMEN, "doc")
        for feld, spec in felder.items():  # Felder, die eine Regel als Text umwandelt (z. B. Messgröße)
            if spec.get("umwandeln") and feld in b:
                doc += f" Messgröße: {_text(b[feld])}."
                melde(b, feld, UMGEWANDELT, spec["ziel"], spec["umwandeln"])
        if doc:
            zeilen.append(f"        doc /* {doc.strip()} */")
        for a in b.get("attribute", []):
            feld = f"attribute.{a['name']}"
            if "einheit" not in a:
                zeilen.append(f"        attribute {a['name']} : String = \"{_text(a['wert'])}\";")
                melde(b, feld, UEBERNOMMEN, "attribute : String", str(a["wert"]))
            elif a["einheit"] in EINHEITEN:
                groesse, einheit = EINHEITEN[a["einheit"]]
                zeilen.append(f"        attribute {a['name']} :> {groesse} = {_zahl(a['wert'])} [{einheit}];")
                melde(b, feld, UEBERNOMMEN, f"attribute :> {groesse} [{einheit}]", f"{a['wert']} {a['einheit']}")
            else:
                zeilen.append(f"        attribute {a['name']} : Real = {_zahl(a['wert'])} "
                              f"{{ doc /* Einheit laut Quelle: {a['einheit']} */ }}")
                melde(b, feld, UMGEWANDELT, "attribute : Real, Einheit im doc",
                      f"Die Einheit „{a['einheit']}“ hat (noch) keine Zeile in der Einheitentabelle; der Zahlwert "
                      f"{a['wert']} ist übernommen, die Einheit steht als Text daneben.")
        for p in b.get("schnittstellen", []):
            ports.add(p["art"])
            zeilen.append(f"        port {p['name']} : {p['art']};")
            melde(b, f"schnittstellen.{p['name']}", UEBERNOMMEN, f"port : {p['art']}")
        if b.get("zustaende"):
            zd = [f"    state def {name}Zustaende {{", f"        entry; then {b['zustaende'][0]['name']};"]
            for z in b["zustaende"]:
                if z.get("bedingung"):
                    zd.append(f"        state {z['name']} {{ doc /* Bedingung (informell): {_text(z['bedingung'])} */ }}")
                    melde(b, f"zustaende.{z['name']}", UMGEWANDELT, "state mit doc",
                          "Die Bedingung ist Freitext; sie steht als Text am Zustand, bis eine formale Form "
                          "festgelegt ist.")
                else:
                    zd.append(f"        state {z['name']};")
                    melde(b, f"zustaende.{z['name']}", UEBERNOMMEN, "state")
            zd.append("    }")
            zustandsdefs.append("\n".join(zd))
            zeilen.append(f"        exhibit state betrieb : {name}Zustaende;")
        zeilen.append("    }")
        defs.append("\n".join(zeilen))
        teil = _kamel(name)
        nutzungen.append(f"        part {teil} : {name};")
        for f in b.get("funktionen", []):
            funktionen.append(f"        action <'{f['id']}'> {f['name']} {{ doc /* {_text(f['text'])} */ }}")
            allocate.append(f"    allocate Funktionen::{f['name']} to {_kamel(paket)}.{teil};")
            melde(b, f"funktionen.{f['id']}", UEBERNOMMEN, "action und allocate")
        for rid in b.get("erfuellt", []):
            if rid in anf:
                benutzte_anf[rid] = anf[rid]
                satisfy.append(f"    satisfy Anforderungen::{anf[rid]['name']} by {_kamel(paket)}.{teil};")
                melde(b, f"erfuellt.{rid}", UEBERNOMMEN, "satisfy")
            else:
                melde(b, f"erfuellt.{rid}", OFFEN, "–",
                      f"{rid} gibt es im Anforderungsstand nicht; die Beziehung wird nicht erfunden, sondern als offene "
                      f"Referenz an den Anforderungsstand gemeldet.")

        gemeldet = {e["feld"].split(".")[0] for e in bericht if e["baustein"] == b["baustein_id"]
                    and e["version"] == str(b["version"])}
        for feld in b:  # Sicherheitsnetz: keine Angabe darf ohne Zeile im Bericht bleiben
            if feld not in gemeldet and b[feld] not in (None, "", []):
                melde(b, feld, NICHT, "–", f"Die Regel nennt „{feld}“, bildet es aber nicht ab; die Angabe bleibt in der "
                                          f"Quelle und steht hier im Bericht.")

    t = [f"// Erzeugt von der Bausteinbrücke aus den Bausteinbeschreibungen; nicht von Hand ändern.",
         f"package {paket} {{",
         "    private import ScalarValues::*;",
         "    metadata def Herkunft { attribute bausteinId : String; attribute version : String; "
         "attribute ebene : String; attribute vorgaenger : String; }",
         "    metadata def Semantik { attribute begriff : String; attribute iri : String; }"]
    t += [f"    port def {p};" for p in sorted(ports)]
    t.append("    package Anforderungen {")
    t += [f"        requirement <'{a['id']}'> {a['name']} {{ doc /* {_text(a['text'])} */ }}"
          for a in sorted(benutzte_anf.values(), key=lambda a: a["id"])]
    t.append("    }")
    t.append("    package Funktionen {")
    t += funktionen
    t.append("    }")
    t += zustandsdefs + defs
    t.append(f"    part {_kamel(paket)} {{")
    t += nutzungen
    t.append("    }")
    t += satisfy + allocate
    t.append("}")
    return "\n".join(t) + "\n", bericht


def zusammenfassung(bericht: list[dict]) -> dict:
    z = {UEBERNOMMEN: 0, UMGEWANDELT: 0, NICHT: 0, OFFEN: 0}
    for e in bericht:
        z[e["status"]] += 1
    z["ampel"] = "grün" if z[UMGEWANDELT] + z[NICHT] + z[OFFEN] == 0 else "gelb"
    return z


def paketname(ordner: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", ordner.title())
