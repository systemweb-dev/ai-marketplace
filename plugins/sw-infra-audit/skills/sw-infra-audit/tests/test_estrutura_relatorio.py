import build_report as br
from tests.test_build_report_v3 import relatorio


def dados():
    r = relatorio()
    r["nota_geral"] = {"valor": 79, "faixa": "atencao", "parcial": False, "online": 1, "base": 1,
                       "teto": 79, "parcelas": {}}
    return r


def test_as_cinco_partes_aparecem_na_ordem():
    html = br.render_html_v3(dados())
    ids = ["bl-capa", "saude-por-sistema", "detalhes-tecnicos", "problemas", "registro"]
    posicoes = [html.index(f'id="{i}"') for i in ids]
    assert posicoes == sorted(posicoes)


def test_seccoes_antigas_sairam():
    html = br.render_html_v3(dados())
    for fora in ("Agir agora", "Redes, secrets e configs", "Instrumentos", "Topologia"):
        assert fora not in html


def test_toda_recomendacao_aparece_mesmo_sem_regra_correspondente():
    r = dados()
    r["recomendacoes"] = [{"alvo": "cluster", "titulo": "Sem regra", "comando": "ls"},
                          {"alvo": "cluster", "titulo": "Com regra", "regra": "spof", "comando": "pwd"}]
    html = br.render_html_v3(r)
    assert "Sem regra" in html and "Outras recomendações" in html and "pwd" in html


def test_alvo_fora_da_rodada_vira_uma_linha_com_os_nomes():
    r = dados()
    r["alvos"][1]["coletado"] = False
    html = br.render_html_v3(r)
    assert "Fora desta rodada: site" in html and html.count("alvo não confirmado") == 0


def test_riscos_aceitos_e_o_que_falta_declarar_ficam():
    html = br.render_html_v3(dados())
    assert "Riscos aceitos" in html and "O que falta declarar" in html


def test_pontos_ficam_depois_da_saude_e_antes_dos_detalhes():
    html = br.render_html_v3(dados())
    assert html.index('id="saude-por-sistema"') < html.index("TLS em dia") < html.index('id="detalhes-tecnicos"')
    assert html.index("Traefik sem redundância") < html.index('id="detalhes-tecnicos"')


def test_fortes_e_fracos_escapam_html_e_traduzem_id_de_regra():
    r = dados()
    r["fortes"], r["fracos"] = ["<b>solto</b>"], ["Ver SEC_USER_ROOT"]
    html = br.render_html_v3(r)
    assert "&lt;b&gt;solto&lt;/b&gt;" in html and "Ver SEC_USER_ROOT" not in html


def test_painel_duplo_agrupa_banco_cache_consumo_e_falhas():
    html = br.render_html_v3(dados())
    par = html[html.index('<div class="bl-par">'):]
    assert par.index("Bancos de dados") < par.index("Cache") < par.index("Maiores consumidores") \
        < par.index("Pontos únicos de falha")


def test_medidas_por_stack_somam_cpu_e_memoria_e_o_que_falta_fica_de_fora():
    from lib.dados_blocos import medidas_por_stack

    def app(nome, *respostas):
        return {"nome": nome, "papel": "app", "respostas": [{"pergunta": p, "valor": v} for p, v in respostas]}
    alvos = [{"componentes": [app("loja_api", ("app.cpu", 30), ("app.memoria", 1024)),
                              app("loja_web", ("app.cpu", 0)),
                              app("fila_mq", ("app.memoria", 2048))]}]
    assert medidas_por_stack(alvos) == {"loja": {"cpu": 30, "memoria": 1024}, "fila": {"memoria": 2048}}


def test_disponibilidade_do_sistema_e_a_do_pior_servico():
    from lib.dados_blocos import medidas_por_stack

    def app(nome, valor):
        return {"nome": nome, "papel": "app",
                "respostas": [{"pergunta": "app.disponibilidade_7d", "valor": valor}]}
    alvos = [{"componentes": [app("loja_api", 99.5), app("loja_web", 80)]}]
    assert medidas_por_stack(alvos) == {"loja": {"disponivel": 80}}


def test_memoria_em_bytes_nao_vira_percentual_na_saude():
    from lib.capa import saude_por_sistema
    alvo = {"nome": "c", "fatos": {"services": [{"name": "loja_api", "replicas": "1/1"}]}}
    html = saude_por_sistema([alvo], [], medidas={"loja": {"memoria": 2 * 1024 ** 3}})
    assert "2 GB" in html and "%" not in html.replace('width:', '').split("<tbody>")[1]


def test_regra_com_achado_alto_nao_some_na_contagem_dos_baixos():
    corte = dict(br_op().SEM_CORTE, baixos_em_contagem=True)
    achados = [{"regra": "x", "severidade": "low", "objeto": "a"}, {"regra": "x", "severidade": "high", "objeto": "b"}]
    assert br._regras_visiveis(achados, corte) == {"x"} and "bl-prob" in br._problemas(achados, [], corte)


def br_op():
    from lib import orcamento_paginas
    return orcamento_paginas
