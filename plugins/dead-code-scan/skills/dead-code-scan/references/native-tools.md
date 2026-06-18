# Ferramentas nativas de dead-code por linguagem

Prefira sempre a ferramenta nativa: ela entende o AST/tipos e erra muito menos que busca textual.
Detecte se já está instalada (no `package.json`/`pyproject`/etc. ou no PATH); se não estiver mas
for trivial rodar de forma efêmera (`npx`, `uvx`, `go run`), **ofereça rodar via AskUserQuestion**
antes — não instale dependência no projeto sem aprovação.

Legenda do que cada uma pega: **F**=arquivos órfãos · **E**=exports não usados · **D**=deps não usadas ·
**V**=variáveis/imports · **M**=métodos/funções/classes.

## JavaScript / TypeScript
- **knip** (melhor, abrangente) — `npx knip` · pega **F E D V M**. Lê entradas do projeto; ótimo pra monorepo.
- **ts-prune** — `npx ts-prune` · exports TS não usados (**E**).
- **depcheck** — `npx depcheck` · dependências não usadas/faltando (**D**).
- **ESLint** — regra `no-unused-vars` / `@typescript-eslint/no-unused-vars` (**V**); `import/no-unused-modules` (**E**).
- Dica: comece por `knip`; ele sozinho cobre quase tudo.

## Python
- **vulture** — `uvx vulture <pkg>` ou `vulture .` · funções/classes/variáveis não usadas (**M V**), com % de confiança embutido.
- **ruff** — `ruff check --select F401,F811,F841` · imports não usados (F401), redefinição (F811), variável local não usada (F841) (**V**). Rápido.
- **pyflakes** — alternativa leve ao ruff (**V**).
- **deptry** — `uvx deptry .` · dependências não usadas/faltando/transitivas (**D**).

## Go
- **deadcode** (oficial, x/tools) — `go run golang.org/x/tools/cmd/deadcode@latest ./...` · funções inalcançáveis (**M**).
- **staticcheck** — `staticcheck ./...` · inclui `U1000` (unused) para código não exportado (**M V**).
- **go vet** — checagens básicas. O próprio compilador já barra import/var local não usados.

## Rust
- O **compilador** já emite `dead_code`, `unused_imports`, `unused_variables` — rode `cargo build`/`cargo check` e leia os warnings (**M V**).
- **cargo-machete** — `cargo machete` · dependências não usadas no `Cargo.toml` (**D**).
- **cargo-udeps** (nightly) — `cargo +nightly udeps` · deps não usadas, mais preciso (**D**).

## PHP
- **PHPStan** — `phpstan analyse` com nível alto; a extensão **phpstan/phpstan-deadcode** acha métodos/constantes privados não usados (**M**).
- **Psalm** — `psalm --find-dead-code` (ou `--find-unused-code`) · código não usado (**M V**).
- **composer-unused** — `composer unused` · pacotes do `composer.json` não usados (**D**).
- **composer-require-checker** — deps usadas mas não declaradas.

## Java / Kotlin
- **PMD** — regras `UnusedPrivateField`, `UnusedPrivateMethod`, `UnusedLocalVariable` (**V M**).
- **SpotBugs** — detecta campos/métodos não usados.
- **error-prone** (Java) / **detekt** (Kotlin, `UnusedPrivateMember`) (**V M**).
- IDE (IntelliJ "Unused declaration") é o mais preciso, mas não é CLI.

## C# / .NET
- **Roslyn analyzers** — `IDE0051` (membro privado não usado), `IDE0052` (campo só escrito), `CS0219`/`CS0168` (var não usada). Rode `dotnet build` com analyzers ligados ou `dotnet format analyzers` (**V M**).
- **ReSharper CLI** (`jb inspectcode`) — análise profunda de não usados.

## Ruby
- **RuboCop** — `Lint/UselessAssignment`, `Lint/UnusedMethodArgument` (**V**).
- **debride** — `debride <dir>` · métodos possivelmente não chamados (**M**).

## Swift
- **periphery** — `periphery scan` · excelente pra dead code em Swift (**F E M V**).

## Dart / Flutter
- **dart analyze** — reporta imports/elementos não usados (**V M**).

## CSS / estilos
- **PurgeCSS** / **UnCSS** — seletores CSS não usados em relação ao HTML/JS.

## Quando NÃO há ferramenta
Caia para a heurística genérica do SKILL.md (busca de símbolos com `rg`, contagem de referências
cross-file, guards de falso positivo). E lembre: heurística é base de **média** confiança quando
sozinha; vira **alta** só quando a ferramenta nativa concorda.
