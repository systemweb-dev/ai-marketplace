---
titulo: sw-pr-message
slug: 2026-09-10-sw-pr-message
criado: 2026-09-10
estado: concluido
---

# sw-pr-message — mensagem de PR organizada por tipo de mudança

## Objetivo & outcome

Depois de implementar algo numa branch (feature, ajuste, hotfix, refactor), gerar um
`PR-MESSAGE.md` pronto para colar no GitHub, com as mudanças agrupadas por tipo.

**Outcome:** o revisor entende o PR lendo o texto, sem abrir o log de commits. Mede-se por:
base certa (as mudanças listadas são só as da branch), zero commit esquecido, e o mesmo
formato em todo PR.

Substitui a skill local `sw-git-pr-generator` (não publicada). Diagnóstico em
[`referencias/diagnostico-skill-antiga.md`](referencias/diagnostico-skill-antiga.md) — o conteúdo
da skill antiga não é necessário para implementar: este spec define a nova por inteiro.

## Decisões do usuário (fechadas)

| Tema | Decisão |
|---|---|
| Nome | `sw-pr-message` (categoria `development`) |
| Saída | Arquivo `PR-MESSAGE.md` na raiz do repositório, protegido por `info/exclude` |
| Fonte | Commits (assunto + corpo) **e** diff |
| Título do PR | Frase descritiva livre — sem `feat(escopo):`, sem `[Feature]` |
| Seções | Semântica do Keep a Changelog com os termos do usuário, **sem emoji**, vazias omitidas |
| Extras | "Como testar"; bloco de hotfix (causa, impacto, rollback) |
| Perguntas ao gerar | **Só o idioma** (PT/EN), pulada se o pedido já disser |
| Branch contida num candidato | Para e mostra as contagens de todos os candidatos |
| Hotfix sem evidência | Comentário HTML invisível `<!-- preencher: … -->` |

## Arquitetura

Script coleta e formata o que tem resposta certa; o agente interpreta o que exige leitura.

```
/sw-pr-message
  0. agente   idioma; base via pedido ou `gh pr view` → --base
  1. collect.py  → <git-path>/sw-pr-message/fatos.json
  2. agente      → <git-path>/sw-pr-message/mudancas.json
  3. render.py   → <toplevel>/PR-MESSAGE.md  (+ linha em <git-path>/info/exclude)
```

`<git-path>` = `git rev-parse --git-path <x>` e `<toplevel>` = `git rev-parse --show-toplevel`.
Nunca caminhos fixos em `.git/`: em worktree e submódulo, `.git` é um arquivo. Em worktree,
`--git-path info/exclude` aponta o diretório comum — que é o que o git lê; montar à mão erraria.

### Unidades

| Unidade | Responsabilidade | Não faz |
|---|---|---|
| `scripts/lib/gitcmd.py` | Único ponto que executa `git`: args em array, sem shell, lista fechada de subcomandos e argumentos proibidos | Interpretar saída |
| `scripts/lib/base.py` | Detectar a base (algoritmo abaixo) | Ler diff |
| `scripts/lib/coleta.py` | Commits sem merge, diff por arquivo, ruído, corte, sinais de hotfix | Decidir texto |
| `scripts/collect.py` | Pré-checagens, orquestra `base` + `coleta`, grava `fatos.json` | Rede, escrita fora do `git-path` |
| `scripts/render.py` | Valida `mudancas.json` contra `fatos.json`, monta e grava o `.md`, cuida do exclude | Decidir classificação |
| `SKILL.md` | Conduz o agente: idioma, base, ler fatos, escrever mudanças, corrigir recusa | — |

## Detecção da base

Evidência medida em [`referencias/deteccao-de-base.md`](referencias/deteccao-de-base.md).

**Pré-checagens (param com mensagem clara):** fora de repositório (inclusive bare:
`--is-inside-work-tree` precisa responder `true`, não só sair com código 0); clone raso
(`rev-parse --is-shallow-repository` = `true`); HEAD destacado (`symbolic-ref -q HEAD` falha);
rebase em andamento (`git-path rebase-merge` ou `rebase-apply` existe); clone parcial (`*.promisor` em
`--git-path objects/pack`: o diff buscaria arquivos do remoto, e a skill não usa rede); e, **só quando não há
`--base`**, branch atual ser um dos nomes candidatos (`develop`, `main`, `master`, `trunk`,
`staging` ou a branch padrão). Esta última é explícita porque o passo 2 exclui a própria branch
dos candidatos: estando em `develop`, a contagem contra `master` seria > 0 e a heurística
descreveria o `develop` inteiro. Com `--base` explícito ela não se aplica — `develop` com
`--base master` é um PR de release legítimo.

