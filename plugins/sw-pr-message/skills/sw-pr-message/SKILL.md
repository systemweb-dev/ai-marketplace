---
name: sw-pr-message
description: >-
  Gera o PR-MESSAGE.md de uma branch — a descrição do pull request pronta para colar no GitHub,
  com as mudanças agrupadas por tipo (Novas funcionalidades, Ajustes, Correções, Removido,
  Segurança, Interno), "Como testar" e, em hotfix, causa, impacto e rollback. Detecta sozinha a
  branch base certa (inclusive em fluxo develop + master), lê commits e diff, junta commits da
  mesma mudança num item só e não deixa commit de fora. Use SEMPRE que o usuário quiser
  descrever ou preparar um PR, ou resumir o que fez na branch — "gera a mensagem do PR",
  "cria a descrição do pull request", "resume o que fiz nessa branch", "o que mudou nessa
  branch", "prepara a branch pra review", "monta o PR", e em inglês "generate a PR message",
  "write the PR description", "summarize my branch". Dispare mesmo sem a palavra "PR".
  NÃO cria nem edita PR no GitHub e não dá push — só gera o arquivo local. NÃO use para
  escrever mensagem de commit (sw-git-commit) nem para revisar código (sw-code-review).
---

# PR Message

Transforma os commits e o diff de uma branch num `PR-MESSAGE.md` no mesmo padrão sempre.
**O script cuida do que tem resposta certa** (base, coleta, validação, formato); **você cuida do
que exige leitura** (juntar commits numa mudança, classificar, escrever).

**Anuncie no início:** "Estou usando a skill sw-pr-message para gerar a mensagem do PR."

## Garantias

- **Só leitura no git.** Os scripts executam apenas comandos git de leitura, por uma lista
  fechada. Não rode `git` de escrita por conta própria durante esta skill.
- **Nunca inventa.** Impacto ou rollback de hotfix sem evidência ficam como comentário
  `<!-- preencher: … -->`, que aparece no editor e some no GitHub.
- **Não cria nem edita PR, não dá push.** O `gh`, se usado, só consulta.
- **O arquivo não vai para commit por engano:** o render registra `/PR-MESSAGE.md` no
  `info/exclude` local.

## Fluxo

### 1. Idioma — a única pergunta

Se o pedido já disser ("em inglês", "in English"), use. Senão, pergunte via `AskUserQuestion`:
**Português** / **English**. Não faça nenhuma outra pergunta.

### 2. Base pelo PR aberto (se houver)

Se o usuário informou a base, use-a como `--base`. Senão, tente descobrir pelo PR já aberto:

```bash
gh auth status >/dev/null 2>&1 && \
  gh pr view --json baseRefName,state --jq 'select(.state=="OPEN") | .baseRefName' 2>/dev/null
```

Saída não vazia → use como `--base` e **anote que veio do `gh`**. Qualquer falha (sem `gh`, sem
login, sem PR) → siga sem `--base`, sem avisar.

### 3. Coletar

```bash
python3 <skill-dir>/scripts/collect.py [--base <nome>]
```

Rode os dois scripts **dentro do repositório** que vai descrever (qualquer subpasta serve): eles usam o
diretório atual. Não faça `cd` para `<skill-dir>`.

- **Exit 0** → imprime o caminho do `fatos.json`, a linha `base: …` com as contagens e, se houver,
  `empate:`, `cortados:` e `aviso:`. **Guarde essas linhas** — elas voltam no passo 6.
