# tests/test_runner_ssh.py
from unittest import mock

import pytest

from lib import runner
from lib.coletores.docker_allowlist import NotAllowed


def _ok(stdout="root\n", rc=0, stderr=""):
    return mock.Mock(stdout=stdout, returncode=rc, stderr=stderr)


def test_argv_segue_o_molde_inteiro():
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("usuario@srv", 2222, "id -un", timeout=20)
    assert m.call_args[0][0] == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                                 "-o", "RemoteCommand=none", "-o", "RequestTTY=no",
                                 "-p", "2222", "usuario@srv", "id -un"]
    assert m.call_args[1]["shell"] is False


def test_sem_porta_nao_passa_p():
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("usuario@srv", None, "id -un", timeout=20)
    assert "-p" not in m.call_args[0][0]


@pytest.mark.parametrize("destino,comando,porta", [
    ("-Jevil@host", "id -un", None),
    ("usuario@srv", "id -un; reboot", None),
    ("usuario@srv", "cat /etc/shadow", None),
    ("usuario@srv", "id -un", 0),
])
def test_fora_do_permitido_levanta_sem_chamar_subprocesso(destino, comando, porta):
    with mock.patch("lib.runner.subprocess.run") as m:
        with pytest.raises(NotAllowed):
            runner.run_ssh(destino, porta, comando, timeout=20)
    assert m.call_count == 0


def test_codigo_255_vira_motivo_de_conexao():
    erros = []
    with mock.patch("lib.runner.subprocess.run",
                    return_value=_ok("", 255, "ssh: connect to host srv port 22: timed out")):
        saida = runner.run_ssh("usuario@srv", None, "id -un", timeout=20, errors=erros)
    assert saida is None
    assert "não abri a sessão para usuario@srv" in erros[0]["reason"]
    assert "VPN" in erros[0]["reason"]


def test_ambiente_do_filho_nao_carrega_docker_nem_senha(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://x:2376")
    monkeypatch.setenv("SENHA_DO_BANCO", "segredo")
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("usuario@srv", None, "id -un", timeout=20)
    env = m.call_args[1]["env"]
    assert "DOCKER_HOST" not in env and "SENHA_DO_BANCO" not in env and "DOCKER_CONTEXT" not in env
