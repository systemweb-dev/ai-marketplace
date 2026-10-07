"""O que o histórico do git diz sobre acoplamento.

Arquivos que mudam juntos revelam acoplamento que import nenhum mostra. Mas
consultoria que recebe projeto de terceiro recebe zip ou `initial import`: SEM
HISTÓRICO É O CASO NORMAL, não a borda. Quando não há amostra, isso vira lacuna
com motivo — nunca seção omitida, porque omissão se lê como "nada muda junto".
"""
import subprocess
from collections import Counter
from itertools import combinations
from pathlib import Path

from lib.stacks import IGNORAR

MIN_COMMITS = 50      # abaixo disso, co-mudança é ruído
TETO_ARQUIVOS = 50    # commit maior que isso é reformat/lint em massa
MAX_PARES = 40        # quantos pares o inventário carrega


def _git(raiz, *args):
    r = subprocess.run(['git', *args], cwd=str(raiz), capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout


def _de_um_repo(raiz) -> dict:
    """Co-mudança de UM repositório, ou a lacuna com o motivo."""
    raiz = Path(raiz)
    vazio = {'commits': 0, 'co_mudanca': [], 'commits_descartados': 0, 'lacuna': None}

    # `git log` SOBE a árvore de diretórios: apontar para um subdiretório de um
    # monorepo devolvia commits e co-mudança de arquivos fora do escopo auditado.
    # Pior: as fixturas de teste vão para dentro deste repositório no `make sync`,
    # então sem esta checagem o teste "sem histórico" passa a ver o histórico daqui.
    topo = _git(raiz, 'rev-parse', '--show-toplevel')
    if topo is None:
        return {**vazio, 'lacuna': 'não há repositório git aqui — '
                                   'co-mudança não pode ser apurada'}
    if Path(topo.strip()).resolve() != raiz.resolve():
        return {**vazio, 'lacuna': f'o repositório git começa em {topo.strip()}, acima do '
                                   f'projeto auditado — a co-mudança seria de outro escopo'}

    # `--follow`/`-M` para o arquivo renomeado não virar dois
    saida = _git(raiz, 'log', '-M', '--name-only', '--pretty=format:%H%x09%aI')
    if not saida:
        return {**vazio, 'lacuna': 'o repositório não tem nenhum commit ainda'}

    commits, atual = [], None
    for linha in saida.split('\n'):
        if '\t' in linha and len(linha.split('\t')[0]) == 40:
            atual = {'data': linha.split('\t')[1], 'arquivos': []}
            commits.append(atual)
        elif linha.strip() and atual is not None:
            atual['arquivos'].append(linha.strip())

    if len(commits) < MIN_COMMITS:
        return {**vazio, 'commits': len(commits),
                'lacuna': f'só {len(commits)} commits no histórico; abaixo de {MIN_COMMITS} '
                          f'a co-mudança é ruído, não sinal'}

    uteis = [c for c in commits if 1 < len(c['arquivos']) <= TETO_ARQUIVOS]
    descartados = sum(1 for c in commits if len(c['arquivos']) > TETO_ARQUIVOS)

    pares = Counter()
    for c in uteis:
        for a, b in combinations(sorted(set(c['arquivos'])), 2):
            pares[(a, b)] += 1

    return {
        'commits': len(commits),
        'commits_descartados': descartados,
        'co_mudanca': [{'arquivos': list(par), 'vezes': n}
                       for par, n in sorted(pares.most_common(MAX_PARES),
                                            key=lambda x: (-x[1], x[0]))],
        'lacuna': None,
    }


def historico(raiz) -> dict:
    """Co-mudança do projeto, olhando um nível abaixo quando a raiz não tem git.

    **Monorepo por justaposição** é o formato normal de projeto recebido: `/projeto`
    sem `.git`, mas `/projeto/api`, `/projeto/admin` e `/projeto/website` com
    repositório próprio. Num projeto real isso eram 782 commits em quatro
    sub-repositórios, e o documento afirmava "não há repositório git aqui" — uma
    falsidade com o fato a um nível de profundidade.
    """
    raiz = Path(raiz)
    proprio = _de_um_repo(raiz)
    if proprio['lacuna'] is None:
        return proprio

    subs = []
    try:
        filhos = sorted(p for p in raiz.iterdir() if p.is_dir() and p.name not in IGNORAR)
    except OSError:
        return proprio
    for filho in filhos:
        if not (filho / '.git').exists():
            continue
        h = _de_um_repo(filho)
        if h['commits']:
            subs.append((filho.name, h))

    if not subs:
        return proprio

    # Os caminhos ganham o prefixo do sub-repositório, senão `src/App.php` de dois
    # sub-repos diferentes viraria o mesmo arquivo no documento.
    co_mudanca = []
    for nome, h in subs:
        for c in h['co_mudanca']:
            co_mudanca.append({'arquivos': [f'{nome}/{a}' for a in c['arquivos']],
                               'vezes': c['vezes']})
    co_mudanca.sort(key=lambda c: (-c['vezes'], c['arquivos']))

    total = sum(h['commits'] for _, h in subs)
    sem_amostra = [nome for nome, h in subs if h['lacuna']]
    aviso = (f'; sem amostra suficiente em {", ".join(sem_amostra)}' if sem_amostra else '')
    return {
        'commits': total,
        'commits_descartados': sum(h['commits_descartados'] for _, h in subs),
        'co_mudanca': co_mudanca[:MAX_PARES],
        'subrepos': [{'caminho': nome, 'commits': h['commits']} for nome, h in subs],
        'lacuna': (f'a raiz não é repositório git; a co-mudança vem de '
                   f'{len(subs)} sub-repositórios ({", ".join(n for n, _ in subs)}){aviso}'),
    }
