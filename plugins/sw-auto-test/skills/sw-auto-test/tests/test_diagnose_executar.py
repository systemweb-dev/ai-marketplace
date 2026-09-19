# tests/test_diagnose_executar.py
import json
import os
import stat
from pathlib import Path

import diagnose
from lib import pastas
from projeto import projeto_phpunit, projeto_pytest, projeto_vitest
from runners import chamadas, instalar

JUNIT_OK = """<?xml version="1.0"?>
<testsuites><testsuite name="pytest" tests="2" failures="0" skipped="0" time="3">
  <testcase classname="tests.unit.test_calculadora" name="test_soma_dois_numeros" time="0.01"/>
  <testcase classname="tests.unit.test_problemas" name="test_lento" time="4.5"/>
</testsuite></testsuites>
"""

COBERTURA_OK = """<?xml version="1.0"?>
<coverage><packages><package><classes>
  <class filename="src/calculadora.py" line-rate="0.9" branch-rate="1.0"/>
</classes></package></packages></coverage>
"""

DESCOBERTA = ("tests/unit/test_calculadora.py::test_soma_dois_numeros\n"
              "tests/unit/test_problemas.py::test_lento\n")


def pytest_falso(tmp_path, monkeypatch, descoberta=DESCOBERTA):
    return instalar(tmp_path, monkeypatch, "pytest", {
        "--collect-only": (descoberta, None, None, 0),
        "--junit-xml": ("2 passed\n", "junit.xml", JUNIT_OK, 0),
        "__padrao__": ("", None, None, 0),
    })


def fatos_de(repo):
    return json.loads(pastas.fatos(repo.path).read_text(encoding="utf-8"))


def rodar(repo, *args):
    return diagnose.main(["--repo", str(repo.path), *args])


