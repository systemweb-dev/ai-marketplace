# Plano de implementação — Grafo de import real para PHP e TypeScript

[spec.md](spec.md) · medição que sustenta o desenho:
[`referencias/medicao-de-resolucao.md`](referencias/medicao-de-resolucao.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** a seção *"o que depende do quê"* deixa de ser lacuna em PHP e TypeScript, com
aresta real resolvida pelos arquivos que existem e a taxa de resolução publicada no documento —
**sem perder o grafo de Python**, que já funciona.

**Arquitetura:** sintaxe é por linguagem, resolução é uma só. Cada `lib/linguagens/<x>.py`
devolve as strings de import, classifica cada uma em `relativo | qualificado | nome_puro` e
**declara** o que a resolução precisa saber da linguagem sem perguntar (extensões, builtins,
arquivo de pasta, se nome puro pode ser interno, onde mora a configuração). O
`lib/resolucao.py` casa as strings contra o índice de sufixos dos arquivos que existem — único
resolve, ambíguo não resolve — e uma segunda passada usa as bases já provadas para desempatar.
O `lib/imports.py` orquestra, conta sete baldes e ordena.

**Stack:** Python 3 (stdlib), `pytest` no `.venv` do diretório da skill. Sem dependência nova.

**Onde o código vive:** `~/.claude/skills/sw-codebase-guide/`. Todos os caminhos deste plano
são relativos a essa pasta. Rode os testes de lá:
`.venv/bin/python -m pytest tests/ -q` (hoje: **206 passam**).

**Restrições verificáveis (do spec):**

| Restrição | Como o plano checa |
|---|---|
| nenhuma aresta errada numa amostra de 30 conferidas à mão | Task 1, steps 4 a 6 (spike) |
| **o grafo de Python não regride** | Task 9, steps 6 e 7 (os testes de hoje, sem alteração) |
| PHP resolve ≥ 95% dos `use` internos | Task 11, step 3 |
| JS/TS resolve ≥ 95% dos imports internos | Task 11, step 3 |
| nenhum nome puro vira aresta onde a linguagem não permite | Task 6, steps 6 a 9 |
| abaixo de 70% numa linguagem, a seção dela é lacuna | Task 13, steps 1, 3 e 10 |
| arquivo de puro re-export fora do ranking | Task 13, steps 5 e 6 |
| `resolucao.py` não contém `if linguagem ==` nem nome de linguagem | Task 15, step 1 |
| varredura ≤ 60 s num projeto de ~2.000 arquivos | Task 15, step 7 |
| mesmo projeto → mesmo `inventory.json`, byte a byte, **entre processos** | Task 15, steps 3 a 5 |
| nenhuma afirmação de ausência de dependentes no documento montado | Task 15, step 9 |

**Tipos de teste:** unit e integração, como o spec decidiu. Sem e2e — não há interface.

**A disciplina desta base:** teste verde prova que o teste roda, não que a guarda funciona.
Toda guarda nova tem uma **prova por mutação**: quebre a guarda, confirme que um teste cai,
desfaça. São **22** no plano, cada uma como step próprio.

**O que a revisão do plano mudou, antes de uma linha ser escrita** (um revisor independente
prototipou os módulos e rodou os testes e as mutações dos steps):

1. **A primeira versão destruía o grafo de Python.** `from pedido import Pedido` virava
   `nome_puro`, e "nome puro é externo" o mandava para fora: os 210 arquivos `.py` deste
   repositório cairiam abaixo do piso de 70% e a seção voltaria a ser lacuna — regressão da
   v0.2.0 disfarçada de progresso. "Nome puro é externo" é regra do **JS e do PHP**, não do
   mundo: em Python um nome solto costuma ser módulo local. Por isso o contrato das linguagens
   cresceu: `NOME_PURO_PODE_SER_INTERNO` e `ARQUIVO_DE_PASTA` passaram a ser **declarados**, e
   o resolvedor continua sem saber qual linguagem está olhando.
2. **`candidatos` tenta a string INTEIRA antes de tirar o primeiro segmento.** `lib/config`
   casa direto em Python; `App\Dominio\X` só casa sem o `App`, porque a pasta é `app`
   minúscula. Tentar as duas, nessa ordem, serve às três linguagens sem ramificar.
3. **Três provas por mutação não matavam**, e uma fixture tinha a ordem de inserção já
   ordenada. Estão refeitas.
4. **A Task 9 original fazia trabalho de três** e escondia três dos defeitos acima. Virou 9,
   10 e 11.
5. **O rodapé que a Task 13 escreve continha uma frase da lista `PROIBIDAS`** — e o teste da
   Task 15 reprovaria o texto que a Task 13 acabou de escrever. É a terceira vez que essa
   armadilha pega alguém nesta skill.

---

### Task 1: SPIKE — sufixo único é evidência ou coincidência?

**Arquivos:**
- Criar: `/tmp/spike-sufixo/conferir.py` (descartável; **não** vira produção)

**Depende de:** nada

**Por que é a task 1:** se o sufixo único produzir aresta errada, a abordagem do spec cai e o
plano inteiro muda. É a única suposição que pode derrubar o desenho.

**Deu certo se:** zero arestas erradas nas 30 conferidas.
**Se falhar:** primeiro tenta-se exigir **três** segmentos no candidato (hoje são dois) e
remede; se ainda houver erro, `MIN_PROVAS` sobe para 10 e o sufixo único passa a valer **só**
sob base provada; se nem isso, o sufixo deixa de ser evidência e sobra a configuração
declarada, com o que ela não cobrir virando lacuna.

- [x] **Step 1: criar o diretório do spike**

```bash
mkdir -p /tmp/spike-sufixo
```

- [x] **Step 2: escrever o amostrador com as MESMAS regras que o plano implementa**

O medidor do dossiê serviu para decidir o desenho, mas ele **não tem** o piso de dois segmentos
nem o desempate por base — as duas regras que o plano acrescentou. Conferir o algoritmo antigo
provaria a coisa errada. Crie `/tmp/spike-sufixo/conferir.py`:

```python
"""Sorteia 30 arestas resolvidas e imprime cada uma com o contexto, para conferência
à mão. Implementa as regras DO PLANO: piso de dois segmentos, tentativa com a string
inteira antes da sem o primeiro segmento, e desempate por base provada.

Semente fixa: a mesma amostra sai em qualquer execução. Amostra que não se regera
não serve de prova."""
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SEMENTE = 20261007
MIN_PROVAS, MIN_SEGMENTOS = 5, 2
IGNORAR = {'vendor', 'node_modules', '.git', 'dist', 'build', '.next', 'coverage'}
POR_LINGUAGEM = {
    '.php': (['.php'], re.compile(r'^\s*use\s+(?:function\s+|const\s+)?\\?([A-Za-z_][\w\\]*)',
                                  re.M | re.I), '\\'),
    '.ts': (['.ts', '.tsx', '.js', '.jsx', '.vue', '.mjs'],
            re.compile(r"""(?:^|\n)\s*(?:import\s[^'"]*from\s*|import\s*|require\()\s*['"]([^'"]+)['"]"""),
            None),
}


def indexar(caminhos):
    idx = defaultdict(set)
    for c in caminhos:
        partes = c.split('/')
        for i in range(len(partes)):
            idx['/'.join(partes[i:])].add(c)
    return idx


def casar(alvo, idx, exts):
    if alvo.count('/') + 1 < MIN_SEGMENTOS:
        return [], ''
    for t in [alvo] + [alvo + e for e in exts] + [f'{alvo}/index{e}' for e in exts]:
        if idx.get(t):
            return sorted(idx[t]), t
    return [], ''


def base_de(destino, sufixo):
    return destino[:len(destino) - len(sufixo)].rstrip('/')


def arestas(raiz, extensoes, padrao, separador):
    raiz = Path(raiz)
    arqs = [p for p in raiz.rglob('*')
            if p.is_file() and p.suffix in extensoes
            and not any(x in p.parts for x in IGNORAR)]
    caminhos = [p.relative_to(raiz).as_posix() for p in arqs]
    idx = indexar(caminhos)
    bases, pendentes, saida = defaultdict(Counter), [], []
    for p, rel in zip(arqs, caminhos):
        for m in padrao.finditer(p.read_text('utf-8', 'replace')):
            alvo = m.group(1)
            if separador:
                alvo = alvo.replace(separador, '/')
            if alvo.startswith('.'):
                continue                       # relativo resolve sem índice
            prefixo, _, resto = alvo.partition('/')
            for tentativa in (alvo, resto):
                if not tentativa:
                    continue
                achados, sufixo = casar(tentativa, idx, extensoes)
                if achados:
                    break
            if len(achados) == 1:
                saida.append((rel, alvo, achados[0], 'sufixo_unico'))
                bases[prefixo][base_de(achados[0], sufixo)] += 1
            elif achados:
                pendentes.append((rel, alvo, prefixo, achados, sufixo))
    provadas = {k: {b for b, n in c.items() if n >= MIN_PROVAS} for k, c in bases.items()}
    for rel, alvo, prefixo, achados, sufixo in pendentes:
        sob = [d for d in achados if base_de(d, sufixo) in provadas.get(prefixo, set())]
        if len(sob) == 1:
            saida.append((rel, alvo, sob[0], 'base_provada'))
    return saida


if __name__ == '__main__':
    todas = []
    for raiz in sys.argv[1:]:
        for extensoes, padrao, separador in POR_LINGUAGEM.values():
            todas += arestas(raiz, extensoes, padrao, separador)
    random.Random(SEMENTE).shuffle(todas)
    print(f'{len(todas)} arestas resolvidas; conferindo 30\n')
    for i, (origem, alvo, destino, proc) in enumerate(todas[:30], 1):
        print(f'{i:2}. [{proc}]  {origem}')
        print(f'      import {alvo!r}  ->  {destino}')
```

- [x] **Step 3: rodar o spike nos projetos de calibração, PHP e JS**

```bash
python3 /tmp/spike-sufixo/conferir.py <raiz-do-monorepo> <raiz-do-projeto-next>
```
Esperado: imprime 30 pares `import 'X' -> arquivo`, misturando `.php` e `.ts`/`.vue`, com a
procedência de cada um.

- [x] **Step 4: conferir as 30 à mão**

Para cada par, abra o arquivo de origem, ache a linha do import e responda **uma** pergunta:
*o arquivo de destino é mesmo o que esse import carrega?*

Os dois modos de erro a caçar: **(a)** o destino tem o nome certo mas está na pasta errada
(duas pastas com o mesmo arquivo, e o índice escolheu a de fora do alcance do apelido);
**(b)** o import era de pacote e casou com arquivo do projeto por coincidência de nome.

- [x] **Step 5: conferir em especial as de procedência `base_provada`**

São as de maior risco: nelas o destino foi escolhido entre vários candidatos. Se houver menos
de 5 na amostra, rode de novo com `SEMENTE` diferente **só para olhar** e anote — a amostra
que vale como prova é a da semente declarada.

- [x] **Step 6: registrar o resultado no plano**

Escreva o veredito em "Ajustes durante a execução", no fim deste arquivo, com a data e o
número (ex.: *"30 de 30 corretas; nenhuma aresta errada"*). **Se houver qualquer erro**, pare e
aplique a saída declarada no topo da task antes de seguir.

---

### Task 2: o contrato das linguagens, com o Python mudando de casa

**Arquivos:**
- Criar: `scripts/lib/linguagens/__init__.py`
- Criar: `scripts/lib/linguagens/python.py`
- Teste: `tests/test_linguagens.py`

**Depende de:** Task 1

**Contrato que esta task publica:** cada módulo em `lib/linguagens/` expõe

```python
EXTENSOES: list[str]                  # candidatas na resolução, em ordem de precedência
BUILTINS: frozenset[str]              # nomes que a linguagem resolve sozinha
CONFIGS: list[dict]                   # onde mora o vocabulário de caminho
ARQUIVO_DE_PASTA: str | None          # 'index' no JS, '__init__' no Python, None no PHP
NOME_PURO_PODE_SER_INTERNO: bool      # True em Python, False em JS e PHP
def extrair(texto: str) -> list[str]
def classificar(alvo: str) -> str     # 'relativo' | 'qualificado' | 'nome_puro'
```

**Nenhuma das sete toca o disco.** As duas últimas constantes existem porque a primeira versão
deste plano tratou "nome puro é externo" e "pasta tem `index`" como universais — e as duas são
do JS. O resultado medido pelo revisor: cada import Python de módulo de um segmento virava
externo, e `from pacote import X` nunca achava o `__init__.py`.

- [x] **Step 1: escrever o teste do contrato, que falha**

```python
# tests/test_linguagens.py
import importlib

MODULOS = ['python']        # cresce com as tasks 3 e 4


def test_cada_modulo_de_linguagem_cumpre_o_contrato():
    """O contrato é o que permite acrescentar uma linguagem sem tocar no resolvedor.
    Sem este teste, o quarto módulo chega com uma constante a menos e o resolvedor
    ganha um `if` para compensar — que é exatamente o que o desenho proíbe."""
    for nome in MODULOS:
        # Arrange
        mod = importlib.import_module(f'lib.linguagens.{nome}')
        # Act / Assert
        assert isinstance(mod.EXTENSOES, list) and mod.EXTENSOES
        assert isinstance(mod.BUILTINS, frozenset)
        assert isinstance(mod.CONFIGS, list)
        assert mod.ARQUIVO_DE_PASTA is None or isinstance(mod.ARQUIVO_DE_PASTA, str)
        assert isinstance(mod.NOME_PURO_PODE_SER_INTERNO, bool)
        assert callable(mod.extrair) and callable(mod.classificar)


def test_extrator_de_python_devolve_o_modulo_com_barra():
    """O resolvedor casa contra um índice de caminhos, que usa `/`. Devolver
    `lib.config` obrigaria o resolvedor a saber que ponto é separador em Python —
    um `if linguagem ==` disfarçado."""
    # Arrange
    from lib.linguagens import python
    # Act
    achados = python.extrair('from lib.config import ler\nimport json\n')
    # Assert
    assert 'lib/config' in achados
    assert 'json' in achados


def test_import_relativo_de_python_vira_caminho_relativo():
    """`from .irmao import x` é `./irmao` e `from ..pai import x` é `../pai`. Sem a
    tradução, o resolvedor leria `.irmao` como NOME DE ARQUIVO e o import ficaria
    pendurado — medido pelo revisor do plano contra a primeira versão."""
    # Arrange
    from lib.linguagens import python
    # Act / Assert
    assert python.extrair('from .irmao import x\n') == ['./irmao']
    assert python.extrair('from ..pai.modulo import x\n') == ['../pai/modulo']


def test_python_declara_que_nome_puro_pode_ser_interno():
    """`from pedido import Pedido` é import de módulo LOCAL num layout plano — o
    mais comum em projeto Python pequeno. Tratar nome puro como externo (que é a
    regra certa no JS) apagaria o grafo de Python inteiro."""
    # Arrange
    from lib.linguagens import python
    # Act / Assert
    assert python.NOME_PURO_PODE_SER_INTERNO is True
    assert python.ARQUIVO_DE_PASTA == '__init__'
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_linguagens.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.linguagens'`

- [x] **Step 3: criar o pacote e o módulo de Python**

```python
# scripts/lib/linguagens/__init__.py
"""Um módulo por linguagem: a SINTAXE mora aqui, a resolução mora no `resolucao.py`.

Nenhum destes módulos toca o sistema de arquivos. É essa separação que mantém de pé
a restrição "o resolvedor não conhece linguagem": o que é específico de uma delas ou
é expressão regular (`extrair`), ou é regra de forma da string (`classificar`), ou é
dado declarado (as cinco constantes).

As duas constantes menos óbvias nasceram de um defeito: a primeira versão do plano
tratou "nome puro é externo" e "pasta tem index" como universais, e as duas são do
JavaScript. Em Python, `from pedido import X` é módulo local e a pasta tem
`__init__.py` — com as regras do JS, o grafo de Python desaparecia inteiro.
"""
```

```python
# scripts/lib/linguagens/python.py
"""Python: o `ast` da stdlib, que sempre está presente."""
import ast

EXTENSOES = ['.py']
BUILTINS = frozenset()          # o índice decide: o que não é arquivo do projeto é externo
CONFIGS = []                    # Python não declara mapeamento de caminho em JSON
ARQUIVO_DE_PASTA = '__init__'   # `from pacote import X` -> `pacote/__init__.py`
NOME_PURO_PODE_SER_INTERNO = True   # layout plano: `from pedido import Pedido`


def extrair(texto: str) -> list[str]:
    """Os módulos importados, como CAMINHO: ponto vira `/`, e o import relativo vira
    `./` e `../`.

    As duas traduções são feitas AQUI e não no resolvedor. `from .irmao import x` com
    o ponto cru seria lido como nome de arquivo (`pasta/.irmao`) e o import ficaria
    pendurado; e fazer o resolvedor saber que em Python o separador é ponto seria um
    `if linguagem ==` disfarçado de detalhe.
    """
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return []               # arquivo quebrado não derruba a varredura
    achados = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            achados += [a.name.replace('.', '/') for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            modulo = (no.module or '').replace('.', '/')
            if not no.level:
                if modulo:
                    achados.append(modulo)
            else:
                # nível 1 é o pacote do próprio arquivo: `./`. Cada nível a mais sobe um.
                achados.append('./' + '../' * (no.level - 1) + modulo)
    return achados


def classificar(alvo: str) -> str:
    if alvo.startswith('.'):
        return 'relativo'
    return 'qualificado' if '/' in alvo else 'nome_puro'
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_linguagens.py -q`
Esperado: PASSA (4 testes)

- [x] **Step 5: prova por mutação — o relativo de Python volta a ser cru**

Troque `achados.append('./' + '../' * (no.level - 1) + modulo)` por
`achados.append('.' * no.level + modulo)` e rode.
Esperado: **cai** `test_import_relativo_de_python_vira_caminho_relativo`. Desfaça.

- [x] **Step 6: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **210 passam** (206 + 4). O `imports.py` ainda usa o caminho antigo — a troca
acontece na Task 9, e até lá nada regride.

---
### Task 3: extrator de JavaScript, TypeScript e Vue

**Arquivos:**
- Criar: `scripts/lib/linguagens/js.py`
- Alterar: `tests/test_linguagens.py:3` (acrescentar `'js'` a `MODULOS`)
- Teste: `tests/test_linguagens.py`

**Depende de:** Task 2

**Contrato que esta task publica:** `lib.linguagens.js`, cumprindo o contrato da Task 2.

- [x] **Step 1: escrever os testes que falham**

```python
# acrescente em tests/test_linguagens.py


def test_extrator_de_js_pega_as_cinco_formas():
    """As cinco foram MEDIDAS nos projetos reais. Perder uma tira arestas do
    denominador em silêncio, que é pior que não resolvê-las: a taxa de resolução
    passaria a mentir para cima."""
    # Arrange
    from lib.linguagens import js
    fonte = (
        "import Box from '@Component/Box.vue'\n"
        "import './estilo.css'\n"
        "export { util } from './util'\n"
        "const V = () => import('@View/Pedido.vue')\n"
        "const fs = require('fs')\n")
    # Act
    achados = js.extrair(fonte)
    # Assert
    assert achados == ['@Component/Box.vue', './estilo.css', './util',
                       '@View/Pedido.vue', 'fs']


def test_extrator_de_js_le_o_script_do_arquivo_vue():
    """Em projeto Vue medido, 389 dos 676 imports vivem dentro de `.vue` — mais da
    metade. O `<script>` é JavaScript normal, então o arquivo é lido inteiro."""
    # Arrange
    from lib.linguagens import js
    sfc = ("<template><div/></template>\n"
           "<script>\nimport Card from '@Component/Card.vue'\n</script>\n"
           "<style>.a{}</style>\n")
    # Act / Assert
    assert js.extrair(sfc) == ['@Component/Card.vue']


def test_classificar_de_js_trata_nome_puro_e_escopado():
    """Nome puro é externo por regra, e pacote escopado tem DOIS segmentos: tratar
    `@vue/test-utils` como apelido faria `test-utils` casar com `src/test-utils/`."""
    # Arrange
    from lib.linguagens import js
    # Act / Assert
    assert js.classificar('./x') == 'relativo'
    assert js.classificar('../x/y') == 'relativo'
    assert js.classificar('@Component/Box.vue') == 'qualificado'
    assert js.classificar('~/lib/x') == 'qualificado'
    assert js.classificar('vuex') == 'nome_puro'
    assert js.classificar('vitest/config') == 'nome_puro'
    # `@escopo/pacote` e `@Apelido/arquivo` têm a MESMA forma — não dá para separar
    # pela sintaxe, e tentar pela caixa da inicial erra: medido num projeto real,
    # `@areas` é um apelido minúsculo com 45 imports, que a regra da caixa
    # mandaria para fora como se fosse pacote. Quem separa é a etapa 2, pela
    # dependência DECLARADA, e o que sobra é decidido pelos arquivos que existem.
    assert js.classificar('@vue/test-utils') == 'qualificado'
    assert js.classificar('@areas/painel/Perfil.vue') == 'qualificado'


def test_js_declara_que_nome_puro_NAO_pode_ser_interno():
    """O oposto do Python, e é por isso que a constante existe: aqui o nome solto é
    pacote ou builtin, e deixá-lo tentar o índice produziu oito arestas erradas num
    projeto real (`server-only` -> `tests/helpers/server-only.ts`)."""
    # Arrange
    from lib.linguagens import js
    # Act / Assert
    assert js.NOME_PURO_PODE_SER_INTERNO is False
    assert js.ARQUIVO_DE_PASTA == 'index'


def test_js_declara_os_builtins_do_node():
    """`fs`, `path` e `url` nunca aparecem em `dependencies`, e têm nome de
    utilitário comum: sem a lista, `import path from 'path'` casaria com
    `src/utils/path.ts`."""
    # Arrange
    from lib.linguagens import js
    # Act / Assert
    assert {'fs', 'path', 'url', 'crypto', 'events'} <= js.BUILTINS
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_linguagens.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.linguagens.js'`

- [x] **Step 3: escrever o módulo**

```python
# scripts/lib/linguagens/js.py
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

# As cinco formas, medidas como presentes nos projetos reais. (A ordem das
# alternativas NÃO importa aqui: a de efeito colateral exige aspa imediatamente
# depois de `import`, então ela não casa `import X from 'y'` de jeito nenhum —
# conferido invertendo a ordem e comparando a saída.)
FORMAS = re.compile(
    r"""(?:^|\n)\s*import\s[^'"\n]*from\s*['"]([^'"]+)['"]"""     # import … from
    r"""|(?:^|\n)\s*export\s[^'"\n]*from\s*['"]([^'"]+)['"]"""    # export … from
    r"""|(?:^|\n)\s*import\s*['"]([^'"]+)['"]"""                  # import 'x' (efeito)
    r"""|import\s*\(\s*['"]([^'"]+)['"]"""                        # import() dinâmico
    r"""|require\s*\(\s*['"]([^'"]+)['"]""")                      # require()


def extrair(texto: str) -> list[str]:
    """As strings de import, na ordem em que aparecem.

    O `import()` dinâmico vale pouco em quantidade (14 e 9 ocorrências nos projetos
    medidos) e muito em valor: é a aresta ROTA -> TELA da SPA, o análogo front-end
    da rota-por-string do PHP — com a diferença de ser visível.
    """
    return [g for m in FORMAS.finditer(texto) for g in m.groups() if g]


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
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_linguagens.py -q`
Esperado: FALHA ainda, em `test_todo_modulo_de_linguagem_cumpre_o_contrato` — falta
acrescentar `'js'` à lista.

- [x] **Step 5: ligar o módulo ao teste de contrato**

Em `tests/test_linguagens.py`, troque `MODULOS = ['python']` por:

```python
MODULOS = ['python', 'js']
```

Rode: `.venv/bin/python -m pytest tests/test_linguagens.py -q`
Esperado: PASSA (9 testes)

- [x] **Step 6: prova por mutação — o extrator perde o `import()` dinâmico**

Apague a linha do `import() dinâmico` em `FORMAS` e rode
`.venv/bin/python -m pytest tests/test_linguagens.py -q`.
Esperado: **cai** `test_extrator_de_js_pega_as_cinco_formas`. Desfaça.

- [x] **Step 7: prova por mutação — o `.vue` deixa de ser lido**

Troque o corpo de `extrair` por `return []` quando o texto contiver `'<template>'` e rode.
Esperado: **cai** `test_extrator_de_js_le_o_script_do_arquivo_vue`. Desfaça.

- [x] **Step 8: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: a suíte inteira verde (ficou em **224**; a aritmética do plano é anterior às correções da Task 2)

---

### Task 4: extrator de PHP

**Arquivos:**
- Criar: `scripts/lib/linguagens/php.py`
- Alterar: `tests/test_linguagens.py:3` (acrescentar `'php'` a `MODULOS`)
- Teste: `tests/test_linguagens.py`

**Depende de:** Task 2

**Contrato que esta task publica:** `lib.linguagens.php`, cumprindo o contrato da Task 2.

- [x] **Step 1: escrever os testes que falham**

```python
# acrescente em tests/test_linguagens.py


def test_extrator_de_php_pega_as_formas_do_use():
    """`use X;` responde por 992 e 1.145 ocorrências nos dois projetos medidos;
    `use … as` por 1 em cada. As outras três não apareceram, mas são sintaxe padrão
    e custam uma alternância — cair fora delas tiraria arestas do DENOMINADOR em
    silêncio."""
    # Arrange
    from lib.linguagens import php
    fonte = (
        "<?php\nnamespace App\\Admin;\n"
        "use App\\Dominio\\Models\\Pedido;\n"
        "use App\\Dominio\\Models\\Item as LinhaDoPedido;\n"
        "use App\\Servicos\\{Cobranca, Entrega};\n"
        "use function App\\Ajuda\\formatar;\n"
        "use const App\\Ajuda\\TETO;\n"
        "use Exception;\n")
    # Act
    achados = php.extrair(fonte)
    # Assert
    assert 'App/Dominio/Models/Pedido' in achados
    assert 'App/Dominio/Models/Item' in achados
    assert 'App/Servicos/Cobranca' in achados
    assert 'App/Servicos/Entrega' in achados
    assert 'App/Ajuda/formatar' in achados
    assert 'App/Ajuda/TETO' in achados
    assert 'Exception' in achados


def test_extrator_de_php_nao_devolve_a_propria_declaracao_de_namespace():
    """`namespace App\\Admin;` diz onde o arquivo MORA, não de quem ele depende.
    Devolvê-la criaria uma aresta do arquivo para a própria pasta."""
    # Arrange
    from lib.linguagens import php
    # Act
    achados = php.extrair("<?php\nnamespace App\\Admin;\nuse App\\X;\n")
    # Assert
    assert achados == ['App/X']


def test_classificar_de_php_trata_classe_global_como_nome_puro():
    """`use Exception;` é classe global do PHP. É a mesma frase que no JS se diz
    'nome puro é externo' — e é por as duas serem a MESMA categoria que o resolvedor
    não precisa saber qual linguagem está olhando."""
    # Arrange
    from lib.linguagens import php
    # Act / Assert
    assert php.classificar('Exception') == 'nome_puro'
    assert php.classificar('App/Dominio/Models/Pedido') == 'qualificado'
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_linguagens.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.linguagens.php'`

- [x] **Step 3: escrever o módulo**

```python
# scripts/lib/linguagens/php.py
"""PHP: o `use` do topo do arquivo, que tem gramática simples e fica sempre lá.

Medido em dois projetos reais: `use X;` são 992 e 1.145 ocorrências, `use … as` é 1
em cada, e as outras três formas não aparecem. Elas entram mesmo assim porque são
sintaxe padrão e custam uma alternância — e o que o extrator não vê sai do
DENOMINADOR da taxa sem avisar, que é pior do que não resolver.
"""
import re

EXTENSOES = ['.php']
BUILTINS = frozenset()      # o `classificar` resolve: nome sem `/` é classe global
ARQUIVO_DE_PASTA = None     # PHP não tem arquivo-de-pasta: um `use` aponta uma classe
NOME_PURO_PODE_SER_INTERNO = False   # `use Exception;` é classe global, nunca do projeto
CONFIGS = [{'arquivo': 'composer.json', 'prefixos': 'autoload.psr-4'}]

SIMPLES = re.compile(r'^\s*use\s+(?:function\s+|const\s+)?\\?([A-Za-z_][\w\\]*)\s*(?:as\s+\w+)?\s*;',
                     re.M | re.I)
AGRUPADO = re.compile(r'^\s*use\s+\\?([A-Za-z_][\w\\]*)\\\{([^}]+)\}', re.M | re.I)


def extrair(texto: str) -> list[str]:
    """Os nomes importados, com `/` no lugar da barra invertida.

    A troca do separador é feita AQUI: a string com `\\` jamais casaria num índice
    construído sobre `/`, e consertar isso no resolvedor exigiria que ele soubesse
    que aquilo é PHP.
    """
    achados = [m.group(1) for m in SIMPLES.finditer(texto)]
    for m in AGRUPADO.finditer(texto):
        raiz = m.group(1)
        for item in m.group(2).split(','):
            item = item.strip().split(' as ')[0].strip()
            if item:
                achados.append(f'{raiz}\\{item}')
    return [a.replace('\\', '/') for a in achados]


def classificar(alvo: str) -> str:
    """`use Exception;` é classe global; com namespace, é qualificado.

    Não existe `relativo` em PHP — `use` é sempre a partir da raiz do namespace.
    """
    return 'qualificado' if '/' in alvo else 'nome_puro'
```

- [x] **Step 4: ligar ao contrato e rodar**

Acrescente também, em `tests/test_linguagens.py`:

```python
def test_php_declara_que_nao_tem_arquivo_de_pasta():
    """`use App\\Dominio\\Pedido;` aponta uma classe, não uma pasta. Tentar
    `App/Dominio/Pedido/index.php` seria procurar o que a linguagem não tem."""
    # Arrange
    from lib.linguagens import php
    # Act / Assert
    assert php.ARQUIVO_DE_PASTA is None
    assert php.NOME_PURO_PODE_SER_INTERNO is False
```


Em `tests/test_linguagens.py`, troque a lista por:

```python
MODULOS = ['python', 'js', 'php']
```

Rode: `.venv/bin/python -m pytest tests/test_linguagens.py -q`
Esperado: PASSA (12 testes)

- [x] **Step 5: prova por mutação — o `use` agrupado some**

Troque o corpo do laço de `AGRUPADO` por `pass` e rode.
Esperado: **cai** `test_extrator_de_php_pega_as_formas_do_use`. Desfaça.

- [x] **Step 6: prova por mutação — a declaração de namespace vira import**

Acrescente a `SIMPLES` a alternativa `|^\s*namespace\s+([A-Za-z_][\w\\]*)\s*;` e rode.
Esperado: **cai** `test_extrator_de_php_nao_devolve_a_propria_declaracao_de_namespace`. Desfaça.

- [x] **Step 7: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **221 passam**

---


### Task 5: o índice de sufixos e as etapas 1 e 3

**Arquivos:**
- Criar: `scripts/lib/resolucao.py`
- Teste: `tests/test_resolucao.py`

**Depende de:** Task 2

**Contrato que esta task publica:**
`indexar(caminhos: list[str]) -> dict[str, set[str]]` ·
`resolver_relativo(origem, alvo, indice, extensoes, arquivo_de_pasta) -> str | None` ·
`candidatos(alvo, indice, extensoes, arquivo_de_pasta) -> tuple[list[str], str]`
(os caminhos **e o sufixo que casou**) · `MIN_SEGMENTOS = 2`

- [x] **Step 1: escrever os testes que falham**

```python
# tests/test_resolucao.py
from lib.resolucao import candidatos, indexar, resolver_relativo

EXTS = ['.ts', '.vue', '.js']
PASTA = 'index'


def test_indice_guarda_todo_sufixo_de_cada_caminho():
    """A chave ancorada na raiz nunca casa com o que o código escreve: o import diz
    `@Component/Box`, não `src/components/Box`. Indexar por TODOS os sufixos é o que
    permite casar sem saber qual é a raiz do apelido."""
    # Arrange / Act
    idx = indexar(['src/components/boxs/Box.vue'])
    # Assert
    assert idx['src/components/boxs/Box.vue'] == {'src/components/boxs/Box.vue'}
    assert idx['boxs/Box.vue'] == {'src/components/boxs/Box.vue'}
    assert idx['Box.vue'] == {'src/components/boxs/Box.vue'}


def test_relativo_resolve_contra_o_arquivo_de_origem():
    # Arrange
    idx = indexar(['src/a/pagina.ts', 'src/a/util.ts'])
    # Act / Assert
    assert resolver_relativo('src/a/pagina.ts', './util', idx, EXTS, PASTA) == 'src/a/util.ts'
    assert resolver_relativo('src/a/pagina.ts', '../a/util', idx, EXTS, PASTA) == 'src/a/util.ts'


def test_relativo_de_python_acha_o_arquivo_de_pasta_declarado():
    """Cada linguagem diz como se chama o arquivo de uma pasta. Fixar `index` faria
    `from pacote import X` nunca achar o `__init__.py` — o resolvedor procuraria o
    que o Python não tem."""
    # Arrange
    idx = indexar(['app/principal.py', 'app/pacote/__init__.py'])
    # Act / Assert
    assert resolver_relativo('app/principal.py', './pacote', idx, ['.py'],
                             '__init__') == 'app/pacote/__init__.py'


def test_relativo_que_sobe_acima_da_raiz_nao_resolve():
    """`../../x` num arquivo de raiz não tem para onde subir. O extrator não pode
    barrar isso — ele não conhece o caminho de origem —, e a normalização engole o
    `..` sobrando em silêncio: o alvo viraria `x` e casaria com um `x.py` qualquer.
    Isso é ARESTA ERRADA, a única coisa que o desenho declara pior que aresta
    faltando. O extrator antigo tinha a guarda (`if no.level - 1 > len(partes)`) e
    ela não podia simplesmente desaparecer."""
    # Arrange
    idx = indexar(['pagina.ts', 'x.ts'])
    # Act / Assert
    assert resolver_relativo('pagina.ts', '../../x', idx, EXTS, PASTA) is None


def test_relativo_que_nao_existe_devolve_nulo():
    """Import pendurado é contado, nunca vira aresta: inventar o destino seria a
    aresta errada que este desenho existe para evitar."""
    # Arrange
    idx = indexar(['src/a/pagina.ts'])
    # Act / Assert
    assert resolver_relativo('src/a/pagina.ts', './sumiu', idx, EXTS, PASTA) is None


def test_relativo_prefere_o_arquivo_a_pasta_com_index():
    """Com `x.ts` e `x/index.ts` nos dois, vence a ordem declarada em EXTENSOES — é
    o que o Node faz. Ordem FIXA e escrita, não 'o primeiro candidato ganha'."""
    # Arrange
    idx = indexar(['src/a/pagina.ts', 'src/a/x.ts', 'src/a/x/index.ts'])
    # Act / Assert
    assert resolver_relativo('src/a/pagina.ts', './x', idx, EXTS, PASTA) == 'src/a/x.ts'


def test_tenta_a_string_INTEIRA_antes_de_tirar_o_primeiro_segmento():
    """As duas tentativas servem a linguagens diferentes, e a ordem importa: em
    Python `lib/config` casa inteiro, e em PHP `App/Dominio/X` só casa sem o `App`,
    porque a pasta é `app` minúscula. Quem chama tenta as duas, nesta ordem."""
    # Arrange
    idx = indexar(['lib/config.ts', 'app/Dominio/X.ts'])
    # Act / Assert
    assert candidatos('lib/config', idx, EXTS, PASTA) == (['lib/config.ts'], 'lib/config.ts')
    assert candidatos('App/Dominio/X', idx, EXTS, PASTA) == ([], '')
    assert candidatos('Dominio/X', idx, EXTS, PASTA) == (['app/Dominio/X.ts'], 'Dominio/X.ts')


def test_sufixo_ambiguo_devolve_os_dois_candidatos():
    """Ambíguo NÃO resolve aqui: devolve os candidatos para a segunda passada.
    Escolher um deles seria aresta errada silenciosa.

    O alvo tem DOIS segmentos de propósito: com um só ele cairia no piso e o teste
    passaria por outro motivo — foi o defeito da primeira versão deste plano."""
    # Arrange
    idx = indexar(['src/area/constants.ts', 'src/assets/js/area/constants.ts'])
    # Act
    achados, sufixo = candidatos('area/constants', idx, EXTS, PASTA)
    # Assert
    assert achados == ['src/area/constants.ts', 'src/assets/js/area/constants.ts']
    assert sufixo == 'area/constants.ts'


def test_candidato_de_um_segmento_so_nao_tenta_o_indice():
    """`@/utils` sobra um segmento. Casar um nome solto é sorte, não evidência — ele
    é FRACO e vai para a segunda passada, onde a base provada decide."""
    # Arrange
    idx = indexar(['src/utils.ts'])
    # Act / Assert
    assert candidatos('utils', idx, EXTS, PASTA) == ([], '')
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_resolucao.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.resolucao'`

- [x] **Step 3: escrever o módulo**

```python
# scripts/lib/resolucao.py
"""Resolve a string de import no arquivo — pela EVIDÊNCIA, não pela configuração.

Resolver pelo que o projeto declara exige um leitor por formato, e num projeto real
medido os apelidos moram num `vue.config.js`: JavaScript executando, não dado.
Resolvendo pelos arquivos que EXISTEM, o mesmo projeto resolve 100% dos imports
internos — e os quatro apelidos inferidos batem exatamente com os declarados lá.

**A invariante deste arquivo: aresta errada é pior que aresta faltando.** A falta
aparece na taxa de resolução e o leitor a vê; a errada manda alguém mexer no arquivo
errado e não deixa rastro. Por isso ambíguo não resolve, por isso configuração só
vale conferida, e por isso um segmento só não basta.

Nada aqui conhece linguagem: as três categorias (`relativo`, `qualificado`,
`nome_puro`) e as constantes de forma (extensões, arquivo de pasta) chegam de fora,
declaradas por cada módulo de `lib/linguagens/`.
"""
MIN_SEGMENTOS = 2       # candidato de um segmento é sorte, não evidência


def indexar(caminhos) -> dict:
    """Todo sufixo de caminho -> os arquivos que terminam nele."""
    por_sufixo = {}
    for caminho in caminhos:
        partes = caminho.split('/')
        for i in range(len(partes)):
            por_sufixo.setdefault('/'.join(partes[i:]), set()).add(caminho)
    return por_sufixo


def _tentativas(alvo: str, extensoes: list, arquivo_de_pasta) -> list:
    """O alvo com cada extensão candidata, e depois como pasta.

    A ordem é a de `EXTENSOES` e é FIXA: com `x.ts` e `x/index.ts` existindo, vence
    o primeiro da lista, que é o que o Node faz. Ordem escrita não é o mesmo que
    'o primeiro candidato ganha' — lá são dois candidatos igualmente plausíveis.

    O nome do arquivo de pasta vem declarado: `index` no JS, `__init__` no Python,
    e `None` no PHP, onde um `use` aponta uma classe e não uma pasta.
    """
    saida = [alvo] + [alvo + e for e in extensoes]
    if arquivo_de_pasta:
        saida += [f'{alvo}/{arquivo_de_pasta}{e}' for e in extensoes]
    return saida


def _normalizar(caminho: str):
    """Resolve `.` e `..` sem tocar o disco. Subiu acima da raiz -> None.

    O `..` sobrando NÃO pode ser engolido em silêncio: `../../x` num arquivo de raiz
    viraria `x` e casaria com um `x.py` qualquer — aresta errada, que é a única
    coisa que este desenho declara pior que aresta faltando. O extrator não pode
    barrar isso sozinho porque não conhece o caminho de origem.
    """
    partes = []
    for parte in caminho.split('/'):
        if parte == '..':
            if not partes:
                return None
            partes.pop()
        elif parte not in ('.', ''):
            partes.append(parte)
    return '/'.join(partes)


def resolver_relativo(origem, alvo, indice, extensoes, arquivo_de_pasta):
    """`./x` e `../x` contra o arquivo de origem. Não existe -> None (pendurado)."""
    pasta = origem.rsplit('/', 1)[0] if '/' in origem else ''
    caminho = _normalizar(f'{pasta}/{alvo}' if pasta else alvo)
    if not caminho:
        return None         # subiu acima da raiz, ou o alvo era só `./`
    for tentativa in _tentativas(caminho, extensoes, arquivo_de_pasta):
        # a tentativa é um caminho a partir da raiz, e todo caminho é sufixo de si
        # mesmo no índice: se ele estiver no próprio conjunto, o arquivo existe
        if tentativa in indice.get(tentativa, ()):
            return tentativa
    return None


def candidatos(alvo: str, indice: dict, extensoes: list, arquivo_de_pasta) -> tuple:
    """Os arquivos cujo caminho termina no alvo, E o sufixo que casou.

    O sufixo volta junto porque quem chama precisa dele para calcular a base
    (destino menos sufixo): com `@Component/Box` casando em `Box.vue`, cortar pelo
    tamanho de `Box` deixaria `.vue` na base e ela nunca bateria com outra.

    Um candidato por si não é aresta: quem decide é quem chama. Devolver a lista
    inteira é o que permite o ambíguo ir para a segunda passada em vez de ser
    resolvido no chute.
    """
    if alvo.count('/') + 1 < MIN_SEGMENTOS:
        return [], ''
    for tentativa in _tentativas(alvo, extensoes, arquivo_de_pasta):
        achados = indice.get(tentativa)
        if achados:
            return sorted(achados), tentativa
    return [], ''
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_resolucao.py -q`
Esperado: PASSA (9 testes)

- [x] **Step 5: prova por mutação — ambíguo passa a resolver pelo primeiro**

Em `candidatos`, troque `return sorted(achados), tentativa` por
`return sorted(achados)[:1], tentativa` e rode.
Esperado: **cai** `test_sufixo_ambiguo_devolve_os_dois_candidatos`. Desfaça.

- [x] **Step 6: prova por mutação — o piso de segmentos some**

Troque `MIN_SEGMENTOS = 2` por `MIN_SEGMENTOS = 1` e rode.
Esperado: **cai** `test_candidato_de_um_segmento_so_nao_tenta_o_indice`. Desfaça.

- [x] **Step 7b: prova por mutação — o `..` sobrando volta a ser engolido**

Em `_normalizar`, troque `if not partes: return None` por `if partes:` (e reindente o `pop`)
e rode.
Esperado: **cai** `test_relativo_que_sobe_acima_da_raiz_nao_resolve`. Desfaça.

- [x] **Step 7: prova por mutação — o arquivo de pasta volta a ser fixo em `index`**

Em `_tentativas`, troque `f'{alvo}/{arquivo_de_pasta}{e}'` por `f'{alvo}/index{e}'` e rode.
Esperado: **cai** `test_relativo_de_python_acha_o_arquivo_de_pasta_declarado`. Desfaça.

- [x] **Step 8: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **229 passam**

---

### Task 6: etapa 2 — o que é externo

**Arquivos:**
- Alterar: `scripts/lib/resolucao.py` (acrescentar `eh_externo`)
- Alterar: `scripts/lib/stacks.py` (acrescentar `dependencias_declaradas`)
- Teste: `tests/test_resolucao.py`, `tests/test_stacks.py`

**Depende de:** Task 5

**Contrato que esta task publica:**
`eh_externo(alvo, classe, builtins, declarados, raizes, nome_puro_pode_ser_interno) -> bool` ·
`stacks.dependencias_declaradas(raiz) -> dict[str, set[str]]` (caminho do manifesto -> nomes)

- [x] **Step 1: escrever o teste de `dependencias_declaradas`, que falha**

```python
# acrescente em tests/test_stacks.py
import json

from lib.stacks import dependencias_declaradas


def test_le_so_as_CHAVES_das_dependencias(tmp_path):
    """Valor de dependência carrega URL de registro privado com token. A regra é a
    mesma do `.env`: o nome entra, o valor nunca é lido para dentro."""
    # Arrange
    (tmp_path / 'package.json').write_text(json.dumps({
        'dependencies': {'vue': '^3.0.0',
                         'interno': 'https://usuario:segredo@registro.local/x.tgz'},
        'devDependencies': {'vitest': '^1.0.0'}}))
    # Act
    achados = dependencias_declaradas(tmp_path)
    # Assert
    assert achados['package.json'] == {'vue', 'interno', 'vitest'}
    # `set` não é serializável: o dump precisa de lista, senão o assert levanta
    # TypeError e o teste falha pelo motivo errado
    assert 'segredo' not in json.dumps({k: sorted(v) for k, v in achados.items()})


def test_manifesto_quebrado_nao_derruba_a_varredura(tmp_path):
    # Arrange
    (tmp_path / 'composer.json').write_text('{ isto não é json')
    # Act / Assert
    assert dependencias_declaradas(tmp_path) == {}
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_stacks.py -q`
Esperado: FALHA com `ImportError: cannot import name 'dependencias_declaradas'`

- [x] **Step 3: escrever `dependencias_declaradas` no `stacks.py`**

```python
# acrescente ao fim de scripts/lib/stacks.py
# (`json` e `Path` já estão importados no topo do arquivo — não duplique)
CHAVES_DE_DEPENDENCIA = ('dependencies', 'devDependencies', 'peerDependencies',
                         'optionalDependencies', 'require', 'require-dev')


def dependencias_declaradas(raiz) -> dict:
    """Por manifesto, os NOMES das dependências declaradas — nunca os valores.

    Quem descobre manifesto é este módulo, que já caminha com poda e já aprendeu a
    lição do `.next/package.json`. Duas descobertas de manifesto em arquivos
    diferentes é como aquele bug volta.

    **Só as chaves.** O valor de uma dependência carrega URL de registro privado com
    token — é a mesma regra do `.env`, e vale igual aqui.
    """
    achados = {}
    for arquivo in caminhar(Path(raiz)):
        if arquivo.name not in ('package.json', 'composer.json'):
            continue
        try:
            dados = json.loads(arquivo.read_text('utf-8', 'replace'))
        except (json.JSONDecodeError, OSError):
            continue        # manifesto quebrado não derruba a varredura
        if not isinstance(dados, dict):
            continue
        nomes = set()
        for chave in CHAVES_DE_DEPENDENCIA:
            bloco = dados.get(chave)
            if isinstance(bloco, dict):
                nomes |= set(bloco)
        if nomes:
            achados[arquivo.relative_to(Path(raiz)).as_posix()] = nomes
    return achados
```

Se o `import json` não estiver no topo do `stacks.py`, acrescente-o lá.

- [x] **Step 4: escrever o teste de `eh_externo`, que falha**

```python
# acrescente em tests/test_resolucao.py
from lib.resolucao import eh_externo

DECLARADOS = {'vue', 'vuex', '@vue/test-utils', 'server-only'}
BUILTINS = frozenset({'fs', 'path', 'url'})


def externo(alvo, classe='nome_puro', raizes=(), interno=False):
    return eh_externo(alvo, classe, BUILTINS, DECLARADOS, list(raizes), interno)


def test_nome_puro_e_externo_na_linguagem_que_declara_isso():
    """Medido num projeto real: `import 'server-only'` casaria com
    `tests/helpers/server-only.ts` — oito arestas erradas. No JS, nome puro é
    externo por REGRA, não por não casar."""
    # Act / Assert
    assert externo('server-only')
    assert externo('pacote-nao-declarado')


def test_nome_puro_NAO_e_externo_na_linguagem_que_permite_modulo_local():
    """`from pedido import Pedido` é o layout plano de Python. A primeira versão
    deste plano tratava a regra do JS como universal e apagava o grafo de Python
    inteiro — o revisor mediu: todos os quatro testes de import saíam com zero
    arestas."""
    # Act / Assert
    assert not externo('pedido', interno=True)


def test_builtin_e_externo_mesmo_na_linguagem_que_permite_interno():
    """`fs`, `path` e `url` nunca aparecem em `dependencies` e têm nome de utilitário
    comum. Uma exceção escrita como 'o que não é dependência declarada' autorizaria
    `import fs from 'fs'` -> `src/fs.ts`."""
    # Act / Assert
    assert externo('fs', raizes=['src'])
    assert externo('path', raizes=['src'], interno=True)


def test_nome_puro_de_dois_segmentos_sob_baseUrl_nao_e_externo():
    """A exceção legítima: import absoluto a partir da raiz declarada. Três
    condições juntas — não é declarado, não é builtin, e tem dois ou mais
    segmentos."""
    # Act / Assert
    assert not externo('componentes/Botao', raizes=['src'])


def test_qualificado_nao_declarado_nao_e_externo_por_esta_etapa():
    """`@Component/Box.vue` é apelido: quem decide é o índice, na etapa 3."""
    # Act / Assert
    assert not externo('@Component/Box.vue', classe='qualificado')


def test_pacote_escopado_DECLARADO_e_externo_mesmo_sendo_qualificado():
    """`@vue/test-utils` tem a mesma forma de um apelido, e o `classificar` não tenta
    adivinhar qual é qual — medido, `@areas` é um apelido minúsculo com 45
    imports. Se a dependência declarada não fosse conferida aqui, ele cairia no
    índice e sairia contado como não resolvido: deflacionar a taxa é o espelho de
    inflá-la."""
    # Act / Assert
    assert externo('@vue/test-utils', classe='qualificado')
```

- [x] **Step 5: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_resolucao.py -q`
Esperado: FALHA com `ImportError: cannot import name 'eh_externo'`

- [x] **Step 6: escrever `eh_externo`**

```python
# acrescente em scripts/lib/resolucao.py
def eh_externo(alvo, classe, builtins, declarados, raizes,
               nome_puro_pode_ser_interno) -> bool:
    """O import sai do projeto?

    É aqui que a aresta errada nasce quando nasce, então cada condição tem motivo
    medido:

    - **A dependência declarada vence para QUALQUER classe.** `@vue/test-utils` tem
      a forma de um apelido, e sem esta linha ele cairia no índice e sairia contado
      como não resolvido.
    - **`nome_puro` é externo nas linguagens que declaram isso.** Medido:
      `import 'server-only'` casaria com `tests/helpers/server-only.ts`, oito vezes.
      Mas em Python `from pedido import X` é módulo local, e aplicar a regra do JS
      lá apagava o grafo inteiro — por isso a linguagem declara.
    - **Builtin é externo sempre**, inclusive na linguagem que permite nome puro
      interno: ele nunca está em `dependencies`, então qualquer exceção escrita como
      "o que não é declarado" o deixaria passar.
    - **A exceção do `baseUrl` é estreita**: não declarado, não builtin, e dois ou
      mais segmentos.
    """
    primeiro = alvo.split('/', 1)[0]
    if alvo in declarados or primeiro in declarados:
        return True
    if classe != 'nome_puro':
        return False
    if alvo in builtins or primeiro in builtins:
        return True
    if nome_puro_pode_ser_interno:
        return False        # quem decide é o índice: o que não é arquivo é externo
    cabe_em_raiz = bool(raizes) and alvo.count('/') + 1 >= MIN_SEGMENTOS
    return not cabe_em_raiz
```

- [x] **Step 7: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_resolucao.py -q`
Esperado: PASSA (14 testes)

- [x] **Step 8: prova por mutação — o builtin deixa de ser excluído**

Apague a linha `if alvo in builtins or primeiro in builtins: return True` **inteira** (as duas
checagens de uma vez; tirar só uma delas deixa o teste verde, porque a outra ainda pega `fs`) e
rode.
Esperado: **cai** `test_builtin_e_externo_mesmo_na_linguagem_que_permite_interno`. Desfaça.

- [x] **Step 9: prova por mutação — a regra do JS vira universal**

Troque `if nome_puro_pode_ser_interno: return False` por `if False: return False` e rode.
Esperado: **cai** `test_nome_puro_NAO_e_externo_na_linguagem_que_permite_modulo_local` — que é
o teste que protege o grafo de Python. Desfaça.

- [x] **Step 10: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **237 passam**

---
### Task 7: o leitor genérico de configuração

**Arquivos:**
- Alterar: `scripts/lib/resolucao.py` (acrescentar `ler_vocabulario`)
- Teste: `tests/test_resolucao.py`

**Depende de:** Task 6

**Contrato que esta task publica:**
`ler_vocabulario(raiz: Path, configs: list[dict]) -> dict` com as chaves
`prefixos: list[tuple[str, str]]` e `raizes: list[str]`

- [x] **Step 1: escrever os testes que falham**

```python
# acrescente em tests/test_resolucao.py
import json

from lib.resolucao import ler_vocabulario

CONFIG_TS = [{'arquivo': 'tsconfig.json', 'prefixos': 'compilerOptions.paths',
              'raizes': 'compilerOptions.baseUrl'}]


def test_le_o_mapeamento_declarado_quando_a_pasta_existe(tmp_path):
    # Arrange
    (tmp_path / 'src').mkdir()
    (tmp_path / 'tsconfig.json').write_text(json.dumps(
        {'compilerOptions': {'baseUrl': 'src', 'paths': {'@/*': ['src/*']}}}))
    # Act
    vocab = ler_vocabulario(tmp_path, CONFIG_TS)
    # Assert
    assert ('@', 'src') in vocab['prefixos']
    assert vocab['raizes'] == ['src']


def test_mapeamento_que_aponta_para_pasta_inexistente_e_descartado(tmp_path):
    """Configuração desatualizada é comum. Confiar nela cegamente produz exatamente
    o que esta skill não pode produzir: aresta errada. Descartado em silêncio, o
    import cai na etapa 3 e resolve pelos arquivos que existem."""
    # Arrange
    (tmp_path / 'tsconfig.json').write_text(json.dumps(
        {'compilerOptions': {'baseUrl': 'pasta-que-nao-existe',
                             'paths': {'@/*': ['src-antigo/*']}}}))
    # Act
    vocab = ler_vocabulario(tmp_path, CONFIG_TS)
    # Assert
    assert vocab == {'prefixos': [], 'raizes': []}


def test_o_leitor_e_o_mesmo_para_psr4(tmp_path):
    """O leitor não sabe o que é um tsconfig nem um composer: ele recebe o caminho
    da chave e o aplica. É isso que mantém o resolvedor sem nome de linguagem."""
    # Arrange
    (tmp_path / 'app').mkdir()
    (tmp_path / 'composer.json').write_text(json.dumps(
        {'autoload': {'psr-4': {'App\\': 'app'}}}))
    # Act
    vocab = ler_vocabulario(tmp_path, [{'arquivo': 'composer.json',
                                        'prefixos': 'autoload.psr-4'}])
    # Assert
    assert ('App', 'app') in vocab['prefixos']
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_resolucao.py -q`
Esperado: FALHA com `ImportError: cannot import name 'ler_vocabulario'`

- [x] **Step 3: escrever `ler_vocabulario`**

```python
# acrescente em scripts/lib/resolucao.py
import json
from pathlib import Path


def _descer(dados, caminho_da_chave: str):
    """`compilerOptions.paths` -> dados['compilerOptions']['paths']."""
    for chave in caminho_da_chave.split('.'):
        if not isinstance(dados, dict) or chave not in dados:
            return None
        dados = dados[chave]
    return dados


def ler_vocabulario(raiz, configs: list) -> dict:
    """O mapeamento declarado pelo projeto, CONFERIDO contra o disco.

    O `configs` vem do módulo da linguagem e diz só ONDE as coisas moram
    (`{'arquivo': 'composer.json', 'prefixos': 'autoload.psr-4'}`). Sem essa
    indireção o resolvedor precisaria das strings `composer.json`, `tsconfig.json` e
    `psr-4`, e a restrição "nenhum nome de linguagem no resolvedor" cairia.

    Atalho, nunca verdade: o que aponta para pasta inexistente é descartado e o
    import volta a resolver pelos arquivos que existem.
    """
    raiz = Path(raiz)
    prefixos, raizes = [], []
    for config in configs:
        arquivo = raiz / config['arquivo']
        try:
            dados = json.loads(arquivo.read_text('utf-8', 'replace'))
        except (json.JSONDecodeError, OSError):
            continue
        mapa = _descer(dados, config.get('prefixos', '')) or {}
        if isinstance(mapa, dict):
            for prefixo, destino in mapa.items():
                alvos = destino if isinstance(destino, list) else [destino]
                for alvo in alvos:
                    if not isinstance(alvo, str):
                        continue
                    base = alvo.rstrip('/*').rstrip('/').replace('\\', '/')
                    if base and (raiz / base).is_dir():
                        prefixos.append((prefixo.rstrip('\\/*'), base))
        base_url = _descer(dados, config.get('raizes', '')) if config.get('raizes') else None
        if isinstance(base_url, str) and (raiz / base_url).is_dir():
            raizes.append(base_url.rstrip('/'))
    return {'prefixos': sorted(set(prefixos)), 'raizes': sorted(set(raizes))}
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_resolucao.py -q`
Esperado: PASSA (17 testes)

- [x] **Step 5: prova por mutação — a configuração deixa de ser conferida**

Troque `if base and (raiz / base).is_dir():` por `if base:` e rode.
Esperado: **cai** `test_mapeamento_que_aponta_para_pasta_inexistente_e_descartado`. Desfaça.

- [x] **Step 6: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **240 passam**

---


### Task 8: a segunda passada — base provada pelos arquivos

**Arquivos:**
- Alterar: `scripts/lib/resolucao.py` (acrescentar `base_de`, `bases_provadas`, `desempatar`)
- Teste: `tests/test_resolucao.py`

**Depende de:** Task 7

**Contrato que esta task publica:**
`base_de(destino: str, sufixo: str) -> str` ·
`bases_provadas(resolvidos: list[tuple[str, str, str]]) -> dict[str, set[str]]` ·
`desempatar(prefixo, resto, candidatos_, sufixo, provadas, indice, extensoes, arquivo_de_pasta) -> str | None` ·
`MIN_PROVAS = 5`

O **sufixo que casou** entra na assinatura, e não é detalhe: sem ele o desempate teria de usar
`destino.startswith(base + '/')`, que é o que a primeira versão deste plano fazia — e aí os dois
candidatos de `@/constants` (`src/constants/…` e `src/assets/js/constants/…`) começam ambos com
`src/` e **nenhum** desempata. Pior, `startswith` é gerador de aresta errada em geral.

- [x] **Step 1: escrever os testes que falham**

```python
# acrescente em tests/test_resolucao.py
from lib.resolucao import base_de, bases_provadas, desempatar


def test_base_e_o_destino_menos_o_sufixo_que_casou():
    """Com a extensão completando o casamento, cortar pelo tamanho do alvo deixaria
    `.vue` dentro da base e ela nunca bateria com outra."""
    # Act / Assert
    assert base_de('src/components/Box.vue', 'components/Box.vue') == 'src'


def test_base_so_vale_com_cinco_provas():
    """Medido: o apelido `@Assets` tinha exatamente 5 provas. Abaixo disso entra
    ruído; acima, perde-se um apelido real. É o ÚNICO limiar do resolvedor."""
    # Arrange — (prefixo, sufixo_que_casou, destino)
    resolvidos = [('@C', f'Box{i}.vue', f'src/components/Box{i}.vue') for i in range(5)]
    resolvidos += [('@X', 'Um.vue', 'src/outro/Um.vue')]
    # Act
    provadas = bases_provadas(resolvidos)
    # Assert
    assert provadas['@C'] == {'src/components'}
    assert provadas.get('@X', set()) == set()


def test_ambiguo_resolve_quando_UM_candidato_esta_sob_base_provada():
    """Os dois candidatos começam com `src/` — `startswith` não separa nenhum. O que
    separa é a BASE: `src` para um, `src/assets/js` para o outro."""
    # Arrange
    idx = indexar(['src/area/constants.ts', 'src/assets/js/area/constants.ts'])
    # Act
    achado = desempatar('@', 'area/constants',
                        ['src/area/constants.ts', 'src/assets/js/area/constants.ts'],
                        'area/constants.ts', {'@': {'src'}}, idx, EXTS, PASTA)
    # Assert
    assert achado == 'src/area/constants.ts'


def test_ambiguo_com_dois_candidatos_sob_base_provada_nao_resolve():
    """Dois sob a mesma base provada continua sendo escolha entre iguais."""
    # Arrange
    idx = indexar(['src/a/x.ts', 'src/b/x.ts'])
    # Act
    achado = desempatar('@', 'a/x', ['src/a/x.ts', 'src/b/x.ts'], 'x.ts',
                        {'@': {'src/a', 'src/b'}}, idx, EXTS, PASTA)
    # Assert
    assert achado is None


def test_fraco_de_um_segmento_resolve_pela_base_provada():
    """`@/utils` não gerou candidato nenhum na etapa 3 — tem um segmento só. Aqui
    ele vira `base + resto`. É o apelido mais comum dos projetos Vue e Next
    medidos: sem esta regra ele cairia inteiro em `nao_resolvidos`."""
    # Arrange
    idx = indexar(['src/utils.ts', 'outro/utils.ts'])
    # Act
    achado = desempatar('@', 'utils', [], '', {'@': {'src'}}, idx, EXTS, PASTA)
    # Assert
    assert achado == 'src/utils.ts'


def test_fraco_sem_base_provada_nao_resolve():
    # Arrange
    idx = indexar(['src/utils.ts'])
    # Act / Assert
    assert desempatar('@', 'utils', [], '', {}, idx, EXTS, PASTA) is None
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_resolucao.py -q`
Esperado: FALHA com `ImportError: cannot import name 'base_de'`

- [x] **Step 3: escrever as três funções**

```python
# acrescente em scripts/lib/resolucao.py
from collections import Counter, defaultdict

MIN_PROVAS = 5      # `@Assets` tinha exatamente 5 provas no projeto medido


def base_de(destino: str, sufixo: str) -> str:
    """O destino menos o sufixo que casou: `src/components/Box.vue` - `components/Box.vue`.

    O sufixo, não o alvo do import: a extensão pode ter completado o casamento, e
    cortar pelo tamanho do alvo deixaria `.vue` dentro da base.
    """
    return destino[:len(destino) - len(sufixo)].rstrip('/')


def bases_provadas(resolvidos) -> dict:
    """Por prefixo, as pastas onde ele já foi visto cair pelo menos MIN_PROVAS vezes.

    Isto é a configuração REDESCOBERTA pelos arquivos: num projeto real saiu
    `@ -> src`, `@Component -> src/components`, `@View -> src/views` e
    `@Assets -> src/assets`, que é exatamente o que o `vue.config.js` declara — e o
    arquivo nunca foi aberto.
    """
    contagem = defaultdict(Counter)
    for prefixo, sufixo, destino in resolvidos:
        contagem[prefixo][base_de(destino, sufixo)] += 1
    return {prefixo: {base for base, n in c.items() if n >= MIN_PROVAS}
            for prefixo, c in contagem.items()}


def desempatar(prefixo, resto, candidatos_, sufixo, provadas, indice, extensoes,
               arquivo_de_pasta):
    """A segunda passada, para os dois tipos de pendência que a etapa 3 deixou.

    Roda UMA vez e usa somente evidência da primeira passada: aresta criada aqui não
    realimenta prova, senão haveria iteração, com convergência e determinismo em
    aberto.

    - **ambíguo** (vários candidatos): resolve se EXATAMENTE UM tem a base provada.
      Comparar por base, e não por `startswith`, é o que separa
      `src/constants/index.ts` de `src/assets/js/constants/index.ts` — os dois
      começam com `src/`, e só a base distingue.
    - **fraco** (um segmento, sem candidato): monta `base + resto` e resolve se esse
      arquivo existe e é único.
    """
    bases = provadas.get(prefixo, set())
    if not bases:
        return None
    if candidatos_:
        sob = [c for c in candidatos_ if base_de(c, sufixo) in bases]
        return sob[0] if len(sob) == 1 else None
    achados = set()
    for base in bases:
        for tentativa in _tentativas(f'{base}/{resto}', extensoes, arquivo_de_pasta):
            encontrados = indice.get(tentativa)
            if encontrados:
                achados |= encontrados
                break
    return next(iter(achados)) if len(achados) == 1 else None
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_resolucao.py -q`
Esperado: PASSA (23 testes)

- [x] **Step 5: prova por mutação — base com 4 provas passa a valer**

Troque `MIN_PROVAS = 5` por `MIN_PROVAS = 1` e rode.
Esperado: **cai** `test_base_so_vale_com_cinco_provas`. Desfaça.

- [x] **Step 6: prova por mutação — o desempate volta a ser por `startswith`**

Troque `if base_de(c, sufixo) in bases` por `if any(c.startswith(b + '/') for b in bases)`
e rode.
Esperado: **cai** `test_ambiguo_resolve_quando_UM_candidato_esta_sob_base_provada`. Desfaça.

- [x] **Step 7: prova por mutação — dois candidatos resolvem pelo primeiro**

Troque `return sob[0] if len(sob) == 1 else None` por `return sob[0] if sob else None` e rode.
Esperado: **cai** `test_ambiguo_com_dois_candidatos_sob_base_provada_nao_resolve`. Desfaça.

- [x] **Step 8: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **246 passam**

---

### Task 9: o orquestrador, parte 1 — despacho por extensão, relativo e externo

**Arquivos:**
- Alterar: `scripts/lib/imports.py` (reescrita do `grafo`)
- Alterar: `scripts/varrer.py:78` (a chamada passa a levar a árvore)
- Teste: `tests/test_imports.py`

**Depende de:** Task 8

**Contrato que esta task publica:**
`grafo(raiz, stacks: list, arvore: list, area: str | None = None) -> dict` com as chaves
`arestas` (cada uma `{de, para, origem}`), `indisponivel` e `resolucao`. O parâmetro `stacks`
fica na assinatura **sem uso no corpo**, para não quebrar quem chama; a Task 11 decide se sai.

**A rede de segurança desta task:** os quatro testes de Python que já existem em
`tests/test_imports.py` **não são alterados**. Eles são a prova de que a migração do extrator
não mudou o resultado — e foi exatamente neles que o revisor do plano pegou a regressão.

- [x] **Step 1: ler os testes de Python que já existem**

```bash
sed -n '1,60p' tests/test_imports.py
```
São quatro, e todos passam hoje. Nenhum step desta task os altera; se algum cair, **o conserto
é no código**, não no teste.

- [x] **Step 2: escrever os testes novos, que falham**

```python
# acrescente em tests/test_imports.py
from lib.arvore import varrer as varrer_arvore


def arvore_de(raiz):
    return varrer_arvore(raiz)


def test_despacha_por_EXTENSAO_e_nao_pela_stack_detectada(tmp_path):
    """O `stacks.py` registra que a regra por stack deixou 210 arquivos Python nem
    parseados nem declarados como lacuna, e a detecção por extensão tem piso de 5
    arquivos. Com três extratores isso volta: dois arquivos `.ts` num projeto PHP
    sumiriam em silêncio."""
    # Arrange — projeto PHP com DOIS arquivos .ts, abaixo do piso de stack
    (tmp_path / 'composer.json').write_text('{"autoload":{"psr-4":{"App\\\\":"app"}}}')
    (tmp_path / 'app' / 'Dominio').mkdir(parents=True)
    (tmp_path / 'app' / 'Dominio' / 'A.php').write_text(
        '<?php\nnamespace App\\Dominio;\nuse App\\Dominio\\B;\n')
    (tmp_path / 'app' / 'Dominio' / 'B.php').write_text(
        '<?php\nnamespace App\\Dominio;\nclass B {}\n')
    (tmp_path / 'util.ts').write_text("import { x } from './outro'\n")
    (tmp_path / 'outro.ts').write_text('export const x = 1\n')
    # Act
    g = grafo(tmp_path, [], arvore_de(tmp_path))
    # Assert — o `use` casa pelo sufixo `Dominio/B`, sem o primeiro segmento
    assert {'de': 'app/Dominio/A.php', 'para': 'app/Dominio/B.php',
            'origem': 'sufixo_unico'} in g['arestas']
    assert {'de': 'util.ts', 'para': 'outro.ts', 'origem': 'relativo'} in g['arestas']


def test_extensao_de_CODIGO_sem_extrator_vira_lacuna_com_motivo(tmp_path):
    """Silêncio se lê como 'nada depende de nada'. E não há piso de quantidade aqui:
    o piso é justamente o defeito que o despacho por extensão veio consertar. Quem
    filtra é a mesma pergunta que o documento já usa — isto é código?"""
    # Arrange — DOIS arquivos .go, bem abaixo de qualquer piso
    (tmp_path / 'main.go').write_text('package main\n')
    (tmp_path / 'outro.go').write_text('package main\n')
    (tmp_path / 'LEIAME.md').write_text('# doc\n')
    # Act
    g = grafo(tmp_path, [], arvore_de(tmp_path))
    # Assert
    motivos = {i['stack']: i['motivo'] for i in g['indisponivel']}
    assert '.go' in motivos
    assert 'resolvedor' in motivos['.go']
    assert '.md' not in motivos, 'markdown não é código: declarar lacuna dele é ruído'


def test_conta_relativo_externo_e_pendurado(tmp_path):
    """O percentual depende de qual balde recebe cada import. No projeto medido a
    diferença entre duas rotulagens plausíveis era 85,5% e 75,7% — e o veredito
    sairia da rotulagem, não do resolvedor."""
    # Arrange
    (tmp_path / 'package.json').write_text('{"dependencies":{"vue":"^3"}}')
    (tmp_path / 'a.ts').write_text(
        "import x from './b'\nimport Vue from 'vue'\nimport y from './sumiu'\n")
    (tmp_path / 'b.ts').write_text('export default 1\n')
    # Act
    r = grafo(tmp_path, [], arvore_de(tmp_path))['resolucao']['js']
    # Assert
    assert r['relativos'] == 1
    assert r['externos'] == 1
    assert r['pendurados'] == 1


def test_a_contagem_e_por_LINGUAGEM_e_nao_por_extensao(tmp_path):
    """Um projeto Vue tem `.ts`, `.js` e `.vue`, e contar por extensão daria três
    blocos no documento e um piso de 70% calculado em cima de um terço dos dados —
    um `vite.config.js` solto viraria um bloco 'não medido' próprio."""
    # Arrange
    (tmp_path / 'a.vue').write_text("<script>import x from './b'</script>\n")
    (tmp_path / 'b.ts').write_text('export default 1\n')
    # Act
    chaves = set(grafo(tmp_path, [], arvore_de(tmp_path))['resolucao'])
    # Assert
    assert chaves == {'js'}
```

- [x] **Step 3: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_imports.py -q`
Esperado: FALHA com `TypeError: grafo() takes 2 positional arguments but 3 were given`

- [x] **Step 4: reescrever o `grafo` — a parte que esta task cobre**

Substitua o corpo de `scripts/lib/imports.py` abaixo do docstring do módulo por:

```python
from collections import defaultdict
from pathlib import Path

from lib import resolucao, stacks as mod_stacks
from lib.arvore import eh_codigo, linguagem_de
from lib.linguagens import js, php, python

# O despacho é por EXTENSÃO, não por stack detectada. A regra por stack já deixou
# 210 arquivos Python nem parseados nem declarados como lacuna, e a detecção por
# extensão do `stacks.py` tem piso de MIN_ARQUIVOS = 5: dois arquivos `.ts` num
# projeto PHP sumiriam em silêncio. Além disso `node` é uma stack só para cinco
# extensões, então o nome dela não identificaria o extrator de qualquer forma.
MODULOS = {'python': python, 'js': js, 'php': php}
POR_EXTENSAO = {ext: nome for nome, mod in MODULOS.items() for ext in mod.EXTENSOES}

TETO_EXEMPLOS = 5       # com teto e ordem, porque o inventory.json tem que dar diff

VAZIO = {'relativos': 0, 'externos': 0, 'sufixo_unico': 0, 'base_provada': 0,
         'config_conferida': 0, 'ambiguos': 0, 'pendurados': 0, 'nao_resolvidos': 0}


def _declarados_de(caminho: str, por_manifesto: dict) -> set:
    """As dependências do manifesto ANCESTRAL MAIS PRÓXIMO do arquivo.

    Não a união de todos: num monorepo, a união torna o falso-externo mais provável
    — e falso-externo infla a taxa escondendo aresta interna.
    """
    melhor, nomes = -1, set()
    for manifesto, declarados in por_manifesto.items():
        pasta = str(Path(manifesto).parent)
        pasta = '' if pasta == '.' else pasta + '/'
        if caminho.startswith(pasta) and len(pasta) > melhor:
            melhor, nomes = len(pasta), declarados
    return nomes


def grafo(raiz, stacks: list, arvore: list, area: str | None = None) -> dict:
    """Arestas de import do que deu para resolver, e a contagem do que não deu.

    `stacks` continua na assinatura para não quebrar quem chama, e não é usado: o
    despacho é por extensão.

    A árvore recebida é a do projeto INTEIRO, mesmo numa rodada com `--area`: um
    import que sai da área não pode virar `nao_resolvidos` e derrubar a taxa sem
    nada estar errado.
    """
    raiz = Path(raiz)
    por_manifesto = mod_stacks.dependencias_declaradas(raiz)
    caminhos = [i['caminho'] for i in arvore if not i['gerado']]

    # agrupado por LINGUAGEM, não por extensão: um projeto Vue tem `.ts`, `.js` e
    # `.vue`, e três blocos no documento seriam três pisos de 70% sobre um terço
    # dos dados cada
    por_linguagem, sem_extrator = defaultdict(list), defaultdict(list)
    for caminho in caminhos:
        extensao = Path(caminho).suffix.lower()
        nome = POR_EXTENSAO.get(extensao)
        if nome:
            por_linguagem[nome].append(caminho)
        elif eh_codigo(linguagem_de(Path(caminho))):
            sem_extrator[extensao].append(caminho)

    arestas, indisponivel, contagem = [], [], {}

    for extensao, arquivos in sorted(sem_extrator.items()):
        indisponivel.append({
            'stack': extensao,
            'motivo': f'{len(arquivos)} arquivo(s) {extensao}, e esta versão não tem '
                      f'resolvedor de import para eles; isto NÃO significa que nada '
                      f'depende de nada'})

    for nome, arquivos in sorted(por_linguagem.items()):
        modulo = MODULOS[nome]
        indice = resolucao.indexar(
            [c for c in caminhos if Path(c).suffix.lower() in modulo.EXTENSOES])
        vocab = resolucao.ler_vocabulario(raiz, modulo.CONFIGS)
        cont = dict(VAZIO)

        for caminho in arquivos:
            try:
                texto = (raiz / caminho).read_text('utf-8', 'replace')
            except OSError:
                continue
            declarados = _declarados_de(caminho, por_manifesto)
            for alvo in modulo.extrair(texto):
                classe = modulo.classificar(alvo)
                if classe == 'relativo':
                    destino = resolucao.resolver_relativo(
                        caminho, alvo, indice, modulo.EXTENSOES, modulo.ARQUIVO_DE_PASTA)
                    if destino:
                        cont['relativos'] += 1
                        arestas.append({'de': caminho, 'para': destino,
                                        'origem': 'relativo'})
                    else:
                        cont['pendurados'] += 1
                    continue
                if resolucao.eh_externo(alvo, classe, modulo.BUILTINS, declarados,
                                        vocab['raizes'],
                                        modulo.NOME_PURO_PODE_SER_INTERNO):
                    cont['externos'] += 1
                    continue
                # a etapa 3 e a segunda passada entram na Task 10
                cont['nao_resolvidos'] += 1
                # (na Task 10 isto vira: tenta o índice; e, para a linguagem que
                # permite nome puro interno, o que NÃO casou é `externos`, não
                # `nao_resolvidos` — `import json` não é falha de resolução)

        cont['exemplos_nao_resolvidos'] = []
        contagem[nome] = cont

    if not arestas and not indisponivel and not contagem:
        indisponivel.append({
            'stack': '(nenhuma)',
            'motivo': 'nenhum arquivo de linguagem reconhecida foi encontrado, então '
                      'não houve o que resolver; isto NÃO significa que nada depende '
                      'de nada'})

    return {'arestas': sorted(arestas, key=lambda a: (a['de'], a['para'], a['origem'])),
            'indisponivel': sorted(indisponivel, key=lambda i: i['stack']),
            'resolucao': contagem}
```

- [x] **Step 5: ligar o `varrer.py`**

Em `scripts/varrer.py`, troque a linha 78 por:

```python
        'imports': imports.grafo(projeto, componentes, todos, area=area),
```

A árvore completa (`todos`), não a recortada.

- [x] **Step 6: rodar os testes de import e conferir o Python**

Rode: `.venv/bin/python -m pytest tests/test_imports.py -q`
Esperado: os quatro testes de Python **passam sem alteração**. Se algum cair, pare: é a
regressão que esta task existe para impedir, e o conserto é no código.

Dois deles dependem da etapa 3, que só chega na Task 10 — se
`test_resolve_import_de_modulo_local` falhar por falta de aresta, confirme que a causa é essa
(`from pedido import Pedido` é `nome_puro` e Python o deixa seguir) e **registre em "Ajustes"**
que ele volta ao verde na Task 10, step 5.

- [x] **Step 7: prova por mutação — o despacho volta a ter piso de quantidade**

Em `sem_extrator`, envolva o `indisponivel.append` com
`if len(arquivos) >= mod_stacks.MIN_ARQUIVOS:` e rode.
Esperado: **cai** `test_extensao_de_CODIGO_sem_extrator_vira_lacuna_com_motivo`. Desfaça.

- [x] **Step 8: prova por mutação — a contagem volta a ser por extensão**

Troque `por_linguagem[nome].append(caminho)` por `por_linguagem[extensao].append(caminho)` e
rode.
Esperado: **cai** `test_a_contagem_e_por_LINGUAGEM_e_nao_por_extensao`. Desfaça.

---

### Task 10: o orquestrador, parte 2 — sufixo, base provada e configuração

**Arquivos:**
- Alterar: `scripts/lib/imports.py` (o laço por import, dentro do `grafo`)
- Teste: `tests/test_imports.py`

**Depende de:** Task 9

- [x] **Step 1: escrever os testes que falham**

```python
# acrescente em tests/test_imports.py


def test_resolve_pelo_sufixo_e_conta_o_balde(tmp_path):
    # Arrange
    (tmp_path / 'src' / 'components').mkdir(parents=True)
    (tmp_path / 'src' / 'components' / 'Box.vue').write_text('<template/>\n')
    (tmp_path / 'src' / 'tela.ts').write_text("import B from '@C/components/Box.vue'\n")
    # Act
    g = grafo(tmp_path, [], arvore_de(tmp_path))
    # Assert
    assert {'de': 'src/tela.ts', 'para': 'src/components/Box.vue',
            'origem': 'sufixo_unico'} in g['arestas']
    assert g['resolucao']['js']['sufixo_unico'] == 1


def test_a_base_provada_desempata_na_segunda_passada(tmp_path):
    """Cinco provas com o mesmo prefixo provam a base; aí o ambíguo resolve. É o
    mecanismo que, medido num projeto real, fechou 56 de 56 ambíguos sem abrir o
    `vue.config.js`."""
    # Arrange — cinco imports `@/area/mN` resolvem sozinhos sob `src`
    (tmp_path / 'src' / 'area').mkdir(parents=True)
    (tmp_path / 'outro' / 'area').mkdir(parents=True)
    for i in range(5):
        (tmp_path / 'src' / 'area' / f'm{i}.ts').write_text('export default 1\n')
    # o ambíguo: existe em `src/area` e em `outro/area`
    (tmp_path / 'src' / 'area' / 'dois.ts').write_text('export default 1\n')
    (tmp_path / 'outro' / 'area' / 'dois.ts').write_text('export default 1\n')
    (tmp_path / 'src' / 'tela.ts').write_text(
        ''.join(f"import m{i} from '@/area/m{i}'\n" for i in range(5))
        + "import d from '@/area/dois'\n")
    # Act
    g = grafo(tmp_path, [], arvore_de(tmp_path))
    # Assert
    assert {'de': 'src/tela.ts', 'para': 'src/area/dois.ts',
            'origem': 'base_provada'} in g['arestas']


def test_psr4_conferido_resolve_e_carrega_a_procedencia(tmp_path):
    """O PSR-4 é atalho, e é ele que leva o PHP aos 95%: `App\\X\\Y` -> `app/X/Y.php`
    por substituição de prefixo. Só vale depois de conferido contra o disco."""
    # Arrange
    (tmp_path / 'composer.json').write_text('{"autoload":{"psr-4":{"App\\\\":"app"}}}')
    (tmp_path / 'app' / 'Dominio').mkdir(parents=True)
    (tmp_path / 'app' / 'Dominio' / 'Pedido.php').write_text('<?php\nclass Pedido {}\n')
    (tmp_path / 'app' / 'Servico.php').write_text(
        '<?php\nuse App\\Dominio\\Pedido;\n')
    # Act
    g = grafo(tmp_path, [], arvore_de(tmp_path))
    # Assert
    assert {'de': 'app/Servico.php', 'para': 'app/Dominio/Pedido.php',
            'origem': 'config_conferida'} in g['arestas']
    assert g['resolucao']['php']['config_conferida'] == 1


def test_nome_puro_que_nao_casa_no_indice_e_externo_e_nao_falha(tmp_path):
    """`import json` não é falha de resolução: é a stdlib. Na linguagem que permite
    nome puro interno, quem decide é o índice — o que não casou com arquivo do
    projeto é externo. Contá-lo como não resolvido levaria a taxa do Python a ~28%
    (86 de 119 alvos desta skill são stdlib de um segmento) e jogaria a seção
    abaixo do piso, regredindo a v0.2.0 pela CONTAGEM, com as arestas certas."""
    # Arrange
    (tmp_path / 'a.py').write_text('import json\nfrom b import coisa\n')
    (tmp_path / 'b.py').write_text('coisa = 1\n')
    # Act
    r = grafo(tmp_path, [], arvore_de(tmp_path))['resolucao']['python']
    # Assert
    assert r['externos'] == 1, 'json é externo'
    assert r['nao_resolvidos'] == 0


def test_exemplos_do_que_nao_resolveu_tem_teto_e_ordem(tmp_path):
    """Com teto e ordem lexicográfica, porque o `inventory.json` tem que dar diff."""
    # Arrange
    (tmp_path / 'a.ts').write_text(
        ''.join(f"import x from '@X/sumiu{i}/fundo'\n" for i in range(9)))
    # Act
    exemplos = grafo(tmp_path, [], arvore_de(tmp_path))['resolucao']['js'][
        'exemplos_nao_resolvidos']
    # Assert
    assert len(exemplos) == 5
    assert exemplos == sorted(exemplos)
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_imports.py -q`
Esperado: FALHA — não há aresta de sufixo nem de configuração

- [x] **Step 3: trocar o fim do laço por import**

No `grafo`, troque a linha `cont['nao_resolvidos'] += 1` (e o comentário acima dela) por:

```python
                prefixo, _, resto = alvo.partition('/')
                # a configuração declarada é ATALHO: tentada primeiro porque é exata
                # quando existe, e já vem conferida contra o disco pelo
                # `ler_vocabulario` — o que apontava para pasta inexistente foi
                # descartado lá
                destino = None
                for declarado, base in vocab['prefixos']:
                    if alvo == declarado or alvo.startswith(declarado + '/'):
                        resto_do_prefixo = alvo[len(declarado):].lstrip('/')
                        destino = resolucao.resolver_relativo(
                            f'{base}/x', f'./{resto_do_prefixo}', indice,
                            modulo.EXTENSOES, modulo.ARQUIVO_DE_PASTA)
                        if destino:
                            break
                if destino:
                    cont['config_conferida'] += 1
                    arestas.append({'de': caminho, 'para': destino,
                                    'origem': 'config_conferida'})
                    continue
                # a string INTEIRA antes da string sem o primeiro segmento: em
                # Python `lib/config` casa inteiro, e em PHP `App/Dominio/X` só casa
                # sem o `App`, porque a pasta é `app` minúscula
                for tentativa in (alvo, resto):
                    if not tentativa:
                        continue
                    achados, sufixo = resolucao.candidatos(
                        tentativa, indice, modulo.EXTENSOES, modulo.ARQUIVO_DE_PASTA)
                    if achados:
                        break
                if len(achados) == 1:
                    cont['sufixo_unico'] += 1
                    arestas.append({'de': caminho, 'para': achados[0],
                                    'origem': 'sufixo_unico'})
                    resolvidos.append((prefixo, sufixo, achados[0]))
                elif not achados and classe == 'nome_puro' \
                        and modulo.NOME_PURO_PODE_SER_INTERNO:
                    # `import json` não casou com arquivo nenhum do projeto: é
                    # externo, não falha de resolução. Na linguagem que permite nome
                    # puro interno, QUEM DECIDE É O ÍNDICE — e contá-lo como não
                    # resolvido derrubaria a taxa do Python para ~28% (medido: 86 de
                    # 119 alvos desta skill são stdlib de um segmento), jogando a
                    # seção abaixo do piso de 70% e regredindo a v0.2.0 pela
                    # CONTAGEM, com as arestas todas certas.
                    cont['externos'] += 1
                else:
                    pendentes.append((caminho, prefixo, resto or alvo, achados, sufixo))
```

E, logo antes do laço `for caminho in arquivos:`, acrescente:

```python
        resolvidos, pendentes, nao_resolvidos = [], [], []
```

E, logo depois desse laço (ainda dentro do laço por linguagem), acrescente a segunda passada:

```python
        provadas = resolucao.bases_provadas(resolvidos)
        for caminho, prefixo, resto, achados, sufixo in pendentes:
            destino = resolucao.desempatar(prefixo, resto, achados, sufixo, provadas,
                                           indice, modulo.EXTENSOES,
                                           modulo.ARQUIVO_DE_PASTA)
            if destino:
                cont['base_provada'] += 1
                arestas.append({'de': caminho, 'para': destino,
                                'origem': 'base_provada'})
            elif achados:
                cont['ambiguos'] += 1
                nao_resolvidos.append(f'{caminho}: {prefixo}/{resto}')
            else:
                cont['nao_resolvidos'] += 1
                nao_resolvidos.append(f'{caminho}: {prefixo}/{resto}')
```

e troque `cont['exemplos_nao_resolvidos'] = []` por:

```python
        cont['exemplos_nao_resolvidos'] = sorted(nao_resolvidos)[:TETO_EXEMPLOS]
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_imports.py -q`
Esperado: PASSA, incluindo os quatro testes de Python

- [x] **Step 5: conferir que o grafo de Python voltou inteiro**

```bash
.venv/bin/python -m pytest tests/test_imports.py -q
.venv/bin/python scripts/varrer.py --projeto /var/www/ai-marketplace --out /tmp/d-self
.venv/bin/python -c "
import json; i=json.load(open('/tmp/d-self/inventory.json'))['imports']
c=i['resolucao'].get('python', {})
res=c.get('relativos',0)+c.get('sufixo_unico',0)+c.get('base_provada',0)+c.get('config_conferida',0)
den=res+c.get('ambiguos',0)+c.get('pendurados',0)+c.get('nao_resolvidos',0)
print('arestas:', len(i['arestas']), '· python:', res, 'de', den)"
```
Esperado: **centenas de arestas** e a taxa de Python **acima de 70%**. Este repositório tem
210 arquivos `.py`; se a taxa cair abaixo do piso, a v0.2.0 regrediu e o plano para aqui.

- [x] **Step 5b: prova por mutação — nome puro que não casa volta a ser falha**

Troque `and modulo.NOME_PURO_PODE_SER_INTERNO:` por `and False:` e rode.
Esperado: **cai** `test_nome_puro_que_nao_casa_no_indice_e_externo_e_nao_falha`. Desfaça.

- [x] **Step 6: prova por mutação — a configuração deixa de ser tentada**

Troque `for declarado, base in vocab['prefixos']:` por `for declarado, base in []:` e rode.
Esperado: **cai** `test_psr4_conferido_resolve_e_carrega_a_procedencia`. Desfaça.

- [x] **Step 7: prova por mutação — a string inteira deixa de ser tentada primeiro**

Troque `for tentativa in (alvo, resto):` por `for tentativa in (resto,):` e rode.
Esperado: **cai** um dos testes de Python (`from lib.config import ...` deixa de resolver).
Desfaça.

- [x] **Step 8: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **254 passam**

---

### Task 11: o orquestrador, parte 3 — recorte por área e a medição de aceitação

**Arquivos:**
- Alterar: `scripts/lib/imports.py` (o recorte, no fim do `grafo`)
- Teste: `tests/test_imports.py`

**Depende de:** Task 10

- [x] **Step 1: escrever os testes que falham**

```python
# acrescente em tests/test_imports.py


def test_com_area_vale_a_aresta_com_UMA_PONTA_dentro(tmp_path):
    """É a terceira regra de recorte que a skill já usa em história e menções: o par
    que cruza a fronteira é o valor da seção ('para mexer aqui você mexe lá fora')."""
    # Arrange
    for pasta in ('dentro', 'fora'):
        (tmp_path / pasta).mkdir()
    (tmp_path / 'dentro' / 'a.ts').write_text("import x from '../fora/b'\n")
    (tmp_path / 'fora' / 'b.ts').write_text("import y from './c'\n")
    (tmp_path / 'fora' / 'c.ts').write_text('export const y = 1\n')
    # Act
    g = grafo(tmp_path, [], arvore_de(tmp_path), area='dentro')
    # Assert
    assert {'de': 'dentro/a.ts', 'para': 'fora/b.ts', 'origem': 'relativo'} in g['arestas']
    assert all(a['de'].startswith('dentro/') or a['para'].startswith('dentro/')
               for a in g['arestas'])


def test_as_arestas_saem_ordenadas(tmp_path):
    """O laço antigo iterava um `set` de strings, cuja ordem varia por processo, e
    concatenava sem reordenar.

    A fixture precisa que a ordem de INSERÇÃO difira da ordenada, senão o teste
    passa sem o `sorted` — foi o defeito da primeira versão: `z.ts` é varrido depois
    de `a.ts`, mas as duas linguagens inserem intercaladas."""
    # Arrange — o `.py` é varrido depois do `.ts`, e ordena antes dele
    (tmp_path / 'z.ts').write_text("import a from './a'\n")
    (tmp_path / 'a.ts').write_text('export default 1\n')
    (tmp_path / 'alfa.py').write_text('from beta import x\n')
    (tmp_path / 'beta.py').write_text('x = 1\n')
    # Act
    arestas = grafo(tmp_path, [], arvore_de(tmp_path))['arestas']
    # Assert
    assert [a['de'] for a in arestas] == ['alfa.py', 'z.ts']
```

- [x] **Step 2: rodar, implementar o recorte e confirmar**

No fim do `grafo`, logo antes do `return`, acrescente:

```python
    if area:
        # UMA ponta dentro, não as duas: o par que cruza a fronteira é o valor da
        # seção — "para mexer aqui você mexe lá fora".
        prefixo_da_area = area.rstrip('/') + '/'
        arestas = [a for a in arestas
                   if a['de'].startswith(prefixo_da_area)
                   or a['para'].startswith(prefixo_da_area)]
```

Rode: `.venv/bin/python -m pytest tests/test_imports.py -q`
Esperado: PASSA

- [x] **Step 3: medir a taxa nos projetos reais — a restrição de aceitação**

```bash
for p in <raiz-do-monorepo> <raiz-do-projeto-php> <raiz-do-projeto-next>; do
  .venv/bin/python scripts/varrer.py --projeto "$p" --out /tmp/d-medir >/dev/null
  .venv/bin/python -c "
import json,sys; r=json.load(open('/tmp/d-medir/inventory.json'))['imports']['resolucao']
for ling,c in sorted(r.items()):
    res=c['relativos']+c['sufixo_unico']+c['base_provada']+c['config_conferida']
    den=res+c['ambiguos']+c['pendurados']+c['nao_resolvidos']
    print(f\"  {ling}: {res}/{den}\" + (f' = {res*100//den}%' if den else ' = não medido'))"
done
```
Esperado: **php ≥ 95%** e **js ≥ 95%**. Registre os números em "Ajustes durante a execução".
**Abaixo disso, pare** — a meta do spec não foi atingida e a decisão é do dono.

- [x] **Step 4: prova por mutação — o recorte passa a exigir as DUAS pontas**

Troque o `or` do filtro por `and` e rode.
Esperado: **cai** `test_com_area_vale_a_aresta_com_UMA_PONTA_dentro`. Desfaça.

- [x] **Step 5: prova por mutação — a ordenação final some**

Troque `sorted(arestas, key=...)` por `arestas` no `return` e rode.
Esperado: **cai** `test_as_arestas_saem_ordenadas`. Desfaça.

- [x] **Step 6: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **256 passam**

---

### Task 12: tirar do índice o que fabrica ambiguidade

**Arquivos:**
- Alterar: `scripts/lib/arvore.py:43-44` (a tupla `GERADOS`)
- Teste: `tests/test_arvore.py`

**Depende de:** Task 11

- [x] **Step 1: escrever o teste que falha**

```python
# acrescente em tests/test_arvore.py


def test_declaracao_de_tipo_e_instantaneo_contam_como_gerados(tmp_path):
    """`.d.ts` e `.stories.*` são fabricantes clássicos de sufixo duplicado: cada
    `Botao.d.ts` ao lado de `Botao.ts` cria uma ambiguidade artificial que derruba a
    taxa de resolução sem que nada esteja errado."""
    # Arrange
    (tmp_path / 'Botao.ts').write_text('export const x = 1')
    (tmp_path / 'Botao.d.ts').write_text('export declare const x: number')
    (tmp_path / 'Lista.stories.tsx').write_text('export default {}')
    # Act
    por_caminho = {i['caminho']: i['gerado'] for i in varrer(tmp_path)}
    # Assert
    assert por_caminho['Botao.ts'] is False
    assert por_caminho['Botao.d.ts'] is True
    assert por_caminho['Lista.stories.tsx'] is True
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_arvore.py -q`
Esperado: FALHA — `Botao.d.ts` vem `False`

- [x] **Step 3: acrescentar os sufixos**

Em `scripts/lib/arvore.py`, troque a tupla por:

```python
# `.d.ts` e `.stories.*` não são código que alguém mantém, e são fabricantes de
# sufixo duplicado: `Botao.d.ts` ao lado de `Botao.ts` cria ambiguidade artificial
# que derruba a taxa de resolução sem nada estar errado.
GERADOS = ('.min.js', '.min.css', '.lock', '.map', '-lock.json', '.pyc', '.generated.ts',
           '.tsbuildinfo', '.snap', '.pb.go', '_pb2.py', '.d.ts',
           '.stories.ts', '.stories.tsx', '.stories.js', '.stories.jsx', '.stories.vue')
```

- [x] **Step 4: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: **257 passam**

---

### Task 13: o documento — ranking por arquivo, com piso

**Arquivos:**
- Alterar: `scripts/montar.py` (reescrita de `_dependentes`)
- Alterar: `scripts/lib/resolucao.py` (acrescentar `eh_barril`)
- Alterar: `scripts/lib/imports.py` (marcar os barris)
- Alterar: `tests/test_montar.py` (quatro testes da versão sem grafo)
- Teste: `tests/test_montar.py`

**Depende de:** Task 12

**Contrato que esta task publica:** `PISO_RESOLUCAO = 0.70` · `TETO_RANKING = 15` ·
`resolucao.eh_barril(texto: str) -> bool` · a chave `barris` no retorno do `grafo`

**Quatro testes existentes mudam de significado, e isso é decisão de escopo, não detalhe de
execução.** `test_sem_grafo_de_import_a_secao_vira_lacuna`,
`test_com_grafo_de_import_a_lista_continua`, `test_sem_lista_o_aviso_nao_se_repete` e
`test_simbolo_so_citado_em_documentacao_fica_de_fora` descrevem a seção **sem grafo**: a frase
"não foi medido nesta versão" e o filtro de símbolo citado só em documentação. Com grafo real
nos três casos, a frase deixa de existir e o filtro de símbolo também. Os steps 8 e 9 os
reescrevem — não os apagam em silêncio.

- [x] **Step 1: escrever os testes novos, que falham**

```python
# acrescente em tests/test_montar.py
from montar import _dependentes

BALDES = ('relativos', 'externos', 'sufixo_unico', 'base_provada', 'config_conferida',
          'ambiguos', 'pendurados', 'nao_resolvidos')


def contagem(**valores):
    return {**dict.fromkeys(BALDES, 0), **valores}


def inventario(arestas, resolucao, barris=()):
    return {'imports': {'arestas': arestas, 'indisponivel': [],
                        'resolucao': resolucao, 'barris': list(barris)},
            'mencoes': {}}


def test_ranking_por_arquivo_ordenado_por_quem_importa():
    """A lista de antes era por SÍMBOLO e ordenada por menções textuais — ela existia
    só por não haver grafo. Com aresta real, a pergunta 'o que mais gente importa'
    tem resposta direta e sem o ruído do casamento por palavra."""
    # Arrange
    arestas = [{'de': f'src/t{i}.ts', 'para': 'src/servico.ts', 'origem': 'relativo'}
               for i in range(3)]
    arestas.append({'de': 'src/t0.ts', 'para': 'src/raro.ts', 'origem': 'relativo'})
    inv = inventario(arestas, {'js': contagem(relativos=4)})
    # Act
    linhas = '\n'.join(_dependentes(inv))
    # Assert
    assert 'src/servico.ts' in linhas
    assert linhas.index('src/servico.ts') < linhas.index('src/raro.ts')
    assert '3 arquivos importam' in linhas


def test_diz_importa_diretamente_e_nunca_alcanca():
    """'alcança' se lê como transitivo, e o desenho declara que não é."""
    # Arrange
    inv = inventario([{'de': 'a.ts', 'para': 'b.ts', 'origem': 'relativo'}],
                     {'js': contagem(relativos=1)})
    # Act / Assert
    assert 'alcança' not in '\n'.join(_dependentes(inv))


def test_abaixo_do_piso_a_linguagem_vira_lacuna_e_nao_ranking():
    """Ranking construído sobre metade do grafo tem cara de fato — é o erro que a
    v0.1.1 custou. Não basta publicar a taxa ao lado: ninguém lê uma ressalva e
    depois duvida de uma lista ordenada."""
    # Arrange — 4 de 10 resolvidos: 40%
    inv = inventario([{'de': 'a.ts', 'para': 'b.ts', 'origem': 'relativo'}],
                     {'js': contagem(relativos=4, ambiguos=3, nao_resolvidos=3)})
    # Act
    linhas = '\n'.join(_dependentes(inv))
    # Assert
    assert 'lacuna' in linhas
    assert '40%' in linhas
    assert 'b.ts' not in linhas


def test_denominador_zero_e_nao_medido_e_nunca_zero_por_cento():
    """Linguagem com extrator e nenhum import interno: 0/0 não é 0%."""
    # Arrange
    inv = inventario([], {'js': contagem()})
    # Act
    linhas = '\n'.join(_dependentes(inv))
    # Assert
    assert 'não medido' in linhas
    assert '0%' not in linhas


def test_o_texto_gerado_nao_usa_nenhuma_frase_proibida():
    """O rodapé precisa dizer que a lista não é exaustiva SEM usar as palavras que a
    skill proíbe. A primeira versão deste plano escrevia 'não é afirmação de que
    nada depende dele' — e `PROIBIDAS[0]` é exatamente `'nada depende'`. O teste da
    Task 15 reprovaria o texto que esta task acabou de escrever."""
    # Arrange
    from montar import PROIBIDAS
    inv = inventario([{'de': 'a.ts', 'para': 'b.ts', 'origem': 'relativo'}],
                     {'js': contagem(relativos=1)})
    # Act
    texto = '\n'.join(_dependentes(inv)).lower()
    # Assert
    assert not [f for f in PROIBIDAS if f in texto]
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_montar.py -q`
Esperado: FALHA — o `_dependentes` de hoje é indexado por símbolo e não lê `resolucao`

- [x] **Step 3: reescrever `_dependentes`**

Substitua a função inteira em `scripts/montar.py` por:

```python
PISO_RESOLUCAO = 0.70     # abaixo disto, ranking vira lacuna
TETO_RANKING = 15


def _taxa(c: dict):
    """(resolvidos, denominador) — ou (0, 0) quando não houve import interno.

    A fórmula escrita uma vez, porque sem ela dois leitores chegam a números
    diferentes: `externos` fica FORA dos dois lados de propósito, e é a conta mais
    delicada daqui — inflar aquele balde inflaria a taxa.
    """
    resolvidos = (c['relativos'] + c['sufixo_unico'] + c['base_provada']
                  + c['config_conferida'])
    return resolvidos, resolvidos + c['ambiguos'] + c['pendurados'] + c['nao_resolvidos']


def _dependentes(inv: dict) -> list:
    """Quem importa quem, por linguagem — ou a lacuna, quando a medição foi fraca.

    Substitui a lista por símbolo que existia antes: ela vinha de `mencoes` e casava
    PALAVRA, o que num projeto em português devolvia `banco` e `caminho` com centenas
    de menções. Com aresta real a pergunta tem resposta direta.
    """
    resolucao = inv['imports'].get('resolucao') or {}
    barris = set(inv['imports'].get('barris') or [])
    entrada = {}
    for aresta in inv['imports']['arestas']:
        entrada.setdefault(aresta['para'], set()).add(aresta['de'])

    linhas = []
    for linguagem, contagem in sorted(resolucao.items()):
        resolvidos, denominador = _taxa(contagem)
        linhas.append(f'### {linguagem}\n')
        if denominador == 0:
            linhas.append(f'Nenhum import interno em {linguagem} — '
                          f'não medido, que não é o mesmo que zero.  [lacuna]\n')
            continue
        pct = round(resolvidos * 100 / denominador)
        if resolvidos / denominador < PISO_RESOLUCAO:
            linhas.append(
                f'A resolução de import ficou em **{pct}%** ({resolvidos} de '
                f'{denominador}), abaixo do piso de {round(PISO_RESOLUCAO * 100)}%. '
                f'Um ranking sobre esse grafo teria cara de fato.\n')
            linhas.append(f'*Quem depende de quem em {linguagem} continua por '
                          f'apurar.*  [lacuna]\n')
            continue
        # o barril é um corredor, não um destino: com `export … from` no extrator,
        # todo `@/utils` resolve nele e o topo viraria "300 arquivos importam
        # index.ts" — verdadeiro, inútil, e com o arquivo que a pessoa precisa abrir
        # a dois saltos, que o não-objetivo "sem análise transitiva" proíbe seguir
        ranking = sorted(((alvo, des) for alvo, des in entrada.items()
                          if alvo not in barris),
                         key=lambda t: (-len(t[1]), t[0]))
        linhas.append(f'Resolvidos {resolvidos} de {denominador} imports '
                      f'({pct}%).  [fato]\n')
        for alvo, des in ranking[:TETO_RANKING]:
            plural = 'arquivo importa' if len(des) == 1 else 'arquivos importam'
            linhas.append(f'- {len(des)} {plural} diretamente `{alvo}`')
        if len(ranking) > TETO_RANKING:
            linhas.append(f'- … e mais {len(ranking) - TETO_RANKING}')
        linhas.append('')
    if not linhas:
        return ['*Quem depende de quem continua por apurar.*  [lacuna]']
    # a ressalva precisa dizer que a lista é parcial SEM usar as frases de
    # `PROIBIDAS` — "nada depende" é a primeira delas, e o teste da Task 15 roda a
    # lista sobre o documento montado
    linhas.append('Esta lista diz quem importa **diretamente** — não é transitiva. E ela '
                  'cobre só o que o grafo enxerga: injeção de dependência, rota como '
                  'string, reflexão e template ficam de fora, então um arquivo ausente '
                  'daqui pode ter dependentes que esta medição não alcança.')
    return linhas
```

- [x] **Step 4: rodar e conferir que os testes novos passam**

Rode: `.venv/bin/python -m pytest tests/test_montar.py -q -k "ranking or piso or denominador or proibida or diretamente"`
Esperado: PASSA

- [x] **Step 5: escrever o teste do barril, que falha**

```python
# acrescente em tests/test_montar.py
def test_arquivo_de_puro_reexport_fica_fora_do_ranking():
    """Com `export … from` no extrator e centenas de imports apelidados, todo
    `@/utils` resolve no barril."""
    # Arrange
    arestas = [{'de': f'src/t{i}.ts', 'para': 'src/index.ts', 'origem': 'relativo'}
               for i in range(9)]
    arestas += [{'de': f'src/t{i}.ts', 'para': 'src/servico.ts', 'origem': 'relativo'}
                for i in range(2)]
    inv = inventario(arestas, {'js': contagem(relativos=11)}, barris=['src/index.ts'])
    # Act
    linhas = '\n'.join(_dependentes(inv))
    # Assert
    assert 'src/index.ts' not in linhas
    assert 'src/servico.ts' in linhas
```

E em `tests/test_resolucao.py`:

```python
def test_arquivo_que_so_reexporta_e_barril():
    """O critério é estreito e escrito, senão dois critérios plausíveis dariam duas
    implementações: é barril o arquivo cujo conteúdo, fora comentário e linha em
    branco, é SÓ `export … from`."""
    # Arrange
    from lib.resolucao import eh_barril
    # Act / Assert
    assert eh_barril("export { a } from './a'\n// nota\nexport * from './b'\n")
    assert not eh_barril("export { a } from './a'\nconst x = 1\n")
    assert not eh_barril('')
```

- [x] **Step 6: escrever `eh_barril` e marcar os barris**

Em `scripts/lib/resolucao.py` (acrescente `import re` no topo, se não houver):

```python
REEXPORT = re.compile(r"""^\s*export\s[^\n]*\sfrom\s*['"]""")


def eh_barril(texto: str) -> bool:
    """Arquivo que só re-exporta não é dependência de ninguém — é um corredor.

    Sem isto, o topo do ranking vira o `index.ts`, que é verdadeiro e não ajuda: o
    arquivo que a pessoa precisa abrir está do outro lado do corredor.
    """
    uteis = [l for l in texto.split('\n')
             if l.strip() and not l.strip().startswith(('//', '/*', '*'))]
    return bool(uteis) and all(REEXPORT.match(l) for l in uteis)
```

Em `scripts/lib/imports.py`, dentro do laço por arquivo, logo depois de ler o `texto`:

```python
            if resolucao.eh_barril(texto):
                barris.append(caminho)
```

com `barris = []` antes do laço por linguagem, e `'barris': sorted(barris)` no dicionário
devolvido pelo `grafo`.

- [x] **Step 7: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_montar.py tests/test_resolucao.py -q`
Esperado: PASSA

- [x] **Step 8: reescrever os três testes que descreviam a seção sem grafo**

Em `tests/test_montar.py`, os três testes que exigem a frase *"não foi medido nesta versão"*
descreviam o comportamento de quando **não havia** resolvedor para a stack. Com o grafo real,
a lacuna passa a vir do **piso de resolução**, e a frase muda. Troque as três asserções
`assert 'não foi medido nesta versão' in guia` por:

```python
    assert 'continua por apurar' in guia
```

e a negativa `assert 'não foi medido nesta versão' not in guia` por:

```python
    assert 'continua por apurar' not in guia
```

Se algum desses testes montar um inventário sem a chave `resolucao`, acrescente
`'resolucao': {}` ao `imports` dele — é o estado de um projeto sem linguagem reconhecida, e
`_dependentes` devolve a lacuna genérica.

- [x] **Step 9: apagar o teste do símbolo citado só em documentação, com registro**

Ache o bloco em `tests/test_montar.py` e apague-o inteiro:

```python
def test_simbolo_so_citado_em_documentacao_fica_de_fora(tmp_path):
    ...
    assert 'só em documentação' in guia
```

Confira que ele sumiu:

```bash
grep -c "só em documentação" tests/test_montar.py   # esperado: 0
```

Ele testa o filtro de `mencoes`, que a reescrita removeu junto com a lista por símbolo.
**Registre em "Ajustes durante a execução"**: *"o filtro de símbolo citado só em documentação saiu com a lista por
símbolo; o ruído que ele combatia era do casamento por palavra, que o grafo real substitui."*

- [x] **Step 10: prova por mutação — o piso some**

Troque `PISO_RESOLUCAO = 0.70` por `PISO_RESOLUCAO = 0.0` e rode.
Esperado: **cai** `test_abaixo_do_piso_a_linguagem_vira_lacuna_e_nao_ranking`. Desfaça.

- [x] **Step 11: prova por mutação — denominador zero vira 0%**

Troque `if denominador == 0:` por `if False:` e rode.
Esperado: **cai** `test_denominador_zero_e_nao_medido_e_nunca_zero_por_cento` (com
`ZeroDivisionError`, que também é falha). Desfaça.

- [x] **Step 12: rodar a suíte inteira e LER o documento de um projeto real**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/varrer.py --projeto <raiz-do-monorepo> --out /tmp/d-mono
.venv/bin/python scripts/montar.py --dir /tmp/d-mono
sed -n '/O que depende do quê/,/^## /p' /tmp/d-mono/guide.md | head -50
```
Esperado: um bloco por linguagem, com a taxa e o ranking. **Leia**, não só rode: os defeitos
que importam nesta skill apareceram todos na leitura, nunca no código de saída.

---
### Task 14: o bloco da taxa no documento humano

**Arquivos:**
- Alterar: `scripts/lib/pagina.py` (acrescentar `bloco_resolucao`)
- Alterar: `scripts/imprimir.py` (incluir o bloco no corpo)
- Teste: `tests/test_imprimir.py`

**Depende de:** Task 13

- [x] **Step 1: escrever o teste que falha**

```python
# acrescente em tests/test_imprimir.py


def test_bloco_da_taxa_mostra_os_numeros_absolutos(tmp_path):
    """Sem a taxa, uma lista de dependências parece completa mesmo quando metade
    falhou. Os números absolutos, e não o percentual sozinho, porque é a rotulagem
    do balde `externos` que move a fração."""
    # Arrange
    preparar(tmp_path, imports={'arestas': [], 'indisponivel': [], 'resolucao': {
        'php': {'relativos': 0, 'externos': 424, 'sufixo_unico': 569,
                 'base_provada': 0, 'config_conferida': 0, 'ambiguos': 0,
                 'pendurados': 0, 'nao_resolvidos': 0, 'exemplos_nao_resolvidos': []}}})
    # Act
    r = imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert r.returncode == 0, r.stderr
    bloco = secao_do_bloco(html, 'Quanto disto foi medido')
    assert '569' in bloco and '424' in bloco
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_imprimir.py -q`
Esperado: FALHA com `IndexError` ao fatiar — o bloco não existe

- [x] **Step 3: escrever `bloco_resolucao` no `pagina.py`**

```python
def bloco_resolucao(inv: dict) -> str:
    """Quanto do grafo foi de fato medido, em números absolutos.

    O percentual sozinho esconde a decisão que o produz: é o resolvedor que decide
    o que é `externo`, e inflar aquele balde infla a fração. Num projeto medido a
    diferença entre duas rotulagens plausíveis era 85,5% e 75,7%.
    """
    resolucao = (inv.get('imports') or {}).get('resolucao') or {}
    if not resolucao:
        return ''
    linhas = []
    for linguagem, c in sorted(resolucao.items()):
        resolvidos = (c['relativos'] + c['sufixo_unico'] + c['base_provada']
                      + c['config_conferida'])
        denominador = (resolvidos + c['ambiguos'] + c['pendurados']
                       + c['nao_resolvidos'])
        quanto = (f'{round(resolvidos * 100 / denominador)}%' if denominador
                  else 'não medido')
        linhas.append(
            f'<div class="r"><b>{e(quanto)}</b><span>{e(linguagem)}</span>'
            f'<p>{resolvidos} de {denominador} imports internos. '
            f'{c["externos"]} externos, {c["ambiguos"]} ambíguos, '
            f'{c["pendurados"]} pendurados.</p></div>')
    return _bloco('Quanto disto foi medido', 'fato',
                  'O quanto confiar na seção de dependências.',
                  f'<div class="retratos">{"".join(linhas)}</div>',
                  classe='n2', largo=True,
                  rodape='O que não resolveu está contado, não escondido: import que o '
                         'resolvedor não casou com arquivo nenhum não vira aresta.')
```

- [x] **Step 4: incluir no corpo do documento**

Em `scripts/imprimir.py`, dentro da lista de `construir`, logo **depois** de
`pagina.bloco_muda_junto(inv),`, acrescente:

```python
        pagina.bloco_resolucao(inv),
```

- [x] **Step 5: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: todos passam, com o teste novo verde

---


### Task 15: as restrições verificáveis viram teste

**Arquivos:**
- Criar: `tests/fixtures/poliglota_com_codigo/` (o projeto de teste que faltava)
- Criar: `tests/test_restricoes.py`
- Teste: `tests/test_restricoes.py`

**Depende de:** Task 14

**Por que uma task própria:** restrição que ninguém checa é restrição que ninguém cumpre. As
quatro daqui não cabem em nenhuma task de implementação porque são sobre o **conjunto**.

**Por que a fixture nova:** `tests/fixtures/poliglota` tem só `api/composer.json` e
`web/package.json` — **zero arquivo de código**. Um teste de determinismo rodado nela não
produziria aresta nenhuma e não poderia detectar o que existe para detectar. A fixture nova
tem as três linguagens, e inclui o caso que o spec pede por nome: **um projeto Vue cujo
apelido só existe no config executável.**

- [x] **Step 1: escrever o teste da restrição de desenho**

```python
# tests/test_restricoes.py
import re
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / 'fixtures'


def test_o_resolvedor_nao_conhece_nenhuma_linguagem():
    """A restrição que mantém o desenho honesto: se o resolvedor souber o que é um
    tsconfig, acrescentar a quarta linguagem deixa de custar um extrator pequeno.
    Este teste é a diferença entre a regra estar escrita e estar valendo."""
    # Arrange
    fonte = (RAIZ / 'scripts' / 'lib' / 'resolucao.py').read_text('utf-8')
    proibidos = ['python', 'javascript', 'typescript', 'php', 'vue', 'node',
                 'tsconfig', 'composer', 'psr-4', 'package.json', '.py', '.ts', '.php']
    # Act — fora de comentário e docstring, nenhum nome de linguagem
    codigo = re.sub(r'(?s)""".*?"""', '', fonte)
    codigo = '\n'.join(l.split('#')[0] for l in codigo.split('\n'))
    # Assert
    achados = [p for p in proibidos if p in codigo.lower()]
    assert not achados, f'o resolvedor passou a conhecer linguagem: {achados}'
    assert 'if linguagem' not in codigo.lower()
```

- [x] **Step 2: rodar e confirmar que passa (ou corrigir o resolvedor)**

Rode: `.venv/bin/python -m pytest tests/test_restricoes.py -q`
Esperado: PASSA. Se falhar, **o conserto é no `resolucao.py`**, movendo o que for específico
para o módulo da linguagem — não no teste.

- [x] **Step 3: criar a fixture com as três linguagens**

```bash
cd ~/.claude/skills/sw-codebase-guide/tests/fixtures
mkdir -p poliglota_com_codigo/{api/app/Dominio,painel/src/components,servico}
cd poliglota_com_codigo

cat > api/composer.json <<'EOF'
{"autoload": {"psr-4": {"App\\": "app"}}, "require": {"monolog/monolog": "^3.0"}}
EOF
cat > api/app/Servico.php <<'EOF'
<?php
namespace App;
use App\Dominio\Pedido;
use Exception;
class Servico {}
EOF
cat > api/app/Dominio/Pedido.php <<'EOF'
<?php
namespace App\Dominio;
class Pedido {}
EOF

cat > painel/package.json <<'EOF'
{"dependencies": {"vue": "^3.0.0"}}
EOF
# o apelido mora SÓ aqui, em JavaScript executando: é o caso que motivou o desenho
cat > painel/vue.config.js <<'EOF'
const Path = require('path')
module.exports = { configureWebpack: { resolve: { alias: {
  '@Comp': Path.resolve(__dirname + '/src/components'),
} } } }
EOF
for i in 1 2 3 4 5; do
  echo "<template><div/></template>" > painel/src/components/Box$i.vue
done
cat > painel/src/tela.vue <<'EOF'
<template><div/></template>
<script>
import Box1 from '@Comp/Box1.vue'
import Box2 from '@Comp/Box2.vue'
import Box3 from '@Comp/Box3.vue'
import Box4 from '@Comp/Box4.vue'
import Box5 from '@Comp/Box5.vue'
import Vue from 'vue'
</script>
EOF

cat > servico/principal.py <<'EOF'
from servico.apoio import ajudar
import json
EOF
cat > servico/apoio.py <<'EOF'
def ajudar():
    return 1
EOF
```

- [x] **Step 4: escrever o teste que prova que a fixture tem o que testar**

```python
# acrescente em tests/test_restricoes.py
import json


def test_a_fixture_poliglota_produz_aresta_nas_tres_linguagens(tmp_path):
    """Teste de determinismo que roda sobre projeto sem import nenhum não detecta
    nada — e era esse o estado da fixture antiga. Este teste é a guarda da guarda."""
    # Arrange / Act
    subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'varrer.py'),
                    '--projeto', str(FIXTURES / 'poliglota_com_codigo'),
                    '--out', str(tmp_path)], check=True, capture_output=True)
    imports = json.loads((tmp_path / 'inventory.json').read_text())['imports']
    # Assert
    assert set(imports['resolucao']) == {'php', 'js', 'python'}
    linguagens_com_aresta = {a['de'].rsplit('.', 1)[-1] for a in imports['arestas']}
    assert {'php', 'vue', 'py'} <= linguagens_com_aresta
