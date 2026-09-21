# tests/test_sumario_bate_com_template.py
"""O sumário é um registro à parte do template. Dois lugares para a mesma verdade.

Se alguém acrescenta uma seção no HTML e esquece do registro, o sumário simplesmente não a
lista — e o leitor conclui que ela não existe. Se remove do HTML e esquece do registro, o
sumário oferece um link que não leva a lugar nenhum: no PDF, âncora morta.

Nenhum dos dois quebra teste por si. Esta trava é o que faz quebrar.
"""
import re

from build_report import DESCRICAO_SECAO, SECOES_V3, TEMPLATE_V3


def _secoes_do_template():
    html = open(TEMPLATE_V3, encoding="utf-8").read()
    return re.findall(r'<h2 id="([a-z]+)"><em>\d+</em>', html)


def test_registro_e_template_listam_as_mesmas_secoes_na_mesma_ordem():
    assert [id_ for id_, _ in SECOES_V3] == _secoes_do_template()


def test_toda_secao_tem_descricao():
    faltando = [id_ for id_, _ in SECOES_V3 if not DESCRICAO_SECAO.get(id_)]
    assert not faltando, f"seções sem descrição no sumário: {faltando}"


def test_numeracao_do_template_e_sequencial():
    """O `<em>05</em>` é escrito à mão no HTML. Inserir uma seção no meio sem renumerar deixa
    dois `05` — e o sumário, que numera pela posição, discorda do corpo do relatório."""
    html = open(TEMPLATE_V3, encoding="utf-8").read()
    numeros = [int(n) for n in re.findall(r'<h2 id="[a-z]+"><em>(\d+)</em>', html)]
    assert numeros == list(range(1, len(numeros) + 1))


def test_o_sumario_conta_o_que_a_secao_de_instrumentos_mostra():
    """O sumário dizia "Instrumentos — 3 leituras" e a seção dizia "nenhuma medida com
    tolerância declarada respondeu": o sumário contava TODA resposta com dado, e a seção só as
    que têm faixa. Dois números para a mesma coisa."""
    from build_report import _sumario

    ctx = {"panorama": {"total": 1, "achados": 0, "aceitos": 0}, "recomendacoes": [],
           "historico": None,
           "alvos": [{"nome": "p", "componentes": [{"nome": "broker", "respostas": [
               {"pergunta": "fila.filas", "fonte": "a", "valor": [{"nome": "x"}]},
               {"pergunta": "fila.consumidores_por_fila", "fonte": "a", "valor": []}]}]}]}

    assert "0 leituras" in _sumario(ctx)
