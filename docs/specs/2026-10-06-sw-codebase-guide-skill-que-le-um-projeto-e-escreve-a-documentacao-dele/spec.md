---
titulo: sw-codebase-guide: skill que le um projeto e escreve a documentacao dele
slug: 2026-10-06-sw-codebase-guide-skill-que-le-um-projeto-e-escreve-a-documentacao-dele
criado: 2026-10-06
estado: concluido
---

# sw-codebase-guide — skill que lê um projeto e escreve a documentação dele

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `plan.md` é o passo a
> passo de execução; `referencias/` guarda o material de apoio.

## Objetivo & outcome

Encurtar o tempo entre receber um projeto de terceiro e conseguir mexer nele sem medo.

**Outcome:** o dev responde duas perguntas sem abrir o código — *"o que quebra se eu mexer
aqui?"* e *"o que este sistema faz?"* — e sai com a **pauta** do que precisa perguntar a quem
conhece o sistema.

A skill aponta para um repositório, varre código e histórico, e grava em `docs/project/` um
guia em Markdown. Ela **descreve**; não julga, não roda, não altera.

## Exploração & decisões

**Problema enquadrado.** Uma consultoria recebe projetos que ninguém da casa conhece. As duas
dores confirmadas pelo dono: *onde mexer sem quebrar* e *o que o sistema faz*. As duas têm
naturezas opostas — a primeira o código responde com precisão, a segunda ele apenas sugere.

**Suposição derrubada.** O requisito original era "a skill precisa fazer várias
`AskUserQuestion` para entender o projeto". Não sobrevive à pergunta *"quem responde?"*: quem
roda a skill é exatamente quem acabou de receber o projeto. A skill passa a **deduzir e
marcar**; pergunta só escopo e formato. O princípio já existe na casa — *"nunca pergunte o que
dá para descobrir sozinho; pergunta serve para decisão e autorização"*. Vale a ressalva: há
coisas que o dev **sabe** e custam uma pergunta (qual é o alvo de deploy, qual destes três
diretórios está morto); a regra é não perguntar o que o código responde, não é nunca perguntar.

**Ângulos levantados e descartados:**
- *Agente lê e escreve direto* — barato, mas estoura contexto em projeto grande, não é
  reprodutível e não separa fato de suposição.
- *Entrevistar o dev* — derrubado acima.
- *Modo dedicado de migração de stack* — descartado por YAGNI; a informação que migração
  precisa é a mesma da seção "Superfície pública", que se justifica sozinha pelo onboarding.

**Direção escolhida.** Varredura determinística apura os fatos; o agente escreve a
interpretação num artefato separado; um script monta o documento juntando as fontes com
precedência explícita.

## Arquitetura

```
scripts/
  varrer.py        →  inventory.json        fatos, determinístico e regenerável
  montar.py        →  guide.md [.html .pdf] junta inventário + interpretação + conhecimento
  gravar.py        →  knowledge.toml        registra o que humano confirmou
  lib/
    stacks.py      — detecta as stacks pelos manifestos
    arvore.py      — arquivos, tamanho, linguagem, o que é gerado
    imports.py     — grafo de dependências (nativo primeiro, regex como queda)
    textual.py     — grafo textual: menção ao símbolo em qualquer arquivo
    historia.py    — git: co-mudança, idade, concentração
    entradas.py    — rotas, comandos, jobs, consumidores de fila
    dados.py       — entidades, migrations, relacionamentos
    regras.py      — regra verificável: validação, constraint, enum, estado, cron, retry
    redact.py      — redação de segredo e dado pessoal
references/
  stacks/<nome>.toml   — onde cada stack declara rota, modelo, teste, resolução de import
assets/report-template/
tests/fixtures/<projeto-exemplo>/
```

**Três artefatos, três donos — e um escritor cada.** É o que mantém o inventário determinístico
e o diff legível:

