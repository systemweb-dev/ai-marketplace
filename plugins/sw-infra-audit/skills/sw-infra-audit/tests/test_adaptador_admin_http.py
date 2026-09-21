# tests/test_adaptador_admin_http.py
"""O adaptador que fala com API de administração.

Ele não sabe o que é o produto. Pergunta "que família você é?" olhando as chaves do JSON de
identificação, e a partir daí tudo vem do arquivo daquela família.

Os testes substituem `http_get.get_autenticado` — a fronteira de rede — e não sobem servidor.
O catálogo usado é um arquivo de teste em `tmp_path`, para o teste não depender do catálogo
publicado (que tem os próprios testes).
"""
import json

import pytest

from lib.adaptadores import admin_http

COMPONENTE = {"nome": "broker", "papel": "fila",
              "admin_url": "http://exemplo.test:15672", "senha_env": "SENHA_BROKER"}

OVERVIEW = json.dumps({"product_name": "Exemplo", "product_version": "4.0"})
QUEUES = json.dumps([
    {"name": "pedidos", "vhost": "/", "messages_ready": 42, "consumers": 3},
    {"name": "emails", "vhost": "/", "messages_ready": 7, "consumers": 0},
    {"name": "emails", "vhost": "staging", "messages_ready": 2, "consumers": 0},
])

CATALOGO = """
familia = "exemplo-mgmt"
prioridade = 20

[identificacao]
caminho = "/api/overview"
exige_chaves = ["product_name"]
aceita_401 = true

[[pergunta]]
id = "fila.filas"
caminho = "/api/queues"
lista = ""
identidade = ["nome", "vhost"]
campos = { nome = "/name", vhost = "/vhost", prontas = "/messages_ready", consumidores = "/consumers" }
transformar = { prontas = "inteiro", consumidores = "inteiro" }
ordenar_por = "prontas"
ordem = "desc"
desempate = "nome"
"""


@pytest.fixture(autouse=True)
def catalogo(tmp_path, monkeypatch):
    """`familias(pasta=PASTA)` fixa o default na definição, então trocar `PASTA` não bastaria:
    substitui-se a função que o adaptador chama."""
    from lib.catalogo_api import carregar_arquivo

    (tmp_path / "exemplo-mgmt.toml").write_text(CATALOGO, encoding="utf-8")
    carregadas = [carregar_arquivo(tmp_path / "exemplo-mgmt.toml")]
    monkeypatch.setattr(admin_http.catalogo_api, "familias", lambda: carregadas)


@pytest.fixture
def api(monkeypatch):
    """Mapa caminho -> (status, corpo). O que não estiver no mapa devolve (404, "")."""
    mapa, pedidos = {}, []

    def falso(url, permitidos, credencial, alvo=None, timeout=None):
        par = credencial.para(url, alvo) if credencial else None
        pedidos.append((url, par, alvo))
        for caminho, resposta in mapa.items():
            if url.endswith(caminho):
                return resposta
        return (404, "")

    monkeypatch.setattr(admin_http.http_get, "get_autenticado", falso)
    return mapa, pedidos


@pytest.fixture
def contexto(monkeypatch):
    monkeypatch.setenv("SENHA_BROKER", "abre-te")
    return {"timeout": 5, "janela": "24h", "at": "2026-09-19T22:00:00Z", "alvo": "prod"}


def test_responde_a_populacao_inteira_com_fonte(api, contexto):
    """Sem `limite`: o limiar precisa ver todas as filas, não só as de cima."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["fonte"] == "admin_http:exemplo-mgmt"
    assert len(resposta["valor"]) == 3


def test_identidade_composta_distingue_vhosts(api, contexto):
    """`emails` em `/` e em `staging` são duas filas. Sem a identidade composta viravam o mesmo
    achado, e no histórico colapsavam numa chave só."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    objetos = sorted(item["objeto"] for item in resposta["valor"])
    assert objetos == ["emails@/", "emails@staging", "pedidos@/"]


def test_sem_admin_url_diz_o_que_declarar(api, contexto):
    resposta = admin_http.perguntar("fila.filas", {"nome": "broker", "papel": "fila"}, contexto)

    assert resposta["sem_dados"] is True
    assert "admin_url" in resposta["motivo"]


def test_api_que_nao_responde_vira_sem_dados(api, contexto):
    mapa, _ = api
    mapa["/api/overview"] = (None, None)

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "não respondeu" in resposta["motivo"]


def test_401_diz_que_falta_credencial_e_nao_que_a_api_caiu(api, contexto):
    """A diferença entre "exporte a variável" e "a rede está quebrada"."""
    mapa, _ = api
    mapa["/api/overview"] = (401, "")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "credencial" in resposta["motivo"]


def test_json_que_nao_bate_com_nenhuma_familia(api, contexto):
    mapa, _ = api
    mapa["/api/overview"] = (200, json.dumps({"algo": "outro"}))

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "família" in resposta["motivo"]


