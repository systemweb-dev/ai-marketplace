# tests/test_report_v2.py
import json

from lib.report import (SCHEMA_VERSION, achados_ordenados, montar_inventario, na, novo,
                        novo_alvo, ordenar, valido)


def achado(regra, objeto, severidade, alvo):
    return {"regra": regra, "objeto": objeto, "severidade": severidade, "alvo": alvo}


def test_relatorio_novo_tem_o_esqueleto_do_v2():
    r = novo(generated_at="2026-09-19T10:00:00Z")

    assert r["schema_version"] == SCHEMA_VERSION == 2
    assert r["alvos"] == [] and r["aceites"] == [] and r["inventario"] == []
    assert r["resumo"] == "" and r["recomendacoes"] == []


def test_alvo_novo_nasce_sem_dados_ate_alguem_coletar():
    a = novo_alvo(nome="cluster", tipo="docker", onde="context: ctx")

    assert a["saude"] == "sem dados"
    assert a["achados"] == [] and a["nao_coletado"] == []
    assert a["analise"] == ""


def test_marcador_de_nao_coletado_carrega_o_motivo():
    assert na("alvo não confirmado nesta execução") == {"valor": None,
                                                        "motivo": "alvo não confirmado nesta execução"}


def relatorio_com_dois_alvos():
    r = novo(generated_at="x")
    r["alvos"] = [{"nome": "b", "achados": [achado("z", "2", "high", "b"),
                                            achado("a", "1", "critical", "b")]},
                  {"nome": "a", "achados": [achado("m", "9", "high", "a")]}]
    return r


def test_dentro_do_alvo_os_achados_vao_do_mais_grave_ao_menos():
    ordenado = ordenar(relatorio_com_dois_alvos())

    assert [f["regra"] for f in ordenado["alvos"][0]["achados"]] == ["a", "z"]


def test_a_lista_do_relatorio_e_global_por_severidade_e_nao_por_alvo():
    """A seção "Achados" abre pelo mais grave: se fosse agrupada por alvo, um crítico do
    segundo alvo ficaria abaixo de um aviso do primeiro."""
    chaves = [(f["severidade"], f["alvo"], f["regra"])
              for f in achados_ordenados(ordenar(relatorio_com_dois_alvos()))]

    assert chaves == [("critical", "b", "a"), ("high", "a", "m"), ("high", "b", "z")]


def test_ordem_dos_alvos_e_a_declarada_nao_a_alfabetica():
    r = novo(generated_at="x")
    r["alvos"] = [{"nome": "site", "achados": []}, {"nome": "cluster", "achados": []}]

    assert [a["nome"] for a in ordenar(r)["alvos"]] == ["site", "cluster"]


def test_inventario_sai_dos_alvos_com_o_que_interessa_para_o_mapa():
    r = novo(generated_at="x")
    r["alvos"] = [novo_alvo("cluster", "docker", "context: ctx"),
                  novo_alvo("site", "http", "https://exemplo.invalido/health")]
    r["alvos"][0]["saude"] = "🟢"

    assert montar_inventario(r) == [
        {"nome": "cluster", "tipo": "docker", "onde": "context: ctx", "saude": "🟢"},
        {"nome": "site", "tipo": "http", "onde": "https://exemplo.invalido/health",
         "saude": "sem dados"}]





def test_valido_exige_versao_e_lista_de_alvos():
    assert valido(novo(generated_at="x")) is True
    assert valido({"schema_version": 1, "alvos": []}) is False
    assert valido({"schema_version": 2}) is False


def test_determinismo_nao_depende_da_ordem_em_que_o_agente_escreveu():
    """Ordem de inserção diferente, mesmo relatório: é isso que a restrição 4 promete."""
    um = novo(generated_at="x")
    um["alvos"] = [{"nome": "a", "achados": [achado("z", "2", "high", "a"),
                                             achado("a", "1", "critical", "a")]}]
    dois = novo(generated_at="x")
    dois["alvos"] = [{"nome": "a", "achados": [achado("a", "1", "critical", "a"),
                                               achado("z", "2", "high", "a")]}]

    assert json.dumps(ordenar(um), ensure_ascii=False, indent=1) == \
        json.dumps(ordenar(dois), ensure_ascii=False, indent=1)


def test_ordenar_nao_estraga_o_relatorio_recebido():
    """O histórico compara com o relatório anterior: mutar a entrada corromperia a comparação."""
    original = novo(generated_at="x")
    original["alvos"] = [{"nome": "a", "achados": [achado("z", "2", "high", "a"),
                                                   achado("a", "1", "critical", "a")]}]
    antes = json.dumps(original, ensure_ascii=False, sort_keys=True)

    ordenar(original)

    assert json.dumps(original, ensure_ascii=False, sort_keys=True) == antes
