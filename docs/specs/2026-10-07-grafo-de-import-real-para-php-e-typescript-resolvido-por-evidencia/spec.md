---
titulo: Grafo de import real para PHP e TypeScript, resolvido por evidencia
slug: 2026-10-07-grafo-de-import-real-para-php-e-typescript-resolvido-por-evidencia
criado: 2026-10-07
estado: em-execucao
---

# Grafo de import real para PHP e TypeScript, resolvido por evidência

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `plan.md` é o passo a
> passo de execução; `referencias/` guarda o material de apoio.

Item **D** do roteiro acordado da `sw-codebase-guide` (**A → D → B → C**): documento humano
(feito, v0.2.0) → **grafo real de PHP e TypeScript** → julgamento → conhecimento vivo.

## Objetivo & outcome

A seção *"o que depende do quê"* deixa de ser lacuna nas stacks que o dono usa. Hoje ela diz
*"o acoplamento por import não foi medido para: node, php"*; depois deste trabalho ela diz
quem depende de quem, com aresta real, **e quanto da medição deu certo**.

**Outcome:** PHP resolve ≥ 95% dos `use` internos e JS/TS ≥ 95% dos imports internos nos
projetos de calibração, com a taxa publicada no próprio documento. Os 95% são a **meta nos
projetos medidos**; o piso de 70% da seção "O que muda no documento" é outra coisa — é o limite
abaixo do qual **qualquer** projeto volta a receber lacuna no lugar de ranking.

**Por que antes do julgamento (item B):** não dá para afirmar *"mexer aqui é arriscado"* sem
saber quem depende de quem. O D é o que destrava o B.

## Exploração & decisões

A pergunta que organizou o design foi **resolver por configuração ou por evidência**. Medição
completa em [`referencias/medicao-de-resolucao.md`](referencias/medicao-de-resolucao.md),
regerável por [`referencias/medir-resolucao.py`](referencias/medir-resolucao.py).

O que a medição derrubou e o que confirmou:

1. **Derrubou a premissa de que é preciso ler a configuração.** Num dos projetos os apelidos
   moram num `vue.config.js` — JavaScript executando, não dado. Era o risco nº 1 do trabalho.
   Resolvendo **pelos arquivos que existem**, sem abrir configuração nenhuma, o mesmo projeto
   resolve 276 de 332 imports apelidados, e a inferência de apelido (abaixo) fecha os 56
   restantes. **O risco nº 1 deixou de existir.**
2. **Confirmou que o apelido é inferível e verificável.** Agrupando o que já resolveu pelo
   prefixo e tirando a base (destino menos o sufixo que casou), saiu `@ → src` (152 provas),
   `@Component → src/components` (104), `@View → src/views` (15), `@Assets → src/assets` (5) —
   **100% de concordância nos quatro**, e exatamente o que o `vue.config.js` declara. O método
   redescobriu a configuração sem abrir o arquivo.
3. **Corrigiu uma conclusão minha que estava errada.** Eu li "todos os não-achou são pacotes
   escopados" como *"pacote se separa sozinho"*. A revisão apontou que a conta não fechava —
   682 imports contra 436 classificados — e o motivo é que o meu script **não classificou os
   246 imports de nome puro** (`vuex`, `vitest/config`): eles nunca foram testados contra o
   índice. Medindo depois: num projeto real, `import 'server-only'` **casaria** com
   `tests/helpers/server-only.ts` — oito arestas erradas. Nome puro, portanto, é externo por
   regra, não por coincidência de não casar.
4. **Mostrou onde o extrator não pode falhar.** Em projeto Vue, **mais da metade** dos imports
   vive dentro de arquivos `.vue` (389 de 676). E o `import()` dinâmico, embora pouco
   frequente (14 e 9 ocorrências), é a aresta **rota → tela** da SPA — é o análogo front-end
   da rota-por-string do PHP, com a diferença de ser visível.
5. **Mostrou que o PHP é o caso fácil.** `use X;` responde por 992 e 1.145 ocorrências nos dois
   projetos; `use … as` aparece **1 vez** em cada; `use` agrupado e `use function` não
   aparecem. Com PSR-4 declarado em JSON, `use` → arquivo é substituição de prefixo.

**Alternativas descartadas:** ver a seção Decisões.

## Arquitetura

A decisão estrutural: **sintaxe é por linguagem; resolução é uma só, por evidência.**

