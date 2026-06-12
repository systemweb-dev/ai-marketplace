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
- `make sync SKILL=<nome>` (local → repo) · `make import SKILL=<nome>` (repo → local).
- **Não reescreva o conteúdo de uma skill** sem o dono pedir.
- 1 plugin por skill; detalhes em [`docs/estrutura.md`](docs/estrutura.md).

## Git

- Conventional Commits.
- **Não dar push sem aprovação explícita do dono.**
