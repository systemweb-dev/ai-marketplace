---
name: frontend-component-kit
description: >-
  Gera o kit de componentes frontend de um projeto (Button, Input, Modal,
  Table, etc.) como código real de produção, seguindo o design system, os
  tokens e as convenções já existentes no projeto. Oferece combos de
  componentes (Essenciais, Formulários, Feedback & Overlay, Navegação & Dados,
  Dashboard, Marketing, Auth) e pergunta quais o usuário quer antes de gerar.
  Se o projeto não tem design system, faz um bootstrap guiado de tokens. Use
  SEMPRE que o usuário estiver começando um projeto frontend e precisar da base
  de componentes, ou disser coisas como "cria os componentes do projeto",
  "kit de componentes", "componentes base", "scaffolding de UI", "monta a
  component library", "preciso de Button/Input/Modal padrão", "cria o design
  system com componentes". Dispare mesmo sem a palavra "kit" quando a intenção
  for criar componentes reutilizáveis — vários de uma vez ou um único
  componente padrão que entra na biblioteca do projeto (ex.: "cria um
  componente de Table reutilizável seguindo nossos tokens"). NÃO usar para:
  mockup descartável (isso é a frontend-mockup-preview), tela/feature
  específica do app, nem instalar/configurar lib de componentes de terceiros
  (shadcn/ui, Vuetify, PrimeVue — isso é setup de dependência, não geração de
  kit próprio).
---

# Frontend Component Kit

Gerar a base de componentes reutilizáveis de um projeto frontend — código real,
no repositório, seguindo o design system e as convenções do projeto. Esta skill
é **autossuficiente**: não depende de nenhuma outra skill. Tudo que ela produz
(componentes, tokens, página de demo) é código de produção dentro do projeto —
nada de artefatos descartáveis em `/tmp`.

## Regra: TODA pergunta é via AskUserQuestion

**Toda pergunta que você fizer ao usuário usa a ferramenta `AskUserQuestion` (menu
clicável) — nunca texto solto pedindo pra ele digitar, e NUNCA termine um turno com uma
pergunta em texto** (tipo "qual stack?" / "tirar ou adicionar algum componente?" / "uso a
lib ou implementação própria?"). Vale para todos os pontos: stack (projeto novo), bootstrap
de tokens (cor/raio/fonte/tema), escolha de combos, confirmação de escopo, lib vs
implementação própria, onde montar a rota de demo. Para perguntas mais abertas (ex.: cor
em hex), ofereça as opções prováveis e conte com o campo **"Other"**. Dá pra juntar até 4
perguntas numa só chamada. Não pergunte o que dá pra inferir com segurança do código —
aí só siga e mencione a suposição.

## Fluxo

**Detectar → Tokens (+ direção via Button, em projeto novo) → Perguntar combos → Gerar → Demo + resumo**

### Fase 1: Detectar o projeto

Antes de gerar qualquer componente, mapeie:

1. **Stack**: Vue, React, Svelte, Angular ou HTML/JS vanilla? Sinais:
   `vite.config.*` + deps no `package.json`, `*.vue`, `*.tsx`, `*.svelte`.
   Se for projeto novo/vazio, pergunte a stack via AskUserQuestion.
2. **Abordagem de CSS**: Tailwind (`tailwind.config.*`), CSS variables
   (`:root { --* }`), SCSS (`*.scss`), CSS Modules, styled-components.
3. **Design tokens existentes**: procure `tailwind.config.*` com theme
   customizado, arquivos `tokens.*`, `variables.*`, `theme.*`, `:root` com
   custom properties, `DESIGN.md`.
4. **Convenções**: se já existem componentes, leia 2–3 deles e extraia o
   padrão — naming (PascalCase? prefixo tipo `App*`/`Base*`?), estrutura de
   diretórios (`src/components/ui/`?), como definem props, como exportam
   (barrel `index.ts`?), composition API vs options (Vue), function vs class.
   **Componentes novos devem parecer escritos pela mesma pessoa.**
5. **Componentes já existentes**: liste-os. Nunca sobrescreva um componente
   existente — pule e informe no resumo final.

### Fase 2: Garantir os tokens

Componente sem token vira hardcode de cor — e o kit inteiro nasce
inconsistente. Por isso esta fase vem antes da geração.

- **Projeto já tem tokens/design system** → use-os. Toda cor, espaçamento,
  raio e fonte nos componentes referencia o token, nunca o valor literal.
- **Projeto sem tokens** → faça o **bootstrap guiado**: pergunte via
  AskUserQuestion o essencial:
  - Cor primária (oferecer 3–4 paletas como opções + "Other" para hex)
  - Estilo de borda: arredondado (8px), suave (4px), quadrado (0) ou pill
  - Fonte: system stack, Inter, ou outra
  - Tema: só claro, só escuro, ou ambos (light + dark com toggle)
  
  Com as respostas, gere a fundação no formato nativo do projeto
  (`tailwind.config.*` theme, ou `:root`/`[data-theme]` custom properties, ou
  `_variables.scss`): escala da cor primária (50–900), neutros, cores
  semânticas (success/warning/error/info), espaçamento, raios, tipografia e
  sombras. Mostre os tokens criados antes de seguir para os componentes.

**Definir a direção visual via Button (só no bootstrap).** Antes de gerar o kit
inteiro, ofereça variações de **um componente-chave — o Button** — pra fixar a
estética que todos os outros vão herdar. Em vez de gerar 3 versões de cada
componente (desperdício), você explora a direção **uma vez**, no Button, e o resto
nasce consistente.

- **Dispare um `AskUserQuestion`**: *"Quer ver variações do Button pra definir o
  estilo do kit?"* → **Não, segue um padrão neutro** / **Sim, 3 variações** /
  **Sim, 5**. (Menu único — a quantidade já está nas opções, nada de pergunta
  separada de "quantos".)
- Se sim, gere as N variações em **direções genuinamente distintas** (ex.: A =
  arredondado + sombra suave + fill sólido; B = reto + flat + borda fina; C = pill
  + bold + alto contraste), todas usando os **tokens reais** já criados.
- **A pessoa precisa VER pra escolher**: renderize as N variações (claro + escuro)
  na **própria página de demo do projeto** (a mesma da Fase 5, só começando cedo) —
  é **código do projeto, não `/tmp`**, e mostra o botão renderizado de verdade com
  os tokens reais. Abra pela rota de dev do projeto. Depois da escolha, a demo passa
  a mostrar só o Button final e evolui pro kit completo. A escolha em si é outro
  `AskUserQuestion` (as variações como opções + "Other" pra misturar).
- A direção escolhida (raio, sombra, preenchimento, peso, transições) vira **regra
  para TODO o kit** — Card, Input, Modal, Tabs etc. herdam o mesmo tom. Só então
  siga para a Fase 4.

Pule esse passo quando o projeto **já tem design system**: a direção já existe, e
variação só geraria inconsistência — gere seguindo o padrão.

### Fase 3: Perguntar quais componentes gerar

Use AskUserQuestion (multiSelect: true) oferecendo os **combos**. Apresente os
4 primeiros como opções e mencione os demais — o usuário pode pedir via
"Other". Se o usuário já disse o que quer ("cria os componentes de formulário"),
pule a pergunta.

| Combo | Componentes |
|---|---|
| **Essenciais** | Button, Input, Card, Badge, Avatar, Icon, Typography (headings/text), Divider |
| **Formulários** | Select, Checkbox, Radio, Switch, Textarea, DatePicker, FileUpload, FormField (label + hint + erro) |
| **Feedback & Overlay** | Modal, Drawer, Toast, Alert, Tooltip, Popover, Spinner, Skeleton, EmptyState, ProgressBar |
| **Navegação & Dados** | Navbar, Sidebar, Tabs, Breadcrumb, Pagination, DropdownMenu, Table, List |
| **Dashboard & Métricas** | StatCard/KPI, ChartContainer (wrapper p/ lib de gráfico), FilterBar, DateRangePicker |
| **Marketing/Landing** | Hero, Footer, PricingCard, TestimonialCard, Accordion/FAQ, CTASection |
| **Auth & Conta** | LoginForm, RegisterForm, ForgotPasswordForm, UserMenu, ProfileCard |

Depois da escolha dos combos, **confirme o escopo via `AskUserQuestion`** — mostre a lista
("Vou gerar 18 componentes: Essenciais + Formulários") e ofereça **"Pode gerar"** /
**"Quero ajustar a lista"** (no "Quero ajustar" / "Other" a pessoa diz o que tirar ou
adicionar). É mais barato ajustar a lista agora do que apagar componente gerado — mas a
confirmação é um menu clicável, não uma pergunta em texto.

Dependências entre combos: Formulários, Auth e Dashboard pressupõem peças dos
Essenciais (Button, Input). Se o usuário escolher um combo dependente sem os
Essenciais, gere apenas as peças essenciais necessárias e avise.

### Fase 4: Gerar os componentes

Para cada componente:

- **Siga o padrão extraído na Fase 1** — mesmo naming, mesma estrutura de
  arquivo, mesmo estilo de props. Em projeto novo, use o idiomático da stack
  (Vue 3: `<script setup>` + composition; React: function components + hooks).
- **Variantes e estados fazem parte do componente**, não são extra: variantes
  visuais (primary/secondary/ghost/danger onde fizer sentido), tamanhos
  (sm/md/lg), e estados hover, focus, disabled, loading, erro.
- **Acessibilidade é requisito**: foco visível, `aria-*` correto (modal com
  `role="dialog"` + foco preso, toast com `aria-live`), navegação por teclado
  em menus/tabs/modais, contraste respeitando os tokens.
- **Tokens, sempre** — nenhuma cor/espaçamento/raio hardcoded.
- **Dark mode**: se os tokens suportam, todo componente funciona nos dois
  temas sem código extra (essa é a vantagem de tokens semânticos).
- **Zero dependências novas sem aprovação.** Se um componente pede uma lib
  (DatePicker, gráficos, máscara de input), pergunte antes via AskUserQuestion
  — opção de lib vs implementação própria simplificada, com prós/contras.
- **Documentação no próprio arquivo**: bloco de comentário no topo com
  descrição em uma linha, tabela de props (nome, tipo, default) e 1–2 exemplos
  de uso. Padrão JSDoc/docblock da stack.

### Fase 5: Página de demo + resumo

1. **Página de demo dentro do projeto** (código real, versionado): uma rota de
   desenvolvimento (`/dev/components`, ou `ComponentsDemo` acessível só em
   dev) que renderiza todos os componentes gerados com suas variantes e
   estados. Serve como documentação viva e smoke test visual. Siga o sistema
   de rotas do projeto; se não houver router, gere um `components-demo.html`
   na pasta de dev do projeto.
2. **Resumo final**:
   - Tokens criados/usados (e onde estão)
   - Componentes gerados, agrupados por combo, com paths
   - Componentes pulados (já existiam)
   - URL/rota da página de demo e como rodar o projeto para vê-la
   - Sugestões de próximo passo (combos não selecionados que façam sentido)

## Exemplos

**Exemplo 1 — projeto Vue novo, sem tokens:**
```
User: "cria os componentes base do projeto"
→ Detect: Vue 3 + Vite + Tailwind, sem theme customizado, zero componentes
→ Bootstrap: pergunta cor primária, raio, fonte, dark mode → estende tailwind.config
→ Direção: AskUserQuestion "ver variações do Button? Não/3/5" → usuário pede 3
  → renderiza 3 Buttons distintos (claro+escuro) na página de demo do projeto → escolhe a B
  → a direção da B vira regra do kit
→ Pergunta combos → usuário marca Essenciais + Formulários
→ Confirma o escopo via AskUserQuestion (16 componentes → Pode gerar / Quero ajustar)
→ Gera src/components/ui/*.vue + src/pages/dev/ComponentsDemo.vue + rota /dev/components
→ Resumo: tokens, 16 componentes, demo em http://localhost:5173/dev/components
```

**Exemplo 2 — projeto React existente com design system:**
```
User: "preciso dos componentes de feedback: modal, toast, essas coisas"
→ Detect: React + CSS Modules, tokens em src/styles/tokens.css,
  componentes existentes em src/components/ui (PascalCase, barrel export)
→ Tokens existem → pula bootstrap
→ Combo já especificado (Feedback & Overlay) → pula pergunta de combos
→ Detecta que Tooltip já existe → pula e informa
→ Gera os 9 restantes seguindo o padrão dos componentes existentes
→ Atualiza a página de demo existente (ou cria, se não houver)
```

## Importante

- Esta skill gera **código de produção no repositório** — não confundir com
  mockup descartável. Se o usuário quer só visualizar/explorar um design antes
  de decidir, isso é caso para a frontend-mockup-preview, não para esta skill.
- Skill autossuficiente: não invoque outras skills. Testes dos componentes,
  se o usuário quiser, são um pedido separado.
- Nunca sobrescreva componente existente; nunca instale dependência sem
  aprovação explícita.
- Em dúvida real de design (lib vs implementação própria, onde montar a rota
  de demo, paleta de cores), pergunte via AskUserQuestion com opções claras —
  não decida silenciosamente nem trave esperando texto livre.

## Checklist de fidelidade (confira antes de fechar)

Antes de dar o resumo final, releia e confirme cada item — é onde a execução costuma escapar:

- [ ] **Leu 2–3 componentes existentes e copiou o padrão** (naming, estrutura de pasta, props, export)? Os novos parecem escritos pela mesma pessoa?
- [ ] **Zero hardcode** — toda cor/espaçamento/raio/fonte referencia um token, nunca o valor literal?
- [ ] **Nenhum componente existente sobrescrito** (listou os existentes e pulou)?
- [ ] **Nenhuma dependência nova sem aprovação** explícita via AskUserQuestion?
- [ ] **Acessibilidade real** em cada um (foco visível, `aria-*`, foco preso no modal, `aria-live` no toast, teclado em menus/tabs)?
- [ ] **Dark mode** funciona nos componentes (se os tokens suportam)?
- [ ] **Página de demo gerada** e citada no resumo (com a rota/URL)?
- [ ] **Toda pergunta foi via `AskUserQuestion`** — nenhuma decisão em texto solto?
