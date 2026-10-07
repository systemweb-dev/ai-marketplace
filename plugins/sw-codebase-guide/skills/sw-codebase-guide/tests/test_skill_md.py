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
    # Act
    texto = SKILL.read_text('utf-8').lower()
    # Assert — os não-objetivos do spec precisam estar escritos para o agente
    assert 'não altera' in texto
    assert 'não avalia qualidade' in texto


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
