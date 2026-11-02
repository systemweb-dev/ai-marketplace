"""URLs mais acessadas: do Loki ao bloco do relatório, sem nada bruto no caminho.

O Loki é sempre falso: nenhum teste aqui abre socket. Os hosts são `.exemplo.test`.
"""
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

import build_report as br
import collect
from lib import agregacao_urls as au
from lib import alvos as alvos_mod
from lib import catalogo_logs, cobertura, http_get, orcamento_paginas as op
from lib.adaptadores import REGISTRO, logql, todos
from lib.blocos import render_bloco
from lib.dados_blocos import dados_do_papel
from lib.orcamento import Prazo
from lib.perguntas import PERGUNTAS

AT = "2026-11-01T10:00:00Z"
FIM = 1793527200
LOKI = "http://logs.interno:3100"
ID = "entrada.urls_mais_acessadas"
RAIZ = Path(__file__).resolve().parents[1]
SEGREDO = "Cookie: sessao=abc123; Authorization: Bearer xyz789"
AMOSTRA_JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + "abcdefghijklmnop"


def linha(host="loja.exemplo.test", caminho="/produtos", status=200, ns=1_000_000):
    return f"{host}\t{caminho}\t{status}\t{ns}"


def corpo(linhas):
    """Cada linha num stream próprio, como o `json` do LogQL devolve: os rótulos extraídos
    separam os streams, e o rótulo traz o valor cru — que nunca pode ser lido."""
    return json.dumps({"status": "success", "data": {"resultType": "streams", "result": [
        {"stream": {"p": f"/segredo?token={AMOSTRA_JWT}", "cookie": SEGREDO},
         "values": [[str(FIM * 10 ** 9), texto]]} for texto in linhas]}})


class Loki:
    def __init__(self, resposta=None):
        self.resposta = resposta or (lambda i: (200, corpo([linha()])))
        self.chamadas = []

    def __call__(self, url, permitidos, timeout=None, maximo=None):
        self.chamadas.append({"url": url, "permitidos": permitidos, "timeout": timeout})
        return self.resposta(len(self.chamadas) - 1)


@pytest.fixture
def loki(monkeypatch):
    falso = Loki()
    monkeypatch.setattr(http_get, "get_com_status", falso)
    return falso


def contexto(**extra):
    return dict({"timeout": 20, "http_timeout": 8, "at": AT, "logs_url": LOKI, "cache": {}}, **extra)


def perguntar(**extra):
    return logql.perguntar(ID, {"nome": "proxy", "papel": "entrada"}, contexto(**extra))


# ---------------------------------------------------------------- normalização
@pytest.mark.parametrize("cru, esperado", [
    ("/produtos?cupom=abc#topo", "/produtos"),
    ("/produtos%3Ftoken=abc", "/produtos"),
    ("/pedidos/123/itens/456", "/pedidos/:id/itens/:id"),
    ("/u/550e8400-e29b-41d4-a716-446655440000/foto", "/u/:id/foto"),
    ("/git/ABCDEF0123456789", "/git/:id"),
    (f"/reset/{AMOSTRA_JWT}", "/reset/:token"),
    (f"/reset/{'a1B2-_' * 4}", "/reset/:token"),
    ("/x/abcdefghij0123456789abc", "/x/:token"),                       # curto, mas sem cara de rota
    ("/a//b/", "/a/b"),
    ("/", "/"),
    ("/app;jsessionid=abc", "/app"),
    ("/descadastro/fulano@exemplo.test", "/descadastro/:token"),
])
def test_normaliza_o_caminho(cru, esperado):
    assert au.normalizar_caminho(cru) == esperado


def test_caminho_tem_no_maximo_200_caracteres():
    assert len(au.normalizar_caminho("/abcdefghij" * 40)) == 200


def test_caminho_passa_por_scrub_text():
    assert "abc" not in au.normalizar_caminho("/x/API_KEY=abc")


@pytest.mark.parametrize("cru", ["", "*", "http://u:s@h/x", "sem-barra"])
def test_o_que_nao_e_caminho_fica_de_fora(cru):
    assert au.normalizar_caminho(cru) is None


@pytest.mark.parametrize("texto", [
    "so\tduas", "a\tb\tc\td\te", '{"RequestPath":"/x?token=abc","Cookie":"s=1"}',
    linha(host="<script>"), linha(status="ok"), linha(ns="muito"), linha(ns="-1"), linha(ns="nan"),
    linha(caminho="*"), "\t/x\t200\t1",
])
def test_linha_fora_do_formato_e_descartada(texto):
    assert au.ler_linha(texto) is None