```
scripts/lib/linguagens/php.py     texto -> ['App\Dominio\Models\Pedido', 'Exception', …]
scripts/lib/linguagens/js.py      texto -> ['@Component/boxs/Box', './App.vue', 'vuex', …]
scripts/lib/linguagens/python.py  (o extrator que já existe, movido para cá)
                                        |
scripts/lib/resolucao.py          (string + arquivo de origem) -> arquivo de destino | motivo
scripts/lib/imports.py            orquestra, conta e devolve {arestas, indisponivel, resolucao}
```

O extrator **não sabe** o que é apelido, PSR-4 ou barrel — ele devolve strings. Quem conhece o
sistema de arquivos é o resolvedor, e ele é o mesmo para todas as linguagens.

**Restrição de simplicidade:** acrescentar uma linguagem custa **um extrator pequeno e uma
lista de extensões**. Se custar mais, o desenho está errado. Verificável: o `resolucao.py` não
pode conter nenhum `if linguagem ==`.

## Componentes

### `lib/linguagens/<linguagem>.py`

Cada módulo expõe **três** coisas, e nenhuma delas toca o sistema de arquivos:

```python
EXTENSOES = ['.ts', '.tsx', '.js', '.jsx', '.vue', '.mjs']   # candidatas na resolução
def extrair(texto: str) -> list[str]: ...                     # as strings de import, em ordem
def classificar(alvo: str) -> str: ...  # 'relativo' | 'qualificado' | 'nome_puro'
```

O `classificar` é o que mantém a restrição de simplicidade de pé. Sem ele, as regras de
externalidade — *"nome puro é externo"* no JS, *"`use` sem barra invertida é global"* no PHP —
viveriam no resolvedor, e ele voltaria a ter `if linguagem ==`. Com ele, as duas frases são a
mesma coisa dita por linguagens diferentes: **`nome_puro`**. O resolvedor conhece três
categorias e nenhuma linguagem.

**JS/TS** cobre cinco formas, todas medidas como presentes nos projetos reais:
`import … from 'x'` · `import 'x'` (efeito) · `export … from 'x'` · `import('x')` (dinâmico,
que é a aresta rota → tela) · `require('x')`. O arquivo `.vue` é lido como texto inteiro —
o `<script>` contém JavaScript normal, e separar o bloco não paga o custo.

**PHP** cobre `use X;` (992 e 1.145 ocorrências), `use X as Y;` (1 em cada), `use X\{A, B};`,
`use function X\y;` e `use const X\Y;` — as três últimas não aparecem nos projetos de
calibração, mas são sintaxe padrão e custam uma alternância na expressão. Cair fora delas
tiraria arestas do **denominador** em silêncio, que é pior que não resolvê-las.

### `lib/resolucao.py`

Uma função por etapa, e o caminho de cada import nesta ordem:

| # | Etapa | Resultado |
|---|---|---|
| 1 | **Relativo** (`./x`, `../x`) — resolve contra o arquivo de origem, na ordem fixa das extensões e depois `/index.*` | aresta, ou **pendurado** (contado, nunca aresta) |
| 2 | **Externo** — ver as regras abaixo | **externo** (não é falha de resolução) |
| 3 | **Sufixo no índice** dos arquivos que existem, para todo `qualificado` | **único** vira aresta; **ambíguo** e **fraco** ficam reservados para a segunda passada |
| 4 | *(segunda passada)* **base provada pelos arquivos** | aresta, ou **não resolvido** |

Quando `x.ts` e `x/index.ts` existem os dois, vence o primeiro da ordem declarada em
`EXTENSOES` — é o que o Node faz, e é **ordem fixa e escrita**, não o "primeiro candidato
ganha" que a Decisão 2 proíbe (lá são dois candidatos igualmente plausíveis; aqui há uma regra
de precedência conhecida).

**Etapa 2, as regras do externo** — é aqui que nasce a aresta errada, então cada uma tem
motivo medido:

