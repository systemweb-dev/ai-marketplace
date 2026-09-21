---
name: sw-frontend-mockup-preview
description: >-
  Cria mockups HTML descartáveis de qualquer tela ou componente de UI usando os
  design tokens REAIS do projeto (cores, espaçamento, fonte), serve com
  live-reload para iteração visual instantânea via URL no navegador, e ao
  aprovar converte a variação escolhida em código real seguindo as regras do
  projeto. Stack-agnostic (CSS variables, Tailwind, SCSS). Use SEMPRE que o
  usuário quiser ver/explorar/comparar um design antes de implementar — frases
  como "cria um mockup", "preview da tela", "ver variações antes de codar",
  "mockup do card/modal/dashboard", "como ficaria se...", "me mostra umas
  opções de layout", "quero ver antes de aplicar". Também decide a DIREÇÃO
  VISUAL vendo: lê o pedido em uma linha, gera variações que diferem de verdade
  (hierarquia, layout, tipografia, cor, densidade), roda um detector de visual
  genérico de IA e dá knobs para ajustar ao vivo — use também para "deixa menos
  cara de IA", "tá genérico, dá personalidade", "define a direção de design",
  "que vibe dar nisso", "deixa mais ousado/mais calmo". Dispare mesmo que o
  usuário não diga "mockup" explicitamente, sempre que a intenção for visualizar
  ou decidir um design antes de mexer no código de produção.
---

# Mockup Preview

Mostrar antes de implementar. Esta skill gera um mockup HTML rápido e
**descartável** de uma tela/componente, fiel ao design system do projeto, e o
serve com auto-reload para que o usuário veja e peça ajustes em tempo real. Só
quando o usuário aprova uma variação é que o código vira componente de verdade.

Ela também **decide a direção visual** — vendo, não por entrevista: lê o pedido,
gera variações que diferem de verdade, barra o visual genérico de IA com um
detector e deixa o usuário ajustar ao vivo com knobs.

## Por que existe

Iterar no código de produção para "ver como fica" é caro: rebuild, navegar até
a tela, desfazer se não gostou. Um mockup HTML isolado é instantâneo de editar e
não corre risco de sujar o repo. A chave é **fidelidade**: o mockup usa os
tokens reais (mesmas CSS vars / cores Tailwind / variáveis SCSS), então o que o
usuário vê é o que vai aparecer no app.

Princípio central: **o mockup é descartável e não precisa seguir as convenções
do projeto** (kebab-case e estilos inline são OK nele). Apenas o código aplicado
no passo final segue as regras e passa pelo sw-code-review. Não gaste esforço
"caprichando" no HTML do mockup — ele serve só para o olho.

## Regra: TODA pergunta é via AskUserQuestion

**Toda pergunta que você fizer ao usuário nesta skill usa a ferramenta `AskUserQuestion`
(menu clicável) — nunca texto solto pedindo pra ele digitar a opção, e NUNCA termine um
turno com uma pergunta em texto** (tipo "quer 3 ou 5 variações?" / "aplico no `X.vue`?").
Errar o palpite desperdiça o tempo do usuário; e uma pergunta em texto solto trava o
fluxo. Pergunta curta clicável é barata; refazer não é.

Vale para todos os pontos de decisão:

- **Escopo ambíguo** — qual componente/tela exatamente, quando o pedido é vago.
- **Sem print e estrutura incerta** — confirmar o layout base / pedir referência.
- **Tokens não detectados** — confirmar onde está o arquivo de tema.
- **Quantas variações e qual tema** (passo 3) — sempre menu.
- **Direção de design** — caminhos divergentes ("mais sóbrio" vs "mais ousado").
- **Escolher a variação vencedora** (passo 6b) — liste as variações como opções.
- **Auto-conferência do render** (passo 5b) — oferecer conferir por screenshot antes
  de entregar a URL (só quando o Playwright está disponível).
- **Aplicar no código** (passo 7) — SEMPRE confirmar antes de tocar em qualquer arquivo.

Para perguntas mais abertas (ex.: qual o componente), ofereça as opções mais prováveis e
conte com o campo **"Other"** do `AskUserQuestion` pra resposta livre. Dá pra juntar até 4
perguntas numa só chamada (ex.: variações + tema juntos) pra não perguntar duas vezes.

**Única exceção:** o feedback livre de iteração (passo 6) — quando o usuário olha o preview
e descreve o ajuste que quer ("aumenta o card", "tom mais sóbrio"). Isso é o usuário
dirigindo, não você perguntando; não force menu aí.

Não pergunte o que dá pra inferir com segurança do contexto/código (aí só siga e mencione a
suposição). O alvo é: zero retrabalho por palpite errado, e zero pergunta em texto solto.

## As skills irmãs (arsenal)

A direção visual é decidida **aqui** (passos 1b e 2b) — não há skill separada para isso. Depois que
o usuário aprova, ofereça a irmã (via `AskUserQuestion`), se instalada; senão, recomende
`/plugin install <skill>@ai-marketplace`:

- **Depois (aprovou) → `sw-frontend-component-kit`.** No passo 7/9, quando o usuário aprova uma
  variação, ofereça *"quer gerar o resto do kit de componentes nesse estilo?"* — a component-kit
  materializa o padrão como código de produção no projeto.

## Workflow

### 1. Escopo

