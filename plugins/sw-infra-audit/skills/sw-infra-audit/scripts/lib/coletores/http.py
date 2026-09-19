"""Coletor de endpoint HTTP: está no ar, que código devolve, e quando o certificado vence.

Reaproveita o ponto de rede único (`lib/http_get.py`): só GET, sem credencial, sem seguir
redirect, com teto de bytes e tempo.
"""
import ipaddress
import time
from urllib.parse import urlparse

from lib import http_get, report as report_mod

FAIXAS = ((1, "<1s"), (10, "1-10s"), (60, "10-60s"), (float("inf"), ">60s"))
HOSTS_LOCAIS = ("localhost", "localhost.localdomain")
DIAS_DE_ALERTA = 30


def faixa(segundos):
    for teto, nome in FAIXAS:
        if segundos < teto:
            return nome
    return FAIXAS[-1][1]


def interno(host):
    """Loopback, rede privada ou nome de serviço. Cobrar TLS de endpoint interno é ruído — e
    ruído faz a regra ser ignorada no dia em que ela aponta um endpoint público de verdade."""
    if not host or host.casefold() in HOSTS_LOCAIS:
        return True
    if "." not in host:            # rótulo único: nome de serviço na rede interna
        return True
    try:
        endereco = ipaddress.ip_address(host)
    except ValueError:
        return False
    return endereco.is_loopback or endereco.is_private


def coletar(alvo, contexto):
    url = alvo["url"]
    partes = urlparse(url)
    timeout = contexto.get("http_timeout", 8)
    fatos, achados, nao_coletado = {}, [], []

    inicio = time.monotonic()
    codigo, _ = http_get.get_com_status(url, [partes.hostname], timeout=timeout)
    if codigo is not None:
        fatos["codigo"] = codigo
        fatos["tempo_faixa"] = faixa(time.monotonic() - inicio)
    else:
        nao_coletado.append(report_mod.na(f"não consegui alcançar {partes.hostname}"))

    # o certificado é lido mesmo quando o GET falha: vencido derruba o handshake, e é o achado
    # que mais importa
    if partes.scheme == "https":
        certificado = http_get.validade_do_certificado(url, [partes.hostname], timeout)
        fatos["certificado"] = certificado
        if "erro" in certificado:
            fatos["certificado"] = report_mod.na(f"não li o certificado: {certificado['erro']}")
        else:
            if certificado["dias"] <= DIAS_DE_ALERTA:
                achados.append({"regra": "certificado_vencendo", "objeto": partes.hostname,
                                "severidade": "critical" if certificado["dias"] <= 0 else "high",
                                "detalhe": f"expira em {certificado['expira_em']}",
                                "alvo": alvo["nome"]})
    else:
        fatos["certificado"] = report_mod.na("http sem TLS: não há certificado para checar")
        if not interno(partes.hostname):
            achados.append({"regra": "sem_tls", "objeto": partes.hostname, "severidade": "medium",
                            "detalhe": "endpoint público servido em http", "alvo": alvo["nome"]})

    if codigo is None:
        saude = "sem dados" if not achados else "🔴"
    elif codigo >= 500:
        achados.append({"regra": "http_fora_do_ar", "objeto": url, "severidade": "critical",
                        "detalhe": f"código {codigo}", "alvo": alvo["nome"]})
        saude = "🔴"
    elif codigo >= 400:
        # 4xx é servidor de pé respondendo: rota errada ou sem permissão, não serviço caído
        achados.append({"regra": "http_resposta_de_erro", "objeto": url, "severidade": "medium",
                        "detalhe": f"código {codigo}", "alvo": alvo["nome"]})
        saude = "🟡"
    elif any(a["severidade"] in ("critical", "high") for a in achados):
        saude = "🔴"
    elif achados:
        saude = "🟡"
    else:
        saude = "🟢"
    return {"saude": saude, "fatos": fatos, "achados": achados, "nao_coletado": nao_coletado}
