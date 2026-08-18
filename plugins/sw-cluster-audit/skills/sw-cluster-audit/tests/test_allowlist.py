import pytest
from lib.allowlist import check, NotAllowed


def test_permite_par_read_only():
    assert check(["docker", "service", "inspect", "web"]) is True
    assert check(["docker", "context", "inspect", "prod"]) is True
    assert check(["docker", "info"]) is True


@pytest.mark.parametrize("cmd", [
    ["docker", "--context", "prod", "service", "rm", "web"],  # flag global antes do noun
    ["docker", "-H", "tcp://evil:2375", "ps"],                # host remoto via flag
    ["docker", "--host", "x", "service", "rm", "web"],
])
def test_flag_global_antes_do_noun_nao_fura(cmd):
    # a flag vira o "noun" (começa com -) e o par não está na allowlist positiva
    with pytest.raises(NotAllowed):
        check(cmd)


@pytest.mark.parametrize("cmd", [[], ["docker"], ["kubectl", "get", "pods"]])
def test_guard_clauses(cmd):
    with pytest.raises(NotAllowed):
        check(cmd)


@pytest.mark.parametrize("cmd", [
    ["docker", "config", "inspect", "c"],     # vaza valor do config
    ["docker", "container", "exec", "x"],
    ["docker", "container", "logs", "x"],
    ["docker", "service", "rm", "web"],       # mutante
    ["docker", "swarm", "join-token", "worker"],
    ["docker", "secret", "inspect", "s"],
])
def test_bloqueia_deny_e_fora_da_allowlist(cmd):
    with pytest.raises(NotAllowed):
        check(cmd)


def test_match_nos_dois_primeiros_tokens():
    check(["docker", "config", "ls"])              # (config, ls) permitido
    with pytest.raises(NotAllowed):
        check(["docker", "config", "inspect", "c"])  # (config, inspect) não
