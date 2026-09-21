"""A expressão que transforma resposta em achado — parser próprio, nunca `eval`.

`eval` sobre arquivo de catálogo é executar código a partir de dado. Hoje o catálogo é da
própria skill; no dia em que alguém aceitar um de terceiro, a diferença entre parser e `eval` é
a diferença entre dado e execução remota.

A gramática é minúscula de propósito:

    expressao := termo (('e' | 'ou') termo)*
    termo     := CAMPO OP LITERAL
    OP        := == | != | >= | <= | > | <
    LITERAL   := número | 'texto' | "texto"

Sem parênteses e sem misturar `e` com `ou`: precedência implícita é a forma mais barata de o
arquivo dizer uma coisa e a skill entender outra. Sem aritmética: o que precisa de conta é
derivação declarada (`lib/extracao.py`).
"""
import math
import re

OPERADORES = ("==", "!=", ">=", "<=", ">", "<")
# `\w` é unicode por padrão no Python 3: `média`, `usuário` e `memória` são nomes
# naturais num catálogo em português, e a versão ASCII-only os recusava.
_TERMO = re.compile(r"^\s*([^\W\d]\w*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")


class LimiarInvalido(Exception):
    """Expressão que a skill se recusa a interpretar."""


def _literal(cru):
    """Número ou texto entre aspas. Qualquer outra coisa é recusada.

    `nome == pedidos` (sem aspas) compararia campo com campo sem dizer que faz isso; o spec
    permite campo contra LITERAL, e só.
    """
    if len(cru) >= 2 and cru[0] == cru[-1] and cru[0] in "\"'":
        return cru[1:-1]
    try:
        return int(cru)
    except ValueError:
        pass
    try:
        numero = float(cru)
    except ValueError:
        pass
    else:
        if math.isnan(numero) or math.isinf(numero):
            # `float("nan")` aceita a string, e `prontas != nan` é VERDADEIRO para todo item:
            # um achado por objeto, em cima de nada.
            raise LimiarInvalido(
                f"{cru!r} não é um número comparável; limiar com nan/inf ou nunca dispara ou "
                f"dispara sempre")
        return numero
    raise LimiarInvalido(
        f"{cru!r} não é literal: texto vai entre aspas e número vai sem elas. Comparar "
        f"dois campos não é permitido — o limiar é campo contra literal")


def _comparar(valor, operador, alvo):
    if valor is None:
        # "não li" nunca vira achado: ausência não é evidência. Vale inclusive para `!=`, o
        # operador em que isso mais engana — `None != 0` é verdadeiro em Python, e a fila que
        # não respondeu viraria "tem consumidor".
        return False
    if isinstance(valor, bool) != isinstance(alvo, bool):
        # `True == 1` em Python: um campo booleano casaria com um limiar numérico.
        return False
    try:
        if operador == "==":
            return valor == alvo
        if operador == "!=":
            return valor != alvo
        if operador == ">":
            return valor > alvo
        if operador == ">=":
            return valor >= alvo
        if operador == "<":
            return valor < alvo
        return valor <= alvo
    except TypeError:
        # texto contra número: o arquivo está errado, mas derrubar a auditoria inteira por
        # causa de uma fila seria pior que não disparar este limiar
        return False


_ASPAS = re.compile(r"'[^']*'|\"[^\"]*\"")


def _mascarar_literais(texto):
    """Troca cada literal entre aspas por um bloco de `\x00` do mesmo tamanho.

    A busca por `e`/`ou` varria o texto inteiro, inclusive dentro das aspas: num catálogo em
    português, `nome == 'produto e servico'` era recusado, e a mensagem apontava para
    `'produto` — um fragmento que o autor nunca escreveu. Mascarar preserva as POSIÇÕES, então
    os índices da máscara servem para cortar o texto original.
    """
    return _ASPAS.sub(lambda m: "\x00" * len(m.group(0)), texto)


def _partir(texto, mascara, juncao):
    """Parte o texto ORIGINAL nas posições onde a MÁSCARA tem a junção."""
    pedacos, inicio = [], 0
    for achado in re.finditer(rf"\b{juncao}\b", mascara):
        pedacos.append(texto[inicio:achado.start()])
        inicio = achado.end()
    pedacos.append(texto[inicio:])
    return pedacos


def compilar(expressao):
    """Devolve uma função `(item) -> bool`. Compila uma vez, avalia em N itens."""
    texto = str(expressao or "").strip()
    if not texto:
        raise LimiarInvalido("expressão de limiar vazia")

    # A busca é por PALAVRA (`\b`) e sobre o texto MASCARADO: `count` contém "ou" e um literal
    # em português contém "e" o tempo todo. Por substring ou sobre o texto cru, a expressão se
    # partiria no meio de um nome de campo ou dentro das aspas.
    mascara = _mascarar_literais(texto)
    tem_e = re.search(r"\be\b", mascara) is not None
    tem_ou = re.search(r"\bou\b", mascara) is not None
    if tem_e and tem_ou:
        raise LimiarInvalido(
            f"{texto!r} mistura `e` com `ou`, e isso tem duas leituras. Escreva duas regras, "
            f"ou uma derivação que já resolva a conta")

    juncao = "ou" if tem_ou else "e"
    termos = []
    for cru in _partir(texto, mascara, juncao):
        casado = _TERMO.match(cru)
        if not casado:
            raise LimiarInvalido(
                f"{cru.strip()!r} não é `campo OPERADOR literal`; os operadores são "
                f"{', '.join(OPERADORES)}, e não há aritmética nem chamada de função aqui")
        campo, operador, literal = casado.group(1), casado.group(2), _literal(casado.group(3))
        termos.append((campo, operador, literal))

    def pronta(item):
        resultados = [_comparar(item.get(campo), operador, alvo)
                      for campo, operador, alvo in termos]
        return any(resultados) if juncao == "ou" else all(resultados)

    return pronta


def campos(expressao):
    """Os nomes de campo que a expressão compara — o contrato com quem extrai o dado.

    Sobre o texto MASCARADO: em `nome == 'x > 1'`, o `x` está dentro das aspas e não é campo.
    """
    mascara = _mascarar_literais(str(expressao or ""))
    return set(re.findall(r"([^\W\d]\w*)\s*(?:==|!=|>=|<=|>|<)", mascara))


def avaliar(expressao, item):
    """Atalho para um item só — em lista, use `compilar` e reaproveite."""
    return compilar(expressao)(item)
