# Testes

## Regra
Todo projeto testa com Pest, em três suítes: `Unit/` (sem banco), `Integration/` (banco `_test`) e `Http/`
(endpoint de ponta a ponta, contra um servidor embutido). A pasta `tests/` tem a árvore abaixo, com o `Support/`
copiado dos moldes da skill (`assets/tests-support/`) na etapa 0. O caminho do teste espelha o do código, e o nome
do teste, em português, diz o comportamento. Sem Mockery, sem SQL no teste (dado entra por `Fixtures`, pelo ORM) e
sem serviço externo real, nem no `Http/`: toda integração tem `fake()`, instalado pelo `Support/Fakes.php`. O core
só lê o `.env`: as chaves de teste ficam nele (ex.: `MARIADB_DBNAME_TEST`), e o `config/*.php` escolhe pelo
`getenv('APP_TESTING')` (banco `_test`, webhook do Discord vazio, fila de teste). Controller e middleware são testados só pelo `Http/`. Toda regra nova
nasce com teste, e código existente só é movido depois de ter teste.

```
tests/
├── Pest.php                       Boot::start(), as três suítes e Boot::reset() no beforeEach
├── TestCase.php                   classe base vazia que o Pest.php estende
├── Support/
│   ├── Boot.php                   força env=dev, liga APP_TESTING, recarrega a config, recria o banco, sobe o servidor
│   ├── TestDatabase.php           recria <projeto>_test a partir de database/sql/; recusa nome sem _test
│   ├── TestServer.php             php -S na porta de teste, uma vez por rodada, pelo app-router.php
│   ├── app-router.php             roteador do servidor: recusa sem APP_TESTING, instala os fakes, entrega ao www/index.php
│   ├── Http.php                   cliente do Http/: Http::post(...), Http::as($company)->post(...)
│   ├── Fakes.php                  Fakes::install(): uma linha Integracao::fake(...) por integração
│   ├── Fake/                      as implementações falsas (FakeAcmePayments.php)
│   └── Fixtures.php               Fixtures::company(), Fixtures::invoice(...) pelo ORM e o truncate()
├── Unit/
│   ├── Helpers/MoneyTest.php
│   └── Enums/EQueueTest.php
├── Integration/
│   ├── Models/InvoiceTest.php
│   ├── Services/Billing/InvoiceCancelServiceTest.php
│   └── Jobs/SendInvoiceEmailJobTest.php
└── Http/
    └── InvoiceTest.php            as rotas do InvoiceController, com os middlewares delas
```

| Camada | Pasta | O que testa | Como |
|---|---|---|---|
| Helper e enum | `Unit/Helpers/`, `Unit/Enums/` | função pura: entrada e saída, borda (zero, vazio, negativo) | sem banco, sem `Support/` além do Pest |
| Model | `Integration/Models/` | cada `findBy`/`listBy`/`countBy`/`existsBy`: o filtro certo, o escopo da empresa, o vazio | `Fixtures` grava, o método lê |
| Service | `Integration/Services/<Domínio>/` | a regra: o sucesso (o dado devolvido e o que ficou gravado) e cada array de erro, com o `status` | chama o método estático; integração pelo fake |
| Job | `Integration/Jobs/` | o `handle`: o que grava e o `ack`/`nack` de cada caso | monta a mensagem e chama o job, sem fila |
| Endpoint | `Http/` | validação (422), sem token (401), registro de outra empresa (404), sucesso com o formato exato da resposta | `Http::post` e `Http::as($company)` contra o `TestServer` |

## Por quê
O molde é o dos projetos mais maduros da casa, e um formato só deixa qualquer pessoa achar e escrever o teste sem
perguntar. O `ResponseApi` termina com `exit()`, então o endpoint não roda dentro do processo do Pest: o `Http/`
fala com um servidor embutido. Esse servidor é outro processo, e o fake instalado no Pest não chega nele; por isso
ele sobe pelo `Support/app-router.php`, que instala os fakes do lado do servidor. Mockery acopla o teste à
implementação e quebra a cada refatoração; o fake por `instance()` troca o fornecedor inteiro e o teste confere o
resultado. SQL no teste duplica o model e não pega o erro dele. O banco `_test`, recriado pelas migrations, impede
que a suíte grave no banco de dev.

