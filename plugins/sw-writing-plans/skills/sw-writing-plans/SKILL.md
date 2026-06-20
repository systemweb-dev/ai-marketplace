---
name: sw-writing-plans
description: >-
  Transforma um spec/requisitos em um plano de implementação detalhado (estrutura de
  arquivos + tasks bite-sized com código e comandos exatos, qualidade de teste, sem
  placeholders) e ORQUESTRA a execução task-by-task com checkpoints de aprovação. Use
  quando já existe um design/spec/requisitos e é hora de planejar COMO construir e executar
  — frases como "faz o plano", "plano de implementação", "como vou construir isso", "quebra
  em tasks", "monta o passo a passo", "bora implementar isso", "executa o plano". É o passo
  depois da sw-brainstorming. NÃO use para: decidir O QUE construir do zero (isso é a
  sw-brainstorming), nem para uma edição trivial pontual. Interação em português, via
  AskUserQuestion.
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Anuncie no início:** "Estou usando a skill sw-writing-plans para criar o plano de implementação."

**Regra:** toda decisão ao usuário é via `AskUserQuestion` (menu clicável) — nunca pergunta em texto solto.

**Branch/worktree (se for git):** no início, se o diretório for um repositório git, **ofereça via `AskUserQuestion`** criar um branch ou worktree dedicado pra este trabalho — ex.: **branch `feat/<tópico>` / worktree dedicado / continuar no branch atual**. Não crie nada sem a escolha do usuário.

**Save plans to:** `~/.claude/projects/<cwd-slug>/plans/YYYY-MM-DD-<feature-name>.md`
- **Slug dinamico**: derivar do diretorio de trabalho atual rodando `pwd | sed 's|/|-|g'`. Ex: cwd `/var/www/challenge` → slug `-var-www-challenge` → path `~/.claude/projects/-var-www-challenge/plans/...`. NUNCA usar nome fixo de projeto.
- Criar o diretorio se nao existir (`mkdir -p`).
- **NAO commitar automaticamente** o plano no git. Deixar o arquivo para o usuario commitar manualmente.
- (User preferences for plan location override this default)

## Tipos de teste (pergunte antes de definir as tasks)

Antes de montar as tasks, **pergunte via `AskUserQuestion` (multiSelect)** quais tipos de teste
o plano deve incluir: **Unit** / **Integração** / **E2E** / **Nenhum** (protótipo ou projeto
sem suíte). Detecte o que o projeto já usa e sugira o(s) mais adequado(s).

- Os steps de teste de cada task seguem **só os tipos escolhidos** — não gere e2e onde unit
  basta (menos teste desnecessário).
- **TDD é flexível:** havendo suíte, escreva o teste primeiro (red → green). Se o usuário
  escolher **Nenhum** ou não houver setup de teste, **não force** test-first — troque o par
  "escreve teste / roda" por "implementa + verifica" (rodar o app, conferir a saída) e deixe
  isso explícito nos steps.

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **Execucao:** Implementar este plano task-by-task. Steps usam checkbox (`- [ ]`) para tracking. Ver secao "Execution Handoff" da skill `sw-writing-plans` para os 2 modos de execucao disponiveis.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
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

## No Placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may be reading tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Remember
- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits

## Self-Review

After writing the complete plan, look at the spec with fresh eyes and check the plan against it. This is a checklist you run yourself — not a subagent dispatch.

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Placeholder scan:** Search your plan for red flags — any of the patterns from the "No Placeholders" section above. Fix them.

**3. Type consistency:** Do the types, method signatures, and property names you used in later tasks match what you defined in earlier tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

If you find issues, fix them inline. No need to re-review — just fix and move on. If you find a spec requirement with no task, add the task.

## Aprovação do plano (antes de executar)

Depois do self-review, **apresente o plano e peça aprovação via `AskUserQuestion`**
(**Aprovar / Ajustar / Cancelar**) antes de iniciar qualquer execução. Mostre um resumo
escaneável: objetivo, lista de tasks (títulos) e arquivos tocados — não despeje o plano
inteiro. Se pedir ajuste, edite o plano e re-rode o self-review. Só vá pra execução com
aprovação.

