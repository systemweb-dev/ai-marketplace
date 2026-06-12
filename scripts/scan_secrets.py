#!/usr/bin/env python3
"""Gate de segurança: procura credenciais e dados pessoais antes de commit/push.

Como este repositório é PÚBLICO, nada de segredo (chave de API, token, chave
privada, .env) nem dado pessoal (caminho do home, e-mail do git) pode vazar.

O script escaneia o CONTEÚDO que está prestes a ir para o git e sai com código
!= 0 se achar algo suspeito — bloqueando o commit/push quando chamado por hook.

Modos:
    python3 scripts/scan_secrets.py staged          # conteúdo staged (pre-commit)
    python3 scripts/scan_secrets.py range A..B       # arquivos do range (pre-push)
    python3 scripts/scan_secrets.py paths a b c       # arquivos específicos no disco

Nada pessoal é embutido aqui: o home (`$HOME`) e o e-mail (`git config user.email`)
são lidos em tempo de execução.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# Extensões/arquivos binários ou irrelevantes que não precisam ser escaneados.
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mov", ".lock",
}

# Valores claramente-placeholder que NÃO são segredo real.
PLACEHOLDER = re.compile(
    r"(?i)(example|exemplo|placeholder|your[-_ ]|seu[-_ ]|sample|dummy|fake|"
    r"changeme|redacted|xxx+|\.\.\.|<[^>]+>|\{\{|process\.env|os\.environ|getenv|env\()"
)

# Regras de detecção. Cada uma: (rótulo, regex).
RULES: list[tuple[str, re.Pattern]] = [
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(gh[posru]_[A-Za-z0-9]{30,}|github_pat_[0-9A-Za-z_]{20,})\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("OpenAI/Anthropic key", re.compile(r"\b(sk|sk-ant)-[A-Za-z0-9_\-]{20,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("caminho /home", re.compile(r"/home/[A-Za-z][A-Za-z0-9._-]*")),
    ("caminho /Users", re.compile(r"/Users/[A-Za-z][A-Za-z0-9._-]*")),
]

# Atribuição genérica de segredo (chave sensível seguida de valor entre aspas).
GENERIC_SECRET = re.compile(
    r"""(?ix)
    \b(pass(word|wd)?|secret|api[_-]?key|access[_-]?token|auth[_-]?token|
       client[_-]?secret|private[_-]?key|db[_-]?pass|token)\b
    \s*[:=]\s*
    (['"])(?P<val>[^'"]{6,})\3
    """
)


def runtime_rules() -> list[tuple[str, re.Pattern]]:
    """Regras que dependem do ambiente (não ficam escritas no arquivo)."""
    extra = []
    home = os.environ.get("HOME", "")
    if home and home not in ("/root", "/home"):
        extra.append(("seu diretório home", re.compile(re.escape(home))))
    try:
        email = subprocess.run(
            ["git", "config", "user.email"], capture_output=True, text=True
        ).stdout.strip()
        if email:
            extra.append(("seu e-mail do git", re.compile(re.escape(email))))
    except OSError:
        pass
    return extra


def scan_text(text: str, filename: str, extra_rules) -> list[str]:
    findings = []
    for i, line in enumerate(text.splitlines(), 1):
        if "noscan" in line:  # pragma explícito para exentar uma linha (use com cuidado)
            continue
        for label, rx in RULES + extra_rules:
            if rx.search(line):
                findings.append(f"  {filename}:{i}  [{label}]  {line.strip()[:120]}")
        m = GENERIC_SECRET.search(line)
        if m and not PLACEHOLDER.search(m.group("val")):
            findings.append(f"  {filename}:{i}  [segredo atribuído]  {line.strip()[:120]}")
    return findings


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def content_staged(path: str) -> str | None:
    out = subprocess.run(["git", "show", f":{path}"], capture_output=True)
    return out.stdout.decode("utf-8", "ignore") if out.returncode == 0 else None


def content_at(rev: str, path: str) -> str | None:
    out = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True)
    return out.stdout.decode("utf-8", "ignore") if out.returncode == 0 else None


def is_scannable(path: str) -> bool:
    return Path(path).suffix.lower() not in SKIP_SUFFIXES


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    mode = sys.argv[1]
    extra = runtime_rules()
    findings: list[str] = []

    if mode == "staged":
        files = git("diff", "--cached", "--name-only", "--diff-filter=ACMR").split()
        for f in files:
            if not is_scannable(f):
                continue
            text = content_staged(f)
            if text:
                findings += scan_text(text, f, extra)

    elif mode == "range" and len(sys.argv) >= 3:
        rng = sys.argv[2]
        head = rng.split("..")[-1] or "HEAD"
        files = git("diff", "--name-only", "--diff-filter=ACMR", rng).split()
        for f in files:
            if not is_scannable(f):
                continue
            text = content_at(head, f)
            if text:
                findings += scan_text(text, f, extra)

    elif mode == "paths":
        for f in sys.argv[2:]:
            if not is_scannable(f) or not Path(f).is_file():
                continue
            findings += scan_text(Path(f).read_text("utf-8", "ignore"), f, extra)

    else:
        print(f"modo inválido: {mode}", file=sys.stderr)
        return 2

    if findings:
        print("\n🚨 GATE DE SEGURANÇA: possível conteúdo sensível detectado\n", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        print(
            "\nRevise os itens acima. Se for falso positivo, ajuste/whiteliste e rode de novo.\n"
            "Para pular intencionalmente (use com MUITO cuidado): git commit --no-verify\n",
            file=sys.stderr,
        )
        return 1

    print("✓ gate de segurança: nada sensível detectado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
