import pytest

from lib import coleta
from lib.coleta import (avisos, commits, eh_ruido, merges_ignorados, numstat, preencher_diffs,
                        sinais_hotfix, tipo_escopo)


@pytest.mark.parametrize("caminho,esperado", [
    ("package-lock.json", True), ("web/yarn.lock", True), ("go.sum", True), ("Pipfile.lock", True),
    ("web/dist/app.js", True), ("vendor/lib/x.php", True), ("src/app.min.js", True),
    ("static/app.js.map", True), ("tests/__snapshots__/a.snap", True),
    ("src/app.py", False), ("distribuicao.py", False), ("build.gradle", False), ("docs/build.md", False),
])
def test_classifica_ruido_pelo_caminho(caminho, esperado):
    assert eh_ruido(caminho) is esperado


@pytest.mark.parametrize("assunto,esperado", [
    ("feat(auth): login", ("feat", "auth")), ("Fix: checkout", ("fix", None)),
    ("feat!: quebra", ("feat", None)), ("ajustes", (None, None)),
])
def test_tipo_e_escopo_do_prefixo_conventional(assunto, esperado):
    assert tipo_escopo(assunto) == esperado


def test_commits_sem_merge_em_ordem_cronologica_com_corpo(repo):
    repo.branch("develop")
    repo.branch("feature/x")
    repo.commit("feat(login): tela\n\nMotivo: pedido do cliente.")
    repo.checkout("develop")
    repo.commit("feat: algo no develop", {"so_develop.txt": "d\n"})
    repo.checkout("feature/x")
    repo.merge("develop", "Merge branch 'develop' into feature/x")
    repo.commit("fix: ajuste")

    lista = commits(repo.path, "develop")

    assert [c["assunto"] for c in lista] == ["feat(login): tela", "fix: ajuste"]
    assert lista[0]["corpo"] == "Motivo: pedido do cliente."
    assert (lista[0]["tipo"], lista[0]["escopo"]) == ("feat", "login")
    assert len(lista[0]["hash"]) == 40
    assert merges_ignorados(repo.path, "develop") == 1
    assert "so_develop.txt" not in [a["caminho"] for a in numstat(repo.path, "develop")]


def test_mensagem_com_separadores_de_controle_nao_forja_commit(repo, tmp_path):
    repo.branch("feature/x")
    mensagem = tmp_path / "msg.txt"
    mensagem.write_text("feat: real\n\ncorpo\x1e" + "f" * 40 + "\x1ffix: FORJADO\x1fcorpo forjado\n",
                        encoding="utf-8")
    (repo.path / "x.txt").write_text("x\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-F", str(mensagem))

    lista = commits(repo.path, "master")

    assert [c["hash"] for c in lista] == [repo.sha()]
    assert lista[0]["assunto"] == "feat: real"
    assert "FORJADO" in lista[0]["corpo"]


def test_numstat_marca_ruido_binario_e_renomeacao_em_ordem_de_caminho(repo):
    repo.commit("chore: arquivo a mover", {"antigo.txt": "".join(f"linha {i}\n" for i in range(20))})
    repo.branch("feature/x")
    repo.git("mv", "antigo.txt", "novo.txt")
    repo.commit("refactor: renomeia", {"package-lock.json": '{"lock": 1}\n', "logo.png": b"\x89PNG\x00\x01"})

    arquivos = {a["caminho"]: a for a in numstat(repo.path, "master")}

    assert list(arquivos) == sorted(arquivos)
    assert arquivos["novo.txt"]["anterior"] == "antigo.txt" and arquivos["novo.txt"]["ruido"] is False
    assert arquivos["package-lock.json"]["ruido"] is True and arquivos["package-lock.json"]["mais"] == 1
    assert arquivos["logo.png"]["binario"] is True and arquivos["logo.png"]["ruido"] is True


def test_diff_de_renomeacao_usa_os_dois_caminhos(repo):
    repo.commit("chore: arquivo a mover", {"antigo.txt": "".join(f"linha {i}\n" for i in range(20))})
    repo.branch("feature/x")
    repo.git("mv", "antigo.txt", "novo.txt")
    repo.commit("refactor: renomeia")
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    novo = next(a for a in arquivos if a["caminho"] == "novo.txt")
    assert "rename from antigo.txt" in novo["diff"]
    assert "linha 5" not in novo["diff"]


