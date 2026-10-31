#!/usr/bin/env python3
"""Comentários do projeto: quais existem, o que cada um informa, e quais não informam nada.

Esta é a única parte da varredura em que errar **apaga conhecimento**. Código removido por
engano volta do git, dos testes e do próprio comportamento do sistema; o comentário que
registrava POR QUE a linha é daquele jeito — o bug contornado, o trade-off escolhido, o
número da issue — é a única cópia dessa informação que existe. Por isso o módulo é
assimétrico de propósito: o catálogo de *protegido* é maior que o de *candidato*, e tudo
que não foi PROVADO desnecessário sai como `prosa`, para um humano decidir.

Três armadilhas motivaram o analisador léxico em vez de `grep`, e cada uma foi medida:

  `grep '^\\s*//'` casa `//` dentro de `url(http://cdn/x.png)` e dentro de qualquer string
  que contenha uma URL; `grep '#'` casa o `#` de `${#lista}` e o de `"cor: #fff"`. Nos dois
  casos a "remoção do comentário" corta código vivo no meio.

  Diretiva não é comentário, é código escrito em forma de comentário. `# type: ignore`,
  `// eslint-disable-next-line`, `//go:build linux` e um docblock com `@ORM\\Column` são
  LIDOS por ferramenta ou framework: removê-los muda comportamento ou quebra o build. O
  docblock do Doctrine é o caso extremo — ele é o schema do banco.

  Comentário dentro de `\"\"\"...\"\"\"` ou de template literal não é comentário nenhum.

Nada aqui escreve no projeto sem `--aplicar`. E `--aplicar` recusa cortar quando o texto do
arquivo não é mais, byte a byte, o que foi apurado: offset velho é como se corrompe arquivo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

IGNORAR = {
    'vendor', 'node_modules', 'bower_components', '.git', '__pycache__', '.venv',
    'venv', 'dist', 'build', 'out', 'target', 'coverage', '.next', '.nuxt',
    '.svelte-kit', '.turbo', '.cache', '.terraform', '.tox', '.ruff_cache',
    '.pytest_cache', '.mypy_cache', '.idea', '.vscode', '.gradle', '.dart_tool',
    'migrations', 'storage',
}

# Arquivo gerado tem comentário de gerador, não de pessoa: ele inflaria a contagem com
# centenas de candidatos que ninguém escreveu e ninguém deve editar.
GERADOS = ('.min.js', '.min.css', '.map', '.lock', '-lock.json', '.pyc', '.d.ts',
           '.pb.go', '_pb2.py', '.generated.ts', '.snap', '.tsbuildinfo')

TETO_BYTES = 600_000

# ---------------------------------------------------------------- famílias de sintaxe
# A família diz onde um comentário COMEÇA e TERMINA. É o que separa um comentário de um
# `//` dentro de string.
SINTAXE = {
    'c':     {'linha': ('//',), 'bloco': (('/*', '*/'),), 'strings': ('"', "'", '`'),
              'escapa': True},
    'php':   {'linha': ('//', '#'), 'bloco': (('/*', '*/'),), 'strings': ('"', "'"),
              'escapa': True, 'tags': True},
    # CSS não tem `//`, e tentar lê-lo quebra `url(http://…)`, que não é citado.
    'css':   {'linha': (), 'bloco': (('/*', '*/'),), 'strings': ('"', "'"),
              'escapa': True},
    'hash':  {'linha': ('#',), 'bloco': (), 'strings': ('"', "'"), 'escapa': True},
    'py':    {'linha': ('#',), 'bloco': (), 'strings': ('"', "'"), 'escapa': True,
              'triplas': True},
    'dash':  {'linha': ('--',), 'bloco': (('/*', '*/'),), 'strings': ('"', "'"),
              'escapa': True},
    'html':  {'linha': (), 'bloco': (('<!--', '-->'),), 'strings': (), 'escapa': False},
    'blade': {'linha': (), 'bloco': (('{{--', '--}}'), ('<!--', '-->')), 'strings': (),
              'escapa': False},
    'twig':  {'linha': (), 'bloco': (('{#', '#}'), ('<!--', '-->')), 'strings': (),
              'escapa': False},
}

FAMILIA = {
    '.blade.php': 'blade', '.twig': 'twig',
    '.js': 'c', '.jsx': 'c', '.mjs': 'c', '.cjs': 'c', '.ts': 'c', '.tsx': 'c',
    '.java': 'c', '.cs': 'c', '.go': 'c', '.rs': 'c', '.swift': 'c', '.kt': 'c',
    '.kts': 'c', '.scala': 'c', '.dart': 'c', '.c': 'c', '.h': 'c', '.cpp': 'c',
    '.hpp': 'c', '.cc': 'c', '.m': 'c', '.mm': 'c', '.groovy': 'c', '.gradle': 'c',
    '.sol': 'c', '.scss': 'c', '.less': 'c', '.css': 'css',
    '.php': 'php',
    '.py': 'py',
    '.rb': 'hash', '.sh': 'hash', '.bash': 'hash', '.zsh': 'hash', '.yml': 'hash',
    '.yaml': 'hash', '.toml': 'hash', '.pl': 'hash', '.tf': 'hash', '.ex': 'hash',
    '.exs': 'hash', '.conf': 'hash',
    '.sql': 'dash', '.lua': 'dash',
    '.html': 'html', '.htm': 'html', '.xml': 'html', '.vue': 'html',
    '.svelte': 'html', '.svg': 'html',
}
FAMILIA_POR_NOME = {'Dockerfile': 'hash', 'Makefile': 'hash', 'Procfile': 'hash',
                    '.env': 'hash', '.gitignore': 'hash', '.dockerignore': 'hash'}

# Markdown fica fora de propósito: o arquivo inteiro é prosa, e "comentário desnecessário"
# em documento é revisão de texto, não varredura de código morto.
FORA = {'.md', '.mdx', '.rst', '.txt', '.json', '.csv', '.svg'}


def familia_de(caminho: Path) -> str | None:
    nome = caminho.name
    if nome in FAMILIA_POR_NOME:
        return FAMILIA_POR_NOME[nome]
    baixo = nome.lower()
    # sufixo mais LONGO primeiro: `.php` vencia `.blade.php` e a família blade nunca
    # era atribuída — o mesmo defeito já medido no atribuidor de linguagem.
    for sufixo, fam in sorted(FAMILIA.items(), key=lambda kv: -len(kv[0])):
        if baixo.endswith(sufixo):
            return fam
    return None


# ---------------------------------------------------------------- o analisador léxico
def _fim_de_string(texto: str, i: int, delim: str, escapa: bool) -> int:
    j = i + 1
    n = len(texto)
    while j < n:
        c = texto[j]
        if escapa and c == '\\':
            j += 2
            continue
        if c == delim:
            return j + 1
        # String não fechada na linha (quase sempre uma aspa dentro de texto, ou o
        # apóstrofo de `don't`): parar na quebra evita arrastar o arquivo inteiro para
        # dentro de uma string e perder todos os comentários abaixo.
        if c == '\n' and delim != '`':
            return j
        j += 1
    return n


def _pode_abrir(texto: str, i: int) -> bool:
    """Marca de comentário de linha só vale no início da linha ou depois de espaço.

    É o que impede `http://` (precedido por `:`) e `${#lista}` (precedido por `{`) de
    abrirem um comentário. Perder um `a=1;//x` colado é barato: deixa de ser proposto.
    """
    return i == 0 or texto[i - 1] in ' \t\n\r;),}'


def extrair(texto: str, familia: str) -> list:
    """Os comentários do arquivo, como (inicio, fim, forma) em offsets de caractere."""
    s = SINTAXE[familia]
    achados: list = []
    i, n = 0, len(texto)
    # Um `.php` começa em HTML e só entra em PHP no `<?`. Fora da tag, `//` é texto.
    em_codigo = not s.get('tags')
    while i < n:
        c = texto[i]
        if s.get('tags'):
            if not em_codigo:
                if texto.startswith('<?', i):
                    em_codigo = True
                    i += 2
                    continue
                if texto.startswith('<!--', i):
                    fim = texto.find('-->', i + 4)
                    fim = n if fim < 0 else fim + 3
                    achados.append((i, fim, 'bloco'))
                    i = fim
                    continue
                i += 1
                continue
            if texto.startswith('?>', i):
                em_codigo = False
                i += 2
                continue
        if c in s['strings']:
            if s.get('triplas') and texto.startswith(c * 3, i):
                fim = texto.find(c * 3, i + 3)
                i = n if fim < 0 else fim + 3
                continue
            i = _fim_de_string(texto, i, c, s['escapa'])
            continue
        for abre, fecha in s['bloco']:
            # `/*` dentro de literal de regex (`/[/*]/`) ou escapado não abre bloco.
            if texto.startswith(abre, i) and not (abre == '/*' and i and texto[i - 1] in '[\\'):
                fim = texto.find(fecha, i + len(abre))
                fim = n if fim < 0 else fim + len(fecha)
                achados.append((i, fim, 'bloco'))
                i = fim
                break
        else:
            for marca in s['linha']:
                if texto.startswith(marca, i) and _pode_abrir(texto, i):
                    fim = texto.find('\n', i)
                    fim = n if fim < 0 else fim
                    if fim > i and texto[fim - 1] == '\r':
                        fim -= 1
                    achados.append((i, fim, 'linha'))
                    i = fim
                    break
            else:
                i += 1
    return achados


def agrupar(texto: str, spans: list) -> list:
    """Linhas de comentário seguidas e sozinhas na linha formam UM comentário.

    O defeito que isto conserta foi medido em projeto real: um bloco de três linhas `//`
    entrava como três comentários, e o "porque" da PRIMEIRA linha não protegia as outras
    duas — as continuações viravam candidatas a remoção, deixando no arquivo uma
    explicação decapitada. Quem escreve um bloco escreve um texto, não três rótulos.

    Só agrupa comentário de linha, sozinho na linha e em linhas consecutivas: linha em
    branco no meio separa dois comentários, e comentário no rabo do código descreve
    aquela linha, não a de cima.
    """
    juntos: list = []
    for inicio, fim, forma in spans:
        if forma != 'linha' or not juntos:
            juntos.append([inicio, fim, forma])
            continue
        anterior = juntos[-1]
        if anterior[2] != 'linha':
            juntos.append([inicio, fim, forma])
            continue
        entre = texto[anterior[1]:inicio]
        sozinho = not texto[texto.rfind('\n', 0, inicio) + 1:inicio].strip()
        abriu_sozinho = not texto[texto.rfind('\n', 0, anterior[0]) + 1:anterior[0]].strip()
        if entre.count('\n') == 1 and not entre.strip() and sozinho and abriu_sozinho:
            anterior[1] = fim
            continue
        juntos.append([inicio, fim, forma])
    return [tuple(j) for j in juntos]


def corpo_de(texto: str) -> str:
    """O conteúdo do comentário, sem as marcas e sem o `*` de enfeite de cada linha."""
    t = texto.strip()
    for abre, fecha in (('/*', '*/'), ('<!--', '-->'), ('{{--', '--}}'), ('{#', '#}')):
        if t.startswith(abre):
            t = t[len(abre):]
            if t.endswith(fecha):
                t = t[:-len(fecha)]
            linhas = [re.sub(r'^\s*\*+\s?', '', ln) for ln in t.splitlines()]
            return '\n'.join(linhas).strip()
    linhas = [re.sub(r'^\s*(//+|#+|--)\s?', '', ln) for ln in t.splitlines()]
    return '\n'.join(linhas).strip()


# ---------------------------------------------------------------- catálogo: protegido
# Diretiva é código escrito em forma de comentário: o compilador, o linter, o empacotador
# ou o framework LÊ a linha. Remover muda comportamento ou quebra o build. O catálogo é
# versionado aqui, e não deduzido na hora, porque "parece um comentário comum" é
# exatamente como `# frozen_string_literal: true` e `@ORM\Column` se disfarçam.
DIRETIVAS = (
    (r'^#!', 'shebang: é o interpretador do arquivo'),
    (r'^-\*-\s*coding|^\s*coding[:=]', 'declaração de encoding (PEP 263)'),
    (r'\btype:\s*ignore\b', 'silencia o mypy naquela linha'),
    (r'\bnoqa\b', 'silencia o flake8/ruff naquela linha'),
    (r'\bpragma:\s*no\s*cover\b', 'exclui a linha da cobertura'),
    (r'^\s*(pylint|mypy|ruff|flake8|bandit|pyright|isort)\s*:', 'configura a ferramenta'),
    (r'\bfmt:\s*(off|on)\b|\bblack\b.*\b(off|on)\b', 'liga/desliga o formatador'),
    (r'@ts-(ignore|expect-error|nocheck)', 'silencia o TypeScript'),
    (r'\beslint-(disable|enable|env)', 'configura o ESLint'),
    (r'^\s*(global|eslint|jshint|jslint|exported)\s', 'diretiva de linter JS'),
    (r'\bprettier-ignore\b', 'impede o Prettier de reformatar'),
    (r'\bistanbul\s+ignore\b|\bc8\s+ignore\b|\bv8\s+ignore\b', 'exclui da cobertura'),
    (r'\bwebpackChunkName\b|\bwebpackIgnore\b|\bvite-ignore\b',
     'nomeia/ignora o chunk no empacotador'),
    (r'__PURE__|__NO_SIDE_EFFECTS__', 'marca para o tree-shaking do empacotador'),
    (r'^\s*@(jsx|jsxImportSource|jsxRuntime)\b', 'escolhe o runtime de JSX'),
    (r'^\s*@type\b|^\s*@satisfies\b', 'é o TIPO, em JS checado pelo TypeScript'),
    (r'^go:(build|generate|embed|linkname|noinline|nosplit)\b|^\s*\+build\b',
     'diretiva do compilador Go'),
    (r'\bnolint\b|\bNOSONAR\b|\bCHECKSTYLE\b|\bNOPMD\b|\bNOLINT\b',
     'silencia o analisador estático'),
    (r'\bclang-format\s+(off|on)\b|^\s*#pragma\b', 'diretiva de compilador C/C++'),
    (r'@(ORM|ODM|Route|Entity|Table|Column|ManyToOne|OneToMany|ManyToMany|JoinColumn|'
     r'Id|GeneratedValue|Embeddable|Assert|Serializer|Groups|Security|IsGranted)\b',
     'ANOTAÇÃO que o framework executa: o docblock é o schema/a rota'),
    (r'@(dataProvider|depends|covers|test|group|expectedException|runInSeparateProcess|'
     r'backupGlobals|requires|before|after|beforeClass|afterClass|ticket)\b',
     'anotação que o runner de teste executa'),
    (r'@(psalm|phpstan|phan)-|@template\b|@mixin\b',
     'tipo lido pelo analisador estático de PHP'),
    (r'\bfrozen_string_literal\b|\bencoding\s*:\s*\w', 'diretiva mágica do Ruby'),
    (r'\brubocop:(disable|enable|todo)\b', 'silencia o RuboCop'),
    (r'\bshellcheck\s+(disable|source|shell)\b', 'configura o ShellCheck'),
    (r'\bstylelint-(disable|enable)\b', 'configura o Stylelint'),
    (r'^\s*syntax\s*=|^\s*escape\s*=|^\s*check=', 'diretiva de parser do Dockerfile'),
    (r'\byamllint\b|\btflint-ignore\b|\bterraform\b.*\bignore\b',
     'silencia o linter de configuração'),
    (r'\bsqlfluff\b|\bnoqa\b', 'silencia o linter de SQL'),
    (r'^\s*!\s*$|^\s*\[if\s|^\s*<!\[endif\]', 'comentário condicional lido pelo navegador'),
    (r'\bregion\b.*\w|\bendregion\b', 'dobra de região lida pelo editor'),
    (r'^!\d{3,}', 'execução condicional do MySQL: `/*!40101 SET … */` é SQL, '
                   'não comentário — o servidor executa a linha'),
)

LICENCAS = (
    r'SPDX-License-Identifier', r'\bcopyright\b', r'\(c\)\s*\d{4}', r'©',
    r'licensed under', r'all rights reserved', r'\bGNU\b', r'\bMIT License\b',
    r'\bApache License\b', r'@license\b', r'\bBSD\b.*\blicense\b',
)

# O "por quê" é a informação que NÃO está no código e não volta de lugar nenhum. Qualquer
# um destes sinais tira o comentário da lista de remoção, mesmo que ele também pareça
# redundante — o custo de manter uma linha a mais é zero; o de apagar o motivo é perpétuo.
PORQUES = (
    (r'\b(porque|porqu[eê]|pois|j[aá] que|uma vez que|dado que|sen[aã]o|'
     r'caso contr[aá]rio|do contr[aá]rio|por isso|motivo|raz[aã]o|'
     r'because|since|otherwise|so that|in order to|reason|that is why)\b',
     'explica um motivo'),
    (r'\b(workaround|gambiarra|contorna|contornar|bug\b|defeito|quebra|quebrava|'
     r'falha|falhava|regress[aã]o|vazamento|race\b|deadlock|timeout|'
     r'breaks?\b|broke\b|crash)\b', 'registra um defeito contornado'),
    (r'\b(n[aã]o|nunca|jamais|cuidado|aten[cç][aã]o|evite|evitar|proibido|'
     r'dont|do not|never|careful|warning|beware|avoid|must not|'
     r'importante|cr[ií]tico)\b', 'é um aviso ou uma proibição'),
    (r'#\d{2,}|\b[A-Z]{2,}-\d+\b|https?://|\bCVE-\d|\bRFC\s*\d|\bissue\b|\bticket\b|'
     r'\bPR\b\s*#?\d', 'cita issue, ticket, CVE, RFC ou link'),
    (r'\b(mais r[aá]pido|mais lento|perform|otimiza|desempenho|mem[oó]ria|'
     r'\d+\s*(ms|s|kb|mb|gb|x\b)|benchmark|medido|medi[cç][aã]o)\b',
     'traz uma medida ou um ganho medido'),
    (r'\b(ordem importa|a ordem|antes de|depois de|precisa vir|tem que vir|'
     r'order matters|must come|must be before|must be after)\b',
     'declara uma dependência de ordem que o código não mostra'),
    (r'\b\w+(?:ria|riam|r[ií]amos)\b|\bsem (?:a|o|os|as|isso|ele|ela|esse|essa)\b|'
     r'\bpara que\b|\bde modo que\b|\bbasta\b|\bdo contr[aá]rio\b',
     'explica a consequência de fazer diferente'),
    (r'\b(hist[oó]ric|legado|legacy|compatibilidade|retrocompat|migra[cç][aã]o|'
     r'deprecated|obsoleto|remover em|remove in|at[eé]\s)\b',
     'registra história ou prazo'),
)

# Dívida registrada não é lixo: muitas vezes é o único registro de um problema conhecido.
PENDENCIAS = r'\b(TODO|FIXME|HACK|XXX|BUG|OPTIMIZE|REVIEW|NOTE)\b'

# `# Assert` sobre `assert x == 1` repete a palavra da linha — e apagá-lo destrói a
# estrutura do teste. O marcador não DESCREVE a linha seguinte: ele marca a fronteira de um
# bloco, e a convenção AAA/BDD é exigida por outra skill desta casa. Numa rodada real num
# projeto de 76 arquivos eram 200 dos 317 candidatos a "redundante".
MARCADORES = (
    (r'^[=\-*~#_]{2,}\s*[^\s=\-*~#_][^\n]*?[=\-*~#_]{2,}$',
     'faixa de seção: rotula um bloco, não a linha seguinte'),
    (r'^(arrange|act|assert|given|when|then|setup|teardown|fixture|'
     r'arranjo|a[cç][aã]o|verifica[cç][aã]o|prepara[cç][aã]o|preparo)\s*[:.\-]?$',
     'marca a fronteira de um bloco (AAA/BDD), não descreve a linha'),
)

DOC_TAGS = (r'@(param|returns?|throws?|var|property|method|example|see|deprecated|'
            r'since|author|package|api|inheritDoc|inheritdoc|template|link)\b')

# ---------------------------------------------------------------- catálogo: candidato
# Lixo de ferramenta e de scaffold: texto que nenhuma pessoa escreveu e que nenhuma pessoa
# leu. O cabeçalho de IDE merece nota à parte — ele costuma carregar o nome de usuário de
# quem gerou o arquivo, que é dado pessoal viajando no repositório.
SCAFFOLDS = (
    (r'auto-?generated\s+(method\s+)?stub', 'stub gerado pela IDE'),
    (r'^\s*(TODO|FIXME|XXX|HACK)\s*:?\s*$', 'pendência sem conteúdo'),
    (r'^\s*(TODO|FIXME)\s*:?\s*(implement|implementar|auto-generated|document me|'
     r'write me|fill in|add description)\s*\.?\s*$', 'pendência de scaffold'),
    (r'created\s+by\s+.*\b(intellij|phpstorm|webstorm|pycharm|eclipse|netbeans)',
     'cabeçalho de IDE — costuma carregar o nome de usuário de quem gerou'),
    (r'^\s*created\s+(by|on)\s|^\s*user\s*:\s*\S+\s*$|^\s*date\s*:\s*[\d/-]+\s*$',
     'cabeçalho de scaffold com autor/data (o git já guarda os dois)'),
    (r'^\s*(constructor|construtor|getter|setter|destructor|destrutor)\s*\.?\s*$',
     'nomeia o que a assinatura logo abaixo já diz'),
    (r'^\s*(class|interface|trait|enum|m[eé]todo|method|fun[cç][aã]o|function)\s*$',
     'rótulo sem conteúdo'),
    (r'^\s*(code|c[oó]digo)\s+(here|aqui)\s*\.?\s*$', 'marcador de scaffold'),
    (r'^\s*(descri[cç][aã]o|description|summary|resumo|undefined|n/?a)\s*\.?\s*$',
     'campo de template não preenchido'),
)

# Palavra do comentário que já está dita por um token de sintaxe da linha. Sem esta tabela,
# `// incrementa o contador` sobre `contador++` não é reconhecido como repetição: a palavra
# "incrementa" não aparece no identificador, mas o `++` a diz por inteiro.
SINONIMOS = {
    'incrementa': ('++', '+= 1', '+=1'), 'incrementar': ('++', '+= 1'),
    'decrementa': ('--', '-= 1', '-=1'), 'decrementar': ('--', '-= 1'),
    'soma': ('+',), 'subtrai': ('-',), 'multiplica': ('*',), 'divide': ('/',),
    'retorna': ('return', 'yield'), 'retornar': ('return',), 'devolve': ('return',),
    'return': ('return',), 'returns': ('return',),
    'define': ('=',), 'atribui': ('=',), 'seta': ('=',), 'set': ('=', 'set'),
    'chama': ('(',), 'chamar': ('(',), 'invoca': ('(',), 'executa': ('(',),
    'cria': ('new', 'create', 'make'), 'criar': ('new',), 'instancia': ('new',),
    'nova': ('new',), 'novo': ('new',), 'new': ('new',),
    'importa': ('import', 'require', 'use', 'from'), 'import': ('import',),
    'itera': ('for', 'foreach', 'while', 'map', 'each'),
    'percorre': ('for', 'foreach', 'while', 'map', 'each'),
    'loop': ('for', 'while', 'foreach'), 'cada': ('each', 'foreach', 'map'),
    'verifica': ('if', 'assert', 'check'), 'checa': ('if', 'assert'),
    'testa': ('if', 'assert', 'test'), 'valida': ('valid', 'assert', 'if'),
    'deleta': ('delete', 'unset', 'remove', 'drop'),
    'remove': ('remove', 'delete', 'unset', 'splice', 'pop'),
    'apaga': ('delete', 'unset', 'remove'),
    'adiciona': ('add', 'push', 'append', 'insert'),
    'conta': ('count', 'len', 'size', 'length'), 'contador': ('count', 'counter', 'i'),
    'inicializa': ('init', 'constructor', '__init__', '__construct'),
    'construtor': ('constructor', '__init__', '__construct'),
    'constructor': ('constructor', '__init__', '__construct'),
    'destrutor': ('destructor', '__destruct', '__del__'),
    'pega': ('get', 'fetch', 'find'), 'obtem': ('get', 'fetch'),
    'busca': ('get', 'fetch', 'find', 'search', 'query'),
    'salva': ('save', 'store', 'persist', 'insert', 'update'),
    'atualiza': ('update', 'set', 'patch'),
    'converte': ('to', 'parse', 'cast', 'convert'),
    'formata': ('format', 'sprintf', 'fmt'),
    'imprime': ('print', 'echo', 'log', 'console'),
    'lan[cç]a': ('throw', 'raise'), 'lanca': ('throw', 'raise'),
    'captura': ('catch', 'except'), 'trata': ('catch', 'except', 'handle'),
    'getter': ('get',), 'setter': ('set',),
    'propriedade': ('property', 'prop'), 'atributo': ('attr', 'property'),
    'variavel': ('var', 'let', 'const'), 'constante': ('const', 'final'),
    'classe': ('class',), 'class': ('class',), 'interface': ('interface',),
    'metodo': ('function', 'def', 'func', 'fun'), 'funcao': ('function', 'def', 'func'),
    'function': ('function', 'def', 'func'),
    'publico': ('public',), 'privado': ('private',), 'protegido': ('protected',),
    'estatico': ('static',), 'abstrato': ('abstract',),
    'true': ('true',), 'false': ('false',), 'nulo': ('null', 'none', 'nil'),
}

VAZIAS = {'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'do', 'da', 'dos', 'das', 'no',
          'na', 'nos', 'nas', 'em', 'para', 'por', 'com', 'e', 'ou', 'que', 'se',
          'ao', 'aos', 'pelo', 'pela', 'este', 'esta', 'esse', 'essa', 'isto',
          'the', 'of', 'to', 'in', 'on', 'at', 'is', 'are', 'this', 'that', 'it',
          'and', 'or', 'for', 'with', 'from', 'by', 'as', 'be', 'all', 's'}

# Começo de linha que denuncia código, não prosa.
PALAVRAS_DE_CODIGO = (
    'if', 'else', 'elif', 'for', 'foreach', 'while', 'switch', 'case', 'return',
    'function', 'def', 'func', 'fun', 'class', 'interface', 'trait', 'enum',
    'import', 'from', 'require', 'include', 'use', 'const', 'let', 'var', 'public',
    'private', 'protected', 'static', 'async', 'await', 'try', 'catch', 'except',
    'finally', 'throw', 'raise', 'new', 'echo', 'print', 'console', 'dd', 'dump',
    'var_dump', 'print_r', 'self', 'this', 'super', 'end', 'elseif', 'unset',
    'delete', 'yield', 'with', 'match', 'struct', 'impl', 'package', 'namespace',
)


# ---------------------------------------------------------------- a classificação
def _casa(corpo: str, padroes) -> str | None:
    for padrao, motivo in padroes:
        if re.search(padrao, corpo, re.I | re.M):
            return motivo
    return None


def _palavras(texto: str) -> list:
    bruto = re.findall(r"[A-Za-zÀ-ÿ_][A-Za-zÀ-ÿ0-9_]*", texto)
    return [p.lower() for p in bruto if p.lower() not in VAZIAS]


SEM_STRING = re.compile(r"""(?:'[^']*'|"[^"]*"|`[^`]*`)""")


