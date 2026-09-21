#!/usr/bin/env python3
"""Self-contained live-reload static server (Python stdlib only).

Serves a directory over HTTP and auto-refreshes connected browsers whenever any
file in that directory changes. No external dependencies and no `npm install` —
it uses Server-Sent Events plus mtime polling, so it works even with no network.

This exists so the mockup-preview loop is frictionless: the agent edits the
mockup HTML in response to user feedback, and the user's browser refreshes on
its own. The user never has to reload.

Usage:
    python3 serve.py <directory> [--port 8765] [--host 127.0.0.1]   # --host 0.0.0.0 p/ acesso na rede
"""
import argparse
import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

# O que o usuário diz pela tela (comentários num elemento, a variação escolhida) vai para
# esta pasta, dentro do diretório do mockup, e o agente lê de lá. Fica fora do live-reload.
PASTA_FEEDBACK = ".mockup"
MAX_CORPO = 64 * 1024
MAX_TEXTO = 4000
# Só estes campos são gravados; o resto do JSON enviado é descartado. Valor: (tipo, limite).
CAMPOS_COMENTARIO = {"variacao": (int, None), "titulo": (str, 200), "seletor": (str, 500),
                     "trecho": (str, 200), "texto": (str, MAX_TEXTO), "vw": (str, 20),
                     "theme": (str, 10)}
CAMPOS_ESCOLHA = {"variacao": (int, None), "titulo": (str, 200), "knobs": (dict, None),
                  "vw": (str, 20), "theme": (str, 10), "fonte_titulo": (str, 80),
                  "fonte_corpo": (str, 80), "nota": (str, MAX_TEXTO)}
_trava_arquivo = threading.Lock()

# Injected before </body> of every HTML response. Opens an SSE channel and
# reloads the page when the server signals a change. Wrapped in try/catch so a
# mockup never breaks just because live-reload hiccups.
RELOAD_SNIPPET = b"""
<script>
(function(){
  try {
    var es = new EventSource("/__livereload");
    es.onmessage = function(e){ if (e.data === "reload") location.reload(); };
  } catch (err) {}
})();
</script>
"""


def snapshot(root):
    """Map of file path -> mtime for everything under root. Comparing two
    snapshots tells us if anything changed, added, or was removed."""
    sig = {}
    for p in Path(root).rglob("*"):
        if PASTA_FEEDBACK in p.relative_to(root).parts:
            continue  # feedback gravado pela tela não é edição do mockup
        if p.is_file():
            try:
                sig[str(p)] = p.stat().st_mtime
            except OSError:
                pass
    return sig


class Recusa(Exception):
    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status


def limpar(dados, campos, obrigatorios):
    """Fica só com os campos conhecidos, do tipo certo e dentro do limite."""
    if not isinstance(dados, dict):
        raise Recusa(400, "o corpo precisa ser um objeto JSON")
    limpo = {}
    for nome, (tipo, limite) in campos.items():
        if nome not in dados or dados[nome] is None:
            continue
        valor = dados[nome]
        if tipo is int and (isinstance(valor, bool) or not isinstance(valor, int)):
            raise Recusa(400, f"'{nome}' precisa ser número inteiro")
        if not isinstance(valor, tipo):
            raise Recusa(400, f"'{nome}' tem o tipo errado")
        if tipo is str:
            valor = valor.strip()
            if limite and len(valor) > limite:
                raise Recusa(400, f"'{nome}' passa de {limite} caracteres")
        if tipo is dict:
            valor = {str(k)[:40]: v for k, v in list(valor.items())[:8]
                     if isinstance(v, (str, int, float, bool)) and len(str(v)) <= 80}
        limpo[nome] = valor
    for nome in obrigatorios:
        if limpo.get(nome) in (None, ""):
            raise Recusa(400, f"'{nome}' é obrigatório")
    return limpo


