# Glossário de técnicas de design (para não-designers)

Lido pela `sw-design-studio` no **modo didático**. Cada técnica: o **nome** (pra você
reconhecer e reaplicar), o que é **em linguagem simples**, e **por que importa**. Use o nome
exato na dica do terminal, no formato:

> 💡 **\<Nome\>** — \<explicação simples\>. *Por que importa:* \<ganho prático\>.

---

## Composição & layout

- **Hierarquia visual** — deixar claro o que olhar primeiro (um "herói" grande, o resto quieto).
  *Por que importa:* o olho se perde quando tudo tem o mesmo peso; com hierarquia, a tela "se lê sozinha".
- **Respiro / whitespace** — espaço vazio de propósito ao redor das coisas.
  *Por que importa:* vazio não é desperdício — é o que faz parecer caro e respirável; aperto parece barato.
- **Escala modular** — tamanhos (de texto e espaço) seguem uma régua fixa (ex.: 12·14·16·20·28),
  não números aleatórios. *Por que importa:* dá ritmo e consistência; some o ar de "feito no olho".
- **Grid / alinhamento** — tudo apoiado numa grade invisível (ex.: base de 4px ou 8px).
  *Por que importa:* alinhamento é o que o olho lê como "caprichado", mesmo sem saber por quê.
- **Lei de proximidade (Gestalt)** — coisas relacionadas ficam perto; coisas diferentes, separadas.
  *Por que importa:* o usuário entende grupos sem precisar de caixa/linha em volta de tudo.
- **Densidade (minimal ↔ maximal)** — quão "cheia" é a tela.
  *Por que importa:* dashboard pede densidade controlada; landing pede respiro. Combine ao conteúdo.

## Cor

- **Regra 60-30-10** — ~60% cor dominante (fundo), 30% secundária, 10% acento.
  *Por que importa:* evita a "festa de cores"; dá equilíbrio e destaca o que importa.
- **Acento com significado** — uma cor forte reservada pra ação/destaque (ou pra dado, tipo verde=positivo).
  *Por que importa:* cor que decora vira ruído; cor que significa vira informação.
- **Contraste AA** — texto/fundo com diferença suficiente pra ler (≈ 4.5:1 em texto).
  *Por que importa:* design lindo que não dá pra ler falhou; e é acessibilidade de verdade.

## Tipografia

- **Contraste tipográfico** — um tipo "display" com caráter + um "body" neutro e legível.
  *Por que importa:* a personalidade mora no tipo; um tipo só em tudo fica sem graça (cara de template).
- **Restrição (usar o display pouco)** — a fonte marcante só em títulos/números, não no texto corrido.
  *Por que importa:* personalidade demais cansa; pouca, no lugar certo, marca.
- **Tabular-nums / optical sizing** — números de largura fixa (alinham em coluna) e fonte que ajusta no tamanho.
  *Por que importa:* faz tabelas/preços parecerem "financeiro sério", alinhados como num extrato.

## Profundidade & efeitos

- **Elevação por tom (vs sombra)** — separar cards por uma diferença de cor de fundo, não por sombra borrada.
  *Por que importa:* sombra igual em tudo é o tell nº1 de design de IA; tom é mais limpo.
- **Sombra direcional** — uma sombra com direção/luz definida, só no que está "à frente".
  *Por que importa:* sombra com propósito dá profundidade real; sombra uniforme em tudo achata.
- **Menos efeitos, com propósito** — escolher 1–2 (sombra OU glass OU grain), não empilhar todos.
  *Por que importa:* efeito demais polui e parece gerado; restrição parece intencional.

## Movimento

- **Motion deliberado** — um momento orquestrado (entrada, revelação) > efeitos espalhados.
  *Por que importa:* animação contínua/chamativa grita "IA"; um gesto certo encanta.
- **Easing & stagger** — curva de aceleração natural + pequeno atraso entre itens em sequência.
  *Por que importa:* movimento linear parece robótico; com easing parece físico e caro.
- **prefers-reduced-motion** — desligar animações pra quem pediu (acessibilidade do sistema).
  *Por que importa:* movimento pode causar enjoo/tontura; respeitar isso é robustez, não opcional.

## Princípios que blindam contra o "cara de IA"

- **Hero é uma tese** — abrir com a coisa mais característica do assunto, não com o template genérico.
  *Por que importa:* o começo define a primeira impressão; genérico no topo = genérico no todo.
- **Signature element** — a UMA coisa memorável que carrega a identidade.
  *Por que importa:* é o que faz lembrar; sem ela, tudo vira "mais um".
- **Gaste a ousadia num lugar só** — uma coisa marcante, o resto disciplinado.
  *Por que importa:* ousadia espalhada vira poluição; concentrada, vira estilo.
- **Tire um acessório (restrição)** — antes de entregar, remova uma decoração que não serve.
  *Por que importa:* o que sobra fica mais forte; excesso dilui.
- **Estrutura é informação** — numeração/eyebrows/divisores só se significam algo real.
  *Por que importa:* decoração que finge ser informação confunde e parece template.

## Conteúdo (copy é design)

- **Voz ativa / nomear pelo que a pessoa controla** — "Salvar alterações", não "Enviar"; "Notificações", não "Webhook config".
  *Por que importa:* a palavra certa é metade da usabilidade; jargão afasta.
- **Affordance** — o elemento parece o que faz (botão parece clicável; link parece link).
  *Por que importa:* o usuário age sem pensar quando a aparência promete o comportamento.
- **Foco visível** — anel claro no elemento focado pelo teclado.
  *Por que importa:* quem navega por teclado precisa ver onde está; sumir com isso quebra o uso.
