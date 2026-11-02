"""Do formato do catálogo ao texto do bloco, sem atalho.

Os testes de bloco montavam o dicionário à mão, e por isso bytes crus e status desligado no
adaptador passavam. Aqui a entrada é a resposta da fonte (Prometheus ou API de administração),
e o caminho é o de produção: `collect.responder` → `dados_do_papel` → `render_bloco`.
"""
import json

import collect
from lib.adaptadores import admin_http, promql
from lib.blocos import render_bloco
from lib.dados_blocos import dados_do_papel
from lib.orcamento import Prazo
from test_adaptador_promql import _vetor, prometheus  # noqa: F401

CONTEXTO = {"at": "2026-09-19T10:00:00Z", "janela": "24h", "timeout": 2}
GIB = 1024 ** 3


def _bloco(papel_do_bloco, papel, base, nome):
    componente = {"nome": nome, "papel": papel, "metricas_url": base, "papel_origem": "padrão",
                  "exportador": False, "respostas": []}
    contexto = dict(CONTEXTO, cache={})
    collect.identificar([componente], contexto, [promql], Prazo(120))
    collect.responder(componente, contexto, [promql], Prazo(120))
    return render_bloco(papel_do_bloco, dados_do_papel(papel_do_bloco, [{"componentes": [componente]}]))


def test_banco_mostra_gb_a_partir_dos_bytes_do_exporter(prometheus):
    base, falso = prometheus
    falso.REGRAS += [("count by (job) (pg_stat_database_numbackends)", _vetor([({"job": "pg"}, 1)])),
                     ("sum(pg_stat_database_numbackends", _vetor([({}, 212)])),
                     ("sum(pg_database_size_bytes", _vetor([({}, 86 * GIB)]))]

    html = _bloco("banco", "banco", base, "pg")

    assert "86 GB" in html and "212 conexões" in html
    assert str(86 * GIB) not in html


def test_banco_mysql_tambem_mostra_mb(prometheus):
    base, falso = prometheus
    falso.REGRAS += [("count by (job) (mysql_global_status_threads_connected)", _vetor([({"job": "db"}, 1)])),
                     ("sum(mysql_global_status_threads_connected", _vetor([({}, 1)])),
                     ("sum(mysql_info_schema_table_size", _vetor([({}, 90 * 1024 ** 2)]))]

    html = _bloco("banco", "banco", base, "db")

    assert "90 MB" in html and "1 conexão" in html


def test_cache_mostra_memoria_legivel(prometheus):
    base, falso = prometheus
    falso.REGRAS += [("count by (job) (redis_memory_used_bytes)", _vetor([({"job": "redis"}, 1)])),
                     ("sum(redis_memory_used_bytes", _vetor([({}, int(1.8 * GIB))])),
                     ("sum(increase(redis_evicted_keys_total", _vetor([({}, 3)]))]

    html = _bloco("cache", "cache", base, "redis")

    assert "1,8 GB" in html and "3 evicções" in html
    assert str(int(1.8 * GIB)) not in html


def test_consumo_mostra_cores_e_gb_a_partir_do_cadvisor(prometheus):
    base, falso = prometheus
    etiqueta = "container_label_com_docker_swarm_service_name"
    falso.REGRAS += [(f"count by ({etiqueta}) (container_cpu_usage_seconds_total)",
                      _vetor([({etiqueta: "loja_api"}, 1)])),
                     ("sum(rate(container_cpu_usage_seconds_total", _vetor([({}, 250.0)])),
                     ("sum(container_memory_usage_bytes", _vetor([({}, int(1.9 * GIB))]))]

    html = _bloco("consumo", "app", base, "loja_api")

    assert "2,5 cores" in html and "1,9 GB" in html
    assert "250%" not in html and str(int(1.9 * GIB)) not in html


