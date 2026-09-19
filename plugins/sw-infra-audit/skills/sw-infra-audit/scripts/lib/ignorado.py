"""O git como verificador: esta pasta está mesmo fora do versionamento?

O arquivo de alvos guarda conexão e mora DENTRO do projeto, junto do relatório. Isso só é
seguro enquanto o git estiver ignorando a pasta — sem isso, o arquivo está a um `git add -A`
de virar público. Aqui não se escreve nada: só se pergunta ao git.

Único lugar da skill que roda `git` (o `lib/runner.py` é só docker, e a allowlist dele barra
qualquer outro binário).
"""
import subprocess

TEMPO = 5


def _git(args, pasta):
    """Devolve (código, saída) ou None quando não há git para perguntar."""
    try:
        p = subprocess.run(["git", *args], cwd=str(pasta), capture_output=True, text=True,
                           timeout=TEMPO, shell=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.returncode, p.stdout


def em_repositorio(pasta="."):
    """Sem git instalado ou fora de repositório, não há o que proteger."""
    resposta = _git(["rev-parse", "--is-inside-work-tree"], pasta)
    return resposta is not None and resposta[0] == 0 and resposta[1].strip() == "true"


def ignorado(caminho, pasta="."):
    """True quando o git já ignora este caminho (`git check-ignore`)."""
    resposta = _git(["check-ignore", "-q", "--", str(caminho)], pasta)
    return resposta is not None and resposta[0] == 0
