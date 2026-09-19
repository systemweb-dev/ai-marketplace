# Matriz de frameworks (linguagem × tipo de teste)

**Framework matrix (language × test type):**

| Language | Unit | Integration | E2E |
|---|---|---|---|
| PHP | PHPUnit | PHPUnit | Playwright (web UI) · PHPUnit against the running app (API) |
| Python | pytest | pytest | Playwright (web UI) · pytest against the running app (API) |
| JS/TS | Vitest | Vitest | Playwright |
| Java | JUnit 5 | JUnit 5 | Playwright (web UI) · JUnit 5 against the running app (API) |
| Go | Built-in `testing` | Built-in `testing` | Playwright (web UI) · `testing` against the running app (API) |
| Ruby | RSpec | RSpec | Capybara (web UI) · RSpec against the running app (API) |
| Rust | Built-in `#[test]` | Built-in `#[test]` (`tests/` dir) | Playwright (web UI) · `#[test]` against the running app (API) |
| C# | xUnit | xUnit | Playwright for .NET (web UI) · xUnit against the running app (API) |

Reading the e2e column: the deciding factor is **what the user interacts with**, not the backend language. Web UI → Playwright (any backend). HTTP API without UI → the same runner as unit/integration, hitting the real running app over HTTP. CLI → the language's test framework spawning the real binary.

## Sinal → linguagem

**2. Identify the language**

Map config files and extensions to languages:

| Signal | Language |
|---|---|
| `composer.json`, `*.php` | PHP |
| `requirements.txt`, `pyproject.toml`, `*.py` | Python |
| `package.json`, `*.ts`, `*.tsx` | TypeScript |
| `package.json`, `*.js`, `*.jsx` (no .ts) | JavaScript |
| `go.mod`, `*.go` | Go |
| `pom.xml`, `build.gradle`, `*.java` | Java |
| `Gemfile`, `*.rb` | Ruby |
| `Cargo.toml`, `*.rs` | Rust |
| `*.csproj`, `*.cs` | C# |
| `build.gradle.kts`, `*.kt` | Kotlin |

## Config do framework por linguagem, e sinais de integração/e2e

**3. Detect existing test framework**

Search for framework config files and test directories:

| Language | Config files to look for | Test directories |
|---|---|---|
| PHP | `phpunit.xml`, `phpunit.dist.xml`, `pest.php` | `tests/`, `test/` |
| Python | `pytest.ini`, `pyproject.toml [tool.pytest]`, `setup.cfg`, `tox.ini` | `tests/`, `test/` |
| JS/TS | `jest.config.*`, `vitest.config.*`, `.mocharc.*`, `karma.conf.*` | `__tests__/`, `tests/`, `*.test.*`, `*.spec.*` |
| Java | `pom.xml (junit dep)`, `build.gradle (testImplementation)` | `src/test/` |
| Go | Built-in (`*_test.go`) | Same package |
| Ruby | `.rspec`, `Gemfile (rspec)`, `test/test_helper.rb` | `spec/`, `test/` |
| Rust | Built-in (`#[test]`, `#[cfg(test)]`) | Same file or `tests/` |
| C# | `*.csproj (xunit/nunit/mstest ref)` | `*.Tests/` project |

Also detect frameworks specific to integration and e2e testing — they often live alongside the unit framework:

| Signal | Means the project already has |
|---|---|
| `playwright.config.*`, `e2e/` dir | Playwright e2e |
| `cypress.config.*`, `cypress/` dir | Cypress e2e |
| `codeception.yml` | Codeception (PHP, supports unit/functional/acceptance) |
| `behat.yml` | Behat acceptance (PHP) |
| `testcontainers` in dependencies | Container-backed integration tests |
| `docker-compose*.yml` with db/queue services | Infra available for integration tests |
| `tests/Integration/`, `tests/Feature/`, `tests/E2E/` dirs | Type-separated suites |

## Empates que viram pergunta

**When two frameworks genuinely tie**, don't pick silently — present both with pros/cons via the AskUserQuestion tool and let the user decide. Known ties to ask about:

- **PHP unit/integration:** PHPUnit (standard, ubiquitous) vs Pest (cleaner syntax, built on PHPUnit) — ask on fresh projects
- **JS/TS unit/integration:** Vitest (fast, ESM-native) vs Jest (larger ecosystem, CRA/older stacks) — ask when the project predates ESM or already has Jest-adjacent tooling
- **Web e2e:** Playwright (cross-browser, trace viewer) vs Cypress (team familiarity, existing Cypress knowledge) — ask when the user or team already knows one of them

A tie only exists when **no signal in the project breaks it** — any existing config, dependency, or test file for one of the options decides immediately without asking.