```

- [x] **Step 5: escrever o teste de idempotência ENTRE PROCESSOS**

```python
# acrescente em tests/test_restricoes.py


def test_mesmo_projeto_mesmo_inventario_em_processos_diferentes(tmp_path):
    """Duas chamadas dentro do mesmo pytest compartilham o seed de hash do Python e
    passariam mesmo com artefato não-determinístico. O laço antigo iterava um `set`
    de strings e concatenava arestas sem reordenar — passava por acidente porque só
    uma linguagem gerava aresta."""
    # Arrange
    saidas = []
    # Act — dois PROCESSOS, com seeds de hash diferentes
    for seed in ('1', '2'):
        destino = tmp_path / f'saida{seed}'
        subprocess.run(
            [sys.executable, str(RAIZ / 'scripts' / 'varrer.py'),
             '--projeto', str(FIXTURES / 'poliglota_com_codigo'), '--out', str(destino)],
            check=True, capture_output=True,
            env={'PATH': '/usr/bin:/bin', 'PYTHONHASHSEED': seed})
        saidas.append((destino / 'inventory.json').read_bytes())
    # Assert
    assert saidas[0] == saidas[1]
```

- [x] **Step 6: rodar e conferir**

Rode: `.venv/bin/python -m pytest tests/test_restricoes.py -q`
Esperado: PASSA. Se falhar, há ordem instável em alguma seção — ache-a comparando os dois
JSON com `json.loads` e `difflib`, e ordene **na origem**, não no teste.

- [x] **Step 7: escrever o teste de orçamento de tempo**

```python
# acrescente em tests/test_restricoes.py


