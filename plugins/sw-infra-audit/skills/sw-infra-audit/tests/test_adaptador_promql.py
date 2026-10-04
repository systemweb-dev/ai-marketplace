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


def _identifica_traefik(falso, seletor='job="proxy"', valores=("proxy",)):
    """Ensina o Prometheus falso a ser identificado como Traefik.

    São DUAS consultas desde que o adaptador parou de supor o valor da etiqueta: primeiro ele
    pergunta quais valores a etiqueta tem (`count by (job) (serie)`), depois confirma o
    componente com o valor que casou. Supor o valor fazia dois componentes diferentes
    receberem o mesmo número, carimbado como se fosse de cada um.
    """
    falso.REGRAS.append(('count by (job) (traefik_service_requests_total)',
                         _vetor([({"job": v}, 1) for v in valores])))
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


def test_familia_de_outro_papel_nunca_identifica_o_componente(prometheus):
    """O banco aponta para o MESMO Prometheus do proxy — a série de Traefik existe lá.

    Sem o filtro por papel, a família era candidata para qualquer componente e o banco
    recebia o número do proxy. Hoje a família só concorre se responde pergunta do papel
    daquele componente, e por isso nenhuma consulta de Traefik sequer sai.
    """
    base, falso = prometheus
    _identifica_traefik(falso)
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 7)])))

    componente = dict(_componente(base, "banco"), papel="banco")
    resposta = promql.perguntar("entrada.volume_na_janela", componente, dict(CONTEXTO))

    assert resposta["sem_dados"] is True, "o banco não pode ser identificado como o proxy"
    assert not any("traefik" in q for q in falso.RECEBIDAS), falso.RECEBIDAS


def test_nome_que_nao_casa_com_nenhum_valor_da_etiqueta_nao_recebe_a_medida(prometheus):
    """A etiqueta tem dois valores e nenhum é deste componente.

    O número sem filtro aqui é a SOMA dos dois — entregá-lo como se fosse de um é a mentira
    que fazia dois componentes exibirem a mesma medida. Melhor não medir.
    """
    base, falso = prometheus
    _identifica_traefik(falso, valores=("proxy", "borda"))
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 500)])))

    resposta = promql.perguntar("entrada.volume_na_janela", _componente(base, "cdn"),
                                dict(CONTEXTO))

    assert resposta["sem_dados"] is True
    assert "soma de todos" in resposta["motivo"]


def test_etiqueta_com_um_valor_so_responde_pelo_exporter_inteiro_e_a_fonte_diz(prometheus):
    """Um proxy só no cluster, e a etiqueta não vale o nome do serviço: o número sem filtro
    é a resposta certa — mentir que ele é do componente é que não pode."""
    base, falso = prometheus
    _identifica_traefik(falso, valores=("borda",))
    falso.REGRAS.append((VOLUME_TRAEFIK, _vetor([({}, 500)])))

    resposta = promql.perguntar("entrada.volume_na_janela",
                                _componente(base, "pilha_entrada"), dict(CONTEXTO))

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


def test_pergunta_que_nenhuma_familia_responde_nao_manda_declarar_metricas_url():
    """Pergunta sem família recebia o motivo "o componente não declara `metricas_url`" — e o
    dono ia declarar algo que não faz a pergunta responder. O motivo tem que ser o verdadeiro:
    ninguém aqui responde isto."""
    from lib.adaptadores import promql
    from lib.perguntas import PERGUNTAS

    id_ = pergunta_sem_familia()
    resposta = promql.perguntar(id_, {"nome": "x", "papel": PERGUNTAS[id_]["papel"]},
                                {"timeout": 5})

    assert resposta["sem_dados"] is True
    assert "metricas_url" not in resposta["motivo"]
    assert "exporter" in resposta["motivo"]


def test_pergunta_que_alguma_familia_responde_continua_pedindo_metricas_url():
    """Regressão: para `entrada`, declarar `metricas_url` É o conserto."""
    from lib.adaptadores import promql

    resposta = promql.perguntar("entrada.latencia", {"nome": "proxy", "papel": "entrada"},
                                {"timeout": 5})

    assert "metricas_url" in resposta["motivo"]


def pergunta_sem_familia():
    """Uma pergunta canônica que NENHUMA família do catálogo responde.

    Derivada do catálogo real, não digitada: o teste anterior fixava `fila.filas`, e no dia em
    que uma família passou a responder aquilo o teste caiu sem que a garantia tivesse mudado.
    O que se protege é o MOTIVO — "ninguém responde isto" nunca pode virar "declare
    `metricas_url`", que manda o dono configurar algo que não faz a pergunta responder.
    """
    from lib import catalogo
    from lib.perguntas import PERGUNTAS

    respondidas = {p["id"] for familia in catalogo.familias()
                   for p in familia.get("pergunta", [])}
    sobrando = sorted(set(PERGUNTAS) - respondidas)
    assert sobrando, ("toda pergunta canônica tem família promql — o motivo "
                      "`nao_se_aplica` ficou inalcançável e esta trava não protege mais nada")
    return sobrando[0]
