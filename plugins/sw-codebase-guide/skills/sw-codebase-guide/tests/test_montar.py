import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / 'fixtures'

# A lista vive no `montar.py`, porque a recusa é do PARSER. Importar em vez de
# copiar é o que impede as duas divergirem na primeira vez que alguém
# acrescentar uma frase a uma só delas.
sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))
from montar import PROIBIDAS, _dependentes  # noqa: E402


def varrer(projeto, saida):
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True, text=True)


def montar(saida):
    return subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                           '--dir', str(saida)], capture_output=True, text=True)


def test_o_documento_diz_que_nao_ve_acoplamento_por_string(tmp_path):
    """Esta fixture tem acoplamento que existe SÓ por string e injeção. Antes ele
    aparecia na lista por símbolo, que vinha do grafo textual; com o grafo de import
    real, a lista saiu e o acoplamento invisível **deixa de ser mostrado**.

    Isso é perda de capacidade, e a resposta honesta não é escondê-la: o documento
    diz o que não enxerga e aponta onde o dado bruto está. A seção que cruza
    co-mudança com import para achar esse acoplamento ficou para o próximo ciclo."""
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — o documento declara o que não enxerga, e não finge medir
    assert 'rota como string' in guia
    assert 'injeção de dependência' in guia
    assert 'continua por apurar' in guia or 'não medido' in guia
    for frase in PROIBIDAS:
        assert frase not in guia.lower(), frase


def test_nenhuma_frase_de_ausencia(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text().lower()
    # Assert — o par NEGATIVO
    for frase in PROIBIDAS:
        assert frase not in guia, frase


def test_diz_o_que_o_grafo_de_import_nao_enxerga(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text().lower()
    # Assert — a ressalva viaja junto da afirmação, não numa nota de rodapé
    assert 'injeção de dependência' in guia or 'injecao de dependencia' in guia
    assert 'rota como string' in guia


def test_secao_de_co_mudanca_existe_com_motivo_sem_historico(tmp_path):
    # Arrange — a fixture não é repositório git
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — omissão se leria como "nada muda junto"
    assert 'muda junto' in guia.lower()
    assert 'git' in guia.lower()


def test_as_quatro_secoes_do_contrato_aparecem(tmp_path):
    # Arrange — uma afirmação em cada seção publicada pelo contrato
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '\n'.join(
            f'[[afirmacao]]\nsecao = "{secao}"\ntexto = "marca-{secao}"\n'
            f'nivel = "declarado"\nevidencia = ["rotas.py:1"]\nmotivo = ""\n'
            for secao in ('como-entrar', 'depende-de', 'o-que-faz', 'superficie')))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — seção publicada no contrato e não consumida faz o agente trabalhar à toa
    for secao in ('como-entrar', 'depende-de', 'o-que-faz', 'superficie'):
        assert f'marca-{secao}' in guia, secao


def test_secao_invalida_e_recusada_sem_traceback(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\ntexto = "sem secao"\nnivel = "fato"\n'
        'evidencia = ["rotas.py:1"]\nmotivo = ""\n')
    # Act
    r = montar(tmp_path)
    # Assert
    assert r.returncode == 2
    assert 'secao' in (r.stderr + r.stdout).lower()
    assert 'Traceback' not in r.stderr


def test_superficie_sai_marcada_como_deducao(tmp_path):
    # Arrange — a fixture tem rotas.py na raiz, sem pasta de convenção
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — sem convenção reconhecida, é lacuna com motivo; nunca silêncio
    assert 'Superfície pública' in guia
    assert 'lacuna' in guia.lower() or 'dedução' in guia


def test_duas_montagens_identicas(tmp_path):
    # Arrange — interpretation.toml CONGELADO: a parte não-determinística fica fora
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\n'
        'secao = "o-que-faz"\n'
        'texto = "Expõe um endpoint de usuário"\n'
        'nivel = "deducao"\n'
        'evidencia = ["rotas.py:3"]\n'
        'motivo = ""\n')
    # Act
    montar(tmp_path)
    primeira = (tmp_path / 'guide.md').read_bytes()
    montar(tmp_path)
    segunda = (tmp_path / 'guide.md').read_bytes()
    # Assert
    assert primeira == segunda


