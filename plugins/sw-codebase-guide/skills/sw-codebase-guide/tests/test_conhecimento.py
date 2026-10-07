"""O conhecimento humano: o único arquivo da skill que não se regenera."""
import subprocess
import sys
from pathlib import Path

import pytest

from lib import conhecimento

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
from gravar import gravar  # noqa: E402


def test_sem_arquivo_nao_e_erro(tmp_path):
    """A grande maioria dos projetos nunca vai ter um. Ausência é o normal."""
    # Act / Assert
    assert conhecimento.ler(tmp_path) == []


def test_responder_de_novo_acrescenta_e_vence_a_mais_recente(tmp_path):
    """Corrigir uma resposta não pode exigir editar o passado à mão. O arquivo
    guarda o histórico inteiro; quem lê fica com a última de cada pergunta."""
    # Arrange
    gravar(tmp_path, 'app/x.py', 'ainda é usado?', 'sim, pelo cron', 'ana',
           quando='2026-01-01')
    gravar(tmp_path, 'app/x.py', 'ainda é usado?', 'não, o cron saiu', 'bruno',
           quando='2026-06-01')
    # Act
    respostas = conhecimento.ler(tmp_path)
    # Assert
    assert len(respostas) == 1
    assert respostas[0]['resposta'] == 'não, o cron saiu'
    assert respostas[0]['quem'] == 'bruno'
    # e o histórico continua no arquivo, para dar para ver o que mudou de ideia
    assert 'pelo cron' in (tmp_path / 'knowledge.toml').read_text()


def test_resposta_sem_quem_e_recusada(tmp_path):
    """Resposta sem nome não dá para conferir depois, e é o nome que a torna um
    nível de confiança em vez de uma frase solta no documento."""
    # Act / Assert
    with pytest.raises(ValueError, match='quem'):
        gravar(tmp_path, 'app/x.py', 'usado?', 'sim', '   ')


def test_bloco_quebrado_falha_na_LEITURA_com_o_numero_do_bloco(tmp_path):
    """Este arquivo não se regenera: formato quebrado aqui é informação perdida, e
    o erro precisa dizer QUAL bloco para dar para consertar à mão."""
    # Arrange
    (tmp_path / 'knowledge.toml').write_text(
        '[[resposta]]\nsobre = "a.py"\npergunta = "x?"\nresposta = "sim"\n'
        'quem = "ana"\nquando = "2026-01-01"\n\n'
        '[[resposta]]\nsobre = "b.py"\npergunta = "y?"\nresposta = "sim"\n')
    # Act / Assert
    with pytest.raises(ValueError, match='resposta 2'):
        conhecimento.ler(tmp_path)


def test_resposta_envelhece_quando_o_arquivo_muda_depois(tmp_path):
    """Invalidação por EVIDÊNCIA, não por cronômetro: "este controller é chamado
    pelo cron" vale enquanto ninguém mexe nele. Mexeu, a resposta vira suspeita —
    não falsa, suspeita — e o documento diz isso em vez de repeti-la."""
    # Arrange
    gravar(tmp_path, 'app/x.py', 'usado?', 'sim, pelo cron', 'ana', quando='2026-01-01')
    gravar(tmp_path, 'app/y.py', 'usado?', 'sim', 'ana', quando='2026-01-01')
    mudancas = {'app/x.py': {'ultima': '2026-08-01T00:00:00+00:00'},
                'app/y.py': {'ultima': '2025-01-01T00:00:00+00:00'}}
    # Act
    por_sobre = {r['sobre']: r for r in
                 conhecimento.envelhecidas(conhecimento.ler(tmp_path), mudancas)}
    # Assert
    assert por_sobre['app/x.py']['mudou_depois'] == '2026-08-01'
    assert por_sobre['app/y.py']['mudou_depois'] is None


def test_o_arquivo_nasce_dizendo_que_nao_se_regenera(tmp_path):
    """Quem abre o arquivo precisa saber, na primeira linha, que apagá-lo perde
    informação que o repositório não tem."""
    # Act
    gravar(tmp_path, 'app/x.py', 'usado?', 'sim', 'ana')
    # Assert
    assert 'não se regenera' in (tmp_path / 'knowledge.toml').read_text()


def test_aspas_na_resposta_nao_quebram_o_toml(tmp_path):
    """Resposta é texto livre de gente, e gente escreve aspas."""
    # Act
    gravar(tmp_path, 'app/x.py', 'usado?', 'sim, o job "diário" chama', 'ana')
    # Assert
    assert conhecimento.ler(tmp_path)[0]['resposta'] == 'sim, o job "diário" chama'


def test_o_cli_grava_e_imprime_o_caminho(tmp_path):
    # Act
    r = subprocess.run(
        [sys.executable, str(RAIZ / 'scripts' / 'gravar.py'), '--dir', str(tmp_path),
         '--sobre', 'app/x.py', '--pergunta', 'usado?', '--resposta', 'sim',
         '--quem', 'ana'], capture_output=True, text=True)
    # Assert
    assert r.returncode == 0, r.stderr
    assert 'knowledge.toml' in r.stdout


def test_resposta_recusada_nao_deixa_rastro_no_arquivo(tmp_path):
    """Este arquivo não se regenera: um bloco quebrado dentro dele torna a
    informação de todo mundo inacessível. Anexar e validar depois deixava
    exatamente isso quando a validação falhava."""
    # Arrange
    gravar(tmp_path, 'app/x.py', 'usado?', 'sim', 'ana', quando='2026-01-01')
    antes = (tmp_path / 'knowledge.toml').read_text()
    # Act
    with pytest.raises(ValueError):
        gravar(tmp_path, 'app/y.py', 'usado?', 'sim', '')
    # Assert
    assert (tmp_path / 'knowledge.toml').read_text() == antes


def test_resposta_com_quebra_de_linha_e_recusada_em_vez_de_corromper(tmp_path):
    """Texto de gente chega com surpresa. O que não vira TOML válido é recusado
    ANTES de tocar o arquivo, com o erro dizendo o que aconteceu."""
    # Arrange
    gravar(tmp_path, 'app/x.py', 'usado?', 'sim', 'ana', quando='2026-01-01')
    antes = (tmp_path / 'knowledge.toml').read_text()
    # Act / Assert
    with pytest.raises(ValueError, match='TOML'):
        gravar(tmp_path, 'app/y.py', 'usado?', 'sim\nfalso = 1', 'ana')
    assert (tmp_path / 'knowledge.toml').read_text() == antes
