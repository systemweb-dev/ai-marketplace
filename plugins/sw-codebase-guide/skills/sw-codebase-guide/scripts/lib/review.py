"""Confere a interpretação — o que o `build.py` aceita e não devia.

O `build.py` tem três recusas duras e elas pegam o que é verificável de forma
binária: afirmação sem evidência, lacuna sem motivo, citação que não existe no
projeto. O que sobra são **fraquezas de julgamento** — e recusar por elas
transformaria julgamento em burocracia. Então aqui ninguém recusa: isto lista, e
quem escreveu decide.

Medido contra as TRÊS interpretações reais que existem em disco, escritas por
agente contra projeto real (1126, 26 e 1025 arquivos; 80 afirmações e 46 blocos
somados; 198 citações com número de linha). Quatro decisões saíram da medição,
todas contra a expectativa:

1. **"Evidência genérica" não é defeito.** A candidata mais óbvia — afirmação cuja
   evidência é só pasta ou só arquivo sem linha — apontaria 12 itens nas três
   interpretações, e lendo um por um quase todos estão CERTOS: *"não é um projeto,
   são cinco repositórios justapostos"* citando as cinco pastas é a evidência
   exata. Bronca injusta ensina a ignorar a ferramenta, então ela não existe aqui.
2. **Pasta citada endereça o arquivo — até um tamanho.** Contar a pasta zerou a
   lacuna do perigo num projeto onde ela é real: `backend/` cobre 430 arquivos
   (41% do projeto) e `backend/app/Dominio/` cobre 135; nenhuma das duas é o
   endereço de um arquivo. A pasta de 8 arquivos, no mesmo material, é. Daí o
   `TETO_DA_PASTA`, e daí o número dele.
3. **Classificar a linha citada por sintaxe não serve.** Comentário é a melhor
   evidência que existe quando o arquivo é um `CLAUDE.md` com os comandos de
   subida; e ` ```bash ` é delimitador que não prova nada, mas não é comentário.
   A pergunta que a guarda faz é mais estreita: a linha tem CONTEÚDO?
4. **O agente cita a saída da própria skill.** Numa das três, uma afirmação sobre
   o projeto tinha `docs/project/inventory.json` como evidência — o leitor do
   documento é mandado conferir um arquivo que a skill escreveu. A guarda do
   `build.py` aceita, porque o arquivo existe mesmo.

E o limite honesto: a conferência da linha **mediu 1 em 198**, e isso não é
evidência de que o defeito é raro. O relato do agente limpo da v0.13.0 diz que ele
citou linha em branco e corrigiu as 60+ citações à mão antes de montar — o material
em disco é pós-correção. Medição não vê o que foi consertado antes de salvar.
"""
import re
from pathlib import Path

from lib import judge, trail

# Quantos arquivos uma pasta citada pode cobrir e ainda ser o ENDEREÇO de um
# arquivo. Calibrado na medição: 8 endereça, 23 e 26 endereçam, 59 em diante não.
# Passa por parâmetro em todo lugar — um teste que dimensiona a fixture pela
# constante de produção para de provar que o padrão serve.
TETO_DA_PASTA = 30

# Quantos dos arquivos mais importados cobrar. Três, porque o quarto e o quinto
# de um projeto real já são detalhe, e lista longa de cobrança é lista ignorada.
TETO_DO_CENTRO = 3

# Quantos itens por achado. Lista de 30 arquivos perigosos não é cobrança, é
# enxurrada — e o que se faz com enxurrada é fechar.
TETO_DE_ITENS = 8

SECOES = ('como-entrar', 'depende-de', 'o-que-faz', 'superficie')
PARTES = ('o-que-e', 'percurso', 'mapa', 'orientacoes')

TITULO_DA_PARTE = {
    'o-que-e': 'O que o produto faz',
    'percurso': 'O percurso de uma funcionalidade',
    'mapa': 'Onde ficam as coisas',
    'orientacoes': 'Para mexer',
}

# Nome de arquivo que só a própria skill escreve. `guide.md` e `readme.md` NÃO
# entram: projeto real tem os dois, e acusar o `readme.md` de alguém seria a
# aresta errada — pior que a aresta faltando.
ARTEFATOS = ('inventory.json', 'inventory.prev.json', 'interpretation.toml',
             'knowledge.toml')

# Linha que não prova nada: só pontuação, cerca de bloco de código, separador.
SEM_CONTEUDO = re.compile(
    r'^[\s{}()\[\];,>]*$|^\s*(```|~~~|---+|===+|\*\*\*+)\s*\w*\s*$')

