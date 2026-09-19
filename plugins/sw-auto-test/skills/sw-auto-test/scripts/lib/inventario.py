"""Varre o escopo: quais arquivos são de teste, quantos testes cada um tem, e de que suíte é."""
import os
import re
from pathlib import Path

from lib import sinais

IGNORAR = {".git", "node_modules", "vendor", "dist", "build", "coverage", "__pycache__",
           ".venv", "venv", ".tox", ".next", ".pytest_cache", ".phpunit.cache"}
EXTENSOES = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".php", ".go", ".rb", ".java", ".cs", ".rs"}
_NOME_DE_TESTE = re.compile(r"(^test_.*|.*_test|.*\.test|.*\.spec|.*Test|.*Spec|.*_spec)$")

_SUITE = (
    ("e2e", ("e2e", "end-to-end", "acceptance", "cypress", "playwright")),
    ("integracao", ("integration", "integracao", "feature", "functional")),
    ("unit", ("unit", "unitario", "unitarios")),
)


def eh_arquivo_de_teste(caminho: Path) -> bool:
    if caminho.suffix not in EXTENSOES:
        return False
    return bool(_NOME_DE_TESTE.match(caminho.stem))


def suite_de(relativo) -> str:
    partes = [p.lower() for p in Path(relativo).parts]
    for nome, marcas in _SUITE:
        if any(parte in marcas for parte in partes):
            return nome
    return "desconhecida"


def varrer(raiz) -> dict:
    """Inventário do escopo, com a lista de arquivos e a contagem de testes por suíte."""
    raiz = Path(raiz)
    lista, por_suite, total = [], {}, 0
    for pasta, subpastas, arquivos in os.walk(raiz):
        # poda antes de descer: node_modules e vendor são grandes demais para varrer e descartar
        subpastas[:] = sorted(s for s in subpastas if s not in IGNORAR)
        for nome in sorted(arquivos):
            caminho = Path(pasta) / nome
            if not eh_arquivo_de_teste(caminho):
                continue
            relativo = caminho.relative_to(raiz)
            try:
                texto = caminho.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            quantos = len(sinais.blocos(texto))
            if quantos == 0:
                continue
            suite = suite_de(relativo)
            lista.append({"caminho": str(relativo), "testes": quantos, "suite": suite})
            por_suite[suite] = por_suite.get(suite, 0) + quantos
            total += quantos
    lista.sort(key=lambda a: a["caminho"])
    return {"arquivos": len(lista), "testes": total, "por_suite": por_suite, "lista": lista}
