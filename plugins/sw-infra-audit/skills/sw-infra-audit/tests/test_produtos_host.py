import pytest

from lib import produtos


def test_mariadb_casa_por_processo_e_por_unidade():
    assert produtos.por_processo("mariadbd")["nome"] == "mariadb"
    assert produtos.por_unidade("mariadb.service")["nome"] == "mariadb"
    assert produtos.por_unidade("postgresql@15-main.service")["nome"] == "postgres"


def test_qdrant_e_produto_de_busca():
    qdrant = produtos.por_processo("qdrant")
    assert qdrant["nome"] == "qdrant" and qdrant["kind"] == "busca"


def test_processo_desconhecido_nao_casa():
    assert produtos.por_processo("meu-binario") is None


def test_produto_so_com_processo_carrega(tmp_path):
    caminho = tmp_path / "p.toml"
    caminho.write_text('[[produto]]\nnome = "x"\nprocesso = ["xd"]\nkind = "banco"\n', encoding="utf-8")
    assert produtos.carregar(caminho)[0]["nome"] == "x"


def test_processo_com_mais_de_15_caracteres_e_recusado(tmp_path):
    caminho = tmp_path / "p.toml"
    caminho.write_text('[[produto]]\nnome = "x"\nprocesso = ["nome-longo-demais-1"]\n', encoding="utf-8")
    with pytest.raises(produtos.ProdutosInvalidos, match="15"):
        produtos.carregar(caminho)


def test_produto_sem_nenhum_sinal_e_recusado(tmp_path):
    caminho = tmp_path / "p.toml"
    caminho.write_text('[[produto]]\nnome = "x"\nkind = "banco"\n', encoding="utf-8")
    with pytest.raises(produtos.ProdutosInvalidos):
        produtos.carregar(caminho)
