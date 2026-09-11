import subprocess

import pytest

from gitrepo import ENV
from lib import base
from lib.base import Parada, detectar_base, pre_checar
from lib.gitcmd import GitRecusado


def feature_de_develop(repo):
    """master ← develop (+1) ← feature/x (+1). Contagens: develop 1, master 2."""
    repo.branch("develop")
    repo.commit("feat: base do develop")
    repo.branch("feature/x")
    repo.commit("feat: trabalho da feature")


def develop_local_atrasado(repo):
    """develop local em A; origin/develop em B, à frente; feature/x saiu de origin/develop."""
    repo.branch("develop")
    repo.commit("feat: A")
    repo.branch("tmp")
    repo.commit("feat: B")
    repo.ref_remota("develop")
    repo.branch("feature/x")
    repo.git("branch", "-D", "tmp")
    repo.commit("feat: F")


def test_feature_de_develop_com_master_presente_escolhe_develop(repo):
    feature_de_develop(repo)

    b = detectar_base(repo.path)

    assert (b["nome"], b["ref"], b["como"], b["a_frente"]) == ("develop", "refs/heads/develop", "heuristica", 1)
    assert b["candidatas"] == {"develop": 1, "master": 2}


def test_candidato_que_ja_contem_a_branch_para_e_lista_contagens(repo):
    feature_de_develop(repo)
    repo.git("branch", "staging")

    with pytest.raises(Parada) as parada:
        detectar_base(repo.path)

    msg = str(parada.value)
    assert "staging já contém a branch" in msg
    assert "develop: 1" in msg and "master: 2" in msg
    assert "--base develop" in msg


def test_arquivo_ou_pasta_com_nome_de_candidato_nao_esconde_a_branch(repo):
    feature_de_develop(repo)
    repo.git("branch", "staging")
    (repo.path / "develop").write_text("arquivo solto com nome de branch\n", encoding="utf-8")
    (repo.path / "staging").mkdir()
    (repo.path / "staging" / "x.txt").write_text("x\n", encoding="utf-8")

    with pytest.raises(Parada, match="staging já contém a branch"):
        detectar_base(repo.path)


def test_tag_com_nome_de_candidato_nao_vira_candidata(repo):
    repo.git("tag", "main")
    repo.branch("feature/x")
    repo.commit("feat: x")

    b = detectar_base(repo.path)

    assert "main" not in b["candidatas"]
    assert b["nome"] == "master"


def test_empate_resolvido_pela_branch_padrao(repo):
    repo.git("branch", "main")
    repo.ref_remota("master")
    repo.origin_head("master")
    repo.branch("feature/x")
    repo.commit("feat: x")

    assert detectar_base(repo.path)["nome"] == "master"


def test_empate_sem_branch_padrao_prefere_main(repo):
    repo.git("branch", "main")
    repo.branch("feature/x")
    repo.commit("feat: x")

    assert detectar_base(repo.path)["nome"] == "main"


def test_empate_sem_padrao_nem_main_master_para(repo):
    repo.git("branch", "develop")
    repo.git("branch", "trunk")
    repo.branch("feature/x", "develop")
    repo.git("branch", "-D", "master")
    repo.commit("feat: x")

    with pytest.raises(Parada, match="Empate entre develop, trunk"):
        detectar_base(repo.path)


def test_branch_padrao_fora_da_lista_entra_como_candidata(repo):
    repo.git("branch", "-m", "master", "production")
    repo.ref_remota("production")
    repo.origin_head("production")
    repo.branch("feature/x")
    repo.commit("feat: x")

    assert detectar_base(repo.path)["nome"] == "production"


def test_develop_local_atrasado_perde_para_origin_develop_na_heuristica(repo):
    develop_local_atrasado(repo)

    b = detectar_base(repo.path)

    assert (b["nome"], b["ref"], b["a_frente"]) == ("develop", "refs/remotes/origin/develop", 1)


def test_develop_local_atrasado_perde_para_origin_develop_com_base_informada(repo):
    develop_local_atrasado(repo)

    b = detectar_base(repo.path, "develop")

    assert (b["ref"], b["como"], b["a_frente"]) == ("refs/remotes/origin/develop", "informada", 1)


def test_base_informada_com_prefixo_origin_e_normalizada(repo):
    develop_local_atrasado(repo)

    b = detectar_base(repo.path, "origin/develop")

    assert (b["nome"], b["ref"], b["a_frente"]) == ("develop", "refs/remotes/origin/develop", 1)


