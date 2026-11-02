"""Adaptador de log: URLs mais acessadas, lidas do Loki declarado em `logs_url`.

Só `GET` na `rota` do catálogo, só na `logs_url` do alvo, só com a consulta do catálogo, que sempre passa
por `line_format`. O corpo da resposta traz o caminho cru nos rótulos do stream: daqui só sai o
quarteto da linha formatada, e ele só chega ao `agregar`. Nenhuma exceção carrega texto do log
para o relatório: bug vira o nome do tipo do erro.

A agregação no LogQL estoura `maximum of series (500)`, então são janelas de 1 hora com `limit`.
"""
import json
from datetime import datetime, timezone
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from lib import agregacao_urls, catalogo_logs, http_get
from lib.adaptadores.promql import momento

ID = "logql"
PERGUNTA = "entrada.urls_mais_acessadas"
JANELA_S = 3600
JANELAS_PADRAO = 24
LIMITE = 5000
MAX_BYTES_JANELA = 32 * 1024 * 1024   # cada linha vira um stream com rótulos: o corpo incha
NAO_RESPONDEU = "o Loki não respondeu (endereço, porta ou rede)"
FORMATO = "a resposta do Loki veio em formato inesperado"
SEM_LOGS_URL = ("o alvo não declara `logs_url` — aponte no alvos.toml o Loki que recebe o log de "
                "acesso do proxy")
QUEDAS_SEGUIDAS = 2


def horas_da_janela(janela):
    """`6h` ou `2d` em horas. Formato que o log não entende fica no padrão."""
    texto = str(janela or "")
    unidade = {"h": 1, "d": 24}.get(texto[-1:])
    return int(texto[:-1]) * unidade if unidade and texto[:-1].isdigit() and int(texto[:-1]) else JANELAS_PADRAO


def _sem_dados(motivo, **extra):
    return dict({"pergunta": PERGUNTA, "sem_dados": True, "motivo": motivo}, **extra)


def base_de(url, rota):
    """A raiz do Loki, mesmo que o dono tenha colado a URL inteira de uma consulta."""
    partes = urlsplit(str(url))
    caminho = partes.path.split(rota.split("/api/")[0] + "/")[0].rstrip("/")
    return urlunsplit((partes.scheme, partes.netloc, caminho, "", ""))


def consulta_de(familia):
    return familia["consulta"].replace("%SELETOR%", familia["seletor"])


def _url(raiz, consulta, inicio, fim):
    parametros = {"query": consulta, "start": inicio * 10 ** 9, "end": fim * 10 ** 9,
                  "limit": LIMITE, "direction": "backward"}
    return f"{raiz}?{urlencode(parametros, quote_via=quote)}"


def _textos(corpo):
    """As linhas formatadas, ou None. Lê só `values[][1]`: o rótulo `stream` nem é tocado."""
    try:
        documento = json.loads(corpo)
    except ValueError:
        return None
    dados = documento.get("data") if isinstance(documento, dict) else None
    if (not isinstance(dados, dict) or documento.get("status") != "success"
            or dados.get("resultType") != "streams" or not isinstance(dados.get("result"), list)):
        return None
    textos = []
    for stream in dados["result"]:
        valores = stream.get("values") if isinstance(stream, dict) else None
        if not isinstance(valores, list):
            return None
        for valor in valores:
            if not isinstance(valor, list) or len(valor) != 2 or not isinstance(valor[1], str):
                return None
            textos.append(valor[1])
    return textos


def _ler_janela(url, permitidos, timeout):
    """(linhas, motivo): um dos dois é sempre None."""
    try:
        status, corpo = http_get.get_com_status(url, permitidos, timeout=timeout, maximo=MAX_BYTES_JANELA)
    except http_get.RespostaGrandeDemais:
        return None, f"uma janela passou de {MAX_BYTES_JANELA // (1024 * 1024)} MB, grande demais para ler"
    if status is None:
        return None, NAO_RESPONDEU
    if status != 200:
        return None, f"o Loki respondeu {status}"
    textos = _textos(corpo or "")
    return (None, FORMATO) if textos is None else (textos, None)


