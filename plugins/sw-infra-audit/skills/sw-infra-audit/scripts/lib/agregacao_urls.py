"""Do texto do log às métricas por `host + caminho`. Sem rede e sem guardar nada bruto.

A linha só existe dentro de `agregar`: o que sai daqui é caminho normalizado e número.
"""
import math
import re
from urllib.parse import unquote

from lib.redact import scrub_text

MAX_CAMINHO = 200
MIN_TOKEN = 24
TOP_POR_SITE = 50
_CORTE = re.compile(r"[?#]")
_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")
_ID = re.compile(r"\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{8,}", re.I)
_ROTA = re.compile(r"v\d+|[a-z]+(?:[-_.][a-z0-9]+)*")
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,251}[a-z0-9])?")
_STATUS = re.compile(r"\d{1,3}")


def _sem_consulta(texto):
    return _CORTE.split(texto, maxsplit=1)[0]


def _segmento(cru):
    """Só o que tem cara de rota aparece: o `;` leva parâmetro de sessão, e o resto vira `:token`."""
    segmento = cru.split(";", 1)[0]
    if not segmento:
        return ""
    if _ID.fullmatch(segmento):
        return ":id"
    return ":token" if len(segmento) >= MIN_TOKEN or not _ROTA.fullmatch(segmento) else segmento


def normalizar_caminho(cru):
    """Caminho agregado, ou None quando não é caminho. Decodifica antes de cortar de novo:
    `%3Ftoken=x` é um `?` para quem lê o relatório."""
    texto = str(cru or "")
    if not texto.startswith("/"):
        return None
    decodificado = unquote(_sem_consulta(texto), errors="replace")
    limpo = _CONTROLE.sub("", _sem_consulta(decodificado))
    segmentos = [_segmento(s) for s in limpo.split("/")]
    return scrub_text("/" + "/".join(s for s in segmentos if s), limit=MAX_CAMINHO)


def _host(cru):
    host = str(cru).strip().lower()
    nome, separador, porta = host.rpartition(":")
    if separador and porta.isdigit():
        host = nome
    return scrub_text(host, limit=253) if _HOST.fullmatch(host) else None


def _duracao(cru):
    try:
        numero = float(cru)
    except ValueError:
        return None
    return None if math.isnan(numero) or math.isinf(numero) or numero < 0 else int(numero)


def ler_linha(texto):
    """(host, caminho, status, nanossegundos), ou None. Linha sem os quatro campos não é a do
    `line_format`, e a linha bruta tem cabeçalho: nada dela é aproveitado."""
    partes = str(texto).split("\t")
    if len(partes) != 4 or not _STATUS.fullmatch(partes[2]):
        return None
    host, caminho, duracao = _host(partes[0]), normalizar_caminho(partes[1]), _duracao(partes[3])
    if host is None or caminho is None or duracao is None:
        return None
    return host, caminho, int(partes[2]), duracao


def percentil_95(valores):
    """Posto mais próximo: é sempre um valor medido, e não depende de interpolação."""
    ordem = sorted(valores)
    return ordem[math.ceil(0.95 * len(ordem)) - 1]


def _item(host, caminho, grupo):
    acessos = len(grupo["duracoes"])
    return {"nome": f"{host}{caminho}", "site": host, "caminho": caminho, "acessos": acessos,
            "erros": grupo["erros"], "pct_5xx": round(100 * grupo["erros"] / acessos, 2),
            "p95_ms": round(percentil_95(grupo["duracoes"]) / 1_000_000, 2)}


def _ordem(item):
    return (-item["acessos"], item["nome"])


def agregar(linhas):
    grupos = {}
    descartadas = 0
    for texto in linhas:
        lida = ler_linha(texto)
        if lida is None:
            descartadas += 1
            continue
        host, caminho, status, duracao = lida
        grupo = grupos.setdefault((host, caminho), {"erros": 0, "duracoes": []})
        grupo["erros"] += 500 <= status < 600
        grupo["duracoes"].append(duracao)

    por_site = {}
    for (host, caminho), grupo in grupos.items():
        por_site.setdefault(host, []).append(_item(host, caminho, grupo))
    itens = [i for lista in por_site.values() for i in sorted(lista, key=_ordem)[:TOP_POR_SITE]]
    sites = [{"site": host, "acessos": sum(i["acessos"] for i in lista)} for host, lista in por_site.items()]
    return {"itens": sorted(itens, key=_ordem), "descartadas": descartadas,
            "sites": sorted(sites, key=lambda s: (-s["acessos"], s["site"]))}
