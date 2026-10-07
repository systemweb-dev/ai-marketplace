#!/usr/bin/env python3
"""Junta inventário e interpretação no `guide.md`.

Duas propriedades inegociáveis:

1. NUNCA afirma ausência de dependentes. O grafo de import não vê injeção de
   dependência, reflexão, rota como string, facade, template nem config — em
   projeto legado isso é a maior parte do acoplamento. Então a saída é sempre
   "N por import, M menções textuais", com a lista do que o grafo não enxerga
   anexada à própria afirmação.
2. É função pura dos arquivos de entrada. Mesmos fatos, mesmo documento, byte a
   byte — sem carimbo de tempo, com ordem estável. É o que faz o diff servir.
"""
import argparse
import json
import sys
import tomllib
from pathlib import Path

NIVEIS = {'fato', 'declarado', 'deducao', 'lacuna'}
TETO_SIMBOLOS = 40
DOCUMENTACAO = ('.md', '.txt', '.rst', '.adoc')
SECOES = {'como-entrar', 'depende-de', 'o-que-faz', 'superficie'}

CEGUEIRAS = [
    'injeção de dependência / container',
    'rota como string ("Controller@acao")',
    'reflexão e chamada dinâmica',
    'include de template',
    'acoplamento por SQL ou config',
]


def _ler_interpretacao(caminho: Path) -> list:
    if not caminho.exists():
        return []
    dados = tomllib.loads(caminho.read_text('utf-8'))
    afirmacoes = dados.get('afirmacao', [])
    for a in afirmacoes:
        if a.get('secao') not in SECOES:
            raise ValueError(f'secao inválida ou ausente: {a.get("secao")!r}')
        if a.get('nivel') not in NIVEIS:
            raise ValueError(f'nivel inválido: {a.get("nivel")!r}')
        if a['nivel'] == 'lacuna' and not a.get('motivo'):
            raise ValueError(f'lacuna sem motivo: {a.get("texto")!r}')
        if a['nivel'] != 'lacuna' and not a.get('evidencia'):
            raise ValueError(
                f'afirmacao sem evidencia e sem ser lacuna: {a.get("texto")!r}')
    return afirmacoes


def _como_foi_detectada(componente: dict) -> str:
    """Stack sem manifesto é detectada por contagem de extensão.

    Imprimir `manifesto` cru colocaria a palavra `None` no documento — dizer COMO
    foi detectada é o que o leitor precisa para saber o quanto confiar.
    """
    manifesto = componente.get('manifesto')
    if manifesto:
        return f'`{manifesto}`'
    return f'sem manifesto; detectada por {componente.get("por", "contagem de arquivos")}'


def _dependentes(inv: dict) -> list:
    """Uma linha por arquivo: import + menção textual, nunca ausência."""
    entrada = {}
    for aresta in inv['imports']['arestas']:
        entrada.setdefault(aresta['para'], []).append(aresta['de'])

    # Sem NENHUMA aresta de import, o que resta é só o grafo textual — e ele casa
    # PALAVRA, não símbolo de código. Num projeto em português isso devolve `banco`,
    # `caminho` e `conta` com centenas de "menções", contadas inclusive dentro de
    # arquivo de documentação. A seção vira 142 linhas de ruído com `import não
    # medido` em cada uma, e o leitor não tem como separar sinal de palavra comum.
    #
    # Lacuna curta com motivo é mais honesta que lista longa que ninguém consegue ler.
    if not inv['imports']['arestas'] and inv['imports']['indisponivel']:
        stacks = ', '.join(sorted(i['stack'] for i in inv['imports']['indisponivel']))
        return [
            f'O acoplamento por import não foi medido nesta versão para: **{stacks}**.',
            '',
            'Resta o grafo textual, que casa o nome como palavra — e isso traz ruído',
            'demais para virar afirmação: numa base em português, `banco` e `caminho`',
            'aparecem às centenas sem que haja relação de código. A lista completa está',
            'em `inventory.json`, na seção `mencoes`, para quem quiser olhar à mão.',
            '',
            '*Quem depende de quem, nesta stack, continua por apurar.*  [lacuna]',
        ]

    # Símbolo citado SÓ em documentação não é acoplamento de código: o nome de um
    # arquivo de spec aparecia como dependente, inflando a lista com ruído.
    so_em_doc = 0
    linhas = []
    for simbolo, achadas in inv['mencoes'].items():
        arquivos = sorted({m['caminho'] for m in achadas})
        if all(a.lower().endswith(DOCUMENTACAO) for a in arquivos):
            so_em_doc += 1
            continue
        por_import = sorted({d for alvo, ds in entrada.items()
                             if Path(alvo).stem == simbolo for d in ds})
        # chegou aqui porque HÁ grafo de import; sem ele a seção vira lacuna acima
        plural = 'menção textual' if len(arquivos) == 1 else 'menções textuais'
        linhas.append((len(arquivos), simbolo,
                       f'- **{simbolo}** — {len(por_import)} por import, '
                       f'{len(arquivos)} {plural}: '
                       f'{", ".join(arquivos[:6])}'
                       + (' …' if len(arquivos) > 6 else '')))

    # Ordenado pelo MAIS citado e cortado: sem isto a seção era 85% do documento
    # (264 de 310 linhas), sem ranking, e ninguém lia.
    linhas.sort(key=lambda t: (-t[0], t[1]))
    saida = [texto for _, _, texto in linhas[:TETO_SIMBOLOS]]
    sobra = len(linhas) - len(saida)
    if sobra:
        saida.append(f'\n*Mais {sobra} símbolos com menos menções, no `inventory.json`.*')
    if so_em_doc:
        saida.append(f'*{so_em_doc} símbolos citados só em documentação ficaram de fora.*')
    return saida


