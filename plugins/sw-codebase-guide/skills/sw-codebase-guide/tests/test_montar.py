import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / 'fixtures'

# A lista vive no `montar.py`, porque a recusa é do PARSER. Importar em vez de
# copiar é o que impede as duas divergirem na primeira vez que alguém
# acrescentar uma frase a uma só delas.
sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))
from montar import PROIBIDAS  # noqa: E402


def varrer(projeto, saida):
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True, text=True)


def montar(saida):
    return subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                           '--dir', str(saida)], capture_output=True, text=True)


def test_acoplamento_invisivel_aparece_como_mencao(tmp_path):
    # Arrange — o acoplamento existe SÓ por string e injeção
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — o par POSITIVO: o acoplamento TEM que aparecer
    assert 'UserController' in guia
    assert 'menç' in guia.lower()          # apareceu como menção textual
    assert 'rotas.py' in guia or 'container.py' in guia


def test_nenhuma_frase_de_ausencia(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text().lower()
    # Assert — o par NEGATIVO
    for frase in PROIBIDAS:
        assert frase not in guia, frase


def test_diz_o_que_o_grafo_de_import_nao_enxerga(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text().lower()
    # Assert — a ressalva viaja junto da afirmação, não numa nota de rodapé
    assert 'injeção de dependência' in guia or 'injecao de dependencia' in guia
    assert 'rota como string' in guia


def test_secao_de_co_mudanca_existe_com_motivo_sem_historico(tmp_path):
    # Arrange — a fixture não é repositório git
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — omissão se leria como "nada muda junto"
    assert 'muda junto' in guia.lower()
    assert 'git' in guia.lower()


def test_as_quatro_secoes_do_contrato_aparecem(tmp_path):
    # Arrange — uma afirmação em cada seção publicada pelo contrato
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '\n'.join(
            f'[[afirmacao]]\nsecao = "{secao}"\ntexto = "marca-{secao}"\n'
            f'nivel = "declarado"\nevidencia = ["rotas.py:1"]\nmotivo = ""\n'
            for secao in ('como-entrar', 'depende-de', 'o-que-faz', 'superficie')))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — seção publicada no contrato e não consumida faz o agente trabalhar à toa
    for secao in ('como-entrar', 'depende-de', 'o-que-faz', 'superficie'):
        assert f'marca-{secao}' in guia, secao


def test_secao_invalida_e_recusada_sem_traceback(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\ntexto = "sem secao"\nnivel = "fato"\n'
        'evidencia = ["rotas.py:1"]\nmotivo = ""\n')
    # Act
    r = montar(tmp_path)
    # Assert
    assert r.returncode == 2
    assert 'secao' in (r.stderr + r.stdout).lower()
    assert 'Traceback' not in r.stderr


def test_superficie_sai_marcada_como_deducao(tmp_path):
    # Arrange — a fixture tem rotas.py na raiz, sem pasta de convenção
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — sem convenção reconhecida, é lacuna com motivo; nunca silêncio
    assert 'Superfície pública' in guia
    assert 'lacuna' in guia.lower() or 'dedução' in guia


def test_duas_montagens_identicas(tmp_path):
    # Arrange — interpretation.toml CONGELADO: a parte não-determinística fica fora
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\n'
        'secao = "o-que-faz"\n'
        'texto = "Expõe um endpoint de usuário"\n'
        'nivel = "deducao"\n'
        'evidencia = ["rotas.py:3"]\n'
        'motivo = ""\n')
    # Act
    montar(tmp_path)
    primeira = (tmp_path / 'guide.md').read_bytes()
    montar(tmp_path)
    segunda = (tmp_path / 'guide.md').read_bytes()
    # Assert
    assert primeira == segunda


def test_afirmacao_sem_evidencia_e_recusada(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\n'
        'secao = "o-que-faz"\n'
        'texto = "O sistema gere uma loja de departamentos"\n'
        'nivel = "deducao"\n'
        'evidencia = []\n'
        'motivo = ""\n')
    (tmp_path / 'guide.md').write_text('documento anterior')   # sentinela
    # Act
    r = montar(tmp_path)
    # Assert — prosa plausível sem lastro não entra, e o documento bom não é destruído
    assert r.returncode == 2
    assert 'evidencia' in (r.stderr + r.stdout).lower()
    assert (tmp_path / 'guide.md').read_text() == 'documento anterior'


