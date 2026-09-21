# tests/test_relatorio_honesto_batch6.py
"""O relatório dizendo o que a documentação promete.

A revisão do último batch leu o PDF de um broker de 500 filas e achou quatro lugares em que o
relatório contradizia o que a SKILL.md afirma: a fila travada "aparece na coluna de não
confirmadas" e não aparecia em lugar nenhum; "mostra as 10 primeiras de cada lista e diz
quantas ficaram de fora" e duas listas cortavam em silêncio; um broker sem contadores saía com
tabelas de "—" carimbadas com a fonte; e o nó da topologia mostrava o tamanho do corte como se
fosse uma contagem.
"""
import json

import collect
from build_report import _no_da_topologia, _resposta
from lib import adaptadores, http_get
from lib.catalogo_api import familias
from lib.extracao import extrair
from lib.orcamento import Prazo

TRAVADA = {"name": "travada", "vhost": "/", "messages_ready": 0,
           "messages_unacknowledged": 80000, "consumers": 4}
FILAS = ([{"name": f"cheia-{n:02d}", "vhost": "/", "messages_ready": 5000 - n,
           "messages_unacknowledged": 0, "consumers": 2} for n in range(20)]
         + [TRAVADA])


def _declarada(id_):
    familia = next(f for f in familias() if f["familia"] == "amqp-mgmt")
    return next(p for p in familia["pergunta"] if p["id"] == id_)


def test_a_fila_travada_encabeca_a_lista_de_filas():
    """80 mil mensagens entregues e nunca confirmadas: é o caso pior, e ordenar por "prontas"
    a mandava para o fim — invisível atrás do corte. A lista agora é ordenada pelo que está
    ACUMULADO (prontas + não confirmadas)."""
    itens = extrair(json.loads(json.dumps(FILAS)), _declarada("fila.filas"))

    assert itens[0]["nome"] == "travada"
    assert itens[0]["nao_confirmadas"] == 80000


def test_nenhuma_lista_do_catalogo_corta_na_extracao():
    """Com `limite` na extração, o relatório não sabia que havia mais — nem o `report.json`
    tinha. O corte é SÓ do relatório, que diz quantas ficaram de fora."""
    familia = next(f for f in familias() if f["familia"] == "amqp-mgmt")

    assert [p["id"] for p in familia["pergunta"] if p.get("limite") is not None] == []


def test_toda_lista_grande_diz_quantas_ficaram_de_fora():
    for id_ in ("fila.filas", "fila.consumidores_por_fila", "fila.taxa_entrada_saida"):
        itens = extrair(json.loads(json.dumps(FILAS)), _declarada(id_))
        html = _resposta({"pergunta": id_, "fonte": "admin_http:amqp-mgmt", "valor": itens})

        assert "e mais 11" in html, id_


# --- lista sem nenhum número ---

def _responder(filas):
    def rede(url, permitidos, credencial, alvo=None, timeout=None):
        if url.split("?")[0].endswith("/api/overview"):
            return 200, json.dumps({"product_name": "X", "rabbitmq_version": "4.0"})
        return 200, json.dumps(filas)

    import pytest

    mp = pytest.MonkeyPatch()
    mp.setattr(http_get, "get_autenticado", rede)
    try:
        componente = {"nome": "broker", "papel": "fila",
                      "admin_url": "http://exemplo.test:15672", "respostas": []}
        collect.responder(componente, {"timeout": 20, "http_timeout": 8, "alvo": "p",
                                       "cache": {}}, adaptadores.todos(), Prazo(120))
        return componente
    finally:
        mp.undo()


def test_lista_sem_nenhum_numero_vira_sem_dados_em_toda_pergunta():
    """Broker com estatísticas desligadas: a listagem traz só nome e vhost. As duas perguntas
    SEM limiar saíam como tabelas de 500 linhas de "—", carimbadas com a fonte — pareciam
    respondidas e não diziam nada."""
    componente = _responder([{"name": f"f{n}", "vhost": "/"} for n in range(50)])

    assert all(r.get("sem_dados") for r in componente["respostas"]), componente["respostas"]


def test_topologia_nao_mostra_o_tamanho_de_uma_lista_qualquer_como_contagem():
    """Com `fila.filas` sem dados, a "primeira resposta" virava `consumidores_por_fila`, e o nó
    dizia "Consumidores por fila: 10" — o tamanho do corte, apresentado como fato."""
    componente = {"nome": "broker", "papel": "fila", "achados": [], "respostas": [
        {"pergunta": "fila.filas", "sem_dados": True, "motivo": "x"},
        {"pergunta": "fila.consumidores_por_fila", "fonte": "a",
         "valor": [{"nome": "a", "consumidores": 2}] * 10}]}

    html = _no_da_topologia({"nome": "p"}, componente)

    assert "Consumidores por fila: 10" not in html


def test_topologia_conta_a_populacao_quando_ela_respondeu():
    componente = {"nome": "broker", "papel": "fila", "achados": [], "respostas": [
        {"pergunta": "fila.filas", "fonte": "a",
         "valor": [{"nome": f"f{n}", "prontas": 1} for n in range(500)]}]}

    assert "Filas: 500" in _no_da_topologia({"nome": "p"}, componente)


# --- o detalhe do achado filtra por NOME de campo, não por valor ---

def test_detalhe_nao_esconde_campo_cujo_valor_coincide_com_a_identidade():
    """A regra anterior comparava VALOR: um vhost chamado `stream` e um campo `tipo: stream`
    fariam o tipo sumir do detalhe. A identidade é uma lista de NOMES de campo, e é por nome
    que se filtra."""
    resposta = {"pergunta": "fila.filas", "fonte": "a", "identidade": ["nome", "vhost"],
                "valor": [{"objeto": "q@stream", "nome": "q", "vhost": "stream",
                           "tipo": "stream", "prontas": 3, "consumidores": 0}]}

    achado = collect.achados_da_resposta(
        resposta, {"quando": "consumidores == 0 e prontas > 0", "regra": "fila_sem_consumidor"},
        componente="broker")[0]

    assert "tipo: stream" in achado["detalhe"]
    assert "vhost" not in achado["detalhe"]
