#!/usr/bin/env python3
"""Transforma o inventário e a interpretação num documento que se lê e se manda.

Markdown versiona bem e lê mal de ponta a ponta: não dá hierarquia visual, não
dá quebra de página, e não carrega a etiqueta de confiança de um jeito que o olho
registre. Esta skill existe para quem acabou de receber um projeto — a conversa
seguinte é com alguém, e Markdown não se imprime nem se manda.

**O HTML não é conversão do `guide.md`.** É um emissor irmão, sobre a mesma fonte:
converter perderia exatamente o que faz o documento ser lido em vez de folheado.

Self-contained de propósito: as três fontes vão em base64 e não há uma única
requisição de rede, então o PDF é gerado offline. A mecânica de impressão
(`@page`, `print-color-adjust`, `break-inside`) vem da `sw-infra-audit`, que já
resolveu o mesmo problema.

Sem Chromium na máquina, entrega o HTML e avisa: não é falha da skill.
"""
import argparse
import base64
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import montar
from lib import pagina  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
ESTILOS = ('escuro', 'brutalista')
CHROMIUM = ('google-chrome', 'google-chrome-stable', 'chromium',
            'chromium-browser', 'chrome')

FONTES = [
    ('Figtree', 'figtree-latin.woff2', '400 700'),
    ('Bricolage Grotesque', 'bricolage-grotesque-latin.woff2', '600 800'),
    ('JetBrains Mono', 'jetbrains-mono-latin.woff2', '400 600'),
]


def achar_chromium():
    for nome in CHROMIUM:
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    return None


