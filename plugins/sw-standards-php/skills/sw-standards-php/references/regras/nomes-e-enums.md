# Nomes e enums

## Regra
O código é em inglês, com os nomes da tabela abaixo. **Quando o banco está em português, a model e as colunas
seguem o banco** (`Usuario`, `$user->nome_completo`); métodos, variáveis e códigos de resposta continuam em
inglês. Valor fixo de coluna vira enum `EModel{Tabela}{Coluna}`, e enum que não é de coluna vira `E{Nome}`, os dois
em `app/LogicApp/Enums/`, com valor em string e o nome do caso em MAIÚSCULO, igual ao valor do banco. Código de
resposta em snake_case e frase do erro em inglês.

| O quê | Forma | Exemplo |
|---|---|---|
| Classe | PascalCase, singular | `Invoice`, `Customer` |
| Model | o mesmo nome da tabela (singular), em PascalCase e na língua do banco | `Invoice` (`invoice`), `Usuario` (`usuario`) |
| Controller | `{Recurso}Controller` | `InvoiceController` |
| Middleware de validação | `Validate{Recurso}{Ação}Middleware` | `ValidateInvoiceCreateMiddleware` |
| Middleware de existência | `{Recurso}ExistsMiddleware` | `InvoiceExistsMiddleware` |
| Service | `{Nome}Service` em `Services/<Domínio>/` | `Services/Billing/InvoiceCancelService` |
| Método público | camelCase, verbo | `cancel()`, `listByCompany()` |
| Método privado | `_camelCase`, abaixo dos públicos | `_calculateFee()` |
| Variável | camelCase, sem abreviação | `$invoice`, `$customerIds`, `$idCompany` |
| Enum de coluna | `EModel{Tabela}{Coluna}` | `EModelInvoiceStatus` |
| Enum comum | `E{Nome}` | `EQueue`, `ELogger` |
| Caso de enum | MAIÚSCULO, igual ao valor do banco | `case OPEN = 'OPEN';` |
| Código de resposta | snake_case, em inglês | `invoice_already_paid` |
| Frase do erro | inglês, frase curta | `'Invoice already paid'` |
| Tabela e coluna | snake_case | `invoice_items.amount_in_cents` |

## Por quê
Nome previsível é o que deixa abrir qualquer projeto e achar a coisa sem procurar: o middleware da rota de criar
fatura só pode se chamar de um jeito. A model segue o banco porque a coluna é o nome real do dado, e traduzir na
model cria dois nomes para a mesma coisa, que quebram em todo SQL. O enum tira a string mágica do código: um
`'pago'` digitado errado vira erro de compilação em vez de um filtro que nunca acha nada. O código de resposta em
snake_case é o contrato que o front trata; a frase é só para gente ler.

## Certo
O enum da coluna `status` da tabela `invoice`:

```php
namespace App\LogicApp\Enums;

enum EModelInvoiceStatus: string
{
    case OPEN = 'OPEN';
    case PAID = 'PAID';
    case CANCELED = 'CANCELED';
}
```

O service usa o enum, os métodos públicos vêm antes e o privado com `_` fica embaixo:

```php
namespace App\LogicApp\Services\Billing;

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Models\Invoice;

final class InvoicePayService
{
    public static function pay(Invoice $invoice, int $paidInCents): Invoice|array
    {
        if($invoice->status === EModelInvoiceStatus::PAID->value){
            return ['error' => 'invoice_already_paid', 'message' => 'Invoice already paid', 'status' => 409];
        }

        $invoice->status = EModelInvoiceStatus::PAID->value;
        $invoice->paid_in_cents = $paidInCents;
        $invoice->fee_in_cents = self::_calculateFee($paidInCents);
        $invoice->save();

        return $invoice;
    }

    private static function _calculateFee(int $paidInCents): int
    {
        return intdiv($paidInCents * 3, 100);
    }
}
```

Banco em português: a model e as colunas seguem o banco; método e variável, não:

```php
$user = Usuario::findByEmail($email);
$fullName = $user->nome_completo;
```

## Errado
```php
// app/LogicApp/Services/FaturaServ.php
class FaturaServ
{
    private static function calcTaxa($v) { ... }

    public static function pagar($fat, $vlr)
    {
        if ($fat->status == 'pago') {
            ResponseApi::error('Fatura já paga', 'erro', 409);
        }

        $fat->status = 'paid';
        $fat->taxa = self::calcTaxa($vlr);
        $fat->save();
    }
}

class User extends Model
{
    protected static $_table = 'usuarios';

    public function getFullName() { return $this->fullName; }
}
```

Nome em português e abreviado, service sem sufixo e fora do domínio, privado acima do público e sem `_`, string
mágica (e diferente do banco: `'pago'` num lugar e `'paid'` em outro), código de resposta em frase e model
traduzida que não bate com a tabela nem com a coluna.

## Como reconhecer
- Método, variável ou código de resposta em português (`pagar`, `$fatura`, `'fatura_paga'`), fora as colunas e a
  model de banco em português.
- Abreviação em variável ou parâmetro (`$fat`, `$vlr`, `$usr`, `$qtd`, `$cnt`).
- Model com nome diferente da tabela no singular, ou propriedade que traduz a coluna.
- Classe em `Controllers/` sem o sufixo `Controller`; middleware de validação fora do molde
  `Validate{Recurso}{Ação}Middleware`; service sem o sufixo `Service` ou fora de `Services/<Domínio>/`.
- `private function` sem `_` ou acima de um método público.
- String literal comparada ou gravada em coluna de valor fixo (`status`, `type`, `role`) sem enum.
- Enum fora de `app/LogicApp/Enums/`, sem o prefixo `E`/`EModel`, com valor `int` ou caso em minúsculo.
- Primeiro argumento de `ResponseApi::error`/`success` fora de snake_case; segundo argumento em português.

## Como corrigir
1. Renomeie método, variável e código de resposta para inglês, por extenso, sem tocar em coluna nem em model de
   banco em português. Código de resposta muda contrato: confira com o dono se o front já trata o nome velho.
2. Renomeie classes para os moldes da tabela e mova o service para `Services/<Domínio>/`.
3. Prefixe os privados com `_` e mova-os para baixo dos públicos.
4. Para cada coluna de valor fixo, crie o enum `EModel{Tabela}{Coluna}` com os valores que estão no banco e troque
   as strings pelo enum.

```php
namespace App\LogicApp\Enums;

enum EModelInvoicePaymentMethod: string
{
    case PIX = 'PIX';
    case BOLETO = 'BOLETO';
    case CREDIT_CARD = 'CREDIT_CARD';
}
```
