import re
from pathlib import Path

from lib import graficos
from lib.html_comum import tamanho

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "report-template" / "template_v3.html"


def test_medidor_abaixo_da_marca_usa_o_acento_e_sem_etiqueta():
    html = graficos.medidor(42, 100, 80, "Conexões em uso", "42%", marca_texto="alerta em 80%")
    assert 'class="gf-acc"' in html and "bl-tag-" not in html and "42%" in html and "alerta em 80%" in html


def test_medidor_acima_da_marca_tem_cor_de_status_icone_e_rotulo():
    html = graficos.medidor(5, 4, 2, "Idade do backup", "5 dias", acima="crit")
    assert 'class="gf-crit"' in html and 'class="bl-tag-crit"' in html and "#ic-achado" in html
    assert "acima do limite" in html


def test_medidor_sem_valor_diz_sem_dado():
    html = graficos.medidor(None, 100, 80, "Conexões em uso", "")
    assert "sem dado" in html and "<svg" not in html


def test_barras_ordenam_e_cortam_com_e_mais():
    itens = [("a", 10), ("b", 300), ("c", None), ("d", 50), ("e", 1), ("f", 2), ("g", 3)]
    html = graficos.barras(itens, tamanho, "Tamanho por banco", limite=5)
    rotulos = re.findall(r'<span class="br-l">([^<]+)</span>', html)
    assert rotulos == ["b", "d", "a", "g", "f"] and "e mais 2" in html


def test_barras_sem_dado_vem_por_ultimo_e_escritas():
    html = graficos.barras([("x", None), ("y", 1024)], tamanho, "t")
    assert html.index(">y<") < html.index(">x<") and "sem dado" in html


def test_toda_marca_tem_title():
    html = graficos.medidor(42, 100, 80, "Conexões", "42%") + graficos.barras([("a", 1)], str, "t")
    assert html.count("<svg") == html.count("<title>")


def test_svg_nao_tem_cor_literal():
    html = (graficos.medidor(95, 100, 90, "Disco", "95%") + graficos.barras([("a", 1), ("b", 2)], str, "t")
            + graficos.barra(50, "Memória", tom="warn", marca=90))
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b|rgb\(|\b(fill|stroke)=", html)


def test_classes_dos_graficos_usam_tokens_nos_dois_temas():
    css = TEMPLATE.read_text(encoding="utf-8")
    for classe, token in (("gf-acc", "--g-acc"), ("gf-warn", "--g-warn"), ("gf-crit", "--g-crit"),
                          ("gf-trk", "--g-trk"), ("gf-lim", "--g-lim")):
        assert f".gf .{classe}{{fill:var({token})}}" in css, classe
        assert css.count(f"{token}:") == 2, token        # claro e escuro
