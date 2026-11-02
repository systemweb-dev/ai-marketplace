import re

import pytest

from lib.alvos import OPCIONAIS
from lib.capa import VEREDITOS, render_capa, saude_por_sistema

NOTA = {"valor": 79, "faixa": "atencao", "parcial": False, "online": 64, "base": 67,
        "teto": 79, "parcelas": {}}


def ctx():
    return {"recomendacoes": [{"titulo": "Religar a fila", "porque": "avisos parados", "impacto": "alto"}],
            "historico": {"novos": ["c · r · a"], "resolvidos": ["c · r · b", "c · r · d"], "nota_anterior": 71},
            "tendencias": {"disco": [80.0, 91.0]},
            "certificados": [{"nome": "loja", "dias": 12}]}


def test_capa_tem_tudo_o_que_o_spec_pede():
    html = render_capa(ctx(), NOTA, "<p>Resumo.</p>", ["bancos"])
    for esperado in (">79<", ">64<", VEREDITOS["atencao"], "Resumo.", "Religar a fila",
                     "2 resolvidos", "1 novo", "nota 71 → 79", "polyline", "91%", "12 dias", "Não medido", "bancos"):
        assert esperado in html


def test_sem_nota_a_capa_diz_que_nao_mediu():
    assert "Não medido" in render_capa({}, None, "", [])


def test_sem_nota_a_capa_nao_engole_prioridades_nem_o_que_mudou():
    html = render_capa(ctx(), None, "<p>Resumo.</p>", ["bancos"])
    for esperado in ("Resumo.", "Religar a fila", "2 resolvidos", "12 dias", "bancos"):
        assert esperado in html
    assert "nota 71" not in html


def test_o_anel_desenha_a_fracao_da_nota():
    html = render_capa({}, NOTA, "", [])
    assert 'aria-label="Nota 79 de 100"' in html and 'stroke-dasharray="228.3 289.0"' in html
    assert "Atenção" in html and "limitada a 79" in html


def test_nota_abaixo_do_teto_nao_se_diz_limitada():
    assert "limitada" not in render_capa({}, {**NOTA, "valor": 50, "faixa": "critico", "teto": 79}, "", [])


def test_veredito_critico_nao_afirma_uma_causa_que_a_nota_nao_garante():
    assert VEREDITOS["critico"] == "Há falha grave que exige ação agora."
    html = render_capa({}, {**NOTA, "valor": 40, "faixa": "critico", "teto": 59}, "", [])
    assert "Há falha grave que exige ação agora." in html and "Há serviço fora do ar" not in html


def test_nota_parcial_se_declara():
    assert "(parcial)" in render_capa({}, {**NOTA, "parcial": True}, "", [])


def test_a_barra_de_online_mostra_online_e_fora():
    html = render_capa({}, NOTA, "", [])
    assert '<i style="flex:64"></i><u style="flex:3"></u>' in html
    assert "de 67 serviços online" in html
    assert "<u " not in render_capa({}, {**NOTA, "online": 67}, "", [])


def alvo_com_fora():
    return {"nome": "cluster", "tipo": "docker", "fatos": {"services": [
        {"name": "b_worker", "replicas": "0/1"}, {"name": "a_worker", "replicas": "0/1"},
        {"name": "c_aceito", "replicas": "0/1"}, {"name": "d_web", "replicas": "1/1"}]}}


def test_a_capa_nomeia_quem_esta_fora_e_respeita_o_aceite():
    html = render_capa({"alvos": [alvo_com_fora()],
                        "aceites": [{"alvo": "cluster", "regra": "OPS_SERVICE_STOPPED", "objeto": "c_aceito"}]},
                       NOTA, "", [])
    assert "Fora: a_worker, b_worker" in html and "c_aceito" not in html


def test_endpoint_fora_do_ar_tambem_e_nomeado():
    alvo = {"nome": "site", "tipo": "http", "fatos": {"codigo": 503}}
    assert "Fora: site" in render_capa({"alvos": [alvo], "aceites": []}, NOTA, "", [])


def test_lista_de_fora_nao_estoura_a_faixa():
    servicos = [{"name": f"s{i:02}", "replicas": "0/1"} for i in range(9)]
    html = render_capa({"alvos": [{"nome": "c", "fatos": {"services": servicos}}]}, NOTA, "", [])
    assert "s04" in html and "s05" not in html and "e mais 4" in html


def test_linha_de_contexto_tem_alvo_data_e_comparacao():
    html = render_capa({"gerado_em": "2026-10-26T10:00:00Z", "alvos": [{"nome": "Aurora"}, {"nome": "x", "coletado": False}],
                        "historico": {"vs": "2026-10-23T1000", "novos": [], "resolvidos": []}}, NOTA, "", [])
    assert "Aurora · Auditoria de 26/10/2026 · comparada com 23/10" in html
    assert "Desde 23/10" in html and '"x"' not in html


