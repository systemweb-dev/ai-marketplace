"""Allowlist POSITIVA de comandos docker read-only, por par (noun, verb)."""


class NotAllowed(Exception):
    pass


# "-" = verbo ausente (comando de 1 token após `docker`, ex.: `docker info`).
ALLOW = {
    ("context", "ls"), ("context", "inspect"), ("info", "-"), ("version", "-"),
    ("node", "ls"), ("node", "inspect"), ("service", "ls"), ("service", "ps"),
    ("service", "inspect"), ("ps", "-"), ("container", "inspect"),
    ("network", "ls"), ("network", "inspect"), ("secret", "ls"),
    ("config", "ls"), ("image", "ls"),
}


def check(cmd):
    """cmd = ['docker', noun, verb?, ...]. Levanta NotAllowed se o par não estiver na allowlist.

    O match é sobre os DOIS primeiros tokens após `docker` — assim (context, inspect) é
    permitido e (config, inspect) NÃO, mesmo ambos sendo `inspect`.
    """
    if not cmd or cmd[0] != "docker" or len(cmd) < 2:
        raise NotAllowed(f"comando inesperado: {cmd!r}")
    noun = cmd[1]
    verb = cmd[2] if len(cmd) >= 3 and not cmd[2].startswith("-") else "-"
    if (noun, verb) not in ALLOW:
        raise NotAllowed(f"par não permitido: ({noun}, {verb})")
    return True
