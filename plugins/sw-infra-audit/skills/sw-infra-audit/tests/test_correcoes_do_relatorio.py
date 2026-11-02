"""Achados da revisão do relatório simples: cada um travado por teste."""
import shutil
import subprocess

import pytest

import build_report as br
from lib import blocos as b
from lib import catalogo, orcamento_paginas as op, perguntas
from lib.capa import render_capa
from lib.dados_blocos import dados_do_papel
from tests.test_build_report_v3 import relatorio

SENHA = "S3nhaFalsaDoTeste"
COMANDO_COM_SENHA = f"curl https://admin:{SENHA}@exemplo.invalido/api"

pdf_textual = pytest.mark.skipif(not br.find_chromium() or not shutil.which("pdftotext"),
                                 reason="Chromium ou pdftotext ausente: PDF não verificado")


def _linha_do_que_faltou(html):
    return html.split('class="bl-naoviu"', 1)[1].split("</div>", 1)[0]


# --- 1. a capa diz o que não foi medido
def test_alvo_inteiro_sem_dados_aparece_na_linha_do_que_nao_foi_medido():
    assert "site" in _linha_do_que_faltou(br.render_html_v3(relatorio()))


def test_alvo_sem_dados_nao_sai_da_linha_cortado_pelos_componentes():
    alvos = [{"nome": "zeta", "nao_coletado": [{"motivo": "x"}]},
             {"nome": "a", "componentes": [{"nome": "b", "papel": "banco"}],
              "cobertura": {"mudos": [{"componente": c} for c in "bcde"]}}]
    assert br._faltou(alvos) == ["zeta", "bancos", "3 serviços"]


def test_a_capa_diz_quantos_ficaram_fora_da_linha_do_que_nao_foi_medido():
    html = render_capa({}, None, "", list("abcdefgh"))
    assert "a, b, c, d, e, f e mais 2." in html


def test_alvo_fora_da_rodada_fica_so_em_fora_desta_rodada():
    r = relatorio()
    r["alvos"][1]["coletado"] = False
    r["alvos"][1]["cobertura"] = {"mudos": [{"componente": "comp-do-site", "pergunta": "p"}]}
    html = br.render_html_v3(r)
    assert 'class="bl-naoviu"' not in html
    assert "Fora desta rodada: site" in html


# --- 2. sem taxa medida, a fila não se diz ociosa
def _fila_com(taxa):
    alvo = {"componentes": [{"nome": "mq", "papel": "fila", "respostas": [
        {"pergunta": "fila.filas", "valor": [{"nome": "e", "prontas": 0, "consumidores": 1}]}, taxa]}]}
    return b.render_bloco("fila", dados_do_papel("fila", [alvo]))


def test_estatisticas_desligadas_nao_viram_fila_ociosa():
    html = _fila_com({"pergunta": "fila.taxa_entrada_saida", "sem_dados": True})
    assert "ritmo não medido" in html.lower()
    assert "Ociosa" not in html and "Sem movimento" not in html and "ociosa" not in html


def test_taxa_medida_em_outra_fila_prova_que_esta_esta_ociosa():
    alvo = {"componentes": [{"nome": "mq", "papel": "fila", "respostas": [
        {"pergunta": "fila.filas", "valor": [{"nome": "e", "prontas": 0, "consumidores": 1},
                                             {"nome": "f", "prontas": 0, "consumidores": 1}]},
        {"pergunta": "fila.taxa_entrada_saida", "valor": [{"nome": "e", "entrada": None, "saida": None},
                                                          {"nome": "f", "entrada": 1, "saida": 1}]}]}]}
    assert "Ociosa" in b.render_bloco("fila", dados_do_papel("fila", [alvo]))


# --- 3. todo corte do consumo avisa, com a quantidade
def _apps(n):
    return [{"nome": f"app{i}", "papel": "app", "respostas": [
        {"pergunta": "app.cpu", "valor": 100 - i}]} for i in range(n)]


def test_corte_do_consumo_sem_corte_geral_avisa_a_quantidade():
    r = op.cortes({"achados": 1, "regras": 1, "sistemas": 1, "consumo": 14})
    assert r["baixos_em_contagem"] is False
    assert r["avisos"] == ["O consumo mostra só os 10 maiores de 14."]


def test_corte_do_consumo_com_corte_geral_avisa_a_quantidade():
    r = op.cortes({"achados": 204, "regras": 10, "sistemas": 5, "consumo": 9})
    assert "O consumo mostra só os 4 maiores de 9." in r["avisos"]


@pytest.mark.parametrize("contagem", [{"achados": 1, "regras": 1, "consumo": 10},
                                      {"achados": 204, "regras": 10, "consumo": 4}])
def test_consumo_que_cabe_inteiro_nao_avisa_corte(contagem):
    assert not any("consumo" in a for a in op.cortes(contagem)["avisos"])


def test_o_aviso_do_consumo_chega_a_pagina():
    r = relatorio()
    r["alvos"][0]["componentes"] = _apps(14)
    html = br.render_html_v3(r)
    assert '<p class="bl-aviso">O consumo mostra só os 10 maiores de 14.</p>' in html


# --- 4. recomendação com regra mostra porque e esforço
def test_recomendacao_alem_da_quinta_mantem_porque_e_esforco():
    r = relatorio()
    r["recomendacoes"] = [{"titulo": f"r{i}", "alvo": "cluster", "impacto": "alto"} for i in range(5)]
    r["recomendacoes"].append({"titulo": "sexta", "regra": "spof", "porque": "motivo-da-sexta",
                               "esforco": "esforco-da-sexta", "comando": "ls"})
    html = br.render_html_v3(r)
    assert "motivo-da-sexta" in html and "esforco-da-sexta" in html


