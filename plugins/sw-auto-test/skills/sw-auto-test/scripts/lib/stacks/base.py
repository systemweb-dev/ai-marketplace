"""O que é comum a todas as stacks: leitura de junit/cobertura e faixas de duração.

Faixa em vez de segundo exato é o que deixa o relatório determinístico (restrição 4).
"""
import xml.etree.ElementTree as ET
from pathlib import Path

FAIXAS = ((1, "<1s"), (10, "1-10s"), (60, "10-60s"), (300, "1-5min"), (float("inf"), ">5min"))
LIMITE_DE_LENTO = {"unit": 1.0, "integracao": 10.0, "e2e": 60.0, "desconhecida": 10.0}


def faixa(segundos: float) -> str:
    for teto, nome in FAIXAS:
        if segundos < teto:
            return nome
    return FAIXAS[-1][1]


def _arvore(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return None
    try:
        return ET.parse(caminho).getroot()
    except ET.ParseError:
        return None


def ler_junit(caminho, limite_lento: float = 1.0):
    """Contagens, faixa de duração total e os testes acima do limite. `None` se não deu para ler."""
    raiz = _arvore(caminho)
    if raiz is None:
        return None
    casos = raiz.iter("testcase")
    passou = falhou = pulado = 0
    soma_dos_casos = 0.0
    lentos = []
    for caso in casos:
        duracao = float(caso.get("time") or 0)
        soma_dos_casos += duracao
        nome = f"{caso.get('classname', '')}::{caso.get('name', '')}".strip(":")
        if caso.find("failure") is not None or caso.find("error") is not None:
            falhou += 1
        elif caso.find("skipped") is not None:
            pulado += 1
        else:
            passou += 1
            if duracao >= limite_lento:
                lentos.append({"teste": nome, "faixa": faixa(duracao)})
    # o tempo da suíte inclui setup/teardown; a soma dos casos ignora isso e mente para menos.
    # Só os filhos diretos: `iter` desceria em suíte aninhada e contaria o mesmo tempo duas vezes.
    filhos = raiz.findall("testsuite") or ([raiz] if raiz.tag == "testsuite" else [])
    tempos = [float(s.get("time")) for s in filhos if s.get("time")]
    total = sum(tempos) if tempos else soma_dos_casos
    return {"passou": passou, "falhou": falhou, "pulado": pulado, "verde": falhou == 0,
            "duracao_faixa": faixa(total), "lentos": lentos}


def relativizar(caminho, raiz) -> str:
    """Caminho absoluto dentro da raiz vira relativo — caminho de máquina nos fatos quebraria
    o determinismo do relatório e ainda vazaria o diretório de quem rodou."""
    alvo = Path(caminho)
    if raiz and alvo.is_absolute():
        raiz = Path(raiz).resolve()
        if alvo.is_relative_to(raiz):
            return str(alvo.relative_to(raiz))
    return str(caminho)


def _pct(valor) -> int:
    return int(round(float(valor) * 100))


def ler_cobertura_xml(caminho, raiz=None) -> list:
    """Formato Cobertura (pytest-cov, coverage.py, istanbul --reporter=cobertura)."""
    arvore = _arvore(caminho)   # `raiz` aqui é o parâmetro do projeto, não a raiz do XML
    if arvore is None:
        return []
    saida = []
    for classe in arvore.iter("class"):
        nome = classe.get("filename")
        if not nome:
            continue
        saida.append({"caminho": relativizar(nome, raiz),
                      "linhas_pct": _pct(classe.get("line-rate") or 0),
                      "ramos_pct": _pct(classe.get("branch-rate") or 0)})
    return saida


def ler_clover(caminho, raiz=None) -> list:
    """Formato clover (phpunit). `raiz` recorta o caminho absoluto do container/CI."""
    arvore = _arvore(caminho)
    if arvore is None:
        return []
    saida = []
    for arquivo in arvore.iter("file"):
        metrica = arquivo.find("metrics")
        nome = arquivo.get("name")
        if metrica is None or not nome:
            continue
        nome = relativizar(nome, raiz)
        declaracoes = float(metrica.get("statements") or 0)
        condicionais = float(metrica.get("conditionals") or 0)
        saida.append({
            "caminho": nome,
            "linhas_pct": int(round(float(metrica.get("coveredstatements") or 0) / declaracoes * 100))
                          if declaracoes else 0,
            "ramos_pct": int(round(float(metrica.get("coveredconditionals") or 0) / condicionais * 100))
                         if condicionais else 0,
        })
    return saida


class Stack:
    """Contrato das stacks nativas. Cada uma só diz QUAL comando rodar e como ler a saída."""

    linguagem = runner = ""

    def comando_descoberta(self, escopo) -> list:
        raise NotImplementedError

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        raise NotImplementedError

    def ler_descoberta(self, texto: str) -> list:
        raise NotImplementedError

    def arquivos(self, ids, escopo):
        """Arquivos que a descoberta listou, relativos ao escopo.

        `None` quando a stack não sabe dizer (phpunit lista classe, não arquivo) — e aí a regra
        de "arquivo não descoberto" não se aplica, em vez de acusar a suíte inteira.
        """
        return None

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        raise NotImplementedError

    def ler_cobertura(self, saida: Path, escopo) -> list:
        return []
