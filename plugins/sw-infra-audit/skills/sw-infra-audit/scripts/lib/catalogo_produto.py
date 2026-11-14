"""Catálogos de produto para servidores host: `references/produtos-host/<produto>.toml`.

Produto novo é medido escrevendo um arquivo, sem mudar código: o cliente do produto por modo de
leitura, as consultas literais e como a saída vira resposta — pela linguagem fechada de
`lib/extracao.py`, nunca por expressão. O carregador recusa o que não é leitura fixa: vaga fora do
lugar, consulta com caractere que o shell interpretaria, pergunta que não existe no registro.
"""
import re
import tomllib
from pathlib import Path

from lib import catalogo_host, produtos
from lib.extracao import FORMATOS, ExtracaoInvalida, ponteiro, validar_declaracao
from lib.vagas import nomes, sql_valido

PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "produtos-host"
NOME_DE_PRODUTO = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
MODOS = ("socket", "senha", "container")
CHAVES = {"produto", "porta_padrao", "cliente", "erro", "pergunta"}
CHAVES_DO_ERRO = {"contem", "codigo", "modo", "motivo", "nao_publica"}
PROPRIAS = {"id", "sql", "formato", "colunas", "separador", "enumerar"}
DA_EXTRACAO = {"lista", "campos", "transformar", "derivar", "ordenar_por", "ordem", "desempate",
               "limite"}
VAGAS_DO_CLIENTE = {"socket": {"sql", "porta"}, "senha": {"sql", "porta"},
                    "container": {"sql", "container", "porta"}}
COLUNA = re.compile(r"[a-z_][a-z0-9_]{0,31}")


class CatalogoInvalido(Exception):
    """Catálogo de produto que a skill se recusa a usar."""


def _cliente(nome, modo, molde):
    if modo not in MODOS:
        raise CatalogoInvalido(f"{nome}: modo de leitura {modo!r} não existe; os modos são "
                               f"{', '.join(MODOS)}")
    if not isinstance(molde, str) or not molde.strip():
        raise CatalogoInvalido(f"{nome}: cliente {modo!r} vazio")
    ruins = sorted(catalogo_host.PROIBIDOS & set(molde))
    if ruins:
        raise CatalogoInvalido(f"{nome}: cliente {modo!r} tem {''.join(ruins)!r}; o cliente não "
                               f"encadeia nem interpola")
    sobrando = nomes(molde) - VAGAS_DO_CLIENTE[modo]
    if sobrando:
        raise CatalogoInvalido(f"{nome}: cliente {modo!r} usa a vaga {', '.join(sorted(sobrando))}, "
                               f"que este modo não preenche")
    partes = molde.split('"')
    if molde.count("{sql}") != 1 or len(partes) % 2 == 0 or any("{sql}" in p for p in partes[0::2]):
        raise CatalogoInvalido(f"{nome}: cliente {modo!r} precisa de UMA vaga {{sql}}, dentro de "
                               f"aspas duplas")


def _sql(nome, id_, sql, com_colecao):
    if not sql_valido(sql):
        raise CatalogoInvalido(f"{nome}: {id_} tem consulta vazia ou com caractere proibido "
                               f"(aspas duplas, $, crase, \\, %, <, > ou quebra de linha)")
    sobrando = nomes(sql) - ({"colecao"} if com_colecao else set())
    if sobrando:
        raise CatalogoInvalido(f"{nome}: {id_} tem a vaga {', '.join(sorted(sobrando))} na consulta")


def _enumerar(nome, id_, enumerar, formato, sqls):
    if not isinstance(enumerar, dict) or set(enumerar) != {"sql", "lista", "campo"} \
            or formato != "json":
        raise CatalogoInvalido(f"{nome}: {id_}: `enumerar` é {{sql, lista, campo}} e só vale com "
                               f"formato json")
    _sql(nome, id_, enumerar["sql"], com_colecao=False)
    try:
        ponteiro({}, enumerar["lista"])
    except ExtracaoInvalida as erro:
        raise CatalogoInvalido(f"{nome}: {id_}: `enumerar.lista` — {erro}") from erro
    if len(sqls) != 1 or "colecao" not in nomes(sqls[0]):
        raise CatalogoInvalido(f"{nome}: {id_}: com `enumerar`, a consulta é uma só e usa a vaga "
                               f"{{colecao}}")