def test_esforco_aparece_tambem_nas_primeiras():
    html = br._comandos([{"titulo": "t", "porque": "p", "esforco": "baixo"}])
    assert "esforço baixo" in html and "<p>p</p>" in html


def test_recomendacao_sem_porque_nem_esforco_nao_deixa_buraco():
    assert br._comandos([{"titulo": "t"}]) == "<h4>t</h4>"


# --- 5. opcional não tem limiar
def test_nenhuma_pergunta_opcional_tem_limiar():
    assert [p["id"] for p in perguntas.PERGUNTAS.values() if p["opcional"] and p["limiar"]] == []


def test_familia_que_responde_opcional_com_limiar_e_recusada(monkeypatch):
    monkeypatch.setitem(perguntas.PERGUNTAS, "fila.filas",
                        dict(perguntas.PERGUNTAS["fila.filas"], opcional=True))
    with pytest.raises(catalogo.CatalogoInvalido, match="opcional"):
        catalogo.familias()


# --- 6. texto do agente sai redigido
def _relatorio_com_segredo():
    url = f"https://admin:{SENHA}@exemplo.invalido/api"
    r = relatorio()
    r["resumo"] = f"Resumo citando {url}"
    r["fortes"], r["fracos"] = [f"Forte {url}"], [f"Fraco {url}"]
    r["recomendacoes"] = [
        {"titulo": f"Solta {url}", "porque": f"Porque {url}", "comando": COMANDO_COM_SENHA,
         "alvo": f"alvo {url}", "impacto": "alto", "esforco": f"esforço {url}"},
        {"titulo": f"Com regra {url}", "regra": "spof", "porque": f"Porque {url}",
         "comando": COMANDO_COM_SENHA, "esforco": url}]
    r["alvos"][0]["analise"] = f"Análise {url}"
    r["alvos"][0]["componentes"] = [{"nome": "obs", "papel": "observabilidade",
                                     "respostas": [], "analise": f"Análise do componente {url}"}]
    r["alvos"][0]["components_analysis"] = {"loja_web": f"Nota {url}"}
    r["alvos"][0]["fatos"] = {"stacks": [{"stack": "loja", "services": [{"name": "loja_web"}]}]}
    return r


def test_texto_do_agente_nao_leva_senha_ao_html():
    html = br.render_html_v3(_relatorio_com_segredo())
    assert SENHA not in html
    for campo in ("Resumo citando", "Forte", "Fraco", "Solta", "Porque", "Com regra",
                  "Análise do componente"):
        assert f"{campo} https://***@exemplo.invalido" in html, campo
    assert "curl https://***@exemplo.invalido/api" in html


def test_redigir_nao_trunca_o_texto_do_agente():
    r = relatorio()
    r["recomendacoes"][0]["comando"] = "x" * 300 + "-fim-do-comando"
    r["resumo"] = "y" * 300 + "-fim-do-resumo"
    html = br.render_html_v3(r)
    assert "-fim-do-comando" in html and "-fim-do-resumo" in html


def test_redigir_nao_altera_o_report_de_entrada():
    r = _relatorio_com_segredo()
    br.render_html_v3(r)
    assert r["recomendacoes"][0]["comando"] == COMANDO_COM_SENHA


@pdf_textual
def test_texto_do_agente_nao_leva_senha_ao_pdf(tmp_path):
    pdf = br.build(_relatorio_com_segredo(), str(tmp_path), formato="html+pdf")["pdf"]
    texto = subprocess.run(["pdftotext", pdf, "-"], check=True, capture_output=True, text=True).stdout
    assert SENHA not in texto and "***@exemplo.invalido" in texto


# --- 7. âncoras dos testes de mutação
def test_outras_recomendacoes_recebem_a_de_regra_que_o_corte_escondeu():
    baixo = {"regra": "regra_baixa", "severidade": "low"}
    alto = {"regra": "regra_alta", "severidade": "high"}
    corte = dict(op.SEM_CORTE, baixos_em_contagem=True)
    regras = br._regras_visiveis([baixo, alto], corte)
    na_capa = [{"titulo": f"capa {i}"} for i in range(5)]
    html = br._outras_recomendacoes([*na_capa, {"regra": "regra_baixa", "titulo": "escondida"},
                                     {"regra": "regra_alta", "titulo": "no-problema"},
                                     {"titulo": "solta"}], regras)
    assert "Outras recomendações" in html and "escondida" in html and "solta" in html
    assert "no-problema" not in html


def test_sem_corte_a_regra_baixa_fica_no_proprio_problema():
    regras = br._regras_visiveis([{"regra": "regra_baixa", "severidade": "low"}], dict(op.SEM_CORTE))
    assert regras == {"regra_baixa"}


def test_comandos_escapa_titulo_e_comando():
    html = br._comandos([{"titulo": "<b>t</b>", "comando": "echo '<script>'"}])
    assert "<script>" not in html and "<b>t</b>" not in html
    assert "&lt;script&gt;" in html


def test_comandos_escapa_porque_e_esforco():
    html = br._comandos([{"titulo": "t", "porque": "<i>p</i>", "esforco": "<u>e</u>"}])
    assert "<i>" not in html and "<u>" not in html
