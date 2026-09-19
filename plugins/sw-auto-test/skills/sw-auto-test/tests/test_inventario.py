# tests/test_inventario.py
from lib import inventario
from projeto import projeto_phpunit, projeto_pytest, projeto_vitest


def test_conta_arquivos_e_testes_do_projeto_python(repo):
    projeto_pytest(repo)

    dados = inventario.varrer(repo.path)

    assert dados["arquivos"] == 2
    assert dados["testes"] == 5
    assert dados["por_suite"] == {"unit": 5}


def test_classifica_a_suite_pelo_caminho(repo):
    repo.escrever({
        "tests/unit/test_a.py": "def test_a():\n    assert 1\n",
        "tests/Integration/test_b.py": "def test_b():\n    assert 1\n",
        "e2e/compra.spec.ts": "it('compra', () => { expect(1).toBe(1); });\n",
        "tests/test_solto.py": "def test_c():\n    assert 1\n",
    })
    repo.commit("chore: suites")

    dados = inventario.varrer(repo.path)

    assert dados["por_suite"] == {"unit": 1, "integracao": 1, "e2e": 1, "desconhecida": 1}


def test_ignora_dependencias_e_artefatos(repo):
    projeto_vitest(repo)
    repo.escrever({
        "node_modules/lib/x.test.ts": "it('x', () => {});\n",
        "coverage/relatorio.test.ts": "it('y', () => {});\n",
    })

    dados = inventario.varrer(repo.path)

    assert [a["caminho"] for a in dados["lista"]] == ["tests/unit/carrinho.test.ts"]


def test_php_conta_metodos_de_teste(repo):
    projeto_phpunit(repo)

    dados = inventario.varrer(repo.path)

    assert dados["testes"] == 3
    assert dados["por_suite"] == {"unit": 3}


def test_escopo_limita_a_varredura_a_um_pacote(repo):
    repo.escrever({
        "packages/api/tests/unit/test_a.py": "def test_a():\n    assert 1\n",
        "packages/web/tests/unit/b.test.ts": "it('b', () => { expect(1).toBe(1); });\n",
    })
    repo.commit("chore: monorepo")

    dados = inventario.varrer(repo.path / "packages/api")

    assert dados["arquivos"] == 1
    assert dados["lista"][0]["caminho"] == "tests/unit/test_a.py"


def test_projeto_go_nao_some_do_inventario(repo):
    repo.escrever({"go.mod": "module exemplo\n",
                   "interno/soma_test.go": "func TestSoma(t *testing.T) {\n    t.Error(\"x\")\n}\n"})
    repo.commit("chore: go")

    dados = inventario.varrer(repo.path)

    assert dados["arquivos"] == 1 and dados["testes"] == 1
