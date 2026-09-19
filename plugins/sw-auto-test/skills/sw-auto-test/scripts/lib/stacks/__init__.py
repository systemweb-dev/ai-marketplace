"""Escolhe o módulo da stack. Nesta task só detecta; rodar e normalizar entram no lote 2."""
from pathlib import Path

# (linguagem, runner, arquivos que provam a presença)
CANDIDATAS = [
    ("py", "pytest", ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")),
    ("js", "vitest", ("vitest.config.ts", "vitest.config.js", "vitest.config.mjs")),
    ("js", "jest", ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.json")),
    ("php", "phpunit", ("phpunit.xml", "phpunit.xml.dist", "phpunit.dist.xml")),
]


def _no_manifesto(raiz: Path, agulha: str) -> bool:
    for manifesto in ("package.json", "composer.json", "pyproject.toml"):
        arquivo = raiz / manifesto
        if arquivo.exists() and agulha in arquivo.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


# Extensão de teste → runner, quando NÃO há config nem manifesto. Só onde não há ambiguidade:
# entre vitest e jest não dá para adivinhar, e chutar errado faria a skill rodar o comando errado.
PALPITE_POR_EXTENSAO = {".py": ("py", "pytest"), ".php": ("php", "phpunit")}


def detectar(raiz, inventario=None) -> list:
    """Stacks presentes, na ordem em que aparecem em CANDIDATAS. `nativo` = temos módulo próprio.

    Config e manifesto vêm primeiro. Sem eles, o inventário decide: um projeto com `tests/test_x.py`
    rodado por `python -m pytest` não tem arquivo de config nenhum, e ficava de fora.
    """
    raiz = Path(raiz)
    achadas, vistos = [], set()
    for linguagem, runner, configs in CANDIDATAS:
        config = next((c for c in configs if (raiz / c).exists()), None)
        if config is None and not _no_manifesto(raiz, runner):
            continue
        if runner in vistos:
            continue
        vistos.add(runner)
        achadas.append({"linguagem": linguagem, "runner": runner, "nativo": True, "config": config})

    for arquivo in (inventario or {}).get("lista", []):
        palpite = PALPITE_POR_EXTENSAO.get(Path(arquivo["caminho"]).suffix)
        if palpite and palpite[1] not in vistos:
            vistos.add(palpite[1])
            achadas.append({"linguagem": palpite[0], "runner": palpite[1], "nativo": True,
                            "config": None})
    return achadas


from lib.stacks.js import Jest, Vitest        # noqa: E402
from lib.stacks.php import PHPUnit            # noqa: E402
from lib.stacks.py import Pytest              # noqa: E402

MODULOS = {"pytest": Pytest, "vitest": Vitest, "jest": Jest, "phpunit": PHPUnit}


def montar(runner):
    """Instância da stack. `KeyError` no runner sem módulo nativo — o chamador cai no heurístico."""
    return MODULOS[runner]()
