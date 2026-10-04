"""O que a skill sabe por NOME DE IMAGEM — carregado de `references/produtos.toml`.

Três tabelas viviam no código, as três chaveadas por imagem: o `kind` do serviço, quem monta o
`docker.sock` por desenho, e os candidatos a fonte de métrica do `--sugerir`. Um produto é uma
coisa; acrescentar um passou a ser escrever um bloco, não editar três listas em dois arquivos.

Isto NÃO substitui o catálogo de métrica, que identifica a família pela série que EXISTE
justamente porque nome de imagem mente. Aqui o nome é o único sinal disponível: antes de falar
com qualquer fonte, a skill precisa saber que perguntas fazer, e isso vem do papel, que vem do
`kind`. É o elo fraco reconhecido — e por isso o `alvos.toml` sempre vence.
"""
import tomllib
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent.parent / "references" / "produtos.toml"


class ProdutosInvalidos(Exception):
    """Arquivo de produtos que a skill se recusa a interpretar."""


def _validar(produto, onde):
    for obrigatorio in ("nome", "imagem"):
        if not produto.get(obrigatorio):
            raise ProdutosInvalidos(f"{onde}: produto sem {obrigatorio!r}")
    if not isinstance(produto["imagem"], list):
        raise ProdutosInvalidos(f"{onde}: `imagem` de {produto['nome']!r} precisa ser lista de "
                                f"trechos, mesmo com um só")
    for trecho in produto["imagem"]:
        if not isinstance(trecho, str) or not trecho or trecho != trecho.lower():
            raise ProdutosInvalidos(f"{onde}: trecho {trecho!r} de {produto['nome']!r} precisa "
                                    f"ser texto minúsculo e não vazio — o casamento é feito "
                                    f"sobre o caminho da imagem já em minúsculas")
    metricas = produto.get("metricas")
    if metricas is not None:
        for obrigatorio in ("familia", "porta", "caminho", "prioridade", "entrega"):
            if obrigatorio not in metricas:
                raise ProdutosInvalidos(f"{onde}: `[produto.metricas]` de {produto['nome']!r} "
                                        f"sem {obrigatorio!r} — proposta de fonte sem isso não "
                                        f"dá para testar nem para explicar a quem recebe")
    return produto


def carregar(caminho=None):
    """Os produtos, NA ORDEM DO ARQUIVO — é ela que decide o empate no casamento."""
    caminho = Path(caminho or ARQUIVO)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise ProdutosInvalidos(f"{caminho.name}: TOML inválido — {erro}") from erro
    produtos = dados.get("produto") or []
    if not produtos:
        raise ProdutosInvalidos(f"{caminho.name}: nenhum produto declarado")
    nomes = set()
    for produto in produtos:
        _validar(produto, caminho.name)
        if produto["nome"] in nomes:
            raise ProdutosInvalidos(f"{caminho.name}: produto {produto['nome']!r} aparece duas "
                                    f"vezes — o segundo nunca seria alcançado")
        nomes.add(produto["nome"])
    return produtos


def kind_do_caminho(caminho_da_imagem, produtos=None):
    """O `kind` do primeiro produto cujo trecho aparece no caminho — ou None."""
    alvo = (caminho_da_imagem or "").lower()
    for produto in (produtos if produtos is not None else carregar()):
        if produto.get("kind") and any(t in alvo for t in produto["imagem"]):
            return produto["kind"]
    return None


def kind_da_tag(primeiro_segmento, com_estado, produtos=None):
    """O `kind` quando só a TAG nomeia o produto. Nunca decide tipo com estado — ver
    `detect_kind`: na tag, um datastore quase sempre é o *sabor* da aplicação."""
    alvo = (primeiro_segmento or "").lower()
    for produto in (produtos if produtos is not None else carregar()):
        kind = produto.get("kind")
        if kind and kind not in com_estado and any(t == alvo for t in produto["imagem"]):
            return kind
    return None


def socket_esperado(texto, produtos=None):
    """Montar o `docker.sock` é o funcionamento deste produto?"""
    alvo = (texto or "").lower()
    return any(any(t in alvo for t in produto["imagem"])
               for produto in (produtos if produtos is not None else carregar())
               if produto.get("socket_esperado"))


def candidatos_de_metrica(produtos=None):
    """`(trechos, familia, porta, caminho, prioridade, entrega)` de quem expõe métrica."""
    saida = []
    for produto in (produtos if produtos is not None else carregar()):
        m = produto.get("metricas")
        if m:
            saida.append((tuple(produto["imagem"]), m["familia"], m["porta"], m["caminho"],
                          m["prioridade"], m["entrega"]))
    return saida
