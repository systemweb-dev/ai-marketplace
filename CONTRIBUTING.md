# Como adicionar uma skill

Este marketplace é alimentado a partir das skills locais em `~/.claude/skills/`.
O fluxo normal é: **criar/ajustar a skill localmente → rodar o sync → revisar → commit/push.**

## 1. Tenha a skill local válida

A skill precisa de um `SKILL.md` com frontmatter YAML mínimo:

```markdown
---
name: minha-skill
description: >-
  Descrição otimizada para *triggering*: diga claramente QUANDO a skill deve ser
  usada, com gatilhos e exemplos de frases do usuário. É isso que faz o Claude
  Code escolher (ou não) a skill na hora certa.
---

# Minha Skill

Instruções, passos, exemplos…
```

Diretrizes da `description`:

- Comece pelo **quando usar** (gatilhos), não só pelo "o que faz".
- Inclua frases reais que o usuário diria.
- Se a skill só deve rodar sob invocação explícita, deixe isso explícito.
- Sem caminhos absolutos da sua máquina nem dados pessoais.

Subdiretórios de apoio (`references/`, `scripts/`, `assets/`, `evals/`) são copiados
junto. Lixo de build/eval (`.venv/`, `node_modules/`, `__pycache__/`, `*-workspace/`)
é ignorado automaticamente.

## 2. Publique no marketplace

```bash
make sync SKILL=minha-skill          # empacota como plugin e registra no catálogo
make list                            # confere o status (publicada / não publicada)
```

Isso cria:

```text
plugins/minha-skill/
├─ .claude-plugin/plugin.json        # name, description, version, author
└─ skills/minha-skill/SKILL.md       (+ subdiretórios)
```

…e atualiza `.claude-plugin/marketplace.json` + a tabela do `README.md`.

## 3. Revise e versione

- Confira o `git diff`.
- Para mudanças de conteúdo já publicado, incremente a versão:
  `make sync SKILL=minha-skill BUMP=patch` (ou `minor` / `major`).
- Anote o que mudou no [`CHANGELOG.md`](CHANGELOG.md).

## 4. Commit e push

Commits seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/):

```bash
git add -A
git commit -m "feat(minha-skill): publica skill no marketplace"
git push
```

> **Nada vai para o GitHub sem revisão.** O `push` é sempre uma ação explícita sua.
