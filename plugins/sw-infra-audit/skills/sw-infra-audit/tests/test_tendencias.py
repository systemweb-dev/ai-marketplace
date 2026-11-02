"""Tendências da capa: `query_range` só na fonte declarada, sem NaN e sem derrubar a coleta."""
import json
import math
from urllib.parse import parse_qs, urlparse

import pytest

import build_report as br
import collect
from lib import catalogo, report, tendencias
from lib.adaptadores import promql
from lib.capa import METRICAS, linha_tendencia
from lib.orcamento import Prazo

AT = "2026-11-01T10:00:00Z"
FONTE = "http://metricas.interno:9090"
ALVO = {"nome": "c", "tipo": "docker", "context": "x", "metricas_url": FONTE}
CTX = {"timeout": 7, "http_timeout": 2, "orcamento": 120, "janela": "24h", "at": AT}


def _matriz(valores):
    return {"status": "success", "data": {"result": [{"metric": {}, "values": list(enumerate(valores))}]}}


def _coletor(alvo, contexto):
    return {"saude": "🟢", "fatos": {}, "componentes": []}


def test_serie_exige_momento_valido():
    assert promql.serie("http://p", "up", None, 1) is None


def test_serie_devolve_os_valores_e_ignora_nan(monkeypatch):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: {"status": "success", "data": {
        "result": [{"values": [[1, "2"], [2, "NaN"], [3, "3.5"]]}]}})
    assert promql.serie("http://p", "up", 3, 1) == [2.0, 3.5]


def test_falha_da_consulta_devolve_none(monkeypatch):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: None)
    assert promql.serie("http://p", "up", 3, 1) is None


def test_alvo_sem_fonte_nao_tem_tendencia():
    assert tendencias.coletar_tendencias({}, AT, 1) == {}


def test_svg_so_com_dois_pontos():
    assert linha_tendencia([1.0]) == "" and "polyline" in linha_tendencia([1.0, 2.0])


def test_serie_pede_24_horas_com_passo_de_1_hora(monkeypatch):
    urls = []
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: urls.append(url))
    promql.serie(FONTE, 'up{a="b"}', 90000, 1)
    url = urlparse(urls[0])
    assert (url.netloc, url.path) == ("metricas.interno:9090", "/api/v1/query_range")
    assert parse_qs(url.query) == {"query": ['up{a="b"}'], "start": ["3600"], "end": ["90000"],
                                   "step": ["3600"]}


def test_instante_zero_e_valido(monkeypatch):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: _matriz(["1"]))
    assert promql.serie(FONTE, "up", 0, 1) == [1.0]


def test_infinito_some_e_o_resultado_e_json_valido(monkeypatch):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: _matriz(["+Inf", "1.5", "-Inf", "NaN", "x"]))
    valores = promql.serie(FONTE, "up", 3, 1)
    assert valores == [1.5] and all(math.isfinite(v) for v in valores)
    json.dumps(valores, allow_nan=False)


@pytest.mark.parametrize("corpo", [
    _matriz(["NaN", "+Inf"]),
    {"status": "error"},
    {"status": "success"},
    {"status": "success", "data": []},
    {"status": "success", "data": {"result": []}},
    {"status": "success", "data": {"result": [{"metric": {}}]}},
    {"status": "success", "data": {"result": [{"values": [[1]]}]}},
    {"status": "success", "data": {"result": [{"values": [[1, "1"]]}, {"values": [[1, "2"]]}]}},
])
def test_resposta_sem_serie_utilizavel_devolve_none(monkeypatch, corpo):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: corpo)
    assert promql.serie(FONTE, "up", 3, 1) is None


@pytest.mark.parametrize("resposta", [(None, None), (500, ""), (200, ""), (200, "{"), (200, "[1]")])
def test_baixar_devolve_none_quando_nao_le(monkeypatch, resposta):
    monkeypatch.setattr(promql.http_get, "get_com_status", lambda *a, **k: resposta)
    assert promql._baixar(f"{FONTE}/api/v1/query_range?query=up", 1) is None