def test_varredura_cabe_no_orcamento(tmp_path):
    """60 s é o que REPROVA; os 5 minutos são o teto que o dono aceita, não a meta.
    O índice de sufixos é O(arquivos x profundidade) e o extrator é um passe de
    regex por arquivo — se isto estourar, alguma coisa virou quadrática."""
    # Arrange — 600 arquivos com import, a ordem de grandeza de um projeto real
    projeto = tmp_path / 'grande'
    (projeto / 'src').mkdir(parents=True)
    for i in range(600):
        (projeto / 'src' / f'm{i}.ts').write_text(
            f"import a from './m{(i + 1) % 600}'\nimport b from '@/src/m{(i + 2) % 600}'\n")
    # Act
    inicio = time.monotonic()
    subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(tmp_path / 'out')],
                   check=True, capture_output=True)
    gasto = time.monotonic() - inicio
    # Assert
    assert gasto < 60, f'{gasto:.1f}s'
```

- [x] **Step 8: rodar e registrar o tempo**

Rode: `.venv/bin/python -m pytest tests/test_restricoes.py -q`
Esperado: PASSA, e bem abaixo de 60 s. Registre o tempo real em "Ajustes durante a execução".

- [x] **Step 9: escrever o teste da garantia sobre o documento MONTADO**

```python
# acrescente em tests/test_restricoes.py