def _vocabulario_da_linha(linha: str, so_identificador: bool = False) -> set:
    """As palavras que a linha de código já diz, com camelCase e snake_case abertos.

    `so_identificador` tira o conteúdo das strings. Medido: o comentário
    `# importa nada fora de si` acima de `corpo += '<p>O núcleo não importa nada fora de
    si.</p>'` casava palavra por palavra — com a prosa que a linha IMPRIME, não com o que
    ela faz. Comparar comentário com texto de saída acha repetição onde não há.
    """
    if so_identificador:
        linha = SEM_STRING.sub(' ', linha)
    palavras = set()
    for ident in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', linha):
        palavras.add(ident.lower())
        for parte in re.findall(r'[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+', ident):
            palavras.add(parte.lower())
        palavras.update(p.lower() for p in ident.split('_') if p)
    return palavras


def eh_redundante(corpo: str, alvo: str) -> bool:
    """O comentário repete o que a linha alvo já diz, palavra por palavra.

    A exigência é total: UMA palavra do comentário que não esteja na linha (nem por
    sinônimo de operação) já basta para o comentário não ser redundante — ela pode ser
    justamente a informação que o código não tem.
    """
    palavras = _palavras(corpo)
    if not palavras or not alvo.strip():
        return False
    # Comentário de uma palavra é rótulo, não descrição: `# RabbitMQ` acima de
    # `RABBITMQ_HOST=...` nomeia o grupo de variáveis que começa ali.
    if len(palavras) < 2:
        return False
    # Comentário longo não é rótulo de linha: ele é explicação, e explicação não se
    # julga por sobreposição de palavras.
    if len(palavras) > 6:
        return False
    # `// Status de API` acima de `API_STATUS = {` rotula o OBJETO, não a linha: a
    # palavra coincide, mas o comentário é o título do bloco que começa ali.
    if re.search(r'[\{\[(:]\s*$', alvo) or re.match(
            r'^\s*(export\s+)?(def|class|function|func|fun|interface|trait|enum|'
            r'public|private|protected|static|const|let|var|async)\b', alvo):
        return False
    vocabulario = _vocabulario_da_linha(alvo, so_identificador=True)
    baixo = SEM_STRING.sub(' ', alvo).lower()
    for palavra in palavras:
        if palavra in vocabulario:
            continue
        if any(t in baixo for t in SINONIMOS.get(palavra, ())):
            continue
        return False
    return True


