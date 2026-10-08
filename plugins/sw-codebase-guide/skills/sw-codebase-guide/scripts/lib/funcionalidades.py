"""As funcionalidades do projeto, pelo vocabulário que o próprio código usa.

O `areas.py` responde *onde*; este responde *o quê*. Quem recebe um projeto não
pergunta por `src/app/(app)`, pergunta pelo cadastro, pelo faturamento, pelo
funil — e o nome dessas coisas já está escrito no código, só não está em lugar
nenhum reunido.

**A hipótese, medida antes de escrever o módulo:** uma funcionalidade é um NOME
que aparece em mais de um PAPEL. Um mesmo nome em `middleware/`, em `services/` e em
`store/` é uma fatia vertical; um nome que aparece num componente e no teste dele
é um arquivo com o teste dele. Rodada em quatro projetos reais (um monorepo PHP+Vue,
um portal de notícias, um CRM Next.js e uma API PHP), a extração devolveu
`cadastro`, `cobranca`, `funil`, `leads`, `relatorio` — e
quatro defeitos, cada um virou uma regra aqui:

1. `[id]` e `(app)` — segmento de roteador não é nome de funcionalidade.
2. `paginacao [component test]` — **teste não conta como papel**: é o espelho do
   arquivo, não uma segunda camada.
3. `site [middleware route]` — no framework PHP toda ÁREA tem middleware e
   arquivo de rotas. Papel que sozinho só declara área não faz funcionalidade, e
   para área já existe o `--areas`.
4. `api [client index service]` — `index` é barril, não camada.

**Duas perguntas, dois rigores.** Para PROPOR o nome no menu, o casamento é
estrito (termo × papel), senão o menu enche de ruído. Para RECORTAR, depois que
alguém escolheu o termo, ele é largo (o termo como palavra no nome do arquivo ou
em qualquer pasta do caminho) — no projeto medido isso era a diferença entre 22
arquivos e os 3 que casavam com a regra estrita.
"""
import re
from collections import defaultdict
from pathlib import Path

from lib.arvore import eh_codigo, linguagem_de

# Um termo precisa aparecer em dois papéis para ser fatia vertical. Com 1, todo
# arquivo do projeto vira "funcionalidade"; com 3, o CRM Next.js — onde a fatia
# é `page` + `actions` e mais nada — não tinha funcionalidade nenhuma.
MIN_PAPEIS = 2
# Acima disto, o alvo é de todo mundo: ele continua no recorte, mas numa lista
# própria, dizendo quantos o importam. O número veio da medição: no projeto real,
# o que a fatia do cadastro alcançava se partia em dois grupos nítidos —
# três alvos com 2 importadores de fora cada, contra outros com 11, 15, 29 e 37.
TETO_COMPARTILHADO = 10
# Núcleo maior que isto não é funcionalidade, é área — e dizer isso vale mais que
# entregar 148 arquivos chamando-os de uma funcionalidade. O termo mais largo do
# projeto medido pegava 19% de tudo.
TETO_NUCLEO = 60

PAPEIS = {
    'controller', 'service', 'middleware', 'job', 'model', 'repository',
    'handler', 'command', 'listener', 'provider', 'policy', 'resource',
    'request', 'factory', 'seeder', 'migration', 'test', 'spec', 'store',
    'view', 'page', 'component', 'hook', 'helper', 'enum', 'dto', 'mapper',
    'validator', 'actions', 'action', 'route', 'routes', 'rotas', 'schema',
    'type', 'types', 'util', 'utils', 'api', 'form', 'modal', 'card', 'table',
    'list', 'detail', 'index', 'agent', 'client', 'adapter', 'gateway',
    'serializer', 'transformer', 'exception', 'event', 'mail', 'notification',
    'query', 'mutation', 'resolver', 'guard', 'interceptor', 'pipe', 'layout',
}
# Pasta no plural (ou no idioma do projeto) é o mesmo papel do arquivo no
# singular: sem isto `Controllers/` e `Controller.php` eram dois papéis, e um
# arquivo sozinho virava fatia vertical.
SINONIMO = {'controllers': 'controller', 'services': 'service', 'models': 'model',
            'jobs': 'job', 'middlewares': 'middleware', 'middleware': 'middleware',
            'repositories': 'repository', 'helpers': 'helper', 'enums': 'enum',
            'views': 'view', 'pages': 'page', 'components': 'component',
            'hooks': 'hook', 'commands': 'command', 'migrations': 'migration',
            'requests': 'request', 'resources': 'resource', 'policies': 'policy',
            'providers': 'provider', 'listeners': 'listener', 'events': 'event',
            'mails': 'mail', 'tests': 'test', 'agents': 'agent', 'rotas': 'route',
            'routes': 'route', 'schemas': 'schema', 'types': 'type', 'dtos': 'dto'}
