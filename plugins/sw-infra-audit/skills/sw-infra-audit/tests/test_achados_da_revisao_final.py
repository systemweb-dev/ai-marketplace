"""Achados da revisão final do relatório simples: cada um travado por teste."""
import pathlib

import build_report as br
from lib import html_comum, orcamento_paginas as op, triagem
from lib.blocos.maquinas import _linha_do_no
from lib.capa import saude_por_sistema
from lib.dados_blocos import medidas_por_stack
from tests.test_build_report_v3 import relatorio

SKILL = pathlib.Path(__file__).resolve().parents[1] / "SKILL.md"


def achado(regra, severidade, **extra):
    return {"regra": regra, "severidade": severidade, "objeto": "o", "alvo": "c", **extra}


def _ordem_das_regras(html, regras):
    return sorted(regras, key=lambda r: html.index(f'regra">{r}<'))


# --- 2. gravidade antes da contagem
def test_problemas_vem_por_gravidade_depois_contagem_e_nome():
    achados = ([achado("r_medio", "medium")] * 4 + [achado("r_alto_b", "high")] * 2
               + [achado("r_alto_a", "high")] * 2 + [achado("r_alto_c", "high")] * 3
               + [achado("r_critico", "critical")] + [achado("r_baixo", "low")] * 5)
    html = br._problemas(achados, [], op.cortes({}))
    assert _ordem_das_regras(html, ["r_baixo", "r_medio", "r_alto_b", "r_alto_a", "r_alto_c", "r_critico"]) == [
        "r_critico", "r_alto_c", "r_alto_a", "r_alto_b", "r_medio", "r_baixo"]


def test_regra_com_gravidades_mistas_ordena_pela_pior():
    achados = [achado("r_mista", "low"), achado("r_mista", "critical"), achado("r_alta", "high")]
    html = br._problemas(achados, [], op.cortes({}))
    assert _ordem_das_regras(html, ["r_alta", "r_mista"]) == ["r_mista", "r_alta"]


# --- 3. esperado não é problema
def _so_esperados():
    r = relatorio()
    r["recomendacoes"] = []
    r["alvos"][0]["achados"] = [achado("SEC_DOCKER_SOCK_EXPECTED", "low"),
                                achado("r_normal", "low", esperada=True)]
    return r


def test_problemas_exclui_achado_esperado_pelos_dois_caminhos():
    achados = _so_esperados()["alvos"][0]["achados"]
    assert br._problemas(achados, [], op.cortes({})) == ""
    assert br._regras_visiveis(achados, op.cortes({})) == set()


def test_cluster_saudavel_volta_a_dizer_que_nao_ha_problema():
    html = br.render_html_v3(_so_esperados())
    parte = html.split('id="problemas"', 1)[1].split('id="registro"', 1)[0]
    assert "Nenhum problema nesta rodada." in parte
    assert "2 achados esperados" in parte and "bl-prob" not in parte


def test_contagem_de_esperados_nao_aparece_sem_esperados():
    r = relatorio()
    html = br.render_html_v3(r)
    assert "esperado" not in html.split('id="problemas"', 1)[1].split('id="registro"', 1)[0]


def test_achado_esperado_nao_gasta_o_orcamento_de_paginas():
    r = _so_esperados()
    r["alvos"][0]["achados"] = [achado("r_normal", "low", esperada=True, objeto=str(i)) for i in range(100)]
    assert "Achados de baixa gravidade aparecem só em contagem." not in br.render_html_v3(r)


# --- 4. alvo inteiro só quando não trouxe fatos
def test_lacuna_parcial_cita_a_categoria_e_nao_o_alvo():
    alvo = {"nome": "cluster", "fatos": {"services": [{"name": "a_b"}]},
            "nao_coletado": [{"motivo": "métricas: o alvo não declara `metricas_url`"},
                             {"motivo": "tasks de a_b: indisponível"},
                             {"motivo": "tasks por nó/serviço: indisponível"}]}
    assert br._faltou([alvo]) == ["métricas", "tarefas"]


def test_lacuna_desconhecida_nao_cita_o_alvo_nem_some():
    alvo = {"nome": "cluster", "fatos": {"services": [{"name": "a_b"}]}, "nao_coletado": [{"motivo": "algo novo"}]}
    assert br._faltou([alvo]) == ["outros dados"]


def test_alvo_so_com_marcadores_de_nao_coletado_nao_trouxe_fatos():
    http = {"nome": "site", "fatos": {"certificado": {"valor": None, "motivo": "não li"}},
            "nao_coletado": [{"motivo": "não consegui alcançar site"}]}
    docker = {"nome": "ctx", "fatos": {"services": {"status": "n/a"}}, "nao_coletado": [{"motivo": "docker info: x"}]}
    assert br._faltou([http, docker]) == ["ctx", "site"]