1. **`nome_puro` é externo** — a categoria que o `classificar` da linguagem devolve. Em JS é a
   string sem `./` e sem prefixo de apelido: pacote ou builtin do Node. Em PHP é o `use` sem
   barra invertida: classe global. Medido num projeto real: `import 'server-only'` casaria com
   `tests/helpers/server-only.ts` — **8 arestas erradas** de um pacote. `path`, `fs` e `url`
   são a mesma armadilha com nome de utilitário comum. A exceção é `baseUrl` do `tsconfig`
   (import absoluto a partir de uma raiz declarada). Ela é **estreita**, porque escrita larga
   ela reabre o buraco que acabou de ser fechado: builtin do Node (`fs`, `path`, `url`,
   `crypto`, `events`, `stream`, `os`, `util`…) é nome puro e **nunca** aparece em
   `dependencies` — "não é dependência declarada" autorizaria `import fs from 'fs'` →
   `src/fs.ts`. Então valem as **três** condições juntas: não é dependência declarada, **não
   está na lista de builtins da linguagem**, e tem **dois ou mais segmentos**.
2. **Dependência declarada vence, pelo nome inteiro, e para qualquer classe.**
   `@escopo/pacote` e `@Apelido/arquivo` são sintaticamente **iguais** — não há como separá-los
   pela forma. Tentar pela caixa da inicial erra: medido, `@areas` é um apelido **minúsculo**
   com 45 imports num projeto real, e a regra da caixa o mandaria para fora como se fosse
   pacote, sumindo com 45 arestas internas em silêncio. Então os dois saem do `classificar`
   como `qualificado`, e é **a declaração** que separa. Sem conferir a declaração também para o
   `qualificado`, `@vue/test-utils` cairia no índice e sairia contado como *não resolvido* —
   deflacionar a taxa é o espelho de inflá-la. O risco de `test-utils` casar com
   `src/test-utils/` é barrado duas vezes: pela declaração, e pelo piso de dois segmentos.
As dependências declaradas são lidas **só pelas chaves** de `dependencies`/`require`, nunca
pelos valores: valor de dependência carrega URL de registro privado com token. É a mesma regra
do `.env`, e vale igual aqui.

**Etapa 3, o candidato a sufixo** é a string **menos o primeiro segmento**, e isso é genérico
de propósito: no JS o primeiro segmento é o apelido (`@Component`), no PHP é o namespace raiz
(`App`) — `App\Dominio\Models\Pedido` vira o sufixo `Dominio/Models/Pedido`, que casa com
`app/Dominio/Models/Pedido.php`. Sem essa frase o `qualificado` do PHP ficaria **sem etapa
nenhuma** e só resolveria pelo atalho de configuração, contra o "PSR-4 nunca como verdade".

Para isso valer, **o extrator devolve a string já com `/` como separador** — a string com `\`
jamais casaria num índice construído sobre `/`, e consertar isso no resolvedor exigiria que ele
soubesse que aquilo é PHP.

O candidato precisa de **dois ou mais segmentos**. `@/utils` sobra um só: é **fraco**, e vai
para a segunda passada junto com os ambíguos.

**Etapa 4 é uma SEGUNDA PASSADA, não o quarto passo de um pipeline por import.** Ela precisa do
resultado agregado da primeira, roda **uma única vez** e usa **somente** evidência da passada 1
— aresta que ela cria não realimenta prova, senão haveria iteração, com convergência e
determinismo em aberto.

A regra é estritamente de evidência, **sem voto de maioria**: uma **base** é provada para um
prefixo quando **`MIN_PROVAS = 5`** imports daquele prefixo resolveram sozinhos sob ela.

A etapa 3 manda para cá **dois** tipos de pendência, e cada um tem a sua regra:

- **ambíguo** (vários candidatos): resolve se **exatamente um** deles está sob base provada;
- **fraco** (um segmento só, sem candidato nenhum, caso do `@/utils`): monta
  `base_provada + resto` e resolve se esse arquivo **existe e é único**.

A regra do fraco não é detalhe: `@/` é o apelido mais comum nos projetos Vue e Next medidos, e
sem ela ele cairia inteiro em `nao_resolvidos` — a meta de 95% morreria por omissão, não por
desenho.

Medido: isso desempata **56 de 56** no projeto de calibração, o mesmo resultado que o voto de
maioria dava — sem o palpite. Maioria contrariava a invariante: uma concordância de 80% é a
prova explícita de que aquele prefixo *não* cai sempre na mesma pasta, e forçar o ambíguo para
a maioria é exatamente onde a aresta errada nasceria. Com a regra por base provada, o limiar de
concordância **deixa de existir**.

**Toda aresta carrega a procedência**: `relativo` · `sufixo_unico` · `base_provada` ·
`config_conferida`. É isso que permite a amostra de conferência à mão ser sorteada **dentro das
inferidas**, que são as de maior risco, e o documento contá-las em separado.

**PSR-4, `tsconfig.paths` e `baseUrl` entram como atalho, nunca como verdade.** Conferidos
contra o disco antes de valer: mapeamento que aponta para pasta inexistente é descartado e o
import cai na etapa 3.

**Quem é dono dessa leitura é a linguagem, mas de forma declarativa** — senão o resolvedor
precisaria das strings `composer.json`, `tsconfig.json` e `psr-4`, e a restrição *"nenhum nome
de linguagem no resolvedor"* cairia. Cada módulo de linguagem declara **onde** o vocabulário
mora, e um leitor genérico o aplica:

```python
# lib/linguagens/php.py
CONFIGS = [{'arquivo': 'composer.json', 'prefixos': 'autoload.psr-4'}]
BUILTINS = frozenset()            # o PHP resolve isso pelo `classificar`
# lib/linguagens/js.py
CONFIGS = [{'arquivo': 'tsconfig.json', 'prefixos': 'compilerOptions.paths',
            'raizes': 'compilerOptions.baseUrl'},
           {'arquivo': 'jsconfig.json', 'prefixos': 'compilerOptions.paths',
            'raizes': 'compilerOptions.baseUrl'}]