def test_executar_roda_descoberta_e_suite_e_preenche_os_fatos(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    registro = pytest_falso(tmp_path, monkeypatch)

    assert rodar(repo, "--executar") == 0
    fatos = fatos_de(repo)

    assert [c.split()[1] for c in chamadas(registro)] == ["--collect-only", "-q"]  # descoberta primeiro
    assert fatos["execucao"]["rodou"] is True
    assert (fatos["execucao"]["passou"], fatos["execucao"]["falhou"]) == (2, 0)
    assert fatos["execucao"]["verde"] is True
    assert fatos["execucao"]["duracao_faixa"] == "1-10s"


def test_banco_no_ambiente_barra_antes_de_qualquer_execucao(repo, tmp_path, monkeypatch, capsys):
    projeto_pytest(repo)
    registro = pytest_falso(tmp_path, monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgres://usuario@host/banco")

    codigo = rodar(repo, "--executar")

    assert codigo == 2
    assert chamadas(registro) == [], "nem a descoberta pode rodar: a coleta importa conftest"
    erro = capsys.readouterr().err
    assert "DATABASE_URL" in erro and "--banco-ok" in erro


def test_com_banco_ok_a_execucao_segue(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    registro = pytest_falso(tmp_path, monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgres://usuario@host/banco")

    assert rodar(repo, "--executar", "--banco-ok") == 0
    assert len(chamadas(registro)) == 2


def test_env_de_banco_no_arquivo_do_projeto_tambem_barra(repo, tmp_path, monkeypatch, capsys):
    projeto_pytest(repo)
    repo.escrever({".env.testing": "DB_HOST=127.0.0.1\nDB_DATABASE=loja\n"})
    pytest_falso(tmp_path, monkeypatch)

    assert rodar(repo, "--executar") == 2
    assert ".env.testing" in capsys.readouterr().err


def test_timeout_vira_achado_e_a_skill_continua(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    pasta = tmp_path / "bin"
    pasta.mkdir(exist_ok=True)
    lento = pasta / "pytest"
    lento.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    lento.chmod(lento.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{pasta}{os.pathsep}{os.environ['PATH']}")

    assert rodar(repo, "--executar", "--timeout", "1") == 0
    fatos = fatos_de(repo)

    assert fatos["execucao"]["timeout"] is True
    assert fatos["execucao"]["verde"] is None
    assert any(s["regra"] == "execucao_estourou" for s in fatos["sinais"])


def test_arquivo_que_o_runner_nao_descobre_vira_sinal(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    pytest_falso(tmp_path, monkeypatch,
                 descoberta="tests/unit/test_calculadora.py::test_soma_dois_numeros\n")

    rodar(repo, "--executar")
    fatos = fatos_de(repo)

    orfaos = [s for s in fatos["sinais"] if s["regra"] == "nao_descoberto"]
    assert [s["caminho"] for s in orfaos] == ["tests/unit/test_problemas.py"]


def test_teste_lento_para_o_tipo_vira_sinal(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    pytest_falso(tmp_path, monkeypatch)

    rodar(repo, "--executar")
    fatos = fatos_de(repo)

    lentos = [s for s in fatos["sinais"] if s["regra"] == "lento_para_o_tipo"]
    assert lentos and "test_lento" in lentos[0]["evidencia"]


def test_cobertura_entra_nos_fatos_quando_pedida(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    instalar(tmp_path, monkeypatch, "pytest", {
        "--collect-only": (DESCOBERTA, None, None, 0),
        "--cov-report": ("2 passed\n", "cobertura.xml", COBERTURA_OK, 0),
        "__padrao__": ("", None, None, 0),
    })

    rodar(repo, "--executar", "--cobertura")
    fatos = fatos_de(repo)

    assert fatos["cobertura"]["disponivel"] is True
    assert fatos["cobertura"]["ferramenta"] == "pytest"
    assert fatos["cobertura"]["por_arquivo"] == [{"caminho": "src/calculadora.py",
                                                  "linhas_pct": 90, "ramos_pct": 100}]


def test_stack_sem_modulo_nativo_nao_executa_e_avisa(repo, capsys):
    repo.escrever({"go.mod": "module exemplo\n",
                   "interno/soma_test.go": "func TestSoma(t *testing.T) { t.Error(\"x\") }\n"})
    repo.commit("chore: go")

    assert rodar(repo, "--executar") == 0
    fatos = fatos_de(repo)

    assert fatos["execucao"]["rodou"] is False
    assert "heurístico" in capsys.readouterr().out


VITEST_JSON_OK = json.dumps({
    "testResults": [{"name": "/app/tests/unit/carrinho.test.ts", "assertionResults": [
        {"fullName": "soma itens", "status": "passed", "duration": 5}]}]})


def test_runner_ausente_nao_vira_suite_ilegivel(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))

    assert rodar(repo, "--executar") == 0
    fatos = fatos_de(repo)

    assert fatos["execucao"]["rodou"] is False
    assert any(s["regra"] == "runner_ausente" for s in fatos["sinais"])


def test_codigo_de_saida_do_runner_conta_para_o_verde(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    instalar(tmp_path, monkeypatch, "pytest", {
        "--collect-only": (DESCOBERTA, None, None, 0),
        "--junit-xml": ("bootstrap quebrou\n", "junit.xml", JUNIT_OK, 2),
        "__padrao__": ("", None, None, 0)})

    rodar(repo, "--executar")

    assert fatos_de(repo)["execucao"]["verde"] is False, \
        "junit sem falha, mas o runner saiu com erro: não é verde"


def test_ambiente_da_execucao_fica_registrado_nos_fatos(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    pytest_falso(tmp_path, monkeypatch)

    rodar(repo, "--executar", "--cobertura")
    ambiente = fatos_de(repo)["execucao"]["ambiente"]

    assert ambiente["CI"] == "1"
    assert ambiente["COVERAGE_FILE"].endswith("sw-auto-test/saida/.coverage"), \
        "o coverage precisa gravar dentro da pasta de fatos, não no projeto"


def test_vitest_nao_gera_nao_descoberto_em_massa(repo, tmp_path, monkeypatch):
    projeto_vitest(repo)
    instalar(tmp_path, monkeypatch, "vitest", {
        "list": ("tests/unit/carrinho.test.ts > carrinho > soma\n", None, None, 0),
        "--reporter=json": ("", "vitest.json", VITEST_JSON_OK, 0),
        "__padrao__": ("", None, None, 0)})

    rodar(repo, "--executar")

    assert [s for s in fatos_de(repo)["sinais"] if s["regra"] == "nao_descoberto"] == []


def test_phpunit_nao_gera_nao_descoberto(repo, tmp_path, monkeypatch):
    projeto_phpunit(repo)
    instalar(tmp_path, monkeypatch, "phpunit", {
        "--list-tests": (" - CarrinhoTest::test_sem_assercao\n", None, None, 0),
        "junit.xml": ("", "junit.xml", JUNIT_OK, 0),
        "__padrao__": ("", None, None, 0)})

    rodar(repo, "--executar")

    assert [s for s in fatos_de(repo)["sinais"] if s["regra"] == "nao_descoberto"] == []


def test_banco_declarado_no_phpunit_xml_tambem_barra(repo, tmp_path, monkeypatch, capsys):
    projeto_phpunit(repo)
    repo.escrever({"phpunit.xml": "<phpunit><php><env name='DB_DATABASE' value='loja'/></php></phpunit>\n"})
    registro = instalar(tmp_path, monkeypatch, "phpunit", {"__padrao__": ("", None, None, 0)})

    assert rodar(repo, "--executar") == 2
    assert "phpunit.xml" in capsys.readouterr().err
    assert chamadas(registro) == []
