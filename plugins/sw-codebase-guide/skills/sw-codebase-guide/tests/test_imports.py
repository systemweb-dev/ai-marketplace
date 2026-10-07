# tests/test_imports.py
from lib.arvore import varrer as varrer_arvore
from lib.imports import grafo


def arvore_de(raiz):
    return varrer_arvore(raiz)


def test_resolve_import_de_modulo_local(tmp_path):
    # Arrange
    (tmp_path / 'pedido.py').write_text('class Pedido: pass')
    (tmp_path / 'servico.py').write_text('from pedido import Pedido\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks, arvore_de(tmp_path))
    # Assert
    assert any(a['de'] == 'servico.py' and a['para'] == 'pedido.py'
               for a in g['arestas'])


def test_ignora_import_de_biblioteca_externa(tmp_path):
    # Arrange
    (tmp_path / 'servico.py').write_text('import json\nimport requests\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks, arvore_de(tmp_path))
    # Assert — só aresta para arquivo QUE EXISTE no projeto
    assert g['arestas'] == []


def test_arquivo_com_erro_de_sintaxe_nao_derruba_a_varredura(tmp_path):
    # Arrange
    (tmp_path / 'quebrado.py').write_text('def (:::')
    (tmp_path / 'pedido.py').write_text('class Pedido: pass')
    (tmp_path / 'servico.py').write_text('from pedido import Pedido\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks, arvore_de(tmp_path))
    # Assert
    assert any(a['de'] == 'servico.py' and a['para'] == 'pedido.py'
               for a in g['arestas'])


def test_linguagem_de_codigo_sem_extrator_diz_o_motivo(tmp_path):
    """Este teste descrevia o PHP, que até esta versão não tinha resolvedor. Agora
    tem — então o que ele guarda mudou de assunto, não de valor: a garantia é que
    linguagem de CÓDIGO sem extrator vira indisponibilidade declarada, nunca
    silêncio. Silêncio se lê como "nada depende de nada".

    E não há piso de quantidade: dois arquivos bastam. O piso de 5 do `stacks.py` é
    justamente o defeito que o despacho por extensão veio consertar."""
    # Arrange
    (tmp_path / 'main.go').write_text('package main\n')
    (tmp_path / 'outro.go').write_text('package main\n')
    (tmp_path / 'LEIAME.md').write_text('# doc\n')
    # Act
    g = grafo(tmp_path, [], arvore_de(tmp_path))
    # Assert
    motivos = {i['stack']: i['motivo'] for i in g['indisponivel']}
    assert g['arestas'] == []
    assert '.go' in motivos and motivos['.go']
    assert '.md' not in motivos, 'markdown não é código: declarar lacuna dele é ruído'


# ─── Casos reais que o plano não previa. Cada um ataca o mesmo risco: grafo vazio
#     se lê como "nada depende de nada", e é esse dano que o módulo existe para evitar.

def test_sem_linguagem_reconhecida_o_silencio_e_proibido(tmp_path):
    """Projeto em que nada é linguagem reconhecida: o grafo sai vazio, e vazio se
    lê como "nada depende de nada". Tem que sair com o motivo escrito."""
    # Arrange
    (tmp_path / 'LEIAME.md').write_text('# só documentação\n')
    # Act
    g = grafo(tmp_path, [], arvore_de(tmp_path))
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
    g = grafo(tmp_path, stacks, arvore_de(tmp_path))
    # Assert — nível 1 resolve no próprio pacote, nível 2 sobe um
    assert any(a['de'] == 'loja/dominio/servico.py' and a['para'] == 'loja/dominio/pedido.py'
               for a in g['arestas'])
    assert any(a['de'] == 'loja/dominio/servico.py' and a['para'] == 'loja/modelos.py'
               for a in g['arestas'])


def test_import_de_pacote_aponta_para_o_init(tmp_path):
    # Arrange — `from pacote import X` não tem arquivo `pacote.py`: o arquivo é o
    # `__init__.py`, e sem esse apelido a aresta sumiria
    (tmp_path / 'pacote').mkdir()
    (tmp_path / 'pacote' / '__init__.py').write_text('class X: pass')
    (tmp_path / 'app.py').write_text('from pacote import X\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks, arvore_de(tmp_path))
    # Assert
    assert any(a['de'] == 'app.py' and a['para'] == 'pacote/__init__.py'
               for a in g['arestas'])


def test_import_pela_source_root_e_resolvido(tmp_path):
    # Arrange — o arquivo mora em `scripts/lib/config.py`, mas o import diz
    # `from lib.config` porque é `scripts/` que entra no sys.path. Ancorar o módulo
    # na raiz dava ZERO arestas num projeto real com 243 imports locais.
    (tmp_path / 'scripts' / 'lib').mkdir(parents=True)
    (tmp_path / 'scripts' / 'lib' / 'config.py').write_text('X = 1')
    (tmp_path / 'scripts' / 'app.py').write_text('from lib.config import X\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks, arvore_de(tmp_path))
    # Assert
    assert any(a['de'] == 'scripts/app.py' and a['para'] == 'scripts/lib/config.py'
               for a in g['arestas'])


def test_sufixo_ambiguo_nao_vira_aresta(tmp_path):
    # Arrange — dois `config.py`: não dá para saber qual é o alvo
    for pasta in ('a', 'b'):
        (tmp_path / pasta / 'lib').mkdir(parents=True)
        (tmp_path / pasta / 'lib' / 'config.py').write_text('X = 1')
    (tmp_path / 'app.py').write_text('from lib.config import X\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks, arvore_de(tmp_path))
    # Assert — aresta errada manda mexer no arquivo errado; a falta o grafo textual cobre
    assert not [a for a in g['arestas'] if a['de'] == 'app.py']
