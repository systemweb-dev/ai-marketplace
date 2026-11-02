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


def test_as_partes_saem_sem_numero_de_pagina():
    """Numero de pagina exigiria segunda passada dependente de ferramenta externa — saida
    diferente por maquina, e la se vai o determinismo."""
    html = build_report.render_html_v3(_relatorio())
    assert "Saúde por sistema" in html and "Problemas" in html and "Registro" in html
    assert "pág." not in html


def test_insight_mostra_valor_e_fonte():
    html = build_report.render_html_v3(_relatorio())
    assert "12,5 mil de acessos" in html
    assert "promql:traefik" in html


def test_insight_sem_dados_mostra_o_motivo_em_vez_de_sumir():
    html = build_report.render_html_v3(_relatorio())
    assert "não expõe histograma" in html


def test_lista_vira_ranking_com_as_chaves():
    html = build_report.render_html_v3(_relatorio())
    assert "200" in html and "404" in html


def test_achado_traz_como_resolver_e_como_confirmar():
    html = build_report.render_html_v3(_relatorio())
    assert "O que fazer" in html and "Como conferir" in html
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
    assert "Não medido" in html and "Outros sistemas" not in html


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
    alvo["achados"] = alvo["achados"] + alvo["componentes"][2]["achados"]   # como o coletor promove
    return r


def test_detalhes_seguem_a_ordem_dos_papeis_e_dizem_que_e_papel():
    """O agrupamento mostra PAPEL, não dependência medida. Deixar isso implícito faria o
    relatório afirmar uma topologia que a skill nunca observou."""
    r = _com_componentes()
    r["alvos"][0]["componentes"].append(
        {"nome": "busca", "papel": "busca", "achados": [], "analise": "",
         "respostas": [{"pergunta": "x", "fonte": "promql:y", "valor": 1}]})
    html = build_report.render_html_v3(r)

    assert html.index("Serviços web") < html.index("Maiores consumidores") < html.index("Outros sistemas"), \
        "entrada vem antes de app, que vem antes do que não tem bloco"
    assert "papel" in html.lower()
    assert "não é dependência medida" in html.lower(), \
        "a legenda precisa dizer que o agrupamento não é dependência observada"


def test_componente_calado_e_contado_e_nao_vira_cartao():
    """54 de 57 componentes não responderam nada numa rodada real. Um cartão para cada,
    todos repetindo a mesma frase, deu NOVE páginas A4 de ruído. A informação não some:
    ela é contada uma vez, em "O que falta declarar"."""
    html = build_report.render_html_v3(_com_componentes())

    detalhes = html[html.index('id="detalhes-tecnicos"'):html.index('id="o-que-falta-declarar"')]
    assert "postgres_principal" not in detalhes, "componente sem nada a dizer não ganha cartão"
    assert "traefik" in detalhes and "api" in detalhes, "quem respondeu ou tem achado continua"

    # ...mas e NOMEADO em "O que falta declarar": o relatorio nao fica mudo sobre o silencio
    pend = html[html.index('id="o-que-falta-declarar"'):]
    assert "postgres_principal" in pend, "o calado é nomeado, não sumido"
    assert "alvos.toml" in pend, "e o relatório diz o que fazer para ele falar"


def test_problema_mostra_quantos_achados_tem():
    html = build_report.render_html_v3(_com_componentes())
    assert "Afetados: 1 ocorrência" in html


def test_cor_de_tolerancia_so_aparece_onde_ha_faixa_declarada():
    """Veredito sem tolerância declarada sugere uma leitura que ninguém definiu."""
    html = build_report.render_html_v3(_com_componentes())

    assert '<b class="bl-c-warn">890 ms</b>' in html, "só a latência declara faixa"
    assert "12,5 mil de acessos" in html and 'bl-c-warn">12,5' not in html


def test_relatorio_diz_qual_e_a_faixa():
    html = build_report.render_html_v3(_com_componentes())
    assert "700 ms" in html and "1.500 ms" in html


def test_selos_contam_os_estados_em_palavra():
    r = _com_componentes()
    r["nota_geral"] = {"valor": 70, "faixa": "atencao", "parcial": False, "online": 1, "base": 1,
                       "teto": None, "parcelas": {}}
    html = build_report.render_html_v3(r)
    assert "Atenção" in html and "🟡" not in html


def test_problema_traz_contagem():
    html = build_report.render_html_v3(_com_componentes())
    assert "1 ocorrência" in html
