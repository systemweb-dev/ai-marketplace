"""JavaScript, TypeScript e Vue — a mesma sintaxe de import nos três.

O arquivo `.vue` é lido INTEIRO, sem separar o bloco `<script>`: ele contém
JavaScript normal, e em projeto Vue medido mais da metade dos imports mora ali
(389 de 676). Separar o bloco custaria um parser de SFC e pegaria o mesmo.
"""
import re

EXTENSOES = ['.ts', '.tsx', '.js', '.jsx', '.vue', '.mjs', '.cjs']
ARQUIVO_DE_PASTA = 'index'          # `./pasta` -> `pasta/index.ts`
NOME_PURO_PODE_SER_INTERNO = False  # string sem `./` e sem apelido é pacote ou builtin

# Builtin do Node tem nome de utilitário comum e NUNCA aparece em `dependencies` —
# as duas coisas juntas fazem dele a armadilha perfeita: `import path from 'path'`
# casaria com `src/utils/path.ts`, único, resolvido, errado.
BUILTINS = frozenset({
    'assert', 'buffer', 'child_process', 'cluster', 'console', 'constants', 'crypto',
    'dgram', 'dns', 'domain', 'events', 'fs', 'http', 'http2', 'https', 'inspector',
    'module', 'net', 'os', 'path', 'perf_hooks', 'process', 'punycode', 'querystring',
    'readline', 'repl', 'stream', 'string_decoder', 'timers', 'tls', 'trace_events',
    'tty', 'url', 'util', 'v8', 'vm', 'wasi', 'worker_threads', 'zlib',
})

# Onde mora o vocabulário de caminho desta linguagem. É DECLARAÇÃO: quem lê é o
# leitor genérico do `resolucao.py`, que não sabe o que é um tsconfig.
CONFIGS = [
    {'arquivo': 'tsconfig.json', 'prefixos': 'compilerOptions.paths',
     'raizes': 'compilerOptions.baseUrl'},
    {'arquivo': 'jsconfig.json', 'prefixos': 'compilerOptions.paths',
     'raizes': 'compilerOptions.baseUrl'},
]

# As cinco formas, medidas como presentes nos projetos reais.
#
# O miolo entre `import` e `from` é UMA classe negada, e cada caractere de fora dela
# está lá por um motivo medido:
#
# - ela aceita QUEBRA DE LINHA — classe negada casa `\n`, ao contrário do `.` —,
#   porque importar vários nomes passa da largura e o formatador quebra em bloco.
#   Barrar isso custava **40 imports internos** nos três projetos de calibração, e
#   todos eram relativos ou apelidados: sumiam sem erro, só ausentes;
# - é UMA classe, nunca `(?:[^'";]|\n)*?`. Essa alternância é ambígua, já que a
#   classe negada também casa `\n`, e os dois ramos disputando o mesmo caractere
#   fazem o backtracking dobrar por linha. Medido: 0,56 s com 18 linhas de miolo,
#   2,3 s com 20, 9 s com 22, **36 s com 24** — e o gatilho é uma `interface`
#   TypeScript sem ponto e vírgula, que é o padrão do formatador em projeto Vue. Um
#   arquivo desses estourava sozinho o orçamento de 60 s da varredura inteira;
# - `;` e CRASE ficam de fora para o casamento preguiçoso não atravessar instrução.
#   Sem a crase, `export const DOC = \`veja from "@/paginas/Home.vue"\`` virava aresta
#   para um arquivo que existe, inventada por prosa dentro de template literal.
#
# A âncora de início de linha barra o `//` e o ` * ` do JSDoc. Bloco `/* */` sem
# prefixo por linha **passa** — o "comentar bloco" do editor produz aresta fantasma.
# Isso está escrito porque mediu **zero** ocorrências nos quatro projetos de
# calibração: é limite conhecido, não garantia.
#
# As duas últimas alternativas NÃO podem ter âncora — `import()` e `require()`
# aparecem no meio de uma expressão —, então elas casam dentro de comentário também.
# Medido nos quatro projetos de calibração: 10 casamentos assim, 8 deles num
# `.min.js` que a poda já exclui, e os 2 restantes apontando alvo externo. Zero
# aresta errada. Um `import('./arquivo-real')` comentado viraria aresta fantasma, e
# por isso o caso está escrito aqui — tirar comentário antes de extrair exigiria um
# analisador que não confunda `//` dentro de string (toda URL tem um), e é máquina
# demais para um risco que mediu zero.
FORMAS = re.compile(
    r"""(?:^|\n)\s*import\s+[^'"`;]*?from\s*['"]([^'"]+)['"]"""   # import … from
    r"""|(?:^|\n)\s*export\s+[^'"`;]*?from\s*['"]([^'"]+)['"]"""  # export … from
    r"""|(?:^|\n)\s*import\s*['"]([^'"]+)['"]"""                  # import 'x' (efeito)
    r"""|import\s*\(\s*['"]([^'"]+)['"]"""                        # import() dinâmico
    r"""|require\s*\(\s*['"]([^'"]+)['"]""")                      # require()


def extrair(texto: str) -> list[str]:
    """As strings de import, na ordem em que aparecem e SEM REPETIÇÃO.

    O `import()` dinâmico vale pouco em quantidade (14 e 9 ocorrências nos projetos
    medidos) e muito em valor: é a aresta ROTA -> TELA da SPA, o análogo front-end
    da rota-por-string do PHP — com a diferença de ser visível.

    A repetição sai aqui porque o orquestrador dá `append` em `arestas` por
    ocorrência: alvo repetido viraria aresta duplicada no inventário e dependente
    contado duas vezes no ranking. Caso real: o `.vue` com dois blocos `<script>`
    que importam o mesmo componente nos dois.
    """
    achados = [g for m in FORMAS.finditer(texto) for g in m.groups() if g]
    return list(dict.fromkeys(achados))


def classificar(alvo: str) -> str:
    """Forma da string, sem olhar o disco e sem adivinhar.

    `@escopo/pacote` e `@Apelido/arquivo` são sintaticamente IGUAIS, e separar pela
    caixa da inicial erra: medido num projeto real, `@areas` é um apelido
    minúsculo com 45 imports — a regra da caixa o mandaria para fora como pacote, e
    45 arestas internas sumiriam em silêncio. Então os dois saem daqui como
    `qualificado`, e quem separa é a etapa 2, pela dependência DECLARADA.

    O risco de `@vue/test-utils` virar `test-utils` e casar com `src/test-utils/` é
    barrado em dois lugares: a dependência declarada vence antes, e o que resta tem
    um segmento só, abaixo de MIN_SEGMENTOS.
    """
    if alvo.startswith('.'):
        return 'relativo'
    if alvo.startswith(('@', '~')):
        return 'qualificado' if '/' in alvo else 'nome_puro'
    return 'nome_puro'
