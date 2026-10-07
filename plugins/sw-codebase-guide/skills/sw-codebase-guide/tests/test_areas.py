import subprocess

from lib.areas import detectar
from lib.historia import commits_por_pasta


def arvore_de(caminhos):
    return [{'caminho': c, 'bytes': 10, 'linguagem': 'python',
             'gerado': False, 'acima_do_teto': False} for c in caminhos]


def test_desce_enquanto_um_filho_domina():
    # Arrange — tudo mora sob `src/app/(app)/`; parar em `src` não daria área nenhuma útil
    arvore = arvore_de([
        'src/app/(app)/funil/page.tsx', 'src/app/(app)/funil/card.tsx',
        'src/app/(app)/funil/util.ts',
        'src/app/(app)/tarefas/page.tsx', 'src/app/(app)/tarefas/lista.tsx',
        'src/app/(app)/tarefas/x.ts',
        'src/app/(app)/agenda/page.tsx', 'src/app/(app)/agenda/dia.tsx',
        'src/app/(app)/agenda/y.ts',
    ])
    # Act
    caminhos = sorted(a['caminho'] for a in detectar(arvore, None))
    # Assert
    assert caminhos == ['src/app/(app)/agenda', 'src/app/(app)/funil',
                        'src/app/(app)/tarefas']


def test_monorepo_por_justaposicao_para_no_nivel_1():
    # Arrange — o outro caso-âncora: três sistemas lado a lado
    arvore = arvore_de([
        'api/src/a.php', 'api/src/b.php', 'api/src/c.php',
        'web/src/a.ts', 'web/src/b.ts', 'web/src/c.ts',
        'admin/src/a.vue', 'admin/src/b.vue', 'admin/src/c.vue',
    ])
    # Act
    caminhos = sorted(a['caminho'] for a in detectar(arvore, None))
    # Assert
    assert caminhos == ['admin', 'api', 'web']


def test_pasta_abaixo_do_piso_nao_vira_area():
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py', 'b/1.py'])
    # Act
    caminhos = [a['caminho'] for a in detectar(arvore, None)]
    # Assert — `b` tem 1 arquivo, abaixo do piso de 3
    assert caminhos == ['a']


def test_conta_os_arquivos_de_cada_area():
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py', 'a/sub/4.py',
                        'b/1.py', 'b/2.py', 'b/3.py'])
    # Act
    por_caminho = {a['caminho']: a['arquivos'] for a in detectar(arvore, None)}
    # Assert — conta recursivo: `a/sub/4.py` é de `a`
    assert por_caminho == {'a': 4, 'b': 3}


def test_ordena_por_commits_recentes_quando_houver():
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py', 'b/1.py', 'b/2.py', 'b/3.py'])
    # Act
    ordem = [x['caminho'] for x in detectar(arvore, {'b': 12, 'a': 3})]
    # Assert
    assert ordem == ['b', 'a']


def test_cai_para_numero_de_arquivos_sem_git():
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py',
                        'b/1.py', 'b/2.py', 'b/3.py', 'b/4.py'])
    # Act
    ordem = [x['caminho'] for x in detectar(arvore, None)]
    # Assert — um terço dos projetos testados não tem git na raiz
    assert ordem == ['b', 'a']


def test_commits_por_pasta_conta_commit_e_nao_toque(tmp_path):
    # Arrange — DOIS arquivos por commit: com contagem por toque daria 4, não 2
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git('init', '-q')
    git('config', 'user.email', 'teste@exemplo.local')
    git('config', 'user.name', 'Teste')
    (tmp_path / 'api').mkdir()
    for i in range(2):
        (tmp_path / 'api' / 'a.php').write_text(f'<?php {i}')
        (tmp_path / 'api' / 'b.php').write_text(f'<?php {i}')
        git('add', '-A')
        git('commit', '-q', '-m', f'c{i}')
    # Act / Assert — o rótulo do menu diz "14 commits no último mês"
    assert commits_por_pasta(tmp_path, dias=90).get('api') == 2


