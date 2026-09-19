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


def test_ambiente_do_filho_e_base_positiva(monkeypatch):
    """A credencial de banco chega pelo ambiente (senha_env). Copiar o ambiente inteiro menos
    uma lista de proibidos deixaria PGPASSWORD alcançar todo comando docker — e lista negativa
    só protege do que alguém lembrou de escrever nela."""
    import os
    from lib.runner import ambiente
    monkeypatch.setenv("PGPASSWORD", "segredo-do-banco")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "outro-segredo")
    monkeypatch.setenv("PATH", "/usr/bin")

    env = ambiente("prod")

    assert env["DOCKER_CONTEXT"] == "prod"
    assert env["PATH"] == "/usr/bin"
    assert "PGPASSWORD" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_ambiente_entrega_o_que_o_chamador_declarar(monkeypatch):
    """O perfil de cada binário declara as suas (plano 3). Sem declarar, nada passa."""
    from lib.runner import ambiente
    monkeypatch.setenv("PGPASSWORD", "segredo-do-banco")
    assert ambiente(None, extras=("PGPASSWORD",))["PGPASSWORD"] == "segredo-do-banco"
    assert "PGPASSWORD" not in ambiente(None)


def test_segredo_nao_chega_ao_processo_filho(monkeypatch):
    """Restrição 2, a parte que faltava: nem argv, nem ambiente. O teste que existia
    substituía runner.run e nunca via o env."""
    monkeypatch.setenv("SENHA_DO_ALVO", "trocadilho-secreto")

    with mock.patch("lib.runner.subprocess.run") as m:
        m.return_value = mock.Mock(stdout="{}", returncode=0)
        run(["docker", "info"], timeout=5, context="prod")
        env = m.call_args.kwargs["env"]
        argv = m.call_args[0][0]

    assert "trocadilho-secreto" not in " ".join(argv)
    assert "trocadilho-secreto" not in "".join(env.values())
