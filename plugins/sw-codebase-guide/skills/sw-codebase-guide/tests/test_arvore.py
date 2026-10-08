# tests/test_arvore.py
from lib.arvore import linhas_por_arquivo, varrer


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


# ───────────────────── quantas linhas tem cada arquivo ───────────────────────
# A guarda de evidência confere o ARQUIVO citado desde sempre, e a LINHA nunca:
# `app/Pedido.php:999999` atravessava intacto. Conferir a linha exige o número no
# inventário, porque o `montar.py` só recebe `--dir` — ele nunca vê o projeto em
# disco, e é essa ignorância que o torna reprodutível.


def test_conta_a_ultima_linha_mesmo_sem_quebra_no_fim(tmp_path):
    """Contar `\\n` subestima em um o arquivo que não termina em quebra — e o erro
    cai justamente na ÚLTIMA linha, a mais citada quando alguém aponta o fim de uma
    função. Recusar a citação correta é pior que não conferir."""
    # Arrange
    (tmp_path / 'com.py').write_text('a = 1\nb = 2\n')
    (tmp_path / 'sem.py').write_text('a = 1\nb = 2')
    # Act
    linhas = linhas_por_arquivo(tmp_path, varrer(tmp_path))
    # Assert
    assert linhas['com.py'] == 2
    assert linhas['sem.py'] == 2


def test_arquivo_vazio_nao_tem_linha_nenhuma(tmp_path):
    # Arrange
    (tmp_path / 'vazio.py').write_text('')
    # Act
    linhas = linhas_por_arquivo(tmp_path, varrer(tmp_path))
    # Assert — zero é a medida certa aqui: o arquivo existe e não tem linha
    assert linhas['vazio.py'] == 0


def test_binario_fica_sem_contagem(tmp_path):
    """Contar `\\n` num PNG dá um número, e número que não quer dizer nada é pior
    que ausência: a guarda o usaria para recusar uma citação."""
    # Arrange
    (tmp_path / 'logo.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'\n' * 40)
    (tmp_path / 'app.py').write_text('x = 1\n')
    # Act
    linhas = linhas_por_arquivo(tmp_path, varrer(tmp_path))
    # Assert
    assert 'logo.png' not in linhas
    assert linhas['app.py'] == 1


def test_arquivo_acima_do_teto_nao_e_lido(tmp_path):
    """O teto existe para a varredura não ler um dump de 40 MB. Contar linha dele
    desfaria a economia — e a ausência é honesta: não foi apurado."""
    # Arrange
    (tmp_path / 'dump.sql').write_text('insert\n' * 100)
    # Act
    itens = varrer(tmp_path, teto_bytes=10)
    linhas = linhas_por_arquivo(tmp_path, itens)
    # Assert
    assert itens[0]['acima_do_teto'] is True
    assert linhas == {}


def test_a_prosa_conta_porque_e_o_que_mais_se_cita(tmp_path):
    """`README.md:12` é a citação mais comum do documento inteiro — markdown não é
    código para o bloco de "arquivos maiores", mas é fonte de evidência."""
    # Arrange
    (tmp_path / 'README.md').write_text('# T\n\numa linha\n')
    # Act
    linhas = linhas_por_arquivo(tmp_path, varrer(tmp_path))
    # Assert
    assert linhas['README.md'] == 3


def test_dotfile_de_configuracao_conta(tmp_path):
    """`config` está em `ATIVOS` porque dotfile não é CÓDIGO — e a primeira versão
    da contagem reusou esse conjunto, deixando `.env.example` e 508 SVGs sem
    contagem num projeto real. "Não é código" e "não é texto" são perguntas
    diferentes, e `.env.example:12` é citação legítima."""
    # Arrange
    (tmp_path / '.env.example').write_text('A=1\nB=2\nC=3\n')
    (tmp_path / 'icone.svg').write_text('<svg>\n</svg>\n')
    (tmp_path / 'foto.png').write_bytes(b'\x89PNG\n\n')
    # Act
    linhas = linhas_por_arquivo(tmp_path, varrer(tmp_path))
    # Assert
    assert linhas['.env.example'] == 3
    assert linhas['icone.svg'] == 2
    assert 'foto.png' not in linhas
