# tests/test_stacks.py
from pathlib import Path
from lib.stacks import detectar

FIXTURES = Path(__file__).parent / 'fixtures'


def test_acha_as_duas_stacks_de_um_projeto_poliglota():
    # Arrange
    raiz = FIXTURES / 'poliglota'
    # Act
    achadas = detectar(raiz)
    # Assert
    nomes = sorted(c['stack'] for c in achadas)
    assert nomes == ['node', 'php']


def test_informa_onde_cada_stack_mora():
    # Arrange
    raiz = FIXTURES / 'poliglota'
    # Act
    por_stack = {c['stack']: c for c in detectar(raiz)}
    # Assert
    assert por_stack['node']['caminho'] == 'web'
    assert por_stack['php']['caminho'] == 'api'
    assert por_stack['node']['manifesto'] == 'package.json'


def test_projeto_sem_manifesto_devolve_lista_vazia(tmp_path):
    # Arrange
    (tmp_path / 'leiame.txt').write_text('oi')
    # Act / Assert
    assert detectar(tmp_path) == []


def test_build_no_caminho_absoluto_nao_esconde_a_stack(tmp_path):
    # Arrange — projeto que mora dentro de um diretório chamado `build`:
    # o filtro IGNORAR vale para o caminho RELATIVO à raiz, não para o absoluto.
    raiz = tmp_path / 'build' / 'loja'
    raiz.mkdir(parents=True)
    (raiz / 'package.json').write_text('{ "name": "loja" }')
    # Act
    achadas = detectar(raiz)
    # Assert
    assert [c['stack'] for c in achadas] == ['node']
    assert achadas[0]['caminho'] == '.'


def test_dist_no_caminho_absoluto_nao_esconde_a_stack(tmp_path):
    # Arrange — mesmo caso, com `dist` em vez de `build`.
    raiz = tmp_path / 'dist' / 'loja'
    raiz.mkdir(parents=True)
    (raiz / 'package.json').write_text('{ "name": "loja" }')
    # Act
    achadas = detectar(raiz)
    # Assert
    assert [c['stack'] for c in achadas] == ['node']


def test_manifesto_dentro_de_node_modules_nao_vira_componente(tmp_path):
    # Arrange — nenhum teste prendia a guarda do IGNORAR em `stacks`: a mutação
    # sobrevivia, e num projeto real isso devolvia 357 componentes em vez de 3
    (tmp_path / 'package.json').write_text('{"name": "app"}')
    (tmp_path / 'node_modules' / 'lodash').mkdir(parents=True)
    (tmp_path / 'node_modules' / 'lodash' / 'package.json').write_text('{"name": "lodash"}')
    (tmp_path / 'vendor' / 'guzzle').mkdir(parents=True)
    (tmp_path / 'vendor' / 'guzzle' / 'composer.json').write_text('{"name": "guzzle"}')
    # Act
    achadas = detectar(tmp_path)
    # Assert
    assert [(c['stack'], c['caminho']) for c in achadas] == [('node', '.')]


def test_diretorio_de_build_com_manifesto_nao_vira_componente(tmp_path):
    # Arrange — `.next/package.json` existe em todo projeto Next.js, e dois dos três
    # componentes de um projeto real eram lixo gerado
    (tmp_path / 'package.json').write_text('{"name": "app"}')
    for pasta in ('.next', '.nuxt', 'target', 'coverage'):
        (tmp_path / pasta).mkdir()
        (tmp_path / pasta / 'package.json').write_text('{"name": "gerado"}')
    # Act
    achadas = detectar(tmp_path)
    # Assert
    assert [c['caminho'] for c in achadas] == ['.']


def test_linguagem_sem_manifesto_e_detectada(tmp_path):
    # Arrange — 210 arquivos Python sem `pyproject.toml` saíam como "sem stack", e o
    # grafo nem tentava parseá-los nem registrava a lacuna: silêncio
    for i in range(6):
        (tmp_path / f'modulo{i}.py').write_text('x = 1')
    # Act
    achadas = detectar(tmp_path)
    # Assert
    assert len(achadas) == 1
    assert achadas[0]['stack'] == 'python'
    assert achadas[0]['manifesto'] is None
    assert 'nenhum manifesto' in achadas[0]['por']


def test_poucos_arquivos_soltos_nao_viram_stack(tmp_path):
    # Arrange — script solto num projeto de outra linguagem não é stack do projeto
    (tmp_path / 'package.json').write_text('{"name": "app"}')
    (tmp_path / 'build.py').write_text('x = 1')
    # Act
    stacks = {c['stack'] for c in detectar(tmp_path)}
    # Assert
    assert stacks == {'node'}


def test_dois_manifestos_da_mesma_stack_nao_duplicam(tmp_path):
    # Arrange
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "x"')
    (tmp_path / 'requirements.txt').write_text('requests\n')
    # Act
    achadas = detectar(tmp_path)
    # Assert — o documento imprimia a mesma linha duas vezes
    assert len(achadas) == 1
    assert achadas[0]['stack'] == 'python'
