---
name: sw-auto-test
description: >
  Automatically generates tests for any project, regardless of language or framework.
  Detects project structure (monorepo, frontend/backend, microservices), identifies
  programming languages, finds existing test frameworks, and generates appropriate tests
  for features being implemented. Use this skill whenever the user asks to generate tests,
  create test coverage, write tests for a feature, test a file or directory, or mentions
  "auto-test", "test-gen", "generate tests", "write tests", "add tests", "test coverage".
  Also use for "test this", "cover this with tests", "what's untested", and for judging an existing
  suite: "are my tests any good?", "review my test suite". Covers unit, integration and e2e — it
  asks which type and adapts framework, analysis and generated code to it and to the stack.
  Dispara também em português: "cria os testes", "escreve os testes de", "cobre com testes",
  "gera teste unitário", "meus testes estão bons?", "diagnostica os testes", "a suíte presta?",
  "revisa a bateria de testes", "que teste está faltando".
---

# Auto Test Generator

Generate tests for any project by detecting the language, framework, and structure automatically. This skill is language-agnostic — it works with PHP, Python, JavaScript/TypeScript, Java, Go, Ruby, Rust, C#, and any other language with a testing ecosystem.

## Antes de tudo: resíduo de uso anterior

Nos **dois modos**, comece com `python3 <skill-dir>/scripts/backup.py varrer`: se uma execução
anterior morreu no meio de uma edição, o arquivo do projeto ficou alterado, e é isto que devolve.
`nenhum resíduo pendente` → siga. Outra saída: conte o que voltou; o que **não** voltou (cópia
ausente, exit 2) precisa da atenção do usuário antes de qualquer outra coisa.

## How It Works

The process follows four phases: **Detect → Ask Test Type → Analyze → Generate**. Never skip detection — understanding the project comes before writing a single test. And never skip the test-type question — unit, integration, and e2e tests differ in framework, structure, and what gets mocked, so guessing wrong wastes the whole generation.

### Phase 1: Detect the Project

Before generating anything, build a mental map of the project:

**1. Scan project structure**

Look for signals that reveal the project layout: `./frontend`, `./backend`, `./packages/*` and
`./apps/*` indicate a monorepo; `./src`, `./app` or `./lib` at root, a single app; and the manifest
(`package.json`, `composer.json`, `pyproject.toml`, `go.mod`, `composer.json`, `Gemfile`…) names the stack.

If the project has multiple languages (e.g., PHP backend + Vue frontend), treat each as an independent sub-project. Detect and generate tests for each separately.

**2. Identify the language and the existing framework** — tabelas de sinal → linguagem, config e
indícios de suíte de integração/e2e: [`references/frameworks.md`](references/frameworks.md).

If a framework exists for the requested test type, use it. If not, proceed to Phase 4 to suggest one.

### Phase 2: Ask the Test Type

Ask which type the user wants via `AskUserQuestion` (multiSelect): **Unit** (one unit in isolation,
everything external mocked), **Integration** (modules together, real infra) or **E2E** (full user
flow, nothing mocked). **Skip the question** only when the user already stated the type, or when a
single type makes sense — and say which type you assumed. The chosen type governs scope, mocks,
target, speed and what a failure means; the table is in
[`references/generation.md`](references/generation.md). Several types → one Analyze + Generate each.

### Phase 3: Analyze What to Test

Three strategies, used based on context:

Três estratégias: **diff do git** ("testa o que eu mudei"), **alvo apontado** (arquivo, pasta,
feature) e **varredura** ("o que está sem teste"). Comandos e o que ler em cada uma:
[`references/generation.md`](references/generation.md).

**Prioritization order** — regardless of strategy, prioritize what to test in this order:
1. **Business logic** — rules, calculations, validations, state machines
2. **API surface** — endpoints, public methods, interfaces
3. **Edge cases** — error handling, boundary values, null/empty inputs

**Filter the analysis through the chosen test type** — the same code yields different test targets:

- **Unit** → individual functions and methods with logic worth isolating: calculations, validations, branching, state transitions. Skip thin glue code (a controller that only delegates) — it has nothing to unit-test.
- **Integration** → the boundaries: repository/DAO methods against a real database, HTTP handlers through the framework's test client (Laravel `$this->get()`, FastAPI `TestClient`, Spring `MockMvc`), queue consumers, cache layers, transactions. Identify which infra each boundary needs (DB, RabbitMQ, Redis) and check whether the project's `docker-compose` already provides it.
- **E2E** → user journeys, not files. Map the routes/pages/commands first, then pick the critical flows: authentication, the main business transaction, destructive actions. Each test is a scenario ("user logs in, adds item, checks out"), not a function.

