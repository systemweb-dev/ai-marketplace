"""O percurso em passos — a camada, a evidência impressa e a fronteira derivada.

O defeito que estes testes existem para não deixar voltar: a `evidencia` do
percurso era validada contra o projeto, linha por linha, e NUNCA chegava ao
documento. Quem lia recebia a história e ia caçar os arquivos no relatório
técnico — que é o trabalho que o documento existe para poupar.
"""
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))

from lib import percurso  # noqa: E402
from lib.pagina import bloco_percurso  # noqa: E402

FIXTURES = Path(__file__).parent / 'fixtures'


def montar(tmp_path, toml):
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(FIXTURES / 'acoplamento_invisivel'),
                    '--out', str(tmp_path)], check=True, capture_output=True)
    (tmp_path / 'interpretation.toml').write_text(toml)
    return subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                           '--dir', str(tmp_path)], capture_output=True, text=True)


def passo(ordem, onde, texto, evidencia='["rotas.py"]', saltos='[]'):
    return (f'[[narrativa]]\nparte = "percurso"\nordem = {ordem}\n'
            f'onde = "{onde}"\ntexto = "{texto}"\n'
            f'evidencia = {evidencia}\nsaltos = {saltos}\n\n')


# ───────────────────────── a camada é obrigatória e fechada ──────────────────

def test_camada_inventada_e_recusada_com_a_lista(tmp_path):
    """Camada livre reabriria a prosa pela porta dos fundos: `onde = "na regra
    de negócio"` passaria, e a trilha não teria onde pôr o passo."""
    # Act
    r = montar(tmp_path, passo(1, 'regra de negócio', 'O pedido entra'))
    # Assert
    saida = r.stderr + r.stdout
    assert r.returncode == 2
    assert 'regra de negócio' in saida
    for camada in percurso.CAMADAS:
        assert camada in saida, f'a recusa precisa ensinar as camadas: falta {camada}'
    assert 'Traceback' not in r.stderr


def test_passo_sem_camada_e_recusado(tmp_path):
    # Act
    r = montar(tmp_path, '[[narrativa]]\nparte = "percurso"\nordem = 1\n'
                         'texto = "O pedido entra"\nevidencia = ["app.py"]\nsaltos = []\n')
    # Assert
    assert r.returncode == 2
    assert 'onde' in (r.stderr + r.stdout)
    assert 'Traceback' not in r.stderr


# ───────────────────────── a travessia é derivada, não declarada ─────────────

def test_a_fronteira_nasce_da_camada_mudar():
    # Arrange
    narrativa = [
        {'parte': 'percurso', 'ordem': 1, 'onde': 'navegador', 'texto': 'a'},
        {'parte': 'percurso', 'ordem': 2, 'onde': 'servidor', 'texto': 'b'},
        {'parte': 'percurso', 'ordem': 3, 'onde': 'servidor', 'texto': 'c'},
        {'parte': 'percurso', 'ordem': 4, 'onde': 'banco', 'texto': 'd'},
    ]
    # Act
    passos = percurso.em_passos(narrativa)
    # Assert
    assert [p['atravessa'] for p in passos] == [
        None, ('navegador', 'servidor'), None, ('servidor', 'banco')]
    assert percurso.travessias(passos) == 2


def test_o_primeiro_passo_nunca_atravessa():
    """Entrar pelo navegador não é atravessar fronteira — é começar. A marca
    antes do primeiro passo diria ao leitor que ele perdeu alguma coisa."""
    # Act
    passos = percurso.em_passos(
        [{'parte': 'percurso', 'ordem': 1, 'onde': 'fila', 'texto': 'a'}])
    # Assert
    assert passos[0]['atravessa'] is None
    assert percurso.travessias(passos) == 0


def test_as_camadas_saem_na_ordem_do_caminho_nao_na_de_aparicao():
    # Arrange — o percurso começa no banco e só depois passa pelo navegador
    narrativa = [
        {'parte': 'percurso', 'ordem': 1, 'onde': 'banco', 'texto': 'a'},
        {'parte': 'percurso', 'ordem': 2, 'onde': 'navegador', 'texto': 'b'},
    ]
    # Act / Assert
    assert percurso.camadas_usadas(narrativa and percurso.em_passos(narrativa)) == [
        'navegador', 'banco']


# ───────────────────────── a evidência chega aos dois documentos ─────────────