def _fontes_embutidas() -> str:
    """As três fontes em base64. É o que faz o PDF sair sem rede."""
    regras = []
    for familia, arquivo, pesos in FONTES:
        caminho = ASSETS / arquivo
        if not caminho.exists():
            continue
        b64 = base64.b64encode(caminho.read_bytes()).decode('ascii')
        regras.append(
            f"@font-face{{font-family:'{familia}';font-style:normal;"
            f"font-weight:{pesos};font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
    return '\n'.join(regras)


TETO_MANCHETE = 120     # acima disto não é manchete, é parágrafo


def _titulo_factual(codigo: int, nomes: list) -> str:
    return (f'Um projeto de {codigo} arquivos em '
            + (', '.join(nomes) if nomes else 'stack não reconhecida') + '.')


def _manchete(texto: str) -> str:
    """A primeira frase da narrativa, se couber numa manchete.

    Cortar só em `. ` não bastou: uma abertura real separava as orações com `:` e
    vírgula, e o `<h1>` saiu com 207 caracteres. Então o corte desce para a primeira
    oração — `:`, `;` ou travessão — e, se nem ela couber, devolve vazio e quem chama
    cai no título factual. Truncar no meio da ideia seria pior que não ter manchete.
    """
    frase = texto.split('. ')[0].strip().rstrip('.')
    if len(frase) <= TETO_MANCHETE:
        return frase + '.'
    for marca in (':', ';', ' — '):
        if marca in frase:
            oracao = frase.split(marca)[0].strip()
            if len(oracao) <= TETO_MANCHETE:
                return oracao + '.'
    return ''


def titulo_do_documento(inv: dict, narrativa: list | None = None) -> str:
    """A manchete, que é também o `<title>` da aba.

    Sai da narrativa quando o agente escreveu uma: "um projeto de 630 arquivos em
    node" é verdadeiro e não diz nada. A primeira frase do bloco `o-que-e` é o que
    alguém escreveu sobre o que o sistema É.
    """
    arvore = inv.get('arvore') or []
    codigo = sum(1 for a in arvore if pagina.eh_codigo(a['linguagem']))
    nomes = sorted({s['stack'] for s in (inv.get('stacks') or [])})
    abertura = next((b for b in (narrativa or [])
                     if b.get('parte') == 'o-que-e'), None)
    if abertura:
        return _manchete(abertura['texto']) or _titulo_factual(codigo, nomes)
    return _titulo_factual(codigo, nomes)


def _abertura(inv: dict, narrativa: list | None = None) -> str:
    e = pagina.e
    arvore = inv.get('arvore') or []
    codigo = sum(1 for a in arvore if pagina.eh_codigo(a['linguagem']))
    ativos = len(arvore) - codigo
    retrato = inv.get('retrato') or {}
    escopo = inv.get('escopo') or {}
    stacks = inv.get('stacks') or []
    titulo = titulo_do_documento(inv, narrativa)

    numeros = [(codigo, 'arquivos de código')]
    if retrato.get('commits'):
        numeros.append((retrato['commits'], 'commits'))
    if stacks:
        numeros.append((len(stacks), 'stack' if len(stacks) == 1 else 'stacks'))
    if inv.get('ambiente'):
        numeros.append((sum(len(v) for v in inv['ambiente'].values()),
                        'variáveis de ambiente'))
    blocos_num = ''.join(f'<div><b>{e(n)}</b><span>{e(r)}</span></div>'
                         for n, r in numeros)

    recorte = ''
    if escopo.get('area'):
        plural = '' if escopo['n_arquivos'] == 1 else 's'
        recorte = (f'<p class="recorte"><b>Recorte:</b> este documento cobre a área '
                   f'<code>{e(escopo["area"])}</code> ({escopo["n_arquivos"]} '
                   f'arquivo{plural}), não o projeto inteiro.</p>')

    # mapa de leitura POR INTENÇÃO, não sumário: é o que orienta quem abre o
    # documento sem saber o que está procurando
    mapa = [
        ('Nunca viu este sistema?',
         'A abertura e <i>o que o sistema faz</i>: são as partes vindas de quem construiu.'),
        ('Vai decidir se pega o projeto?',
         'O <i>retrato</i>. Quatro números respondem se vale, e com que risco.'),
        ('Vai subir na sua máquina?',
         '<i>Variáveis de ambiente</i> e o que o projeto diz de si, nesta ordem.'),
        ('Vai conversar com quem conhece?',
         'As perguntas do fim. São a pauta.'),
    ]
    itens = ''.join(f'<li><b>{p}</b> {r}</li>' for p, r in mapa)

    legenda = ' · '.join(
        f'{pagina._tag(n)} {t}' for n, t in [
            ('fato', 'apurado pelo script'),
            ('declarado', 'escrito por quem construiu'),
            ('deducao', 'inferido, com a evidência ao lado'),
            ('lacuna', 'não consegui ver, e digo por quê')])

    ativos_txt = (f' e {ativos} de imagem, texto ou configuração' if ativos else '')
    return f'''<header class="abertura">
<p class="selo">Guia do projeto · gerado por leitura do código</p>
<h1>{e(titulo)}</h1>
<p class="lead">{codigo} arquivos de código{ativos_txt}, fora <code>vendor/</code>,
<code>node_modules/</code>, cache e gerados. Tudo que está escrito aqui carrega de onde veio.</p>
{recorte}
<div class="numeros">{blocos_num}</div>
<nav class="mapa"><p class="mapa-titulo">Por onde começar</p><ul>{itens}</ul></nav>
<p class="confianca">Cada bloco diz de onde veio: {legenda}.</p>
<p class="fonte">Nada aqui foi inventado: o que o código não respondeu está no fim, como pergunta.</p>
</header>'''


def construir(inv: dict, afirmacoes: list, narrativa: list, estilo: str) -> str:
    titulo = titulo_do_documento(inv, narrativa)
    corpo = ''.join(filter(None, [
        pagina.bloco_o_que_e(narrativa),
        pagina.bloco_retrato(inv),
        pagina.bloco_afirmacoes(afirmacoes, 'o-que-faz', 'O que o sistema faz',
                                'O que mais o código disse sobre o produto.'),
        pagina.bloco_percurso(narrativa),
        pagina.bloco_mapa(narrativa),
        pagina.bloco_orientacoes(narrativa),
        pagina.bloco_onde_mora(inv),
        pagina.bloco_superficie(inv),
        pagina.bloco_muda_junto(inv),
        pagina.bloco_resolucao(inv),
        pagina.bloco_ambiente(inv),
        pagina.bloco_afirmacoes(afirmacoes, 'como-entrar', 'Como entrar',
                                'O que você precisa saber antes do primeiro comando.',
                                classe='n2'),
        pagina.bloco_do_que_e_feito(inv),
        pagina.bloco_arquivos_maiores(inv),
        pagina.bloco_lacunas(afirmacoes),
    ]))
    css = (ASSETS / 'estilo.css').read_text('utf-8')
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{pagina.e(titulo)}</title>
<style>
{_fontes_embutidas()}
{css}
</style></head>
<body class="{estilo}"><article class="doc">
{_abertura(inv, narrativa)}
<div class="grade">{corpo}</div>
</article></body></html>
'''


def _ler_interpretacao(base: Path) -> tuple:
    """As afirmações e a narrativa. As guardas são do `montar.py`: aqui a leitura
    é tolerante de propósito, porque o HTML é gerado DEPOIS dele — se o TOML fosse
    inválido, o `montar.py` já teria parado e não haveria o que imprimir."""
    arquivo = base / 'interpretation.toml'
    if not arquivo.exists():
        return [], []
    try:
        dados = tomllib.loads(arquivo.read_text('utf-8'))
    except tomllib.TOMLDecodeError as erro:
        print(f'interpretation.toml não é TOML válido: {erro}', file=sys.stderr)
        return [], []
    narrativa = dados.get('narrativa', [])
    # a MESMA normalização do `montar.py`: dois leitores do mesmo arquivo divergiram
    # uma vez, e a limpeza do rótulo do salto chegou só ao markdown
    for b in narrativa:
        if b.get('saltos'):
            b['saltos'] = [montar.limpar_salto(s) for s in b['saltos']]
    return dados.get('afirmacao', []), narrativa


def main() -> int:
    p = argparse.ArgumentParser(description='Gera o documento humano em HTML e PDF.')
    p.add_argument('--dir', required=True, help='o diretório com o inventory.json')
    p.add_argument('--estilo', default='escuro',
                   help=f'a vestimenta do documento: {" ou ".join(ESTILOS)}')
    p.add_argument('--pdf', action='store_true', help='gerar o PDF também')
    args = p.parse_args()

    if args.estilo not in ESTILOS:
        print(f'estilo desconhecido: {args.estilo} — use {" ou ".join(ESTILOS)}',
              file=sys.stderr)
        return 2

    base = Path(args.dir).resolve()
    inventario = base / 'inventory.json'
    if not inventario.exists():
        print(f'não achei {inventario} — rode varrer.py antes', file=sys.stderr)
        return 2

    inv = json.loads(inventario.read_text('utf-8'))
    afirmacoes, narrativa = _ler_interpretacao(base)
    destino = base / 'leia-me.html'
    destino.write_text(construir(inv, afirmacoes, narrativa, args.estilo),
                       encoding='utf-8')
    print(destino)

    if not args.pdf:
        return 0

    navegador = achar_chromium()
    if not navegador:
        print('sem Chromium na máquina: o PDF não foi gerado, o HTML está pronto '
              'e abre em qualquer navegador')
        return 0

    pdf = base / 'leia-me.pdf'
    try:
        subprocess.run([navegador, '--headless', '--disable-gpu', '--no-sandbox',
                        f'--print-to-pdf={pdf}', '--no-pdf-header-footer',
                        destino.as_uri()], capture_output=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError) as erro:
        print(f'o Chromium não terminou ({erro}): o HTML está pronto', file=sys.stderr)
        return 0
    if pdf.exists():
        print(pdf)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
