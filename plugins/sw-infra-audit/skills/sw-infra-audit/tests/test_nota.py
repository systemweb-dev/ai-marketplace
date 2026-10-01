"""A nota de estabilidade e a primeira frase que alguem le. Ela sai das dimensoes por
regra, nao da prosa do agente: titulo reinventado a cada rodada torna duas auditorias
incomparaveis, que e exatamente o que um relatorio de auditoria nao pode ser.

As dimensoes aqui tem a forma REAL do report.json (conferida contra uma rodada de
verdade). Teste que inventa a forma do dado valida a propria invencao.
"""
import json
import pathlib
import pytest
from lib.nota import nota_de_estabilidade, pontuacoes, ORDEM


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


# -------------------------------------------------------------------- titulo
def test_tudo_bem_e_dito_sem_rodeio():
    n = nota_de_estabilidade(dims())
    assert n["faixa"] == "bom" and n["titulo"].endswith(".")


def test_o_caso_classico_roda_mas_nao_tem_reserva():
    """Operacao cheia e disponibilidade baixa e a infra que serve hoje e cai amanha."""
    n = nota_de_estabilidade(dims(ha=42))
    assert "frágil" in n["titulo"].lower() and n["faixa"] == "atencao"
    assert n["pior"] == "disponibilidade"


def test_operacao_quebrada_manda_no_titulo():
    """Com servico fora do ar, nada mais importa primeiro."""
    n = nota_de_estabilidade(dims(op=(2, 10), ha=100))
    assert n["faixa"] == "ruim" and "fora do ar" in n["titulo"]


def test_a_nota_aponta_a_dimensao_mais_fraca():
    assert nota_de_estabilidade(dims(ha=90, hig=(31, 31, 31, 31)))["pior"] == "higiene"


def test_a_nota_diz_por_que_em_numero():
    assert "31 de 100" in nota_de_estabilidade(dims(hig=(31, 31, 31, 31)))["porque"]


def test_sem_dimensao_nenhuma_a_capa_ainda_existe():
    """Alvo sem dados chega com dimensoes vazias; a capa nao pode ficar em branco."""
    n = nota_de_estabilidade({})
    assert n["faixa"] == "sem_dados" and n["titulo"] and n["pior"] is None


def test_mesma_entrada_mesma_nota():
    assert nota_de_estabilidade(dims(ha=42)) == nota_de_estabilidade(dims(ha=42))


def test_valor_corrompido_nao_derruba_o_relatorio():
    for v in (-10, 101, None, "x"):
        assert nota_de_estabilidade(dims(ha=v))["titulo"]


def test_pontuacao_fica_presa_entre_0_e_100():
    """A barra da dimensao usa a nota como largura em %: 142 vazaria do cartao."""
    assert pontuacoes(dims(ha=142))["disponibilidade"] == 100
    assert pontuacoes(dims(ha=-5))["disponibilidade"] == 0
