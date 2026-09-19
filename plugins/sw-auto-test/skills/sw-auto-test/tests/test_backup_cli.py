# tests/test_backup_cli.py
import backup as cli
from lib import backup


def test_guardar_restaurar_e_descartar_pela_linha_de_comando(repo, capsys):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    alvo = repo.path / "src/a.py"

    assert cli.main(["--repo", str(repo.path), "guardar", "src/a.py"]) == 0
    alvo.write_text("mexido\n", encoding="utf-8")
    assert cli.main(["--repo", str(repo.path), "restaurar", "src/a.py"]) == 0
    assert alvo.read_text(encoding="utf-8") == "original\n"

    cli.main(["--repo", str(repo.path), "guardar", "src/a.py"])
    assert cli.main(["--repo", str(repo.path), "descartar", "src/a.py"]) == 0
    assert backup.residuo(repo.path) == []


def test_varrer_lista_e_restaura_residuo(repo, capsys):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    (repo.path / "src/a.py").write_text("mexido\n", encoding="utf-8")

    assert cli.main(["--repo", str(repo.path), "varrer"]) == 0

    assert (repo.path / "src/a.py").read_text(encoding="utf-8") == "original\n"
    assert "src/a.py" in capsys.readouterr().out


def test_guardar_arquivo_inexistente_sai_com_dois(repo, capsys):
    assert cli.main(["--repo", str(repo.path), "guardar", "nao-existe.py"]) == 2
    assert "não existe" in capsys.readouterr().err


def test_restaurar_sem_backup_avisa_e_sai_com_dois(repo, capsys):
    repo.escrever({"src/a.py": "x\n"})
    repo.commit("feat: a")

    assert cli.main(["--repo", str(repo.path), "restaurar", "src/a.py"]) == 2
    assert "sem backup" in capsys.readouterr().err


def test_recusa_caminho_fora_da_raiz(repo, capsys):
    assert cli.main(["--repo", str(repo.path), "guardar", "../fora.txt"]) == 2
    assert cli.main(["--repo", str(repo.path), "guardar", "/etc/hostname"]) == 2
    assert "fora" in capsys.readouterr().err.lower()


def test_restaurar_avisa_quando_sobrescreve_alteracao_posterior(repo, capsys):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    (repo.path / "src/a.py").write_text("mexido depois do backup\n", encoding="utf-8")

    assert cli.main(["--repo", str(repo.path), "restaurar", "src/a.py"]) == 0
    assert "alteração posterior ao backup" in capsys.readouterr().out


def test_varrer_com_a_copia_sumida_avisa_e_nao_sai_zero(repo, capsys):
    from lib import pastas

    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    next(pastas.backups(repo.path).glob("*.bak")).unlink()

    assert cli.main(["--repo", str(repo.path), "varrer"]) == 2
    assert "não consegui restaurar" in capsys.readouterr().err


def test_guardar_com_a_copia_sumida_sai_com_dois_e_sem_traceback(repo, capsys):
    from lib import pastas

    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    next(pastas.backups(repo.path).glob("*.bak")).unlink()

    assert cli.main(["--repo", str(repo.path), "guardar", "src/a.py"]) == 2
    assert "sumiu" in capsys.readouterr().err
