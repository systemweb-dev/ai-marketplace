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


def test_o_mostrador_nao_herda_a_quebra_de_pagina_da_faixa_de_triagem():
    """`.faixa` era duas coisas: a banda de triagem (que força página nova em impressão) e a
    tolerância do mostrador. O `<p>` de dentro do cartão herdava a quebra e partia o cartão."""
    fonte = PY_.read_text(encoding="utf-8")
    v3 = fonte[fonte.index(MARCA_V3):]
    css = _css()

    assert re.search(r"\.faixa\{[^}]*break-before:\s*page", css), \
        "a faixa de triagem deixou de forçar página nova; este teste perdeu o sentido"
    dentro_do_mostrador = re.search(r'<div class="mdr">.*?</div>\'\)', v3, re.S)
    assert dentro_do_mostrador, "o cartão de mostrador mudou de forma; reveja esta trava"
    assert 'class="faixa"' not in dentro_do_mostrador.group(0), \
        "o mostrador voltou a usar `faixa`, que é o nome da banda que quebra a página"


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
    assert inline, "nenhuma variável inline encontrada; o padrão do `style=` mudou"
    usadas = set(re.findall(r"var\((--[\w-]+)[,)]", css)) - inline
    definidas = set(re.findall(r"(--[\w-]+)\s*:", css))

    assert not usadas - definidas, sorted(usadas - definidas)


# ---------------------------------------------------------------- o arco diz a verdade
def test_os_arcos_do_mostrador_saem_da_tolerancia_declarada():
    """Três partes iguais é bonito e mente.

    Com `bom_ate` 700 e `ruim_a_partir` 1500 sobre um máximo de 3000, as marcas reais estão em
    42° e 90° — um terço cada (60° e 120°) diria que 1000 ms ainda é bom.
    """
    import build_report

    faixa = {"sentido": "menor_melhor", "bom_ate": 700, "ruim_a_partir": 1500, "maximo": 3000}

    assert build_report._arcos(faixa) == (42.0, 90.0)


def test_no_sentido_invertido_o_bom_continua_a_esquerda():
    """`_angulo` põe o lado bom sempre à esquerda nos dois sentidos; se os arcos não
    espelharem junto, o verde fica do lado onde a agulha nunca é boa."""
    import build_report

    faixa = {"sentido": "maior_melhor", "bom_ate": 90, "ruim_a_partir": 50, "maximo": 100}
    g1, g2 = build_report._arcos(faixa)

    assert (g1, g2) == (18.0, 90.0)
    agulha_otima = build_report._angulo(100, faixa)
    assert agulha_otima == -90.0, "100 é o melhor valor e a agulha tem de encostar à esquerda"
