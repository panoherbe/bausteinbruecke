# Messbericht vom 13.11.2026

Ein Lauf von `messen.py` am 13.11.2026 um 04:10 Uhr (x86_64, 16 Kerne, Python 3.13.18). Synthetische Beispielbausteine; Gegenstellen nachgebildet (simuliert); Werkzeugprüfung mit der OMG-SysML-v2-Pilotimplementierung. Alle Zahlen hier stehen in `ergebnis.json` daneben; die erzeugten SysML-Texte und das Übertragungsprotokoll liegen im selben Ordner.

## 1. Übersetzen und Rückweg

| Demonstrator | Bausteine | Angaben | übernommen | umgewandelt | nicht abbildbar | offene Referenz | im Werkzeug | Rückweg |
|---|---|---|---|---|---|---|---|---|
| Roboterarm | 3 | 52 | 47 | 3 | 1 | 1 | gültig, 568 Elemente, 1,77 s | 50 von 50 |
| Flurförderfahrzeug | 3 | 49 | 47 | 2 | 0 | 0 | gültig, 550 Elemente, 1,81 s | 49 von 49 |

Rückweg: Der JSON-Export der OMG-Pilotimplementierung wird wieder gelesen; jede übernommene oder umgewandelte Angabe muss dort wieder auftauchen (Baustein, Version, Werte, Schnittstellen, Zustände, Funktionen, Anforderungen, Begriff).

Was nicht 1:1 übernommen wurde:

- **Gelenkantrieb 2.0.0**, `attribute.maxDrehzahl`: umgewandelt. Die Einheit „1/min“ hat (noch) keine Zeile in der Einheitentabelle; der Zahlwert 3000 ist übernommen, die Einheit steht als Text daneben.
- **Greifermodul 1.2.0**, `cad_datei`: nicht abbildbar. Für „cad_datei“ ist keine Abbildung vereinbart; die Angabe bleibt in der Quelle (greifer_v12.step) und steht hier im Bericht.
- **Greifermodul 1.2.0**, `zustaende.stoerung`: umgewandelt. Die Bedingung ist Freitext; sie steht als Text am Zustand, bis eine formale Form festgelegt ist.
- **Greifermodul 1.2.0**, `erfuellt.R-12`: offene Referenz. R-12 gibt es im Anforderungsstand nicht; die Beziehung wird nicht erfunden, sondern als offene Referenz an den Anforderungsstand gemeldet.
- **Kameramodul 1.0.0**, `messgroesse`: umgewandelt. Die Messgröße steht als Text im Modell; die Projektbibliothek hat dafür noch keinen Typ.
- **Antriebseinheit 1.1.0**, `zustaende.notHalt`: umgewandelt. Die Bedingung ist Freitext; sie steht als Text am Zustand, bis eine formale Form festgelegt ist.
- **Sicherheitslaserscanner 1.0.0**, `messgroesse`: umgewandelt. Die Messgröße steht als Text im Modell; die Projektbibliothek hat dafür noch keinen Typ.

## 2. Neue Version des Greifermoduls (1.2.0 → 1.3.0)

- In der Quelle geändert: `attribute.maxGreifkraft` 140 N → 160 N; `version` 1.2.0 → 1.3.0; neu: vorgaenger, zustaende.quittiert; weggefallen: nichts.
- Im Werkzeug: geänderte Werte unter `Roboterarm::Greifermodul`: 2, neu: Roboterarm::GreifermodulZustaende::quittiert, weggefallen: 0.
- Interne Element-IDs des Werkzeugs: nur 15 von 568 blieben beim zweiten Einlesen desselben Texts gleich. Darum trägt die Brücke Identität selbst (Baustein-ID, Version, Vorgänger), nie über diese IDs.
- Übergabe an die drei Gegenstellen: KI-Assistenz: übertragen (B-GM 1.3.0 gespeichert); Modellverwaltung: übertragen (Stand 1.3.0 angelegt (Vorgänger 1.2.0)); Wissensgraph: übertragen (9 Tripel übernommen). Ampel grün.
- KI-Assistenz fragt nach dem aktuellen Stand: Version 1.3.0, „Neu gegenüber 1.2.0: maxGreifkraft 140 → 160; Zustand „quittiert““. Nach Version 9.9.9: HTTP 404, „Version 9.9.9 von B-GM unbekannt; bekannt: 1.2.0, 1.3.0. Keine Ersatzantwort.“

## 3. Störfälle

