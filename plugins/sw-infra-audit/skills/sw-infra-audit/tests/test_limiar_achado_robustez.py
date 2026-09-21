# tests/test_limiar_achado_robustez.py
"""O que a ponte entre limiar e achado precisa aguentar.

A revisão do batch mostrou que a ponte funcionava no caminho feliz e tinha sete formas de
mentir ou de derrubar a auditoria. Cada teste aqui corresponde a uma delas.
"""
import pytest

from collect import achados_da_resposta, agravar_saude


def _resposta(valor, **extra):
    return dict({"pergunta": "fila.filas", "fonte": "admin_http:amqp-mgmt",
                 "valor": valor}, **extra)


# `OPS_NODE_DOWN` é uma regra que JÁ existe no registro (severidade padrão `high`). A regra do
# papel `fila` só entra na Task 8, e um teste desta task não pode depender da seguinte.
CRUZA = {"quando": "consumidores == 0 e prontas > 0", "regra": "OPS_NODE_DOWN",
         "severidade": "high"}
UM_ITEM = [{"nome": "emails", "prontas": 7, "consumidores": 0}]


# --- 1. a saúde do alvo precisa enxergar o achado novo ---

@pytest.mark.parametrize("severidade, esperada", [
    ("critical", "🔴"), ("high", "🔴"), ("medium", "🟡"), ("low", "🟢"), ("info", "🟢"),
])
def test_achado_de_limiar_agrava_a_saude_do_alvo(severidade, esperada):
    """`saude` vinha do coletor e era gravada ANTES de as perguntas serem feitas. O painel
    anunciava "1 alvo 🟢 · 1 achado" com um achado crítico aberto — e o estado é o único
    número que o leitor bate o olho."""
    registro = {"saude": "🟢", "achados": [{"regra": "fila_sem_consumidor", "severidade": severidade}]}

    agravar_saude(registro)

    assert registro["saude"] == esperada


def test_agravar_nunca_melhora_a_saude():
    """Um achado `medium` propõe 🟡. Num alvo que o coletor já deu como 🔴, isso não pode
    rebaixar o estado para 🟡 — o achado novo se soma ao quadro, não o substitui.

    O `low` não serve para provar isto: ele não propõe estado nenhum, então a comparação de
    gravidade nem chega a ser exercida e a mutação sobrevive.
    """
    registro = {"saude": "🔴", "achados": [{"regra": "fila_sem_consumidor", "severidade": "medium"}]}

    agravar_saude(registro)

    assert registro["saude"] == "🔴"


def test_achado_de_baixa_severidade_nao_muda_nada():
    registro = {"saude": "🟢", "achados": [{"regra": "fila_sem_consumidor", "severidade": "low"}]}

    agravar_saude(registro)

    assert registro["saude"] == "🟢"


def test_o_pior_achado_e_quem_manda():
    """Vários achados: vale o mais grave, não o último da lista."""
    registro = {"saude": "🟢", "achados": [{"regra": "fila_sem_consumidor", "severidade": "critical"},
                                          {"regra": "fila_sem_consumidor", "severidade": "low"}]}

    agravar_saude(registro)

    assert registro["saude"] == "🔴"


def test_alvo_sem_achado_mantem_o_que_o_coletor_disse():
    registro = {"saude": "🟡", "achados": []}

    agravar_saude(registro)

    assert registro["saude"] == "🟡"


def test_achado_que_nao_nasce_de_limiar_nao_agrava():
    """A nota do coletor já leva os achados dele em conta."""
    registro = {"saude": "🟡", "achados": [{"regra": "SEC_PRIVILEGED", "severidade": "high"}]}

    agravar_saude(registro)

    assert registro["saude"] == "🟡"


def test_sem_dados_nao_vira_verde_por_agravamento():
    """"Sem dados" não é um estado bom a ser preservado nem um ruim a ser agravado: é a
    ausência de leitura, e continua sendo até alguém ler alguma coisa."""
    registro = {"saude": "sem dados", "achados": []}

    agravar_saude(registro)

    assert registro["saude"] == "sem dados"


# --- 2. limiar malformado não pode matar a auditoria ---

@pytest.mark.parametrize("limiar", ["prontas > 0", ["prontas > 0"], 7, True])
def test_limiar_que_nao_e_dicionario_nao_derruba_a_coleta(limiar):
    """`limiar = "prontas > 0"` (a expressão no lugar do dicionário) é erro de autoria
    plausível, e estourava `AttributeError` que subia até matar a auditoria inteira: sem
    report.json, sem inventário, sem nada."""
    assert achados_da_resposta(_resposta(UM_ITEM), limiar, componente="broker") == []


def test_resposta_que_nao_e_dicionario_nao_derruba_a_coleta():
    assert achados_da_resposta("não sou resposta", CRUZA, componente="broker") == []


