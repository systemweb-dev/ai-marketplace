# tests/test_admin_http_producao.py
"""O `admin_http` diante de um broker de verdade.

A revisão do batch 5 mediu o que os testes de caminho feliz não mostravam: estatísticas
desligadas, resposta maior que o teto, porta errada, permissão faltando, catálogo quebrado. Em
cada um o adaptador ou mentia sobre o motivo, ou dava "verde" sobre o que não leu.
"""
import json

import pytest

import collect
from lib import http_get
from lib.adaptadores import admin_http
from lib.orcamento import Prazo

COMPONENTE = {"nome": "broker", "papel": "fila", "admin_url": "http://exemplo.test:15672"}
OVERVIEW = json.dumps({"product_name": "Exemplo", "rabbitmq_version": "4.0"})


@pytest.fixture
def api(monkeypatch):
    mapa, pedidos = {}, []

    def falso(url, permitidos, credencial, alvo=None, timeout=None):
        pedidos.append((url, timeout))
        for caminho, resposta in mapa.items():
            if url.split("?")[0].endswith(caminho):
                if isinstance(resposta, Exception):
                    raise resposta
                return resposta
        return (404, "")

    monkeypatch.setattr(admin_http.http_get, "get_autenticado", falso)
    return mapa, pedidos


def _contexto():
    return {"timeout": 20, "http_timeout": 8, "orcamento": 120, "alvo": "prod", "cache": {}}


def _responder(adaptadores=None):
    componente = dict(COMPONENTE, respostas=[])
    collect.responder(componente, _contexto(), adaptadores or [admin_http], Prazo(120))
    return componente


# --- custo: uma identificação e um download por endpoint, por componente ---

def test_tres_perguntas_uma_identificacao_e_um_download(api):
    """As três perguntas de `fila` leem o MESMO `/api/queues`. Sem cache eram 3 identificações
    e 3 downloads inteiros — num broker de 5 mil filas, 25 MB para responder uma pergunta."""
    mapa, pedidos = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, "[]")

    _responder()

    caminhos = [url.split("?")[0].rsplit("/api", 1)[1] for url, _ in pedidos]
    assert caminhos.count("/overview") == 1
    assert caminhos.count("/queues") == 1


def test_usa_o_timeout_de_http_nao_o_de_comando(api):
    mapa, pedidos = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, "[]")

    _responder()

    assert all(timeout <= 8 for _, timeout in pedidos)


# --- motivos que mandam procurar no lugar certo ---

@pytest.mark.parametrize("status, trecho", [(403, "permissão"), (302, "redireciona"),
                                            (301, "redireciona")])
def test_identificacao_com_status_revelador(api, status, trecho):
    """403 ou 302 viravam "não reconheci a família" — e o dono ia procurar o catálogo errado,
    quando o problema é permissão ou o proxy redirecionando http para https."""
    mapa, _ = api
    mapa["/api/overview"] = (status, "")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), _contexto())

    assert trecho in resposta["motivo"]


def test_status_da_consulta_nao_e_descartado(api):
    """Overview 200 e `/api/queues` 403 virava "não respondeu" — respondeu, e recusou."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (403, "")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), _contexto())

    assert "403" in resposta["motivo"]


def test_resposta_grande_demais_e_dita_como_tal(api):
    """Acima do teto, o corpo era cortado no meio, o JSON quebrava, e o motivo dizia "a API não
    respondeu". Respondeu — grande demais."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = http_get.RespostaGrandeDemais(http_get.MAX_BYTES)

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), _contexto())

    assert resposta["sem_dados"] is True
    assert "grande" in resposta["motivo"]


def test_catalogo_quebrado_nao_derruba_as_perguntas_de_outro_papel(api, monkeypatch):
    """Um TOML de API quebrado virava erro em TODAS as perguntas de TODOS os papéis — inclusive
    `entrada`, que o `admin_http` nem responde — porque `perguntar` lê o catálogo antes de
    tudo. Com o promql depois dele, o proxy ficava sem resposta por culpa do broker."""
    from lib import catalogo_api

    def quebrado():
        raise catalogo_api.CatalogoInvalido("x.toml: TOML inválido")

    monkeypatch.setattr(admin_http.catalogo_api, "familias", quebrado)

    resposta = admin_http.perguntar("entrada.latencia", {"nome": "proxy"}, _contexto())

    assert resposta["sem_dados"] is True
    assert resposta.get("nao_se_aplica") is True


# --- estatísticas desligadas ---

def test_populacao_sem_os_contadores_do_limiar_vira_sem_dados(api):
    """Com as estatísticas do broker desligadas, `/api/queues` vem sem `messages_ready` e sem
    `consumers`. Eram 300 itens com None, zero achados e alvo verde: a pergunta aparecia como
    respondida sobre números que ninguém leu. None não é zero — no agregado também não."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, json.dumps([{"name": f"f{n}", "vhost": "/"}
                                            for n in range(300)]))

    componente = _responder()
    filas = next(r for r in componente["respostas"] if r["pergunta"] == "fila.filas")

    assert filas["sem_dados"] is True
    assert "estatísticas" in filas["motivo"]
    assert componente.get("achados", []) == []


def test_fila_recem_criada_sem_contador_nao_invalida_as_outras(api):
    """Um item sem contador (fila recém-criada) não anula a resposta inteira."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, json.dumps([
        {"name": "nova", "vhost": "/"},
        {"name": "emails", "vhost": "/", "messages_ready": 7, "consumers": 0}]))

    componente = _responder()
    filas = next(r for r in componente["respostas"] if r["pergunta"] == "fila.filas")

    assert not filas.get("sem_dados")
    assert [a["objeto"] for a in componente["achados"]] == ["emails@/"]


