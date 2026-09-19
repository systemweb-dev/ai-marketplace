# tests/test_stacks_base.py
from lib.stacks import base

JUNIT = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="pytest" tests="4" failures="1" skipped="1" time="12.5">
    <testcase classname="tests.unit.test_a" name="test_rapido" time="0.01"/>
    <testcase classname="tests.unit.test_a" name="test_lento" time="7.2"/>
    <testcase classname="tests.unit.test_b" name="test_quebrado" time="0.4">
      <failure message="esperava 4">assert 3 == 4</failure>
    </testcase>
    <testcase classname="tests.unit.test_b" name="test_pulado" time="0">
      <skipped message="instavel"/>
    </testcase>
  </testsuite>
</testsuites>
"""

COBERTURA = """<?xml version="1.0"?>
<coverage>
  <packages><package><classes>
    <class filename="src/calculadora.py" line-rate="0.8" branch-rate="0.5"/>
    <class filename="src/pagamento.py" line-rate="0.1" branch-rate="0.0"/>
  </classes></package></packages>
</coverage>
"""

CLOVER = """<?xml version="1.0"?>
<coverage><project>
  <file name="/app/src/Carrinho.php">
    <metrics statements="10" coveredstatements="9" conditionals="4" coveredconditionals="1"/>
  </file>
</project></coverage>
"""


def test_le_junit_com_contagens_e_duracoes(tmp_path):
    arquivo = tmp_path / "junit.xml"
    arquivo.write_text(JUNIT, encoding="utf-8")

    resultado = base.ler_junit(arquivo)

    assert (resultado["passou"], resultado["falhou"], resultado["pulado"]) == (2, 1, 1)
    assert resultado["verde"] is False
    assert resultado["duracao_faixa"] == "10-60s"
    assert resultado["lentos"] == [{"teste": "tests.unit.test_a::test_lento", "faixa": "1-10s"}]


def test_junit_sem_falha_e_verde(tmp_path):
    arquivo = tmp_path / "junit.xml"
    arquivo.write_text(JUNIT.replace('<failure message="esperava 4">assert 3 == 4</failure>', "")
                            .replace('failures="1"', 'failures="0"'), encoding="utf-8")

    assert base.ler_junit(arquivo)["verde"] is True


def test_le_cobertura_formato_cobertura(tmp_path):
    arquivo = tmp_path / "cobertura.xml"
    arquivo.write_text(COBERTURA, encoding="utf-8")

    linhas = base.ler_cobertura_xml(arquivo)

    assert linhas == [{"caminho": "src/calculadora.py", "linhas_pct": 80, "ramos_pct": 50},
                      {"caminho": "src/pagamento.py", "linhas_pct": 10, "ramos_pct": 0}]


def test_le_cobertura_formato_clover_com_caminho_relativo(tmp_path):
    arquivo = tmp_path / "clover.xml"
    arquivo.write_text(CLOVER, encoding="utf-8")

    linhas = base.ler_clover(arquivo, raiz="/app")

    assert linhas == [{"caminho": "src/Carrinho.php", "linhas_pct": 90, "ramos_pct": 25}]


def test_arquivo_ausente_ou_corrompido_nao_explode(tmp_path):
    quebrado = tmp_path / "junit.xml"
    quebrado.write_text("<testsuites", encoding="utf-8")

    assert base.ler_junit(tmp_path / "nao-existe.xml") is None
    assert base.ler_junit(quebrado) is None
    assert base.ler_cobertura_xml(quebrado) == []


def test_faixas_de_duracao_sao_as_do_spec():
    assert [base.faixa(s) for s in (0.4, 5, 30, 200, 900)] == \
        ["<1s", "1-10s", "10-60s", "1-5min", ">5min"]