**Algoritmo:**

1. **`--base <nome>` informado** — o agente passa quando o usuário pediu, ou quando
   `gh pr view --json baseRefName,state` retorna um PR `OPEN` para a branch. Existindo `<nome>` e
   `origin/<nome>`, vale a de **menor contagem**, como no passo 3 — com PR aberto e `develop` local
   atrasado, o local descreveria commits que já estão no remoto. Contagem 0 ou ref inexistente → erro.
2. **Candidatos:** `develop`, `main`, `master`, `trunk`, `staging` e o nome da branch padrão
   (de `origin/HEAD`, se existir).
3. **Contagem por candidato:** `rev-list --count --no-merges <ref>..HEAD --`, avaliando
   `refs/heads/<nome>` e `refs/remotes/origin/<nome>` quando existirem; fica a **menor** por nome e
   registra qual ref venceu. Refs completas porque o git resolve tag antes de branch; `--` no fim
   porque arquivo ou pasta de mesmo nome tornaria o argumento ambíguo e a branch sumiria.
4. **Algum candidato com 0** → para. Mensagem lista todos com a contagem e sugere o menor > 0:
   `staging já contém a branch · develop: 9 · master: 205 → rode com --base develop`.
5. **Escolha:** menor contagem. **Empate** → branch padrão se estiver entre os empatados; senão
   o primeiro de `main`, `master` entre os empatados; senão para mostrando as contagens. O empate fica
   registrado em `base.empate` e aparece no relatório — o conteúdo é o mesmo para os empatados.
6. **Nenhum candidato existe** → para pedindo `--base`.

## Coleta (`fatos.json`)

- **Commits:** `log -z --no-merges <base>..HEAD`, com NUL entre os campos — único byte que uma
  mensagem de commit não aceita; qualquer outro separador deixaria a mensagem forjar commits —, com hash completo, tipo e escopo (do prefixo
  Conventional, se houver), assunto e corpo. Merges ficam de fora e só contam em
  `merges_ignorados`.
- **Diff:** sempre `diff <base>...HEAD` (a partir do merge-base), com `--no-ext-diff` e
  `--no-textconv` forçados — o repositório analisado pode ter conversores configurados que
  executariam programas.
- **Ruído** (fica nas estatísticas, fora do conteúdo): lockfiles (`package-lock.json`,
  `yarn.lock`, `pnpm-lock.yaml`, `composer.lock`, `Gemfile.lock`, `poetry.lock`, `Cargo.lock`,
  `go.sum`, `*.lock`); diretórios `dist/`, `build/`, `vendor/`, `node_modules/`, `.next/`,
  `coverage/`; `*.min.js`, `*.min.css`, `*.map`, `*.snap`; binários (numstat `-`).
- **Corte** — calibrado em [`referencias/calibracao-do-diff.md`](referencias/calibracao-do-diff.md):
  lista de arquivos (numstat) **sempre completa**; conteúdo com teto de **400 linhas por arquivo**
  e **60 KB no total**. Arquivos em ordem crescente de linhas alteradas (`mais + menos`): os pequenos
  entram inteiros, os grandes recebem o que sobra e ficam com `cortado: true`. As 400 linhas são
  **do patch** daquele arquivo. Arquivo sem orçamento restante: `diff: ""` e `cortado: true`. No JSON,
  `arquivos` sai em ordem de caminho — a ordem por tamanho só distribui o orçamento. Caminhos via
  `--numstat -z` (imune a `core.quotepath`); renomeação é classificada pelo caminho novo, e o diff
  dela usa **os dois caminhos** — pedido só pelo novo, o git mostra o arquivo inteiro como adicionado. O caminho vai ao git como
  `:(literal)<caminho>` (sem isso `[id].tsx` casaria com `i.tsx`), e o corte conta só `\n` como quebra de linha.
- **Sinais de hotfix:** branch com prefixo `hotfix/`; commit com tipo `hotfix`; ou todos os
  commits do tipo `fix` com **base escolhida** `main`/`master`, **desde que o repositório tenha
  `develop`** (sem `develop`, toda branch de correção sai de `master` e o sinal não distingue nada). Também não
  dispara quando `develop` empata com a base: no git-flow, branch criada antes do último release conta
  igual contra os dois, e a base `master` é só o desempate.