# --- 5. um escape só
def test_no_escapa_uma_vez():
    linha = _linha_do_no({"nome": "a&b", "estado": "x&y", "engine": "1<2", "tarefas": 1})
    assert "a&amp;b" in linha and "x&amp;y" in linha and "1&lt;2" in linha and "&amp;amp;" not in linha
    assert "&amp;lt;" not in linha


# --- 6. fora da rodada aparece só em "Fora desta rodada"
def test_alvo_nao_coletado_sai_da_lista_de_alvos_e_do_titulo():
    r = relatorio()
    r["alvos"][1]["coletado"] = False
    html = br.render_html_v3(r)
    assert "Fora desta rodada: site" in html
    assert "<title>Auditoria de infraestrutura — 1 alvo" in html
    assert 'class="nome">site' not in html and 'class="nome">cluster' in html


# --- 7. sistemas de alvos diferentes não se fundem
def _app(nome, cpu):
    return {"nome": nome, "papel": "app", "respostas": [{"pergunta": "app.cpu", "valor": cpu}]}


def _dois_clusters():
    return [{"nome": "c1", "fatos": {"services": [{"name": "loja_api", "replicas": "2/2"}]},
             "rotulos": {"loja": "Loja virtual"}, "componentes": [_app("loja_api", 100)]},
            {"nome": "c2", "fatos": {"services": [{"name": "loja_api", "replicas": "0/1"}]},
             "componentes": [_app("loja_api", 300)]}]


def test_mesma_stack_em_dois_alvos_sao_dois_sistemas():
    alvos = _dois_clusters()
    html = saude_por_sistema(alvos, [], medidas=medidas_por_stack(alvos))
    assert "c1 · Loja virtual" in html and "c2 · loja" in html and "2 sistemas" in html
    assert "1 core" in html.split("c1 · Loja virtual")[1].split("</tr>")[0]
    assert "3 cores" in html.split("c2 · loja")[1].split("</tr>")[0]


def test_medidas_de_dois_alvos_ficam_separadas():
    assert medidas_por_stack(_dois_clusters()) == {"c1 · loja": {"cpu": 100}, "c2 · loja": {"cpu": 300}}


def test_um_alvo_so_nao_ganha_prefixo():
    alvos = _dois_clusters()[:1]
    assert "c1 ·" not in saude_por_sistema(alvos, [], medidas=medidas_por_stack(alvos))
    assert medidas_por_stack(alvos) == {"loja": {"cpu": 100}}


def test_alvo_fora_da_rodada_nao_conta_para_o_prefixo():
    alvos = _dois_clusters()[:1] + [{"nome": "c2", "coletado": False, "fatos": {}}]
    assert "c1 ·" not in saude_por_sistema(alvos, [])
    assert medidas_por_stack(alvos) == {"loja": {"cpu": 100}}


def test_rodada_so_de_endpoints_lista_os_endpoints():
    alvos = [{"nome": "api", "tipo": "http", "fatos": {"codigo": 200}},
             {"nome": "site", "tipo": "http", "fatos": {"codigo": 503}},
             {"nome": "novo", "tipo": "http", "fatos": {}},
             {"nome": "fora", "tipo": "http", "coletado": False, "fatos": {"codigo": 200}}]
    html = saude_por_sistema(alvos, [])
    assert "nenhum sistema" not in html and "3 endpoints" in html
    assert ">api<" in html and ">site<" in html and ">novo<" in html and ">fora<" not in html
    assert "Online" in html.split(">api<")[1].split("</tr>")[0]
    assert "Fora do ar" in html.split(">site<")[1].split("</tr>")[0]
    assert "Sem dado" in html.split(">novo<")[1].split("</tr>")[0]


def test_endpoint_junto_de_cluster_nao_vira_sistema():
    alvos = _dois_clusters()[:1] + [{"nome": "api", "tipo": "http", "fatos": {"codigo": 200}}]
    assert ">api<" not in saude_por_sistema(alvos, [])


# --- 8. código órfão
def test_triagem_guarda_so_a_ordem_de_severidade():
    assert triagem.ORDEM_SEVERIDADE[:2] == ("critical", "high")
    for orfao in ("triar", "cascata", "FAIXAS"):
        assert not hasattr(triagem, orfao)


def test_tons_saiu_de_html_comum():
    assert not hasattr(html_comum, "TONS")


# --- 9. a descrição fala do relatório atual
def test_descricao_da_skill_fala_do_relatorio_novo():
    frontmatter = SKILL.read_text(encoding="utf-8").split("---", 2)[1]
    descricao = " ".join(frontmatter.split())
    assert "POR AÇÃO" not in descricao
    assert "nota geral, problemas agrupados, blocos por tipo de sistema" in descricao
