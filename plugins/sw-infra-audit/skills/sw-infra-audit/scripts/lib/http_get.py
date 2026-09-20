"""Único ponto de rede da skill — GET read-only para endpoints CONFIRMADOS pelo usuário.

Invariante: a skill não faz egress nenhum, EXCETO GETs para destinos que o usuário declarou
no `alvos.toml` e confirmou na rodada (`--confirmar`). Aqui dentro:
  - só método GET, só http/https;
  - **host E porta** obrigatoriamente na allowlist recebida — host declarado não autoriza
    porta não declarada, senão a coleta viraria varredura de portas;
  - sem cookies; e sem credencial, EXCETO em `get_autenticado`, que é a única porta
    autenticada e nunca aceita credencial embutida na URL;
  - redirect NÃO é seguido (evita exfiltração para outro host);
  - timeout curto e teto de bytes.
Nenhum outro módulo importa urllib/socket.
"""
import base64
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


PORTA_PADRAO = {"http": 80, "https": 443}


def destino(url):
    """(host, porta) de uma URL, com a porta implícita do esquema já resolvida.

    Porta fora da faixa (erro de digitação no alvos.toml) vira `NotConfirmed` com a URL no
    texto — `urlparse().port` levanta `ValueError` cru, que chegaria ao relatório como
    "erro interno do coletor" em vez de "arruma a tua configuração".
    """
    p = urlparse(url or "")
    try:
        porta = p.port
    except ValueError as erro:
        raise NotConfirmed(f"porta inválida em {url!r}: {erro}") from erro
    return p.hostname, (porta if porta is not None else PORTA_PADRAO.get(p.scheme))


def check_allowed(url, permitidos):
    """`permitidos` é uma lista de (host, porta).

    Host declarado NÃO autoriza porta não declarada: um componente expõe métrica numa porta e
    administração noutra, e liberar o host inteiro transformaria a coleta em varredura de
    portas na máquina que o dono confirmou.
    """
    p = urlparse(url or "")
    if p.scheme not in ("http", "https"):
        raise NotConfirmed(f"esquema não permitido: {p.scheme!r}")
    if "@" in p.netloc:
        # `urlparse().hostname` DESCARTA o `user:senha@`, então sem esta guarda a URL passaria
        # na allowlist e a senha seguiria viva dentro dela: no header Host, no log do servidor,
        # e — pior — no valor copiado para o componente, que vira report.json, HTML e PDF.
        # A mensagem não repete o valor recusado, senão a senha iria para o terminal junto.
        raise NotConfirmed("a URL traz credencial embutida (`usuario:senha@`); declare a senha "
                           "em `senha_env` no alvos.toml")
    host, porta = destino(url)
    conhecidos = {(h, int(n)) for h, n in (permitidos or []) if h and n is not None}
    if not host or (host, porta) not in conhecidos:
        raise NotConfirmed(f"destino não confirmado: {host!r}:{porta}")
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


def get_autenticado(url, allowed_hosts, credencial, alvo=None, timeout=DEFAULT_TIMEOUT):
    """GET com credencial — a ÚNICA função desta skill que manda header de autenticação.

    `get()` e `get_com_status()` continuam anônimos de propósito: concentrar o segredo aqui é o
    que faz "por onde sai credencial?" ser uma pergunta com uma resposta só.

    A senha entra em header, nunca na URL: URL vai para log de servidor, para histórico de
    proxy e para mensagem de erro. Por isso `userinfo` na URL é recusado em vez de ignorado —
    `urlparse().hostname` descarta o `user:senha@`, então `check_allowed` aprovaria sem ver.

    `credencial` é um objeto `lib.credencial.Credencial` (ou None), NUNCA um par solto: é esta
    função que chama `.para(url, alvo)` e descobre se aquela senha pertence a este destino. A
    primeira versão recebia o par pronto, e aí a amarração virava convenção — quem chamasse
    `par()` em vez de `para()` mandava a senha para qualquer host da allowlist, sem erro. Um
    par ou uma string seriam desempacotados em silêncio (`"ab"` viraria `a:b`).

    Devolve `(status, corpo)`, com `(None, None)` quando não deu para alcançar — 401 volta como
    status, porque "a família é essa, falta credencial" é informação, não falha.
    """
    check_allowed(url, allowed_hosts)   # recusa esquema, destino fora da lista E userinfo
    req = urllib.request.Request(url, method="GET")
    if credencial is not None:
        if not hasattr(credencial, "para"):
            raise TypeError("credencial precisa ser um lib.credencial.Credencial; um par solto "
                            "não sabe a que destino pertence")
        par = credencial.para(url, alvo)
        if par:
            usuario, senha = par
            cru = f"{usuario}:{senha}".encode("utf-8")
            req.add_header("Authorization",
                           "Basic " + base64.b64encode(cru).decode("ascii"))
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read(MAX_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as erro:
        return erro.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return None, None


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
