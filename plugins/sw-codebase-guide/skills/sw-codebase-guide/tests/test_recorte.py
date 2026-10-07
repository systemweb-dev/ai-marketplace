import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent


def git(raiz, *args):
    subprocess.run(['git', *args], cwd=raiz, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def projeto_com_area(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / 'area').mkdir()
    (tmp_path / 'fora').mkdir()
    (tmp_path / 'package.json').write_text('{"name": "app"}')
    (tmp_path / '.env').write_text('DB_HOST=localhost\nAPP_NAME=loja\n')
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'teste@exemplo.local')
    git(tmp_path, 'config', 'user.name', 'Teste')
    for i in range(60):
        (tmp_path / 'area' / 'a.py').write_text(f'x = {i}')
        (tmp_path / 'fora' / 'b.py').write_text(f'y = {i}')
        git(tmp_path, 'add', '-A')
        git(tmp_path, 'commit', '-q', '-m', f'c{i}')
    return tmp_path


def varrer_com_area(projeto, saida, area):
    r = subprocess.run(
        [sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
         '--projeto', str(projeto), '--out', str(saida), '--area', area],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads((saida / 'inventory.json').read_text())


def test_arvore_recorta_por_prefixo(tmp_path):
    # Arrange
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert
    assert all(a['caminho'].startswith('area/') for a in inv['arvore'])


def test_stack_e_env_da_raiz_sao_herdados(tmp_path):
    # Arrange — o package.json está em `.` e o .env na raiz; recorte por prefixo
    # puro faria o documento dizer "nenhum manifesto reconhecido", que é falso
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert
    assert inv['stacks'], 'a stack da raiz sumiu'
    assert inv['stacks'][0]['de_fora_da_area'] is True
    assert '.env' in inv['ambiente']


def test_co_mudanca_cruzando_a_fronteira_sobrevive(tmp_path):
    # Arrange — `area/a.py` e `fora/b.py` mudam sempre juntos
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert — é exatamente esse par que vira "para mexer na área você mexe lá fora"
    pares = [tuple(sorted(c['arquivos'])) for c in inv['historia']['co_mudanca']]
    assert ('area/a.py', 'fora/b.py') in pares


def test_evidencia_que_cruza_a_fronteira_e_aceita(tmp_path):
    # Arrange — a orientação "para mexer na área você mexe lá fora" cita um arquivo
    # de fora, e a guarda de caminho a recusava porque a árvore vinha recortada
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert
    assert 'fora/b.py' in inv['caminhos_do_projeto']
    assert all(a['caminho'].startswith('area/') for a in inv['arvore'])


def test_escopo_fica_gravado_no_inventario(tmp_path):
    # Arrange
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert — sem isto, "mesmos fatos, mesmo documento" passaria a depender de
    # lembrar o que foi clicado no menu
    assert inv['escopo']['area'] == 'area'
    assert inv['escopo']['n_arquivos'] >= 1


def test_area_de_subrepo_preserva_a_co_mudanca(tmp_path):
    # Arrange — monorepo por justaposição: a raiz não tem git, `api` e `web` têm.
    # O filtro rodando antes do prefixo comparava `api` com `app/X.php` e zerava tudo.
    raiz = tmp_path / 'mono'
    for nome in ('api', 'web'):
        sub = raiz / nome
        sub.mkdir(parents=True)
        git(sub, 'init', '-q')
        git(sub, 'config', 'user.email', 'teste@exemplo.local')
        git(sub, 'config', 'user.name', 'Teste')
        for i in range(60):
            (sub / 'a.py').write_text(f'x = {i}')
            (sub / 'b.py').write_text(f'y = {i}')
            git(sub, 'add', '-A')
            git(sub, 'commit', '-q', '-m', f'c{i}')
    # Act
    inv = varrer_com_area(raiz, tmp_path / 'out', 'api')
    # Assert
    pares = [tuple(sorted(c['arquivos'])) for c in inv['historia']['co_mudanca']]
    assert ('api/a.py', 'api/b.py') in pares


def test_commits_continuam_do_projeto_todo(tmp_path):
    # Arrange
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert — o número é do projeto; o documento é que diz isso por extenso
    assert inv['historia']['commits'] == 60


def test_par_que_cruza_sobrevive_ao_teto_global(tmp_path):
    # Arrange — o fixture pequeno não prova a razão do desenho: com 2 arquivos
    # nunca se chega perto de MAX_PARES=40, e filtrar antes ou depois do corte dá
    # o mesmo resultado. Aqui `fora/` gera 66 pares de alta frequência, e o par
    # que CRUZA a fronteira fica em 67º — fora do teto. Filtrar depois do corte
    # apaga exatamente o sinal que a seção existe para dar.
    projeto = tmp_path / 'p'
    (projeto / 'area').mkdir(parents=True)
    (projeto / 'fora').mkdir()
    git(projeto, 'init', '-q')
    git(projeto, 'config', 'user.email', 'teste@exemplo.local')
    git(projeto, 'config', 'user.name', 'Teste')
    # 60 commits mexendo nos 12 arquivos de fora juntos → 66 pares, 60 vezes cada
    for i in range(60):
        for j in range(12):
            (projeto / 'fora' / f'f{j}.py').write_text(f'x = {i}')
        git(projeto, 'add', '-A')
        git(projeto, 'commit', '-q', '-m', f'fora{i}')
    # 30 commits ligando a área a um arquivo de fora → 1 par, 30 vezes
    for i in range(30):
        (projeto / 'area' / 'a.py').write_text(f'y = {i}')
        (projeto / 'fora' / 'f0.py').write_text(f'z = {i}')
        git(projeto, 'add', '-A')
        git(projeto, 'commit', '-q', '-m', f'cruza{i}')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert
    pares = [tuple(sorted(c['arquivos'])) for c in inv['historia']['co_mudanca']]
    assert ('area/a.py', 'fora/f0.py') in pares
    # e o recorte de fato filtrou: nenhum par com as DUAS pontas fora da área
    assert all(any(a.startswith('area/') for a in par) for par in pares)
