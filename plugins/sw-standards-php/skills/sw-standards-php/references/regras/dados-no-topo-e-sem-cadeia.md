# Dados no topo e sem cadeia no cabeçalho

## Regra
Tudo que chega de fora do método é lido em variáveis com nome no começo dele, antes do primeiro `if`: o
`$this->shared()` no controller (inclusive a empresa, `$this->shared('company')`), `Request::post()`,
`Request::get()` e `Router::param()` no middleware, e `sw_config()` em qualquer camada. Nenhum `foreach`, `if`,
`while`, `switch` ou `return` tem query ou cadeia de chamadas (`->a()->b()`) no cabeçalho: o resultado vai antes
para uma variável com nome, e o cabeçalho só usa essa variável. Chamada simples, de um nível e sem query, continua
valendo como argumento ou condição (`Api::returnAttributes(...)` dentro do `ResponseApi::success`,
`if(!in_array($status, $allowed, true))`).

## Por quê
Quem abre o método vê de uma vez do que ele depende, sem caçar leituras no meio da lógica. A mesma entrada não é
lida duas vezes com resultados diferentes. Query no cabeçalho de laço esconde a ida ao banco e não deixa dar nome
ao que veio; cadeia no cabeçalho não tem onde parar no debugger nem como ver o valor intermediário. A variável com
nome documenta o que o dado é.

## Certo
O controller lê tudo no topo:

```php
public function remind(): void
{
    $company = $this->shared('company', Company::class);
    $reminderData = $this->shared('reminder');

    $reminded = InvoiceReminderService::remindOverdue($company->id, $reminderData['channel']);

    if(is_array($reminded) && isset($reminded['error'])){
        ResponseApi::error($reminded['error'], $reminded['message'], $reminded['status']);
    }

    ResponseApi::success('reminders_sent', ['total' => $reminded['total']]);
}
```

O service guarda a consulta numa variável antes do laço:

```php
public static function remindOverdue(int $idCompany, string $channel): array
{
    $maxReminders = sw_config('billing')['max_reminders'];
    $invoices = Invoice::listOverdueByCompany($idCompany);

    if(!$invoices->count()){
        return ['error' => 'no_overdue_invoices', 'message' => 'No overdue invoices', 'status' => 404];
    }

    $total = 0;

    foreach($invoices as $invoice){
        if($invoice->reminders_sent >= $maxReminders){
            continue;
        }

        Mailer::instance()->sendInvoiceReminder($invoice, $channel);
        $total++;
    }

    return ['total' => $total];
}
```

## Errado
```php
public function remind()
{
    if ($this->shared('company')->plan === 'free') {
        ResponseApi::error('plan_not_allowed', 'Plan not allowed', 403);
    }

    foreach (Invoice::where(['id_company =' => $this->shared('company')->id])->get()->toArray() as $invoice) {
        if ($invoice['reminders_sent'] >= sw_config('billing')['max_reminders']) {
            continue;
        }
        Mailer::instance()->sendInvoiceReminder($invoice, Request::post()['channel']);
    }

    return ResponseApi::success('reminders_sent', Invoice::where(['id_company =' => $this->shared('company')->id])->get()->count());
}
```

A empresa é lida três vezes, a entrada da request e a config aparecem no meio do laço, há query com cadeia no
cabeçalho do `foreach` e do `return`, e a mesma consulta roda duas vezes.

## Como reconhecer
- `$this->shared(`, `Request::post(`, `Request::get(`, `Router::param(` ou `sw_config(` depois do primeiro `if`
  do método, ou repetidos com a mesma chave.
- `foreach (`/`foreach(` cujo cabeçalho tem `::where(`, `::find`, `DB::`, `->get()`, `->toArray()`, `->first()`
  ou dois `->` seguidos (`->a()->b()`).
- `if(`, `while(`, `switch(` ou `return` com `::where(`, `DB::`, `->get()` ou cadeia de duas chamadas ou mais.
- A mesma chamada repetida no método (sinal de que faltou guardar numa variável).

## Como corrigir
1. Junte no topo do método uma variável por dado de fora, com o nome do que ele é (`$company`, `$reminderData`,
   `$maxReminders`), e troque as leituras espalhadas por ela.
2. Para cada cabeçalho com query ou cadeia, guarde o resultado numa variável na linha de cima e use a variável no
   cabeçalho. Se for query fora do model, leve-a antes para um método do model (`banco-no-model.md`).
3. Apague o `->toArray()` que só existia para o laço: itere a `Collection` e use `$invoice->coluna`.

O caso mais comum, `foreach (Invoice::where([...])->get()->toArray() as $invoice)`, fica assim:

```php
$invoices = Invoice::listOverdueByCompany($idCompany);

foreach($invoices as $invoice){
    Mailer::instance()->sendInvoiceReminder($invoice, $channel);
}
```
