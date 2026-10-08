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


# ───────────────────── escolher QUAL percurso seguir ────────────────────────
# O SKILL.md declarava "a skill não detecta entrypoint" enquanto a `superficie`
# já os listava. O que faltava era usá-los para PROPOR.

def _inv(superficie, arestas):
    return {'superficie': superficie, 'imports': {'arestas': arestas}}


def test_a_entrada_que_alcanca_mais_papeis_vem_primeiro():
    """Ordena por PAPÉIS, não por arquivos: uma entrada que toca request,
    service e model é fatia vertical; uma que toca trinta modelos é listagem."""
    # Arrange — `fundo` alcança 3 modelos; `raso` alcança 2 papéis diferentes
    sup = [{'caminho': 'app/Controllers/RasoController.php', 'tipo': 'rota'},
           {'caminho': 'app/Controllers/FundoController.php', 'tipo': 'rota'}]
    arestas = (
        [{'de': 'app/Controllers/FundoController.php', 'para': f'app/Models/M{i}.php'}
         for i in range(3)]
        + [{'de': 'app/Controllers/RasoController.php', 'para': 'app/Services/S.php'},
           {'de': 'app/Services/S.php', 'para': 'app/Models/M9.php'}])
    # Act
    r = percurso.candidatos(_inv(sup, arestas))
    # Assert
    assert [c['entrada'] for c in r['candidatos']] == [
        'app/Controllers/RasoController.php', 'app/Controllers/FundoController.php']


def test_entrada_que_nao_alcanca_ninguem_e_contada_e_nao_listada():
    """Num projeto real eram 17 de 49, e a contagem mede o ponto cego: quem
    despacha por string não aparece no grafo."""
    # Arrange
    sup = [{'caminho': 'app/Controllers/MudoController.php', 'tipo': 'rota'},
           {'caminho': 'app/Controllers/VivoController.php', 'tipo': 'rota'}]
    arestas = [{'de': 'app/Controllers/VivoController.php', 'para': 'app/Models/M.php'}]
    # Act
    r = percurso.candidatos(_inv(sup, arestas))
    # Assert
    assert r['entradas'] == 2
    assert r['entradas_sem_alcance'] == 1
    assert [c['entrada'] for c in r['candidatos']] == ['app/Controllers/VivoController.php']


def test_o_candidato_leva_o_termo_da_funcionalidade():
    """Liga os dois eixos: a entrada que mais exercita o sistema costuma levar o
    nome de uma das funcionalidades do menu."""
    # Act
    r = percurso.candidatos(_inv(
        [{'caminho': 'app/Controllers/PedidoController.php', 'tipo': 'rota'}],
        [{'de': 'app/Controllers/PedidoController.php', 'para': 'app/Models/M.php'}]))
    # Assert
    assert r['candidatos'][0]['termo'] == 'pedido'


def test_a_lista_de_candidatos_tem_teto():
    # Arrange
    sup = [{'caminho': f'app/Controllers/C{i}Controller.php', 'tipo': 'rota'}
           for i in range(9)]
    arestas = [{'de': s['caminho'], 'para': f'app/Models/M{i}.php'}
               for i, s in enumerate(sup)]
    # Act / Assert
    assert len(percurso.candidatos(_inv(sup, arestas))['candidatos']) == \
        percurso.TETO_CANDIDATOS


def test_sem_superficie_nao_ha_candidato_e_o_motivo_vem_junto():
    # Act
    r = percurso.candidatos(_inv([], []))
    # Assert
    assert r['candidatos'] == []
    assert 'convenção' in r['limite']


def test_o_limite_do_grafo_sai_sempre_que_ha_candidato():
    """Sem ele o leitor conclui que o caminho acaba ali: num monorepo real
    nenhuma das 49 entradas atravessava para outro repositório, porque a
    travessia é por HTTP."""
    # Act
    r = percurso.candidatos(_inv(
        [{'caminho': 'app/Controllers/PedidoController.php', 'tipo': 'rota'}],
        [{'de': 'app/Controllers/PedidoController.php', 'para': 'app/Models/M.php'}]))
    # Assert
    assert 'HTTP' in r['limite']


def test_o_alcance_nao_entra_em_laco_com_ciclo():
    """Import circular existe, e a busca não pode rodar para sempre."""
    # Act
    r = percurso.candidatos(_inv(
        [{'caminho': 'app/Controllers/AController.php', 'tipo': 'rota'}],
        [{'de': 'app/Controllers/AController.php', 'para': 'app/Models/B.php'},
         {'de': 'app/Models/B.php', 'para': 'app/Controllers/AController.php'}]))
    # Assert
    assert r['candidatos'][0]['alcanca'] == 2