def test_tendencias_seguem_a_ordem_e_os_nomes_do_mockup():
    html = render_capa({"tendencias": {"disco": [1.0, 91.0], "erros": [1.0, 0.4], "resposta": [9.0, 612.0],
                                       "cpu": [2.0, 41.0], "memoria": [3.0, 78.0]}}, NOTA, "", [])
    posicoes = [html.index(n) for n in ("Erros nos sites", "Tempo de resposta", "CPU das máquinas", "Memória", "Disco")]
    assert posicoes == sorted(posicoes)
    assert "0,4%" in html and "612 ms" in html
    assert re.search(r'class="bl-met bl-c-crit"><span>Disco', html)
    assert re.search(r'class="bl-met bl-c-warn"><span>Memória', html)
    assert re.search(r'class="bl-met bl-c-ok"><span>CPU', html)


def test_singular_de_resolvido():
    assert "1 resolvido<" in render_capa({"historico": {"resolvidos": ["a"], "novos": []}}, NOTA, "", [])


def test_aviso_do_historico_nao_some():
    html = render_capa({"historico": {"resolvidos": [], "novos": [], "aviso": "formato anterior"}}, NOTA, "", [])
    assert "formato anterior" in html


def test_certificado_mais_perto_de_vencer_nao_fica_de_fora():
    certs = [{"nome": f"c{i}", "dias": 50 + i} for i in range(4)] + [{"nome": "urgente", "dias": 2}]
    html = render_capa({"certificados": certs}, NOTA, "", [])
    assert html.index("urgente") < html.index("c0") and "c3" not in html and "e mais 2" in html


def test_certificado_vencido_e_sem_dado():
    html = render_capa({"certificados": [{"nome": "a", "dias": -3}, {"nome": "b", "dias": None}]}, NOTA, "", [])
    assert "vencido" in html and "sem dado" in html and "-3 dias" not in html


def test_prioridades_tem_nivel_e_avisam_do_excedente():
    recs = [{"titulo": f"r{i}", "porque": "p", "impacto": "médio", "alvo": "cluster"} for i in range(7)]
    html = render_capa({"recomendacoes": recs}, NOTA, "", [])
    assert "r4" in html and "r5" not in html and "e mais 2" in html
    assert 'class="bl-nivel bl-nivel-warn">Médio<' in html and "cluster" in html


def test_texto_do_coletor_e_escapado():
    html = render_capa({"certificados": [{"nome": "<x>", "dias": 1}],
                        "recomendacoes": [{"titulo": "<y>", "porque": "<z>", "impacto": "<w>"}]},
                       NOTA, "", ["<k>"])
    assert not re.search(r"<(x|y|z|w|k)>", html)


def test_comparar_guarda_a_nota_anterior():
    from lib.historico import comparar
    base = {"schema_version": 3, "alvos": []}
    assert comparar({**base, "nota_geral": {"valor": 71}}, base, "a")["nota_anterior"] == 71
    assert comparar({**base, "nota_geral": None}, base, "a")["nota_anterior"] is None
    assert comparar(base, base, "a")["nota_anterior"] is None


def alvo_sis():
    return {"nome": "c", "rotulos": {"loja": "Loja virtual"}, "fatos": {"services": [
        {"name": "loja_api", "replicas": "2/2"}, {"name": "loja_web", "replicas": "1/2"},
        {"name": "fila_mq", "replicas": "1/1"}]}}


def test_estado_do_sistema_e_o_pior_dos_servicos_e_usa_o_rotulo():
    html = saude_por_sistema([alvo_sis()], [])
    assert "Loja virtual" in html and "Parcial" in html and "3/4" in html


def test_resposta_e_disponivel_aparecem_ou_ficam_sem_dado():
    html = saude_por_sistema([alvo_sis()], [], medidas={"loja": {"disponivel": 99.5}})
    assert "Disponível (7 dias)" in html and "99.5%" in html and "sem dado" in html


def test_juntar_online_resume_os_saudaveis():
    html = saude_por_sistema([alvo_sis()], [], juntar_online=True)
    assert "fila" not in html and "1 sistema online" in html


def test_rotulos_e_campo_aceito_no_alvo():
    assert "rotulos" in OPCIONAIS["docker"]


def test_estado_tem_ponto_colorido_e_numero_alinhado():
    html = saude_por_sistema([alvo_sis()], [])
    assert '<i class="bl-pt bl-fl-warn"></i><b>Loja virtual</b>' in html
    assert '<b class="bl-c-warn">Parcial</b>' in html
    assert '<td class="bl-d">3/4</td>' in html


