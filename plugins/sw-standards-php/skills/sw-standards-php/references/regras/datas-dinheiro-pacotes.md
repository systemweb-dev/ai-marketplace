# Datas, dinheiro e pacotes

## Regra
Data e hora são `CarbonImmutable` (`nesbot/carbon`), nunca `date()`, `strtotime()` ou `DateTime` mutável. Dinheiro
é inteiro em centavos (coluna `*_in_cents`), ou `brick/money` quando há divisão, juros ou arredondamento; nunca
`float`. Pacote segue a tabela de preferidos, e pacote novo passa pela regra abaixo. E-mail sai pelo SendGrid,
salvo quando o projeto registrou outro em `docs/sw-standards/config.md`.

| Para | Use | Nunca |
|---|---|---|
| HTTP com fornecedor | `php-curl-class/php-curl-class`, dentro de `Integrations/<Fornecedor>/` | Guzzle direto, `curl_init` solto |
| Data e hora | `nesbot/carbon` (`CarbonImmutable`) | `date()`, `strtotime()`, `DateTime` |
| Dinheiro | inteiro em centavos; `brick/money` para cálculo | `float`, `round()` em valor |
| Fila, cache e JWT | `Queue`, `Cache` e `Jwt` do core | o pacote do broker, do Redis ou de JWT direto |
| Arquivo na nuvem | `aws/aws-sdk-php` | outro SDK de S3 |
| PDF | `dompdf/dompdf` | outro gerador |
| Pagamento com Stripe | `stripe/stripe-php` | chamada HTTP crua à API |
| Teste | Pest | PHPUnit puro, Mockery |
| E-mail | SendGrid (ou o que o projeto registrou) | `mail()` |

**Pacote novo:** primeiro veja se o core resolve; se não, use o da tabela; se a tabela não cobre, escolha um
pacote consolidado (mantido, com uso amplo) e registre o motivo em `docs/sw-standards/config.md`.

## Por quê
`float` não representa centavo: `0.1 + 0.2` não dá `0.3`, e a diferença aparece no fechamento do mês. Centavo
inteiro soma sem erro, e o `brick/money` arredonda de propósito, com o modo escrito. `CarbonImmutable` não muda a
data de quem a passou: um `addDays()` num `DateTime` compartilhado altera o vencimento de outra fatura sem
ninguém ver. A tabela de pacotes faz todos os projetos resolverem a mesma coisa do mesmo jeito; usar o `Queue` e
o `Cache` do core mantém a config e o teste num lugar só.

## Certo
Data com `CarbonImmutable` e dinheiro em centavos:

```php
namespace App\LogicApp\Services\Billing;

use App\LogicApp\Models\Invoice;
use Brick\Math\RoundingMode;
use Brick\Money\Money;
use Carbon\CarbonImmutable;

final class InvoiceInstallmentService
{
    public static function split(Invoice $invoice, int $installments): array
    {
        $firstDueDate = CarbonImmutable::parse($invoice->due_date);
        $total = Money::ofMinor($invoice->amount_in_cents, 'BRL');
        $parts = $total->split($installments);

        $schedule = [];

        foreach($parts as $number => $part){
            $schedule[] = [
                'due_date' => $firstDueDate->addMonths($number)->format('Y-m-d'),
                'amount_in_cents' => $part->getMinorAmount()->toInt(),
            ];
        }

        return $schedule;
    }

    public static function lateFee(Invoice $invoice): int
    {
        $total = Money::ofMinor($invoice->amount_in_cents, 'BRL');
        $fee = $total->multipliedBy('0.02', RoundingMode::HALF_UP);

        return $fee->getMinorAmount()->toInt();
    }
}
```

HTTP com fornecedor pelo `php-curl-class`, na implementação real da integração:

```php
namespace App\LogicApp\Integrations\Acme;

use Curl\Curl;

final class AcmeHttpPayments implements AcmePayments
{
    public function __construct(private string $apiKey)
    {
    }

    public function charge(int $amountInCents, string $customerToken): array
    {
        $curl = new Curl();
        $curl->setHeader('Authorization', "Bearer {$this->apiKey}");
        $curl->post('https://api.acme.example/charges', ['amount' => $amountInCents, 'customer' => $customerToken]);

        if($curl->error){
            throw new AcmeException("charge failed: {$curl->errorCode}");
        }

        return (array) $curl->response;
    }
}
```

## Errado
```php
$dueDate = date('Y-m-d', strtotime($invoice->due_date . ' +30 days'));

$date = new DateTime($invoice->due_date);
$reminderDate = $date->modify('-3 days');   // mudou $date também

$amount = (float) $invoice->amount;
$installment = round($amount / 3, 2);
$fee = $amount * 0.02;

$client = new \GuzzleHttp\Client();
$response = $client->post('https://api.acme.example/charges', ['json' => $payload]);

$redis = new \Predis\Client();
$redis->set('invoice:' . $invoice->id, json_encode($invoice));

mail($customer->email, 'Invoice', $body);
```

Data com `date`/`strtotime` e `DateTime` mutável, dinheiro em `float` com `round`, Guzzle direto, Redis sem o
`Cache` do core e e-mail por `mail()`.

## Como reconhecer
- `date(`, `strtotime(`, `mktime(`, `new DateTime(`, `new \DateTime(`, `Carbon::` (o mutável) ou `now()` do Carbon
  mutável.
- `(float)`, `floatval(`, `round(` ou divisão sobre valor de dinheiro; coluna de dinheiro DECIMAL ou sem o sufixo
  `_in_cents`; `number_format` fora do helper de exibição.
- No `composer.json`: `guzzlehttp/guzzle` usado direto, cliente de broker, de Redis ou de JWT
  (`firebase/php-jwt`, `predis/predis`, `php-amqplib`) em vez do core, pacote fora da tabela sem motivo registrado.
- `new \GuzzleHttp\Client`, `new \Predis\Client`, `JWT::encode` direto no código.
- `mail(` ou provedor de e-mail diferente do registrado no `docs/sw-standards/config.md`.

## Como corrigir
1. Troque `date`/`strtotime`/`DateTime` por `CarbonImmutable::parse(...)` ou `CarbonImmutable::now()`, guardando o
   resultado de cada operação numa variável nova.
2. Migre dinheiro para inteiro em centavos: coluna `*_in_cents` (com migration e conversão dos dados existentes,
   aprovada pelo dono) e `int` no código. Cálculo com divisão ou percentual passa pelo `brick/money`, com o
   `RoundingMode` explícito.
3. Leve chamada HTTP para `Integrations/<Fornecedor>/` com `php-curl-class` (`services-e-integracoes.md`) e tire o
   Guzzle do `composer.json` quando ninguém mais usar.
4. Troque cliente direto de fila, cache e JWT pelo `Queue`, `Cache` e `Jwt` do core.
5. Para pacote novo fora da tabela, registre o motivo em `docs/sw-standards/config.md` antes de instalar.
6. Para e-mail, leia `docs/sw-standards/config.md`. Se não houver registro e o projeto usa outro provedor que não
   o SendGrid, pergunte ao dono e grave a resposta ali.

```php
$dueDate = CarbonImmutable::parse($invoice->due_date);
$reminderDate = $dueDate->subDays(3);

$total = Money::ofMinor($invoice->amount_in_cents, 'BRL');
$fee = $total->multipliedBy('0.02', RoundingMode::HALF_UP);
$feeInCents = $fee->getMinorAmount()->toInt();
```
