# Changelog

Todas as mudanças relevantes deste marketplace são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões de cada skill seguem [SemVer](https://semver.org/lang/pt-BR/) no
`plugin.json` correspondente.

## [Não publicado]

### Alterado
- `sw-cluster-audit` (v0.9.0): **layout do PDF — mesmo conteúdo em 14 páginas em vez de 19**,
  com mais respiro. Margem do papel de 10mm→7mm nas laterais (+6mm de largura útil), padding e
  entrelinha maiores nos cards, e cards de nó em 4 colunas no papel (2 colunas deixavam a linha
  do grid alta demais e desperdiçavam página). O ganho maior veio da paginação: blocos de texto
  longo (impacto, recomendação, achados, stack) deixaram de ser indivisíveis — marcá-los assim
  empurrava o bloco inteiro e abandonava até 40% de papel em branco; agora fluem entre páginas e
  o que continua atômico é a unidade de leitura (um passo, um bloco de comando, uma linha de
  tabela). O plano perdeu o fundo preenchido: retângulo colorido cortado por quebra de página
  deixava faixa vazia no rodapé — virou régua lateral. Rodapé vazio médio: 9%, pior caso 16%.
  Corrigido também o rótulo colidindo com o número nos cards de dimensão.
- `sw-cluster-audit` (v0.8.0): **pontos de impacto passam a trazer plano de execução, não dica.**
  Cada ponto ganha uma lista ordenada de passos com comando pronto e o porquê da ordem, derivada
  dos fatos coletados: nº de managers reais (`docker node promote` já com os hostnames), storage
  do ACME do ingress (volume local vira passo bloqueante ANTES de escalar, senão o TLS quebra),
  e serviço com estado ganha passo próprio — nunca "suba 2 réplicas" para um banco, que daria
  duas instâncias brigando pelo mesmo volume. `mounts` passou a ser gravado por serviço para
  viabilizar a detecção do ACME.
- `scripts/sync_skill.py`: **o aviso de dado pessoal passou a respeitar os excludes do rsync.**
  Ele varria a origem inteira, incluindo `__pycache__`/`.ruff_cache`, e cuspia dezenas de avisos
  por sync sobre arquivos que nunca são publicados — gate que grita à toa é gate que se aprende
  a ignorar. Agora só olha o que de fato vai pro repo, e pula binário em vez de lê-lo com
  `errors="ignore"`. `.ruff_cache`/`.mypy_cache` entraram na lista de exclusão.
- `sw-cluster-audit` (v0.7.3): **saúde para de acusar migration como serviço caído.**
  `is_job_service` passa a aceitar task `Complete` em serviço cujo `kind` **não roda
  continuamente** — banco, fila, cache, busca e ingress ficam fora da exceção, então um postgres
  fora do ar continua sendo reportado. Certificado de cliente com validade > 3 anos virou
  **ponto de impacto** (credencial root-equivalente, sem revogação em `--tlsverify`; `ssh://`
  como saída para CI/CD), e a recomendação de **fechar a porta 2376 no firewall deixou de ser
  padrão** — quebra CI/CD hospedado e o mTLS já é a barreira. `completed_job` passou a exigir
  **nenhuma task ativa**: só `any(Complete)` isentava também worker que roda e reinicia saindo
  com 0, que ficaria mudo no dia em que caísse de verdade.
- `sw-brainstorming` (v0.5.0): **spec mais forte — anti-over-engineering + pronta pra execução**
  (baseado em pesquisa web 2025–26: Spec Kit/Kiro, *Building Evolutionary Architectures* 2ª ed.,
  Shape Up, context engineering da Anthropic). O spec passa a fechar com **Não-objetivos**,
  **Restrição de simplicidade** ("a menor solução que resolve"), **Appetite** e **MVP vs MLP**;
  ganha seção **Decisões (estilo ADR)** (contexto · decisão · alternativas descartadas ·
  consequências) e **2-4 fitness functions verificáveis** em specs substanciais (ex.: "p95 <
  200ms", "domínio sem import de infra"). Novo princípio "spec = contexto pro agente (altitude
  certa), não prosa" + item no auto-review cobrando não-objetivos/simplicidade/fitness-functions.
  Tudo proporcional ao tamanho (feature pequena leva versão enxuta).
- **Trio de design — quick wins + consolidação de tokens** (`sw-design-studio`,
  `sw-frontend-component-kit`, `sw-frontend-mockup-preview`):
  - **Tokens (fonte única):** `token-extraction.md` da mockup-preview vira o guia **canônico**
    (corrigido: usava seletores mortos `.panel--light/dark` → agora `[data-theme]`); studio e
    component-kit apontam pra ele em vez de duplicar a lógica.
  - **component-kit:** removida a contradição "autossuficiente, não invoque outras skills" (é um
    trio); nota **Stack-agnostic** (idioma por stack: Vue/React/Svelte/Angular/vanilla); consome a
    **Direção da design-studio/`DESIGN.md`** e pula a exploração via Button; corrigida a promessa
    do preview (a mockup-preview não ingere componentes reais → ver o kit é pela demo do projeto);
    `evals.json` com `skill_name` corrigido (pré-`sw-`) + **fixtures criadas** (eram inexistentes).
  - **design-studio:** Step 2 deixa de abrir menu de referência em **Autopilot** (contradição) e a
    referência entra junto de "tom & ousadia"; fallback de preview reaproveita o harness da irmã.
  - **mockup-preview:** ganha **consciência do arsenal** (oferece design-studio antes / component-kit
    depois); `serve.py` agora escuta em **`127.0.0.1`** por padrão (0.0.0.0 vira opt-in); notas sobre
    `?font` fora do mapa, `overflow` do frame no 5b e animação de entrada × troca de aba.
- `sw-brainstorming` (v0.4.0): **modo exploração ("Explorar a fundo")** — no passo 2, um loop
  divergente **opcional** de ideação por **lentes** (JTBD, divergir, desafiar suposições, flip de
  restrições, referências, riscos & bordas); a skill escolhe 2-3 conforme a ideia, pergunta uma a
  uma (com "Pular"/"Other") e oferece **convergir** a cada ~2 lentes (sem loop infinito). A síntese
  **"Exploração & decisões"** alimenta as abordagens, vira seção do spec e entra no Briefing.
  Catálogo em `references/exploration-lenses.md`. "Direto" continua o padrão (retrocompatível).
- **Rename:** `sw-writing-plans` → **`sw-plan`** (pipeline mais claro: brainstorming → plan → build).
  ⚠️ muda o comando de install (`/plugin install sw-plan@ai-marketplace`). Também: o plano salva
  em `docs/plans/` do projeto (versionável, fallback `~/.claude`); **revisor-juiz de execução
  escalonável** (Sem / por task-batch / no fim), consultivo, integrado nos dois modos; e nota
  **Stack-agnostic** (detecta linguagem/runner de teste reais; Python/pytest é só ilustração).
- `sw-brainstorming` (v0.3.0): o "resumo não-técnico" vira **"Briefing"**; o spec passa a salvar
  em **`docs/specs/`** do projeto (default, versionável) com fallback; nova seção **"Feature
  visual? Sugira as skills de design"** (arsenal: a skill analisa se é UI e sugere
  `sw-design-studio`/`sw-frontend-mockup-preview` via menu). Refs à `sw-plan` atualizadas.
- `sw-frontend-component-kit` (v0.2.0): na Fase 5, além da página de demo, **oferece via
  `AskUserQuestion` ver os componentes** — rodar a demo (`/dev/components`) ou um **preview
  isolado** via `sw-frontend-mockup-preview` (visualizar é o padrão).
- `sw-brainstorming` (v0.2.0): **revisor opcional escalonável** — no início do fluxo completo
  pergunta uma vez o nível de revisão (Sem revisor / Só no spec / Design + spec / Em cada
  checkpoint); um subagent revisor **consultivo** (não edita, não aprova) entra no design e/ou
  no spec conforme o nível. Novo template "design/checkpoint" no reviewer-prompt.
- `sw-frontend-mockup-preview` (v0.2.0): harness redesenhado — **variações em abas no topo**
  (uma tela por vez, sem empilhar) e **preview responsivo** (toggle 📱/💻/🖥/⛶) com
  responsividade real via `@container`; tema vira toggle ao vivo (canvas único). SKILL.md
  atualizado e verificado por screenshot (Playwright).
- `sw-frontend-mockup-preview` (v0.3.0): passo opcional de **auto-conferência do render**
  (passo 5b) — quando o Playwright está disponível, a skill oferece via `AskUserQuestion`
  tirar screenshot do mockup e conferir/consertar o óbvio antes de entregar a URL.
- `sw-frontend-mockup-preview` (v0.6.0): **seletor de fonte** no harness — dropdown na barra
  pra trocar a tipografia do mockup ao vivo (carrega o Google Font sob demanda; "Projeto" volta
  à fonte dos tokens) + URL param `?font=<nome>` pra screenshots. `autocomplete="off"` evita a
  restauração de formulário do Chrome sobrescrever o estado.
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
- `sw-cluster-audit` (v0.2.0): **relatório muito mais rico e amigável.** Além dos fatos, agora traz:
  **resumo executivo** (o agente explica *por que* o veredito), **notas por dimensão**
  (Segurança/Disponibilidade/Higiene, determinísticas), **recomendações priorizadas**
  (impacto/esforço), **pontos fortes × fracos**, **findings agrupados por regra e explicados**
  ("o que é / por que importa / como corrigir" em vez de tabela crua), **análise por componente**,
  **top ofensores** e **diff com a auditoria anterior** (resolvidos/novos). Template redesenhado
  (self-contained). +5 módulos/testes (métricas, rule_meta), 68 testes. Validado no cluster real.
- Skill publicada: **`sw-cluster-audit`** (v0.1.0, categoria `development`) — auditoria **READ-ONLY**
  de cluster Docker (context/Swarm) → relatório técnico **HTML + PDF** (opt-in) em `docs/infra/`.
  Coleta via **allowlist `(noun,verb)`**, **redação field-allowlist positiva** (zero valor de
  secret/env), **findings de segurança por regra determinística** (privileged, docker.sock, porta
  0.0.0.0, imagem sem digest, root), **análise por componente app-aware** (detecta Traefik/filas/
  bancos/cache e o agente analisa cada um — roteamento, HA, exposição), **degradação honesta** e
  `.gitignore` não-opcional. **7 fitness functions verificáveis**, 63 testes. Desenhada via
  `sw-brainstorming` → `sw-plan` (spec e plano em `docs/specs/` e `docs/plans/`).
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
