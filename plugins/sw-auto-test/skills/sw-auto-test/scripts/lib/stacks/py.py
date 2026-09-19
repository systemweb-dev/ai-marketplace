"""pytest."""
from pathlib import Path

from lib.stacks.base import Stack, ler_cobertura_xml, ler_junit


class Pytest(Stack):
    linguagem, runner = "py", "pytest"

    def comando_descoberta(self, escopo) -> list:
        return ["pytest", "--collect-only", "-q", "--no-header", "-p", "no:cacheprovider"]

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        comando = ["pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                   f"--junit-xml={Path(saida) / 'junit.xml'}"]
        if cobertura:
            comando += ["--cov", f"--cov-report=xml:{Path(saida) / 'cobertura.xml'}"]
        return comando

    def ler_descoberta(self, texto: str) -> list:
        # id parametrizado tem espaço e colchete: casar por "::" é mais fiel que uma regex estreita
        return [linha.strip() for linha in texto.splitlines()
                if "::" in linha and not linha.lstrip().startswith(("=", "-", "<"))]

    def arquivos(self, ids, escopo):
        return {identificador.split("::")[0] for identificador in ids}

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        return ler_junit(Path(saida) / "junit.xml", limite_lento)

    def ler_cobertura(self, saida: Path, escopo) -> list:
        return ler_cobertura_xml(Path(saida) / "cobertura.xml", raiz=escopo)