def test_o_arquivo_de_cada_passo_aparece_no_documento_humano(tmp_path):
    """O defeito original: `evidencia` conferida contra o projeto e invisível."""
    # Act
    r = montar(tmp_path,
               passo(1, 'navegador', 'A tela chama', '["rotas.py"]')
               + passo(2, 'banco', 'O serviço grava', '["container.py"]'))
    # Assert
    assert r.returncode == 0, r.stderr
    leia_me = (tmp_path / 'leia-me.md').read_text()
    assert '`rotas.py`' in leia_me
    assert '`container.py`' in leia_me


def test_o_arquivo_de_cada_passo_aparece_no_html():
    # Arrange
    narrativa = [
        {'parte': 'percurso', 'ordem': 1, 'onde': 'navegador',
         'texto': 'A tela chama', 'evidencia': ['app.py:12'], 'saltos': []},
    ]
    # Act
    html = bloco_percurso(narrativa)
    # Assert
    assert 'app.py:12' in html
    assert 'pc-ev' in html


def test_o_html_marca_a_fronteira_onde_ela_acontece():
    # Arrange
    narrativa = [
        {'parte': 'percurso', 'ordem': 1, 'onde': 'navegador', 'texto': 'A tela chama',
         'evidencia': ['app.py'], 'saltos': []},
        {'parte': 'percurso', 'ordem': 2, 'onde': 'servidor', 'texto': 'A API recebe',
         'evidencia': ['lib/core.py'], 'saltos': []},
    ]
    # Act
    html = bloco_percurso(narrativa)
    # Assert
    assert 'pc-fronteira' in html
    assert 'navegador → servidor' in html
    # a fronteira vem ANTES do passo que ela abre, não depois do que a fecha
    assert html.index('pc-fronteira') < html.index('A API recebe')


def test_o_subtitulo_conta_passos_camadas_e_fronteiras():
    """Oito passos em duas camadas é um sistema; oito em cinco é outro — e é a
    conta que o leitor não faria sozinho folheando."""
    # Arrange
    narrativa = [
        {'parte': 'percurso', 'ordem': i, 'onde': onde, 'texto': f'passo {i}',
         'evidencia': ['app.py'], 'saltos': []}
        for i, onde in enumerate(('navegador', 'servidor', 'servidor', 'banco'), 1)
    ]
    # Act
    html = bloco_percurso(narrativa)
    # Assert
    assert '4 passos' in html
    assert '3 camadas' in html
    assert '2 fronteiras' in html


def test_uma_fronteira_so_sai_no_singular():
    # Arrange
    narrativa = [
        {'parte': 'percurso', 'ordem': 1, 'onde': 'navegador', 'texto': 'a',
         'evidencia': ['app.py'], 'saltos': []},
        {'parte': 'percurso', 'ordem': 2, 'onde': 'servidor', 'texto': 'b',
         'evidencia': ['app.py'], 'saltos': []},
    ]
    # Act / Assert
    assert '1 fronteira ' in bloco_percurso(narrativa)


def test_o_salto_continua_no_passo_a_que_pertence():
    """Regra antiga que a mudança de layout não pode derrubar: salto escondido
    numa nota de rodapé é o erro mais caro que este documento pode cometer."""
    # Arrange
    narrativa = [
        {'parte': 'percurso', 'ordem': 1, 'onde': 'navegador', 'texto': 'A tela chama',
         'evidencia': ['app.py'], 'saltos': []},
        {'parte': 'percurso', 'ordem': 2, 'onde': 'banco', 'texto': 'O serviço grava',
         'evidencia': ['lib/core.py'], 'saltos': ['o que o gatilho faz depois']},
    ]
    # Act
    html = bloco_percurso(narrativa)
    # Assert — o salto está dentro do corpo do passo 2, não no rodapé do bloco
    corpo2 = html[html.index('O serviço grava'):]
    assert 'o que o gatilho faz depois' in corpo2
    assert 'Sem saltos' not in html


def test_percurso_inteiro_sem_salto_declara_isso_uma_vez_so():
    # Arrange
    narrativa = [
        {'parte': 'percurso', 'ordem': i, 'onde': 'servidor', 'texto': f'passo {i}',
         'evidencia': ['app.py'], 'saltos': []} for i in (1, 2, 3)
    ]
    # Act
    html = bloco_percurso(narrativa)
    # Assert
    assert html.count('Sem saltos') == 1


def test_a_camada_de_cada_passo_aparece_no_markdown(tmp_path):
    # Act
    r = montar(tmp_path,
               passo(1, 'navegador', 'A tela chama')
               + passo(2, 'fila', 'O job sai por e-mail'))
    # Assert
    assert r.returncode == 0, r.stderr
    leia_me = (tmp_path / 'leia-me.md').read_text()
    assert '**1 · navegador**' in leia_me
    assert '**2 · fila**' in leia_me
    assert 'navegador → fila' in leia_me
