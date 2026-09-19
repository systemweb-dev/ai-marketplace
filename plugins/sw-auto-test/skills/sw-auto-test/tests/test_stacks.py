# tests/test_stacks.py
import json
from pathlib import Path

from lib import stacks
from lib.stacks import base

VITEST_JSON = json.dumps({
    "numTotalTests": 3, "numPassedTests": 2, "numFailedTests": 1, "numPendingTests": 0,
    "testResults": [{"name": "/app/tests/unit/carrinho.test.ts", "assertionResults": [
        {"fullName": "soma itens", "status": "passed", "duration": 12},
        {"fullName": "aplica cupom", "status": "passed", "duration": 2300},
        {"fullName": "recusa cupom vencido", "status": "failed", "duration": 8}]}]})


def instancia(runner):
    return stacks.montar(runner)


def test_comandos_do_pytest_gravam_a_saida_na_pasta_de_fatos(tmp_path):
    stack = instancia("pytest")

    descoberta = stack.comando_descoberta(tmp_path / "projeto")
    suite = stack.comando_suite(tmp_path / "projeto", tmp_path / "saida", cobertura=True)

    assert descoberta[:2] == ["pytest", "--collect-only"]
    assert f"--junit-xml={tmp_path / 'saida' / 'junit.xml'}" in suite
    assert f"--cov-report=xml:{tmp_path / 'saida' / 'cobertura.xml'}" in suite
    assert all("--cov-report=html" not in parte for parte in suite), "nada de saída fora da pasta"


def test_pytest_le_a_descoberta_ignorando_rodape(tmp_path):
    stack = instancia("pytest")
    texto = ("tests/unit/test_a.py::test_x\n"
             "tests/unit/test_a.py::test_y\n"
             "\n2 tests collected in 0.01s\n")

    assert stack.ler_descoberta(texto) == ["tests/unit/test_a.py::test_x",
                                           "tests/unit/test_a.py::test_y"]


def test_vitest_le_resultado_do_json_com_lentos(tmp_path):
    stack = instancia("vitest")
    saida = tmp_path / "saida"
    saida.mkdir()
    (saida / "vitest.json").write_text(VITEST_JSON, encoding="utf-8")

    resultado = stack.ler_resultado("", saida, limite_lento=1.0)

    assert (resultado["passou"], resultado["falhou"], resultado["verde"]) == (2, 1, False)
    assert resultado["lentos"] == [{"teste": "aplica cupom", "faixa": "1-10s"}]


def test_jest_usa_flags_proprias_mas_o_mesmo_json(tmp_path):
    stack = instancia("jest")
    suite = stack.comando_suite(tmp_path, tmp_path / "saida", cobertura=True)

    assert "--json" in suite and f"--outputFile={tmp_path / 'saida' / 'jest.json'}" in suite
    assert f"--coverageDirectory={tmp_path / 'saida' / 'cobertura'}" in suite


def test_phpunit_usa_junit_e_clover(tmp_path):
    stack = instancia("phpunit")
    suite = stack.comando_suite(tmp_path, tmp_path / "saida", cobertura=True)

    assert suite[:1] == ["phpunit"]
    assert "--log-junit" in suite and str(tmp_path / "saida" / "junit.xml") in suite
    assert "--coverage-clover" in suite and str(tmp_path / "saida" / "clover.xml") in suite


def test_phpunit_le_lista_de_testes_do_formato_proprio():
    stack = instancia("phpunit")
    texto = ("PHPUnit 11.0.0\n\nAvailable test(s):\n"
             " - CarrinhoTest::test_soma\n - CarrinhoTest::test_cupom\n")

    assert stack.ler_descoberta(texto) == ["CarrinhoTest::test_soma", "CarrinhoTest::test_cupom"]


def test_montar_recusa_runner_desconhecido():
    import pytest

    with pytest.raises(KeyError):
        stacks.montar("mocha")


def test_detectar_devolve_stack_montavel(tmp_path):
    (tmp_path / "phpunit.xml").write_text("<phpunit/>", encoding="utf-8")

    achadas = stacks.detectar(tmp_path)

    assert achadas[0]["runner"] == "phpunit"
    assert isinstance(stacks.montar(achadas[0]["runner"]), base.Stack)


def test_cada_stack_sabe_dizer_o_arquivo_do_id(tmp_path):
    assert instancia("pytest").arquivos(["tests/unit/test_a.py::test_x[com espaço]"], tmp_path) == \
        {"tests/unit/test_a.py"}
    assert instancia("vitest").arquivos(["tests/unit/a.test.ts > carrinho > soma"], tmp_path) == \
        {"tests/unit/a.test.ts"}
    assert instancia("jest").arquivos([str(tmp_path / "tests/unit/a.test.ts")], tmp_path) == \
        {"tests/unit/a.test.ts"}
    assert instancia("phpunit").arquivos(["CarrinhoTest::test_soma"], tmp_path) is None, \
        "phpunit lista classe, não arquivo: a regra de não descoberto não se aplica"


def test_pytest_le_id_parametrizado_com_espaco():
    texto = "tests/unit/test_a.py::test_x[com espaço]\n\n1 test collected in 0.01s\n"

    assert instancia("pytest").ler_descoberta(texto) == ["tests/unit/test_a.py::test_x[com espaço]"]


def test_cobertura_sai_com_caminho_relativo_ao_escopo(tmp_path):
    saida = tmp_path / "saida"
    saida.mkdir()
    (saida / "cobertura.xml").write_text(
        '<?xml version="1.0"?><coverage><packages><package><classes>'
        f'<class filename="{tmp_path}/src/a.py" line-rate="0.5" branch-rate="0.5"/>'
        "</classes></package></packages></coverage>", encoding="utf-8")

    linhas = instancia("pytest").ler_cobertura(saida, tmp_path)

    assert linhas == [{"caminho": "src/a.py", "linhas_pct": 50, "ramos_pct": 50}]


def test_projeto_com_teste_python_sem_arquivo_de_config_ainda_e_reconhecido(tmp_path):
    """Validado em projeto real: suíte pytest rodada por `python -m pytest`, sem pytest.ini."""
    inventario = {"lista": [{"caminho": "tests/test_a.py", "testes": 3, "suite": "unit"}]}

    achadas = stacks.detectar(tmp_path, inventario)

    assert [(s["runner"], s["config"], s["nativo"]) for s in achadas] == [("pytest", None, True)]


def test_config_encontrada_tem_prioridade_sobre_o_palpite(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    inventario = {"lista": [{"caminho": "tests/test_a.py", "testes": 1, "suite": "unit"}]}

    achadas = stacks.detectar(tmp_path, inventario)

    assert [s["config"] for s in achadas] == ["pytest.ini"]


def test_js_sem_config_nem_manifesto_nao_e_chutado(tmp_path):
    """Entre vitest e jest não dá para adivinhar: melhor cair no caminho heurístico."""
    inventario = {"lista": [{"caminho": "tests/unit/a.test.ts", "testes": 1, "suite": "unit"}]}

    assert stacks.detectar(tmp_path, inventario) == []
