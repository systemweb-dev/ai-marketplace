# Sem ruído defensivo

## Regra
O dado é convertido e conferido uma vez, na borda; depois disso o código confia no tipo. As oito regras:

1. **Converter só uma vez, na borda.** O middleware entrega no `Request::share` já tipado; o payload de fornecedor
   é convertido na integração; DECIMAL e SUM viram `int` no método do model. Depois disso, nenhum cast.
2. **Sem `(int)` em id ou coluna INT do model**, e sem cast antes de parâmetro tipado.
3. **`??` só no que é opcional de verdade**, nunca em chave que a validação já garantiu.
4. **`json_decode` sempre com `JSON_THROW_ON_ERROR`**, sem indexar o resultado direto.
5. **Existência e vazio com `if($x)` ou `if(!$x)` direto**, sem `empty()`, `count() > 0`, `isset()` de variável ou
   `=== null`. O `=== null` só quando `0` ou `''` são valores válidos.
6. **Ternário aninhado proibido:** `match` ou guard clause.
7. **No máximo duas funções aninhadas por linha;** acima disso, uma variável com nome.
8. **Sem `@`**, exceto em limpeza com comentário do motivo; sem `print_r`, `var_dump`, `dd` ou `die`.

## Por quê
O ruído defensivo é sintoma de uma causa só: **o dado não foi tipado na borda**, e cada camada se protege de novo
por desconfiança. O `(int) $company->id` repetido 150 vezes, o `?? ''` em chave obrigatória e o `empty()` em tudo
escondem a dúvida real (o dado pode faltar ou não?) e mascaram bug: um `?? 0` em chave que devia existir troca um
erro visível por um valor errado gravado no banco. `json_decode` sem exceção devolve `null` calado e o índice
seguinte vira warning longe da causa. Ternário aninhado e quatro funções numa linha não se leem de primeira. `@`
esconde o erro e `dd` esquecido derruba a produção.

## Certo
1. A conversão acontece no `share` do middleware e no método do model; o service recebe o tipo pronto:

```php
Request::share('invoice', [
    'id_customer' => (int) $data['id_customer'],
    'amount_in_cents' => (int) $data['amount_in_cents'],
]);
```

```php
public static function sumOpenByCompany(int $idCompany): int
{
    // o builder do core não faz SUM
    $sql = 'SELECT COALESCE(SUM(amount_in_cents), 0) AS total FROM invoice WHERE id_company = :id_company AND status = :status';

    $row = DB::query($sql, ['id_company' => $idCompany, 'status' => 'open'])->get(true);

    return (int) $row['total'];
}
```

2. O id da model e o parâmetro tipado passam como estão:

```php
$invoice = Invoice::findByCompany($company->id, $invoiceId);
```

3. A chave validada é lida direto; o `??` fica para o que pode faltar de verdade:

```php
$description = $invoiceData['description'];
$notes = $invoiceData['notes'] ?? null;
```

4. `json_decode` lança no JSON quebrado, e o resultado vai para uma variável antes de indexar:

```php
$payload = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
$status = $payload['status'];
```

5. Existência e vazio com o valor direto; `=== null` só onde `0` é válido:

```php
if(!$invoice){
    return ['error' => 'invoice_not_found', 'message' => 'Invoice not found', 'status' => 404];
}

if(!$items){
    return ['error' => 'items_required', 'message' => 'Items are required', 'status' => 422];
}

// desconto zero é válido: só a ausência cai no padrão
if($discountInCents === null){
    $discountInCents = $customer->default_discount_in_cents;
}
```

`Collection` é objeto e sempre é verdadeira: para ela, `if(!$invoices->count())`.

6. Três caminhos ou mais viram `match`:

```php
$label = match($invoice->status){
    'paid' => 'Paid',
    'canceled' => 'Canceled',
    default => 'Open',
};
```

7. Cada passo com nome, no máximo duas funções por linha:

