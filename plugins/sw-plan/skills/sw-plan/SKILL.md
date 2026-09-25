---
name: sw-plan
description: >-
  Transforma um spec/requisitos em um plano de implementação detalhado (estrutura de
  arquivos + tasks bite-sized com código e comandos exatos, qualidade de teste, sem
  placeholders) e ORQUESTRA a execução task-by-task com checkpoints de aprovação. Use
  quando já existe um design/spec/requisitos e é hora de planejar COMO construir e executar
  — frases como "faz o plano", "plano de implementação", "como vou construir isso", "quebra
  em tasks", "monta o passo a passo", "bora implementar isso", "executa o plano", "continua
  o plano de onde parou". É o passo depois da sw-brainstorming. NÃO use para: decidir O QUE
  construir do zero (isso é a sw-brainstorming), nem para uma edição trivial pontual.
  Interação em português, via AskUserQuestion.
---

# Plan — do spec ao build

## Visão geral

Escreva o plano como se quem for executar não conhecesse esta base de código: diga quais
arquivos tocar em cada task, o código, como testar e o que conferir. O plano inteiro vem em
tasks pequenas. DRY, YAGNI, TDD.

Assuma alguém que programa bem, mas que **não conhece o domínio nem as ferramentas deste
projeto** — e que provavelmente não escreve bons testes sozinho. O que não estiver escrito no
plano não vai acontecer.

**Anuncie no início:** "Estou usando a skill sw-plan para criar o plano de implementação."

**Regra:** toda decisão ao usuário é via `AskUserQuestion` (menu clicável) — nunca pergunta em
texto solto. Para despachar subagente, a ferramenta é a **`Agent`** (`subagent_type:
general-purpose`).

## Antes de tudo: já existe plano?

Se já houver `plan.md` no dossiê com tasks marcadas (`- [x]`), **não comece do zero**: leia,
conte o que está feito e **ofereça via `AskUserQuestion`** → **Continuar da primeira task não
marcada** / **Revisar o plano antes de seguir** / **Refazer o plano** (só com "refazer" o
arquivo é reescrito). Ver "Retomar uma execução" no fim.

## Stack-agnostic

Funciona em **qualquer linguagem/framework**. Os exemplos deste guia usam Python/`pytest`
apenas como **ilustração** — **detecte a stack real do projeto** e use o equivalente:

- **Runner/comando de teste:** `pytest -q` é exemplo → use o real (`jest`, `vitest`,
  `go test ./...`, `phpunit`, `cargo test`, `dotnet test`, `rspec`, `mvn test`…).
- **Paths/extensões:** `.py` / `tests/…` → o layout do projeto (`.ts`, `.go`, `.php`;
  `__tests__/`, `*_test.go`, `tests/`).
- **Idioma/convenções nos steps** = os da base de código (nomenclatura, lint/format do projeto).

Detecte pelos manifestos (`package.json`, `composer.json`, `go.mod`, `Cargo.toml`, `pom.xml`,
`pyproject.toml`, `Gemfile`, `*.csproj`) e pelos scripts de teste já configurados. Na dúvida
sobre o comando de teste, confirme via `AskUserQuestion`.

**Branch/worktree (se for git):** no início, se o diretório for um repositório git, **ofereça
via `AskUserQuestion`** criar um branch ou worktree dedicado pra este trabalho — ex.: **branch
`feat/<tópico>` / worktree dedicado / continuar no branch atual**. Não crie nada sem a escolha
do usuário.

## Onde salvar o plano

Dentro do **dossiê do trabalho**, como `plan.md` — ao lado do `spec.md` que originou o plano:

```
docs/specs/<AAAA-MM-DD>-<slug>/
  spec.md        ← o design aprovado (veio da sw-brainstorming)
  plan.md        ← ESTE arquivo
  referencias/   ← material de apoio; leia antes de planejar
```

- **Veio de um spec?** Grave o plano na MESMA pasta dele. Não crie pasta nova — spec e plano do
  mesmo trabalho separados é como isso vira bagunça.
