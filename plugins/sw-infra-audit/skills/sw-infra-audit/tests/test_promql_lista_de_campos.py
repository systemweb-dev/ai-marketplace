"""O adaptador promql respondendo uma lista cujos itens têm vários campos.

Uma consulta por campo, juntas pela etiqueta declarada em `chave`. É o que permite o papel
`fila` ser respondido por quem tem o exporter no Prometheus e não a credencial da API de
administração — e é a última coisa que o `lib/enrich.py` fazia e o catálogo não.
"""
import json
import pytest

from lib import catalogo
from lib.adaptadores import promql

from test_adaptador_promql import CONTEXTO, _vetor, prometheus  # noqa: F401

FAMILIA = """
familia = "exporter-de-fila"
prioridade = 50
papel = "fila"
identifica_papel = true
[identificacao]
metrica_presente = "fila_mensagens_prontas"
[seletor]
etiqueta = "job"

[[pergunta]]
id = "fila.filas"
chave = "queue"
desempate = "nome"
ordenar_por = "prontas"
valor = "inteiro"
  [[pergunta.campo]]
  nome = "prontas"
  query = 'sum by (queue) (fila_mensagens_prontas{%SELETOR%})'
  [[pergunta.campo]]
  nome = "consumidores"
  query = 'sum by (queue) (fila_consumidores{%SELETOR%})'
"""


@pytest.fixture
def catalogo_de_fila(tmp_path, monkeypatch):
    (tmp_path / "fila.toml").write_text(FAMILIA, encoding="utf-8")
    monkeypatch.setattr(catalogo, "familias", lambda pasta=tmp_path: _carregar(tmp_path))
    return tmp_path


def _carregar(pasta):
    return [catalogo.carregar_arquivo(pasta / "fila.toml")]


def _componente(base, nome="broker"):
    return {"nome": nome, "papel": "fila", "metricas_url": base}


def _identifica(falso, valores=("broker",)):
    falso.REGRAS.append(("count by (job) (fila_mensagens_prontas)",
                         _vetor([({"job": v}, 1) for v in valores])))
    falso.REGRAS.append(('count(fila_mensagens_prontas{job="broker"})', _vetor([({}, 1)])))


def test_cada_campo_e_uma_consulta_e_elas_se_juntam_pela_chave(catalogo_de_fila, prometheus):
    base, falso = prometheus
    _identifica(falso)
    falso.REGRAS.append(("sum by (queue) (fila_mensagens_prontas{job",
                         _vetor([({"queue": "emails"}, 12), ({"queue": "notas"}, 3)])))
    falso.REGRAS.append(("sum by (queue) (fila_consumidores{job",
                         _vetor([({"queue": "emails"}, 0), ({"queue": "notas"}, 2)])))

    resposta = promql.perguntar("fila.filas", _componente(base), dict(CONTEXTO))

    assert resposta["valor"] == [{"nome": "emails", "prontas": 12, "consumidores": 0},
                                 {"nome": "notas", "prontas": 3, "consumidores": 2}]


def test_fila_presente_num_campo_e_ausente_no_outro_nao_vira_zero(catalogo_de_fila, prometheus):
    """A fila existe e tem mensagens prontas; a série de consumidores não a inclui.

    Preencher com 0 produziria `fila_sem_consumidor` em cima de uma medida que ninguém fez —
    um achado alto inventado. `None` é o que o limiar sabe recusar.
    """
    base, falso = prometheus
    _identifica(falso)
    falso.REGRAS.append(("sum by (queue) (fila_mensagens_prontas{job",
                         _vetor([({"queue": "emails"}, 12)])))
    falso.REGRAS.append(("sum by (queue) (fila_consumidores{job", _vetor([])))

    resposta = promql.perguntar("fila.filas", _componente(base), dict(CONTEXTO))

    assert resposta["valor"] == [{"nome": "emails", "prontas": 12, "consumidores": None}]


def test_ordena_pelo_campo_declarado_e_desempata_pelo_nome(catalogo_de_fila, prometheus):
    base, falso = prometheus
    _identifica(falso)
    falso.REGRAS.append(("sum by (queue) (fila_mensagens_prontas{job",
                         _vetor([({"queue": "zeta"}, 5), ({"queue": "alfa"}, 5),
                                 ({"queue": "meio"}, 9)])))
    falso.REGRAS.append(("sum by (queue) (fila_consumidores{job", _vetor([])))

    resposta = promql.perguntar("fila.filas", _componente(base), dict(CONTEXTO))

    assert [i["nome"] for i in resposta["valor"]] == ["meio", "alfa", "zeta"]