def test_diff_de_um_arquivo_nao_traz_outros_por_glob_ou_magic(repo):
    repo.branch("feature/x")
    repo.commit("feat: nomes especiais", {
        "[ab].txt": "colchete\n", "a.txt": "letra A\n", "b.txt": "letra B\n",
        "pages/[id].tsx": "rota dinamica\n", "pages/i.tsx": "rota i\n",
        ":foo": "dois pontos\n", "foo": "sem dois pontos\n",
    })
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    por_nome = {a["caminho"]: a for a in arquivos}
    assert "+colchete" in por_nome["[ab].txt"]["diff"]
    assert "letra A" not in por_nome["[ab].txt"]["diff"] and "letra B" not in por_nome["[ab].txt"]["diff"]
    assert "rota i" not in por_nome["pages/[id].tsx"]["diff"]
    assert "+dois pontos" in por_nome[":foo"]["diff"]


def test_arquivo_com_nome_de_prefixo_proibido_nao_derruba_a_coleta(repo):
    repo.branch("feature/x")
    repo.commit("docs: nomes estranhos", {"--output.txt": "saida\n", "--submodule.md": "sub\n"})
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    por_nome = {a["caminho"]: a for a in arquivos}
    assert "+saida" in por_nome["--output.txt"]["diff"]
    assert "+sub" in por_nome["--submodule.md"]["diff"]


def test_corte_por_arquivo_e_ruido_sem_conteudo(repo):
    repo.branch("feature/x")
    repo.commit("feat: arquivos", {
        "grande.py": "".join(f"x_{i} = {i}\n" for i in range(1000)),
        "pequeno.py": "y = 1\n",
        "yarn.lock": "".join(f"pacote-{i}\n" for i in range(50)),
    })
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    por_nome = {a["caminho"]: a for a in arquivos}
    assert por_nome["pequeno.py"]["cortado"] is False and "+y = 1" in por_nome["pequeno.py"]["diff"]
    assert por_nome["grande.py"]["cortado"] is True
    assert por_nome["grande.py"]["diff"].count("\n") == coleta.TETO_LINHAS
    assert por_nome["yarn.lock"]["diff"] == ""


def test_so_quebra_de_linha_real_conta_para_o_corte(repo):
    repo.branch("feature/x")
    repo.commit("feat: form feed", {"ff.el": "".join(f"linha {i}\x0c\n" for i in range(300))})
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    assert arquivos[0]["cortado"] is False


def test_orcamento_total_esgotado_deixa_diff_marcado_e_respeita_teto(repo):
    repo.branch("feature/x")
    repo.commit("feat: dois arquivos", {"a.py": "a = 1\n", "b.py": "".join(f"b{i} = {i}\n" for i in range(30))})
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos, teto_bytes=200)

    por_nome = {a["caminho"]: a for a in arquivos}
    assert por_nome["a.py"]["cortado"] is False
    assert por_nome["b.py"]["cortado"] is True
    assert sum(len(a["diff"].encode("utf-8")) for a in arquivos) <= 200


def test_arquivo_sem_orcamento_restante_fica_vazio_e_marcado(repo):
    repo.branch("feature/x")
    repo.commit("feat: dois", {"a.py": "a = 1\n", "b.py": "b = 1\n"})
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos, teto_bytes=0)

    assert [(a["diff"], a["cortado"]) for a in arquivos] == [("", True), ("", True)]


@pytest.mark.parametrize("branch,tipos,base_nome,tem_develop,provavel", [
    ("hotfix/login", ["feat"], "develop", True, True),
    ("feature/x", ["feat", "hotfix"], "develop", True, True),
    ("fix/checkout", ["fix", "fix"], "master", True, True),
    ("fix/checkout", ["fix", "fix"], "master", False, False),
    ("fix/checkout", ["fix", "feat"], "master", True, False),
    ("feature/x", ["fix"], "develop", True, False),
])
def test_sinais_de_hotfix(branch, tipos, base_nome, tem_develop, provavel):
    lista = [{"tipo": t} for t in tipos]

    assert sinais_hotfix(branch, lista, base_nome, tem_develop)["provavel"] is provavel


def test_avisos_so_apontam_pr_message_versionado_sem_ler_o_working_tree(repo):
    (repo.path / "rascunho.txt").write_text("não commitado\n", encoding="utf-8")
    assert avisos(repo.path) == []

    repo.commit("docs: pr antigo", {"PR-MESSAGE.md": "velho\n"})

    assert avisos(repo.path) == ["pr_message_versionado"]


def test_so_correcoes_com_base_master_nao_e_hotfix_quando_develop_empata():
    # git-flow: branch que saiu do develop antes do último release empata com master
    lista = [{"tipo": "fix"}, {"tipo": "fix"}]

    sinais = sinais_hotfix("fix/checkout", lista, "master", True, develop_empata=True)

    assert sinais["provavel"] is False
