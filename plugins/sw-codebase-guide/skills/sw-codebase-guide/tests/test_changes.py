"""O que mudou desde a rodada anterior.

O documento regenera do zero a cada rodada, e por isso não dizia o que tinha
mudado: quem já tinha lido relia tudo para descobrir que um arquivo entrou no mapa
de perigo. A medição que precedeu o desenho rodou duas vezes num projeto real com
um mês e 63 commits entre elas, e o que ela derrubou está guardado aqui como teste
— porque as três decisões foram contra a intuição:

- número que se move em item que FICOU na lista é ruído;
- de lista cortada só a ENTRADA é fato — a saída é artefato do corte;
- comparar rodadas de recortes diferentes inventa movimento, e é recusado inteiro.
"""
import json

import pytest

from lib import changes


def inv(**campos) -> dict:
    """Um inventário mínimo que passa os pré-requisitos de todos os grupos.

    Os pré-requisitos existem para separar "mediu e não achou" de "não pôde medir";
    um inventário de teste que não os cumpre manda todo grupo para `nao_comparado`
    e o teste verde não prova nada.
    """
    base = {
        'gerado_em_versao': 1,
        'projeto': 'loja',
        'escopo': {'tipo': None, 'area': None, 'funcionalidade': None},
        'arvore': [],
        'linhas_por_arquivo': {},
        'retrato': {'commits': 10, 'semanas_parado': 0},
        'mudanca_por_arquivo': {'a.py': '2026-01-01'},
        'imports': {'arestas': [{'de': 'a.py', 'para': 'b.py', 'origem': 'x'}]},
        'historia': {'co_mudanca': [{'arquivos': ['a.py', 'b.py'], 'vezes': 3}]},
        'julgamento': {'perigo': [], 'sem_alcance': []},
        'superficie': [],
        'ambiente': {},
        'execucao': {'composicoes': [], 'comandos': []},
    }
    base.update(campos)
    return base


def grupo(resultado: dict, chave: str) -> dict | None:
    return next((g for g in resultado['listas'] if g['chave'] == chave), None)


def numero(resultado: dict, chave: str) -> dict | None:
    return next((n for n in resultado['numeros'] if n['chave'] == chave), None)


def perigo(*caminhos) -> dict:
    return {'julgamento': {
        'perigo': [{'caminho': c, 'dependentes': 6, 'mudancas': 10} for c in caminhos],
        'sem_alcance': []}}


# ───────────────────────── a trava: quando não comparar ───────────────────────


def test_sem_rodada_anterior_nao_inventa_mudanca():
    # Act
    r = changes.comparar(inv(**perigo('a.py')), None)
    # Assert
    assert r['houve_rodada_anterior'] is False
    assert r['listas'] == [] and r['numeros'] == []


def test_recorte_diferente_recusa_a_comparacao_inteira():
    """O caso que mais machuca: uma rodada `--area api` contra uma do projeto
    inteiro reportaria centenas de arquivos saindo, e mandaria alguém investigar
    o que não aconteceu."""
    # Arrange
    antes = inv(escopo={'tipo': None, 'area': None, 'funcionalidade': None})
    depois = inv(escopo={'tipo': 'area', 'area': 'api', 'funcionalidade': None},
                 **perigo('a.py'))
    # Act
    r = changes.comparar(depois, antes)
    # Assert
    assert r['lacuna'] and 'recortes diferentes' in r['lacuna']
    assert r['listas'] == [] and r['numeros'] == []


def test_a_recusa_por_recorte_diz_qual_era_e_qual_e():
    # Act
    r = changes.comparar(
        inv(escopo={'tipo': 'area', 'area': 'api', 'funcionalidade': None}),
        inv(escopo={'tipo': 'funcionalidade', 'area': None,
                    'funcionalidade': 'cadastro'}))
    # Assert
    assert '`cadastro`' in r['lacuna'] and '`api`' in r['lacuna']


