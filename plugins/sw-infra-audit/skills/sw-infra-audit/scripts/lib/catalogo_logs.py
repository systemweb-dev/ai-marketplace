"""Carrega as consultas de log. A forma é fixa: só mudam o seletor e os nomes dos campos.

Os logs brutos trazem cabeçalhos com segredo, então a consulta que não passa por `line_format`
não pode existir. A validação é por gramática inteira, não por lista do que é proibido.
"""
import re
import tomllib
from pathlib import Path

from lib.perguntas import PERGUNTAS

PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "logs"
CHAVES = {"familia", "pergunta", "rota", "seletor", "consulta"}
ROTA = re.compile(r"/[a-z]+/api/v1/query_range")
SELETOR = re.compile(r'\{[a-z_]+="[A-Za-z0-9_.-]+"\}')
CAMPO = r'"[A-Za-z]+"'
FORMA = re.compile(
    rf'%SELETOR% \|= {CAMPO} \| json h={CAMPO}, p={CAMPO}, s={CAMPO}, d={CAMPO} \| __error__="" \| '
    r'line_format "\{\{\.h\}\}\\t\{\{\.p\}\}\\t\{\{\.s\}\}\\t\{\{\.d\}\}"')
CAMPO_PROIBIDO = re.compile(r"cookie|authorization|header", re.I)


class CatalogoInvalido(Exception):
    """Arquivo de consulta de log que a skill se recusa a usar."""


def carregar_arquivo(caminho):
    caminho = Path(caminho)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise CatalogoInvalido(f"{caminho.name}: TOML inválido — {erro}") from erro
    if set(dados) != CHAVES:
        raise CatalogoInvalido(f"{caminho.name}: as chaves são exatamente {', '.join(sorted(CHAVES))}")
    if not ROTA.fullmatch(str(dados["rota"])):
        raise CatalogoInvalido(f"{caminho.name}: a única rota aceita é a de consulta `query_range`")
    if dados["pergunta"] not in PERGUNTAS:
        raise CatalogoInvalido(f"{caminho.name}: a pergunta não existe no registro canônico")
    if not SELETOR.fullmatch(str(dados["seletor"])):
        raise CatalogoInvalido(f"{caminho.name}: o seletor é um único rótulo com valor exato")
    consulta = str(dados["consulta"])
    if not FORMA.fullmatch(consulta) or CAMPO_PROIBIDO.search(consulta):
        raise CatalogoInvalido(f"{caminho.name}: a consulta foge da forma fixa com `line_format`")
    return dados


def familias(pasta=PASTA):
    return sorted((carregar_arquivo(p) for p in sorted(Path(pasta).glob("*.toml"))),
                  key=lambda f: f["familia"])
