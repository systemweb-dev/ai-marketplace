# Catálogo de movimento (valores prontos)

Leia **antes de escrever animação** (passo 4) e **antes de portar para o código real**
(passo 7). O guard de `prefers-reduced-motion` já é obrigatório (passo 4); o que está aqui
é o *o quê, quanto tempo e com qual curva* — pra decisão não virar "animar um pouquinho".

## Escala de duração

| Movimento | Tempo | Onde |
|---|---|---|
| **Micro** | 100–150ms | hover, press, ícone, tooltip |
| **Padrão** | 200–300ms | troca de estado, toggle, tab |
| **Entrada** | 300–500ms | cascata de seção/card no load |
| **Navegação** | 400–600ms | drawer, modal, transição de tela |

Abaixo de 100ms vira "pulo"; acima de 600ms, arrasta — só entrada de página inteira
proposital, e uma vez só.

## Curvas (prontas pra colar)

```css
--ease-out:      cubic-bezier(0.16, 1, 0.3, 1);  /* expo-out — a workhorse: entradas e estados */
--ease-standard: cubic-bezier(0.4, 0, 0.2, 1);   /* sutil: hover, micro */
--ease-in-out:   cubic-bezier(0.65, 0, 0.35, 1); /* ida e volta: tabs, reveal */
```

Regras:

- **Nunca `linear` em UI** (exceto progresso de "carregando").
- **Overshoot/quique é falha do detector** — não use; se o brief pede movimento
  lúdico, use a curva suave `cubic-bezier(0.34, 1.3, 0.64, 1)` e **declare a
  exceção** no HTML (`<!-- detector: ignorar ... -->`).
- Sempre **de um estado já visível, com saída exponencial**.

## Padrões de micro-interação

| Padrão | Spec | Onde |
|---|---|---|
| **Lift no hover** | `translateY(-1px)` + sombra, 150ms `--ease-standard` | card, botão primário |
| **Press** | `scale(0.97)`, 100ms | todos os botões |
| **Cascata** | 300–400ms cada, delay 40–80ms entre itens, `--ease-out` | grid/lista na entrada |
| **Reveal** | `opacity 0→1` + `translateY(12px)`, 400ms | seção ao rolar |
| **Sublinhado deslizante** | pseudo-elemento `scaleX(0→1)`, origem à esquerda, 200ms | link, tab |
| **Troca de ícone** | `rotate(90deg)` ou `scale(0.8→1)` + opacity, 150ms | expandir/colapsar, estado |
| **Drawer/modal** | 250–350ms `--ease-out`; backdrop só `opacity`, 200ms | overlays |
| **Troca de tab/painel** | `opacity` + `translateY(8px)`, 150–200ms | tabs, accordion |

Performance: anime **só `transform` e `opacity`** (nunca `width`/`height`/`top`).
Um elemento, no máximo duas propriedades ao mesmo tempo.

## Movimento em dashboard (modo operar)

| Efeito | Spec |
|---|---|
| **Count-up de KPI** | 400–600ms, ease-out, via JS; número em `font-variant-numeric: tabular-nums` pra não tremer |
| **Desenho do gráfico** | linha: `stroke-dashoffset`; barra: `scaleY(0→1)` com origem embaixo, 500ms, stagger 60ms |
| **Skeleton → conteúdo** | fade + `scale(0.98→1)`, 200ms |
| **Indicador "ao vivo"** | pulse de baixa intensidade, 2s (opacity 1→.5→1); é o **único loop** permitido |
| **Delta de variação** | sobe 2px, 300ms, depois que o número assenta |

## CSS ou biblioteca?

| Uso | Ferramenta |
|---|---|
| hover, estado, toggle, entrada, reveal | **CSS puro** (`transition`/`@keyframes`) — zero dependência |
| reordenar lista (layout), elemento compartilhado, saída de componente montado, física | **framer-motion / motion** — **se já existir no projeto** |

Projeto sem a lib? **Só CSS** — zero dependência nova sem aprovação (regra do kit).
No mockup (HTML), sempre CSS/JS vanilla.

## Piso (não fazer)

- Loop infinito, exceto o indicador "ao vivo" (baixa intensidade).
- Mais de 3 elementos animando em disputa na mesma tela — **uma orquestração por
  tela**, o resto quieto.
- Animar tudo que mexe: escolha os elementos que carregam o sentido; o resto fica
  estático.
- Na dúvida: **menos**. Uma transição de estado bem feita (150ms) vale mais que
  cinco cascatas malfeitas.