```php
$words = str_replace('_', ' ', $name);
$hyphenated = preg_replace('/\s+/', '-', trim($words));
$slug = strtolower($hyphenated);
```

8. `@` só em limpeza, com o motivo:

```php
// o arquivo temporário pode já ter sido apagado pelo SO; a falha aqui não muda nada
@unlink($temporaryPath);
```

## Errado
```php
// 1 e 2: cast em todas as camadas, inclusive no id da model e antes de parâmetro tipado
$invoice = Invoice::findByCompany((int) $this->company->id, (int) $invoiceData['id_invoice']);
$total = (int) InvoiceTotalService::sum((int) $invoice->id);

// 3: ?? em chave que o Validator já exigiu
$description = $invoiceData['description'] ?? '';

// 4: sem exceção e indexado direto
$status = json_decode($body, true)['status'];

// 5: empty, count e === null onde o valor direto basta
if (empty($invoice)) { ... }
if (count($items) > 0) { ... }
if ($customer === null) { ... }

// 6: ternário aninhado
$label = $invoice->status == 'paid' ? 'Paid' : ($invoice->status == 'canceled' ? 'Canceled' : 'Open');

// 7: quatro funções aninhadas numa linha
$slug = strtolower(trim(preg_replace('/\s+/', '-', str_replace('_', ' ', $name))));

// 8: @ sem motivo e depuração esquecida
$file = @file_get_contents($path);
print_r($invoice);
dd($payload);
```

## Como reconhecer
- `(int)`, `(float)`, `(string)`, `intval(`, `floatval(` fora do `Request::share` do middleware, da integração e do
  retorno de DECIMAL/SUM no model; em especial sobre `->id`, `$this->shared(` ou argumento de parâmetro já tipado.
- `?? ''`, `?? 0`, `?? null`, `?? []` em chave que a regra do `Validator::check` marca como `require`.
- `json_decode(` sem `JSON_THROW_ON_ERROR`, ou `json_decode(...)[`.
- `empty(`, `count(...) > 0`, `count(...) == 0`, `isset($variavel)` e `=== null`/`!== null` em teste de existência,
  sem um comentário dizendo que `0` ou `''` vale.
- `? ... : (... ? ... : ...)` ou dois `?` de ternário na mesma expressão.
- Linha com três funções ou mais aninhadas (`a(b(c(`).
- `@` antes de chamada sem comentário de limpeza; `print_r(`, `var_dump(`, `var_export(`, `dd(`, `dump(`, `die(`.

## Como corrigir
1. Ache a borda do dado (o middleware, a integração ou o método do model) e faça a conversão lá, uma vez, já no
   tipo final. Se a borda não converte, corrija-a antes (`validacao-no-middleware.md`).
2. Apague os casts das camadas de dentro e ponha tipo nos parâmetros (`tipos-e-comentarios.md`).
3. Em cada `??`, pergunte se a chave pode faltar. Se não pode, apague o `??`; se pode, mantenha e confira que a
   validação a trata como opcional.
4. Troque `json_decode($x, true)` por `json_decode($x, true, 512, JSON_THROW_ON_ERROR)` numa variável, e indexe
   depois.
5. Troque `empty($x)`, `count($x) > 0` e `$x === null` por `if($x)`/`if(!$x)`; mantenha `=== null`, com
   comentário, onde `0` ou `''` vale.
6. Troque ternário aninhado por `match` ou por guard clause (`guard-clause-sem-else.md`).
7. Quebre a linha com mais de duas funções aninhadas em variáveis com nome.
8. Apague `print_r`, `var_dump` e `dd`. Troque `@` por tratamento real ou, em limpeza, deixe-o com o comentário.

```php
$invoice = Invoice::findByCompany($company->id, $invoiceData['id_invoice']);

if(!$invoice){
    return ['error' => 'invoice_not_found', 'message' => 'Invoice not found', 'status' => 404];
}

$label = match($invoice->status){
    'paid' => 'Paid',
    'canceled' => 'Canceled',
    default => 'Open',
};
```
