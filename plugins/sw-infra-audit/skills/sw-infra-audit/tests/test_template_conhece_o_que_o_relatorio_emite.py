"""Toda classe que o renderizador emite tem de existir no CSS do template.

Esta trava nasceu de uma rodada real. O relatório imprimia o VALOR em cima do NOME na lista de
consumidores por fila — `notas4`, `emai0s` —, e a causa não era o CSS estar feio: era o
renderizador falar um vocabulário que o template não conhece. `_ranking` emitia
`.lb/.vl/.bar`; a regra `.rk` é uma grade de quatro colunas que espera `.o/.nm/.tr/.vl`. O
nome caía na coluna de 20px e transbordava por cima do número.

Do mesmo jeito, o mostrador (`.med`, `.anel`, `.agulha`) não tinha regra nenhuma: cinco divs
vazios, e o `<p class="faixa">` de dentro dele herdava a regra da FAIXA DE TRIAGEM, que em
impressão força `break-before:page`. Resultado: todo cartão com tolerância declarada partia ao
meio numa quebra de página.

Nenhum teste pegou isso porque teste de HTML confere o conteúdo, não se o navegador sabe
desenhá-lo. Esta confere a junta entre os dois — que é onde o desenho novo sempre quebra.

O escopo é o renderizador v3, o único que `build()` chama.
"""
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PY_ = RAIZ / "scripts" / "build_report.py"
TPL = RAIZ / "assets" / "report-template" / "template_v3.html"
LIB = RAIZ / "scripts" / "lib"
MARCA_V3 = "# ---------------------------------------------------------------- relatório v3"


def _classes(texto):
    saida = set()
    for padrao in (r'class="([^"{}]*)"', r'class=\\"([^"{}\\]*)\\"'):
        for casado in re.finditer(padrao, texto):
            saida.update(parte for parte in casado.group(1).split() if parte)
    return saida


def _css():
    html = TPL.read_text(encoding="utf-8")
    return html[html.index("<style"):html.rindex("</style>")]


def test_nenhuma_classe_do_v3_fica_sem_regra():
    fonte = PY_.read_text(encoding="utf-8")
    v3 = fonte[fonte.index(MARCA_V3):]
    css = _css()

    orfas = sorted(c for c in _classes(v3)
                   if not re.search(r"[.]" + re.escape(c) + r"(?![\w-])", css))

    assert not orfas, ("o renderizador emite estas classes e o template não tem regra para "
                       "nenhuma delas — no navegador elas não existem, e o que aparece é o "
                       "fluxo padrão por cima do desenho:\n  ." + "\n  .".join(orfas))


def test_nenhuma_classe_dos_blocos_fica_sem_regra():
    fontes = list((LIB / "blocos").glob("*.py")) + [LIB / "html_comum.py", LIB / "capa.py"]
    css = _css()
    achadas = set()
    for p in fontes:
        if p.exists():
            texto = p.read_text(encoding="utf-8")
            achadas |= _classes(texto)
            for prefixo in re.findall(r'([\w-]+)-\{(?:tom|nota\["faixa"\])\}', texto):
                sufixos = ("bom", "atencao", "critico") if prefixo == "bl-f" else ("ok", "warn", "crit")
                achadas |= {f"{prefixo}-{t}" for t in sufixos}
    orfas = sorted(c for c in achadas if not re.search(r"[.]" + re.escape(c) + r"(?![\w-])", css))
    assert not orfas, orfas


URL = {"nome": "a.test/x", "site": "a.test", "caminho": "/x", "acessos": 10, "erros": 1, "pct_5xx": 10.0,
       "p95_ms": 5.0}
