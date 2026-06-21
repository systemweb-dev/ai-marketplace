---
name: sw-code-review
description: Code review profundo com deteccao de autorizacao/RBAC ausente, information disclosure em erros, typos cross-file, coercao de tipos em boundaries, disciplina de catch, leitura de regras do projeto, modo PR (vs branch base) e reasoning enriquecido com truth tables e step-by-step proofs. Inclui analise de impacto, contrato, orfaos, cross-repo, supressao de falsos positivos. INVOCAR SOMENTE sob pedido explicito do usuario — via `/sw-code-review` ou frases como "rodar/executar/fazer code review", "code review", "revisa as mudancas", "revisa meu diff", "revisa meu codigo", "review disso". NAO auto-disparar a cada mudanca de codigo. Funciona em qualquer linguagem e framework. Output sempre em portugues.
---

# Code Review

Review profundo e **language-agnostic**, com leitura de regras do projeto, modo PR e reasoning enriquecido (truth tables, step-by-step proofs, impacto quantificado). Os patterns sao genericos — exemplos em linguagens especificas sao apenas ilustracoes a adaptar.

## Principio: Language-Agnostic

Esta skill funciona com **qualquer linguagem e framework**. Todos os patterns de deteccao sao definidos de forma generica. Quando um pattern lista exemplos em linguagens especificas (PHP, JS, Python, Go, Java, Ruby, C#), sao apenas ilustracoes — o pattern se aplica ao equivalente em qualquer outra linguagem. Detectar a linguagem no Step 3b e aplicar os patterns com a sintaxe correspondente.

Leia o arquivo `references/checklist.md` para obter todos os labels, severidades, categorias, templates e mensagens.

## Principio: precisao acima de cobertura (ZERO falso positivo)

Um review que "fala demais" e ignorado. **Prefira perder um achado duvidoso a inventar um falso.** Regras inegociaveis:

- **Todo achado precisa de evidencia** verificavel: `arquivo:linha` + por que e problema. Sem evidencia clara, nao registra.
- **Na duvida, NAO flagueie** — derrube o achado ou rebaixe para confianca baixa com nota "verificar"; nunca como CRITICAL/HIGH.
- **Ferramenta nativa > heuristica** (Step 4c). Quando o regex heuristico e a ferramenta divergem, confie na ferramenta.
- Todo achado passa SEMPRE pela Supressao (5.0) e pela Verificacao (Step 5.5) antes de ser apresentado.

## Workflow

### Step 0: Ler regras do projeto

Antes de qualquer analise, buscar convencoes explicitas do projeto para aplicar como achados de categoria `consistency` ou `refactoring`.

**0a. Localizar arquivos de regras:**

```bash
find . -maxdepth 5 -type f \( \
  -path "*.claude/rules/*.md" -o \
  -path "*.claude/CLAUDE.md" -o \
  -name "CONTRIBUTING.md" -o \
  -name "STYLE.md" -o \
  -name ".editorconfig" \
\) 2>/dev/null
```

Tambem identificar configs de linter/typechecker — eles serao **executados** no Step 4c (nao so contexto):
- `.eslintrc.*`, `eslint.config.*`
- `phpcs.xml`, `phpstan.neon`, `.php-cs-fixer.*`
- `ruff.toml`, `pyproject.toml` (secao `[tool.ruff]`), `.flake8`
- `rubocop.yml`
- `.golangci.yml`

**0b. Parsear regras aplicaveis:**

Para cada arquivo de regras encontrado:

1. Ler o conteudo
2. Extrair:
   - **Escopo** (frontmatter `globs:` ou inferir por contexto — ex: regras em `rules/naming-conventions.md` de projeto PHP aplicam-se a `**/*.php`)
   - **Regras concretas** — qualquer declaracao no formato:
     - "metodos privados em `_camelCase`" -> pattern
     - "sem if aninhado — maximo 1 nivel" -> pattern
     - "API sempre em ingles com snake_case" -> pattern
     - "Campo ENUM no banco = enum PHP obrigatorio" -> pattern
   - **Exemplos CORRETO/ERRADO** — usar como base para regex de deteccao

3. Armazenar a lista de regras com:
   - ID da regra (slug do titulo)
   - Glob de escopo
   - Pattern de deteccao (regex ou descricao)
   - Severidade (default LOW se nao especificada; MEDIUM se a regra usa palavras como "obrigatorio", "sempre", "nunca")
   - Descricao e fonte (arquivo:linha)

**0c. Se nao houver regras:**

Pular este step. As regras do projeto sao opcionais — a skill funciona sem elas usando apenas os patterns generics.

### Step 1: Detectar escopo das mudancas

**1a. Detectar repositorios:**

```bash
git rev-parse --git-dir 2>/dev/null
```

Se funcionar, estamos dentro de um repo git -> **modo single-repo** (comportamento padrao).

Se falhar, verificar se existem sub-projetos com repos git independentes:

```bash
find . -name ".git" -type d -maxdepth 3 2>/dev/null
```

Se encontrar 2+ repos, entrar em **modo multi-repo**:
- Para cada sub-diretorio com `.git`, executar os comandos de diff DENTRO daquele diretorio
- Combinar todos os resultados, prefixando cada arquivo com o path relativo do sub-repo
- Classificar cada sub-repo por tipo (ver Step 1b)
- A analise cross-repo (5k) sera executada APOS todas as analises individuais

Se nenhum repo git encontrado, mostrar mensagem `no_git` do checklist.md e parar.

**1b. Classificar sub-repos (apenas modo multi-repo):**

Para cada sub-repo encontrado, determinar seu tipo automaticamente:

| Tipo | Como detectar |
|---|---|
| `client` | Contem `package.json` com dependencia `vue`, `react`, `angular`, `svelte`, `next`, `nuxt` OU contem diretorios `src/views/`, `src/components/`, `src/pages/` |
| `server` | Contem `composer.json` (PHP), `requirements.txt`/`pyproject.toml` (Python), `go.mod` (Go), `pom.xml`/`build.gradle` (Java), `Gemfile` (Ruby), `*.csproj` (C#) OU contem diretorios `Controllers/`, `middleware/`, `routes/`, `app/Http/` |
| `service` | Contem indicadores de ambos ou nao se encaixa claramente |

**1c. Detectar modo PR:**

Apos detectar o repo, verificar se o usuario esta em uma branch diferente da branch base do projeto:

```bash
git rev-parse --abbrev-ref HEAD
```

Se a branch atual NAO e `main`/`master`/`develop`/`trunk`, tentar identificar a branch base:

```bash
# Tentar em ordem: origin/main, origin/master, origin/develop, origin/trunk
git merge-base HEAD origin/main 2>/dev/null || \
git merge-base HEAD origin/master 2>/dev/null || \
git merge-base HEAD origin/develop 2>/dev/null || \
git merge-base HEAD origin/trunk 2>/dev/null
```

Se encontrar a base:
- Perguntar via `AskUserQuestion` (opcoes: **modo PR** / **modo local**): "Detectei que voce esta na branch `feature/xxx` com base em `origin/main`. Executar em **modo PR** (analisar todos os commits da branch) ou **modo local** (apenas working tree)?"
- Default sugerido: modo PR se houver 2+ commits diferentes da base; modo local caso contrario

Se o usuario escolher modo PR:
- Coletar arquivos via `git diff --name-status <base>...HEAD` em vez de `git diff HEAD`
- Tagear cada achado com label de origem (ver 5.0f)

Se modo local ou nao for possivel detectar base, seguir em modo local (working tree).

**1d. Coletar mudancas:**

Dependendo do modo:

**Modo local (working tree):**
```bash
git diff --name-status HEAD
git diff --cached --name-status
git ls-files --others --exclude-standard
```

**Modo PR:**
```bash
git diff --name-status <base>...HEAD
```

Combinar resultados em lista unica com status (Modified, Added, Deleted, Renamed).

Se nenhum arquivo modificado, mostrar `no_changes` e parar.

Filtrar binarios: `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.ico`, `.woff`, `.woff2`, `.ttf`, `.eot`, `.mp4`, `.mp3`, `.zip`, `.tar`, `.gz`, `.pdf`, `.lock`.

Se apenas binarios, mostrar `only_binary` e parar.

Se apenas delecoes, entrar em **modo reducido**: pular 2-5 de conteudo, mas executar Impacto (5f) e Orfaos (5i).

### Step 2: Ler arquivos e classificar contexto

Ler o conteudo completo de cada arquivo modificado ou adicionado.

Para arquivos modificados, ler a versao anterior (modo local: `HEAD:`, modo PR: `<base>:`):

```bash
# Modo local
git show HEAD:<filepath>

# Modo PR
git show <base>:<filepath>
```

Armazenar ambas as versoes de cada arquivo modificado.

**2b. Classificar cada arquivo por contexto:**

| Contexto | Como detectar | Efeito |
|---|---|---|
| `test` | Path contem `test/`, `tests/`, `__tests__/`, `spec/`, `__mocks__/`, ou nome contem `.test.`, `.spec.`, `_test.`, `_spec.` | Reduzir severidade de security/validation em 1 nivel. Nao flagear dead-code de debug. |
| `config` | `*.config.*`, `vite.config.*`, `webpack.config.*`, `tailwind.config.*`, `.eslintrc.*`, `tsconfig.json`, `docker-compose.*`, `Dockerfile`, `Makefile` | Nao flagear patterns de seguranca. Nao flagear consistencia de nomenclatura. |
| `migration` | Path contem `migration/`, `migrations/`, `seeds/`, `seeders/`, nome `*_create_*`, `*_alter_*`, timestamps como prefixo | Nao flagear dead-code. Reduzir severidade de performance. |
| `script` | Path contem `scripts/`, `bin/`, `cli/`, ou shebang `#!/` na primeira linha | Reduzir severidade de validation em 1 nivel. |
| `production` | Todo o resto | Severidades normais. |

### Step 3: Mapear dependencias

**3a. Encontrar dependentes (quem importa cada arquivo modificado):**

Adaptar o pattern conforme a linguagem detectada:

- **JS/TS/Vue/React**: `import .* from ['"].*<filename>`, `require(['"].*<filename>`
- **PHP**: `use .*<namespace>`, `include.*<filename>`, `require.*<filename>`
- **Python**: `from <module> import`, `import <module>`
- **Go**: `import ".*<package>"`
- **Rust**: `use <crate>::`, `mod <module>`
- **Java/Kotlin**: `import .*<package>`
- **Ruby**: `require ['"].*<filename>`, `require_relative`
- **C/C++**: `#include.*<filename>`
- **C#**: `using .*<namespace>`
- **Fallback**: buscar o nome do arquivo (sem extensao) no projeto

Limitar a 1 nivel de dependentes.

**3b. Detectar linguagem/framework do projeto:**

Verificar arquivos marcadores na raiz:
- `package.json` -> Node/JS. Verificar `vue`, `react`, `angular`, `svelte` nas dependencias.
- `composer.json` -> PHP
- `requirements.txt`, `pyproject.toml`, `setup.py` -> Python
- `go.mod` -> Go
- `Cargo.toml` -> Rust
- `pom.xml`, `build.gradle` -> Java/Kotlin
- `Gemfile` -> Ruby
- `*.csproj`, `*.sln` -> C#/.NET

### Step 4: Ler dependentes

Ler conteudo completo dos dependentes diretos. Se > 20, priorizar:
1. Arquivos que importam o maior numero de modificados
2. Arquivos de teste (menor prioridade de leitura)
3. Arquivos de config que referenciam modulos modificados

### Step 4b: Filtro de foco (pergunte via AskUserQuestion)

Antes de analisar, **pergunte via `AskUserQuestion`** (uma chamada, duas perguntas) pra nao
cansar em diff grande:

1. **Severidade minima** — **Tudo** / **MEDIUM+** / **HIGH+** / **So CRITICAL**.
2. **Foco de categorias** — **Tudo** / **So seguranca** / **Seguranca + bugs** / **Outro**
   (use "Other" pra combinar, ex.: "seguranca e performance").

Default sugerido: **HIGH+** e **Tudo** quando o diff e grande (muitos arquivos); **Tudo/Tudo**
em diff pequeno. Rode/apresente so o que casa com o filtro e registre no dashboard o que foi
ocultado (ex.: "12 achados LOW/MEDIUM ocultos pelo filtro"). O usuario pode pedir "mostra o
resto" depois.

### Step 4c: Rodar ferramentas nativas (lint / typecheck) — alta confianca

Antes da analise heuristica, **rode as ferramentas que o projeto ja tem** nos arquivos do diff
e use a saida como achados de **alta confianca** (ferramenta entende AST; erra muito menos que regex).

- Detecte e rode o que existir, escopado aos arquivos alterados:
  - JS/TS: `eslint <arquivos>`, `tsc --noEmit`
  - PHP: `phpstan analyse <arquivos>`, `psalm`, `php -l` (lint sintatico)
  - Python: `ruff check <arquivos>`, `mypy <arquivos>`, `flake8`
  - Go: `go vet ./...`, `golangci-lint run`
  - Ruby: `rubocop <arquivos>`
  - C#: analyzers via `dotnet build`
- **Nao instale dependencias.** Se a ferramenta nao estiver instalada, pule (a heuristica do Step 5
  cobre como fallback). Se rodar parecer pesado/lento, **pergunte via `AskUserQuestion`** antes
  ("Rodar `<tool>` nos arquivos alterados?").
- Cada item da ferramenta vira um achado com **confianca alta**, com a regra/codigo da ferramenta
  (ex.: `eslint(no-unused-vars)`, `phpstan`) e severidade mapeada (error -> HIGH, warning -> MEDIUM).
- Ferramenta nativa **e** heuristica apontando o mesmo -> alta confianca; so heuristica -> media.

### Step 5: Analise por categorias

Aplicar cada categoria. Para cada achado, atribuir severidade conforme checklist.md.

**Aplique TODAS as categorias a cada local — nao pare no primeiro achado.** Uma mesma linha
pode ter mais de um problema (ex.: SQL injection **e** autorizacao ausente **e** validacao
faltando). Avalie a linha por todas as categorias relevantes antes de seguir.

**IMPORTANTE:** Aplicar as Regras de Supressao (5.0) ANTES de registrar qualquer achado.

**5.0. Regras de Supressao de Falsos Positivos**

**5.0a. Analise de fluxo de dados (Data Origin Tracing)**

Para achados de seguranca (5a) e validacao (5c), antes de flagear, rastrear a ORIGEM do dado suspeito verificando ate 3 niveis acima:

| Origem | Classificacao | Acao |
|---|---|---|
| Literal hardcoded | Seguro | SUPRIMIR |
| Constante (`const`, `final`, `readonly`, `#define`, enum) | Seguro | SUPRIMIR |
| Arquivo de config local (env, config) | Confiavel | Rebaixar para LOW |
| Retorno de funcao interna sem input externo | Confiavel | Rebaixar 1 nivel |
| Parametro de funcao (pode vir de qualquer lugar) | Indeterminado | Manter + nota "verificar chamador" |
| Input de usuario direto | Perigoso | Manter severidade |
| Banco / API externa | Potencialmente perigoso | Manter + nota "dado externo" |

Lista de sources externos por linguagem:

| Linguagem | Sources externos |
|---|---|
| PHP | `$_GET`, `$_POST`, `$_REQUEST`, `$request->input`, `$request->post`, `$request->query`, `$Request->post`, `$Request->queryString` |
| JS/TS/Node | `req.body`, `req.query`, `req.params`, `request.body`, `formData`, `event.target.value`, `useSearchParams`, `$route.params`, `$route.query` |
| Python | `request.args`, `request.form`, `request.GET`, `request.POST`, `request.data`, `input()`, `args` (argparse), `flask.request`, `django.request` |
| Go | `c.Query()`, `c.PostForm()`, `c.Param()`, `r.FormValue()`, `r.URL.Query()` |
| Ruby | `params[]`, `params.require`, `params.permit` |
| C# | `Request.Query`, `Request.Form`, `Request.Body`, `[FromBody]`, `[FromQuery]` |
| Java | `@RequestParam`, `@RequestBody`, `request.getParameter` |

**5.0b. Supressao por comentario explicito**

Se a linha suspeita ou a imediatamente acima contem comentario de supressao:
- `// @review-ignore`, `# review-ignore`, `/* @review-ignore */`
- `// eslint-disable-next-line`, `// noinspection`, `# noqa`, `// NOLINT`
- `// SAFETY:`, `// SECURITY:` (justificativa explicita)
- `@SuppressWarnings` (Java/Kotlin)

**5.0c. Supressao por contexto do arquivo**

Aplicar ajustes de severidade conforme Step 2b.

**5.0d. Supressao por pattern seguro conhecido**

| Pattern | Contexto seguro | Razao |
|---|---|---|
| `eval()` | Em configs de build (jest, vite, webpack) | Uso legitimo |
| `innerHTML` / `v-html` | Atribuicao de string literal sem interpolacao | Estatico nao e XSS |
| `dangerouslySetInnerHTML` | Valor vem de sanitizer (`DOMPurify.sanitize`, `xss()`) | Ja sanitizado |
| `exec()`/`spawn()` | Argumentos sao todos literais | Sem injecao |
| `http://` | `localhost`, `127.0.0.1`, `0.0.0.0`, comentarios/docs | Ambiente local |
| `http://` | Arquivos de teste | Testes locais |
| `console.log` / `print` | Arquivos com contexto `script` ou `config` | CLI precisa output |
| `TODO`/`FIXME` | Arquivos de teste | Aceitavel em testes |
| `new Function()` | Bibliotecas de template engine | Metaprogramacao legitima |
| SQL concatenado | Query builders (Knex, Eloquent, TypeORM raw) com bindings | Parametrizacao gerenciada |

**5.0e. Supressao de duplicatas**

Mesmo pattern multiplas vezes no mesmo arquivo com mesma causa raiz -> UM UNICO achado com nota "Encontrado em N ocorrencias (linhas X, Y, Z)".

**5.0f. Tagging de origem no modo PR**

Se modo PR ativo, determinar para cada achado se o bug foi introduzido ou pre-existe:

1. Localizar a linha do achado no diff `<base>...HEAD`:
   - Se a linha esta em um bloco `+` do diff -> **"introduzido nesta PR"**
   - Se a linha esta em um bloco de contexto (nao modificada) -> **"pre-existente"**
   - Se ha mesmo pattern em outros arquivos NAO modificados na PR -> **"pre-existente, ampliado nesta PR"**

2. Adicionar esse label ao achado para apresentacao.

Os **patterns de deteccao detalhados** de cada categoria estao em `references/patterns.md` — **leia esse arquivo** e aplique categoria por categoria, SEMPRE com as Regras de Supressao (5.0 acima) e a Verificacao (Step 5.5) antes de registrar cada achado.

Categorias do catalogo: **5a Seguranca** (injection/XSS, RBAC/autorizacao ausente, info-disclosure em erros), **5b Bugs** (typo cross-file, type coercion em boundaries, disciplina de catch, outros), **5c Validacao**, **5d Codigo Morto**, **5e Performance**, **5f Impacto**, **5g Contrato**, **5h Fluxo**, **5i Orfaos**, **5j Consistencia**, **5k Cross-Repo** (so multi-repo), **5l Refatoracao**, **5m Regras do Projeto** (Step 0).

### Step 5.5: Verificacao de cada achado (anti-falso-positivo) — OBRIGATORIO

Nenhum achado vai pra apresentacao sem passar por aqui. Para CADA achado candidato, **tente
refuta-lo** antes de aceitar:

1. **Releia o trecho exato + contexto suficiente** — nao decida por uma linha isolada.
2. **Confirme a afirmacao especifica, de verdade:**
   - "Metodo/simbolo nao existe" -> faca `grep` no projeto inteiro antes de afirmar.
   - "Dado externo" -> re-rastreie a origem (5.0a); se for literal/constante, derrube.
   - "Sem autorizacao" -> procure auth na cadeia inteira (middleware, decorator, classe base,
     rota), nao so no corpo do handler.
   - "Cast sem validacao" -> confirme que nao ha validador/guard antes.
3. **Atribua nivel de confianca:**
   - 🔴 **alta** — ferramenta nativa apontou, ou prova clara (call path/grep confirmam).
   - 🟡 **media** — heuristica forte, mas depende de contexto nao 100% verificavel.
   - ⚪ **baixa** — heuristica fraca / pode ser falso positivo.
4. **Eliminacao:** confianca **baixa** nunca vira CRITICAL/HIGH — rebaixe para nota "verificar"
   ou descarte. Se nao conseguir sustentar o achado com evidencia, **descarte**.

Inclua o nivel de confianca no cabecalho do achado (Etapa 1 do Step 7) e conte no dashboard
quantos achados foram descartados nesta verificacao (transparencia).

### Step 6: Compilar, agrupar e ordenar

Coletar achados. Agrupar por arquivo (5a-5m). Cross-repo (5k) em secao separada por endpoint.

Dentro de cada arquivo, ordenar por severidade (CRITICAL > HIGH > MEDIUM > LOW) e depois por numero de linha.

Numerar sequencialmente comecando em 1 (numeracao global).

Se zero achados: mostrar `all_clear` e parar.

**6a. Metricas de saude por arquivo:**

| Condicao | Indicador |
|---|---|
| 1+ CRITICAL | `[!!!]` |
| 1+ HIGH (sem CRITICAL) | `[!!]` |
| Apenas MEDIUM/LOW | `[!]` |
| Sem achados | `[ok]` |

**6b. Ordenacao de apresentacao:**

1. Arquivos com CRITICAL primeiro
2. Depois HIGH
3. Depois MEDIUM
4. Depois LOW
5. Mesma prioridade: ordenar por total de achados (decrescente)

### Step 7: Apresentar a review

**7a. Dashboard**

Incluir:
- Modo (single/multi + modo PR se ativo)
- Total de arquivos e dependentes
- Achados por severidade
- Suprimidos (transparencia)

**7b. Mapa de Arquivos**

Todos os arquivos com achados, agrupados por indicador de saude.

**7c. Checklist Interativa (apresentacao em duas etapas)**

PROBLEMA: O campo `question` do `AskUserQuestion` renderiza como texto cru — blocos de codigo, tabelas, headings, syntax highlighting nao funcionam. Por isso, apresentar o achado em DUAS etapas:

**Etapa 1 — Mensagem normal (renderiza markdown corretamente):**

Enviar uma mensagem assistant normal (fora do AskUserQuestion) com TODO o detalhe do achado em markdown. Aqui blocos de codigo ficam com syntax highlighting, tabelas renderizam como tabelas, headings funcionam. Conteudo:

- Se primeiro achado de um novo arquivo: cabecalho do arquivo
- Badge de severidade + numero + titulo curto
- Caminho:linha + categoria + label de origem (modo PR)
- Bloco **Antes** com fenced code block
- Bloco **Depois** com fenced code block
- Explicacao (1-2 frases diretas)
- **Reasoning enriquecido** quando aplicavel:
  - Truth table (bugs de coercao/edge case)
  - Step-by-step proof (bugs funcionais com call path)
  - Impacto quantificado (patterns cross-file)
- Regra aplicada (achados de project-rules)
- Nota de ajuste de severidade
- Linha de progresso: `[{atual}/{total}]`

**Etapa 2 — AskUserQuestion curto (so a decisao):**

Imediatamente apos a mensagem acima, chamar `AskUserQuestion` com:
- `question` curto e em texto puro: `"Correcao #{N} — aplicar?"` ou `"#{N} [{severidade}] {titulo_curto} — aplicar?"`
- `options` com apenas os labels curtos:
  - `"Aplicar"` / `"Pular"` / `"Aplicar todos deste arquivo"` / `"Aplicar todos"` / `"Parar"`
- NADA de markdown no campo question (sem backticks, sem headings, sem tabelas) — usar apenas texto plano

**Fluxo por achado:**

```
[mensagem assistant com markdown completo]
    ↓
[AskUserQuestion: "Correcao #3 — aplicar?" + 5 opcoes]
    ↓
[resposta do usuario]
    ↓
[aplicar/pular conforme resposta]
    ↓
[proximo achado]
```

**Regras de apresentacao:**
- OBRIGATORIO dividir em mensagem markdown + AskUserQuestion curto
- NUNCA colocar blocos de codigo, tabelas ou headings dentro do `question` do AskUserQuestion
- O `question` deve ser uma frase curta de uma linha em texto puro
- Mostrar APENAS UM achado por vez
- Aguardar resposta antes do proximo
- Apos terminar arquivo, mini-resumo (tambem como mensagem normal, nao AskUserQuestion)
- Se "Aplicar todos", aplicar tudo sem prompts e ir para Step 9

### Step 8: Aplicar fixes

Edit para aplicar, passar adiante, pular, aplicar por arquivo, aplicar todos, parar.

### Step 9: Resumo

Mostrar resumo final:
- Tabela por severidade (encontrados/aplicados/ignorados)
- Breakdown por arquivo
- **Breakdown por categoria:** quantos de cada categoria (security, bugs, validation, etc.)
- **Breakdown por origem no modo PR:** introduzidos vs pre-existentes
- Total de suprimidos
- Lista de arquivos modificados pela review

**9a. Relatorio opcional (via `AskUserQuestion`):** ofereca salvar o resultado num
`code-review-<data>.md` (**raiz do projeto** / **/tmp** / **nao salvar**). O relatorio traz:
cabecalho (data, modo, filtro, totais), breakdown por severidade/categoria/origem, lista de
achados (`arquivo:linha`, severidade, categoria, titulo, antes/depois resumido, status
aplicado/pulado, regra aplicada) e arquivos tocados. **Nao commitar.**

**9b. Commit pos-fix (se for git, via `AskUserQuestion`):** se houve fixes aplicados, ofereca
commitar — use a skill **`sw-git-commit`** se disponivel (separa em Conventional Commits bem
escopados); senao, faca um Conventional Commit simples. Nunca commite sem o "sim".

## Edge Cases

- **Sem repo git**: verificar sub-diretorios antes de desistir
- **Multi-repo sem mudancas em um**: pular repos sem diff
- **Multi-repo com apenas 1 tipo**: pular cross-repo
- **Sem mudancas**: `no_changes` e parar
- **Apenas binarios**: `only_binary` e parar
- **Arquivos > 1000 linhas**: analisar com aviso `large_file`
- **Marcadores de merge conflict**: flagear como CRITICAL de bugs
- **Submodules**: detectar via `.gitmodules`, pular e reportar
- **>20 dependentes**: priorizar conforme Step 4
- **Imports circulares**: rastrear visitados
- **Arquivos untracked**: incluir, pular versao "antes"
- **Modo PR sem base detectavel**: cair para modo local e avisar
- **Rules do projeto vazias ou mal formatadas**: pular silenciosamente

## Limites

Para varredura completa de **codigo morto** no projeto inteiro (nao so no diff), use a
`sw-dead-code-scan`. Para gerar a mensagem do PR a partir dos commits, a `sw-git-pr-generator`.

Esta skill revisa codigo no working tree (ou range PR). NAO:
- Executa testes automatizados
- Faz push para remote
- Cria PRs ou issues
- Instala dependencias
- Modifica historico git
