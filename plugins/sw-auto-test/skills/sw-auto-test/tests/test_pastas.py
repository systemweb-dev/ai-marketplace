# tests/test_pastas.py
import tempfile
from pathlib import Path

from lib import pastas


def test_com_git_grava_dentro_do_diretorio_do_git(repo):
    base = pastas.base(repo.path)

    assert base == (repo.path / ".git" / "sw-auto-test").resolve()
    assert pastas.fatos(repo.path).name == "fatos.json"
    assert pastas.achados(repo.path).name == "achados.json"
    assert pastas.backups(repo.path).parent == base
    assert pastas.saida(repo.path).parent == base


def test_sem_git_cai_no_temporario_do_sistema_por_caminho(tmp_path):
    solto = tmp_path / "sem-git"
    solto.mkdir()

    base = pastas.base(solto)

    assert base.parent == Path(tempfile.gettempdir())
    assert base.name.startswith("sw-auto-test-")
    assert pastas.base(solto) == base, "o mesmo projeto precisa cair sempre na mesma pasta"


def test_projetos_diferentes_nao_compartilham_pasta(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()

    assert pastas.base(a) != pastas.base(b)


def test_criar_faz_a_pasta_existir(repo):
    destino = pastas.criar(repo.path)

    assert destino.is_dir()