def _linha_e_codigo(linha: str, familia: str) -> bool:
    """Uma linha do comentário é código — não prosa que PARECE código.

    Três enganos medidos em projeto real, todos classificando prosa como código morto:

      `If done with making changes, start watching for changes in DOM again` começa com
      `if`. Palavra-chave no início não basta: exigir também pontuação de código
      (`;(){}[]=`, `->`, `=>`, `::`) separa `if (x) {` de uma frase em inglês.

      `Função helper para obter label de enum` virava código porque `[^A-Za-z_$]` cortava
      no `ç` e deixava o token `fun`, que está na lista de palavras-chave. O separador
      precisa conhecer acento.

      `Arquivos (apenas criação)` casava o formato de chamada de função. Chamada de
      verdade termina em `;` ou qualifica o nome (`console.log`, `$this->x`, `Classe::m`).
    """
    nu = linha.lstrip('$@')
    primeira = re.split(r'[^0-9A-Za-zÀ-ÿ_$]', nu, maxsplit=1)[0].lower()
    tem_pontuacao = bool(re.search(r'[;(){}\[\]=]|->|=>|::', linha))
    if primeira in PALAVRAS_DE_CODIGO and tem_pontuacao:
        return True
    if linha.endswith((';', '{', '}')) and re.search(r'[A-Za-z_)\]]', linha):
        return True
    if re.match(r'^[\w$\->:.\[\]]+\s*=[^=]', linha):
        direita = linha.split('=', 1)[1]
        # `status=OPEN nulifica delivery` tem um `=`, e é prosa: duas palavras soltas
        # lado a lado, sem operador nem pontuação entre elas, não são uma expressão.
        if re.search(r'''[()\[\]{};'"]|::|->|\.''', direita) or not re.search(
                r'[A-Za-zÀ-ÿ_]\w*\s+[A-Za-zÀ-ÿ_]', direita):
            return True
    if re.match(r'^[\w$]+(?:[.\->:]+[\w$]+)+\s*\([^)]*\)\s*;?$', linha) \
            or re.match(r'^[\w$]+\s*\([^)]*\)\s*;$', linha):
        return True
    if familia in ('html', 'blade', 'twig') and re.match(r'^<[\w/]', linha):
        return True
    if re.match(r'^[:@v#\[(][\w.-]+\s*=\s*["\']', linha):   # atributo de template Vue
        return True
    return False


