"""O ciclo inteiro por `coletar_alvo`: o papel confirmado decide QUAIS perguntas são feitas.

Este arquivo existe porque a suíte ficava 100% verde com o passe rodando DEPOIS do laço de
perguntas. Nesse estado o componente termina com `papel_origem = "exporter redis-exporter"` — o
relatório diria "confirmado" — e recebeu as perguntas do papel PROVISÓRIO, as duas `sem_dados`.
Papel certo no papel, medidas erradas no relatório.

Nenhum teste de unidade pega isso: eles exercitam `identificar` e `perguntar` separados, e a
ordem entre os dois não é propriedade de nenhum dos dois.
"""
import collect
from lib.adaptadores import promql

from test_adaptador_promql import _vetor, prometheus  # noqa: F401

CONTEXTO = {"timeout": 2, "http_timeout": 2, "orcamento": 120, "janela": "24h",
            "at": "2026-10-05T10:00:00Z"}


def _coletor(componentes):
    def coletar(alvo, contexto):
        return {"saude": "🟢", "dimensoes": {}, "fatos": {}, "achados": [],
                "componentes": componentes}
    return coletar


def _componente(nome, base, papel="app", origem="padrão", exportador=False):
    return {"nome": nome, "papel": papel, "papel_origem": origem, "metricas_url": base,
            "exportador": exportador, "respostas": [], "achados": []}


def test_as_perguntas_feitas_sao_as_do_papel_CONFIRMADO(prometheus):
    """A ordem é a garantia: o passe tem de rodar ANTES do laço de perguntas.

    Um fork de cache chega como `app` (o `produtos.toml` não o conhece pelo nome). Se as
    perguntas forem escolhidas antes do passe, ele recebe `app.cpu`/`app.memoria` e as duas
    saem `sem_dados` — com o papel dizendo `cache` ao lado.
    """
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (redis_memory_used_bytes)",
                         _vetor([({"job": "cache_fork"}, 1)])))
    falso.REGRAS.append(("sum(redis_memory_used_bytes", _vetor([({}, 734003200)])))
    falso.REGRAS.append(("sum(redis_evicted_keys", _vetor([({}, 0)])))

    registro = collect.coletar_alvo(
        {"nome": "c", "tipo": "docker", "context": "ctx", "metricas_url": base},
        _coletor([_componente("cache_fork", base)]), dict(CONTEXTO), [promql])

    componente = registro["componentes"][0]
    assert componente["papel"] == "cache"
    assert componente["papel_origem"] == "exporter redis-exporter"
    perguntadas = {r["pergunta"] for r in componente["respostas"]}
    assert perguntadas == {"cache.memoria_usada", "cache.evicções"}, \
        "as perguntas vieram do papel provisório: o passe rodou tarde demais"
    respondida = next(r for r in componente["respostas"]
                      if r["pergunta"] == "cache.memoria_usada")
    assert respondida["valor"] == 734003200
    assert respondida["fonte"] == "promql:redis-exporter"


def test_o_papel_declarado_sobrevive_ao_passe_no_caminho_real(prometheus):
    """Restrição verificável 3, no fluxo de produção e não na função pura.

    Com `papel_origem` fixo em `padrão` — o que acontece se o coletor não o gravar — `resolver`
    entra no ramo que sobrescreve, e a evidência vence a declaração do dono.
    """
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (redis_memory_used_bytes)",
                         _vetor([({"job": "infra_x"}, 1)])))

    registro = collect.coletar_alvo(
        {"nome": "c", "tipo": "docker", "context": "ctx", "metricas_url": base},
        _coletor([_componente("infra_x", base, papel="fila", origem="declarado")]),
        dict(CONTEXTO), [promql])

    componente = registro["componentes"][0]
    assert componente["papel"] == "fila", "a evidência não pode vencer a declaração do dono"
    assert componente["papel_origem"] == "declarado"


def test_o_container_do_exportador_nao_e_confirmado_no_caminho_real(prometheus):
    """D4 no fluxo de produção. Com `exportador` não gravado pelo coletor, o papel sai
    invertido: o exporter vira o produto, e o produto fica sem identidade."""
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (redis_memory_used_bytes)",
                         _vetor([({"job": "redis-exporter"}, 1)])))

    registro = collect.coletar_alvo(
        {"nome": "c", "tipo": "docker", "context": "ctx", "metricas_url": base},
        _coletor([_componente("monitoring_redis-exporter", base, exportador=True)]),
        dict(CONTEXTO), [promql])

    componente = registro["componentes"][0]
    assert componente["papel"] == "app"
    assert componente["papel_origem"] == "padrão"