def test_afirmacao_sem_evidencia_e_recusada(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\n'
        'secao = "o-que-faz"\n'
        'texto = "O sistema gere uma loja de departamentos"\n'
        'nivel = "deducao"\n'
        'evidencia = []\n'
        'motivo = ""\n')
    (tmp_path / 'guide.md').write_text('documento anterior')   # sentinela
    # Act
    r = montar(tmp_path)
    # Assert — prosa plausível sem lastro não entra, e o documento bom não é destruído
    assert r.returncode == 2
    assert 'evidencia' in (r.stderr + r.stdout).lower()
    assert (tmp_path / 'guide.md').read_text() == 'documento anterior'


def test_co_mudanca_de_subrepos_aparece_com_ressalva(tmp_path):
    # Arrange — inventário de um projeto cuja raiz não tem git mas os filhos têm:
    # há dado E há lacuna. Decidir pela lacuna escondia os 40 pares que existiam.
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['historia'] = {
        'commits': 782, 'commits_descartados': 3,
        'co_mudanca': [{'arquivos': ['api/Rotas.php', 'api/Middleware.php'], 'vezes': 38}],
        'subrepos': [{'caminho': 'api', 'commits': 325}],
        'lacuna': 'a raiz não é repositório git; a co-mudança vem de 1 sub-repositório (api)',
    }
    # os dois caminhos precisam existir: o emissor filtra par que cita arquivo que
    # não está mais no projeto, e sem isto o teste mediria o filtro
    inv['caminhos_do_projeto'] = sorted(
        set(inv['caminhos_do_projeto']) | {'api/Rotas.php', 'api/Middleware.php'})
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — o dado aparece, e a ressalva viaja junto
    assert 'api/Rotas.php' in guia and '38x' in guia
    assert 'Ressalva' in guia and 'sub-repositório' in guia
    assert 'Não apurado' not in guia
    # e a pergunta sobre histórico não faz mais sentido
    assert 'Existe histórico de versionamento' not in guia


def test_pergunta_fixa_some_quando_a_secao_foi_respondida(tmp_path):
    # Arrange — a interpretação declara o propósito com fonte
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\nsecao = "o-que-faz"\n'
        'texto = "Transmite eventos do eSocial de processo trabalhista"\n'
        'nivel = "declarado"\nevidencia = ["commit 3c5aabb"]\nmotivo = ""\n')
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — perguntar o propósito logo abaixo da resposta é o documento se
    # contradizendo na mesma página
    assert 'Transmite eventos do eSocial' in guia
    assert 'Qual é o propósito de negócio' not in guia


def test_simbolo_citado_em_documentacao_nao_vira_dependente(tmp_path):
    """Este teste guardava um filtro da lista por SÍMBOLO, que vinha de `mencoes` e
    casava palavra. Com grafo de import real a lista saiu inteira, e o filtro foi
    junto — o que ele combatia (nome de arquivo de spec virando "dependente") deixa
    de ser possível, porque só aresta resolvida entra. A garantia continua, com
    outra causa."""
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['mencoes']['PlanoDeMigracao'] = [{'caminho': 'docs/plano.md', 'linha': 3},
                                         {'caminho': 'README.md', 'linha': 9}]
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert 'PlanoDeMigracao' not in guia
    assert 'docs/plano.md' not in guia


def test_sem_grafo_de_import_a_secao_vira_lacuna(tmp_path):
    # Arrange — sem arestas, o que resta é grafo textual casando PALAVRA: num
    # projeto em português devolvia `banco` e `caminho` com centenas de "menções"
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['imports'] = {'arestas': [],
                      'indisponivel': [{'stack': 'node', 'motivo': 'sem resolvedor'}]}
    inv['mencoes'] = {'banco': [{'caminho': 'a.ts', 'linha': 1},
                                {'caminho': 'b.ts', 'linha': 2}],
                      'caminho': [{'caminho': 'c.ts', 'linha': 3},
                                  {'caminho': 'd.ts', 'linha': 4}]}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — a lacuna aparece com motivo, e o ruído não
    assert 'indisponível para **node**' in guia
    assert 'sem resolvedor' in guia, 'a lacuna precisa dizer POR QUE não mediu'
    assert '[lacuna]' in guia
    assert '**banco**' not in guia and 'import não medido' not in guia
    # e a garantia mais forte continua de pé
    for frase in PROIBIDAS:
        assert frase not in guia.lower(), frase


