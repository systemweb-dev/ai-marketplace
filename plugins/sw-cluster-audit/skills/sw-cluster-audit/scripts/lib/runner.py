"""Executor de comandos docker read-only: args-array (nunca shell), timeout, valida allowlist."""
import subprocess

from lib.allowlist import check


def run(cmd, timeout, errors=None):
    """Roda um comando docker read-only. Valida na allowlist ANTES de executar.

    Retorna stdout (str) em sucesso, ou None se falhou/estourou o timeout.
    Se `errors` for uma lista, o MOTIVO real da falha é registrado nela — assim o relatório
    diz "certificado TLS expirou" em vez de um genérico "indisponível".
    NÃO captura NotAllowed — comando fora da allowlist é bug de dev, deve estourar.
    """
    check(cmd)  # levanta NotAllowed antes de tocar no subprocess
    label = " ".join(cmd[:3])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
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