## Certo
O teste de service grava pelo `Fixtures`, chama o service e confere o resultado, inclusive o array de erro:

```php
<?php

use App\LogicApp\Models\Invoice;
use App\LogicApp\Services\Billing\InvoiceCancelService;
use Tests\Support\Fixtures;

it('cancela a fatura em aberto e grava o motivo', function () {
    $invoice = Fixtures::invoice(Fixtures::company(), ['status' => 'open']);

    $canceled = InvoiceCancelService::cancel($invoice, 'Pedido duplicado');

    expect($canceled->status)->toBe('canceled');
    expect(Invoice::find($invoice->id)->cancel_reason)->toBe('Pedido duplicado');
});

it('não cancela fatura paga', function () {
    $invoice = Fixtures::invoice(Fixtures::company(), ['status' => 'paid']);

    $canceled = InvoiceCancelService::cancel($invoice, 'Pedido duplicado');

    expect($canceled)->toBe(['error' => 'invoice_already_paid', 'message' => 'Invoice already paid', 'status' => 409]);
});
```

O teste de endpoint cobre a borda pelo `TestServer`, sem SQL e sem token fixo:

```php
<?php

use Tests\Support\Fixtures;
use Tests\Support\Http;

it('recusa o cancelamento sem token', function () {
    $response = Http::post('/v1/invoices/1/cancel', ['reason' => 'Pedido duplicado']);

    expect($response['status'])->toBe(401);
});

it('não acha a fatura de outra empresa', function () {
    $invoice = Fixtures::invoice(Fixtures::company(), ['status' => 'open']);

    $response = Http::as(Fixtures::company())->post("/v1/invoices/{$invoice->id}/cancel", ['reason' => 'Pedido duplicado']);

    expect($response['status'])->toBe(404);
    expect($response['json']['message'])->toBe('invoice_not_found');
});

it('exige o motivo do cancelamento', function () {
    $company = Fixtures::company();
    $invoice = Fixtures::invoice($company, ['status' => 'open']);

    $response = Http::as($company)->post("/v1/invoices/{$invoice->id}/cancel", []);

    expect($response['status'])->toBe(422);
});

it('cancela e devolve só os campos da lista', function () {
    $company = Fixtures::company();
    $invoice = Fixtures::invoice($company, ['status' => 'open']);

    $response = Http::as($company)->post("/v1/invoices/{$invoice->id}/cancel", ['reason' => 'Pedido duplicado']);

    expect($response['status'])->toBe(200);
    expect(array_keys($response['json']['data']))->toBe(['id', 'status', 'cancel_reason']);
});
```

A integração entra no teste pelo fake, instalado numa linha do `Support/Fakes.php`:

```php
final class Fakes
{
    public static function install(): void
    {
        Acme::fake(new \Tests\Support\Fake\FakeAcmePayments());
    }
}
```

## Errado
```php
use Mockery;

test('cancel', function () {
    DB::query("INSERT INTO invoice (id, status, id_company) VALUES (99, 'open', 1)")->get();

    $gateway = Mockery::mock(AcmeHttpPayments::class);
    $gateway->shouldReceive('refund')->once()->andReturn(['id' => 'rf_1']);

    $controller = new InvoiceController();
    $controller->cancel();

    $client = new AcmeHttpPayments('https://api.acme.example', sw_config('acme')['api_key']);
    $client->charge(1000, 'tok_123');

    $token = 'eyJhbGciOiJIUzI1NiJ9...';
    $response = (new Curl())->post('http://localhost/invoices/99/cancel', [], ['Authorization' => $token]);

    expect($response)->not->toBeNull();
});
```

SQL no teste, Mockery, controller chamado dentro do Pest (o `exit()` do `ResponseApi` derruba a suíte), chamada
ao fornecedor de verdade, token fixo, requisição ao servidor de dev em vez do `TestServer`, nome sem
comportamento e um `expect` que não confere nada.

## Como reconhecer
- `tests/` sem `Pest.php` ou sem `Support/`, ou com `Support/` diferente dos moldes (sem `app-router.php`, sem
  recusa de banco sem `_test`, sem `env=dev` forçado).