def test_com_grafo_de_import_a_lista_continua(tmp_path):
    # Arrange — o par positivo: havendo aresta, a seção não some
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['imports'] = {
        'arestas': [{'de': 'rotas.py', 'para': 'app/UserController.py',
                     'origem': 'sufixo_unico'}],
        'indisponivel': [], 'barris': [],
        'resolucao': {'python': {'relativos': 0, 'externos': 0, 'sufixo_unico': 1,
                                 'base_provada': 0, 'config_conferida': 0,
                                 'ambiguos': 0, 'pendurados': 0,
                                 'nao_resolvidos': 0}}}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — a lista virou ranking por ARQUIVO, com a taxa ao lado
    assert '1 arquivo importa diretamente `app/UserController.py`' in guia
    assert 'Resolvidos 1 de 1' in guia
    assert 'indisponível para' not in guia


def test_sem_lista_o_aviso_nao_se_repete(tmp_path):
    # Arrange — o preâmbulo das cegueiras qualifica uma lista; sem lista, ele mais a
    # indisponibilidade mais a lacuna dizem a mesma coisa três vezes
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['imports'] = {'arestas': [],
                      'indisponivel': [{'stack': 'node', 'motivo': 'sem resolvedor'}]}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    # a indisponibilidade sai UMA vez, no preâmbulo — imprimi-la também na lista
    # deu vinte linhas repetidas num projeto real
    assert guia.count('[lacuna]') >= 1
    assert guia.count('indisponível para **node**') == 1
    assert 'importa diretamente' not in guia, 'sem lista, a ressalva da lista não sai'


def _com_escopo(tmp_path, **ajustes):
    """Inventário da fixture, com o escopo (e o que mais for pedido) forçado."""
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['escopo'] = {'area': 'app', 'criterio': 'prefixo de caminho', 'n_arquivos': 1}
    inv.update(ajustes)
    # os pares injetados usam caminhos sintéticos, e o emissor passou a filtrar par
    # que cita arquivo inexistente — então eles precisam constar como existentes,
    # senão o teste mede o filtro em vez de medir o que ele quer medir
    citados = {a for c in (inv.get('historia') or {}).get('co_mudanca') or []
               for a in c['arquivos']}
    inv['caminhos_do_projeto'] = sorted(set(inv.get('caminhos_do_projeto') or []) | citados)
    # a árvore do inventário É o recorte, e o `varrer.py` põe nela todo arquivo do
    # projeto que cai dentro. A fixture precisa fazer o mesmo, senão a ponta de
    # DENTRO sai marcada como fora e o teste mede a própria fixture.
    area = inv['escopo']['area']
    dentro = sorted(c for c in citados if c == area or c.startswith(f'{area}/'))
    ja = {a['caminho'] for a in inv['arvore']}
    inv['arvore'] += [{'caminho': c, 'bytes': 1, 'linguagem': 'Python', 'gerado': False}
                      for c in dentro if c not in ja]
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    r = montar(tmp_path)
    assert r.returncode == 0, r.stderr
    return (tmp_path / 'guide.md').read_text()


def test_documento_diz_qual_escopo_o_gerou(tmp_path):
    # Act
    guia = _com_escopo(tmp_path)
    # Assert — quem lê precisa saber que está vendo um recorte, e isso tem que
    # estar no TOPO: o plano mandava procurar em `linhas[2:8].__str__()`, que
    # passaria com a palavra em qualquer lugar daquelas seis linhas
    topo = '\n'.join(guia.split('\n')[:10])
    assert 'Recorte' in topo
    assert '`app`' in topo
    assert '1 arquivo' in topo


def test_sem_recorte_o_documento_nao_fala_de_area(tmp_path):
    # Arrange — o par negativo: sem ele, um cabeçalho fixo passaria no teste acima
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    assert montar(tmp_path).returncode == 0
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert 'Recorte' not in guia


def test_stack_de_fora_da_area_sai_marcada(tmp_path):
    # Act
    guia = _com_escopo(tmp_path, stacks=[
        {'stack': 'node', 'caminho': '.', 'manifesto': 'package.json',
         'por': 'manifesto', 'de_fora_da_area': True}])
    # Assert
    assert 'fora da área' in guia


def test_ponta_de_fora_sai_marcada(tmp_path):
    # Act
    guia = _com_escopo(tmp_path, historia={
        'commits': 90, 'commits_descartados': 0, 'lacuna': None,
        'co_mudanca': [{'arquivos': ['app/a.py', 'fora/b.py'], 'vezes': 9}]})
    # Assert — "mexer aqui mexe lá fora" só ensina se o leitor souber qual é o lá fora
    assert '`fora/b.py` *(fora)*' in guia
    assert '`app/a.py`' in guia and '`app/a.py` *(fora)*' not in guia


