# Modo gerar — detalhes

## Baseline antes de gerar

Antes de escrever teste novo, saiba se a suíte já estava vermelha. Ofereça rodar
(`diagnose.py --executar`) e guarde o resultado. **Sem baseline**, diga no resumo final: "não dá
para distinguir bug do código de quebra que já existia".

## Prova do vermelho

Depois de gerar, prove que o teste acusa o erro que promete acusar. Em **até 3 testes**, os que
cobrem regra de negócio — nunca glue code:

1. **Varra resíduo antes** (`backup.py varrer`): sobra de um uso anterior misturaria dois
   estados na mesma janela.
2. Pré-requisitos: é repositório git; o arquivo **de produção** a mutar está versionado e sem
   alteração pendente (`git status --porcelain -- <arquivo>` vazio); nenhum watcher, dev server ou
   formatador ao salvar está rodando (**pergunte ao usuário**; na dúvida, pule a prova e diga por quê).
3. `python3 <skill-dir>/scripts/backup.py guardar <arquivo de produção>`.
4. Mute **uma** coisa por vez no trecho que o teste cobre: inverter uma condição, trocar o retorno
   por constante, neutralizar a validação.
5. Rode **só aquele teste**.
6. `python3 <skill-dir>/scripts/backup.py restaurar <arquivo>` — sempre, inclusive se algo falhar.
7. **Teste ficou vermelho** → ele presta. **Continuou verde** → é o defeito que esta prova existe
   para achar: relate ("o teste não prova o comportamento que o nome promete") e proponha o ajuste.
   Não reescreva sozinho.

8. **Confira a volta.** O `restaurar` avisa quando o arquivo tinha alteração posterior ao
   backup — se aparecer, diga ao usuário o que foi perdido. Se o runner morrer, estourar o tempo
   ou a sessão cair com a mutação no lugar, o resíduo fica registrado, e o `varrer` do próximo
   uso devolve o arquivo. É por isso que ele abre toda execução.

Sem git, não faça a prova: não há como garantir a volta com segurança.

## Determinismo no teste gerado

Semente fixa em qualquer aleatório; relógio congelado (freezegun, `vi.setSystemTime`,
`Carbon::setTestNow`) em vez de `datetime.now()`; nada de `sleep`; cada teste monta o próprio
estado, sem depender de ordem.

## Proibido forçar verde

- Não altere código de produção para o teste passar.
- Não use `skip`/`xfail`/`only` para esconder falha.
- Nada de asserção que passa de qualquer jeito ("não é nulo", "não lançou").
- Teste novo falhando por **bug do código** → relate o bug. Consertar o teste aí é apagar o achado.

## Cobertura

Só com a ferramenta nativa (`--cov`, `--coverage`, `--coverage-clover`). Diga sempre que percentual
alto não significa suíte boa — ele mede linha executada, não comportamento verificado.

## AAA: por que é o padrão, como marcar as fases e quando não se aplica

**AAA Pattern — the default structure**

Every generated test follows three clearly separated phases:

1. **Arrange** — prepare inputs, instantiate the subject, set up mocks, build initial state
2. **Act** — execute the single behavior under test (usually one line)
3. **Assert** — verify the outcome against expectations

Why AAA is the default:

- It's framework- and language-agnostic, so the skill can apply it uniformly across PHP, Python, JS, Go, Java, Ruby, etc.
- It makes "what is being tested" obvious at a glance — the reader jumps straight to the Act line to understand the subject under test
- It naturally enforces **one behavior per test**, which keeps failures diagnostic (a red test points to a specific broken behavior, not "something somewhere")
- It discourages hidden assertions spread through setup code, which are the main source of flaky, hard-to-debug tests

How to mark the phases in generated code:

- Prefer **blank lines** between phases — the visual break is enough in most cases
- In longer tests (>10 lines or non-obvious setup), add inline comments: `// Arrange`, `// Act`, `// Assert` (use the comment syntax of the target language)
- For trivial one-liners where the whole test collapses into a single expression (e.g., `assertEquals(4, double(2))`), AAA is implicit — don't add ceremony

Exemplos em PHP, Python, TypeScript, Go, Java e Ruby em [`aaa-por-linguagem.md`](aaa-por-linguagem.md).

When AAA doesn't fit (and that's fine):

