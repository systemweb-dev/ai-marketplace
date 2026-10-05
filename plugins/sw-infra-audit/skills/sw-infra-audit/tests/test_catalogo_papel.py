"""A família declara o papel que ela prova — ou declara que não prova nenhum.

`cadvisor` publica `container_cpu_usage_seconds_total` com a etiqueta
`container_label_com_docker_swarm_service_name`, cujo valor É o nome do serviço no Swarm. Logo
TODO componente do cluster casa cAdvisor por igualdade exata (medido: 5 de 5). Se "casou a
etiqueta" bastasse para confirmar papel, ou nada seria confirmado nunca, ou — pior — um
componente cujo exporter real usa outro nome de job casaria só o cAdvisor e receberia papel
`app` CONFIRMADO. O caso que motiva o ciclo passaria a falhar com carimbo de autoridade.

`http-generico` tem o mesmo problema na outra direção: `http_requests_total` é publicado por
qualquer aplicação instrumentada, e promoveria uma API a `entrada`.

As duas MEDEM e NÃO VOTAM.
"""
import pytest

from lib import catalogo
from lib.papel import PAPEIS

# `papel` e `identifica_papel` vêm ANTES da primeira tabela: em TOML, chave escrita depois de
# um `[cabecalho]` pertence ÀQUELA tabela, não ao topo. O corpo de cada teste é concatenado
# depois do BASE, então quem declara papel no corpo precisa declará-lo antes de `[identificacao]`.
BASE_TOPO = """
familia = "exemplo"
prioridade = 50
"""
BASE_TABELAS = """
[identificacao]
metrica_presente = "x_total"
[seletor]
etiqueta = "job"
"""


def _escrever(tmp_path, topo="", corpo=""):
    caminho = tmp_path / "familia.toml"
    caminho.write_text(BASE_TOPO + topo + BASE_TABELAS + corpo, encoding="utf-8")
    return caminho


def test_familia_sem_papel_e_recusada(tmp_path):
    corpo = """
[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(x_total{%SELETOR%})'
"""
    with pytest.raises(catalogo.CatalogoInvalido, match="`papel`"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo=corpo))


def test_papel_inexistente_e_recusado(tmp_path):
    topo = 'papel = "banco-de-dados"\nidentifica_papel = true\n'
    corpo = """
[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(x_total{%SELETOR%})'
"""
    with pytest.raises(catalogo.CatalogoInvalido, match="banco-de-dados"):
        catalogo.carregar_arquivo(_escrever(tmp_path, topo, corpo))


def test_pergunta_de_outro_papel_e_recusada(tmp_path):
    """A família diz que prova `banco` e responde pergunta de `entrada`: uma das duas mente, e
    descobrir qual no relatório é tarde demais."""
    topo = 'papel = "banco"\nidentifica_papel = true\n'
    corpo = """
[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(x_total{%SELETOR%})'
"""
    with pytest.raises(catalogo.CatalogoInvalido, match="entrada.volume_na_janela"):
        catalogo.carregar_arquivo(_escrever(tmp_path, topo, corpo))


def test_identifica_papel_nao_booleano_e_recusado(tmp_path):
    topo = 'papel = "entrada"\nidentifica_papel = "sim"\n'
    corpo = """
[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(x_total{%SELETOR%})'
"""
    with pytest.raises(catalogo.CatalogoInvalido, match="identifica_papel"):
        catalogo.carregar_arquivo(_escrever(tmp_path, topo, corpo))


# ---------------------------------------------------------------- contrato sobre o catálogo REAL
def test_toda_familia_publicada_declara_papel_e_se_prova():
    familias = catalogo.familias()

    assert familias, "catálogo vazio faria este laço passar sem verificar nada"
    for familia in familias:
        assert familia["papel"] in PAPEIS, familia["familia"]
        assert isinstance(familia["identifica_papel"], bool), familia["familia"]


def test_as_sondas_de_medida_nao_provam_papel():
    """Fixa quais famílias MEDEM sem votar. Mudar esta lista é mudar como um cluster real é
    lido — tem de ser deliberado, com o diff à vista."""
    por_nome = {f["familia"]: f for f in catalogo.familias()}

    assert por_nome["cadvisor"]["identifica_papel"] is False
    assert por_nome["http-generico"]["identifica_papel"] is False
    for prova in ("traefik", "rabbitmq-prometheus", "postgres-exporter",
                  "mysqld-exporter", "redis-exporter"):
        assert por_nome[prova]["identifica_papel"] is True, prova
