# tests/test_gitinfo.py
from pathlib import Path

import pytest

from lib.gitinfo import GitIndisponivel, branch, dentro_de_repo, head, limpo, rastreado, toplevel, git_path


def test_reconhece_repositorio_e_devolve_a_raiz(repo):
    assert dentro_de_repo(repo.path) is True
    assert toplevel(repo.path) == repo.path.resolve()


def test_fora_de_repositorio_responde_falso(tmp_path):
    solto = tmp_path / "sem-git"
    solto.mkdir()

    assert dentro_de_repo(solto) is False
    with pytest.raises(GitIndisponivel):
        toplevel(solto)


def test_branch_e_head(repo):
    assert branch(repo.path) == "master"
    assert len(head(repo.path)) == 40


def test_git_path_funciona_tambem_em_worktree(repo, tmp_path):
    wt = tmp_path / "wt"
    repo.git("worktree", "add", "-q", str(wt), "-b", "outra")

    assert git_path(repo.path, "sw-auto-test") == (repo.path / ".git" / "sw-auto-test").resolve()
    assert git_path(wt, "info/exclude") == (repo.path / ".git" / "info" / "exclude").resolve()


def test_limpo_distingue_arquivo_intocado_de_alterado(repo):
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")

    assert limpo(repo.path, "src/a.py") is True
    (repo.path / "src/a.py").write_text("x = 2\n", encoding="utf-8")
    assert limpo(repo.path, "src/a.py") is False


def test_arquivo_nao_versionado_nao_conta_como_limpo(repo):
    (repo.path / "novo.py").write_text("x = 1\n", encoding="utf-8")

    assert rastreado(repo.path, "novo.py") is False
    assert limpo(repo.path, "novo.py") is False


def test_recusa_subcomando_de_escrita(repo):
    from lib import gitinfo

    with pytest.raises(ValueError):
        gitinfo._git(["commit", "-m", "x"], repo.path)
