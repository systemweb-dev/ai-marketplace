# tests/test_imports.py
from lib.imports import grafo


def test_resolve_import_de_modulo_local(tmp_path):
    # Arrange
    (tmp_path / 'pedido.py').write_text('class Pedido: pass')
    (tmp_path / 'servico.py').write_text('from pedido import Pedido\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert
    assert {'de': 'servico.py', 'para': 'pedido.py'} in g['arestas']


def test_ignora_import_de_biblioteca_externa(tmp_path):
    # Arrange
    (tmp_path / 'servico.py').write_text('import json\nimport requests\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert — só aresta para arquivo QUE EXISTE no projeto
    assert g['arestas'] == []


def test_arquivo_com_erro_de_sintaxe_nao_derruba_a_varredura(tmp_path):
    # Arrange
    (tmp_path / 'quebrado.py').write_text('def (:::')
    (tmp_path / 'pedido.py').write_text('class Pedido: pass')
    (tmp_path / 'servico.py').write_text('from pedido import Pedido\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert
    assert {'de': 'servico.py', 'para': 'pedido.py'} in g['arestas']


def test_stack_sem_ferramenta_nativa_diz_o_motivo(tmp_path):
    # Arrange
    (tmp_path / 'index.php').write_text('<?php')
    stacks = [{'stack': 'php', 'caminho': '.', 'manifesto': 'composer.json'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert — não é silêncio: é indisponibilidade declarada
    assert g['arestas'] == []
    assert g['indisponivel'][0]['stack'] == 'php'
    assert g['indisponivel'][0]['motivo']


# ─── Casos reais que o plano não previa. Cada um ataca o mesmo risco: grafo vazio
#     se lê como "nada depende de nada", e é esse dano que o módulo existe para evitar.

def test_sem_stack_nenhuma_o_silencio_e_proibido(tmp_path):
    # Arrange — projeto sem manifesto nenhum existe de verdade (331 arquivos PHP e
    # nenhum composer.json), e aí `stacks.detectar` devolve []
    (tmp_path / 'index.php').write_text('<?php')
    # Act
    g = grafo(tmp_path, [])
    # Assert — sem arestas E sem indisponível seria silêncio: o leitor concluiria
    # que nada depende de nada, quando a verdade é que nada foi sequer tentado
    assert g['arestas'] == []
    assert g['indisponivel'], 'lista de stacks vazia não pode sair como grafo vazio'
    assert g['indisponivel'][0]['motivo']


def test_import_relativo_vira_aresta(tmp_path):
    # Arrange — `from .x import Y` é a forma NORMAL dentro de um pacote; ignorá-la
    # faria o grafo de um projeto bem organizado sair mais vazio que o de um bagunçado
    pacote = tmp_path / 'loja'
    (pacote / 'dominio').mkdir(parents=True)
    (pacote / '__init__.py').write_text('')
    (pacote / 'dominio' / '__init__.py').write_text('')
    (pacote / 'dominio' / 'pedido.py').write_text('class Pedido: pass')
    (pacote / 'modelos.py').write_text('class X: pass')
    (pacote / 'dominio' / 'servico.py').write_text(
        'from .pedido import Pedido\nfrom ..modelos import X\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert — nível 1 resolve no próprio pacote, nível 2 sobe um
    assert {'de': 'loja/dominio/servico.py',
            'para': 'loja/dominio/pedido.py'} in g['arestas']
    assert {'de': 'loja/dominio/servico.py',
            'para': 'loja/modelos.py'} in g['arestas']


def test_import_de_pacote_aponta_para_o_init(tmp_path):
    # Arrange — `from pacote import X` não tem arquivo `pacote.py`: o arquivo é o
    # `__init__.py`, e sem esse apelido a aresta sumiria
    (tmp_path / 'pacote').mkdir()
    (tmp_path / 'pacote' / '__init__.py').write_text('class X: pass')
    (tmp_path / 'app.py').write_text('from pacote import X\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert
    assert {'de': 'app.py', 'para': 'pacote/__init__.py'} in g['arestas']


def test_import_pela_source_root_e_resolvido(tmp_path):
    # Arrange — o arquivo mora em `scripts/lib/config.py`, mas o import diz
    # `from lib.config` porque é `scripts/` que entra no sys.path. Ancorar o módulo
    # na raiz dava ZERO arestas num projeto real com 243 imports locais.
    (tmp_path / 'scripts' / 'lib').mkdir(parents=True)
    (tmp_path / 'scripts' / 'lib' / 'config.py').write_text('X = 1')
    (tmp_path / 'scripts' / 'app.py').write_text('from lib.config import X\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert
    assert {'de': 'scripts/app.py', 'para': 'scripts/lib/config.py'} in g['arestas']


def test_sufixo_ambiguo_nao_vira_aresta(tmp_path):
    # Arrange — dois `config.py`: não dá para saber qual é o alvo
    for pasta in ('a', 'b'):
        (tmp_path / pasta / 'lib').mkdir(parents=True)
        (tmp_path / pasta / 'lib' / 'config.py').write_text('X = 1')
    (tmp_path / 'app.py').write_text('from lib.config import X\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert — aresta errada manda mexer no arquivo errado; a falta o grafo textual cobre
    assert not [a for a in g['arestas'] if a['de'] == 'app.py']
