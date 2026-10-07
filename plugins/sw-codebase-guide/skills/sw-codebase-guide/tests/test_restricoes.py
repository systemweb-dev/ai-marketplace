"""As restrições que o spec declarou verificáveis.

Elas não cabem em nenhuma task de implementação porque são sobre o CONJUNTO:
restrição que ninguém checa é restrição que ninguém cumpre.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / 'fixtures'
POLIGLOTA = FIXTURES / 'poliglota_com_codigo'


def varrer_em(projeto, destino, seed=None):
    ambiente = {'PATH': '/usr/bin:/bin'}
    if seed:
        ambiente['PYTHONHASHSEED'] = seed
    subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(destino)],
                   check=True, capture_output=True, env=ambiente)


def test_o_resolvedor_nao_conhece_nenhuma_linguagem():
    """A restrição que mantém o desenho honesto: se o resolvedor souber o que é um
    tsconfig, acrescentar a quarta linguagem deixa de custar um extrator pequeno.
    Este teste é a diferença entre a regra estar escrita e estar valendo."""
    # Arrange
    fonte = (RAIZ / 'scripts' / 'lib' / 'resolucao.py').read_text('utf-8')
    proibidos = ['python', 'javascript', 'typescript', ' php', 'vue', 'node',
                 'tsconfig', 'composer', 'psr-4', 'package.json', '.py', '.ts']
    # Act — fora de docstring e comentário, nenhum nome de linguagem
    codigo = re.sub(r'(?s)""".*?"""', '', fonte)
    codigo = '\n'.join(l.split('#')[0] for l in codigo.split('\n'))
    # Assert
    achados = [p for p in proibidos if p in codigo.lower()]
    assert not achados, f'o resolvedor passou a conhecer linguagem: {achados}'
    assert 'if linguagem' not in codigo.lower()


def test_a_fixture_poliglota_produz_aresta_nas_tres_linguagens(tmp_path):
    """Teste de determinismo que roda sobre projeto sem import nenhum não detecta
    nada — e era esse o estado da fixture antiga, que só tinha dois manifestos.
    Este teste é a guarda da guarda."""
    # Arrange / Act
    varrer_em(POLIGLOTA, tmp_path)
    imports = json.loads((tmp_path / 'inventory.json').read_text())['imports']
    # Assert
    assert set(imports['resolucao']) == {'php', 'js', 'python'}
    extensoes = {a['de'].rsplit('.', 1)[-1] for a in imports['arestas']}
    assert {'php', 'vue', 'py'} <= extensoes
    procedencias = {a['origem'] for a in imports['arestas']}
    assert {'sufixo_unico', 'base_provada'} <= procedencias, \
        'a fixture precisa exercitar também a segunda passada'


def test_mesmo_projeto_mesmo_inventario_em_processos_diferentes(tmp_path):
    """Duas chamadas dentro do mesmo pytest compartilham o seed de hash do Python e
    passariam mesmo com artefato não-determinístico. O laço antigo iterava um `set`
    de strings e concatenava arestas sem reordenar — passava por acidente porque só
    uma linguagem gerava aresta."""
    # Arrange / Act — dois PROCESSOS, com seeds de hash diferentes
    saidas = []
    for seed in ('1', '2'):
        destino = tmp_path / f'saida{seed}'
        varrer_em(POLIGLOTA, destino, seed=seed)
        saidas.append((destino / 'inventory.json').read_bytes())
    # Assert
    assert saidas[0] == saidas[1]


def test_varredura_cabe_no_orcamento(tmp_path):
    """60 s é o que REPROVA; os 5 minutos são o teto que o dono aceita, não a meta.
    O índice de sufixos é O(arquivos x profundidade) e o extrator é um passe de
    expressão por arquivo — se isto estourar, alguma coisa virou quadrática."""
    # Arrange — 600 arquivos com import, a ordem de grandeza de um projeto real
    projeto = tmp_path / 'grande'
    (projeto / 'src').mkdir(parents=True)
    for i in range(600):
        (projeto / 'src' / f'm{i}.ts').write_text(
            f"import a from './m{(i + 1) % 600}'\n"
            f"import b from '@/src/m{(i + 2) % 600}'\n")
    # Act
    inicio = time.monotonic()
    varrer_em(projeto, tmp_path / 'out')
    gasto = time.monotonic() - inicio
    # Assert
    assert gasto < 60, f'{gasto:.1f}s'


def test_o_documento_montado_nao_afirma_ausencia_de_dependentes(tmp_path):
    """A guarda `PROIBIDAS` roda dentro de `_ler_narrativa()` — ou seja, só no texto
    que o AGENTE escreve. Todos os blocos novos são gerados pelo script e passam ao
    largo dela. A restrição só vale com este teste.

    Esta armadilha já pegou duas vezes nesta skill: a pergunta gerada pela própria
    skill continha 'não é usada', e um rascunho do rodapé do ranking continha
    'nada depende'."""
    # Arrange
    sys.path.insert(0, str(RAIZ / 'scripts'))
    from montar import PROIBIDAS
    varrer_em(POLIGLOTA, tmp_path)
    subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'montar.py'),
                    '--dir', str(tmp_path)], check=True, capture_output=True)
    # Act
    guia = (tmp_path / 'guide.md').read_text('utf-8').lower()
    # Assert
    achadas = [f for f in PROIBIDAS if f in guia]
    assert not achadas, f'o documento gerado afirma ausência: {achadas}'
