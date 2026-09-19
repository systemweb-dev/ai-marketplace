"""phpunit."""
from pathlib import Path

from lib.stacks.base import Stack, ler_clover, ler_junit


class PHPUnit(Stack):
    linguagem, runner = "php", "phpunit"

    def _binario(self, escopo) -> str:
        local = Path(escopo) / "vendor" / "bin" / "phpunit"
        return str(local) if local.exists() else "phpunit"

    def comando_descoberta(self, escopo) -> list:
        return [self._binario(escopo), "--list-tests"]

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        saida = Path(saida)
        comando = [self._binario(escopo), "--log-junit", str(saida / "junit.xml")]
        if cobertura:
            comando += ["--coverage-clover", str(saida / "clover.xml")]
        return comando

    def ler_descoberta(self, texto: str) -> list:
        return [linha.strip(" -").strip() for linha in texto.splitlines()
                if linha.strip().startswith("-") and "::" in linha]

    def arquivos(self, ids, escopo):
        # phpunit lista "Classe::metodo": não dá para saber o arquivo sem parser — regra não se aplica
        return None

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        return ler_junit(Path(saida) / "junit.xml", limite_lento)

    def ler_cobertura(self, saida: Path, escopo) -> list:
        return ler_clover(Path(saida) / "clover.xml", raiz=Path(escopo).resolve())