def make_handler(root):
    feedback = Path(root) / PASTA_FEEDBACK

    def ler_json(nome, padrao):
        try:
            return json.loads((feedback / nome).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return padrao

    def gravar_json(nome, dados):
        feedback.mkdir(exist_ok=True)
        temporario = feedback / (nome + ".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(feedback / nome)


    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)

        def log_message(self, *a):  # keep the console quiet
            pass

        def do_GET(self):
            if self.path == "/__livereload":
                self._serve_sse()
                return
            if self.path.split("?")[0] == "/__detector":
                self._serve_detector()
                return
            if self.path.split("?")[0] == "/__comentarios":
                self._json(200, ler_json("comentarios.json", []))
                return
            if self.path.split("?")[0] == "/__escolha":
                self._json(200, ler_json("escolha.json", None))
                return

            path = self.translate_path(self.path)
            if os.path.isdir(path):
                index = os.path.join(path, "index.html")
                if os.path.exists(index):
                    path = index

            if path.endswith(".html") and os.path.exists(path):
                self._serve_html(path)
                return

            super().do_GET()

        def do_POST(self):
            rotas = {"/__comentarios": self._comentar, "/__comentarios/apagar": self._apagar,
                     "/__escolha": self._escolher}
            rota = rotas.get(self.path.split("?")[0])
            try:
                if rota is None:
                    raise Recusa(404, "rota desconhecida")
                self._json(200, rota(self._corpo()))
            except Recusa as recusa:
                self._json(recusa.status, {"erro": str(recusa)})

        def _corpo(self):
            origem = self.headers.get("Origin")
            if origem and urlsplit(origem).netloc != self.headers.get("Host"):
                raise Recusa(403, "origem diferente da do preview")
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                raise Recusa(415, "só aceita application/json")
            try:
                tamanho = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise Recusa(400, "Content-Length inválido")
            if tamanho > MAX_CORPO:
                raise Recusa(413, "corpo grande demais")
            try:
                return json.loads(self.rfile.read(tamanho) or b"null")
            except ValueError:
                raise Recusa(400, "JSON inválido")

        def _comentar(self, dados):
            novo = limpar(dados, CAMPOS_COMENTARIO, ["texto"])
            with _trava_arquivo:
                lista = ler_json("comentarios.json", [])
                estado = ler_json("estado.json", {"proximo_id": 1})
                novo = {"id": estado["proximo_id"], **novo,
                        "criado": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                lista.append(novo)
                gravar_json("comentarios.json", lista)
                gravar_json("estado.json", {"proximo_id": novo["id"] + 1})
            return novo

        def _apagar(self, dados):
            if not isinstance(dados, dict) or isinstance(dados.get("id"), bool) \
                    or not isinstance(dados.get("id"), int):
                raise Recusa(400, "'id' precisa ser número inteiro")
            with _trava_arquivo:
                lista = [c for c in ler_json("comentarios.json", []) if c.get("id") != dados["id"]]
                gravar_json("comentarios.json", lista)
            return {"ok": True}

        def _escolher(self, dados):
            escolha = limpar(dados, CAMPOS_ESCOLHA, ["variacao", "titulo"])
            escolha["criado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with _trava_arquivo:
                gravar_json("escolha.json", escolha)
            return escolha

        def _json(self, status, dados):
            corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _serve_html(self, path):
            with open(path, "rb") as f:
                body = f.read()
            if b"</body>" in body:
                body = body.replace(b"</body>", RELOAD_SNIPPET + b"</body>", 1)
            else:
                body += RELOAD_SNIPPET
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _serve_detector(self):
            """O resultado do detector anti-slop sobre o index.html, em JSON. A tela do harness
            pede isto a cada carga e mostra o selo; erro vira JSON legível, nunca derruba o
            servidor."""
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import detectar
                with open(os.path.join(root, "index.html"), encoding="utf-8") as f:
                    resultado = detectar.analisar(f.read())
            except (OSError, ValueError) as erro:
                resultado = {"erro": str(erro)}
            corpo = json.dumps(resultado, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _serve_sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last = snapshot(root)
            try:
                while True:
                    time.sleep(0.5)
                    cur = snapshot(root)
                    if cur != last:
                        last = cur
                        self.wfile.write(b"data: reload\n\n")
                    else:
                        self.wfile.write(b": ping\n\n")  # keepalive
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

    return Handler


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    # Threaded so the long-lived SSE connection doesn't block normal requests.
    daemon_threads = True
    allow_reuse_address = True


def find_free_port(host, preferred, attempts=50):
    """Return a bindable port, starting at `preferred` and walking up. Avoids the
    manual 'port busy, try the next one' dance — the script just picks one."""
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit(f"mockup-preview: no free port in {preferred}-{preferred + attempts}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--port", type=int, default=8765)
    # Local por padrão (não expõe o preview na rede). Use --host 0.0.0.0 só se precisar
    # abrir de outra máquina/celular na mesma rede.
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    root = Path(args.directory).resolve()
    root.mkdir(parents=True, exist_ok=True)

    port = find_free_port(args.host, args.port)
    httpd = ThreadingServer((args.host, port), make_handler(root))
    # Machine-readable line so the launcher can grep the actual URL/PID reliably.
    print(f"MOCKUP_PREVIEW_URL=http://localhost:{port}/")
    print(f"MOCKUP_PREVIEW_PID={os.getpid()}")
    print(f"mockup-preview: serving {root}")
    print(f"mockup-preview: open http://localhost:{port}/ (live-reload on)")
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