def test_host_perde_a_porta_e_a_caixa():
    assert au.ler_linha(linha(host="Loja.Exemplo.TEST:8443"))[0] == "loja.exemplo.test"


# ---------------------------------------------------------------- métricas
def test_agrega_por_host_e_caminho():
    linhas = [linha(caminho=f"/p/{i}", status=500 if i < 5 else 200, ns=i * 1_000_000) for i in range(1, 101)]
    linhas += [linha(host="blog.exemplo.test", caminho="/p/1")]
    resultado = au.agregar(linhas)
    assert resultado["itens"][0] == {
        "nome": "loja.exemplo.test/p/:id", "site": "loja.exemplo.test", "caminho": "/p/:id",
        "acessos": 100, "erros": 4, "pct_5xx": 4.0, "p95_ms": 95.0}
    assert resultado["sites"] == [{"site": "loja.exemplo.test", "acessos": 100},
                                  {"site": "blog.exemplo.test", "acessos": 1}]


def test_p95_e_por_posto_mais_proximo():
    assert au.percentil_95([1, 2, 3, 4]) == 4
    assert au.percentil_95(list(range(1, 21))) == 19


def test_empate_resolve_pelo_nome_e_a_ordem_de_entrada_nao_importa():
    linhas = [linha(caminho=c) for c in ("/b", "/a", "/c")]
    primeiro = au.agregar(linhas)
    assert [i["caminho"] for i in primeiro["itens"]] == ["/a", "/b", "/c"]
    assert primeiro == au.agregar(linhas[::-1])


def test_grava_no_maximo_50_por_site():
    linhas = [linha(caminho=f"/r{letra}{outra}") for letra in "abcdefgh" for outra in "abcdefgh"]
    linhas += [linha(host="blog.exemplo.test", caminho="/um")]
    itens = au.agregar(linhas)["itens"]
    assert sum(i["site"] == "loja.exemplo.test" for i in itens) == 50
    assert sum(i["site"] == "blog.exemplo.test" for i in itens) == 1


# ---------------------------------------------------------------- catálogo
def test_catalogo_e_a_consulta_medida():
    familia = catalogo_logs.familias()[0]
    assert logql.consulta_de(familia) == (
        '{job="traefik"} |= "RequestPath" | json h="RequestHost", p="RequestPath", '
        's="DownstreamStatus", d="Duration" | __error__="" | '
        'line_format "{{.h}}\\t{{.p}}\\t{{.s}}\\t{{.d}}"')


@pytest.mark.parametrize("troca", [
    {"consulta": '%SELETOR% | json'},
    {"consulta": 'sum by (p) (count_over_time(%SELETOR%[1h]))'},
    {"consulta": '%SELETOR% | json h="RequestHost", p="request_Cookie", s="S", d="D" | __error__="" | '
                 'line_format "{{.h}}\\t{{.p}}\\t{{.s}}\\t{{.d}}"'},
    {"seletor": '{job=~".+"}'},
    {"caminho": "/loki/api/v1/delete"},
    {"rota": "/loki/api/v1/delete"},
    {"rota": "/loki/api/v1/tail"},
    {"pergunta": "entrada.inventada"},
])
def test_catalogo_recusa_o_que_foge_da_consulta_fixa(tmp_path, troca):
    base = tomllib.loads((RAIZ / "references/logs/traefik.toml").read_text(encoding="utf-8"))
    base.update(troca)
    arquivo = tmp_path / "x.toml"
    arquivo.write_text("\n".join(f"{k} = {json.dumps(v)}" for k, v in base.items()), encoding="utf-8")
    with pytest.raises(catalogo_logs.CatalogoInvalido):
        catalogo_logs.carregar_arquivo(arquivo)


# ---------------------------------------------------------------- campo do alvo
def _alvos(tmp_path, texto):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(0o600)
    return alvos_mod.ler(caminho)


def test_logs_url_e_opcional_do_alvo_docker(tmp_path):
    lidos, _ = _alvos(tmp_path, f'[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "c"\nlogs_url = "{LOKI}"\n')
    assert lidos[0]["logs_url"] == LOKI