def test_commits_do_projeto_todo_sao_declarados(tmp_path):
    # Act
    guia = _com_escopo(tmp_path, historia={
        'commits': 500, 'commits_descartados': 0, 'lacuna': None,
        'co_mudanca': [{'arquivos': ['app/a.py', 'fora/b.py'], 'vezes': 9}]})
    # Assert — o número é do projeto, não da área, e o documento não pode esconder isso
    assert 'De 500 commits do projeto todo' in guia


def _com_evidencia(tmp_path, evidencias):
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    linhas = ''.join(
        f'[[afirmacao]]\nsecao = "o-que-faz"\ntexto = "t{i}"\nnivel = "deducao"\n'
        f'evidencia = {json.dumps([e])}\nmotivo = ""\n\n'
        for i, e in enumerate(evidencias))
    (tmp_path / 'interpretation.toml').write_text(linhas)
    return montar(tmp_path)


def test_quatro_formas_de_evidencia(tmp_path):
    # Arrange / Act — caminho, caminho:linha, diretório e não-caminho.
    # O SKILL.md documenta `app/Pedido.php:88` e os testes usam `commit 3c5aabb`:
    # uma conferência ingênua recusaria a evidência CORRETA.
    r = _com_evidencia(tmp_path, ['rotas.py', 'rotas.py:3', 'app/', 'commit 3c5aabb'])
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout


def test_caminho_inventado_recusado_nos_dois_blocos(tmp_path):
    # Arrange / Act
    r = _com_evidencia(tmp_path, ['nao/existe.php'])
    # Assert
    assert r.returncode == 2
    assert 'nao/existe.php' in (r.stderr + r.stdout)
    assert 'Traceback' not in r.stderr


def test_diretorio_casa_por_prefixo(tmp_path):
    # Arrange — a árvore só tem arquivos; `app/` é diretório e é citação legítima
    r = _com_evidencia(tmp_path, ['app/'])
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout


def test_diretorio_inventado_tambem_e_recusado(tmp_path):
    # Arrange — o par negativo do anterior: sem ele, bastaria aceitar tudo que
    # termina em barra para os dois testes passarem
    r = _com_evidencia(tmp_path, ['inventado/'])
    # Assert
    assert r.returncode == 2
    assert 'inventado/' in (r.stderr + r.stdout)


def test_markdown_nao_conta_como_codigo_no_cabecalho(tmp_path):
    """O mesmo documento chamava `.md` de código no cabeçalho e de "não é código" no
    bloco de arquivos maiores — duas definições de código na mesma página. E o
    conjunto `ATIVOS` existia em TRÊS cópias, uma por emissor."""
    # Arrange
    projeto = tmp_path / 'proj'
    projeto.mkdir()
    (projeto / 'app.py').write_text('x = 1')
    (projeto / 'pyproject.toml').write_text('[project]\nname = "x"')
    (projeto / 'README.md').write_text('# Projeto')
    (projeto / 'notas.md').write_text('# Notas')
    (projeto / 'dados.yaml').write_text('a: 1')
    saida = tmp_path / 'out'
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True)
    # Act
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                    '--dir', str(saida)], check=True, capture_output=True)
    guia = (saida / 'guide.md').read_text()
    # Assert — só `app.py` é código; os três markdown/yaml e o toml não são
    assert '1 arquivos de código' in guia or '1 arquivo de código' in guia, \
        [l for l in guia.split('\n') if 'arquivos de código' in l]


# ───────────────────────── o ranking por arquivo, com piso ─────────────────────
BALDES = ('relativos', 'externos', 'sufixo_unico', 'base_provada', 'config_conferida',
          'ambiguos', 'pendurados', 'nao_resolvidos')


def contagem(**valores):
    return {**dict.fromkeys(BALDES, 0), **valores}


def inv_com(arestas, resolucao, barris=()):
    return {'imports': {'arestas': arestas, 'indisponivel': [],
                        'resolucao': resolucao, 'barris': list(barris)},
            'mencoes': {}}


