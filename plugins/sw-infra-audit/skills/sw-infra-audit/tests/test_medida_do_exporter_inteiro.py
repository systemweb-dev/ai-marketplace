"""Medida que vale para o exporter INTEIRO não pode ser atribuída a cada componente.

Quando o adaptador não consegue restringir a consulta a um componente, ele carimba a fonte
com "(exporter inteiro)" — e isso é honesto. O que não era honesto é o relatório desenhar o
mesmo número uma vez por componente: numa rodada real, `systemweb_nginx` e `traefik_traefik`
apareciam cada um com "60.281 requisições" e "652,63 ms", os MESMOS valores, da MESMA fonte.
Lido assim, o relatório afirma que o nginx serviu 60 mil requisições. Ele não serviu — quem
serviu foi o conjunto medido pelo exporter.

A medida aparece UMA vez, nomeando os componentes que ela cobre.
"""
from build_report import _instrumentos


def componente(nome, valor, fonte):
    return {"nome": nome, "papel": "entrada", "achados": [], "analise": "",
            "respostas": [{"pergunta": "entrada.latencia", "valor": valor, "fonte": fonte}]}


def alvos_com(componentes):
    return [{"nome": "cluster", "componentes": componentes}]


def test_medida_do_exporter_inteiro_aparece_uma_vez_so():
    html = _instrumentos(alvos_com([
        componente("systemweb_nginx", 652.63, "promql:traefik (exporter inteiro)"),
        componente("traefik_traefik", 652.63, "promql:traefik (exporter inteiro)")]))

    assert html.count("652") == 1, "o mesmo número do mesmo exporter, desenhado duas vezes"


def test_e_diz_quais_componentes_ela_cobre():
    html = _instrumentos(alvos_com([
        componente("systemweb_nginx", 652.63, "promql:traefik (exporter inteiro)"),
        componente("traefik_traefik", 652.63, "promql:traefik (exporter inteiro)")]))

    assert "systemweb_nginx" in html and "traefik_traefik" in html, \
        "some o número duplicado, não a informação de quem ele cobre"


def test_medidas_por_componente_continuam_separadas():
    """Fonte restrita ao componente: cada um tem a sua, e são medidas diferentes."""
    html = _instrumentos(alvos_com([
        componente("app-a", 120.0, "promql:traefik{service=app-a}"),
        componente("app-b", 980.0, "promql:traefik{service=app-b}")]))

    assert "120" in html and "980" in html


def test_mesmo_valor_de_fontes_diferentes_nao_se_funde():
    """Coincidência de valor não é a mesma medida."""
    html = _instrumentos(alvos_com([
        componente("app-a", 652.63, "promql:nginx"),
        componente("app-b", 652.63, "promql:traefik")]))

    assert html.count("652") == 2
