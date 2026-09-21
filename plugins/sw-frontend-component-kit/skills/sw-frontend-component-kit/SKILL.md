---
name: sw-frontend-component-kit
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
  system com componentes". Gera também a página de demo QUE ENSINA: para cada
  componente, a peça viva com controles, todos os tipos de uma vez, quando usar cada
  variante e exemplos em contexto. Use também para "página de demo dos componentes",
  "documenta os componentes", "mostra as variações pra equipe entender". Dispare mesmo sem a palavra "kit" quando a intenção
  for criar componentes reutilizáveis — vários de uma vez ou um único
  componente padrão que entra na biblioteca do projeto (ex.: "cria um
  componente de Table reutilizável seguindo nossos tokens"). NÃO usar para:
  mockup descartável (isso é a sw-frontend-mockup-preview), tela/feature
  específica do app, nem instalar/configurar lib de componentes de terceiros
  (shadcn/ui, Vuetify, PrimeVue — isso é setup de dependência, não geração de
  kit próprio).
---

# Frontend Component Kit

Gerar a base de componentes reutilizáveis de um projeto frontend — código real,
no repositório, seguindo o design system e as convenções do projeto. Ela **roda
sozinha** (não exige nenhuma outra skill), mas faz dupla com a
`sw-frontend-mockup-preview`, que decide a direção visual vendo as variações — e se integra a
ela quando está disponível. Tudo que ela produz (componentes,
tokens, página de demo) é **código de produção dentro do projeto** — nada de artefatos
descartáveis em `/tmp`.

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

**Detectar → Tokens (+ direção via amostra, em projeto novo) → Perguntar combos → Gerar → Demo que ensina + resumo**

### Fase 1: Detectar o projeto

Antes de gerar qualquer componente, mapeie:

1. **Stack**: Vue, React, Svelte, Angular ou HTML/JS vanilla? Sinais:
   `vite.config.*` + deps no `package.json`, `*.vue`, `*.tsx`, `*.svelte`.
   Se for projeto novo/vazio, pergunte a stack via AskUserQuestion.
2. **Abordagem de CSS**: Tailwind (`tailwind.config.*`), CSS variables
   (`:root { --* }`), SCSS (`*.scss`), CSS Modules, styled-components.
3. **Design tokens existentes**: procure `tailwind.config.*` com theme
   customizado, arquivos `tokens.*`, `variables.*`, `theme.*`, `:root` com
   custom properties, `DESIGN.md`. *(Guia de detecção por stack — a mesma lógica
   das skills irmãs — em `sw-frontend-mockup-preview/references/token-extraction.md`,
   se instalada; o resumo acima basta se não estiver.)*
4. **Convenções**: se já existem componentes, leia 2–3 deles e extraia o
   padrão — naming (PascalCase? prefixo tipo `App*`/`Base*`?), estrutura de
   diretórios (`src/components/ui/`?), como definem props, como exportam
   (barrel `index.ts`?), composition API vs options (Vue), function vs class.
   **Componentes novos devem parecer escritos pela mesma pessoa.**
5. **Componentes já existentes**: liste-os. Nunca sobrescreva um componente
   existente — pule e informe no resumo final.

> **Stack-agnostic — adapte a saída à stack detectada.** Os exemplos deste guia usam Vue/React
> como ilustração, mas gere no **idioma do projeto**: **Vue** → `.vue` `<script setup>` · **React**
> → `.jsx/.tsx` + hooks · **Svelte** → `.svelte` · **Angular** → componente *standalone* +
> `.html/.scss` · **vanilla** → Web Component (`customElements`) ou template + CSS. Naming,
> estrutura de pastas, barrel e a rota de demo seguem o que o projeto já usa.

### Fase 2: Garantir os tokens

Componente sem token vira hardcode de cor — e o kit inteiro nasce
inconsistente. Por isso esta fase vem antes da geração.

- **Projeto já tem tokens/design system** → use-os. Toda cor, espaçamento,
  raio e fonte nos componentes referencia o token, nunca o valor literal.
- **Projeto sem tokens** → faça o **bootstrap guiado**, sem cair no visual genérico. Pergunte
  via AskUserQuestion (até 4 perguntas numa chamada):
  - **Cena de uso:** quem usa, onde e sob que luz (ex.: "atendente no balcão, tela clara, o dia
    todo" / "gestor no celular, à noite"). É ela que decide claro ou escuro e a densidade, não a
    categoria do produto.
  - **Tom:** três palavras (ex.: sóbrio, preciso, caloroso), com opções prováveis + "Other".
  - **Cor da marca**, se existir (hex no "Other"). Sem marca, **proponha 2 ou 3 paletas
    derivadas da cena e do tom**, cada uma com o nome do que ela evoca. Nunca ofereça a lista
    pronta de "azul, roxo, verde".
  - **Tema:** só claro, só escuro, ou ambos.

  **Fontes vêm do Google Fonts**, escolhidas para o tom: um par (títulos + texto) com contraste
  real entre os dois, e mono só se o produto mostra código ou dado tabular. Inter, Roboto e
  "system stack" não são padrão: só entram se o usuário pedir ou se o projeto já usa.

  Com as respostas, gere a fundação no formato nativo do projeto (`tailwind.config.*` theme, ou
  `:root`/`[data-theme]` custom properties, ou `_variables.scss`): escala da cor primária
  (50–900), neutros **tingidos** pela cor da marca (nunca cinza puro nem preto `#000`), cores
  semânticas (success/warning/error/info), espaçamento, raios, tipografia e sombras com
  hierarquia (não a mesma sombra em tudo). Mostre os tokens criados antes de seguir.

**Direção já decidida a montante?** Se a **`sw-frontend-mockup-preview`** já fixou a direção
nesta sessão (a leitura do pedido e a variação escolhida), ou existe um **`DESIGN.md`/Direção**
no projeto, **siga essa direção e PULE a exploração via amostra abaixo** — a estética já foi
decidida; refazê-la aqui gera conflito. E no **bootstrap de projeto novo**, se a mockup estiver
instalada, **ofereça-a via `AskUserQuestion`** antes de materializar os tokens (evita o kit
nascer com "cara de IA" genérica). Só caia no fluxo da amostra quando não há direção nem mockup
à mão.

**Definir a direção visual com uma amostra (só no bootstrap, sem direção a montante).** Um
botão sozinho não decide densidade, tipografia, superfícies nem o formato dos campos. Por isso a
direção é explorada numa **amostra**: um Button (primária + secundária), um Input com rótulo e
ajuda, um Card com título e texto, dois Badges e **uma linha de tabela**. É pequeno de gerar e
cobre as decisões que o kit inteiro herda.

- **Dispare um `AskUserQuestion`**: *"Quer ver variações da amostra pra definir o estilo do
  kit?"* → **Não, sigo a direção dos tokens** / **Sim, 3 variações** / **Sim, 5**.
- As variações diferem em **eixos diferentes**, não em ajustes do mesmo: uma muda a
  **tipografia** (par de fontes e escala), outra a **superfície** (borda, sombra, raio,
  profundidade), outra a **densidade** (espaçamento, altura dos controles). Todas com os tokens
  reais já criados. Se sair "a mesma coisa com outra cor", refaça.
- **A pessoa precisa VER pra escolher**: renderize a amostra, nas N variações, claro e escuro, na
  **própria página de demo do projeto** (a mesma da Fase 5, começando cedo): é código do projeto,
  não `/tmp`. Abra pela rota de dev. A escolha é outro `AskUserQuestion` (as variações como
  opções + "Other" pra misturar).
- A variação escolhida vira **regra para TODO o kit**: raio, sombra, preenchimento, peso,
  densidade e transições. Registre-a no topo do arquivo de tokens (um comentário curto com as
  decisões), para os próximos componentes seguirem o mesmo tom. Só então siga para a Fase 3.

Pule esse passo quando o projeto **já tem design system**: a direção já existe, e variação só
geraria inconsistência.

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
- **Piso anti-genérico** (vale para cada componente): nada de texto em gradiente, preto puro,
  borda colorida grossa num lado só de card ou aviso, halo colorido sem deslocamento, "pill soup"
  (toda etiqueta virando a mesma pílula cinza), toggle iOS padrão sem adaptação, a mesma sombra
  e o mesmo raio em tudo, emoji no lugar de ícone. Easing sem quique; movimento curto, com saída
  exponencial, e o guard de `prefers-reduced-motion`. Se a `sw-frontend-mockup-preview` estiver
  instalada, o catálogo completo está em `references/piso-e-recusas.md` dela.
- **Dark mode**: se os tokens suportam, todo componente funciona nos dois
  temas sem código extra (essa é a vantagem de tokens semânticos).
- **Zero dependências novas sem aprovação.** Se um componente pede uma lib
  (DatePicker, gráficos, máscara de input), pergunte antes via AskUserQuestion
  — opção de lib vs implementação própria simplificada, com prós/contras.
- **Documentação no próprio arquivo**: bloco de comentário no topo com
  descrição em uma linha, tabela de props (nome, tipo, default) e 1–2 exemplos
  de uso. Padrão JSDoc/docblock da stack.

### Fase 5: A demo que ensina + resumo

**Leia [`references/demo-que-ensina.md`](references/demo-que-ensina.md) antes de gerar a demo**
e abra [`assets/demo-estudio.html`](assets/demo-estudio.html) no navegador: é a referência
visual aprovada (direção "Estúdio").

1. **Página de demo dentro do projeto** (código real, versionado): uma rota de desenvolvimento
   (`/dev/components`, ou `ComponentsDemo` acessível só em dev), no sistema de rotas do projeto;
   sem router, um `components-demo.html` na pasta de dev. **Toda tela de componente** tem, nesta
   ordem:
   - lista lateral dos componentes do kit, com o número de variantes;
   - cabeçalho com o nome e uma frase do que faz;
   - **barra de controles dentro do conteúdo** (variante, tamanho, estado, texto), acima do palco;
   - **palco de estúdio** com o componente real vivo e a legenda do estado atual;
   - **Todos os tipos**: todas as variantes, tamanhos, estados e formas **ao mesmo tempo**
     (tabela variantes × tamanhos/estados, e cartões para as formas extras);
   - **Quando usar cada variante**: amostra, quando usar, e "Não use" com a consequência;
   - **Exemplos em contexto**: de 3 a 5 usos reais, cada um com o porquê em uma frase.

   **Nada de código na página**: sem bloco de código nem "copiar". O código e os exemplos de uso
   ficam no docblock do componente. O catálogo do que mostrar em "Todos os tipos" e nos exemplos,
   componente por componente, está na referência.
2. **Resumo final**:
   - Tokens criados/usados (e onde estão)
   - Componentes gerados, agrupados por combo, com paths
   - Componentes pulados (já existiam)
   - URL/rota da página de demo e como rodar o projeto para vê-la
   - Sugestões de próximo passo (combos não selecionados que façam sentido)
3. **Ver os componentes — ofereça via `AskUserQuestion`** (visualizar é o padrão, não um extra):
   - **Rodar a demo do projeto** — suba o app e abra a rota `/dev/components` gerada acima. É o
     jeito real de ver o kit: código de produção renderizado com os tokens reais.
   - Sem router/app pra subir? O `components-demo.html` estático abre direto no navegador.

   > **Não** ofereça a `sw-frontend-mockup-preview` pra "ver o kit gerado" — ela cria HTML
   > **descartável do zero** e não ingere seus componentes Vue/React (seria reescrever tudo). O
   > lugar dela é **antes**, pra explorar uma direção/variação nova; depois de gerar, quem mostra
   > o kit é a demo do projeto.

## Exemplos

**Exemplo 1 — projeto Vue novo, sem tokens:**
```
User: "cria os componentes base do projeto"
→ Detect: Vue 3 + Vite + Tailwind, sem theme customizado, zero componentes
→ Bootstrap: pergunta cor primária, raio, fonte, dark mode → estende tailwind.config
→ Direção: AskUserQuestion "ver variações da amostra? Não/3/5" → usuário pede 3
  → renderiza a amostra (Button, Input, Card, Badges, linha de tabela) em 3 eixos diferentes
    (tipografia, superfície, densidade), claro+escuro, na página de demo do projeto → escolhe a B
  → a direção da B vira regra do kit (registrada no topo do arquivo de tokens)
→ Pergunta combos → usuário marca Essenciais + Formulários
→ Confirma o escopo via AskUserQuestion (16 componentes → Pode gerar / Quero ajustar)
→ Gera src/components/ui/*.vue + src/pages/dev/ComponentsDemo.vue + rota /dev/components
  (cada componente com controles, palco, todos os tipos, quando usar e exemplos em contexto)
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
  de decidir, isso é caso para a sw-frontend-mockup-preview, não para esta skill.
- Skill autossuficiente: roda sem nenhuma outra skill. A única que ela **oferece** (via
  `AskUserQuestion`, nunca invoca por conta própria) é a `sw-frontend-mockup-preview`, para
  explorar a direção antes do bootstrap (Fase 2). Testes dos componentes, se o usuário quiser, são
  um pedido separado.
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
- [ ] **Cada tela de componente** tem controles no conteúdo, palco, **todos os tipos**, quando
      usar / não use e **3 a 5 exemplos em contexto**, sem nenhum bloco de código?
- [ ] **Sem visual genérico**: nada de paleta ou fonte "padrão de IA" no bootstrap, fontes do
      Google Fonts escolhidas pelo tom, e o piso anti-genérico em cada componente?
- [ ] **Toda pergunta foi via `AskUserQuestion`** — nenhuma decisão em texto solto?