def test_logs_url_nao_existe_em_alvo_http(tmp_path):
    with pytest.raises(alvos_mod.AlvoInvalido):
        _alvos(tmp_path, f'[[alvo]]\nnome = "s"\ntipo = "http"\nurl = "http://s"\nlogs_url = "{LOKI}"\n')


def test_logs_url_com_credencial_e_recusada_sem_repetir_a_senha(tmp_path):
    with pytest.raises(alvos_mod.AlvoInvalido) as erro:
        _alvos(tmp_path, '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "c"\n'
                         'logs_url = "http://u:senhaX@logs.interno:3100"\n')
    assert "senhaX" not in str(erro.value)


# ---------------------------------------------------------------- coleta
def test_cobre_24_janelas_de_1_hora_ancoradas_no_at(loki):
    resposta = perguntar()
    assert len(loki.chamadas) == 24
    for i, chamada in enumerate(loki.chamadas):
        url = urlparse(chamada["url"])
        q = parse_qs(url.query)
        assert (url.scheme, url.netloc, url.path) == ("http", "logs.interno:3100", "/loki/api/v1/query_range")
        assert set(q) == {"query", "start", "end", "limit", "direction"}
        assert q["limit"] == ["5000"] and q["direction"] == ["backward"]
        assert int(q["end"][0]) == (FIM - i * 3600) * 10 ** 9
        assert int(q["start"][0]) == (FIM - (i + 1) * 3600) * 10 ** 9
        assert "line_format" in q["query"][0]
    assert resposta["fonte"] == "logql:traefik" and resposta["valor"][0]["acessos"] == 24
    assert resposta["janelas"]["amostra"] is False and len(resposta["janelas"]["cobertas"]) == 24


def test_egress_so_para_a_logs_url(loki):
    perguntar()
    assert all(c["permitidos"] == [("logs.interno", 3100)] for c in loki.chamadas)


@pytest.mark.parametrize("colado", [f"{LOKI}/", f"{LOKI}/loki/api/v1/query_range?query=x"])
def test_url_colada_inteira_cai_na_raiz(loki, colado):
    perguntar(logs_url=colado)
    assert urlparse(loki.chamadas[0]["url"]).path == "/loki/api/v1/query_range"


def test_destino_fora_da_lista_e_recusado():
    with pytest.raises(http_get.NotConfirmed):
        http_get.get_com_status("http://logs.interno:9999/x", [("logs.interno", 3100)])


def test_janela_que_bateu_no_limite_conta_como_amostrada(loki):
    loki.resposta = lambda i: (200, corpo([linha()] * (5000 if i == 3 else 2)))
    janelas = perguntar()["janelas"]
    assert janelas["amostra"] is True and janelas["amostradas"] == 1
    assert [j["amostrada"] for j in janelas["cobertas"]].count(True) == 1


def test_janela_que_falhou_nao_conta_como_coberta(loki):
    loki.resposta = lambda i: (500, "") if i == 2 else (200, corpo([linha()]))
    resposta = perguntar()
    assert len(resposta["janelas"]["cobertas"]) == 23 and resposta["janelas"]["amostra"] is True
    assert resposta["janelas"]["falhas"] == ["o Loki respondeu 500"]


def test_prazo_para_a_coleta_e_guarda_o_que_leu(loki):
    instantes = iter([0] + [1] * 7 + [999] * 100)
    prazo = Prazo(10, agora=lambda: next(instantes))
    resposta = perguntar(prazo=prazo)
    assert 0 < len(loki.chamadas) < 24 and resposta["janelas"]["amostra"] is True
    assert resposta["janelas"]["falhas"] == [prazo.motivo()]


def test_prazo_esgotado_antes_da_primeira_janela_e_sem_dados(loki):
    resposta = perguntar(prazo=Prazo(0))
    assert resposta["sem_dados"] and "orçamento" in resposta["motivo"] and not loki.chamadas


def test_timeout_nunca_passa_do_que_o_alvo_tem(loki):
    perguntar(prazo=Prazo(3))
    assert all(c["timeout"] <= 3 for c in loki.chamadas)


