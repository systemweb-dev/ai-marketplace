"""Nome de produto vive em arquivo de dados, nunca no código.

A skill promete, em `SKILL.md` e em `lib/catalogo.py`, que acrescentar um produto é escrever um
arquivo e que não há `if produto ==` no código. Isso era verdade do caminho de MÉTRICA e
mentira do resto: três tabelas chaveadas por nome de imagem moravam no código — o `kind` do
serviço (`coletores/docker.py`), quem monta o `docker.sock` por desenho (`rules.py`) e os
candidatos a fonte de métrica do `--sugerir` (`discover.py`). Acrescentar um produto exigia
editar três listas em dois arquivos, e quem não soubesse disso acrescentava uma.

Esta trava lê o CÓDIGO, não os arquivos de dados. Comentário e docstring estão liberados: o
`promql.py` precisa poder explicar por que não olha o nome da imagem, e o arquivo de família
do Traefik precisa poder se chamar Traefik.
"""
import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "scripts"

# Produtos que a skill reconhece. Qualquer um deles escrito num literal de string do código é
# conhecimento de produto fora do lugar.
PRODUTOS = ("traefik", "nginx", "haproxy", "envoy", "caddy", "kong", "rabbitmq", "kafka",
            "nats", "redis", "memcached", "postgres", "mysql", "mariadb", "mongo",
            "elasticsearch", "opensearch", "grafana", "loki", "minio", "cadvisor",
            "promtail", "portainer", "watchtower", "autoheal", "logspout", "shepherd", "diun")

# `prometheus` fica de fora da lista: aqui ele é o nome do PROTOCOLO de consulta (`promql`,
# `/api/v1/query`), não um produto entre outros — o adaptador inteiro é construído sobre ele.

LIBERADOS = {
    # Mensagem de ajuda que NOMEIA os tipos de alvo ainda não suportados. Dizer "banco chega
    # no plano 2" sem dizer quais seria pior para quem lê o erro.
    ("lib/alvos.py", "postgres"), ("lib/alvos.py", "mysql"), ("lib/alvos.py", "mariadb"),
}


def _literais(caminho):
    """Toda string literal do módulo — docstring e comentário ficam de fora por construção."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    docstrings = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = getattr(no, "body", None)
            if corpo and isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
                docstrings.add(id(corpo[0].value))
    return [no.value for no in ast.walk(arvore)
            if isinstance(no, ast.Constant) and isinstance(no.value, str)
            and id(no) not in docstrings]


def test_nenhum_nome_de_produto_em_literal_de_codigo():
    """Só literais SEM ESPAÇO contam.

    Um nome de produto no meio de uma frase é prosa dirigida a quem lê o relatório — a ficha de
    uma regra precisa poder dizer "monta o docker.sock, é assim que a ferramenta funciona". O
    que não pode é o nome ser um VALOR: chave de tabela, item de tupla, trecho de casamento.
    Esses não têm espaço, e é essa a linha.
    """
    achados = []
    for caminho in sorted(RAIZ.rglob("*.py")):
        rel = str(caminho.relative_to(RAIZ))
        for texto in _literais(caminho):
            baixo = texto.lower()
            if any(c.isspace() for c in baixo):
                continue
            for produto in PRODUTOS:
                if produto in baixo and (rel, produto) not in LIBERADOS:
                    achados.append(f"{rel}: {produto!r} em {texto[:60]!r}")

    assert not achados, ("conhecimento de produto voltou para o código — ele vive em "
                         "`references/produtos.toml` (nome de imagem), `references/metricas/` "
                         "(série de exporter) e `references/apis/` (API de administração):\n  "
                         + "\n  ".join(sorted(set(achados))))
