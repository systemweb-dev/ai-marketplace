# Estéticas de referência (perfis de tokens prontos)

Referente **não é fantasia**: cada perfil é um ponto de partida para variações no modo
**nova direção** (passo 2b) — adapte ao assunto, à cena e ao tom, e **declare a paleta
e o par de fontes na própria variação** (passo 2). A trava de identidade e o brief
vencem este catálogo; e o detector continua valendo (cada estética diz qual exceção
declarar).

## Como escolher

| Cena / modo | Referentes que funcionam |
|---|---|
| Painel, admin, dados (operar) | bento · dark-first · soft minimal |
| Landing, campanha (convencer) | editorial · vidro sobre foto |
| Portfólio, vitrine (experimentar) | bento · neo-brutalism |
| Mobile, noite, sessões longas | dark-first · soft minimal |
| Produto com identidade forte | neo-brutalism · editorial |

---

## Bento grid

- **Quando:** visão geral — "tudo num glance": overview, perfil, vitrine, home de
  produto, dashboard moderno.
- **Tokens:** gap 8px; células num mosaico **assimétrico** de 12 colunas (2×1, 1×2, 2×2,
  1×1); raio 12–16; elevação **por tom** (célula um nível acima do fundo), não por sombra.
- **Como:** `grid-template-columns: repeat(12, 1fr)` + `grid-column: span N` por célula;
  no mínimo 3 tamanhos diferentes e **1 célula hero** (a maior, com o que importa).
- **Evite:** todas as células do mesmo tamanho (isso é grade, não bento); texto em toda
  célula — misture mídia, número, lista, mini-gráfico.

## Vidro (glassmorphism) intencional

- **Quando:** camada flutuante **sobre conteúdo com profundidade** — foto, vídeo, mapa,
  gradiente colorido. Command palette, nav flutuante, stats sobre fundo.
- **Tokens (claro):** `background: rgba(255,255,255,.55)` · `backdrop-filter: blur(16px) saturate(1.2)` ·
  borda 1px `rgba(255,255,255,.45)` · sombra suave.
- **Tokens (escuro):** `background: rgba(18,18,22,.55)` · blur 16px · borda 1px `rgba(255,255,255,.12)`.
- **Evite:** vidro sobre fundo **plano** — o blur não tem o que difratar e vira decoração
  (o detector recusa). Nada de vidro em tudo: só na camada que flutua.

## Neo-brutalism

- **Quando:** identidade com atitude, produto jovem, editorial, marca "grosso".
- **Tokens:** borda 2px sólida (cor escura da paleta); sombra dura `4px 4px 0` (sem
  desfoque); raio 0–4; cores saturadas (2–3 na paleta: amarelo, rosa, azul, verde);
  tipografia display forte (peso black).
- **Como:** tudo plano, sem gradiente sutil; hover = sombra `0 0 0` + `translate(2px,2px)`.
- **Evite:** misturar com sombra suave na mesma tela. **Declare a exceção** no HTML:
  `<!-- detector: ignorar sombra-dura (mundo neobrutalista) -->`.

## Dark-first

- **Quando:** sessões longas, mobile à noite, dados/dashboard, produto com tom "pro".
- **Tokens (escala de superfície — nunca preto puro):**

  ```css
  --bg:        #0a0a0c;  /* base */
  --surface:   #131316;  /* card */
  --surface-2: #1c1c21;  /* elevado */
  --text:      #ededf0;
  --text-dim:  #9a9aa3;
  --line:      rgba(255,255,255,.08);
  ```

- **Como:** **elevação por luminosidade** (surface-2 acima de surface), não por sombra;
  bordas hairline `--line`; acento com glow **só em elemento interativo**
  (`box-shadow: 0 0 12px <accento>40`); gráfico em acento + 2–3 cores de apoio dessaturadas.
- **Evite:** preto puro `[detector]`; cinza claro demais sobre o fundo (use `--text-dim`);
  glow como decoração em elemento estático.

## Soft minimal

- **Quando:** produto calmo, B2B, saúde, "limpo" sem ser estéril; desktop e mobile.
- **Tokens:** cores dessaturadas (croma baixo); raio 16–24; sombra muito suave
  (`0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.06)`); borda 1px neutra;
  whitespace generoso (base 8px, seções 64–96px).
- **Como:** hierarquia por **tamanho e peso**, não por cor; um acento para ação;
  tipografia leve (peso 300–500).
- **Evite:** cair no "plano sem profundidade" — uma sombra sutil ou diferença de tom
  entre níveis salva; não empilhe mais de 3 neutros.

## Editorial (tipográfico)

- **Quando:** produto com conteúdo denso, marca cultural, landing "premium", docs com
  personalidade.
- **Tokens:** display serifada ou grotesca expressiva em título (escala grande,
  `letter-spacing: -0.02em`); sans neutra no corpo; fios hairline (1px, no tom da
  paleta, nunca preto); whitespace generoso; um acento de personalidade.
- **Como:** o título é o herói — 56–96px no desktop; layout assimétrico (colunas 7/5,
  8/4); numeração/eyebrows **só quando informam** (o piso recusa como decoração).
- **Evite:** cair no default "jornal" (creme + terracota + fios) sem escolha própria:
  escolha um acento real do assunto e um par de fontes concreto.