@pytest.mark.parametrize("resposta, motivo", [
    ((None, None), "não respondeu"), ((401, ""), "401"), ((200, "não é json"), "formato"),
    ((200, '{"status":"error"}'), "formato"),
    ((200, '{"status":"success","data":{"resultType":"matrix","result":[]}}'), "formato"),
    ((200, '{"status":"success","data":{"resultType":"streams","result":[{"values":[[1]]}]}}'), "formato"),
])
def test_falha_vira_sem_dados_com_motivo(loki, resposta, motivo):
    loki.resposta = lambda i: resposta
    saida = perguntar()
    assert saida["sem_dados"] and motivo in saida["motivo"] and "nao_publica" not in saida


def test_fonte_morta_nao_gasta_as_24_janelas(loki):
    loki.resposta = lambda i: (None, None)
    perguntar()
    assert len(loki.chamadas) == 2


def test_resposta_grande_demais_e_dita(monkeypatch):
    def grande(*a, **k):
        raise http_get.RespostaGrandeDemais(1)
    monkeypatch.setattr(http_get, "get_com_status", grande)
    assert "grande demais" in perguntar()["motivo"]


def test_get_com_status_recusa_em_vez_de_cortar_quando_ha_maximo(monkeypatch):
    class Resposta:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b"x" * n
    monkeypatch.setattr(http_get._OPENER, "open", lambda req, timeout: Resposta())
    with pytest.raises(http_get.RespostaGrandeDemais):
        http_get.get_com_status("http://a.test/x", [("a.test", 80)], maximo=10)
    assert len(http_get.get_com_status("http://a.test/x", [("a.test", 80)])[1]) == http_get.MAX_BYTES


def test_sem_linhas_e_ausencia_que_nao_conta(loki):
    loki.resposta = lambda i: (200, corpo([]))
    saida = perguntar()
    assert saida["sem_dados"] and saida["nao_publica"]


def test_linha_bruta_nunca_e_aproveitada(loki):
    loki.resposta = lambda i: (200, corpo([json.dumps({"RequestPath": "/x", "Cookie": SEGREDO})]))
    saida = perguntar()
    assert saida["sem_dados"] and "formato" in saida["motivo"] and "Cookie" not in json.dumps(saida)


def test_outra_pergunta_nao_e_do_adaptador(loki):
    saida = logql.perguntar("entrada.latencia", {"nome": "p"}, contexto())
    assert saida.get("nao_se_aplica") and not loki.chamadas


def test_sem_logs_url_nao_ha_rede_e_o_motivo_ensina(loki):
    saida = logql.perguntar(ID, {"nome": "p"}, {"timeout": 1, "at": AT, "cache": {}})
    assert saida["sem_dados"] and saida["nao_publica"] and "logs_url" in saida["motivo"]
    assert not loki.chamadas


def test_dois_proxies_no_alvo_custam_uma_coleta(loki):
    ctx = contexto()
    logql.perguntar(ID, {"nome": "a"}, ctx)
    logql.perguntar(ID, {"nome": "b"}, ctx)
    assert len(loki.chamadas) == 24


def test_nada_bruto_na_resposta(loki):
    sujo = linha(caminho=f"/pedidos/42?token={AMOSTRA_JWT}&email=a@b.test")
    loki.resposta = lambda i: (200, corpo([sujo]))
    texto = json.dumps(perguntar())
    for proibido in (AMOSTRA_JWT, "email", "token=", "Cookie", "Authorization", "42"):
        assert proibido not in texto.replace(str(FIM), ""), proibido


def test_adaptador_vem_antes_do_promql_para_o_motivo_dele_valer():
    assert REGISTRO["logql"]["prioridade"] < REGISTRO["promql"]["prioridade"]
    assert logql in todos()


def test_motivo_do_log_vence_o_do_exporter(monkeypatch, loki):
    loki.resposta = lambda i: (401, "")
    alvo = {"nome": "c", "tipo": "docker", "context": "c", "logs_url": LOKI}
    registro = collect.coletar_alvo(alvo, _proxy, {"timeout": 1, "at": AT}, todos())
    resposta = next(r for r in registro["componentes"][0]["respostas"] if r["pergunta"] == ID)
    assert resposta["motivo"] == "o Loki respondeu 401"


# ---------------------------------------------------------------- orquestração
def _proxy(alvo, ctx):
    return {"saude": "🟢", "fatos": {}, "componentes": [{"nome": "proxy", "papel": "entrada"}]}


class Conta:
    ID = "conta"

    def __init__(self):
        self.ordem = []

    def perguntar(self, pergunta, componente, contexto):
        self.ordem.append(pergunta)
        return {"pergunta": pergunta, "sem_dados": True, "motivo": "x", "nao_se_aplica": True}