| Arquivo | Quem escreve | Regenerável |
|---|---|---|
| `inventory.json` | `varrer.py` | sim, descartável |
| `interpretation.toml` | o agente | sim, mas preserva o que não mudou |
| `knowledge.toml` | humano, via `gravar.py` | **não** — é o único com conteúdo insubstituível |

`montar.py` junta os três com precedência explícita, e o nível de confiança é **propriedade do
dado**, não convenção de prosa — é o que os testes conseguem afirmar.

O `interpretation.toml` é o contrato entre um escritor não-determinístico (o agente) e um parser,
então o formato é fixo e fechado — o agente preenche campos, não escreve prosa livre:

```toml
[[afirmacao]]
secao = "o-que-faz"              # como-entrar | depende-de | o-que-faz | superficie
texto = "O módulo fiscal calcula ICMS por estado"
nivel = "deducao"                # fato | declarado | deducao | lacuna
evidencia = ["app/Fiscal/Icms.php:88", "app/Fiscal/Icms.php:140"]
fato_id = "regra:icms-por-uf"    # id do fato no inventory.json, quando existir
motivo = ""                      # obrigatório quando nivel = "lacuna"
```

Afirmação sem `evidencia` e com `nivel` diferente de `lacuna` é **recusada** por `montar.py`:
é a guarda que impede prosa plausível de entrar sem lastro.

**Piso universal, profundidade por stack.** A skill nunca recusa um projeto. Esta é a lista
canônica — **o que o piso entrega sem nenhum TOML de stack**:

| No piso | Como |
|---|---|
| stacks detectadas | presença de manifesto (`package.json`, `composer.json`, `go.mod`…) |
| árvore: arquivo, tamanho, linguagem, o que é gerado | extensão e caminho |
| histórico: co-mudança, idade, concentração | git |
| **grafo textual** | o símbolo procurado como texto em todo o repositório |
| **grafo de import** | só quando a ferramenta nativa da linguagem existe na máquina |
| superfície por convenção de caminho | pastas `routes/`, `controllers/`, `migrations/` — marcada como **dedução**, não fato |
| propósito com fonte textual | README, ADR, commit, locale — é universal, não depende de stack |
| perguntas em aberto | sempre |

**Exige TOML da stack** — e, sem ele, aparece como lacuna com motivo: rota precisa, entidade,
padrão de teste, **regra verificável** e o **caminho ponta a ponta**.

> O caminho ponta a ponta **não está no piso**. Ele atravessa middleware, container e ORM, que é
> conhecimento de stack por definição. Sem TOML, a seção "Como entrar" sai sem ele, dizendo por
> quê — não sai com um caminho pela metade.

**A regra "dois sinais cruzados" vale quando há dois sinais.** Só com o grafo textual, a
afirmação sai como "7 menções textuais; grafo de import indisponível — `<motivo>`". O que nunca
muda, com um sinal ou com dois, é a proibição de afirmar ausência.

**Qual stack ganha o primeiro TOML:** a do primeiro projeto real em que a skill rodar. Escrever
TOML contra uma stack hipotética é generalizar antes de ver um caso.

**Projeto poliglota é o caso normal.** `/web` com `package.json` e `/api` com `composer.json`
são dois componentes, cada um com sua stack. A fronteira entre eles ganha destaque próprio: é
onde mais se quebra coisa sem perceber, e é onde nenhum dos dois grafos enxerga.

## O documento

Quatro seções, em ordem de certeza decrescente — quem lê sabe onde pisar firme.

**1. Como entrar.** Stacks detectadas, como sobe, os arquivos que importam, e um caminho ponta
a ponta de uma requisição até o banco.

> O caminho ponta a ponta é a afirmação mais difícil do documento: atravessa middleware,
> container e ORM, que é a mágica que nenhum grafo segue. Então ele **mostra os saltos que não
> resolveu**, explicitamente ("daqui o container resolve a implementação — não rastreado"), ou
> escolhe a rota cujo encadeamento fechou inteiro e diz que foi por isso. Caminho com salto
> escondido numa seção de alta certeza é o erro mais caro que a skill pode cometer.

