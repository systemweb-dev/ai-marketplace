# Validação no middleware

## Regra
Toda entrada da rota é validada, normalizada e convertida no middleware `Validate{Recurso}{Ação}Middleware`,
com `SysWeb\Validator\Validator::check`. O middleware repassa o resultado com `Request::share('chave', $dados)`,
inclusive o registro que ele já buscou. O controller lê só `$this->shared('chave')`, uma vez, em variáveis no topo
do método, antes do primeiro `if`. Ele nunca lê `Request::post()`, `Request::get()`, `Router::param()` nem busca
de novo o que o middleware já entregou. A conversão de tipo acontece uma vez, no `share`; depois dela, nenhum cast.

## Por quê
É o padrão Middleware/Pipeline: a borda decide o que entra, e o resto do código confia no que recebe. Sem isso, o
controller relê a request, repete a validação e espalha `(int)` por todas as camadas. `Request::share` só
existe no core a partir da 1.10, por isso a etapa 0 sobe o core antes de corrigir.

## Certo
```php
namespace Middleware;

use SysWeb\Api\ResponseApi;
use SysWeb\Request\Request;
use SysWeb\Response\Response;
use SysWeb\Validator\Validator;

final class ValidateInvoiceCreateMiddleware
{
    public function __invoke(Request $request, Response $response, callable $next)
    {
        $data = Request::post();

        $rules = [
            'id_customer' => 'require|int',
            'description' => 'require|max:255',
            'amount_in_cents' => 'require|int',
        ];

        if(!Validator::check($data, $rules)){
            ResponseApi::error('invalid_data', Validator::error()->msg, 422);
        }

        // o min do Validator conta caracteres, não valor: pedido ao framework
        if((int) $data['amount_in_cents'] < 1){
            ResponseApi::error('amount_must_be_positive', 'Amount must be positive', 422);
        }

        Request::share('invoiceData', [
            'id_customer' => (int) $data['id_customer'],
            'description' => trim($data['description']),
            'amount_in_cents' => (int) $data['amount_in_cents'],
        ]);

        return $next();
    }
}
```

O controller da mesma rota lê tudo no topo e não converte nada:

```php
public function create(): void
{
    $company = $this->shared('company', Company::class);
    $invoiceData = $this->shared('invoiceData');

    $invoice = InvoiceCreateService::create($company->id, $invoiceData);

    if(is_array($invoice) && isset($invoice['error'])){
        ResponseApi::error($invoice['error'], $invoice['message'], $invoice['status']);
    }

    ResponseApi::success('invoice_created', Api::returnAttributes($invoice, ['id', 'description', 'amount_in_cents']));
}
```

## Errado
```php
public function create()
{
    $companyId = (int) $this->company->id;
    $data = Request::post();

    if (empty($data['id_customer']) || !is_numeric($data['id_customer'])) {
        ResponseApi::error('customer_id_is_required', 'Customer is required');
    }

    $customer = Customer::where(['id =' => (int) $data['id_customer'], 'AND' => ['id_company =' => $companyId]])->first();

    $invoice = InvoiceCreateService::create((int) $companyId, (int) $data['id_customer'], (float) ($data['amount'] ?? 0));
    ...
}
```

A validação está no controller, sem status, a entrada é relida e convertida em três lugares, há `??` em chave
"obrigatória" e dinheiro em float.

## Como reconhecer
- Em `app/**/Controllers/`: `Request::post(`, `Request::get(`, `Request::put(`, `Request::queryString(`,
  `Router::param(`, `$this->request->` ou `Validator::check(`.
- Controller que busca de novo um registro pelo id que o middleware já validou.
- Rota POST/PUT/PATCH/DELETE ou com `{id}` sem um `Validate{Recurso}{Ação}Middleware`.
- Middleware que valida mas não chama `Request::share` (o controller vai reler a request).
- `(int)`, `(float)`, `(string)` ou `intval(` sobre o que veio de `shared()`, e casts repetidos do mesmo dado em
  controller, service e model.
- Leitura de entrada no meio do método, depois do primeiro `if`.

## Como corrigir
1. Garanta o core ≥ 1.10 (etapa 0). Sem ele não há `Request::share`.
2. Crie ou complete o `Validate{Recurso}{Ação}Middleware` com `Validator::check` e as regras do core (`require`,
   `int`, `email`, `url`, `max:N`, `unique:tabela:coluna`). O que o core não valida certo vai em `if` manual,
   com o comentário do pedido ao framework (seção abaixo).
3. Converta cada campo uma vez dentro do `Request::share`, já no tipo final, e compartilhe também o registro que o
   middleware buscou (`Request::share('invoice', $invoice)`).
4. Registre o middleware na rota.
5. No controller, troque toda leitura da request por `$this->shared('chave')` em variáveis no topo, apague a
   validação e os casts que sobraram, e passe os valores direto para o service.

```php
public function update(): void
{
    $invoice = $this->shared('invoice', Invoice::class);
    $changes = $this->shared('invoiceChanges');

    $updated = InvoiceUpdateService::update($invoice, $changes);

    if(is_array($updated) && isset($updated['error'])){
        ResponseApi::error($updated['error'], $updated['message'], $updated['status']);
    }

    ResponseApi::success('invoice_updated', Api::returnAttributes($updated, ['id', 'description', 'amount_in_cents']));
}
```

## Enquanto o core não corrigir
Vale para o core até a 1.11.0, inclusive. Confira o CHANGELOG do core instalado (`composer.lock`) antes de aplicar:
quando o `Validator` corrigir o caso, a nota sai e o `if` manual volta a ser regra do `check`.

- **`min`/`max` contam caracteres** (`strlen`), não comparam o número. Valor mínimo ou máximo numérico vai em `if`
  manual depois do `check`.
- **Zero é rejeitado por `int`** (o core usa `filter_var` sem tratar o `0`). Campo em que `0` é válido sai do `check`
  e é conferido à mão com `filter_var($valor, FILTER_VALIDATE_INT) === false`.
- **Campo opcional não existe:** chave com regra que não veio na request reprova o `check`. Monte as regras só com os
  campos presentes, ou confira o opcional com `if` manual.

Cada `if` manual leva um comentário curto que aponta o pedido ao framework, por exemplo
`// o int do Validator reprova o zero: pedido ao framework`.