# --- 3 e 4. a regra precisa existir no registro ---

def test_regra_fora_do_registro_nao_vira_achado():
    """Achado com regra desconhecida entra sem remediação, com severidade `info`, e o
    relatório desenha o id cru como título. Melhor não nascer."""
    desconhecida = dict(CRUZA, regra="regra_que_ninguem_registrou")

    assert achados_da_resposta(_resposta(UM_ITEM), desconhecida, componente="broker") == []


def test_regra_com_travessia_de_caminho_nao_vira_achado():
    """`regra` vira `references/remediacao/<regra>.md`. Com `../../SKILL`, a leitura saía da
    pasta e a exceção subia até matar a auditoria."""
    travessia = dict(CRUZA, regra="../../SKILL")

    assert achados_da_resposta(_resposta(UM_ITEM), travessia, componente="broker") == []


# --- 5. severidade validada ---

@pytest.mark.parametrize("severidade", ["alta", "GRAVÍSSIMO", "", {"x": 1}, 3])
def test_severidade_invalida_cai_no_padrao_da_regra(severidade):
    """`alta` é o erro natural num catálogo em português. Cru, chegava ao HTML como
    `class="grp alta"`: badge vazia, sem cor, e o grupo jogado para o fim da lista."""
    resposta = _resposta(UM_ITEM)

    achados = achados_da_resposta(resposta, dict(CRUZA, severidade=severidade),
                                  componente="broker")

    assert achados[0]["severidade"] == "high"     # a padrão de OPS_NODE_DOWN


# --- 6. detalhe não pode despejar segredo nem texto sem fim ---

def test_detalhe_e_higienizado():
    """O único caminho de texto de adaptador que não passava por `lib/redact.py`."""
    resposta = _resposta([{"nome": "a", "prontas": 2, "consumidores": 0,
                           "url": "amqp://admin:S3nh4Sup3r@203.0.113.5:5672/"}])

    achados = achados_da_resposta(resposta, CRUZA, componente="broker")

    assert "S3nh4Sup3r" not in achados[0]["detalhe"]


def test_detalhe_tem_teto_de_tamanho():
    resposta = _resposta([{"nome": "a", "prontas": 2, "consumidores": 0,
                           "lixo": "x" * 5000}])

    achados = achados_da_resposta(resposta, CRUZA, componente="broker")

    assert len(achados[0]["detalhe"]) <= 400


# --- 8. contrato com o adaptador que já existe ---

def test_objeto_usa_chave_quando_o_item_vem_do_promql():
    """`promql.perguntar` monta itens de lista com `chave`, nunca com `nome`. Sem este
    fallback, TODO achado de lista vindo dele teria o nome do componente como objeto — e o
    relatório mostraria N linhas indistinguíveis."""
    resposta = _resposta([{"chave": "500", "valor": 900}])
    limiar = {"quando": "valor > 100", "regra": "OPS_NODE_DOWN"}

    achados = achados_da_resposta(resposta, limiar, componente="proxy")

    assert achados[0]["objeto"] == "500"


def test_nome_que_nao_e_texto_nao_vai_cru_para_o_objeto():
    resposta = _resposta([{"nome": {"a": 1}, "prontas": 2, "consumidores": 0}])

    achados = achados_da_resposta(resposta, CRUZA, componente="broker")

    assert achados[0]["objeto"] == "broker"


def test_objeto_explicito_do_item_tem_precedencia():
    """Filas de mesmo nome em vhosts diferentes (`emails` em `/` e em `staging`) viravam dois
    achados com o mesmo objeto: no histórico, colapsavam numa chave só, e consertar um deles
    não aparecia como resolvido. O adaptador compõe um `objeto` que distingue os dois
    (`/ · emails`), e a ponte usa esse campo antes de `nome`."""
    resposta = _resposta([{"objeto": "staging · emails", "nome": "emails", "prontas": 3,
                           "consumidores": 0}])

    achados = achados_da_resposta(resposta, CRUZA, componente="broker")

    assert achados[0]["objeto"] == "staging · emails"
    assert "staging" not in achados[0]["detalhe"], "o objeto não se repete no detalhe"


def test_detalhe_nao_repete_o_que_ja_esta_na_identidade():
    """`orfa-000@staging` já diz o vhost; `vhost: staging` no detalhe repetia isso em cada uma
    das 300 linhas. O filtro é pelos NOMES de campo que a resposta declara como identidade."""
    resposta = _resposta([{"objeto": "orfa-000@staging", "nome": "orfa-000",
                           "vhost": "staging", "prontas": 3, "consumidores": 0}],
                         identidade=["nome", "vhost"])

    detalhe = achados_da_resposta(resposta, CRUZA, componente="broker")[0]["detalhe"]

    assert "staging" not in detalhe
    assert "prontas: 3" in detalhe and "consumidores: 0" in detalhe