Identifique o alvo: qual tela ou componente o usuário quer explorar. Se ele
anexou um print do estado atual, use-o como referência de estrutura/layout.
Localize o arquivo real do componente se já existir (`grep`/glob pelo nome) — vai
ser preciso no passo 7, e ajuda a replicar a estrutura atual no mockup.

### 1b. Leitura do pedido e direção

Antes de gerar, declare em **uma linha** como leu o pedido:

> *Lendo como: \<tipo de tela> para \<público>, em linguagem \<vibe>, no modo \<modo>.*

O **modo** diz o que é sucesso nesta tela, e vem da **tela pedida**, não do produto (a landing
de uma ferramenta é *convencer*; o painel dela é *operar*):

| Modo | Sucesso é | Onde |
|---|---|---|
| **convencer** | a pessoa decide e age | landing, preço, campanha |
| **operar** | a pessoa conclui a tarefa | painel, admin, formulário, editor |
| **ler** | a pessoa entende | documentação, artigo, ajuda |
| **experimentar** | a pessoa está dentro da obra | portfólio, galeria, vitrine |

Em *operar*, legibilidade, consistência e densidade útil vencem expressão — a marca mora nos
detalhes precisos. Em *convencer*, a ousadia é bem-vinda, gasta num lugar só.

**Uma pergunta, uma só, e só quando a leitura diverge de verdade** (ex.: "mais perto de um
painel sóbrio ou de um produto de consumo?"). Se dá para inferir do contexto, do print ou do
design system, **não pergunte**: declare a leitura e siga. A pergunta, quando houver, vai junto
com as do passo 3, no mesmo menu.

**Refinando uma tela que já existe?** Se o pedido não deixa claro o que manter, inclua no mesmo
menu do passo 3 a pergunta **"o que preservar?"** (a estrutura, a cópia, a paleta, a
tipografia...). Refinar preserva; redesenhar substitui — e o pior resultado é o meio-termo:
polir um visual que o usuário queria trocar.

**Modo didático** *(opcional)*: se o usuário pedir para entender as escolhas ("me explica",
"por que isso?", "modo didático"), anexe a cada decisão uma dica curta com o nome da técnica,
tirada de `references/tecnicas-de-design.md`:

> 💡 **\<Nome da técnica\>** — \<o que é, em linguagem simples\>. *Por que importa:* \<ganho\>.

Uma dica por decisão, não um parágrafo. Sem o pedido, vá direto ao ponto.

### 2. Extrair os design tokens (stack-agnostic)

A fidelidade depende disso. Detecte o sistema de design do projeto e monte um
bloco de tokens para injetar no mockup. Procure, em ordem:

- **CSS variables** — arquivo de estilo global (`src/style.css`, `app.css`,
  `:root {}`, blocos `[data-theme="dark"]`). Extraia cores, `--spacing-*`,
  `--radius-*`, `--font-*`, sombras. Pegue os dois temas (claro/escuro).
- **Tailwind** — `tailwind.config.{js,ts}` → `theme.extend` (colors, spacing,
  borderRadius, fontFamily). Traduza para CSS vars equivalentes no mockup.
- **SCSS/Sass** — arquivos `_variables.scss`/`_tokens.scss` com `$cor: ...`.
- **Fonte** — descubra a família real (link do Google Fonts no `index.html`,
  `font-family` no CSS, `fontFamily` no Tailwind). Ajuste o `<link>` e o
  `--font-sans` do harness se não for Inter.

**Projeto sem design system.** Os tokens que vêm no harness (slate, azul `#3b82f6`, Inter)
são **de exemplo** — um placeholder para o canvas funcionar, **nunca** um design. Usá-los como
estão é o visual "padrão de IA" mais reconhecível que existe, e o detector não tem como saber
que você não decidiu nada. Sem design system:

- As variações entram automaticamente no modo **nova direção** (passo 2b): cada uma parte de
  um referente concreto do mundo do assunto e traz **a própria paleta e o próprio par de
  fontes**, declarados na própria variação —
  `.variation.v2 { --bg-primary: …; --accent-primary: …; --font-sans: …; }` (e a versão
  escura em `[data-theme="dark"] .variation.v2 { … }`).
- Diga ao usuário, em uma linha, que o projeto não tem tokens e que a escolha da variação
  vai **definir** a direção.

Para detalhes e exemplos de extração por stack, leia
`references/token-extraction.md`.

### 2b. Trava de identidade e modo de variação

**Trava de identidade.** Com os tokens reais em mãos (passo 2) e, se houver, a tela atual,
escreva UMA frase com o que está na tela de fato: cor de superfície e acento (valores reais, não "quente"), o par de fontes
carregado, a topologia (empilhado / lado a lado / grade / assimétrico / sobreposto), o
tratamento de superfície (cantos, bordas, sombras, densidade de enfeite) e o tom da cópia. É a
trava: toda variação tem que parecer a mesma marca, lado a lado.

**Dois modos de variação:**
- **Mesma identidade** *(padrão, ~90% dos casos)*: varia a expressão dentro da trava. Fonte
  nova, cor nova ou estética nova são proibidas aqui.
- **Nova direção**: quando o usuário pede com todas as letras ("refaz do zero", "algo
  completamente diferente", "muda tudo") — ou quando o projeto não tem design system (passo 2),
  e aí não há identidade a preservar. Cada variação parte de um **referente concreto do
  mundo real** derivado do assunto ("um sistema de etiquetas de museu", nunca "limpo e
  minimalista"), e nenhuma pode caber no produto vizinho.

Na dúvida, **mesma identidade**: errar para ela custa "três variações parecidas" (corrigível);
errar para nova direção custa três variações fora da marca (perdidas).

**Sem design system não há trava** — o modo é **nova direção** (passo 2), e é a escolha da
variação que cria a identidade.

### 3. Perguntar quantas variações e qual tema

Antes de gerar, **dispare um `AskUserQuestion`** com as duas perguntas de abertura numa só
chamada (o tool aceita até 4 perguntas juntas):

1. **Quantas variações** o usuário quer ver — opções ex.: **1** / **3** / **5** (sugira 3).
   Com 1, não há etapa de escolha depois — é só refinar sob demanda.
2. **Tema** — opções: **Claro** / **Escuro** / **Ambos** (sugira **Ambos**). O canvas tem
   toggle de tema sempre disponível na barra: **Ambos** abre no claro já com o toggle pronto
   pra alternar (e, se houver auto-conferência, captura os dois temas); **Claro**/**Escuro**
   apenas fixam qual abre primeiro.

Menu clicável, nunca pergunta em texto. Isso evita gerar painéis/variações que o usuário não
quer e mantém o preview enxuto.

### 4. Montar o mockup (scaffold)

Copie `assets/harness.html` para o diretório de trabalho (passo 5) e preencha:

- O `<title>` com o nome do componente.
- O bloco TOKENS com os valores reais extraídos, nos **dois** blocos
  `[data-theme="light"]` e `[data-theme="dark"]`.
- O `<link>` da fonte, se diferente.
- Uma **`<section class="variation">` por variação** (passo 3), cada uma com
  `data-title` (rótulo da aba) e `data-desc` (a frase de trade-off). O harness as
  exibe como **abas no topo — uma tela por vez, sem empilhar**. Com uma variação só,
  a barra de abas some sozinha. Cada variação = ideia genuinamente distinta, não
  quase-iguais — ver **"Variações que diferem de verdade"** abaixo.
- **Não mexa na chrome do harness** — barra, painel lateral, knobs, comentários e detector
  já vêm prontos. O tema abre no escolhido no passo 3; o usuário alterna no próprio canvas.
  O que a tela oferece, para você saber citar ao usuário:
  - **Barra (uma linha):** abas das variações · **Comparar** (todas lado a lado, cada coluna
    é um container próprio, então `@container` vale por coluna) · larguras 📱 390 / tablet 768 /
    desktop 1280 / **largura total** (sem margem nem moldura, o design de borda a borda) · o
    switch **Livre** (arrasta a borda do canvas para qualquer largura e mostra os px) ·
    **Comentar** · tema · selo do detector · painel.
  - **Painel lateral:** no topo, fixos, a variação em foco (título, trade-off e **Seguir com
    esta**). Embaixo, abas com contador, uma por vez: **Ajustes** (knobs, com Restaurar),
    **Direção** (paleta e fontes lidas do CSS já renderizado, e dois campos, **Título** e
    **Corpo**, que aceitam **qualquer família do Google Fonts** e carregam na hora), **Notas**
    (os comentários) e **Detector** (clicar num achado rola o canvas até o elemento e o
    destaca). No comparar, clicar numa coluna a põe em foco e o painel mostra só ela.
  - **Atalhos:** ← → variação · C comparar · 1-4 largura · L livre · K comentar · T tema · P painel.
- **Fontes.** Os campos Título e Corpo pedem a família ao Google Fonts na hora: qualquer
  nome que exista lá funciona, sem configurar nada. **Título** troca `h1`-`h6` e o que tiver
  `data-titulo`; **Corpo** troca o resto e mantém os títulos. Marque com `data-titulo` o texto
  de display que não é heading (um número-herói, por exemplo), senão ele segue o corpo. Para
  screenshot: `?font=<corpo>&font-titulo=<título>` (espaço vira `+`).
- **Estado na URL.** Cada clique reescreve a URL. O live-reload recarrega a mesma URL, então o
  usuário não perde aba, largura, fontes nem knobs a cada edição sua, e a URL copiada abre
  exatamente o que ele está vendo.

**Responsivo de verdade (novo).** O canvas (`.hz-frame`) é um *container* CSS.
Escreva os breakpoints com `@container (max-width: 480px) { … }` (não `@media`) —
assim o toggle 📱/💻/🖥 da barra dispara os breakpoints **ao vivo**. Prefira layouts
intrínsecos (`auto-fit`/`minmax(min(100%, 380px), 1fr)`, `flex-wrap`, `clamp`) pra
refluir limpo. **Confira no mobile antes de entregar**, não só no desktop.

**Consistência com o app (princípio central).** O mockup deve refletir os mesmos
ícones, tokens, componentes e padrões que o app já usa — não versões parecidas.
Quando reaproveitar algo que já existe (um card, badge, ícone, bloco de
insights), espelhe o real, não improvise:

- **Ícones**: para libs SVG (Lucide, Heroicons, etc.), cole o SVG inline — não
  importe a lib — mas **extraia o SVG EXATO da lib instalada, não aproxime de
  memória** (paths/pontos mudam entre versões). Ex.: Lucide → leia
  `node_modules/lucide-<framework>/dist/esm/icons/<nome>.js` e copie `points`/`d`
  literalmente, com os atributos padrão (`stroke-width`, `linecap`/`linejoin`).
- **Blocos reaproveitados entre telas**: se um elemento já aparece em outra tela
  (ex.: o bloco de insights do feed), replique o mesmo desenho e rótulos na nova
  tela em vez de inventar um diferente.
- **Padrão de navegação**: descubra como o app realmente navega para a ação que
  está sendo desenhada (rota vs modal vs drawer) e reproduza isso. Se o "ver
  detalhe / ver todos" abre uma rota no app (ex.: `/x/:id/y`), simule uma
  **transição de página** no mockup — não um modal — e olhe a página real para
  copiar a estrutura (breadcrumb, header, listagem).
- **Múltiplos gatilhos → mesmo destino**: se há mais de um ponto de entrada para
  a mesma ação (um botão + um link "ver todos"), todos devem disparar o mesmo
  comportamento. Verifique essa consistência.
- **Sem redundância**: não repita a mesma informação várias vezes (ex.: o nome
  da entidade em breadcrumb + título + pill). Cabeçalho de detalhe = título +
  config + métricas, sem ecoar o nome.

**Qualidade do primeiro render (importante — o uso mostrou que isso falha por
padrão):**

- **Dimensione generoso desde o início.** Componente cortado/espremido frustra.
  Para cards num grid, prefira `minmax(~380-400px, 1fr)` (2-3 por linha, não 5
  apertados) e padding folgado. É mais fácil o usuário pedir "menor" do que
  perceber que estava grande demais.
- **Use dados realistas e estados variados**, não um único caso feliz. Renderize
  vários itens de exemplo cobrindo casos-limite: nome longo, estado inativo/erro,
  número baixo, texto que quebra. É isso que revela problemas de layout cedo.
- **Imagens reais quando ajudam.** Se o componente mostra foto (produto, avatar, capa,
  banner), não deixe só um retângulo cinza — puxe de um serviço **público** de placeholder,
  que deixa o mockup muito mais fiel:
  - **Fotos**: `https://picsum.photos/seed/<algo>/400/300` (Lorem Picsum — o `seed` mantém
    a mesma imagem entre reloads, evitando "piscar" diferente a cada refresh).
  - **Avatares**: `https://i.pravatar.cc/80?img=<n>` ou DiceBear.
  - **Caixa simples com rótulo**: `https://placehold.co/400x300`.
  Hotlink direto já funciona (online). Se precisar que rode **offline** ou que as imagens
  **apareçam nos screenshots da auto-conferência**, baixe pro dir do mockup
  (`curl -o img/p1.jpg "<url>"`) e referencie local. Nunca use imagens com direitos/privadas.
- **Fuja do visual genérico de IA.** Além do catálogo de `references/piso-e-recusas.md`,
  reconheça os três defaults que IA produz independente do assunto: (1) fundo creme + serifa
  de alto contraste + acento terracota; (2) fundo quase-preto + um único acento verde-ácido
  ou vermelhão; (3) layout "jornal", com fios finos, raio zero e colunas densas; (4) slate +
  azul-500 + Inter — os tokens de exemplo do próprio harness. São legítimos quando o brief pede — viram clichê quando aparecem sozinhos. Onde o eixo está livre, faça uma
  escolha específica para ESTE caso, vinda do mundo do assunto. O objetivo é parecer
  projetado, não gerado.
- **Dados críveis, não "Jane Doe".** Nome, empresa e e-mail do lugar e do setor; números
  bagunçados como os reais (`47,2%`, `R$ 1.847,30`), nunca `99,99%` ou `1234567`.

**Antes de escrever o markup, leia `references/piso-e-recusas.md`.** Ele traz o que
verificar no resultado (contraste, estados, medida de linha, superfícies do navegador,
cópia) e o que recusar por ser padrão de categoria (cards iguais como estrutura, texto em
gradiente, borda colorida lateral, emoji como ícone, dados "Jane Doe", travessão no texto de
interface...). O brief vence qualquer recusa; o eixo livre, não.

**Variações que diferem de verdade.** Cada variação escolhe **um eixo primário diferente**,
dentro da trava de identidade (passo 2b):

| Eixo | O que muda |
|---|---|
| **Hierarquia** | qual elemento comanda o olho |
| **Topologia** | empilhado, lado a lado, grade, assimétrico, sobreposto |
| **Sistema tipográfico** | lógica do par, razão da escala, caixa e peso — com as fontes disponíveis |
| **Estratégia de cor** | qual papel da paleta carrega a superfície: contida, comprometida, paleta inteira, encharcada |
| **Densidade** | mínima, confortável, densa |
| **Decomposição** | juntar, separar, revelar aos poucos |

Uma variação por eixo: com 3, três eixos diferentes — a mesma marca vista de três ângulos;
com 5, cinco dos seis. Três variações "mais compactas" é fracasso. Com **1** variação não há
comparação: escolha o eixo que o pedido mais pede, e o resto é refino (passo 6).

**Teste do olhar semicerrado**, antes de servir: (1) compare cada variação com a trava —
paleta, voz tipográfica ou retórica que vazou é variação que atravessou para "nova direção"
sem querer: refaça; (2) confirme três eixos diferentes; (3) as três frases de `data-desc`,
lado a lado, não podem rimar; (4) a pergunta mais barata de todas: **"eu produziria isto para
qualquer pedido parecido?"** — se sim, é o default, não uma escolha: refaça a parte que é
default. No modo *nova direção*, dê a cada variação um rótulo de família próprio — rótulos
intercambiáveis significam refazer.

**Knobs (ajuste ao vivo).** Cada variação pode declarar de 0 a 4 knobs em `data-knobs`, e o
harness desenha os controles na barra — o usuário ajusta **sem gerar de novo**. Exponha o eixo
que você escolheu: quando o usuário pode razoavelmente dizer "um pouco mais apertado" ou "um
toque a mais de acento" sem querer outra geração, isso é um knob.

| Peso visual da variação | Knobs |
|---|---|
| folha (botão, ícone, título solto) | 0 |
| composição pequena (card simples, campo com rótulo) | 0 a 1 |
| composição média (seção, navegação) | cerca de 2 |
| composição grande (hero, tela inteira) | 2 a 4 |

Três tipos: `range` vira a variável `--k-<id>` (escreva `var(--k-acento, .5)`), `steps` vira o
atributo `data-k-<id>` (escreva `.variation[data-k-densidade="compacta"] .x {...}`) e `toggle`
vira `--k-<id>` (0 ou 1) mais o atributo quando ligado. O formato exato está no comentário do
harness. Cada variação guarda os próprios valores ao trocar de aba. `?v=2&k=acento:0.8` abre
direto num estado (útil no passo 5b) — o `?k=` vale para a variação **ativa**, então combine com
`?v=`. Valor fora do mínimo/máximo é limitado, e opção fora da lista volta ao padrão.

**Interatividade (adicione quando os elementos têm comportamento):**

Mockup não precisa ser estático. Quando o componente tem ações (toggle/switch,
delete, tabs, expandir, hover com estado), adicione JS vanilla pra que o usuário
**sinta o fluxo real** — ex.: o toggle realmente alterna o estado e atualiza os
visuais dependentes; o delete remove o card com fade. Isso torna a decisão muito
mais informada do que olhar algo parado. Mantenha o JS simples e inline no
mockup (é descartável).

Escreva o JS sempre com `querySelectorAll` + `closest()` (cada item cuida de si),
nunca `id` ou `querySelector` singular. Há **múltiplas instâncias**: vários cards de
exemplo, e o seu JS roda sobre todas as variações (inclusive as abas inativas no DOM) —
um seletor singular ligaria só uma e o resto pareceria quebrado. (O harness já usa
**canvas único com toggle de tema**, então não há mais painéis light/dark duplicados.)

**Animações (quando pedidas ou quando agregam):**

Toda animação no mockup deve vir embrulhada num guard de acessibilidade:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
```

Prefira movimento sutil e com propósito (entrada em cascata, transição de estado,
indicador "ao vivo") a animação chamativa contínua.

> **Animação de entrada × abas:** todas as variações moram no DOM e as abas alternam com
> `is-active`. Uma animação de **entrada** roda no primeiro render e pode **não repetir** ao
> trocar de aba — se o usuário quer rever a entrada, recarregue com `?v=<n>` (ou avise que a
> entrada é one-shot). Não confie na troca de aba pra "re-tocar" a animação.

### 4b. Rodar o detector (antes de servir)

```bash
python3 <skill-dir>/scripts/detectar.py /tmp/mockup-preview/<slug>/index.html
```

Varredura **determinística** (sem LLM, sem rede) atrás dos tells de IA, com linha, trecho e
dica. Saída **0** = sem falha (avisos aparecem, mas não bloqueiam); **2** = há falha.

- **Falha**: conserte antes de servir. Não entregue um mockup com falha do detector.
- **Aviso**: decida olhando o brief (três colunas iguais podem ser a resposta certa para uma
  tabela de preços).
- **Exceção que o brief justifica** (um mundo neobrutalista pede sombra dura) é declarada no
  próprio HTML, e o detector a relata como **ignorada**, nunca a cala:
  `<!-- detector: ignorar sombra-dura -->`. Ignorar para ficar verde é o mesmo que não rodar.

Ele só olha o **design**: a marcação dentro de cada elemento `.variation` (incluindo
`placeholder`, `aria-label` e as classes utilitárias, como as do Tailwind) e o CSS fora da
casca do harness — tokens incluídos. A casca nunca gera achado. Um knob declarado que nenhum
CSS usa também aparece (`knob-sem-efeito`). Rode de novo depois de mudanças grandes no passo 6.

A exceção vale para o arquivo inteiro; a justificativa vai depois da lista, entre parênteses:
`<!-- detector: ignorar sombra-dura (mundo neobrutalista) -->`. Os achados suprimidos continuam
listados, com linha, sob **IGNORADAS**. Saída **1** = o detector não conseguiu rodar (arquivo
ilegível, ou a declaração cita uma regra que não existe).

### 5. Servir com live-reload

Trabalhe num diretório temporário **fora do repo** para nunca commitar mockups:
`/tmp/mockup-preview/<slug-do-componente>/`. Salve o HTML como `index.html` ali.

Suba o servidor self-contained (Python stdlib, sem dependências, com SSE) em
background:

```bash
python3 <skill-dir>/scripts/serve.py /tmp/mockup-preview/<slug>
```

O script **escolhe sozinho uma porta livre** (a partir de 8765) e imprime duas
linhas legíveis por máquina, além das humanas:

```
MOCKUP_PREVIEW_URL=http://localhost:<porta>/
MOCKUP_PREVIEW_PID=<pid>
```

Leia a porta real dessa saída (não assuma 8765 — pode haver outro preview
rodando) e **guarde o PID** para encerrar de forma confiável no passo 9 (em vez
de `pkill -f`, que é frágil). Passe a URL ao usuário.

O servidor também responde o detector, os comentários e a escolha da tela (passos 6 e 6b).
Aberto direto como arquivo, sem o `serve.py`, o preview funciona, mas **Comentar** e
**Seguir com esta** ficam desligados. Se ele acessa de outra
máquina, ofereça `http://<ip-ou-host>:<porta>/` (escuta em 0.0.0.0).

### 5b. Auto-conferência do render (opcional — pergunte via AskUserQuestion)

Antes de entregar a URL, ofereça **conferir o render você mesma** — assim o primeiro
preview que o usuário vê já vem decente, sem depender só do olho dele.

**Com o Playwright MCP** use o fluxo abaixo. **Sem ele**, se houver Chrome ou Chromium na
máquina, a conferência é a mesma pela linha de comando — `?limpo=1` esconde a casca, então o
screenshot mostra só o design:

```bash
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --window-size=1280,900 --virtual-time-budget=1500 \
  --screenshot=/tmp/mockup-preview/<slug>/desk.png "http://localhost:<porta>/?limpo=1"
# mobile: --window-size=390,844 e "?limpo=1&vw=mobile"; escuro: "&theme=dark"; variação: "&v=2"
```

Sem nenhum dos dois, **pule este passo em silêncio** e entregue a URL como no passo 5.

**Pergunte via `AskUserQuestion`** (uma chamada, as duas perguntas juntas):
1. "Confiro o render por screenshot antes de te entregar?" → **Sim** / **Não, só a URL**.
2. Se Sim, "Quais telas?" → **Mobile** / **Desktop** / **Ambos** / **Ambos + tema escuro**.
   Deixe o usuário escolher a cobertura — não fixe um número de shots.

**Captura rápida (é aqui que o Playwright fica lento se feito errado):**

- **Sem cliques** — navegue direto ao estado pela **URL**: `…/?vw=mobile`,
  `…/?vw=desktop&theme=dark`, `…/?v=2`, `…/?comparar=1&vw=mobile`, `…/?vw=livre&w=834`,
  `…/?font=DM+Sans&font-titulo=Fraunces`. Cada shot = 1 navigate + 1 screenshot, zero cliques
  (dá pra comparar fontes tirando shots com `?font=` diferentes). Some `&limpo=1` para
  capturar só o design, sem barra nem painel.
- **Reuse o browser** — uma só sessão para todos os shots (o custo é o 1º launch; os
  seguintes são rápidos). Não feche/reabra entre telas.
- **Espere pouco** — `waitUntil: domcontentloaded` (conteúdo é local e a fonte é `swap`,
  não precisa de `networkidle`).
- **Screenshot do canvas** (elemento `.hz-frame`), não `fullPage`; `jpeg` codifica mais
  rápido que `png`.
- **Sem travar** — rode a conferência **sem interrupção**: deixe as ferramentas de leitura
  do Playwright (navigate/screenshot/snapshot/close) **pré-autorizadas** nas configs
  (`permissions.allow` em `~/.claude/settings.json`), senão cada ação pede permissão e
  trava o fluxo. Não peça confirmação a cada passo da captura.

Depois de capturar:

3. **Olhe os screenshots** e cace o óbvio: conteúdo estourando/cortado, render vazio,
   ícone que não apareceu, grid que não colapsou no mobile (`@container`), contraste
   ruim, sobreposição. *(O `.hz-frame` tem `overflow:hidden` pros cantos arredondados —
   conteúdo que vaza aparece **cortado na borda do frame**; é justamente esse corte que você
   quer flagrar. Se suspeitar de estouro escondido, confira o conteúdo sem o clip.)*
4. **Conserte no `index.html`** o que estiver claramente quebrado (o live-reload aplica)
   e recapture só a tela afetada pra confirmar.
5. **Feche o browser** (`browser_close`) — a conferência acabou; não deixe sessão aberta.
6. Entregue a URL mencionando em uma linha o que conferiu.

Mantenha leve: rode na **primeira renderização** (e após mudanças grandes), não a cada
ajuste fino — o ciclo rápido com o olho do usuário (passo 6) continua sendo o principal.
Complemento, não substituto. Limpe os screenshots temporários ao terminar.

**Rodada única, com teto.** Capture desktop e mobile juntos, conserte **tudo** o que apareceu de
uma vez e confirme com **no máximo mais uma** rodada — depois pare. Autoajuste em ciclo aberto
gasta o tempo do usuário fazendo pior o que o olho dele faz melhor no passo 6.

### 6. Iterar

O usuário olha no navegador e pede ajustes. Para cada pedido, **edite o
`index.html`** — o servidor detecta a mudança e o navegador recarrega sozinho
(o usuário não precisa fazer nada). Pode misturar ideias ("a 2 com o rodapé da
1") — refine no mesmo arquivo.

**Leia os comentários da tela a cada turno.** O usuário pode apontar o ajuste direto no
elemento (botão **Comentar**, ou tecla K). Antes de responder, leia
`/tmp/mockup-preview/<slug>/.mockup/comentarios.json`: cada item traz `variacao` (1-based),
`titulo`, `seletor` (caminho do elemento dentro da `<section>`), `trecho` (o texto dele),
`texto` (o pedido), `vw` e `theme`. Aplique cada um no `index.html` e diga, em uma linha por
comentário, o que mudou. Ao terminar um, apague-o com
`curl -s -X POST -H 'Content-Type: application/json' localhost:<porta>/__comentarios/apagar -d '{"id":<id>}'`
(ou deixe o usuário clicar em Resolver). O arquivo fica fora do live-reload: gravar
comentário não recarrega a página.

**Knobs antes de regenerar.** Se o pedido é "um pouco mais..." num eixo que a variação já
expõe, aponte o knob em vez de gerar de novo.

**Vocabulário de refino.** Depois do primeiro render, quando o usuário não sabe para onde ir
("melhora", "tá quase"), ofereça via `AskUserQuestion` a direção — e cada escolha gera novas
variações **na dimensão dela**, cada uma mexendo numa faceta diferente:

| Direção | As variações mexem em... |
|---|---|
| **mais ousado** | escala · saturação · mudança estrutural (uma em cada) |
| **mais calmo** | cor · ornamento · espaçamento |
| **enxugar** | ruído visual · conteúdo redundante · estrutura aninhada |
| **polir** | ritmo · hierarquia · microdetalhe |
| **tipografia** | par de fontes diferente E razão de escala diferente em cada |
| **cor** | família de matiz diferente em cada, variando croma e contraste |
| **layout** | arranjo estrutural diferente, não ajuste de espaçamento |
| **movimento** | vocabulário diferente: cascata, recorte, escala e foco, transformação |
| **adaptar** | contexto diferente: mobile primeiro, tablet, desktop |

O pedido que traz intenção sem vocabulário ("com cara de banco", "mais premium") vale como
direção livre, com as palavras do usuário. Rode o detector (passo 4b) de novo antes de servir.

### 6b. Convergir numa variação (funil)

Quando havia **mais de uma variação**, confira primeiro
`/tmp/mockup-preview/<slug>/.mockup/escolha.json`: se o usuário clicou **Seguir com esta** na
tela, ali estão a `variacao` (1-based), o `titulo`, os valores dos `knobs` naquele momento, a
largura, o tema e as fontes que ele testou. Com a escolha gravada, **confirme em uma linha** e
siga (os knobs viram os valores fixos da vencedora; as fontes testadas, se houver, viram
proposta para os tokens). Sem escolha gravada, **dispare um `AskUserQuestion`** ("Qual variação
seguimos?") listando as variações como opções (+ "Other" pra misturar, ex.: "a 2 com o
rodapé da 1"). Escolhida uma, **descarte as demais** e reescreva o canvas só com a vencedora
— agora o foco é aprofundá-la.
Ajuda a renderizá-la com vários itens de exemplo (estados variados) pra refinar
no contexto real. Iterar com 3 variações vivas depois da escolha só dispersa.
Com **uma só variação** desde o início, não há esse passo — vá refinando sob
demanda.

### 6c. Registrar a direção (quando ela é nova)

Quando o projeto **não tinha** design system, ou o usuário pediu **nova direção**, a variação
escolhida acabou de **definir** a identidade. Ofereça via `AskUserQuestion` registrá-la no
projeto — **Registrar no `DESIGN.md`** / **Só o documento, sem aplicar código** / **Não
precisa** — e só escreva com o "sim" (é arquivo do projeto, não do `/tmp`).

O `DESIGN.md` é curto e concreto:

- **Paleta** — 4 a 6 cores nomeadas, em hex, com o papel de cada (fundo, superfície, texto,
  texto secundário, acento), nos dois temas.
- **Tipografia** — display + corpo (+ utilitária, se houver), com escala e pesos.
- **Densidade e ritmo** — a escala de espaçamento e o eixo que a variação escolheu.
- **Movimento** — nível (nenhum, sutil, orquestrado) e onde, sempre com `prefers-reduced-motion`.
- **Profundidade** — o tratamento de superfície (sombra, borda, raio), um ou dois, com propósito.
- **Assinatura** — a UMA coisa memorável desta direção.
- **Evitar** — o que o detector barrou e o que o usuário recusou nas outras variações.

É esse arquivo que a `sw-frontend-component-kit` lê para gerar o kit na mesma direção — e,
numa interface grande (um painel inteiro), é ele que torna a direção **regra** para todas as
telas, em vez de um capricho por tela.

### 7. Aplicar no componente real

**Confirme antes de tocar no projeto.** Aprovar a variação no preview NÃO é
autorização para editar arquivos — o usuário pode estar só explorando ou testando
ideias. Antes de qualquer edição, pergunte explicitamente via `AskUserQuestion`
(ex.: "Aplico no `X.vue` agora, ou paramos no preview?"). Só prossiga com um sim
claro. Se o contexto for exploração/teste, encerre no passo 9 sem aplicar.

Com a confirmação dada, converta a variação em código de verdade — **aqui as
regras do projeto valem integralmente**:

- Leia `.claude/rules/` (se existir) e siga: nomenclatura de classes, uso de CSS
  vars, mobile-first, framework (Composition API no Vue, etc.).
- **Tokens novos vão primeiro para o arquivo de tema** (ex.: nova var no
  `style.css`, nos dois temas claro/escuro), e o componente referencia a var —
  nunca cor/valor hardcoded, nunca CSS condicional por tema dentro do componente.
- **Porte as interações com fidelidade ao framework**, não copie o JS vanilla do
  mockup. Conecte o comportamento ao que já existe (ex.: um toggle vira o
  handler/estado real do componente — no Vue um método/`ref`, no React um
  `state`/handler — e não um `addEventListener` solto). Eventos pela via idiomática
  do framework (emits/props/handlers).
- **Porte animações como classes CSS** (não inline), reusando/criando vars de
  tema, e **mantenha o guard `prefers-reduced-motion`** no código final.
- **Porte o responsivo**: os `@container` do mockup viram a abordagem do projeto
  (`@media` ou `@container`, conforme a convenção) — mantendo os mesmos breakpoints.
- Aplique no arquivo real do componente localizado no passo 1.
- Cuide das pontas: se remover algo, cheque referências órfãs antes.

### 8. Verificar fidelidade (não pule)

O risco nº1 ao aplicar é o resultado **não bater com o mockup aprovado** — em
geral porque se *retrofita* o mockup na estrutura antiga do componente em vez de
**reproduzir a estrutura do mockup**. Reproduza o mockup: se ele trocou facets
rotulados por chips simples, um link por um botão, ou adicionou uma toolbar de
busca/filtro, o componente real precisa refletir exatamente isso — não manter o
layout velho com um remendo.

Depois de aplicar, **compare lado a lado**: rode o app (ou reabra o preview) e
confira elemento a elemento contra o mockup — estrutura, ordem, chips, botões,
labels, seções e estados (carrosséis, abas, botões de ação, badges, overflow
"+N", estados vazios). Se algo divergir, corrija até bater. Só então:

- Rode o build do projeto e, se disponível, o sw-code-review, pra validar padrão e
  que nada quebrou. Não force — ofereça.

### 9. Encerrar

Ao terminar, pare o servidor de preview matando o PID capturado no passo 5
(`kill <MOCKUP_PREVIEW_PID>`). Os arquivos em `/tmp` podem ficar — somem no
reboot e estão fora do repo (inclusive `.mockup/`, com os comentários e a escolha).

## Checklist de fidelidade (confira nos momentos-chave)

Estas são as regras mais fáceis de atropelar na execução. Confira:

**Ao montar/servir o mockup:**
- [ ] **Tokens REAIS** do projeto (cores/espaçamento/fonte extraídos), não aproximados de memória?
- [ ] **Ícones** colados do `node_modules` (SVG exato da versão instalada), não desenhados de cabeça?
- [ ] **Declarou a leitura do pedido** (uma linha, com o modo) antes de gerar?
- [ ] **Sem design system:** trocou os tokens de exemplo do harness por uma paleta e um par de
      fontes por variação (nova direção)? E ofereceu registrar a escolhida no `DESIGN.md`?
- [ ] **Variações em abas** (`data-title`/`data-desc`, uma por vez), não empilhadas verticalmente?
- [ ] **Três eixos primários diferentes**, dentro da trava de identidade (a não ser que o
      usuário tenha pedido nova direção)?
- [ ] **Detector rodado** (passo 4b) e sem falha? Exceção declarada no HTML, não calada?
- [ ] **Knobs** onde o usuário poderia dizer "um pouco mais..." (composição média ou grande)?
- [ ] **Responsivo** com `@container` e conferido no **mobile** (toggle 📱), não só desktop?
- [ ] **Porta e PID** lidos da saída do `serve.py` (não assumiu 8765)?
- [ ] **Leu `.mockup/comentarios.json` e `.mockup/escolha.json`** antes de responder a cada
      turno de iteração?
- [ ] **Ofereceu a auto-conferência por screenshot** (passo 5b) quando o Playwright estava disponível?

**Antes de aplicar no código (passo 7):**
- [ ] **Confirmou via `AskUserQuestion`** que é pra aplicar (aprovar no preview ≠ autorização)?
- [ ] Vai **reproduzir a ESTRUTURA do mockup** no componente real (não retrofitar o mockup no layout velho)?
- [ ] Tokens novos vão pro **arquivo de tema** primeiro; interações/animações portadas no idioma do framework (não o JS vanilla cru)?

**Em qualquer pergunta:** foi via `AskUserQuestion` (menu), sem terminar turno em texto solto?

## Notas

- **Referências.** A leitura do pedido, os eixos de variação, o piso de qualidade, os knobs e
  o vocabulário de refino são adaptados, com texto próprio, do
  [Impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0) e da
  [Taste Skill](https://github.com/Leonxlnx/taste-skill) (MIT).

- Mantenha o ciclo leve: o valor está na velocidade de ver→ajustar→ver. Não
  burocratize o mockup.
- Se o usuário só quer explorar ideias e não aplicar, pare no passo 6 — o passo
  7 é opcional e guiado pela decisão dele.
- **Em sessões longas de iteração**, vá registrando as decisões de design e os
  aprendizados num arquivo de notas (ex.: em `specs/`), para depois revisar e
  decidir o que vira regra permanente da skill ou requisito do projeto (ex.:
  novos campos de API que o layout novo passou a exigir).
