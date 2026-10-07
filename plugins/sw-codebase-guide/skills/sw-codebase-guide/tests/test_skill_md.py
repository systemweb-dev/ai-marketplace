from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / 'SKILL.md'


def test_frontmatter_tem_nome_igual_ao_diretorio():
    # Arrange
    texto = SKILL.read_text('utf-8')
    # Act
    linhas = texto.split('\n')
    # Assert
    assert linhas[0] == '---'
    assert 'name: sw-codebase-guide' in texto
    assert SKILL.parent.name == 'sw-codebase-guide'


def test_documenta_os_dois_comandos_com_o_caminho_certo():
    # Act
    texto = SKILL.read_text('utf-8')
    # Assert
    assert 'scripts/varrer.py' in texto
    assert 'scripts/montar.py' in texto
    assert 'docs/project/' in texto


def test_declara_o_que_nao_faz():
    """O não-objetivo "não avalia qualidade" valeu até a v0.3.0 e saiu na v0.4.0: o
    dono decidiu que ele vale para o relatório técnico, não para o produto todo.
    O que entrou no lugar é mais estreito e mais verificável — a skill opina, mas
    **nota não existe**, porque número único vira meta e meta vira teatro."""
    # Act
    texto = SKILL.read_text('utf-8').lower()
    # Assert — os não-objetivos precisam estar escritos para o agente
    assert 'não altera' in texto
    assert 'nota não existe' in texto
    assert 'limiar escrito' in texto


def test_pergunta_antes_de_gravar_no_repositorio_do_projeto():
    # Arrange — a skill ESCREVE num projeto de terceiro. A decisão fundante do spec
    # foi "não entrevistar para descobrir o sistema", não "nunca pedir autorização".
    texto = SKILL.read_text('utf-8')
    # Act / Assert
    assert 'AskUserQuestion' in texto
    assert 'Confirmar onde grava' in texto
    assert 'antes de escrever' in texto.lower()


def test_a_regra_distingue_autorizacao_de_preguica():
    # Arrange — sem esta distinção a skill volta a entrevistar quem não sabe responder
    texto = SKILL.read_text('utf-8').lower()
    # Act / Assert
    assert 'não pergunte o que o código responde' in texto
    assert 'decisão e autorização' in texto


def test_documenta_a_pergunta_de_escopo():
    # Arrange
    texto = SKILL.read_text('utf-8')
    # Act / Assert
    assert '--areas' in texto
    assert '--area' in texto
    assert 'escopo' in texto.lower()


def test_documenta_os_dois_documentos():
    # Act
    texto = SKILL.read_text('utf-8')
    # Assert
    assert 'leia-me.md' in texto
    assert 'guide.md' in texto


def test_documenta_o_bloco_narrativa_e_as_guardas():
    # Act
    texto = SKILL.read_text('utf-8').lower()
    # Assert
    assert '[[narrativa]]' in texto
    assert 'trecho' in texto and 'fonte' in texto
    assert 'saltos' in texto


def test_o_rotulo_do_menu_de_escopo_e_descritivo():
    # Arrange — rótulo semântico ("funil · rota do App Router") é a afirmação que a
    # skill não consegue provar, e aqui ela decidiria o escopo dos dois documentos
    texto = SKILL.read_text('utf-8').lower()
    # Assert
    assert 'descritivo' in texto and 'semântico' in texto


def test_a_lista_de_secoes_bate_com_o_que_o_varrer_grava():
    """O `SKILL.md` anunciava "oito seções" quando o inventário já tinha doze — e é
    por esta lista que o agente decide o que vai achar no arquivo. Documentação que
    descreve uma versão anterior do próprio código é pior que documentação nenhuma."""
    # Arrange
    import json
    import subprocess
    import sys
    import tempfile
    raiz = SKILL.parent
    texto = SKILL.read_text('utf-8')
    # Act — varre a própria fixture e compara com o que está escrito
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(raiz / 'scripts' / 'varrer.py'),
                        '--projeto', str(raiz / 'tests' / 'fixtures' / 'acoplamento_invisivel'),
                        '--out', tmp], check=True, capture_output=True)
        secoes = set(json.loads(Path(tmp, 'inventory.json').read_text()))
    # Assert
    faltando = [s for s in secoes if f'`{s}`' not in texto]
    assert not faltando, f'seções que o inventário grava e o SKILL.md não cita: {faltando}'
