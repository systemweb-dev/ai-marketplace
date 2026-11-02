"""Janela de acessos, top e orçamento são escolhidos a cada rodada, com padrão."""
import pytest

import build_report as br
import collect
from lib.adaptadores import logql
from lib.blocos import render_bloco
from lib.blocos.entrada import selecionar
from tests.fixtures.relatorio_grande import relatorio_grande


@pytest.mark.parametrize("janela, horas", [("6h", 6), ("48h", 48), ("2d", 48), ("24h", 24), (None, 24), ("x", 24)])
def test_horas_de_log_vem_da_janela(janela, horas):
    assert logql.horas_da_janela(janela) == horas


def test_top_escolhido_limita_a_tabela_de_sites():
    servicos = [{"nome": f"s{i:02}", "acessos": 100 - i, "erros": 0} for i in range(30)]
    assert len(selecionar(servicos, 20)) == 20
    assert len(selecionar(servicos)) == 15


def test_top_escolhido_chega_ao_corte_do_relatorio():
    from lib import orcamento_paginas as op
    assert op.cortes({"top": 20})["urls_geral"] == 20
    assert op.cortes({"top": 20, "achados": 204, "regras": 10})["urls_geral"] == 20
    assert op.cortes({})["urls_geral"] == 15


def test_entrada_recebe_o_top_do_corte():
    dados = br._dados_com_corte("entrada", [], {"urls_geral": 10})
    assert dados["top"] == 10


@pytest.mark.parametrize("flag, valor", [("--top", "3"), ("--janela-horas", "0"), ("--janela-horas", "999"), ("--orcamento", "5")])
def test_opcao_fora_da_faixa_para_com_codigo_2(tmp_path, flag, valor):
    assert collect.main(["--out", str(tmp_path), "--at", "2026-11-01T10:00:00Z", flag, valor]) == 2


def test_relatorio_sem_opcoes_continua_montando():
    assert "bl-capa" in br.render_html_v3(relatorio_grande())


def test_rotulo_diz_as_horas_lidas():
    janelas = [{"total": 6, "cobertas": [{}] * 6, "amostradas": 0, "amostra": False, "falhas": []}]
    item = {"nome": "a/b", "site": "a", "caminho": "/b", "acessos": 1, "erros": 0, "pct_5xx": 0, "p95_ms": 1}
    html = render_bloco("urls", {"geral": [item], "sites": [], "erros": [], "lentas": [item], "janelas": janelas})
    assert "últimas 6 horas" in html


@pytest.mark.parametrize("janela, top", [("90m", 15), ("abc", 15), ("0h", 15), (48, 15), ("8d", 15),
                                         ("24h", "10"), ("24h", -5), ("24h", True), ("24h", 51)])
def test_opcao_invalida_vinda_do_config_e_recusada(janela, top):
    assert collect.opcoes_invalidas(janela, top)


@pytest.mark.parametrize("janela, top", [("24h", 15), ("2d", 5), ("168h", 50)])
def test_opcao_valida_passa(janela, top):
    assert collect.opcoes_invalidas(janela, top) is None


@pytest.mark.parametrize("chave", ["customrequestheaders.Cookie", "customresponseheaders.X-Interno", "customrequestheaders.X-Internal-Auth"])
def test_valor_de_cabecalho_em_label_nao_sai(chave):
    from lib.redact import redact_labels
    label = f"traefik.http.middlewares.a.headers.{chave}"
    assert redact_labels({label: "s3nh4"}) == {label: "***"}


def test_conexao_ignora_proxy_do_ambiente():
    from lib import http_get
    proxies = [h for h in http_get._OPENER.handlers if type(h).__name__ == "ProxyHandler"]
    assert all(not h.proxies for h in proxies)


def test_dois_alvos_nao_somam_as_horas():
    janela = {"total": 24, "cobertas": [{}] * 24, "amostradas": 0, "amostra": False, "falhas": []}
    item = {"nome": "a/b", "site": "a", "caminho": "/b", "acessos": 1, "erros": 0, "pct_5xx": 0, "p95_ms": 1}
    html = render_bloco("urls", {"geral": [item], "sites": [], "erros": [], "lentas": [item], "janelas": [janela, janela]})
    assert "últimas 24 horas" in html


def test_top_maior_pesa_no_orcamento_de_paginas():
    from lib import orcamento_paginas as op
    dados = {"geral": [{}] * 60, "sites": [{}], "lentas": []}
    assert op.linhas_de_urls(dados, 50) - op.linhas_de_urls(dados) == 35


def test_corte_das_urls_avisa_mesmo_com_poucos_sites():
    from lib import orcamento_paginas as op
    r = op.cortes({"achados": 61, "regras": 10, "sistemas": 3, "urls_sites": 2})
    assert any("URLs" in a and "report.json" in a for a in r["avisos"])


def test_mesmo_loki_em_dois_alvos_nao_dobra():
    from lib.dados_blocos import dados_do_papel
    item = {"nome": "a/b", "site": "a", "acessos": 10, "erros": 0, "p95_ms": 1}
    resposta = {"pergunta": "entrada.urls_mais_acessadas", "valor": [item], "sites": [{"site": "a", "acessos": 10}],
                "janelas": {"total": 1, "cobertas": [], "amostradas": 0, "amostra": False}}
    alvos = [{"nome": n, "componentes": [{"papel": "entrada", "respostas": [resposta]}]} for n in "xy"]
    dados = dados_do_papel("urls", alvos)
    assert len(dados["geral"]) == 1 and dados["sites"][0]["acessos"] == 10


def test_rotulo_que_junta_stacks_soma_cpu_e_memoria():
    from lib.capa import _medidas_do_sistema
    servicos = [("online", "1/1", "a"), ("online", "1/1", "b")]
    medidas = {"a": {"cpu": 100, "memoria": 5, "disponivel": 99, "resposta": 10},
               "b": {"cpu": 300, "disponivel": 90, "resposta": 40}}
    assert _medidas_do_sistema(servicos, medidas) == {"cpu": 400, "memoria": 5, "disponivel": 90, "resposta": 40}


def test_report_antigo_sem_nota_recalcula_em_vez_de_dizer_que_nada_foi_medido():
    r = relatorio_grande()
    r.pop("nota_geral", None)
    assert "nenhum serviço foi medido" not in br.render_html_v3(r)
