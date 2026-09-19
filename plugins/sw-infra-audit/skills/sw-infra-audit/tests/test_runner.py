from unittest import mock
import subprocess
import pytest

from lib.runner import run
from lib.coletores.docker_allowlist import NotAllowed


def test_chama_subprocess_com_args_array_sem_shell():
    with mock.patch("lib.runner.subprocess.run") as m:
        m.return_value = mock.Mock(stdout="{}", returncode=0)
        run(["docker", "ps", "--format", "{{json .}}"], timeout=5)
        args, kwargs = m.call_args
        assert args[0] == ["docker", "ps", "--format", "{{json .}}"]  # lista, não string
        assert kwargs.get("shell", False) is False                    # nunca shell=True


def test_nome_malicioso_nao_injeta():
    with mock.patch("lib.runner.subprocess.run") as m:
        m.return_value = mock.Mock(stdout="", returncode=0)
        run(["docker", "container", "inspect", "a; touch /tmp/pwned"], timeout=5)
        assert m.call_args[0][0][-1] == "a; touch /tmp/pwned"  # 1 argumento, não 2 comandos


def test_bloqueia_comando_fora_da_allowlist_sem_executar():
    # valida-antes-de-executar: se check() bloqueia, o subprocess NUNCA é chamado
    with mock.patch("lib.runner.subprocess.run") as m:
        with pytest.raises(NotAllowed):
            run(["docker", "service", "rm", "web"], timeout=5)
        assert m.call_count == 0


def test_timeout_vira_none(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=1)
    monkeypatch.setattr("lib.runner.subprocess.run", boom)
    assert run(["docker", "info"], timeout=1) is None


def test_docker_ausente_vira_none(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("docker")
    monkeypatch.setattr("lib.runner.subprocess.run", boom)
    assert run(["docker", "info"], timeout=1) is None


def test_docker_host_do_ambiente_nao_sequestra_o_alvo(monkeypatch):
    """No docker, DOCKER_HOST tem precedência sobre DOCKER_CONTEXT. Herdá-lo faria a coleta
    falar com outra máquina enquanto o relatório assina com o nome do alvo confirmado."""
    monkeypatch.setenv("DOCKER_HOST", "tcp://198.51.100.99:2376")
    monkeypatch.setenv("DOCKER_TLS_VERIFY", "1")
    monkeypatch.setenv("DOCKER_CERT_PATH", "/tmp/certs")

    with mock.patch("lib.runner.subprocess.run") as m:
        m.return_value = mock.Mock(stdout="{}", returncode=0)
        run(["docker", "info"], timeout=5, context="prod")
        env = m.call_args.kwargs["env"]

    assert env["DOCKER_CONTEXT"] == "prod"
    assert not {"DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"} & set(env)


def test_sem_context_o_ambiente_tambem_nao_escolhe_cluster(monkeypatch):
    """Comando sem alvo (ex.: `context ls`) é sobre a máquina local — o ambiente não pode
    redirecioná-lo para um daemon remoto sem ninguém ver."""
    import os
    monkeypatch.setenv("DOCKER_HOST", "tcp://198.51.100.99:2376")
    monkeypatch.setenv("DOCKER_CONTEXT", "outro")

    with mock.patch("lib.runner.subprocess.run") as m:
        m.return_value = mock.Mock(stdout="{}", returncode=0)
        run(["docker", "context", "ls"], timeout=5)
        env = m.call_args.kwargs["env"]

    assert not {"DOCKER_HOST", "DOCKER_CONTEXT"} & set(env)
    assert env.get("PATH") == os.environ.get("PATH"), "o resto do ambiente continua de pé"
