# tests/test_coletor_http.py
import http.server
import threading

import pytest

from lib.coletores import http as coletor


@pytest.fixture
def servidor():
    """Servidor local de verdade: testar HTTP com mock esconde justamente o que pode quebrar."""
    class Mão(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            corpo = b'{"status":"ok"}'
            self.send_response(200 if self.path == "/health" else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *args):
            pass

    s = http.server.HTTPServer(("127.0.0.1", 0), Mão)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()
    s.server_close()


def test_endpoint_saudavel_vira_alvo_verde(servidor):
    bloco = coletor.coletar({"nome": "site", "tipo": "http", "url": f"{servidor}/health"},
                            {"http_timeout": 5})

    assert bloco["saude"] == "🟢"
    assert bloco["fatos"]["codigo"] == 200
    assert bloco["fatos"]["tempo_faixa"] in ("<1s", "1-10s")
    assert bloco["achados"] == []


def test_codigo_de_erro_vira_achado_alto(servidor):
    bloco = coletor.coletar({"nome": "site", "tipo": "http", "url": f"{servidor}/quebrado"},
                            {"http_timeout": 5})

    assert bloco["saude"] == "🔴"
    assert [a["regra"] for a in bloco["achados"]] == ["http_fora_do_ar"]
    assert bloco["achados"][0]["severidade"] == "critical"


def test_host_que_nao_responde_vira_sem_dados_e_nao_achado():
    bloco = coletor.coletar({"nome": "site", "tipo": "http", "url": "http://127.0.0.1:1/x"},
                            {"http_timeout": 1})

    assert bloco["saude"] == "sem dados"
    assert bloco["achados"] == [], "não consegui alcançar ≠ está fora do ar"
    assert bloco["nao_coletado"]


def test_tempo_vai_em_faixa_para_o_relatorio_ser_deterministico(servidor):
    um = coletor.coletar({"nome": "s", "tipo": "http", "url": f"{servidor}/health"}, {"http_timeout": 5})
    dois = coletor.coletar({"nome": "s", "tipo": "http", "url": f"{servidor}/health"}, {"http_timeout": 5})

    assert um["fatos"]["tempo_faixa"] == dois["fatos"]["tempo_faixa"]
    assert "tempo_ms" not in um["fatos"], "milissegundo exato mudaria o relatório a cada rodada"


def test_certificado_vencendo_vira_achado(monkeypatch):
    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (200, ""))
    monkeypatch.setattr(coletor.http_get, "validade_do_certificado",
                        lambda url, allowed, timeout: {"dias": 9, "expira_em": "2026-09-28"})

    bloco = coletor.coletar({"nome": "site", "tipo": "http", "url": "https://exemplo.invalido/"},
                            {"http_timeout": 1})

    regras = [a["regra"] for a in bloco["achados"]]
    assert "certificado_vencendo" in regras


def test_http_simples_nao_gera_achado_de_certificado(servidor):
    bloco = coletor.coletar({"nome": "s", "tipo": "http", "url": f"{servidor}/health"},
                            {"http_timeout": 5})

    assert all(a["regra"] != "certificado_vencendo" for a in bloco["achados"])
    assert bloco["fatos"]["certificado"]["motivo"].startswith("http sem TLS")


def test_endpoint_local_em_http_nao_vira_achado_de_tls(servidor):
    """127.0.0.1 sem TLS é normal; cobrar certificado aí faria a regra virar ruído."""
    bloco = coletor.coletar({"nome": "s", "tipo": "http", "url": f"{servidor}/health"},
                            {"http_timeout": 5})

    assert [a["regra"] for a in bloco["achados"]] == []
    assert coletor.interno("127.0.0.1") and coletor.interno("10.0.0.5") and coletor.interno("localhost")


def test_endpoint_publico_em_http_vira_achado_de_tls(monkeypatch):
    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (200, ""))

    bloco = coletor.coletar({"nome": "s", "tipo": "http", "url": "http://exemplo.invalido/health"},
                            {"http_timeout": 1})

    assert [a["regra"] for a in bloco["achados"]] == ["sem_tls"]
    assert coletor.interno("exemplo.invalido") is False


def test_certificado_vencido_e_lido_mesmo_com_o_get_falhando(monkeypatch):
    """Certificado vencido derruba o GET — e era justamente o achado mais importante que sumia."""
    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (None, None))
    monkeypatch.setattr(coletor.http_get, "validade_do_certificado",
                        lambda url, allowed, timeout: {"dias": -3, "expira_em": "2026-09-16"})

    bloco = coletor.coletar({"nome": "s", "tipo": "http", "url": "https://exemplo.invalido/"},
                            {"http_timeout": 1})

    vencido = next(a for a in bloco["achados"] if a["regra"] == "certificado_vencendo")
    assert vencido["severidade"] == "critical"
    assert bloco["saude"] == "🔴"


def test_erro_do_servidor_e_fora_do_ar_mas_404_nao(monkeypatch):
    """5xx é o serviço quebrado; 404 é o servidor de pé respondendo que a rota não existe."""
    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (503, ""))
    quebrado = coletor.coletar({"nome": "s", "tipo": "http", "url": "http://127.0.0.1:1/x"},
                               {"http_timeout": 1})

    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (404, ""))
    ausente = coletor.coletar({"nome": "s", "tipo": "http", "url": "http://127.0.0.1:1/x"},
                              {"http_timeout": 1})

    assert [a["regra"] for a in quebrado["achados"]] == ["http_fora_do_ar"]
    assert quebrado["achados"][0]["severidade"] == "critical"
    assert [a["regra"] for a in ausente["achados"]] == ["http_resposta_de_erro"]
    assert ausente["achados"][0]["severidade"] == "medium"


def test_nome_de_servico_interno_nao_e_tratado_como_publico():
    """`traefik` é nome de serviço na rede do cluster, não um host público sem TLS."""
    assert coletor.interno("traefik") is True
    assert coletor.interno("api.exemplo.invalido") is False
