# tests/test_catalogo.py
import pytest

from lib.catalogo import CatalogoInvalido, carregar_arquivo, familias


def test_carrega_as_familias_que_a_skill_publica():
    todas = {f["familia"]: f for f in familias()}
    assert "traefik" in todas and "http-generico" in todas
    traefik = todas["traefik"]
    assert traefik["identificacao"]["metrica_presente"] == "traefik_service_requests_total"
    assert "entrada.volume_na_janela" in {p["id"] for p in traefik["pergunta"]}


def test_familias_vem_em_ordem_estavel():
    """Ordem é prioridade e depois nome: a escolha do adaptador não pode depender do
    sistema de arquivos."""
    ordem = [(f["prioridade"], f["familia"]) for f in familias()]
    assert ordem == sorted(ordem)


CABECA = ('familia = "x"\nprioridade = 10\n[identificacao]\nmetrica_presente = "m"\n'
          '[seletor]\netiqueta = "job"\n')


def _escrever(tmp_path, corpo):
    (tmp_path / "x.toml").write_text(corpo, encoding="utf-8")
    return tmp_path / "x.toml"


def test_familia_que_cita_pergunta_inexistente_e_recusada(tmp_path):
    caminho = _escrever(tmp_path, CABECA + '[[pergunta]]\n'
                                  'id = "entrada.inexistente"\nquery = "up"\n')
    with pytest.raises(CatalogoInvalido) as erro:
        carregar_arquivo(caminho)
    assert "entrada.inexistente" in str(erro.value)


def test_query_so_aceita_as_duas_interpolacoes(tmp_path):
    """%SELETOR% e %JANELA% são as únicas. Outro %ALGO% seria um buraco por onde entra
    conteúdo não previsto dentro da consulta."""
    caminho = _escrever(tmp_path, CABECA + '[[pergunta]]\n'
                                  'id = "entrada.volume_na_janela"\nquery = "sum(m{%FILTRO%})"\n')
    with pytest.raises(CatalogoInvalido) as erro:
        carregar_arquivo(caminho)
    assert "%FILTRO%" in str(erro.value)


def test_pergunta_de_lista_sem_desempate_e_recusada(tmp_path):
    caminho = _escrever(tmp_path, CABECA + '[[pergunta]]\n'
                                  'id = "entrada.distribuicao_de_status"\n'
                                  'query = "sum by (code) (m)"\nchave = "code"\n')
    with pytest.raises(CatalogoInvalido) as erro:
        carregar_arquivo(caminho)
    assert "desempate" in str(erro.value)


def test_arquivo_sem_identificacao_e_recusado(tmp_path):
    caminho = _escrever(tmp_path, 'familia = "x"\nprioridade = 10\n')
    with pytest.raises(CatalogoInvalido):
        carregar_arquivo(caminho)


def test_tipo_de_valor_desconhecido_e_recusado(tmp_path):
    caminho = _escrever(tmp_path, CABECA + '[[pergunta]]\n'
                                  'id = "entrada.volume_na_janela"\nquery = "sum(m)"\n'
                                  'valor = "quilo"\n')
    with pytest.raises(CatalogoInvalido) as erro:
        carregar_arquivo(caminho)
    assert "quilo" in str(erro.value)


def test_familia_sem_etiqueta_de_seletor_e_recusada(tmp_path):
    """Sem etiqueta, a consulta sai com `{}` e agrega o exporter inteiro como se fosse o
    componente — número errado com cara de certo."""
    caminho = _escrever(tmp_path, 'familia = "x"\nprioridade = 10\n[identificacao]\n'
                                  'metrica_presente = "m"\n')
    with pytest.raises(CatalogoInvalido) as erro:
        carregar_arquivo(caminho)
    assert "etiqueta" in str(erro.value)