- **Exit 2** → mostre a mensagem ao usuário e **pare**. A mensagem já diz o que fazer (ex.: "staging
  já contém a branch · develop: 9 · master: 205 → rode com --base develop").
  **Única exceção:** se a `--base` veio do `gh` e a mensagem é `A base '…' não existe localmente`
  (fork com remoto `upstream`), rode de novo **sem** `--base` e avise o usuário disso no final. Se essa
  nova coleta também parar, mostre a mensagem dela e diga que a base do `gh` foi descartada.
- **Qualquer outro código** (erro inesperado, com traceback) → mostre a saída e pare.

### 4. Escrever o `mudancas.json`

Leia o `fatos.json` inteiro. Escreva `mudancas.json` **na mesma pasta**, todo o texto no idioma
escolhido:

```json
{ "idioma": "pt",
  "titulo": "Pagamento por Pix no checkout",
  "resumo": "Permite cobrar por Pix no checkout, com confirmação automática do gateway.",
  "secoes": { "novas":     [{"texto": "Pagamento por Pix com QR Code", "commits": ["a1b2c3d", "9f8e7d6"]}],
              "ajustes":   [{"texto": "Timeout da cobrança de 30s para 60s", "commits": ["5c4b3a2"]}],
              "correcoes": [], "removido": [], "seguranca": [],
              "interno":   [{"texto": "Serviço de cobrança extraído do controller", "commits": ["1a2b3c4"]}] },
  "como_testar": ["Criar um pedido e escolher Pix", "Pagar o QR Code no ambiente de teste"],
  "sem_item": [{"hash": "7e6d5c4", "motivo": "desfeito pelo commit seguinte"}] }
```

**Regras:**
- **Um item = uma mudança.** Commits do mesmo ajuste viram um item só, com todos os hashes
  (prefixo de 7+ caracteres).
- **Classifique pelo significado, não pelo prefixo do commit.**
  - `novas` — capacidade que não existia.
  - `ajustes` — comportamento existente que mudou (inclusive um `feat` que só altera algo).
  - `correcoes` — o que estava errado e foi corrigido.
  - `removido` — o que deixou de existir.
  - `seguranca` — vulnerabilidade fechada (inclusive um `chore(deps)` com esse efeito).
  - `interno` — refactor, testes, CI, build, docs: sem efeito para quem usa.
- **Commit vago** ("ajustes", "wip") → explique pelo diff. Arquivo com `"cortado": true` não é
  descrito além do que aparece.
- **`sem_item`** só para commit sem efeito líquido (desfeito depois, vazio, wip revertido) — nunca
  para commit difícil de descrever.
- **`titulo`** é uma frase descritiva, sem `feat(x):` nem `[Feature]`. **`resumo`**: 1–3 frases com
  o que muda e por quê. Todo texto vira uma linha só — não use quebra de linha, lista ou título dentro dele.
- **Nome de código** (componente, função, arquivo, comando) vai **entre crases**: `<Select>` solto some
  quando o GitHub renderiza.
- **`como_testar`** só com passos observáveis. Nada a observar (só refactor/testes) → lista vazia.
- **`hotfix`** — se `fatos.hotfix.provavel` for `true`, inclua **obrigatoriamente**
  `{"causa": …, "impacto": …, "rollback": …}`, com `null` em todo campo sem evidência nos commits ou
  no diff. Se for `false`, **não inclua** a chave. Nunca invente impacto ou rollback.

### 5. Renderizar

```bash
python3 <skill-dir>/scripts/render.py
```

- **Exit 0** → `PR-MESSAGE.md` gravado; pode imprimir avisos.
- **Exit 3** → o render lista **todos** os problemas. Corrija todos no `mudancas.json` e rode de
  novo. **Na 3ª recusa seguida, pare** e mostre os problemas ao usuário.
- **Exit 2** → problema de ambiente (`fatos.json` de outra branch, `PR-MESSAGE.md` como link
  simbólico…): mostre a mensagem e pare. Não mexa no `mudancas.json` — ele não é a causa.
- **Qualquer outro código** (erro inesperado, com traceback) → mostre a saída e pare.

### 6. Informar

Termine com:
- caminho do `PR-MESSAGE.md`;
- **base e como foi detectada**, copiando a linha `base:` da coleta (`base: develop (origin/develop) ·
  heuristica · 9 commit(s) · develop 9 · master 205`) e a de `empate:`, se houver — se a base estiver
  errada, o usuário refaz com `--base`;
- se a `--base` veio do PR aberto (`gh`), diga isso — a linha `base:` mostra `informada`, mas quem
  informou foi o PR, não o usuário; se ela foi descartada no passo 3, diga isso também;
- avisos da coleta e do render (ex.: `pr_message_versionado` — o exclude não protege arquivo versionado);
- arquivos cortados, se houver;
- quantos campos de hotfix ficaram como `<!-- preencher -->`;
- **sempre**, como última linha: "Só entram mudanças commitadas — o que não foi commitado ficou de fora."

## Limites

- Descreve **commits**: mudança não commitada fica de fora. Os scripts não leem o working tree (o
  `git status` executaria filtros configurados), por isso isso é um lembrete fixo, não uma detecção.
- Branch saída de `release/*` ou empilhada sobre outra feature pode ter a base errada — por isso a
  base aparece no final.
- Clone raso, clone parcial, HEAD destacado e rebase em andamento não são suportados (a coleta para).
