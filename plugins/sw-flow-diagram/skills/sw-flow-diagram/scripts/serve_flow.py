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
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BUILDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_flow.py")
SAVE_LOCK = threading.Lock()


class BuildError(RuntimeError):
    pass


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_directory(path):
    try:
        subprocess.run([sys.executable, BUILDER, "--dir", str(path)],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise BuildError(exc.stderr or "build falhou") from exc


class FlowFileLock:
    def __init__(self, path):
        self.path = path
        self.stream = None

    def __enter__(self):
        self.stream = open(self.path, "r+", encoding="utf-8")
        fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()


def commit_pair(staged_json, staged_html, flow_path, html_path, backup_dir):
    old_json = os.path.join(backup_dir, "flow.json")
    old_html = os.path.join(backup_dir, "flow.html")
    shutil.copy2(flow_path, old_json)
    if os.path.exists(html_path):
        shutil.copy2(html_path, old_html)
    try:
        os.replace(staged_json, flow_path)
        os.replace(staged_html, html_path)
    except Exception:
        os.replace(old_json, flow_path)
        if os.path.isfile(old_html):
            os.replace(old_html, html_path)
        elif os.path.exists(html_path):
            os.unlink(html_path)
        raise


def save_candidate(dirpath, data, expected_hash, build_fn=build_directory):
    flow_path = os.path.join(dirpath, "flow.json")
    from flow_contract import validate_flow

    errors = validate_flow(data)
    if errors:
        return {"status": 400, "ok": False, "code": "invalid_flow", "message": errors}

    with SAVE_LOCK, FlowFileLock(flow_path):
        if file_sha256(flow_path) != expected_hash:
            return {"status": 409, "ok": False, "code": "conflict", "message": "flow.json mudou no disco"}

        staging = tempfile.mkdtemp(prefix=".flow-save-", dir=dirpath)
        backup = tempfile.mkdtemp(prefix=".flow-backup-", dir=dirpath)
        try:
            with open(os.path.join(staging, "flow.json"), "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            build_fn(staging)
            staged_json = os.path.join(staging, "flow.json")
            staged_html = os.path.join(staging, "flow.html")
            if not os.path.isfile(staged_html):
                raise BuildError("build não gerou flow.html")
            if file_sha256(flow_path) != expected_hash:
                return {"status": 409, "ok": False, "code": "conflict", "message": "flow.json mudou durante o build"}
            html_path = os.path.join(dirpath, "flow.html")
            commit_pair(staged_json, staged_html, flow_path, html_path, backup)
            return {"status": 200, "ok": True, "code": "saved", "message": "salvo"}
        except BuildError as exc:
            return {"status": 500, "ok": False, "code": "build_failed", "message": str(exc)}
        except Exception as exc:
            try:
                if os.path.isfile(os.path.join(backup, "flow.json")):
                    os.replace(os.path.join(backup, "flow.json"), flow_path)
                if os.path.isfile(os.path.join(backup, "flow.html")):
                    os.replace(os.path.join(backup, "flow.html"), os.path.join(dirpath, "flow.html"))
            finally:
                return {"status": 500, "ok": False, "code": "save_failed", "message": str(exc)}
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            shutil.rmtree(backup, ignore_errors=True)


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
                payload = json.loads(self.rfile.read(n))
            except Exception as e:
                self._json(400, {"ok": False, "code": "invalid_json", "message": f"JSON inválido: {e}"})
                return
            try:
                data = payload["flow"]
                expected_hash = payload["baseHash"]
            except (KeyError, TypeError):
                self._json(400, {"ok": False, "code": "invalid_payload", "message": "use flow e baseHash"})
                return
            result = save_candidate(dirpath, data, expected_hash)
            if result["status"] != 200:
                self._json(result["status"], result)
                return
            self._json(200, result)

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