- **BDD / Given-When-Then** — RSpec, Cucumber/Gherkin, or Jasmine-style specs use `given/when/then` which maps 1:1 to Arrange/Act/Assert. Keep the project's convention — the underlying principle is the same.
- **Table-driven / parameterized tests** — in Go or Rust, the Arrange phase lives in the table rows; each row runs Act + Assert in a loop. Structural separation is preserved, just factored differently.
- **Property-based tests** (Hypothesis, QuickCheck, fast-check) — generators replace explicit Arrange. Act and Assert stay clearly separated inside the property body.
- **Snapshot / golden tests** — Arrange and Act look normal; Assert is a single `toMatchSnapshot()` / `cupaloy.SnapshotT()` call. Still AAA.
- **Trivial one-liners** — `assertEquals(4, double(2))` is fine as-is. Don't pad it with comments.
- **E2E scenarios** — a user flow has multiple act/assert steps (navigate → assert page → click → assert result). Don't force a single Act; structure the test as named user steps and keep each step's action and verification adjacent.

## Antipadrões ao gerar teste

Anti-patterns to avoid when generating tests:

- **Acting in the Arrange phase** — e.g., calling the method under test to set up state for another test. If setup requires the subject itself, that's a design smell; create the state through a helper or fixture, not through the Act.
- **Multiple unrelated Acts in one test** — each additional Act dilutes what the test is about. Split into separate tests with specific names.
- **Assertions sprinkled through the setup** — defensive checks in Arrange ("make sure the DB is empty") belong in fixtures or guard clauses, not inline — they distract from the real assertions at the end.
- **Hidden Arrange in base classes** — if a shared fixture performs non-obvious setup, either (a) name it descriptively (`setUpUserWithActiveSubscription`) so the intent is clear, or (b) inline the setup for clarity, trading duplication for readability.

## Exemplos de ponta a ponta

## Examples

**Example 1 — PHP project with existing PHPUnit:**
```
User: "generate tests for the UserService"
→ Detect: PHP, PHPUnit exists (phpunit.xml found), tests/Unit and tests/Feature dirs
→ Ask: unit, integration, or e2e? → User picks: unit
→ Read: app/Services/UserService.php
→ Find: createUser(), updateProfile(), deleteUser(), validateEmail()
→ Generate: tests/Unit/Services/UserServiceTest.php (following existing convention)
→ Summary: unit suite, 4 test methods covering create, update, delete, validation + edge cases
```

**Example 2 — Python project without tests:**
```
User: "add tests for my changes"
→ Detect: Python (pyproject.toml), no test framework found
→ Ask: unit, integration, or e2e? → User picks: unit + integration
→ Suggest: "I recommend pytest for both suites. Should I set it up?"
→ User: "yes"
→ Configure: pip install pytest, create pytest.ini
→ Analyze: git diff shows changes in api/handlers.py and models/user.py
→ Generate: tests/unit/test_user.py (mocked deps),
            tests/integration/test_handlers.py (FastAPI TestClient + test DB)
→ Summary: 8 unit tests + 4 integration tests; integration suite needs
           `docker compose up -d postgres` first
```

**Example 3 — Monorepo:**
```
User: "scan the project for missing tests"
→ Detect: ./frontend (TypeScript + Vitest), ./backend (Go)
→ Ask: unit, integration, or e2e? → User picks: unit
→ Scan frontend: 15 components, 8 have tests, 7 missing
→ Scan backend: 20 packages, 12 have tests, 8 missing
→ Report: "Found 15 untested files. Want me to generate tests for all, or pick specific ones?"
```

**Example 4 — type stated upfront, question skipped:**
```
User: "e2e do fluxo de checkout"
→ Detect: Vue frontend, no e2e framework found, no signal breaking the Playwright/Cypress tie
→ Type already stated (e2e) → skip the type question
→ Ask (tie): Playwright (cross-browser, trace viewer) vs Cypress (team familiarity)?
→ User picks: Playwright → confirm setup
→ Analyze: map routes → cart, checkout, payment confirmation
→ Generate: e2e/checkout.spec.ts (3 scenarios: happy path, empty cart, payment declined)
→ Summary: e2e suite; requires the app running (`npm run dev`) before `npx playwright test`
```

## Infraestrutura para teste de integração

**Integration test infrastructure:** real dependencies need to come from somewhere. In order of preference:
1. Reuse services from the project's existing `docker-compose` (a dedicated test database/vhost, not the dev one)
2. Testcontainers (or equivalent) when the language ecosystem supports it
3. A framework-managed test database (Laravel `RefreshDatabase`, Django test DB, Rails fixtures)