- **Avisos:** `ls-files --error-unmatch PR-MESSAGE.md` bem-sucedido (arquivo versionado — o exclude
  não protege). **Os scripts não leem o working tree:** para comparar conteúdo, `git status` executaria
  os filtros de limpeza configurados, então mudança não commitada não é detectada — o relatório final
  sempre lembra que só entra o que está commitado.

```json
{ "branch": "feature/x",
  "base": {"nome": "develop", "ref": "refs/remotes/origin/develop", "como": "heuristica", "a_frente": 9,
           "candidatas": {"develop": 9, "master": 205}, "empate": []},
  "hotfix": {"provavel": false, "sinais": []},
  "stats": {"arquivos": 19, "insercoes": 739, "delecoes": 24, "ruido": ["composer.lock"],
            "merges_ignorados": 1},
  "commits": [{"hash": "<40 hex>", "tipo": "feat", "escopo": "x", "assunto": "…", "corpo": "…"}],
  "arquivos": [{"caminho": "src/a.py", "mais": 134, "menos": 0, "ruido": false,
                "cortado": false, "diff": "…"}],
  "avisos": ["pr_message_versionado"] }
```

## O que o agente escreve (`mudancas.json`)

```json
{ "idioma": "pt",
  "titulo": "Assistente de IA no painel",
  "resumo": "…",
  "secoes": { "novas": [{"texto": "…", "commits": ["a1b2c3d"]}],
              "ajustes": [], "correcoes": [], "removido": [], "seguranca": [], "interno": [] },
  "como_testar": ["…"],
  "hotfix": {"causa": "…", "impacto": null, "rollback": null},
  "sem_item": [{"hash": "e4f5a6b", "motivo": "desfeito pelo commit seguinte"}] }
```

Regras para o agente (no `SKILL.md`):

- **Um item = uma mudança.** Vários commits do mesmo ajuste viram um item com todos os hashes.
- **Classifica pelo significado, não pelo prefixo.** `feat` que só altera comportamento
  existente → `ajustes`; `chore(deps)` que fecha vulnerabilidade → `seguranca`; `refactor`,
  `test`, `ci`, `build`, `docs` → `interno`.
- **Commit vago é explicado pelo diff.** Arquivo `cortado: true` não é descrito além do que
  foi visto.
- **`sem_item`** só para commit sem efeito líquido (desfeito, vazio, wip revertido). Não é
  lixeira para commit difícil de descrever.
- **`como_testar`** só com passo observável; vazio quando a mudança não tem nada a observar.
- **`hotfix`** é objeto **obrigatório** se `fatos.hotfix.provavel`, e **ausente** caso contrário. Cada
  campo só com evidência em commit ou diff;
  sem evidência, `null`. Nunca inventar impacto ou rollback.

## Render (`PR-MESSAGE.md`)

**Validação — recusa gravar (exit 3) e lista todos os problemas de uma vez:**
- JSON malformado; chave de seção desconhecida;
- tipo errado: seção que não é lista, item ou `sem_item` que não é objeto, `commits` ou `como_testar`
  que não são listas de texto, `hotfix` que não é objeto, `titulo`/`resumo`/campo de hotfix que não é
  texto — sempre problema listado, nunca exceção;
- `idioma` fora de `pt`/`en`; `titulo` ou `resumo` vazios; título vazio depois de remover o prefixo;
- item com `commits: []` — item sem lastro em commit é item inventado; item com `texto` vazio;
  `sem_item` com `motivo` vazio;
- hash que não existe em `fatos.commits`, com menos de 7 caracteres ou ambíguo;
- commit de `fatos.commits` que não aparece em nenhum item nem em `sem_item`;
- o mesmo commit num item **e** em `sem_item`;
- hotfix inconsistente: `fatos.hotfix.provavel` verdadeiro e `hotfix` ausente ou `null`, ou falso e
  `hotfix` presente.

Um commit pode aparecer em mais de um item.

**Montagem:**
- Título `# <titulo>` com prefixo removido: `^(feat|fix|chore|refactor|docs|test|ci|build|perf|style|revert|hotfix)(\([^)]*\))?!?:\s*`
  (sem diferenciar maiúsculas) e `^\[[^\]]+\]\s*`. **Só tipos Conventional** — "Checkout: novo fluxo"
  fica intacto. Vazio depois disso → recusa.
