"""Restrição 3 do spec da parte C: relatório sem host sai igual, fora dos painéis Máquinas e Bancos.

Os goldens foram gravados ANTES da mudança (task 1 do plano). Regravar um golden para o teste passar
apaga justamente o que ele protege: só regrave com decisão registrada no plano.
"""
import re
from pathlib import Path

import build_report as br
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_grande import relatorio_grande

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
# os dois painéis que o spec deixa mudar também nos clusters
_PAINEL_QUE_MUDA = re.compile(
    r'<section class="bl-pn[^"]*"><header><h3>(?:Máquinas|Bancos de dados)</h3>.*?</section>', re.S)
# a âncora que o "ver todos os passos" usa; não muda nada do que se lê
_ID_DA_REGRA = re.compile(r' id="regra-[^"]*"')


def corpo(html):
    body = re.search(r"<body.*?</body>", html, re.S).group(0)
    body = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
    return _PAINEL_QUE_MUDA.sub("", _ID_DA_REGRA.sub("", body))


def test_rodada_grande_de_cluster_sai_igual_fora_de_maquinas_e_bancos():
    esperado = (GOLDEN / "relatorio_grande.body.html").read_text(encoding="utf-8")
    assert corpo(br.render_html_v3(relatorio_grande())) == esperado


def test_cluster_e_endpoint_saem_iguais_fora_de_maquinas_e_bancos():
    esperado = (GOLDEN / "relatorio_docker.body.html").read_text(encoding="utf-8")
    assert corpo(br.render_html_v3(relatorio_docker())) == esperado