BUILTINS = frozenset({'fs', 'path', 'url', 'crypto', 'events', 'stream', 'os', 'util', …})
```

O leitor devolve sempre o **mesmo formato, sem linguagem dentro**:
`{'nomes_declarados': {...}, 'prefixos': [{'prefixo': ..., 'base': ...}], 'raizes': [...]}`.
Daí a procedência da aresta ser **`config_conferida`**, e não `psr4_conferido`: o nome de uma
linguagem num vocabulário que precisa ser agnóstico é o começo do `if linguagem ==`, e além
disso não haveria procedência para a aresta vinda de `tsconfig.paths`.

**O limiar tem número** pelo mesmo motivo do `areas.py`: sem número, cada projeto se comporta
diferente por motivo que ninguém sabe explicar. `MIN_PROVAS = 5` está calibrado por pouco —
`@Assets` tem exatamente 5 provas; abaixo disso entra ruído, acima perde-se um apelido real.
É o **único** limiar do resolvedor.

### `lib/imports.py`

**Despacha por extensão presente na árvore, não por stack detectada.** O `stacks.py` registra
que a regra por stack já deixou 210 arquivos Python *nem parseados nem declarados como lacuna*,
e a detecção por extensão tem piso de `MIN_ARQUIVOS = 5` — com três extratores isso volta: 4
arquivos `.ts` num projeto PHP sumiriam em silêncio. Extensão presente **sem** extrator vira
`indisponivel` com motivo. (`node` também não identificaria o extrator: é uma stack só para
`.js`, `.jsx`, `.ts`, `.tsx` e `.vue`.)

**A lista de arestas é ordenada no fim, uma vez.** Hoje o laço é
`for componente in {s['stack'] for s in stacks}` — um `set` de strings, cuja ordem varia por
processo — e `arestas.extend(...)` concatena sem reordenar. Passa por acidente porque só o
Python gera aresta; com três extratores, o `inventory.json` sairia diferente a cada rodada.
**O teste de idempotência tem que comparar processos diferentes** (`subprocess`): duas chamadas
dentro do mesmo pytest compartilham o seed de hash e passariam com o artefato não-determinístico.

Devolve três coisas em vez de duas:

```json
{
  "arestas": [{"de": "api/app/X.php", "para": "api/app/Y.php", "origem": "config_conferida"}],
  "indisponivel": [{"stack": "go", "motivo": "…"}],
  "resolucao": {"php": {"relativos": 0, "externos": 424, "sufixo_unico": 569,
                        "base_provada": 0, "config_conferida": 0, "ambiguos": 0, "pendurados": 0,
                        "nao_resolvidos": 0, "exemplos_nao_resolvidos": []}}
}
```

**A fórmula da taxa**, escrita uma vez para os dois leitores chegarem ao mesmo número:

```
resolvidos  = relativos + sufixo_unico + base_provada + config_conferida
denominador = resolvidos + ambiguos + pendurados + nao_resolvidos
taxa        = resolvidos / denominador          # externos ficam FORA dos dois
denominador == 0  ->  "não medido", nunca 0%    # linguagem sem import interno nenhum
```

`relativos` conta só os **resolvidos** — o relativo que não existe no disco é `pendurado`, e é
por isso que o balde existe. `externos` fica fora do denominador de propósito, e é a conta mais
delicada do spec: é o resolvedor que decide o que é externo, e inflar esse balde infla a taxa.
Por isso o documento mostra os **sete números**, não só a fração.

`exemplos_nao_resolvidos` leva **os 5 primeiros em ordem lexicográfica** — com teto e ordem,
porque o `inventory.json` tem que dar diff byte a byte.

**Números absolutos, não percentual.** O percentual depende de qual balde recebe o import que
não é relativo, não é dependência declarada e não casa no índice: chamá-lo de externo **infla**
a taxa, chamá-lo de interno **deflaciona**. No projeto de calibração a diferença entre as duas
leituras era 85,5% contra 75,7% — e o veredito sairia da rotulagem, não do resolvedor. Então o
quarto balde tem nome próprio (`nao_resolvidos`) e os sete números aparecem.

## A invariante

**Aresta errada é pior que aresta faltando.** A falta aparece na taxa de resolução e o leitor a
vê; a errada manda alguém mexer no arquivo errado e não deixa rastro. Dela saem três regras:

- sufixo **ambíguo não resolve** — nem na etapa 3, nem depois, a não ser por apelido provado;
- configuração só vale **conferida** contra o disco;
- o que não resolveu é **contado e exemplificado**, nunca omitido.

## Fluxo de dados

**Com `--area`, o import segue a terceira regra de recorte que a skill já tem** — a mesma de
`historia` e `mencoes`: vale a aresta com **uma ponta dentro** da área. O par que cruza a
fronteira é o valor da seção ("para mexer aqui você mexe lá fora"), e descartá-lo esvaziaria
justamente o caso interessante. **O índice e a varredura são sempre do projeto inteiro**, nunca
do recorte: um import que sai da área não pode virar `nao_resolvidos` e derrubar a taxa sem
nada estar errado. Hoje o `varrer.py` passa `componentes` já recortados ao `imports.grafo()`
enquanto o grafo varre o projeto todo por conta própria — essa inconsistência morre aqui.

`varrer.py` já tem a árvore de arquivos e as stacks. O `imports.grafo()` passa a receber a
árvore (que ele hoje reconstrói), monta o índice de sufixos uma vez, roda o extrator por
arquivo e o resolvedor por string. Nada muda na forma como o `montar.py` e o `imprimir.py`
consomem `arestas`; o que é novo é `resolucao`, que vira bloco de fato nos dois documentos.

## O que muda no documento

**Piso: abaixo de 70% resolvido numa linguagem, a seção daquela linguagem volta a ser lacuna**,
com a taxa como motivo. Um ranking construído sobre metade do grafo tem cara de fato e é o erro
que a v0.1.1 custou — não basta publicar a taxa ao lado, porque ninguém lê uma ressalva e
depois duvida de uma lista ordenada.

Acima do piso, a seção passa a responder:

**A seção continua sendo UMA, com um bloco por linguagem que tem extrator** — é o que o piso
pressupõe: num projeto com PHP a 98% e JS a 60%, o leitor vê o ranking do PHP e, abaixo, a
lacuna do JS com a taxa como motivo. Sem isso, "piso por linguagem" numa seção única não tem
como ser apresentado.

1. **O que mais arquivos importam diretamente** — *"23 arquivos importam `PedidoService.php`"*.
   **Isto SUBSTITUI a lista por símbolo de hoje**, não convive com ela. O `_dependentes()`
   atual itera `mencoes` **por símbolo** e ordena por número de menções textuais — ele era o
   que dava para fazer sem grafo. Com aresta real, ranking por arquivo e ordenado por
   importadores responde a mesma pergunta sem o ruído do casamento por palavra. Isso é
   reescrita do `_dependentes()`, e portanto está **dentro** do escopo, não fora dele.
   **"Importa diretamente", nunca "alcança"**: "alcança" se lê como transitivo, e o design
   declara que não é. A ressalva da garantia continua ao lado, porque um top-N convida o leitor
   a inferir o complemento — *"o que não está aqui não tem dependente"* é exatamente a
   afirmação que esta skill nunca faz.
   **Arquivo de puro re-export fica fora do ranking**, marcado. O critério é estreito e
   escrito: arquivo cujo conteúdo, fora comentário e linha em branco, é **só** `export … from`.
   Qualquer outro código e ele volta a ser um arquivo normal — dois critérios plausíveis dariam
   duas implementações. Com `export … from` no extrator
   e centenas de imports apelidados, todo `@/utils` resolve no barril e o topo viraria *"300
   arquivos importam `index.ts`"* — verdadeiro, inútil, e com o dependente real a dois saltos
   que o não-objetivo "sem análise transitiva" proíbe seguir.
2. **A taxa de resolução, em números absolutos**, como fato medido.
A seção continua **nunca** afirmando ausência de dependentes, e as cinco cegueiras continuam
declaradas: grafo melhor não torna verdadeiro o que ele não vê.

**Fronteira com o `stacks.py`:** quem descobre manifesto é ele, que já caminha com poda, já
desduplica e já aprendeu a lição do `.next/package.json`. Ele passa a devolver, por manifesto e
caminho, o **conjunto de nomes** de dependência declarada. O `resolucao.py` não redescobre
manifesto — duas descobertas em módulos diferentes é a volta daquele bug. Num projeto
poliglota, o que vale para um arquivo é o manifesto **ancestral mais próximo** dele, não a
união de todos: a união torna o falso-externo mais provável, e falso-externo infla a taxa
escondendo aresta interna.

**O índice de sufixos é construído sobre os arquivos não gerados e não podados**, e exclui
também `.d.ts`, `__snapshots__` e `*.stories.*` — que não estão em `GERADOS` hoje e são
fabricantes clássicos de sufixo duplicado, ou seja, de ambiguidade artificial que derruba a
taxa sem que nada esteja errado.

## Fica para a continuação: o par que muda junto e não se importa

**Cortado deste ciclo por tamanho**, não por falta de valor — e o desenho fica registrado aqui
para não ser redescoberto.

A ideia: cruzar a co-mudança do git (que já existe) com as arestas novas. Dois arquivos que
mudam juntos 38 vezes sem um importar o outro são acoplamento **invisível ao código** — é o
caso da rota-por-string. Custa comparar dois conjuntos que já existirão.

Por que não entra agora: o outcome deste spec é *a seção deixar de ser lacuna*, e isso se
entrega sem ele. É também a peça mais independente do conjunto — depende só do grafo
resolvido, que este ciclo produz.

**E é a peça com maior risco de virar a v0.1.1 de novo**, pelo mesmo mecanismo: a co-mudança
vem do `git log`, que devolve caminhos **históricos**. Arquivo renomeado, movido ou apagado
nunca terá aresta de import, logo cairia automático na lista de "acoplamento invisível". Some
os pares não-código (`README.md` + `.env.example`, componente + `.scss`) e os de linguagem sem
extrator, e a seção vira uma lista plausível de lixo. **Quatro filtros, antes de a seção
existir:**

- as **duas** pontas estão em `caminhos_do_projeto` (existem hoje);
- as duas são de extensão **com extrator**, e estão no conjunto cujos imports foram resolvidos;
- a ausência de aresta é checada nas **duas direções**;
- o par **não importa um terceiro arquivo em comum** — dois arquivos que mudam junto porque
  ambos dependem de um terceiro não são acoplamento oculto, são dois dependentes do mesmo.

## Tratamento de erro

| Situação | O que acontece |
|---|---|
| arquivo ilegível (encoding, permissão) | contado como não lido, com o caminho; nunca derruba a varredura |
| linguagem sem extrator | `indisponivel` com motivo, como hoje |
| import relativo que não existe no disco | **pendurado**: contado e exemplificado, nunca aresta |
| `composer.json`/`tsconfig.json` inválido | ignorado em silêncio; a resolução cai na etapa 3 |
| mapeamento declarado apontando para pasta inexistente | descartado; cai na etapa 3 |
| índice com sufixo ambíguo e sem apelido provado | não resolvido, contado |

## Testes

Unit e integração, sem e2e (não há interface). Fixtures pequenos com resposta conhecida, um por
linguagem, incluindo **um projeto Vue com o apelido só no config executável** — é o caso que
motivou o design.

**Provas por mutação obrigatórias** (a lição que esta skill já aprendeu caro: teste verde prova
que o teste roda, não que a guarda funciona):

| Mutação | Teste que precisa cair |
|---|---|
| ambíguo passa a resolver pelo primeiro candidato | o que confere que ambíguo não vira aresta |
| configuração declarada deixa de ser conferida | o que usa config apontando para pasta que não existe |
| `MIN_PROVAS = 1` | o que confere que prefixo com 1 prova não vira apelido |
| base com 4 provas passa a valer | o que confere que prefixo com poucas provas não desempata |
| externo deixa de ser separado | o que confere a taxa de resolução (ela infla) |
| extrator perde `import()` dinâmico | o que confere a aresta rota → tela |
| extrator perde o conteúdo de `.vue` | o que confere import dentro de SFC |
| nome puro passa a tentar o índice | o que confere que um pacote **declarado** não vira aresta (caso real: `server-only` → `tests/helpers/server-only.ts`) |
| a exceção do `baseUrl` deixa de excluir builtin | o que confere que `import fs from 'fs'` não vira aresta para `src/fs.ts` — a mutação do pacote declarado fica verde aqui, porque builtin nunca está em `dependencies` |
| pacote escopado perde o primeiro segmento antes do sufixo | o que confere que `@vue/test-utils` não casa com `src/test-utils/` |
| o piso de 70% é removido | o que confere que linguagem mal resolvida vira lacuna, não ranking |
| a lista de arestas deixa de ser ordenada no fim | o de idempotência **entre processos** |
| o despacho volta a ser por stack detectada | o que usa 4 arquivos `.ts` num projeto PHP |

## Restrições verificáveis

| Restrição | Como o plano checa |
|---|---|
| PHP resolve ≥ 95% dos `use` internos | medido nos dois projetos PHP de calibração |
| JS/TS resolve ≥ 95% dos imports internos (relativo + apelido) | medido nos três projetos JS de calibração, com o denominador escrito |
| nenhum nome puro vira aresta sem `baseUrl` conferido | teste com o caso real do `server-only` |
| abaixo de 70% numa linguagem, a seção dela é lacuna | teste com projeto de resolução baixa |
| nenhuma aresta errada numa amostra de 30 conferidas à mão | task 1 (spike) |
| `resolucao.py` não contém nenhum `if linguagem ==` nem nome de linguagem | teste que lê o arquivo |
| varredura completa em ≤ 60 s num projeto de ~2.000 arquivos | medido. **60 s é o que reprova**; os 5 minutos são o teto que o dono aceita, não a meta |
| mesmo projeto → mesmo `inventory.json`, byte a byte | teste de idempotência **em dois processos** (`subprocess`), senão o seed de hash compartilhado o faz passar com artefato não-determinístico |
| nenhuma afirmação de ausência de dependentes no documento | **teste novo** que roda `PROIBIDAS` sobre o documento MONTADO. A guarda que já existe roda dentro de `_ler_narrativa()`, ou seja, só no texto que o agente escreve — todos os blocos novos são gerados pelo script e passam ao largo dela |

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| sufixo único é evidência, não coincidência | **aresta errada** — o pior modo de falha | **task 1 (spike)**: resolver os imports JS e PHP reais e conferir **30 sorteadas com semente fixa** entre as de procedência `base_provada` e `sufixo_unico`, que são as de maior risco. Semente fixa porque amostra que não se regera não serve de prova |
| nome puro é sempre externo, fora `baseUrl` | perde aresta interna real num projeto que usa import absoluto | contar quantos nomes puros casariam sob um `baseUrl` declarado nos projetos de calibração |
| a inferência de apelido desempata os ambíguos | 13% de um projeto fica sem resolver | **já validado**: 56 de 56 desempatados, 100% de concordância |
| pacote externo nunca casa com arquivo do projeto | taxa de resolução inflada ou aresta errada | **já validado** nos três projetos JS |
| o extrator cobre as formas que existem | arestas somem em silêncio | **já validado**: cinco formas medidas no JS, três no PHP |

A primeira continua aberta e é a única que pode derrubar o desenho — por isso é a task 1.

## Não-objetivos

- **Não** lê rota-como-string, container de injeção, reflexão nem include de template. As cinco
  cegueiras continuam declaradas. (O leitor de convenção de rota vai com o recorte por
  funcionalidade, onde ele é aresta de expansão e não enfeite.)
- **Não** afirma ausência de dependentes — isso não muda com grafo melhor.
- **Não** analisa dependência externa: versão, vulnerabilidade, pacote abandonado. Pacote entra
  só para ser separado do que é interno.
- **Não** faz análise transitiva nem detecta ciclo.
- **Não** cria arquivo de configuração da skill. Projeto que precisa ser configurado para ser
  lido é projeto que a skill não leu.
- **Não** reescreve o `montar.py` nem o `imprimir.py` além dos blocos novos — com uma exceção
  nomeada: o `_dependentes()` é reescrito, porque a lista por símbolo existe só por não haver
  grafo, e manter as duas daria duas respostas para a mesma pergunta.

## Restrição de simplicidade

A menor solução que resolve: **um extrator por linguagem e um resolvedor**. Nada de plugin, de
registro dinâmico, de cache em disco ou de configuração por TOML. O índice de sufixos é um
dicionário em memória, construído uma vez.

## Appetite

Um ciclo de trabalho, no mesmo porte da v0.2.0 (12 a 14 tasks). **O corte já foi feito:** o
"par que muda junto e não se importa" saiu para a continuação, porque o outcome se entrega sem
ele e ele é a peça mais independente. Se ainda assim passar, o próximo corte é o **ranking por
arquivo** — o inventário com o grafo e a taxa já serve ao item B mesmo sem o bloco novo no
documento. O que **não** se corta é o PHP: o extrator dele é o menor dos três, e tirá-lo
economiza pouco.

## MVP vs MLP

**MVP.** O valor é a aresta existir e a taxa ser publicada. Apresentação boa dos novos blocos
é a v0.3.1, não esta.

## Decisões (ADR)

**1. Resolver por evidência, não por configuração.**
*Contexto:* a string do import só vira arquivo com PSR-4, `paths`, apelido de bundler e
workspaces; num projeto real o apelido mora em JavaScript executando.
*Decisão:* resolver casando contra os arquivos que existem; configuração é atalho conferido.
*Alternativas descartadas:* **(a)** ler cada formato de config — exige um leitor por bundler, um
deles sendo JS executável, e vai a zero em projeto incomum; **(b)** executar o config com Node —
executar código de projeto recebido é inaceitável numa skill que promete só ler.
*Consequências:* o apelido que aponta para **fora** da árvore não resolve (nenhum caso nos
projetos de calibração); em compensação, o mecanismo é um só e não envelhece com bundler.

**2. Ambíguo não resolve.**
*Contexto:* dois arquivos terminando no mesmo sufixo.
*Decisão:* não vira aresta; vai para a etapa 4 e, se nem lá, para a contagem.
*Alternativas descartadas:* escolher o mais raso, ou o primeiro em ordem alfabética — as duas
produzem aresta errada silenciosa.
*Consequências:* a taxa de resolução é menor e honesta.

**3. A taxa de resolução entra no documento.**
*Contexto:* uma lista de dependências parece completa mesmo quando metade falhou.
*Decisão:* `resolucao` é seção do inventário e bloco de fato nos dois documentos.
*Alternativas descartadas:* registrar só em log — quem lê o documento não vê o log.
*Consequências:* o documento admite o próprio limite, em número, a cada execução.

**4. O extrator não conhece o sistema de arquivos.**
*Contexto:* a tentação é cada linguagem resolver o próprio import.
*Decisão:* extrator devolve strings; resolvedor é único.
*Alternativas descartadas:* um resolvedor por linguagem — multiplicaria a regra de ambiguidade
e a conferência de configuração por N, e cada cópia envelheceria sozinha.
*Consequências:* uma linguagem com resolução genuinamente diferente (Go com módulos, Java com
classpath) vai precisar de uma exceção explícita, e ela aparecerá como tal.

## Rollout e reversibilidade

Skill local, sem produção e sem dado de cliente. Entra por `make sync` com bump de **minor**; o
caminho de volta é a versão anterior do plugin, que fica no git. O `inventory.json` é
regenerável por definição — nenhuma migração.

## Revisões do spec

- **2026-10-07** — a separação entre pacote escopado e apelido saía de uma heurística de caixa
  da inicial, escrita antes de medir. Medida: `@areas` é um apelido minúsculo com 45
  imports num projeto real, e a heurística perderia as 45 arestas. A regra passou a ser a
  dependência declarada, conferida também para a classe `qualificado`. Afeta as tasks 3 e 6 do
  plano, que já nasceram com a correção.