### Phase 4: Generate Tests

**If no test framework exists:**

Recommend a framework based on the detected **language** and the chosen **test type**, using the matrix below, and wait for user approval. Do not install or configure anything without explicit confirmation.

Veja a matriz completa em [`references/frameworks.md`](references/frameworks.md).

**Empate** (PHPUnit×Pest, Vitest×Jest, Playwright×Cypress) vira `AskUserQuestion`; critérios em
[`references/frameworks.md`](references/frameworks.md). Sinal no projeto desempata sozinho.

**Infraestrutura de integração** (`docker-compose`, testcontainers, banco de teste do framework;
nunca dev nem produção): [`references/generation.md`](references/generation.md).

After user approves, set up the minimal configuration needed (config file + dependency).

**Onde gravar e em que estilo** (convenção existente, tipos em pastas separadas, nome que descreve
comportamento): [`references/generation.md`](references/generation.md) — e o local vai a menu.

**AAA é o padrão.** Por que, como marcar as fases, e os casos em que ele não se aplica (table-driven, property-based, snapshot, e2e): [`references/generation.md`](references/generation.md).

**Antipadrões** (agir no Arrange, vários Acts, asserção escondida no setup, Arrange oculto na classe base): [`references/generation.md`](references/generation.md).

**Mocks seguem o tipo:** unit mocka tudo externo; integração usa infra real e mocka só o que cruza a
fronteira; e2e não mocka nada dentro do app. Detalhes: [`references/generation.md`](references/generation.md).

**After generating tests:**

1. Create the test files directly in the project
2. **Rode a suíte** e mostre o resultado. Teste gerado que não roda não é entrega.
3. **Prove o vermelho** em até 3 testes — o passo a passo está em
   [`references/generation.md`](references/generation.md), que também traz baseline, determinismo
   e a regra de nunca forçar verde. **Leia antes de gerar.**
4. Show a summary:
   - Test type(s) generated (unit / integration / e2e)
   - Files created (with paths)
   - Number of tests per file
   - What each test covers (brief description)
   - How to run them (the exact command, per suite)
   - Infrastructure prerequisites, if any (e.g., `docker compose up -d mariadb` before the integration suite, app running before e2e)

## Modo diagnóstico — avaliar os testes que já existem

Rode este modo quando o pedido for sobre a **qualidade da suíte** ("meus testes estão bons?",
"diagnostica os testes", "a suíte presta?"), e o modo gerar quando o pedido for **escrever teste
novo**. Frase ambígua ("olha meus testes") → decida com `AskUserQuestion`, nunca no chute.
Qualidade do **código de produção** não é aqui: isso é `sw-code-review`.

### 1. Escopo

Em monorepo, o padrão é o pacote em que o usuário está ou que ele apontou. Ofereça ampliar para o
repositório inteiro via `AskUserQuestion` — não amplie sozinho.

### 2. Apurar sem executar nada

```bash
python3 <skill-dir>/scripts/diagnose.py [--escopo <pacote>]
```

Sai com 0 e imprime o caminho do `fatos.json`, o inventário, as stacks e quantos sinais achou.
Exit 2 → mostre a mensagem e pare (sem teste no escopo, `--repo`/`--escopo` inexistente).
Se ele restaurar resíduo de backup, **diga isso ao usuário**: algum uso anterior morreu no meio.

### 3. Perguntar sobre executar

A execução é o que traz suíte verde/vermelha, tempo por teste e cobertura — e é opt-in. Pergunte
via `AskUserQuestion`, **mostrando o comando** que será usado (está em `fatos.stacks`) e o que foi
detectado em `fatos.ambiente.banco`:

- **Só estática** → siga com o que já tem; cobertura e velocidade ficarão `⚪ sem dados`.
- **Descoberta + suíte** → `--executar`.
- **Com cobertura** → `--executar --cobertura`.

Havendo banco no ambiente, o script **para** e pede `--banco-ok`. Repasse o aviso ao usuário com
o que foi detectado e só acrescente a flag com o "sim" dele. Integração e e2e só sob pedido
explícito. Timeout padrão de 300s; estouro vira achado e a skill continua.

