"""A nota geral e a primeira coisa que alguem le. Ela sai das dimensoes e dos servicos por
regra, nao da prosa do agente: nota reinventada a cada rodada torna duas auditorias
incomparaveis, que e exatamente o que um relatorio de auditoria nao pode ser.

As dimensoes aqui tem a forma REAL do report.json (conferida contra uma rodada de
verdade). Teste que inventa a forma do dado valida a propria invencao.
"""
import json
import pathlib
import pytest
from lib.nota import nota_geral, pontuacoes

ORDEM = ("operacao", "disponibilidade", "seguranca", "higiene")


def dims(op=(57, 57), ha=100, high=0, med=0, hig=(100, 100, 100, 100)):
    """A forma que o coletor produz — nao uma inventada para o teste passar."""
    return {
        "operacao": {"services_up": op[0], "services_total": op[1], "stopped": 0,
                     "failing": 0, "nodes_down": 0},
        "disponibilidade": {"ha_pct": ha, "spof_stateful": [], "spof_critical": []},
        "seguranca": {"high": high, "med": med, "expected": 0},
        "higiene": {"pinned_pct": hig[0], "nonroot_pct": hig[1],
                    "limits_pct": hig[2], "healthcheck_pct": hig[3]},
    }


# ------------------------------------------------- a forma do dado e a de verdade
def test_a_forma_usada_no_teste_e_a_que_o_coletor_produz():
    """Trava de contrato: se o coletor mudar as chaves, este teste cai junto — em vez
    de o resto do arquivo continuar verde validando um formato que nao existe mais."""
    real = pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/dimensoes_reais.json"
    esperado = json.loads(real.read_text(encoding="utf-8"))
    for chave in ORDEM:
        assert set(esperado[chave]) >= set(dims()[chave]), f"{chave}: o teste inventou chave"


# --------------------------------------------------------------- pontuacoes
def test_operacao_e_a_fracao_de_servicos_no_ar():
    assert pontuacoes(dims(op=(57, 57)))["operacao"] == 100
    assert pontuacoes(dims(op=(5, 10)))["operacao"] == 50


def test_higiene_e_a_media_das_quatro_praticas_e_nao_so_uma():
    """61 fixadas, 0 nao-root, 42 com limite, 21 com healthcheck -> 31."""
    assert pontuacoes(dims(hig=(61, 0, 42, 21)))["higiene"] == 31


def test_dimensao_ausente_vira_None_e_nao_zero():
    """Nao coletado nao e zero: zero seria uma afirmacao que ninguem mediu."""
    assert pontuacoes({})["disponibilidade"] is None


# -------------------------------------------------------------------- nota
def alvo(dimensoes, replicas="1/1"):
    return {"nome": "c", "tipo": "docker", "dimensoes": dimensoes,
            "fatos": {"services": [{"name": "x_a", "replicas": replicas}]}, "achados": []}


def test_tudo_bem_e_dito_sem_rodeio():
    assert nota_geral([alvo(dims())], [])["faixa"] == "bom"


def test_o_caso_classico_roda_mas_nao_tem_reserva():
    """Operacao cheia e disponibilidade baixa e a infra que serve hoje e cai amanha."""
    n = nota_geral([alvo(dims(ha=42))], [])
    assert n["parcelas"]["estabilidade"] == 42 and n["parcelas"]["online"] == 100


def test_operacao_quebrada_manda_na_nota():
    """Com servico fora do ar, nada mais importa primeiro."""
    n = nota_geral([alvo(dims(ha=100), "0/1")], [])
    assert n["faixa"] == "critico" and n["valor"] <= 59


def test_a_nota_guarda_a_parcela_mais_fraca():
    assert nota_geral([alvo(dims(hig=(31, 31, 31, 31)))], [])["parcelas"]["praticas"] < 100


def test_sem_dimensao_nenhuma_a_nota_e_parcial():
    """Alvo sem dimensoes nao pode somar zero nem sair verde."""
    n = nota_geral([alvo({})], [])
    assert n["parcial"] is True and n["faixa"] != "bom"


def test_mesma_entrada_mesma_nota():
    assert nota_geral([alvo(dims(ha=42))], []) == nota_geral([alvo(dims(ha=42))], [])


def test_valor_corrompido_nao_derruba_o_relatorio():
    for v in (-10, 101, None, "x"):
        assert nota_geral([alvo(dims(ha=v))], [])["valor"] >= 0


def test_pontuacao_fica_presa_entre_0_e_100():
    """A barra da dimensao usa a nota como largura em %: 142 vazaria do cartao."""
    assert pontuacoes(dims(ha=142))["disponibilidade"] == 100
    assert pontuacoes(dims(ha=-5))["disponibilidade"] == 0
