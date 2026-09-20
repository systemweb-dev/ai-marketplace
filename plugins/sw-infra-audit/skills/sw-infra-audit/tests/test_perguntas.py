# tests/test_perguntas.py
from lib.papel import PAPEIS
from lib.perguntas import PERGUNTAS, do_papel


def test_perguntas_do_papel_vem_na_ordem_declarada():
    """A ordem é contrato: o orçamento corta da última para a primeira, então ela vai da
    pergunta mais barata para a mais cara."""
    assert [p["id"] for p in do_papel("entrada")] == [
        "entrada.volume_na_janela", "entrada.distribuicao_de_status", "entrada.latencia"]


def test_pergunta_de_lista_exige_desempate():
    """Empate de valor no top N herdaria a ordem da resposta da fonte, e o relatório mudaria
    entre rodadas sem nada ter mudado na infraestrutura."""
    for pergunta in PERGUNTAS.values():
        if pergunta["forma"] == "lista":
            assert pergunta.get("desempate"), f"{pergunta['id']} é lista e não declara desempate"


def test_toda_pergunta_pertence_a_um_papel_existente():
    invalidos = sorted({p["papel"] for p in PERGUNTAS.values()} - set(PAPEIS))
    assert invalidos == [], f"pergunta de papel inexistente: {invalidos}"


def test_id_da_pergunta_comeca_pelo_papel():
    """`entrada.top_rotas` — o prefixo é o que deixa o relatório agrupar sem tabela extra."""
    for id_, pergunta in PERGUNTAS.items():
        assert id_.split(".")[0] == pergunta["papel"], id_


def test_papel_sem_pergunta_devolve_lista_vazia():
    """`storage` existe no vocabulário e ainda não tem adaptador que o responda — perguntar
    sem quem responda só produziria `sem dados` em série."""
    assert do_papel("storage") == []