**2. O que depende do quê.** Módulos, dependentes, co-mudança, concentração de risco.

**3. O que o sistema faz.** Duas partes com naturezas diferentes, e elas **não se misturam**:
- **Regras verificáveis** — validação, constraint de banco, enum, máquina de estados, política
  de autorização, limiar em constante nomeada, cron, retry de fila. Saem do código com
  arquivo:linha. É quase fato.
- **Propósito e público** — só é afirmado quando existe **texto humano citado como fonte**:
  README, ADR, mensagem de commit, issue, texto de tela ou arquivo de tradução. Sem fonte
  textual, propósito **não é afirmado**: vira pergunta em aberto.

**4. Superfície pública.** Rotas, comandos, jobs, consumidores de fila, tabelas.

**Fecha com: perguntas em aberto.** O que não deu para apurar, em forma de pauta para levar a
quem conhece o sistema. Para a dor *"o que o sistema faz"*, esta é provavelmente a seção de
maior valor — ela admite o que a skill não sabe em vez de preencher com prosa plausível.

## Marcação de confiança

Quatro níveis, mais um selo ortogonal:

| Nível | O que é |
|---|---|
| **fato** | medido pela varredura — "3 stacks: PHP 8.1, Node 18, Python 3.9" |
| **declarado** | humano escreveu antes, com citação — o README, um ADR |
| **dedução** | inferida de padrão, com a evidência junto |
| **lacuna** | não deu para apurar, **com motivo** |

**`confirmado · <fonte>`** é selo, não nível: marca o que veio do `knowledge.toml`.

**README é `declarado`, nunca `fato`.** README de projeto herdado é a fonte mais provável de
falsidade confiante. "Como sobe" lido do README só vira fato depois de cruzar com compose,
scripts ou CI — e a **divergência entre o que o README diz e o que o compose faz** é, por si,
um dos achados mais úteis para quem acabou de receber o projeto. O documento mostra as duas
versões quando elas discordam.

**Lacuna nunca vira afirmação negativa.** "Não encontrei teste em `api/`" não é "não há teste".

## O grafo de dependências

É a decisão mais arriscada do design, e o perfil de erro do regex é assimétrico — cai todo no
lado ruim. Ele não vê injeção de dependência, autowiring, reflexão, `import()` dinâmico, rota
como string (`"UserController@show"`), facade, annotation, event bus, include de template,
acoplamento por SQL e wiring por config. Em projeto legado com framework pesado — o alvo
declarado desta skill — **isso é a maior parte do acoplamento**.

Três consequências, todas obrigatórias:

1. **A skill nunca afirma ausência de dependentes.** Não existe "nada depende disso". Existe
   "2 dependentes por import, 7 menções textuais", com a lista do que o grafo não enxerga
   anexada à própria afirmação.
2. **Dois sinais, sempre cruzados.** Ao grafo de import soma-se o **grafo textual**: o nome do
   símbolo, classe ou arquivo procurado como texto em todo o repositório — config, template,
   locale, YAML, SQL. O erro dele é falso positivo, que aqui é o lado seguro, e ele pega
   `UserController` no `routes.php` que o import jamais veria.
3. **Ferramenta nativa primeiro, regex como queda.** O `ast` da stdlib do Python,
   `tsc --listFiles`, `go list`, `php -l`, e o JSON dos manifestos. Resolver a *string* do
   import em *arquivo* exige `paths` do tsconfig, alias de bundler, PSR-4 do composer,
   workspaces e barrel `index.ts` — sem isso as arestas ficam penduradas e o grafo perde nó em
   silêncio. Os manifestos de mapeamento são entrada de primeira classe.

> "Não roda nada" significa **não altera nada**. Executar parser que já existe na máquina,
> em modo de leitura, é permitido e é o que mantém o grafo honesto.

