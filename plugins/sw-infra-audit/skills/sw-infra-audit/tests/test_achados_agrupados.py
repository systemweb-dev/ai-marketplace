# tests/test_achados_agrupados.py
"""O relatório com volume de verdade.

Uma auditoria real trouxe 213 achados: 75 da MESMA regra, com UM detalhe distinto entre os 75.
O renderizador antigo desenhava um card por ocorrência e repetia o bloco de remediação em cada
uma — 121 páginas A4, das quais a maior parte era a mesma frase impressa dezenas de vezes.

Agrupar não pode virar esconder: toda ocorrência continua no relatório. O que sai é a
repetição, não o dado.
"""
import re

from build_report import _achados_com_remediacao, agrupar_achados


def _achado(regra, objeto, severidade="medium", detalhe="mesmo texto", **extra):
    return dict({"regra": regra, "objeto": objeto, "severidade": severidade,
                 "detalhe": detalhe, "alvo": "alvo-1"}, **extra)


def test_agrupa_por_regra_preservando_toda_ocorrencia():
    achados = [_achado("SEC_USER_ROOT", f"svc-{n}") for n in range(75)]

    grupos = agrupar_achados(achados)

    assert len(grupos) == 1
    assert grupos[0]["regra"] == "SEC_USER_ROOT"
    assert len(grupos[0]["ocorrencias"]) == 75


def test_detalhe_identico_em_todas_sobe_para_o_grupo():
    """75 vezes a mesma frase é ruído. Ela vale uma vez, no cabeçalho."""
    achados = [_achado("SEC_USER_ROOT", f"svc-{n}",
                       detalhe="container roda como root") for n in range(75)]

    grupo = agrupar_achados(achados)[0]

    assert grupo["detalhe_comum"] == "container roda como root"
    assert all(not oc.get("detalhe_proprio") for oc in grupo["ocorrencias"])


def test_detalhe_que_varia_fica_na_ocorrencia():
    """O oposto do caso acima: aqui o detalhe é o dado, e some se for tratado como comum."""
    achados = [_achado("OPS_TASK_FAILING", "worker-a", detalhe="4 tasks falharam"),
               _achado("OPS_TASK_FAILING", "worker-b", detalhe="20 tasks falharam")]

    grupo = agrupar_achados(achados)[0]

    assert grupo["detalhe_comum"] is None
    assert [oc["detalhe_proprio"] for oc in grupo["ocorrencias"]] == [
        "4 tasks falharam", "20 tasks falharam"]


def test_grupos_saem_na_ordem_de_severidade():
    achados = [_achado("R_BAIXA", "a", severidade="low"),
               _achado("R_CRITICA", "b", severidade="critical"),
               _achado("R_MEDIA", "c", severidade="medium")]

    assert [g["regra"] for g in agrupar_achados(achados)] == [
        "R_CRITICA", "R_MEDIA", "R_BAIXA"]


def test_mesma_regra_em_severidades_diferentes_nao_se_mistura():
    """Severidade é por achado, não por regra: um aceite pode rebaixar uma ocorrência.
    Fundir as duas faria o relatório anunciar gravidade que aquela ocorrência não tem."""
    achados = [_achado("R", "a", severidade="critical"),
               _achado("R", "b", severidade="low")]

    grupos = agrupar_achados(achados)

    assert [(g["regra"], g["severidade"]) for g in grupos] == [("R", "critical"), ("R", "low")]


def test_remediacao_sai_uma_vez_por_grupo_e_nao_por_ocorrencia():
    """A regressão que gerou 121 páginas: 204 blocos de remediação para 213 achados."""
    remediacao = {"titulo": "Roda como root", "como_resolver": "use `user:` no compose",
                  "como_confirmar": "docker exec id", "quando_nao_fazer": "quando precisa de root"}
    achados = [_achado("SEC_USER_ROOT", f"svc-{n}", como_resolver=remediacao)
               for n in range(75)]

    html = _achados_com_remediacao(achados)

    assert html.count("Como resolver") == 1
    assert html.count("Como confirmar") == 1
    assert html.count("<code>user:</code> no compose") == 1


def test_toda_ocorrencia_aparece_no_html():
    """Densidade não é corte: os 75 objetos continuam legíveis no PDF."""
    achados = [_achado("SEC_USER_ROOT", f"svc-{n}") for n in range(75)]

    html = _achados_com_remediacao(achados)

    for n in range(75):
        assert f"svc-{n}<" in html or f"svc-{n} " in html, f"svc-{n} sumiu do relatório"


def test_contagem_do_grupo_aparece_no_cabecalho():
    achados = [_achado("SEC_USER_ROOT", f"svc-{n}") for n in range(75)]

    html = _achados_com_remediacao(achados)

    assert "75" in re.search(r'<div class="grp-h">.*?</div>', html, re.S).group(0)


def test_aceite_vencido_marca_a_ocorrencia_nao_o_grupo():
    """O aceite é de UMA ocorrência. Marcar o grupo acusaria 74 serviços inocentes."""
    achados = [_achado("R", "a"), _achado("R", "b", aceite_vencido=True)]

    html = _achados_com_remediacao(achados)

    assert html.count("aceite vencido") == 1


def test_descricao_do_grupo_respeita_o_markdown():
    """A descrição vem do mesmo arquivo de remediação que o resto — escrita em markdown.
    Escapada com `_e`, ela imprimia `**assim**` e as crases no meio da frase."""
    remediacao = {"titulo": "Imagem sem versão fixa",
                  "por_que_importa": "Com `:latest`, **o que roda pode mudar** sozinho."}
    html = _achados_com_remediacao([_achado("SEC_IMAGE_UNPINNED", "a",
                                            como_resolver=remediacao)])

    assert "<code>:latest</code>" in html
    assert "<strong>o que roda pode mudar</strong>" in html
    assert "**" not in html