STATUS_MISTO = [{"chave": "200", "valor": 90}, {"chave": "404", "valor": 8}, {"chave": "500", "valor": 2}]
DADOS_DE_EXEMPLO = {
    "fila": {"filas": [
        {"nome": "parada", "prontas": 900, "consumidores": 0, "entrada": 3, "saida": 0},
        {"nome": "lenta", "prontas": 40, "consumidores": 1, "entrada": 9, "saida": 3},
        {"nome": "fluindo", "prontas": 1, "consumidores": 2, "entrada": 5, "saida": 5},
        {"nome": "sem ritmo", "prontas": None, "consumidores": None, "entrada": None, "saida": None},
        {"nome": "ociosa", "prontas": 0, "consumidores": 1, "entrada": None, "saida": None}]},
    "entrada": {"itens": [
        {"nome": "rapido", "volume": 12000, "status": STATUS_MISTO, "latencia": 100,
         "servicos": [{"nome": "api", "acessos": 10, "erros": 1, "resposta": 80},
                      {"nome": "vazio", "acessos": None, "erros": None, "resposta": None}]},
        {"nome": "medio", "volume": None, "status": None, "latencia": 1000},
        {"nome": "lento", "volume": 5, "status": [{"chave": "200", "valor": 5}], "latencia": 2000},
        {"nome": "sem dado", "latencia": None}]},
    "banco": {"itens": [{"nome": "pg", "conexoes": 12, "tamanho": 2048}, {"nome": "mysql"}]},
    "cache": {"itens": [{"nome": "redis", "acerto": 97, "memoria": 2048, "evictions": 0},
                        {"nome": "memcached"}]},
    "maquinas": {"itens": [{"nome": "m1", "cpu": 40, "memoria": 75, "disco": 91},
                           {"nome": "m2", "cpu": None, "memoria": None, "disco": None}]},
    "consumo": {"itens": [{"nome": "api", "cpu": 40, "memoria": 2048}, {"nome": "web"}]},
    "falhas": {"itens": [{"cenario": "a", "consequencia": "b", "impacto": "alto"},
                         {"cenario": "c", "consequencia": "d", "impacto": "médio"},
                         {"cenario": "e", "consequencia": "f", "impacto": "baixo"}, {}]},
    "urls": {"geral": [URL], "sites": [{"site": "a.test", "acessos": 10, "urls": [URL]}], "erros": [URL],
             "lentas": [URL], "faltas": [{"alvo": "b", "motivo": "m"}],
             "janelas": [{"total": 24, "cobertas": [], "amostradas": 1, "amostra": True}]},
    "storage": {"uso": "41%", "cota": None},
}
SEM_DADO = {"motivo": "sem exporter"}


def _capas():
    from lib.capa import render_capa

    def nota(valor, faixa, **resto):
        return {"valor": valor, "faixa": faixa, "parcial": False, "online": 3, "base": 4,
                "teto": None, "parcelas": {}, **resto}

    cheio = {"gerado_em": "2026-10-26T10:00:00Z", "aceites": [],
             "alvos": [{"nome": "c", "fatos": {"services": [{"name": "x", "replicas": "0/1"}]}}],
             "recomendacoes": [{"titulo": "a", "porque": "b", "impacto": i, "alvo": "c"}
                               for i in ("alto", "médio", "baixo", "outro", None)]
             + [{"titulo": "excedente"}],
             "historico": {"vs": "2026-10-23_1000", "novos": ["a"], "resolvidos": ["b"],
                           "nota_anterior": 70, "aviso": "formato anterior"},
             "tendencias": {"erros": [1.0, 0.4], "resposta": [1.0, 1000.0], "disco": [1.0, 91.0],
                            "cpu": [1.0, 40.0], "memoria": [1.0, 75.0]},
             "certificados": [{"nome": "a", "dias": 90}, {"nome": "b", "dias": 12},
                              {"nome": "c", "dias": -1}, {"nome": "d", "dias": None}]}
    capas = [render_capa(cheio, nota(v, f), "<p>Resumo.</p>", ["bancos"])
             for v, f in ((90, "bom"), (79, "atencao"), (40, "critico"))]
    capas.append(render_capa(cheio, nota(59, "critico", teto=59, online=0), "", []))
    capas.append(render_capa({}, nota(79, "atencao", teto=79, online=4), "", []))
    capas.append(render_capa(cheio, None, "<p>Resumo.</p>", ["bancos"]))
    capas.append(render_capa({}, None, "", []))
    return capas


def _html_de_exemplo():
    from lib.blocos import render_bloco
    from lib.html_comum import nao_medido, painel

    pedacos = [painel("Título", "resumo", "<p>corpo</p>"), painel("Título", "", "", cheio=True),
               nao_medido("sem fonte")]
    for papel, dados in DADOS_DE_EXEMPLO.items():
        pedacos += [render_bloco(papel, dados), render_bloco(papel, SEM_DADO)]
    return "".join(pedacos + _capas())


def test_toda_classe_que_sai_no_html_renderizado_tem_regra_no_template():
    """A varredura da fonte não enxerga `bl-c-{tom}`, nem classe montada em função. O que chega
    ao navegador é o HTML, então a trava lê o HTML: cobre tom e faixa sem lista de prefixos."""
    emitidas = {nome for valor in re.findall(r'class="([^"]*)"', _html_de_exemplo())
                for nome in valor.split()}
    css = _css()

    orfas = sorted(c for c in emitidas if not re.search(r"[.]" + re.escape(c) + r"(?![\w-])", css))

    assert not orfas, orfas