def test_o_documento_montado_nao_afirma_ausencia_de_dependentes(tmp_path):
    """A guarda `PROIBIDAS` roda dentro de `_ler_narrativa()` — ou seja, só no texto
    que o AGENTE escreve. Todos os blocos novos são gerados pelo script e passam ao
    largo dela. A restrição só vale com este teste.

    Esta armadilha já pegou duas vezes nesta skill: a pergunta gerada pela própria
    skill continha 'não é usada', e o rodapé do ranking continha 'nada depende'."""
    # Arrange
    sys.path.insert(0, str(RAIZ / 'scripts'))
    from montar import PROIBIDAS
    subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'varrer.py'),
                    '--projeto', str(FIXTURES / 'poliglota_com_codigo'),
                    '--out', str(tmp_path)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'montar.py'),
                    '--dir', str(tmp_path)], check=True, capture_output=True)
    # Act
    guia = (tmp_path / 'guide.md').read_text('utf-8').lower()
    # Assert
    achadas = [f for f in PROIBIDAS if f in guia]
    assert not achadas, f'o documento gerado afirma ausência: {achadas}'
```

- [x] **Step 10: rodar a suíte inteira**

Rode: `.venv/bin/python -m pytest tests/ -q`
Esperado: todos passam. Se alguma frase proibida aparecer, **reescreva o texto do bloco** —
nunca afrouxe a lista.

---
### Task 16: publicar a v0.3.0

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/SKILL.md`
- Alterar: `CHANGELOG.md` (no repositório)

