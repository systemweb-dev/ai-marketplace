---
name: sw-codebase-guide
description: Lê um projeto que você acabou de receber e escreve a documentação dele em docs/project/ — como entrar, o que depende do quê e o que o sistema faz, com o nível de confiança de cada afirmação e a lista do que ficou sem resposta.
---

# Codebase Guide — ler um projeto e escrever a documentação dele

Você recebeu um projeto que ninguém da casa conhece. Esta skill varre o código e o histórico e
grava em `docs/project/` um guia que responde **como entrar**, **o que depende do quê** e **o
que o sistema faz** — e termina com as perguntas que ela não conseguiu responder.

**Anuncie no início:** "Estou usando a skill sw-codebase-guide para documentar este projeto."

## Regra: toda decisão é via AskUserQuestion

**Toda pergunta ao usuário usa `AskUserQuestion` (menu clicável) — nunca pergunta em texto
solto, e nunca termine um turno com pergunta escrita.**

Mas **pergunta serve para decisão e autorização, não para suprir leitura que você não fez.**
Não pergunte o que o código responde: qual é a stack, quantos arquivos há, se existe teste,
o que depende do quê. Isso a varredura descobre, e perguntar ao usuário é pedir que ele faça
o trabalho da skill — ainda por cima a quem acabou de receber o projeto e não sabe responder.

| Momento | O que perguntar |
|---|---|
| **Antes de gravar** (obrigatório) | o guia vai para dentro do repositório do projeto — confirmar o caminho, ou gravar fora dele |
| Já existe `guide.md` ali | regerar por cima, ou gravar em outro lugar para comparar |
| O inventário saiu **mudo** (sem stack, sem histórico, sem superfície) | seguir assim, ou apontar para outra raiz |
| **No fim** | as perguntas em aberto viram pauta para alguém? |

Para resposta aberta (um caminho, uma raiz diferente), ofereça as opções prováveis e conte com
o campo **"Other"**. A exceção é o usuário descrevendo livremente o que quer — aí ele dirige.

## Garantias

- **Não altera nada do projeto.** Só lê, e só escreve em `docs/project/`.
- **Avalia com limiar escrito, nunca com nota.** A seção "antes de mexer" opina — onde é mais
  caro errar, que risco se vê, o que parece sem uso — e cada opinião mostra o número que a
  sustenta e o limiar que a decidiu. **Nota não existe**: número único vira meta, e meta vira
  teatro. Bug específico continua sendo trabalho da `sw-code-review`.
- **Nenhum segredo sai.** De cada `.env` o inventário carrega **só os nomes** das variáveis,
  extraídos na origem — não existe caminho pelo qual o valor chegue ao documento.
- **Nunca afirma ausência de dependentes.** O grafo não enxerga injeção de dependência,
  rota como string, reflexão nem template — então "nada depende disso" não existe neste
  documento.
- **Não apurado ≠ não existe.** O que não deu para ler vira lacuna com motivo.

## Fluxo

### 0. Confirmar onde grava — antes de escrever qualquer coisa

O projeto é de terceiro, e esta skill **escreve** nele. Pergunte via `AskUserQuestion` antes:

- **`<projeto>/docs/project/`** — o padrão. É documentação, mora junto do código, e o próximo
  dev acha sozinho. Exige que você possa gravar ali.
- **Fora do repositório** — quando o repositório não é seu, quando você não tem push, ou
  quando é só um teste. O guia sai do mesmo jeito.

Se já houver `guide.md` no destino, pergunte antes de sobrescrever: comparar a versão de hoje
com a de três meses atrás costuma valer mais que a versão nova sozinha.

### 0b. Perguntar o escopo — antes de varrer

A primeira pergunta é **o que documentar**: o projeto inteiro, uma **área** dele (*onde*) ou
uma **funcionalidade** (*o quê*). Num projeto de 630 arquivos as três respostas são documentos
diferentes, e descobrir isso depois custa a varredura toda.

Quem acabou de receber um projeto raramente pergunta por `src/app/(app)` — pergunta pelo
cadastro, pelo faturamento, pelo funil. Ofereça os dois eixos no mesmo menu.

```bash
python3 <skill-dir>/scripts/varrer.py --projeto . --areas
```

Imprime as áreas em stdout e **não grava nada** — é a fase barata: `os.walk` com poda, uma
consulta git limitada por data, e a leitura só das fontes textuais. Meio segundo num projeto de
630 arquivos.

