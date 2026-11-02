import re
import shutil
import subprocess

import pytest

import build_report as br
from lib import orcamento_paginas as op
from lib.dados_blocos import dados_do_papel
from tests.fixtures.relatorio_grande import relatorio_grande

chromium = pytest.mark.skipif(not br.find_chromium() or not shutil.which("pdfinfo"),
                              reason="Chromium ou pdfinfo ausente: limite não verificado")


def paginas(caminho):
    saida = subprocess.run(["pdfinfo", caminho], check=True, capture_output=True, text=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", saida, re.M).group(1))


def test_relatorio_pequeno_nao_corta():
    assert op.cortes({"achados": 10, "regras": 3, "sistemas": 5})["avisos"] == []


def test_cada_corte_tem_o_proprio_aviso():
    r = op.cortes({"achados": 204, "regras": 10, "sistemas": 30})
    assert r["afetados_max"] == 8 and r["juntar_online"] and len(r["avisos"]) >= 3


def test_registro_grande_avisa_que_o_limite_cedeu():
    r = op.cortes({"achados": 1, "regras": 1, "sistemas": 1, "aceites": 400})
    assert any("limite" in a for a in r["avisos"])


def test_a_fixture_tem_o_tamanho_de_referencia():
    r = relatorio_grande()
    assert len(r["alvos"][0]["fatos"]["services"]) == 60 and len(r["alvos"][0]["achados"]) == 216
    assert br._conta_sistemas(r["alvos"]) == 12
    assert any(a.get("como_resolver") for a in r["alvos"][0]["achados"])


def test_a_fixture_tem_a_forma_da_rodada_real():
    r = relatorio_grande()
    alvo = next(a for a in r["alvos"] if a.get("coletado") is not False)
    filas = dados_do_papel("fila", r["alvos"])["filas"]
    assert 140 <= len(filas) <= 160 and 200 < len(r["resumo"]) <= br.MAXIMO_DE_CARACTERES_NO_RESUMO
    assert sum(1 for s in alvo["fatos"]["stacks"] if s["routes"]) >= 10
    assert all(x.get("comando") for x in r["recomendacoes"])


def test_orcamento_conta_as_filas_ate_o_teto_e_o_resto_do_documento():
    base = {"regras": 3, "sistemas": 5}
    assert op._linhas({**base, "filas": 150}, 8) == op._linhas({**base, "filas": op.FILAS_MAX}, 8) \
        > op._linhas(base, 8)
    for campo in ("recomendacoes", "pontos_de_falha", "nos"):
        assert op._linhas({**base, campo: 8}, 8) > op._linhas(base, 8), campo


def _poucos_achados():
    """O limite de 60 achados escondia a conta: era ele que cortava, e não as linhas."""
    r = relatorio_grande()
    alvo = r["alvos"][0]
    alvo["achados"] = [next(a for a in alvo["achados"] if a["regra"] == regra)
                       for regra in sorted({a["regra"] for a in alvo["achados"]})] * 6
    assert len(alvo["achados"]) <= 60
    return r


def test_poucos_achados_em_muitas_regras_ainda_cortam():
    assert 'class="bl-aviso">Achados de baixa' in br.render_html_v3(_poucos_achados())


def test_o_monkeypatch_do_corte_chega_ao_render(monkeypatch):
    com_corte = br.render_html_v3(relatorio_grande())
    monkeypatch.setattr(op, "cortes", lambda c: dict(op.SEM_CORTE))
    sem_corte = br.render_html_v3(relatorio_grande())
    assert 'class="bl-aviso"' in com_corte and 'class="bl-aviso"' not in sem_corte
    assert len(sem_corte) > len(com_corte)


@chromium
def test_sem_corte_a_fixture_estoura(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "cortes", lambda c: dict(op.SEM_CORTE))
    assert paginas(br.build(relatorio_grande(), str(tmp_path), formato="html+pdf")["pdf"]) > 21


@chromium
def test_relatorio_de_57_servicos_tem_no_maximo_21_paginas(tmp_path):
    n = paginas(br.build(relatorio_grande(), str(tmp_path), formato="html+pdf")["pdf"])
    assert 0 < n <= 21


@chromium
def test_poucos_achados_em_muitas_regras_tem_no_maximo_21_paginas(tmp_path):
    assert paginas(br.build(_poucos_achados(), str(tmp_path), formato="html+pdf")["pdf"]) <= 21
