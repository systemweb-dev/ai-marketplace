# tests/test_varrer.py
import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent


def rodar(projeto, saida):
    return subprocess.run(
        [sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
         '--projeto', str(projeto), '--out', str(saida)],
        capture_output=True, text=True)


def projeto_simples(raiz):
    (raiz / 'app').mkdir(parents=True, exist_ok=True)
    (raiz / 'app' / 'pedido.py').write_text('class Pedido: pass')
    (raiz / 'rotas.py').write_text('ROTAS = {"/p": "pedido@listar"}')
    (raiz / 'pyproject.toml').write_text('[project]\nname = "loja"')
    return raiz


def test_grava_inventario_com_as_secoes_esperadas(tmp_path):
    # Arrange
    projeto, saida = projeto_simples(tmp_path / 'p'), tmp_path / 'out'
    # Act
    r = rodar(projeto, saida)
    # Assert
    assert r.returncode == 0, r.stderr
    inv = json.loads((saida / 'inventory.json').read_text())
    assert set(inv) >= {'stacks', 'arvore', 'historia', 'imports', 'mencoes',
                        'superficie', 'ambiente', 'gerado_em_versao'}
    assert inv['stacks'][0]['stack'] == 'python'


def test_varrer_so_escreve_em_docs_project(tmp_path):
    # Arrange
    projeto = projeto_simples(tmp_path / 'p')
    saida = tmp_path / 'out'
    antes = {p for p in projeto.rglob('*')}
    # Act
    rodar(projeto, saida)
    # Assert — o projeto auditado não ganha nem perde arquivo
    assert {p for p in projeto.rglob('*')} == antes
    assert sorted(p.name for p in saida.iterdir()) == ['inventory.json']


def test_chave_de_env_entra_e_valor_nao(tmp_path):
    # Arrange
    projeto = projeto_simples(tmp_path / 'p')
    (projeto / '.env').write_text('DB_PASSWORD=sup3rs3cr3t\nAPP_NAME=loja\n')
    saida = tmp_path / 'out'
    # Act
    rodar(projeto, saida)
    inv = json.loads((saida / 'inventory.json').read_text())
    # Assert — o par POSITIVO primeiro: a informação útil TEM que chegar.
    # Sem ele o teste passaria com o inventário vazio, que foi o defeito da versão
    # anterior — o valor não tinha por onde chegar, então nada era provado.
    assert inv['ambiente']['.env'] == ['APP_NAME', 'DB_PASSWORD']
    # e o valor não pode estar em NENHUM arquivo gravado
    for arquivo in saida.rglob('*'):
        if arquivo.is_file():
            assert 'sup3rs3cr3t' not in arquivo.read_text('utf-8', 'replace'), arquivo


def test_inventario_e_json_valido_com_simbolo_que_parece_segredo(tmp_path):
    # Arrange — `AuthController` casa com o padrão de nome de segredo
    projeto = projeto_simples(tmp_path / 'p')
    (projeto / 'app' / 'AuthController.py').write_text('class AuthController: pass')
    (projeto / 'app' / 'TokenService.py').write_text('class TokenService: pass')
    saida = tmp_path / 'out'
    # Act
    rodar(projeto, saida)
    # Assert — redigir o JSON pronto transformava `"AuthController": [` em
    # `"AuthController": ***` e quebrava o arquivo
    inv = json.loads((saida / 'inventory.json').read_text())
    caminhos = [a['caminho'] for a in inv['arvore']]
    assert 'app/AuthController.py' in caminhos


def test_inventario_nao_carrega_carimbo_de_tempo(tmp_path):
    # Arrange — carimbo de tempo quebraria a idempotência (Task 10)
    projeto = projeto_simples(tmp_path / 'p')
    # Act
    rodar(projeto, tmp_path / 'a')
    rodar(projeto, tmp_path / 'b')
    # Assert
    assert (tmp_path / 'a' / 'inventory.json').read_bytes() == \
           (tmp_path / 'b' / 'inventory.json').read_bytes()