Monte o menu de `AskUserQuestion` com o que ele devolveu: **"o projeto todo"** como primeira
opção, mais as três primeiras áreas, dizendo quantas ficaram de fora e imprimindo a lista
completa antes — assim o dev acha a dele pelo nome e usa o "Other". O campo `ordenado_por` diz
se a ordem veio dos commits recentes ou do número de arquivos, e `commits_recentes` vem
**`null`** quando não houve medição — que não é a mesma coisa que zero commits. O `caminho` é o que vai no
`--area`.

O rótulo é **descritivo** (`funil · pasta · 7 arquivos · 12 commits no último mês`), nunca
**semântico** (`funil · rota do App Router`). Rótulo semântico é justamente a afirmação que a
skill não consegue provar — e aqui ela decidiria o escopo dos dois documentos.

**Esta pergunta absorve a de sub-repositórios**: é a mesma pergunta. Junte-a com a do destino de
gravação, na mesma chamada.

#### O outro eixo: por funcionalidade

```bash
python3 <skill-dir>/scripts/varrer.py --projeto . --funcionalidades
```

Também não grava nada. Devolve os nomes que **o próprio código usa** para mais de uma camada —
`cobranca [controller model service view]`, `funil [action card page]`, `relatorio
[controller middleware]`. A regra é essa: *uma funcionalidade é um nome que aparece em mais de
um papel*. Um mesmo nome em `middleware/`, `services/` e `store/` é fatia vertical; um nome que
aparece num componente e no teste dele é um arquivo com o teste dele — por isso **teste e barril não contam
como papel**, e papel que sozinho só declara área (`middleware` + `rotas`) também não.

Use o `termo` no `--funcionalidade`. O recorte sai em três grupos, e o documento diz quanto é
de cada um:

| Grupo | O que é |
|---|---|
| **núcleo** | os arquivos que levam o nome no caminho |
| **alcance** | o que o núcleo importa e quase ninguém de fora usa |
| **compartilhado** | o que o núcleo importa **e o resto do sistema também** — entra no recorte, com a contagem de quem o importa ao lado |

O terceiro grupo é o que paga o recorte. Medindo um cadastro real, o arquivo mais importante da
fatia era também o mais compartilhado: o helper onde mora a regra do formulário, com **29
importadores de fora**. Deixá-lo de fora perderia a regra; chamá-lo de "parte da funcionalidade"
seria mentira. Ele entra, e o documento diz a conta.

**Termo que pega o projeto inteiro é área, e a skill diz isso.** Núcleo acima de
`TETO_NUCLEO` arquivos sai com o aviso no documento, em vez de entregar 197 arquivos chamando-os
de uma funcionalidade — foi o que o termo mais largo fez no projeto medido: 148 de 760.

**Limite declarado:** a superfície pública de uma funcionalidade só aparece quando o arquivo que
a declara leva o nome dela. Rota declarada num `Rotas.php` de área **não entra** — se
ela importa para o que você está documentando, cite-a como evidência (o `caminhos_do_projeto`
tem o projeto inteiro) e registre o que faltou como `lacuna`.

### 1. Apurar os fatos

```bash
python3 <skill-dir>/scripts/varrer.py --projeto . --out docs/project \
    [--area <caminho> | --funcionalidade <termo>]
```

Grava `docs/project/inventory.json` com estas chaves de primeiro nível: `stacks`, `arvore`,
`historia`, `retrato`, `imports` (que carrega `arestas`, `indisponivel`, `resolucao` e
`barris` **dentro** dela), `superficie`, `ambiente`, `mencoes`, `textos`, `julgamento`,
`escopo`, `caminhos_do_projeto`, `mudanca_por_arquivo` e `gerado_em_versao`. É determinístico — sem carimbo de tempo, ordem estável — para o documento
dar diff.

O que cada seção carrega, e o quanto confiar nela:

- **`stacks`** — um componente por manifesto encontrado (`package.json`, `composer.json`,
  `pyproject.toml`…). A stack que **domina o projeto sem manifesto nenhum** também é detectada,
  por **contagem de extensão**: nesse caso `manifesto` vem `None` e o campo `por` diz como foi
  contada. Diretório de dependência e de build (`node_modules`, `vendor`, `.next`, `target`,
  `coverage`…) é podado antes de qualquer contagem.