def test_os_dados_de_exemplo_cobrem_todos_os_tons_e_faixas():
    """Sem isto, tirar um caso do exemplo deixa a trava de cima verde e cega para aquele tom."""
    emitidas = set(re.findall(r'class="([^"]*)"', _html_de_exemplo()))
    texto = " ".join(emitidas).split()
    esperadas = {f"{prefixo}-{tom}" for tom in ("ok", "warn", "crit")
                 for prefixo in ("bl-c", "bl-fl", "bl-tag", "bl-q", "bl-imp", "bl-nivel")}
    esperadas |= {f"bl-f-{faixa}" for faixa in ("bom", "atencao", "critico")}
    esperadas |= {"bl-sd", "bl-nm", "bl-cheio"}

    assert esperadas <= set(texto), sorted(esperadas - set(texto))


def test_tokens_do_mockup_nao_vazam_para_o_template():
    assert "--border-color" not in TPL.read_text(encoding="utf-8")


def test_nenhuma_variavel_css_do_v3_fica_sem_definicao():
    """A mesma junta, no outro eixo — e com o mesmo custo.

    O renderizador escrevia `style="--c:var(--verde)"` nas três bolinhas da legenda do mapa.
    `--verde` não existe: o template define `--ok`, `--warn` e `--crit`. As três bolinhas
    saíam com `background` vazio, ou seja, invisíveis — a legenda que explica as cores do mapa
    não tinha cor nenhuma. A varredura de CLASSES não pega isto, porque não há classe errada.
    """
    fonte = PY_.read_text(encoding="utf-8")
    v3 = fonte[fonte.index(MARCA_V3):]
    css = _css()

    usadas = set(re.findall(r"var\((--[\w-]+)\)", v3))
    definidas = set(re.findall(r"(--[\w-]+)\s*:", css))

    assert not usadas - definidas, (
        "o renderizador referencia variáveis CSS que o template não define — elas resolvem "
        "para vazio, e a propriedade inteira some: " + ", ".join(sorted(usadas - definidas)))


def test_o_template_nao_referencia_variavel_que_ele_mesmo_nao_define():
    css = _css()
    # Algumas o RENDERIZADOR define inline (`style="--ang:50deg"`). Lê-las da fonte, em vez de
    # listá-las aqui, é o que faz o teste continuar valendo quando uma nova aparecer — uma
    # lista escrita à mão envelhece calada, que é o defeito que esta suíte inteira persegue.
    fonte = PY_.read_text(encoding="utf-8")
    # duas passadas: os blocos `style="..."`, e dentro de cada um TODAS as variáveis. Uma
    # expressão só captura a primeira por `style`, e `--g2` sumia de um `style` com duas.
    inline = {nome for estilo in re.findall(r'style="([^"]*)"', fonte[fonte.index(MARCA_V3):])
              for nome in re.findall(r"(--[\w-]+)\s*:", estilo)}
    usadas = set(re.findall(r"var\((--[\w-]+)[,)]", css)) - inline
    definidas = set(re.findall(r"(--[\w-]+)\s*:", css))

    assert not usadas - definidas, sorted(usadas - definidas)


# ---------------------------------------------------------------- função que ninguém chama
def test_nenhuma_funcao_do_v3_fica_inalcancavel():
    """Função órfã no renderizador não é código morto inofensivo: é uma ARMADILHA.

    Neste ciclo ela custou duas vezes. `_insights_v3` e `_topologia` desenhavam cartão de
    componente e legenda de camada — exatamente como as funções vivas —, e `build()` não chamava
    nenhuma das duas. Escrevi a origem do papel dentro da primeira: teste verde, nada no PDF.
    Escrevi a nota da limitação dentro da segunda: teste verde, nada no PDF. As duas vezes só o
    PDF renderizado mostrou, porque o teste provava que a FUNÇÃO funciona, não que ela é usada.
    """
    import ast

    fonte = PY_.read_text(encoding="utf-8")
    v3 = fonte[fonte.index(MARCA_V3):]
    arvore = ast.parse(v3)

    definidas = {no.name for no in ast.walk(arvore)
                 if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))}
    chamadas = {no.func.id for no in ast.walk(arvore)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)}
    # o ponto de entrada e o que o `collect`/`build` chamam de fora não precisam de chamador
    entradas = {"render_html_v3", "montar_contexto", "build"}
    # Órfãs que JÁ existiam quando esta trava foi escrita (v0.16.0). Estão aqui nomeadas, e não
    # perdoadas em silêncio: cada uma tem uma irmã viva que faz a mesma coisa, e é essa
    # duplicação que arma a armadilha. Removê-las é limpeza de outro ciclo — o que esta trava
    # impede é que a lista CRESÇA.
    conhecidas = {"_achados_com_remediacao", "_estado", "_pendencias", "_topologia"}

    orfas = sorted(definidas - chamadas - entradas - conhecidas)

    assert not orfas, ("estas funções do renderizador v3 não são chamadas por ninguém. Escrever "
                       "dentro de uma delas dá teste verde e nada no relatório:\n  "
                       + "\n  ".join(orfas))
