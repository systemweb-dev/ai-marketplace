"""Como rodar isto: composição, scripts de manifesto e alvos de Makefile.

A seção "Como entrar" do documento emitia stack, contagem de arquivos e nomes de
variáveis de ambiente — e **nenhum comando**. "Como eu rodo isso?" é a primeira
pergunta de quem recebe um projeto, e a resposta estava em arquivos que a skill
nem abria. Medido em sete projetos reais: 6 arquivos de composição, 17
Dockerfiles, 7 `package.json`, 5 `composer.json`. Todo projeto PHP da casa
declara `start` no `composer.json`.

Três decisões que a medição tomou:

1. **`environment:` não é lido.** Nem os nomes. A seção `ambiente` já extrai
   chave de `.env` na origem, e não abrir o bloco do compose deixa a superfície
   de segredo deste módulo em **zero** — num arquivo que num projeto real tem
   `FLYWAY_PASSWORD` e `RABBITMQ_DEFAULT_PASS` em linha.
2. **Dois arquivos de composição não são desempatados aqui.** Um monorepo real
   tem `infra/` e `infra_v2/`; qual é o atual não está no código.
   Os dois aparecem, e a pergunta vai para a lista de perguntas em aberto.
3. **O gerenciador vem do lockfile.** Mandar `npm run` num repositório `pnpm`
   quebra a instalação de quem acabou de chegar. Sem lockfile, `npm` é suposição
   e o emissor diz isso.

O leitor de YAML é por **indentação**, porque a skill é stdlib pura e não há
PyYAML. Medido contra os 6 arquivos de composição reais: 6 lidos, 0 recusados, 0
no nível errado, conferidos à mão. O que ele não modela — mais de um documento no
arquivo, bloco `services:` ausente — vira lacuna **com o motivo escrito**, nunca
meia lista: serviço inventado manda alguém subir o que não existe.
"""
import json
import re
from pathlib import Path

# Medido: os arquivos de composição de sete projetos têm 1, 6, 7, 8, 12 e 17
# serviços. Com teto 12, o de 17 perdia `scheduler`, `frontend_app` e `website` —
# o relógio do sistema e as duas superfícies que servem o produto. Um teto que
# esconde a porta de entrada não está protegendo o leitor de nada: serviço é uma
# linha, e 24 linhas não afogam ninguém.
TETO_SERVICOS = 24
TETO_SCRIPTS = 12
TETO_ALVOS = 12

# nome de script que a convenção associa a "sobe a aplicação". É indício, não
# prova — sai como dedução, com a lista inteira ao lado para quem discordar.
SUBIR = ('start', 'dev', 'serve')


def _parece_subir(script: str) -> bool:
    """A comparação é por PARTE do nome: `webpack_dev` aparece em três projetos
    reais e a comparação pelo nome inteiro o perdia. `up` saiu da convenção porque
    casava `db:up` — subir o banco não é subir a aplicação, e o palpite errado
    custa mais que o silêncio, já que a lista inteira sai logo ao lado."""
    return any(parte in SUBIR for parte in re.split(r'[_:.-]', script))

# lockfile → gerenciador. A ordem é a da especificidade: um repositório com
# `pnpm-lock.yaml` e `package-lock.json` é pnpm com sobra de npm antigo.
LOCKFILES = (('pnpm-lock.yaml', 'pnpm'), ('yarn.lock', 'yarn'),
             ('bun.lockb', 'bun'), ('package-lock.json', 'npm'))

COMPOSE = re.compile(r'^(docker-)?compose([.-][\w.-]+)?\.ya?ml$', re.I)
MANIFESTOS = {'package.json': 'npm', 'composer.json': 'composer'}
ALVOS_DE = {'makefile': 'make', 'justfile': 'just'}

# Chave de compose que nunca é nome de serviço. Ela parece paranoia até alguém
# indentar `volumes:` por engano dentro de `services:` — o erro mais comum de YAML
# editado à mão —, e o leitor por indentação não tem como saber que aquilo não é
# serviço. Serviço inventado manda alguém subir o que não existe. O prefixo `x-`
# entra pela mesma razão: é o idioma do próprio formato para campo de extensão.
NAO_E_SERVICO = {'image', 'build', 'ports', 'environment', 'volumes', 'networks',
                 'depends_on', 'command', 'restart', 'healthcheck', 'deploy',
                 'container_name', 'env_file', 'labels', 'expose', 'entrypoint',
                 'working_dir', 'user', 'extends', 'profiles', 'secrets'}


def _de_documentacao(caminho: str) -> bool:
    """Compose anexado a um relatório não é o jeito de subir o sistema.

    Medido: `docs/registros/<data>-<assunto>/docker-compose.yml` num projeto real.
    É a mesma regra que tira o dossiê de trabalho das fontes textuais.
    """
    return any(p in ('docs', 'doc', 'documentation') for p in caminho.split('/')[:-1])


def _servicos(texto: str) -> tuple:
    """(serviços, lacuna). O recuo é descoberto na primeira filha, não suposto."""
    if re.search(r'^---\s*$', texto, re.M):
        return [], 'há mais de um documento YAML neste arquivo, e o leitor por ' \
                   'indentação não modela isso'
    linhas = texto.splitlines()
    inicio = next((i for i, l in enumerate(linhas)
                   if re.match(r'^services:\s*(#.*)?$', l)), None)
    if inicio is None:
        return [], 'não há bloco `services:` no primeiro nível'
    recuo, achados = None, []
    for linha in linhas[inicio + 1:]:
        if not linha.strip() or linha.lstrip().startswith('#'):
            continue
        espacos = len(linha) - len(linha.lstrip())
        if espacos == 0:
            break
        if recuo is None:
            recuo = espacos
        if espacos != recuo:
            if achados:
                achados[-1]['linhas'].append(linha)
            continue
        # o corpo pode vir na própria linha (`web: {image: nginx}`): sem isto o
        # serviço desaparecia calado, e lista incompleta com cara de completa é
        # pior que arquivo não lido
        m = re.match(r'^\s*["\']?([A-Za-z0-9_.-]+)["\']?:\s*(\{.*\})?\s*(#.*)?$', linha)
        if m and m.group(1) not in NAO_E_SERVICO \
                and not m.group(1).startswith('x-'):
            achados.append({'nome': m.group(1), 'linhas': [], 'inline': m.group(2) or ''})
    return [{'nome': s['nome'], **_do_bloco(s['linhas'], s['inline'])}
            for s in achados], None


