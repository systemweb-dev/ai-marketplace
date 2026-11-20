# Guard clause e sem else

## Regra
Cada erro é testado no topo e sai na hora (guard clause, ou early return); o caminho feliz fica embaixo, sem
aninhar. No service, o erro sai com `return` do array de erro. No controller e no middleware, sai com
`ResponseApi::error(...)`, que já encerra a execução: um `return` depois dele é ruído. **Evite `else` e `elseif`
sempre:** guard clause para erro, valor padrão antes do `if` para atribuição e `match` para três caminhos ou mais.
O fixer ainda formata `}else{` para o raro caso que sobrar, mas sobrar é exceção, não estilo.

## Por quê
Com a guarda no topo, quem lê sabe logo o que impede o método de seguir, e o resto do método é a regra sem
recuo. `if/else` aninhado empurra o caminho feliz para a direita e obriga a lembrar de qual ramo se está. O
`ResponseApi` termina com `exit()` (o `Response::json` do core encerra), então o código depois do erro nunca roda: o
`return` e o `else` só sugerem um fluxo que não existe.

## Certo
No service, cada guarda devolve o array de erro e o caminho feliz fica no fim:

```php
public static function cancel(Invoice $invoice, string $reason): Invoice|array
{
    if($invoice->status === 'paid'){
        return ['error' => 'invoice_already_paid', 'message' => 'Invoice already paid', 'status' => 409];
    }

    if($invoice->status === 'canceled'){
        return ['error' => 'invoice_already_canceled', 'message' => 'Invoice already canceled', 'status' => 409];
    }

    $invoice->status = 'canceled';
    $invoice->cancel_reason = $reason;
    $invoice->save();

    return $invoice;
}
```

No middleware e no controller, o `ResponseApi::error` encerra e não leva `return`:

```php
public function __invoke(Request $request, Response $response, callable $next)
{
    $data = Request::post();

    $rules = [
        'reason' => 'require|max:255',
    ];

    if(!Validator::check($data, $rules)){
        ResponseApi::error('invalid_data', Validator::error()->msg, 422);
    }

    Request::share('cancelReason', trim($data['reason']));

    return $next();
}
```

Atribuição com valor padrão antes do `if`, no lugar do `else`:

```php
$dueDays = 30;

if($customer->is_premium){
    $dueDays = 60;
}
```

Três caminhos ou mais com `match`:

```php
$feeInCents = match($invoice->payment_method){
    'pix' => 0,
    'boleto' => 350,
    'credit_card' => intdiv($invoice->amount_in_cents * 3, 100),
};
```

## Errado
```php
public static function cancel($invoice, $reason)
{
    if ($invoice->status != 'paid') {
        if ($invoice->status != 'canceled') {
            $invoice->status = 'canceled';
            $invoice->cancel_reason = $reason;
            $invoice->save();
            return $invoice;
        } else {
            return ['error' => 'invoice_already_canceled', 'message' => 'Invoice already canceled', 'status' => 409];
        }
    } else {
        return ['error' => 'invoice_already_paid', 'message' => 'Invoice already paid', 'status' => 409];
    }
}

// no controller
if (is_array($canceled) && isset($canceled['error'])) {
    ResponseApi::error($canceled['error'], $canceled['message'], $canceled['status']);
    return;
} else {
    ResponseApi::success('invoice_canceled', Api::returnAttributes($canceled, ['id', 'status']));
}

if ($customer->is_premium) {
    $dueDays = 60;
} elseif ($customer->is_partner) {
    $dueDays = 45;
} else {
    $dueDays = 30;
}
```

Caminho feliz aninhado no meio, erro no fim, `return` depois do `ResponseApi::error`, `else` depois de guarda e
`elseif` em cadeia onde caberia valor padrão ou `match`.

## Como reconhecer
- `else` ou `elseif` em qualquer arquivo (`}else{`, `} else {`, `elseif(`, `else if`).
- `return;` ou `return ResponseApi::` logo depois de um `ResponseApi::error(`.
- `if` aninhado em dois níveis ou mais quando o de fora só protege o de dentro.
- `return` do caminho feliz dentro de um `if`, com o erro testado depois.
- Atribuição da mesma variável nos dois ramos de um `if/else`.

## Como corrigir
1. Inverta cada condição de erro e leve-a para o topo, saindo na hora: `return [...]` no service,
   `ResponseApi::error(...)` sem `return` no controller e no middleware.
2. Desaninhe o caminho feliz para o nível do método, depois das guardas.
3. Atribuição em dois ramos vira valor padrão antes do `if`; três ramos ou mais viram `match`.
4. Apague o `return` que segue um `ResponseApi::error` e o `else` que sobrou depois dele.
5. Se ainda sobrar um `else` que não cabe em nenhum dos três moldes, deixe-o e registre o motivo na revisão.

```php
public function cancel(): void
{
    $invoice = $this->shared('invoice', Invoice::class);
    $reason = $this->shared('cancelReason');

    $canceled = InvoiceCancelService::cancel($invoice, $reason);

    if(is_array($canceled) && isset($canceled['error'])){
        ResponseApi::error($canceled['error'], $canceled['message'], $canceled['status']);
    }

    ResponseApi::success('invoice_canceled', Api::returnAttributes($canceled, ['id', 'status', 'cancel_reason']));
}
```
