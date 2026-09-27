# Padrões de dashboard e painel (modo operar)

Quando o mockup for um **painel, admin ou tela de dados** (passo 1b, modo *operar*),
compose a partir dos padrões abaixo — não invente a estrutura do zero. O padrão dá a
**topologia**; os tokens continuam sendo os do projeto (trava de identidade).

## Shells (topologia da tela)

| Shell | Quando |
|---|---|
| **A — sidebar + conteúdo** | painel com 5+ seções; sidebar fixa 240–280px, recolhível |
| **B — topbar + conteúdo** | compacto, mobile, 1–3 seções |
| **C — sidebar + topbar + conteúdo** | enterprise completo: navegação global à esquerda, contexto no topo |
| **+ command palette** | overlay (não rota) para ação rápida/busca |

**Shell A (o padrão):**

```
┌────────┬────────────────────────────────┐
│        │  topbar: título + ações        │
│  SIDE  ├────────────────────────────────┤
│  BAR   │  KPI row (3–5)                 │
│ (nav + │  ┌───────────┬───────────────┐ │
│  user) │  │ gráfico   │ lista/tabela  │ │
│        │  └───────────┴───────────────┘ │
└────────┴────────────────────────────────┘
```

**Shell C:** topbar com breadcrumb + busca + ações; sidebar com seções agrupadas;
conteúdo com margem 24px.

## Linha de KPI

- **3 a 5 KPIs** — mais de 5 a linha deixa de ser "o que importa" e vira tabela.
- **Hierarquia: nunca 5 idênticos.** Um KPI primário (2× a largura, ou com
  sparkline/tendência) e os demais secundários. Atenção: o detector só acusa
  (`tres-colunas-iguais`) quando são **exatamente três** colunas iguais — com 4 ou 5 KPIs
  idênticos ele fica calado, e a linha continua errada. Aqui o piso é o seu olho.
- **Anatomia do KPI:** rótulo (12–13px, `--text-dim`) → valor (24–32px,
  `font-variant-numeric: tabular-nums`, peso 600–700) → delta (`+3,2%` com cor
  semântica e seta pequena).
- **Sparkline** no KPI primário (últimos 7–30 dias, 1 linha, cor do acento).

## Grade de gráficos

| Padrão | Quando |
|---|---|
| **Gráfico grande 2fr + dois de 1fr** | uma métrica principal + duas de apoio |
| **2×2** | quatro métricas comparáveis |
| **Gráfico cheio + tabela 50/50** | tendência + detalhe |
| **Bento 12 colunas** | mistura de KPI + gráfico + lista + tabela |

**Regras de gráfico:** título + período/filtro no topo do card; **sem moldura e sem
12 meses no eixo** — 4–6 linhas hairline; cor: acento (série que importa) + 2–3
apoios dessaturados, nunca arco-íris; legenda só com 3+ séries; valor no hover
(tooltip), não em todos os pontos.

## Tabela data-dense

- **Linha compacta: 36–44px** (confortável) ou 32–36px (compacta).
- **Header sticky** (`position: sticky; top: 0`) com fundo do `--surface`.
- **Hierarquia de colunas:** coluna primária peso 500–600; secundárias `--text-dim`.
- **Números em `tabular-nums`**, alinhados à direita.
- **Status** em badge pequeno (11–12px) com cor semântica.
- **Zebra ou hairline, nunca borda em tudo** (sem caixão 3D).
- Hover de linha (tom do `--surface-2`); ação na última coluna (botão de ícone, não
  link de texto).
- **Overflow:** "+N" ou paginação — nunca coluna cortada.

## Barra de filtro

- Acima do conteúdo (abaixo da topbar), alinhada com a KPI/tabela.
- **Chips** de filtro rápido + **intervalo de datas** + **busca**; filtro ativo
  destacado (cor do acento ou tom preenchido).
- Se não há filtro de verdade, **não monte a barra** vazia.

## Densidade

| Densidade | Padding | Linha | Quando |
|---|---|---|---|
| **Confortável** | 16–24px | 40–48px | poucas métricas, tela de decisão |
| **Compacta** | 8–12px | 32–40px | dados densos, uso profissional, sessão longa |

**Uma densidade por tela** — misturar é o que vira "remendo".

## Hierarquia no modo operar

1. **O que o usuário veio fazer** (estado da operação principal) — mais peso.
2. **Métricas que apoiam a decisão** (KPI row).
3. **Detalhe** (tabela/gráfico).
4. **Navegação global** (sidebar/topbar) — quieta, nunca competindo.
