"""Die drei Adapter: je Gegenstelle nur, wohin und in welcher Form übertragen wird. Alles andere macht der Kern.

  KI-Assistenz     REST/JSON nach OpenAPI-Beschreibung; liest Bausteine nach Kennung und Version
  Modellverwaltung neue Stände mit Vorgänger (Versionskette); paralleler Stand -> Konflikt, nie Überschreiben
  Wissensgraph     RDF (Turtle), vor dem Senden gegen SHACL geprüft; je Kennung und Version, ohne Dubletten
"""
from __future__ import annotations

import hashlib
import json
import re

from rdflib import Graph
from pyshacl import validate as shacl

from .kern import Adapter, Vorgang, http

SY = "https://example.org/bausteine/"
SHAPES = f"""
@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix sy: <{SY}> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
sy:BausteinForm a sh:NodeShape ; sh:targetClass sy:Baustein ;
  sh:property [ sh:path sy:bausteinId ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path sy:version ; sh:minCount 1 ; sh:maxCount 1 ; sh:pattern "^[0-9]+\\\\.[0-9]+\\\\.[0-9]+$" ] ;
  sh:property [ sh:path sy:begriff ; sh:maxCount 1 ; sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path sy:nachfolgerVon ; sh:maxCount 1 ; sh:class sy:Baustein ] .
"""


def teiltext(paket_text: str, name: str) -> str:
    """Der Block `part def … Name { … }` aus dem erzeugten Paket (für die KI-Assistenz)."""
    zeilen = paket_text.splitlines()
    start = next(i for i, z in enumerate(zeilen) if re.match(rf"\s*part def <'[^']+'> {name} \{{", z))
    ende = next(i for i in range(start, len(zeilen)) if zeilen[i] == "    }")
    return "\n".join(zeilen[start:ende + 1])


def knoten(b: dict) -> str:
    return f"{SY}baustein/{b['baustein_id']}/{b['version']}"


def als_rdf(b: dict) -> str:
    t = [f"@prefix sy: <{SY}> .", f"@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
         f"<{knoten(b)}> a sy:Baustein ;",
         f'  sy:bausteinId "{b["baustein_id"]}"^^xsd:string ;',
         f'  sy:version "{b["version"]}" ;',
         f'  sy:name "{b["name"]}" ;']
    if b.get("semantik"):
        t.append(f"  sy:begriff <{b['semantik']['iri']}> ;")
    if b.get("vorgaenger"):
        vor = {**b, "version": b["vorgaenger"]}
        t.append(f"  sy:nachfolgerVon <{knoten(vor)}> ;")
    t[-1] = t[-1].rstrip(" ;") + " ."
    if b.get("vorgaenger"):  # Vorgänger als Knoten nennen, damit die SHACL-Klasse lokal prüfbar ist
        t.append(f"<{knoten({**b, 'version': b['vorgaenger']})}> a sy:Baustein ; "
                 f'sy:bausteinId "{b["baustein_id"]}"^^xsd:string ; sy:version "{b["vorgaenger"]}" .')
    return "\n".join(t) + "\n"


class KiAssistenz(Adapter):
    ziel = "KI-Assistenz"
    schema = {"type": "object", "required": ["baustein_id", "version", "name", "typ", "ebene", "sysml", "attribute"],
              "properties": {"baustein_id": {"type": "string"}, "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
                             "ebene": {"enum": ["R", "F", "L", "P"]}, "sysml": {"type": "string", "minLength": 10},
                             "attribute": {"type": "array"}}}

    @staticmethod
    def nutzlast(b: dict, paket_text: str) -> dict:
        return {"baustein_id": b["baustein_id"], "version": str(b["version"]), "name": b["name"], "typ": b["typ"],
                "ebene": b.get("ebene", ""), "sysml": teiltext(paket_text, b["name"]),
                "attribute": b.get("attribute", []), "zustaende": [z["name"] for z in b.get("zustaende", [])]}

    def uebertragen(self, v: Vorgang):
        return http("POST", f"{self.basis}/ki/bausteine", json.dumps(v.nutzlast).encode(),
                    kopf={"Idempotency-Key": v.schluessel})

    def lesen(self, baustein_id: str, version: str = "aktuell"):
        return http("GET", f"{self.basis}/ki/bausteine/{baustein_id}?version={version}")


class Modellverwaltung(Adapter):
    ziel = "Modellverwaltung"
    schema = {"type": "object", "required": ["baustein_id", "version", "vorgaenger", "sysml", "sha256"],
              "properties": {"version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
                             "vorgaenger": {"type": "string"}, "sha256": {"type": "string", "minLength": 64}}}

    @staticmethod
    def nutzlast(b: dict, paket_text: str, vorgaenger: str | None = None) -> dict:
        teil = teiltext(paket_text, b["name"])
        return {"baustein_id": b["baustein_id"], "version": str(b["version"]),
                "vorgaenger": str(vorgaenger if vorgaenger is not None else b.get("vorgaenger", "")),
                "sysml": teil, "sha256": hashlib.sha256(teil.encode()).hexdigest()}

    def uebertragen(self, v: Vorgang):
        return http("POST", f"{self.basis}/modell/staende", json.dumps(v.nutzlast).encode(),
                    kopf={"Idempotency-Key": v.schluessel})


class Wissensgraph(Adapter):
    ziel = "Wissensgraph"

    def pruefe(self, nutzlast) -> str:
        try:
            g = Graph().parse(data=nutzlast, format="turtle")
        except Exception as e:  # noqa: BLE001 - jede Parserfehlermeldung ist ein Grund
            return f"RDF nicht lesbar: {e}"
        ok, _, text = shacl(g, shacl_graph=Graph().parse(data=SHAPES, format="turtle"))
        return "" if ok else "SHACL: " + " ".join(text.split())[:300]

    def uebertragen(self, v: Vorgang):
        return http("POST", f"{self.basis}/graph/tripel", v.nutzlast.encode(), art="text/turtle",
                    kopf={"Idempotency-Key": v.schluessel})
