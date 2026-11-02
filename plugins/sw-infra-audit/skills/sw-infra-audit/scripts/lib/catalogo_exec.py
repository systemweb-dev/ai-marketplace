"""Carrega `references/execs/<familia>.toml`: os únicos comandos que a skill roda dentro de um container.

A validação acontece no carregamento e recusa o que não é leitura fixa: shell, caminho de
binário, terminal, verbo que não seja de listagem e argumento fora do formato. A allowlist lê
estas formas, então um catálogo inválido fecha o `exec` em vez de abri-lo.
"""
import re
import tomllib
from pathlib import Path

from lib import produtos
from lib.extracao import ExtracaoInvalida, validar_declaracao

PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "execs"
VAGA = "{vhost}"
CHAVES = {"familia", "enumerar", "listar", "pergunta"}
CHAVES_DA_PERGUNTA = {"id", "lista", "identidade", "campos", "transformar", "derivar", "ordenar_por",
                      "ordem", "desempate"}

ID_DE_CONTAINER = re.compile(r"[0-9a-f]{12,64}")
# Começar com `-` faria o valor virar flag do comando.
VALOR_DA_VAGA = re.compile(r"(?!-)[A-Za-z0-9/_.:~-]{1,255}")
_TOKEN = re.compile(r"[A-Za-z0-9_-]+")
_INTERPRETADORES = {"sh", "bash", "ash", "dash", "zsh", "ksh", "busybox", "env", "python", "python3",
                    "perl", "ruby", "node", "php"}
_FLAGS_PROIBIDAS = {"-i", "-t", "-it", "-ti", "-c", "--interactive", "--tty"}
_VERBO_DE_LEITURA = "list_"


class CatalogoInvalido(Exception):
    """Arquivo de comandos que a skill se recusa a interpretar."""


def _validar_argv(arquivo, onde, argv, com_vaga):
    if not isinstance(argv, list) or len(argv) < 2 or not all(isinstance(t, str) for t in argv):
        raise CatalogoInvalido(f"{arquivo}: `{onde}.argv` precisa ser binário, verbo e argumentos")
    if argv[0] in _INTERPRETADORES or not _TOKEN.fullmatch(argv[0]):
        raise CatalogoInvalido(f"{arquivo}: `{onde}` chama {argv[0]!r} — só binário do produto, sem shell")
    if not argv[1].startswith(_VERBO_DE_LEITURA):
        raise CatalogoInvalido(f"{arquivo}: `{onde}` usa o verbo {argv[1]!r}, que não é de listagem")
    if argv.count(VAGA) != int(com_vaga):
        raise CatalogoInvalido(f"{arquivo}: `{onde}` precisa de {int(com_vaga)} vaga {VAGA}")
    for token in argv[2:]:
        if token in _FLAGS_PROIBIDAS or (token != VAGA and not _TOKEN.fullmatch(token)):
            raise CatalogoInvalido(f"{arquivo}: `{onde}` tem o argumento proibido {token!r}")


def _validar_pergunta(arquivo, pergunta, registro):
    id_ = pergunta.get("id")
    if id_ not in registro:
        raise CatalogoInvalido(f"{arquivo}: pergunta {id_!r} não existe no registro")
    desconhecidas = sorted(set(pergunta) - CHAVES_DA_PERGUNTA)
    if desconhecidas:
        raise CatalogoInvalido(f"{arquivo}: {id_} usa {', '.join(desconhecidas)}, fora da linguagem")
    try:
        validar_declaracao(pergunta)
    except ExtracaoInvalida as erro:
        raise CatalogoInvalido(f"{arquivo}: {id_} — {erro}") from erro
    from lib.catalogo_api import campos_do_limiar

    extraidos = set(pergunta.get("campos") or {}) | set(pergunta.get("derivar") or {})
    faltando = sorted(campos_do_limiar(registro[id_].get("limiar")) - extraidos)
    if faltando:
        raise CatalogoInvalido(f"{arquivo}: {id_} não extrai {', '.join(faltando)}, que o limiar compara")


def carregar_arquivo(caminho):
    from lib.perguntas import PERGUNTAS

    caminho = Path(caminho)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise CatalogoInvalido(f"{caminho.name}: TOML inválido — {erro}") from erro
    desconhecidas = sorted(set(dados) - CHAVES)
    if desconhecidas:
        raise CatalogoInvalido(f"{caminho.name}: chave desconhecida {', '.join(desconhecidas)}")
    if dados.get("familia") not in {p["nome"] for p in produtos.carregar()}:
        raise CatalogoInvalido(f"{caminho.name}: `familia` precisa ser um produto de produtos.toml")
    enumerar, listar = dados.get("enumerar") or {}, dados.get("listar") or {}
    if set(enumerar) - {"argv", "campo"} or set(listar) - {"argv"}:
        raise CatalogoInvalido(f"{caminho.name}: `enumerar` e `listar` só aceitam `argv` e `campo`")
    if not enumerar.get("campo"):
        raise CatalogoInvalido(f"{caminho.name}: `enumerar` sem `campo`")
    _validar_argv(caminho.name, "enumerar", enumerar.get("argv"), com_vaga=False)
    _validar_argv(caminho.name, "listar", listar.get("argv"), com_vaga=True)
    for pergunta in dados.get("pergunta", []):
        _validar_pergunta(caminho.name, pergunta, PERGUNTAS)
    return dados


def familias(pasta=PASTA):
    return [carregar_arquivo(p) for p in sorted(Path(pasta).glob("*.toml"))]


def forma_aceita(argv):
    """Este argv é, token a token, um comando do catálogo com a vaga bem preenchida?"""
    formas = [f[bloco]["argv"] for f in familias() for bloco in ("enumerar", "listar")]
    return any(len(argv) == len(forma)
               and all(VALOR_DA_VAGA.fullmatch(token) if esperado == VAGA else token == esperado
                       for token, esperado in zip(argv, forma))
               for forma in formas)
