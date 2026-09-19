"""Onde ficam fatos, achados, backups e a saída do runner — sempre fora da árvore de trabalho."""
import hashlib
import tempfile
from pathlib import Path

from lib import gitinfo

NOME = "sw-auto-test"


def base(raiz) -> Path:
    """`<git-path>/sw-auto-test` no repositório; no projeto sem git, uma pasta fixa no temp."""
    raiz = Path(raiz)
    if gitinfo.dentro_de_repo(raiz):
        return gitinfo.git_path(raiz, NOME)
    digitais = hashlib.sha256(str(raiz.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"{NOME}-{digitais}"


def criar(raiz) -> Path:
    destino = base(raiz)
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def fatos(raiz) -> Path:
    return base(raiz) / "fatos.json"


def achados(raiz) -> Path:
    return base(raiz) / "achados.json"


def backups(raiz) -> Path:
    return base(raiz) / "backup"


def saida(raiz) -> Path:
    """Onde o runner grava junit/cobertura, por flag explícita."""
    return base(raiz) / "saida"