def alvo_ilegivel(alvo: str) -> str | None:
    """A linha é de um tipo que PEDE legenda: regex, bits, constante em hexa.

    É o guard "explica o incompreensível". A legenda repete os literais do padrão por
    necessidade — é essa repetição que a torna útil —, e as duas regras que olham
    repetição (`redundante`) e forma de código (`codigo_comentado`) acusavam as duas
    coisas. Num ensaio de ponta a ponta as três legendas das alternativas de um regex
    foram removidas, e o padrão ficou sem dizer o que cada ramo casa.
    """
    if re.search(r're\.(?:compile|match|search|sub|findall)|regex|preg_|RegExp|'
                 r'\(\?:|\(\?<|\[\^', alvo) or alvo.count('\\') >= 2:
        return 'legenda de um padrão (regex): o código não diz o que ele casa'
    if re.search(r'0x[0-9a-fA-F]+|<<|>>|&\s*0x|\|\s*0x', alvo):
        return 'legenda de operação de bits ou constante em hexadecimal'
    return None


def eh_codigo_comentado(corpo: str, familia: str) -> bool:
    """Código desativado é o bloco em que o CÓDIGO é a maioria.

    Um bloco de documentação com exemplo de uso tem linha de código dentro, e aceitar uma
    linha bastava para propor apagar a documentação inteira — medido em quatro arquivos de
    um projeto real, incluindo o cabeçalho que ensinava a importar o módulo.
    """
    linhas = [ln.strip() for ln in corpo.splitlines() if ln.strip()]
    linhas = [ln for ln in linhas if not re.match(r'^@\w+', ln)]
    if not linhas:
        return False
    codigo = sum(1 for ln in linhas if _linha_e_codigo(ln, familia))
    return codigo * 2 > len(linhas)