def test_base_informada_vence_a_heuristica(repo):
    feature_de_develop(repo)

    b = detectar_base(repo.path, "master")

    assert (b["nome"], b["como"], b["a_frente"]) == ("master", "informada", 2)


def test_base_informada_inexistente_para(repo):
    feature_de_develop(repo)

    with pytest.raises(Parada, match="não existe localmente"):
        detectar_base(repo.path, "release/9.9")


def test_base_informada_sem_commits_a_frente_para(repo):
    feature_de_develop(repo)
    repo.git("branch", "staging")

    with pytest.raises(Parada, match="não tem commits à frente"):
        detectar_base(repo.path, "staging")


def test_nenhum_candidato_existe_pede_base(repo):
    repo.git("branch", "-m", "master", "principal")
    repo.branch("feature/x")
    repo.commit("feat: x")

    with pytest.raises(Parada, match="Informe --base"):
        detectar_base(repo.path)


def test_base_que_parece_opcao_e_recusada(repo):
    feature_de_develop(repo)

    with pytest.raises(GitRecusado):
        detectar_base(repo.path, "--output=/tmp/x")


def test_pre_checagem_fora_de_repositorio(tmp_path):
    with pytest.raises(Parada, match="Não é um repositório git"):
        pre_checar(tmp_path, tem_base=False)


def test_pre_checagem_repositorio_bare(tmp_path):
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], env=ENV, check=True)

    with pytest.raises(Parada, match="Não é um repositório git"):
        pre_checar(bare, tem_base=False)


def test_pre_checagem_git_antigo(repo, monkeypatch):
    monkeypatch.setattr(base, "versao", lambda *a, **k: (2, 20))

    with pytest.raises(Parada, match="ou mais novo"):
        pre_checar(repo.path, tem_base=False)


def test_pre_checagem_clone_raso(repo, tmp_path):
    repo.commit("feat: segundo")
    raso = tmp_path / "raso"
    repo.git("clone", "-q", "--depth", "1", "--no-local", f"file://{repo.path}", str(raso))

    with pytest.raises(Parada, match="Clone raso"):
        pre_checar(raso, tem_base=False)


def test_pre_checagem_head_destacado(repo):
    repo.git("checkout", "-q", "--detach")

    with pytest.raises(Parada, match="HEAD destacado"):
        pre_checar(repo.path, tem_base=False)


def test_pre_checagem_rebase_em_andamento(repo):
    repo.branch("c1")
    repo.commit("feat: um", {"conflito.txt": "um\n"})
    repo.branch("c2", "master")
    repo.commit("feat: dois", {"conflito.txt": "dois\n"})
    repo.git("rebase", "c1", check=False)

    with pytest.raises(Parada, match="Rebase em andamento"):
        pre_checar(repo.path, tem_base=False)


def test_pre_checagem_em_develop_sem_base_para(repo):
    repo.branch("develop")
    repo.commit("feat: d")

    with pytest.raises(Parada, match="que é uma branch base"):
        pre_checar(repo.path, tem_base=False)


def test_pre_checagem_em_branch_padrao_fora_da_lista_para(repo):
    repo.git("branch", "-m", "master", "production")
    repo.ref_remota("production")
    repo.origin_head("production")

    with pytest.raises(Parada, match="que é uma branch base"):
        pre_checar(repo.path, tem_base=False)


def test_em_develop_com_base_master_segue_como_pr_de_release(repo):
    repo.branch("develop")
    repo.commit("feat: d")

    atual = pre_checar(repo.path, tem_base=True)
    b = detectar_base(repo.path, "master")

    assert atual == "develop"
    assert (b["nome"], b["a_frente"]) == ("master", 1)


def test_empate_fica_registrado_na_base_escolhida(repo):
    repo.git("branch", "develop")
    repo.branch("fix/checkout")
    repo.commit("fix: um")

    b = detectar_base(repo.path)

    assert (b["nome"], b["empate"]) == ("master", ["develop", "master"])


def test_pre_checagem_clone_parcial(repo, tmp_path):
    repo.commit("feat: segundo", {"dados.txt": "conteúdo\n"})
    repo.git("config", "uploadpack.allowfilter", "true")
    parcial = tmp_path / "parcial"
    repo.git("clone", "-q", "--filter=blob:none", "--no-local", f"file://{repo.path}", str(parcial))
    assert list((parcial / ".git" / "objects" / "pack").glob("*.promisor")), "o clone não saiu parcial (ambiente)"

    with pytest.raises(Parada, match="Clone parcial"):
        pre_checar(parcial, tem_base=False)
