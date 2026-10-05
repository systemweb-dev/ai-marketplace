"""Quebrar cada trava e confirmar que um teste cai.

Teste verde prova que o teste roda, não que a trava funciona. Neste ciclo, SEIS travas nasceram
decorativas — passavam verdes com a mutação aplicada —, e duas delas eram a correção do ciclo
inteiro: a ordem do passe e a origem do papel gravada pelo coletor.

Das quatro travas da restrição verificável 2, DUAS são as que mais importam: sem
`identifica_papel` o exporter de container volta a votar e todo componente é confirmado `app`;
sem `exportador` o papel sai invertido — o container do exporter vira o produto. Nas duas, as
outras travas continuam passando e a suíte fica verde com o design quebrado.
"""
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]

# (nome, arquivo, trecho original, trecho mutado, teste que precisa cair)
MUTACOES = [
    ("casamento de etiqueta", "scripts/lib/identificacao.py",
     "    if len(candidatos) == 1:",
     "    if candidatos:",
     "tests/test_seletor_por_componente.py"),
    ("familia única", "scripts/lib/identificacao.py",
     "            elif len(votos) > 1:",
     "            elif False:",
     "tests/test_identificacao.py::test_duas_familias_que_provam_nao_confirmam"),
    ("identifica_papel", "scripts/lib/identificacao.py",
     'if reconhecida.get("identifica_papel") and not componente.get("exportador"):',
     'if not componente.get("exportador"):',
     "tests/test_identificacao.py::test_cadvisor_casa_todo_mundo_e_nao_confirma_ninguem"),
    ("exportador", "scripts/lib/identificacao.py",
     'if reconhecida.get("identifica_papel") and not componente.get("exportador"):',
     'if reconhecida.get("identifica_papel"):',
     "tests/test_identificacao.py::test_container_do_exportador_nunca_recebe_papel_provado"),
    # --- restrição 5: o prefixo da pergunta bate com o papel declarado pela família
    ("prefixo da pergunta", "scripts/lib/catalogo.py",
     '        if str(id_).split(".")[0] != papel:',
     "        if False:",
     "tests/test_catalogo_papel.py::test_pergunta_de_outro_papel_e_recusada"),
    # --- as duas que nasceram destestadas e quase passaram
    ("origem do papel no coletor", "scripts/lib/coletores/docker.py",
     'componente["papel_origem"] = ("declarado" if declarado.get("papel")',
     'componente["papel_origem"] = ("padrão" if True',
     "tests/test_coletor_docker.py::test_o_componente_nasce_com_a_origem_do_papel"),
    ("exportador marcado pelo coletor", "scripts/lib/coletores/docker.py",
     'componente["exportador"] = produtos.e_exportador(',
     'componente["exportador"] = False and produtos.e_exportador(',
     "tests/test_coletor_docker.py::test_o_componente_nasce_marcado_se_e_exportador"),
]


def _rodar(teste):
    return subprocess.run([sys.executable, "-m", "pytest", teste, "-q"],
                          cwd=RAIZ, capture_output=True, text=True).returncode


@pytest.mark.parametrize("nome,arquivo,original,mutado,teste",
                         MUTACOES, ids=[m[0] for m in MUTACOES])
def test_cada_trava_sustenta_um_teste(nome, arquivo, original, mutado, teste):
    caminho = RAIZ / arquivo
    antes = caminho.read_text(encoding="utf-8")
    assert original in antes, f"{nome}: a trava mudou de forma; reveja esta mutação"
    try:
        caminho.write_text(antes.replace(original, mutado, 1), encoding="utf-8")
        assert _rodar(teste) != 0, f"a trava `{nome}` não sustenta nenhum teste"
    finally:
        caminho.write_text(antes, encoding="utf-8")


def test_a_ordem_do_passe_sustenta_um_teste():
    """A mutação que não cabe num `replace`: mover o passe para DEPOIS do laço de perguntas.

    Era o estado em que a suíte ficava 100% verde e o componente recebia as perguntas do papel
    provisório com o papel confirmado ao lado. A ordem entre `identificar` e `responder` não é
    propriedade de nenhum dos dois, então nenhum teste de unidade a pega.
    """
    caminho = RAIZ / "scripts" / "collect.py"
    antes = caminho.read_text(encoding="utf-8")
    inicio = antes.index("    passe = identificar(")
    laco = '    for componente in registro["componentes"]:\n        responder('
    bloco = antes[inicio:antes.index(laco)]
    try:
        depois = antes.replace(bloco, "", 1)
        linha = "        responder(componente, contexto, adaptadores, prazo)\n"
        caminho.write_text(depois.replace(linha, linha + bloco, 1), encoding="utf-8")
        assert _rodar("tests/test_ciclo_ponta_a_ponta.py") != 0, \
            "o passe pode rodar depois das perguntas e nenhum teste reclama"
    finally:
        caminho.write_text(antes, encoding="utf-8")
