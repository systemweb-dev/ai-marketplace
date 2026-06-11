# ai-marketplace

Meu **marketplace pessoal de skills do [Claude Code](https://claude.com/claude-code)**.
Cada skill é publicada como um plugin instalável **individualmente** — você escolhe
exatamente quais quer levar para cada máquina, e instala direto pelo Claude Code.

> Repositório: [`systemweb-dev/ai-marketplace`](https://github.com/systemweb-dev/ai-marketplace)
> Documentação em PT-BR. As skills mantêm o idioma original do seu `SKILL.md`.

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

_Nenhuma skill publicada ainda. Use `make sync SKILL=<nome>` para adicionar a primeira._

<!-- SKILLS:END -->

---

## Como sincronizar uma skill (local → repositório)

As skills nascem e evoluem em `~/.claude/skills/`. Este repositório é a **vitrine
distribuível** delas. Quando uma skill local muda, um *sync* a empacota como plugin
aqui — **sem reescrever o conteúdo**.

```bash
# Ver o que existe localmente e o que já foi publicado
make list

# Publicar / atualizar uma skill (troque pelo nome real da sua skill)
make sync SKILL=minha-skill

# Pré-visualizar sem escrever nada
python3 scripts/sync_skill.py sync minha-skill --dry-run

# Remover uma skill do marketplace
make remove SKILL=minha-skill
```

O sync faz, de forma idempotente:

1. lê `~/.claude/skills/<skill>/SKILL.md` e valida o frontmatter (`name`, `description`);
2. avisa se houver caminho absoluto pessoal vazado no conteúdo;
3. espelha a skill (com `--delete`, ignorando `.venv/`, `node_modules/`, etc.) para
   `plugins/<skill>/skills/<skill>/`;
4. gera/atualiza `plugins/<skill>/.claude-plugin/plugin.json`;
5. registra a skill em `.claude-plugin/marketplace.json`;
6. regenera a tabela de skills deste README.

> O sync **nunca** faz commit nem push. Você revisa o diff e publica quando aprovar.

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
│  └─ sync_skill.py         # motor de sync local → repo
├─ docs/estrutura.md        # formato oficial + decisões
├─ Makefile                 # atalhos: make sync / list / remove
├─ CHANGELOG.md
├─ CONTRIBUTING.md
└─ README.md
```

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