## Histórico do git — o caso normal é não ter

Consultoria que recebe projeto de terceiro recebe zip ou `initial import`. Sem histórico,
co-mudança e concentração de risco **zeram** — e a seção não pode sumir em silêncio, porque
omissão se lê como "nada muda junto". Vira lacuna com motivo.

Com histórico, quatro cuidados que separam sinal de ruído:
- **amostra mínima declarada** — abaixo de **50 commits** a co-mudança sai como lacuna, não como
  número; acima, o documento diz de quantos commits ela saiu;
- **descartar commit que toque mais de 50 arquivos** — reformat, lint e import em massa
  envenenam a co-mudança;
- **`--follow` / `-M`** para não perder o arquivo renomeado;
- **atenção a clone shallow, squash-merge e `vendor/` commitado.**

Sem histórico, a concentração de risco é substituída por sinais estáticos — fan-in do grafo,
tamanho do arquivo, número de stacks que o tocam, ausência de teste — e o documento diz que a
substituição aconteceu.

## knowledge.toml — conhecimento humano com âncora

O documento é commitado e regenerado, então correção humana seria apagada na segunda execução.
O conhecimento humano mora fora do gerado:

```toml
[[conhecimento]]
texto = "O módulo fiscal implementa regra de ICMS de 4 estados; não mexer sem o contador"
fonte = "ex-mantenedor, e-mail de 2026-09-30"
data = 2026-10-06
ancora = "app/Fiscal/"          # caminho, símbolo ou id de fato do inventário
```

**A âncora é o que impede o conhecimento de sobreviver ao código que ele descrevia.** Humano
confirma algo sobre o módulo X; seis meses depois X foi reescrito, e sem âncora o gerador
continuaria emitindo a frase com selo `[confirmado]` — pior que a dedução que ela substituiu,
porque confirmado ganha de tudo.

| Na regeneração | O que acontece |
|---|---|
| âncora intacta | entra no corpo com `[confirmado · fonte]` |
| âncora mudou | entra marcada como possivelmente desatualizada |
| âncora sumiu | sai do corpo e vai para **"conhecimento a revalidar"** |

**Conhecimento humano sobrescreve interpretação, nunca fato medido.** Se contradiz um fato, o
documento mostra os dois e sinaliza o conflito — não escolhe sozinho.

**`gravar.py` é parte do produto, não conveniência.** O ciclo *perguntas em aberto → conversa
com o cliente → conhecimento gravado → regenera* é o que faz a skill melhorar com o uso. Se o
dev tiver que editar TOML à mão com campo `fonte` e âncora, o arquivo fica vazio e a camada
confirmada vira peso morto. No fim de cada rodada a skill oferece: *"as perguntas em aberto
viraram respostas? grava"*.

## Segredo e dado pessoal

A varredura lê `.env`, config e compose; o guia cita arquivo:linha; e o documento é commitado
no repositório do cliente. Sem isso explícito, a skill vaza credencial e PII por desenho.

- **Nunca imprime valor** de `.env`, secret ou variável que case com padrão de segredo —
  apenas a **chave**.
- **Nunca imprime linha** que case com padrão de credencial, token, chave privada ou string de
  conexão.
- **Pula** `vendor/`, `node_modules/`, `.git/`, build e artefato gerado, com teto de tamanho
  por arquivo.
- Vale também para o que entra no **contexto do agente**: o que não pode sair no documento não
  é lido para o contexto.

## Escopo na entrada

Projeto todo, ou uma área: `--area pagamento`.

A rodada com recorte escreve em **arquivo próprio** (`docs/project/area-<nome>.md`) — o guia do
projeto todo nunca corre risco de ser apagado por uma rodada parcial.

O recorte casa contra caminho, símbolo e nome de rota. A skill **mostra quantos nós casaram e
por qual critério**, e pergunta quando o casamento for suspeito de pequeno — o caso comum é o
domínio estar em inglês no código e o usuário ter digitado em português, o que devolveria um
recorte quase vazio parecendo dizer que a área não existe.

