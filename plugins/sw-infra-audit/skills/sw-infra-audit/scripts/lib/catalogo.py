"""Carrega os arquivos de família de exporter — o conhecimento de produto que NÃO vira código.

Mesmo protocolo não significa mesmo esquema: o Traefik publica `traefik_service_requests_total`
com a etiqueta `code`; uma aplicação instrumentada publica `http_requests_total` com `status`.
Um `if produto == ...` dentro do adaptador resolveria hoje e apodreceria amanhã; um arquivo por
família mantém o núcleo agnóstico e faz "adicionar o Kafka" ser escrever um arquivo.

A validação é dura de propósito e acontece no CARREGAMENTO, não na coleta: arquivo que cita
pergunta inexistente, interpolação fora das duas permitidas ou lista sem desempate é recusado
no teste, não no relatório de quem usa.
"""
import re
import tomllib
from pathlib import Path

INTERPOLACOES = ("%SELETOR%", "%JANELA%")
VALORES = ("inteiro", "decimal", "texto")
PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "metricas"
_MARCA = re.compile(r"%[A-Z_]+%")


class CatalogoInvalido(Exception):
    """Arquivo de família que a skill se recusa a interpretar."""


def carregar_arquivo(caminho):
    from lib.perguntas import PERGUNTAS

    caminho = Path(caminho)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise CatalogoInvalido(f"{caminho.name}: TOML inválido — {erro}") from erro

    for obrigatorio in ("familia", "prioridade", "identificacao"):
        if obrigatorio not in dados:
            raise CatalogoInvalido(f"{caminho.name}: falta {obrigatorio!r}")
    if not dados.get("seletor", {}).get("etiqueta"):
        raise CatalogoInvalido(f"{caminho.name}: falta `[seletor] etiqueta` — sem ela a "
                               f"consulta agregaria o exporter inteiro como se fosse o "
                               f"componente")
    if not dados["identificacao"].get("metrica_presente"):
        raise CatalogoInvalido(f"{caminho.name}: identificacao sem `metrica_presente` — é ela "
                               f"que diz se esta família é a certa para o componente")

    for pergunta in dados.get("pergunta", []):
        id_ = pergunta.get("id")
        if id_ not in PERGUNTAS:
            raise CatalogoInvalido(f"{caminho.name}: pergunta {id_!r} não existe no registro "
                                   f"de perguntas canônicas")
        for marca in sorted(set(_MARCA.findall(pergunta.get("query", ""))) - set(INTERPOLACOES)):
            raise CatalogoInvalido(f"{caminho.name}: interpolação {marca} não é permitida em "
                                   f"{id_}; só {' e '.join(INTERPOLACOES)}")
        if pergunta.get("valor", "inteiro") not in VALORES:
            raise CatalogoInvalido(f"{caminho.name}: valor {pergunta.get('valor')!r} em {id_} "
                                   f"não existe; os tipos são {', '.join(VALORES)}")
        if PERGUNTAS[id_]["forma"] == "lista" and not pergunta.get("desempate"):
            raise CatalogoInvalido(f"{caminho.name}: {id_} é lista e não declara `desempate` — "
                                   f"empate de valor mudaria o relatório entre rodadas")
    return dados


def familias(pasta=PASTA):
    """Todas as famílias, em ordem estável: prioridade, depois nome.

    Ordem estável importa: é ela que decide quem responde quando duas famílias identificam o
    mesmo componente, e isso não pode depender da ordem do sistema de arquivos.
    """
    carregadas = [carregar_arquivo(p) for p in sorted(Path(pasta).glob("*.toml"))]
    return sorted(carregadas, key=lambda f: (f["prioridade"], f["familia"]))