def test_co_mudanca_de_subrepos_aparece_com_ressalva(tmp_path):
    # Arrange — inventário de um projeto cuja raiz não tem git mas os filhos têm:
    # há dado E há lacuna. Decidir pela lacuna escondia os 40 pares que existiam.
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['historia'] = {
        'commits': 782, 'commits_descartados': 3,
        'co_mudanca': [{'arquivos': ['api/Rotas.php', 'api/Middleware.php'], 'vezes': 38}],
        'subrepos': [{'caminho': 'api', 'commits': 325}],
        'lacuna': 'a raiz não é repositório git; a co-mudança vem de 1 sub-repositório (api)',
    }
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — o dado aparece, e a ressalva viaja junto
    assert 'api/Rotas.php' in guia and '38x' in guia
    assert 'Ressalva' in guia and 'sub-repositório' in guia
    assert 'Não apurado' not in guia
    # e a pergunta sobre histórico não faz mais sentido
    assert 'Existe histórico de versionamento' not in guia


def test_pergunta_fixa_some_quando_a_secao_foi_respondida(tmp_path):
    # Arrange — a interpretação declara o propósito com fonte
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\nsecao = "o-que-faz"\n'
        'texto = "Transmite eventos do eSocial de processo trabalhista"\n'
        'nivel = "declarado"\nevidencia = ["commit 3c5aabb"]\nmotivo = ""\n')
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — perguntar o propósito logo abaixo da resposta é o documento se
    # contradizendo na mesma página
    assert 'Transmite eventos do eSocial' in guia
    assert 'Qual é o propósito de negócio' not in guia


def test_simbolo_so_citado_em_documentacao_fica_de_fora(tmp_path):
    # Arrange — nome de arquivo de spec virava "dependente"
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['mencoes']['PlanoDeMigracao'] = [{'caminho': 'docs/plano.md', 'linha': 3},
                                         {'caminho': 'README.md', 'linha': 9}]
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert '**PlanoDeMigracao**' not in guia
    assert 'só em documentação' in guia


def test_sem_grafo_de_import_a_secao_vira_lacuna(tmp_path):
    # Arrange — sem arestas, o que resta é grafo textual casando PALAVRA: num
    # projeto em português devolvia `banco` e `caminho` com centenas de "menções"
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['imports'] = {'arestas': [],
                      'indisponivel': [{'stack': 'node', 'motivo': 'sem resolvedor'}]}
    inv['mencoes'] = {'banco': [{'caminho': 'a.ts', 'linha': 1},
                                {'caminho': 'b.ts', 'linha': 2}],
                      'caminho': [{'caminho': 'c.ts', 'linha': 3},
                                  {'caminho': 'd.ts', 'linha': 4}]}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — a lacuna aparece com motivo, e o ruído não
    assert 'não foi medido nesta versão' in guia
    assert '[lacuna]' in guia
    assert '**banco**' not in guia and 'import não medido' not in guia
    # e a garantia mais forte continua de pé
    for frase in PROIBIDAS:
        assert frase not in guia.lower(), frase


def test_com_grafo_de_import_a_lista_continua(tmp_path):
    # Arrange — o par positivo: havendo aresta, a seção não some
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['imports'] = {'arestas': [{'de': 'rotas.py', 'para': 'app/UserController.py'}],
                      'indisponivel': []}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert 'por import' in guia
    assert 'não foi medido nesta versão' not in guia


def test_sem_lista_o_aviso_nao_se_repete(tmp_path):
    # Arrange — o preâmbulo das cegueiras qualifica uma lista; sem lista, ele mais a
    # indisponibilidade mais a lacuna dizem a mesma coisa três vezes
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['imports'] = {'arestas': [],
                      'indisponivel': [{'stack': 'node', 'motivo': 'sem resolvedor'}]}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert 'injeção de dependência' not in guia
    assert guia.count('[lacuna]') >= 1
    assert 'não foi medido nesta versão' in guia


def _com_escopo(tmp_path, **ajustes):
    """Inventário da fixture, com o escopo (e o que mais for pedido) forçado."""
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['escopo'] = {'area': 'app', 'criterio': 'prefixo de caminho', 'n_arquivos': 1}
    inv.update(ajustes)
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    r = montar(tmp_path)
    assert r.returncode == 0, r.stderr
    return (tmp_path / 'guide.md').read_text()


def test_documento_diz_qual_escopo_o_gerou(tmp_path):
    # Act
    guia = _com_escopo(tmp_path)
    # Assert — quem lê precisa saber que está vendo um recorte, e isso tem que
    # estar no TOPO: o plano mandava procurar em `linhas[2:8].__str__()`, que
    # passaria com a palavra em qualquer lugar daquelas seis linhas
    topo = '\n'.join(guia.split('\n')[:10])
    assert 'Recorte' in topo
    assert '`app`' in topo
    assert '1 arquivo' in topo


