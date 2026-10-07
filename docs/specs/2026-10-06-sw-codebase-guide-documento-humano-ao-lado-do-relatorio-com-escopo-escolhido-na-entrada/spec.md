---
titulo: "sw-codebase-guide: documento humano ao lado do relatorio, com escopo escolhido na entrada"
slug: 2026-10-06-sw-codebase-guide-documento-humano-ao-lado-do-relatorio-com-escopo-escolhido-na-entrada
criado: 2026-10-06
estado: concluido
---

# Documento humano ao lado do relatório, com escopo escolhido na entrada

> Evolução da `sw-codebase-guide` v0.1.0. O trabalho anterior está em
> [`../2026-10-06-sw-codebase-guide-skill-que-le-um-projeto-e-escreve-a-documentacao-dele/`](../2026-10-06-sw-codebase-guide-skill-que-le-um-projeto-e-escreve-a-documentacao-dele/spec.md).

## Objetivo & outcome

O `guide.md` de hoje é um **inventário**: diz "103 menções", "630 arquivos", "co-mudança 38×".
Não diz o que o produto é nem onde o dev mexe para resolver o chamado que ele pegou.

**Outcome:** depois de ler, o dev sabe responder *"o que este sistema faz"* e *"em que pasta eu
mexo para alterar X"* — e consegue escolher, antes de ler, se quer o sistema inteiro ou uma
parte dele.

## Exploração & decisões

**O trabalho real:** o dono enquadrou como *"entender o todo do projeto ou alguma parte
específica"*. Não é tour, nem avaliação de esforço: é compreensão, com **escopo escolhido**.

**Suposição derrubada.** O spec anterior tratou o recorte por área (`--area`) como refinamento
opcional do "Plano 2". É o contrário: **a pergunta de escopo é a porta de entrada**, e quem
propõe as opções é a skill — o dev não precisa saber o nome da área antes de começar.

**Ângulos levantados e descartados:**
- *Duas interpretações separadas* (um arquivo por público) — descartado: o agente passaria duas
  vezes pelo mesmo material e nada garantiria que os dois contassem a mesma história.
- *Um documento humano com o técnico virando anexo* — descartado: o dono pediu os dois.
- *O percurso ponta a ponta produzido pela varredura* — descartado por ora: exige o TOML de
  stack, que não existe.

**Direção escolhida:** uma fonte (`interpretation.toml` com dois tipos de bloco), dois
documentos (`leia-me.md` humano e `guide.md` técnico), e a pergunta de escopo antes de tudo.

## O documento humano — quatro partes, nesta ordem

A ordem é pedagógica: **o que é → como funciona de ponta a ponta → onde ficam as coisas → como
agir.**

