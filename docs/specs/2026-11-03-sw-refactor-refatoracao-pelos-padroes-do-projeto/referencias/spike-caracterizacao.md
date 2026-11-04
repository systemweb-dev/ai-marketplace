# Spike: caracterização pela sw-auto-test

Executado em 2026-11-03, num diretório temporário com cópia do fixture (sem `GABARITO.md`). A
`sw-auto-test` foi seguida por um subagente com o pedido explícito da Task 4.

- Teste gerado: `tests/test_invoices.py`, 11 testes em `unittest`, no estilo de `test_orders.py`.
- Entradas fixadas: `0` e `-5` (DomainError com a mensagem exata), `1` (total 0), `30` (total 0,
  limite exclusivo), `31` (30), `60` (30), `61` (90). Fixou também o estranho: `True` aceito como
  id; `2.5`, `"3"` e `None` dão `TypeError` em vez de `DomainError`.
- Passa sem mudar o código: sim (`Ran 15 tests ... OK`).
- Falha com a mutação `if line % 5 == 0:` → `if True:`: sim (`FAILED (failures=4)`).
- Observação: a `sw-auto-test` não fez a prova do vermelho sozinha, porque ela altera `app/` e o
  pedido proibia. A prova foi feita fora dela, como prevê o step 3.

Veredito: **funciona**. Consequência para o plano: nenhuma; a oferta da `sw-auto-test` fica.