| Störung | Ergebnis |
|---|---|
| Wissensgraph nicht erreichbar | 3 Versuche, dann „offen“, Ampel rot, geschrieben: 0 |
| … wieder erreichbar | „übertragen“ im 1. Versuch |
| Antwort der Modellverwaltung geht verloren | „schon vorhanden (keine Dublette)“ im 2. Versuch |
| Derselbe Stand noch einmal gesendet | „schon vorhanden (keine Dublette)“ |
| Paralleler Stand (1.3.1 auf Basis 1.2.0) | „Konflikt gemeldet“: Paralleler Stand: aktueller Kopf ist 1.3.0, Ihr Vorgänger 1.2.0; nichts überschrieben, bitte zusammenführen |
| Begriff im Wissensgraph unbekannt | „abgelehnt mit Grund“: Begriff im Wissensgraph unbekannt: https://example.org/bausteine/begriff/Schutzfeldsensor (offene Referenz an die Zuständigen des Wissensgraphen); nichts geschrieben |
| Fehlerhafte Angabe (Version „1.3“) | „vor dem Senden abgelehnt“ |

Dubletten nach dem ganzen Lauf (Schreibvorgänge minus gespeicherte Objekte): KI-Assistenz 0, Modellverwaltung 0, Wissensgraph 0.

## 4. KMU-Bewertung: Wachstum, Aufwand, Kosten

Die 10- und 100-fache Menge vervielfältigt die sechs Beispielbausteine und ist damit **simuliert**.

| Bausteine | Angaben | Prüfung im Werkzeug | Rückweg | Übergabe an 3 Gegenstellen |
|---|---|---|---|---|
| 6 | 101 | gültig, 2,69 s | 99/99 | 18 Vorgänge, 0,06 s |
| 60 (simuliert) | 1010 | gültig, 26,75 s | 990/990 | 180 Vorgänge, 0,5 s |
| 600 (simuliert) | 10100 | gültig, aber der JSON-Export blieb leer (nach 286,76 s) | 0/0 | 1800 Vorgänge, 8,91 s |
| 600 in 10 Paketen zu 60 (simuliert) | – | gültig, zusammen 260,33 s | 9900/9900 | – |

**Was daraus folgt:** Die Prüfung im Werkzeug wächst gleichmäßig mit der Zahl der Bausteine. Bei einem einzigen Paket mit 600 Bausteinen liefert der Export der Pilotimplementierung kein JSON mehr, der Rückweg ist dann nicht prüfbar; in Paketen je Teilsystem geht alles. Darum wird je Demonstrator oder Teilsystem ein Paket gebildet.

| Erweiterung | Aufwand (gezählt) |
|---|---|
| Neuer Bausteintyp | Regel „sensor“: 7 Zeilen (erbt von „komponente“, 16 Zeilen) |
| Neue Einheit | 1 Zeile (Einheitentabelle mit 9 Einheiten) |
| Neue Gegenstelle | 1 Adapter: KI-Assistenz 16 Zeilen, Modellverwaltung 14 Zeilen, Wissensgraph 12 Zeilen; Prüfung, Schlüssel, Wiederholung, Protokoll im Kern (121 Zeilen) |
| Lizenzkosten je Arbeitsplatz | 0 € (pyyaml (MIT), rdflib (BSD-3), pyshacl (Apache-2.0), jsonschema (MIT), OMG SysML v2 Pilotimplementierung (EPL-2.0)) |

## 5. Tests

14 von 14 bestanden in 7,8 s:

- `test_abbildung_ist_im_werkzeug_gueltig_und_kommt_vollstaendig_zurueck[roboterarm]`
- `test_abbildung_ist_im_werkzeug_gueltig_und_kommt_vollstaendig_zurueck[flurfoerderfahrzeug]`
- `test_bericht_nennt_jede_angabe_und_verschweigt_nichts`
- `test_falscher_text_wird_vom_werkzeug_abgelehnt`
- `test_schritt1_neue_version_genau_die_aenderungen`
- `test_schritt1_im_werkzeug_gleiche_aenderungen_und_baustein_id`
- `test_werkzeug_vergibt_bei_jedem_einlesen_neue_element_ids`
- `test_schritt2_paralleler_stand_meldet_konflikt_und_ueberschreibt_nichts`
- `test_schritt3_graph_kennt_nachfolger_und_lehnt_unbekannte_begriffe_ab`
- `test_schritt3_gegenstelle_aus_wird_offen_und_spaeter_ohne_dublette_nachgeholt`
- `test_antwort_verloren_wiederholung_schreibt_nicht_doppelt`
- `test_schritt4_assistenz_bekommt_aktuellen_stand_mit_notiz_und_keine_ersatzantwort`
- `test_ungueltige_nutzlast_wird_nicht_gesendet`
- `test_protokoll_hat_eine_zeile_je_vorgang_ohne_zugangsdaten`

## Grenzen

- Die drei Werkzeuge sind nachgebildet (`gegenstellen/server.py`). In einem Projekt treten die echten Zugänge an ihre Stelle; der Kern bleibt, die Adapter werden an die vereinbarten Schnittstellen angepasst.
- Bausteine, Anforderungen und Begriffe sind erfunden. Die Regeln decken die Felder dieser Beispiele ab, nicht jede denkbare Bausteinbeschreibung.
- Kein Rückweg vom Werkzeug in die Quelle (nur Prüfung, ob alles angekommen ist); keine Anmeldung und Rechte; keine Messung auf einem echten PLM- oder Graph-System.