def test_cpu_e_em_nucleos_sem_barra_nem_vermelho_e_ausencia_vira_sem_dado():
    html = saude_por_sistema([alvo_sis()], [], medidas={"loja": {"cpu": 250, "memoria": None}})
    corpo = html.split("<tbody>")[1]
    assert '<td class="bl-e">2,5 cores</td>' in corpo
    assert "bl-bar" not in corpo and "250%" not in corpo and "bl-fl-crit" not in corpo
    assert ">Memória<" in html and html.count('<td class="bl-e"><span class="bl-sd">sem dado') >= 3


def test_replicas_somam_por_sistema_em_vez_de_listar_cada_servico():
    alvo = {"nome": "c", "fatos": {"services": [
        {"name": f"loja_s{i}", "replicas": "3/3"} for i in range(3)]}}
    html = saude_por_sistema([alvo], [])
    assert '<td class="bl-d">9/9</td>' in html and "3/3" not in html


def test_servico_parado_de_proposito_nao_falta_na_soma_de_replicas():
    alvo = {"nome": "c", "fatos": {"services": [
        {"name": "loja_api", "replicas": "2/2"},
        {"name": "loja_seed", "replicas": "0/1 (1/1 completed)", "mode": "replicated-job"},
        {"name": "fila_seed", "replicas": "0/1", "mode": "replicated-job"}]}}
    html = saude_por_sistema([alvo], [])
    assert '<td class="bl-d">2/2</td>' in html and '<td class="bl-d">0/1</td>' in html


def test_replica_ilegivel_nao_entra_na_soma_e_o_estado_acusa():
    alvo = {"nome": "c", "fatos": {"services": [{"name": "loja_api", "replicas": "2/2"},
                                                {"name": "loja_web", "replicas": None}]}}
    html = saude_por_sistema([alvo], [])
    assert '<td class="bl-d">2/2</td>' in html and "Sem dado" in html


def test_replicas_desconhecidas_viram_sem_dado_e_nao_none():
    alvo = {"nome": "c", "fatos": {"services": [{"name": "x_a", "replicas": None}]}}
    html = saude_por_sistema([alvo], [])
    assert "None" not in html and '<td class="bl-d"><span class="bl-sd">sem dado</span></td>' in html


def test_sem_servico_medido_nao_sai_tabela_vazia():
    assert "Não medido" in saude_por_sistema([{"nome": "h", "tipo": "http", "fatos": {}}], [])


@pytest.mark.parametrize("id_, legivel", [
    ("OPS_TASK_FAILING", "Tasks falhando"),
    ("SEC_DOCKER_SOCK_EXPECTED", "docker.sock em ferramenta que precisa dele"),
    ("fila_sem_consumidor", "Fila com mensagem presa e nenhum consumidor"),
    ("OPS_REGRA_NOVA", "Regra nova"),
])
def test_prioridade_mostra_o_nome_da_regra_e_nunca_o_id(id_, legivel):
    html = render_capa({"recomendacoes": [{"titulo": id_, "porque": f"ver {id_}", "impacto": "alto"}]}, NOTA, "", [])
    assert f"<b>{legivel}</b>" in html and f"ver {legivel}" in html and id_ not in html


def test_id_no_meio_da_frase_tambem_sai():
    html = render_capa({"recomendacoes": [{"titulo": "Corrigir OPS_TASK_FAILING em c", "porque": "p"}]}, NOTA, "", [])
    assert "Corrigir Tasks falhando em c" in html


def test_titulo_comum_passa_intacto_e_ausente_nao_vira_none():
    html = render_capa({"recomendacoes": [{"titulo": "Religar a fila sem_tls_x", "porque": None}]}, NOTA, "", [])
    assert "Religar a fila sem_tls_x" in html and "None" not in html


def test_o_que_mudou_tambem_nao_expoe_o_id():
    h = {"novos": ["c · loja · OPS_TASK_FAILING · api"], "resolvidos": ["c · sem_tls · site"]}
    html = render_capa({"historico": h}, NOTA, "", [])
    assert "c · loja · Tasks falhando · api" in html and "c · Endpoint público servido sem TLS · site" in html
    assert "OPS_TASK_FAILING" not in html and "sem_tls" not in html


def test_tendencia_nao_medida_fica_no_cartao():
    html = render_capa({"tendencias": {"disco": [1.0, 91.0], "cpu": None}}, NOTA, "", [])
    assert re.search(r'<div class="bl-met"><span>CPU das máquinas</span><b>não medido</b></div>', html)
    assert "91%" in html


def test_nota_boa_com_alerta_nao_diz_tudo_em_ordem():
    nota = dict(NOTA, valor=88, faixa="bom", com_alerta=2)
    html = render_capa({}, nota, "", [])
    assert "Tudo em ordem" not in html and "alertas para acompanhar" in html
