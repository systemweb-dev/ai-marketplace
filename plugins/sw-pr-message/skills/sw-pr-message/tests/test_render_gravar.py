import shutil

import collect
import render
from fluxo import escrever_mudancas, preparar
from gitrepo import Repo
from lib.gitcmd import caminho_git


def test_grava_na_raiz_e_protege_pelo_exclude(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)

    assert render.main(["--repo", str(repo.path)]) == 0

    texto = (repo.path / "PR-MESSAGE.md").read_text(encoding="utf-8")
    assert texto.startswith("# Tela de login\n")
    assert repo.git("check-ignore", "PR-MESSAGE.md").strip() == "PR-MESSAGE.md"


def test_rodar_duas_vezes_nao_duplica_a_linha_do_exclude(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)

    render.main(["--repo", str(repo.path)])
    render.main(["--repo", str(repo.path)])

    linhas = caminho_git(repo.path, "info/exclude").read_text(encoding="utf-8").splitlines()
    assert linhas.count("/PR-MESSAGE.md") == 1


def test_versao_anterior_editada_a_mao_e_preservada(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    (repo.path / "PR-MESSAGE.md").write_text("editado à mão\n", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == 0

    assert (pasta / "PR-MESSAGE.anterior.md").read_text(encoding="utf-8") == "editado à mão\n"


def test_conteudo_igual_nao_gera_copia_anterior(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)

    render.main(["--repo", str(repo.path)])
    render.main(["--repo", str(repo.path)])

    assert not (pasta / "PR-MESSAGE.anterior.md").exists()


def test_pr_message_existente_que_nao_e_utf8_e_preservado(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    (repo.path / "PR-MESSAGE.md").write_bytes(b"\xff\xfe latin")

    assert render.main(["--repo", str(repo.path)]) == 0

    assert (pasta / "PR-MESSAGE.anterior.md").read_bytes() == b"\xff\xfe latin"


def test_avisa_quando_o_arquivo_ja_e_versionado(repo, capsys):
    repo.branch("feature/x")
    sha_doc = repo.commit("docs: mensagem antiga", {"PR-MESSAGE.md": "velho\n"})
    sha_feat = repo.commit("feat: tela de login", {"login.py": "x = 1\n"})
    assert collect.main(["--repo", str(repo.path)]) == 0
    capsys.readouterr()                       # descarta o aviso da coleta: aqui o teste é do render
    escrever_mudancas(caminho_git(repo.path, "sw-pr-message"), sha_feat, sha_doc)

    assert render.main(["--repo", str(repo.path)]) == 0

    assert "aviso: PR-MESSAGE.md é versionado" in capsys.readouterr().out


def test_pr_message_versionado_como_link_simbolico_e_recusado_sem_escrever_fora(repo, tmp_path, capsys):
    fora = tmp_path / "fora.txt"
    fora.write_text("intocado\n", encoding="utf-8")
    repo.branch("feature/x")
    (repo.path / "PR-MESSAGE.md").symlink_to(fora)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "chore: link")
    sha_link = repo.sha()
    sha_feat = repo.commit("feat: tela", {"tela.py": "x = 1\n"})
    assert collect.main(["--repo", str(repo.path)]) == 0
    escrever_mudancas(caminho_git(repo.path, "sw-pr-message"), sha_feat, sha_link)

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_AMBIENTE

    assert fora.read_text(encoding="utf-8") == "intocado\n"
    assert "link simbólico" in capsys.readouterr().err


def test_recusa_com_commit_esquecido_nao_grava(repo, capsys):
    repo.branch("feature/x")
    sha_a = repo.commit("feat: a", {"a.py": "a = 1\n"})
    repo.commit("fix: b", {"b.py": "b = 1\n"})
    assert collect.main(["--repo", str(repo.path)]) == 0
    escrever_mudancas(caminho_git(repo.path, "sw-pr-message"), sha_a)

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_RECUSA

    assert "commit esquecido" in capsys.readouterr().err
    assert not (repo.path / "PR-MESSAGE.md").exists()


def test_json_malformado_e_recusado(repo, capsys):
    pasta, _ = preparar(repo)
    (pasta / "mudancas.json").write_text("{ isto não é json", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_RECUSA

    assert "JSON malformado" in capsys.readouterr().err
    assert not (repo.path / "PR-MESSAGE.md").exists()


def test_mudancas_ausente_e_recusado(repo, capsys):
    preparar(repo)

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_RECUSA

    assert "mudancas.json não encontrado" in capsys.readouterr().err


def test_mudancas_que_nao_e_objeto_e_recusado(repo, capsys):
    pasta, _ = preparar(repo)
    (pasta / "mudancas.json").write_text("[]", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_RECUSA

    assert "deve ser um objeto JSON" in capsys.readouterr().err


def test_sem_fatos_e_erro_de_ambiente(repo, capsys):
    assert render.main(["--repo", str(repo.path)]) == render.EXIT_AMBIENTE

    assert "rode collect.py antes" in capsys.readouterr().err


def test_fatos_corrompido_e_erro_de_ambiente_sem_traceback(repo, capsys):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    (pasta / "fatos.json").write_text("{ truncado", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_AMBIENTE

    assert "rode collect.py de novo" in capsys.readouterr().err


def test_fatos_de_outra_branch_e_recusado(repo, capsys):
    pasta, sha = preparar(repo)               # coletado em feature/x
    escrever_mudancas(pasta, sha)
    repo.branch("feature/y")

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_AMBIENTE

    assert "feature/x" in capsys.readouterr().err
    assert not (repo.path / "PR-MESSAGE.md").exists()


def test_render_fora_de_repositorio_e_erro_de_ambiente(tmp_path, capsys):
    assert render.main(["--repo", str(tmp_path)]) == render.EXIT_AMBIENTE

    assert "Não é um repositório git" in capsys.readouterr().err


def test_repo_inexistente_e_erro_de_ambiente(tmp_path, capsys):
    assert render.main(["--repo", str(tmp_path / "nao-existe")]) == render.EXIT_AMBIENTE

    assert "não existe" in capsys.readouterr().err


def test_repo_por_subdiretorio_grava_na_raiz(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    sub = repo.path / "src"
    sub.mkdir()

    assert render.main(["--repo", str(sub)]) == 0

    assert (repo.path / "PR-MESSAGE.md").exists() and not (sub / "PR-MESSAGE.md").exists()


def test_exclude_sem_quebra_final_recebe_linha_separada(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    exclude = caminho_git(repo.path, "info/exclude")
    exclude.write_text("*.log", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == 0

    assert exclude.read_text(encoding="utf-8").splitlines()[-2:] == ["*.log", "/PR-MESSAGE.md"]


def test_sem_pasta_info_ela_e_criada(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    shutil.rmtree(caminho_git(repo.path, "info"))

    assert render.main(["--repo", str(repo.path)]) == 0

    assert caminho_git(repo.path, "info/exclude").read_text(encoding="utf-8").strip() == "/PR-MESSAGE.md"


def test_worktree_resolve_intermediarios_e_exclude_pelo_git_path(repo, tmp_path):
    wt = tmp_path / "wt"
    repo.git("worktree", "add", str(wt), "-b", "feature/wt")
    outro = Repo(wt)
    sha = outro.commit("feat: algo no worktree", {"wt.py": "x = 1\n"})

    assert collect.main(["--repo", str(wt)]) == 0
    pasta = caminho_git(wt, "sw-pr-message")
    escrever_mudancas(pasta, sha)
    assert render.main(["--repo", str(wt)]) == 0

    assert (wt / ".git").is_file()
    assert (pasta / "fatos.json").exists()
    assert (wt / "PR-MESSAGE.md").exists()
    assert outro.git("check-ignore", "PR-MESSAGE.md").strip() == "PR-MESSAGE.md"