def eh_divisoria(corpo: str) -> bool:
    limpo = corpo.strip()
    if not limpo:
        return True
    return bool(re.fullmatch(r'[=\-*~#/+_.<>|\s]{3,}', limpo))


def _docblock_contradiz(corpo: str, adiante: str) -> str | None:
    """`@param $b` numa função que recebe `$c`.

    O comentário que MENTE é pior que comentário nenhum: quem lê confia nele e para de
    ler o código. Por isso esta classe sai com ação `corrigir`, não `remover` — a
    assinatura é a verdade, e o docblock tem de passar a dizê-la.
    """
    declarados = re.findall(r'@param\s+(?:[\w\\|\[\]<>,\s]*?)?\$(\w+)', corpo)
    if not declarados:
        declarados = re.findall(r'@param\s+\{[^}]*\}\s+(\w+)', corpo)
        if not declarados:
            return None
    assinatura = re.search(r'\b(?:function|def|func)\s+\w+\s*\(([^)]*)\)',
                           adiante, re.S)
    if not assinatura:
        return None
    reais = set(re.findall(r'[\$\w]+', assinatura.group(1)))
    reais = {r.lstrip('$') for r in reais}
    faltam = [d for d in declarados if d not in reais]
    if faltam and len(faltam) < len(declarados) + 1:
        return 'o docblock documenta $%s, que não está na assinatura' % ', $'.join(faltam)
    return None