## Onde grava

`docs/project/`, commitado no repositório do projeto — é documentação, e documentação mora
junto do código para o próximo dev achar sozinho. Isso só se sustenta com a redação da seção
anterior, que é obrigatória, não opcional.

```
docs/project/
  inventory.json          fatos
  interpretation.toml     o que o agente escreveu
  knowledge.toml          o que humano confirmou
  guide.md                o documento
  guide.html              sob demanda
  area-<nome>.md          rodada com recorte
```

Markdown é o primário porque vai ser commitado e precisa dar **diff** — daqui a seis meses o
valor está em ver *o que mudou no entendimento*.

## Não-objetivos

- **Não avalia qualidade nem aponta bug.** Misturar isso faria o cliente ler o documento como
  crítica ao trabalho de quem veio antes.
- **Não desenha diagrama.** Pode sugerir gerar um.
- **Não roda a aplicação, não instala dependência, não altera arquivo do projeto.**
- **Não substitui a conversa com o cliente** — gera a pauta dela.
- **Não faz migração de stack**, e não há modo dedicado a ela. A seção "Superfície pública" se
  justifica sozinha pelo onboarding; justificativa que aponta para fora do escopo é semente de
  scope creep.
- **Não tenta afirmar propósito sem fonte textual.**

## Restrição de simplicidade

A menor solução que resolve: **um** `guide.md` por projeto, **quatro** níveis de confiança,
**três** artefatos com um escritor cada. Não construir por ora: modo de migração, diagrama,
comparação entre execuções, interface web, análise de performance ou segurança.

## Appetite

Duas a três semanas até rodar num projeto real recebido. O corte, se estourar, é a profundidade
por stack — o piso universal e as seções 1, 2 e 4 ficam; a camada 3 encolhe para só regras
verificáveis, sem propósito.

## MVP vs MLP — e o corte em dois planos

**MVP.** O critério é descobrir rápido se a camada 3 se sustenta. Documento bonito não importa
agora; documento honesto importa. Nove módulos e três scripts não cabem num plano só, então o
corte é declarado aqui e não fica para a execução decidir:

**Spike, antes de qualquer plano.** Extrair regra verificável de um projeto real já recebido,
com script descartável, e conferir à mão quantas saíram certas. É a suposição de maior risco: se
a precisão não for útil, a parte de regras morre e a camada 3 vira só propósito-com-fonte e
perguntas em aberto. Produto do spike: um número e uma decisão, não código de produção. A saída
vai para `referencias/`.

**Plano 1 — o piso que já serve.**
`varrer.py` · `montar.py` só em Markdown · `lib/{stacks,arvore,textual,historia,redact}.py` ·
`imports.py` apenas no caminho de ferramenta nativa · `inventory.json` · `interpretation.toml` ·
seções 1, 2 e 4 na profundidade do piso · perguntas em aberto · redação.
Entregue isso, a skill já roda em qualquer projeto recebido e produz documento útil.

**Plano 2 — o que o uso real justificar.**
`knowledge.toml` com âncora · `gravar.py` · `references/stacks/<primeira>.toml` · `regras.py` ·
caminho ponta a ponta · `dados.py` · `--area` · `guide.html` e PDF.

**`guide.html` e PDF não são v1.** O `guide.md` precisa provar valor num projeto real antes de
ganhar embalagem — e `assets/report-template/` só existe no Plano 2.

## Decisões

**Deduzir em vez de entrevistar.**
*Contexto:* o requisito original pedia várias `AskUserQuestion`. *Decisão:* a skill deduz e
marca; pergunta só escopo e formato. *Alternativas descartadas:* entrevistar o dev (ele não
sabe — é por isso que roda a skill); gerar a lista para o cliente responder antes (bloqueia a
primeira rodada). *Consequências:* o valor depende da qualidade da marcação de confiança, e as
"perguntas em aberto" viram entregável de primeira classe.

