"""A linguagem fechada que tira resposta de um JSON de API.

Fechada é o ponto: JSON pointer para achar, `campos` para nomear, `transformar` para tipar,
`ordenar_por`/`limite` para recortar, `derivar` para as contas. Não há expressão arbitrária —
uma linguagem que aceita expressão é `eval` com outro nome, e arquivo de catálogo é dado, não
código.

O que não couber aqui não ganha arquivo: vira adaptador próprio, com código e teste.
"""
import math
import re
from datetime import datetime

_INDICE = re.compile(r"0|[1-9][0-9]*")

TRANSFORMACOES = ("inteiro", "decimal", "texto", "bytes", "segundos", "percentual", "data_iso")
DERIVACOES = ("razao", "percentual_de", "diferenca", "soma")


class ExtracaoInvalida(Exception):
    """Arquivo de catálogo que a skill se recusa a interpretar."""


def ponteiro(documento, caminho):
    """JSON pointer (RFC 6901). `""` é o documento inteiro.

    Chave ausente devolve None em vez de levantar: a família pode não expor aquele campo, e
    isso é `sem_dados` daquela pergunta — não um defeito da skill.
    """
    if caminho in (None, ""):
        return documento
    if not str(caminho).startswith("/"):
        raise ExtracaoInvalida(
            f"ponteiro {caminho!r} não começa com '/' — ponteiro JSON sempre começa, e "
            f"'items/0' parece funcionar sem nunca achar nada")
    atual = documento
    for cru in str(caminho).split("/")[1:]:
        token = cru.replace("~1", "/").replace("~0", "~")
        if isinstance(atual, dict):
            if token not in atual:
                return None
            atual = atual[token]
        elif isinstance(atual, list):
            # O RFC 6901 só admite `0` ou `[1-9][0-9]*`. `-1` funcionava por acidente do
            # Python e devolvia o ÚLTIMO item onde o autor do catálogo pediu o primeiro.
            if not _INDICE.fullmatch(token):
                return None
            try:
                atual = atual[int(token)]
            except IndexError:
                return None
        else:
            return None
    return atual


def _numero(bruto):
    if isinstance(bruto, bool):
        # `True` vira 1.0 num float() e passaria por medida; booleano não é número aqui
        return None
    try:
        valor = float(bruto)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(valor) or math.isinf(valor) else valor


def transformar(bruto, tipo):
    """O valor tipado, ou None quando ele não é o que se declarou.

    None não é zero. Zero é uma medida ("nenhuma mensagem pronta"); None é a ausência dela
    ("não li"). Confundir os dois é o que faz relatório dizer "está tudo bem" sobre o que não
    olhou.
    """
    if tipo not in TRANSFORMACOES:
        raise ExtracaoInvalida(
            f"transformação {tipo!r} não existe; as permitidas são "
            f"{', '.join(TRANSFORMACOES)}")
    if bruto is None:
        return None
    if tipo == "texto":
        return str(bruto)
    if tipo == "data_iso":
        try:
            # `fromisoformat` já aceita o sufixo `Z` desde o 3.11; um `replace("Z", ...)`
            # aqui seria código morto e trocaria `Z` em qualquer posição da string.
            return datetime.fromisoformat(str(bruto)).isoformat()
        except ValueError:
            return None
    valor = _numero(bruto)
    if valor is None:
        return None
    if tipo in ("inteiro", "bytes"):
        return int(valor)
    if tipo == "percentual":
        return round(valor * 100, 2)
    return round(valor, 2)


def _valores(documento, caminhos):
    """Os números dos caminhos, ou None se QUALQUER um faltar.

    Um só ausente derruba a derivação inteira: somar o que existe e chamar de total seria
    inventar um denominador menor e, com ele, uma razão melhor do que a real.
    """
    saida = []
    for caminho in caminhos:
        valor = _numero(ponteiro(documento, caminho))
        if valor is None:
            return None
        saida.append(valor)
    return saida


