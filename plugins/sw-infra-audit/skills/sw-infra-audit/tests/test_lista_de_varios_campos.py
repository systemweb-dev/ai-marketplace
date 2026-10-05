"""Uma pergunta em forma de lista cujos itens têm MAIS DE UM campo.

O catálogo promql sabia devolver `{chave, valor}` — um número por item. `fila.filas` precisa
de três (prontas, não confirmadas, consumidores), e o limiar que produz `fila_sem_consumidor`
compara dois deles. Sem isso, o único caminho para o papel `fila` era a API de administração,
que exige credencial; quem tem o exporter no Prometheus ficava sem resposta, e era por isso
que o `lib/enrich.py` sobrevivia em paralelo com uma tabela de consultas escrita no código.

Cada campo é uma consulta, e as consultas se juntam pela ETIQUETA declarada em `chave`.
"""
import tomllib

import pytest

from lib import catalogo, limiar

BASE = """
familia = "exporter-de-fila"
prioridade = 50
papel = "fila"
identifica_papel = true
[identificacao]
metrica_presente = "fila_mensagens_prontas"
[seletor]
etiqueta = "job"
"""


def _escrever(tmp_path, corpo, nome="familia.toml", papel="fila"):
    """O `papel` do fixture acompanha a pergunta usada no corpo.

    A validação de D1 recusa família que diga falar de um papel e responda pergunta de outro —
    e é uma trava que se quer: dois testes aqui usavam pergunta de `entrada`/`app` num fixture
    de `fila`, e eram recusados antes de chegar na asserção que eles realmente testam.
    """
    caminho = tmp_path / nome
    caminho.write_text(BASE.replace('papel = "fila"', f'papel = "{papel}"') + corpo,
                       encoding="utf-8")
    return caminho


LISTA_VALIDA = """
[[pergunta]]
id = "fila.filas"
chave = "queue"
desempate = "nome"
ordenar_por = "prontas"
valor = "inteiro"
  [[pergunta.campo]]
  nome = "prontas"
  query = 'sum by (queue) (fila_mensagens_prontas{%SELETOR%})'
  [[pergunta.campo]]
  nome = "consumidores"
  query = 'sum by (queue) (fila_consumidores{%SELETOR%})'
"""


def test_carrega_pergunta_com_varios_campos(tmp_path):
    dados = catalogo.carregar_arquivo(_escrever(tmp_path, LISTA_VALIDA))

    campos = dados["pergunta"][0]["campo"]
    assert [c["nome"] for c in campos] == ["prontas", "consumidores"]


def test_campo_e_query_na_mesma_pergunta_e_recusado(tmp_path):
    """Duas fontes para o mesmo item: qual delas vale? Ambiguidade no arquivo é erro de
    carregamento, não escolha silenciosa na coleta."""
    corpo = LISTA_VALIDA.replace('valor = "inteiro"',
                                 'valor = "inteiro"\nquery = \'sum by (queue) (x)\'')
    with pytest.raises(catalogo.CatalogoInvalido, match="`query` e `campo`"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_pergunta_sem_query_e_sem_campo_e_recusada(tmp_path):
    corpo = """
[[pergunta]]
id = "entrada.volume_na_janela"
valor = "inteiro"
"""
    with fail_sem_fonte():
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo, papel="entrada"))


def fail_sem_fonte():
    return pytest.raises(catalogo.CatalogoInvalido, match="nem `query` nem `campo`")


