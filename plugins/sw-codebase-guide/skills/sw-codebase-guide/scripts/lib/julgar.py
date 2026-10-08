"""O julgamento: as quatro perguntas de quem recebe um projeto.

Até aqui a skill descrevia. Este módulo é o primeiro que **opina** — e opinar é
exatamente onde ela pode virar a prosa plausível que existe para evitar. A regra que
governa o arquivo inteiro:

    **nada de nota.** Cada julgamento é um SINAL MEDIDO, um LIMIAR DECLARADO e a
    frase do que ele NÃO diz.

Nenhuma função daqui inventa número: tudo vem do inventário, que já foi apurado por
script. O que elas acrescentam é o recorte — quais números, juntos, respondem a
pergunta — e o limiar, que tem valor escrito pelo mesmo motivo do `areas.py`: sem
número, cada projeto se comporta diferente por motivo que ninguém sabe explicar.
"""
from datetime import datetime, timezone
from pathlib import Path

from lib.arvore import eh_codigo, linguagem_de

# Perigo: os três sinais precisam coincidir. Isoladamente nenhum diz nada — arquivo
# muito importado pode ser estável, arquivo que muda muito pode ser isolado.
MIN_DEPENDENTES = 5
MIN_COMMITS = 10        # churn: abaixo disto o arquivo é estável, não quente

# Sem alcance: um ano parado. Abaixo disso é projeto em andamento, não abandono.
DIAS_PARADO = 365

PISO_RESOLUCAO = 0.70   # o mesmo do documento: abaixo disto não se afirma nada

# Arquivo que NINGUÉM importa de propósito: ferramenta o carrega por convenção, pelo
# nome ou pelo lugar. Sem esta lista, os primeiros "candidatos a morto" de um projeto
# real eram `babel.config.js` e um `.js` dentro de `public/` — dois falsos positivos
# no topo destroem a confiança na lista inteira.
ENTRADAS_POR_CONVENCAO = ('config.js', 'config.ts', 'config.mjs', 'config.cjs',
                          'conf.py', 'setup.py', 'manage.py', 'wsgi.py', 'asgi.py',
                          'gulpfile.js', 'gruntfile.js', 'webpack.mix.js')
PASTAS_SERVIDAS = ('public/', 'static/', 'dist/', 'assets/vendor/', 'www/')
# front controller: o servidor o chama, nenhum arquivo o importa
ENTRADAS_DE_SERVIDOR = ('index.php', 'index.html', 'main.py', '__main__.py')

# Papel que o FRAMEWORK instancia por convenção — por nome, por rota em string, por
# descoberta de pasta. Nenhum arquivo os importa, e isso não diz nada sobre eles
# estarem vivos: é literalmente a primeira das cinco cegueiras que o documento
# declara. Num projeto real, o terceiro "candidato a morto" era um controller que a
# rota alcança por string, e lista de candidatos cheia de controller é pior que
# lista nenhuma.
PAPEIS_POR_CONVENCAO = ('controller', 'middleware', 'command', 'job', 'listener',
                        'subscriber', 'handler', 'seeder', 'migration', 'factory',
                        'provider', 'scheduler', 'rule', 'policy')

# Nome que denuncia credencial. Não é lista de segredos — é lista de PALAVRAS que
# aparecem em nome de variável; o valor nunca é lido.
PALAVRAS_DE_CREDENCIAL = ('secret', 'token', 'password', 'passwd', 'senha', 'key',
                          'apikey', 'api_key', 'private', 'credential', 'auth')


def _eh_teste(caminho: str) -> bool:
    c = caminho.lower()
    return ('test' in c or 'spec' in c or '__tests__' in c) and 'contest' not in c


def _taxa(c: dict) -> float:
    resolvidos = (c['relativos'] + c['sufixo_unico'] + c['base_provada']
                  + c['config_conferida'])
    denominador = (resolvidos + c['ambiguos'] + c['pendurados']
                   + c['nao_resolvidos'])
    return resolvidos / denominador if denominador else 0.0


