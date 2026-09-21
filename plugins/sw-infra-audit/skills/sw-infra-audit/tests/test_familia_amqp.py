# tests/test_familia_amqp.py
"""O arquivo de família que a skill publica.

Ele é dado, não código — mas dado que decide para onde a credencial vai e o que vira achado, e
por isso tem teste.
"""
import json

from lib.catalogo_api import PASTA, carregar_arquivo, familias
from lib.extracao import extrair
from lib.limiar import compilar
from lib.perguntas import PERGUNTAS

ARQUIVO = PASTA / "amqp-mgmt.toml"


def _familia():
    return next(f for f in familias() if f["familia"] == "amqp-mgmt")


def _declarada(id_):
    return next(p for p in _familia()["pergunta"] if p["id"] == id_)


def test_o_arquivo_passa_na_propria_validacao():
    assert carregar_arquivo(ARQUIVO)["familia"] == "amqp-mgmt"


def test_o_nome_da_familia_e_do_formato_nao_do_produto():
    """Nome de produto no identificador é o começo do `if produto == ...` que o spec proíbe."""
    assert "rabbit" not in _familia()["familia"].lower()


def test_todo_caminho_e_de_leitura():
    """A API tem PUT e DELETE em filas e POST para publicar. O adaptador só faz GET, mas o
    catálogo é a lista do que ele ALCANÇA — e é essa lista que um revisor lê."""
    familia = _familia()
    caminhos = [familia["identificacao"]["caminho"]] + [p["caminho"] for p in familia["pergunta"]]

    for caminho in caminhos:
        rota, _, consulta = caminho.partition("?")
        assert rota.startswith("/api/")
        # Escrita, nesta API, é ROTA (`/api/queues/{vhost}/{fila}/contents`, `/purge`...). O
        # parâmetro `columns` só escolhe campos a LER — `publish_details` é o nome de uma
        # coluna de leitura, não um endpoint. Por isso a checagem de palavra é na rota, e a
        # consulta só pode trazer `columns`.
        for palavra in ("delete", "purge", "publish", "create", "reset", "close", "move",
                        "contents", "get"):
            assert palavra not in rota.lower(), f"{rota}: {palavra}"
        for parametro in filter(None, consulta.split("&")):
            assert parametro.split("=")[0] == "columns", f"parâmetro inesperado: {parametro}"


def test_as_perguntas_leem_o_mesmo_caminho():
    """Um download por componente só acontece se o caminho for IDÊNTICO nas três."""
    assert len({p["caminho"] for p in _familia()["pergunta"]}) == 1


def test_columns_pede_tudo_que_as_perguntas_extraem():
    """`columns=` que esquecesse um campo faria o contador sumir — e sem o contador a resposta
    inteira vira sem_dados ("estatísticas desligadas?") por culpa do catálogo."""
    familia = _familia()
    colunas = set(familia["pergunta"][0]["caminho"].split("columns=")[1].split(","))
    for pergunta in familia["pergunta"]:
        for ponteiro_ in pergunta["campos"].values():
            assert ponteiro_.strip("/").replace("/", ".") in colunas, ponteiro_


def test_identificacao_exige_as_duas_chaves():
    """`product_name` sozinho casaria com qualquer API que tenha esse campo."""
    assert set(_familia()["identificacao"]["exige_chaves"]) == {"product_name",
                                                                "rabbitmq_version"}


def test_consumidores_por_fila_e_taxa_leem_os_campos_certos():
    """Trocar `deliver_get_details` por `ack_details`, ou `consumers` por outro contador,
    passava com a suíte verde."""
    consumidores = _declarada("fila.consumidores_por_fila")["campos"]
    taxa = _declarada("fila.taxa_entrada_saida")["campos"]

    assert consumidores["consumidores"] == "/consumers"
    assert taxa["entrada"] == "/message_stats/publish_details/rate"
    assert taxa["saida"] == "/message_stats/deliver_get_details/rate"


def test_a_prioridade_e_a_do_adaptador():
    from lib.adaptadores import REGISTRO

    assert _familia()["prioridade"] == REGISTRO["admin_http"]["prioridade"]


def test_responde_todas_as_perguntas_do_papel_fila():
    declaradas = {p["id"] for p in _familia()["pergunta"]}

    assert declaradas == {id_ for id_, p in PERGUNTAS.items() if p["papel"] == "fila"}


# --- ponta a ponta sobre um JSON no formato real da API ---

QUEUES = [
    {"name": "pedidos", "vhost": "/", "messages_ready": 42, "messages_unacknowledged": 0,
     "consumers": 3,
     "message_stats": {"publish_details": {"rate": 8.0}, "deliver_get_details": {"rate": 8.5}}},
    {"name": "emails", "vhost": "/", "messages_ready": 7, "messages_unacknowledged": 0,
     "consumers": 0},
    {"name": "emails", "vhost": "staging", "messages_ready": 2, "messages_unacknowledged": 0,
     "consumers": 0},
    {"name": "travada", "vhost": "/", "messages_ready": 0, "messages_unacknowledged": 80000,
     "consumers": 4},
    {"name": "ociosa", "vhost": "/", "messages_ready": 0, "messages_unacknowledged": 0,
     "consumers": 0},
]


def test_o_limiar_ve_todas_as_filas_orfas_com_mensagem():
    """O caso que motivou tirar o `limite`: TODA fila órfã com mensagem vira achado, não só as
    que caberiam num top 10."""
    itens = extrair(json.loads(json.dumps(QUEUES)), _declarada("fila.filas"))
    cruzou = compilar(PERGUNTAS["fila.filas"]["limiar"]["quando"])

    orfas = sorted((i["vhost"], i["nome"]) for i in itens if cruzou(i))

    assert orfas == [("/", "emails"), ("staging", "emails")]


def test_300_orfas_atras_de_10_filas_cheias_viram_300_achados():
    """A sonda do juiz que dava 🟢 e zero achados com `limite = 10`."""
    cheias = [{"name": f"cheia-{n}", "vhost": "/", "messages_ready": 5000, "consumers": 2}
              for n in range(10)]
    orfas = [{"name": f"orfa-{n}", "vhost": "/", "messages_ready": 3, "consumers": 0}
             for n in range(300)]
    itens = extrair(cheias + orfas, _declarada("fila.filas"))
    cruzou = compilar(PERGUNTAS["fila.filas"]["limiar"]["quando"])

    assert sum(1 for i in itens if cruzou(i)) == 300


def test_a_fila_travada_fica_visivel_na_lista():
    """Consumidor conectado que não confirma: a regra não dispara, mas a coluna
    `nao_confirmadas` torna o caso pior visível no relatório."""
    itens = extrair(json.loads(json.dumps(QUEUES)), _declarada("fila.filas"))
    travada = next(i for i in itens if i["nome"] == "travada")

    assert travada["nao_confirmadas"] == 80000


def test_fila_ociosa_sem_taxas_vai_para_o_fim_do_ritmo():
    """Fila ociosa não traz `message_stats`: saldo None vai para o fim, não aparece como zero."""
    itens = extrair(json.loads(json.dumps(QUEUES)), _declarada("fila.taxa_entrada_saida"))

    assert itens[0]["nome"] == "pedidos" and itens[0]["saldo"] == -0.5
    assert all(i["saldo"] is None for i in itens[1:])