## Execution Handoff

Apos salvar o plano, via `AskUserQuestion`, perguntar qual modo de execucao o usuario prefere. As duas opcoes sao autossuficientes — nao dependem de skills externas (`superpowers:*`).

**Mensagem sugerida ao apresentar as opcoes:**
> "Plano salvo em `<path>`. Dois modos de execucao:
> - **Subagent-Driven**: cada task roda num subagent novo (contexto limpo). Revisao entre tasks.
> - **Inline**: execucao na mesma sessao, em batches com checkpoints."

### Modo 1 — Subagent-Driven

**Como orquestrar (instrucoes embutidas, sem depender de sub-skill):**

1. Ler o arquivo do plano na sessao atual.
2. Para CADA task do plano, na ordem:
   - Disparar um subagent via tool `Agent` (subagent_type=`general-purpose`) passando:
     - A task completa (titulo + todos os steps com codigo)
     - Instrucao: "Implemente exatamente esta task. NAO pule steps. NAO refatore fora do escopo. Retorne um resumo curto (<150 palavras) do que foi feito."
   - Esperar o subagent terminar.
   - **Stage 1 review (automatico)**: ler os arquivos modificados e verificar:
     - Todos os steps marcados foram realmente executados?
     - Testes rodam verdes?
     - Codigo bate com o que o plano especificou?
   - **Stage 2 review (humano)**: apresentar ao usuario via `AskUserQuestion`: "Task N concluida. Aprovar e seguir? (sim / revisar / parar)".
   - Se aprovado, marcar checkbox no arquivo do plano (`- [x]`) e seguir para proxima task.
3. Ao final de todas as tasks, reportar resumo consolidado.

**Vantagem**: contexto principal nao infla. Desvantagem: custo maior (cada subagent re-le contexto).

### Modo 2 — Inline Execution

**Como orquestrar (instrucoes embutidas, sem depender de sub-skill):**

1. Ler o arquivo do plano na sessao atual.
2. Agrupar tasks em **batches** de 2-4 tasks relacionadas (ou 1 task se for grande).
3. Para cada batch:
   - Executar todos os steps das tasks do batch diretamente (Read/Edit/Write/Bash).
   - Marcar checkboxes (`- [x]`) no arquivo do plano conforme conclui.
   - Ao final do batch, rodar a suite de testes relevante.
   - **Checkpoint**: parar e perguntar ao usuario via `AskUserQuestion`: "Batch N concluido (tasks X-Y). Aprovar e seguir pro proximo batch? (sim / revisar / parar)".
4. Apos aprovacao, seguir pro proximo batch ate finalizar.

**Vantagem**: mais rapido, mantem contexto. Desvantagem: contexto cresce, pode compactar em planos grandes.

### Regras comuns aos dois modos

- **Commit nos checkpoints (se for git):** a cada checkpoint (fim de task no modo Subagent,
  fim de batch no modo Inline), **pergunte via `AskUserQuestion`**: "Commitar agora?
  (sim / não / depois)". Se **sim**, use a skill **`sw-git-commit`** se estiver disponível
  (ela separa em Conventional Commits bem escopados); senão, faça um Conventional Commit
  simples só dos arquivos daquele checkpoint. **Nunca commite sem o "sim"** — fora dos
  checkpoints não há commit automático.
- **Plano é a fonte da verdade:** atualize os checkboxes (`- [x]`) conforme as tasks terminam.
  Se durante a execução o plano se mostrar **errado/incompleto** (a realidade divergiu),
  **atualize o arquivo do plano** (ajuste/insira tasks) em vez de improvisar fora do escopo —
  e avise o usuário do ajuste.
- Se algum step falhar (teste vermelho, erro inesperado), pare imediatamente e reporte com
  diagnóstico — não tente "consertar" silenciosamente fora do escopo da task.
