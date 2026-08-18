"""Executor de comandos docker read-only: args-array (nunca shell), timeout, valida allowlist."""
import subprocess

from lib.allowlist import check


def run(cmd, timeout):
    """Roda um comando docker read-only. Valida na allowlist ANTES de executar.

    Retorna stdout (str) em sucesso, ou None se estourou o timeout ou o comando falhou.
    NÃO captura NotAllowed — comando fora da allowlist é bug de dev, deve estourar.
    """
    check(cmd)  # levanta NotAllowed antes de tocar no subprocess
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
    except (subprocess.TimeoutExpired, OSError):
        # timeout OU binário ausente/não-executável (docker não instalado) → não coletado
        return None
    return p.stdout if p.returncode == 0 else None
