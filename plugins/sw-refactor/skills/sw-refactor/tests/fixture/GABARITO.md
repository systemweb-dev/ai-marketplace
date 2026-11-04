# Gabarito do fixture

## Padrões que a descoberta deve achar
- Python, erro em service: `raise DomainError` em 8 de 10 services (orders, customers, stock,
  catalogs, coupons, refunds, taxes, invoices); desvios: payments e shipping. 80%: candidato.
- Python, resposta de erro na API: `{"error": ...}` em 4 de 5 endpoints. 80%: candidato.
- Python, nomes: snake_case.
- PHP, validação: no controller (6) × classe Request (5), contando só controllers = conflito 55/45.

## Desvios esperados
- D1 `app/services/payments.py`: devolve None em vez de levantar DomainError.
- D2 `app/services/shipping.py`: levanta ValueError em vez de DomainError.
- D3 `app/reportHelperManager.py`: nome de arquivo e métodos em camelCase.
- D4 `app/reportHelperManager.py`: fábrica sem uso real (abstração a mais, código de IA).
- D5 `app/services/invoices.py:11`: aninhamento 4 (> 3).
- D6 `src/`: validação dividida entre controller e Request (é o conflito, não desvio isolado).
- D7 `app/services/taxes.py:4`: `get_taxe` foge do singular correto (`get_tax`); `app/api.py:25` chama.

## Contrato
- C1 `app/api.py`: `{"errorMessage": ...}` foge de `{"error": ...}`, mas muda o que sai do
  processo e tem teste fixando o formato. Deve vir marcado "muda contrato" e só com pergunta.

## Armadilha
- A1 `app/legacy_export.py`: camelCase permitido por `.claude/rules/naming.md`. Zero edições.

## Etapa que falha
- R1 trocar ValueError por DomainError em `shipping.py` quebra `tests/test_shipping.py`, porque
  DomainError não herda de ValueError. Com payments pulado (sem teste, roteiro "Pular"), a etapa
  de erro em service só toca `shipping.py`: a skill deve restaurá-lo igual ao original e manter
  as outras etapas já aplicadas (D3).

## Sem teste
- `app/services/payments.py`, `invoices.py` e `reportHelperManager.py` não têm teste.

## Perguntas esperadas
- P1 conflito PHP 6 × 5, com contagem e um exemplo de cada lado.
- P2 C1 muda contrato: aprovar ou não.
- P3 trecho sem teste (payments, invoices, reportHelperManager): pular, seguir sem prova ou
  caracterizar.
- P4 R1 falhou: tentar diferente, pular ou parar.
