# Gabarito do fixture (sw-skill-test)

Fica **fora** de `fixture/`, para a auditoria não lê-lo. As linhas foram conferidas com `grep -n` no próprio
fixture. Caminhos relativos a `fixture/`.

O fixture é um projeto mínimo do framework (core `v1.11.0` no `composer.lock`), multiempresa por `id_company`,
com a etapa 0 já feita (fixer, `tests/Support/`, tratador global, `AGENTS.md`, `docs/sw-standards/`). Tem dois
temas: `Api` (JSON, `config/Themes.php` → `api`) e `Site` (Twig, tema padrão). Por isso o `config/Env.php` diz
`application => 'website'`: com `'api'`, a skill pularia a família Website e a violação 17 nunca seria achada.

## Violações plantadas (uma por arquivo de regra, sem o `estilo.md`)

| # | Regra | Arquivo:linha | O que está errado |
|---|---|---|---|
| 1 | validacao-no-middleware | app/Api/Controllers/InvoiceController.php:21 | o controller lê `Request::get('status')` em vez de um middleware validar e compartilhar |
| 2 | controller-fino | app/Api/Controllers/InvoiceController.php:64 | método privado `_invoiceAttributes` no controller |
| 3 | banco-no-model | app/LogicApp/Services/Billing/InvoiceService.php:15 | `Invoice::where(...)->get()` montado no service, sem método com nome no model |
| 4 | services-e-integracoes | app/LogicApp/Helpers/CustomerLabel.php:12 | helper chama model (`Customer::findByCompany`): helper com banco |
| 5 | transacao-e-fila | app/LogicApp/Services/Billing/InvoiceCreateService.php:51 | `Queue::send` dentro do `try`, antes do `DB::commit()` |
| 6 | erro-e-resposta | middleware/ValidateCustomerCreateMiddleware.php:22 | `ResponseApi::error` sem o status (sai HTTP 200) |
| 7 | dados-no-topo-e-sem-cadeia | app/LogicApp/Services/Billing/PricingPageService.php:19 | `sw_config('billing')` lido depois do primeiro `if` do método |
| 8 | ruido-defensivo | app/LogicApp/Services/Customer/CustomerService.php:17 | `(int) $idCompany` sobre parâmetro já tipado `int` |
| 9 | guard-clause-sem-else | app/LogicApp/Services/Billing/InvoiceDueDateService.php:13 | `}else{` atribuindo a mesma variável nos dois ramos (cabe valor padrão) |
| 10 | nomes-e-enums | app/LogicApp/Services/Billing/InvoiceCancelService.php:23 | string mágica `'CANCELED'` gravada no `status` em vez de `EModelInvoiceStatus::CANCELED->value` |
| 11 | tipos-e-comentarios | app/LogicApp/Helpers/Money.php:7 | parâmetro `$cents` sem tipo |
| 12 | datas-dinheiro-pacotes | scheduler/InvoiceOverdueScheduler.php:13 | `date('Y-m-d')` em vez de `CarbonImmutable` |
| 13 | seguranca-e-config | app/LogicApp/Integrations/Aws/Aws.php:14 | `sw_env('AWS_BUCKET')` fora de `config/` (a config já tem `aws.bucket`) |
| 14 | rotas | app/Api/Rotas.php:13 | URL `customers` sem a versão (`v1/`) |
| 15 | jobs-e-scheduler | jobs/InvoiceCreatedJob.php:23 | o caminho do array de erro sai com `return` sem `ack` nem `nack` |
| 16 | infra | app/LogicApp/Services/Billing/PricingPageService.php:31 | `Cache::set` sem TTL (usa o padrão do core, não o `ECache::...->ttl()`) |
| 17 | website-twig | app/Site/Views/pricing/index.twig:10 | o template calcula o preço (`/ 100` e `number_format`) em vez de receber o rótulo pronto do service |
| 18 | testes | tests/Integration/Services/Billing/InvoiceServiceTest.php:23 | `Mockery::mock` no lugar da falsa de `Support/Fake/` |

## Armadilhas (legítimas, não acusar)

| # | Armadilha (legítima, não acusar) | Arquivo:linha |
|---|---|---|
| A1 | SQL cru (`DB::query`) no model, com placeholder nomeado e o comentário do motivo (o builder não faz SUM) | app/LogicApp/Models/Invoice.php:34 |
| A2 | `?? null` em `notes`, campo opcional de verdade (o middleware só compartilha quando vem) | app/LogicApp/Services/Billing/InvoiceCreateService.php:31 |
| A3 | `@unlink($temporaryPath)` com o comentário de limpeza | app/LogicApp/Integrations/Aws/S3Storage.php:26 |
| A4 | `=== null` onde o desconto zero é valor válido, com o comentário | app/LogicApp/Services/Billing/DiscountService.php:12 |
| A5 | `Invoice::find($idInvoice)` e `save()` no service, com id que vem do payload da fila (não da rota) | app/LogicApp/Services/Billing/InvoiceService.php:39 |

## Como contar

- **Achou:** o relatório tem a regra certa em até 2 linhas da indicada. A 7 e a 16 estão no mesmo arquivo, em
  linhas diferentes: cada uma conta uma vez.
- **Acusou armadilha:** o relatório lista a linha da armadilha (ou a de `save()`/`find` do mesmo método, na A5)
  como violação de qualquer regra.
- **Exceções documentadas em `tests/Support/`:** o `TestDatabase` (`sw_env` e PDO) e o `Fixtures::truncate()`
  (`DB::query`) trazem o comentário da exceção, e as regras `banco-no-model`, `seguranca-e-config` e `testes`
  mandam não acusar. Acusação nesses dois arquivos conta como falso positivo, à parte das 5 armadilhas.
- **Teste vermelho de propósito:** `tests/Http/CustomerTest.php` espera 422 na validação do cliente, e a
  violação 6 devolve 200. O teste segue o padrão; quem quebra é o código.
