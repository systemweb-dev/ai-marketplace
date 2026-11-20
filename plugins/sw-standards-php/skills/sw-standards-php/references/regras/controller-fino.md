# Controller fino

## Regra
O controller só tem métodos públicos de ação, um por rota. Cada ação lê `$this->shared()` no topo, chama um
service e responde (`ResponseApi::success`/`ResponseApi::error` na API, `$this->view()` no website). Nada de
`try/catch`, query, `Model::where`, `find`/`save`/`insert`/`remove`, método privado ou regra de negócio no
controller. Erro é testado logo no começo e sai na hora (guard clause), sem `else`; o caminho feliz fica
embaixo. `ResponseApi::error` já encerra a execução, então um `return` depois dele é ruído.

## Por quê
Thin Controller e Service Layer: o controller é a cola entre a rota e o service, e a regra fica num lugar só,
testável sem HTTP. Método privado no controller é regra escondida que nenhum outro ponto reaproveita. O
`ResponseApi` termina com `exit()` (o `Response::json` do core encerra), por isso o `return` e o `else` depois de
um erro nunca rodam.

## Certo
```php
namespace App\Api\Controllers;

use App\LogicApp\Services\Billing\InvoiceCancelService;
use App\LogicApp\Models\Invoice;
use SysWeb\Api\Api;
use SysWeb\Api\ResponseApi;
use SysWeb\Controller;

final class InvoiceController extends Controller
{
    public function show(): void
    {
        $invoice = $this->shared('invoice', Invoice::class);

        ResponseApi::success('invoice_found', Api::returnAttributes($invoice, ['id', 'status', 'amount_in_cents']));
    }

    public function cancel(): void
    {
        $invoice = $this->shared('invoice', Invoice::class);
        $reason = $this->shared('cancelReason');

        $canceled = InvoiceCancelService::cancel($invoice, $reason);

        if(is_array($canceled) && isset($canceled['error'])){
            ResponseApi::error($canceled['error'], $canceled['message'], $canceled['status']);
        }

        ResponseApi::success('invoice_canceled', Api::returnAttributes($canceled, ['id', 'status', 'canceled_at']));
    }
}
```

## Errado
```php
class InvoiceController extends Controller
{
    public function cancel()
    {
        try {
            $invoice = Invoice::where(['id =' => Router::param('id')])->first();
            if (!$invoice) {
                ResponseApi::error('invoice_not_found', 'Invoice not found', 404);
                return;
            } else {
                if ($invoice->status == 'paid') {
                    return ResponseApi::error('invoice_already_paid', 'Invoice already paid');
                }
                $invoice->status = 'canceled';
                $invoice->save();
                $this->notifyCustomer($invoice);
                ResponseApi::success('invoice_canceled', $invoice);
            }
        } catch (\Exception $e) {
            ResponseApi::error('error', $e->getMessage());
        }
    }

    private function notifyCustomer($invoice) { ... }
}
```

Query, escrita, regra de negócio, método privado, `try/catch` devolvendo `getMessage()`, `return` depois do
`ResponseApi::error`, `else` depois de guard clause e erro sem status.

## Como reconhecer
- Em `app/**/Controllers/`: `private function`, `protected function` (fora de `init()`), `try{`/`try {`,
  `catch`, `DB::`, `::where(`, `::find(`, `->save(`, `->insert(`, `->remove(`, `new <Model>`.
- `return;` ou `return ResponseApi::` logo depois de `ResponseApi::error(`.
- `else` ou `elseif` em ação de controller.
- Ação com mais do que: leitura de `shared()`, uma chamada de service, um `if` de erro e a resposta.
  `if` que decide regra de negócio (status, permissão, cálculo) é sinal de regra no lugar errado.
- Model ou `toArray()` direto na resposta, sem `Api::returnAttributes` (ver `erro-e-resposta.md`).

## Como corrigir
1. Mova a busca do registro para o `{Recurso}ExistsMiddleware` (busca, 404 e `Request::share`) e a validação
   para o `Validate{Recurso}{Ação}Middleware` (ver `validacao-no-middleware.md`).
2. Mova regra de negócio, escrita e métodos privados para um service em `Services/<Domínio>/` (ver
   `services-e-integracoes.md`). O service devolve o dado ou o array de erro.
3. Apague o `try/catch`: o erro inesperado vai para o tratador global (ver `erro-e-resposta.md`).
4. Troque `if/else` por guard clause e apague o `return` que segue um `ResponseApi::error`.
5. Deixe a ação com a forma do bloco abaixo.

```php
public function cancel(): void
{
    $invoice = $this->shared('invoice', Invoice::class);
    $reason = $this->shared('cancelReason');

    $canceled = InvoiceCancelService::cancel($invoice, $reason);

    if(is_array($canceled) && isset($canceled['error'])){
        ResponseApi::error($canceled['error'], $canceled['message'], $canceled['status']);
    }

    ResponseApi::success('invoice_canceled', Api::returnAttributes($canceled, ['id', 'status', 'canceled_at']));
}
```
