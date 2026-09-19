"""vitest e jest — runners diferentes, mesmo formato de resultado em JSON."""
import json
from pathlib import Path

from lib.stacks.base import Stack, faixa, relativizar


def _ler_json(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _resultado(dados, limite_lento: float):
    """`testResults[].assertionResults[]` com status e duração em milissegundos."""
    if not isinstance(dados, dict):
        return None
    passou = falhou = pulado = 0
    total_ms = 0.0
    lentos = []
    for arquivo in dados.get("testResults", []):
        for caso in arquivo.get("assertionResults", []):
            duracao = float(caso.get("duration") or 0)
            total_ms += duracao
            estado = caso.get("status")
            if estado == "passed":
                passou += 1
                if duracao / 1000 >= limite_lento:
                    lentos.append({"teste": caso.get("fullName", ""), "faixa": faixa(duracao / 1000)})
            elif estado in ("failed", "broken"):
                falhou += 1
            else:
                pulado += 1
    return {"passou": passou, "falhou": falhou, "pulado": pulado, "verde": falhou == 0,
            "duracao_faixa": faixa(total_ms / 1000), "lentos": lentos}


class Vitest(Stack):
    linguagem, runner = "js", "vitest"

    def comando_descoberta(self, escopo) -> list:
        return ["vitest", "list", "--run"]

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        saida = Path(saida)
        comando = ["vitest", "run", "--reporter=json", f"--outputFile={saida / 'vitest.json'}"]
        if cobertura:
            comando += ["--coverage", "--coverage.reporter=cobertura",
                        f"--coverage.reportsDirectory={saida / 'cobertura'}"]
        return comando

    def ler_descoberta(self, texto: str) -> list:
        return [linha.strip() for linha in texto.splitlines()
                if linha.strip() and not linha.startswith(("✓", "RUN", "DEV"))]

    def arquivos(self, ids, escopo):
        # `vitest list` imprime "arquivo > suite > teste"
        return {identificador.split(" > ")[0].strip() for identificador in ids}

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        return _resultado(_ler_json(Path(saida) / "vitest.json"), limite_lento)

    def ler_cobertura(self, saida: Path, escopo) -> list:
        from lib.stacks.base import ler_cobertura_xml
        return ler_cobertura_xml(Path(saida) / "cobertura" / "cobertura-coverage.xml", raiz=escopo)


class Jest(Stack):
    linguagem, runner = "js", "jest"

    def comando_descoberta(self, escopo) -> list:
        return ["jest", "--listTests"]

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        saida = Path(saida)
        comando = ["jest", "--ci", "--json", f"--outputFile={saida / 'jest.json'}"]
        if cobertura:
            comando += ["--coverage", "--coverageReporters=cobertura",
                        f"--coverageDirectory={saida / 'cobertura'}"]
        return comando

    def ler_descoberta(self, texto: str) -> list:
        return [linha.strip() for linha in texto.splitlines() if linha.strip()]

    def arquivos(self, ids, escopo):
        # `jest --listTests` devolve caminho absoluto
        return {relativizar(identificador, escopo) for identificador in ids}

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        return _resultado(_ler_json(Path(saida) / "jest.json"), limite_lento)

    def ler_cobertura(self, saida: Path, escopo) -> list:
        from lib.stacks.base import ler_cobertura_xml
        return ler_cobertura_xml(Path(saida) / "cobertura" / "cobertura-coverage.xml", raiz=escopo)