def test_versao_diferente_do_inventario_recusa():
    # Act
    r = changes.comparar(inv(gerado_em_versao=2, **perigo('a.py')),
                         inv(gerado_em_versao=1))
    # Assert
    assert r['lacuna'] and r['listas'] == []


def test_outro_projeto_recusa():
    # Act
    r = changes.comparar(inv(projeto='loja', **perigo('a.py')), inv(projeto='erp'))
    # Assert
    assert r['lacuna'] and '`erp`' in r['lacuna']


# ───────────────── lista vazia antes: mediu e não achou ou não pôde? ──────────


def test_sem_import_na_rodada_anterior_o_perigo_nao_e_comparado():
    """Oito arquivos perigosos "novos" quando o que entrou foi a medição é a
    forma que o «não apurado ≠ não existe» assume aqui."""
    # Arrange
    antes = inv(imports={'arestas': []})
    depois = inv(**perigo('a.py', 'b.py'))
    # Act
    r = changes.comparar(depois, antes)
    # Assert
    assert grupo(r, 'perigo') is None
    assert any(x['chave'] == 'perigo' for x in r['nao_comparado'])


def test_com_import_antes_a_entrada_no_perigo_e_reportada():
    # Act
    r = changes.comparar(inv(**perigo('a.py')), inv())
    # Assert
    g = grupo(r, 'perigo')
    assert [i['nomes'] for i in g['entrou']] == [['a.py']]
    assert g['entrou'][0]['detalhe'] == '6 dependentes, 10 mudanças'


def test_sem_historico_antes_os_commits_nao_viram_linha():
    # Act
    r = changes.comparar(inv(retrato={'commits': 70, 'semanas_parado': 0}),
                         inv(mudanca_por_arquivo={},
                             retrato={'commits': 10, 'semanas_parado': 0}))
    # Assert
    assert numero(r, 'commits') is None
    assert any(x['chave'] == 'commits' for x in r['nao_comparado'])


# ─────────────────────────── lista cortada ────────────────────────────────────


def test_de_lista_cortada_so_a_entrada_e_fato():
    """Na rodada medida, três pares "saíram" com 3x e 4x — empurrados para fora
    do corte de 40 por pares que cresceram. A linha dizia que um acoplamento tinha
    acabado quando ninguém tinha tocado nele."""
    # Arrange
    antes = inv(historia={'co_mudanca': [
        {'arquivos': ['velho.py', 'outro.py'], 'vezes': 4}]})
    depois = inv(historia={'co_mudanca': [
        {'arquivos': ['novo.py', 'outro.py'], 'vezes': 9}]})
    # Act
    g = grupo(changes.comparar(depois, antes), 'co_mudanca')
    # Assert
    assert [i['nomes'] for i in g['entrou']] == [['novo.py', 'outro.py']]
    assert g['saiu'] == []
    assert g['saida_nao_apurada'] and '40 pares' in g['saida_nao_apurada']


def test_o_par_e_identificado_pelas_DUAS_pontas():
    """Identificar o par pela primeira ponta faz `a.py + c.py` desaparecer
    quando `a.py + b.py` já estava lá — o acoplamento novo some em silêncio,
    e é justamente o que esta seção existe para mostrar."""
    # Arrange
    antes = inv(historia={'co_mudanca': [{'arquivos': ['a.py', 'b.py'], 'vezes': 4}]})
    depois = inv(historia={'co_mudanca': [{'arquivos': ['a.py', 'c.py'], 'vezes': 9}]})
    # Act
    g = grupo(changes.comparar(depois, antes), 'co_mudanca')
    # Assert
    assert [i['nomes'] for i in g['entrou']] == [['a.py', 'c.py']]