LINHA = re.compile(r'^(.+):(\d+)$')


def _pedaco(texto: str, quanto: int = 56) -> str:
    """O começo do texto, com reticência quando foi cortado.

    Sem a reticência o corte MENTE: `"copiar .env."` parecia o fim da frase, e o
    item do relatório é lido como citação do que o agente escreveu.
    """
    limpo = ' '.join(texto.split())
    return limpo if len(limpo) <= quanto else limpo[:quanto].rstrip() + '…'


def _cortar(itens: list) -> list:
    """Os primeiros itens, e uma linha dizendo quantos sobraram."""
    if len(itens) <= TETO_DE_ITENS:
        return itens
    return itens[:TETO_DE_ITENS] + [f'… e mais {len(itens) - TETO_DE_ITENS}']


def _sem_linha(ev: str) -> str:
    m = LINHA.match(ev)
    return m.group(1) if m else ev


def _citacoes(itens: list) -> tuple:
    """Os arquivos e as pastas que a interpretação cita, separados."""
    arquivos, pastas = set(), set()
    for x in itens:
        for ev in x.get('evidencia') or []:
            (pastas if ev.endswith('/') else arquivos).add(_sem_linha(ev))
    return arquivos, pastas


def _enderecado(caminho: str, arquivos: set, pastas: set, universo: list,
                teto: int = TETO_DA_PASTA) -> bool:
    """A interpretação diz onde este arquivo está?

    Citação direta conta sempre. Pasta conta quando ela é pequena o bastante para
    ser endereço: mandar o leitor para uma pasta de 8 arquivos é dizer onde está,
    mandá-lo para uma de 430 é dizer em que repositório.
    """
    if caminho in arquivos:
        return True
    for pasta in pastas:
        if not caminho.startswith(pasta):
            continue
        if sum(1 for c in universo if c.startswith(pasta)) <= teto:
            return True
    return False


def _universo(inv: dict) -> list:
    return (inv.get('caminhos_do_projeto')
            or [a['caminho'] for a in inv.get('arvore') or []])


# ───────────────────────────── as conferências ─────────────────────────────
#
# A ordem é a do dano que cada uma causa a quem LÊ o documento: citação que manda
# para o lugar errado antes de seção vazia, seção vazia antes de arquivo que
# ninguém explicou. Não é a ordem em que elas são fáceis de escrever.


def _saida_da_skill(ctx: dict) -> dict | None:
    """Evidência que aponta um arquivo que a própria skill escreveu.

    É circular e o `build.py` aceita, porque o arquivo existe mesmo. Para quem lê
    o documento é pior que citação inventada: ele abre, encontra o arquivo, e o
    que está lá é a medição que gerou a frase.
    """
    achados = []
    for x in ctx['itens']:
        for ev in x.get('evidencia') or []:
            if Path(_sem_linha(ev)).name in ARTEFATOS:
                achados.append(f'`{ev}` — em "{_pedaco(x["texto"])}"')
    if not achados:
        return None
    return {
        'chave': 'saida-da-skill',
        'titulo': 'a evidência aponta a saída da própria skill',
        'itens': _cortar(sorted(set(achados))),
        'conserto': ('cite o arquivo do PROJETO que sustenta a frase; se a frase '
                     'só se sustenta na medição, ela é `deducao` com a evidência '
                     'de código, ou é lacuna'),
    }


def _linha_sem_conteudo(ctx: dict) -> dict | None:
    """A citação aponta uma linha que não prova nada.

    A guarda do `build.py` confere o INTERVALO: `arquivo.py:9000` num arquivo de
    80 linhas é recusado, `README.md:12` apontando ` ```bash ` passa. O leitor
    abre a linha e encontra um delimitador.
    """
    if ctx['projeto'] is None:
        ctx['nao_conferido'].append(
            {'chave': 'linha-sem-conteudo',
             'motivo': 'o conteúdo da linha citada: rode com `--projeto` para conferir'})
        return None
    cache, achados = {}, []
    for x in ctx['itens']:
        for ev in x.get('evidencia') or []:
            if not (m := LINHA.match(ev)):
                continue
            arquivo, numero = m.group(1), int(m.group(2))
            if arquivo not in cache:
                alvo = ctx['projeto'] / arquivo
                try:
                    cache[arquivo] = alvo.read_text('utf-8',
                                                    errors='replace').splitlines()
                except OSError:
                    cache[arquivo] = None
            linhas = cache[arquivo]
            # fora do intervalo é recusa do build, não achado daqui: duas vozes
            # sobre o mesmo defeito mandam consertar duas vezes
            if linhas is None or numero > len(linhas) or numero < 1:
                continue
            if SEM_CONTEUDO.match(linhas[numero - 1]):
                achados.append(f'`{ev}` → `{linhas[numero - 1].strip()}`'
                               f' — em "{_pedaco(x["texto"], 44)}"')
    if not achados:
        return None
    return {
        'chave': 'linha-sem-conteudo',
        'titulo': 'a linha citada não tem conteúdo',
        'itens': _cortar(sorted(set(achados))),
        'conserto': ('aponte a linha que contém o que a frase afirma — quem lê '
                     'abre exatamente esta'),
    }


