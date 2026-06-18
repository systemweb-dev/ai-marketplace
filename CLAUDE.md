# Regras do projeto — ai-marketplace

Marketplace **público** de skills do Claude Code da systemweb. Estas regras valem
para qualquer pessoa (ou agente) trabalhando neste repositório.

## 🔒 Segurança antes de commit e push (obrigatório)

Como o repositório é **público**, **NUNCA** deixe ir para o git:

- credenciais ou segredos: chaves de API, tokens, chaves privadas, senhas, `.env`;
- dados pessoais ou da máquina: caminhos do home (`/home/...`, `/Users/...`),
  e-mail pessoal, nomes de usuário.

**Antes de todo commit/push, rode o gate de segurança:**

```bash
make check          # escaneia o conteúdo staged
```

O gate também roda **automaticamente** via git hooks (`pre-commit` e `pre-push`)
depois de `make hooks`. Se ele apontar algo, **pare e reveja** — só prossiga com
`--no-verify` se tiver certeza de que é falso positivo.

> Em máquina nova, rode `make hooks` uma vez para ativar os hooks (eles vivem em
> `.githooks/`, versionados, mas precisam do `core.hooksPath` apontado).

## Fluxo de skills

- Skills evoluem em `~/.claude/skills/` e são publicadas como plugins via sync.
- **Convenção de nome: toda skill da systemweb usa o prefixo `sw-`** (ex.: `sw-git-commit`,
  `sw-code-review`). Evita colisão com skills de outros marketplaces e marca a origem.
  O `name` do frontmatter, o nome do diretório e o nome do plugin são sempre iguais.
- `make sync SKILL=sw-<nome>` (local → repo) · `make import SKILL=sw-<nome>` (repo → local).
- **Não reescreva o conteúdo de uma skill** sem o dono pedir.
- 1 plugin por skill; detalhes em [`docs/estrutura.md`](docs/estrutura.md).

### Ao sincronizar/atualizar uma skill (regra)

1. O `make sync` **já atualiza** `marketplace.json` e a tabela do `README.md` — não
   edite esses dois à mão.
2. A **categoria é preservada** automaticamente entre syncs; só informe `CATEGORY=`
   para definir/alterar (skill nova entra como `development` se nada for passado).
3. **Mudou o conteúdo de uma skill já publicada?** Faça bump de versão:
   `make sync SKILL=<nome> BUMP=patch` (ou `minor`/`major`).
4. Registre a mudança no [`CHANGELOG.md`](CHANGELOG.md) e rode `make check` antes de commitar.

## Git

- Conventional Commits.
- **Não dar push sem aprovação explícita do dono.**
