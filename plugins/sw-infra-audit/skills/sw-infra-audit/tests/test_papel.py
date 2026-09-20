# tests/test_papel.py
import pytest

from lib.coletores.docker import _KINDS
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
    """Um kind novo em _KINDS sem papel viraria `app` calado, e o componente perderia todas
    as perguntas do papel certo sem ninguém notar."""
    faltando = sorted({kind for _, kind in _KINDS} - set(POR_KIND))
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
