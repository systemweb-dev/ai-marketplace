import hashlib
import json

import configurar
from apoio_host import runner_falso
from test_descoberta import CONTAINERS, PORTAS, SERVICOS

ALVOS = '[[alvo]]\nnome = "banco-01"\ntipo = "host"\nssh_destino = "root@banco-01"\n'
SAIDAS = {"usuario": "root\n", "servicos": SERVICOS, "portas": PORTAS, "containers": CONTAINERS}


def _alvos(tmp_path):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(ALVOS, encoding="utf-8")
    caminho.chmod(0o600)
    return caminho


def test_descobrir_lista_os_candidatos_e_nao_altera_o_arquivo(tmp_path, monkeypatch, capsys):
    caminho = _alvos(tmp_path)
    antes = hashlib.sha256(caminho.read_bytes()).hexdigest()
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(SAIDAS))

    codigo = configurar.main(["descobrir", "--alvo", "banco-01", "--infra", str(caminho)])

    assert codigo == 0
    saida = json.loads(capsys.readouterr().out)
    assert "unidade:mariadb.service" in {c["origem"] for c in saida["candidatos"]}
    assert hashlib.sha256(caminho.read_bytes()).hexdigest() == antes
    assert not (tmp_path / "alvos.toml.bak").exists()


def test_vpn_desligada_para_com_motivo(tmp_path, monkeypatch, capsys):
    caminho = _alvos(tmp_path)
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso({}, conexao=False))
    assert configurar.main(["descobrir", "--alvo", "banco-01", "--infra", str(caminho)]) == 2
    assert "VPN" in capsys.readouterr().err


def test_alvo_que_nao_e_host_e_recusado(tmp_path, capsys):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text('[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "c"\n', encoding="utf-8")
    caminho.chmod(0o600)
    assert configurar.main(["descobrir", "--alvo", "c", "--infra", str(caminho)]) == 2
    assert "host" in capsys.readouterr().err
