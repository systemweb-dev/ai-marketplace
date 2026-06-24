# Changelog

Todas as mudanças relevantes deste marketplace são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões de cada skill seguem [SemVer](https://semver.org/lang/pt-BR/) no
`plugin.json` correspondente.

## [Não publicado]

### Alterado
- `sw-frontend-mockup-preview` (v0.2.0): harness redesenhado — **variações em abas no topo**
  (uma tela por vez, sem empilhar) e **preview responsivo** (toggle 📱/💻/🖥/⛶) com
  responsividade real via `@container`; tema vira toggle ao vivo (canvas único). SKILL.md
  atualizado e verificado por screenshot (Playwright).
- `sw-frontend-mockup-preview` (v0.3.0): passo opcional de **auto-conferência do render**
  (passo 5b) — quando o Playwright está disponível, a skill oferece via `AskUserQuestion`
  tirar screenshot do mockup e conferir/consertar o óbvio antes de entregar a URL.
- `sw-frontend-mockup-preview` (v0.5.0): pergunta de **tema com 3 opções** (Claro/Escuro/Ambos)
  e orientação para usar **imagens de placeholder público** (Lorem Picsum, pravatar, placehold.co)
  quando o componente mostra foto — hotlink ou baixar pro dir do mockup.
- `sw-frontend-mockup-preview` (v0.4.1): a auto-conferência roda **sem interrupção**
  (ferramentas de leitura do Playwright pré-autorizadas, sem prompt a cada ação) e
  **fecha o browser** (`browser_close`) ao terminar.
- `sw-frontend-mockup-preview` (v0.4.0): auto-conferência mais **rápida** — harness aceita
  estado por URL (`?vw`/`?theme`/`?v`), então o 5b captura sem cliques (1 navigate + 1 shot),
  reusa o browser, usa `domcontentloaded` e screenshot do canvas (não fullPage). E **pergunta
  ao usuário quais telas** capturar em vez de fixar um número.
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
- Skill publicada: `sw-study-buddy` (v0.1.0, categoria `productivity`) — tutor de estudos de
  tecnologia (modos Aprender/Explicar/Praticar, apostila viva em HTML, progresso). Ao iniciar,
  oferece buscar novidades/mudanças recentes do tema na internet (foco "o que mudou", datado).
- Skill publicada: `sw-design-studio` (v0.1.0, categoria `design`) — diretor de design
  interativo: decide a direção visual (8 eixos) fugindo dos clichês de IA, com modo de condução
  (guiado/autopilot/híbrido), modo didático (nomeia técnicas + glossário), e usa o design system
  existente como base. Combina só com skills de design (mockup-preview, component-kit).
- Skill publicada: `sw-code-review` (v0.1.0, categoria `development`) — review profundo
  language-agnostic com princípio "zero falso positivo": roda linters/typecheckers reais
  (Step 4c), verificação adversarial + nível de confiança (Step 5.5), supressão de FP, modo PR,
  RBAC/info-disclosure/typo-cross-file/cross-repo. Catálogo de patterns em references/patterns.md.
- Skills publicadas: `sw-brainstorming` e `sw-writing-plans` (v0.1.0, categoria `productivity`) —
  pipeline de design→plano: brainstorming (o quê, com resumo não-técnico opcional) e
  writing-plans (como + executar, com tipos/qualidade de teste, aprovação de plano e commit nos checkpoints).
- Skills publicadas: `dead-code-scan` e `skill-test` (v0.1.0, categoria `development`) —
  varredura de código morto com modelo de confiança; e teste leve de skills (comportamento + disparo).
- Skill publicada: `git-commit` (v0.1.0, categoria `development`) — split em Conventional
  Commits, com split por hunk (Rule E), fallback p/ repo sem histórico, tratamento de hook
  que reformata, `Co-Authored-By` conforme convenção e toda decisão via `AskUserQuestion`.
- Gate de segurança `scripts/scan_secrets.py` + git hooks `pre-commit`/`pre-push`
  (`make hooks` / `make check`): bloqueia commit/push com credenciais ou dados pessoais.
- `CLAUDE.md` com as regras do projeto.
- Documentação PT-BR: README, CONTRIBUTING e `docs/estrutura.md`.
