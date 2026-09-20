# tests/test_build_report_insights.py
import build_report


def _relatorio():
    return {
        "schema_version": 3, "generated_at": "2026-09-19T10:00:00Z",
        "resumo": "", "fortes": [], "fracos": [], "recomendacoes": [], "aceites": [],
        "historico": None,
        "inventario": [{"nome": "cluster", "tipo": "docker", "onde": "context: prod",
                        "saude": "🟡"}],
        "alvos": [{
            "nome": "cluster", "tipo": "docker", "onde": "context: prod", "saude": "🟡",
            "dimensoes": {}, "nao_coletado": [], "analise": "",
            "fatos": {"impact_points": [{"titulo": "Proxy é ponto único",
                                         "cenario": "se o proxy cair",
                                         "consequencia": "17 aplicações saem do ar"}]},
            "achados": [{"regra": "SEC_PORT_EXPOSED", "objeto": "adminer", "severidade": "medium",
                         "alvo": "cluster", "componente": "adminer",
                         "detalhe": "0.0.0.0:8080",
                         "como_resolver": {
                             "titulo": "Porta publicada em todas as interfaces do host",
                             "por_que_importa": "é a superfície de exposição",
                             "como_resolver": "1. publique na interface interna",
                             "como_confirmar": "rode a auditoria de novo",
                             "quando_nao_fazer": "quando é o proxy público"}}],
            "componentes": [{
                "nome": "proxy", "papel": "entrada", "achados": [], "analise": "",
                "respostas": [
                    {"pergunta": "entrada.volume_na_janela", "fonte": "promql:traefik",
                     "valor": 12480},
                    {"pergunta": "entrada.distribuicao_de_status", "fonte": "promql:traefik",
                     "valor": [{"chave": "200", "valor": 8940}, {"chave": "404", "valor": 1980}]},
                    {"pergunta": "entrada.latencia", "sem_dados": True,
                     "motivo": "o exporter deste componente não expõe histograma"}]}]}]}


def test_sumario_lista_as_secoes_sem_numero_de_pagina():
    """Número de página exigiria segunda passada dependente de ferramenta externa — saída
    diferente por máquina, e lá se vai o determinismo."""
    html = build_report.render_html_v3(_relatorio())
    assert "Sumário" in html
    assert "Insights por sistema" in html and "Achados" in html
    assert "pág." not in html


def test_insight_mostra_valor_e_fonte():
    html = build_report.render_html_v3(_relatorio())
    assert "12.480" in html or "12480" in html
    assert "promql:traefik" in html


def test_insight_sem_dados_mostra_o_motivo_em_vez_de_sumir():
    html = build_report.render_html_v3(_relatorio())
    assert "não expõe histograma" in html


def test_lista_vira_ranking_com_as_chaves():
    html = build_report.render_html_v3(_relatorio())
    assert "200" in html and "404" in html


def test_achado_traz_como_resolver_e_como_confirmar():
    html = build_report.render_html_v3(_relatorio())
    assert "Como resolver" in html and "Como confirmar" in html
    assert "rode a auditoria de novo" in html
    assert "quando é o proxy público" in html


def test_impacto_volta_a_aparecer():
    """`impact.build` roda desde o v1 e o resultado era descartado."""
    html = build_report.render_html_v3(_relatorio())
    assert "17 aplicações saem do ar" in html


def test_valor_dinamico_continua_escapado():
    r = _relatorio()
    r["alvos"][0]["componentes"][0]["nome"] = "<script>alert(1)</script>"
    html = build_report.render_html_v3(r)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_placeholder_escrito_pelo_agente_nao_injeta_secao():
    """Substituição em UMA passada: %%ACHADOS%% escrito dentro do resumo é texto, não seção."""
    r = _relatorio()
    r["resumo"] = "o agente escreveu %%ACHADOS%% aqui"
    html = build_report.render_html_v3(r)
    assert html.count("SEC_PORT_EXPOSED") == 1


def test_relatorio_sem_componente_nao_quebra():
    r = _relatorio()
    r["alvos"][0]["componentes"] = []
    html = build_report.render_html_v3(r)
    assert "nenhum componente" in html


def _com_componentes():
    r = _relatorio()
    alvo = r["alvos"][0]
    alvo["componentes"] = [
        {"nome": "traefik", "papel": "entrada", "achados": [], "analise": "",
         "respostas": [{"pergunta": "entrada.latencia", "fonte": "promql:traefik", "valor": 890},
                       {"pergunta": "entrada.volume_na_janela", "fonte": "promql:traefik",
                        "valor": 12480}]},
        {"nome": "postgres_principal", "papel": "banco", "achados": [], "analise": "",
         "respostas": []},
        {"nome": "api", "papel": "app", "achados": [
            {"regra": "SEC_USER_ROOT", "severidade": "medium", "alvo": "cluster",
             "componente": "api"}], "analise": "", "respostas": []},
    ]
    return r


def test_topologia_agrupa_por_papel_e_diz_que_e_papel():
    """O mapa mostra CAMADAS POR PAPEL, não dependência medida. Deixar isso implícito faria
    o relatório afirmar uma topologia que a skill nunca observou."""
    html = build_report.render_html_v3(_com_componentes())

    assert "Topologia" in html
    assert html.index("traefik") < html.index("api") < html.index("postgres_principal"), \
        "entrada vem antes de app, que vem antes de banco"
    assert "papel" in html.lower()
    assert "não é dependência medida" in html.lower(), \
        "a legenda precisa dizer que o agrupamento não é dependência observada"


def test_no_da_topologia_mostra_quantos_achados_tem():
    html = build_report.render_html_v3(_com_componentes())
    assert 'class="qt"' in html


def test_medidor_so_aparece_onde_ha_faixa_declarada():
    """Agulha sem tolerância declarada sugere uma leitura que ninguém definiu."""
    html = build_report.render_html_v3(_com_componentes())

    assert html.count('class="anel"') == 1, "só a latência declara faixa"
    assert "890" in html and "12.480" in html


def test_medidor_diz_qual_e_a_faixa():
    html = build_report.render_html_v3(_com_componentes())
    assert "700" in html and "1.500" in html or "1500" in html


def test_selos_contam_os_estados_em_palavra():
    html = build_report.render_html_v3(_com_componentes())
    assert "Atenção" in html and "🟡" not in html


def test_sumario_traz_contagem_por_secao():
    html = build_report.render_html_v3(_com_componentes())
    assert "1 achado" in html or "1 aberto" in html