def test_campo_sem_nome_ou_sem_query_e_recusado(tmp_path):
    corpo = LISTA_VALIDA.replace('  nome = "consumidores"\n', "")
    with pytest.raises(catalogo.CatalogoInvalido, match="campo sem `nome`"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))

    corpo = LISTA_VALIDA.replace(
        "  query = 'sum by (queue) (fila_consumidores{%SELETOR%})'\n", "")
    with pytest.raises(catalogo.CatalogoInvalido, match="sem `query`"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_nome_de_campo_repetido_e_recusado(tmp_path):
    """Dois campos com o mesmo nome: o segundo sobrescreveria o primeiro na junção, e o
    arquivo pareceria medir duas coisas enquanto mede uma."""
    corpo = LISTA_VALIDA.replace('nome = "consumidores"', 'nome = "prontas"')
    with pytest.raises(catalogo.CatalogoInvalido, match="campo `prontas` aparece duas vezes"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_interpolacao_invalida_no_campo_e_recusada(tmp_path):
    """A validação de interpolação valia só para `query`; campo abriria um buraco por onde
    `%HOST%` entraria sem ninguém olhar."""
    corpo = LISTA_VALIDA.replace("{%SELETOR%}", "{%HOST%}", 1)
    with pytest.raises(catalogo.CatalogoInvalido, match="%HOST%"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_varios_campos_sem_chave_e_recusado(tmp_path):
    """`chave` é a etiqueta pela qual as consultas se juntam. Sem ela não há junção."""
    corpo = LISTA_VALIDA.replace('chave = "queue"\n', "")
    with pytest.raises(catalogo.CatalogoInvalido, match="`chave`"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_campo_em_pergunta_escalar_e_recusado(tmp_path):
    """Escalar é um número só: vários campos não têm onde caber."""
    corpo = LISTA_VALIDA.replace('id = "fila.filas"', 'id = "entrada.volume_na_janela"')
    with pytest.raises(catalogo.CatalogoInvalido, match="não é lista"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo, papel="entrada"))


def test_limiar_que_compara_campo_inexistente_e_recusado(tmp_path):
    """Esta é a trava que importa de verdade.

    `fila.filas` carrega o limiar `consumidores == 0 e prontas > 0`. Uma família que declare
    só `prontas` passaria no carregamento e produziria itens sem `consumidores`; o limiar vê
    `None`, `_comparar` devolve False por desenho, e a fila sem consumidor NUNCA viraria
    achado. Verde em tudo, e o achado que a pergunta existe para produzir desaparecido.
    """
    corpo = LISTA_VALIDA.replace("""  [[pergunta.campo]]
  nome = "consumidores"
  query = 'sum by (queue) (fila_consumidores{%SELETOR%})'
""", "")
    with pytest.raises(catalogo.CatalogoInvalido, match="consumidores"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_todo_arquivo_publicado_satisfaz_o_limiar_da_pergunta(tmp_path):
    """Contrato sobre o catálogo REAL, não sobre um arquivo de teste.

    Se alguém acrescentar uma família que responde pergunta com limiar, ela tem de medir os
    campos que o limiar compara — senão o achado some em silêncio.
    """
    from lib.perguntas import PERGUNTAS

    for familia in catalogo.familias():
        for pergunta in familia.get("pergunta", []):
            regra = PERGUNTAS[pergunta["id"]].get("limiar")
            if not regra:
                continue
            medidos = {c["nome"] for c in pergunta.get("campo", [])}
            faltando = limiar.campos(regra["quando"]) - medidos
            assert not faltando, (f"{familia['familia']} responde {pergunta['id']} sem medir "
                                  f"{sorted(faltando)} — o limiar nunca disparará")


# ---------------------------------------------------------------- ordenação declarada
def test_varios_campos_sem_ordenar_por_e_recusado(tmp_path):
    """Com um campo só, "do maior para o menor" não tem ambiguidade. Com três, ordenar pelo
    primeiro declarado seria a ordem decidida pela POSIÇÃO no arquivo — e mudar a ordem dos
    blocos mudaria o topo do relatório sem nada ter mudado na infraestrutura."""
    corpo = LISTA_VALIDA.replace('ordenar_por = "prontas"\n', "")
    with pytest.raises(catalogo.CatalogoInvalido, match="`ordenar_por`"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


LISTA_ORDENADA = LISTA_VALIDA


def test_ordenar_por_campo_inexistente_e_recusado(tmp_path):
    corpo = LISTA_ORDENADA.replace('ordenar_por = "prontas"', 'ordenar_por = "acumuladas"')
    with pytest.raises(catalogo.CatalogoInvalido, match="acumuladas"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_desempate_fora_do_item_e_recusado(tmp_path):
    """`desempate` nomeia um campo DO ITEM. Apontando para o que não existe, o empate cai em
    None e volta a herdar a ordem da fonte — o defeito que o desempate existe para matar."""
    corpo = LISTA_ORDENADA.replace('desempate = "nome"', 'desempate = "vhost"')
    with pytest.raises(catalogo.CatalogoInvalido, match="vhost"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_lista_ordenada_carrega(tmp_path):
    dados = catalogo.carregar_arquivo(_escrever(tmp_path, LISTA_ORDENADA))
    assert dados["pergunta"][0]["ordenar_por"] == "prontas"
