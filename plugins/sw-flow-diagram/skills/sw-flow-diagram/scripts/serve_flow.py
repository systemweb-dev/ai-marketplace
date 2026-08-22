#!/usr/bin/env python3
"""
Servidor do diagrama COM edição: serve os arquivos (GET) e aceita salvar (POST /save).
No /save: grava o flow.json recebido e re-roda o build_flow.py — o live-reload da página
então recarrega sozinho com o novo render. Use este no lugar do `python3 -m http.server`
quando quiser editar pelo painel do navegador.

Uso:
  python3 serve_flow.py --dir ./flows/<slug> [--port 8900]
"""
import argparse
import json
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BUILDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_flow.py")


def make_handler(dirpath):
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=dirpath, **k)

        def log_message(self, *a):  # silencioso
            pass

        def end_headers(self):  # nunca cacheia — o live-reload depende de pegar o html/js novo
            self.send_header("Cache-Control", "no-store, max-age=0")
            super().end_headers()

        def do_POST(self):
            if self.path.rstrip("/") != "/save":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(n))
            except Exception as e:
                self._json(400, {"ok": False, "error": f"JSON inválido: {e}"})
                return
            try:
                with open(os.path.join(dirpath, "flow.json"), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                subprocess.run([sys.executable, BUILDER, "--dir", dirpath],
                               check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                self._json(500, {"ok": False, "error": (e.stderr or "build falhou")})
                return
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
                return
            self._json(200, {"ok": True})

        def _json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return H


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="diretorio do fluxo (com flow.json)")
    ap.add_argument("--port", type=int, default=8900)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    d = os.path.expanduser(args.dir)
    if not os.path.isfile(os.path.join(d, "flow.json")):
        sys.exit(f"flow.json nao encontrado em {d}")
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(d))
    print(f"FLOW_URL=http://{args.host}:{args.port}/flow.html  (editor ativo · POST /save)")
    httpd.serve_forever()
