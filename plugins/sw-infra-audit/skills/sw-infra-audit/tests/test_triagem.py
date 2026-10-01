"""A triagem decide em que faixa cada achado cai — e e ela que o relatorio novo usa
para montar as tres bandas. E logica pura de proposito: ordenar e contar achado nao
precisa de HTML para ser verificado."""
import pytest
from lib.triagem import triar, FAIXAS, ORDEM_SEVERIDADE


def ach(sev, regra="r", esperada=False, **kw):
    return {"severidade": sev, "regra": regra, "esperada": esperada, **kw}


def test_cada_severidade_cai_na_faixa_que_lhe_cabe():
    t = triar([ach("critical"), ach("high"), ach("medium"), ach("low"), ach("info")])
    assert [len(t["faixas"][f]["achados"]) for f in ("agir", "programar", "registrar")] == [2, 1, 2]


def test_achado_esperado_nao_entra_em_faixa_nenhuma():
    """Regra marcada como esperada descreve o normal — cobrar isso e ruido."""
    t = triar([ach("high"), ach("high", esperada=True)])
    assert len(t["faixas"]["agir"]["achados"]) == 1
    assert t["esperados"] == 1
    assert t["total"] == 2


def test_a_cascata_fecha_a_conta():
    """O grafico de cascata so e honesto se as tres faixas somarem o total menos os esperados."""
    achados = ([ach("high")] * 7) + ([ach("medium")] * 114) + ([ach("low")] * 98) + [ach("low", esperada=True)]
    t = triar(achados)
    soma = sum(len(t["faixas"][f]["achados"]) for f in t["faixas"])
    assert t["total"] == 220 and t["esperados"] == 1
    assert soma == t["total"] - t["esperados"] == 219


def test_severidade_desconhecida_nao_some_do_relatorio():
    """Preferimos a faixa mais fraca a perder o achado: sumir calado e o pior resultado."""
    t = triar([ach("inventada")])
    assert sum(len(t["faixas"][f]["achados"]) for f in t["faixas"]) == 1


def test_dentro_da_faixa_a_ordem_e_a_da_severidade():
    t = triar([ach("low", "a"), ach("info", "b"), ach("low", "c")])
    assert [a["severidade"] for a in t["faixas"]["registrar"]["achados"]] == ["low", "low", "info"]


def test_empate_de_severidade_desempata_estavel_por_regra_e_objeto():
    """Duas execucoes com a mesma entrada tem de dar a mesma ordem — senao o diff
    entre auditorias acusa mudanca que nao houve."""
    a = [ach("medium", "z", objeto="2"), ach("medium", "a", objeto="9"), ach("medium", "a", objeto="1")]
    ordem = [(x["regra"], x["objeto"]) for x in triar(a)["faixas"]["programar"]["achados"]]
    assert ordem == [("a", "1"), ("a", "9"), ("z", "2")]
    assert ordem == [(x["regra"], x["objeto"]) for x in triar(list(reversed(a)))["faixas"]["programar"]["achados"]]


def test_as_faixas_tem_rotulo_e_ordem_fixa():
    assert [f[0] for f in FAIXAS] == ["agir", "programar", "registrar"]
    assert ORDEM_SEVERIDADE[0] == "critical"


def test_sem_achado_nenhum_as_tres_faixas_existem_vazias():
    """O relatorio desenha as tres bandas sempre; faixa ausente viraria KeyError no template."""
    t = triar([])
    assert set(t["faixas"]) == {"agir", "programar", "registrar"}
    assert t["total"] == 0 and all(not t["faixas"][f]["achados"] for f in t["faixas"])


# ------------------------------------------------------------------ cascata
from lib.triagem import cascata


def test_a_cascata_comeca_no_total_coletado():
    t = triar([ach("high"), ach("low", esperada=True)])
    degraus = {d["id"]: d["n"] for d in cascata(t)}
    assert degraus["total"] == 2
    assert degraus["acionaveis"] == 1


def test_os_tres_ultimos_degraus_somam_o_degrau_dos_acionaveis():
    """E o que o desenho promete: o universo afunila ate o que exige acao hoje."""
    t = triar(([ach("high")] * 7) + ([ach("medium")] * 114) + ([ach("low")] * 98))
    d = {x["id"]: x["n"] for x in cascata(t)}
    assert d["registrar"] + d["programar"] + d["agir"] == d["acionaveis"] == 219


def test_a_cascata_diz_quantos_esperados_saiu():
    assert [d["nota"] for d in cascata(triar([ach("low", esperada=True)])) if d["id"] == "acionaveis"] == ["menos 1"]
    assert [d["nota"] for d in cascata(triar([ach("low")])) if d["id"] == "acionaveis"] == ["nenhum esperado"]


def test_a_cascata_tem_os_cinco_degraus_na_ordem_do_desenho():
    assert [d["id"] for d in cascata(triar([]))] == ["total", "acionaveis", "registrar", "programar", "agir"]
