"""Messbericht in Klartext aus nachweis/<datum>/ergebnis.json: nachweis/<datum>/BERICHT.md.

    python bericht.py            # neuester Messlauf
"""
import json
from pathlib import Path

ORD = sorted(Path("nachweis").glob("*/ergebnis.json"))[-1].parent
E = json.loads((ORD / "ergebnis.json").read_text(encoding="utf-8"))
D = ".".join(reversed(E["datum"].split("-")))
s = lambda x: f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")  # noqa: E731

ra, ff = E["demonstratoren"]["roboterarm"], E["demonstratoren"]["flurfoerderfahrzeug"]
nv, st, t, a = E["neue_version"], E["stoerfaelle"], E["tests"], E["aufwand"]
z = []
z += [f"# Messbericht vom {D}", "",
      f"Ein Lauf von `messen.py` am {D} um {E['zeit'][11:16]} Uhr ({E['rechner']}). {E['hinweis']} "
      "Alle Zahlen hier stehen in `ergebnis.json` daneben; die erzeugten SysML-Texte und das Übertragungsprotokoll "
      "liegen im selben Ordner.", "",
      "## 1. Übersetzen und Rückweg", "",
      "| Demonstrator | Bausteine | Angaben | übernommen | umgewandelt | nicht abbildbar | offene Referenz | im Werkzeug | Rückweg |",
      "|---|---|---|---|---|---|---|---|---|"]
for n, d in (("Roboterarm", ra), ("Flurförderfahrzeug", ff)):
    zs = d["zusammenfassung"]
    z.append(f"| {n} | {len(d['bausteine'])} | {len(d['bericht'])} | {zs['übernommen']} | {zs['umgewandelt']} | "
             f"{zs['nicht abbildbar']} | {zs['offene Referenz']} | {'gültig' if d['werkzeug']['ok'] else 'FEHLER'}, "
             f"{d['rueckweg']['elemente']} Elemente, {s(d['werkzeug']['dauer_s'])} s | "
             f"{d['rueckweg']['wiedergefunden']} von {d['rueckweg']['geprueft']} |")
z += ["", "Rückweg: Der JSON-Export der OMG-Pilotimplementierung wird wieder gelesen; jede übernommene oder "
      "umgewandelte Angabe muss dort wieder auftauchen (Baustein, Version, Werte, Schnittstellen, Zustände, "
      "Funktionen, Anforderungen, Begriff).", "", "Was nicht 1:1 übernommen wurde:", ""]
for d in (ra, ff):
    for b in d["bericht"]:
        if b["status"] != "übernommen":
            z.append(f"- **{b['name']} {b['version']}**, `{b['feld']}`: {b['status']}. {b['grund']}")
e = nv["element_ids"]
z += ["", "## 2. Neue Version des Greifermoduls (1.2.0 → 1.3.0)", "",
      f"- In der Quelle geändert: " + "; ".join(f"`{k}` {a_} → {b_}" for k, (a_, b_) in nv["quelle"]["geaendert"].items())
      + f"; neu: {', '.join(nv['quelle']['neu'])}; weggefallen: {', '.join(nv['quelle']['weg']) or 'nichts'}.",
      f"- Im Werkzeug: geänderte Werte unter `Roboterarm::Greifermodul`: {len(nv['werkzeug_baustein']['geaendert'])}, "
      f"neu: {', '.join(nv['werkzeug_zustaende']['neu'])}, weggefallen: {len(nv['werkzeug_baustein']['weg'])}.",
      f"- Interne Element-IDs des Werkzeugs: nur {e['gleich_bei_zweitem_einlesen']} von {e['gesamt']} blieben beim "
      f"zweiten Einlesen desselben Texts gleich. Darum trägt die Brücke Identität selbst (Baustein-ID, Version, "
      f"Vorgänger), nie über diese IDs.",
      f"- Übergabe an die drei Gegenstellen: " + "; ".join(f"{v['ziel']}: {v['ergebnis']} ({v['meldung']})"
                                                        for v in nv["uebertragung"]) + f". Ampel {nv['ampel']}.",
      f"- KI-Assistenz fragt nach dem aktuellen Stand: Version {E['assistenz']['aktuell']['version']}, "
      f"„{E['assistenz']['aktuell']['notiz']}“. Nach Version 9.9.9: HTTP {E['assistenz']['unbekannte_version']['http']}, "
      f"„{E['assistenz']['unbekannte_version']['meldung']}“", "",
      "## 3. Störfälle", "",
      f"| Störung | Ergebnis |", "|---|---|",
      f"| Wissensgraph nicht erreichbar | {st['gegenstelle_aus']['versuche']} Versuche, dann „{st['gegenstelle_aus']['ergebnis']}“, "
      f"Ampel {st['gegenstelle_aus']['ampel']}, geschrieben: {st['gegenstelle_aus']['geschrieben']} |",
      f"| … wieder erreichbar | „{st['nachgeholt']['ergebnis']}“ im {st['nachgeholt']['versuche']}. Versuch |",
      f"| Antwort der Modellverwaltung geht verloren | „{st['antwort_verloren']['ergebnis']}“ im {st['antwort_verloren']['versuche']}. Versuch |",
      f"| Derselbe Stand noch einmal gesendet | „{st['nochmal_gesendet']['ergebnis']}“ |",
      f"| Paralleler Stand (1.3.1 auf Basis 1.2.0) | „{st['paralleler_stand']['ergebnis']}“: {st['paralleler_stand']['meldung']} |",
      f"| Begriff im Wissensgraph unbekannt | „{st['unbekannter_begriff']['ergebnis']}“: {st['unbekannter_begriff']['meldung']} |",
      f"| Fehlerhafte Angabe (Version „1.3“) | „{st['vor_dem_senden_abgelehnt']['ergebnis']}“ |", "",
      f"Dubletten nach dem ganzen Lauf (Schreibvorgänge minus gespeicherte Objekte): "
      f"KI-Assistenz {st['dubletten']['ki']}, Modellverwaltung {st['dubletten']['modell']}, Wissensgraph {st['dubletten']['graph']}.", "",
      "## 4. KMU-Bewertung: Wachstum, Aufwand, Kosten", "",
      "Die 10- und 100-fache Menge vervielfältigt die sechs Beispielbausteine und ist damit **simuliert**.", "",
      "| Bausteine | Angaben | Prüfung im Werkzeug | Rückweg | Übergabe an 3 Gegenstellen |", "|---|---|---|---|---|"]
