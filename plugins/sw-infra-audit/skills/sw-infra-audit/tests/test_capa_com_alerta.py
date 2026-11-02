"""A capa diz quem pede atenção e explica a nota com fatos da rodada."""
import re

from lib.capa import render_capa
from lib.nota import nota_geral

PRATICAS = {"disponibilidade": {"ha_pct": 30}, "seguranca": {"high": 0, "med": 78},
            "higiene": {"pinned_pct": 40, "nonroot_pct": 40, "limits_pct": 40, "healthcheck_pct": 40}}


def alvo(servicos, dimensoes=None, achados=()):
    return {"nome": "c", "tipo": "docker", "coletado": True, "achados": list(achados),
            "fatos": {"services": servicos}, "dimensoes": PRATICAS if dimensoes is None else dimensoes}


def ok(n):
    return {"name": f"loja_ok{n}", "replicas": "1/1"}


def capa(a, aceites=()):
    nota = nota_geral([a], list(aceites))
    return render_capa({"alvos": [a], "aceites": list(aceites)}, nota, "", [])


def texto_do_porque(html):
    casou = re.search(r'<p class="bl-porque">(.*?)</p>', html)
    return re.sub(r"<[^>]+>", "", casou.group(1)) if casou else None


def test_com_alerta_aparece_em_amarelo_e_a_barra_separa_as_cores():
    a = alvo([ok(1), ok(2), {"name": "loja_api", "replicas": "2/2", "tasks_failed": 3},
              {"name": "loja_fila", "replicas": "1/2"}, {"name": "loja_web", "replicas": "0/1"}])
    html = capa(a)
    assert '<em class="bl-hal">1 com alerta</em>' in html
    assert ('<i style="flex:2"></i><s style="flex:2"></s><u style="flex:1"></u>') in html


def test_sem_alerta_nao_ha_aviso_amarelo():
    html = capa(alvo([ok(1)]))
    assert "bl-hal" not in html and "<s " not in html


def test_cita_nomes_curtos_por_ordem_de_gravidade():
    a = alvo([ok(1), {"name": "loja_api", "replicas": "2/2", "tasks_failed": 3},
              {"name": "loja_fila", "replicas": "1/2"}, {"name": "loja_web", "replicas": "0/1"}])
    assert "<small>Fora: web. Parcial: fila. Com alerta: api</small>" in capa(a)


def test_nome_repetido_entre_stacks_fica_inteiro():
    a = alvo([{"name": "a_api", "replicas": "0/1"}, {"name": "b_api", "replicas": "0/1"}])
    assert "Fora: a_api, b_api" in capa(a)


def test_limite_de_cinco_nomes_no_total_e_o_resto_contado():
    fora = [{"name": f"s_f{i}", "replicas": "0/1"} for i in range(3)]
    parciais = [{"name": f"s_p{i}", "replicas": "1/2"} for i in range(4)]
    alertas = [{"name": f"s_a{i}", "replicas": "1/1", "tasks_failed": 1} for i in range(2)]
    html = capa(alvo(fora + parciais + alertas))
    assert "Fora: f0, f1, f2. Parcial: p0, p1 e mais 2. Com alerta: 2" in html


def test_por_que_esta_nota_com_tudo_online():
    servicos = [ok(i) for i in range(12)]
    assert texto_do_porque(capa(alvo(servicos))) == (
        "Por que esta nota: Serviços: 12 de 12 online. Redundância baixa: 30%. Boas práticas: 31%.")


def test_por_que_cita_alerta_sem_inventar_teto():
    a = alvo([ok(1), {"name": "s_api", "replicas": "1/1", "tasks_failed": 1}])
    frase = texto_do_porque(capa(a))
    assert "Serviços: 2 de 2 online, 1 com alerta." in frase and "limitada" not in frase


def test_por_que_diz_o_teto_e_a_causa_com_nomes():
    bom = {"disponibilidade": {"ha_pct": 100}, "seguranca": {"high": 0, "med": 0},
           "higiene": {"pinned_pct": 100, "nonroot_pct": 100, "limits_pct": 100, "healthcheck_pct": 100}}
    servicos = [ok(i) for i in range(30)] + [{"name": "s_web", "replicas": "0/1"}]
    frase = texto_do_porque(capa(alvo(servicos, bom)))
    assert "Serviços: 30 de 31 online." in frase
    assert "Redundância boa: 100%." in frase
    assert "Nota limitada a 59: 1 serviço fora do ar (web)." in frase


def test_por_que_do_teto_de_79_cita_parcial_e_problema_alto():
    bom = {"disponibilidade": {"ha_pct": 100}, "seguranca": {"high": 0, "med": 0},
           "higiene": {"pinned_pct": 100, "nonroot_pct": 100, "limits_pct": 100, "healthcheck_pct": 100}}
    servicos = [ok(i) for i in range(30)] + [{"name": "s_web", "replicas": "1/2"}]
    achados = [{"regra": "OPS_NODE_DOWN", "severidade": "high"}]
    frase = texto_do_porque(capa(alvo(servicos, bom, achados)))
    assert "Nota limitada a 79: 1 serviço parcial (web) e 1 problema alto (" in frase
    assert "OPS_NODE_DOWN" not in frase


def test_por_que_cita_no_fora_e_nao_mistura_causa_do_teto_mais_alto():
    d = {"disponibilidade": {"ha_pct": 100}, "seguranca": {"high": 0, "med": 0}, "operacao": {"nodes_down": 2},
         "higiene": {"pinned_pct": 100, "nonroot_pct": 100, "limits_pct": 100, "healthcheck_pct": 100}}
    frase = texto_do_porque(capa(alvo([ok(1), {"name": "s_web", "replicas": "1/2"}], d)))
    assert "Nota limitada a 59: 2 nós fora do ar." in frase and "parcial" not in frase


def test_nota_abaixo_do_teto_nao_diz_limitada():
    a = alvo([{"name": "s_a", "replicas": "0/1"}, {"name": "s_b", "replicas": "0/1"}])
    assert "limitada" not in texto_do_porque(capa(a))


def test_parcela_nao_medida_e_dita():
    assert texto_do_porque(capa(alvo([ok(1)], {}))) == (
        "Por que esta nota: Serviços: 1 de 1 online. Redundância não medida. Boas práticas não medidas.")


def test_redundancia_media():
    d = dict(PRATICAS, disponibilidade={"ha_pct": 70})
    assert "Redundância média: 70%." in texto_do_porque(capa(alvo([ok(1)], d)))


def test_nome_de_servico_e_escapado():
    a = alvo([{"name": "s_<b>", "replicas": "0/1"}])
    assert "<b>" not in texto_do_porque(capa(a)).replace("&lt;", "") and "s_<b>" not in capa(a)


def test_endpoint_fora_aparece_na_explicacao():
    http = {"nome": "site", "tipo": "http", "coletado": True, "fatos": {"codigo": 503}, "dimensoes": {},
            "achados": []}
    a = alvo([ok(i) for i in range(30)], {"disponibilidade": {"ha_pct": 100}})
    nota = nota_geral([a, http], [])
    frase = texto_do_porque(render_capa({"alvos": [a, http], "aceites": []}, nota, "", []))
    assert "1 serviço fora do ar (site)" in frase


def test_sem_instavel_na_capa():
    from lib import capa as modulo
    assert "instavel" not in modulo.ROTULO_ESTADO and "instavel" not in modulo.TOM_ESTADO
    assert "instavel" not in modulo.ORDEM_ESTADO
