# tests/test_backup.py
import hashlib
import json

import pytest

from lib import backup, pastas


def sha(caminho):
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_guardar_registra_o_original_e_restaurar_devolve_os_bytes(repo):
    alvo = repo.path / "src/a.py"
    repo.escrever({"src/a.py": "def f():\n    return 1\n"})
    repo.commit("feat: a")
    antes = sha(alvo)

    backup.guardar(repo.path, "src/a.py")
    alvo.write_text("def f():\n    return 999\n", encoding="utf-8")
    backup.restaurar(repo.path, "src/a.py")

    assert sha(alvo) == antes


def test_mutacao_temporaria_restaura_mesmo_com_excecao_no_meio(repo):
    alvo = repo.path / "src/a.py"
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")
    antes = sha(alvo)

    with pytest.raises(RuntimeError):
        with backup.mutacao_temporaria(repo.path, "src/a.py"):
            alvo.write_text("x = 2\n", encoding="utf-8")
            raise RuntimeError("o teste morreu no meio da prova")

    assert sha(alvo) == antes
    assert backup.residuo(repo.path) == [], "backup usado e restaurado não pode ficar pendente"


def test_residuo_de_execucao_anterior_e_detectado_e_limpo(repo):
    alvo = repo.path / "src/a.py"
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")
    antes = sha(alvo)

    backup.guardar(repo.path, "src/a.py")          # simula a sessão morrendo aqui
    alvo.write_text("x = 2\n", encoding="utf-8")

    assert backup.residuo(repo.path) == ["src/a.py"]
    assert backup.restaurar_tudo(repo.path) == {"intacto": [], "sobrescrito": ["src/a.py"]}
    assert sha(alvo) == antes
    assert backup.residuo(repo.path) == []


def test_descartar_apaga_o_backup_sem_mexer_no_arquivo(repo):
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    (repo.path / "src/a.py").write_text("x = 2\n", encoding="utf-8")

    backup.descartar(repo.path, "src/a.py")

    assert backup.residuo(repo.path) == []
    assert (repo.path / "src/a.py").read_text(encoding="utf-8") == "x = 2\n"


def test_guardar_duas_vezes_preserva_o_original_da_primeira(repo):
    alvo = repo.path / "src/a.py"
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")

    backup.guardar(repo.path, "src/a.py")
    alvo.write_text("mexido\n", encoding="utf-8")
    backup.guardar(repo.path, "src/a.py")          # não pode sobrescrever o backup bom
    backup.restaurar(repo.path, "src/a.py")

    assert alvo.read_text(encoding="utf-8") == "original\n"


def test_arquivo_binario_e_sem_final_de_linha_voltam_identicos(repo):
    alvo = repo.path / "dados.bin"
    alvo.write_bytes(b"\x00\x01\x02sem quebra")
    repo.git("add", "-A"); repo.git("commit", "-qm", "chore: bin")
    antes = sha(alvo)

    with backup.mutacao_temporaria(repo.path, "dados.bin"):
        alvo.write_bytes(b"outra coisa")

    assert sha(alvo) == antes


def test_registro_guarda_caminho_relativo_e_hash(repo):
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")

    backup.guardar(repo.path, "src/a.py")
    registro = json.loads((pastas.backups(repo.path) / "guardados.json").read_text(encoding="utf-8"))

    assert list(registro) == ["src/a.py"]
    assert len(registro["src/a.py"]["sha256"]) == 64


def test_backup_sumido_do_disco_nao_grava_o_arquivo_mutado_como_original(repo):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    copia = next(p for p in pastas.backups(repo.path).glob("*.bak"))
    copia.unlink()
    (repo.path / "src/a.py").write_text("mutado\n", encoding="utf-8")

    with pytest.raises(backup.BackupSumiu):
        backup.guardar(repo.path, "src/a.py")


def test_restaurar_diz_se_precisou_sobrescrever(repo):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")

    backup.guardar(repo.path, "src/a.py")
    assert backup.restaurar(repo.path, "src/a.py") == "intacto"

    backup.guardar(repo.path, "src/a.py")
    (repo.path / "src/a.py").write_text("mexido\n", encoding="utf-8")
    assert backup.restaurar(repo.path, "src/a.py") == "sobrescrito"


def test_restaurar_tudo_separa_o_que_foi_sobrescrito(repo):
    repo.escrever({"src/a.py": "a\n", "src/b.py": "b\n"})
    repo.commit("feat: dois")
    backup.guardar(repo.path, "src/a.py")
    backup.guardar(repo.path, "src/b.py")
    (repo.path / "src/b.py").write_text("mexido\n", encoding="utf-8")

    assert backup.restaurar_tudo(repo.path) == {"intacto": ["src/a.py"], "sobrescrito": ["src/b.py"]}