IDENT_TECNICO = re.compile(r'\b(?:[A-Za-z][a-z0-9]+(?:[A-Z][a-z0-9]*)+|'
                           r'[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+|'
                           r'[\w./-]+\.(?:php|py|js|ts|tsx|jsx|go|rb|java|cs|rs|vue|sql))\b')


REFERENCIA = re.compile(
    r'\b(ver|veja|vide|conforme|cf\.?|see|usa|usado em|definido em|declarado em|'
    r'movido para|veio de|vem de|como em|chamado por|substitui|renomeado|igual ao?)\b',
    re.I)


def _orfaos(corpo: str, vocabulario: set, primeira_palavra: str) -> str | None:
    """Só acusa símbolo inexistente quando o comentário está REFERENCIANDO algo.

    Sem esta porta, qualquer palavra de aparência técnica dentro de prosa virava achado —
    num projeto real ele acusou `robotsXtxt`, nome que o próprio comentário INVENTOU para
    explicar por que o ponto do regex precisa de contrabarra.
    """
    if re.search(r'→|->|\bex\.|\bexemplo|\be\.g\.|\bpor exemplo|\bcomo em\b|'
                 r'\bno formato\b|\bvira\b', corpo, re.I):
        return None
    if not REFERENCIA.search(corpo):
        return None
    for token in IDENT_TECNICO.findall(corpo):
        if token.lower() == primeira_palavra:
            continue
        alvo = token.split('/')[-1]
        if alvo.lower() in vocabulario or token.lower() in vocabulario:
            continue
        return f'cita `{token}`, que não existe em nenhum código do projeto'
    return None


