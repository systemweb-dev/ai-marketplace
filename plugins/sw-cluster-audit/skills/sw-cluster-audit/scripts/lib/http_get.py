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
import urllib.error
import urllib.request
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
