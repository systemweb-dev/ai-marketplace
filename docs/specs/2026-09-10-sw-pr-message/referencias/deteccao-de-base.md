# Detecção da branch base — evidência medida

Medido em 2026-09-10, somente leitura, em dois repositórios reais de projetos que usam
`develop` (integração) e `master` (produção). Nomes de repositório e de branch omitidos
de propósito: este marketplace é público.

## Sinais que NÃO servem

| Sinal | O que devolve | Por que não serve |
|---|---|---|
| `@{upstream}` | a própria branch remota (`origin/<a-branch>`) | não diz de onde a branch saiu |
| `origin/HEAD` | a branch padrão (`master`) | errado para quem abre branch a partir de `develop` |

## Heurística "menos commits à frente" (`git rev-list --count <candidata>..<branch>`)

| Repo | `develop` à frente de `master` | Branch | à frente de `develop` | à frente de `master` | Escolha | Correto? |
|---|---|---|---|---|---|---|
| A | 211 | feature 1 | 9 | 205 | develop | sim |
| A | 211 | feature 2 | **0** | 158 | develop | sim — já mergeada |
| B | 264 | feature 3 | 6 | 260 | develop | sim |

**Consequência para a skill antiga:** ela testa `main → master → develop` nessa ordem.
No repo A, feature 1, escolheria `master` e descreveria **205 commits em vez de 9**.

**Caso de borda:** a feature 2 está 0 commits à frente de `develop`. A skill deve dizer
"parece já mergeada" e parar — nunca trocar para `master` e gerar 158 itens.
