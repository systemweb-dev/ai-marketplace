# tests/test_dizer_uma_vez.py
"""O relatório não escreve a mesma frase uma vez por linha.

Esta trava nasceu de uma rodada real de 61 serviços. Em 6 das 9 regras o campo `detalhe`
era IDÊNTICO em todas as ocorrências — `container roda como root (user root/uid 0 ou USER
ausente)` saía 61 vezes, `sem HEALTHCHECK definido` 49, `sem limite de CPU/memória
definido` 34 —, e as 79 perguntas sem resposta carregavam 3 motivos, um deles impresso 55
vezes. Repetir a mesma frase dez vezes não informa dez vezes: ensina quem lê a pular o
bloco inteiro, inclusive a linha que mudaria.

A regra: o texto que vale para TODAS as ocorrências descreve a regra, não a ocorrência, e
é escrito uma vez. O texto que varia continua linha a linha — agrupar o que difere
esconderia informação, que é o erro oposto e pior.
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import build_report as br  # noqa: E402

TPL = RAIZ / "assets" / "report-template" / "template_v3.html"


def _achado(objeto, detalhe, regra="SEC_USER_ROOT", severidade="medium"):
    return {"regra": regra, "objeto": objeto, "severidade": severidade, "detalhe": detalhe}


# --------------------------------------------------------------- o detalhe da regra
def test_detalhe_igual_em_todas_as_ocorrencias_e_da_regra():
    itens = [_achado(f"svc{i}", "container roda como root") for i in range(5)]
    assert br._detalhe_comum(itens) == "container roda como root"


def test_detalhe_que_varia_nao_e_da_regra():
    """`4 task(s) falharam` e `20 task(s) falharam` descrevem ocorrências diferentes.
    Hoistar o primeiro faria o relatório afirmar 4 para quem tem 20."""
    itens = [_achado("a", "4 task(s) falharam"), _achado("b", "20 task(s) falharam")]
    assert br._detalhe_comum(itens) is None


def test_o_bloco_escreve_a_frase_comum_uma_vez_so():
    itens = [_achado(f"svc{i}", "container roda como root") for i in range(12)]

    html = br._achado_bloco("SEC_USER_ROOT", itens, completo=False)

    assert html.count("container roda como root") == 1
    # e os doze nomes continuam no documento — a frase saiu, a lista não
    for i in range(12):
        assert f"svc{i}" in html


def test_com_detalhe_que_varia_cada_ocorrencia_mantem_o_seu():
    itens = [_achado("a", "4 task(s) falharam", regra="OPS_TASK_FAILING"),
             _achado("b", "20 task(s) falharam", regra="OPS_TASK_FAILING")]

    html = br._achado_bloco("OPS_TASK_FAILING", itens, completo=False)

    assert "4 task(s) falharam" in html and "20 task(s) falharam" in html


def test_sem_numero_e_sem_legenda_a_lista_perde_a_barra_vazia():
    """A grade de ranking desenha uma barra por item. Sem medida nenhuma ela desenharia
    doze barras vazias — doze gráficos que não medem coisa alguma."""
    itens = [_achado(f"svc{i}", "sem HEALTHCHECK definido") for i in range(12)]

    html = br._achado_bloco("OPS_NO_HEALTHCHECK", itens, completo=False)

    assert 'class="tr"' not in html
    assert 'class="nomes"' in html


# --------------------------------------------------------------- o silêncio
def _mudo(componente, pergunta, motivo):
    return {"componente": componente, "pergunta": pergunta, "motivo": motivo}


def test_perguntas_caladas_sao_agrupadas_pelo_motivo():
    motivo = "o exporter cadvisor cobre vários componentes e nenhum valor da etiqueta casa"
    mudos = [_mudo(f"c{i}", "app.cpu", motivo) for i in range(18)]

    html = br._mudos_por_motivo(mudos)

    assert html.count(motivo) == 1
    assert "18 perguntas" in re.sub(r"<[^>]+>", "", html)
    for i in range(18):
        assert f"c{i}" in html


def test_motivos_diferentes_continuam_separados():
    html = br._mudos_por_motivo([_mudo("a", "app.cpu", "sem exporter"),
                                 _mudo("b", "app.cpu", "papel não provado")])

    assert "sem exporter" in html and "papel não provado" in html


def test_o_motivo_com_mais_componentes_vem_primeiro():
    html = br._mudos_por_motivo([_mudo("a", "x", "raro")]
                                + [_mudo(f"b{i}", "x", "comum") for i in range(3)])

    assert html.index("comum") < html.index("raro")


def test_respostas_do_cartao_dizem_o_motivo_uma_vez():
    """Três perguntas descartadas pela mesma razão imprimiam o mesmo parágrafo três vezes
    dentro do MESMO cartão."""
    motivo = "é o tráfego do proxy inteiro, não o deste serviço"
    respostas = [{"pergunta": f"entrada.p{i}", "sem_dados": True, "motivo": motivo}
                 for i in range(3)]

    html = br._respostas_do_cartao(respostas)

    assert html.count(motivo) == 1


def test_a_medida_vem_antes_do_silencio_no_cartao():
    html = br._respostas_do_cartao([
        {"pergunta": "app.cpu", "sem_dados": True, "motivo": "sem fonte"},
        {"pergunta": "app.memoria", "fonte": "promql:cadvisor", "valor": 7}])

    assert html.index("promql:cadvisor") < html.index("sem fonte")


# --------------------------------------------------------------- o que o papel comporta
def test_a_etiqueta_do_inventario_quebra_linha():
    """`<span>A</span><span>B</span>` sem espaço entre as tags não dá ao navegador NENHUM
    ponto de quebra. Com 68 secrets isso virou uma linha única de 13.007px: no HTML pedia
    rolagem horizontal e no PDF as etiquetas sumiam no corte da página a partir da
    terceira. A regra tem de valer para toda `.tags`, não só a de dentro do `.rec`."""
    css = TPL.read_text(encoding="utf-8")
    regra = re.search(r"(?<![\w.-])\.tags\{([^}]*)\}", css)

    assert regra, "não há regra para `.tags` fora de um seletor aninhado"
    assert "flex-wrap:wrap" in regra.group(1).replace(" ", "")


def test_sistema_que_so_responde_numero_vira_linha_de_tabela():
    componente = {"nome": "api", "papel": "app", "achados": [], "analise": "",
                  "respostas": [{"pergunta": "app.cpu", "fonte": "promql", "valor": 1}]}
    assert br._so_medidas_simples(componente) is True

    com_lista = dict(componente, respostas=[{"pergunta": "fila.filas", "fonte": "a",
                                             "valor": [{"chave": "x", "valor": 1}]}])
    assert br._so_medidas_simples(com_lista) is False

    com_analise = dict(componente, analise="o worker reinicia")
    assert br._so_medidas_simples(com_analise) is False


def test_a_tabela_de_sistemas_poe_cada_pergunta_numa_coluna():
    itens = [{"nome": f"svc{i}", "achados": [], "analise": "",
              "respostas": [{"pergunta": "app.cpu", "fonte": "promql:cadvisor", "valor": i},
                            {"pergunta": "app.memoria", "fonte": "promql:cadvisor",
                             "valor": i * 10}]} for i in range(3)]

    html = br._tabela_de_sistemas(itens)

    assert html.count("<tr>") == 4          # o cabeçalho e as três linhas
    # a fonte é a mesma nas três: ela vale uma vez, no rodapé
    assert html.count("promql:cadvisor") == 1


# --------------------------------------------------------------- o que estava invisível
def _relatorio_sem_achado_critico():
    """Uma rodada em que a faixa "Agir agora" fica vazia — o caso REAL em que as oito
    recomendações da auditoria não saíram em nenhuma das 31 páginas."""
    from tests.test_build_report_v3 import relatorio
    r = relatorio()
    for a in r["alvos"]:
        a["achados"] = [dict(x, severidade="low") for x in (a.get("achados") or [])]
    # "Se isto falhar" só existe com ponto de impacto, e é dele que o teste de ordem fala
    r["alvos"][0]["fatos"] = {"impact_points": [
        {"cenario": "Se o nó manager cair", "consequencia": "o ingress cai junto",
         "impacto": "alto", "esforco": "alto", "alvos": ["traefik"]}]}
    return r


def test_as_recomendacoes_aparecem_mesmo_sem_nada_para_agir_hoje():
    html = br.render_html_v3(_relatorio_sem_achado_critico())

    assert "Agir agora" in html          # a faixa continua anunciada no índice
    assert "O que fazer primeiro" in html
    assert "Subir segunda réplica do Traefik" in html


def test_o_indice_lista_as_secoes_e_nao_so_as_faixas():
    html = br.render_html_v3(_relatorio_sem_achado_critico())
    indice = html[html.index('<div class="idx">'):html.index('<div class="idx">') + 4000]

    assert 'href="#o-que-fazer-primeiro"' in indice
    assert 'href="#riscos-aceitos"' in indice


def test_alvo_nao_confirmado_aparece_com_o_nome_dele():
    """Três alvos não confirmados viravam três linhas idênticas dizendo "alvo não
    confirmado nesta execução" sem dizer QUAL alvo."""
    r = _relatorio_sem_achado_critico()

    html = br._pendencias_novo(r["alvos"])

    assert "<b>site</b>" in html


