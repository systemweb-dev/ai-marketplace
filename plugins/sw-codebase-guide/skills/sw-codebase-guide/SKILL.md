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
| A varredura achou **sub-repositórios** | documentar o conjunto, ou só um deles |
| O inventário saiu **mudo** (sem stack, sem histórico, sem superfície) | seguir assim, ou apontar para outra raiz |
| **No fim** | as perguntas em aberto viram pauta para alguém? |

Para resposta aberta (um caminho, uma raiz diferente), ofereça as opções prováveis e conte com
o campo **"Other"**. A exceção é o usuário descrevendo livremente o que quer — aí ele dirige.

## Garantias

- **Não altera nada do projeto.** Só lê, e só escreve em `docs/project/`.
- **Não avalia qualidade nem aponta bug.** Ela descreve; quem julga é a `sw-code-review`.
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

### 1. Apurar os fatos

```bash
python3 <skill-dir>/scripts/varrer.py --projeto . --out docs/project
```

Grava `docs/project/inventory.json` com oito seções: `stacks`, `arvore`, `historia`, `imports`,
`superficie`, `ambiente`, `mencoes` e `gerado_em_versao`. É determinístico — sem carimbo de
tempo, ordem estável — para o documento dar diff.

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
- **`mencoes`** — grafo textual: onde cada símbolo aparece como texto. É o que pega o
  acoplamento que o import não vê.

### 2. Escrever a interpretação

Leia o `inventory.json` e os **poucos** arquivos que ele aponta como centrais. Não leia o
projeto inteiro: o inventário existe justamente para isso.

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

**README é `declarado`, nunca `fato`.** Se o README discorda do `docker-compose`, mostre os
dois — a divergência é um dos achados mais úteis para quem acabou de receber o projeto.

### 3. Montar o documento

```bash
python3 <skill-dir>/scripts/montar.py --dir docs/project
```

Grava `docs/project/guide.md`. É função pura das duas entradas: mesmos fatos, mesmo documento,
byte a byte.

### 3b. O documento tem o que dizer?

Varrer sem erro **não** quer dizer que a skill apurou alguma coisa. Antes de entregar, olhe o
inventário: nenhuma stack detectada, histórico em lacuna e superfície vazia ao mesmo tempo
costuma significar que a raiz está errada — um diretório acima do projeto, ou um que só tem
`docs/`. Nesse caso **pergunte via `AskUserQuestion`** se segue assim ou aponta para outra
raiz, em vez de entregar um documento que diz "não apurado" três vezes.

Se a varredura achou **sub-repositórios**, pergunte se o guia cobre o conjunto ou só um deles:
num monorepo por justaposição, cada sub-repo costuma ser um sistema diferente, e um guia só
mistura três domínios na mesma página.

### 4. Informar

Diga onde ficou o arquivo, quantos arquivos foram lidos, quais stacks apareceram, e **leia em
voz alta as perguntas em aberto** — elas são a pauta da conversa com quem conhece o sistema, e
são o entregável de maior valor quando o código não diz o propósito.

Feche oferecendo, via `AskUserQuestion`, levar essas perguntas adiante — virar pauta de
reunião, mensagem para o cliente ou issue. O documento sozinho não marca conversa.

## Limites desta versão

- **Grafo de import só para Python** (pelo `ast` da stdlib). Outras stacks aparecem em
  `indisponivel` com o motivo declarado, e o acoplamento delas sai pelo grafo textual.
- **Sem conhecimento humano persistido.** Não há `knowledge.toml` nem `gravar.py`: o que
  alguém confirmar não sobrevive entre execuções — reescrever a interpretação é manual.
- **Sem configuração de stack por TOML.** Manifestos, extensões e convenções de caminho são os
  que estão no código dos módulos; stack de nicho não é reconhecida.
- **Sem recorte por área** (`--area`), **sem HTML e sem PDF** — só o `guide.md`.
- **Sem extração de regra de negócio** — só propósito com fonte textual citada.
