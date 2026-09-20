# tests/test_report_v3.py
from lib.report import (SCHEMA_VERSION, montar_inventario, novo, novo_alvo, novo_componente,
                        ordenar)


def test_alvo_nasce_com_lista_de_componentes():
    assert SCHEMA_VERSION == 3
    assert novo(generated_at="2026-09-19T10:00:00Z")["schema_version"] == 3
    assert novo_alvo("cluster", "docker", "context: prod")["componentes"] == []


def test_componente_guarda_papel_respostas_e_achados():
    assert novo_componente("proxy", "entrada") == {
        "nome": "proxy", "papel": "entrada", "respostas": [], "achados": [], "analise": ""}


def _relatorio_desordenado():
    r = novo("2026-09-19T10:00:00Z")
    alvo = novo_alvo("cluster", "docker", "context: prod")
    banco = novo_componente("banco", "banco")
    banco["respostas"] = [
        {"pergunta": "entrada.latencia", "fonte": "promql", "valor": 1},
        {"pergunta": "entrada.volume_na_janela", "fonte": "promql", "valor": 2}]
    alvo["componentes"] = [banco, novo_componente("proxy", "entrada")]
    r["alvos"] = [alvo]
    return r


def test_ordenar_deixa_componentes_e_respostas_em_ordem_estavel():
    """Sem isso a ordem vem do dicionário da coleta, e dois relatórios da mesma entrada saem
    diferentes — o teste de determinismo viraria teatro."""
    saida = ordenar(_relatorio_desordenado())

    assert [c["nome"] for c in saida["alvos"][0]["componentes"]] == ["banco", "proxy"]
    assert [x["pergunta"] for x in saida["alvos"][0]["componentes"][0]["respostas"]] == [
        "entrada.volume_na_janela", "entrada.latencia"]


def test_ordenar_nao_muta_a_entrada():
    """O histórico compara com o relatório anterior; mutar a baseline durante a comparação
    a corromperia."""
    r = _relatorio_desordenado()
    ordenar(r)
    assert [c["nome"] for c in r["alvos"][0]["componentes"]] == ["banco", "proxy"]
    assert r["alvos"][0]["componentes"][0]["respostas"][0]["pergunta"] == "entrada.latencia"


def test_inventario_continua_sendo_por_alvo():
    r = _relatorio_desordenado()
    assert montar_inventario(r) == [{"nome": "cluster", "tipo": "docker",
                                     "onde": "context: prod", "saude": "sem dados"}]