def test_entrada_soma_o_status_por_classe(prometheus):
    base, falso = prometheus
    falso.REGRAS += [("count by (job) (traefik_service_requests_total)", _vetor([({"job": "proxy"}, 1)])),
                     ("sum(increase(traefik_service_requests_total", _vetor([({}, 1000)])),
                     ("sum by (code) (increase(traefik_service_requests_total",
                      _vetor([({"code": "200"}, 800), ({"code": "301"}, 100),
                              ({"code": "404"}, 60), ({"code": "403"}, 30), ({"code": "500"}, 10)])),
                     ("histogram_quantile", _vetor([({}, 184.0)]))]

    html = _bloco("entrada", "entrada", base, "proxy")

    assert "90,0% ok" in html and "9,0% 4xx" in html and "1,0% 5xx" in html
    assert "184 ms" in html and "1 mil de acessos" in html


def _filas_pela_api(monkeypatch, filas):
    respostas = {"/api/overview": json.dumps({"product_name": "Exemplo", "rabbitmq_version": "4.0"}),
                 "/api/queues": json.dumps(filas)}

    def falso(url, permitidos, credencial, alvo=None, timeout=None):
        return 200, respostas[next(c for c in respostas if url.split("?")[0].endswith(c))]

    monkeypatch.setattr(admin_http.http_get, "get_autenticado", falso)
    componente = {"nome": "mq", "papel": "fila", "admin_url": "http://exemplo.test:15672", "respostas": []}
    contexto = {"timeout": 20, "http_timeout": 8, "orcamento": 120, "alvo": "prod", "cache": {}}
    collect.responder(componente, contexto, [admin_http], Prazo(120))
    return render_bloco("fila", dados_do_papel("fila", [{"componentes": [componente]}]))


def test_api_sem_taxa_em_fila_nenhuma_nao_prova_que_a_fila_esta_ociosa(monkeypatch):
    """Estatística desligada e broker todo parado chegam iguais: sem `message_stats` em nada."""
    html = _filas_pela_api(monkeypatch, [{"name": "avisos", "vhost": "/", "messages_ready": 0,
                                          "messages_unacknowledged": 0, "consumers": 1}])

    assert "Ociosa" not in html and "Sem movimento" not in html
    assert "Ritmo não medido" in html


def test_fila_ociosa_ao_lado_de_outra_com_movimento(monkeypatch):
    estatisticas = {"publish_details": {"rate": 1.0}, "deliver_get_details": {"rate": 1.0}}
    html = _filas_pela_api(monkeypatch, [
        {"name": "avisos", "vhost": "/", "messages_ready": 0, "messages_unacknowledged": 0, "consumers": 1},
        {"name": "pedidos", "vhost": "/", "messages_ready": 2, "messages_unacknowledged": 0, "consumers": 1,
         "message_stats": estatisticas}])

    assert "1 fluindo · 1 ociosa" in html


def test_fila_travada_em_transito_nao_e_ociosa(monkeypatch):
    """Zero prontas e 80 mil sem confirmação: o catálogo chama este de "o caso pior"."""
    html = _filas_pela_api(monkeypatch, [{"name": "travada", "vhost": "/", "messages_ready": 0,
                                          "messages_unacknowledged": 80000, "consumers": 1}])

    assert ">Ociosa<" not in html and "bl-tag-warn" in html and "Em trânsito" in html


def test_fila_sem_taxa_medida_pela_fonte_nao_se_diz_ociosa():
    """O exporter não responde `fila.taxa_entrada_saida`: ritmo desconhecido não é ritmo zero."""
    alvo = {"componentes": [{"nome": "mq", "papel": "fila", "respostas": [
        {"pergunta": "fila.filas", "fonte": "promql:rabbitmq-prometheus",
         "valor": [{"nome": "e", "prontas": 0, "nao_confirmadas": 0, "consumidores": 1}]},
        {"pergunta": "fila.taxa_entrada_saida", "sem_dados": True, "motivo": "não expõe"}]}]}

    html = render_bloco("fila", dados_do_papel("fila", [alvo]))

    assert "bl-tag-neutro" in html and ">Vazia<" in html and ">Ociosa<" not in html