def test_commits_por_pasta_ignora_repo_acima(tmp_path):
    # Arrange — projeto dentro de repositório maior: é o caso das próprias fixtures
    # depois do `make sync`, e o `historia.py` já registra isso num comentário
    def git(raiz, *args):
        subprocess.run(['git', *args], cwd=raiz, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'teste@exemplo.local')
    git(tmp_path, 'config', 'user.name', 'Teste')
    (tmp_path / 'raiz.py').write_text('x = 1')
    git(tmp_path, 'add', '-A')
    git(tmp_path, 'commit', '-q', '-m', 'c')
    sub = tmp_path / 'sub'
    sub.mkdir()
    (sub / 'a.py').write_text('y = 1')
    # Act / Assert
    assert commits_por_pasta(sub, dias=90) == {}


def test_commits_por_pasta_conta_o_periodo(tmp_path):
    # Arrange
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git('init', '-q')
    git('config', 'user.email', 'teste@exemplo.local')
    git('config', 'user.name', 'Teste')
    (tmp_path / 'api').mkdir()
    for i in range(3):
        (tmp_path / 'api' / f'{i}.php').write_text('<?php')
        git('add', '-A')
        git('commit', '-q', '-m', f'c{i}')
    # Act
    por_pasta = commits_por_pasta(tmp_path, dias=90)
    # Assert
    assert por_pasta.get('api') == 3


def test_git_lento_cai_para_contagem_de_arquivos(tmp_path, monkeypatch):
    # Arrange
    import lib.historia as historia
    monkeypatch.setattr(historia, '_git', lambda *a, **k: None)
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py',
                        'b/1.py', 'b/2.py', 'b/3.py', 'b/4.py'])
    # Act
    recentes = historia.commits_por_pasta(tmp_path)
    ordem = [x['caminho'] for x in detectar(arvore, recentes or None)]
    # Assert — sem git útil, ordena por tamanho e o menu diz isso
    assert recentes == {}
    assert ordem == ['b', 'a']


def test_pasta_com_manifesto_proprio_nao_se_abre():
    # Arrange — o monorepo por justaposição: `admin` é um sistema inteiro, e abrir
    # por dentro misturaria os componentes de uma aplicação com as rotas da outra
    arvore = arvore_de(
        [f'admin/src/components/c{i}.vue' for i in range(200)]
        + [f'admin/src/views/v{i}.vue' for i in range(150)]
        + [f'admin/src/store/s{i}.js' for i in range(80)]
        + [f'api/app/a{i}.php' for i in range(40)]
        + [f'web/src/w{i}.ts' for i in range(30)]
    )
    stacks = [{'caminho': 'admin', 'manifesto': 'package.json', 'stack': 'node'},
              {'caminho': 'api', 'manifesto': 'composer.json', 'stack': 'php'},
              {'caminho': 'web', 'manifesto': 'package.json', 'stack': 'node'}]
    # Act
    caminhos = sorted(a['caminho'] for a in detectar(arvore, None, stacks))
    # Assert — sem a regra de átomo, `admin` (430 arquivos) seria aberto em três
    assert caminhos == ['admin', 'api', 'web']


def test_area_grande_que_se_abre_em_tres_e_substituida_pelos_filhos():
    # Arrange — o defeito que a suíte verde escondia: no fixture antigo só existia
    # `src/app/(app)/*`, e o corte descia. Num projeto real há `tests/` e `docs/`
    # ao lado, o corte para no nível 1, e o menu oferece `src` — que ninguém pede.
    arvore = arvore_de(
        [f'src/app/funil/f{i}.tsx' for i in range(60)]
        + [f'src/app/agenda/a{i}.tsx' for i in range(60)]
        + [f'src/app/tarefas/t{i}.tsx' for i in range(60)]
        + [f'tests/t{i}.ts' for i in range(10)]
        + [f'docs/d{i}.md' for i in range(10)]
        + [f'scripts/s{i}.ts' for i in range(10)]
    )
    # Act
    caminhos = sorted(a['caminho'] for a in detectar(arvore, None, None))
    # Assert
    assert caminhos == ['docs', 'scripts', 'src/app/agenda', 'src/app/funil',
                        'src/app/tarefas', 'tests']