- **Não veio de spec** (o usuário chegou direto com requisitos): crie o dossiê com o
  `dossie.py` da `sw-brainstorming`, se ela estiver instalada. **Ache o script antes de chamar**,
  porque instalada como plugin ela não mora em `~/.claude/skills/`:

  ```bash
  DOSSIE=$(ls ~/.claude/skills/sw-brainstorming/scripts/dossie.py \
              ~/.claude/plugins/*/sw-brainstorming/skills/sw-brainstorming/scripts/dossie.py \
              2>/dev/null | head -1)
  [ -n "$DOSSIE" ] && python3 "$DOSSIE" novo --titulo "<tema>"
  ```

  Não achou? Crie `docs/specs/<AAAA-MM-DD>-<slug>/plan.md` na mão e siga.
- **Leia `referencias/`** antes de escrever as tasks — print, PDF ou export guardado ali é
  contexto que o spec assume conhecido.
- **Fallback:** cwd sem `.git`/manifesto → `~/.claude/projects/<cwd-slug>/specs/<slug>/plan.md`.
- **Não commite o plano automaticamente.** Deixe o arquivo para o usuário commitar.
- A preferência do usuário sobre o local sempre sobrescreve este padrão.

## Tipos de teste (confira o spec antes de perguntar)

**Primeiro leia a seção de testes do spec.** Se ela já diz o que vale (ex.: "unit + integração,
sem e2e"), **siga e diga a suposição** — não pergunte de novo o que já foi decidido.

O spec calou? **Pergunte via `AskUserQuestion` (multiSelect)**: **Unit** / **Integração** /
**E2E** / **Nenhum** (protótipo ou projeto sem suíte). Detecte o que o projeto já usa e sugira
o mais adequado.

- Os steps de teste de cada task seguem **só os tipos escolhidos** — não gere e2e onde unit
  basta (menos teste desnecessário).
- **TDD é flexível:** havendo suíte, escreva o teste primeiro (red → green). Se o usuário
  escolher **Nenhum** ou não houver setup de teste, **não force** test-first — troque o par
  "escreve teste / roda" por "implementa + verifica" (rodar o app, conferir a saída) e deixe
  isso explícito nos steps.

## Escopo

Se o spec cobre vários subsistemas independentes, ele deveria ter sido quebrado em specs
menores no brainstorming. Se não foi, **sugira quebrar em planos separados** — um por
subsistema. Cada plano precisa entregar software que funciona e é testável por si só.

## Estrutura de arquivos

Antes de definir as tasks, mapeie quais arquivos serão criados ou alterados e de que cada um é
responsável. É aqui que as decisões de decomposição ficam travadas.

- Unidades com fronteira clara e interface bem definida. Cada arquivo com uma responsabilidade.
- Você raciocina melhor sobre código que cabe no contexto de uma vez, e edita com mais
  segurança arquivos focados. Prefira arquivos menores a um que faz coisa demais.
- Arquivos que mudam juntos moram juntos. Divida por responsabilidade, não por camada técnica.
- Em base existente, siga o padrão que já está lá. Se o projeto usa arquivos grandes, não
  reestruture por conta própria — mas se um arquivo que você vai mexer já está difícil de
  segurar, incluir a divisão no plano é razoável.

Essa estrutura informa a divisão em tasks. Cada task produz uma mudança que se sustenta sozinha.

## Ordem das tasks: o risco primeiro

**A primeira task não é a mais fácil nem a de baixo: é a que pode derrubar o plano.** Leia as
suposições do spec (a tabela `Suposição · Risco · Como validar`, quando existir) e pergunte: se
esta premissa for falsa, o que acontece com o resto? Se a resposta for "o plano inteiro muda",
ela vira a **task 1**.

- **Spike** = task curta cujo produto é uma **resposta**, não a feature: chamar a API de
  verdade e ver o formato, medir o tempo do caminho crítico, confirmar que a biblioteca faz o
  que promete na versão que o projeto usa. Tem critério explícito ("deu certo se…") e uma saída
  para quando falha ("se não, o plano muda assim…").
- Spike é descartável por definição: o código dele **não** precisa virar produção, e o plano diz
  isso.
- Depois dos spikes, o resto segue a ordem natural de dependência.
- Sem suposição arriscada? Diga isso em uma linha no plano e comece pela base.

## Tasks pequenas

**Cada step é uma ação de 2 a 5 minutos:**
- "Escreva o teste que falha" — step
- "Rode e confirme que falha" — step
- "Escreva o mínimo que faz passar" — step
- "Rode os testes e confirme que passam" — step

**Commit não é step de task.** O commit acontece **no checkpoint**, com a pergunta e o "sim" do
usuário (ver "Regras comuns aos dois modos"). Um step de commit dentro da task faz o subagente
commitar sozinho, sem aprovação.

## Cabeçalho obrigatório do plano

**Todo plano começa assim:**

```markdown
# Plano de implementação — [Nome da feature]

[spec.md](spec.md)  ← quando o plano nasceu de um spec; sem spec, escreva "Sem spec: requisitos no chat de <data>"

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** [uma frase do que isto constrói]

**Arquitetura:** [2-3 frases sobre a abordagem]

**Stack:** [tecnologias e bibliotecas principais]

**Restrições verificáveis (do spec):**
| Restrição | Como o plano checa |
|---|---|
| [ex.: p95 < 200ms no endpoint X] | [Task N, step do teste de carga] |

---
```

**A tabela de restrições não é enfeite.** O spec da `sw-brainstorming` fecha com *fitness
functions* — restrições que dá para **checar**, não só descrever. Cada uma precisa apontar para
a task e o step que a verifica; a que não tiver verificação é uma restrição que ninguém vai
cumprir, e isso aparece no self-review. Spec sem restrições verificáveis: escreva "o spec não
declarou" e siga.

## Estrutura da task

````markdown
### Task N: [Nome do componente]

**Arquivos:**
- Criar: `caminho/exato/arquivo.py`
- Alterar: `caminho/exato/existente.py:123-145`
- Teste: `tests/caminho/exato/test.py`

**Depende de:** Task N-1 (ou "nada" — tasks sem dependência podem rodar em paralelo)

**Contrato que esta task publica:** `função(entrada: Tipo) -> Saída` (o que as próximas tasks
podem usar; omita quando a task não expõe nada novo)

- [ ] **Step 1: escrever o teste que falha**

```python
def test_comportamento_especifico():
    resultado = funcao(entrada)
    assert resultado == esperado
```

- [ ] **Step 2: rodar o teste e confirmar que falha**

Rode: `pytest tests/caminho/test.py::test_nome -v`
Esperado: FALHA com "function not defined"

- [ ] **Step 3: escrever o mínimo que faz passar**

```python
def funcao(entrada):
    return esperado
```

- [ ] **Step 4: rodar o teste e confirmar que passa**

Rode: `pytest tests/caminho/test.py::test_nome -v`
Esperado: PASSA
````

## Qualidade dos testes (não escreva teste inútil ou falso)

Teste ruim é pior que nenhum — dá falsa confiança. Todo teste do plano segue:

- **AAA** — estruture cada teste em **Arrange · Act · Assert** (blocos claros).
- **Comportamento, não implementação** — asserta no resultado **observável** (saída, estado
  público, efeito), nunca em chamadas internas/estado privado. Senão quebra a cada refactor
  sem haver bug (falso alarme).
- **Asserts fortes, sem tautologia** — verifique o valor esperado **real**, não só "não é
  nulo"/"não lançou". Não teste o framework nem getter trivial, e **não mocke o que está sob
  teste** (mockar tudo = teste que passa sem testar nada = teste falso).
- **Determinístico e isolado** — sem rede/tempo/random reais (controle/fixe); sem depender de
  ordem de execução (teste flaky = sinal falso).
- **Red pelo motivo certo** — no TDD, confirme que o teste falha **pela razão esperada** antes
  de implementar (garante que ele testa algo de verdade).
- **Nome descreve o comportamento** (ex.: "rejeita token expirado", não "teste1").

Vale o YAGNI: cubra happy path + edge real + erro que importa; nada de teste só pra coverage.

## Nada de placeholder

Todo step traz o conteúdo real que quem executa precisa. Estes são **defeitos do plano** —
nunca escreva:
- "TBD", "TODO", "implementar depois", "preencher detalhes"
- "Tratar os erros adequadamente" / "adicionar validação" / "cobrir os casos-limite"
- "Escreva os testes do que está acima" (sem o código do teste)
- "Igual à Task N" (repita o código — quem lê pode estar fora de ordem)
- Step que diz o que fazer sem mostrar como (step de código exige bloco de código)
- Referência a tipo, função ou método que nenhuma task define

## Lembre

- Caminho de arquivo exato, sempre
- Código completo em todo step que mexe em código
- Comando exato, com a saída esperada
- DRY, YAGNI, TDD

## Self-review

Terminado o plano, olhe o spec com olhos frescos e confira o plano contra ele. Esta é uma
checagem sua, não um despacho de subagente.

**1. Rode o lint do plano** (determinístico, pega o que o olho deixa passar):

```bash
python3 <skill-dir>/scripts/plan_check.py docs/specs/<slug>/plan.md
```

Ele acusa task sem arquivos, step de código sem bloco de código, placeholder, checkbox
malformado, dependência para task inexistente e **arquivo "Alterar" que não existe no
projeto** (o typo de caminho que só apareceria na execução). Conserte o que ele apontar.

**2. Cobertura do spec:** percorra cada requisito do spec. Dá para apontar a task que o
implementa? Liste as lacunas.

**3. Restrições verificáveis:** cada linha da tabela do cabeçalho aponta para uma task e um
step que checa? Restrição sem verificação vira task nova ou sai da tabela com o motivo.

**4. Risco antes do resto:** a primeira task ataca a suposição mais arriscada? Se o plano
começa pelo fácil e o risco está na task 8, reordene.

**5. Consistência de tipos:** os tipos, assinaturas e nomes usados nas tasks finais batem com
os definidos nas primeiras? `clearLayers()` na Task 3 e `clearFullLayers()` na Task 7 é bug.

Achou problema, conserte na hora. Não precisa re-revisar: conserte e siga. Requisito do spec
sem task, crie a task.

## Revisor do plano (antes do gate)

Depois do self-review, **pergunte via `AskUserQuestion`** se quer um revisor independente do
**documento do plano**: **Sem revisor** / **Revisar o plano** (recomendado acima de 8 tasks ou
quando o plano nasceu de um spec grande).

Se sim, despache com a `Agent` (`general-purpose`) usando o template
[`plan-document-reviewer-prompt.md`](plan-document-reviewer-prompt.md), passando o caminho do
`plan.md` e o do `spec.md`. Ele é **consultivo**: devolve status, problemas e recomendações,
não edita nada. Corrija o que fizer sentido (ou explique por que não) e leve o que ele apontou
para o gate do usuário.

## Aprovação do plano (antes de executar)

Apresente o plano e peça aprovação via `AskUserQuestion` (**Aprovar / Ajustar / Cancelar**)
antes de qualquer execução. Mostre um resumo escaneável, não o plano inteiro:

- objetivo em uma linha;
- **tamanho**: quantas tasks, quantos batches no modo Inline (2-4 tasks cada) e o porte
  (até 5 tasks = pequeno · 6-12 = médio · acima de 12 = grande, e aí sugira o modo Subagent);
- a lista de títulos das tasks, marcando os spikes;
- os arquivos tocados;
- o que o revisor apontou, se houve revisor.

**O que cada resposta significa:**
- **Aprovar** → segue para a escolha do modo de execução.
- **Ajustar** → o usuário diz o que mudar, você edita o plano e roda o self-review de novo.
- **Cancelar** → **não execute nada**. O `plan.md` fica no dossiê como está (é rascunho útil,
  não lixo), o dossiê **continua** `aprovado` (não vai para `em-execucao`), e você diz em uma
  linha onde o arquivo ficou, para retomar depois. Só apague o arquivo se o usuário pedir.

## Execution Handoff

Depois de salvar o plano, pergunte via `AskUserQuestion` qual modo de execução o usuário
prefere. Os dois são autossuficientes — não dependem de nenhuma outra skill.

**Mensagem sugerida ao apresentar as opções:**
> "Plano salvo em `<path>`: N tasks, porte <pequeno|médio|grande>. Dois modos de execução:
> - **Subagent-Driven**: cada task roda num subagente novo (contexto limpo). Revisão entre tasks.
> - **Inline**: execução na mesma sessão, em batches com checkpoints."

**Acima de 12 tasks, recomende o Subagent** e diga o porquê: no Inline o contexto cresce e a
sessão pode ser compactada no meio da execução, o que faz perder o fio do plano. Se o usuário
preferir Inline mesmo assim, siga — mas feche cada batch com o checkpoint e o commit, para que
uma compactação não leve trabalho não salvo junto.

### Revisor de execução (juiz — escalonável)

Junto com o modo, **pergunte via `AskUserQuestion`** o nível de revisão durante a execução (uma
vez, governa a sessão):

- **Sem revisor extra** *(padrão)* — só o Stage-1 self-review + o gate humano que já existem.
- **Juiz por task/batch** *(recomendado p/ código sensível)* — após cada task (Modo Subagent) ou
  batch (Inline), despache um **revisor subagente independente** (`Agent`, `general-purpose`)
  **antes** do gate humano.
- **Juiz no fim** — um revisor do resultado completo ao terminar tudo, antes do resumo final.

**O que o juiz checa** (é **consultivo** — não edita, não aprova no lugar do usuário; passe a ele
o material implementado + a task/plano relevante):
- O código implementa **exatamente** a task/batch do plano (sem scope creep, sem refactor fora)?
- Os testes rodam **verdes** e são de **qualidade** (AAA, sem teste falso/tautológico)?
- Algum bug óbvio, regressão, ou ponta solta (referência órfã)?

Ele retorna **ok** ou **problemas + recomendações**. Com problemas: corrija o que fizer sentido
(ou explique por que não) e **só então** apresente o gate humano, listando o que o juiz apontou.
Se a **`sw-code-review`** estiver instalada, ofereça-a (via menu) pra um pass mais profundo.

### Modo 1 — Subagent-Driven

1. Leia o arquivo do plano na sessão atual.
2. Para CADA task do plano, na ordem:
   - Despache um subagente com a ferramenta **`Agent`** (`subagent_type: general-purpose`)
     passando:
     - a task completa (título e todos os steps com código);
     - **os contratos já publicados** pelas tasks anteriores (as assinaturas, tipos e nomes de
       arquivo do campo "Contrato que esta task publica"). Sem isso cada subagente inventa a
       sua própria interface, e a task seguinte não encaixa;
     - a instrução: "Implemente exatamente esta task. NÃO pule steps. NÃO refatore fora do
       escopo. NÃO faça commit. Devolva um resumo curto (até 150 palavras) do que foi feito."
   - Espere o subagente terminar.
   - **Stage 1 (automático)**: leia os arquivos alterados e confira — todos os steps foram
     mesmo executados? Os testes passam? O código bate com o que o plano especificou?
   - **[se o nível pedir] Juiz**: despache o revisor sobre esta task **antes** do Stage 2.
   - **Stage 2 (humano)**: `AskUserQuestion` — "Task N concluída. Aprovar e seguir?
     (sim / revisar / parar)".
   - Aprovado: marque o checkbox no plano (`- [x]`) e siga.
3. Ao final, reporte o resumo consolidado.

**Paralelismo:** tasks cujo campo "Depende de" é "nada" **e** que não tocam nos mesmos arquivos
podem ser despachadas na mesma mensagem, em paralelo. Na menor dúvida sobre sobreposição de
arquivos, rode em série — dois subagentes editando o mesmo arquivo é conflito silencioso.

**Vantagem:** o contexto principal não infla. **Desvantagem:** custo maior, porque cada
subagente relê o contexto.

### Modo 2 — Inline

1. Leia o arquivo do plano na sessão atual.
2. Agrupe as tasks em **batches** de 2-4 relacionadas (ou 1 task, se for grande).
3. Para cada batch:
   - Execute os steps diretamente (Read/Edit/Write/Bash).
   - Marque os checkboxes (`- [x]`) no plano conforme conclui.
   - No fim do batch, rode a suíte de testes relevante.
   - **[se o nível pedir] Juiz**: despache o revisor sobre o batch **antes** do checkpoint.
   - **Checkpoint**: `AskUserQuestion` — "Batch N concluído (tasks X-Y). Aprovar e seguir para o
     próximo? (sim / revisar / parar)".
4. Com a aprovação, siga para o próximo batch até terminar.

**Vantagem:** mais rápido e mantém o contexto. **Desvantagem:** o contexto cresce e pode ser
compactado em planos grandes.

### Quando um step falha

Pare na hora — não tente consertar em silêncio fora do escopo da task. Reporte o que falhou, o
erro e o seu diagnóstico em uma ou duas linhas, e **ofereça a saída via `AskUserQuestion`**:

- **Ajustar o plano e seguir** — a realidade divergiu do plano (assinatura diferente, arquivo
  que não existe mais, biblioteca que mudou). Atualize o `plan.md`, registre em "Ajustes durante
  a execução" e continue.
- **Refazer o batch** — o erro foi de execução, não de plano. Desfaça o que ficou pela metade e
  rode de novo. Se houver commit do checkpoint anterior, ele é o ponto de volta.
- **Parar aqui** — deixa o estado como está, com o plano marcado até onde deu, para retomar
  depois.

Um step que falha **três vezes seguidas** vira parada obrigatória: o problema não é o passo, é o
plano ou o ambiente.

### Retomar uma execução

Sessão que morre no meio acontece. O plano é o que permite voltar:

1. Leia o `plan.md` e conte as tasks marcadas.
2. `AskUserQuestion` — "O plano está em X de N tasks. Continuar da task X+1?"
   (**Continuar** / **Revisar o que foi feito antes** / **Refazer o plano**).
3. Antes de seguir, confira que o que está marcado existe mesmo no código (os arquivos da task
   estão lá, os testes passam). Checkbox marcado com trabalho perdido é pior que checkbox vazio.
4. Registre a retomada em **"## Ajustes durante a execução"** no fim do `plan.md`:

```markdown
## Ajustes durante a execução

- **2026-09-25** — retomada na task 7; a task 6 estava marcada mas o teste não passava, refeita.
- **2026-09-25** — task 9 alterada: a API devolve `id` como string, não int (spec assumia int).
```

Esse log é o que a `sw-brainstorming` lê depois para saber o que a execução descobriu.

### Estado do dossiê

Se o plano vive num dossiê (`docs/specs/<slug>/`), mantenha o estado em dia — é o que faz o
índice em `docs/specs/README.md` dizer a verdade sobre o que está em andamento:

```bash
DOSSIE=$(ls ~/.claude/skills/sw-brainstorming/scripts/dossie.py \
            ~/.claude/plugins/*/sw-brainstorming/skills/sw-brainstorming/scripts/dossie.py \
            2>/dev/null | head -1)
python3 "$DOSSIE" estado <slug> em-execucao   # ao iniciar a execução
python3 "$DOSSIE" estado <slug> concluido     # ao terminar todas as tasks
```

**Esses dois estados são responsabilidade desta skill** — a `sw-brainstorming` só marca
`aprovado`. Se a execução foi cancelada e ninguém vai retomar, diga isso ao usuário e pergunte
se marca `concluido` mesmo assim, para o índice não anunciar trabalho parado como se estivesse
andando.

### Ao terminar: o spec ainda vale?

Execução descobre coisa. Ao fechar a última task, **ofereça via `AskUserQuestion`** levar de
volta ao `spec.md` o que mudou: uma seção **"## Decisões da execução"** com o que foi feito
diferente e por quê (o log de "Ajustes durante a execução" é a matéria-prima). Um spec que
morre no primeiro dia do build vira documento de ficção — e é ele que a próxima pessoa vai ler.

### Regras comuns aos dois modos

- **Commit nos checkpoints (se for git):** a cada checkpoint (fim de task no modo Subagent,
  fim de batch no modo Inline), **pergunte via `AskUserQuestion`**: "Commitar agora?
  (sim / não / depois)". Se **sim**, use a skill **`sw-git-commit`** se estiver disponível
  (ela separa em Conventional Commits bem escopados); senão, faça um Conventional Commit
  simples só dos arquivos daquele checkpoint. **Nunca commite sem o "sim"** — nem dentro de uma
  task, nem por iniciativa de um subagente.
- **Testes ao concluir:** terminadas as tasks, se o plano criou ou alterou testes, **ofereça via
  `AskUserQuestion`** rodar o diagnóstico da **`sw-auto-test`** (se instalada) sobre o que foi
  mexido — é o que pega teste que passa sem provar nada. Só oferece.
- **Mensagem de PR ao concluir (se for git):** ao terminar todas as tasks, se a branch atual
  tiver commits que ainda não estão na base, **ofereça via `AskUserQuestion`** gerar a descrição
  do PR com a skill **`sw-pr-message`** (se estiver disponível). Só oferece — não gera sem o "sim".
- **Plano é a fonte da verdade:** atualize os checkboxes (`- [x]`) conforme as tasks terminam.
  Se durante a execução o plano se mostrar **errado/incompleto** (a realidade divergiu),
  **atualize o arquivo do plano** (ajuste/insira tasks) em vez de improvisar fora do escopo —
  e avise o usuário do ajuste, registrando em "Ajustes durante a execução".
