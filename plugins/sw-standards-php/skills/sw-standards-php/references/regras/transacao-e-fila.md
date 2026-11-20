# Transação e fila

## Regra
Quando uma operação grava em mais de uma tabela, o **service** abre a transação com `DB::startTransaction()`,
confirma com `DB::commit()` e, em qualquer falha, desfaz com `DB::roolback()` (assim mesmo, com dois "o": é o
nome do método no core) e devolve o array `server_error`. Controller, middleware, model e job nunca abrem
transação. O `try/catch` do service existe só para transação e integração externa. Fila, e-mail e webhook saem
**só depois do commit**, fora do `try`, e o payload da fila leva **só ids**: quem consome busca o dado atual no
banco.

## Por quê
Sem transação, a falha na segunda tabela deixa a primeira gravada pela metade (fatura sem itens, pedido sem
pagamento). O service é quem conhece a operação inteira, por isso é ele que abre e fecha. Publicar dentro da
transação manda a mensagem antes de o dado existir: o job consome, não acha o registro, e o rollback ainda pode
apagar o que a mensagem anunciou. Payload com o registro inteiro envelhece na fila (o job grava um valor que já
mudou) e espalha dado pessoal pelo broker; com o id, o job lê o estado do momento.

## Certo
```php
namespace App\LogicApp\Services\Billing;

use App\LogicApp\Enums\EQueue;
use App\LogicApp\Models\Invoice;
use App\LogicApp\Models\InvoiceItem;
use SysWeb\Database\DB;
use SysWeb\Jobs\Queue;
use SysWeb\Logger\DiscordLogger;
use SysWeb\Logger\ELogger;

final class InvoiceCreateService
{
    public static function create(int $idCompany, array $invoiceData): Invoice|array
    {
        DB::startTransaction();

        try{
            $invoice = new Invoice();
            $invoice->id_company = $idCompany;
            $invoice->id_customer = $invoiceData['id_customer'];
            $invoice->amount_in_cents = $invoiceData['amount_in_cents'];
            $invoice->status = 'open';

            $created = $invoice->insert();

            // o builder não lança exceção quando a escrita falha: pedido ao framework
            if(!$created){
                throw new \RuntimeException('invoice insert failed');
            }

            foreach($invoiceData['items'] as $itemData){
                $item = new InvoiceItem();
                $item->id_invoice = $created->id;
                $item->description = $itemData['description'];
                $item->amount_in_cents = $itemData['amount_in_cents'];

                if(!$item->insert()){
                    throw new \RuntimeException('invoice_item_insert_failed');
                }
            }

            DB::commit();
        }catch(\Throwable $exception){
            DB::roolback();
            DiscordLogger::setTitle('Invoice create failed');
            DiscordLogger::send("invoice create company {$idCompany}: {$exception->getMessage()}", ELogger::ERROR);

            return ['error' => 'server_error', 'message' => 'Unexpected error', 'status' => 500];
        }

        Queue::send(EQueue::SEND_INVOICE_EMAIL->queue(), ['id_invoice' => $created->id]);

        return $created;
    }
}
```

Operação que grava numa tabela só não precisa de transação nem de `try`: o `insert()` ou o `save()` direto, e o
erro inesperado vai para o tratador global.

## Errado
```php
// no controller
public function create()
{
    DB::startTransaction();
    try {
        $invoice = InvoiceService::create($this->company->id, Request::post());
        Queue::send('send-invoice-email', $invoice->toArray());
        InvoiceItemService::createAll($invoice->id, Request::post('items'));
        DB::commit();
        ResponseApi::success('ok', $invoice);
    } catch (\Exception $e) {
        DB::rollback();
        ResponseApi::error('error', $e->getMessage(), 500);
    }
}
```

Transação aberta no controller, fila publicada antes do commit (o job pode rodar antes dos itens existirem, e o
rollback não desfaz a mensagem), payload com o model inteiro, `DB::rollback()` que não existe no core (vira erro
fatal justamente na hora da falha) e `getMessage()` devolvido ao cliente.

## Como reconhecer
- `DB::startTransaction`, `DB::commit` ou `DB::roolback` em `Controllers/`, `Models/`, middleware ou `jobs/`.
- `DB::rollback(` ou `DB::rollBack(`: o método do core é `roolback`.
- Service que chama `insert()`, `save()` ou `remove()` em dois ou mais models sem `DB::startTransaction`.
- `DB::startTransaction` sem `DB::roolback()` no `catch`, ou `catch` que não devolve o array `server_error`.
- `Queue::send(`, envio de e-mail ou chamada de webhook entre o `startTransaction` e o `commit`, ou dentro do
  `try`.
- Payload de `Queue::send` com `->toArray()`, `(array) $model`, o model inteiro ou campos como nome, e-mail,
  valor ou status em vez do id.
- `try{` em service sem transação nem integração externa no corpo.

## Como corrigir
1. Leve a transação do controller (ou do model) para o service que faz a operação inteira; se a operação está
   espalhada em dois services, crie um que orquestre os dois.
2. Envolva só as escritas no `try`: `DB::startTransaction()` antes, `DB::commit()` como última linha do `try`.
3. No `catch(\Throwable $exception)`: `DB::roolback()`, log no `DiscordLogger` com o contexto e `return` do array
   `server_error`, sem a mensagem.
4. Mova `Queue::send`, e-mail e webhook para depois do bloco, quando o commit já aconteceu.
5. Reduza o payload aos ids (`['id_invoice' => $created->id]`) e faça o job buscar o registro pelo model.
6. Apague o `try/catch` do controller; o erro esperado volta como array do service.

```php
DB::startTransaction();

try{
    $order->status = 'paid';
    $order->save();

    $payment = new Payment();
    $payment->order_id = $order->id;
    $payment->amount_in_cents = $order->amount_in_cents;
    $payment->insert();

    DB::commit();
}catch(\Throwable $exception){
    DB::roolback();
    DiscordLogger::setTitle('Order payment failed');
    DiscordLogger::send("order {$order->id}: {$exception->getMessage()}", ELogger::ERROR);

    return ['error' => 'server_error', 'message' => 'Unexpected error', 'status' => 500];
}

Queue::send(EQueue::SEND_PAYMENT_RECEIPT->queue(), ['order_id' => $order->id]);

return $order;
```

## Enquanto o core não corrigir
Vale para o core até a 1.11.0, inclusive; confira o CHANGELOG do core instalado (`composer.lock`).

- **O rollback chama `roolback`.** `DB::rollback()` não existe e quebra com erro fatal. Use `DB::roolback()`
  até o core ganhar o nome certo.
- **Erro de escrita do builder não vira exceção.** O core faz `trigger_error(E_USER_ERROR)` no `insert`, no
  `update` e na conexão, e o `catch(\Throwable)` não vê. Confira o retorno do `insert()` (devolve `null` quando
  falha) e lance uma exceção dentro do `try` para cair no rollback, com o comentário do pedido ao framework. Se o
  processo morrer antes, a transação não foi confirmada e o banco a desfaz quando a conexão fecha.
