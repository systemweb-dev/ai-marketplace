"""`reconhecer` pergunta "quem está publicando aqui?" — uma consulta por família.

A consulta de descoberta depende de (fonte, família), NUNCA do componente. É isso que faz o
passe de identificação custar F consultas por fonte em vez de F por componente, e é por isso
que inverter a ordem sai mais barato do que o estado anterior.
"""
from lib.adaptadores import promql

from test_adaptador_promql import CONTEXTO, _vetor, prometheus  # noqa: F401


def test_uma_consulta_por_familia_e_devolve_os_valores(prometheus):
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "edge"}, 1)])))

    reconhecidas = promql.reconhecer(base, dict(CONTEXTO, cache={}))

    traefik = next(f for f in reconhecidas if f["familia"] == "traefik")
    assert traefik["valores"] == ["edge"]
    assert traefik["papel"] == "entrada" and traefik["identifica_papel"] is True
    assert len([q for q in falso.RECEBIDAS if "traefik_service_requests_total" in q]) == 1


def test_familia_sem_serie_na_fonte_nao_entra(prometheus):
    base, falso = prometheus

    assert promql.reconhecer(base, dict(CONTEXTO, cache={})) == []


def test_o_cache_vale_para_a_fonte_inteira(prometheus):
    """O cache antigo era gravado numa CÓPIA do contexto feita por pergunta
    (`collect.py:236`), e morria com ela: a mesma consulta de identificação rodava 3× para o
    mesmo componente. O molde certo é `contexto["cache"]`, que `admin_http` já usa."""
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "edge"}, 1)])))
    contexto = dict(CONTEXTO, cache={})

    promql.reconhecer(base, contexto)
    promql.reconhecer(base, contexto)

    assert len([q for q in falso.RECEBIDAS if "traefik_service_requests_total" in q]) == 1


def test_o_cache_sobrevive_a_copia_rasa_do_contexto(prometheus):
    """`collect.py` copia o contexto por pergunta (`dict(contexto, timeout=...)`). A cópia é
    RASA, então `cache` é o MESMO objeto — era disso que o cache anterior não se aproveitava,
    porque gravava a chave no topo da cópia em vez de dentro do `cache` compartilhado."""
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "edge"}, 1)])))
    contexto = dict(CONTEXTO, cache={})

    # A ORDEM importa, e é o que fazia este teste passar com o bug de volta. `collect` chama
    # `reconhecer` SEMPRE pela cópia (`contexto_fonte = dict(contexto, timeout=...)`), então a
    # GRAVAÇÃO acontece através dela. Gravando pelo original e lendo pela cópia, o cache antigo
    # — a chave no topo do contexto — também sobreviveria, e o teste não provava nada.
    promql.reconhecer(base, dict(contexto, timeout=1))
    promql.reconhecer(base, dict(contexto, timeout=2))

    assert len([q for q in falso.RECEBIDAS if "traefik_service_requests_total" in q]) == 1
