# tests/test_limiar.py
"""A expressão de limiar — parser próprio, sem `eval`.

`eval` num arquivo de catálogo é execução de código a partir de dado. Mesmo sendo arquivo da
própria skill hoje, a linguagem é o contrato: no dia em que alguém aceitar catálogo de terceiro,
a diferença entre parser e `eval` é a diferença entre dado e RCE.

Sem parênteses e sem misturar `e` com `ou`: precedência implícita é a forma mais barata de o
arquivo dizer uma coisa e a skill entender outra.
"""
import pytest

from lib.limiar import LimiarInvalido, avaliar, compilar

ITEM = {"nome": "pedidos", "prontas": 42, "consumidores": 0, "hit_ratio": 0.75}


@pytest.mark.parametrize("expressao, esperado", [
    ("consumidores == 0", True),
    ("consumidores != 0", False),
    ("prontas > 40", True),
    ("prontas > 42", False),
    ("prontas >= 42", True),
    ("prontas < 100", True),
    ("prontas <= 42", True),
    ("hit_ratio < 0.8", True),
    ("nome == 'pedidos'", True),
    ('nome == "pedidos"', True),
    ("nome == 'outra'", False),
])
def test_comparacoes(expressao, esperado):
    assert avaliar(expressao, ITEM) is esperado


def test_conjuncao():
    assert avaliar("consumidores == 0 e prontas > 0", ITEM) is True
    assert avaliar("consumidores == 0 e prontas > 100", ITEM) is False


def test_disjuncao():
    assert avaliar("consumidores > 5 ou prontas > 40", ITEM) is True
    assert avaliar("consumidores > 5 ou prontas > 100", ITEM) is False


def test_misturar_e_com_ou_e_recusado():
    """`a e b ou c` tem duas leituras. Recusar é melhor que escolher uma em silêncio."""
    with pytest.raises(LimiarInvalido) as erro:
        compilar("consumidores == 0 e prontas > 0 ou nome == 'x'")

    assert "e" in str(erro.value) and "ou" in str(erro.value)


def test_campo_ausente_nao_dispara():
    """Campo que a família não expõe não pode virar achado: ausência não é evidência."""
    assert avaliar("consumidores == 0", {"nome": "x"}) is False


def test_campo_none_nao_dispara():
    """`consumidores = None` quer dizer "não li", e "não li" nunca vira achado."""
    assert avaliar("consumidores == 0", {"consumidores": None}) is False


def test_campo_none_nao_dispara_nem_com_diferente():
    """`!=` é o operador em que a ausência mais engana: `None != 0` é verdadeiro em Python, e
    a fila que não respondeu viraria "tem consumidor"."""
    assert avaliar("consumidores != 0", {"consumidores": None}) is False


def test_comparar_texto_com_numero_nao_explode():
    assert avaliar("nome > 10", ITEM) is False


def test_expressao_com_aritmetica_e_recusada():
    """Aritmética é derivação declarada, não expressão — a regra de ouro do spec."""
    with pytest.raises(LimiarInvalido):
        compilar("prontas / consumidores > 2")


def test_chamada_de_funcao_e_recusada():
    with pytest.raises(LimiarInvalido):
        compilar("__import__('os').system('rm -rf /') == 0")


def test_acesso_a_atributo_e_recusado():
    with pytest.raises(LimiarInvalido):
        compilar("nome.__class__ == 'x'")


def test_atribuicao_e_recusada():
    with pytest.raises(LimiarInvalido):
        compilar("prontas = 0")


def test_operador_desconhecido_e_recusado():
    with pytest.raises(LimiarInvalido):
        compilar("prontas ~ 0")


def test_literal_nao_numerico_sem_aspas_e_recusado():
    """`nome == pedidos` compararia campo com campo sem dizer — o spec só permite campo
    contra literal."""
    with pytest.raises(LimiarInvalido):
        compilar("nome == pedidos")


def test_compilar_e_reutilizavel():
    """Compila uma vez, avalia em 500 filas: o parser não pode rodar por item."""
    pronta = compilar("consumidores == 0 e prontas > 0")

    assert pronta(ITEM) is True
    assert pronta({"consumidores": 2, "prontas": 5}) is False


def test_expressao_vazia_e_recusada():
    with pytest.raises(LimiarInvalido):
        compilar("   ")


def test_campo_chamado_e_ou_ou_nao_quebra_a_divisao():
    """Um campo chamado `entrada` contém as letras "e", e `ou` aparece dentro de `roteadou`.
    A divisão é por PALAVRA; se fosse por substring, a expressão se partiria no meio do nome."""
    assert avaliar("entrada > 5", {"entrada": 9}) is True


def test_negrito_de_campo_com_maiuscula_e_digito():
    assert avaliar("fila_2 == 3", {"fila_2": 3}) is True


def test_booleano_do_item_nao_vira_numero():
    """`True == 1` em Python. Um campo booleano casaria com um limiar numérico."""
    assert avaliar("prontas == 1", {"prontas": True}) is False


def test_literal_entre_aspas_pode_conter_e():
    """Num catálogo em português, `e` é a palavra mais comum que existe. A divisão varria o
    texto INTEIRO, inclusive dentro das aspas, e `nome == 'produto e servico'` era recusado —
    com a mensagem apontando para `'produto`, um fragmento que o autor nunca escreveu."""
    assert avaliar("nome == 'produto e servico'", {"nome": "produto e servico"}) is True


def test_literal_entre_aspas_pode_ser_a_palavra_ou():
    assert avaliar("estado == 'ou'", {"estado": "ou"}) is True


def test_literal_com_e_nao_e_confundido_com_conjuncao():
    """Prova que a expressão não se partiu: se tivesse partido, sobrariam dois termos e o
    resultado seria outro."""
    assert avaliar("nome == 'a e b'", {"nome": "a"}) is False


def test_conjuncao_continua_funcionando_com_literal_de_texto():
    assert avaliar("nome == 'a e b' e n > 1", {"nome": "a e b", "n": 5}) is True


def test_campo_com_ou_dentro_do_nome():
    """`count`, `routing`, `grouped` contêm "ou". Por substring, a expressão se partiria no
    meio do nome do campo."""
    assert avaliar("consumers_count == 0", {"consumers_count": 0}) is True


@pytest.mark.parametrize("literal", ["nan", "inf", "-inf", "infinity", "NaN"])
def test_nan_e_infinito_nao_sao_literais(literal):
    """`float("nan")` aceita a string. E `prontas != nan` é VERDADEIRO para todo item —
    um achado por objeto, em cima de nada."""
    with pytest.raises(LimiarInvalido):
        compilar(f"prontas != {literal}")


def test_numero_em_notacao_cientifica_e_aceito():
    assert avaliar("prontas > 1e3", {"prontas": 5000}) is True


def test_campo_acentuado_e_aceito():
    """`média`, `usuário`, `memória` são nomes naturais num catálogo em português."""
    assert avaliar("média > 1", {"média": 9}) is True
