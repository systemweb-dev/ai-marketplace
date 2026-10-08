"""As perguntas derivadas do que foi medido.

A seção "Perguntas em aberto" é o entregável que a skill mais valoriza, e era
três strings fixas enquanto o `julgamento` já tinha medido os fatos que dariam
pauta de verdade. Estes testes guardam as três regras do módulo: pergunta sem
número não entra, pergunta não afirma, e a genérica só sai quando não há
específica.
"""
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))

from lib import perguntas  # noqa: E402
from montar import PROIBIDAS  # noqa: E402


def inv(**partes):
    base = {'julgamento': {'perigo': [], 'sem_alcance': [], 'risco': [], 'dossie': {}},
            'historia': {'co_mudanca': []}, 'imports': {'arestas': [], 'resolucao': {}},
            'arvore': [], 'retrato': {}}
    for chave, valor in partes.items():
        if chave in ('perigo', 'sem_alcance', 'risco'):
            base['julgamento'][chave] = valor
        else:
            base[chave] = valor
    return base


# ───────────────────────── a guarda que vale para todas ─────────────────────

def test_nenhuma_pergunta_afirma_ausencia_de_dependentes():
    """A guarda `PROIBIDAS` do `montar.py` recusaria o documento inteiro — e
    estaria certa: quem lê de relance guarda a frase e esquece o ponto de
    interrogação. A pergunta sobre arquivo parado é a mais fácil de errar."""
    # Arrange — todas as categorias de uma vez
    dados = inv(
        perigo=[{'caminho': 'app/a.py', 'dependentes': 55, 'mudancas': 35}],
        sem_alcance=[{'caminho': 'app/b.py', 'dias_parado': 426}],
        risco=[{'o_que': 'x', 'onde': '.env', 'tipo': 'env-versionado'}],
        retrato={'autores': 1, 'commits': 985},
        imports={'arestas': [], 'resolucao': {'php': {
            'relativos': 3, 'sufixo_unico': 0, 'base_provada': 0,
            'config_conferida': 0, 'ambiguos': 7, 'pendurados': 0,
            'nao_resolvidos': 0, 'externos': 0}}})
    # Act
    saida = perguntas.derivar(dados, set())
    # Assert
    assert saida, 'o arranjo precisa produzir perguntas para o teste valer'
    for d in saida:
        texto = (d['pergunta'] + ' ' + d['porque']).lower()
        for frase in PROIBIDAS:
            assert frase not in texto, f'{frase!r} em {d["pergunta"]!r}'


def test_toda_pergunta_termina_em_interrogacao():
    # Arrange
    dados = inv(perigo=[{'caminho': 'app/a.py', 'dependentes': 55, 'mudancas': 35}],
                sem_alcance=[{'caminho': 'app/b.py', 'dias_parado': 426}],
                retrato={'autores': 1, 'commits': 985})
    # Act / Assert
    for d in perguntas.derivar(dados, set()):
        assert d['pergunta'].rstrip().endswith('?'), d['pergunta']


def test_sem_nada_medido_nao_ha_pergunta_derivada():
    """Pergunta sem número é conversa que qualquer um puxaria sem a skill."""
    # Act / Assert
    assert perguntas.derivar(inv(), set()) == []


# ───────────────────────── arquivo perigoso ─────────────────────────────────

def test_a_pergunta_do_perigoso_leva_os_dois_numeros():
    # Act
    saida = perguntas.derivar(
        inv(perigo=[{'caminho': 'app/a.py', 'dependentes': 55, 'mudancas': 35}]), set())
    # Assert
    assert len(saida) == 1
    assert '55' in saida[0]['pergunta'] and '35' in saida[0]['pergunta']
    assert 'app/a.py' in saida[0]['pergunta']


def test_a_lista_de_perigosos_tem_teto():
    """Oito perguntas sobre arquivo perigoso é a mesma pergunta oito vezes."""
    # Arrange
    muitos = [{'caminho': f'app/{i}.py', 'dependentes': 50, 'mudancas': 9}
              for i in range(8)]
    # Act / Assert
    assert len(perguntas.derivar(inv(perigo=muitos), set())) == \
        perguntas.TETO_POR_CATEGORIA


# ───────────────────────── credencial versionada ────────────────────────────