Never point integration tests at a development or production database. If no isolated option exists, propose adding a test service to `docker-compose` and wait for approval.

## Onde gravar e em que estilo

**Test location:**

- If tests already exist in the project → follow the same convention
- If the project separates suites by type (`tests/Unit/`, `tests/Integration/`, `tests/Feature/`, `e2e/`) → put each generated test in the matching directory; never mix types in one suite
- If no tests exist → ask the user: "Should I put tests alongside the source files or in a separate `tests/` directory?" When generating more than one type, default to type-separated directories (`tests/Unit/`, `tests/Integration/`, `e2e/`) so each suite can run independently

**Test style:**

- If tests already exist → match the existing naming, structure, and patterns (even if they don't use AAA — consistency beats ideal form)
- If no tests exist → default to **AAA (Arrange-Act-Assert)**. Veja a seção do AAA neste arquivo.
- Test names always describe the behavior being verified: `test_returns_error_when_email_is_invalid`, not `test_validate_email_1`
- Group related tests in describe/context blocks where the framework supports it (RSpec `describe`, Jest `describe`, PHPUnit `@group`)

## O que muda conforme o tipo de teste

The chosen type drives every later decision:

| Aspect | Unit | Integration | E2E |
|---|---|---|---|
| Scope | one class/function | a boundary between modules | a complete user journey |
| Dependencies | mock everything external | real infra (test DB, containers); mock only third-party APIs | nothing mocked; app runs against a test environment |
| Typical target | business logic, validations, calculations | repositories, HTTP handlers, queue consumers, cache | login, checkout, CRUD flows, critical paths |
| Speed expectation | ms | seconds | minutes |
| A failure means | logic bug | wiring/contract/query bug | anything in the stack broke |

## As três estratégias de análise

**Strategy A — Git diff (when user says "test my changes", "test what I changed", or no specific target)**

```bash
# Check staged files first, then unstaged changes
git diff --cached --name-only --diff-filter=ACMR
git diff --name-only --diff-filter=ACMR
```

Read each changed file. Identify new or modified:
- Functions and methods (public surface)
- Classes and their public API
- API endpoints / route handlers
- Business logic (calculations, validations, state transitions)

**Strategy B — User-pointed (when user specifies a file, directory, or feature)**

Read the specified code. Understand what it does before writing tests. Follow imports and dependencies to understand the full picture.

**Strategy C — Full scan (when user asks for "coverage", "what's untested", "scan the project")**

Cross-reference source files with test files. Report what's covered and what's missing. Prioritize generating tests for the most critical uncovered code.

## Mocks conforme o tipo de teste

**Mocks and dependencies — governed by the test type:**

- **Unit** → mock everything external to the subject: database, HTTP APIs, third-party SDKs, filesystem, clock. The test must run with no infrastructure.
- **Integration** → use the real infrastructure the test is about (database, queue, cache) and mock only what crosses the system boundary: third-party HTTP APIs, payment gateways, email/SMS providers. Mocking the database in a repository integration test defeats its purpose.
- **E2E** → mock nothing inside the app. External paid/side-effectful services (payments, SMS) go through sandbox modes or a fake server (WireMock, Mailpit), configured at the environment level — not in test code.
- Use the mocking library standard for the detected framework (Mockery for PHP, unittest.mock for Python, vi.mock/jest.mock for JS, etc.)

## A pergunta do tipo de teste, na íntegra

### Phase 2: Ask the Test Type

Before analyzing any code, ask which type of test the user wants, using the AskUserQuestion tool (multiSelect: true — more than one type can be picked):

- **Unit** — one class/function in isolation; all external dependencies mocked; runs in milliseconds
- **Integration** — modules working together (service + real database, API handler + queue); only third-party services mocked
- **E2E** — full user flow through the running application; nothing mocked

**Skip the question** only when the user already stated the type ("write unit tests for X", "e2e do checkout", "integration test for the repository") or when only one type makes sense (a pure-function utility library → unit). When skipping, state the assumed type before generating.

O tipo escolhido governa escopo, mocks, alvo, velocidade e o que uma falha significa — a tabela está logo abaixo.

If multiple types were selected, run Analyze + Generate once per type, keeping each suite in its own location and convention.
