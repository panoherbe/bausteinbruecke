"""Prüf- und Exportdienst für SysML-v2-Text, im Jupyter-Kernel der OMG-Pilotimplementierung.

    POST /pruefen {"text": "..."}               -> {"ok", "meldungen", "dauer_s", "kernel"}
    POST /export  {"text": "...", "paket": "P"} -> {"ok", "meldungen", "elemente": [...JSON der Pilotimplementierung...]}

Ein Kernel für alle Aufrufe; jeder Text bekommt ein eigenes Wurzelpaket (Name__n), damit frühere Aufrufe nicht
mitzählen. Im Export wird der Zusatz wieder entfernt, sodass qualifizierte Namen dem Text entsprechen.
"""
import base64
import itertools
import json
import queue
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jupyter_client.manager import start_new_kernel

_sperre, _zaehler = threading.Lock(), itertools.count(1)
km, kc = start_new_kernel(kernel_name="sysml")
try:
    _v = subprocess.run(["micromamba", "list", "-n", "base", "jupyter-sysml-kernel", "--json"], capture_output=True,
                        text=True).stdout
    KERNEL = "jupyter-sysml-kernel " + json.loads(_v)[0]["version"]
except Exception:  # noqa: BLE001 - nur Zusatzinformation
    KERNEL = "jupyter-sysml-kernel (Version unbekannt)"


def _ausfuehren(code: str) -> dict:
    msg_id = kc.execute(code)
    aus = {"meldungen": [], "text": "", "html": ""}
    while True:
        try:
            m = kc.get_iopub_msg(timeout=300)
        except queue.Empty:
            aus["meldungen"].append("Zeitüberschreitung im Kernel")
            return aus
        if m["parent_header"].get("msg_id") != msg_id:
            continue
        art, inhalt = m["msg_type"], m["content"]
        if art == "status" and inhalt["execution_state"] == "idle":
            return aus
        if art == "stream":
            aus["meldungen"] += [z for z in inhalt["text"].splitlines() if z.strip()]
        elif art == "execute_result":
            aus["text"] += inhalt["data"].get("text/plain", "")
            aus["html"] += inhalt["data"].get("text/html", "")
        elif art == "error":
            aus["meldungen"].append(f"{inhalt.get('ename')}: {inhalt.get('evalue')}")


def _fehler(meldungen):
    return [z for z in meldungen if z.startswith("ERROR") or "Zeitüberschreitung" in z or ("Error" in z and ":" in z)]


def pruefen(text: str, export: str | None = None) -> dict:
    with _sperre:
        n = next(_zaehler)
        m = re.search(r"^package\s+(\w+)\s*\{", text, flags=re.M)
        alt = m.group(1) if m else ""
        neu = f"{alt}__{n}"
        code = text[:m.start(1)] + neu + text[m.end(1):] if m else text
        t = time.perf_counter()
        r = _ausfuehren(code)
        fehler = _fehler(r["meldungen"])
        ok = not fehler and r["text"].startswith("Package")
        antwort = {"ok": ok, "meldungen": r["meldungen"], "dauer_s": round(time.perf_counter() - t, 3), "kernel": KERNEL}
        if export and ok:
            e = _ausfuehren(f"%export {neu}")
            treffer = re.search(r"base64,([A-Za-z0-9+/=]+)", e["html"])
            if not treffer:
                antwort["export_fehler"] = "Export lieferte kein JSON " + "; ".join(m for m in e["meldungen"] if m.strip(". "))
            else:
                roh = base64.b64decode(treffer.group(1)).decode("utf-8").replace(neu, alt)
                antwort["elemente"] = json.loads(roh)
        antwort["dauer_s"] = round(time.perf_counter() - t, 3)
        return antwort


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        if self.path not in ("/pruefen", "/export"):
            self.send_error(404)
            return
        daten = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        antwort = json.dumps(pruefen(daten["text"], export="1" if self.path == "/export" else None),
                             ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(antwort)))
        self.end_headers()
        self.wfile.write(antwort)

    def do_GET(self):  # noqa: N802
        antwort = json.dumps({"bereit": True, "kernel": KERNEL}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(antwort)))
        self.end_headers()
        self.wfile.write(antwort)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"Prüfdienst bereit ({KERNEL})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8100), Handler).serve_forever()