def test_ranking_por_arquivo_ordenado_por_quem_importa():
    """A lista de antes era por SÍMBOLO e ordenada por menções textuais — ela existia
    só por não haver grafo. Com aresta real, a pergunta 'o que mais gente importa'
    tem resposta direta e sem o ruído do casamento por palavra."""
    # Arrange
    arestas = [{'de': f'src/t{i}.ts', 'para': 'src/servico.ts', 'origem': 'relativo'}
               for i in range(3)]
    arestas.append({'de': 'src/t0.ts', 'para': 'src/raro.ts', 'origem': 'relativo'})
    # Act
    linhas = '\n'.join(_dependentes(inv_com(arestas, {'js': contagem(relativos=4)})))
    # Assert
    assert '3 arquivos importam diretamente `src/servico.ts`' in linhas
    assert linhas.index('src/servico.ts') < linhas.index('src/raro.ts')


def test_diz_importa_diretamente_e_nunca_alcanca():
    """'alcança' se lê como transitivo, e o desenho declara que não é."""
    # Arrange / Act
    linhas = '\n'.join(_dependentes(inv_com(
        [{'de': 'a.ts', 'para': 'b.ts', 'origem': 'relativo'}],
        {'js': contagem(relativos=1)})))
    # Assert
    assert 'alcança' not in linhas


def test_abaixo_do_piso_a_linguagem_vira_lacuna_e_nao_ranking():
    """Ranking construído sobre metade do grafo tem cara de fato — é o erro que a
    v0.1.1 custou. Não basta publicar a taxa ao lado: ninguém lê uma ressalva e
    depois duvida de uma lista ordenada."""
    # Arrange — 4 de 10 resolvidos: 40%
    # Act
    linhas = '\n'.join(_dependentes(inv_com(
        [{'de': 'a.ts', 'para': 'b.ts', 'origem': 'relativo'}],
        {'js': contagem(relativos=4, ambiguos=3, nao_resolvidos=3)})))
    # Assert
    assert 'lacuna' in linhas
    assert '40%' in linhas
    assert 'b.ts' not in linhas


def test_denominador_zero_e_nao_medido_e_nunca_zero_por_cento():
    """Linguagem com extrator e nenhum import interno: 0/0 não é 0%."""
    # Act
    linhas = '\n'.join(_dependentes(inv_com([], {'js': contagem()})))
    # Assert
    assert 'não medido' in linhas
    assert '0%' not in linhas


def test_arquivo_de_puro_reexport_fica_fora_do_ranking():
    """Com `export … from` no extrator e centenas de imports apelidados, todo
    `@/utils` resolve no barril — e o topo viraria "9 arquivos importam index.ts":
    verdadeiro, inútil, e com o arquivo que a pessoa precisa abrir a dois saltos,
    que o não-objetivo "sem análise transitiva" proíbe seguir."""
    # Arrange
    arestas = [{'de': f'src/t{i}.ts', 'para': 'src/index.ts', 'origem': 'relativo'}
               for i in range(9)]
    arestas += [{'de': f'src/t{i}.ts', 'para': 'src/servico.ts', 'origem': 'relativo'}
                for i in range(2)]
    # Act
    linhas = '\n'.join(_dependentes(inv_com(arestas, {'js': contagem(relativos=11)},
                                            barris=['src/index.ts'])))
    # Assert
    assert 'src/index.ts' not in linhas
    assert 'src/servico.ts' in linhas


def test_o_texto_gerado_nao_usa_nenhuma_frase_proibida():
    """O rodapé precisa dizer que a lista não é exaustiva SEM usar as palavras que a
    skill proíbe. Um rascunho deste texto dizia 'não é afirmação de que nada depende
    dele' — e `PROIBIDAS[0]` é exatamente `'nada depende'`."""
    # Act
    texto = '\n'.join(_dependentes(inv_com(
        [{'de': 'a.ts', 'para': 'b.ts', 'origem': 'relativo'}],
        {'js': contagem(relativos=1)}))).lower()
    # Assert
    assert not [f for f in PROIBIDAS if f in texto]


