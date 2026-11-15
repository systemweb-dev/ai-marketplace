import re

import build_report as br
from tests.fixtures.relatorio_host import relatorio_com_hosts


def _html():
    return br.render_html_v3(relatorio_com_hosts())


def test_servicos_dos_servidores_tem_indice_e_uma_area_por_servidor():
    html = _html()
    assert "Serviços dos servidores" in html and html.count('<div class="srv">') == 2
    assert html.count('<ol class="ix">') == 1 and html.count('class="ix-p"') == 4


def test_area_do_servidor_tem_os_tres_grupos_na_ordem():
    html = _html()
    inicio = html.index('<div class="srv">')
    area = html[inicio:html.index('<div class="srv">', inicio + 1)]
    assert area.index("Problemas e o que fazer") < area.index("Estado dos serviços") < area.index("Informativo")
    assert "Debian GNU/Linux 12" in area and "Acesso com a identidade SSH" in area


def test_reinicio_alto_destacado_e_memoria_em_barras():
    html = _html()
    assert 'class="svc alerta"' in html and 'class="rei-alto bl-c-warn"' in html
    assert "Memória por serviço" in html


def test_informativo_diz_o_que_fazer_com_o_descoberto_e_o_nao_medido():
    html = _html()
    assert "Descoberto e não declarado: postgres" in html and "configurar.py descobrir --alvo banco-01" in html
    assert "a VPN está ligada?" in html


def test_problema_da_secao_problemas_tem_ancora_para_o_link_do_cartao():
    html = _html()
    assert 'id="regra-backup_atrasado"' in html and 'href="#regra-backup_atrasado"' in html


def test_busca_aparece_e_o_host_nao_vai_para_outros_sistemas():
    html = _html()
    assert "<h3>Busca</h3>" in html and "Outros sistemas" not in html


def test_nenhum_cartao_de_problema_sem_o_que_fazer():
    html = _html()
    cartoes = re.findall(r'<article class="fx (?:crit|warn)" id="p-[^"]+">.*?</article>', html, re.S)
    assert len(cartoes) == 4
    assert all("<b>O que fazer</b>" in c and 'href="#regra-' in c for c in cartoes)


def test_cada_achado_vira_cartao_uma_vez_so():
    ids = re.findall(r'<article class="fx (?:crit|warn)" id="(p-[^"]+)"', _html())
    assert sorted(ids) == sorted(set(ids)) and len(ids) == 4


def test_cada_link_do_indice_leva_a_um_cartao():
    html = _html()
    indice = re.search(r'<ol class="ix">.*?</ol>', html, re.S).group(0)
    hrefs = set(re.findall(r'href="#(p-[^"]+)"', indice))
    ids = set(re.findall(r'<article class="fx (?:crit|warn)" id="(p-[^"]+)"', html))
    assert hrefs == ids and len(ids) == 4


def test_busca_de_cluster_continua_em_outros_sistemas_sem_bloco_busca():
    from tests.fixtures.relatorio_docker import relatorio_docker
    r = relatorio_docker()
    r["alvos"][0]["componentes"].append({"nome": "loja_qdrant", "papel": "busca", "achados": [], "respostas": []})
    html = br.render_html_v3(r)
    assert "Outros sistemas" in html and "<h3>Busca</h3>" not in html
