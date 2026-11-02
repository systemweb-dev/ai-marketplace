import pytest
from lib.coletores.docker_allowlist import check, exec_de_leitura, inspect_de_task, NotAllowed


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


FORMATO = "{{.Status.ContainerStatus.ContainerID}}"
TASK = "n7h4b2k3j9x2mq8p1w0abcdef"


def test_inspect_de_task_passa_so_na_forma_exata():
    assert inspect_de_task(TASK) == ["docker", "inspect", "--type", "task", "--format", FORMATO, TASK]
    assert check(inspect_de_task(TASK)) is True


@pytest.mark.parametrize("cmd", [
    ["docker", "inspect", TASK],                                   # sem tipo: resolve qualquer objeto
    ["docker", "inspect", "--type", "task", TASK],                 # sem formato: traz o Env da task
    ["docker", "inspect", "--type", "task", "--format", "{{json .}}", TASK],
    ["docker", "inspect", "--type", "task", "--format", "{{.Spec.ContainerSpec.Env}}", TASK],
    ["docker", "inspect", "--type", "config", "--format", FORMATO, TASK],
    ["docker", "inspect", "--type", "secret", "--format", FORMATO, TASK],
    ["docker", "inspect", "--type=config", "c"],
    ["docker", "inspect", "--format", FORMATO, "--type", "task", TASK],
    ["docker", "inspect", "--type", "task", "--format", FORMATO, TASK, "outro-objeto"],
    ["docker", "inspect", "--type", "task", "--format", FORMATO, "--size"],
    ["docker", "inspect", "--type", "task", "--format", FORMATO],
])
def test_qualquer_outro_inspect_generico_e_recusado(cmd):
    with pytest.raises(NotAllowed):
        check(cmd)


def test_o_documento_da_allowlist_descreve_a_forma_exata():
    import pathlib
    doc = (pathlib.Path(__file__).resolve().parents[1] / "references"
           / "commands-allowlist.md").read_text(encoding="utf-8")
    assert f"docker inspect --type task --format '{FORMATO}' <id da task>" in doc


CONTAINER = "0123456789ab"


def _forma_real(vhost="/"):
    """As formas vêm do catálogo: o teste lê o mesmo arquivo que a allowlist."""
    from lib.catalogo_exec import familias
    f = next(x for x in familias() if x["familia"] == "rabbitmq")
    return f["enumerar"]["argv"], [vhost if t == "{vhost}" else t for t in f["listar"]["argv"]]


def test_exec_passa_so_nas_formas_exatas_do_catalogo():
    enumerar, listar = _forma_real("/")
    assert enumerar == ["rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"]
    assert listar == ["rabbitmqctl", "list_queues", "-q", "--formatter", "json", "-p", "/", "name",
                      "messages_ready", "messages_unacknowledged", "consumers"]
    assert check(exec_de_leitura(CONTAINER, enumerar)) is True
    assert check(exec_de_leitura(CONTAINER, listar)) is True
    assert check(exec_de_leitura(CONTAINER, _forma_real("loja.prod-1")[1])) is True


@pytest.mark.parametrize("vhost", ["", "-q", "--help", "a b", "a;id", "$(id)", "`id`", "a|b", "a\nb", "{vhost}",
                                   "a&b", "a>b", "x" * 256])
def test_exec_recusa_vhost_fora_do_formato(vhost):
    with pytest.raises(NotAllowed):
        check(exec_de_leitura(CONTAINER, _forma_real(vhost)[1]))


@pytest.mark.parametrize("cmd", [
    ["docker", "exec", CONTAINER],
    ["docker", "exec", CONTAINER, "sh"],
    ["docker", "exec", CONTAINER, "sh", "-c", "rabbitmqctl list_vhosts"],
    ["docker", "exec", CONTAINER, "bash", "-c", "id"],
    ["docker", "exec", CONTAINER, "env"],
    ["docker", "exec", CONTAINER, "cat", "/etc/passwd"],
    ["docker", "exec", CONTAINER, "rabbitmqctl", "delete_queue", "x"],
    ["docker", "exec", CONTAINER, "rabbitmqctl", "list_users"],
    ["docker", "exec", CONTAINER, "rabbitmqctl", "list_vhosts"],
    ["docker", "exec", CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name", "tracing"],
    ["docker", "exec", CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json"],
    ["docker", "exec", CONTAINER, "rabbitmqctl", "list_queues", "-q", "--formatter", "json", "-p", "/", "name"],
    ["docker", "exec", "-it", CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"],
    ["docker", "exec", "-i", CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"],
    ["docker", "exec", "-u", "root", CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"],
    ["docker", "exec", "-e", "A=1", CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"],
    ["docker", "exec", "web", "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"],
    ["docker", "exec", "--help"],
    ["docker", "--context", "c", "exec", CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"],
    ["docker", "container", "exec", CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"],
    ["docker", "logs", CONTAINER],
    ["docker", "cp", f"{CONTAINER}:/etc/passwd", "."],
    ["docker", "secret", "inspect", "s"],
])
def test_qualquer_outro_exec_e_recusado(cmd):
    with pytest.raises(NotAllowed):
        check(cmd)


def test_catalogo_quebrado_nao_abre_exec(monkeypatch):
    from lib import catalogo_exec

    def quebrado():
        raise catalogo_exec.CatalogoInvalido("x")

    monkeypatch.setattr(catalogo_exec, "familias", quebrado)
    with pytest.raises(NotAllowed):
        check(exec_de_leitura(CONTAINER, _forma_de_mentira()))


def _forma_de_mentira():
    return ["rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"]


def test_o_documento_da_allowlist_descreve_o_exec():
    import pathlib
    doc = (pathlib.Path(__file__).resolve().parents[1] / "references"
           / "commands-allowlist.md").read_text(encoding="utf-8")
    assert "references/execs/<familia>.toml" in doc
    assert "docker exec <container> <comando do catálogo>" in doc
    proibidos = doc.split("## Proibidos explicitamente")[1].split("##")[0]
    assert "`exec` fora do catálogo" in proibidos
