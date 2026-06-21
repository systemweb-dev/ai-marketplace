# Code Review — Templates de Apresentacao

## Severidades

| Nivel | Badge | Descricao |
|---|---|---|
| CRITICAL | `[CRITICAL]` | Vulnerabilidade de seguranca, crash em producao, perda de dados, referencia quebrada, escalacao de privilegio |
| HIGH | `[HIGH]` | Bug que afeta funcionalidade, contrato quebrado, validacao ausente em dados criticos, info disclosure publico |
| MEDIUM | `[MEDIUM]` | Codigo morto, performance degradada, validacao ausente em dados nao-criticos, info disclosure autenticado |
| LOW | `[LOW]` | Estilo, consistencia, debug statements, TODOs, violacoes de regras do projeto |

## Categorias

| ID | Nome |
|---|---|
| security | Seguranca |
| authorization | Autorizacao/RBAC |
| info-disclosure | Vazamento de Informacao |
| bugs | Bugs |
| typo | Typo Cross-File |
| coercion | Coercao de Tipo |
| catch | Disciplina de Catch |
| impact | Impacto |
| contract | Contrato |
| flow | Fluxo |
| validation | Validacao |
| orphans | Orfaos |
| dead-code | Codigo Morto |
| performance | Performance |
| consistency | Consistencia |
| refactoring | Refatoracao |
| cross-repo | Cross-Repo |
| project-rules | Regras do Projeto |

## Ordem de prioridade das categorias (dentro da mesma severidade)

1. security
2. authorization
3. info-disclosure
4. bugs
5. typo
6. coercion
7. catch
8. impact
9. contract
10. flow
11. validation
12. orphans
13. dead-code
14. performance
15. consistency
16. refactoring
17. project-rules
18. cross-repo

## Template do Dashboard

REGRAS: Markdown puro, compacto, scanavel.

```
# Code Review

**Modo:** {modo} ({tipos_repos})
**Base:** {branch_base} (se modo PR)
**Arquivos:** {total_arquivos} analisados | {total_dependentes} dependentes
**Regras do projeto:** {n_regras} carregadas de {arquivos_rules}
**Achados:** {total_itens} | Suprimidos: {total_suprimidos}

| CRITICAL | HIGH | MEDIUM | LOW |
|:--------:|:----:|:------:|:---:|
| **{critical}** | **{high}** | **{medium}** | **{low}** |

> **Comandos:** `s` aplicar | `n` pular | `arquivo` aplicar no arquivo | `todos` aplicar tudo | `parar` encerrar
```

Se houver falsos positivos suprimidos:

```
> **Suprimidos:**
> - ~~{severidade} {categoria}~~ {descricao_curta} — {razao}
```

## Template do Mapa de Arquivos

Exibir apos dashboard e suprimidos. Agrupar por maior severidade.

```
---

## Mapa

**CRITICAL**
- `{caminho_arquivo}` — **{n_critical}**C **{n_high}**H **{n_medium}**M **{n_low}**L

**HIGH**
- `{caminho_arquivo}` — **{n_high}**H **{n_medium}**M **{n_low}**L

**MEDIUM / LOW**
- `{caminho_arquivo}` — **{n_medium}**M **{n_low}**L
```

## Template de Cabecalho de Arquivo

```
---

### `{caminho_arquivo}` — {n_achados} achados [{severidade_maior}]
```

## Template de Item com Fix (enriquecido — apresentacao em DUAS etapas)

IMPORTANTE: O achado e apresentado em duas etapas separadas para que o markdown renderize corretamente (blocos de codigo com syntax highlighting, tabelas, headings). NUNCA colocar markdown dentro do campo `question` do `AskUserQuestion` — ele renderiza como texto cru.

### Etapa 1 — Mensagem assistant normal (markdown completo)

REGRA CRITICA: Blocos de codigo como fenced code blocks com triple backticks. Nunca box drawing. Usar `<br>` dentro de tabelas markdown se precisar quebrar linha.

```
#### `[{severidade}]` #{numero} {titulo_curto}

`{caminho}:{linha}` | {categoria}{label_origem_pr}

**Antes:**

\`\`\`{linguagem}
{codigo_antes}
\`\`\`

**Depois:**

\`\`\`{linguagem}
{codigo_depois}
\`\`\`

{explicacao — 1-2 frases diretas}

{bloco_truth_table — opcional, apenas para bugs de coercao/edge case}

{bloco_step_by_step — opcional, apenas para bugs funcionais com call path}

{bloco_impacto_quantificado — opcional, apenas quando pattern aparece em multiplos arquivos}

{bloco_regra_aplicada — opcional, apenas para achados de project-rules}

{nota_ajuste_severidade — opcional: `Severidade: {original} -> {final} ({razao})`}

**[{atual}/{total}]**
```

