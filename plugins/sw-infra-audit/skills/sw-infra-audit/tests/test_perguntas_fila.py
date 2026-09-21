# tests/test_perguntas_fila.py
"""As perguntas do papel `fila`.

Antes desta task, `do_papel("fila")` devolvia lista vazia — o broker do cluster aparecia no
relatório com nome, papel e mais nada. Era o item que o dono pediu por extenso.
"""
from lib.perguntas import PERGUNTAS, REGRAS_PRODUZIDAS, do_papel

IDS = ["fila.filas", "fila.consumidores_por_fila", "fila.taxa_entrada_saida"]


def test_as_tres_perguntas_estao_registradas():
    assert [p["id"] for p in do_papel("fila")] == IDS


def test_toda_pergunta_de_lista_declara_desempate():
    """Empate de valor não pode herdar a ordem da resposta da API."""
    sem = [p["id"] for p in do_papel("fila") if p["forma"] == "lista" and not p["desempate"]]

    assert sem == []


def test_a_lista_de_filas_dispara_por_fila_sem_consumidor():
    limiar = PERGUNTAS["fila.filas"]["limiar"]

    assert limiar["regra"] == "fila_sem_consumidor"
    assert limiar["severidade"] == "high"


def test_perguntas_sem_limiar_sao_so_informacao():
    """`consumidores_por_fila` e `taxa_entrada_saida` descrevem; não acusam."""
    assert PERGUNTAS["fila.consumidores_por_fila"]["limiar"] is None
    assert PERGUNTAS["fila.taxa_entrada_saida"]["limiar"] is None


def test_filas_e_filas_com_acumulo_viraram_uma_so():
    """Eram a mesma lista, ordenada do mesmo jeito, impressa duas vezes no relatório."""
    assert "fila.filas_com_acumulo" not in PERGUNTAS


def test_o_registro_declara_as_regras_que_produz():
    """O limiar é um TERCEIRO produtor de achado, ao lado de `lib/rules.py` e do coletor http.
    Sem declarar o que produz, o teste do registro de regras só enxergaria os outros dois — e,
    ao registrar a regra nova, a única forma de calá-lo seria afrouxá-lo."""
    assert "fila_sem_consumidor" in REGRAS_PRODUZIDAS


def test_regras_produzidas_e_derivada_nao_digitada():
    """Uma lista digitada à mão desincroniza no primeiro limiar novo."""
    derivadas = {p["limiar"]["regra"] for p in PERGUNTAS.values() if p["limiar"]}

    assert REGRAS_PRODUZIDAS == derivadas


def test_todo_limiar_registrado_compila():
    """Limiar inválido no registro não levanta na coleta — `achados_da_resposta` engole e a
    regra simplesmente nunca dispara, sem um único sinal. O lugar de pegar isso é aqui."""
    from lib.limiar import compilar

    for pergunta in PERGUNTAS.values():
        if pergunta["limiar"]:
            compilar(pergunta["limiar"]["quando"])


def test_o_papel_entrada_nao_foi_mexido():
    """Regressão: `entrada` já está publicado."""
    assert [p["id"] for p in do_papel("entrada")] == [
        "entrada.volume_na_janela", "entrada.distribuicao_de_status", "entrada.latencia"]


# --- a semântica do limiar REAL, não só que ele compila ---
#
# Compilar prova a sintaxe e nada mais. Trocar `e` por `ou`, `>` por `>=` ou errar o nome do
# campo (`consumidor` no lugar de `consumidores`) passava com a suíte inteira verde — e a regra
# ou morria calada, ou acusava toda fila do broker.

def _dispara(item):
    from lib.limiar import avaliar

    return avaliar(PERGUNTAS["fila.filas"]["limiar"]["quando"], item)


def test_fila_orfa_com_mensagem_dispara():
    assert _dispara({"nome": "emails", "prontas": 7, "consumidores": 0}) is True


def test_fila_consumida_com_backlog_nao_dispara():
    """Com `ou` no lugar de `e`, toda fila com consumidor e fila acumulada viraria `high`."""
    assert _dispara({"nome": "pedidos", "prontas": 5000, "consumidores": 4}) is False


def test_fila_orfa_vazia_nao_dispara():
    """Com `>=` no lugar de `>`, toda fila ociosa sem consumidor viraria `high`."""
    assert _dispara({"nome": "ociosa", "prontas": 0, "consumidores": 0}) is False


def test_os_campos_do_limiar_sao_os_que_a_pergunta_devolve():
    """O nome do campo é um contrato com o catálogo da família. Um typo (`consumidor`) faz o
    campo virar None, `_comparar` devolve False, e a regra fica morta para sempre, sem sinal.

    O contrato é amarrado aqui do lado da pergunta; a Task 9 amarra do lado do catálogo,
    recusando catálogo que não extraia os campos que o limiar da pergunta usa.
    """
    import re

    quando = PERGUNTAS["fila.filas"]["limiar"]["quando"]
    campos = set(re.findall(r"([^\W\d]\w*)\s*(?:==|!=|>=|<=|>|<)", quando))

    assert campos == {"consumidores", "prontas"}