def test_arquivo_respondido_sai_da_lista_de_perguntas(tmp_path):
    """O documento precisa melhorar a cada rodada: pergunta já respondida que volta
    a aparecer é como um relatório perde credibilidade. A resposta não some — vai
    para "já perguntamos", com nome e data."""
    # Arrange
    import sys
    sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))
    from gravar import gravar as gravar_resposta
    varrer(FIXTURES / 'poliglota_com_codigo', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['julgamento'] = {
        'perigo': [], 'risco': [], 'dossie': {'autores': 1, 'commits': 2,
                                              'semanas_de_vida': 1, 'semanas_parado': 0,
                                              'arquivos_de_codigo': 3, 'pct_teste': 0,
                                              'stacks': 1, 'linguagens_medidas': ['js'],
                                              'falta': 'custo de reescrita'},
        'sem_alcance': [{'caminho': 'api/app/Servico.php', 'dias_parado': 500},
                        {'caminho': 'servico/apoio.py', 'dias_parado': 400}]}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    gravar_resposta(tmp_path, 'api/app/Servico.php', 'ainda é usado?',
                    'sim, o agendador chama por reflexão', 'ana', quando='2026-10-07')
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    perguntas = guia.split('ainda é usado?')[1].split('### Já perguntamos')[0]
    # Assert
    assert 'api/app/Servico.php' not in perguntas, 'o respondido saiu da lista'
    assert 'servico/apoio.py' in perguntas, 'o não respondido continua'
    assert 'o agendador chama por reflexão' in guia
    assert '**ana**, 2026-10-07' in guia


def test_imagem_importada_nao_entra_no_ranking_de_codigo():
    """`import logo from '@/assets/fallback.png'` é aresta real e fica no grafo — mas
    o ranking responde "quem depende de quem no CÓDIGO", e num projeto real uma
    imagem ocupava uma das quinze vagas da lista."""
    # Arrange
    arestas = [{'de': f'src/t{i}.js', 'para': 'src/assets/fallback.png',
                'origem': 'sufixo_unico'} for i in range(10)]
    arestas += [{'de': f'src/t{i}.js', 'para': 'src/api.js', 'origem': 'relativo'}
                for i in range(3)]
    # Act
    linhas = '\n'.join(_dependentes(inv_com(arestas, {'js': contagem(relativos=13)})))
    # Assert
    assert 'fallback.png' not in linhas
    assert 'src/api.js' in linhas


def test_a_pergunta_do_proposito_some_com_DEDUCAO_e_com_a_narrativa(tmp_path):
    """A guarda contava só `fato` e `declarado`, e foi escrita quando propósito só
    podia vir de fonte textual — regra que a v0.2.0 afrouxou depois do spike. Hoje
    a resposta mais comum é uma `deducao` com evidência convergente, ou a narrativa
    com a citação literal ao lado; nos dois casos, perguntar de novo faz o documento
    se contradizer três parágrafos depois de responder."""
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\nsecao = "o-que-faz"\n'
        'texto = "É um portal de notícias com curadoria por IA"\n'
        'nivel = "deducao"\nevidencia = ["app/UserController.py"]\nmotivo = ""\n')
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert 'portal de notícias' in guia
    assert 'Qual é o propósito de negócio' not in guia


def test_a_co_mudanca_nao_cita_arquivo_que_nao_existe_mais(tmp_path):
    """O `git log` devolve caminho HISTÓRICO: arquivo apagado ou renomeado continua
    na co-mudança. Num projeto real eram 16 caminhos que não existem hoje, e o
    leitor ia procurá-los. O par vale pelo que ensina sobre o código de agora."""
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    vivo = inv['caminhos_do_projeto'][0]
    inv['historia'] = {'commits': 100, 'commits_descartados': 0, 'lacuna': None,
                       'co_mudanca': [
                           {'arquivos': [vivo, 'apagado/ha/tempo.php'], 'vezes': 9},
                           {'arquivos': [vivo, inv['caminhos_do_projeto'][-1]],
                            'vezes': 7}]}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert 'apagado/ha/tempo.php' not in guia
    assert inv['caminhos_do_projeto'][-1] in guia


def test_as_afirmacoes_saem_na_ORDEM_EM_QUE_FORAM_ESCRITAS(tmp_path):
    """Ordenar por texto é ordenar por acaso: num teste real a frase mais importante
    de "o que o sistema faz" começava com "É o esqueleto…" e caiu em ÚLTIMO lugar,
    atrás de três detalhes. Quem escreve a interpretação ordena por importância —
    o emissor não pode desfazer isso."""
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\nsecao = "o-que-faz"\ntexto = "Zebra: a frase que importa"\n'
        'nivel = "deducao"\nevidencia = ["app/UserController.py"]\nmotivo = ""\n\n'
        '[[afirmacao]]\nsecao = "o-que-faz"\ntexto = "Abacate: um detalhe"\n'
        'nivel = "deducao"\nevidencia = ["app/UserController.py"]\nmotivo = ""\n')
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert guia.index('Zebra') < guia.index('Abacate')
