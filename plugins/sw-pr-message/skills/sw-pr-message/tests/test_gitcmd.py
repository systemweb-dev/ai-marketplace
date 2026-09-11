from pathlib import Path

import pytest

from gitrepo import Repo
from lib import gitcmd
from lib.gitcmd import (MIN_VERSAO, GitFalhou, GitRecusado, ambiente, caminho_git, git, git_ok,
                        montar_argv, validar_ref, versao)


@pytest.fixture
def sem_execucao(monkeypatch):
    """Qualquer tentativa de executar processo falha o teste: a recusa tem que vir antes."""
    def proibido(*args, **kwargs):
        raise AssertionError(f"executou processo: {args}")
    monkeypatch.setattr(gitcmd.subprocess, "run", proibido)


@pytest.mark.parametrize("args", [
    ["push"], ["config", "user.name", "x"], ["-c", "core.pager=cat", "log"],
    ["--exec-path=/tmp", "log"], ["update-ref", "refs/heads/x", "HEAD"], [],
    ["status", "--porcelain"],  # para comparar conteúdo, executaria filtros de limpeza da config
])
def test_recusa_subcomando_fora_da_lista_e_opcao_antes_dele(args, sem_execucao):
    with pytest.raises(GitRecusado):
        git(args, ".")


@pytest.mark.parametrize("args", [
    ["diff", "--output=/tmp/x"], ["log", "--output", "/tmp/x"], ["diff", "--no-index", "a", "b"],
    ["diff", "--ext-diff"], ["log", "--end-of-options", "--output=/tmp/x..HEAD"],
    ["diff", "--end-of-options", "--output=/tmp/x...HEAD"],
    # reativariam, depois das defesas, o que elas desligam
    ["diff", "--textconv"], ["log", "--show-signature"], ["diff", "--submodule=diff"],
])
def test_recusa_argumento_proibido_por_prefixo_em_qualquer_posicao(args, sem_execucao):
    with pytest.raises(GitRecusado):
        git(args, ".")


@pytest.mark.parametrize("args", [
    ["symbolic-ref", "HEAD", "refs/heads/novo"], ["symbolic-ref", "-d", "HEAD"],
    ["symbolic-ref", "-m", "msg", "HEAD", "refs/heads/x"], ["symbolic-ref"],
])
def test_symbolic_ref_so_na_forma_de_leitura(args, sem_execucao):
    with pytest.raises(GitRecusado):
        git(args, ".")


def test_version_nao_aceita_argumentos(sem_execucao):
    with pytest.raises(GitRecusado):
        git(["version", "--build-options"], ".")


@pytest.mark.parametrize("ref", ["-x", "--output=/tmp/x", "", "   "])
def test_ref_externa_que_parece_opcao_e_recusada(ref):
    with pytest.raises(GitRecusado):
        validar_ref(ref)


def test_ref_externa_normal_passa():
    assert validar_ref("origin/develop") == "origin/develop"


def test_defesas_sao_injetadas_logo_apos_o_subcomando():
    assert montar_argv(["diff", "--numstat"]) == \
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--submodule=short", "--numstat"]
    assert montar_argv(["log", "--oneline"])[:7] == \
        ["git", "log", "--no-ext-diff", "--no-textconv", "--no-color", "--no-show-signature", "--submodule=short"]
    assert montar_argv(["symbolic-ref", "-q", "--short", "HEAD"]) == \
        ["git", "symbolic-ref", "-q", "--short", "HEAD"]


def test_ambiente_desliga_locks_opcionais_e_fsmonitor():
    env = ambiente()

    assert env["GIT_OPTIONAL_LOCKS"] == "0"
    assert (env["GIT_CONFIG_COUNT"], env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]) == \
        ("1", "core.fsmonitor", "false")


def test_ambiente_descarta_variaveis_herdadas_que_desviariam_o_git(repo, tmp_path, monkeypatch):
    outro = Repo.novo(tmp_path / "outro")
    monkeypatch.setenv("GIT_DIR", str(outro.path / ".git"))
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'core.fsmonitor'='false'")

    env = ambiente()
    git_dir = Path(git(["rev-parse", "--absolute-git-dir"], repo.path).strip())

    herdadas = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_PARAMETERS", "GIT_EXTERNAL_DIFF"}
    assert herdadas.isdisjoint(env)
    # prova que o ambiente limpo chega ao processo: com GIT_DIR herdado, leria o outro repo
    assert git_dir == (repo.path / ".git").resolve()


def test_submodulo_nao_executa_diff_externo_da_config(repo, tmp_path):
    marca = tmp_path / "rodou"
    script = tmp_path / "ext.sh"
    script.write_text(f"#!/bin/sh\ntouch '{marca}'\n", encoding="utf-8")
    script.chmod(0o755)
    origem = Repo.novo(tmp_path / "origem-do-sub")
    permitir = ("-c", "protocol.file.allow=always")
    repo.git(*permitir, "submodule", "add", "-q", str(origem.path), "sub")
    repo.git("commit", "-q", "-m", "chore: submódulo")
    origem.commit("feat: muda o submódulo")
    repo.git(*permitir, "submodule", "update", "--remote", "-q", "sub")
    repo.git("commit", "-qam", "chore: atualiza submódulo")
    repo.git("config", "diff.submodule", "diff")
    Repo(repo.path / "sub").git("config", "diff.external", str(script))

    git(["diff", "--end-of-options", "HEAD~1...HEAD", "--", "sub"], repo.path)
    git(["log", "-p", "-1"], repo.path)

    assert not marca.exists()


def test_executa_leitura_num_repositorio_real(repo):
    assert Path(git(["rev-parse", "--show-toplevel"], repo.path).strip()) == repo.path.resolve()
    assert git_ok(["ls-files", "--error-unmatch", "--", "README.md"], repo.path) is True
    assert git_ok(["ls-files", "--error-unmatch", "--", "nao-existe"], repo.path) is False


def test_falha_do_git_vira_excecao_com_codigo(repo):
    with pytest.raises(GitFalhou) as erro:
        git(["rev-list", "--end-of-options", "ref-que-nao-existe"], repo.path)

    assert erro.value.codigo != 0


def test_caminho_git_resolve_repo_normal_e_worktree(repo, tmp_path):
    wt = tmp_path / "wt"
    repo.git("worktree", "add", "-q", str(wt), "-b", "outra")

    assert caminho_git(repo.path, "sw-pr-message") == (repo.path / ".git" / "sw-pr-message").resolve()
    assert caminho_git(wt, "info/exclude") == (repo.path / ".git" / "info" / "exclude").resolve()


def test_versao_atende_o_minimo(repo):
    assert versao(repo.path) >= MIN_VERSAO


def test_ambiente_proibe_busca_preguicosa_de_objetos():
    # em clone parcial, o diff buscaria do remoto os arquivos que faltam — rede e escrita em .git/objects
    assert ambiente()["GIT_NO_LAZY_FETCH"] == "1"
