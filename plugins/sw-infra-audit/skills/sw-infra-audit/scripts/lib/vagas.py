"""As vagas de um comando remoto: o único lugar onde valor variável entra num comando de host.

A parte A proibia vaga: o comando era o texto do catálogo, e o runner comparava texto com texto.
Componente de host precisa de alvo variável (`systemctl show <unit>`), então o comando passou a ser
MOLDE + VAGAS, cada vaga com o seu validador — no padrão do `forma_aceita` do `catalogo_exec`.
Nenhuma mensagem daqui repete o valor recusado: ele veio de um servidor e pode ser qualquer coisa.
"""
import re

# `{nome}` com UMA chave de cada lado: `{{.Names}}` e `{{json .State}}` (formato do docker) não são vaga.
VAGA = re.compile(r"(?<!\{)\{([a-z_]+)\}(?!\})")
# o mesmo alfabeto do que vem depois de `tipo:` em `alvos.ORIGEM`; começa por letra ou número, então
# nunca vira opção do comando
NOME_DE_ORIGEM = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@:-]{0,127}")
COLECAO = re.compile(r"[A-Za-z0-9_-]{1,64}")
PASTA = re.compile(r"/[A-Za-z0-9._/-]{0,254}")
# Dentro de aspas duplas o shell ainda interpreta `$`, crase e `\`, e `"` fecharia as aspas. `%`, `<`
# e `>` ficam de fora como no resto dos catálogos: uma leitura não precisa deles.
SQL_PROIBIDOS = frozenset('"$`\\%<>\n\r')


class VagaInvalida(Exception):
    """Molde ou valor de vaga que a skill se recusa a montar."""


def nomes(texto):
    return set(VAGA.findall(texto or ""))


def pasta_valida(valor):
    return (isinstance(valor, str) and bool(PASTA.fullmatch(valor))
            and ".." not in valor.split("/"))


def sql_valido(valor):
    return isinstance(valor, str) and bool(valor.strip()) and not (SQL_PROIBIDOS & set(valor))


def _validar(nome, valor, sqls):
    if nome in ("unidade", "container"):
        ok = isinstance(valor, str) and bool(NOME_DE_ORIGEM.fullmatch(valor))
    elif nome == "porta":
        ok = type(valor) is int and 1 <= valor <= 65535
    elif nome == "colecao":
        ok = isinstance(valor, str) and bool(COLECAO.fullmatch(valor))
    elif nome == "backup_pasta":
        ok = pasta_valida(valor)
    elif nome == "sql":
        ok = sql_valido(valor) and valor in sqls
    else:
        ok = False
    if not ok:
        raise VagaInvalida(f"valor recusado para a vaga {{{nome}}}")


def moldes_permitidos():
    """Os moldes de `references/host/linux.toml` e os clientes dos catálogos de produto válidos."""
    from lib import catalogo_host, catalogo_produto

    moldes = set(catalogo_host.carregar()["moldes"].values())
    for catalogo in catalogo_produto.validos():
        moldes |= set(catalogo["cliente"].values())
    return frozenset(moldes)


def sqls_permitidos():
    """As consultas literais dos catálogos de produto válidos — as únicas que entram em `{sql}`."""
    from lib import catalogo_produto

    sqls = set()
    for catalogo in catalogo_produto.validos():
        for pergunta in catalogo["pergunta"]:
            sqls |= set(pergunta["sql"])
            if pergunta["enumerar"]:
                sqls.add(pergunta["enumerar"]["sql"])
    return frozenset(sqls)


def preencher(molde, vagas):
    """O comando pronto, ou `VagaInvalida`.

    O molde precisa estar num catálogo; as vagas preenchidas precisam ser EXATAMENTE as que ele pede,
    contando as que vêm dentro do `{sql}` (`{colecao}`). Vaga sobrando é recusa, não descarte: quem
    manda uma vaga que o molde não usa está montando outro comando que não o do catálogo.
    """
    if not isinstance(molde, str) or molde not in moldes_permitidos():
        raise VagaInvalida("molde fora dos catálogos")
    if not isinstance(vagas, dict):
        raise VagaInvalida("as vagas precisam ser um dicionário")
    texto = molde
    if "sql" in nomes(molde):
        _validar("sql", vagas.get("sql"), sqls_permitidos())
        texto = texto.replace("{sql}", vagas["sql"])
    elif "sql" in vagas:
        raise VagaInvalida("vaga {sql} num molde que não a usa")
    pedidas = nomes(texto)
    if pedidas != set(vagas) - {"sql"}:
        raise VagaInvalida("as vagas preenchidas não são as que o molde pede")
    for nome in sorted(pedidas):
        _validar(nome, vagas[nome], ())
        texto = texto.replace("{" + nome + "}", str(vagas[nome]))
    return texto