def test_envs_versionados_viram_uma_pergunta_so():
    """Três linhas quase iguais empurram as outras perguntas para baixo, e a
    resposta é a mesma para as três."""
    # Arrange
    tres = [{'o_que': 'x', 'onde': f'app/.env.{s}', 'tipo': 'env-versionado'}
            for s in ('dev', 'prod', 'test')]
    # Act
    saida = perguntas.derivar(inv(risco=tres), set())
    # Assert
    assert len(saida) == 1
    assert saida[0]['evidencia'] == ['app/.env.dev', 'app/.env.prod', 'app/.env.test']


def test_risco_que_nao_e_env_versionado_nao_vira_essa_pergunta():
    # Act / Assert
    assert perguntas.derivar(
        inv(risco=[{'o_que': 'y', 'onde': 'app/x', 'tipo': 'outro'}]), set()) == []


# ───────────────────────── o par que muda junto e não se importa ────────────

def _projeto_com_par(vezes: int, arestas=(), linguagem='PHP'):
    return inv(
        historia={'co_mudanca': [{'arquivos': ['a.php', 'b.php'], 'vezes': vezes}]},
        arvore=[{'caminho': 'a.php', 'linguagem': linguagem},
                {'caminho': 'b.php', 'linguagem': linguagem}],
        imports={'arestas': list(arestas), 'resolucao': {}})


def test_par_que_muda_junto_sem_aresta_vira_pergunta():
    """É o acoplamento que o grafo não vê: rota em string, injeção de
    dependência, reflexão, template."""
    # Act
    saida = perguntas.derivar(_projeto_com_par(38), {'PHP'})
    # Assert
    assert len(saida) == 1
    assert '38' in saida[0]['pergunta']
    assert saida[0]['evidencia'] == ['a.php', 'b.php']


def test_par_com_aresta_nao_vira_pergunta():
    """Se um importa o outro, não há mistério: o grafo já conta a história."""
    # Act / Assert
    assert perguntas.derivar(
        _projeto_com_par(38, [{'de': 'a.php', 'para': 'b.php'}]), {'PHP'}) == []


def test_a_aresta_vale_nos_dois_sentidos():
    # Act / Assert
    assert perguntas.derivar(
        _projeto_com_par(38, [{'de': 'b.php', 'para': 'a.php'}]), {'PHP'}) == []


def test_par_abaixo_do_piso_nao_vira_pergunta():
    """Abaixo do piso, "mudaram juntos" é coincidência de quem mexe em tudo no
    mesmo commit."""
    # Act / Assert
    assert perguntas.derivar(
        _projeto_com_par(perguntas.MIN_JUNTOS_SEM_ARESTA - 1), {'PHP'}) == []


def test_linguagem_fora_do_piso_de_resolucao_nao_gera_a_pergunta():
    """Num grafo pela metade, "não há aresta" quer dizer "não medi" — e a
    pergunta nasceria de uma cegueira da skill, não de um fato do projeto."""
    # Act / Assert
    assert perguntas.derivar(_projeto_com_par(38), set()) == []
    assert perguntas.derivar(_projeto_com_par(38), {'js'}) == []


def test_as_duas_pontas_precisam_ser_de_linguagem_medida():
    # Arrange — uma ponta em linguagem confiável, a outra não
    dados = inv(
        historia={'co_mudanca': [{'arquivos': ['a.php', 'b.rb'], 'vezes': 38}]},
        arvore=[{'caminho': 'a.php', 'linguagem': 'PHP'},
                {'caminho': 'b.rb', 'linguagem': 'Ruby'}],
        imports={'arestas': [], 'resolucao': {}})
    # Act / Assert
    assert perguntas.derivar(dados, {'PHP'}) == []


def test_o_mesmo_arquivo_nao_se_repete_na_categoria():
    """Num projeto real os três primeiros pares eram `Rotas` + `Middleware`,
    `Controller` + `Rotas` e `Controller` + `Middleware`: a mesma pergunta
    escrita três vezes."""
    # Arrange
    dados = inv(
        historia={'co_mudanca': [
            {'arquivos': ['rotas.php', 'mid.php'], 'vezes': 38},
            {'arquivos': ['ctrl.php', 'rotas.php'], 'vezes': 18},
            {'arquivos': ['ctrl.php', 'mid.php'], 'vezes': 16},
            {'arquivos': ['x.php', 'y.php'], 'vezes': 12}]},
        arvore=[{'caminho': c, 'linguagem': 'PHP'}
                for c in ('rotas.php', 'mid.php', 'ctrl.php', 'x.php', 'y.php')],
        imports={'arestas': [], 'resolucao': {}})
    # Act
    saida = perguntas.derivar(dados, {'PHP'})
    # Assert
    assert len(saida) == 2
    assert 'rotas.php' in saida[0]['pergunta'] and 'mid.php' in saida[0]['pergunta']
    assert 'x.php' in saida[1]['pergunta']


