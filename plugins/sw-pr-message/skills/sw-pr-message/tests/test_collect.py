import json

import collect
from lib.gitcmd import caminho_git


def ler_fatos(repo):
    return json.loads((caminho_git(repo.path, "sw-pr-message") / "fatos.json").read_text(encoding="utf-8"))


def test_grava_fatos_no_git_path_com_o_esquema_do_spec(repo, capsys):
    repo.branch("develop")
    repo.commit("feat: base")
    repo.branch("feature/x")
    sha = repo.commit("feat: tela", {"tela.py": "x = 1\n"})

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_OK

    fatos = ler_fatos(repo)
    assert set(fatos) == {"branch", "base", "hotfix", "stats", "commits", "arquivos", "avisos"}
    assert fatos["branch"] == "feature/x"
    assert (fatos["base"]["nome"], fatos["base"]["a_frente"]) == ("develop", 1)
    assert [c["hash"] for c in fatos["commits"]] == [sha]
    assert fatos["stats"] == {"arquivos": 1, "insercoes": 1, "delecoes": 0, "ruido": [], "merges_ignorados": 0}
    assert fatos["hotfix"] == {"provavel": False, "sinais": []}
    assert "base: develop (develop) · heuristica · 1 commit(s)" in capsys.readouterr().out


def test_parada_retorna_2_com_mensagem_e_nao_grava(repo, capsys):
    repo.branch("develop")
    repo.commit("feat: d")

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_PARADA

    assert "que é uma branch base" in capsys.readouterr().err
    assert not (caminho_git(repo.path, "sw-pr-message") / "fatos.json").exists()


def test_fora_de_repositorio_retorna_2(tmp_path, capsys):
    assert collect.main(["--repo", str(tmp_path)]) == collect.EXIT_PARADA

    assert "Não é um repositório git" in capsys.readouterr().err


def test_base_que_parece_opcao_e_recusada(repo, capsys):
    repo.branch("feature/x")
    repo.commit("feat: x")

    assert collect.main(["--repo", str(repo.path), "--base=--output=/tmp/x"]) == collect.EXIT_PARADA

    assert "Recusado" in capsys.readouterr().err


def test_hotfix_detectado_pela_branch(repo):
    repo.git("branch", "develop")
    repo.branch("hotfix/pagamento")
    repo.commit("fix: timeout do gateway")

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_OK

    fatos = ler_fatos(repo)
    assert fatos["hotfix"]["provavel"] is True
    assert "branch hotfix/" in fatos["hotfix"]["sinais"]


def test_empate_develop_master_nao_vira_hotfix_e_aparece_na_saida(repo, capsys):
    repo.git("branch", "develop")
    repo.branch("fix/checkout")
    repo.commit("fix: um")

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_OK

    assert ler_fatos(repo)["hotfix"]["provavel"] is False
    assert "empate: develop, master" in capsys.readouterr().out


def test_pr_message_versionado_vira_aviso_na_saida(repo, capsys):
    repo.branch("feature/x")
    repo.commit("docs: mensagem antiga", {"PR-MESSAGE.md": "velho\n"})

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_OK

    assert "aviso: pr_message_versionado" in capsys.readouterr().out


def test_repo_inexistente_retorna_2(tmp_path, capsys):
    assert collect.main(["--repo", str(tmp_path / "nao-existe")]) == collect.EXIT_PARADA

    assert "não existe" in capsys.readouterr().err