**Depende de:** Task 15

- [x] **Step 1: atualizar os limites declarados no `SKILL.md`**

A seção "Limites desta versão" ainda diz **"Grafo de import só para Python"**. Troque por:

```markdown
- **Grafo de import para Python, PHP, JavaScript, TypeScript e Vue.** Outras linguagens
  aparecem em `indisponivel` com o motivo declarado. A resolução é por **evidência** — o
  arquivo que existe —, e cada execução publica a própria **taxa de resolução**: abaixo de
  70% numa linguagem, a seção de dependências dela volta a ser lacuna, porque ranking sobre
  metade do grafo tem cara de fato.
- **O grafo continua sem ver** injeção de dependência, rota como string, reflexão e include
  de template. Grafo melhor não torna verdadeiro o que ele não vê, e a skill continua **nunca**
  afirmando ausência de dependentes.
```

- [x] **Step 2: descrever a seção `resolucao` no `SKILL.md`**

Na lista de seções do inventário, depois do item `imports`, acrescente:

```markdown
- **`resolucao`** — por extensão, sete números: `relativos`, `externos`, `sufixo_unico`,
  `base_provada`, `config_conferida`, `ambiguos`, `pendurados`, `nao_resolvidos`. A taxa é
  `(relativos + sufixo_unico + base_provada + config_conferida)` sobre tudo isso **menos
  `externos`**; denominador zero é "não medido", nunca 0%.
```

