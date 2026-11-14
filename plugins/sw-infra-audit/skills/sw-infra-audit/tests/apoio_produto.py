"""Catálogos de produto de mentira numa pasta temporária.

Os testes não dependem dos catálogos de verdade de `references/produtos-host/` (Task 11): `gravar`
aponta o carregador para a pasta do teste e registra uma pergunta de LISTA temporária, para o caminho
de `enumerar` ter o que responder sem amarrar o teste a uma pergunta real.
"""
from lib import catalogo_produto, perguntas

PERGUNTA_DE_LISTA = "busca.teste_colecoes"

MARIADB = """produto = "mariadb"

[cliente]
socket = 'mariadb -N -B -e "{sql}"'
senha = 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
container = 'docker exec {container} mariadb -N -B -e "{sql}"'

[[erro]]
contem = "ERROR 1698"
motivo = 'o root não entra pelo socket: declare leitura = "senha" com um usuário de leitura'

[[erro]]
contem = "ERROR 1045"
modo = "senha"
motivo = "o banco recusou o usuário e a senha declarados"

[[erro]]
contem = "You are not using binary logging"
motivo = "o binlog está desligado neste servidor"
nao_publica = true

[[pergunta]]
id = "banco.conexoes"
sql = "SHOW GLOBAL STATUS"
formato = "chave_valor"
campos = { valor = "/Threads_connected" }
transformar = { valor = "inteiro" }

[[pergunta]]
id = "banco.tamanho"
sql = "SELECT SUM(data_length + index_length) FROM information_schema.tables"
formato = "tsv"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }
transformar = { valor = "bytes" }
"""

QDRANT = """produto = "qdrant"
porta_padrao = 6333

[cliente]
socket = 'curl -s -f -m 5 "http://127.0.0.1:{porta}{sql}"'

[[erro]]
codigo = 22
motivo = "o Qdrant recusou a leitura (pede chave de API?)"

[[pergunta]]
id = "busca.teste_colecoes"
formato = "json"
enumerar = { sql = "/collections", lista = "/result/collections", campo = "name" }
sql = "/collections/{colecao}"
lista = "/itens"
campos = { nome = "/nome", pontos = "/resposta/result/points_count" }
transformar = { nome = "texto", pontos = "inteiro" }
ordenar_por = "pontos"
desempate = "nome"
"""


def gravar(tmp_path, monkeypatch, **catalogos):
    """Grava `<produto>.toml` numa pasta temporária e aponta o carregador para ela."""
    pasta = tmp_path / "produtos-host"
    pasta.mkdir(exist_ok=True)
    for produto, texto in catalogos.items():
        (pasta / f"{produto}.toml").write_text(texto, encoding="utf-8")
    monkeypatch.setattr(catalogo_produto, "PASTA", pasta)
    monkeypatch.setitem(perguntas.PERGUNTAS, PERGUNTA_DE_LISTA, {
        "id": PERGUNTA_DE_LISTA, "papel": "busca", "titulo": "Coleções de teste", "forma": "lista",
        "unidade": "pontos", "limiar": None, "desempate": "nome", "faixa": None, "opcional": True,
        "por_ultimo": False})
    return pasta
