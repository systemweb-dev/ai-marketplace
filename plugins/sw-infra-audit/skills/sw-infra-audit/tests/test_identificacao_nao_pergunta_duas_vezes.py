"""A identificação não pergunta duas vezes a mesma coisa.

`count by (etiqueta) (serie)` devolve os valores que a etiqueta TEM. Se o nome do componente
está entre eles, `count(serie{etiqueta="<nome>"})` é não-vazio por construção: mesma série,
mesmo instante (`--at`), mesma fonte. A segunda consulta não podia descobrir nada que a
primeira não tivesse dito.

O que ela fazia era pior que gastar tráfego. Quando a confirmação voltava vazia por qualquer
motivo — um instante diferente, um relabel no meio, um proxy que engole a segunda chamada —, o
adaptador caía no ramo de "nenhum valor casa com este componente" e o relatório dizia que o
exporter cobre vários componentes e nenhum é aquele. Com o valor EXATO na mão. Rodando contra
um cluster de cinco serviços, foi o que apareceu: cinco componentes com `sem dados` e um motivo
que afirmava o contrário do que a fonte tinha acabado de responder.
"""
import pytest

from lib.adaptadores import promql
from test_adaptador_promql import CONTEXTO, _vetor, prometheus  # noqa: F401


def _componente(base, nome="proxy"):
    return {"nome": nome, "papel": "entrada", "metricas_url": base}


def test_uma_consulta_de_identificacao_por_familia(prometheus):
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "proxy"}, 1)])))
    falso.REGRAS.append(("sum(increase(traefik_service_requests_total", _vetor([({}, 7)])))

    resposta = promql.perguntar("entrada.volume_na_janela", _componente(base), dict(CONTEXTO))

    assert resposta["valor"] == 7
    assert resposta["fonte"] == "promql:traefik", "casou pela etiqueta, não pelo exporter inteiro"
    identificacao = [q for q in falso.RECEBIDAS if q.startswith("count")]
    assert len(identificacao) == 1, identificacao


def test_valor_que_casa_nunca_vira_nenhum_valor_casa(prometheus):
    """O defeito que apareceu rodando: a etiqueta tinha o valor exato do componente, e o
    relatório dizia que nenhum valor casava com ele."""
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "proxy"}, 1), ({"job": "outro"}, 1)])))
    falso.REGRAS.append(("sum(increase(traefik_service_requests_total", _vetor([({}, 9)])))
    # NENHUMA regra para `count(serie{job="proxy"})`: a confirmação voltaria vazia

    resposta = promql.perguntar("entrada.volume_na_janela", _componente(base), dict(CONTEXTO))

    assert resposta.get("sem_dados") is not True, resposta.get("motivo")
    assert resposta["valor"] == 9
    assert resposta["fonte"] == "promql:traefik"