- Emoji removido de todo texto do agente: `U+1F000–U+1FAFF`, `U+2600–U+26FF`, os emoji de
  `U+2700–U+27BF` (✅ ✨ ❌ ❗ ➕ ➖ ➗ ✊ ✋), os de apresentação fora desses blocos (`U+231A–U+231B`,
  `U+23E9–U+23F3`, `U+23F8–U+23FA`, `U+2B1B–U+2B1C`, `U+2B50`, `U+2B55` — ⏳ ⭐ …), `U+FE0F`, `U+200D` e
  `U+20E3` (keycap). Setas e marcas tipográficas ficam (`→ ✓ ✔ • – —`). Hashes nunca impressos.
- **Texto do agente vira uma linha só** (qualquer espaço em branco, inclusive quebra de linha, vira um
  espaço): um item com uma quebra seguida de `## X` criaria uma seção que não é do render. **Resumo que
  começa com `#`, `<`, ` ``` ` ou `~~~` recebe `\` na frente** — viraria título, ou comentário/bloco de
  código sem fim que engole o resto do PR.
- Ordem fixa; seção vazia não aparece; títulos das seções pertencem ao render:

| Ordem | `pt` | `en` |
|---|---|---|
| 1 | Resumo | Summary |
| 2 | Hotfix *(se `fatos.hotfix.provavel`)* | Hotfix |
| 3 | Novas funcionalidades | New features |
| 4 | Ajustes | Changes |
| 5 | Correções | Fixes |
| 6 | Removido | Removed |
| 7 | Segurança | Security |
| 8 | Interno | Internal |
| 9 | Como testar *(lista numerada)* | How to test |

- **Bloco de hotfix:** um parágrafo por campo — `**Causa:** …`, `**Impacto:** …`,
  `**Rollback:** …` (`en`: Root cause, Impact, Rollback). Campo `null` vira
  `<!-- preencher: **Impacto:** -->` (`en`: `<!-- fill in: **Impact:** -->`). Os três `null` → o bloco inteiro, com o `## Hotfix`,
  vai dentro de um único comentário. Resultado: nada vazio aparece no GitHub se colado sem
  preencher.

**Antes de gravar — exit 2, sem tocar em nada:** `--repo` inexistente; fora de repositório; `fatos.json`
ausente, ilegível ou de **outra branch** (senão a mensagem de uma branch seria gravada estando em outra);
`PR-MESSAGE.md` que é **link simbólico** (um link versionado apontando para fora faria o render
sobrescrever arquivo fora do repositório). O ambiente é checado antes do conteúdo: com ele errado,
corrigir o `mudancas.json` não adiantaria.

**Gravação:** se `PR-MESSAGE.md` existe e difere (comparado em bytes), copia para
`<git-path>/sw-pr-message/PR-MESSAGE.anterior.md` antes de sobrescrever. Acrescenta
`/PR-MESSAGE.md` em `<git-path>/info/exclude` se a linha não existir. Arquivo versionado →
grava e avisa (exit 0).

## Fluxo do agente (`SKILL.md`)

1. Idioma: do pedido, ou `AskUserQuestion` (Português / English).
2. Base: `--base` do pedido; senão, se `gh auth status` ok, `gh pr view` da branch — PR `OPEN`
   vira `--base`. `gh` só lê.
3. `collect.py [--base X]`. Exit 2 → mostra a mensagem e para — exceto quando a `--base` veio do
   `gh` e não existe localmente: roda de novo sem `--base` e avisa.
4. Lê `fatos.json`, escreve `mudancas.json` pelas regras acima.
5. `render.py`. Exit 3 → corrige os problemas listados e roda de novo. Na 3ª recusa, para e
   mostra os problemas ao usuário.
6. Informa: caminho do arquivo, base e como foi detectada (com as contagens), avisos, cortes, e
   quantos campos de hotfix ficaram para preencher.

## Erros e casos de borda