**Propósito só com fonte textual.**
*Contexto:* deduzir propósito de rotas e modelos produz prosa plausível e vazia, que o
consultor leva ao cliente como se fosse apurada. *Decisão:* propósito só é afirmado citando
texto humano; sem isso, vira pergunta. *Alternativas descartadas:* afirmar com confiança
"baixa" — a camada inteira viraria dedução e o olho pararia de ver a marca. *Consequências:* a
camada 3 encolhe e a seção de perguntas cresce. É o resultado honesto.

**Dois sinais no grafo, e nunca afirmar ausência.**
*Contexto:* dependência reversa com regex erra para o lado perigoso, e "nada depende disso" é
o dano que a skill existe para evitar. *Decisão:* import + grafo textual, cruzados; ausência
nunca é afirmada; nativo antes de regex. *Alternativas descartadas:* só import (falso negativo
no lado fatal); só textual (ruído demais). *Consequências:* mais ruído e mais trabalho, em
troca do único erro que não dá para aceitar.

**Três artefatos, um escritor cada.**
*Contexto:* agente e script escrevendo o mesmo JSON quebra determinismo, diff e testabilidade.
*Decisão:* `inventory.json` (varredura) · `interpretation.toml` (agente) · `knowledge.toml`
(humano). *Alternativas descartadas:* arquivo único com merge. *Consequências:* mais arquivos,
e a confiança vira propriedade de dado — que é o que dá para testar.

**Conhecimento humano com âncora e data.**
*Contexto:* conhecimento confirmado sobrevivendo ao código que descrevia é pior que dedução,
porque confirmado ganha de tudo. *Decisão:* toda entrada carrega âncora e data; âncora sumiu →
revalidar; conhecimento sobrescreve interpretação, nunca fato. *Alternativas descartadas:*
texto livre sem âncora. *Consequências:* exige `gravar.py` para o arquivo não nascer vazio.

**Commitar com redação obrigatória.**
*Contexto:* documentação mora junto do código, mas a skill lê `.env` e config de terceiro.
*Decisão:* `docs/project/` commitado, com redação não-opcional. *Alternativas descartadas:*
local e ignorado por padrão (o próximo dev não acha). *Consequências:* a redação vira requisito
de segurança testado, não boa intenção.

## Restrições verificáveis

| Restrição | Como checar |
|---|---|
| **Mesmos fatos, mesmo documento, byte a byte** | `varrer.py` + `montar.py` sobre um `interpretation.toml` **congelado** no fixture, duas vezes: saídas idênticas. A saída não carrega carimbo de tempo. *(Escopado à parte determinística: a rodada do agente não é reprodutível por natureza, e exigir isso dela seria teste impossível.)* |
| **Nunca afirmar ausência de dependentes** | fixture cujo acoplamento existe **só** por injeção de dependência e rota como string. Duas asserções, e a positiva é a que importa: (a) o acoplamento **aparece**, como N menções textuais com a lista do que o grafo não enxerga anexada; (b) nenhuma frase do conjunto proibido (`nada depende`, `sem dependentes`, `não é usado`) sai no documento. Só (b) passaria com a seção vazia ou a varredura quebrada. |
| **Nenhum segredo em nada que seja commitado** | fixture com `.env` e chave privada: afirmar que nenhum valor aparece em **nenhum arquivo de `docs/project/`** — `guide.md`, `inventory.json`, `interpretation.toml` e `area-*.md` |
| **Âncora quebrada não vira confirmado** | `knowledge.toml` apontando para caminho inexistente: a entrada sai em "conhecimento a revalidar" e **não** no corpo com selo |
| **Sem histórico não omite em silêncio** | fixture com um commit só: a seção de co-mudança existe, traz o motivo, e nomeia o sinal estático que a substituiu |
| **`varrer.py` não escreve fora de `docs/project/`** | teste afirmando os caminhos tocados |

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| Regra verificável (validação, enum, constraint, estado) é extraível com precisão útil | a camada 3 inteira cai, e sobra só grafo e superfície | spike: extrair de um projeto real recebido e conferir à mão quantas regras saíram certas |
| Grafo textual tem ruído tolerável | a seção de dependentes vira lista inútil que ninguém lê | medir em projeto real: quantas menções por símbolo, e que fração é sinal |
| A ferramenta nativa está presente na máquina de quem roda | a queda para regex vira o caminho normal, e o grafo perde nó | checar presença e registrar; medir a diferença de arestas nos dois modos |
| Projeto recebido tem histórico de git útil | metade do valor da camada 2 some | olhar os últimos projetos que entraram: quantos vieram com histórico |
| O agente consegue interpretar lendo só o inventário | ou ele lê código demais e estoura, ou escreve raso | rodar num projeto grande e medir contexto e qualidade |