- `composer.json` sem `autoload-dev` de `Tests\\` para `tests/`.
- `Mockery`, `->shouldReceive(`, `createMock(` ou `phpunit/phpunit` usado direto.
- `DB::query(`, `INSERT INTO`, `UPDATE `, `DELETE FROM` ou `->insert()` de model fora de `Support/Fixtures.php`.
- `new <Algo>Controller` ou chamada a middleware dentro de teste; teste em `Unit/Controllers/` ou
  `Unit/Middleware/`.
- URL de fornecedor, `localhost` fora do `Support/`, token fixo (`eyJ`, `Bearer `) ou chave de API em teste.
- Integração usada pelo service sem linha no `Fakes.php`, ou integração sem `fake()`.
- Teste em `Unit/` que toca banco, ou em `Integration/` que só testa função pura.
- Caminho que não espelha o código (`tests/InvoiceServiceTest.php` para `Services/Billing/InvoiceCancelService.php`)
  e nome sem comportamento (`test('cancel')`, `it('works')`).
- Service, model ou job sem nenhum teste; endpoint sem os casos 401, 404 (em projeto multiempresa) e 422.
- `config/*.php` que, com `APP_TESTING` ligado, ainda aponta para o banco ou a fila de produção ou deixa o webhook
  do Discord preenchido.
- **Exceção às outras regras:** `tests/Support/` é infraestrutura. O `TestDatabase` usa `sw_env` e PDO, e o `Fixtures::truncate()` usa `DB::query`, cada um com o comentário da exceção no topo. O resto de `tests/` segue todas as regras.

## Como corrigir
1. Na etapa 0, copie `assets/tests-support/` para `tests/` (o `Pest.php` na raiz, o resto em `tests/Support/`),
   crie o `TestCase.php` vazio, ponha o `autoload-dev` de `Tests\\` no `composer.json` e configure o banco `_test`
   no `config/Database.php` (escolhido por `getenv('APP_TESTING')`) e o `MARIADB_DBNAME_TEST` no `.env`.
2. Ajuste os moldes ao projeto: a constante `HOST` do `Http.php` (o host de dev do `config/Env.php`), o payload do
   `Http::as()` (o que o middleware de auth lê), a lista `KEEP` do `Fixtures.php` e uma linha no `Fakes.php` por
   integração.
3. Troque SQL e `insert` de teste por métodos com nome no `Fixtures.php`, sempre pelo ORM.
4. Troque Mockery por uma falsa em `Support/Fake/` que implementa a interface da integração.
5. Mova teste de controller e middleware para `Http/`, por `Http::post` e `Http::as($company)`.
6. Mova cada teste para a pasta que espelha o código e renomeie com o comportamento em português.
7. Antes de mover código sem teste, escreva o teste (sw-auto-test, se instalada) e deixe verde.

```php
it('lista só as faturas da empresa', function () {
    $company = Fixtures::company();
    Fixtures::invoice($company, ['status' => 'open']);
    Fixtures::invoice(Fixtures::company(), ['status' => 'open']);

    $invoices = Invoice::listByCompany($company->id);

    expect($invoices->count())->toBe(1);
});
```

## Enquanto o core não corrigir
Vale para o core até a 1.11.0, inclusive; cada item sai quando o core ganhar o recurso (confira o CHANGELOG do
core instalado).

- O `Support/Boot.php` existe porque o core não tem boot de teste. Quando ganhar `SysWeb\Testing::boot()`, o
  `Boot.php` some e o `Pest.php` chama o core.
- O `TestServer.php` e o `app-router.php` existem porque o `ResponseApi` termina com `exit()`. Enquanto for
  assim, endpoint só se testa pelo `Http/`.
- `Queue::send` e `DiscordLogger::send` não têm `fake()`, por isso não entram no `Fakes.php`. Com
  `APP_TESTING` ligado, o `config/*.php` aponta a fila para a de teste (o `EQueue` já põe o prefixo `-test`) e
  deixa o webhook do Discord vazio, com o logger tolerando isso. O teste confere o resultado do service, não a publicação na fila.
