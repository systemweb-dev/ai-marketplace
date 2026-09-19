# tests/test_diagnose_estatico.py
import json

import diagnose
from lib import pastas
from projeto import projeto_phpunit, projeto_pytest, projeto_vitest
from runners import chamadas, instalar


def rodar(repo, *args):
    return diagnose.main(["--repo", str(repo.path), *args])


def test_grava_fatos_com_repositorio_branch_e_head(repo, capsys):
    projeto_pytest(repo)

    assert rodar(repo) == 0
    fatos = json.loads(pastas.fatos(repo.path).read_text(encoding="utf-8"))

    assert fatos["versao"] == 1
    assert fatos["repo"]["branch"] == "master"
    assert len(fatos["repo"]["head"]) == 40
    assert fatos["execucao"]["rodou"] is False
    assert fatos["cobertura"]["disponivel"] is False


def test_detecta_a_stack_e_o_runner(repo):
    projeto_vitest(repo)
    rodar(repo)
    fatos = json.loads(pastas.fatos(repo.path).read_text(encoding="utf-8"))

    assert [(s["linguagem"], s["runner"], s["nativo"]) for s in fatos["stacks"]] == [("js", "vitest", True)]


def test_sinais_entram_nos_fatos_com_caminho_relativo(repo):
    projeto_pytest(repo)
    rodar(repo)
    fatos = json.loads(pastas.fatos(repo.path).read_text(encoding="utf-8"))

    regras = {s["regra"] for s in fatos["sinais"]}
    assert "marcado_para_pular" in regras
    assert all(not s["caminho"].startswith("/") for s in fatos["sinais"])
    assert "tests/unit/test_problemas.py" in fatos["suspeitos"]


def test_sem_executar_nenhum_runner_e_chamado(repo, tmp_path, monkeypatch):
    """Restrição verificável 2: nada executa sem aprovação."""
    projeto_pytest(repo)
    registros = [instalar(tmp_path, monkeypatch, nome, {"__padrao__": ("", None, None, 0)})
                 for nome in ("pytest", "vitest", "jest", "phpunit")]

    rodar(repo)

    assert [chamadas(r) for r in registros] == [[], [], [], []]


def test_projeto_sem_teste_nenhum_avisa_e_nao_grava_fatos(repo, capsys):
    codigo = rodar(repo)

    assert codigo == 2
    assert "nenhum arquivo de teste" in capsys.readouterr().err.lower()
    assert not pastas.fatos(repo.path).exists()


def test_repo_inexistente_para_com_mensagem(tmp_path, capsys):
    codigo = diagnose.main(["--repo", str(tmp_path / "nao-existe")])

    assert codigo == 2
    assert "não existe" in capsys.readouterr().err


def test_residuo_de_backup_e_restaurado_antes_de_qualquer_coisa(repo, capsys):
    projeto_pytest(repo)
    from lib import backup
    backup.guardar(repo.path, "src/calculadora.py")
    (repo.path / "src/calculadora.py").write_text("QUEBRADO\n", encoding="utf-8")

    rodar(repo)

    assert (repo.path / "src/calculadora.py").read_text(encoding="utf-8").startswith("def somar")
    assert "restaurado" in capsys.readouterr().out


def test_escopo_fora_da_raiz_para_com_mensagem(repo, capsys):
    codigo = diagnose.main(["--repo", str(repo.path), "--escopo", "../.."])

    assert codigo == 2
    assert "dentro" in capsys.readouterr().err