### Etapa 2 — AskUserQuestion (apenas texto puro)

Imediatamente apos a mensagem acima, chamar `AskUserQuestion`:

```
question: "Correcao #{numero} [{severidade}] {titulo_curto} — aplicar?"
options:
  - label: "Aplicar"
  - label: "Pular"
  - label: "Aplicar todos deste arquivo"
  - label: "Aplicar todos"
  - label: "Parar"
```

REGRAS do campo `question`:
- Apenas texto plano, sem backticks, sem headings, sem tabelas, sem blocos de codigo
- Uma unica linha, curta e direta
- Exemplos validos:
  - `"Correcao #3 [HIGH] Query string boolean invertido — aplicar?"`
  - `"#1 — Middleware sem role guard. Aplicar?"`
  - `"Aplicar correcao #5?"`
- Exemplos invalidos:
  - Qualquer texto com marcadores markdown
  - Texto com quebras de linha
  - Tabelas ou blocos de codigo

REGRAS dos `options`:
- Usar os 5 labels padrao em portugues
- Nada de descricoes longas, so o label curto

### Sub-bloco: Label de origem (modo PR)

```
| {categoria} · **introduzido nesta PR**
| {categoria} · **pre-existente, ampliado nesta PR**
| {categoria} · **pre-existente**
```

### Sub-bloco: Truth Table

Usar quando o bug e de coercao/edge case com multiplos inputs possiveis.

```
**Tabela de comportamento:**

| Input | Resultado atual | Esperado |
|:------|:---------------:|:--------:|
| `"false"` | `true` ❌ | `false` |
| `"true"` | `true` ✅ | `true` |
| `"0"` | `false` ✅ | `false` |
| `null` | `false` ✅ | `false` |
```

### Sub-bloco: Step-by-Step Proof

Usar quando o bug tem call path ou sequencia de eventos que precisa ser explicada.

```
**Passo a passo:**

1. Cliente envia `POST /endpoint` com payload `{id: 42, level: "ADMIN"}`
2. Middleware valida apenas formato dos campos (linha X)
3. Middleware NAO verifica role do chamador
4. Controller acessa `request.post('level')` e grava direto (linha Y)
5. Qualquer usuario autenticado escala para ADMIN
```

### Sub-bloco: Impacto Quantificado

Usar quando o pattern aparece em multiplos arquivos.

```
**Encontrado em {n} ocorrencias:**
- `{arquivo_1}:{linha}`
- `{arquivo_2}:{linha}`
- `{arquivo_3}:{linha}`
```

### Sub-bloco: Regra Aplicada

Usar em achados de `project-rules`.

```
**Regra aplicada:** `.claude/rules/{arquivo}.md` — "{citacao_da_regra}"
```

## Template de Item Informativo (sem fix aplicavel)

Usar APENAS quando nao existe correcao possivel.

```
#### `[{severidade}]` #{numero} {titulo_curto}

`{caminho}:{linha}` | {categoria}

\`\`\`{linguagem}
{codigo}
\`\`\`

{explicacao}

**[{atual}/{total}]** Proximo? (s/parar)
```

## Template de Mini-Resumo de Arquivo

```
> `{caminho_arquivo}` — **{aplicados}** aplicados, **{ignorados}** ignorados
```

## Template de Resumo Final (enriquecido)

```
---

# Resumo

**{total_aplicados}** de **{total}** achados aplicados

## Por severidade

| Severidade | Aplicados | Total |
|:-----------|:---------:|:-----:|
| CRITICAL   | {ca}      | {c}   |
| HIGH       | {ha}      | {h}   |
| MEDIUM     | {ma}      | {m}   |
| LOW        | {la}      | {l}   |

## Por categoria

| Categoria | Achados |
|:----------|:-------:|
| security | {n} |
| authorization | {n} |
| info-disclosure | {n} |
| bugs | {n} |
| typo | {n} |
| coercion | {n} |
| catch | {n} |
| validation | {n} |
| ... | ... |

## Por origem (modo PR)

| Origem | Achados |
|:-------|:-------:|
| Introduzidos nesta PR | {n} |
| Pre-existentes ampliados | {n} |
| Pre-existentes | {n} |

## Por arquivo

- `{caminho}` — **{n_aplicados}** aplicados, **{n_ignorados}** ignorados

> {total_suprimidos} falsos positivos suprimidos

## Arquivos modificados pela review
- `{arquivo_1}`
- `{arquivo_2}`
```

## Mensagens de Sistema