for k in E["skalierung"]:
    if k.get("pakete"):
        z.append(f"| {k['bausteine']} in {k['pakete']} Paketen zu 60 (simuliert) | – | "
                 f"{'gültig' if k['werkzeug_ok'] else 'FEHLER'}, zusammen {s(k['dauer_werkzeug_s'])} s | {k['rueckweg']} | – |")
    else:
        if k["werkzeug_ok"] and k.get("export_ok", True):
            w = f"gültig, {s(k['dauer_werkzeug_s'])} s"
        elif k["werkzeug_ok"]:
            w = f"gültig, aber der JSON-Export blieb leer (nach {s(k['dauer_werkzeug_s'])} s)"
        else:
            w = f"Fehler nach {s(k['dauer_werkzeug_s'])} s ({'; '.join(k.get('meldungen', [])) or 'ohne Meldung'})"
        z.append(f"| {k['bausteine']}{' (simuliert)' if k['simuliert'] else ''} | {k['angaben']} | {w} | {k['rueckweg']} | "
                 f"{k['vorgaenge']} Vorgänge, {s(k['dauer_uebertragen_s'])} s |")
z += ["", "**Was daraus folgt:** Die Prüfung im Werkzeug wächst gleichmäßig mit der Zahl der Bausteine. Bei einem "
      "einzigen Paket mit 600 Bausteinen liefert der Export der Pilotimplementierung kein JSON mehr, der Rückweg ist "
      "dann nicht prüfbar; in Paketen je Teilsystem geht alles. Darum wird je Demonstrator oder Teilsystem ein "
      "Paket gebildet.", "",
      "| Erweiterung | Aufwand (gezählt) |", "|---|---|",
      f"| Neuer Bausteintyp | Regel „sensor“: {a['regel_sensor_zeilen']} Zeilen (erbt von „komponente“, {a['regel_komponente_zeilen']} Zeilen) |",
      f"| Neue Einheit | 1 Zeile (Einheitentabelle mit {a['einheitentabelle_zeilen']} Einheiten) |",
      f"| Neue Gegenstelle | 1 Adapter: " + ", ".join(f"{k} {v} Zeilen" for k, v in a["adapter_zeilen"].items())
      + f"; Prüfung, Schlüssel, Wiederholung, Protokoll im Kern ({a['kern_zeilen']} Zeilen) |",
      f"| Lizenzkosten je Arbeitsplatz | {a['lizenzkosten_je_arbeitsplatz_eur']} € ({', '.join(a['abhaengigkeiten'])}) |", "",
      f"## 5. Tests", "", f"{t['tests'] - t['failures'] - t['errors']} von {t['tests']} bestanden in {s(t['dauer_s'])} s:", ""]
z += [f"- `{n}`" for n in t["namen"]]
z += ["", "## Grenzen", "",
      "- Die drei Werkzeuge sind nachgebildet (`gegenstellen/server.py`). In einem Projekt treten die echten Zugänge an ihre "
      "Stelle; der Kern bleibt, die Adapter werden an die vereinbarten Schnittstellen angepasst.",
      "- Bausteine, Anforderungen und Begriffe sind erfunden. Die Regeln decken die Felder dieser Beispiele ab, nicht "
      "jede denkbare Bausteinbeschreibung.",
      "- Kein Rückweg vom Werkzeug in die Quelle (nur Prüfung, ob alles angekommen ist); keine Anmeldung und Rechte; "
      "keine Messung auf einem echten PLM- oder Graph-System.", ""]
(ORD / "BERICHT.md").write_text("\n".join(z), encoding="utf-8")
print(f"{ORD}/BERICHT.md: {len(z)} Zeilen")