def test_de_lista_por_limiar_a_saida_e_fato():
    """`perigo` não tem teto — entra por limiar. Sair dela é o arquivo que ganhou
    teste ou perdeu dependentes, e é exatamente o que o leitor quer saber."""
    # Act
    g = grupo(changes.comparar(inv(), inv(**perigo('a.py'))), 'perigo')
    # Assert
    assert [i['nomes'] for i in g['saiu']] == [['a.py']]
    assert g['saida_nao_apurada'] is None


# ───────────────────────────── o que é ruído ──────────────────────────────────


def test_numero_que_se_move_em_item_que_ficou_nao_vira_linha():
    """Quatro arquivos perigosos tiveram `dependentes` subindo de 1 a 3 no mês
    medido. Nada que o leitor faça muda: o arquivo já estava na lista."""
    # Arrange
    antes = inv(julgamento={'perigo': [
        {'caminho': 'a.py', 'dependentes': 59, 'mudancas': 22}], 'sem_alcance': []})
    depois = inv(julgamento={'perigo': [
        {'caminho': 'a.py', 'dependentes': 62, 'mudancas': 23}], 'sem_alcance': []})
    # Act
    r = changes.comparar(depois, antes)
    # Assert
    assert grupo(r, 'perigo') is None
    assert r['nada_mudou'] is True


def test_numero_parado_nao_vira_linha():
    # Act
    r = changes.comparar(inv(), inv())
    # Assert
    assert r['numeros'] == [] and r['nada_mudou'] is True


def test_numero_nao_apurado_de_um_dos_lados_nao_vira_zero():
    """Zero no lugar de "não sei" é a frase que esta skill não emite.

    O campo tem de faltar em UM lado só: faltando nos dois, `None == None` já
    descarta a linha pelo caminho do "não mudou", e a mutação que tira a guarda
    do não apurado passa verde. Foi assim que ela escapou na primeira rodada.
    """
    # Act
    r = changes.comparar(inv(retrato={'commits': 70, 'semanas_parado': 2}),
                         inv(retrato={'commits': 10}))   # sem `semanas_parado`
    # Assert
    assert numero(r, 'commits')['depois'] == 70
    assert numero(r, 'parado') is None


# ─────────────────────────── os grupos, um a um ───────────────────────────────


def test_variavel_de_ambiente_nova_sai_com_o_arquivo_que_a_declara():
    # Act
    g = grupo(changes.comparar(inv(ambiente={'.env.example': ['A', 'B']}),
                               inv(ambiente={'.env.example': ['A']})), 'ambiente')
    # Assert
    assert g['entrou'] == [{'nomes': ['B'], 'detalhe': 'em .env.example'}]


def test_a_mesma_variavel_em_dois_env_conta_duas_vezes():
    """Declarar num `.env` e não no outro é a diferença que faz alguém passar a
    tarde atrás de um erro de configuração."""
    # Act
    g = grupo(changes.comparar(inv(ambiente={'.env': ['A'], '.env.prod': ['A']}),
                               inv(ambiente={'.env': ['A']})), 'ambiente')
    # Assert
    assert g['entrou'] == [{'nomes': ['A'], 'detalhe': 'em .env.prod'}]


def test_rota_nova_sai_com_o_tipo():
    # Act
    g = grupo(changes.comparar(
        inv(superficie=[{'caminho': 'app/X.php', 'tipo': 'rota', 'por': 'app/'}]),
        inv()), 'superficie')
    # Assert
    assert g['entrou'] == [{'nomes': ['app/X.php'], 'detalhe': 'rota'}]


def test_servico_novo_do_compose():
    def com(*nomes):
        return {'execucao': {'composicoes': [
            {'caminho': 'docker-compose.yml',
             'servicos': [{'nome': n} for n in nomes]}], 'comandos': []}}
    # Act
    g = grupo(changes.comparar(inv(**com('web', 'fila')), inv(**com('web'))),
              'servicos')
    # Assert
    assert g['entrou'] == [{'nomes': ['fila'], 'detalhe': 'em docker-compose.yml'}]