def test_consultas_cobrem_a_capa_com_series_reais():
    consultas = tendencias.consultas()
    assert sorted(consultas) == sorted(nome for nome, _ in METRICAS)
    assert "traefik_service_" in consultas["erros"] and "traefik_service_" in consultas["resposta"]
    assert 'avail_bytes{mountpoint="/"}' in consultas["disco"]
    assert 'size_bytes{mountpoint="/"}' in consultas["disco"]
    assert "or vector(0)" in consultas["erros"]


def test_tendencia_mal_declarada_e_recusada(tmp_path):
    base = next(catalogo.PASTA.glob("node-exporter.toml")).read_text(encoding="utf-8")
    arquivo = tmp_path / "x.toml"
    arquivo.write_text(base + '\n[[tendencia]]\nnome = "x"\n', encoding="utf-8")
    with pytest.raises(catalogo.CatalogoInvalido, match="nome"):
        catalogo.carregar_arquivo(arquivo)
    arquivo.write_text(base + '\n[[tendencia]]\nnome = "x"\nquery = "up{%SELETOR%}"\n', encoding="utf-8")
    with pytest.raises(catalogo.CatalogoInvalido, match="interpolação"):
        catalogo.carregar_arquivo(arquivo)


def test_uma_serie_que_falha_nao_leva_as_outras(monkeypatch):
    monkeypatch.setattr(promql, "_baixar",
                        lambda url, timeout: None if "node_cpu" in parse_qs(urlparse(url).query)["query"][0]
                        else _matriz(["1", "2"]))
    saida = tendencias.coletar_tendencias(ALVO, AT, 1)
    assert sorted(n for n, v in saida.items() if v) == ["disco", "erros", "memoria", "resposta"]


def test_prazo_limita_o_timeout_e_interrompe(monkeypatch):
    relogio = [0.0]
    pedidos = []

    def baixar(url, timeout):
        pedidos.append(timeout)
        relogio[0] += 4
        return _matriz(["1", "2"])

    monkeypatch.setattr(promql, "_baixar", baixar)
    saida = tendencias.coletar_tendencias(ALVO, AT, 20, Prazo(10, agora=lambda: relogio[0]))
    assert pedidos == [10, 6, 2] and sum(1 for v in saida.values() if v) == 3


def test_prazo_esgotado_nao_consulta(monkeypatch):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: pytest.fail("consultou sem prazo"))
    assert not any(tendencias.coletar_tendencias(ALVO, AT, 20, Prazo(0)).values())


def _prometheus(monkeypatch, viva=True):
    chamadas = []

    def falso(url, permitidos, timeout=None):
        chamadas.append((url, permitidos))
        if not viva:
            return None, None
        if "/query_range" in url:
            return 200, json.dumps(_matriz(["NaN", "10", "20.5"]))
        return 200, json.dumps({"status": "success", "data": {"result": (
            [{"metric": {}, "value": [0, "1"]}] if "vector(1)" in url else [])}})

    monkeypatch.setattr(promql.http_get, "get_com_status", falso)
    return chamadas


def test_coleta_so_fala_com_a_fonte_declarada_e_a_tendencia_chega_a_capa(monkeypatch):
    chamadas = _prometheus(monkeypatch)
    registro = collect.coletar_alvo(dict(ALVO), _coletor, dict(CTX), [promql])

    assert registro["tendencias"]["disco"] == [10.0, 20.5] and len(registro["tendencias"]) == 5
    caminhos = set()
    for url, permitidos in chamadas:
        partes = urlparse(url)
        caminhos.add(partes.path)
        assert partes.netloc == "metricas.interno:9090" and permitidos == [("metricas.interno", 9090)]
    assert caminhos == {"/api/v1/query", "/api/v1/query_range"}

    relatorio = report.ordenar(dict(report.novo(AT), alvos=[dict(registro, coletado=True)]))
    relatorio = json.loads(json.dumps(relatorio, allow_nan=False))
    assert relatorio["alvos"][0]["tendencias"] == registro["tendencias"]
    assert "bl-spark" in br.render_html_v3(relatorio)