NORMALIZAR = {'rotas': 'route', 'routes': 'route', 'actions': 'action',
              'utils': 'util', 'types': 'type', 'policies': 'policy'}

# Papel que não conta para o piso — ver o cabeçalho, defeitos 2 e 4.
NAO_CONTA = {'test', 'spec', 'index'}
# Papéis que, sozinhos, declaram área e não funcionalidade — defeito 3.
SO_AREA = {'middleware', 'route'}

# Termo que não nomeia nada: ou é a própria camada, ou é palavra de arrumação.
RUIDO = {'', 'index', 'app', 'base', 'abstract', 'main', 'common', 'shared',
         'core', 'default', 'new', 'old', 'temp', 'util', 'utils', 'helper',
         'helpers', 'config', 'test', 'tests', 'spec', 'type', 'types'}


def palavras(nome: str) -> list:
    """Quebra `PedidoMiddleware`, `pedido-payload` e `pedido_payload` igual."""
    s = re.sub(r'[-_. ]+', ' ', nome)
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', s)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', s)
    return [p.lower() for p in s.split() if p]


def _casa_sequencia(seq: list, termo: str) -> bool:
    """O termo como PALAVRA, não como substring: `user` não casa `useRouter`."""
    t = termo.split()
    if not t or len(t) > len(seq):
        return False
    return any(seq[i:i + len(t)] == t for i in range(len(seq) - len(t) + 1))


def termo_e_papel(caminho: str) -> tuple | None:
    """O par (termo, papel) de um arquivo — o casamento ESTRITO, para o menu."""
    p = Path(caminho)
    partes = [x for x in p.parent.parts if x not in ('.', '')]
    ws = palavras(p.stem)
    if not ws:
        return None
    # 1. o nome termina num papel: PedidoMiddleware → (pedido, middleware)
    if len(ws) > 1 and ws[-1] in PAPEIS:
        termo = ' '.join(ws[:-1])
        if termo not in RUIDO:
            return termo, NORMALIZAR.get(ws[-1], ws[-1])
    # 2. o nome É o papel, e a pasta nomeia: funil/page.tsx → (funil, page)
    nome = ' '.join(ws)
    if nome in PAPEIS and partes:
        pai = partes[-1]
        # `[id]`, `[...slug]`, `@modal`: segmento do roteador, não nome de coisa
        if pai.startswith('[') or pai.startswith('@'):
            return None
        termo = ' '.join(palavras(re.sub(r'^\(|\)$', '', pai)))
        if termo and termo not in RUIDO and termo not in SINONIMO:
            return termo, NORMALIZAR.get(nome, nome)
    # 3. a pasta é o papel: Controllers/UserController.php → (user, controller)
    for pasta in reversed(partes):
        chave = pasta.lower()
        papel = SINONIMO.get(chave) or (chave if chave in PAPEIS else None)
        if not papel:
            continue
        termo = ' '.join(w for w in ws if w not in PAPEIS) or nome
        return (termo, NORMALIZAR.get(papel, papel)) if termo not in RUIDO else None
    return None


def _papeis_que_contam(papeis) -> set:
    return {p for p in papeis if p not in NAO_CONTA}


