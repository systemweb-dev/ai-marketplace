"""O que a skill sabe por nome de imagem, agora num arquivo e não em três listas de código.

O teste que importa é o de EQUIVALÊNCIA: a classificação de cada produto conhecido fica fixada
aqui, para que reordenar os blocos do arquivo — o que decide o empate no casamento por trecho —
não mude o inventário em silêncio. Papel errado não é detalhe cosmético: é perguntar de fila
para um banco, e sair `sem dados` sem ninguém entender por quê.
"""
import pytest

from lib import produtos

# A classificação que vigorava quando as tabelas moravam no código. Mudar uma linha daqui é
# mudar como um cluster real é lido — tem de ser deliberado, com o diff à vista.
CLASSIFICACAO = {
    "traefik": "ingress/proxy", "nginx": "proxy", "haproxy": "proxy", "envoy": "proxy",
    "caddy": "proxy", "kong": "api-gateway",
    "rabbitmq": "fila", "kafka": "fila/broker", "nats": "fila/broker",
    "redis": "cache/fila", "memcached": "cache",
    "postgres": "banco", "mysql": "banco", "mariadb": "banco", "mongo": "banco",
    "elasticsearch": "busca", "opensearch": "busca",
    "prometheus": "observabilidade", "grafana": "observabilidade", "loki": "observabilidade",
    "minio": "object-storage",
}

SOCKET_ESPERADO = ("cadvisor", "promtail", "node-exporter", "node_exporter", "portainer",
                   "traefik", "watchtower", "autoheal", "socket-proxy", "prune", "logspout",
                   "dockerd-exporter", "swarm-cronjob", "shepherd", "diun")


@pytest.mark.parametrize("trecho,kind", sorted(CLASSIFICACAO.items()))
def test_cada_produto_conhecido_continua_classificado_igual(trecho, kind):
    assert produtos.kind_do_caminho(f"registry.exemplo/{trecho}:1.2") == kind


@pytest.mark.parametrize("trecho", SOCKET_ESPERADO)
def test_quem_monta_o_socket_por_desenho_continua_na_lista(trecho):
    assert produtos.socket_esperado(f"org/{trecho}:latest") is True


def test_imagem_desconhecida_nao_ganha_kind():
    assert produtos.kind_do_caminho("registry.exemplo/minha-api:4.2") is None
    assert produtos.socket_esperado("registry.exemplo/minha-api:4.2") is False


def test_a_tag_nunca_decide_um_tipo_com_estado():
    """`umami:postgresql-latest` é o umami que FALA com Postgres. Classificá-lo como banco o
    punha em `metrics.STATEFUL`, e ele saía no relatório como ponto único de falha com
    estado — um risco inventado."""
    com_estado = {"fila", "fila/broker", "banco", "cache", "cache/fila", "busca",
                  "object-storage"}

    assert produtos.kind_da_tag("postgresql", com_estado) is None
    assert produtos.kind_da_tag("postgres", com_estado) is None
    assert produtos.kind_da_tag("prometheus", com_estado) == "observabilidade"


# ---------------------------------------------------------------- o arquivo é recusado quando mente
def test_trecho_em_maiuscula_e_recusado(tmp_path):
    """O casamento é feito sobre o caminho JÁ em minúsculas: um trecho com maiúscula nunca
    casaria, e o produto ficaria invisível sem nenhum erro."""
    arquivo = tmp_path / "p.toml"
    arquivo.write_text('[[produto]]\nnome = "x"\nimagem = ["Traefik"]\n', encoding="utf-8")

    with pytest.raises(produtos.ProdutosInvalidos, match="minúsculo"):
        produtos.carregar(arquivo)


def test_produto_repetido_e_recusado(tmp_path):
    arquivo = tmp_path / "p.toml"
    arquivo.write_text('[[produto]]\nnome = "x"\nimagem = ["a"]\n'
                       '[[produto]]\nnome = "x"\nimagem = ["b"]\n', encoding="utf-8")

    with pytest.raises(produtos.ProdutosInvalidos, match="duas vezes"):
        produtos.carregar(arquivo)