def linguagens_confiaveis(inv: dict) -> set:
    """As linguagens cuja medição passou do piso. Fora delas, nada se afirma."""
    return {ling for ling, c in (inv['imports'].get('resolucao') or {}).items()
            if _taxa(c) >= PISO_RESOLUCAO}


def onde_e_perigoso(inv: dict, por_arquivo: dict) -> list:
    """Os arquivos em que mexer alcança muita gente, que mudam muito, e sem teste.

    Os três sinais **juntos**, nunca isolados: arquivo muito importado pode ser
    estável há anos, e arquivo que muda toda semana pode não ter dependente nenhum.
    É a coincidência dos três que descreve perigo — e mesmo ela é descrição, não
    veredito: o documento mostra os três números ao lado do nome.

    O churn vem da contagem de commits por arquivo, não da co-mudança: aquela é
    cortada em 40 pares e deixava sem dado justamente os arquivos mais importados —
    num monorepo real, zero arquivos perigosos num projeto com arquivo de 38
    dependentes.
    """
    dependentes = {}
    for aresta in inv['imports']['arestas']:
        dependentes.setdefault(aresta['para'], set()).add(aresta['de'])

    # o nome do teste conta junto com a EXTENSÃO: sem isso, um `pedido.test.js` do
    # painel Vue dava "tem teste" para o `Pedido.php` da API, e num monorepo isso
    # zerava a lista inteira
    universo = inv.get('caminhos_do_projeto') or []
    nomes_de_teste = set()
    for c in universo:
        if _eh_teste(c):
            p_teste = Path(c)
            base = p_teste.stem.lower().replace('.test', '').replace('.spec', '')
            nomes_de_teste.add((base, p_teste.suffix.lower()))

    achados = []
    for caminho, quem in dependentes.items():
        if _eh_teste(caminho) or len(quem) < MIN_DEPENDENTES:
            continue
        mudancas = (por_arquivo.get(caminho) or {}).get('commits', 0)
        if mudancas < MIN_COMMITS:
            continue
        alvo = Path(caminho)
        if (alvo.stem.lower(), alvo.suffix.lower()) in nomes_de_teste:
            continue
        achados.append({'caminho': caminho, 'dependentes': len(quem),
                        'mudancas': mudancas})
    return sorted(achados, key=lambda a: (-a['dependentes'], a['caminho']))


def sem_alcance(inv: dict, ultima_mudanca: dict, agora=None) -> list:
    """Arquivos que nenhum import alcança e que ninguém toca há mais de um ano.

    **Isto é pergunta, não veredito.** "Está morto" é literalmente a frase que a
    skill promete nunca dizer: o grafo não vê injeção de dependência, rota como
    string, reflexão nem template, e num framework em que a rota escolhe o
    controller por string o arquivo mais vivo do projeto não tem import nenhum
    apontando para ele.

    Por isso há três travas: só linguagem cuja medição passou do piso, só arquivo
    parado há mais de um ano, e o texto sai como pergunta para levar a quem conhece
    o sistema.
    """
    confiaveis = linguagens_confiaveis(inv)
    if not confiaveis:
        return []
    from lib.imports import POR_EXTENSAO

    alcancados = {a['para'] for a in inv['imports']['arestas']}
    # o que a superfície já reconheceu é alcançado de fora do código: rota, job,
    # comando e migration não têm quem os importe, por desenho
    superficie = {s['caminho'] for s in (inv.get('superficie') or [])}
    agora = agora or datetime.now(timezone.utc)
    achados = []
    for item in inv['arvore']:
        caminho = item['caminho']
        if item['gerado'] or _eh_teste(caminho) or caminho in alcancados:
            continue
        nome = Path(caminho).name.lower()
        if (nome.endswith(ENTRADAS_POR_CONVENCAO) or '.config.' in nome
                or nome in ENTRADAS_DE_SERVIDOR):
            continue
        if any(f'/{pasta}' in f'/{caminho}' for pasta in PASTAS_SERVIDAS):
            continue
        sem_extensao = Path(caminho).stem.lower()
        if any(sem_extensao.endswith(papel) for papel in PAPEIS_POR_CONVENCAO):
            continue
        if caminho in superficie:
            continue
        if POR_EXTENSAO.get(Path(caminho).suffix.lower()) not in confiaveis:
            continue
        quando = ultima_mudanca.get(caminho)
        if not quando:
            continue
        parado = (agora - datetime.fromisoformat(quando)).days
        if parado < DIAS_PARADO:
            continue
        achados.append({'caminho': caminho, 'dias_parado': parado})
    return sorted(achados, key=lambda a: (-a['dias_parado'], a['caminho']))


