# Extração de Design Tokens por Stack

Guia de referência para o passo 2 do workflow. O objetivo é montar um bloco de
CSS variables (light + dark) para injetar no harness, traduzindo o que o projeto
usar para esse formato comum. Leia só a seção do stack detectado.

## Como detectar o stack

Verifique marcadores na raiz e em `src/`:

- `tailwind.config.{js,ts,cjs}` presente → **Tailwind**
- Arquivos `.scss`/`.sass` com `$variaveis` → **SCSS**
- Bloco `:root { --x: ... }` em CSS global → **CSS variables** (mais comum)

Um projeto pode misturar (ex.: Tailwind + CSS vars). Prefira a fonte que define
as cores semânticas reais usadas nos componentes.

## CSS variables (caso mais comum)

Procure o CSS global: `src/style.css`, `src/assets/*.css`, `app.css`,
`main.css`. Extraia de `:root` (tema claro) e do seletor de tema escuro
(`[data-theme="dark"]`, `.dark`, `@media (prefers-color-scheme: dark)`).

Pegue: backgrounds, textos, bordas, acentos, `--spacing-*`, `--radius-*`,
`--font-*`, sombras. Copie os valores **literalmente** para o harness — light no
`.panel--light`, dark no `.panel--dark`.

```
/* projeto */                    →   /* harness .panel--light */
:root {                              .panel--light {
  --bg-card: #ffffff;                  --bg-card: #ffffff;
  --text-primary: #0f172a;             --text-primary: #0f172a;
  --accent-primary: #3b82f6;           --accent-primary: #3b82f6;
}                                    }
[data-theme="dark"] {                .panel--dark {
  --bg-card: #1e293b;                  --bg-card: #1e293b;
  --text-primary: #f8fafc;             --text-primary: #f8fafc;
}                                    }
```

Cuidado com superfícies que no dark colapsam (ex.: `--bg-secondary` igual ao
`--bg-card`). Para zonas internas sutis, use tinta translúcida
(`rgba(148,163,184,0.07)`) que funciona sobre qualquer fundo.

## Tailwind

Leia `tailwind.config.{js,ts}` → `theme.extend`. Traduza para CSS vars no
harness:

- `colors` → `--cor-*` (mapeie os nomes semânticos: `primary`, `surface`, etc.)
- `spacing` → `--spacing-*` (ou use os próprios valores Tailwind)
- `borderRadius` → `--radius-*`
- `fontFamily` → `--font-sans`

Se o projeto usa dark mode do Tailwind (`darkMode: 'class'`), os valores dark
costumam estar nas mesmas escalas de cor (ex.: `slate-900` para fundo dark).
Espelhe a escolha real vista nos componentes.

```
// tailwind.config.js                →  harness
theme.extend.colors.primary['500']     --accent-primary: <valor hex correspondente>
theme.extend.borderRadius.lg           --radius-lg: <valor>
```

Dica: se preferir, em vez de traduzir, pode carregar o Tailwind via CDN no
harness e usar as classes direto — mas traduzir para vars mantém o mockup
alinhado ao resto do fluxo e independente de rede.

## SCSS / Sass

Procure `_variables.scss`, `_tokens.scss`, `_colors.scss`. Variáveis SCSS
(`$cor-primaria: #3b82f6;`) são resolvidas em build, então no mockup vire-as
CSS vars com o valor literal.

```
// _variables.scss          →   harness .panel--light
$bg-card: #ffffff;              --bg-card: #ffffff;
$text-primary: #0f172a;         --text-primary: #0f172a;
$radius-lg: 12px;               --radius-lg: 12px;
```

Para temas em SCSS (mixins/mapas de tema), localize os dois conjuntos de valores
(claro/escuro) e distribua entre `.panel--light` e `.panel--dark`.

## Fonte

Descubra a família real e replique no harness:

- **Google Fonts** — `<link>` no `index.html` ou `@import` no CSS. Copie o
  `<link>` para o harness e ajuste `--font-sans`.
- **Fonte local** — `@font-face` no CSS. No mockup pode-se cair para a família
  genérica equivalente (`system-ui`, serif, etc.) se o arquivo não for
  facilmente carregável; avise que a fonte é aproximada.
- **Tailwind** — `theme.fontFamily.sans`.

## Quando não encontrar nada

Use defaults neutros (já presentes no harness) e diga ao usuário que os tokens
não foram detectados — o mockup fica utilizável, porém menos fiel. Ofereça que
ele aponte o arquivo de tema se souber onde está.