def derivar(documento, declarada):
    """A conta declarada, ou None quando ela não pode ser feita com honestidade."""
    tipo = declarada.get("tipo")
    if tipo not in DERIVACOES:
        raise ExtracaoInvalida(
            f"derivação {tipo!r} não existe; as permitidas são {', '.join(DERIVACOES)}")

    if tipo == "soma":
        valores = _valores(documento, declarada.get("parcelas") or [])
        return None if valores is None else round(sum(valores), 4)

    if tipo == "diferenca":
        valores = _valores(documento, [declarada["de"], declarada["menos"]])
        return None if valores is None else round(valores[0] - valores[1], 4)

    if tipo == "razao":
        caminhos = [declarada["numerador"], *declarada["denominador_soma"]]
    else:                                   # percentual_de
        caminhos = [declarada["numerador"], declarada["denominador"]]
    valores = _valores(documento, caminhos)
    if valores is None:
        return None
    numerador, denominador = valores[0], sum(valores[1:])
    if denominador == 0:
        # não é 0 nem infinito: é "não dá para dizer". Cache sem acesso nenhum não tem taxa de
        # acerto, e escrever 0% acusaria um problema que não existe.
        return None
    bruto = numerador / denominador
    return round(bruto * 100, 2) if tipo == "percentual_de" else round(bruto, 4)


ORDENS = ("asc", "desc")
_OBRIGATORIAS = {"razao": ("numerador", "denominador_soma"),
                 "percentual_de": ("numerador", "denominador"),
                 "diferenca": ("de", "menos"),
                 "soma": ("parcelas",)}
_LISTAS = {"razao": ("denominador_soma",), "soma": ("parcelas",)}


def _validar_derivacao(nome, declarada):
    tipo = declarada.get("tipo")
    if tipo not in DERIVACOES:
        raise ExtracaoInvalida(
            f"derivação {tipo!r} em {nome!r} não existe; as permitidas são "
            f"{', '.join(DERIVACOES)}")
    for chave in _OBRIGATORIAS[tipo]:
        if chave not in declarada:
            raise ExtracaoInvalida(
                f"a derivação {nome!r} é do tipo {tipo!r} e não declara {chave!r}")
    for chave in _LISTAS.get(tipo, ()):
        if not isinstance(declarada[chave], list) or not declarada[chave]:
            # `denominador_soma = "/hits"` (string em vez de array) é erro trivial de TOML, e
            # sem esta checagem virava lista de CARACTERES: devolvia None para sempre, calado.
            raise ExtracaoInvalida(
                f"{nome!r}: {chave!r} precisa ser uma lista de ponteiros não vazia")


def validar_declaracao(declarada):
    """Recusa a declaração inteira ANTES de olhar o dado. Devolve None quando está boa.

    Existe porque validar só na extração deixava catálogo quebrado passar verde enquanto a
    fila estivesse vazia — e explodir no dia em que existisse uma fila. `lib/catalogo_api.py`
    chama isto no carregamento; `extrair` chama de novo, para quem usar o módulo direto.
    """
    campos = declarada.get("campos") or {}
    derivar_ = declarada.get("derivar") or {}
    if not campos and not derivar_:
        raise ExtracaoInvalida("a declaração não tem `campos` nem `derivar`: extrairia itens "
                               "vazios e o relatório mostraria N linhas sem informação")

    for caminho in campos.values():
        ponteiro({}, caminho)          # levanta se o ponteiro for malformado

    conhecidos = set(campos) | set(derivar_)
    for nome, regra in derivar_.items():
        if nome in campos:
            raise ExtracaoInvalida(
                f"`{nome}` está em `campos` e em `derivar` — nome repetido vira precedência "
                f"silenciosa, e o arquivo passa a depender da ordem de leitura")
        _validar_derivacao(nome, regra)

    for nome, tipo in (declarada.get("transformar") or {}).items():
        if nome not in campos:
            # Sem esta checagem, um typo deixava o campo CRU e a ordenação virava lexicográfica:
            # "9" > "42" > "900". O "top 2 filas com mais mensagens" entregava a fila de 9 no
            # lugar da de 42 — resposta errada com cara de certa.
            raise ExtracaoInvalida(
                f"`transformar` cita {nome!r}, que não está em `campos` — o campo ficaria cru "
                f"e um número viraria texto, mudando a ordenação sem avisar")
        if tipo not in TRANSFORMACOES:
            raise ExtracaoInvalida(
                f"transformação {tipo!r} em {nome!r} não existe; as permitidas são "
                f"{', '.join(TRANSFORMACOES)}")

    ordem = declarada.get("ordem", "desc")
    if ordem not in ORDENS:
        raise ExtracaoInvalida(
            f"`ordem = {ordem!r}` não existe; use {' ou '.join(ORDENS)}. Qualquer outra coisa "
            f"invertia o ranking em silêncio")

    chave = declarada.get("ordenar_por")
    if chave is not None:
        if chave not in conhecidos:
            raise ExtracaoInvalida(
                f"`ordenar_por = {chave!r}` não é um campo nem uma derivação desta pergunta — "
                f"a lista sairia na ordem da API com a legenda de ranking")
        desempate = declarada.get("desempate")
        if not desempate:
            raise ExtracaoInvalida(
                f"`ordenar_por` sem `desempate`: empate de valor herdaria a ordem da resposta "
                f"da API, e duas rodadas iguais dariam relatórios diferentes")
        if desempate not in conhecidos:
            raise ExtracaoInvalida(
                f"`desempate = {desempate!r}` não é um campo nem uma derivação desta pergunta")

    limite = declarada.get("limite")
    if limite is not None and (isinstance(limite, bool) or not isinstance(limite, int)
                               or limite < 0):
        raise ExtracaoInvalida(f"`limite = {limite!r}` precisa ser inteiro não negativo")