- **`arvore`** — caminho, tamanho, linguagem e marca de arquivo gerado.
- **`historia`** — co-mudança do git. Quando a raiz **não é** repositório git, a skill procura
  sub-repositórios **um nível abaixo** (`/projeto/api`, `/projeto/admin`): monorepo por
  justaposição é o formato normal de projeto recebido, e os caminhos saem prefixados pelo
  sub-repo. Sem amostra suficiente, vira lacuna com motivo.
- **`imports`** — `arestas` e `indisponivel`. O grafo de import existe **só para Python** (pelo
  `ast` da stdlib); cada outra stack entra em `indisponivel` **com o motivo escrito**. Quando
  não há nenhuma aresta e há indisponibilidade declarada, o documento diz **"import não
  medido"** em vez de "0 por import" — repetir zero por símbolo trabalha contra a ressalva.
- **`superficie`** — rota, comando, job e migration reconhecidos por **convenção de caminho**.
  É indício, não prova: no documento a seção inteira sai marcada como **dedução**.
- **`ambiente`** — por arquivo `.env`, **os nomes das variáveis e nada mais**. Saber que o
  projeto usa `STRIPE_SECRET_KEY` e `REDIS_URL` é uma das informações mais úteis do documento
  para quem vai subir o ambiente pela primeira vez; o valor nunca é lido para dentro.
- **`mencoes`** — grafo textual: onde cada símbolo aparece como texto. Fica no inventário para
  quem quiser olhar à mão; não entra no documento, porque casa PALAVRA e numa base em
  português devolve `banco` e `caminho` às centenas sem haver relação de código.
- **`imports.resolucao`** — por linguagem, sete números: `relativos`, `externos`, `sufixo_unico`,
  `base_provada`, `config_conferida`, `ambiguos`, `pendurados` e `nao_resolvidos`. A taxa é
  `(relativos + sufixo_unico + base_provada + config_conferida)` sobre tudo isso **menos
  `externos`**; denominador zero é "não medido", nunca 0%.
- **`retrato`** — quantas pessoas commitaram, quantos commits, idade e semanas parado. Sem git
  vem tudo `None` com a lacuna dizendo por quê: **`0 autores` se lê como "ninguém mexe nisso"**,
  e `1` como "uma pessoa só". Num monorepo por justaposição o retrato é do CONJUNTO — autores é
  a união (quem conhece o sistema, não um pedaço dele) — e a lacuna diz de onde veio.
- **`textos`** — a única seção que carrega **conteúdo**, e por isso a única redigida linha a
  linha. São README, `CLAUDE.md`, ADR, `docs/` e tradução, **em qualquer profundidade** (num
  monorepo o README de cada aplicação não está na raiz) e também em pasta podada da árvore
  (`.claude/`, `.github/`), onde mora a única documentação de muitos projetos. **Não** entra
  dossiê de trabalho — `docs/specs/…/plan.md` descreve uma tarefa passada, não o sistema.
  A seção tem **teto** (32 arquivos, 384 KB): o que não coube continua na lista com
  `omitido` e o motivo, para você abrir à mão — e citá-lo no `trecho` é recusado com essa
  mensagem, não com "o trecho não aparece".
- **`julgamento`** — a única seção que **opina**, e a última a ser calculada, porque lê todas
  as outras. Quatro recortes do que já foi medido, cada um com limiar escrito: `perigo` (os
  três sinais juntos — muitos dependentes, muitos commits, nenhum teste de mesmo nome e mesma
  extensão), `sem_alcance` (arquivo que import nenhum alcança e que ninguém toca há mais de um
  ano, **só** nas linguagens acima do piso de 70%, e sem os papéis que o framework instancia
  por convenção), `risco` (o que se vê sem rede: `.env` **versionado**, credencial que o
  `.env.example` não declara) e `dossie` (os números da decisão "vale manter", **sem o
  veredito** — ele depende do custo de reescrita e do que o negócio depende, e nenhum dos dois
  está no código).
- **`mudanca_por_arquivo`** — a data da última alteração de cada arquivo. Existe para
  envelhecer resposta humana: respondida em outubro, arquivo mexido em dezembro, a pergunta
  pode ter voltado a valer. Invalidação por **evidência**, não por cronômetro.