| Chave | Texto |
|---|---|
| no_git | Sem repositorio git neste diretorio. |
| no_changes | Nenhuma mudanca detectada. Nada para revisar. |
| only_binary | Apenas arquivos binarios modificados. Nada para revisar. |
| binary_skipped | {n} binario(s) ignorado(s) |
| all_clear | **Zero achados.** Tudo limpo. |
| fix_applied | Correcao #{n} aplicada. |
| fix_skipped | #{n} ignorado. |
| review_stopped | Revisao interrompida. **{remaining}** itens restantes. |
| large_file | `{arquivo}` tem **{linhas}** linhas — revisao pode ser parcial |
| submodule_skipped | Submodule `{path}` ignorado |
| pr_mode_detected | Branch `{branch}` detectada. Base: `{base}`. Executar em modo PR? |
| pr_mode_base_not_found | Nao foi possivel detectar branch base. Executando em modo local. |
| rules_loaded | **{n}** regras do projeto carregadas de {arquivos}. |
| rules_none | Nenhuma regra do projeto encontrada. Usando apenas patterns generics. |

## Respostas do Usuario

| Acao | Aceita |
|---|---|
| Aplicar | sim, s, yes, y |
| Ignorar | nao, n, no, pular |
| Aplicar todos deste arquivo | arquivo, file, este |
| Aplicar todos | todos, all, tudo |
| Parar | parar, stop, sair, quit |

## Exemplos de achados (referencia)

### Exemplo 1: Autorizacao ausente (CRITICAL)

```
#### `[CRITICAL]` #1 Escalacao de privilegio — middleware sem role guard

`middleware/AdminUpdateMiddleware.php:19` | authorization · introduzido nesta PR

**Antes:**

\`\`\`php
public function __invoke(Request $Request, Response $Response, $Next)
{
    $this->validateFields($Request);
    return $Next();
}
\`\`\`

**Depois:**

\`\`\`php
public function __invoke(Request $Request, Response $Response, $Next)
{
    if (!Auth::isAdministrator()) {
        ResponseApi::error('unauthorized', 'Administrator level required', 403);
    }
    $this->validateFields($Request);
    return $Next();
}
\`\`\`

Middleware valida apenas formato dos campos, sem verificar o role do chamador. Qualquer usuario autenticado (mesmo PRODUCTION) pode alterar o level de outros admins.

**Passo a passo:**

1. Atacante com JWT de nivel PRODUCTION chama `POST /v1/admin/update`
2. Envia payload `{id: <victim-id>, level: "ADMINISTRATOR"}`
3. Middleware valida que `id` e numerico, admin existe, level e enum valido — tudo passa
4. Controller grava `$admin->level = "ADMINISTRATOR"` e salva
5. Escalacao completa em uma requisicao

**[1/5]** Aplicar? (s/n/arquivo/todos/parar)
```

### Exemplo 2: Coercao de boolean em query string (HIGH)

```
#### `[HIGH]` #3 Query string boolean invertido

`app/Admin/Controllers/NotificationController.php:26` | coercion · introduzido nesta PR

**Antes:**

\`\`\`php
$unreadOnly = (bool)($this->request->queryString('unread_only') ?? false);
\`\`\`

**Depois:**

\`\`\`php
$unreadOnly = filter_var(
    $this->request->queryString('unread_only'),
    FILTER_VALIDATE_BOOLEAN
);
\`\`\`

O cast `(bool)` em string nao-vazia sempre retorna `true` em PHP, exceto para `"0"`. O cliente enviando `?unread_only=false` recebe o comportamento oposto do esperado.

**Tabela de comportamento:**

| Input | `(bool)` atual | `FILTER_VALIDATE_BOOLEAN` esperado |
|:------|:--------------:|:----------------------------------:|
| `"false"` | `true` ❌ | `false` |
| `"true"` | `true` ✅ | `true` |
| `"0"` | `false` ✅ | `false` |
| `"1"` | `true` ✅ | `true` |
| `null` | `false` ✅ | `false` |

**[3/5]** Aplicar? (s/n/arquivo/todos/parar)
```

### Exemplo 3: Typo cross-file (HIGH)

```
#### `[HIGH]` #2 Typo `roolback` em multiplos arquivos

`app/LogicApp/Services/CampaignService.php:83` | typo · pre-existente, ampliado nesta PR

**Antes:**

\`\`\`php
} catch (\Exception $e) {
    DB::roolback();
    throw $e;
}
\`\`\`

**Depois:**

\`\`\`php
} catch (\Exception $e) {
    DB::rollback();
    throw $e;
}
\`\`\`

Metodo `DB::roolback()` nao existe na classe DB — a chamada lanca `Error: Call to undefined method`. Como `catch (\Exception)` nao pega `\Error` em PHP 8, a transacao nunca e revertida explicitamente e o erro original e mascarado.

**Encontrado em 3 ocorrencias:**
- `app/LogicApp/Services/CampaignService.php:83`
- `app/LogicApp/Services/CreatorService.php:49`
- `app/LogicApp/Services/CreatorUpdateService.php:63` (novo nesta PR)

**[2/5]** Aplicar? (s/n/arquivo/todos/parar)
```