def classificar(com: dict, familia: str, alvo: str, adiante: str,
                vocabulario: set) -> dict:
    """Uma classe por comentário, com o sinal que a decidiu escrito no achado.

    A ordem é a própria política: todo protegido é testado ANTES de qualquer candidato,
    para que um docblock com `@ORM\\Column` nunca caia em "divisória" por ter linhas de
    enfeite, e para que um `// não remover: quebra o checkout` nunca caia em
    "código comentado" por terminar em ponto e vírgula.
    """
    corpo = com['corpo']
    # A marca faz parte da diretiva: `corpo_de` tira o `#` e `#!/usr/bin/env python3`
    # chegava aqui como `!/usr/bin/env python3`, deixando o shebang virar candidato.
    motivo = _casa(corpo + '\n' + com.get('texto', ''), DIRETIVAS)
    if motivo:
        return {'classe': 'diretiva', 'confianca': 'protegido', 'sinal': motivo,
                'acao': 'manter'}
    if any(re.search(p, corpo, re.I) for p in LICENCAS):
        return {'classe': 'licenca', 'confianca': 'protegido',
                'sinal': 'licença ou aviso de direito autoral', 'acao': 'manter'}
    motivo = _casa(corpo, PORQUES)
    if motivo:
        return {'classe': 'porque', 'confianca': 'protegido', 'sinal': motivo,
                'acao': 'manter'}
    motivo = _casa(corpo.strip(), MARCADORES)
    if motivo:
        return {'classe': 'marcador', 'confianca': 'protegido', 'sinal': motivo,
                'acao': 'manter'}
    ilegivel = alvo_ilegivel(alvo)
    if ilegivel:
        return {'classe': 'legenda', 'confianca': 'protegido', 'sinal': ilegivel,
                'acao': 'manter'}
    contradicao = _docblock_contradiz(corpo, adiante)
    if contradicao:
        return {'classe': 'contradiz', 'confianca': 'media', 'sinal': contradicao,
                'acao': 'corrigir'}
    if re.search(PENDENCIAS, corpo) and not _casa(corpo, SCAFFOLDS):
        return {'classe': 'pendencia', 'confianca': 'protegido',
                'sinal': 'dívida registrada, com conteúdo', 'acao': 'manter'}
    if re.search(r'^\s*generated\s+by\s+|\bcreated\s+with\s+\w', corpo, re.I | re.M):
        return {'classe': 'gerador', 'confianca': 'media',
                'sinal': 'banner de gerador: em asset de terceiro pode ser a atribuição '
                         'exigida pela licença',
                'acao': 'decidir'}
    motivo = _casa(corpo, SCAFFOLDS)
    if motivo:
        return {'classe': 'scaffold', 'confianca': 'alta', 'sinal': motivo,
                'acao': 'remover'}
    if eh_divisoria(corpo):
        return {'classe': 'divisoria', 'confianca': 'alta',
                'sinal': 'só pontuação ou vazio: não informa nada', 'acao': 'remover'}
    if eh_codigo_comentado(corpo, familia):
        return {'classe': 'codigo_comentado', 'confianca': 'alta',
                'sinal': 'é código desativado — o git já guarda esta versão',
                'acao': 'remover'}
    if eh_redundante(corpo, alvo):
        return {'classe': 'redundante', 'confianca': 'alta',
                'sinal': 'toda palavra do comentário já está na linha que ele descreve',
                'acao': 'remover'}
    if re.search(DOC_TAGS, corpo) or com['forma'] == 'doc':
        return {'classe': 'doc', 'confianca': 'baixa',
                'sinal': 'documentação de API: em lib, é o manual publicado',
                'acao': 'decidir'}
    orfao = _orfaos(corpo, vocabulario, (_palavras(corpo) or [''])[0])
    if orfao:
        return {'classe': 'orfao', 'confianca': 'media', 'sinal': orfao,
                'acao': 'decidir'}
    return {'classe': 'prosa', 'confianca': 'baixa',
            'sinal': 'não foi provado desnecessário', 'acao': 'decidir'}


# ---------------------------------------------------------------- a varredura
def caminhar(raiz: Path):
    for pasta, pastas, arquivos in os.walk(raiz):
        pastas[:] = sorted(d for d in pastas if d not in IGNORAR)
        for nome in sorted(arquivos):
            yield Path(pasta) / nome


def _ler(arquivo: Path) -> str | None:
    try:
        if arquivo.stat().st_size > TETO_BYTES:
            return None
        with open(arquivo, encoding='utf-8', newline='') as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _linha_de(texto: str, pos: int) -> int:
    return texto.count('\n', 0, pos) + 1


def _alvo_de(texto: str, inicio: int, fim: int) -> tuple:
    """A linha que o comentário descreve, e as linhas seguintes.

    Comentário no rabo da linha (`contador++; // incrementa`) descreve o código À
    ESQUERDA; comentário solto descreve o que vem ABAIXO. Trocar os dois faz a regra de
    repetição comparar o comentário com a linha errada.
    """
    comeco_linha = texto.rfind('\n', 0, inicio) + 1
    prefixo = texto[comeco_linha:inicio]
    adiante = texto[fim:fim + 400]
    if prefixo.strip():
        return prefixo.strip(), adiante, 'rabo'
    resto = adiante.lstrip('\n')
    proxima = resto.split('\n', 1)[0] if resto else ''
    proxima = re.split(r'\s(?://|#|--)\s', proxima)[0]
    return proxima.strip(), adiante, 'solto'


def apurar(raiz) -> dict:
    """Todos os comentários do projeto, classificados. Ordem estável, sem carimbo de tempo."""
    raiz = Path(raiz)
    arquivos, nao_lidos, cruas = [], {}, []
    vocabulario: set = set()

    for arquivo in caminhar(raiz):
        rel = arquivo.relative_to(raiz).as_posix()
        if arquivo.name.lower().endswith(GERADOS) or arquivo.suffix.lower() in FORA:
            continue
        fam = familia_de(arquivo)
        if fam is None:
            ext = arquivo.suffix.lower() or arquivo.name
            if ext not in FORA:
                nao_lidos[ext] = nao_lidos.get(ext, 0) + 1
            continue
        texto = _ler(arquivo)
        if texto is None:
            nao_lidos['(ilegível ou maior que o teto)'] = \
                nao_lidos.get('(ilegível ou maior que o teto)', 0) + 1
            continue
        spans = agrupar(texto, extrair(texto, fam))
        arquivos.append(rel)
        # O vocabulário do projeto é o código SEM os comentários: um símbolo que só
        # aparece dentro de comentário não prova que o símbolo existe.
        limpo = list(texto)
        for inicio, fim, _ in spans:
            limpo[inicio:fim] = ' ' * (fim - inicio)
        vocabulario |= _vocabulario_da_linha(''.join(limpo))
        vocabulario.add(arquivo.name.lower())
        vocabulario.add(arquivo.stem.lower())
        cruas.append((rel, fam, texto, spans))

    achados = []
    for rel, fam, texto, spans in cruas:
        for inicio, fim, forma in spans:
            bruto = texto[inicio:fim]
            corpo = corpo_de(bruto)
            if forma == 'bloco' and bruto.lstrip().startswith(('/**', '///', '//!')):
                forma = 'doc'
            if bruto.lstrip().startswith(('///', '//!')):
                forma = 'doc'
            alvo, adiante, posicao = _alvo_de(texto, inicio, fim)
            com = {'arquivo': rel, 'linha': _linha_de(texto, inicio),
                   'inicio': inicio, 'fim': fim, 'texto': bruto, 'corpo': corpo,
                   'forma': forma, 'posicao': posicao, 'alvo': alvo,
                   'linhas': bruto.count('\n') + 1}
            com.update(classificar(com, fam, alvo, adiante, vocabulario))
            com['id'] = hashlib.sha1(
                f'{rel}:{inicio}:{bruto}'.encode('utf-8')).hexdigest()[:8]
            achados.append(com)

    return {'projeto': raiz.resolve().name, 'arquivos_lidos': len(arquivos),
            'comentarios': len(achados), 'nao_lidos': dict(sorted(nao_lidos.items())),
            'achados': achados}


