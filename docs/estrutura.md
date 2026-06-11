# Formato e estrutura do marketplace

Este documento registra **como** o repositório está organizado e **por quê** —
para referência futura e para quem for contribuir.

## Por que "marketplace de plugins"

O Claude Code distribui extensões via **plugin marketplace**: um repositório git
com um `.claude-plugin/marketplace.json` na raiz, que cataloga plugins. Cada plugin
pode embrulhar `skills/`, `commands/`, `agents/`, `hooks/` e `.mcp.json`.

Adotamos esse formato (em vez de um "repo de skills solto") porque ele permite
instalação nativa e seletiva direto no Claude Code:

```text
/plugin marketplace add systemweb-dev/ai-marketplace
/plugin install <skill>@ai-marketplace
```

## Decisão: 1 plugin por skill

Cada skill vira **um plugin independente**. É o que viabiliza "escolher quais
skills levar" — você instala uma a uma, sem arrastar o conjunto todo. O catálogo
(`marketplace.json`) referencia cada plugin por caminho local (`./plugins/<skill>`).

```text
ai-marketplace/
├─ .claude-plugin/
│  └─ marketplace.json          # { name, owner, plugins: [...] }
└─ plugins/
   └─ <skill>/
      ├─ .claude-plugin/
      │  └─ plugin.json          # { name, description, version, author }
      └─ skills/
         └─ <skill>/
            ├─ SKILL.md          # frontmatter: name + description
            └─ ...               # references/, scripts/, assets/, evals/
```

### `marketplace.json` (catálogo)

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "ai-marketplace",
  "description": "...",
  "owner": { "name": "systemweb-dev" },
  "plugins": [
    {
      "name": "minha-skill",
      "source": "./plugins/minha-skill",
      "description": "...",
      "category": "development"
    }
  ]
}
```

### `plugin.json` (por skill)

```json
{
  "name": "minha-skill",
  "description": "...",
  "version": "0.1.0",
  "author": { "name": "systemweb-dev" }
}
```

## Sync local → repositório

O `scripts/sync_skill.py` é a única peça que move conteúdo de `~/.claude/skills/`
para cá. Ele é **idempotente** e **não escreve no git** — só prepara o working tree.
Veja o passo a passo no [README](../README.md#como-sincronizar-uma-skill-local--repositório).

Regras de cópia:

- espelha com `rsync -a --delete` (o repo reflete fielmente a skill local);
- exclui `.venv/`, `node_modules/`, `__pycache__/`, `*-workspace/`, `.DS_Store`, etc.;
- valida frontmatter (`name`, `description`) e avisa sobre caminhos pessoais vazados.

## Categorias usadas

`development`, `design`, `testing`, `productivity` — alinhadas às categorias do
marketplace oficial. Sobrescreva no sync com `CATEGORY=<cat>`.
