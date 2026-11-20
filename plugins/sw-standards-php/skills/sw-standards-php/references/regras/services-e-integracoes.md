# Services e integrações

## Regra
Regra de negócio vive em `app/LogicApp/Services/<Domínio>/<Nome>Service.php`, numa classe com métodos estáticos e
sem estado; nada solto na raiz de `Services/`. Integração com serviço externo vive em
`app/LogicApp/Integrations/<Fornecedor>/`, atrás de uma interface, com `instance()` para obter a implementação e
`fake()` para o teste trocar por uma falsa. Helpers só têm função pura: sem regra de negócio, sem banco e sem
integração. Os dados andam entre as camadas em array associativo, sem DTO.

## Por quê
Service Layer: a regra fica num lugar previsível por domínio, e qualquer pessoa acha onde está a cobrança ou o
cancelamento. Estático e sem estado porque o service não guarda nada entre chamadas. A interface com `fake()`
deixa o teste rodar sem chamar o fornecedor real e sem Mockery. Helper com regra ou banco vira um service
escondido que ninguém testa.

## Certo
Estrutura:

```text
app/LogicApp/
├── Services/
│   └── Billing/
│       ├── InvoiceCreateService.php
│       └── InvoiceCancelService.php
├── Integrations/
│   └── Acme/
│       ├── AcmePayments.php        (interface)
│       ├── AcmeHttpPayments.php    (implementação real)
│       └── Acme.php                (instance() e fake())
└── Helpers/
    └── Money.php                   (função pura)
```

O service:

```php
namespace App\LogicApp\Services\Billing;

use App\LogicApp\Integrations\Acme\Acme;
use App\LogicApp\Models\Invoice;

final class InvoiceChargeService
{
    public static function charge(Invoice $invoice, string $customerToken): Invoice|array
    {
        if($invoice->status !== 'open'){
            return ['error' => 'invoice_not_open', 'message' => 'Invoice is not open', 'status' => 409];
        }

        $charge = Acme::instance()->charge($invoice->amount_in_cents, $customerToken);

        $invoice->status = 'paid';
        $invoice->gateway_charge_id = $charge['id'];
        $invoice->save();

        return $invoice;
    }
}
```

A integração:

```php
namespace App\LogicApp\Integrations\Acme;

interface AcmePayments
{
    public function charge(int $amountInCents, string $customerToken): array;
}
```

```php
namespace App\LogicApp\Integrations\Acme;

final class Acme
{
    private static ?AcmePayments $instance = null;

    public static function instance(): AcmePayments
    {
        return self::$instance ??= new AcmeHttpPayments(sw_config('acme')['api_key']);
    }

    public static function fake(AcmePayments $fake): void
    {
        self::$instance = $fake;
    }
}
```

No teste, o `Support/Fakes.php` instala a falsa numa linha: `Acme::fake(new \Tests\Support\Fake\FakeAcmePayments());`.

O helper puro:

```php
namespace App\LogicApp\Helpers;

final class Money
{
    public static function centsToDecimal(int $cents): string
    {
        return number_format($cents / 100, 2, '.', '');
    }
}
```

## Errado
```php
// app/LogicApp/Services/InvoiceService.php, solto na raiz e com estado
class InvoiceService
{
    private $gateway;

    public function __construct()
    {
        $this->gateway = new \GuzzleHttp\Client(['base_uri' => 'https://api.acme.example']);
    }

    public function charge(InvoiceDTO $dto) { ... }
}

// app/LogicApp/Helpers/InvoiceHelper.php, com banco e regra
class InvoiceHelper
{
    public static function canCancel($id)
    {
        $invoice = Invoice::find($id);
        return $invoice->status == 'open' && $invoice->due_date > date('Y-m-d');
    }
}
```

Service na raiz, instanciado e com estado, cliente HTTP do fornecedor criado direto (sem interface e sem
`fake()`, o teste chama o real), DTO entre camadas e helper com banco e regra.

## Como reconhecer
- Arquivo direto em `app/LogicApp/Services/` (sem a pasta do domínio) ou nome sem o sufixo `Service`.
- Service com `__construct`, propriedade de instância, `new <Nome>Service` ou método não estático.
- `new \GuzzleHttp\Client`, `new Curl`, `curl_init`, SDK de fornecedor (`new \Acme\Client`) fora de
  `Integrations/<Fornecedor>/`.
- Pasta em `Integrations/` sem interface, sem `instance()` ou sem `fake()`.
- Em `Helpers/`: `DB::`, chamada a model, `ResponseApi`, `sw_config`, integração ou decisão de negócio.
- Classe `*DTO`, `*Data` ou `*Payload` usada só para levar dado entre camadas.

## Como corrigir
1. Crie a pasta do domínio em `Services/` e mova o service para lá, com `final class` e métodos `public static`.
   Estado de instância vira parâmetro.
2. Para cada fornecedor, crie em `Integrations/<Fornecedor>/` a interface com os métodos usados, a implementação
   real (com `php-curl-class` para HTTP, nunca Guzzle direto) e a classe com `instance()` e `fake()`, como no
   bloco abaixo. Troque o uso direto por `<Fornecedor>::instance()->metodo()`.
3. Crie a implementação falsa em `tests/Support/Fake/` e registre-a no `Support/Fakes.php`.
4. Leve a regra e o banco do helper para um service do domínio; no helper fica só a parte pura.
5. Troque o DTO por array associativo com as chaves que o service usa.

```php
final class Acme
{
    private static ?AcmePayments $instance = null;

    public static function instance(): AcmePayments
    {
        return self::$instance ??= new AcmeHttpPayments(sw_config('acme')['api_key']);
    }

    public static function fake(AcmePayments $fake): void
    {
        self::$instance = $fake;
    }
}
```
