# tests/test_papel.py
import pytest

from lib import produtos
from lib.papel import PAPEIS, POR_KIND, PapelInvalido, papel_de


def test_papel_traduz_o_kind_existente():
    assert papel_de("ingress/proxy") == "entrada"
    assert papel_de("api-gateway") == "entrada"
    assert papel_de("fila/broker") == "fila"
    assert papel_de("banco") == "banco"
    assert papel_de("object-storage") == "storage"


def test_cache_fila_resolve_para_cache_e_o_alvo_pode_corrigir():
    """Redis é cache na maioria das instalações — mas quando ele é o broker do Celery,
    quem sabe disso é o dono, não a imagem."""
    assert papel_de("cache/fila") == "cache"
    assert papel_de("cache/fila", declarado="fila") == "fila"


def test_todo_kind_conhecido_tem_papel():
    """Um kind novo em `references/produtos.toml` sem papel viraria `app` calado, e o
    componente perderia todas as perguntas do papel certo sem ninguém notar."""
    declarados = {p["kind"] for p in produtos.carregar() if p.get("kind")}
    faltando = sorted(declarados - set(POR_KIND))
    assert faltando == [], f"kind sem papel: {faltando}"


def test_todo_papel_traduzido_existe_na_lista_oficial():
    invalidos = sorted(set(POR_KIND.values()) - set(PAPEIS))
    assert invalidos == [], f"tradução aponta para papel inexistente: {invalidos}"


def test_kind_desconhecido_cai_em_app():
    assert papel_de("coisa-que-nao-existe") == "app"


def test_papel_declarado_invalido_e_recusado():
    with pytest.raises(PapelInvalido) as erro:
        papel_de("banco", declarado="bananco")
    assert "bananco" in str(erro.value)


# ------------------------------------- o vocabulário de kind, num lugar só
def test_o_vocabulario_de_kind_nao_tem_copias():
    """`COM_ESTADO` e `NO_CAMINHO_CRITICO` estavam escritos TRÊS vezes, sob DOIS nomes
    (`metrics.CRITICAL_PATH` e `impact.INGRESS`), e a terceira cópia — inline em `stacks` — já
    tinha derivado: ela não incluía `api-gateway`, então um gateway com réplica única não
    contava como ponto único de falha ali, embora contasse nos outros dois."""
    from lib import impact, metrics, papel

    assert metrics.STATEFUL is papel.COM_ESTADO
    assert impact.STATEFUL is papel.COM_ESTADO
    assert metrics.CRITICAL_PATH is papel.NO_CAMINHO_CRITICO
    assert impact.INGRESS is papel.NO_CAMINHO_CRITICO


def test_gateway_com_replica_unica_e_ponto_unico_de_falha():
    """A deriva que a unificação corrigiu: `api-gateway` estava nas duas cópias que decidem
    caminho crítico e faltava na que decide SPOF por stack."""
    from lib import stacks

    relatorio = {"services": [{"name": "borda_gw", "kind": "api-gateway", "replicas": "1/1"}]}

    grupos = stacks.group(relatorio)

    assert [g["spofs"] for g in grupos] == [["borda_gw"]]


def test_todo_kind_com_estado_e_do_vocabulario_conhecido():
    """Kind com estado que ninguém traduz para papel viraria `app` calado — e um serviço com
    estado tratado como aplicação sem estado é risco inventado ao contrário."""
    from lib.papel import COM_ESTADO, NO_CAMINHO_CRITICO, POR_KIND

    desconhecidos = sorted((COM_ESTADO | NO_CAMINHO_CRITICO) - set(POR_KIND))

    assert not desconhecidos, desconhecidos
