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

# variáveis que escolhem COM QUEM falar: quem decide isso é o alvo, nunca o shell de quem roda
ESCOLHEM_O_DAEMON = ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")


def ambiente(context):
    """O ambiente do processo filho: o seu, sem as variáveis que escolhem daemon, mais o
    context do alvo (quando há um). Sem context, o comando é sobre a máquina local."""
    env = {chave: valor for chave, valor in os.environ.items()
           if chave not in ESCOLHEM_O_DAEMON}
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