- **`escopo`** e **`caminhos_do_projeto`** — o recorte usado e a lista completa de caminhos do
  projeto **inteiro**. A segunda existe porque percentual de teste e autoria são do projeto,
  não da área: um `0% é teste` calculado na área recortada mentia num projeto com 44%.

### 2. Escrever a interpretação

Leia o `inventory.json` e os **poucos** arquivos que ele mais destaca. Onde olhar, em ordem:
`julgamento.perigo` (os que mais gente importa e que mais mudam), `textos` (o que alguém
escreveu sobre o sistema), `historia.co_mudanca` (o que anda junto) e `superficie` (por onde
se entra). Um agente que seguiu este documento travou aqui: a frase dizia "os arquivos que o
inventário aponta como centrais", e **nenhum campo se chama central**. Não leia o
projeto inteiro: o inventário existe justamente para isso.

Leia também o `knowledge.toml`, se existir: ele traz o que alguém já respondeu, e
repetir uma pergunta respondida é como um documento gerado perde credibilidade.

Escreva `docs/project/interpretation.toml`. O formato é fechado — você preenche campos, não
escreve prosa:

```toml
[[afirmacao]]
secao = "o-que-faz"          # como-entrar | depende-de | o-que-faz | superficie
texto = "Pedido só fecha com pagamento confirmado"
nivel = "deducao"            # fato | declarado | deducao | lacuna
evidencia = ["app/Pedido.php:88"]
motivo = ""                  # obrigatório quando nivel = "lacuna"
```

**Afirmação sem evidência e sem ser lacuna é recusada** pelo `montar.py`. Isso é proposital: é
a guarda que impede prosa plausível de entrar sem lastro. Lacuna sem motivo também é recusada,
e seção ou nível fora da lista fecha o processo com erro.

**Escreva nas quatro seções.** Cada uma tem consumidor no documento, e a que você deixar vazia
aparece lá dizendo que ninguém a interpretou.

**Propósito e público só com fonte textual.** Se não houver README, ADR, mensagem de commit ou
texto de tela dizendo para que o sistema serve, **não afirme** — escreva como `lacuna`, e ela
vira pergunta em aberto. Deduzir propósito de rotas e modelos produz prosa plausível e vazia,
que quem recebe leva ao cliente como se fosse apurada.

**Um bloco de `percurso` é um PASSO, não um parágrafo.** Cada bloco declara em que camada
ele roda, e o documento desenha a trilha:

```toml
[[narrativa]]
parte = "percurso"
ordem = 3
onde = "servidor"       # navegador · servidor · fila · banco · externo
texto = "Antes do controller, o middleware do pedido decide a regra do desconto"
evidencia = ["api/middleware/Pedidos/PedidoMiddleware.php:118"]
saltos = []
```

A camada é **fechada** nessas cinco: `onde = "na regra de negócio"` é recusado, com a lista na
mensagem. Camada livre reabriria a prosa pela porta dos fundos, e a trilha não teria onde pôr
o passo.

**A fronteira não se declara — ela é derivada de `onde` mudar entre dois passos.** O documento
imprime `navegador → servidor` entre eles, e nada mais: declarar abriria a porta para afirmar
uma travessia que os dados não mostram. Atravessar aplicação é o evento mais caro para quem
acabou de receber o projeto, e era o que a prosa corrida escondia melhor — ficava numa oração
subordinada no meio do parágrafo.

**O arquivo de cada passo aparece na página.** A `evidencia` do percurso era conferida contra
o projeto, linha por linha, e nunca impressa: quem lia recebia a história e ia caçar os
arquivos no relatório técnico. Escreva o caminho mais preciso que tiver — `arquivo.php:118`
vale muito mais que `arquivo.php`, porque é o que o leitor vai abrir.

**O percurso tem orçamento: no máximo 10 arquivos abertos.** O que não resolver vira
`saltos`, e `saltos = []` é afirmação forte — significa "segui do clique até o banco sem
buraco". O campo é obrigatório justamente para "não tentei" não se confundir com "segui
inteiro". O salto sai **no passo a que pertence**, nunca numa nota de rodapé.

**O percurso é obrigatório como as outras três partes — inclusive em "o projeto todo".** A
regra anterior dizia para só escrevê-lo com escopo recortado, e isso brigava com a tabela
acima: obedecer gerava no documento a frase *"a interpretação não escreveu esta parte"*, que é
o defeito que esta skill existe para evitar. O que muda sem recorte é a AMBIÇÃO: escolha **uma**
funcionalidade representativa e diga qual é, em vez de tentar cobrir o sistema.

