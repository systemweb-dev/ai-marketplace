"""Allowlist POSITIVA de comandos docker read-only, por par (noun, verb)."""
import re


class NotAllowed(Exception):
    pass


# "-" = verbo ausente (comando de 1 token após `docker`, ex.: `docker info`).
ALLOW = {
    ("context", "ls"), ("context", "inspect"), ("info", "-"), ("version", "-"),
    ("node", "ls"), ("node", "inspect"), ("node", "ps"),
    ("service", "ls"), ("service", "ps"),
    ("service", "inspect"), ("ps", "-"), ("container", "inspect"),
    ("network", "ls"), ("network", "inspect"), ("secret", "ls"),
    ("config", "ls"), ("image", "ls"), ("system", "df"),
}


# `docker inspect` é genérico: com outro `--type` ele lê config e secret, e sem `--format` a task
# traz o `Env` do serviço. Por isso ele NÃO entra em `ALLOW`: só esta forma exata passa, com o
# tipo e a saída fixos, e a única coisa que varia é o id.
ID_DE_TASK = re.compile(r"[a-z0-9]{12,64}")
_INSPECT_DE_TASK = ["docker", "inspect", "--type", "task",
                    "--format", "{{.Status.ContainerStatus.ContainerID}}"]


def inspect_de_task(id_da_task):
    """O único `docker inspect` genérico que a skill roda: devolve só o id do container."""
    return [*_INSPECT_DE_TASK, id_da_task]


def _e_inspect_de_task(cmd):
    return (len(cmd) == len(_INSPECT_DE_TASK) + 1 and cmd[:-1] == _INSPECT_DE_TASK
            and ID_DE_TASK.fullmatch(cmd[-1]) is not None)


def exec_de_leitura(container, argv):
    """O `docker exec` da skill: sem flag, sem shell, e só com comando do catálogo."""
    return ["docker", "exec", container, *argv]


def _e_exec_de_leitura(cmd):
    """Fora da forma exata, `exec` nunca passa. Catálogo inválido fecha a porta."""
    from lib import catalogo_exec

    if len(cmd) < 4 or cmd[1] != "exec" or not catalogo_exec.ID_DE_CONTAINER.fullmatch(cmd[2]):
        return False
    try:
        return catalogo_exec.forma_aceita(cmd[3:])
    except catalogo_exec.CatalogoInvalido:
        return False


def check(cmd):
    """cmd = ['docker', noun, verb?, ...]. Levanta NotAllowed se o par não estiver na allowlist.

    O match é sobre os DOIS primeiros tokens após `docker` — assim (context, inspect) é
    permitido e (config, inspect) NÃO, mesmo ambos sendo `inspect`.
    """
    if not cmd or cmd[0] != "docker" or len(cmd) < 2:
        raise NotAllowed(f"comando inesperado: {cmd!r}")
    if _e_inspect_de_task(cmd) or _e_exec_de_leitura(cmd):
        return True
    noun = cmd[1]
    verb = cmd[2] if len(cmd) >= 3 and not cmd[2].startswith("-") else "-"
    if (noun, verb) not in ALLOW:
        raise NotAllowed(f"par não permitido: ({noun}, {verb})")
    return True