Rode depois: `.venv/bin/python -m pytest tests/test_skill_md.py -q`
Esperado: PASSA — o teste que confere que toda seção do inventário está citada no `SKILL.md`.

- [x] **Step 3: rodar a suíte inteira e o ciclo completo num projeto real**

```bash
cd ~/.claude/skills/sw-codebase-guide && .venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/varrer.py --projeto <raiz-do-monorepo> --out /tmp/d-final
# escreva o interpretation.toml e então:
.venv/bin/python scripts/montar.py --dir /tmp/d-final
.venv/bin/python scripts/imprimir.py --dir /tmp/d-final --estilo escuro
```
Esperado: suíte verde e os três documentos gerados. **Leia** a seção de dependências do
`guide.md` antes de seguir — os defeitos que importam aparecem na leitura, não no exit code.

- [x] **Step 4: sincronizar com bump de minor**

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-codebase-guide BUMP=minor
```
Esperado: `✓ plugin.json, marketplace.json e README atualizados.` com a versão **0.3.0**.
Não edite `marketplace.json` nem a tabela do `README.md` à mão — o sync já faz.

- [x] **Step 5: escrever a entrada no `CHANGELOG.md`**

Acrescente no topo de `## [Não publicado]`, trocando os `<…>` pelos números que a Task 9,
step 8 e a Task 13, step 6 mediram:

