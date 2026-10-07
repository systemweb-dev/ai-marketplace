# tests/test_arvore.py
from lib.arvore import varrer


def test_pula_vendor_e_node_modules(tmp_path):
    # Arrange
    (tmp_path / 'app').mkdir()
    (tmp_path / 'app' / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'vendor' / 'lib').mkdir(parents=True)
    (tmp_path / 'vendor' / 'lib' / 'Grande.php').write_text('<?php // 3rd party')
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'x.js').write_text('module.exports={}')
    # Act
    caminhos = [a['caminho'] for a in varrer(tmp_path)]
    # Assert
    assert caminhos == ['app/Pedido.php']


def test_classifica_linguagem_pela_extensao(tmp_path):
    # Arrange
    (tmp_path / 'a.php').write_text('<?php')
    (tmp_path / 'b.py').write_text('x = 1')
    # Act
    por_caminho = {a['caminho']: a['linguagem'] for a in varrer(tmp_path)}
    # Assert
    assert por_caminho['a.php'] == 'php'
    assert por_caminho['b.py'] == 'python'


def test_marca_arquivo_gerado(tmp_path):
    # Arrange
    (tmp_path / 'app.min.js').write_text('var a=1')
    (tmp_path / 'app.js').write_text('var a = 1')
    # Act
    por_caminho = {a['caminho']: a['gerado'] for a in varrer(tmp_path)}
    # Assert
    assert por_caminho['app.min.js'] is True
    assert por_caminho['app.js'] is False


def test_arquivo_acima_do_teto_entra_mas_nao_e_lido(tmp_path):
    # Arrange
    (tmp_path / 'dump.sql').write_text('x' * 5000)
    # Act
    item = varrer(tmp_path, teto_bytes=1000)[0]
    # Assert
    assert item['bytes'] == 5000
    assert item['acima_do_teto'] is True


def test_ordem_e_estavel(tmp_path):
    # Arrange
    for nome in ('c.py', 'a.py', 'b.py'):
        (tmp_path / nome).write_text('x = 1')
    # Act
    primeira = [a['caminho'] for a in varrer(tmp_path)]
    segunda = [a['caminho'] for a in varrer(tmp_path)]
    # Assert — ordem instável quebraria a idempotência do documento (Task 10)
    assert primeira == segunda == ['a.py', 'b.py', 'c.py']


def test_blade_vence_php_pelo_sufixo_mais_longo(tmp_path):
    # Arrange — `.blade.php` termina em `.php`; só o sufixo mais LONGO acerta
    (tmp_path / 'template.blade.php').write_text('@extends("layout")')
    # Act
    por_caminho = {a['caminho']: a['linguagem'] for a in varrer(tmp_path)}
    # Assert
    assert por_caminho['template.blade.php'] == 'blade'


def test_dotfile_composto_nao_inventa_linguagem(tmp_path):
    # Arrange — `.env.production` tem suffix `.production` e virava a linguagem
    # "production" no documento
    for nome in ('.env.production', '.env.teste', '.gitignore'):
        (tmp_path / nome).write_text('X=1')
    # Act
    por_caminho = {a['caminho']: a['linguagem'] for a in varrer(tmp_path)}
    # Assert
    assert set(por_caminho.values()) == {'config'}


def test_declaracao_de_tipo_e_historia_contam_como_gerados(tmp_path):
    """`.d.ts` e `.stories.*` são fabricantes clássicos de sufixo duplicado: cada
    `Botao.d.ts` ao lado de `Botao.ts` cria uma ambiguidade artificial que derruba a
    taxa de resolução sem que nada esteja errado."""
    # Arrange
    (tmp_path / 'Botao.ts').write_text('export const x = 1')
    (tmp_path / 'Botao.d.ts').write_text('export declare const x: number')
    (tmp_path / 'Lista.stories.tsx').write_text('export default {}')
    # Act
    por_caminho = {i['caminho']: i['gerado'] for i in varrer(tmp_path)}
    # Assert
    assert por_caminho['Botao.ts'] is False
    assert por_caminho['Botao.d.ts'] is True
    assert por_caminho['Lista.stories.tsx'] is True
