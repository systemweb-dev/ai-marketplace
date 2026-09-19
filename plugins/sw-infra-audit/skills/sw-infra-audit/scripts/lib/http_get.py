"""Único ponto de rede da skill — GET read-only para endpoints CONFIRMADOS pelo usuário.

Invariante (FF7 revisada): a skill não faz egress nenhum, EXCETO GETs para hosts que o
usuário confirmou explicitamente (`--metrics-endpoint`). Aqui dentro:
  - só método GET, só http/https;
  - host obrigatoriamente na allowlist recebida;
  - sem credenciais/headers de auth, sem cookies;
  - redirect NÃO é seguido (evita exfiltração para outro host);
  - timeout curto e teto de bytes.
Nenhum outro módulo importa urllib/socket.
"""
import os
import socket
import ssl
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

MAX_BYTES = 4 * 1024 * 1024   # 4 MB de resposta é mais que suficiente pra /metrics
DEFAULT_TIMEOUT = 8


class NotConfirmed(Exception):
    """URL fora da allowlist de endpoints confirmados."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None   # nunca segue redirect


_OPENER = urllib.request.build_opener(_NoRedirect)


def host_of(url):
    p = urlparse(url or "")
    return p.hostname


def check_allowed(url, allowed_hosts):
    p = urlparse(url or "")
    if p.scheme not in ("http", "https"):
        raise NotConfirmed(f"esquema não permitido: {p.scheme!r}")
    if not p.hostname or p.hostname not in set(allowed_hosts or []):
        raise NotConfirmed(f"host não confirmado: {p.hostname!r}")
    return True


def get(url, allowed_hosts, timeout=DEFAULT_TIMEOUT):
    """GET read-only. Retorna o corpo (str) ou None se falhar/timeout.

    Levanta NotConfirmed se a URL não estiver na allowlist — é bug de chamada, não degradação.
    """
    check_allowed(url, allowed_hosts)
    req = urllib.request.Request(url, method="GET")  # sem headers de auth
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.read(MAX_BYTES).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return None   # indisponível → o coletor marca n/a


def get_com_status(url, allowed_hosts, timeout=DEFAULT_TIMEOUT):
    """Como `get`, mas devolve (status, corpo). `(None, None)` quando não deu para alcançar.

    Código de erro HTTP não é falha de alcance: o servidor respondeu, e isso é um achado.
    """
    check_allowed(url, allowed_hosts)
    req = urllib.request.Request(url, method="GET")
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read(MAX_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as erro:          # respondeu, só que com erro
        return erro.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return None, None                           # não alcancei


def _datas_do_der(seguro):
    """Sem verificação, `getpeercert()` vem vazio: lê as datas do DER com o parser da stdlib."""
    from ssl import DER_cert_to_PEM_cert
    pem = DER_cert_to_PEM_cert(seguro.getpeercert(binary_form=True))
    import re as _re
    # o objetivo é só a data de validade; o parser completo de X.509 não vale a dependência
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as arquivo:
        arquivo.write(pem)
        caminho = arquivo.name
    try:
        return ssl._ssl._test_decode_cert(caminho)
    finally:
        os.unlink(caminho)


def validade_do_certificado(url, allowed_hosts, timeout=DEFAULT_TIMEOUT):
    """Só as datas do certificado apresentado — nunca a cadeia inteira, nunca chave.

    Mora aqui, e não no coletor, porque abrir socket é abrir socket: passa pela mesma allowlist
    de host que todo o resto da rede desta skill.
    """
    check_allowed(url, allowed_hosts)
    partes = urlparse(url)
    # sem verificação de cadeia DE PROPÓSITO: só queremos as DATAS, e um certificado vencido
    # derrubaria o handshake — justamente o caso que a auditoria mais precisa enxergar
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((partes.hostname, partes.port or 443), timeout=timeout) as cru:
            with contexto.wrap_socket(cru, server_hostname=partes.hostname) as seguro:
                cert = seguro.getpeercert(binary_form=False) or _datas_do_der(seguro)
    except (OSError, ssl.SSLError, ValueError) as erro:
        return {"erro": str(erro)}
    expira = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    return {"dias": (expira - datetime.now(timezone.utc)).days,
            "expira_em": expira.date().isoformat()}
