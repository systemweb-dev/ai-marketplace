"""NaN e infinito nunca podem chegar ao `report.json`.

`collect` grava com `allow_nan=False`: um único NaN aborta a gravação do relatório INTEIRO,
depois de minutos de coleta, com uma mensagem que não diz qual campo foi.

Este bug derrubou o relatório duas vezes, e as duas por causa de um conversor novo que não
filtrava. A primeira vez em `lib/extracao.py`; a segunda em `lib/enrich.py`, que ficou para
trás quando os outros dois foram corrigidos — e só apareceu quando alguém rodou a skill contra
infraestrutura real e a coleta inteira morreu no fim.

O `enrich.py` foi aposentado: as consultas dele vivem nos arquivos de família e quem converte
é o adaptador. Sobraram DOIS conversores, e o último teste aqui é o que faz um terceiro doer
antes de chegar a produção.
"""
import ast
import json
import math
import pathlib

import pytest

from lib.adaptadores.promql import _converter
from lib.extracao import _numero

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "lib"


@pytest.mark.parametrize("bruto", ["NaN", "nan", float("nan"), "Inf", float("inf"),
                                   "-Inf", float("-inf")])
@pytest.mark.parametrize("tipo", ["inteiro", "decimal"])
def test_promql_nan_e_infinito_viram_none(tipo, bruto):
    """O Prometheus devolve NaN quando o histograma não tem amostra — um serviço com zero
    requisições na janela basta."""
    assert _converter(bruto, tipo) is None


@pytest.mark.parametrize("bruto", ["NaN", float("nan"), "Inf", float("-inf")])
def test_extracao_nan_e_infinito_viram_none(bruto):
    assert _numero(bruto) is None


def test_numero_normal_continua_passando():
    # `int()` TRUNCA de propósito: `increase()` de 24 h devolve fração, e arredondar para cima
    # inflaria uma contagem que ninguém contou.
    assert _converter("42.6", "inteiro") == 42
    assert _converter("652.629", "decimal") == 652.63
    assert _numero("1.5") == 1.5


def test_o_resultado_e_sempre_gravavel_em_json():
    """A trava de verdade: o que sai dos conversores tem de passar por `allow_nan=False`, que
    é como o `collect` grava."""
    brutos = ["NaN", "Inf", "-Inf", float("nan"), "12.5", None, "texto"]
    valores = [_converter(b, t) for t in ("inteiro", "decimal") for b in brutos]
    valores += [_numero(b) for b in brutos]

    json.dumps(valores, allow_nan=False)   # levanta ValueError se algum NaN escapou


def test_p95_sem_amostra_nao_derruba_a_coleta():
    """O caso real: `histogram_quantile` sem amostra num serviço sem tráfego."""
    serie = {"sem_trafego": "NaN", "com_trafego": "652.6"}

    saida = {k: _converter(v, "decimal") for k, v in serie.items()}

    assert saida == {"sem_trafego": None, "com_trafego": 652.6}
    json.dumps(saida, allow_nan=False)


# ---------------------------------------------------------------- a trava estrutural
def test_todo_float_do_pacote_passa_por_um_conversor_que_filtra():
    """Quem chama `float()` tem de filtrar NaN no mesmo corpo de função.

    Os dois episódios tiveram a mesma forma: alguém escreveu um `float()` novo, os testes
    ficaram verdes, e o relatório morreu na gravação — minutos de coleta perdidos, com uma
    mensagem que não dizia qual campo foi. Teste de valor não pega isso, porque o conversor
    novo não aparece em teste nenhum; é a ausência que precisa doer.

    Um `float()` que não filtra é permitido só onde o resultado NÃO vai ao relatório, e aí a
    função precisa dizer isso por escrito — com `isnan` no corpo ou com `# nan-ok:` e o
    motivo. Lista de exceções em arquivo separado envelhece calada.
    """
    faltando = []
    for caminho in sorted(RAIZ.rglob("*.py")):
        fonte = caminho.read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        for no in ast.walk(arvore):
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            corpo = ast.get_source_segment(fonte, no) or ""
            chama_float = any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "float"
                              for c in ast.walk(no))
            if not chama_float:
                continue
            if "isnan" in corpo or "nan-ok:" in corpo:
                continue
            faltando.append(f"{caminho.relative_to(RAIZ)}:{no.lineno} {no.name}")

    assert not faltando, ("estas funções convertem float sem filtrar NaN/inf — um deles no "
                          "report.json aborta a gravação INTEIRA em `allow_nan=False`:\n  "
                          + "\n  ".join(faltando))


# ---------------------------------------------------------------- o que a trava achou
def test_pontuacao_infinita_nao_derruba_a_capa():
    """`round(float('inf'))` levanta OverflowError, e o `except` da nota só pega TypeError e
    ValueError — a capa morria inteira por causa de uma pontuação.

    Pior: NaN escapava para `min(100, nan)`, que devolve 100 por como a comparação com NaN é
    sempre falsa. A dimensão corrompida saía com a MELHOR nota possível.
    """
    from lib.nota import _num

    assert _num(float("inf")) is None
    assert _num(float("-inf")) is None
    assert _num(float("nan")) is None
    assert _num(87.4) == 87


def test_timeout_nao_numerico_na_config_nao_derruba_a_coleta():
    """`timeout = nan` é TOML válido, e `int(min(nan, restante))` levanta ValueError no meio
    da coleta — depois de a auditoria já ter começado a falar com a infraestrutura."""
    from lib.orcamento import Prazo

    assert Prazo(60).timeout(float("nan")) == 1
    assert Prazo(60).timeout(float("inf")) >= 1
    assert Prazo(float("nan")).timeout(5) == 1
    assert Prazo(60).timeout(5) == 5