def test_pasta_grande_com_arquivos_soltos_no_topo_nao_se_abre():
    # Arrange — 180 arquivos direto em `nucleo/`, e três subpastas de 4.
    # Abrir aqui esconderia 180 arquivos atrás de um menu de três opções.
    arvore = arvore_de(
        [f'nucleo/n{i}.py' for i in range(180)]
        + [f'nucleo/a/x{i}.py' for i in range(4)]
        + [f'nucleo/b/y{i}.py' for i in range(4)]
        + [f'nucleo/c/z{i}.py' for i in range(4)]
    )
    # Act
    caminhos = sorted(a['caminho'] for a in detectar(arvore, None, None))
    # Assert — os filhos cobrem 12 de 192: não é fan-out
    assert caminhos == ['nucleo']


def test_saida_de_ferramenta_nao_vira_area():
    # Arrange — `.playwright-mcp` entrou num menu real; a poda do `stacks` não pega
    arvore = arvore_de(['src/a.py', 'src/b.py', 'src/c.py',
                        '.playwright-mcp/1.png', '.playwright-mcp/2.png',
                        '.playwright-mcp/3.png', '.playwright-mcp/4.png'])
    # Act
    caminhos = [a['caminho'] for a in detectar(arvore, None, None)]
    # Assert
    assert caminhos == ['src']


def test_sem_medir_commits_o_menu_diz_nulo_e_nao_zero():
    """`commits_recentes: 0` se lê como *ninguém mexe nisso há 90 dias*. Num monorepo
    sem git na raiz NADA foi medido, e o menu anunciava zero nas seis áreas — a mesma
    falsidade que o `retrato` já proíbe. Não medido é `None`."""
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py', 'b/1.py', 'b/2.py', 'b/3.py'])
    # Act
    areas = detectar(arvore, None)
    # Assert
    assert [x['commits_recentes'] for x in areas] == [None, None]


def test_zero_medido_continua_zero():
    """O contrário do teste acima: com git, área sem commit no período É zero medido —
    e trocar isso por `None` jogaria fora informação apurada."""
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py', 'b/1.py', 'b/2.py', 'b/3.py'])
    # Act
    areas = {x['caminho']: x['commits_recentes'] for x in detectar(arvore, {'a': 4})}
    # Assert
    assert areas == {'a': 4, 'b': 0}


def test_commits_por_pasta_desce_nos_subrepos_quando_a_raiz_nao_tem_git(tmp_path):
    """Mesmo caso-âncora do `historico()`, que já desce um nível: `/projeto` sem git,
    `/projeto/api` e `/projeto/admin` com repositório próprio. Sem isto o menu de
    escopo perde a ordenação por recência exatamente onde ela mais importa —
    qual dos quatro sistemas justapostos está vivo."""
    # Arrange
    def git(onde, *args):
        subprocess.run(['git', *args], cwd=onde, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # DUAS pastas tocadas por commit: com a soma das pastas no lugar da contagem de
    # commits, `api` daria 6 — e o rótulo do menu mentiria para cima.
    for nome, commits in (('api', 3), ('admin', 1)):
        sub = tmp_path / nome
        (sub / 'src').mkdir(parents=True)
        (sub / 'cfg').mkdir(parents=True)
        git(sub, 'init', '-q')
        git(sub, 'config', 'user.email', 'teste@exemplo.local')
        git(sub, 'config', 'user.name', 'Teste')
        for i in range(commits):
            (sub / 'src' / 'a.txt').write_text(str(i))
            (sub / 'cfg' / 'b.txt').write_text(str(i))
            git(sub, 'add', '-A')
            git(sub, 'commit', '-q', '-m', f'c{i}')
    # Act
    recentes = commits_por_pasta(tmp_path, dias=90)
    # Assert — o sub-repositório inteiro e as pastas dentro dele, prefixadas
    assert recentes.get('api') == 3
    assert recentes.get('admin') == 1
    assert recentes.get('api/src') == 3
