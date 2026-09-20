"""Papel do componente — derivado do `kind`, nunca em lugar dele.

`detect_kind` já classifica por imagem, e `lib/metrics.py` (STATEFUL) e `lib/impact.py`
(CRITICAL_PATH) comparam aquelas strings LITERALMENTE. Renomeá-las quebraria saúde e impacto
em silêncio — nenhum teste pegaria. Por isso aqui só se traduz.

O papel é o que decide QUAIS PERGUNTAS o componente recebe. Papel errado não é detalhe
cosmético: é perguntar de fila para um banco.
"""

PAPEIS = ("entrada", "fila", "banco", "cache", "busca", "storage", "observabilidade", "app")

POR_KIND = {
    "ingress/proxy": "entrada", "proxy": "entrada", "api-gateway": "entrada",
    "fila": "fila", "fila/broker": "fila",
    "banco": "banco",
    # Redis é cache na maioria das instalações; quando ele é o broker do Celery, quem sabe
    # disso é o dono — e por isso o alvo pode declarar `papel = "fila"`.
    "cache": "cache", "cache/fila": "cache",
    "busca": "busca",
    "observabilidade": "observabilidade",
    "object-storage": "storage",
    "app": "app",
}


class PapelInvalido(Exception):
    """Papel declarado que não existe."""


def papel_de(kind, declarado=None):
    """O papel do componente. O declarado no alvos.toml vence a imagem."""
    if declarado is not None:
        if declarado not in PAPEIS:
            raise PapelInvalido(
                f"papel {declarado!r} não existe; os papéis são {', '.join(PAPEIS)}")
        return declarado
    return POR_KIND.get(kind, "app")
