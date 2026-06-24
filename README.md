# ai-marketplace

**Marketplace de skills do [Claude Code](https://claude.com/claude-code) da systemweb** —
uma coleção curada de **skills personalizadas** para acelerar o desenvolvimento no dia a dia.
Cada skill é publicada como um plugin instalável **individualmente**: registre o marketplace
uma vez e instale só o que precisar, direto pelo Claude Code.

> Repositório: [`systemweb-dev/ai-marketplace`](https://github.com/systemweb-dev/ai-marketplace)
> Mantido pela **systemweb**. Documentação em PT-BR; cada skill mantém o idioma do seu `SKILL.md`.

---

## Como instalar

Dentro do Claude Code:

```text
# 1. Registrar este marketplace (uma vez por máquina)
/plugin marketplace add systemweb-dev/ai-marketplace

# 2. Instalar só as skills que você quer
/plugin install <skill>@ai-marketplace

# 3. Conferir / gerenciar
/plugin                      # abre o gerenciador de plugins
/plugin marketplace update ai-marketplace   # puxa atualizações deste repo
```

Cada linha da tabela abaixo já traz o comando exato de instalação.

---

## Skills disponíveis

<!-- SKILLS:START -->

| Skill | Categoria | O que faz | Instalar |
|-------|-----------|-----------|----------|
| [`sw-brainstorming`](plugins/sw-brainstorming/) | productivity | Transforma uma ideia em design e spec ANTES de implementar, por diálogo guiado: explora o contexto, faz perguntas uma a uma, propõe abordagens e escreve um… | `/plugin install sw-brainstorming@ai-marketplace` |
| [`sw-code-review`](plugins/sw-code-review/) | development | Code review profundo com deteccao de autorizacao/RBAC ausente, information disclosure em erros, typos cross-file, coercao de tipos em boundaries, disciplina de… | `/plugin install sw-code-review@ai-marketplace` |
| [`sw-dead-code-scan`](plugins/sw-dead-code-scan/) | development | Varre o projeto inteiro e identifica código não utilizado — imports/uses órfãos, variáveis e parâmetros mortos, funções/métodos/classes nunca chamados… | `/plugin install sw-dead-code-scan@ai-marketplace` |
| [`sw-design-studio`](plugins/sw-design-studio/) | design | Diretor de design interativo: conduz o usuário, via AskUserQuestion, a DECIDIR a direção visual (referência/âncora, tom & ousadia, personalidade, paleta… | `/plugin install sw-design-studio@ai-marketplace` |
| [`sw-frontend-component-kit`](plugins/sw-frontend-component-kit/) | design | Gera o kit de componentes frontend de um projeto (Button, Input, Modal, Table, etc.) como código real de produção, seguindo o design system, os tokens e as… | `/plugin install sw-frontend-component-kit@ai-marketplace` |
| [`sw-frontend-mockup-preview`](plugins/sw-frontend-mockup-preview/) | design | Cria mockups HTML descartáveis de qualquer tela ou componente de UI usando os design tokens REAIS do projeto (cores, espaçamento, fonte), serve com live-reload… | `/plugin install sw-frontend-mockup-preview@ai-marketplace` |
| [`sw-git-commit`](plugins/sw-git-commit/) | development | Analyze uncommitted changes (staged, unstaged, untracked) and split them into multiple well-scoped Conventional Commits, each representing one logical concern. | `/plugin install sw-git-commit@ai-marketplace` |
| [`sw-skill-test`](plugins/sw-skill-test/) | development | Testa rápido se uma skill JÁ EXISTENTE funciona de verdade — sem navegador, sem benchmark pesado, sem API key. | `/plugin install sw-skill-test@ai-marketplace` |
| [`sw-study-buddy`](plugins/sw-study-buddy/) | productivity | Tutor de estudos para qualquer assunto de tecnologia — linguagens de programação, frameworks, bibliotecas, documentações, paradigmas (funcional, OO, reativo)… | `/plugin install sw-study-buddy@ai-marketplace` |
| [`sw-writing-plans`](plugins/sw-writing-plans/) | productivity | Transforma um spec/requisitos em um plano de implementação detalhado (estrutura de arquivos + tasks bite-sized com código e comandos exatos, qualidade de… | `/plugin install sw-writing-plans@ai-marketplace` |

<!-- SKILLS:END -->

---

## Como sincronizar skills (local ↔ repositório)

As skills nascem e evoluem em `~/.claude/skills/` (onde o Claude Code as carrega e você
as edita). Este repositório é a **vitrine distribuível** delas. O fluxo tem dois sentidos:

```bash
# Ver o que existe localmente e o que já foi publicado
make list

# ── local → repo: publicar / atualizar uma skill ───────────────────
make sync SKILL=minha-skill
python3 scripts/sync_skill.py sync minha-skill --dry-run   # prévia, sem escrever

# ── repo → local: trazer uma skill publicada para EDITAR ───────────
make import SKILL=minha-skill            # copia para ~/.claude/skills/minha-skill
make import SKILL=minha-skill FORCE=1    # sobrescreve a versão local existente

# Remover uma skill do marketplace
make remove SKILL=minha-skill
```

O **sync** (`local → repo`) faz, de forma idempotente:

1. lê `~/.claude/skills/<skill>/SKILL.md` e valida o frontmatter (`name`, `description`);
2. avisa se houver caminho absoluto pessoal vazado no conteúdo;
3. espelha a skill (com `--delete`, ignorando `.venv/`, `node_modules/`, etc.) para
   `plugins/<skill>/skills/<skill>/`;
4. gera/atualiza `plugins/<skill>/.claude-plugin/plugin.json`;
5. registra a skill em `.claude-plugin/marketplace.json`;
6. regenera a tabela de skills deste README.

### Melhorar uma skill já publicada (ciclo completo)

Quando você instala uma skill via `/plugin install`, ela vai para o **cache de plugins**
do Claude Code — um local não editável. Para melhorá-la, traga-a de volta ao local padrão:

1. **Clone** este repositório (ou use o que você já tem).
2. **`make import SKILL=<nome>`** → copia a versão publicada para `~/.claude/skills/<nome>`,
   onde o Claude Code a carrega e você pode editar normalmente.
3. **Melhore** a skill em `~/.claude/skills/<nome>`.
4. **`make sync SKILL=<nome>`** → publica as melhorias de volta no repositório.
5. **Revise o diff, faça commit e push.**

> Nem o `sync` nem o `import` fazem commit ou push. Você revisa o diff e publica quando aprovar.
> O `import` se recusa a sobrescrever uma skill local existente sem `FORCE=1`, para não
> apagar trabalho não sincronizado.

Detalhes do formato e do fluxo em [`docs/estrutura.md`](docs/estrutura.md).

---

## Estrutura do repositório

```text
ai-marketplace/
├─ .claude-plugin/
│  └─ marketplace.json      # catálogo: lista todos os plugins/skills
├─ plugins/
│  └─ <skill>/
│     ├─ .claude-plugin/plugin.json
│     └─ skills/<skill>/SKILL.md   (+ references/, scripts/, assets/…)
├─ scripts/
│  ├─ sync_skill.py         # motor de sync local ↔ repo
│  └─ scan_secrets.py       # gate de segurança (segredos / dados pessoais)
├─ .githooks/               # pre-commit / pre-push (instala com `make hooks`)
├─ docs/estrutura.md        # formato oficial + decisões
├─ CLAUDE.md                # regras do projeto (segurança, fluxo)
├─ Makefile                 # atalhos: sync / import / check / hooks / …
├─ CHANGELOG.md
├─ CONTRIBUTING.md
└─ README.md
```

> **Segurança:** rode `make hooks` uma vez por máquina para ativar o gate que
> bloqueia commit/push com credenciais ou dados pessoais. Veja [`CLAUDE.md`](CLAUDE.md).

---

## Setup opcional por máquina

A skill **`sw-frontend-mockup-preview`** pode conferir o render por screenshot
(Playwright). Para isso rodar **sem pedir permissão a cada ação** (e não travar),
pré-autorize as ferramentas de **leitura** do Playwright no `~/.claude/settings.json`
**desta máquina**:

```json
{
  "permissions": {
    "allow": [
      "mcp__plugin_playwright_playwright__browser_navigate",
      "mcp__plugin_playwright_playwright__browser_take_screenshot",
      "mcp__plugin_playwright_playwright__browser_snapshot",
      "mcp__plugin_playwright_playwright__browser_console_messages",
      "mcp__plugin_playwright_playwright__browser_resize",
      "mcp__plugin_playwright_playwright__browser_wait_for",
      "mcp__plugin_playwright_playwright__browser_close"
    ]
  }
}
```

Só conveniência. As ferramentas que **executam código/enviam arquivo**
(`browser_evaluate`, `browser_run_code_unsafe`, `browser_file_upload`) ficam **de fora
de propósito** — continuam pedindo confirmação.

---

## Versionamento

- Cada plugin tem `version` (semver) em seu `plugin.json`. Atualize ao publicar
  mudanças: `make sync SKILL=<nome> BUMP=patch|minor|major`.
- Mudanças relevantes do repositório vão no [`CHANGELOG.md`](CHANGELOG.md).
- Releases do conjunto podem ser marcadas com tags git (`v1.0.0`, …) quando fizer sentido.

---

## Contribuir / adicionar uma skill nova

Veja [`CONTRIBUTING.md`](CONTRIBUTING.md) para o template de skill e o passo a passo.

## Licença

[MIT](LICENSE) © 2026 systemweb-dev