def test_pergunta_que_a_familia_identificada_nao_expoe(api, contexto, tmp_path,
                                                       monkeypatch):
    """Duas famílias: a OUTRA sabe responder `taxa_entrada_saida`, a identificada não. O motivo
    precisa nomear a identificada — "esta API não expõe isto" é informação; "ninguém sabe" seria
    falso, porque alguém sabe."""
    from lib.catalogo_api import carregar_arquivo

    outra = tmp_path / "outra-mgmt.toml"
    outra.write_text("""
familia = "outra-mgmt"
prioridade = 30

[identificacao]
caminho = "/api/outra"
exige_chaves = ["so_a_outra_tem"]

[[pergunta]]
id = "fila.taxa_entrada_saida"
caminho = "/api/queues"
lista = ""
campos = { nome = "/name", entrada = "/in" }
ordenar_por = "entrada"
ordem = "desc"
desempate = "nome"
""", encoding="utf-8")
    nossa = tmp_path / "exemplo-mgmt.toml"
    monkeypatch.setattr(admin_http.catalogo_api, "familias",
                        lambda: [carregar_arquivo(nossa), carregar_arquivo(outra)])
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)

    resposta = admin_http.perguntar("fila.taxa_entrada_saida", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "exemplo-mgmt não expõe" in resposta["motivo"]


def test_pergunta_que_nenhuma_api_conhece_se_declara_fora_de_alcance(api, contexto):
    """Sem nenhuma família que conheça a pergunta, o adaptador se marca como fora de alcance,
    para o `responder` preferir o motivo de outro adaptador."""
    resposta = admin_http.perguntar("entrada.latencia", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert resposta.get("nao_se_aplica") is True


def test_a_credencial_chega_amarrada_ao_alvo(api, contexto):
    """O adaptador entrega o OBJETO e o alvo; quem decide o par é `get_autenticado`."""
    mapa, pedidos = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)

    admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert pedidos and all(par == ("guest", "abre-te") and alvo == "prod"
                           for _, par, alvo in pedidos)


def test_a_senha_nao_entra_na_resposta(api, contexto):
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)
    componente = dict(COMPONENTE)

    resposta = admin_http.perguntar("fila.filas", componente, contexto)

    assert "abre-te" not in json.dumps(resposta)
    assert "abre-te" not in json.dumps(componente)
    assert "abre-te" not in repr(contexto)


def test_credencial_faltando_vira_sem_dados_e_nao_excecao(api, contexto, monkeypatch):
    """O contrato do adaptador é NUNCA levantar."""
    monkeypatch.delenv("SENHA_BROKER")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "SENHA_BROKER" in resposta["motivo"]


def test_a_identificacao_e_feita_uma_vez_por_componente(api, contexto):
    mapa, pedidos = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)
    componente = dict(COMPONENTE)

    admin_http.perguntar("fila.filas", componente, contexto)
    admin_http.perguntar("fila.consumidores_por_fila", componente, contexto)

    assert sum(1 for url, _, _ in pedidos if url.endswith("/api/overview")) == 1


def test_corpo_que_nao_e_json_vira_sem_dados(api, contexto):
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, "<html>erro</html>")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True


def test_resposta_que_nao_casa_com_o_catalogo_vira_sem_dados(api, contexto):
    """A API mudou o formato (objeto onde se esperava lista): é sem_dados com motivo, não
    exceção que derruba o alvo."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, json.dumps({"items": []}))

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "catálogo" in resposta["motivo"]


def test_broker_sem_fila_e_resposta_nao_ausencia(api, contexto):
    """Broker sem fila nenhuma é um FATO ("zero filas"), não um "não li". Tratá-lo como
    sem_dados mandaria o dono investigar uma coleta que funcionou."""
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, "[]")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta.get("sem_dados") is not True
    assert resposta["valor"] == []


def test_caminho_da_lista_ausente_nao_vira_zero_filas(api, contexto, tmp_path, monkeypatch):
    """O oposto do teste acima: se o catálogo aponta para `/items` e a resposta não tem
    `/items`, a API mudou de formato. Devolver `[]` diria "zero filas" sobre uma resposta que
    ninguém entendeu — e "zero filas" nunca dispara limiar, então o relatório sairia limpo."""
    from lib.catalogo_api import carregar_arquivo

    arquivo = tmp_path / "com-items.toml"
    arquivo.write_text(CATALOGO.replace('lista = ""', 'lista = "/items"'), encoding="utf-8")
    monkeypatch.setattr(admin_http.catalogo_api, "familias",
                        lambda: [carregar_arquivo(arquivo)])
    mapa, _ = api
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, json.dumps({"outra_coisa": []}))

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "catálogo" in resposta["motivo"]


def test_id_do_adaptador():
    assert admin_http.ID == "admin_http"


def test_registrado_com_prioridade_menor_que_promql():
    """Menor prioridade vence: o específico sabe mais que o genérico."""
    from lib.adaptadores import REGISTRO, todos

    assert REGISTRO["admin_http"]["prioridade"] < REGISTRO["promql"]["prioridade"]
    assert [m.ID for m in todos()][0] == "admin_http"
