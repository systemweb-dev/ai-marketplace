"""Executor de comandos docker read-only: args-array (nunca shell), timeout, valida allowlist.

O cluster é escolhido por `DOCKER_CONTEXT` no ambiente **do processo filho** — a flag
`--context`/`-H` do docker é bloqueada pela allowlist, e mexer no `os.environ` da skill
vazaria a seleção para o alvo seguinte.

E o ambiente herdado é limpo antes: no docker, `DOCKER_HOST` tem PRECEDÊNCIA sobre
`DOCKER_CONTEXT`. Um `DOCKER_HOST` exportado no shell mandaria a coleta para outra máquina
enquanto o relatório assinaria com o nome do alvo confirmado — o gate `--confirmar` viraria
enfeite. `DOCKER_TLS_VERIFY`/`DOCKER_CERT_PATH` andam com ele; ficar com o do shell faria a
conexão usar o certificado errado.
"""
import os
import subprocess

from lib.coletores.docker_allowlist import check

# o que um processo filho precisa para existir — e nada além disso.
# Base POSITIVA de propósito: lista de proibidos só protege do que alguém lembrou de escrever
# nela, e a credencial de um alvo chega justamente pelo ambiente (`senha_env`). Com lista
# negativa, a senha do banco viajaria dentro de todo comando docker.
BASE = ("PATH", "HOME", "LANG", "LC_ALL", "TZ",
        # caminhos de que o próprio cliente docker precisa — não são credencial:
        # sem SSH_AUTH_SOCK, um context `ssh://` (que a própria skill recomenda em
        # references/tls-renewal.md) perde o agente e TODO comando vira "indisponível";
        # sem DOCKER_CONFIG, quem o exporta perde o armazenamento de contexts.
        "SSH_AUTH_SOCK", "DOCKER_CONFIG", "XDG_RUNTIME_DIR")


def ambiente(context, extras=()):
    """O ambiente do processo filho: o mínimo, mais o context do alvo, mais o que o chamador
    declarar em `extras` (o perfil de cada binário declara os seus).

    Sem context, o comando é sobre a máquina local — e continua sem `DOCKER_HOST`, que teria
    precedência e mandaria o comando para outro lugar.
    """
    nomes = tuple(BASE) + tuple(extras)
    env = {nome: os.environ[nome] for nome in nomes if nome in os.environ}
    if context:
        env["DOCKER_CONTEXT"] = context
    return env


def run(cmd, timeout, errors=None, context=None):
    """Roda um comando docker read-only. Valida na allowlist ANTES de executar.

    Retorna stdout (str) em sucesso, ou None se falhou/estourou o timeout.
    Se `errors` for uma lista, o MOTIVO real da falha é registrado nela — assim o relatório
    diz "certificado TLS expirou" em vez de um genérico "indisponível".
    NÃO captura NotAllowed — comando fora da allowlist é bug de dev, deve estourar.
    """
    check(cmd)  # levanta NotAllowed antes de tocar no subprocess
    label = " ".join(cmd[:3])
    env = ambiente(context)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False,
                           env=env)
    except subprocess.TimeoutExpired:
        _err(errors, label, f"timeout após {timeout}s")
        return None
    except OSError as e:
        _err(errors, label, f"não foi possível executar o docker ({e})")
        return None
    if p.returncode != 0:
        _err(errors, label, _clean(p.stderr) or f"saiu com código {p.returncode}")
        return None
    return p.stdout


def _clean(stderr):
    """Primeira linha útil do stderr, enxuta o suficiente pro relatório."""
    for line in (stderr or "").splitlines():
        line = line.strip()
        if line:
            return line[:300]
    return ""


def _err(errors, label, reason):
    if errors is not None:
        errors.append({"cmd": label, "reason": reason})
