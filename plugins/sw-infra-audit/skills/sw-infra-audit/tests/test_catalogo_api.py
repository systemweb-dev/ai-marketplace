# tests/test_catalogo_api.py
"""A validação do catálogo de API acontece no CARREGAMENTO.

Erro de catálogo que só aparece na coleta vira "a API não respondeu" no relatório, e manda o
dono caçar problema de rede que não existe. E o pior tipo de erro de catálogo não levanta nada:
produz resposta errada com cara de certa. Estes testes cobrem os dois.
"""
import pytest

from lib.catalogo_api import CatalogoInvalido, carregar_arquivo, familias

BASE = """
familia = "exemplo-mgmt"
prioridade = 20

[identificacao]
caminho = "/api/overview"
exige_chaves = ["product_name"]
aceita_401 = true
"""

# `fila.filas` tem limiar na pergunta canônica: consumidores == 0 e prontas > 0
FILAS = """
[[pergunta]]
id = "fila.filas"
caminho = "/api/queues"
lista = ""
identidade = ["vhost", "nome"]
campos = { nome = "/name", vhost = "/vhost", prontas = "/messages_ready", consumidores = "/consumers" }
transformar = { prontas = "inteiro", consumidores = "inteiro" }
ordenar_por = "prontas"
ordem = "desc"
desempate = "nome"
"""


def _arquivo(tmp_path, conteudo, nome="exemplo-mgmt.toml"):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def test_carrega_arquivo_valido(tmp_path):
    dados = carregar_arquivo(_arquivo(tmp_path, BASE + FILAS))

    assert dados["familia"] == "exemplo-mgmt"
    assert dados["pergunta"][0]["id"] == "fila.filas"