**Cuidado com o orçamento.** Em "o projeto todo" de um legado, rastrear é
adivinhar onde a execução começa — e a skill não detecta entrypoint.

#### O bloco `[[narrativa]]` — o documento humano

As `[[afirmacao]]` alimentam o relatório técnico. O `leia-me.md` e o `leia-me.html` vêm de
outro bloco, em **prosa**, dividido em quatro partes:

```toml
[[narrativa]]
parte = "o-que-e"            # o-que-e | percurso | mapa | orientacoes
ordem = 1                    # inteiro; governa a ordem dentro da parte
texto = "É um sistema de pedidos usado por uma rede de padarias"
trecho = "Sistema de pedidos para padarias, instalação única por cliente"
fonte = "CLAUDE.md"          # tem que ser fonte textual reconhecida
evidencia = ["CLAUDE.md"]
```

| Parte | Título no documento | Campos obrigatórios |
|---|---|---|
| `o-que-e` | O que o produto faz | `texto` · `evidencia` — e o **primeiro** bloco também `trecho` · `fonte` |
| `percurso` | O percurso de uma funcionalidade | `texto` · `evidencia` · **`saltos`** · **`onde`** |
| `mapa` | Onde ficam as coisas | `texto` · `evidencia` |
| `orientacoes` | Para mexer | `texto` · `evidencia` |

**Três guardas recusam o `montar.py` inteiro**, e nenhum dos dois documentos é escrito:

1. **Frase de ausência.** Prosa livre expõe pela primeira vez a garantia mais forte da skill, e
   o teste de saída não bastava: a recusa é do parser. "a pasta não é usada" para o processo.
2. **Trecho literal.** O `trecho` do `o-que-e` tem que aparecer **de fato** na `fonte`, com
   espaço normalizado (README quebrado em 80 colunas faz qualquer frase atravessar linha). É a
   guarda que mais importa: o pior modo de falha dessa parte não é falsidade, é ser fluente,
   verdadeira e **inútil** — *"o sistema gerencia clientes, com um funil de vendas"* passa em
   qualquer conferência e o dev já sabia disso lendo o nome das pastas.

   **Só o primeiro bloco precisa citar.** A guarda confere que a citação *existe* na fonte,
   nunca que ela *sustenta* a frase — e exigir citação de todo bloco empurra você a pendurar
   um trecho verdadeiro e sem relação embaixo do parágrafo, que na tela aparece com cara de
   evidência. A frase mais valiosa costuma ser dedução de evidências convergentes de código
   (rota + coluna + job + middleware): escreva-a **sem** `trecho`, com a `evidencia` que a
   sustenta.
3. **Caminho inventado.** Toda `evidencia` tem que existir. Quatro formas valem: `app/x.py`,
   `app/x.py:88`, `app/` e `commit 3c5aabb`.

**README é `declarado`, nunca `fato`.** Se o README discorda do `docker-compose`, mostre os
dois — a divergência é um dos achados mais úteis para quem acabou de receber o projeto.

### 3. Montar o documento

```bash
python3 <skill-dir>/scripts/montar.py --dir docs/project
```

Grava **dois** arquivos: `guide.md`, o relatório técnico com a evidência de cada afirmação, e
`leia-me.md`, o documento humano em quatro partes. Os dois são função pura das mesmas entradas:
mesmos fatos, mesmo documento, byte a byte — e a recusa de qualquer guarda não escreve nenhum
dos dois, para não deixar um novo ao lado de um velho.

### 3b. O documento tem o que dizer?

Varrer sem erro **não** quer dizer que a skill apurou alguma coisa. Antes de entregar, olhe o
inventário: nenhuma stack detectada, histórico em lacuna e superfície vazia ao mesmo tempo
costuma significar que a raiz está errada — um diretório acima do projeto, ou um que só tem
`docs/`. Nesse caso **pergunte via `AskUserQuestion`** se segue assim ou aponta para outra
raiz, em vez de entregar um documento que diz "não apurado" três vezes.

A pergunta sobre sub-repositórios **não se repete aqui**: ela é a pergunta de escopo do passo
0b, e num monorepo as áreas do menu já são os sub-repositórios. Perguntar de novo é perguntar
duas vezes a mesma coisa num terço dos projetos.

### 4. Gerar o documento humano — HTML e, se pedirem, PDF