def candidatos(arvore: list) -> list:
    """O menu: os nomes que o código usa para mais de uma camada.

    Ordenado por quantos papéis o termo atravessa — a fatia mais vertical
    primeiro —, e depois por tamanho. Quem escolhe quer ver primeiro o que o
    projeto trata como funcionalidade de verdade.
    """
    por_termo = defaultdict(lambda: defaultdict(list))
    for item in arvore:
        caminho = item['caminho']
        if item.get('gerado') or not eh_codigo(linguagem_de(Path(caminho))):
            continue
        achado = termo_e_papel(caminho)
        if achado:
            por_termo[achado[0]][achado[1]].append(caminho)

    saida = []
    for termo, papeis in por_termo.items():
        uteis = _papeis_que_contam(papeis)
        if len(uteis) < MIN_PAPEIS or uteis <= SO_AREA:
            continue
        arquivos = sorted({c for v in papeis.values() for c in v})
        saida.append({'termo': termo, 'papeis': sorted(uteis),
                      'arquivos': len(arquivos), 'exemplos': arquivos[:3]})
    saida.sort(key=lambda f: (-len(f['papeis']), -f['arquivos'], f['termo']))
    return saida


def casa(caminho: str, termo: str) -> bool:
    """O casamento LARGO, para recortar: o termo como palavra no nome do arquivo
    ou em qualquer pasta do caminho.

    Medido: num cadastro de várias etapas, só o nome do arquivo achava 15
    arquivos e deixava de fora os seis passos do formulário, que moram numa
    pasta com o nome da funcionalidade.
    """
    p = Path(caminho)
    if _casa_sequencia(palavras(p.stem), termo):
        return True
    return any(_casa_sequencia(palavras(d), termo) for d in p.parent.parts)


def recortar(arvore: list, arestas: list, termo: str,
             teto_compartilhado: int = TETO_COMPARTILHADO,
             teto_nucleo: int = TETO_NUCLEO) -> dict:
    """A fatia: o núcleo pelo nome, o que ele alcança, e o que é de todo mundo.

    Os três grupos existem porque a medição mostrou que o arquivo mais
    importante da fatia costuma ser também o mais compartilhado: num projeto
    real, o núcleo alcançava o helper onde mora a regra do formulário — e esse
    helper tem 29 importadores de fora. Deixá-lo de fora perderia a regra;
    chamá-lo de "parte da funcionalidade" seria mentira. Ele entra, e o documento
    diz quantos o importam.

    Os dois tetos são parâmetro, com o padrão declarado no módulo, porque o teste
    precisa provar o limiar sem dimensionar a fixture pela constante: escrito
    como `range(TETO_COMPARTILHADO + 1)`, subir o teto para mil faz a suíte
    alocar mil arquivos falsos — e uma prova de mutação que o levasse a 10**9
    travou a máquina de verdade. O limiar se prova com um teto de 2 e três
    arquivos.
    """
    nucleo = sorted(a['caminho'] for a in arvore if casa(a['caminho'], termo))
    conjunto = set(nucleo)

    sai_de, quem_importa = defaultdict(set), defaultdict(set)
    for a in arestas:
        sai_de[a['de']].add(a['para'])
        quem_importa[a['para']].add(a['de'])

    alcance, compartilhado = [], []
    for alvo in sorted({d for f in nucleo for d in sai_de.get(f, ())} - conjunto):
        de_fora = len(quem_importa[alvo] - conjunto)
        if de_fora > teto_compartilhado:
            compartilhado.append({'caminho': alvo, 'importadores': de_fora})
        else:
            alcance.append(alvo)
    compartilhado.sort(key=lambda x: (-x['importadores'], x['caminho']))

    return {
        'termo': termo,
        'nucleo': nucleo,
        'alcance': alcance,
        'compartilhado': compartilhado,
        # Quem importa a fatia de fora não entra no recorte — é raio de alcance,
        # não conteúdo —, mas o número vai para o documento: é o que responde
        # "quanto custa mexer aqui".
        'usada_por': len({q for f in nucleo for q in quem_importa.get(f, ())} - conjunto),
        'eh_area': len(nucleo) > teto_nucleo,
    }