def _secoes_vazias(ctx: dict) -> dict | None:
    """Seção das quatro que ninguém interpretou.

    O documento já diz isso de si mesmo, mas diz DEPOIS de montado — quando quem
    escreveu já declarou pronto.
    """
    af = ctx['afirmacoes']
    if not af:
        return {'chave': 'secoes-vazias',
                'titulo': 'a interpretação não tem nenhuma afirmação',
                'itens': ['as quatro seções do relatório técnico saem vazias'],
                'conserto': 'escreva nas quatro seções: ' + ' · '.join(SECOES)}
    faltam = [s for s in SECOES if not any(a.get('secao') == s for a in af)]
    if not faltam:
        return None
    return {
        'chave': 'secoes-vazias',
        'titulo': f'{len(faltam)} das quatro seções sem afirmação nenhuma',
        'itens': [f'`{s}`' for s in faltam],
        'conserto': ('cada seção tem consumidor no documento, e a vazia aparece '
                     'lá dizendo que ninguém a interpretou'),
    }


def _partes_vazias(ctx: dict) -> dict | None:
    """Parte das quatro que a narrativa não escreveu."""
    nar = ctx['narrativa']
    if not nar:
        return {'chave': 'partes-vazias',
                'titulo': 'a interpretação não tem narrativa',
                'itens': ['o `readme.md` e o `readme.html` saem sem as quatro partes'],
                'conserto': 'escreva as quatro partes: ' + ' · '.join(PARTES)}
    faltam = [p for p in PARTES if not any(b.get('parte') == p for b in nar)]
    if not faltam:
        return None
    return {
        'chave': 'partes-vazias',
        'titulo': f'{len(faltam)} das quatro partes da narrativa sem bloco nenhum',
        'itens': [f'`{p}` — "{TITULO_DA_PARTE[p]}" sai vazia' for p in faltam],
        'conserto': 'escreva ao menos um bloco de cada parte',
    }


def _percurso_plano(ctx: dict) -> dict | None:
    """Percurso que não sai de uma camada só.

    O `build.py` já exige `onde` em cada passo e recusa camada inventada. O que
    ele não vê é o percurso inteiro dentro de `servidor`: três arquivos da mesma
    pasta em sequência não são um caminho pelo sistema, e o bloco existe para
    mostrar a travessia.
    """
    passos = trail.em_passos(ctx['narrativa'])
    if len(passos) < 2:
        return None
    # passo sem camada é recusa dura do `build.py`, e ela já aparece no relatório.
    # Falar aqui também produzia «4 passos, todos em `?`» embaixo da recusa — duas
    # vozes sobre o mesmo defeito mandam consertar duas vezes, e a segunda com um
    # diagnóstico inventado.
    if any(not p['onde'] for p in passos):
        return None
    camadas = trail.camadas_usadas(passos)
    if len(camadas) >= 2:
        return None
    return {
        'chave': 'percurso-plano',
        'titulo': 'o percurso não atravessa camada',
        'itens': [f'{len(passos)} passos, todos em `{camadas[0]}`'],
        'conserto': ('siga até onde o dado para: o `onde` de cada passo é o que '
                     'faz a travessia aparecer no documento'),
    }