A de maior risco é a primeira: **ela é o primeiro spike do plano.** Se regra verificável não
sair com precisão útil, a camada 3 vira só "perguntas em aberto" e o design muda.

## Rollout e reversibilidade

Skill nova, uso interno, nada em produção. Publicação pelas regras do repositório: prefixo
`sw-`, `make sync SKILL=sw-codebase-guide` com `BUMP` a cada mudança de conteúdo, entrada no
`CHANGELOG.md` e `make check` antes de commitar. Desfazer é não usar. O único efeito duradouro é o que ela escreve em `docs/project/` do projeto
auditado — e isso é arquivo novo, em pasta própria, sem tocar em nada existente.

## Revisões do spec

- **2026-10-06** — o spike (task 1 do plano) rodou em dois projetos reais e **mudou a decisão
  sobre `regras.py`**. A versão genérica, com seis padrões sobre qualquer linguagem, extrai 20%
  de regra de negócio num projeto TypeScript e 50% num PHP. Mantendo só `enum` e `estado`, sobe
  para **9 de 10 = 90%** — acima do critério. Então `regras.py` **entra** no Plano 2, mas com
  dois padrões em vez de seis, fora de teste/mock/gerado/comentário, e dentro do TOML da stack.
  `constante`, `limiar`, `validacao` e `cron` saem: os dois primeiros arrastam 20 candidatas
  para trazer 5 regras, e os dois últimos não acharam nada em nenhum dos projetos. Detalhes e a
  classificação item a item em `referencias/spike-regras.md`.
- **2026-10-06** — `docs/project/` entrou no `.gitignore` **deste repositório** (o marketplace),
  porque a skill vai ser testada aqui e a saída de teste não é documentação deste projeto. A
  decisão do spec não muda: nos projetos auditados o guia continua sendo commitado.
- **2026-10-06 (depois do primeiro uso real)** — a skill nasceu com **zero** `AskUserQuestion`,
  única da casa (as irmãs têm de 3 a 14). Isso veio da decisão fundante de deduzir em vez de
  entrevistar, e essa parte se confirmou: no `projeto D` o `CLAUDE.md` do projeto respondeu o que
  entrevista nenhuma responderia.

  Mas a regra da casa não é "não pergunte" — é *"pergunta serve para decisão e autorização, não
  para suprir leitura que você não fez"*. E a skill **escreve** dentro do repositório de um
  projeto de terceiro, criando pasta e arquivo na primeira execução, sem pedir licença. A
  `sw-infra-audit` confirma o alvo antes de qualquer conexão, e lá ela só lê.

  Entrou então uma seção "Regra: toda decisão é via AskUserQuestion" com cinco momentos — todos
  de **autorização ou escopo**, nenhum de descoberta: antes de gravar (obrigatório), ao
  sobrescrever um `guide.md` existente, quando a varredura acha sub-repositórios, quando o
  inventário sai mudo (sinal de raiz errada) e no fim, para as perguntas em aberto virarem
  pauta. Dois testes prendem a regra, inclusive a frase que distingue autorização de preguiça.