def test_sem_recorte_o_documento_nao_fala_de_area(tmp_path):
    # Arrange — o par negativo: sem ele, um cabeçalho fixo passaria no teste acima
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    assert montar(tmp_path).returncode == 0
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert 'Recorte' not in guia


def test_stack_de_fora_da_area_sai_marcada(tmp_path):
    # Act
    guia = _com_escopo(tmp_path, stacks=[
        {'stack': 'node', 'caminho': '.', 'manifesto': 'package.json',
         'por': 'manifesto', 'de_fora_da_area': True}])
    # Assert
    assert 'fora da área' in guia


def test_ponta_de_fora_sai_marcada(tmp_path):
    # Act
    guia = _com_escopo(tmp_path, historia={
        'commits': 90, 'commits_descartados': 0, 'lacuna': None,
        'co_mudanca': [{'arquivos': ['app/a.py', 'fora/b.py'], 'vezes': 9}]})
    # Assert — "mexer aqui mexe lá fora" só ensina se o leitor souber qual é o lá fora
    assert '`fora/b.py` *(fora)*' in guia
    assert '`app/a.py`' in guia and '`app/a.py` *(fora)*' not in guia


def test_commits_do_projeto_todo_sao_declarados(tmp_path):
    # Act
    guia = _com_escopo(tmp_path, historia={
        'commits': 500, 'commits_descartados': 0, 'lacuna': None,
        'co_mudanca': [{'arquivos': ['app/a.py', 'fora/b.py'], 'vezes': 9}]})
    # Assert — o número é do projeto, não da área, e o documento não pode esconder isso
    assert 'De 500 commits do projeto todo' in guia


def _com_evidencia(tmp_path, evidencias):
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    linhas = ''.join(
        f'[[afirmacao]]\nsecao = "o-que-faz"\ntexto = "t{i}"\nnivel = "deducao"\n'
        f'evidencia = {json.dumps([e])}\nmotivo = ""\n\n'
        for i, e in enumerate(evidencias))
    (tmp_path / 'interpretation.toml').write_text(linhas)
    return montar(tmp_path)


def test_quatro_formas_de_evidencia(tmp_path):
    # Arrange / Act — caminho, caminho:linha, diretório e não-caminho.
    # O SKILL.md documenta `app/Pedido.php:88` e os testes usam `commit 3c5aabb`:
    # uma conferência ingênua recusaria a evidência CORRETA.
    r = _com_evidencia(tmp_path, ['rotas.py', 'rotas.py:3', 'app/', 'commit 3c5aabb'])
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout


def test_caminho_inventado_recusado_nos_dois_blocos(tmp_path):
    # Arrange / Act
    r = _com_evidencia(tmp_path, ['nao/existe.php'])
    # Assert
    assert r.returncode == 2
    assert 'nao/existe.php' in (r.stderr + r.stdout)
    assert 'Traceback' not in r.stderr


def test_diretorio_casa_por_prefixo(tmp_path):
    # Arrange — a árvore só tem arquivos; `app/` é diretório e é citação legítima
    r = _com_evidencia(tmp_path, ['app/'])
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout


def test_diretorio_inventado_tambem_e_recusado(tmp_path):
    # Arrange — o par negativo do anterior: sem ele, bastaria aceitar tudo que
    # termina em barra para os dois testes passarem
    r = _com_evidencia(tmp_path, ['inventado/'])
    # Assert
    assert r.returncode == 2
    assert 'inventado/' in (r.stderr + r.stdout)


def test_markdown_nao_conta_como_codigo_no_cabecalho(tmp_path):
    """O mesmo documento chamava `.md` de código no cabeçalho e de "não é código" no
    bloco de arquivos maiores — duas definições de código na mesma página. E o
    conjunto `ATIVOS` existia em TRÊS cópias, uma por emissor."""
    # Arrange
    projeto = tmp_path / 'proj'
    projeto.mkdir()
    (projeto / 'app.py').write_text('x = 1')
    (projeto / 'pyproject.toml').write_text('[project]\nname = "x"')
    (projeto / 'README.md').write_text('# Projeto')
    (projeto / 'notas.md').write_text('# Notas')
    (projeto / 'dados.yaml').write_text('a: 1')
    saida = tmp_path / 'out'
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True)
    # Act
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                    '--dir', str(saida)], check=True, capture_output=True)
    guia = (saida / 'guide.md').read_text()
    # Assert — só `app.py` é código; os três markdown/yaml e o toml não são
    assert '1 arquivos de código' in guia or '1 arquivo de código' in guia, \
        [l for l in guia.split('\n') if 'arquivos de código' in l]
