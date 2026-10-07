# tests/test_historia.py
import subprocess
from lib.historia import historico, MIN_COMMITS, TETO_ARQUIVOS


def git(raiz, *args):
    subprocess.run(['git', *args], cwd=raiz, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def repo(tmp_path, commits):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'teste@exemplo.local')
    git(tmp_path, 'config', 'user.name', 'Teste')
    for i in range(commits):
        (tmp_path / 'a.py').write_text(f'x = {i}')
        (tmp_path / 'b.py').write_text(f'y = {i}')
        git(tmp_path, 'add', '-A')
        git(tmp_path, 'commit', '-q', '-m', f'c{i}')
    return tmp_path


def test_sem_repositorio_git_vira_lacuna_com_motivo(tmp_path):
    # Arrange
    (tmp_path / 'a.py').write_text('x = 1')
    # Act
    h = historico(tmp_path)
    # Assert
    assert h['co_mudanca'] == []
    assert h['lacuna'] is not None
    assert 'git' in h['lacuna'].lower()


def test_um_commit_so_vira_lacuna_dizendo_quantos(tmp_path):
    # Arrange
    raiz = repo(tmp_path, 1)
    # Act
    h = historico(raiz)
    # Assert — amostra pequena demais é ruído; o motivo diz o número real
    assert h['commits'] == 1
    assert h['co_mudanca'] == []
    assert h['lacuna'] is not None
    assert '1' in h['lacuna'] and str(MIN_COMMITS) in h['lacuna']


def test_git_acima_do_projeto_nao_e_usado(tmp_path):
    # Arrange — repositório na raiz, projeto auditado num subdiretório
    repo(tmp_path, MIN_COMMITS + 5)
    sub = tmp_path / 'modulo'
    sub.mkdir()
    (sub / 'c.py').write_text('z = 1')
    # Act
    h = historico(sub)
    # Assert — o histórico do pai não pode virar co-mudança do filho
    assert h['co_mudanca'] == []
    assert h['lacuna'] is not None
    assert 'acima' in h['lacuna']


def test_repositorio_sem_commit_diz_isso(tmp_path):
    # Arrange
    git(tmp_path, 'init', '-q')
    # Act
    h = historico(tmp_path)
    # Assert — "não há repositório git aqui" seria falso
    assert 'commit' in h['lacuna']


def test_com_amostra_suficiente_calcula_co_mudanca(tmp_path):
    # Arrange — a.py e b.py mudam SEMPRE juntos
    raiz = repo(tmp_path, MIN_COMMITS + 5)
    # Act
    h = historico(raiz)
    # Assert
    assert h['lacuna'] is None
    pares = {tuple(sorted(c['arquivos'])): c['vezes'] for c in h['co_mudanca']}
    assert pares[('a.py', 'b.py')] >= MIN_COMMITS


def test_commit_gigante_e_descartado(tmp_path):
    # Arrange
    raiz = repo(tmp_path, MIN_COMMITS + 1)
    for i in range(TETO_ARQUIVOS + 10):          # um "reformat geral"
        (raiz / f'lixo{i}.py').write_text('# formatado')
    git(raiz, 'add', '-A')
    git(raiz, 'commit', '-q', '-m', 'reformat geral')
    # Act
    h = historico(raiz)
    # Assert — o reformat não pode criar co-mudança entre arquivos sem relação
    pares = {tuple(sorted(c['arquivos'])) for c in h['co_mudanca']}
    assert ('lixo0.py', 'lixo1.py') not in pares
    assert h['commits_descartados'] == 1


def test_subrepos_um_nivel_abaixo_sao_encontrados(tmp_path):
    # Arrange — monorepo por justaposição: a raiz não tem git, os filhos têm.
    # Num projeto real eram 782 commits em 4 sub-repos, e o documento afirmava
    # "não há repositório git aqui".
    for nome in ('api', 'web'):
        sub = tmp_path / nome
        sub.mkdir()
        repo(sub, MIN_COMMITS + 2)
    # Act
    h = historico(tmp_path)
    # Assert
    assert h['commits'] == 2 * (MIN_COMMITS + 2)
    assert {s['caminho'] for s in h['subrepos']} == {'api', 'web'}
    assert 'sub-repositórios' in h['lacuna']
    # o caminho carrega o sub-repo, senão `a.py` de dois repos vira o mesmo arquivo
    assert all(c['arquivos'][0].startswith(('api/', 'web/')) for c in h['co_mudanca'])


def test_raiz_com_git_proprio_ignora_os_filhos(tmp_path):
    # Arrange — quando a raiz É repositório, o histórico dela basta
    repo(tmp_path, MIN_COMMITS + 2)
    sub = tmp_path / 'filho'
    sub.mkdir()
    repo(sub, MIN_COMMITS + 2)
    # Act
    h = historico(tmp_path)
    # Assert
    assert h['lacuna'] is None
    assert 'subrepos' not in h
