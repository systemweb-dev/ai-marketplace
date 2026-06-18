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
  opções de layout", "quero ver antes de aplicar". Dispare mesmo que o usuário
  não diga "mockup" explicitamente, sempre que a intenção for visualizar um
  design antes de mexer no código de produção.
---

# Mockup Preview

Mostrar antes de implementar. Esta skill gera um mockup HTML rápido e
**descartável** de uma tela/componente, fiel ao design system do projeto, e o
serve com auto-reload para que o usuário veja e peça ajustes em tempo real. Só
quando o usuário aprova uma variação é que o código vira componente de verdade.

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
- **Aplicar no código** (passo 7) — SEMPRE confirmar antes de tocar em qualquer arquivo.

Para perguntas mais abertas (ex.: qual o componente), ofereça as opções mais prováveis e
conte com o campo **"Other"** do `AskUserQuestion` pra resposta livre. Dá pra juntar até 4
perguntas numa só chamada (ex.: variações + tema juntos) pra não perguntar duas vezes.

**Única exceção:** o feedback livre de iteração (passo 6) — quando o usuário olha o preview
e descreve o ajuste que quer ("aumenta o card", "tom mais sóbrio"). Isso é o usuário
dirigindo, não você perguntando; não force menu aí.

Não pergunte o que dá pra inferir com segurança do contexto/código (aí só siga e mencione a
suposição). O alvo é: zero retrabalho por palpite errado, e zero pergunta em texto solto.

## Workflow

### 1. Escopo

Identifique o alvo: qual tela ou componente o usuário quer explorar. Se ele
anexou um print do estado atual, use-o como referência de estrutura/layout.
Localize o arquivo real do componente se já existir (`grep`/glob pelo nome) — vai
ser preciso no passo 7, e ajuda a replicar a estrutura atual no mockup.

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

Se nada for encontrado, use defaults neutros e avise o usuário que os tokens não
foram detectados (o mockup fica menos fiel, mas funciona).

Para detalhes e exemplos de extração por stack, leia
`references/token-extraction.md`.

### 3. Perguntar quantas variações e qual tema

Antes de gerar, **dispare um `AskUserQuestion`** com as duas perguntas de abertura numa só
chamada (o tool aceita até 4 perguntas juntas):

1. **Quantas variações** o usuário quer ver — opções ex.: **1** / **3** / **5** (sugira 3).
   Com 1, não há etapa de escolha depois — é só refinar sob demanda.
2. Em qual(is) **tema(s)** — opções: **Claro** / **Escuro** / **Ambos**.

Menu clicável, nunca pergunta em texto. Isso evita gerar painéis/variações que o usuário não
quer e mantém o preview enxuto.

### 4. Montar o mockup (scaffold)

Copie `assets/harness.html` para o diretório de trabalho (passo 5) e preencha:

- O `<title>` com o nome do componente.
- O bloco TOKENS com os valores reais extraídos (light em `.panel--light`, dark
  em `.panel--dark`).
- O `<link>` da fonte, se diferente.
- O número de **variações** definido no passo 3 (uma `<section>` cada). Cada
  variação deve ser uma ideia genuinamente distinta — não versões quase iguais.
  Dê a cada uma título curto e uma frase de trade-off.
- Renderize no(s) tema(s) escolhido(s). Para um tema só, remova o painel não
  usado e adicione `panels--single` ao `.panels`.

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
- **Fuja do visual genérico de IA.** Evite por padrão os clichês: "pill soup"
  cinza, toggle iOS padrão, sombra suave uniforme em tudo, cantos arredondados
  idênticos por toda parte. Busque personalidade — hierarquia tipográfica forte,
  uso intencional de cor/acento, escala, detalhes distintos (barra de acento,
  número-herói, controle segmentado, monospace onde fizer sentido). O objetivo é
  parecer projetado, não gerado.

**Interatividade (adicione quando os elementos têm comportamento):**

