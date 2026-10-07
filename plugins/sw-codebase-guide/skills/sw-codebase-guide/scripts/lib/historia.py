"""O que o histórico do git diz sobre acoplamento.

Arquivos que mudam juntos revelam acoplamento que import nenhum mostra. Mas
consultoria que recebe projeto de terceiro recebe zip ou `initial import`: SEM
HISTÓRICO É O CASO NORMAL, não a borda. Quando não há amostra, isso vira lacuna
com motivo — nunca seção omitida, porque omissão se lê como "nada muda junto".
"""
import subprocess
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from lib.stacks import IGNORAR

MIN_COMMITS = 50      # abaixo disso, co-mudança é ruído
TETO_ARQUIVOS = 50    # commit maior que isso é reformat/lint em massa
MAX_PARES = 40        # quantos pares o inventário carrega


def _git(raiz, *args, segundos: int = 20):
    """Roda git com TETO DE TEMPO. Estourando, devolve None e o chamador cai para o
    critério sem git — o spec exige isso: um `git log` de repositório gigante não
    pode travar a primeira tela da skill."""
    try:
        r = subprocess.run(['git', *args], cwd=str(raiz), capture_output=True,
                           text=True, timeout=segundos)
    except subprocess.TimeoutExpired:
        return None          # o chamador cai para o critério sem git
    if r.returncode != 0:
        return None
    return r.stdout


def _cruza_ou_entra(par, area: str) -> bool:
    """O par tem pelo menos UMA ponta dentro da área?

    Uma ponta, não as duas: o valor da seção está justamente no par que CRUZA a
    fronteira — é ele que vira "para mexer nesta área você mexe lá fora".
    """
    prefixo = f'{area}/'
    return any(a == area or a.startswith(prefixo) for a in par)


def _de_um_repo(raiz, prefixo: str = '', area: str | None = None) -> dict:
    """Co-mudança de UM repositório, ou a lacuna com o motivo.

    `prefixo` é o nome do sub-repositório quando a chamada vem do monorepo por
    justaposição, e existe para que o filtro de área compare o caminho COMPLETO.
    Filtrar sem ele comparava `area='api'` com `app/X.php` e zerava tudo — 2 pares
    viravam 0, e o documento voltava a dizer "a raiz não é repositório git".

    O filtro também precisa rodar ANTES do corte em `MAX_PARES`, que é global:
    peneirar os 40 pares do projeto devolveria um ou dois para a área, apagando
    exatamente o sinal que a seção existe para dar.
    """
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

    completo = (lambda a: f'{prefixo}/{a}' if prefixo else a)
    ordenados = sorted(pares.items(), key=lambda x: (-x[1], x[0]))
    if area:
        ordenados = [(par, n) for par, n in ordenados
                     if _cruza_ou_entra([completo(a) for a in par], area)]

    return {
        'commits': len(commits),
        'commits_descartados': descartados,
        'co_mudanca': [{'arquivos': list(par), 'vezes': n}
                       for par, n in ordenados[:MAX_PARES]],
        'lacuna': None,
    }


def historico(raiz, area: str | None = None) -> dict:
    """Co-mudança do projeto, olhando um nível abaixo quando a raiz não tem git.

    **Monorepo por justaposição** é o formato normal de projeto recebido: `/projeto`
    sem `.git`, mas `/projeto/api`, `/projeto/admin` e `/projeto/website` com
    repositório próprio. Num projeto real isso eram 782 commits em quatro
    sub-repositórios, e o documento afirmava "não há repositório git aqui" — uma
    falsidade com o fato a um nível de profundidade.
    """
    raiz = Path(raiz)
    proprio = _de_um_repo(raiz, area=area)
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
        h = _de_um_repo(filho, prefixo=filho.name, area=area)
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


def subrepos(raiz) -> list:
    """Os repositórios git um nível abaixo da raiz.

    Monorepo por justaposição é o formato normal de projeto recebido, e a regra de
    descer um nível estava copiada em cada consumidor — o `retrato` foi escrito
    depois e esqueceu dela, e o documento passou a dizer "não há repositório git
    aqui" ao lado de 782 commits de co-mudança.
    """
    try:
        return [p for p in sorted(Path(raiz).iterdir())
                if p.is_dir() and p.name not in IGNORAR and (p / '.git').exists()]
    except OSError:
        return []


def commits_por_pasta(raiz, dias: int = 90) -> dict:
    """Quantos commits do período tocaram cada diretório, do primeiro nível em diante.

    É consulta PRÓPRIA da fase de áreas, não um subproduto do `historico()`: aquele
    devolve total e pares de co-mudança, não contagem por diretório. Sem isto o menu
    de escopo não tem como ordenar pelo que está sendo mexido agora.

    **Desce um nível quando a raiz não tem git**, pelo mesmo motivo do `historico()`:
    monorepo por justaposição é o formato normal de projeto recebido. Num projeto real
    eram quatro sub-repositórios com 782 commits, e o menu ordenava as quatro
    aplicações por tamanho — ou seja, oferecia primeiro a maior, não a viva.
    """
    # `git log` sobe a árvore: sem a guarda de topo o menu ordenaria pela história de
    # outro repositório. Medido: apontando para um subdiretório, a contagem trazia
    # pastas de fora do escopo auditado.
    topo = _git(raiz, 'rev-parse', '--show-toplevel')
    if topo is not None and Path(topo.strip()).resolve() == Path(raiz).resolve():
        return _contar_pastas(raiz, dias)[0]

    por_pasta = {}
    for filho in subrepos(raiz):
        dentro, commits = _contar_pastas(filho, dias)
        if not commits:
            continue
        # O sub-repositório inteiro é uma área, e é a que o menu oferece: ela precisa
        # da contagem de COMMITS do sub-repo, não da soma das pastas de dentro (que
        # contaria o mesmo commit uma vez por pasta tocada).
        por_pasta[filho.name] = commits
        for pasta, n in dentro.items():
            por_pasta[f'{filho.name}/{pasta}'] = n
    return por_pasta