def test_fonte_de_metrica_incompleta_e_recusada(tmp_path):
    """Proposta sem porta ou sem o que ela entrega não dá para testar nem para explicar a
    quem recebe a sugestão."""
    arquivo = tmp_path / "p.toml"
    arquivo.write_text('[[produto]]\nnome = "x"\nimagem = ["a"]\n'
                       '[produto.metricas]\nfamilia = "f"\nporta = 1\n', encoding="utf-8")

    with pytest.raises(produtos.ProdutosInvalidos, match="caminho"):
        produtos.carregar(arquivo)


def test_todo_papel_derivado_existe():
    """O `kind` do arquivo alimenta `papel.POR_KIND`. Um `kind` que ninguém traduz vira `app`
    em silêncio, e o componente recebe as perguntas erradas."""
    from lib.papel import POR_KIND

    declarados = {p["kind"] for p in produtos.carregar() if p.get("kind")}

    assert not declarados - set(POR_KIND), sorted(declarados - set(POR_KIND))


# ---------------------------------------------------------------- D4: quem só observa
EXPORTADORES = ("cadvisor", "node-exporter", "node_exporter", "promtail",
                "dockerd-exporter",
                # os três que D4 existe para travar, e que não existiam no arquivo
                "postgres-exporter", "mysqld-exporter", "redis-exporter")


@pytest.mark.parametrize("trecho", EXPORTADORES)
def test_exportador_e_reconhecido_como_tal(trecho):
    """Estes produtos OBSERVAM outros; o papel deles nunca pode ser provado pela série que
    eles publicam, porque a série é do observado, não deles."""
    assert produtos.e_exportador(f"org/{trecho}:latest") is True


def test_produto_normal_nao_e_exportador():
    assert produtos.e_exportador("registry.exemplo/postgres:16") is False
    assert produtos.e_exportador("registry.exemplo/minha-api:4.2") is False


# (trecho do exporter, trecho do produto que ele observa, kind do produto)
PARES_DE_PREFIXO = [
    ("postgres-exporter", "postgres", "banco"),
    ("postgresql-exporter", "postgres", "banco"),
    ("mysqld-exporter", "mysql", "banco"),
    ("mysql-exporter", "mysql", "banco"),
    ("redis-exporter", "redis", "cache/fila"),
]


@pytest.mark.parametrize("exportador,produto,kind", PARES_DE_PREFIXO)
def test_o_exportador_nao_rouba_o_kind_do_produto_que_observa(exportador, produto, kind):
    """O casamento é por trecho e o primeiro bloco que casa vence. Com o bloco do exporter
    DEPOIS do bloco do produto, o exporter herda o `kind` dele e entra no inventário como se
    fosse o produto — alimentando `metrics.STATEFUL` e `impact.CRITICAL_PATH`.

    Parametrizado nos três pares, e não só em `postgres`: o teste cobria um caso e o comentário
    do arquivo prometia três, então mover `mysqld-exporter` ou `redis-exporter` para o fim do
    arquivo reintroduzia o defeito com a suíte verde.
    """
    assert produtos.kind_do_caminho(f"org/{exportador}:1") is None
    assert produtos.e_exportador(f"org/{exportador}:1") is True
    assert produtos.kind_do_caminho(f"org/{produto}:16") == kind


def test_exportador_fora_do_arquivo_e_recusado(tmp_path):
    """`exportador` tem de ser booleano: um `exportador = "sim"` passaria como verdadeiro e
    silenciaria o papel de um produto inteiro sem ninguém notar."""
    arquivo = tmp_path / "p.toml"
    arquivo.write_text('[[produto]]\nnome = "x"\nimagem = ["a"]\nexportador = "sim"\n',
                       encoding="utf-8")

    with pytest.raises(produtos.ProdutosInvalidos, match="exportador"):
        produtos.carregar(arquivo)