def _perigo(ctx: dict) -> dict | None:
    """Arquivo que o inventário destacou como perigoso e a interpretação não
    endereça.

    O documento estampa a tabela com nome, dependentes e mudanças. Sem uma frase
    sobre ele, quem lê fica com o número e sem o que fazer com ele.
    """
    itens = (ctx['inv'].get('julgamento') or {}).get('perigo') or []
    if not itens:
        if not ctx['tem_grafo'] or not ctx['tem_git']:
            ctx['nao_conferido'].append(
                {'chave': 'perigo',
                 'motivo': 'o perigo: sem grafo de import ou sem histórico git, o '
                           'inventário não destacou arquivo nenhum'})
        return None
    faltam = [x for x in itens
              if not _enderecado(x['caminho'], ctx['arquivos'], ctx['pastas'],
                                 ctx['universo'], ctx['teto_da_pasta'])]
    ctx['ja_cobrado'].update(x['caminho'] for x in faltam)
    if not faltam:
        return None
    return {
        'chave': 'perigo',
        'titulo': f'{len(faltam)} de {len(itens)} arquivos do mapa de perigo sem '
                  f'uma frase na interpretação',
        'itens': _cortar([f'`{x["caminho"]}` — {x["dependentes"]} dependentes, '
                          f'{x["mudancas"]} mudanças' for x in faltam]),
        'conserto': ('diga o que é cada um e o que quebra quando ele muda — ou '
                     'declare a lacuna com o motivo. O documento já publica o '
                     'número; a interpretação é o que diz o que fazer com ele'),
    }


def _centro(ctx: dict) -> dict | None:
    """O arquivo mais importado do recorte, sem uma frase na interpretação.

    O `SKILL.md` manda ler "os poucos arquivos que o inventário aponta como
    centrais". Num projeto real medido, o mais importado de todos — 46
    dependentes — não aparecia em citação nenhuma, nem por pasta.
    """
    if not ctx['tem_grafo']:
        ctx['nao_conferido'].append(
            {'chave': 'centro',
             'motivo': 'o centro do grafo: nenhuma linguagem tem grafo de import '
                       'confiável neste recorte'})
        return None
    grau = {}
    for aresta in ctx['inv']['imports'].get('arestas') or []:
        if judge.eh_teste(aresta['para']):
            continue
        grau.setdefault(aresta['para'], set()).add(aresta['de'])
    topo = sorted(grau.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    topo = topo[:ctx['teto_do_centro']]
    # quem o mapa de perigo já cobrou não é cobrado outra vez: o arquivo mais
    # importado costuma SER o mais perigoso, e duas linhas sobre o mesmo arquivo,
    # cada uma com um número diferente, leem como dois problemas.
    # Depende da ordem de `CONFERENCIAS` — o perigo vem antes.
    faltam = [(c, len(quem)) for c, quem in topo
              if c not in ctx['ja_cobrado']
              and not _enderecado(c, ctx['arquivos'], ctx['pastas'],
                                  ctx['universo'], ctx['teto_da_pasta'])]
    if not faltam:
        return None
    return {
        'chave': 'centro',
        'titulo': f'{len(faltam)} dos {len(topo)} arquivos mais importados sem uma '
                  f'frase na interpretação',
        'itens': _cortar([f'`{c}` — {n} dependentes' for c, n in faltam]),
        'conserto': ('é por onde passa o maior número de mudanças; cite o arquivo '
                     'ou a pasta que o endereça'),
    }


CONFERENCIAS = (_saida_da_skill, _linha_sem_conteudo, _secoes_vazias,
                _partes_vazias, _percurso_plano, _perigo, _centro)


def conferir(inv: dict, dados: dict, projeto: Path | None = None,
             teto_da_pasta: int = TETO_DA_PASTA,
             teto_do_centro: int = TETO_DO_CENTRO) -> dict:
    """Tudo o que esta interpretação tem de fraco, numa lista.

    `nao_conferido` NÃO é achado: é o que esta rodada não pôde medir, com o
    motivo. Misturar os dois faria "não apurado" contar como "está certo" —
    exatamente o que a skill inteira existe para não fazer.
    """
    af = dados.get('afirmacao') or []
    nar = dados.get('narrativa') or []
    arquivos, pastas = _citacoes(af + nar)
    ctx = {
        'inv': inv, 'afirmacoes': af, 'narrativa': nar, 'itens': af + nar,
        'arquivos': arquivos, 'pastas': pastas, 'universo': _universo(inv),
        'projeto': projeto, 'nao_conferido': [], 'ja_cobrado': set(),
        'tem_grafo': bool(judge.linguagens_confiaveis(inv)
                          and (inv.get('imports') or {}).get('arestas')),
        'tem_git': bool(inv.get('mudanca_por_arquivo')),
        'teto_da_pasta': teto_da_pasta, 'teto_do_centro': teto_do_centro,
    }
    achados = [a for a in (c(ctx) for c in CONFERENCIAS) if a]
    return {
        'achados': achados,
        'nao_conferido': ctx['nao_conferido'],
        'contagem': {'afirmacoes': len(af), 'blocos': len(nar),
                     'citacoes': sum(len(x.get('evidencia') or [])
                                     for x in af + nar)},
    }
