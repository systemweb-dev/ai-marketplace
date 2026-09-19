"""git de leitura para esta skill. Nenhum subcomando que escreve entra na lista.

Diferente da sw-pr-message, `status` é permitido: esta skill já executa o runner do projeto,
que é muito mais invasivo do que os filtros de limpeza que o `status` dispara. O que não muda é
a regra de nunca executar git que altere repositório.
"""
import os
import subprocess
from pathlib import Path

LEITURA = frozenset({"rev-parse", "status", "ls-files"})


class GitIndisponivel(Exception):
    """Não é repositório git, ou o comando falhou."""


def _git(args, cwd) -> str:
    args = list(args)
    if not args or args[0] not in LEITURA:
        raise ValueError(f"subcomando não permitido: {args[:1]!r}")
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    r = subprocess.run(["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise GitIndisponivel(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def dentro_de_repo(cwd) -> bool:
    try:
        return _git(["rev-parse", "--is-inside-work-tree"], cwd).strip() == "true"
    except (GitIndisponivel, FileNotFoundError):
        return False


def toplevel(cwd) -> Path:
    return Path(_git(["rev-parse", "--show-toplevel"], cwd).strip()).resolve()


def git_path(cwd, sub: str) -> Path:
    """Certo também em worktree e submódulo, onde `.git` é um arquivo."""
    saida = Path(_git(["rev-parse", "--git-path", sub], cwd).strip())
    return saida if saida.is_absolute() else (Path(cwd) / saida).resolve()


def branch(cwd):
    nome = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd).strip()
    return None if nome == "HEAD" else nome


def head(cwd) -> str:
    return _git(["rev-parse", "HEAD"], cwd).strip()


def rastreado(cwd, caminho) -> bool:
    try:
        return bool(_git(["ls-files", "--error-unmatch", "--", str(caminho)], cwd).strip())
    except GitIndisponivel:
        return False


def limpo(cwd, caminho) -> bool:
    """Versionado e sem alteração pendente — pré-requisito da prova do vermelho."""
    if not rastreado(cwd, caminho):
        return False
    return _git(["status", "--porcelain", "--", str(caminho)], cwd).strip() == ""