def test_script_de_subida_novo():
    def com(*scripts):
        return {'execucao': {'composicoes': [], 'comandos': [
            {'caminho': 'package.json', 'candidatos': list(scripts)}]}}
    # Act
    g = grupo(changes.comparar(inv(**com('dev', 'start')), inv(**com('dev'))),
              'comandos')
    # Assert
    assert g['entrou'] == [{'nomes': ['start'], 'detalhe': 'em package.json'}]


# ────────────────────────────── o teto ────────────────────────────────────────


def test_grupo_com_entradas_demais_corta_e_diz_quantas_ficaram():
    # Arrange — a aritmética do corte, dimensionada pela constante
    caminhos = [f'f{i}.py' for i in range(changes.TETO_POR_GRUPO + 3)]
    # Act
    g = grupo(changes.comparar(inv(**perigo(*caminhos)), inv()), 'perigo')
    # Assert
    assert len(g['entrou']) == changes.TETO_POR_GRUPO
    assert g['entrou_omitidos'] == 3


def test_o_teto_padrao_segura_uma_enxurrada():
    """O teste acima dimensiona a fixture PELA constante, então deixa de provar
    que o valor dela serve: com o teto em 5000 ele continua verde. Este fixa o
    tamanho pelo mundo — o primeiro `git pull` de um ano de trabalho — e é o que
    prova que o padrão corta."""
    # Arrange
    caminhos = [f'f{i}.py' for i in range(50)]
    # Act
    g = grupo(changes.comparar(inv(**perigo(*caminhos)), inv()), 'perigo')
    # Assert — uma seção de resumo não vira duas telas de lista
    assert len(g['entrou']) <= 10
    assert g['entrou_omitidos'] >= 40


# ────────────────────────────── as frases ─────────────────────────────────────


@pytest.mark.parametrize('antes, depois, esperado', [
    (689, 752, '63 commits novos (689 → 752)'),
    (10, 11, '1 commit novo (10 → 11)'),
])
def test_a_frase_dos_commits_flexiona(antes, depois, esperado):
    # Act / Assert
    assert changes.frase_do_numero(
        {'chave': 'commits', 'antes': antes, 'depois': depois}) == esperado


def test_o_projeto_que_voltou_a_andar_diz_isso_com_todas_as_letras():
    # Act
    f = changes.frase_do_numero({'chave': 'parado', 'antes': 5, 'depois': 0})
    # Assert
    assert f == 'voltou a andar: estava parado há 5 semanas'


def test_o_projeto_que_parou_tambem():
    # Act
    f = changes.frase_do_numero({'chave': 'parado', 'antes': 0, 'depois': 3})
    # Assert
    assert 'parou' in f and '3 semanas' in f


# ───────────────────────── o arquivo da rodada anterior ───────────────────────


def test_anterior_ausente_e_anterior_quebrado_dao_no_mesmo(tmp_path):
    """Arquivo de apoio corrompido some com a seção; nunca derruba o emissor."""
    # Arrange
    (tmp_path / 'inventory.prev.json').write_text('{ não é json')
    # Act / Assert
    assert changes.ler_anterior(tmp_path) is None
    assert changes.ler_anterior(tmp_path / 'vazio') is None


def test_anterior_valido_e_lido(tmp_path):
    # Arrange
    (tmp_path / 'inventory.prev.json').write_text(json.dumps(inv()))
    # Act / Assert
    assert changes.ler_anterior(tmp_path)['projeto'] == 'loja'


def test_rotulo_para_todo_grupo_e_todo_corte():
    """Rótulo faltando sai como `KeyError` na hora de emitir — e o grupo novo que
    ninguém rotulou é justamente o que nenhum teste de emissor alcança."""
    # Assert
    assert {g[0] for g in changes.GRUPOS} <= set(changes.ROTULOS)
    assert set(changes.CORTES) == {g[0] for g in changes.GRUPOS if g[4]}