# ---------------------------------------------------------------- a remoção
def aplicar(raiz, escolhas: list) -> dict:
    """Corta exatamente os comentários aprovados, e nada mais.

    A guarda é o texto, não o offset: antes de cortar, o trecho do arquivo tem de ser
    byte a byte o que foi apurado. Offset velho — porque outra edição entrou no meio —
    cortaria no lugar errado, e é assim que uma limpeza de comentário corrompe código.
    """
    raiz = Path(raiz)
    por_arquivo: dict = {}
    for e in escolhas:
        por_arquivo.setdefault(e['arquivo'], []).append(e)

    feitos, recusados = [], []
    for rel, itens in sorted(por_arquivo.items()):
        caminho = raiz / rel
        texto = _ler(caminho)
        if texto is None:
            recusados += [{**i, 'motivo': 'arquivo ilegível'} for i in itens]
            continue
        validos = []
        for item in itens:
            # Guarda de profundidade: se alguém passar a apuração inteira em vez da
            # lista aprovada, o protegido não sai por esta via. Diretiva, licença e
            # "porquê" só saem por edição à mão, com a pessoa olhando.
            if item.get('confianca') == 'protegido':
                recusados.append({**item, 'motivo':
                                  f"protegido ({item.get('classe')}): não sai por aqui"})
                continue
            inicio, fim = item['inicio'], item['fim']
            if texto[inicio:fim] != item['texto']:
                recusados.append({**item, 'motivo':
                                  'o arquivo mudou desde a apuração — rode de novo'})
                continue
            validos.append(item)
        novo = texto
        for item in sorted(validos, key=lambda i: -i['inicio']):
            novo = _cortar(novo, item['inicio'], item['fim'])
        if validos and novo != texto:
            with open(caminho, 'w', encoding='utf-8', newline='') as f:
                f.write(novo)
            feitos += validos
    return {'removidos': feitos, 'recusados': recusados}


def _cortar(texto: str, inicio: int, fim: int) -> str:
    """Tira o comentário sem deixar linha branca onde havia código, nem juntar blocos."""
    comeco_linha = texto.rfind('\n', 0, inicio) + 1
    prefixo = texto[comeco_linha:inicio]
    quebra = texto.find('\n', fim)
    fim_linha = len(texto) if quebra < 0 else quebra
    sufixo = texto[fim:fim_linha]
    if not prefixo.strip() and not sufixo.strip():
        # linha (ou linhas) só de comentário: sai inteira, com a quebra
        return texto[:comeco_linha] + texto[fim_linha + 1:] if quebra >= 0 \
            else texto[:comeco_linha]
    return texto[:inicio].rstrip(' \t') + texto[fim:]


# ---------------------------------------------------------------- a saída
ROTULO = {
    'diretiva': 'o linter, o compilador ou o framework LÊ esta linha',
    'licenca': 'licença e direito autoral',
    'porque': 'explica o motivo — a única cópia dessa informação',
    'pendencia': 'TODO/FIXME com conteúdo: dívida registrada',
    'doc': 'documentação de API (em lib, é o manual publicado)',
    'scaffold': 'lixo de ferramenta ou de template',
    'gerador': 'banner de gerador (pode ser atribuição de licença)',
    'divisoria': 'divisória ou comentário vazio',
    'codigo_comentado': 'código desativado em forma de comentário',
    'redundante': 'repete o que a linha ao lado já diz',
    'contradiz': 'o docblock não bate com a assinatura — corrigir, não remover',
    'orfao': 'cita símbolo que não existe mais',
    'marcador': 'marca a estrutura do bloco (AAA/BDD)',
    'legenda': 'explica um padrão que o código não deixa ler (regex, bits)',
    'prosa': 'não foi provado desnecessário — humano decide',
}
ORDEM = ('alta', 'media', 'baixa', 'protegido')


def resumir(dados: dict) -> str:
    por_classe: dict = {}
    for a in dados['achados']:
        por_classe.setdefault((a['confianca'], a['classe']), []).append(a)
    linhas = [f"Comentários em {dados['projeto']}",
              f"  {dados['arquivos_lidos']} arquivos lidos · "
              f"{dados['comentarios']} comentários"]
    if dados['nao_lidos']:
        nao = ', '.join(f'{k} ({v})' for k, v in dados['nao_lidos'].items())
        linhas.append(f'  não lidos, sem família de sintaxe registrada: {nao}')
    for conf in ORDEM:
        grupos = {c: v for (cf, c), v in por_classe.items() if cf == conf}
        if not grupos:
            continue
        titulo = {'alta': '🔴 alta — candidato a remover',
                  'media': '🟡 média — revisar antes',
                  'baixa': '⚪ baixa — só com contexto humano',
                  'protegido': '🛡 protegido — fora da lista de remoção'}[conf]
        linhas.append('')
        linhas.append(titulo)
        for classe, itens in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
            linhas.append(f'  {classe:<18}{len(itens):>5}   {ROTULO[classe]}')
    return '\n'.join(linhas)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--projeto', default='.')
    p.add_argument('--json', action='store_true', help='apuração completa em JSON')
    p.add_argument('--classe', help='só esta classe (ex.: codigo_comentado)')
    p.add_argument('--confianca', choices=ORDEM, help='só este nível')
    p.add_argument('--aplicar', metavar='ESCOLHAS.json',
                   help='remove SÓ os comentários listados no arquivo (id/arquivo/'
                        'inicio/fim/texto, como saem do --json)')
    args = p.parse_args()
    raiz = Path(args.projeto)
    if not raiz.is_dir():
        print(f'projeto não encontrado: {raiz}', file=sys.stderr)
        return 2

    if args.aplicar:
        escolhas = json.loads(Path(args.aplicar).read_text(encoding='utf-8'))
        if isinstance(escolhas, dict):
            escolhas = escolhas.get('achados') or escolhas.get('remover') or []
        r = aplicar(raiz, escolhas)
        print(f"removidos: {len(r['removidos'])} · recusados: {len(r['recusados'])}")
        for rec in r['recusados']:
            print(f"  recusado {rec.get('arquivo')}:{rec.get('linha')} — {rec['motivo']}")
        return 0 if not r['recusados'] else 1

    dados = apurar(raiz)
    if args.classe:
        dados['achados'] = [a for a in dados['achados'] if a['classe'] == args.classe]
    if args.confianca:
        dados['achados'] = [a for a in dados['achados']
                            if a['confianca'] == args.confianca]
    if args.json:
        print(json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(resumir(dados))
    return 0


if __name__ == '__main__':
    sys.exit(main())