**1. O que o produto faz.** Dois ou três parágrafos: o que é, quem usa, quais são as partes.
Escrito em paráfrase pelo agente, **com o trecho literal da fonte ao lado** (ver "A guarda da
vacuidade"). Sem fonte textual, a parte sai dizendo que não foi apurada e a pergunta vai para a
pauta.

**2. O percurso de uma funcionalidade.** O agente escolhe uma, rastreia do clique até o banco e
**declara os saltos que não resolveu**.

**3. O mapa de pastas comentado.** A árvore do que importa, uma linha por pasta.

**4. As frases de orientação.** O número vira conselho: a co-mudança de 8× vira *"para mexer no
funil você quase sempre mexe também no componente"*.

Cada parte **aponta para a seção correspondente do `guide.md`**. É a mitigação do risco de
divergência: números são livres na narrativa (decisão do dono), então nada impede ela dizer 81
onde o técnico diz 64 — o link não impede, mas torna descobrível em um clique.

## A pergunta de escopo

A **fase barata** da varredura (árvore + stacks + textos, ~0,1 s) roda antes, e o menu sai
preenchido:

```
Quer entender o projeto todo, ou uma parte?

○ O projeto todo                 630 arquivos · 1 stack · 20 áreas
○ funil                 pasta · 7 arquivos · 14 commits no último mês
○ clientes-aeronaves   pasta · 23 arquivos · 9 commits no último mês
○ Other                (digitar outra pasta ou termo)
```

**As áreas saem do agrupamento de diretórios da `arvore`**, não da detecção por convenção de
caminho — essa é a que marcou 29 "rotas" que eram controllers num projeto PHP e não achou as 20
áreas do App Router num Next.js. A árvore vem do `os.walk` com poda, que é a parte mais
confiável do inventário.

**O rótulo é descritivo, nunca semântico:** `funil · pasta · 7 arquivos`, jamais `funil · rota
do App Router`. Rótulo semântico é a afirmação que a skill não consegue provar, e na porta de
entrada ela decidiria o escopo dos dois documentos.

**Profundidade,** com os limiares nomeados para o plano não os inventar: desce enquanto um único
filho concentrar **≥ 80%** dos arquivos do nível, corta quando houver **≥ 3** filhos acima do
piso, e o piso é **≥ 3 arquivos** por área. Num monorepo por justaposição isso para no nível 1;
num Next.js, em `src/app/(app)/`. São os dois casos-âncora, e servem de teste de aceitação —
a suposição nº 2 calibra os números contra os seis projetos já testados.

**Ordenação:** mais mexidas nos últimos commits, **com queda para número de arquivos** quando
não há git ou quando a consulta estoura o teto de tempo. O campo `ordenado_por` da saída diz
qual critério valeu, para o menu não mentir sobre o que está ordenando.

Isso exige uma consulta git **na fase de áreas**, e nenhum módulo de hoje produz esse dado —
`historia.historico` devolve total de commits e pares de co-mudança, não contagem por diretório.
É código novo: um `git log --since=90.days --name-only`, agregado por diretório de área. Por isso
a fase de áreas não é "0,1 s"; é "rápida o bastante", com fallback declarado. O menu mostra as três primeiras
e **diz quantas ficaram de fora**; o resto sai impresso antes da pergunta, para o dev achar pelo
nome e usar o "Other".

**Sem áreas reconhecíveis:** o menu sai só com "o projeto todo" e "Other", dizendo por quê. Não
inventa recorte — oferecer uma área errada é pior que não oferecer.

**Esta pergunta absorve a de sub-repositórios** que o `SKILL.md` já faz ("documentar o conjunto
ou só um deles?"): é literalmente a mesma pergunta, e um terço dos projetos cai nela. Escopo e
destino de gravação vão na **mesma chamada** de `AskUserQuestion`.

## Arquitetura

### Varredura em duas fases — o contrato

**Um script, dois modos.** A fase de áreas **não grava nada**: imprime JSON em `stdout`. Isso
preserva `test_varrer_so_escreve_em_docs_project`, que afirma que o diretório de saída contém
exatamente `inventory.json` — qualquer arquivo intermediário o quebraria.

```bash
# fase de áreas — não escreve; imprime as áreas em stdout
python3 scripts/varrer.py --projeto . --areas
# → {"areas": [{"caminho": "src/app/(app)/funil", "arquivos": 7, "commits_recentes": 14}, …],
#    "total_arquivos": 630, "stacks": 1, "ordenado_por": "commits_recentes"}

# fase completa — escreve inventory.json, opcionalmente recortada
python3 scripts/varrer.py --projeto . --out docs/project [--area "src/app/(app)/funil"]
```

A área entra por `--area` com o **caminho** (não o rótulo), então a fase completa é
reproduzível sem passar pelo menu — é o que faz o teste e a reexecução funcionarem.

**Orçamento.** A fase de áreas é `os.walk` com poda mais **uma** consulta
`git log --since=90.days --name-only`, limitada no tempo: estourando o teto, cai para ordenação
por número de arquivos e diz isso no `ordenado_por`. Não é "0,1 s" como a primeira redação dizia
— é "rápida o bastante para rodar antes de perguntar", e o fallback existe porque um terço dos
projetos testados não tem git na raiz.

**O que muda no código:** `superficie`, `textual` e `imports` hoje chamam `arvore.varrer(raiz)`
cada um por conta própria. A árvore passa a ser computada uma vez e **passada adiante** — sem
isso, "a fase de áreas já computou a árvore" não se realiza.

### O recorte, por seção

| Seção | Como recorta |
|---|---|
| `arvore`, `superficie`, `textos` | por prefixo de caminho |
| `stacks`, `ambiente` | **prefixo + o que mora acima, herdado e marcado** |
| `historia`, `mencoes` | **pelo menos uma ponta dentro** |

A segunda linha conserta um buraco que esvaziaria o "Como entrar" no caso mais comum. Para a
área `src/app/(app)/funil`, o `package.json` está em `.` e o `.env` está na raiz: recorte por
prefixo puro deixaria os dois de fora, e o documento imprimiria *"nenhum manifesto reconhecido
na raiz [lacuna]"* — falso — além de sumir com a seção de variáveis de ambiente, que o
`SKILL.md` chama de uma das informações mais úteis para quem vai subir o projeto. Então stack e
ambiente **acima** da área entram herdados, marcados como `de_fora_da_area`.

A terceira linha é a correção mais importante do design. O valor das frases de orientação vem do
par que **cruza a fronteira** da área — "mexer no funil mexe no componente" é um arquivo de
dentro com um de fora. Recortar os dois lados apagaria exatamente o que a seção existe para
dizer. O mesmo vale para `mencoes`: os símbolos são os da área, procurados no **repositório
inteiro**, senão some quem usa a área de fora.

**`historia`, campo a campo**, porque o dicionário tem mais que `co_mudanca`:

| Campo | No documento de área |
|---|---|
| `co_mudanca` | filtrado por uma-ponta-dentro, **antes** de aplicar o teto de 40 pares |
| `commits`, `commits_descartados` | continuam do projeto todo, e o documento diz isso por extenso |
| `subrepos` | mantido inteiro — escolher um sub-repo é um caso esperado do menu |
| `lacuna` | mantida como está |

O "antes do teto" não é detalhe: `MAX_PARES = 40` e `MIN_COMMITS = 50` são aplicados hoje de
forma global. Filtrar **depois** dos 40 pares globais devolveria um ou dois pares para a área e
apagaria exatamente o sinal que a seção existe para dar.

`imports` não é recortado porque só existe para Python; no projeto do dono (Next.js) ele é
vazio, e "subgrafo" seria palavra sem referente. O ganho real do recorte, que é o que vale
declarar: o teto de 300 símbolos deixa de morder, e os 40 que chegam ao documento passam a ser
os da área.

**O escopo escolhido é gravado no `inventory.json`** (`escopo = {area, criterio, n_arquivos}`).
Sem isso, "mesmos fatos, mesmo documento byte a byte" passaria a depender de lembrar o que foi
clicado no menu.

### A seção `textos` do inventário

README, `CLAUDE.md`, `AGENTS.md`, `docs/**/*.md` (recursivo, para pegar `docs/adr/0001-*.md`),
`*.adr.md` e arquivos de tradução (`locales/**`, `lang/**`, `i18n/**`): **caminho e conteúdo**.

**E aqui há um invariante a preservar, que a primeira redação deste spec derrubava sem
perceber.** O `varrer.py` carrega hoje o comentário: *"a proteção acontece na ORIGEM: o
inventário só carrega caminho, contagem e nome de chave, nunca conteúdo"* — e `textos` é, por
definição, conteúdo. README de projeto recebido tem token de exemplo com frequência, e o
`inventory.json` é **commitado**.

Três travas, todas obrigatórias:

1. **O conteúdo passa por `redact.redigir` campo a campo, antes de serializar.** Nunca sobre o
   JSON pronto — isso já quebrou o arquivo uma vez (`"AuthController": [` virava
   `"AuthController": ***`) e está registrado no plano anterior.
2. **Teto de 64 KB por arquivo**, com o excedente cortado e a marca de corte no registro. A
   `arvore` já marca `acima_do_teto` em 1 MB; `textos` é mais apertado porque o conteúdo vai
   inteiro para o JSON.
3. **`test_chave_de_env_entra_e_valor_nao` passa a cobrir também os `textos`:** um README com
   `ghp_…` no fixture, afirmando que o token não aparece no `inventory.json`.

Hoje **nenhuma das oito seções do inventário aponta para isso**, e o agente só encontra se
lembrar de procurar — enquanto a parte 1 do documento humano depende inteiramente dessas fontes.
No teste real foi o `CLAUDE.md` do projeto que respondeu o que entrevista nenhuma responderia,
e foi sorte o agente ter olhado.

É também o que viabiliza a conferência de citação literal **sem quebrar a pureza do
`montar.py`**, que hoje é função apenas de `inventory.json` + `interpretation.toml` e tem teste
byte a byte.

### O formato da interpretação

Ao lado das `[[afirmacao]]` de hoje:

```toml
[[narrativa]]
parte = "o-que-e"         # o-que-e | percurso | mapa | orientacoes
texto = "É um CRM para uma empresa de manutenção aeronáutica, com cerca de 30 usuários…"
trecho = "CRM single-tenant para uma empresa de manutenção e aviônicos (~30 usuários)"
fonte = "CLAUDE.md"
evidencia = ["CLAUDE.md"]
saltos = []               # só na parte "percurso"
```

**Quantos blocos por parte, e em que ordem:**

| Parte | Blocos | Campos obrigatórios | Ordem no documento |
|---|---|---|---|
| `o-que-e` | **um** | `texto`, `trecho`, `fonte`, `evidencia` | — |
| `percurso` | **um** | `texto`, `evidencia`, `saltos` | — |
| `mapa` | **vários** | `texto`, `evidencia` | campo `ordem` (inteiro) |
| `orientacoes` | **vários** | `texto`, `evidencia` | campo `ordem` (inteiro) |

O campo `ordem` existe porque hoje `montar._escrever` ordena por `texto` para ser determinístico
— aplicado ao mapa de pastas, isso embaralharia a árvore em ordem alfabética da frase. `ordem`
mantém o determinismo sem destruir o sentido.

`montar.py` emite **dois** arquivos a partir do mesmo `interpretation.toml`: `leia-me.md` e
`guide.md`. Uma fonte, dois documentos, impossível divergirem de origem. **Recusa não escreve
nenhum dos dois** — a sentinela que hoje protege o `guide.md` passa a valer para o par.

## As guardas

### A guarda da vacuidade — a que importa mais

O pior modo de falha da parte 1 **não é falsidade — é ser fluente, verdadeira e inútil**: *"o
sistema gerencia clientes e aeronaves, com um funil de vendas"* passa em qualquer verificação de
caminho, e o dev já sabia disso lendo o nome das pastas.

Por isso a parte 1 carrega `trecho` + `fonte`, e **`montar.py` confere que o trecho aparece no
arquivo citado**, buscando-o na seção `textos`. Trecho literal não consegue ser vazio-e-fluente:
ou alguém escreveu aquilo sobre o sistema, ou não escreveu.

**A comparação normaliza espaço em branco** — colapsa sequências de espaço, tabulação e quebra
de linha em um espaço só, dos dois lados. Sem isso a guarda nasce morta: README quebrado em 80
colunas faz qualquer frase citada atravessar linhas, a substring exata falha, e o agente aprende
a citar fragmentos de quatro palavras para escapar — o oposto do que a guarda quer.

**`fonte` fora da lista do `textos` é recusada**, com a mensagem dizendo que o arquivo não é
fonte textual reconhecida. Aceitar calado levaria a citação a um arquivo que o script não leu.

O documento imprime a paráfrase do agente **com o trecho ao lado**, para o leitor comparar.

### A guarda do caminho

Toda `evidencia` é conferida contra o inventário — caminho que não existe na `arvore` é recusado.
Caminho inventado é a alucinação mais comum em prosa sobre código.

**Vale para os dois blocos**, `[[afirmacao]]` e `[[narrativa]]`: hoje `montar.py` só exige que
`evidencia` esteja presente, sem conferir, e ter dois padrões para o mesmo campo no mesmo arquivo
é convite a confusão.

**Três formas de evidência são legítimas, e a conferência precisa conhecer as três** — o
`SKILL.md` já ensina e os testes já usam todas:

| Forma | Exemplo | Como confere |
|---|---|---|
| caminho de arquivo | `app/Pedido.php` | existe na `arvore` |
| caminho com linha | `app/Pedido.php:88` | **descasca o `:88`** e confere o caminho |
| diretório | `supabase/migrations/` | **prefixo** de ao menos um caminho da `arvore` |
| não-caminho | `commit 3c5aabb`, `https://…` | aceito sem conferir, se casar os prefixos declarados (`commit `, `http`) |

Sem essas quatro linhas, a guarda **recusa a evidência correta**: hoje o `SKILL.md` documenta
`["app/Pedido.php:88"]` e os testes usam `["rotas.py:1"]` e `["commit 3c5aabb"]`. Uma
conferência ingênua quebraria três testes que já passam.

### A guarda da ausência, agora na prosa

A garantia mais forte da skill — *ausência de dependentes nunca é afirmada* — é hoje protegida
por um `guide.md` templatizado e por um teste que lê **só o `guide.md`**. O `leia-me.md` é texto
livre do agente, muito mais propenso a escrever "isso não é usado em lugar nenhum".

A lista de frases proibidas passa a valer **no campo `texto` da `[[narrativa]]`, na recusa do
parser** — não só no teste de saída.

E ela **sai do teste para o código de produção**: hoje `PROIBIDAS` é uma tupla dentro de
`tests/test_montar.py`. Com a recusa no parser, duas listas passariam a existir e divergiriam na
primeira vez que alguém acrescentasse uma frase a uma só. O módulo publica a lista; o teste a
importa.

### O que nenhuma guarda pega

Prosa que cita arquivo real e diz algo falso sobre ele. A trava pega caminho inventado e trecho
inventado, não interpretação errada. Quem pega isso é quem conhece o sistema — e é para isso que
o documento fecha com as perguntas em aberto.

## O percurso — uma reversão declarada

O spec anterior **tirou** o caminho ponta a ponta do piso, com razão escrita: *"atravessa
middleware, container e ORM… sem TOML a seção sai sem ele, dizendo por quê — não sai com um
caminho pela metade."*

Este spec o traz de volta, e a reversão é defensável porque **mudou quem produz**: lá era o
script seguindo o grafo; aqui é o agente lendo arquivo. Mas a razão original continua valendo, e
por isso vem com trava:

- **Orçamento de leitura declarado:** no máximo 10 arquivos. O que não resolver vira `saltos`.
- **`saltos = []` é afirmação forte**, não omissão: significa "segui do clique até o banco sem
  buraco". Com orçamento declarado, a diferença entre "segui inteiro" e "não tentei" fica
  observável.
- **Só com escopo recortado.** Em "o projeto todo" num legado de 10 mil arquivos, rastrear é
  adivinhar onde a execução começa — e o limite nº 2 do plano anterior continua de pé: a skill
  não detecta entrypoint.

## O `leia-me.md` em HTML e PDF — sob demanda, perguntado no fim

Markdown é bom para versionar e ruim para ler de ponta a ponta: não dá hierarquia visual,
índice clicável nem quebra de página controlada. E a skill existe para quem **acabou de receber
um projeto** — a conversa seguinte é com alguém, e Markdown não se manda para um cliente nem se
imprime para uma reunião.

| Arquivo | Quando sai |
|---|---|
| `leia-me.md` | sempre — é o que vai para o git |
| `leia-me.html` | quando pedido — legível, com índice e hierarquia |
| `leia-me.pdf` | quando pedido — para enviar ou imprimir |

**A pergunta é no fim, não no começo.** É a regra que a `sw-infra-audit` já aprendeu e escreveu:
*"O PDF custa alguns segundos de Chromium e nem toda rodada vira documento para enviar;
perguntar no começo gasta a atenção de quem só queria ver o estado."* A skill gera o Markdown,
lê as perguntas em aberto, e **só então** oferece.

**O que é reaproveitado da irmã, e o que não é.** A mecânica de impressão dela já resolveu o
problema: HTML self-contained com as fontes em base64 (o PDF sai **offline**, sem rede), `@page`
e `print-color-adjust`, dez `break-inside` e cinco `break-before` para a quebra de página não
cortar bloco no meio, e Chromium headless com queda graciosa — sem navegador, entrega o HTML e
avisa, sem tratar isso como falha.

O que **não** se reaproveita é o template: o dela é relatório de auditoria, com faixas de
severidade e gráfico de cascata; documento narrativo tem outra hierarquia. Como a casa usa um
plugin por skill, não há como compartilhar código — o template nasce aqui, copiando a mecânica
e as fontes, com a origem citada em comentário.

**O limite, dito antes de alguém se iludir:** isto é embalagem. Com ou sem PDF, o documento diz
o que a interpretação escreveu. Um PDF bonito de um inventário continua sendo um inventário — e
é por isso que esta seção vem **depois** do `leia-me.md` no plano, não no lugar dele.

## Onde grava

A rodada com área **sobrescreve** `guide.md` e `leia-me.md` (decisão do dono). O risco de perder
o guia do projeto todo é aceitável porque `docs/project/` é **commitado**: o git guarda a versão
anterior, então perde-se o arquivo, não o histórico. O documento registra, no topo, qual escopo
o gerou.

## Não-objetivos

- **Não implementa o TOML de stack.** A superfície por convenção continua como está, com os
  erros conhecidos — ela deixa de alimentar o menu de escopo, que é o dano que importava.
- **Não conserta o extrator de símbolos** (`data`, `button`, `banco` vindos de nome de arquivo).
  O recorte por área reduz o estrago; a correção é parsing por linguagem.
- **Não estende o grafo de import** para além de Python.
- **Não persiste conhecimento humano** entre execuções (`knowledge.toml` segue fora).
- **Não gera HTML nem PDF do `guide.md`.** O relatório técnico fica só em Markdown: é o que vai
  para o git e dá diff, e ninguém imprime um inventário. O documento **humano** ganha os dois.
- **Não detecta entrypoint** — o percurso começa de onde o agente conseguir.

## Restrição de simplicidade

A menor solução: **um** `montar.py` emitindo dois arquivos, **um** `interpretation.toml` com dois
tipos de bloco, **uma** pergunta juntando escopo e destino. Não construir por ora: linguagem de
marcador para números, ids de afirmação referenciáveis pela narrativa, ordenação configurável do
menu, mais de um percurso por documento.

## Appetite

Uma a duas semanas. Se estourar, o corte é o **percurso** — as outras três partes do documento
humano entregam a maior parte do valor, e o percurso é a mais cara e a mais arriscada.

**Dois marcos, para o trabalho ter ponto de parada utilizável no meio:**

| Marco | O que entrega | Como se sabe que fechou |
|---|---|---|
| **1 — o escopo** | fase de áreas, menu, `--area`, recorte nas 6 seções, `textos` no inventário | os 92 testes continuam verdes e o `guide.md` de uma área sai correto |
| **2 — o documento humano** | bloco `[[narrativa]]`, `leia-me.md`, as três guardas, o percurso | o spike da prosa passou e o `leia-me.md` de um projeto real serve |

O marco 1 já tem valor sozinho: recortar por área melhora o `guide.md` de hoje, porque o teto de
símbolos deixa de morder. Se o marco 2 não se sustentar no spike, o marco 1 fica e vale a pena.

## MVP vs MLP

**MVP.** O critério é descobrir se a prosa do agente, com inventário e poucos arquivos, produz
2-3 parágrafos que o dev ache melhores que nada.

## Decisões

**A pergunta de escopo vira a porta de entrada.**
*Contexto:* o dono enquadrou o trabalho como "entender o todo ou uma parte". *Decisão:* a fase
barata da varredura roda antes e alimenta o menu. *Alternativas descartadas:* `--area` como
parâmetro (exige saber o nome antes); perguntar sem varrer (o dev não conhece o projeto).
*Consequências:* `varrer.py` deixa de ser monolítico; a pergunta de sub-repos é absorvida.

**As áreas saem da árvore, com rótulo descritivo.**
*Contexto:* a detecção por convenção de caminho erra o que é específico de stack. *Decisão:*
agrupamento de diretórios da `arvore`, rótulo `pasta · N arquivos`. *Alternativas descartadas:*
usar `superficie.py` (erraria na porta de entrada); rótulo semântico (afirmação não provável).
*Consequências:* o menu é mais burro e mais honesto.

**Recorte com "uma ponta dentro" em histórico e menções.**
*Contexto:* o valor das orientações vem do par que cruza a fronteira da área. *Decisão:* prefixo
para o que é inventário, uma-ponta-dentro para o que é relação. *Alternativas descartadas:* os
dois lados dentro (apagaria o sinal). *Consequências:* o documento da área fala de arquivos de
fora, e precisa deixar claro que são de fora.

**Paráfrase com trecho literal ao lado.**
*Contexto:* a pior falha da parte 1 é vacuidade, que conferência de caminho não pega. *Decisão:*
o agente parafraseia e o `trecho` literal é conferido pelo script. *Alternativas descartadas:*
só paráfrase (não pega vacuidade); só trecho (ilegível). *Consequências:* exige a seção `textos`
no inventário.

**Número livre na narrativa.**
*Contexto:* decisão do dono, contra a recomendação do revisor. *Decisão:* a prosa pode carregar
número. *Alternativas descartadas:* número só no técnico; marcador resolvido pelo script.
*Consequências:* os dois documentos podem discordar sem ninguém notar; mitigado por cada parte
do `leia-me.md` apontar a seção correspondente do `guide.md`.

## Restrições verificáveis

| Restrição | Como checar |
|---|---|
| **Trecho literal é conferido** | `interpretation.toml` com `trecho` que não aparece no arquivo citado: `montar.py` sai com erro e não escreve o `leia-me.md` |
| **Caminho inventado é recusado nos dois blocos** | uma `[[afirmacao]]` e uma `[[narrativa]]` citando `nao/existe.php`: as duas recusadas, com a mensagem dizendo qual |
| **Diretório casa por prefixo** | `evidencia = ["supabase/migrations/"]` com a árvore contendo só arquivos dentro dela: **aceito** |
| **Frase proibida na narrativa é recusada** | `texto` contendo "não é usado em lugar nenhum": recusa do parser, não do teste de saída |
| **Recorte preserva a ponta de fora** | fixture com co-mudança entre `area/a.py` e `fora/b.py`, escopo `area`: o par **aparece** no `inventory.json`, e o `montar.py` o imprime marcando que a outra ponta é de fora. A marca é **derivada no `montar.py`** a partir do campo `escopo`, não gravada no inventário — assim o recorte mexe só em `varrer` e a renderização só em `montar` |
| **Stack e ambiente acima da área sobrevivem** | escopo `src/app/funil` com `package.json` em `.` e `.env` na raiz: os dois aparecem, marcados `de_fora_da_area`, e o documento **não** diz "nenhum manifesto reconhecido" |
| **Evidência com `:linha` e `commit` é aceita** | `["app/Pedido.php:88", "commit 3c5aabb"]` com `app/Pedido.php` na árvore: aceito. `["nao/existe.php"]`: recusado |
| **Trecho com quebra de linha casa** | README com a frase quebrada em duas linhas e `trecho` numa linha só: aceito |
| **Token em README não chega ao inventário** | fixture com `ghp_` no README: o `inventory.json` não contém o token, e a seção `textos` tem o resto do arquivo |
| **Mesmos fatos, mesmo documento** | duas montagens sobre o mesmo par de arquivos: `leia-me.md` e `guide.md` byte a byte iguais, sem carimbo de tempo |
| **Sem Chromium, entrega o HTML e avisa** | instrumentar a busca do executável para não achar nenhum: o `leia-me.html` é escrito, o PDF não, a saída diz por quê, e o processo termina com **sucesso** |
| **O PDF não depende de rede** | gerar com as variáveis de proxy apontando para porta morta: o PDF sai igual, porque fonte e estilo estão embutidos |
| **A fase de áreas só abre o que `textos` declara** | instrumentar `open`/`read_text` na fixture: qualquer leitura de arquivo que não case a lista de padrões do `textos` reprova. A primeira redação dizia "não lê conteúdo", o que contradizia a própria seção `textos` — e "arquivo de código" não tem definição única no código (há três listas diferentes) |

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| O agente escreve 2-3 parágrafos de produto que o dev ache melhores que nada | a parte 1 — o coração do pedido — vira ruído educado, e o documento humano não se justifica | spike: escrever a parte 1 de dois projetos reais e mostrar ao dono |
| Agrupamento de diretórios produz áreas que o dev reconhece | o menu de escopo oferece recortes que não são áreas, e a porta de entrada confunde | rodar a detecção nos seis projetos já testados e olhar os menus |
| Existe fonte textual na maioria dos projetos recebidos | a parte 1 sai vazia quase sempre | contar quantos dos seis têm README, `CLAUDE.md` ou `docs/` |
| O orçamento de 10 arquivos basta para um percurso útil | o percurso sai só com saltos, e vira ruído | rastrear uma rota num projeto real contando os arquivos abertos |
| Recortar reduz o ruído do grafo textual o bastante | a seção de dependentes continua ilegível, agora numa área | comparar a seção antes e depois do recorte no mesmo projeto |

A primeira é a de maior risco e **vira o primeiro spike do plano**: se a prosa não se sustentar,
o documento humano encolhe para mapa + orientações, e a parte 1 vira só a citação literal.

## Revisões do spec

- **2026-10-06 (depois de ver a saída rodando)** — o dono apontou que o documento não está num
  formato bom de ler e pediu PDF, perguntado no fim. O Markdown já existia; o que faltava era a
  embalagem. Entrou a seção "O `leia-me.md` em HTML e PDF", e o não-objetivo passou a valer só
  para o `guide.md` técnico.
  **A ordem foi decidida de propósito: o PDF vem depois do `leia-me.md`.** Embalar o `guide.md`
  de hoje seria investir hierarquia visual num conteúdo que esta mesma versão vai reescrever.

## Rollout e reversibilidade

Skill já publicada (v0.1.0). Esta é a v0.2.0: `make sync` com `BUMP=minor`, entrada no
`CHANGELOG.md`, `make check` antes de commitar. Não há migração de dado — o `inventory.json` é
regenerável por desenho, e `interpretation.toml` sem blocos `[[narrativa]]` continua válido,
gerando um `leia-me.md` que diz que as partes não foram interpretadas.

## O que vem depois desta versão

Rodar a v0.1.0 num projeto real levantou três frentes que **não cabem aqui** — cada uma é um
spec próprio, e empilhá-las nesta versão faria uma que não fecha. A ordem foi acordada com o
dono, e a dependência entre elas é real:

| | O que resolve | Por que nesta posição |
|---|---|---|
| **A** *(este spec)* | documento humano, escopo na entrada, HTML e PDF | já planejado e revisado; é o que ele apontou como falta hoje |
| **D** | grafo de import **real** para PHP e TypeScript | é a lacuna mais cara: nas stacks da casa o grafo é vazio, e "o que quebra se eu mexer aqui" fica no palpite |
| **B** | julgamento — vale manter ou reescrever · onde é perigoso mexer · o que está morto · risco de segurança visível | **depende de D**: não dá para dizer "mexer aqui é arriscado" sem saber quem depende do quê, e julgar sobre grafo vazio seria palpite com cara de medida |
| **C** | `knowledge.toml` com âncora: o que alguém confirmou sobrevive à regeração | independente; só se justifica porque o dono confirmou que o documento **vive e é atualizado** |

**Duas restrições do dono que mudam o que era assumido:**

- **O não-objetivo "não avalia qualidade" vale para o relatório técnico, não para o produto.**
  Quando se recebe um projeto, a pergunta real é *"vale manter ou reescrever?"*, e a skill tem
  os dados para responder — hoje ela mostra e cala.
- **Até 5 minutos de varredura é aceitável.** Era o orçamento de tempo que mantinha o grafo de
  import só em Python; com ele folgado, `tsc --listFiles` e um analisador de `use`/`namespace`
  cabem, e D deixa de ser caro demais.
