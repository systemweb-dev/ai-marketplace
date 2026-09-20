# tests/test_adaptador_promql.py
import http.server
import json
import threading
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from lib.adaptadores import promql

CONTEXTO = {"at": "2026-09-19T10:00:00Z", "janela": "24h", "timeout": 2}
VOLUME_TRAEFIK = "sum(increase(traefik_service_requests_total"


def _vetor(pares):
    return {"status": "success",
            "data": {"resultType": "vector",
                     "result": [{"metric": m, "value": [0, str(v)]} for m, v in pares]}}


VAZIO = _vetor([])


class _Prometheus(http.server.BaseHTTPRequestHandler):
    """Prometheus de mentira que responde pela CONSULTA recebida, não por assunto.

    Responder igual a tudo faria o teste passar mesmo com a query errada — que é justamente
    o erro que um servidor falso mais esconde.
    """
    REGRAS = []          # [(trecho_que_a_consulta_precisa_conter, resposta)]
    RECEBIDAS = []
    MOMENTOS = []

    def do_GET(self):
        parametros = parse_qs(urlparse(self.path).query)
        consulta = parametros.get("query", [""])[0]
        self.RECEBIDAS.append(consulta)
        self.MOMENTOS.extend(parametros.get("time", []))
        resposta = next((r for trecho, r in self.REGRAS if trecho in consulta), VAZIO)
        corpo = json.dumps(resposta).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass


@pytest.fixture
def prometheus():
    servidor = http.server.HTTPServer(("127.0.0.1", 0), _Prometheus)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    _Prometheus.REGRAS.clear()
    _Prometheus.RECEBIDAS.clear()
    _Prometheus.MOMENTOS.clear()
    yield f"http://127.0.0.1:{servidor.server_port}", _Prometheus
    servidor.shutdown()


def _identifica_traefik(falso, seletor='job="proxy"'):
    falso.REGRAS.append((f'count(traefik_service_requests_total{{{seletor}}})', _vetor([({}, 1)])))


def _componente(base, nome="proxy"):
    return {"nome": nome, "papel": "entrada", "metricas_url": base}


def test_responde_a_pergunta_da_familia_identificada(prometheus):
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 12480)])))

    resposta = promql.perguntar("entrada.volume_na_janela", _componente(base), dict(CONTEXTO))

    assert resposta["valor"] == 12480
    assert resposta["fonte"] == "promql:traefik"


def test_identificacao_e_escopada_pelo_componente(prometheus):
    """`count(serie)` sem escopo pergunta 'este Prometheus tem ALGUMA série de Traefik?' —
    e aí todo componente apontando para o mesmo Prometheus viraria Traefik, banco inclusive."""
    base, falso = prometheus
    _identifica_traefik(falso, seletor='job="proxy"')
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 7)])))

    resposta = promql.perguntar("entrada.volume_na_janela", _componente(base, "banco"),
                                dict(CONTEXTO))

    assert resposta["sem_dados"] is True, "o banco não pode ser identificado como o proxy"
    assert any('count(traefik_service_requests_total{job="banco"})' in q
               for q in falso.RECEBIDAS), falso.RECEBIDAS


def test_sem_escopo_o_numero_e_do_exporter_inteiro_e_a_fonte_diz(prometheus):
    """Série existe, mas não com a etiqueta do componente: num cluster com um proxy só, o
    número sem filtro é a resposta certa — mentir que ele é do componente é que não pode."""
    base, falso = prometheus
    falso.REGRAS.append(("count(traefik_service_requests_total)", _vetor([({}, 1)])))
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 500)])))

    resposta = promql.perguntar("entrada.volume_na_janela", _componente(base), dict(CONTEXTO))

    assert resposta["valor"] == 500
    assert "exporter inteiro" in resposta["fonte"]


def test_a_consulta_e_avaliada_no_instante_do_at(prometheus):
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 1)])))

    promql.perguntar("entrada.volume_na_janela", _componente(base), dict(CONTEXTO))

    esperado = str(int(datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc).timestamp()))
    assert any("[24h]" in q for q in falso.RECEBIDAS), falso.RECEBIDAS
    assert falso.MOMENTOS and set(falso.MOMENTOS) == {esperado}