def _pergunta(nome, pergunta, registro):
    id_ = pergunta.get("id")
    if id_ not in registro:
        raise CatalogoInvalido(f"{nome}: pergunta {id_!r} não existe no registro")
    desconhecidas = sorted(set(pergunta) - PROPRIAS - DA_EXTRACAO)
    if desconhecidas:
        raise CatalogoInvalido(f"{nome}: {id_} usa {', '.join(desconhecidas)}, fora da linguagem")
    formato = pergunta.get("formato")
    if formato not in FORMATOS:
        raise CatalogoInvalido(f"{nome}: {id_} tem formato {formato!r}; os formatos são "
                               f"{', '.join(FORMATOS)}")
    sqls = pergunta.get("sql")
    sqls = [sqls] if isinstance(sqls, str) else sqls
    if not isinstance(sqls, list) or not sqls:
        raise CatalogoInvalido(f"{nome}: {id_} sem `sql`")
    if len(sqls) > 1 and formato != "chave_valor":
        raise CatalogoInvalido(f"{nome}: {id_} junta {len(sqls)} consultas; só `chave_valor` sabe "
                               f"juntar")
    enumerar = pergunta.get("enumerar")
    if enumerar is not None:
        _enumerar(nome, id_, enumerar, formato, sqls)
    for sql in sqls:
        _sql(nome, id_, sql, com_colecao=enumerar is not None)
    colunas = pergunta.get("colunas")
    if formato == "tsv" and (not isinstance(colunas, list) or not colunas or not all(
            isinstance(c, str) and COLUNA.fullmatch(c) for c in colunas)):
        raise CatalogoInvalido(f"{nome}: {id_} em tsv precisa de `colunas` (nomes minúsculos)")
    separador = pergunta.get("separador")
    if separador is not None and (not isinstance(separador, str) or len(separador) != 1):
        raise CatalogoInvalido(f"{nome}: {id_}: `separador` é um caractere")
    extracao = {k: v for k, v in pergunta.items() if k in DA_EXTRACAO}
    try:
        validar_declaracao(extracao)
    except ExtracaoInvalida as erro:
        raise CatalogoInvalido(f"{nome}: {id_} — {erro}") from erro
    extraidos = set(extracao.get("campos") or {}) | set(extracao.get("derivar") or {})
    if registro[id_]["forma"] == "lista":
        if "lista" not in extracao:
            raise CatalogoInvalido(f"{nome}: {id_} é lista no registro e não declara `lista`")
    elif "lista" in extracao or "valor" not in extraidos:
        raise CatalogoInvalido(f"{nome}: {id_} é escalar: declare o campo ou a derivação `valor`, "
                               f"sem `lista`")
    return {"id": id_, "sql": list(sqls), "formato": formato, "colunas": colunas,
            "separador": separador, "enumerar": enumerar, "extracao": extracao}


def _erro(nome, erro, modos):
    if not isinstance(erro, dict) or set(erro) - CHAVES_DO_ERRO \
            or not isinstance(erro.get("motivo"), str) or not erro["motivo"].strip():
        raise CatalogoInvalido(f"{nome}: cada [[erro]] tem `motivo` e `contem` ou `codigo`")
    contem, codigo = erro.get("contem"), erro.get("codigo")
    if (contem is None and codigo is None) or (contem is not None and (
            not isinstance(contem, str) or not contem)) or (
            codigo is not None and type(codigo) is not int):
        raise CatalogoInvalido(f"{nome}: [[erro]] precisa de `contem` (texto) ou `codigo` (inteiro)")
    if erro.get("modo") is not None and erro["modo"] not in modos:
        raise CatalogoInvalido(f"{nome}: [[erro]] cita o modo {erro['modo']!r}, que o [cliente] "
                               f"não tem")
    if "nao_publica" in erro and type(erro["nao_publica"]) is not bool:
        raise CatalogoInvalido(f"{nome}: [[erro]]: `nao_publica` é true ou false")
    return dict(erro)


def carregar_arquivo(caminho):
    from lib.perguntas import PERGUNTAS

    caminho = Path(caminho)
    nome = caminho.name
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except (OSError, tomllib.TOMLDecodeError) as erro:
        raise CatalogoInvalido(f"{nome}: não consegui ler — {erro}") from erro
    desconhecidas = sorted(set(dados) - CHAVES)
    if desconhecidas:
        raise CatalogoInvalido(f"{nome}: chave desconhecida {', '.join(desconhecidas)}")
    produto = dados.get("produto")
    if produto != caminho.stem:
        raise CatalogoInvalido(f"{nome}: `produto` precisa ser o nome do arquivo ({caminho.stem!r})")
    if produto not in {p["nome"] for p in produtos.carregar()}:
        raise CatalogoInvalido(f"{nome}: o produto {produto!r} não está em references/produtos.toml")
    cliente = dados.get("cliente")
    if not isinstance(cliente, dict) or not cliente:
        raise CatalogoInvalido(f"{nome}: sem tabela [cliente]")
    for modo, molde in cliente.items():
        _cliente(nome, modo, molde)
    porta = dados.get("porta_padrao")
    if porta is not None and (type(porta) is not int or not 1 <= porta <= 65535):
        raise CatalogoInvalido(f"{nome}: `porta_padrao` é inteiro de 1 a 65535")
    if porta is None and any("porta" in nomes(m) for m in cliente.values()):
        raise CatalogoInvalido(f"{nome}: cliente com vaga {{porta}} precisa de `porta_padrao`")
    erros = [_erro(nome, e, cliente) for e in dados.get("erro", [])]
    perguntas = dados.get("pergunta")
    if not isinstance(perguntas, list) or not perguntas:
        raise CatalogoInvalido(f"{nome}: nenhuma [[pergunta]]")
    lidas = [_pergunta(nome, p, PERGUNTAS) for p in perguntas]
    ids = [p["id"] for p in lidas]
    if len(ids) != len(set(ids)):
        raise CatalogoInvalido(f"{nome}: pergunta repetida")
    return {"produto": produto, "porta_padrao": porta, "cliente": dict(cliente), "erro": erros,
            "pergunta": lidas}


def do_produto(nome, pasta=None):
    """O catálogo do produto; None quando não há arquivo. Arquivo inválido levanta."""
    if not isinstance(nome, str) or not NOME_DE_PRODUTO.fullmatch(nome):
        return None
    caminho = Path(pasta or PASTA) / f"{nome}.toml"
    return carregar_arquivo(caminho) if caminho.is_file() else None


def todos(pasta=None):
    return [carregar_arquivo(p) for p in sorted(Path(pasta or PASTA).glob("*.toml"))]


def validos(pasta=None):
    """Só os catálogos que carregam: um arquivo errado não tira os moldes e as consultas dos outros.

    O motivo de cada inválido não se perde: quem pergunta daquele produto o recebe de `do_produto`.
    """
    saida = []
    for caminho in sorted(Path(pasta or PASTA).glob("*.toml")):
        try:
            saida.append(carregar_arquivo(caminho))
        except CatalogoInvalido:
            continue
    return saida
