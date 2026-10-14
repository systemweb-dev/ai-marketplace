# tests/test_mentiras_medidas.py
"""O documento não afirma o que não mediu.

Esta trava nasceu de dois agentes limpos, em dois projetos reais e sem contato entre si,
que chegaram à mesma conclusão: a varredura publicava números falsos com cara de medida.
Cinco deles, e o mais grave era o pior tipo — não uma vagueza, uma **afirmação falsa no
bloco que o documento apresenta como a lista do que mais importa**:

- `sem teste` em arquivos que têm teste, porque o casamento de nome só conhecia a
  convenção com ponto do JavaScript (`Pedido.test.js`). Em PHP, Python e Go a coluna
  dizia "sem teste" em TODO arquivo, houvesse o que houvesse em `tests/`;
- `14% é teste` contando como teste `EAposentadoriaEspecial.php` e `Testemunha.php`, e
  dividindo por 1.946 arquivos — mil deles PNG e SVG — ao lado da frase "763 arquivos
  de código";
- `6 pessoas commitaram` num projeto de uma pessoa com seis e-mails, uma delas o rodapé
  de co-autoria do Claude Code;
- `100%` impresso ao lado de `764 de 767`;
- o limiar escrito (`mais de 10 commits`) diferente do limiar aplicado (`>= 10`).

O encadeamento é o que importa: um dos agentes leu `14% é teste`, deduziu dele uma frase
sobre cobertura e a escreveu no documento humano. Número mal definido vira prosa fluente
e falsa, e **nenhuma das guardas pega isso** — elas conferem procedência, não validade.
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'scripts'))

from lib import history, judge, questions  # noqa: E402
from lib.resolution import pct_honesto  # noqa: E402
from test_build import FIXTURES, montar, varrer  # noqa: E402
from test_judge import arquivo, contagem, inventario  # noqa: E402


# ------------------------------------------------- o que conta como teste
def test_substring_nao_faz_de_um_arquivo_um_teste():
    """`'test' in caminho` casava `Testemunha.php`; `'spec' in caminho` casava
    `EAposentadoriaEspecial.php`. Num sistema trabalhista em português isso punha uma
    testemunha e três enums de aposentadoria especial na contagem de cobertura."""
    for caminho in ('app/Models/Testemunha.php',
                    'app/Enums/EAposentadoriaEspecial.php',
                    'src/components/ProtestBanner.vue',
                    'lib/latest.php',
                    'app/Services/Inspecao.php',
                    'database/sql/V1_48__aposentadoria_especial.sql'):
        assert not judge.eh_teste(caminho), caminho


def test_as_convencoes_de_teste_que_existem_no_mundo():
    for caminho in ('tests/Unit/HelperTest.php', 'spec/models/user_spec.rb',
                    'lib/parser_test.go', 'tests/test_parser.py',
                    'src/Pedido.test.js', 'app/__tests__/botao.tsx',
                    'cypress/e2e/login.cy.js'):
        assert judge.eh_teste(caminho), caminho


def test_o_teste_de_php_python_e_go_cobre_o_arquivo_que_leva_o_nome_dele():
    """O casamento tirava só `.test` e `.spec` do nome — isto é, só o JavaScript."""
    assert 'helper' in judge.bases_do_teste('HelperTest')
    assert 'user' in judge.bases_do_teste('UserSpec')
    assert 'parser' in judge.bases_do_teste('test_parser')
    assert 'srv' in judge.bases_do_teste('srv_test')
    assert 'pedido' in judge.bases_do_teste('Pedido.test')


def test_perigo_nao_chama_de_sem_teste_o_arquivo_que_tem_teste():
    arestas = [{'de': f'app/C{i}.php', 'para': 'app/Helper.php', 'origem': 'x'}
               for i in range(6)]
    arvore = [arquivo('app/Helper.php')] + [arquivo(f'app/C{i}.php') for i in range(6)]
    inv = inventario(arestas=arestas, arvore=arvore,
                     caminhos=[a['caminho'] for a in arvore] + ['tests/Unit/HelperTest.php'],
                     resolucao={'php': contagem(relativos=10)})
    ultima = {'app/Helper.php': {'commits': 30}}

    perigosos = [p['caminho'] for p in judge.onde_e_perigoso(inv, ultima)]

    assert 'app/Helper.php' not in perigosos, 'tests/Unit/HelperTest.php cobre Helper.php'


def test_o_teste_de_outra_stack_nao_cobre_o_arquivo_homonimo():
    """A trava que já existia e tem de continuar: num monorepo, um `pedido.test.js` do
    painel não dá "tem teste" para o `Pedido.php` da API."""
    bases = judge.bases_do_teste(Path('admin/pedido.test.js').stem)
    assert (Path('api/Pedido.php').stem.lower(), '.php') not in {(b, '.js') for b in bases}


# ------------------------------------------------- o percentual de teste
def test_o_percentual_de_teste_divide_codigo_por_codigo():
    """Numerador e denominador no MESMO universo. Com PNG e SVG no denominador, 21%
    virava 14% — e o número saía impresso ao lado de "arquivos de código"."""
    caminhos = ['app/a.php', 'app/b.php', 'tests/aTest.php'] + [
        f'public/img/{i}.png' for i in range(97)]
    inv = inventario(arvore=[arquivo('app/a.php')], caminhos=caminhos)

    c = judge.cobertura_de_teste(inv)

    assert (c['testes'], c['codigo'], c['pct']) == (1, 3, 33), c


def test_sem_nenhum_arquivo_de_codigo_a_cobertura_e_none_nunca_zero():
    assert judge.cobertura_de_teste(inventario(caminhos=['leia.md'])) is None


# ------------------------------------------------- quantas pessoas
def _git(onde, *args, **env):
    import os
    import subprocess
    subprocess.run(['git', *args], cwd=onde, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, env={**os.environ, **env})


def test_a_mesma_pessoa_com_seis_emails_e_uma_pessoa(tmp_path):
    """O caso real: um projeto de uma pessoa anunciado como "6 pessoas commitaram" —
    e "há um time, alguém sabe disto" é o oposto do que o histórico dizia."""
    _git(tmp_path, 'init', '-q')
    for i, (nome, email) in enumerate([('Ana Lima', 'ana@casa.local'),
                                       ('Ana Lima', 'ana@trabalho.local'),
                                       ('Ana', 'ana@casa.local'),
                                       ('Ana Lima', 'ana@maquina-nova.local')]):
        (tmp_path / f'{i}.txt').write_text(str(i))
        _git(tmp_path, 'add', '-A')
        _git(tmp_path, 'commit', '-q', '-m', f'c{i}',
             GIT_AUTHOR_NAME=nome, GIT_AUTHOR_EMAIL=email,
             GIT_COMMITTER_NAME=nome, GIT_COMMITTER_EMAIL=email)

    r = history.retrato(tmp_path)

    assert r['autores'] == 1, 'quatro identidades da mesma pessoa'
    assert r['identidades'] == 4, 'e o documento diz quantas foram agrupadas'


def test_a_ferramenta_nao_e_integrante_do_time(tmp_path):
    _git(tmp_path, 'init', '-q')
    for i, (nome, email) in enumerate([('Ana Lima', 'ana@casa.local'),
                                       ('Ana Lima', 'noreply@anthropic.com'),
                                       ('dependabot[bot]', 'bot@github.com')]):
        (tmp_path / f'{i}.txt').write_text(str(i))
        _git(tmp_path, 'add', '-A')
        _git(tmp_path, 'commit', '-q', '-m', f'c{i}',
             GIT_AUTHOR_NAME=nome, GIT_AUTHOR_EMAIL=email,
             GIT_COMMITTER_NAME=nome, GIT_COMMITTER_EMAIL=email)

    r = history.retrato(tmp_path)

    assert r['autores'] == 1
    assert r['autores_de_maquina'] == 2
    assert r['commits'] == 3, 'o commit continua contado; quem não conta é como pessoa'


def test_nome_de_uma_palavra_nao_junta_duas_pessoas(tmp_path):
    """`admin`, `root`, `ubuntu`, o nome do repositório — um nome de uma palavra é tão
    provável ser login de máquina quanto pessoa, e unir por ele juntaria duas pessoas
    que só configuraram o git do mesmo jeito."""
    _git(tmp_path, 'init', '-q')
    for i, (nome, email) in enumerate([('admin', 'ana@casa.local'),
                                       ('admin', 'bia@casa.local')]):
        (tmp_path / f'{i}.txt').write_text(str(i))
        _git(tmp_path, 'add', '-A')
        _git(tmp_path, 'commit', '-q', '-m', f'c{i}',
             GIT_AUTHOR_NAME=nome, GIT_AUTHOR_EMAIL=email,
             GIT_COMMITTER_NAME=nome, GIT_COMMITTER_EMAIL=email)

    assert history.retrato(tmp_path)['autores'] == 2


# ------------------------------------------------- o percentual honesto
def test_cento_por_cento_exige_ser_cem_por_cento():
    assert pct_honesto(764, 767) == 99, '764 de 767 não é 100%'
    assert pct_honesto(767, 767) == 100
    assert pct_honesto(1, 767) == 1, 'e 0,1% não é 0%, que se lê como nada resolvido'
    assert pct_honesto(0, 767) == 0
    assert pct_honesto(0, 0) == 0


# ------------------------------------------------- o motivo escrito uma vez
def test_o_motivo_igual_em_todas_as_perguntas_e_escrito_uma_vez():
    derivadas = [{'pergunta': f'p{i}', 'porque': 'o mesmo molde', 'evidencia': []}
                 for i in range(3)]
    derivadas.append({'pergunta': 'outra', 'porque': 'outro molde', 'evidencia': []})

    grupos = questions.agrupar(derivadas)

    assert [(m, len(ps)) for m, ps in grupos] == [('o mesmo molde', 3), ('outro molde', 1)]


def test_a_pergunta_do_arquivo_perigoso_nao_afirma_superlativo():
    """`perigo` exige os dois sinais juntos, e o arquivo MAIS importado do projeto
    muitas vezes não está nela, porque é estável. A frase saía em três linhas, uma
    delas com 19 dependentes, enquanto o arquivo de 100 dependentes não recebia
    pergunta nenhuma."""
    inv = {'julgamento': {'perigo': [{'caminho': 'app/x.php', 'dependentes': 19,
                                      'mudancas': 10}]}}

    porque = questions._perigosos(inv)[0]['porque']

    assert 'mais gente' not in porque, porque
    assert 'coincidem' in porque


# ------------------------------------------------- o que o framework carrega
def test_pasta_de_configuracao_fica_fora_de_ninguem_parece_usar():
    """`config/Themes.php` é o mapa prefixo-de-URL → módulo: é o que faz as superfícies
    HTTP existirem, e o framework o carrega por caminho, nunca por `use`. Dois projetos
    diferentes trouxeram o mesmo falso positivo, os dois em `config/`."""
    from datetime import datetime, timedelta, timezone
    velho = (datetime.now(timezone.utc) - timedelta(days=700)).isoformat()
    arvore = [arquivo('config/Themes.php'), arquivo('app/orfao.php')]
    inv = inventario(arvore=arvore, resolucao={'php': contagem(relativos=10)})
    ultima = {'config/Themes.php': velho, 'app/orfao.php': velho}

    achados = {a['caminho'] for a in judge.sem_alcance(inv, ultima)}

    assert 'config/Themes.php' not in achados
    assert 'app/orfao.php' in achados, 'o resto da lista continua'


# ------------------------------------------------- o documento inteiro
def test_o_documento_nomeia_o_projeto_no_titulo(tmp_path):
    """Um arquivo chamado `guide.md` com título "Guia do projeto" não sobrevive a ser
    anexado num e-mail: quem recebe não sabe de qual sistema ele é."""
    varrer(FIXTURES / 'invisible_coupling', tmp_path)
    assert montar(tmp_path).returncode == 0
    primeira = (tmp_path / 'guide.md').read_text().splitlines()[0]

    assert primeira == '# invisible_coupling — guia do projeto', primeira


def test_o_limiar_escrito_e_o_limiar_aplicado(tmp_path):
    """O texto dizia "mais de 10 commits" e a lista imprimia linhas com exatamente 10.
    Num documento cuja promessa é mostrar o limiar que decidiu, errar por um é caro."""
    fonte = (RAIZ / 'scripts' / 'build.py').read_text(encoding='utf-8')
    bloco = re.search(r'Os três sinais \*\*juntos\*\*.*?\n.*?commits de histórico', fonte)

    assert bloco, 'a frase do limiar saiu do build.py'
    assert 'ou mais' in bloco.group(0), bloco.group(0)
    assert 'mais de' not in bloco.group(0), bloco.group(0)


def test_o_percentual_de_teste_sai_com_o_denominador_por_extenso(tmp_path):
    varrer(FIXTURES / 'polyglot_with_code', tmp_path)
    assert montar(tmp_path).returncode == 0
    texto = (tmp_path / 'guide.md').read_text()

    assert 'stack(s)' not in texto, 'plural não resolvido na primeira seção de conteúdo'
    linha = next((l for l in texto.splitlines() if 'arquivos de código' in l), '')
    assert re.search(r'\d+ dos \d+ arquivos de código', linha), linha


def test_a_regra_de_teste_tem_um_dono_so():
    """Havia uma segunda definição de `_eh_teste` no `page.py`, byte a byte igual à do
    `judge.py`: a que o julgamento usa para decidir o que é código vivo e a que o
    documento usa para imprimir a cobertura. Duas cópias divergem na primeira mudança."""
    fonte = (RAIZ / 'scripts').rglob('*.py')
    donos = [p.relative_to(RAIZ).as_posix() for p in fonte
             if re.search(r'^def _?eh_teste\(', p.read_text(encoding='utf-8'), re.M)]

    assert donos == ['scripts/lib/judge.py'], donos