def test_lista_empatada_sai_em_ordem_estavel(prometheus):
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append(("sum by (code)", _vetor([({"code": "500"}, 7), ({"code": "200"}, 7),
                                                  ({"code": "404"}, 7)])))

    resposta = promql.perguntar("entrada.distribuicao_de_status", _componente(base),
                                dict(CONTEXTO))

    assert [item["chave"] for item in resposta["valor"]] == ["200", "404", "500"]


def test_lista_vem_do_maior_para_o_menor(prometheus):
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append(("sum by (code)", _vetor([({"code": "200"}, 3), ({"code": "404"}, 90)])))

    resposta = promql.perguntar("entrada.distribuicao_de_status", _componente(base),
                                dict(CONTEXTO))

    assert [item["valor"] for item in resposta["valor"]] == [90, 3]


def test_valor_nao_numerico_vira_sem_dados(prometheus):
    """`histogram_quantile` sem amostras devolve NaN — e NaN no report.json produz JSON
    inválido para qualquer leitor fora do Python."""
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append(("histogram_quantile", _vetor([({}, "NaN")])))

    resposta = promql.perguntar("entrada.latencia", _componente(base), dict(CONTEXTO))

    assert resposta["sem_dados"] is True
    assert "não é número" in resposta["motivo"]


def test_escalar_com_varias_series_nao_escolhe_uma(prometheus):
    """Seletor frouxo devolve várias séries; pegar uma seria inventar qual é o componente."""
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({"job": "a"}, 1), ({"job": "b"}, 2)])))

    resposta = promql.perguntar("entrada.volume_na_janela", _componente(base), dict(CONTEXTO))

    assert resposta["sem_dados"] is True and "séries" in resposta["motivo"]


def test_url_colada_com_caminho_de_consulta_ainda_funciona(prometheus):
    """O `configurar.py alvos --sugerir` imprime a URL completa de uma consulta; colar aquilo
    inteiro no alvos.toml é o caminho natural — e não pode virar 404 silencioso."""
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 42)])))

    resposta = promql.perguntar("entrada.volume_na_janela",
                                _componente(f"{base}/api/v1/query?query=up"), dict(CONTEXTO))

    assert resposta["valor"] == 42


def test_identificacao_nao_se_repete_a_cada_pergunta(prometheus):
    """Duas consultas de identificação por família, por pergunta, multiplicariam o tráfego
    numa auditoria com muitos componentes."""
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 1)])))
    contexto = dict(CONTEXTO)

    promql.perguntar("entrada.volume_na_janela", _componente(base), contexto)
    identificacoes = sum(1 for q in falso.RECEBIDAS if q.startswith("count("))
    promql.perguntar("entrada.volume_na_janela", _componente(base), contexto)

    assert sum(1 for q in falso.RECEBIDAS if q.startswith("count(")) == identificacoes


def test_sem_metricas_url_responde_sem_dados_com_motivo():
    resposta = promql.perguntar("entrada.volume_na_janela",
                                {"nome": "proxy", "papel": "entrada"}, dict(CONTEXTO))
    assert resposta["sem_dados"] is True and "metricas_url" in resposta["motivo"]


def test_fonte_que_responde_mas_nao_e_familia_conhecida_diz_isso(prometheus):
    base, falso = prometheus
    falso.REGRAS.append(("vector(1)", _vetor([({}, 1)])))

    resposta = promql.perguntar("entrada.volume_na_janela", _componente(base), dict(CONTEXTO))

    assert resposta["sem_dados"] is True
    assert "não reconheci a família" in resposta["motivo"], resposta["motivo"]


def test_fonte_que_nao_responde_vira_sem_dados():
    resposta = promql.perguntar("entrada.volume_na_janela",
                                _componente("http://127.0.0.1:1"), dict(CONTEXTO))
    assert resposta["sem_dados"] is True and "não respondeu" in resposta["motivo"]


def test_pergunta_que_a_familia_nao_expoe_diz_isso(prometheus):
    """Não se inventa dado a partir de outra métrica, nem se cai em outra família calado."""
    from lib import perguntas
    base, falso = prometheus
    _identifica_traefik(falso)
    perguntas._p("entrada.inventada", "entrada", "Inventada", "escalar")
    try:
        resposta = promql.perguntar("entrada.inventada", _componente(base), dict(CONTEXTO))
        assert resposta["sem_dados"] is True
        assert "não expõe" in resposta["motivo"]
    finally:
        perguntas.PERGUNTAS.pop("entrada.inventada")
        perguntas.ORDEM["entrada"].remove("entrada.inventada")