# --------------------------------------------------------------- os quatro movimentos
def test_cada_secao_declara_o_movimento_a_que_pertence():
    html = br.render_html_v3(_relatorio_sem_achado_critico())
    movs = dict(re.findall(r'<section class="sec[^"]*" id="([^"]+)" data-mov="([^"]*)"', html))

    assert movs.get("o-que-fazer-primeiro") == "decidir"
    assert movs.get("se-isto-falhar") == "decidir"
    assert movs.get("riscos-aceitos") == "registrar"
    assert all(m in {"decidir", "medir", "consertar", "registrar"} for m in movs.values()), movs


def test_a_decisao_vem_antes_da_medida():
    """"Se isto falhar" ficava depois de "Instrumentos", no meio do bloco de medição — e é
    a seção que mais se parece com uma decisão em todo o documento. Com a lombada colorida
    isso virava um salto de tom no meio do movimento."""
    html = br.render_html_v3(_relatorio_sem_achado_critico())

    assert html.index('id="se-isto-falhar"') < html.index('id="cluster"')


def test_o_movimento_nao_usa_a_cor_da_gravidade():
    """A paleta já gasta vermelho, âmbar e verde em severidade. Se o movimento também pedir
    matiz, as duas coisas competem pelo mesmo sinal — e quem perde é a gravidade, que é a
    única das duas que muda o que se faz hoje. A escada anda em `--acc` e só nele."""
    css = TPL.read_text(encoding="utf-8")
    bloco = re.search(r'\[data-mov="decidir"\].*?\[data-mov="registrar"\][^}]*\}', css, re.S)

    assert bloco, "o bloco dos movimentos sumiu do template"
    for proibida in ("--crit", "--warn", "--ok"):
        assert proibida not in bloco.group(0), f"{proibida} é cor de gravidade, não de movimento"


def test_o_indice_agrupa_as_secoes_pelo_movimento():
    html = br.render_html_v3(_relatorio_sem_achado_critico())
    idx = html[html.index('<div class="idx">'):]
    idx = idx[:idx.index("</div>\n\n")] if "</div>\n\n" in idx else idx[:6000]

    assert 'data-mov="decidir"' in idx and "Decidir" in idx
    assert 'data-mov="registrar"' in idx and "Registrar" in idx
