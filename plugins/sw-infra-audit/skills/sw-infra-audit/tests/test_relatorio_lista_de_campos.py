# tests/test_relatorio_lista_de_campos.py
"""Lista de vários campos no relatório — e o corte que só existe na hora de desenhar.

`_ranking` nasceu para o `promql`, cujo item é `{chave, valor}`: um rótulo, um número, uma
barra. O `admin_http` devolve `{nome, vhost, prontas, consumidores, ...}`, e desenhar isso como
ranking produzia rótulo vazio, valor zero e barras todas iguais.

E o corte mudou de lugar no batch 4: a extração entrega a POPULAÇÃO inteira (o limiar precisa
ver todas as filas), então é o relatório que mostra as 10 primeiras e diz quantas ficaram de
fora. A lista completa continua no `report.json`.
"""
from build_report import LIMITE_NO_RELATORIO, _resposta

FILAS = {"pergunta": "fila.filas", "fonte": "admin_http:amqp-mgmt", "valor": [
    {"nome": "pedidos", "vhost": "/", "prontas": 42, "consumidores": 3, "objeto": "pedidos@/"},
    {"nome": "emails", "vhost": "/", "prontas": 7, "consumidores": 0, "objeto": "emails@/"},
]}

RANKING = {"pergunta": "entrada.distribuicao_de_status", "fonte": "promql:proxy",
           "valor": [{"chave": "200", "valor": 900}, {"chave": "500", "valor": 12}]}


def _muitas(n):
    return dict(FILAS, valor=[{"nome": f"f{i:03d}", "vhost": "/", "prontas": n - i,
                               "consumidores": 1, "objeto": f"f{i:03d}@/"} for i in range(n)])


def test_lista_de_varios_campos_vira_tabela():
    html = _resposta(FILAS)

    assert "<table" in html
    assert "pedidos" in html and "42" in html and "emails" in html


def test_o_cabecalho_usa_os_nomes_dos_campos():
    html = _resposta(FILAS)

    for campo in ("nome", "vhost", "prontas", "consumidores"):
        assert f"<th>{campo.replace('_', ' ')}</th>" in html


def test_objeto_nao_vira_coluna():
    """`objeto` é a identidade composta para achado e aceite — no relatório ele repetiria as
    colunas nome e vhost lado a lado."""
    assert "<th>objeto</th>" not in _resposta(FILAS)


def test_item_de_chave_e_valor_continua_sendo_ranking():
    """Regressão: `entrada.distribuicao_de_status` já está publicada com barra."""
    html = _resposta(RANKING)

    assert 'class="rk"' in html
    assert "<table" not in html


def test_zero_aparece_como_zero_e_nao_some():
    """`consumidores: 0` é o dado mais importante da linha — é ele que vira achado."""
    assert "<td>0</td>" in _resposta(FILAS)


def test_campo_none_vira_travessao_e_nao_zero():
    resposta = dict(FILAS, valor=[{"nome": "x", "prontas": None, "consumidores": 1}])

    assert "<td>—</td>" in _resposta(resposta)


def test_a_fonte_continua_visivel():
    assert "admin_http:amqp-mgmt" in _resposta(FILAS)


def test_lista_vazia_diz_que_esta_vazia():
    """Zero filas é um fato — o relatório diz, em vez de desenhar uma tabela sem linha."""
    html = _resposta(dict(FILAS, valor=[]))

    assert "<table" not in html and "nenhuma" in html


def test_conteudo_do_campo_e_escapado():
    resposta = dict(FILAS, valor=[{"nome": "<script>alert(1)</script>", "prontas": 1}])

    html = _resposta(resposta)

    assert "<script>" not in html and "&lt;script&gt;" in html


# --- o corte de exibição ---

def test_mostra_so_as_primeiras_e_diz_quantas_ficaram_de_fora():
    """Um broker de 500 filas imprimia 500 linhas: a extração deixou de cortar (o limiar precisa
    da população inteira), e o relatório ainda não cortava."""
    html = _resposta(_muitas(500))

    assert html.count("<tr>") == LIMITE_NO_RELATORIO + 1          # + o cabeçalho
    assert "e mais 490" in html
    assert "report.json" in html


def test_as_primeiras_sao_as_do_topo_da_ordenacao():
    """O corte respeita a ordem que a extração decidiu — não reordena por conta própria."""
    html = _resposta(_muitas(50))

    assert "f000" in html and "f009" in html and "f010" not in html


def test_lista_que_cabe_nao_ganha_rodape():
    assert "e mais" not in _resposta(_muitas(LIMITE_NO_RELATORIO))


def test_ranking_tambem_corta():
    resposta = dict(RANKING, valor=[{"chave": str(i), "valor": 100 - i} for i in range(30)])

    html = _resposta(resposta)

    assert html.count('class="rk"') == LIMITE_NO_RELATORIO
    assert "e mais 20" in html


# --- o despejo que só aparecia olhando o PDF ---

def test_topologia_mostra_a_contagem_e_nao_despeja_a_lista():
    """O nó da topologia mostra "a primeira leitura" de cada componente, e imprimia o valor
    cru: com a lista de filas, eram três páginas A4 do `repr` do Python — `{'nome':
    'orfa-006', 'vhost': ...}` — dentro de um cartão. Nenhum teste pegou; só olhar o PDF."""
    from build_report import _no_da_topologia

    componente = {"nome": "broker", "papel": "fila", "achados": [],
                  "respostas": [_muitas(500)]}

    html = _no_da_topologia({"nome": "exemplo"}, componente)

    assert "Filas: 500" in html
    assert "orfa" not in html and "{" not in html and "f000" not in html


def test_numero_nunca_despeja_colecao():
    """Rede de segurança para qualquer outro chamador: lista ou dicionário viram contagem."""
    from build_report import _numero

    assert _numero([1, 2, 3]) == "3 itens"
    assert "{" not in _numero({"a": 1})


def test_tabela_dentro_de_cartao_nao_herda_o_corte_da_tabela_cartao():
    """A regra genérica `table{}` dá borda, raio e `overflow:hidden` a toda tabela. Dentro de um
    cartão, o canto arredondado cortava a primeira letra da primeira coluna ("NOME" saía com o N
    comido). Só apareceu renderizando o PDF em alta resolução."""
    import re

    from build_report import TEMPLATE_V3

    css = open(TEMPLATE_V3, encoding="utf-8").read()
    regra = re.search(r"\.campos,\.ocs\{([^}]*)\}", css)

    assert regra, "falta a regra que anula o visual de tabela-cartão"
    assert "overflow:visible" in regra.group(1) and "border-radius:0" in regra.group(1)