```bash
python3 <skill-dir>/scripts/imprimir.py --dir docs/project [--estilo escuro|brutalista] [--pdf]
```

Grava `leia-me.html`: o mesmo material do `guide.md`, em forma de ler e de mandar. **Não é
conversão do Markdown** — é um emissor irmão, sobre o mesmo inventário, porque hierarquia de
três níveis, barras, cartões de retrato e etiqueta de confiança não cabem em Markdown.

O que o desenho carrega, e por quê:

- **três níveis de bloco** — o que é espinha (retrato, o que o sistema faz, as perguntas em
  aberto) tem título grande; o apoio fica menor e discreto. Sem isso todo bloco pesa igual e o
  olho não tem onde pousar primeiro;
- **uma pergunta sob cada título** — *o que quebra se você mudar uma coluna* orienta; "quem
  depende disto" só nomeia;
- **legenda dos níveis de confiança** na abertura — a etiqueta é o dispositivo mais importante
  do documento, e sem a legenda ela é decoração;
- **mapa de leitura por intenção**, não sumário.

Dois estilos, à escolha de quem recebe: `escuro` (confortável em tela, gasta tinta no papel) e
`brutalista` (imprime muito bem, identidade forte, não parece documento sério para todo mundo).

É **self-contained**: as três fontes vão em base64, não há uma única requisição de rede, e por
isso o PDF é gerado offline. **Ofereça o PDF no fim, via `AskUserQuestion`** — ele custa alguns
segundos de Chromium e nem toda rodada vira documento para enviar. Sem Chromium na máquina, a
skill entrega o HTML e avisa: não é falha dela.

### 5. Informar

Diga onde ficou o arquivo, quantos arquivos foram lidos, quais stacks apareceram, e **leia em
voz alta as perguntas em aberto** — elas são a pauta da conversa com quem conhece o sistema, e
são o entregável de maior valor quando o código não diz o propósito.

Feche oferecendo, via `AskUserQuestion`, levar essas perguntas adiante — virar pauta de
reunião, mensagem para o cliente ou issue. O documento sozinho não marca conversa.

## Limites desta versão

- **Grafo de import para Python, PHP, JavaScript, TypeScript e Vue.** A resolução é por
  **evidência** — o arquivo que existe —, não pela configuração declarada: num projeto real os
  apelidos moram num `vue.config.js`, que é JavaScript executando. A configuração entra só como
  atalho **conferido contra o disco**. Linguagem com sistema de módulos que esta versão não
  resolve aparece em `indisponivel` com o motivo.
- **Cada execução publica a própria taxa de resolução**, em sete números absolutos. Abaixo de
  **70%** resolvido numa linguagem, a seção de dependências dela volta a ser lacuna: ranking
  sobre metade do grafo tem cara de fato, e é o erro que a v0.1.1 custou.
- **O grafo continua sem ver** injeção de dependência, rota como string, reflexão e include de
  template. Grafo melhor não torna verdadeiro o que ele não vê, e a skill continua **nunca**
  afirmando ausência de dependentes.
- **O conhecimento humano sobrevive à regeração.** O `knowledge.toml` é o **único** arquivo
  que não se regenera: inventário, interpretação e documento se refazem, mas o que está ali só
  existe porque alguém respondeu. Grave com
  `python3 <skill-dir>/scripts/gravar.py --dir docs/project --sobre <caminho> --pergunta "…"
  --resposta "…" --quem <nome>`. O que foi respondido **sai** da lista de perguntas e passa a
  constar em "já perguntamos", com nome e data — e volta a ser destacado se o arquivo mudar
  depois da resposta.
- **O recorte tem dois eixos: `--area` (onde) e `--funcionalidade` (o quê).** O segundo acha a
  funcionalidade pelo vocabulário que o próprio código usa, e por isso **ele só enxerga o que
  tem nome**: funcionalidade cujos arquivos não compartilham palavra nenhuma no caminho não
  aparece no menu e não se recorta. O menu sai curto num projeto que nomeia por área em vez de
  por fatia — isso é retrato do código, não falha da varredura, e dizer isso vale mais que
  encher o menu.
- **Sem configuração de stack por TOML.** Manifestos, extensões e convenções de caminho são os
  que estão no código dos módulos; stack de nicho não é reconhecida.
- **Sem extração de regra de negócio** — só propósito com fonte textual citada.