def test_pergunta_e_opcional_e_fica_para_o_fim_do_orcamento():
    assert PERGUNTAS[ID]["opcional"] and PERGUNTAS[ID]["por_ultimo"]
    conta = Conta()
    collect.coletar_alvo({"nome": "c", "tipo": "docker", "context": "c"}, _proxy,
                         {"timeout": 1, "at": AT}, [conta])
    assert conta.ordem[-1] == ID and conta.ordem.count(ID) == 1


def test_tendencias_vem_antes_das_janelas_de_log(monkeypatch, loki):
    ordem = []
    monkeypatch.setattr(collect, "tendencias_do_alvo", lambda *a: ordem.append("tendencias") or {})
    monkeypatch.setattr(logql, "_coletar", lambda *a: ordem.append("log") or logql._sem_dados("x"))
    alvo = {"nome": "c", "tipo": "docker", "context": "c", "logs_url": LOKI}
    collect.coletar_alvo(alvo, _proxy, {"timeout": 1, "at": AT}, [logql])
    assert ordem == ["tendencias", "log"]


def test_coleta_real_grava_a_resposta(loki):
    alvo = {"nome": "c", "tipo": "docker", "context": "c", "logs_url": LOKI}
    registro = collect.coletar_alvo(alvo, _proxy, {"timeout": 1, "at": AT}, [logql])
    assert next(r for r in registro["componentes"][0]["respostas"] if r["pergunta"] == ID)["valor"]


def test_sem_fonte_nao_derruba_a_cobertura():
    alvo = {"nome": "c", "tipo": "docker", "context": "c"}
    registro = collect.coletar_alvo(alvo, _proxy, {"timeout": 1, "at": AT}, [logql])
    medida = cobertura.medir(registro)
    assert ID not in {m["pergunta"] for m in medida["mudos"]}
    assert medida["perguntadas"] == 4


def test_prazo_esgotado_nao_vira_lacuna_de_quem_nao_tem_fonte():
    alvo = {"nome": "c", "tipo": "docker", "context": "c"}
    registro = collect.coletar_alvo(alvo, _proxy, {"timeout": 1, "at": AT, "orcamento": 0}, [logql])
    assert ID not in {m["pergunta"] for m in cobertura.medir(registro)["mudos"]}


def test_bug_na_coleta_nao_derruba_o_alvo(monkeypatch):
    monkeypatch.setattr(logql, "_coletar", lambda *a: 1 / 0)
    alvo = {"nome": "c", "tipo": "docker", "context": "c", "logs_url": LOKI}
    registro = collect.coletar_alvo(alvo, _proxy, {"timeout": 1, "at": AT}, [logql])
    assert registro["componentes"][0]["respostas"][-1]["erro_interno"]


def test_logs_url_sem_proxy_e_dita():
    alvo = {"nome": "c", "tipo": "docker", "context": "c", "logs_url": LOKI}
    registro = collect.coletar_alvo(alvo, lambda a, c: {"saude": "🟢", "fatos": {}, "componentes": []},
                                    {"timeout": 1, "at": AT}, [logql])
    assert any("logs_url" in n["motivo"] for n in registro["nao_coletado"])


def test_report_json_nao_leva_nada_bruto(loki, tmp_path):
    sujo = [linha(caminho=f"/a/{i}?token={AMOSTRA_JWT}") for i in range(3)]
    loki.resposta = lambda i: (200, corpo(sujo))
    alvo = {"nome": "c", "tipo": "docker", "context": "c", "logs_url": LOKI}
    registro = collect.coletar_alvo(alvo, _proxy, {"timeout": 1, "at": AT}, [logql])
    texto = json.dumps(registro, ensure_ascii=False, default=str)
    assert AMOSTRA_JWT not in texto and "tok" "en=" not in texto and "Cookie" not in texto
    assert "/a/:id" in texto


# ---------------------------------------------------------------- relatório
def item(site, caminho, acessos=10, erros=0, p95=5.0):
    return {"nome": f"{site}{caminho}", "site": site, "caminho": caminho, "acessos": acessos,
            "erros": erros, "pct_5xx": round(100 * erros / acessos, 2), "p95_ms": p95}