| Situação | Comportamento |
|---|---|
| Fora de repo git · clone raso · HEAD destacado · rebase em andamento | Para com mensagem |
| Na própria base (branch atual é nome candidato), sem `--base` | Para — pré-checagem explícita |
| Em `develop` com `--base master` (PR de release) | Segue normalmente |
| Nenhum candidato existe | Para pedindo `--base` |
| `--base` inexistente ou com 0 commits | Para |
| Mudanças não commitadas | Não detectadas (scripts não leem o working tree); o relatório sempre lembra |
| `gh` ausente, sem login ou sem PR | Segue sem `--base`, sem erro |
| Base do PR (`gh`) não existe localmente (fork com remoto `upstream`) | Agente roda de novo sem `--base` e avisa |
| `mudancas.json` inválido | Render recusa listando tudo; agente corrige |
| `PR-MESSAGE.md` versionado | Grava e avisa que o exclude não protege |
| `PR-MESSAGE.md` versionado como link simbólico | Para sem escrever (exit 2) |
| `fatos.json` ilegível ou de outra branch | Para pedindo para rodar a coleta de novo (exit 2) |
| Clone parcial | Para com mensagem — a skill não usa rede |
| `--repo` inexistente | Para com mensagem nos dois scripts |
| Branch saída de `release/*` ou empilhada em outra feature | Heurística pode errar; a base impressa no fim permite refazer com `--base` |

## Testes (pytest)

Repositórios git criados dentro de cada teste (`tmp_path`), sem rede.

- **Base:** feature de `develop` com `master` presente → `develop`; candidato com 0 → para e lista
  contagens; empate com e sem `origin/HEAD`; empate sem padrão nem `main`/`master` → para; `develop`
  local atrasado e `origin/develop` à frente → vence o menor, **com e sem `--base`**; `--base` vence a
  heurística; `--base` inexistente → para; `--base` com 0 commits → para; nenhum candidato existe →
  para pedindo `--base`.
- **Pré-checagens:** fora de repo git, git < 2.31, clone raso, HEAD destacado, rebase em andamento, clone parcial e **estar em `develop` com `master` presente, sem `--base`** param — este último é o caso que passaria despercebido. Em `develop` **com** `--base master` segue (PR de release).
- **Coleta:** merge de `develop` dentro da feature não entra nos commits nem no diff; lockfile
  fora do conteúdo e presente em `ruido`; arquivo de 1.000 linhas cortado e marcado; teto total;
  sinal de hotfix por "só fix com base `master`" só dispara com `develop` presente.
- **Worktree:** intermediários e exclude resolvidos via `--git-path`; `git check-ignore PR-MESSAGE.md`
  confirma que o exclude vale.
- **Render:** ordem; seção vazia omitida; PT e EN (inclusive o comentário `fill in`); emoji removido
  com `→ ✓ ✔` preservados; prefixo Conventional removido e "Checkout: novo fluxo" intacto; hotfix com
  campo `null` vira comentário; os três `null` comentam o bloco inteiro; `sem_item` aceito e não
  impresso; hash nunca impresso; arquivo anterior preservado; exclude sem linha duplicada; aviso de
  arquivo versionado.
- **Recusas (exit 3, todas listadas de uma vez):** JSON malformado; chave de seção desconhecida;
  idioma inválido; `titulo`/`resumo` vazios; título vazio após remover prefixo; item com `commits: []`;
  hash desconhecido, curto ou ambíguo; commit esquecido; commit em item e em `sem_item`; hotfix
  inconsistente nos dois sentidos. Um teste com **vários** problemas confere que saem todos juntos.
- **Segurança (FF1):** ver a lista de formas proibidas.
- **Fora do pytest — comportamento do agente:** uso do `gh`, nova tentativa sem `--base` e parada na
  3ª recusa. Uso do `gh` e nova tentativa sem `--base` validados na execução real, com um `gh` falso
  no `PATH` (Migração, passo 2); a parada na 3ª recusa não ocorreu na validação e fica só como regra do
  `SKILL.md`. O plano não deve inventar teste pytest para eles.

## Restrições verificáveis (fitness functions)