# ───────────────────────── autoria e resolução ──────────────────────────────

def test_autor_unico_vira_pergunta():
    # Act
    saida = perguntas.derivar(inv(retrato={'autores': 1, 'commits': 985}), set())
    # Assert
    assert len(saida) == 1 and '985' in saida[0]['pergunta']


def test_mais_de_um_autor_nao_vira_pergunta():
    # Act / Assert
    assert perguntas.derivar(inv(retrato={'autores': 6, 'commits': 782}), set()) == []


def test_linguagem_abaixo_do_piso_vira_pergunta_com_a_taxa():
    # Arrange
    dados = inv(imports={'arestas': [], 'resolucao': {'php': {
        'relativos': 6, 'sufixo_unico': 0, 'base_provada': 0, 'config_conferida': 0,
        'ambiguos': 4, 'pendurados': 0, 'nao_resolvidos': 0, 'externos': 99}}})
    # Act
    saida = perguntas.derivar(dados, set())
    # Assert
    assert len(saida) == 1
    assert '60%' in saida[0]['pergunta'] and '`php`' in saida[0]['pergunta']


def test_linguagem_nao_medida_nao_vira_pergunta_de_resolucao():
    """Denominador zero é "não medido", e não 0% — a diferença é a que a skill
    inteira existe para preservar."""
    # Arrange
    dados = inv(imports={'arestas': [], 'resolucao': {'python': {
        'relativos': 0, 'sufixo_unico': 0, 'base_provada': 0, 'config_conferida': 0,
        'ambiguos': 0, 'pendurados': 0, 'nao_resolvidos': 0, 'externos': 7}}})
    # Act / Assert
    assert perguntas.derivar(dados, set()) == []


def test_linguagem_acima_do_piso_nao_vira_pergunta():
    # Arrange
    dados = inv(imports={'arestas': [], 'resolucao': {'php': {
        'relativos': 9, 'sufixo_unico': 0, 'base_provada': 0, 'config_conferida': 0,
        'ambiguos': 1, 'pendurados': 0, 'nao_resolvidos': 0, 'externos': 0}}})
    # Act / Assert
    assert perguntas.derivar(dados, {'php'}) == []


# ───────────────────────── a ordem é de urgência ────────────────────────────

def test_credencial_exposta_vem_antes_de_arquivo_perigoso():
    # Arrange
    dados = inv(perigo=[{'caminho': 'app/a.py', 'dependentes': 55, 'mudancas': 35}],
                risco=[{'o_que': 'x', 'onde': '.env', 'tipo': 'env-versionado'}])
    # Act
    saida = perguntas.derivar(dados, set())
    # Assert
    assert 'trocadas' in saida[0]['pergunta']
    assert 'dependentes' in saida[1]['pergunta']


def test_a_lista_de_pares_tem_teto():
    """Faltava este teste, e a falha ficou escondida por um defeito do próprio
    harness de mutação: duas mutações removiam a mesma substring, gerando
    arquivos do mesmo tamanho no mesmo segundo, e o Python reusou o `.pyc` de
    uma na rodada da outra. O relatório marcou "pega" uma mutação que
    sobreviveu."""
    # Arrange — quatro pares sem arquivo repetido, todos acima do piso
    nomes = [f'{chr(97 + i)}.php' for i in range(8)]
    pares = [{'arquivos': [nomes[2 * i], nomes[2 * i + 1]], 'vezes': 20}
             for i in range(4)]
    dados = inv(historia={'co_mudanca': pares},
                arvore=[{'caminho': n, 'linguagem': 'PHP'} for n in nomes],
                imports={'arestas': [], 'resolucao': {}})
    # Act
    saida = perguntas.derivar(dados, {'PHP'})
    # Assert
    assert len(saida) == perguntas.TETO_POR_CATEGORIA


def test_a_lista_de_parados_tem_teto():
    # Arrange
    muitos = [{'caminho': f'app/{i}.py', 'dias_parado': 400 + i} for i in range(7)]
    # Act / Assert
    assert len(perguntas.derivar(inv(sem_alcance=muitos), set())) == \
        perguntas.TETO_POR_CATEGORIA