def resposta_medida(itens, amostra=False, **janelas):
    sites = {}
    for i in itens:
        sites[i["site"]] = sites.get(i["site"], 0) + i["acessos"]
    return {"pergunta": ID, "fonte": "logql:traefik", "valor": itens,
            "sites": [{"site": s, "acessos": n} for s, n in sorted(sites.items(), key=lambda p: (-p[1], p[0]))],
            "janelas": dict({"total": 24, "cobertas": [{}] * 24, "amostradas": 0, "falhas": [],
                             "amostra": amostra}, **janelas)}


def alvos_com(*respostas):
    return [{"nome": f"a{i}", "componentes": [{"nome": "proxy", "papel": "entrada", "respostas": [r]}]}
            for i, r in enumerate(respostas)]


def varios_sites():
    return [item(f"s{n}.exemplo.test", f"/rota{i}", acessos=100 - i - n, erros=(i == 1) * 3, p95=float(i + n))
            for n in range(7) for i in range(12)]


def test_top_15_geral_3_por_site_ate_5_sites():
    dados = dados_do_papel("urls", alvos_com(resposta_medida(varios_sites())))
    html = render_bloco("urls", dados)
    assert len(dados["geral"]) == 12 * 7
    assert html.count('class="bl-url"') == 5 and html.count('class="bl-url-l"') == 15
    assert html.count('<tr class="bl-url-g">') == 15


def test_erros_e_lentas_ate_5_cada_e_so_erro_que_existe():
    dados = dados_do_papel("urls", alvos_com(resposta_medida(varios_sites())))
    html = render_bloco("urls", dados)
    assert "URLs com mais erros" in html and "URLs mais lentas" in html
    assert html.count('class="bl-url-e"') == 5 and html.count('class="bl-url-s"') == 5
    assert all(i["erros"] for i in dados["erros"])
    assert [i["p95_ms"] for i in dados["lentas"]][:2] == [17.0, 16.0]


def test_ordem_das_listas_desempata_pelo_nome():
    dados = dados_do_papel("urls", alvos_com(resposta_medida(
        [item("b.test", "/x", erros=2, p95=7.0), item("a.test", "/x", erros=2, p95=7.0)])))
    assert [i["nome"] for i in dados["erros"]] == ["a.test/x", "b.test/x"]
    assert [i["nome"] for i in dados["lentas"]] == ["a.test/x", "b.test/x"]


def test_sem_erro_a_lista_diz_nenhum():
    html = render_bloco("urls", dados_do_papel("urls", alvos_com(resposta_medida([item("a.test", "/x")]))))
    assert "Nenhuma URL com erro 5xx" in html


def test_amostra_e_dita():
    html = render_bloco("urls", dados_do_papel("urls", alvos_com(resposta_medida(
        [item("a.test", "/x")], amostra=True, amostradas=2, cobertas=[{}] * 20, falhas=["o Loki respondeu 500"]))))
    assert "amostra" in html and "20 de 24" in html and "limite de 5.000" in html


def test_cobertura_inteira_nao_diz_amostra():
    html = render_bloco("urls", dados_do_papel("urls", alvos_com(resposta_medida([item("a.test", "/x")]))))
    assert "amostra" not in html.lower() and "24 horas" in html


def test_sem_fonte_diz_nao_medido_com_a_instrucao():
    html = br_render_sem_fonte()
    assert "Não medido" in html and "logs_url" in html and "URLs mais acessadas" in html


def br_render_sem_fonte():
    alvos = alvos_com({"pergunta": ID, "sem_dados": True, "nao_publica": True,
                       "motivo": logql.SEM_LOGS_URL})
    return render_bloco("urls", dados_do_papel("urls", alvos))


def test_nenhum_proxy_tambem_ensina():
    html = render_bloco("urls", dados_do_papel("urls", [{"nome": "a", "componentes": []}]))
    assert "Não medido" in html and "logs_url" in html


def test_falha_da_fonte_declarada_diz_o_motivo_real():
    alvos = alvos_com({"pergunta": ID, "sem_dados": True, "motivo": "o Loki respondeu 401"})
    assert "o Loki respondeu 401" in render_bloco("urls", dados_do_papel("urls", alvos))


def test_alvo_sem_medida_e_dito_ao_lado_do_que_mediu():
    alvos = alvos_com(resposta_medida([item("a.test", "/x")]),
                      {"pergunta": ID, "sem_dados": True, "motivo": "o Loki respondeu 401"})
    html = render_bloco("urls", dados_do_papel("urls", alvos))
    assert "a.test" in html and "a1" in html and "o Loki respondeu 401" in html


