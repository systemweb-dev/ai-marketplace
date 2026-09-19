"""Leitura e validação do alvos.toml — o arquivo que fica FORA do repositório.

Validação apertada de propósito: campo com erro de digitação (`metrica_url`) que passasse mudo
viraria "a skill não coleta métricas e não diz por quê". Tipo que o plano 1 ainda não implementa
é recusado aqui, com mensagem clara, em vez de chegar quebrado no coletor.
"""
import os
import re
import stat
import tomllib
from pathlib import Path
from urllib.parse import urlparse

OBRIGATORIOS = {
    "docker": ("context",),
    "http": ("url",),
}
OPCIONAIS = {
    "docker": ("metricas_url",),
    "http": (),
}
COMUNS = ("nome", "tipo")
NOME_VALIDO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ESQUEMAS = ("http", "https")


class AlvoInvalido(Exception):
    """Alvo que a skill se recusa a usar."""


def _checar_url(nome, campo, valor):
    partes = urlparse(str(valor))
    if partes.scheme not in ESQUEMAS or not partes.hostname:
        raise AlvoInvalido(f"alvo {nome!r}: {campo} precisa ser http(s) com host — {valor!r} não é")
    try:                          # porta fora da faixa é erro de configuração, não de coleta
        partes.port
    except ValueError as erro:
        raise AlvoInvalido(f"alvo {nome!r}: porta inválida em {campo} — {erro}") from erro


def ler(caminho):
    """Devolve (alvos, avisos). Arquivo ausente não é erro: é projeto ainda sem configurar."""
    caminho = Path(caminho)
    avisos = []
    if not caminho.exists():
        return [], [f"não encontrei {caminho} — rode `configurar.py migrar` para criar o primeiro"]

    modo = stat.S_IMODE(os.stat(caminho).st_mode)
    if modo & 0o077:
        avisos.append(f"permissão {oct(modo)} em {caminho.name}: outros usuários da máquina leem "
                      f"seus alvos. O recomendado é 600")

    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise AlvoInvalido(f"{caminho.name}: TOML inválido — {erro}") from erro
    except OSError as erro:
        raise AlvoInvalido(f"{caminho.name}: não consegui ler — {erro}") from erro

    brutos = dados.get("alvo", [])
    if not isinstance(brutos, list) or not all(isinstance(a, dict) for a in brutos):
        raise AlvoInvalido(f"{caminho.name}: cada alvo é um bloco [[alvo]] (lista de tabelas); "
                           f"[alvo.nome] não funciona")

    alvos, vistos = [], set()
    for bruto in brutos:
        nome = bruto.get("nome")
        if not isinstance(nome, str) or not NOME_VALIDO.match(nome):
            raise AlvoInvalido(f"{caminho.name}: nome de alvo inválido: {nome!r} — use letras, "
                               f"números, ponto, hífen ou sublinhado (o nome vira pasta e chave "
                               f"de histórico)")
        if nome.casefold() in vistos:
            raise AlvoInvalido(f"{caminho.name}: o alvo {nome!r} aparece duas vezes")
        vistos.add(nome.casefold())

        tipo = bruto.get("tipo")
        if tipo not in OBRIGATORIOS:
            extra = " (banco chega no plano 2)" if tipo in ("postgres", "mysql", "mariadb") else ""
            raise AlvoInvalido(f"{caminho.name}: alvo {nome!r} tem tipo {tipo!r}; os tipos desta "
                               f"versão são {', '.join(sorted(OBRIGATORIOS))}{extra}")

        permitidos = set(COMUNS) | set(OBRIGATORIOS[tipo]) | set(OPCIONAIS[tipo])
        desconhecidos = sorted(set(bruto) - permitidos)
        if desconhecidos:
            raise AlvoInvalido(f"{caminho.name}: alvo {nome!r} ({tipo}) tem campo que não existe: "
                               f"{', '.join(desconhecidos)}. Permitidos: {', '.join(sorted(permitidos))}")

        faltando = [campo for campo in OBRIGATORIOS[tipo] if not bruto.get(campo)]
        if faltando:
            raise AlvoInvalido(f"{caminho.name}: alvo {nome!r} ({tipo}) sem {', '.join(faltando)}")

        for campo in ("url", "metricas_url"):
            if bruto.get(campo):
                _checar_url(nome, campo, bruto[campo])

        alvos.append(dict(bruto))
    return alvos, avisos


def selecionar(alvos, escolhidos):
    """Filtra pelos nomes do arquivo do projeto, **na ordem em que ele declarou**.

    Lista vazia = todos. Nome inexistente é erro: silenciar viraria auditoria incompleta sem aviso.
    """
    if not escolhidos:
        return list(alvos)
    por_nome = {a["nome"]: a for a in alvos}
    faltando = [nome for nome in escolhidos if nome not in por_nome]
    if faltando:
        raise AlvoInvalido(f"alvo(s) {', '.join(faltando)} não existem no alvos.toml")
    return [por_nome[nome] for nome in escolhidos]