def test_recusa_pergunta_que_nao_existe_no_registro(tmp_path):
    ruim = BASE + FILAS.replace('id = "fila.filas"', 'id = "fila.inventada"')

    with pytest.raises(CatalogoInvalido, match="não existe no registro"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_a_declaracao_passa_pela_validacao_da_linguagem(tmp_path):
    """`validar_declaracao` já recusa transformação desconhecida, `ordem` inválida, `limite`
    negativo, `transformar` que não casa com `campos`... O catálogo reaproveita, e o erro sai
    com o nome do arquivo e da pergunta."""
    ruim = BASE + FILAS.replace('ordem = "desc"', 'ordem = "descending"')

    with pytest.raises(CatalogoInvalido) as erro:
        carregar_arquivo(_arquivo(tmp_path, ruim))

    assert "exemplo-mgmt.toml" in str(erro.value) and "fila.filas" in str(erro.value)


# --- o caminho é por onde a credencial sai ---

@pytest.mark.parametrize("caminho", ["//outro.test/api/queues",
                                     "http://outro.test/api/queues",
                                     "/api/../../admin",
                                     "api/queues"])
def test_recusa_caminho_que_pode_sair_do_host(tmp_path, caminho):
    """`caminho` é juntado à `admin_url`, e é por ele que a CREDENCIAL sai. `//outro.test/x` é
    URL protocolo-relativa e trocaria o host inteiro."""
    ruim = BASE + FILAS.replace('caminho = "/api/queues"', f'caminho = "{caminho}"')

    with pytest.raises(CatalogoInvalido, match="caminho"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_caminho_de_identificacao_que_sai_do_host(tmp_path):
    ruim = BASE.replace('caminho = "/api/overview"', 'caminho = "//outro.test/x"') + FILAS

    with pytest.raises(CatalogoInvalido, match="caminho"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_identificacao_sem_exige_chaves(tmp_path):
    """Sem chave exigida, QUALQUER JSON de 200 vira esta família."""
    ruim = BASE.replace('exige_chaves = ["product_name"]', "") + FILAS

    with pytest.raises(CatalogoInvalido, match="exige_chaves"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


# --- as regras que vieram da revisão do batch 4 ---

def test_catalogo_nao_declara_limiar(tmp_path):
    """O limiar pertence à PERGUNTA canônica, que independe de quem responde. `responder()` só
    lê o da pergunta: um limiar aqui seria letra morta que diverge com o tempo."""
    ruim = BASE + FILAS + (
        'limiar = { quando = "prontas > 0", regra = "fila_sem_consumidor", '
        'severidade = "high" }\n')

    with pytest.raises(CatalogoInvalido, match="limiar"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_pergunta_com_limiar_nao_pode_ter_limite(tmp_path):
    """Com `limite = 10`, o limiar via só as 10 filas com mais mensagens: 300 filas órfãs atrás
    de 10 filas cheias davam 🟢 e ZERO achados. O corte para exibição é do relatório; a
    extração entrega a população inteira."""
    ruim = BASE + FILAS + "limite = 10\n"

    with pytest.raises(CatalogoInvalido, match="limite"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_pergunta_sem_limiar_pode_ter_limite(tmp_path):
    ok = BASE + """
[[pergunta]]
id = "fila.consumidores_por_fila"
caminho = "/api/queues"
lista = ""
campos = { nome = "/name", consumidores = "/consumers" }
transformar = { consumidores = "inteiro" }
ordenar_por = "consumidores"
ordem = "desc"
desempate = "nome"
limite = 10
"""

    assert carregar_arquivo(_arquivo(tmp_path, ok))["pergunta"][0]["limite"] == 10


def test_catalogo_precisa_extrair_os_campos_do_limiar(tmp_path):
    """O nome do campo é contrato: se o catálogo não extrai `consumidores`, o campo vira None,
    o limiar nunca dispara, e a regra fica morta para sempre, sem sinal nenhum."""
    ruim = BASE + """
[[pergunta]]
id = "fila.filas"
caminho = "/api/queues"
lista = ""
campos = { nome = "/name", prontas = "/messages_ready" }
transformar = { prontas = "inteiro" }
ordenar_por = "prontas"
ordem = "desc"
desempate = "nome"
"""

    with pytest.raises(CatalogoInvalido, match="consumidores"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_identidade_so_com_campos_extraidos(tmp_path):
    ruim = BASE + FILAS.replace('identidade = ["vhost", "nome"]', 'identidade = ["vhost", "cor"]')

    with pytest.raises(CatalogoInvalido, match="identidade"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_identidade_nao_pode_ser_texto_solto(tmp_path):
    """`identidade = "nome"` viraria lista de caracteres em Python."""
    ruim = BASE + FILAS.replace('identidade = ["vhost", "nome"]', 'identidade = "nome"')

    with pytest.raises(CatalogoInvalido, match="identidade"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_chave_desconhecida_na_pergunta_e_recusada(tmp_path):
    """Chave fora da linguagem é erro de digitação ou tentativa de estendê-la em silêncio —
    `filtro = "..."` passaria calado e o autor acharia que filtrou."""
    ruim = BASE + FILAS + 'filtro = "nome ~ dlq"\n'

    with pytest.raises(CatalogoInvalido, match="filtro"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_familias_vem_em_ordem_estavel(tmp_path):
    _arquivo(tmp_path, BASE + FILAS, "zulu.toml")
    _arquivo(tmp_path, BASE.replace("exemplo-mgmt", "alfa-mgmt") + FILAS, "alfa.toml")

    assert [f["familia"] for f in familias(tmp_path)] == ["alfa-mgmt", "exemplo-mgmt"]


def test_toml_invalido_diz_o_arquivo(tmp_path):
    with pytest.raises(CatalogoInvalido, match="exemplo-mgmt.toml"):
        carregar_arquivo(_arquivo(tmp_path, "familia = "))


def test_pergunta_escalar_precisa_extrair_o_campo_valor(tmp_path, monkeypatch):
    """Escalar é UM número. O catálogo diz de onde ele vem num campo chamado `valor`, e não
    pode declarar `lista`."""
    from lib import perguntas

    monkeypatch.setitem(perguntas.PERGUNTAS, "fila.total_de_teste",
                        {"id": "fila.total_de_teste", "papel": "fila", "titulo": "Total",
                         "forma": "escalar", "unidade": None, "limiar": None,
                         "desempate": None, "faixa": None})
    ruim = BASE + """
[[pergunta]]
id = "fila.total_de_teste"
caminho = "/api/overview"
campos = { total = "/total" }
"""

    with pytest.raises(CatalogoInvalido, match="valor"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_limiar_com_literal_entre_aspas_nao_inventa_campo(tmp_path, monkeypatch):
    """`nome == 'x > 1'` tem um `x` DENTRO das aspas. Lido cru, ele virava campo exigido e o
    catálogo legítimo era recusado."""
    from lib import perguntas

    monkeypatch.setitem(perguntas.PERGUNTAS["fila.filas"], "limiar",
                        {"quando": "nome == 'x > 1' e prontas > 0",
                         "regra": "fila_sem_consumidor"})

    assert carregar_arquivo(_arquivo(tmp_path, BASE + FILAS))["familia"] == "exemplo-mgmt"
