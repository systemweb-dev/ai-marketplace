"""NaN e infinito nunca podem chegar ao `report.json`.

`collect` grava com `allow_nan=False`: um único NaN aborta a gravação do relatório
INTEIRO, depois de minutos de coleta, com uma mensagem que não diz qual campo foi.

Este bug já derrubou o relatório antes e foi corrigido em `lib/extracao.py` e em
`lib/adaptadores/promql.py` — e `lib/enrich.py` ficou para trás. Três lugares convertem
float; os três precisam filtrar.
"""
import json
import math

import pytest

from lib.enrich import _fmt


@pytest.mark.parametrize("bruto", ["NaN", "nan", float("nan"), "Inf", float("inf"),
                                   "-Inf", float("-inf")])
@pytest.mark.parametrize("tipo", ["int", "pct", "ms", "raw"])
def test_nan_e_infinito_viram_none(tipo, bruto):
    """O Prometheus devolve NaN quando o histograma não tem amostra — um serviço com zero
    requisições na janela basta."""
    assert _fmt(tipo, bruto) is None


def test_numero_normal_continua_passando():
    assert _fmt("int", "42.6") == 43
    assert _fmt("pct", "87.44") == 87.4
    assert _fmt("ms", "652.629") == 652.6
    assert _fmt("raw", "1.5") == 1.5


def test_o_resultado_e_sempre_gravavel_em_json():
    """A trava de verdade: o que sai daqui tem de passar por `allow_nan=False`, que é
    como o `collect` grava."""
    valores = [_fmt(t, b) for t in ("int", "pct", "ms", "raw")
               for b in ("NaN", "Inf", "-Inf", float("nan"), "12.5", None, "texto")]

    json.dumps(valores, allow_nan=False)   # levanta ValueError se algum NaN escapou


def test_p95_sem_amostra_nao_derruba_a_coleta():
    """O caso real: `histogram_quantile` sem amostra num serviço sem tráfego."""
    serie = {"chatwoot": "NaN", "loja-api": "652.6"}

    saida = {k: _fmt("ms", v) for k, v in serie.items()}

    assert saida == {"chatwoot": None, "loja-api": 652.6}
    json.dumps(saida, allow_nan=False)