def test_nenhum_campo_respondeu_e_sem_dados_nao_lista_vazia(catalogo_de_fila, prometheus):
    """Lista vazia diz "não há fila"; `sem dados` diz "não consegui ver". A primeira mentira
    sai no relatório como broker saudável."""
    base, falso = prometheus
    _identifica(falso)

    resposta = promql.perguntar("fila.filas", _componente(base), dict(CONTEXTO))

    assert resposta.get("sem_dados") is True


def test_o_valor_do_report_e_serializavel(catalogo_de_fila, prometheus):
    """`collect` grava com `allow_nan=False`: um NaN vindo de um campo aborta a gravação
    INTEIRA depois de minutos de coleta."""
    base, falso = prometheus
    _identifica(falso)
    falso.REGRAS.append(("sum by (queue) (fila_mensagens_prontas{job",
                         _vetor([({"queue": "emails"}, float("nan"))])))
    falso.REGRAS.append(("sum by (queue) (fila_consumidores{job",
                         _vetor([({"queue": "emails"}, 1)])))

    resposta = promql.perguntar("fila.filas", _componente(base), dict(CONTEXTO))

    json.dumps(resposta, allow_nan=False)
    assert resposta["valor"] == [{"nome": "emails", "prontas": None, "consumidores": 1}]


def test_serie_agregada_sem_a_etiqueta_diz_que_o_exporter_agrega(catalogo_de_fila, prometheus):
    """O exporter oficial do broker AGREGA por padrão: a série existe, sem a etiqueta `queue`.

    "Nenhuma consulta devolveu série" é falso aqui e manda o dono caçar problema de rede,
    quando o conserto é uma chave de configuração do próprio exporter.
    """
    base, falso = prometheus
    _identifica(falso)
    falso.REGRAS.append(("sum by (queue) (fila_mensagens_prontas{job", _vetor([({}, 41)])))
    falso.REGRAS.append(("sum by (queue) (fila_consumidores{job", _vetor([({}, 3)])))

    resposta = promql.perguntar("fila.filas", _componente(base), dict(CONTEXTO))

    assert resposta["sem_dados"] is True
    assert "agregada" in resposta["motivo"] and "`queue`" in resposta["motivo"]


def test_broker_com_as_duas_fontes_responde_uma_vez_so(catalogo_de_fila, prometheus):
    """Desde que a família de exporter responde `fila.filas`, DOIS adaptadores sabem a
    resposta: a API de administração e o Prometheus.

    `responder` para no primeiro que responde, e o mais específico vem antes — a API traz
    vhost e taxa, que a junção por etiqueta não tem. Sem essa parada, o componente ganharia
    duas respostas para a mesma pergunta e o relatório desenharia a mesma lista duas vezes,
    que é exatamente o defeito que fez "Filas" e "Filas com acúmulo" virarem uma pergunta.
    """
    import collect

    base, falso = prometheus
    _identifica(falso)
    falso.REGRAS.append(("sum by (queue) (fila_mensagens_prontas{job",
                         _vetor([({"queue": "emails"}, 12)])))
    falso.REGRAS.append(("sum by (queue) (fila_consumidores{job", _vetor([({"queue": "emails"}, 0)])))

    class ApiQueResponde:
        ID = "admin_http"

        def perguntar(self, pergunta, componente, contexto):
            return {"pergunta": pergunta, "fonte": "admin_http:broker",
                    "valor": [{"nome": "emails", "vhost": "/", "prontas": 12,
                               "nao_confirmadas": 0, "consumidores": 0, "acumuladas": 12}]}

    componente = dict(_componente(base), respostas=[])
    contexto = dict(CONTEXTO, cache={})
    collect.responder(componente, contexto, [ApiQueResponde(), promql], collect.Prazo(120))

    filas = [r for r in componente["respostas"] if r["pergunta"] == "fila.filas"]
    assert len(filas) == 1, filas
    assert filas[0]["fonte"].startswith("admin_http"), "a fonte mais específica tem de vencer"