def _escalar(valor, nome):
    """O que sai da extração é sempre escalar.

    `campos` aceitava ponteiro para objeto, e o objeto ia inteiro para o `report.json` — e
    `/arguments` e `client_properties` carregam credencial com frequência. O caminho da
    extração não passa por `lib/redact.py`, então a linguagem é que precisa entregar escalar.
    """
    if isinstance(valor, (dict, list)):
        raise ExtracaoInvalida(
            f"o campo {nome!r} aponta para {type(valor).__name__}, e a extração entrega só "
            f"escalar — objeto inteiro no relatório é vazamento esperando acontecer")
    if isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor)):
        # `json.loads` aceita o literal NaN (Jackson emite), e `collect` grava com
        # `allow_nan=False`: um NaN numa fila abortava a gravação do relatório INTEIRO.
        return None
    return valor


def _item(bruto, declarada):
    if not isinstance(bruto, dict):
        raise ExtracaoInvalida(
            f"item da lista é {type(bruto).__name__}, não um objeto — cada campo viraria None "
            f"e o relatório mostraria linhas fantasma")
    campos = declarada.get("campos") or {}
    tipos = declarada.get("transformar") or {}
    saida = {}
    for nome, caminho in campos.items():
        valor = ponteiro(bruto, caminho)
        valor = transformar(valor, tipos[nome]) if nome in tipos else _escalar(valor, nome)
        saida[nome] = valor
    for nome, regra in (declarada.get("derivar") or {}).items():
        saida[nome] = derivar(bruto, regra)
    return saida


def extrair(documento, declarada):
    """Um item (quando não há `lista`) ou a lista de itens já ordenada e cortada."""
    validar_declaracao(declarada)
    if "lista" not in declarada:
        return _item(documento, declarada)

    cru = ponteiro(documento, declarada["lista"])
    if cru is None:
        return []
    if not isinstance(cru, list):
        raise ExtracaoInvalida(
            f"`lista = {declarada['lista']!r}` aponta para {type(cru).__name__}, não para um "
            f"array")

    itens = [_item(bruto, declarada) for bruto in cru]
    chave = declarada.get("ordenar_por")
    if chave:
        desempate = declarada.get("desempate")
        reverso = declarada.get("ordem", "desc") == "desc"
        # Chave TOTAL: valor, depois desempate, depois o item inteiro. Sem a última, duas filas
        # de mesmo nome em vhosts diferentes (que `/api/queues` lista junto) empatavam de vez e
        # a ordem saía da API — `limite: 1` escolheria uma diferente a cada rodada.
        # A ausência sai do `reverse`: invertida junto, ela subiria ao TOPO do ranking.
        presentes = [item for item in itens if item.get(chave) is not None]
        ausentes = [item for item in itens if item.get(chave) is None]
        presentes.sort(key=lambda item: (str(item.get(desempate, "")), _total(item)))
        presentes.sort(key=lambda item: item[chave], reverse=reverso)
        ausentes.sort(key=lambda item: (str(item.get(desempate, "")), _total(item)))
        itens = presentes + ausentes
    limite = declarada.get("limite")
    return itens if limite is None else itens[:limite]


def _total(item):
    """Ordem total, para quando valor e desempate empatam. Repr estável de um dicionário de
    escalares — é só um critério de desempate, não precisa ser bonito."""
    return repr(sorted((str(k), str(v)) for k, v in item.items()))