def test_dois_proxies_do_mesmo_alvo_nao_duplicam():
    medida = resposta_medida([item("a.test", "/x")])
    alvos = [{"nome": "a", "componentes": [{"nome": n, "papel": "entrada", "respostas": [medida]}
                                           for n in ("p1", "p2")]}]
    assert len(dados_do_papel("urls", alvos)["geral"]) == 1


def test_html_escapa_o_caminho():
    html = render_bloco("urls", dados_do_papel("urls", alvos_com(resposta_medida([item("a.test", "/<b>")]))))
    assert "<b>/<b>" not in html.replace("&lt;", "") and "&lt;b&gt;" in html


def test_bloco_sai_nos_detalhes_tecnicos_depois_de_sites():
    corte = dict(op.SEM_CORTE, filas_max=op.FILAS_MAX)
    html = br._blocos_tecnicos(alvos_com(resposta_medida([item("a.test", "/x")])), corte)
    assert html.index("Serviços web") < html.index("URLs mais acessadas")


# ---------------------------------------------------------------- orçamento de páginas
def test_orcamento_conta_as_linhas_das_urls():
    base = {"regras": 3, "sistemas": 5}
    assert op._linhas({**base, "urls": 40}, 8) == op._linhas(base, 8) + 40


def test_sem_aperto_mostra_tudo_e_avisa_dos_sites_de_fora():
    r = op.cortes({"regras": 1, "sistemas": 1, "urls_sites": 7})
    assert (r["urls_geral"], r["urls_por_site"], r["urls_sites"], r["urls_destaques"]) == (15, 3, 5, 5)
    assert any("5 de 7 sites" in a for a in r["avisos"])


def test_no_aperto_corta_as_urls_e_avisa():
    r = op.cortes({"achados": 204, "regras": 10, "sistemas": 30, "urls": 40, "urls_sites": 7})
    assert (r["urls_geral"], r["urls_por_site"], r["urls_sites"], r["urls_destaques"]) == (15, 2, 3, 3)
    assert any("URLs" in a and "report.json" in a for a in r["avisos"])


def test_sem_urls_medidas_nao_ha_aviso():
    r = op.cortes({"achados": 204, "regras": 10, "sistemas": 30})
    assert not any("URLs" in a for a in r["avisos"])


def test_o_corte_chega_ao_bloco():
    corte = dict(op.SEM_CORTE, urls_geral=5, urls_por_site=2, urls_sites=3, urls_destaques=3)
    dados = br._dados_com_corte("urls", alvos_com(resposta_medida(varios_sites())), corte)
    html = render_bloco("urls", dados)
    assert html.count('<tr class="bl-url-g">') == 5 and html.count('class="bl-url"') == 3
    assert html.count('class="bl-url-l"') == 6 and html.count('class="bl-url-s"') == 3


def test_a_fixture_grande_traz_o_bloco():
    from tests.fixtures.relatorio_grande import relatorio_grande
    html = br.render_html_v3(relatorio_grande())
    assert "URLs mais acessadas" in html and "URLs com mais erros" in html
    assert re.search(r'class="bl-aviso">[^<]*URLs', html)


# ---------------------------------------------------------------- documentação
def test_skill_documenta_a_fonte_e_a_protecao():
    texto = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
    assert "| `logql` | o Loki declarado em `logs_url`" in texto and "próximo ciclo |\n| `logql`" not in texto
    for trecho in ("line_format", "maximum of series", "Cookie", "`logs_url`", "amostra"):
        assert trecho in texto, trecho


@pytest.mark.parametrize("cru, esperado", [
    ("/reset/V1StGXR8_Z5jdHi6B-myT", "/reset/:token"),
    ("/cpf/123.456.789-00", "/cpf/:token"),
    ("/a/session=abcdef", "/a/:token"),
    ("/x%253Ftoken=abc123secret", "/:token"),
    ("/u/joao%2540example.com/x", "/u/:token/x"),
    ("/api/v1/accounts/42/contacts", "/api/v1/accounts/:id/contacts"),
    ("/storage/images/foto.png", "/storage/images/foto.png"),
])
def test_so_o_que_tem_cara_de_rota_aparece(cru, esperado):
    assert au.normalizar_caminho(cru) == esperado