1. **Só git de leitura.** Todo `subprocess` passa por `lib/gitcmd.py` (teste pela árvore sintática: nenhum outro
   módulo importa `subprocess`, nem por `__import__`; nenhum `os.system`/`popen`/`exec*`/`spawn*`/`fork*`;
   nenhum `shell=True`).
   - **Subcomandos:** `log`, `diff`, `rev-list`, `rev-parse`, `for-each-ref`, `merge-base`,
     `ls-files`, `version` (sem argumentos: lê a versão sem opção antes do subcomando) e `symbolic-ref`
     **só na forma de leitura** (`-q`/`--short` + exatamente um
     argumento). Recusa `-d`, `-m` e dois argumentos: `git symbolic-ref HEAD refs/heads/x` muda o HEAD.
   - **Nada antes do subcomando** — bloqueia opções globais como `-c` e `--exec-path`.
   - **Recusa por prefixo**, não por palavra exata: qualquer argumento começando com `--output`,
     `--no-index`, `--ext-diff`, `--textconv`, `--show-signature` ou `--submodule` — os três últimos
     religariam, depois, o que as defesas desligam. (`--output=/x` passado como base criou arquivo no teste do revisor.)
   - **Refs vindas de fora** (`--base`, `gh`): recusadas se começarem com `-`, e todo comando que
     recebe revisão leva `--end-of-options` antes dela. Requer git ≥ 2.31 — é quando surge o
     `GIT_CONFIG_COUNT` usado nas defesas abaixo; versão menor para na pré-checagem. Existência de
     ref externa é checada com `rev-list --max-count=0 --end-of-options` (aceito desde a 2.24), não
     com `rev-parse`.
   - **Defesas forçadas** contra configuração do repositório analisado: `--no-ext-diff --no-textconv
     --no-color --submodule=short` em `diff` e `log` (sem o último, o diff filho aberto dentro de um
     submódulo não herdaria as defesas); `--no-show-signature` em `log` (`log.showSignature` executaria
     gpg); ambiente `GIT_OPTIONAL_LOCKS=0` e `core.fsmonitor=false` via
     `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0` — não por `-c`, que a própria regra proíbe. Variáveis herdadas `GIT_DIR`, `GIT_WORK_TREE`,
     `GIT_INDEX_FILE`, `GIT_CONFIG_PARAMETERS` e `GIT_EXTERNAL_DIFF` são descartadas. `GIT_NO_LAZY_FETCH=1`
     impede busca de objetos em clone parcial — segunda barreira depois da pré-checagem (git ≥ 2.44).
   - **Teste:** cada forma proibida — inclusive `--output=/x`, base `--output=/x`, base `-x` e
     `symbolic-ref HEAD refs/heads/x` — lança exceção **antes** de executar qualquer processo.
2. **Sem rede.** O teste chama `main()` de `collect.py` e `render.py` **no mesmo processo** (monkeypatch
   não alcança subprocess) num repo de teste, com `socket.socket` e `socket.create_connection` trocados por uma função que **registra** a tentativa e só
   então lança exceção — um `except` no script não esconde o registro; e nenhum import de rede em `scripts/`,
   verificado pela árvore sintática.
3. **Escrita confinada.** O teste prepara o repositório (branch, commit, `mudancas.json`) **antes** do
   retrato inicial; entre os dois retratos só rodam `collect` e `render`, com o diretório atual dentro do
   repositório. O retrato cobre a árvore inteira, **incluindo `.git`**, com conteúdo, data de modificação
   e pastas — **sem lista de caminhos ignorados**. Só podem mudar `<git-path>/sw-pr-message/*`,
   `<git-path>/info/exclude` e `<toplevel>/PR-MESSAGE.md`.
4. **Render determinístico.** Mesmos `fatos.json` + `mudancas.json` → saída byte a byte igual.

## Não-objetivos

- Criar ou editar PR no GitHub; dar push. O `gh` só é lido pelo agente.
- Diagrama; seções de breaking changes e de issues/links.
- Respeitar template de PR do repositório; configuração por projeto; títulos de seção customizáveis.
- Qualquer pergunta além do idioma.
- Candidatos `release/*` ou detecção de branch empilhada.
- Modo CI (clone raso e HEAD destacado param).

## Restrição de simplicidade

A menor solução: dois scripts com uma biblioteca interna pequena, stdlib apenas, e um
`SKILL.md`. Se a detecção de base pedir regra além das listadas aqui, corta-se escopo — a saída
é `--base`, não uma heurística maior.

## Appetite · MVP vs MLP

**Appetite pequeno** — um ciclo curto. **MVP:** texto certo, com a base certa, no mesmo formato.

## Decisões (ADR)

**1. Script coleta e formata; agente interpreta.**
Contexto: a skill antiga errava base e variava formato — coisas com resposta certa.
Decisão: base, coleta, validação e montagem em script; agrupar e escrever com o agente.
Alternativas: só instruções (erros persistem); script puro (não agrupa por mudança nem lê diff).
Consequência: custo de um script com testes; mesmo padrão já usado na `sw-cluster-audit`.

