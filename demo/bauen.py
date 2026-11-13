"""Baut die Vorführung als eine einzige HTML-Datei (ohne Netzanfragen): demo/bausteinbruecke.html.

    python demo/bauen.py      # nach `docker compose run --rm messen`, das demo/daten.js schreibt
"""
import json
from pathlib import Path

HIER = Path(__file__).parent
quellen = {str(p.relative_to(HIER.parent / "beispiele")): p.read_text(encoding="utf-8")
           for p in sorted((HIER.parent / "beispiele").rglob("*.yaml"))}
(HIER / "quellen.js").write_text("window.QUELLEN = " + json.dumps(quellen, ensure_ascii=False) + ";\n", encoding="utf-8")
html = (HIER / "index.html").read_text(encoding="utf-8")
inline = "<script>\n" + (HIER / "quellen.js").read_text(encoding="utf-8") + (HIER / "daten.js").read_text(encoding="utf-8") + "</script>"
alt = '<script src="quellen.js"></script>\n<script src="daten.js"></script>'
assert alt in html
html = html.replace(alt, inline)
(HIER / "bausteinbruecke.html").write_text(html, encoding="utf-8")
print(f"demo/bausteinbruecke.html: {len(html.encode()) // 1024} KB")
