from gitrepo import Repo
from projeto import projeto_phpunit, projeto_pytest, projeto_vitest
from runners import chamadas, instalar


def test_repo_nasce_em_master_com_um_commit(repo):
    assert repo.git("branch", "--show-current").strip() == "master"
    assert repo.git("rev-list", "--count", "HEAD").strip() == "1"


def test_projetos_fixture_ficam_versionados(repo):
    projeto_pytest(repo)

    assert (repo.path / "tests/unit/test_problemas.py").exists()
    assert repo.git("status", "--porcelain").strip() == ""


def test_runner_falso_responde_e_registra_a_chamada(tmp_path, monkeypatch):
    import subprocess

    registro = instalar(tmp_path, monkeypatch, "pytest", {
        "--collect-only": ("tests/unit/test_a.py::test_x\n", None, None, 0),
        "__padrao__": ("1 passed\n", None, None, 0),
    })

    saida = subprocess.run(["pytest", "--collect-only", "-q"], capture_output=True, text=True)

    assert saida.stdout == "tests/unit/test_a.py::test_x\n"
    assert chamadas(registro) == ["pytest --collect-only -q"]


def test_runner_falso_so_registra_quando_e_chamado(tmp_path, monkeypatch):
    import shutil
    import subprocess

    registro = instalar(tmp_path, monkeypatch, "vitest", {"__padrao__": ("ok\n", None, None, 0)})

    assert shutil.which("vitest"), "o runner falso precisa estar no PATH"
    assert chamadas(registro) == []

    subprocess.run(["vitest", "run"], capture_output=True, text=True)

    assert chamadas(registro) == ["vitest run"]


def test_projetos_js_e_php_montam_os_testes_esperados(repo, tmp_path):
    from lib import sinais

    projeto_vitest(repo)
    outro = projeto_phpunit(Repo.novo(tmp_path / "php"))

    js = (repo.path / "tests/unit/carrinho.test.ts").read_text(encoding="utf-8")
    php = (outro.path / "tests/Unit/CarrinhoTest.php").read_text(encoding="utf-8")

    assert [bloco[0] for bloco in sinais.blocos(js)] == [
        "desligado", "sem assercao", "usa relogio real", "nome repetido", "nome repetido"]
    assert [bloco[0] for bloco in sinais.blocos(php)] == [
        "test_sem_assercao", "test_pulado", "test_rede"]
