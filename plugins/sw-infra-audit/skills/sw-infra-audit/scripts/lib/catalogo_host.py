"""Catálogo de comandos de leitura do host — literais, sem vaga.

O `lib/catalogo.py` permite `%SELETOR%`; copiar aquele módulo traria a interpolação junto, e do
outro lado do ssh há um shell de verdade. Aqui o comando é o texto do arquivo, e o runner só aceita
um texto que esteja nesta lista.
"""
import tomllib
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent.parent / "references" / "host" / "linux.toml"
PROIBIDOS = set(";|&$`<>%\n\r")


class CatalogoInvalido(Exception):
    """Catálogo de host que a skill se recusa a usar."""


def carregar(caminho=None):
    caminho = Path(caminho or ARQUIVO)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except (OSError, tomllib.TOMLDecodeError) as erro:
        raise CatalogoInvalido(f"{caminho.name}: não consegui ler — {erro}") from erro
    comandos = dados.get("comando")
    if not isinstance(comandos, dict) or not comandos:
        raise CatalogoInvalido(f"{caminho.name}: sem tabela [comando]")
    for chave, texto in comandos.items():
        if not isinstance(texto, str) or not texto.strip():
            raise CatalogoInvalido(f"{caminho.name}: comando {chave!r} vazio")
        ruins = sorted(PROIBIDOS & set(texto))
        if ruins:
            raise CatalogoInvalido(f"{caminho.name}: comando {chave!r} tem {''.join(ruins)!r}; "
                                   f"o comando é literal, sem vaga nem encadeamento")
    ignorar = dados.get("ignorar", [])
    if not isinstance(ignorar, list) or not all(isinstance(i, str) and i for i in ignorar):
        raise CatalogoInvalido(f"{caminho.name}: `ignorar` é lista de nomes de processo")
    return {"comandos": {k: v.strip() for k, v in comandos.items()}, "ignorar": tuple(ignorar)}


def comandos_permitidos(caminho=None):
    return frozenset(carregar(caminho)["comandos"].values())
