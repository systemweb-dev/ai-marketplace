import os
import subprocess
from datetime import datetime, timedelta, timezone

from lib.historia import retrato


def git(raiz, *args, quando=None):
    env = None
    if quando:
        import os
        env = dict(os.environ, GIT_AUTHOR_DATE=quando, GIT_COMMITTER_DATE=quando)
    subprocess.run(['git', *args], cwd=raiz, check=True, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def repo(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'a@exemplo.local')
    git(tmp_path, 'config', 'user.name', 'Autor A')
    return tmp_path


def test_conta_autores_distintos(tmp_path):
    # Arrange — o fator ônibus é o número que decide se vale pegar o projeto
    p = repo(tmp_path / 'p')
    for i, (nome, email) in enumerate([('Autor A', 'a@exemplo.local'),
                                       ('Autor B', 'b@exemplo.local'),
                                       ('Autor A', 'a@exemplo.local')]):
        git(p, 'config', 'user.name', nome)
        git(p, 'config', 'user.email', email)
        (p / f'{i}.py').write_text('x = 1')
        git(p, 'add', '-A')
        git(p, 'commit', '-q', '-m', f'c{i}')
    # Act / Assert
    assert retrato(p)['autores'] == 2


def test_mede_a_idade_e_o_tempo_parado(tmp_path):
    # Arrange — primeiro commit há 10 semanas, último há 3
    p = repo(tmp_path / 'p')
    agora = datetime.now(timezone.utc)
    for semanas in (10, 3):
        quando = (agora - timedelta(weeks=semanas)).isoformat()
        (p / f'{semanas}.py').write_text('x = 1')
        git(p, 'add', '-A')
        git(p, 'commit', '-q', '-m', f'c{semanas}', quando=quando)
    # Act
    r = retrato(p)
    # Assert — 7 semanas de vida, 3 paradas
    assert r['semanas_de_vida'] == 7
    assert r['semanas_parado'] == 3
    assert r['primeiro_commit'].startswith(str((agora - timedelta(weeks=10)).year))


def test_sem_git_devolve_lacuna_com_motivo(tmp_path):
    # Arrange — um terço dos projetos testados não tem git na raiz
    p = tmp_path / 'sem'
    p.mkdir()
    # Act
    r = retrato(p)
    # Assert — "não apurado" com motivo, nunca zero: zero se lê como "um autor só"
    assert r['autores'] is None
    assert r['lacuna']
    assert 'git' in r['lacuna']


def test_ignora_repo_acima(tmp_path):
    # Arrange — a MESMA guarda das outras consultas: `git log` sobe a árvore, e sem
    # ela o retrato de um subdiretório sairia com os autores do repositório de cima
    p = repo(tmp_path / 'p')
    (p / 'a.py').write_text('x = 1')
    git(p, 'add', '-A')
    git(p, 'commit', '-q', '-m', 'c')
    sub = p / 'sub'
    sub.mkdir()
    # Act
    r = retrato(sub)
    # Assert
    assert r['autores'] is None
    assert 'acima' in r['lacuna']


def test_retrato_de_monorepo_por_justaposicao(tmp_path):
    """A raiz sem git, os sub-repositórios com ele. O `historico()` desce um nível e o
    `commits_por_pasta()` também — o `retrato` era o único que não descia, e o mesmo
    documento dizia "não há repositório git aqui" ao lado de 782 commits de
    co-mudança. Duas frases da mesma página se contradizendo."""
    # Arrange — dois sub-repositórios, autores diferentes, idades diferentes
    def git(onde, *args, **env):
        subprocess.run(['git', *args], cwd=onde, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       env={**os.environ, **env})
    for nome, email, dias in (('api', 'ana@exemplo.local', 300),
                              ('admin', 'bia@exemplo.local', 40)):
        sub = tmp_path / nome
        sub.mkdir()
        git(sub, 'init', '-q')
        git(sub, 'config', 'user.email', email)
        git(sub, 'config', 'user.name', nome)
        for i in range(2):
            (sub / 'a.txt').write_text(str(i))
            quando = (datetime.now(timezone.utc) - timedelta(days=dias - i)).isoformat()
            git(sub, 'add', '-A')
            git(sub, 'commit', '-q', '-m', f'c{i}',
                GIT_AUTHOR_DATE=quando, GIT_COMMITTER_DATE=quando)
    # a MESMA pessoa nos dois sub-repositórios: é o caso que separa união de soma, e
    # é o comum num time pequeno. Sem ele, contar por repo dá o mesmo número e o
    # fator ônibus sai inflado justamente onde ele precisa estar certo.
    (tmp_path / 'admin' / 'b.txt').write_text('x')
    git(tmp_path / 'admin', 'config', 'user.email', 'ana@exemplo.local')
    git(tmp_path / 'admin', 'add', '-A')
    git(tmp_path / 'admin', 'commit', '-q', '-m', 'ana no admin')
    # Act
    r = retrato(tmp_path)
    # Assert
    assert r['autores'] == 2, 'o fator ônibus é das pessoas do conjunto'
    assert r['commits'] == 5
    assert r['semanas_de_vida'] >= 36, 'a idade vai do commit mais antigo ao mais novo'
    assert r['semanas_parado'] <= 6, 'parado é desde o ÚLTIMO commit de qualquer sub-repo'
    assert r['lacuna'] and 'sub-repositório' in r['lacuna']
