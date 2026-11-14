"""Catálogo de comandos de leitura do host: literais em [comando], moldes com vaga em [molde].

O `lib/catalogo.py` permite `%SELETOR%`; copiar aquele módulo traria a interpolação junto, e do
outro lado do ssh há um shell de verdade. Comando literal é o texto do arquivo, e o runner só aceita
um texto que esteja nesta lista. Molde tem vaga (`{unidade}`, `{container}`, `{backup_pasta}`), e a
vaga só é preenchida por `lib/vagas.py`, com o validador dela — nunca por formatação de texto livre.
"""
import tomllib
from pathlib import Path

from lib.vagas import nomes

ARQUIVO = Path(__file__).resolve().parent.parent.parent / "references" / "host" / "linux.toml"
PROIBIDOS = set(";|&$`<>%\n\r")
VAGAS_DO_MOLDE = {"unidade", "container", "backup_pasta"}


class CatalogoInvalido(Exception):
    """Catálogo de host que a skill se recusa a usar."""


def _checar(caminho, tabela, chave, texto):
    if not isinstance(texto, str) or not texto.strip():
        raise CatalogoInvalido(f"{caminho.name}: {tabela} {chave!r} vazio")
    ruins = sorted(PROIBIDOS & set(texto))
    if ruins:
        raise CatalogoInvalido(f"{caminho.name}: {tabela} {chave!r} tem {''.join(ruins)!r}; "
                               f"o comando não encadeia nem interpola")


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
        _checar(caminho, "comando", chave, texto)
        if nomes(texto):
            raise CatalogoInvalido(f"{caminho.name}: comando {chave!r} tem vaga; comando com vaga "
                                   f"mora em [molde]")
    moldes = dados.get("molde", {})
    if not isinstance(moldes, dict):
        raise CatalogoInvalido(f"{caminho.name}: [molde] é uma tabela")
    for chave, texto in moldes.items():
        _checar(caminho, "molde", chave, texto)
        vagas = nomes(texto)
        if not vagas or not vagas <= VAGAS_DO_MOLDE:
            raise CatalogoInvalido(f"{caminho.name}: molde {chave!r} precisa de vaga, só entre "
                                   f"{', '.join(sorted(VAGAS_DO_MOLDE))}")
    ignorar = dados.get("ignorar", [])
    if not isinstance(ignorar, list) or not all(isinstance(i, str) and i for i in ignorar):
        raise CatalogoInvalido(f"{caminho.name}: `ignorar` é lista de nomes de processo")
    return {"comandos": {k: v.strip() for k, v in comandos.items()},
            "moldes": {k: v.strip() for k, v in moldes.items()}, "ignorar": tuple(ignorar)}


def comandos_permitidos(caminho=None):
    return frozenset(carregar(caminho)["comandos"].values())