```markdown
### Adicionado
- `sw-codebase-guide` (v0.3.0): **o grafo de import passou a existir para PHP, JavaScript,
  TypeScript e Vue** — e a seção "o que depende do quê", que era lacuna nessas stacks, agora
  diz quem importa quem.

  A decisão que faz isso funcionar é não acreditar na configuração. Resolver a string do
  import em arquivo exigiria ler PSR-4, `tsconfig.paths` e o apelido do bundler — e num
  projeto real o apelido mora num `vue.config.js`, que é **JavaScript executando**, não dado.
  A skill resolve pelos **arquivos que existem**: casa o import contra o índice de sufixos do
  projeto, e sufixo único vira aresta. Depois, numa segunda passada, as bases já provadas por
  cinco imports desempatam o que ficou ambíguo. No projeto do `vue.config.js` isso
  redescobriu os quatro apelidos declarados — `@`, `@Component`, `@View` e `@Assets` — sem
  abrir o arquivo, e resolveu <N> de <M> imports internos.

  **Cada execução publica a própria taxa de resolução**, em sete números absolutos e não em
  percentual: é o resolvedor que decide o que é "externo", e inflar esse balde inflaria a
  fração. Abaixo de **70%** resolvido numa linguagem, a seção de dependências dela volta a
  ser lacuna — ranking construído sobre metade do grafo tem cara de fato, e é o erro que a
  v0.1.1 custou.

  Sintaxe é por linguagem, resolução é uma só: acrescentar uma linguagem custa um extrator
  de texto e uma lista de extensões, e um teste confere que o resolvedor não contém nome de
  linguagem nenhum.

### Corrigido
- `sw-codebase-guide` (v0.3.0): **nome puro vira externo por regra, não por coincidência.**
  Medido num projeto real: `import 'server-only'` casaria com
  `tests/helpers/server-only.ts` — oito arestas erradas de um pacote npm. Builtin do Node
  (`path`, `fs`, `url`) é a mesma armadilha com nome de utilitário comum, e pior: ele nunca
  aparece em `dependencies`, então qualquer exceção escrita como "o que não é dependência
  declarada" o deixaria passar.

  Junto: **a lista por símbolo saiu**. Ela vinha de `mencoes` e casava PALAVRA, o que numa
  base em português devolvia `banco` e `caminho` com centenas de menções; com aresta real, o
  ranking é por arquivo e ordenado por quem importa. E o `inventory.json` voltou a ser
  determinístico: as arestas eram concatenadas num laço sobre um `set`, cuja ordem muda por
  processo — passava por acidente porque só o Python gerava aresta.
```