def risco_visivel(inv: dict, rastreados: set) -> list:
    """O que dá para ver sem rede e sem executar nada.

    Deliberadamente curto. Varredura de segurança de verdade é outra ferramenta;
    aqui entram só os três achados que a varredura já tem na mão e que custam caro
    quando passam despercebidos na primeira semana de um projeto recebido.

    O valor de uma variável **nunca** é lido: o inventário carrega só os nomes, e
    estes achados falam de nome e de arquivo, nunca de conteúdo.
    """
    achados = []
    ambiente = inv.get('ambiente') or {}

    for arquivo in sorted(ambiente):
        nome = Path(arquivo).name.lower()
        eh_exemplo = nome.endswith(('.example', '.sample', '.dist', '.template'))
        if nome.startswith('.env') and not eh_exemplo and arquivo in rastreados:
            # `.env` no disco é normal; `.env` VERSIONADO é credencial publicada, e
            # a diferença entre as duas é uma consulta ao git. Sem ela o achado sai
            # como "pode estar versionado", que é palpite com cara de alerta.
            achados.append({'tipo': 'env-versionado', 'onde': arquivo,
                            'o_que': 'está no controle de versão'})

    exemplos = {a for a in ambiente if Path(a).name.lower().startswith('.env')
                and Path(a).name.lower().endswith(('.example', '.sample', '.dist'))}
    if exemplos:
        declarados = set()
        for a in exemplos:
            declarados |= set(ambiente[a])
        for arquivo, chaves in sorted(ambiente.items()):
            if arquivo in exemplos:
                continue
            faltando = [c for c in chaves if c not in declarados
                        and any(p in c.lower() for p in PALAVRAS_DE_CREDENCIAL)]
            if faltando:
                achados.append({
                    'tipo': 'credencial-nao-documentada', 'onde': arquivo,
                    'o_que': (f'{len(faltando)} '
                              + ('variável' if len(faltando) == 1 else 'variáveis')
                              + ' com cara de credencial que o arquivo de exemplo '
                              + 'não declara: ' + ', '.join(sorted(faltando)[:5]))})
    return achados


def dossie_de_decisao(inv: dict) -> dict:
    """Os números que a pergunta "vale manter ou reescrever?" precisa — e o que falta.

    A skill **não responde** essa pergunta, e isso é desenho, não limitação técnica:
    a resposta depende de quanto custa reescrever e do que o negócio depende, e o
    código não contém nenhum dos dois. O que ela faz é pôr a mesa — e dizer, por
    escrito, qual é o número que falta.
    """
    retrato = inv.get('retrato') or {}
    universo = inv.get('caminhos_do_projeto') or []
    codigo = [a for a in inv['arvore'] if eh_codigo(linguagem_de(Path(a['caminho'])))]
    testes = sum(1 for c in universo if _eh_teste(c))
    resolucao = inv['imports'].get('resolucao') or {}
    return {
        'autores': retrato.get('autores'),
        'commits': retrato.get('commits'),
        'semanas_de_vida': retrato.get('semanas_de_vida'),
        'semanas_parado': retrato.get('semanas_parado'),
        'arquivos_de_codigo': len(codigo),
        'pct_teste': round(testes * 100 / len(universo)) if universo else None,
        'stacks': len({s['stack'] for s in (inv.get('stacks') or [])}),
        'linguagens_medidas': sorted(linguagens_confiaveis(inv)),
        'falta': ('quanto custa reescrever e o que o negócio depende disto — '
                  'nenhum dos dois está no código'),
    }