def test_fonte_morta_nao_gasta_timeout_em_tendencia(monkeypatch):
    chamadas = _prometheus(monkeypatch, viva=False)
    registro = collect.coletar_alvo(dict(ALVO), _coletor, dict(CTX), [promql])
    assert registro["tendencias"] == {nome: None for nome, _ in METRICAS}
    assert not [url for url, _ in chamadas if "/query_range" in url]


def test_adaptador_sem_passe_nao_abre_rede(monkeypatch):
    chamadas = _prometheus(monkeypatch)
    registro = collect.coletar_alvo(dict(ALVO), _coletor, dict(CTX), [])
    assert not any(registro["tendencias"].values()) and not chamadas


def test_at_invalido_nao_derruba_a_coleta(monkeypatch):
    chamadas = _prometheus(monkeypatch)
    registro = collect.coletar_alvo(dict(ALVO), _coletor, dict(CTX, at="2026-11-01 lixo"), [promql])
    assert not any(registro["tendencias"].values())
    assert not [url for url, _ in chamadas if "/query_range" in url]


def test_excecao_nas_tendencias_vira_nao_coletado(monkeypatch):
    _prometheus(monkeypatch)

    def quebra(*a, **k):
        raise promql.http_get.NotConfirmed("destino não confirmado")

    monkeypatch.setattr(promql, "serie", quebra)
    registro = collect.coletar_alvo(dict(ALVO), _coletor, dict(CTX), [promql])
    assert registro["tendencias"] == {nome: None for nome, _ in METRICAS}
    assert any("tendências" in n["motivo"] for n in registro["nao_coletado"])
    assert registro["saude"] == "🟢"


def test_serie_que_falha_e_dita_em_nao_coletado(monkeypatch):
    monkeypatch.setattr(promql, "_baixar",
                        lambda url, timeout: None if "node_cpu" in parse_qs(urlparse(url).query)["query"][0]
                        else _matriz(["1", "2"]))
    faltas = []
    saida = tendencias.coletar_tendencias(ALVO, AT, 1, nao_coletado=faltas)
    assert saida["cpu"] is None and saida["disco"] == [1.0, 2.0]
    assert [f["valor"] for f in faltas] == [None]
    assert "tendência cpu" in faltas[0]["motivo"]


def test_prazo_esgotado_diz_cada_serie_que_ficou_de_fora(monkeypatch):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: pytest.fail("consultou sem prazo"))
    faltas = []
    saida = tendencias.coletar_tendencias(ALVO, AT, 20, Prazo(0), nao_coletado=faltas)
    assert saida == {nome: None for nome, _ in METRICAS}
    assert len(faltas) == len(METRICAS)
    assert all(Prazo.motivo() in f["motivo"] for f in faltas)


def test_a_coleta_grava_a_falha_de_serie_no_alvo(monkeypatch):
    chamadas = _prometheus(monkeypatch)
    original = promql.serie
    monkeypatch.setattr(promql, "serie", lambda base, query, *a, **k: None if "node_cpu" in query
                        else original(base, query, *a, **k))
    registro = collect.coletar_alvo(dict(ALVO), _coletor, dict(CTX), [promql])
    assert chamadas
    assert registro["tendencias"]["cpu"] is None
    assert any("tendência cpu" in n["motivo"] for n in registro["nao_coletado"])


def test_fonte_que_nao_foi_sondada_e_dita_sem_abrir_rede(monkeypatch):
    chamadas = _prometheus(monkeypatch)
    registro = collect.coletar_alvo(dict(ALVO), _coletor, dict(CTX), [])
    assert not chamadas and set(registro["tendencias"]) == {n for n, _ in METRICAS}
    assert any("tendências" in n["motivo"] for n in registro["nao_coletado"])


def test_capa_usa_o_alvo_com_serie_mesmo_atras_de_um_sem_medida():
    medido = dict(report.novo_alvo("b", "docker", "x"), coletado=True, tendencias={"disco": [1.0, 2.0]})
    sem_medida = dict(report.novo_alvo("a", "docker", "x"), coletado=True, tendencias={"disco": None})
    relatorio = report.ordenar(dict(report.novo(AT), alvos=[sem_medida, medido]))
    assert '<svg class="bl-spark"' in br.render_html_v3(relatorio)