Mockup não precisa ser estático. Quando o componente tem ações (toggle/switch,
delete, tabs, expandir, hover com estado), adicione JS vanilla pra que o usuário
**sinta o fluxo real** — ex.: o toggle realmente alterna o estado e atualiza os
visuais dependentes; o delete remove o card com fade. Isso torna a decisão muito
mais informada do que olhar algo parado. Mantenha o JS simples e inline no
mockup (é descartável).

Escreva o JS sempre com `querySelectorAll` + `closest()` (cada item cuida de si),
nunca `id` ou `querySelector` singular. Isso importa porque há **múltiplas
instâncias**: vários cards de exemplo e, no modo "ambos os temas", o componente
aparece duplicado nos painéis light e dark — um seletor singular ligaria só um e
o resto pareceria quebrado.

Alternativa para "ambos os temas" com interatividade: em vez de dois painéis
duplicados, considere um **canvas único com um botão que alterna o tema da página
ao vivo** (toggle de `data-theme`). Evita markup duplicado, roda o JS num só
lugar e deixa comparar o mesmo elemento trocando de tema. Use quando a
interatividade for central; para mockups estáticos, os painéis lado a lado
continuam mais diretos.

**Animações (quando pedidas ou quando agregam):**

Toda animação no mockup deve vir embrulhada num guard de acessibilidade:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
```

Prefira movimento sutil e com propósito (entrada em cascata, transição de estado,
indicador "ao vivo") a animação chamativa contínua.

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
de `pkill -f`, que é frágil). Passe a URL ao usuário. Se ele acessa de outra
máquina, ofereça `http://<ip-ou-host>:<porta>/` (escuta em 0.0.0.0).

### 6. Iterar

O usuário olha no navegador e pede ajustes. Para cada pedido, **edite o
`index.html`** — o servidor detecta a mudança e o navegador recarrega sozinho
(o usuário não precisa fazer nada). Pode misturar ideias ("a 2 com o rodapé da
1") — refine no mesmo arquivo.

### 6b. Convergir numa variação (funil)

Quando havia **mais de uma variação**, **dispare um `AskUserQuestion`** ("Qual variação
seguimos?") listando as variações como opções (+ "Other" pra misturar, ex.: "a 2 com o
rodapé da 1"). Escolhida uma, **descarte as demais** e reescreva o canvas só com a vencedora
— agora o foco é aprofundá-la.
Ajuda a renderizá-la com vários itens de exemplo (estados variados) pra refinar
no contexto real. Iterar com 3 variações vivas depois da escolha só dispersa.
Com **uma só variação** desde o início, não há esse passo — vá refinando sob
demanda.

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
reboot e estão fora do repo.

## Checklist de fidelidade (confira nos momentos-chave)

Estas são as regras mais fáceis de atropelar na execução. Confira:

**Ao montar/servir o mockup:**
- [ ] **Tokens REAIS** do projeto (cores/espaçamento/fonte extraídos), não aproximados de memória?
- [ ] **Ícones** colados do `node_modules` (SVG exato da versão instalada), não desenhados de cabeça?
- [ ] **Porta e PID** lidos da saída do `serve.py` (não assumiu 8765)?

**Antes de aplicar no código (passo 7):**
- [ ] **Confirmou via `AskUserQuestion`** que é pra aplicar (aprovar no preview ≠ autorização)?
- [ ] Vai **reproduzir a ESTRUTURA do mockup** no componente real (não retrofitar o mockup no layout velho)?
- [ ] Tokens novos vão pro **arquivo de tema** primeiro; interações/animações portadas no idioma do framework (não o JS vanilla cru)?

**Em qualquer pergunta:** foi via `AskUserQuestion` (menu), sem terminar turno em texto solto?

## Notas

- Mantenha o ciclo leve: o valor está na velocidade de ver→ajustar→ver. Não
  burocratize o mockup.
- Se o usuário só quer explorar ideias e não aplicar, pare no passo 6 — o passo
  7 é opcional e guiado pela decisão dele.
- **Em sessões longas de iteração**, vá registrando as decisões de design e os
  aprendizados num arquivo de notas (ex.: em `specs/`), para depois revisar e
  decidir o que vira regra permanente da skill ou requisito do projeto (ex.:
  novos campos de API que o layout novo passou a exigir).