- [x] **Step 6: rodar o gate de segurança DEPOIS de preparar o commit**

```bash
cd /var/www/ai-marketplace && git add -A && make check
```
Esperado: `✓ gate de segurança: nada sensível detectado`.

**A ordem importa:** o gate escaneia o conteúdo **staged**. E ele não pega tudo — releia o
diff procurando nome real de projeto e descrição de negócio de cliente, que já passaram pelo
gate nesta mesma skill.

---

## Ajustes durante a execução

<!-- registre aqui o que divergiu do plano, com data -->

### 2026-10-07 — Task 1 (SPIKE): sufixo único é evidência, não coincidência

Spike rodado em três projetos de calibração (um monorepo PHP + Vue com quatro repositórios
git justapostos, um projeto Next.js/TypeScript e um projeto PHP puro), com a semente
declarada (`20261007`).

**2250 arestas resolvidas** no total: 2240 por `sufixo_unico` e 10 por `base_provada`.

**Veredito: 30 de 30 corretas; nenhuma aresta errada.** Nenhum dos dois modos de erro
apareceu: nenhum destino com nome certo em pasta errada e nenhum import de pacote casado
com arquivo do projeto por coincidência.

Conferência: nas 13 arestas PHP de um projeto e nas 6 do outro, o `psr-4` do `composer.json`
mapeia `App\` → `app`, e em todas o `namespace` do arquivo de destino e o nome da classe
batem com a string do `use`. Nas 6 de TypeScript, o `paths` do `tsconfig.json`
(`@/*` → `./src/*`) confirma o destino, e o símbolo importado existe como `export` em cada
um. Nas 5 de JavaScript/Vue, os apelidos vivem em `vue.config.js`, em `vitest.config.js` e
em `vitest.config.mjs` — JavaScript executando, exatamente o caso que motivou resolver por
evidência — e a evidência acertou os três.

Das 30 da amostra, **zero eram de procedência `base_provada`** (são 10 em 2250, 0,4%). Como
o piso de 5 do plano não foi atingido na amostra, as 10 foram conferidas à parte, todas as
10 corretas — e elas são justamente o caso de maior risco: `@<apelido>/store/index.js` tem
dois candidatos no monorepo (o `store/index.js` de um repositório e o de outro), e o
desempate por base provada escolheu o que o apelido do `vitest.config.mjs` realmente
alcança. Mesma coisa para `router/index.js` e para um `.vue` homônimo em dois repositórios.

O script do spike rodou sem ajuste nenhum — o código do plano está correto como escrito.
Tempo: ~3,5 s para os três projetos juntos. Conclusão: **o desenho fica como está** (piso de
dois segmentos, `MIN_PROVAS = 5`); nenhuma das saídas de contingência precisou ser acionada.

### 2026-10-07 — Task 2: o contrato das linguagens

Feita como escrita, com **um desvio e quatro correções** vindas do juiz, todas medidas contra
código real.

**O desvio, e ele estava certo.** O código do step 3 do plano (`'./' + '../' * (no.level - 1)`)
produzia `./../pai/modulo`, enquanto o teste do step 1 exige `../pai/modulo`. A implementação
seguiu o teste, que é o contrato. As duas formas apontam o mesmo lugar depois da normalização;
a curta é a canônica, e é ela que chega ao `inventory.json`.

**O que o juiz achou, com número:**

1. **O extrator perdia o candidato por NOME.** `from lib import arvore` devolvia só `lib`. O
   extrator antigo emitia os dois (`imports.py:67`), e 35% das arestas Python desta skill
   vinham só desse candidato. O caso pior é o ponto de entrada dela mesma: `scripts/lib/` não
   tem `__init__.py`, então o `varrer.py` ficaria isolado no grafo do próprio projeto.
   Corrigido, com três testes.
2. **`extrair` devolvia alvo repetido** (10 em 119 nos arquivos da skill). O orquestrador dá
   `append` por ocorrência: viraria aresta duplicada no inventário e dependente contado duas
   vezes no ranking. Agora sai sem repetição, preservando a ordem.
3. **O comentário do `BUILTINS` afirmava o que o pipeline não fazia.** Ele diz "o índice
   decide", mas `import json` terminaria em `nao_resolvidos` — e stdlib de um segmento é 72%
   dos alvos desta skill, o que levaria a taxa do Python a ~28% e jogaria a seção abaixo do
   piso de 70%. Seria a restrição *"o grafo de Python não regride"* violada pela **contagem**,
   com as arestas todas certas. A regra foi escrita na **Task 10** (nome puro que não casa é
   externo, na linguagem que permite nome puro interno), com teste e mutação.
4. **A guarda de "sobe acima da raiz" tinha sumido.** A antiga era
   `if no.level - 1 > len(partes)`; o extrator novo não conhece o caminho de origem e não pode
   tê-la. O `_normalizar` engoliria o `..` sobrando em silêncio, e `../../x` num arquivo de
   raiz casaria com um `x.py` qualquer — aresta errada. A guarda foi para a **Task 5**, com
   teste e mutação.

Também corrigido: `except SyntaxError` virou `except (SyntaxError, ValueError, RecursionError)`
— `ValueError` é o que o `ast` levanta para byte nulo antes do 3.12, e a skill roda com o
`python3` que a máquina tiver.

Suíte: **214 passam** (206 no começo da task; +4 do plano, +4 das correções).

### 2026-10-07 — Task 3: o extrator de JavaScript, TypeScript e Vue

Feita como escrita, mais **três defeitos** achados depois — e o pior deles foi introduzido pela
correção do primeiro, o que vale registrar inteiro.

1. **Import multilinha não casava.** `import {\n um,\n dois,\n} from '…'` é o que o formatador
   produz assim que a linha passa da largura — forma padrão, não borda. Medido: **40 imports
   internos** perdidos nos três projetos de calibração, todos relativos ou apelidados, sem erro
   nenhum, só ausentes. Depois do conserto as contagens subiram exatamente 16, 14 e 10.

2. **A correção trouxe backtracking catastrófico.** Escrevi o miolo como
   `(?:[^'";]|\n)*?` — alternância **ambígua**, porque classe negada já casa `\n`. Os dois ramos
   disputando o mesmo caractere fazem o backtracking dobrar por linha: medido **0,56 s** com 18
   linhas, 2,3 s com 20, 9 s com 22 e **36 s com 24**. O gatilho é uma `interface` TypeScript
   sem ponto e vírgula, que é o padrão do formatador em projeto Vue — **um** arquivo desses
   estoura sozinho o orçamento de 60 s da Task 15. É a mesma classe de bug que o `redact.py`
   desta skill já custou (80 s num arquivo), e ela voltou por outro caminho.

   A correção é uma classe única com a crase dentro, `` [^'"`;]*? ``: 200 linhas em 0,000 s,
   **zero** alvos perdidos nos 427 arquivos reais, e de quebra fecha o defeito 3.

3. **O miolo preguiçoso atravessava instrução.** `export const DOC = \`veja from
   "@/paginas/Home.vue"\`` virava aresta para um arquivo que existe, inventada por prosa dentro
   de template literal. Zero ocorrências nos projetos reais, mas aresta errada é a única coisa
   que este desenho declara pior que aresta faltando.

**Dois comentários afirmavam o que o código não fazia**, e foram reescritos: a âncora de início
de linha barra `//` e ` * `, mas **não** barra bloco `/* */` sem prefixo por linha (limite
conhecido, zero ocorrências medidas); e "a ordem das alternativas importa" é falso — a de efeito
colateral exige aspa logo depois de `import`, então nunca casaria `import X from 'y'` pela
metade. A frase errada estava também no plano, e saiu dos dois.

Suíte: **224 passam**, em 20 s — inclusive um teste de desempenho, porque o 2ⁿ é invisível numa
suíte verde e voltaria na primeira vez que alguém "melhorasse" o miolo.

### 2026-10-07 — Tasks 4 a 16, executadas sem gate a pedido do dono

O dono apontou, com razão, que o processo tinha ficado maior que o trabalho: 300 linhas de
código cercadas por spec, plano, três revisores e um juiz por task. As treze tasks restantes
foram feitas direto, com os testes e a medição valendo como prova.

**Defeitos achados durante a execução**, todos por medição ou por leitura do documento:

| # | Defeito | Como apareceu |
|---|---|---|
| 1 | `_de_fora` tratava prefixo de apelido como externo | prefixo de apelido **nunca** existe como arquivo, então todo import apelidado não resolvido virava "externo" e o caminho fraco morria |
| 2 | dependência externa contada como falha | `collections/Counter` e `use SysWeb\Controller`: Python a 33% e PHP a 57%, com as arestas certas |
| 3 | o ranking de `js` listava arquivos `.php` | a entrada era global; passou a ser por linguagem, pela extensão de quem importa |
| 4 | vinte linhas de lacuna antes do conteúdo | eu dupliquei um emissor que já existia, e `.log`, `.css`, `.txt` e `.sql` eram declarados "linguagem sem resolvedor" |
| 5 | `from pedido import X` com `pedido.py` no projeto virava externo | o piso de dois segmentos barrava o nome puro, que não tem prefixo para tirar |
| 6 | a ressalva repetia as cinco cegueiras | o preâmbulo da seção já as lista; três vezes a mesma coisa na mesma página |

O defeito 4 é a v0.1.1 de novo, por outro caminho — e foi encontrado **lendo o documento
gerado**, não rodando teste. Nenhum teste reclamava.

**Cinco testes existentes descreviam o mundo pré-grafo** e foram reescritos, não apagados: os
que exigiam a frase "não foi medido nesta versão", o do símbolo citado só em documentação, e o
do acoplamento invisível. Este último registra uma **perda de capacidade real**: o acoplamento
que existe só por string e injeção aparecia na lista por símbolo e agora não aparece em lugar
nenhum. A seção que cruza co-mudança com import para achá-lo ficou para o próximo ciclo; o
documento diz o que não enxerga e aponta onde o dado bruto está.

**Medição final**, quatro projetos reais: js 98% e 99%, php 99% e 100%, Python idêntico ao
anterior (353 arestas, diferença zero). Num repositório com oito cópias quase idênticas de
skill, o Python fica em 39% e a seção vira lacuna — correto: ali `from lib import stacks` é
genuinamente ambíguo, e o código antigo tinha a mesma ambiguidade, só nunca a contou.

**Desempenho:** 600 arquivos com 1.200 imports em **0,11 s**. O tempo dos projetos reais vem
do `git log`, não do grafo.

Suíte: **95 → 266 testes**. Publicada a v0.3.0, commit sem push.
