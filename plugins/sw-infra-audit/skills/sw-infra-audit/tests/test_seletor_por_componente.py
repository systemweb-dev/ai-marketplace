"""O seletor tem de encontrar o componente, não supor como ele se chama na métrica.

A primeira versão montava `job="<nome do serviço no Swarm>"`. Isso só acerta quando o valor
da etiqueta é idêntico ao nome do serviço — verdade para o cAdvisor, cujo rótulo É o nome do
serviço, e quase nunca verdade para `job`, que vale o que o scrape config do Prometheus disser.

Errando, caía para "exporter inteiro": `systemweb_nginx` e `traefik_traefik` recebiam os
MESMOS 60.281 requests e os MESMOS 652 ms. Lido assim, o relatório afirma que o nginx serviu
aquele tráfego. Ele não serviu.

O conserto é perguntar quais valores a etiqueta TEM e casar com o componente.
"""
import pytest

from lib.adaptadores.promql import casar_valor_da_etiqueta


@pytest.mark.parametrize("componente,valores,esperado", [
    # exato
    ("traefik", ["traefik", "node", "cadvisor"], "traefik"),
    # o Swarm prefixa com a stack: `<stack>_<serviço>`
    ("traefik_traefik", ["traefik", "node"], "traefik"),
    ("monitoring_cadvisor", ["cadvisor"], "cadvisor"),
    # o valor é que traz o prefixo
    ("redis", ["infra_redis", "postgres"], "infra_redis"),
    # nada parecido: melhor NÃO escolher do que escolher errado
    ("postgres", ["traefik", "node"], None),
    ("", ["traefik"], None),
    ("traefik", [], None),
])
def test_casa_o_componente_com_o_valor_que_existe(componente, valores, esperado):
    assert casar_valor_da_etiqueta(componente, valores) == esperado


def test_entre_dois_parecidos_escolhe_o_mais_proximo():
    """`loja` casaria com `loja` e com `loja-api`; o exato vence."""
    assert casar_valor_da_etiqueta("loja", ["loja-api", "loja"]) == "loja"


def test_ambiguo_de_verdade_nao_escolhe():
    """Dois candidatos igualmente plausíveis: escolher um seria atribuir medida a quem pode
    não ser o dono dela. Sem escolha, a resposta sai como exporter inteiro e DIZ isso."""
    assert casar_valor_da_etiqueta("api", ["loja-api", "shop-api"]) is None


def test_nao_casa_por_substring_solta():
    """`db` não pode casar com `mariadb`: substring frouxa atribuiria a medida do banco
    errado, e errar em silêncio é pior que não medir."""
    assert casar_valor_da_etiqueta("db", ["mariadb", "influxdb"]) is None
