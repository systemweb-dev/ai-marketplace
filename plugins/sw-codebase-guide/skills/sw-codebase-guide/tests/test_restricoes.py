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
    guia = (tmp_path / 'guide.md').read_text('utf-8')
    # Assert
    achadas = [f for f in PROIBIDAS if f in guia.lower()]
    assert not achadas, f'o documento gerado afirma ausência: {achadas}'


ATRIBUICAO = re.compile(r'— \*\*[^*]+\*\*, \d{4}-\d{2}-\d{2}')


def test_frase_de_ausencia_so_vale_com_NOME_e_DATA_ao_lado(tmp_path):
    """A formulação exata da promessa: **a skill** nunca afirma ausência de
    dependentes, porque o grafo não pode provar isso. Uma **pessoa** pode — ela sabe
    o que o grafo não vê, e é justamente para isso que o `knowledge.toml` existe.

    O que separa as duas é a atribuição. "não é usado em lugar nenhum" escrito pelo
    script é falsa confiança; a mesma frase com `— **ana**, 2026-10-07` ao lado é
    testemunho, e o leitor sabe a quem perguntar se discordar.

    Proibir a frase na resposta humana seria absurdo — "removemos o último chamador
    ano passado, isto está morto" é exatamente o conhecimento que o código não tem.
    """
    # Arrange
    sys.path.insert(0, str(RAIZ / 'scripts'))
    from gravar import gravar
    from montar import PROIBIDAS
    varrer_em(POLIGLOTA, tmp_path)
    gravar(tmp_path, sobre='servico/apoio.py', pergunta='pode apagar?',
           resposta='sim, não é usado desde a migração', quem='ana',
           quando='2026-10-07')
    subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'montar.py'),
                    '--dir', str(tmp_path)], check=True, capture_output=True)
    # Act
    guia = (tmp_path / 'guide.md').read_text('utf-8')
    suspeitas = [l for l in guia.split('\n')
                 if any(f in l.lower() for f in PROIBIDAS)]
    # Assert
    assert suspeitas, 'o fixture precisa produzir a frase, senão o teste não prova nada'
    for linha in suspeitas:
        assert ATRIBUICAO.search(linha), f'frase de ausência sem nome e data: {linha}'


def test_o_rotulo_de_confianca_e_escrito_sempre_igual(tmp_path):
    """O documento usava `[deducao]` em dois blocos e `[dedução]` num terceiro. São
    o mesmo nível de confiança, e grafia que varia faz o leitor procurar diferença
    onde não há."""
    # Arrange
    varrer_em(POLIGLOTA, tmp_path)
    subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'montar.py'),
                    '--dir', str(tmp_path)], check=True, capture_output=True)
    # Act
    guia = (tmp_path / 'guide.md').read_text('utf-8')
    # Assert
    assert '[deducao]' not in guia, 'o rótulo sai acentuado'
