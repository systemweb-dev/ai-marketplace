# Changelog

Todas as mudanças relevantes deste marketplace são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões de cada skill seguem [SemVer](https://semver.org/lang/pt-BR/) no
`plugin.json` correspondente.

## [Não publicado]

### Alterado
- **Convenção de nomes:** todas as skills passam a usar o prefixo `sw-` (systemweb) —
  evita colisão com skills de outros marketplaces. As 5 publicadas foram renomeadas:
  `frontend-component-kit`→`sw-frontend-component-kit`, `frontend-mockup-preview`→`sw-frontend-mockup-preview`,
  `git-commit`→`sw-git-commit`, `dead-code-scan`→`sw-dead-code-scan`, `skill-test`→`sw-skill-test`.
  ⚠️ Muda o comando de install (ex.: `/plugin install sw-git-commit@ai-marketplace`).
  Cross-references entre skills atualizadas; caminhos internos da `sw-study-buddy` corrigidos.
- `frontend-component-kit` (v0.1.1) e `frontend-mockup-preview` (v0.1.2): nova regra
  "toda pergunta via `AskUserQuestion`" (menu clicável, sem pergunta em texto solto).
- `scripts/sync_skill.py`: o sync agora **preserva a categoria** já registrada quando
  `CATEGORY=` não é informado (antes revertia para o default `development`).

### Adicionado
- Estrutura inicial do marketplace (formato oficial de plugins do Claude Code).
- Script `scripts/sync_skill.py` + `Makefile`: sync `local → repo`, `import`
  (`repo → local`), `list`, `remove`, `readme`.
- Skills publicadas: `frontend-component-kit` e `frontend-mockup-preview` (categoria `design`).
- Skills publicadas: `dead-code-scan` e `skill-test` (v0.1.0, categoria `development`) —
  varredura de código morto com modelo de confiança; e teste leve de skills (comportamento + disparo).
- Skill publicada: `git-commit` (v0.1.0, categoria `development`) — split em Conventional
  Commits, com split por hunk (Rule E), fallback p/ repo sem histórico, tratamento de hook
  que reformata, `Co-Authored-By` conforme convenção e toda decisão via `AskUserQuestion`.
- Gate de segurança `scripts/scan_secrets.py` + git hooks `pre-commit`/`pre-push`
  (`make hooks` / `make check`): bloqueia commit/push com credenciais ou dados pessoais.
- `CLAUDE.md` com as regras do projeto.
- Documentação PT-BR: README, CONTRIBUTING e `docs/estrutura.md`.
