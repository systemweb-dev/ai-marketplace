# Spike: estabilidade da contagem

Executado em 2026-11-03 no fixture, grupos a, b e e, duas rodadas por versão do prompt. Todas as
linhas citadas conferidas com `sed` (42 de 42 na 1ª versão).

## 1ª versão do prompt (rodadas 1 e 2)

| Dimensão | Rodada 1 | Rodada 2 | Diferença | Exemplos conferidos |
|---|---|---|---|---|
| nomes (Python) | snake 14 · camel 1 · exceção 1 | snake 14 · camel 1 · exceção 1 | 0 | ok |
| erro em service (Python) | DomainError 8 · ValueError 1 · None 1 | igual | 0 | ok |
| validação (PHP), grupo e | inline 6 · Request 5 | inline 6 · Request 10 | 5 | ok |

Instável: a unidade de contagem variou (controller + classe Request contados como 10), e uma
rodada marcou `muda_contrato` em quase todo símbolo interno.

## 2ª versão (unidade = arquivo onde a decisão é tomada; contrato = o que se vê fora do código)

| Dimensão | Rodada 3 | Rodada 4 | Diferença | Exemplos conferidos |
|---|---|---|---|---|
| nomes (Python) | snake 13 · camel 1 · get_taxe 1 · exceção 1 | snake 14 · camel 1 · get_taxe 1 · exceção 1 | 1 | ok |
| erro em service (Python) | DomainError 8 · ValueError 1 · sentinela 2 | igual | 0 | ok |
| validação (PHP) | inline 6 · Request 5 (grupos b e e) | inline 6 · Request 5 | 0 | ok |

`muda_contrato` só em `legacy_export.py` (reflexão) e `api.py:30` (`errorMessage`).

Veredito: **estável** com o prompt corrigido. Consequência para o plano: prompt com unidade e
definição de contrato (já em `references/subagente-descoberta.md`) e recontagem em toda dimensão
abaixo de 80% antes de perguntar (Task 5).
