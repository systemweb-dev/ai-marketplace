# tests/test_markdown_da_remediacao.py
"""A remediação é escrita em markdown e era impressa como se fosse uma frase só.

O template sempre teve CSS para `.fix ol` e `.fix pre` — o desenho contava com lista numerada e
bloco de código. O renderizador entregava tudo achatado num parágrafo, com as crases e o "1."
no meio do texto corrido. O CSS existia para um HTML que nunca era gerado.

Escapar continua sendo a regra: o conteúdo vem de arquivo, e nada aqui pode abrir tag.
"""
from build_report import _rich


def test_lista_numerada_vira_ol():
    html = _rich("1. Primeiro passo\n2. Segundo passo")

    assert "<ol>" in html
    assert html.count("<li>") == 2
    assert "1." not in html, "o número ficou no texto e a lista renumerou por cima"


def test_bloco_de_codigo_vira_pre():
    html = _rich("Antes\n\n```dockerfile\nRUN adduser app\nUSER 10001\n```\n\nDepois")

    assert "<pre>" in html and "RUN adduser app\nUSER 10001" in html
    assert "```" not in html


def test_codigo_inline_vira_code():
    html = _rich("rode `docker exec id` na mão")

    assert "<code>docker exec id</code>" in html
    assert "`" not in html


def test_negrito_de_markdown_e_de_tag_funcionam():
    assert "<strong>forte</strong>" in _rich("um **forte** aqui")
    assert "<strong>forte</strong>" in _rich("um <strong>forte</strong> aqui")


def test_html_do_conteudo_continua_escapado():
    """A remediação vem de arquivo. Se um dia vier de outro lugar, a trava tem que estar aqui."""
    html = _rich("perigo <script>alert(1)</script> e <img src=x onerror=y>")

    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html


def test_cifrao_e_chave_dentro_de_codigo_nao_viram_tag():
    html = _rich("```sh\necho $(id -u) > /tmp/x\n```")

    assert "&gt;" in html or "&amp;gt;" in html
    assert "<script" not in html


def test_paragrafos_separados_por_linha_em_branco():
    html = _rich("Primeiro parágrafo.\n\nSegundo parágrafo.")

    assert html.count("<p>") == 2


def test_lista_com_marcador_vira_ul():
    html = _rich("- um\n- dois")

    assert "<ul>" in html and html.count("<li>") == 2


def test_texto_simples_continua_simples():
    """O caso mais comum não pode ganhar embrulho a mais."""
    assert _rich("uma frase só") == "<p>uma frase só</p>"


def test_item_de_lista_que_continua_na_linha_seguinte():
    """Os arquivos de remediação quebram linha em 95 colunas. Um item de três linhas fazia o
    bloco inteiro deixar de ser lista — era o caso do SEC_USER_ROOT, o achado mais frequente
    da auditoria real, que saía com "1. ... 2. ... 3. ..." em texto corrido."""
    html = _rich("1. Primeiro item\n2. Segundo item que continua\n   na linha de baixo\n"
                 "3. Terceiro")

    assert "<ol>" in html
    assert html.count("<li>") == 3
    assert "na linha de baixo" in html
    assert "<li>Segundo item que continua na linha de baixo</li>" in html


def test_linha_que_comeca_com_numero_sem_ser_item_nao_vira_lista():
    """`2026 foi o ano...` não é item de lista. O ponto depois do número é o que distingue."""
    html = _rich("2026 foi quando isso apareceu")

    assert "<ol>" not in html


def test_paragrafo_seguido_de_lista_no_mesmo_bloco():
    """"...estão assim por desenho:" seguido da lista, sem linha em branco entre os dois — é
    como se escreve markdown à mão, e a lista inteira virava texto corrido."""
    html = _rich("Algumas estão assim por desenho:\n- **fila morta**: guarda o que falhou\n"
                 "- **stream**: log retido")

    assert html.startswith("<p>Algumas estão assim por desenho:</p><ul>")
    assert html.count("<li>") == 2


def test_linha_sem_marcador_depois_do_item_continua_o_item():
    """Continuação preguiçosa, como no markdown padrão: sem indentação, a linha ainda é do
    item. A versão anterior fechava a lista ali, e `"1. passo que quebra\nna linha seguinte\n
    2. Segundo"` virava lista, parágrafo, lista."""
    html = _rich("1. passo que quebra\nna linha seguinte\n2. Segundo")

    assert html == "<ol><li>passo que quebra na linha seguinte</li><li>Segundo</li></ol>"


def test_hifen_no_meio_de_paragrafo_nao_vira_lista():
    """O texto do agente quebra linha onde quiser: "cresceu em\n- 40% na última hora" é uma
    frase, não uma lista. A lista só começa no início do bloco ou depois de uma linha que
    termina em dois-pontos."""
    html = _rich("A fila cresceu em\n- 40% na última hora, e segue subindo.")

    assert "<ul>" not in html and html.startswith("<p>")


def test_numero_no_meio_de_paragrafo_nao_vira_lista():
    assert "<ol>" not in _rich("Foram auditados\n12. Nada mais.")


def test_toda_remediacao_publicada_renderiza_as_listas():
    """Nenhum marcador de lista pode sobrar no meio de parágrafo em arquivo publicado."""
    import re

    from lib.remediacao import disponiveis, para

    for regra in sorted(disponiveis()):
        bloco = para(regra)
        for chave in ("por_que_importa", "como_resolver", "como_confirmar", "quando_nao_fazer"):
            html = _rich(bloco[chave])
            for paragrafo in re.findall(r"<p>(.*?)</p>", html, re.S):
                assert not re.search(r"(^|\s)(-|\d+\.)\s+\S", paragrafo), \
                    f"{regra}/{chave}: lista virou texto corrido — {paragrafo[:60]!r}"
