# tests/test_textual.py
from lib.arvore import varrer
from lib.textual import mencoes, simbolos_de, todas_as_mencoes


def test_acha_a_classe_citada_como_string_na_rota(tmp_path):
    # Arrange — acoplamento que NENHUM grafo de import enxerga
    (tmp_path / 'app').mkdir()
    (tmp_path / 'app' / 'UserController.php').write_text('<?php class UserController {}')
    (tmp_path / 'routes.php').write_text('<?php Route::get("/u", "UserController@show");')
    # Act
    achadas = mencoes(tmp_path, 'UserController')
    # Assert
    caminhos = sorted(m['caminho'] for m in achadas)
    assert 'routes.php' in caminhos


def test_acha_mencao_em_yaml_e_sql(tmp_path):
    # Arrange
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'fila.yml').write_text('handler: App\\Pedido')
    (tmp_path / 'relatorio.sql').write_text('-- junta com Pedido')
    # Act
    caminhos = sorted(m['caminho'] for m in mencoes(tmp_path, 'Pedido'))
    # Assert
    assert caminhos == ['Pedido.php', 'fila.yml', 'relatorio.sql']


def test_informa_a_linha_da_mencao(tmp_path):
    # Arrange
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'uso.php').write_text('<?php\n\n$p = new Pedido();')
    # Act
    item = [m for m in mencoes(tmp_path, 'Pedido') if m['caminho'] == 'uso.php'][0]
    # Assert
    assert item['linha'] == 3


def test_nao_casa_pedaco_de_outra_palavra(tmp_path):
    # Arrange
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'outro.php').write_text('<?php $x = "PedidoCancelado";')
    # Act
    caminhos = [m['caminho'] for m in mencoes(tmp_path, 'Pedido')]
    # Assert — `PedidoCancelado` não é menção a `Pedido`
    assert 'outro.php' not in caminhos


def test_uma_passada_acha_varios_simbolos(tmp_path):
    # Arrange
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'Cliente.php').write_text('<?php class Cliente {}')
    (tmp_path / 'uso.php').write_text('<?php new Pedido(); new Cliente();')
    # Act
    todas = todas_as_mencoes(tmp_path, ['Pedido', 'Cliente'])
    # Assert
    assert 'uso.php' in [m['caminho'] for m in todas['Pedido']]
    assert 'uso.php' in [m['caminho'] for m in todas['Cliente']]


def test_extrai_simbolos_dos_nomes_de_arquivo(tmp_path):
    # Arrange
    (tmp_path / 'app').mkdir()
    (tmp_path / 'app' / 'UserController.php').write_text('<?php')
    (tmp_path / 'app' / 'pedido_service.py').write_text('x = 1')
    # Act
    simbolos = simbolos_de(varrer(tmp_path))
    # Assert
    assert 'UserController' in simbolos
    assert 'pedido_service' in simbolos


def test_simbolo_so_dentro_de_string_em_config_e_achado(tmp_path):
    # Arrange — caso real de projeto legado: a classe é ligada por CONFIG, não por
    # import. Nenhum arquivo importa `RelatorioJob`; ele só existe como string
    # dentro de um .ini de wiring. É exatamente o acoplamento que o grafo de
    # import perde em silêncio.
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'RelatorioJob.php').write_text('<?php class RelatorioJob {}')
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config' / 'queue.ini').write_text(
        '[fila]\nworker = "App\\\\Jobs\\\\RelatorioJob"\ntentativas = 3\n'
    )
    # Act
    achadas = mencoes(tmp_path, 'RelatorioJob')
    # Assert — o grafo textual acha a menção, e com a linha certa
    item = [m for m in achadas if m['caminho'] == 'config/queue.ini']
    assert item, 'menção dentro da string de config não foi achada'
    assert item[0]['linha'] == 2


def test_dotfile_nao_vira_simbolo(tmp_path):
    # Arrange — `Path('.env').stem` é `.env` (não ''), então `.env`, `.gitignore` e
    # companhia encabeçavam a lista alfabética e gastavam as primeiras vagas do teto
    # de símbolos procurando nome de arquivo de configuração pelo repositório todo.
    (tmp_path / '.env').write_text('APP_NAME=loja\n')
    (tmp_path / '.gitignore').write_text('.venv\n')
    (tmp_path / '.dockerignore').write_text('node_modules\n')
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    # Act
    simbolos = simbolos_de(varrer(tmp_path))
    # Assert — nenhum símbolo começa com ponto, e o símbolo legítimo continua lá
    assert [s for s in simbolos if s.startswith('.')] == []
    assert 'Pedido' in simbolos
