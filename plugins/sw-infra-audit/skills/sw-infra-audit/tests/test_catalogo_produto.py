import pytest

from apoio_produto import MARIADB, QDRANT, gravar
from lib import catalogo_produto as cp

CLIENTE = """[cliente]
socket = 'mariadb -N -B -e "{sql}"'
"""
PERGUNTA = """[[pergunta]]
id = "banco.conexoes"
sql = {sql}
formato = "chave_valor"
campos = {{ valor = "/Threads_connected" }}
transformar = {{ valor = "inteiro" }}
"""


def _arquivo(tmp_path, cliente=CLIENTE, sql='"SHOW GLOBAL STATUS"', produto="mariadb", nome=None,
             pergunta=None):
    caminho = tmp_path / f"{nome or produto}.toml"
    corpo = pergunta if pergunta is not None else PERGUNTA.format(sql=sql)
    caminho.write_text(f'produto = "{produto}"\n{cliente}{corpo}', encoding="utf-8")
    return caminho


def test_catalogo_carrega_com_a_extracao_separada(tmp_path, monkeypatch):
    pasta = gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    catalogo = cp.carregar_arquivo(pasta / "mariadb.toml")
    conexoes = catalogo["pergunta"][0]
    assert conexoes["sql"] == ["SHOW GLOBAL STATUS"] and conexoes["formato"] == "chave_valor"
    assert conexoes["extracao"] == {"campos": {"valor": "/Threads_connected"},
                                    "transformar": {"valor": "inteiro"}}
    assert set(catalogo["cliente"]) == {"socket", "senha", "container"}


def test_enumerar_carrega_com_json_e_vaga_colecao(tmp_path, monkeypatch):
    pasta = gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    pergunta = cp.carregar_arquivo(pasta / "qdrant.toml")["pergunta"][0]
    assert pergunta["enumerar"] == {"sql": "/collections", "lista": "/result/collections",
                                    "campo": "name"}


@pytest.mark.parametrize("sql", ["'SELECT $HOME'", "'SELECT `id`'", "'SELECT 1 % 2'",
                                 "'SELECT 1 > 0'", "'SELECT 1 < 0'", "'SELECT \"a\"'",
                                 "'SELECT \\N'", '"SELECT 1\\nSELECT 2"'])
def test_consulta_com_caractere_proibido_e_recusada(tmp_path, sql):
    with pytest.raises(cp.CatalogoInvalido, match="caractere proibido"):
        cp.carregar_arquivo(_arquivo(tmp_path, sql=sql))


def test_vaga_sql_fora_das_aspas_e_recusada(tmp_path):
    cliente = "[cliente]\nsocket = 'redis-cli {sql}'\n"
    with pytest.raises(cp.CatalogoInvalido, match="dentro de aspas duplas"):
        cp.carregar_arquivo(_arquivo(tmp_path, cliente=cliente))


def test_vaga_container_fora_do_modo_container_e_recusada(tmp_path):
    cliente = "[cliente]\nsocket = 'docker exec {container} mariadb -e \"{sql}\"'\n"
    with pytest.raises(cp.CatalogoInvalido, match="que este modo não preenche"):
        cp.carregar_arquivo(_arquivo(tmp_path, cliente=cliente))


def test_cliente_com_encadeamento_e_recusado(tmp_path):
    cliente = "[cliente]\nsocket = 'mariadb -e \"{sql}\" | cat'\n"
    with pytest.raises(cp.CatalogoInvalido, match="cliente 'socket' tem"):
        cp.carregar_arquivo(_arquivo(tmp_path, cliente=cliente))


def test_modo_desconhecido_e_recusado(tmp_path):
    cliente = "[cliente]\nsudo = 'mariadb -e \"{sql}\"'\n"
    with pytest.raises(cp.CatalogoInvalido, match="modo de leitura 'sudo' não existe"):
        cp.carregar_arquivo(_arquivo(tmp_path, cliente=cliente))


def test_pergunta_fora_do_registro_e_recusada(tmp_path):
    pergunta = PERGUNTA.format(sql='"SHOW GLOBAL STATUS"').replace("banco.conexoes", "banco.inventada")
    with pytest.raises(cp.CatalogoInvalido, match="não existe no registro"):
        cp.carregar_arquivo(_arquivo(tmp_path, pergunta=pergunta))


def test_escalar_sem_campo_valor_e_recusado(tmp_path):
    pergunta = PERGUNTA.format(sql='"SHOW GLOBAL STATUS"').replace("{ valor", "{ total")
    with pytest.raises(cp.CatalogoInvalido, match="é escalar"):
        cp.carregar_arquivo(_arquivo(tmp_path, pergunta=pergunta))


def test_varias_consultas_so_em_chave_valor(tmp_path):
    pergunta = ('[[pergunta]]\nid = "banco.tamanho"\nsql = ["SELECT 1", "SELECT 2"]\n'
                'formato = "tsv"\ncolunas = ["valor"]\ncampos = { valor = "/linhas/0/valor" }\n')
    with pytest.raises(cp.CatalogoInvalido, match="só `chave_valor` sabe juntar"):
        cp.carregar_arquivo(_arquivo(tmp_path, pergunta=pergunta))


def test_produto_fora_de_produtos_toml_e_recusado(tmp_path):
    with pytest.raises(cp.CatalogoInvalido, match="não está em references/produtos.toml"):
        cp.carregar_arquivo(_arquivo(tmp_path, produto="inventado"))


def test_nome_do_arquivo_precisa_ser_o_produto(tmp_path):
    with pytest.raises(cp.CatalogoInvalido, match="precisa ser o nome do arquivo"):
        cp.carregar_arquivo(_arquivo(tmp_path, produto="mysql", nome="mariadb"))


def test_enumerar_sem_vaga_colecao_e_recusado(tmp_path, monkeypatch):
    texto = QDRANT.replace('sql = "/collections/{colecao}"', 'sql = "/collections/docs"')
    pasta = gravar(tmp_path, monkeypatch, qdrant=texto)
    with pytest.raises(cp.CatalogoInvalido, match="usa a vaga {colecao}"):
        cp.carregar_arquivo(pasta / "qdrant.toml")


def test_do_produto_sem_arquivo_ou_com_nome_estranho_e_none(tmp_path):
    assert cp.do_produto("mongo", pasta=tmp_path) is None
    assert cp.do_produto("../etc/passwd", pasta=tmp_path) is None
    assert cp.do_produto(None, pasta=tmp_path) is None


def test_todos_le_a_pasta_inteira_em_ordem(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT, mariadb=MARIADB)
    assert [c["produto"] for c in cp.todos()] == ["mariadb", "qdrant"]