**2. Base = candidato com menos commits à frente, parando no zero.**
Contexto: ordem fixa descreveria 205 commits em vez de 9 num caso real.
Decisão: menor contagem `--no-merges`; qualquer candidato com 0 → para com as contagens.
Alternativas: ordem fixa; pular o zero (reabre o erro — branch já mergeada geraria 158 itens).
Consequência: um passo extra (`--base`) quando a branch já foi integrada para QA.

**3. Item por mudança, com rastreio de commits.**
Contexto: um bullet por commit gera ruído.
Decisão: cada item lista seus commits; render recusa commit esquecido; `sem_item` para commit
sem efeito líquido.
Alternativas: 1 commit = 1 item; sem conferência (commits somem calados).
Consequência: o agente precisa justificar todo commit.

**4. `gh` fora dos scripts.**
Contexto: scripts sem rede são testáveis e previsíveis.
Decisão: o agente consulta o PR aberto e passa `--base`.
Alternativa: `gh` no `collect.py` (contradiz a fitness function 2).
Consequência: a lógica de "usar o PR aberto" vive no `SKILL.md`.

**5. Arquivo protegido por `info/exclude`.**
Contexto: o usuário escolheu arquivo; a skill antiga arriscava commitá-lo.
Decisão: grava na raiz e registra no exclude local (não versionado).
Alternativas: chat/área de transferência (recusado pelo usuário); `.gitignore` (alteraria arquivo versionado).
Consequência: arquivo já versionado não fica protegido — só avisa.

**6. Lacuna de hotfix como comentário HTML.**
Contexto: impacto e rollback raramente estão em commit ou diff, e não se pode perguntar.
Decisão: `<!-- preencher: … -->`.
Alternativas: omitir (esquece-se); marcador visível (vaza para o GitHub).
Consequência: lembra no editor, some no GitHub.

**7. Títulos de seção pertencem ao render.**
Contexto: o usuário pediu um padrão.
Decisão: o agente escreve só conteúdo; ordem, títulos e idioma são fixos no render.
Consequência: mudar um título é mudar código, com teste.

**8. Scripts não leem o working tree.**
Contexto: para comparar conteúdo, `git status` executa os filtros de limpeza configurados
(`filter.<x>.clean`); um repositório recebido pode trazer um malicioso, e nenhuma variável de
ambiente desliga isso, porque o nome do filtro é livre.
Decisão: sem checagem de mudança não commitada nos scripts; `status` sai da lista de comandos; o
relatório final sempre lembra que só entra o que está commitado.
Alternativas: checar só por metadados (não pega arquivo rastreado modificado fora do stage);
manter e documentar a exceção.
Consequência: quem esquecer de commitar é lembrado, não avisado.

## Migração e integração

1. Implementar em `~/.claude/skills/sw-pr-message/`.
2. Validar numa branch real, **somente leitura**, invocando `/sw-pr-message` explicitamente — as
   duas skills disparam nas mesmas frases enquanto coexistirem. Nada do repositório real entra
   neste dossiê (marketplace público).
3. Publicar: `make sync SKILL=sw-pr-message CATEGORY=development` + `CHANGELOG.md`.
4. **`sw-code-review`**: na seção "Limites", trocar a menção à `sw-git-pr-generator` pela
   `sw-pr-message`. `BUMP=patch`.
5. **`sw-plan`**: em "Regras comuns aos dois modos", acrescentar: *ao concluir todas as tasks,
   se for repositório git com commits na branch, oferecer via `AskUserQuestion` gerar a
   mensagem de PR com a `sw-pr-message` (se instalada)*. `BUMP=minor`.
6. Só depois de 1–5: apagar `~/.claude/skills/sw-git-pr-generator/` inteiro.

## Suposições a testar

- **60 KB / 400 linhas bastam** para o agente descrever bem — validado em duas branches reais só.
- **O agente agrupa commits por significado de forma consistente** — conferir na validação real
  (passo 2 da migração). Conferido numa branch: dependência junto da funcionalidade
  que a usa, testes em `interno` — uma branch só não prova consistência.
- **Poucos times usam `release/*` como base** entre os usuários desta skill; se não for verdade,
  reavaliar o ADR 2.
