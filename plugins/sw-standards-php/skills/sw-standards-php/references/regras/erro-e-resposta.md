# Erro e resposta

## Regra
Erro esperado sai com `ResponseApi::error('codigo_em_snake_case', 'Frase em inglês', status)`, com o **status HTTP
sempre explícito** (422, 401, 403, 404, 409, 500). O service não responde: no erro devolve
`['error' => código, 'message' => frase, 'status' => http]` e, no sucesso, o dado em si; o controller testa o
`error` e responde. Toda saída de sucesso passa por `Api::returnAttributes()` com a lista explícita de campos,
nunca o model nem `toArray()` direto. Erro inesperado não é capturado: o tratador global do projeto
(`config/ExceptionHandler.php`, cópia de `assets/exception-handler.php`) loga o detalhe e responde `server_error` 500. Nunca
`getMessage()`, trace ou SQL na resposta. O formato do erro é o da casa, salvo quando o projeto registrou outro
em `docs/sw-standards/config.md`.

## Por quê
A assinatura do core é `error(string $message = '', array|object|string $data = [], int $status = 200)`: o
primeiro argumento é o código que o front trata e o segundo é a frase. Sem o terceiro, o erro sai com HTTP 200 e
o cliente acha que deu certo. Lista explícita de campos impede vazar coluna nova (senha, token, dado interno)
quando a tabela cresce. A mensagem da exceção carrega SQL, caminho e às vezes segredo: ela vai para o log, não
para o cliente. O model do core não é array; testar com `isset($x['error'])` quebra no sucesso — use
`is_array($x) && isset($x['error'])`.

## Certo
O service devolve o dado ou o array de erro:

```php
public static function cancel(Invoice $invoice, string $reason): Invoice|array
{
    if($invoice->status === 'paid'){
        return ['error' => 'invoice_already_paid', 'message' => 'Invoice already paid', 'status' => 409];
    }

    $invoice->status = 'canceled';
    $invoice->cancel_reason = $reason;
    $invoice->save();

    return $invoice;
}
```

O controller responde, com status e lista de campos:

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

O service só captura quando chama integração externa (ou abre transação), e devolve `server_error` sem a
mensagem:

```php
public static function refund(Invoice $invoice): Invoice|array
{
    try{
        $refund = Acme::instance()->refund($invoice->gateway_charge_id);
    }catch(\Throwable $exception){
        DiscordLogger::setTitle('Refund failed');
        DiscordLogger::send("refund invoice {$invoice->id}: {$exception->getMessage()}", ELogger::ERROR);

        return ['error' => 'server_error', 'message' => 'Unexpected error', 'status' => 500];
    }

    $invoice->status = 'refunded';
    $invoice->gateway_refund_id = $refund['id'];
    $invoice->save();

    return $invoice;
}
```

O tratador global fica em `config/ExceptionHandler.php` (cópia de `assets/exception-handler.php`, feita na
etapa 0) e é carregado no `www/index.php`, antes do `new SysWeb\System()`:

```php
require __DIR__ . '/../config/ExceptionHandler.php';
```

## Errado
```php
public function cancel()
{
    try {
        $result = InvoiceService::cancel(Router::param('id'));
        if ($result === false) {
            ResponseApi::error('Invoice already paid');
        }
        ResponseApi::success('ok', $result->toArray());
    } catch (\Exception $e) {
        ResponseApi::error('error', $e->getMessage(), 400);
    }
}

// no service
if ($invoice->status == 'paid') {
    ResponseApi::error('invoice_already_paid', 'Invoice already paid', 409);
}
```

Erro sem status (sai 200), frase no lugar do código, service que devolve `false` sem dizer o motivo, service
respondendo HTTP, model inteiro na resposta e `getMessage()` devolvido ao cliente.

## Como reconhecer
- `ResponseApi::error(` com menos de três argumentos, ou com o primeiro argumento em frase em vez de snake_case.
- `getMessage()`, `getTrace`, `getFile`, `getLine` ou `$e` dentro de `ResponseApi::` ou de array devolvido ao
  cliente.
- `ResponseApi::` ou `exit` dentro de `Services/`, `Models/` ou `Helpers/`.
- Service que devolve `false`, `null` ou lança exceção para erro esperado.
- `isset($x['error'])` sem o `is_array($x) &&` na frente: o model do core não é array; testar com
  `isset($x['error'])` quebra no sucesso — use `is_array($x) && isset($x['error'])`.
- `ResponseApi::success(` recebendo model, `->toArray()`, `Collection` ou resultado de query sem
  `Api::returnAttributes`.
- `try{`/`catch` em controller, middleware ou model; em service, `catch` que não envolve transação ou integração.
- `www/index.php` sem o `require __DIR__ . '/../config/ExceptionHandler.php';` antes do `new SysWeb\System()`,
  ou `config/ExceptionHandler.php` sem `set_exception_handler`. Projeto com os dois está preparado.
- Formato de erro diferente do registrado em `docs/sw-standards/config.md`. Sem registro, pergunte ao dono qual
  formato o projeto usa e grave a resposta ali antes de corrigir.

## Como corrigir
1. Leia `docs/sw-standards/config.md`. Se o formato do erro não estiver lá, pergunte e grave.
2. Em todo `ResponseApi::error`, ponha o código em snake_case, a frase em inglês e o status explícito: 422
   validação, 401 sem autenticação, 403 sem permissão, 404 não encontrado, 409 conflito de estado, 500 inesperado.
3. No service, troque `ResponseApi::error`, `false` ou exceção de erro esperado por
   `return ['error' => ..., 'message' => ..., 'status' => ...]`, como guard clause no topo.
4. No controller, responda o array do service com o bloco
   `if(is_array($resultado) && isset($resultado['error']))` e passe o sucesso por
   `Api::returnAttributes($dado, [campos])`.
5. Apague os `try/catch` de controller, middleware, model e de service sem transação ou integração. Registre o
   tratador global (etapa 0) se ainda não houver.
6. Onde sobrou captura legítima, logue a mensagem e responda `server_error` 500, sem a mensagem:

```php
try{
    $refund = Acme::instance()->refund($invoice->gateway_charge_id);
}catch(\Throwable $exception){
    DiscordLogger::setTitle('Refund failed');
    DiscordLogger::send("refund invoice {$invoice->id}: {$exception->getMessage()}", ELogger::ERROR);

    return ['error' => 'server_error', 'message' => 'Unexpected error', 'status' => 500];
}
```

## Enquanto o core não corrigir
Vale para o core até a 1.11.0, inclusive; a nota sai quando o core ganhar um tratador de exceção próprio (confira
o CHANGELOG do core instalado).

- O tratador global é do projeto: `assets/exception-handler.php`, copiado na etapa 0 para
  `config/ExceptionHandler.php` e carregado por `require` no `www/index.php` antes do `new SysWeb\System()`.
- Erro do builder (`DB::table()->select()->all()`) e de conexão não vira exceção: o core faz
  `trigger_error(E_USER_ERROR)`. Em prod ele chega ao tratador; **em dev, o `Error.php` do core responde sozinho
  com SQLSTATE, arquivo e linha**. Não é vazamento em produção, mas não confie na resposta de dev para conferir o
  formato do erro.
- O `ResponseApi::error` tem `$status = 200` por padrão no core; por isso o status é sempre passado.