def _contar_pastas(raiz, dias: int) -> tuple:
    """As pastas tocadas no período e quantos commits houve. Sem guarda de topo: quem
    chama já decidiu que `raiz` é a raiz de um repositório."""
    # Sentinela `\x01` em vez de `len(linha) == 40`: caminho de arquivo com
    # exatamente 40 caracteres e sem espaço era descartado em silêncio.
    saida = _git(raiz, 'log', f'--since={dias}.days', '--name-only',
                 '--pretty=format:\x01%H')
    if not saida:
        return {}, 0

    por_pasta, deste_commit, commits = {}, set(), 0

    def fechar():
        nonlocal commits
        for pasta in deste_commit:
            por_pasta[pasta] = por_pasta.get(pasta, 0) + 1
        deste_commit.clear()

    for linha in saida.split('\n'):
        if linha.startswith('\x01'):
            fechar()           # conta COMMITS, não toques de arquivo: dois commits
            commits += 1       # tocando `api/` devolviam 3 com a contagem direta
            continue
        linha = linha.strip()
        if not linha:
            continue
        partes = linha.split('/')
        for i in range(1, len(partes)):
            deste_commit.add('/'.join(partes[:i]))
    fechar()
    return por_pasta, commits


def retrato(raiz) -> dict:
    """Os quatro números que decidem se vale pegar o projeto, e com que cuidado.

    São descrição, não julgamento — mas é a descrição que responde a primeira
    pergunta de quem recebe um projeto: *dá para assumir isto?* Quantas pessoas
    conhecem o código (o fator ônibus), há quanto tempo ele existe e há quanto
    tempo ninguém encosta nele.

    **Nunca devolve zero no lugar de "não sei".** Sem git, `autores` vem `None` e
    a `lacuna` diz por quê: `0 autores` se lê como *ninguém mexe nisso*, e `1` se
    lê como *uma pessoa só* — a diferença entre as duas é todo o valor do número.
    """
    vazio = {'autores': None, 'commits': None, 'primeiro_commit': None,
             'ultimo_commit': None, 'semanas_de_vida': None,
             'semanas_parado': None, 'lacuna': None}

    # a MESMA guarda de topo das outras consultas: `git log` sobe a árvore
    topo = _git(raiz, 'rev-parse', '--show-toplevel')
    if topo is None:
        # o retrato do CONJUNTO: autores é a união (quem conhece o sistema, não
        # quem conhece um pedaço dele) e a idade vai do commit mais antigo de
        # qualquer sub-repositório ao mais novo de qualquer um
        subs = subrepos(raiz)
        autores, datas = set(), []
        for sub in subs:
            a, d = _autores_e_datas(sub)
            autores |= a
            datas += d
        nomes = ', '.join(s.name for s in subs)
        juntado = _retrato(autores, datas, lacuna=(
            f'a raiz não é repositório git; o retrato é a soma de {len(subs)} '
            f'sub-repositórios ({nomes})'))
        if juntado:
            return juntado
        return {**vazio, 'lacuna': 'não há repositório git aqui — autoria e idade '
                                   'não podem ser apuradas'}
    if Path(topo.strip()).resolve() != Path(raiz).resolve():
        return {**vazio, 'lacuna': f'o repositório git começa em {topo.strip()}, acima do '
                                   f'projeto — o retrato seria de outro escopo'}

    return _retrato(*_autores_e_datas(raiz), lacuna=None) or {
        **vazio, 'lacuna': 'o repositório não tem nenhum commit ainda'}


def _autores_e_datas(raiz) -> tuple:
    """Os autores e as datas de todos os commits de UM repositório."""
    saida = _git(raiz, 'log', '--pretty=format:%aE\t%aI')
    autores, datas = set(), []
    for linha in (saida or '').split('\n'):
        if '\t' not in linha:
            continue
        email, data = linha.split('\t', 1)
        autores.add(email.strip().lower())
        datas.append(data.strip())
    return autores, datas


def _retrato(autores: set, datas: list, lacuna) -> dict | None:
    if not datas:
        return None
    datas = sorted(datas)
    primeiro = datetime.fromisoformat(datas[0])
    ultimo = datetime.fromisoformat(datas[-1])
    agora = datetime.now(timezone.utc)
    return {
        'autores': len(autores),
        'commits': len(datas),
        'primeiro_commit': datas[0],
        'ultimo_commit': datas[-1],
        'semanas_de_vida': (ultimo - primeiro).days // 7,
        'semanas_parado': max(0, (agora - ultimo).days // 7),
        'lacuna': lacuna,
    }