# --- identidade que o dono consegue digitar ---

def test_identidade_e_nome_arroba_vhost(api):
    """`/ · emails` exigia o caractere U+00B7 exato num aceite; `emails@/` se digita."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, json.dumps([
        {"name": "emails", "vhost": "staging", "messages_ready": 2, "consumers": 0}]))

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), _contexto())

    assert resposta["valor"][0]["objeto"] == "emails@staging"


def test_campo_de_identidade_ausente_nao_vira_none(api):
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, json.dumps([{"name": "x", "messages_ready": 1,
                                             "consumers": 0}]))

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), _contexto())

    assert resposta["valor"][0]["objeto"] == "x"


# --- as mutações que sobreviviam à suíte ---

def test_json_com_so_parte_das_chaves_exigidas_nao_identifica(api):
    """`product_name` sozinho existe em mais de uma API; a família exige as duas chaves. Trocar
    `all` por `any` na identificação passava com a suíte verde."""
    mapa, _ = api
    mapa["/api/overview"] = (200, json.dumps({"product_name": "Outro Produto"}))

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), _contexto())

    assert resposta["sem_dados"] is True
    assert "não reconheci" in resposta["motivo"]


def test_401_numa_familia_nao_impede_a_seguinte(api, tmp_path, monkeypatch):
    """Com duas famílias, a primeira que responde 401 não encerra a busca — a segunda pode ser a
    certa. Um `break` no lugar do `continue` só era pego com duas famílias, e todos os testes
    tinham uma."""
    from lib.catalogo_api import carregar_arquivo, familias

    real = familias()
    primeira = tmp_path / "primeira.toml"
    primeira.write_text("""
familia = "primeira"
prioridade = 10

[identificacao]
caminho = "/api/primeira"
exige_chaves = ["x"]
aceita_401 = true
""", encoding="utf-8")
    monkeypatch.setattr(admin_http.catalogo_api, "familias",
                        lambda: [carregar_arquivo(primeira), *real])
    mapa, _ = api
    mapa["/api/primeira"] = (401, "")
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, "[]")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), _contexto())

    assert resposta["fonte"] == "admin_http:amqp-mgmt"


def test_quando_nenhum_adaptador_conhece_a_pergunta_a_marca_nao_vai_ao_relatorio():
    """A remoção da marca só roda quando a resposta FINAL a carrega — e isso só acontece quando
    NENHUM adaptador conhece a pergunta. O teste anterior nunca chegava lá."""
    class NaoConhece:
        ID = "nao"

        def perguntar(self, pergunta, componente, contexto):
            return {"pergunta": pergunta, "sem_dados": True, "motivo": "não conheço",
                    "nao_se_aplica": True}

    componente = {"nome": "proxy", "papel": "entrada", "respostas": []}

    collect.responder(componente, _contexto(), [NaoConhece(), NaoConhece()], Prazo(120))

    assert componente["respostas"]
    assert all("nao_se_aplica" not in r for r in componente["respostas"])


def test_promql_se_marca_quando_nenhuma_familia_conhece_a_pergunta():
    from lib.adaptadores import promql

    resposta = promql.perguntar("fila.filas", {"nome": "broker"}, _contexto())

    assert resposta.get("nao_se_aplica") is True


# --- pergunta escalar ---

def test_pergunta_escalar_devolve_numero_e_nao_dicionario(api, tmp_path, monkeypatch):
    """`extrair` de pergunta escalar devolve `{"valor": 17}`. Repassado assim, o limiar
    comparava um dicionário e o relatório imprimia `{'valor': 17}` onde se esperava 17."""
    from lib import perguntas
    from lib.catalogo_api import carregar_arquivo

    monkeypatch.setitem(perguntas.PERGUNTAS, "fila.total_de_teste",
                        {"id": "fila.total_de_teste", "papel": "fila", "titulo": "Total",
                         "forma": "escalar", "unidade": None, "limiar": None,
                         "desempate": None, "faixa": None})
    arquivo = tmp_path / "escalar.toml"
    arquivo.write_text("""
familia = "escalar"
prioridade = 20

[identificacao]
caminho = "/api/overview"
exige_chaves = ["product_name"]

[[pergunta]]
id = "fila.total_de_teste"
caminho = "/api/overview"
campos = { valor = "/total" }
transformar = { valor = "inteiro" }
""", encoding="utf-8")
    monkeypatch.setattr(admin_http.catalogo_api, "familias", lambda: [carregar_arquivo(arquivo)])
    mapa, _ = api
    mapa["/api/overview"] = (200, json.dumps({"product_name": "X", "total": "17"}))

    resposta = admin_http.perguntar("fila.total_de_teste", dict(COMPONENTE), _contexto())

    assert resposta["valor"] == 17