def _iso(segundos):
    return datetime.fromtimestamp(segundos, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ler_janelas(raiz, consulta, fim, contexto):
    """Da hora mais recente para trás: sem orçamento, fica de fora o que é mais antigo."""
    prazo = contexto.get("prazo")
    pedido = contexto.get("http_timeout", contexto["timeout"])
    permitidos = [http_get.destino(raiz)]
    cobertas, linhas, falhas = [], [], set()
    quedas = 0
    for indice in range(horas_da_janela(contexto.get("janela"))):
        if prazo is not None and prazo.esgotado():
            falhas.add(prazo.motivo())
            break
        ate, desde = fim - indice * JANELA_S, fim - (indice + 1) * JANELA_S
        timeout = pedido if prazo is None else prazo.timeout(pedido)
        textos, motivo = _ler_janela(_url(raiz, consulta, desde, ate), permitidos, timeout)
        if textos is None:
            falhas.add(motivo)
            quedas = quedas + 1 if motivo == NAO_RESPONDEU else 0
            if quedas >= QUEDAS_SEGUIDAS:
                break
            continue
        quedas = 0
        linhas += textos
        cobertas.append({"inicio": _iso(desde), "fim": _iso(ate), "linhas": len(textos),
                         "amostrada": len(textos) >= LIMITE})
    return cobertas, linhas, sorted(falhas)


def _coletar(base, familia, contexto):
    fim = momento(contexto.get("at"))
    if fim is None:
        return _sem_dados("a rodada não tem um instante válido para ancorar as janelas")
    cobertas, linhas, falhas = _ler_janelas(f"{base}{familia['rota']}", consulta_de(familia), fim, contexto)
    if not cobertas:
        return _sem_dados(falhas[0] if falhas else "nenhuma janela foi lida")
    if not linhas:
        extra = {"nao_publica": True} if not falhas else {}
        return _sem_dados(falhas[0] if falhas else "o Loki respondeu sem nenhuma linha de acesso na "
                          "janela — confira se o proxy envia o log de acesso em JSON", **extra)
    agregado = agregacao_urls.agregar(linhas)
    if not agregado["itens"]:
        return _sem_dados("nenhuma linha veio no formato esperado da consulta")
    amostradas = sum(j["amostrada"] for j in cobertas)
    return {"pergunta": PERGUNTA, "fonte": f"{ID}:{familia['familia']}", "valor": agregado["itens"],
            "sites": agregado["sites"],
            "janelas": {"total": horas_da_janela(contexto.get("janela")), "cobertas": cobertas, "amostradas": amostradas,
                        "descartadas": agregado["descartadas"], "falhas": falhas,
                        "amostra": amostradas > 0 or len(cobertas) < horas_da_janela(contexto.get("janela"))}}


def perguntar(pergunta, componente, contexto):
    """Responde só a sua pergunta, uma vez por alvo: dois proxies leem o mesmo Loki."""
    if pergunta != PERGUNTA:
        return {"pergunta": pergunta, "sem_dados": True, "nao_se_aplica": True,
                "motivo": "o adaptador de log só responde às URLs mais acessadas"}
    if not contexto.get("logs_url"):
        return _sem_dados(SEM_LOGS_URL, nao_publica=True)
    cache = contexto.setdefault("cache", {})
    if "urls_logql" not in cache:
        cache["urls_logql"] = _resposta_segura(contexto)
    return dict(cache["urls_logql"])


def _resposta_segura(contexto):
    try:
        familia = catalogo_logs.familias()[0]
        return _coletar(base_de(contexto["logs_url"], familia["rota"]), familia, contexto)
    except http_get.NotConfirmed:
        raise
    except Exception as erro:                      # noqa: BLE001 — a mensagem poderia citar a linha
        return {"pergunta": PERGUNTA, "erro_interno": True, "motivo": f"{ID}: {type(erro).__name__}"}