def _lista_inline(corpo: str) -> list:
    """`["a", "b"]` → `['a', 'b']`. YAML em estilo de fluxo é legítimo, e um projeto
    real escreve o compose inteiro assim."""
    dentro = corpo[corpo.index('[') + 1:corpo.rindex(']')] if '[' in corpo and ']' in corpo else ''
    return [x.strip().strip('"\'') for x in dentro.split(',') if x.strip()]


def _do_bloco(linhas: list, inline: str = '') -> dict:
    """Imagem, construção e portas de um serviço. Nada de `environment`."""
    imagem, constroi, portas, em_portas, recuo_portas = None, False, [], False, 0
    if inline:
        if m := re.search(r'\bimage:\s*["\']?([^"\',}]+)', inline):
            imagem = m.group(1).strip()
        constroi = bool(re.search(r'\bbuild:', inline))
        if m := re.search(r'\bports:\s*(\[[^\]]*\])', inline):
            portas = _lista_inline(m.group(1))
        return {'imagem': imagem, 'constroi': constroi, 'portas': portas}
    for linha in linhas:
        espacos = len(linha) - len(linha.lstrip())
        corpo = linha.strip()
        if em_portas:
            if corpo.startswith('- '):
                portas.append(corpo[2:].strip().strip('"\''))
                continue
            if espacos <= recuo_portas:
                em_portas = False
        if m := re.match(r'^image:\s*["\']?([^"\'#]+)', corpo):
            imagem = m.group(1).strip()
        elif re.match(r'^build:', corpo):
            constroi = True
        elif re.match(r'^ports:', corpo):
            if '[' in corpo:
                portas.extend(_lista_inline(corpo))
            else:
                em_portas, recuo_portas = True, espacos
    return {'imagem': imagem, 'constroi': constroi, 'portas': portas}


def _executor(raiz: Path, pasta: str, gerenciador: str) -> tuple:
    """(executor, por). `por` é o lockfile que PROVOU o gerenciador, ou None."""
    if gerenciador == 'composer':
        return 'composer run', ('composer.lock' if (raiz / pasta / 'composer.lock').exists()
                                else None)
    base = raiz / pasta if pasta else raiz
    for arquivo, nome in LOCKFILES:
        if (base / arquivo).exists():
            return f'{nome} run', arquivo
    return 'npm run', None


def apurar(raiz, itens: list, teto_servicos: int = TETO_SERVICOS) -> dict:
    """O que o projeto declara sobre como ser executado.

    `teto_servicos` é parâmetro para o teste poder dimensionar a fixture sem ler a
    constante de produção: uma mutação que levasse o teto a um bilhão fazia a
    fixture alocar um bilhão de strings e travava a máquina.
    """
    raiz = Path(raiz)
    composicoes, comandos, alvos, containers = [], [], [], []
    for item in sorted(itens, key=lambda i: i['caminho']):
        caminho = item['caminho']
        nome = Path(caminho).name
        if _de_documentacao(caminho):
            continue
        if nome.lower().startswith('dockerfile'):
            containers.append(caminho)
            continue
        if item['acima_do_teto']:
            continue
        try:
            texto = (raiz / caminho).read_text('utf-8', 'replace')
        except OSError:
            continue
        pasta = str(Path(caminho).parent) if Path(caminho).parent != Path('.') else ''
        if COMPOSE.match(nome):
            servicos, lacuna = _servicos(texto)
            composicoes.append({'caminho': caminho, 'lacuna': lacuna,
                                'servicos': servicos[:teto_servicos],
                                'omitidos': max(0, len(servicos) - teto_servicos)})
        elif nome in MANIFESTOS:
            try:
                scripts = sorted((json.loads(texto).get('scripts') or {}))
                lacuna = None
            except ValueError as erro:
                scripts, lacuna = [], f'o manifesto não é JSON válido: {erro}'
            if not scripts and not lacuna:
                continue
            executor, por = _executor(raiz, pasta, MANIFESTOS[nome])
            comandos.append({
                'caminho': caminho, 'executor': executor, 'por': por,
                'lacuna': lacuna, 'scripts': scripts[:TETO_SCRIPTS],
                'omitidos': max(0, len(scripts) - TETO_SCRIPTS),
                'candidatos': [s for s in scripts if _parece_subir(s)]})
        elif nome.lower() in ALVOS_DE:
            # `VAR := x` não é alvo, e `.PHONY` é declaração: os dois já apareceram
            # como "comando para rodar" em geradores de documentação
            achados = [m.group(1) for m in
                       re.finditer(r'^([a-zA-Z][\w.-]*):(?!=)', texto, re.M)]
            if not achados:
                continue
            alvos.append({'caminho': caminho, 'executor': ALVOS_DE[nome.lower()],
                          'alvos': achados[:TETO_ALVOS],
                          'omitidos': max(0, len(achados) - TETO_ALVOS)})
    return {'composicoes': composicoes, 'comandos': comandos,
            'alvos': alvos, 'containers': containers}