def _escrever(L: list, afirmacoes: list, secao: str) -> None:
    """Despeja as afirmações daquela seção. Seção vazia diz que está vazia.

    Toda seção publicada no contrato precisa ter consumidor aqui: a primeira versão
    só lia `o-que-faz`, e o que o agente escrevia para `como-entrar` e `superficie`
    sumia sem erro — trabalho feito, conteúdo evaporado.
    """
    do_agente = [a for a in afirmacoes if a.get('secao') == secao]
    if not do_agente:
        L.append('*A interpretação não escreveu nada aqui.*  [lacuna: seção não interpretada]\n')
        return
    for a in sorted(do_agente, key=lambda x: x['texto']):
        L.append(f'- {a["texto"]}  [{a["nivel"]}]')
        for e in a.get('evidencia', []):
            L.append(f'    ↳ `{e}`')
    L.append('')


def montar(inv: dict, afirmacoes: list) -> str:
    L = []
    A = L.append
    A('# Guia do projeto\n')
    A('> Documento gerado por leitura do código. Cada afirmação carrega o nível de')
    A('> confiança: **fato** (medido) · **declarado** (humano escreveu antes) ·')
    A('> **dedução** (inferida, com evidência) · **lacuna** (não apurado, com motivo).\n')

    A('## Como entrar\n')
    for c in inv['stacks']:
        A(f'- **{c["stack"]}** em `{c["caminho"]}` — {_como_foi_detectada(c)}  [fato]')
    if not inv['stacks']:
        A('- nenhum manifesto reconhecido na raiz  [lacuna: o projeto não declara stack '
          'por manifesto conhecido]')
    A('')
    # "2.036 arquivos" se lê como 2.036 arquivos de CÓDIGO; num projeto real metade
    # eram PNG e SVG. A afirmação estava correta e comunicava errado.
    ATIVOS = {'png', 'svg', 'jpg', 'jpeg', 'gif', 'ico', 'webp', 'woff', 'woff2',
              'ttf', 'eot', 'mp4', 'pdf', 'zip', 'config'}
    ativos = sum(1 for a in inv['arvore'] if a['linguagem'] in ATIVOS)
    codigo = len(inv['arvore']) - ativos
    A(f'{codigo} arquivos de código e {ativos} de imagem, fonte ou configuração '
      f'(fora `vendor/`, `node_modules/`, cache e gerados).  [fato]\n')
    for arquivo, chaves in inv['ambiente'].items():
        A(f'`{arquivo}` declara {len(chaves)} variáveis — **só os nomes**, '
          f'nunca os valores:  [fato]')
        A('`' + '` · `'.join(chaves) + '`\n')
    _escrever(L, afirmacoes, 'como-entrar')

    A('## O que depende do quê\n')
    # O preâmbulo das cegueiras serve para qualificar uma LISTA. Quando não há lista
    # — a seção inteira virou lacuna —, imprimir as cinco cegueiras, mais a
    # indisponibilidade, mais a lacuna é dizer a mesma coisa três vezes.
    if not (not inv['imports']['arestas'] and inv['imports']['indisponivel']):
        # A frase-guarda NÃO pode conter nenhuma das frases proibidas — a primeira
        # versão dizia «não existe "nada depende disso" aqui» e reprovava o próprio teste.
        A('Duas leituras cruzadas. **Ausência de dependentes nunca é afirmada neste**')
        A('**documento**: o grafo de import não enxerga o seguinte —\n')
        for cegueira in CEGUEIRAS:
            A(f'- {cegueira}')
        A('')
        for item in inv['imports']['indisponivel']:
            A(f'> Grafo de import indisponível para **{item["stack"]}**: '
              f'{item["motivo"]}  [lacuna]')
            A('')
    L.extend(_dependentes(inv))
    A('')
    _escrever(L, afirmacoes, 'depende-de')

    A('### O que muda junto\n')
    h = inv['historia']
    # Decide pelo DADO, não pela lacuna. Depois que a busca por sub-repositórios
    # entrou, `lacuna` passou a significar duas coisas — "não há dado" e "há dado,
    # com ressalva" — e o documento escondia 40 pares de co-mudança que tinha.
    if not h['co_mudanca']:
        A(f'Não apurado: {h["lacuna"]}.  [lacuna]\n')
        A('Sem histórico, a concentração de risco é substituída por sinais estáticos —')
        A('número de menções, tamanho do arquivo e quantas stacks o tocam.\n')
    else:
        if h['lacuna']:
            A(f'> Ressalva: {h["lacuna"]}.  [lacuna parcial]\n')
        A(f'De {h["commits"]} commits '
          f'({h["commits_descartados"]} descartados por tocarem arquivos demais).  [fato]\n')
        for c in h['co_mudanca'][:20]:
            A(f'- `{c["arquivos"][0]}` + `{c["arquivos"][1]}` — {c["vezes"]}x')
        A('')

    A('## Superfície pública\n')
    sup = inv['superficie']
    if not sup:
        A('Nenhuma pasta de convenção conhecida (`routes/`, `migrations/`, `Jobs/`…).')
        A('  [lacuna: o projeto não segue convenção de caminho reconhecida]\n')
    else:
        A('Reconhecida por **convenção de caminho** — é indício, não prova.  [dedução]\n')
        for tipo in ('rota', 'comando', 'job', 'migration'):
            itens = [i for i in sup if i['tipo'] == tipo]
            if not itens:
                continue
            A(f'**{tipo}** ({len(itens)}), por `{itens[0]["por"]}`:')
            for i in itens[:10]:
                A(f'- `{i["caminho"]}`')
            if len(itens) > 10:
                A(f'- … e mais {len(itens) - 10}')
            A('')
    _escrever(L, afirmacoes, 'superficie')

    A('## O que o sistema faz\n')
    _escrever(L, afirmacoes, 'o-que-faz')

    A('## Perguntas em aberto\n')
    A('O que o código não respondeu — pauta para levar a quem conhece o sistema.\n')
    for a in sorted((x for x in afirmacoes if x['nivel'] == 'lacuna'),
                    key=lambda x: x['texto']):
        A(f'- {a["texto"]} — *{a["motivo"]}*')
    # Pergunta fixa só faz sentido enquanto ninguém respondeu. Repetir "qual é o
    # propósito?" logo abaixo de três afirmações `declarado` com fonte citada faz o
    # documento se contradizer na mesma página.
    respondido = {a['secao'] for a in afirmacoes if a['nivel'] in ('fato', 'declarado')}
    if not h['co_mudanca']:
        A('- Existe histórico de versionamento deste projeto em outro lugar?')
    if 'o-que-faz' not in respondido:
        A('- Qual é o propósito de negócio do sistema, e quem o usa?')
    if 'como-entrar' not in respondido:
        A('- Como se sobe este projeto do zero?')
    A('- Alguma destas pastas já não é usada e pode ser apagada?')
    A('')
    return '\n'.join(L)


def main() -> int:
    p = argparse.ArgumentParser(description='Monta o guide.md a partir do inventário.')
    p.add_argument('--dir', required=True, help='diretório com inventory.json')
    args = p.parse_args()

    base = Path(args.dir).resolve()
    inventario = base / 'inventory.json'
    if not inventario.exists():
        print(f'não achei {inventario} — rode varrer.py antes', file=sys.stderr)
        return 2

    try:
        afirmacoes = _ler_interpretacao(base / 'interpretation.toml')
    except ValueError as erro:
        print(f'interpretation.toml inválido: {erro}', file=sys.stderr)
        return 2

    texto = montar(json.loads(inventario.read_text('utf-8')), afirmacoes)
    (base / 'guide.md').write_text(texto, encoding='utf-8')
    print(f'{base / "guide.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