### 4. Julgar

Leia o `fatos.json` inteiro e **apenas os arquivos listados em `suspeitos`** — não leia a suíte
toda. Escreva `achados.json` na mesma pasta:

```json
{ "versao": 1,
  "achados": [{"regra": "assercao_tautologica", "dimensao": "confiabilidade", "confianca": "media",
               "caminho": "tests/unit/test_x.py", "linha": 42,
               "problema": "só verifica que o retorno não é nulo",
               "correcao": "asserte o valor esperado de `calcular_total`", "sinal": null}],
  "nao_e_problema": [{"caminho": "tests/unit/test_y.php", "motivo": "convenção diferente da nossa, porém consistente"}] }
```

Regras:
- **Confiança alta exige lastro**: só use quando existir um sinal do script para aquele arquivo, e
  cite o id dele em `sinal`. Os ids e o que cada regra significa estão em
  [`references/diagnostico.md`](references/diagnostico.md). Sem lastro, o `report.py` recusa.
- **Confiança baixa** é para indício — ela entra no relatório como "verificar", nunca como corrigir.
- **Um achado por problema**, com `arquivo:linha` que o usuário possa clicar.
- O que você julgar e **não** for problema (convenção diferente, mas consistente) vai em
  `nao_e_problema` — evita que o relatório vire lista de falso positivo.
- O que procurar, além dos sinais: asserção tautológica ou frouxa; mock do próprio sujeito, ou
  tudo mockado a ponto de o teste verificar só o mock; asserção em detalhe interno; nome que não
  descreve comportamento; teste que testa o framework; vários comportamentos num teste; caminho
  crítico sem teste (cruze `fatos.cobertura` com o código).

### 5. Relatório

```bash
python3 <skill-dir>/scripts/report.py
```

Exit 3 → ele lista **todos** os problemas do `achados.json`; corrija todos e rode de novo. Na 3ª
recusa seguida, pare e mostre ao usuário. Exit 2 → ambiente (fatos de outra branch, por exemplo):
mostre e pare, sem mexer no `achados.json`.

### 6. Correção guiada

Abra um menu de rumo (`AskUserQuestion`): **corrigir os de confiança alta** · **revisar item a
item** · **só o relatório**. Depois:

1. **Antes de editar qualquer arquivo**, guarde o original:
   `python3 <skill-dir>/scripts/backup.py guardar <arquivo>`. Avise se o arquivo tiver alteração
   não commitada — a correção vai se misturar ao trabalho dele.
2. Corrija **em lotes pequenos** (3 a 5 arquivos).
3. Rode a suíte do lote. Verde → `backup.py descartar <arquivo>`. Vermelho →
   `backup.py restaurar <arquivo>` e registre no relatório por que aquele item ficou de fora.
   **Nunca use `git checkout`**: apagaria o trabalho não commitado do usuário.
4. **Suíte já vermelha antes de começar** é o achado nº 1: pare e pergunte se o usuário quer
   consertar isso primeiro. Corrigir teste sobre suíte quebrada esconde o que quebrou.

Feche informando: caminho do relatório, notas por dimensão, quantos achados por confiança, o que
foi corrigido, o que foi revertido, e o que ficou `⚪ sem dados` por falta de execução.

Exemplos completos (PHPUnit, projeto sem suíte, monorepo, e2e): [`references/generation.md`](references/generation.md).

## Important

- Always read and understand the source code before generating tests. Never generate tests based on file names or assumptions alone.
- Respect the chosen test type strictly — don't drift. A "unit" test that boots the framework and hits a database is an integration test wearing the wrong name; an "integration" test with everything mocked tests nothing. If the requested type doesn't fit the target code (e.g., e2e for a pure utility function), say so and propose the type that fits.
- Tests must be runnable without modification. If you're unsure about an import path or dependency, verify it exists.
- When the project uses a custom test helper, base class, or factory pattern — use those. Don't reinvent conventions the team already established.
- **Follow the AAA pattern by default** (see Phase 3 → Test style). It applies across every language and framework. The only reason to deviate is when existing tests in the project use a different style — then match them for consistency.
- If the code is untestable (tightly coupled, no dependency injection, global state), note this in the summary and suggest minimal refactoring to make it testable, but still generate the best tests possible for the current state.
