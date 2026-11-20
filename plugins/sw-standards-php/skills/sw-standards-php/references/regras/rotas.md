# Rotas

## Regra
Toda URL da API tem versão: `v1/recurso`. Toda rota POST, PUT, PATCH ou DELETE e toda rota com `{id}` tem
middleware (`middlewareBefore`): o `Validate{Recurso}{Ação}Middleware` na escrita e o `{Recurso}ExistsMiddleware`
(ou o mecanismo de escopo registrado no projeto) na rota com id. O apelido do middleware em
`config/Middleware.php` é o nome da classe sem o sufixo `Middleware`, em camelCase
(`ValidateInvoiceCreateMiddleware` vira `validateInvoiceCreate`). Há um arquivo de rotas por tema
(`app/<Tema>/Rotas.php`), com as rotas agrupadas por recurso, um comentário curto no topo de cada grupo.
Middleware que vale para o tema inteiro (CORS, log, auth) fica em `app/<Tema>/Middleware.php`, não repetido em
cada rota.

## Por quê
A versão na URL deixa mudar o contrato sem quebrar o app que já está publicado. Escrita e rota com id são as
portas de entrada de dado e de acesso a registro de outra empresa: sem middleware, a validação e o escopo caem no
controller ou não acontecem. Apelido derivado do nome da classe dispensa abrir o `config/Middleware.php` para
saber qual classe roda, e evita dois apelidos para a mesma classe. Rotas agrupadas por recurso mostram de uma vez
tudo o que a API faz com uma fatura.

## Certo
`app/Api/Rotas.php`:

```php
// Faturas
Rota::authJwt('', function ($auth) {
    Rota::get('v1/invoices')->controller('invoice')->method('index')->auth($auth)->middlewareBefore('validateInvoiceList');
    Rota::post('v1/invoices')->controller('invoice')->method('create')->auth($auth)->middlewareBefore('validateInvoiceCreate');
    Rota::get('v1/invoices/{id}')->controller('invoice')->method('show')->auth($auth)->middlewareBefore('invoiceExists');
    Rota::put('v1/invoices/{id}')->controller('invoice')->method('update')->auth($auth)->middlewareBefore(['invoiceExists', 'validateInvoiceUpdate']);
    Rota::delete('v1/invoices/{id}')->controller('invoice')->method('cancel')->auth($auth)->middlewareBefore('invoiceExists');
});
```

`config/Middleware.php`, com o apelido igual ao nome da classe sem o sufixo:

```php
return [
    'invoiceExists' => \Middleware\InvoiceExistsMiddleware::class,
    'validateInvoiceCreate' => \Middleware\ValidateInvoiceCreateMiddleware::class,
    'validateInvoiceList' => \Middleware\ValidateInvoiceListMiddleware::class,
    'validateInvoiceUpdate' => \Middleware\ValidateInvoiceUpdateMiddleware::class,
];
```

Vários middlewares na mesma rota vão num array só, na ordem em que rodam: primeiro o escopo, depois a validação.

## Errado
```php
Rota::post('invoices/create')->controller('invoice')->method('create');
Rota::get('invoice/{id}')->controller('invoice')->method('show');
Rota::put('v1/invoices/{id}')->controller('invoice')->method('update')->middlewareBefore('invoiceExists')->middlewareBefore('invoiceValidation');
Rota::get('v1/customers')->controller('customer')->method('index');
Rota::get('v1/invoices')->controller('invoice')->method('index');

// config/Middleware.php
'invoiceValidation' => \Middleware\ValidateInvoiceUpdateMiddleware::class,
'checkInvoice' => \Middleware\InvoiceExistsMiddleware::class,
```

URL sem versão e com verbo, escrita e rota com `{id}` sem middleware, dois `middlewareBefore` encadeados (o
segundo substitui o primeiro, e o escopo some), recursos misturados e apelido que não diz qual classe roda.

## Como reconhecer
- `Rota::get|post|put|patch|delete('` com URL que não começa por `v1/` (ou pela versão do projeto).
- `Rota::post`, `Rota::put`, `Rota::patch` ou `Rota::delete` sem `->middlewareBefore(`.
- URL com `{id}` (ou `{uuid}`, `{code}`) sem o middleware de existência e escopo.
- `->middlewareBefore(...)->middlewareBefore(...)` na mesma rota.
- Em `config/Middleware.php`, apelido diferente de `lcfirst(<classe sem "Middleware">)`.
- Rotas de um tema fora de `app/<Tema>/Rotas.php`, ou rotas do mesmo recurso espalhadas pelo arquivo.
- O mesmo middleware (`cors`, `auth`) repetido em todas as rotas em vez de `app/<Tema>/Middleware.php`.

## Como corrigir
1. Ponha a versão nas URLs (`v1/`). Em API já publicada, combine com o dono: mantenha a rota velha apontando para
   o mesmo controller até o cliente migrar.
2. Para cada escrita sem middleware, crie o `Validate{Recurso}{Ação}Middleware` (veja `validacao-no-middleware.md`);
   para cada rota com id, o `{Recurso}ExistsMiddleware` (veja `seguranca-e-config.md`).
3. Renomeie os apelidos em `config/Middleware.php` para o nome da classe sem o sufixo, em camelCase, e troque nas
   rotas.
4. Junte os `middlewareBefore` encadeados num array só.
5. Reordene o `Rotas.php` por recurso, com um comentário curto no topo de cada grupo; middleware do tema inteiro
   vai para `app/<Tema>/Middleware.php` com `$middleware->before('nome')`.

```php
// Clientes
Rota::authJwt('', function ($auth) {
    Rota::get('v1/customers')->controller('customer')->method('index')->auth($auth)->middlewareBefore('validateCustomerList');
    Rota::post('v1/customers')->controller('customer')->method('create')->auth($auth)->middlewareBefore('validateCustomerCreate');
    Rota::put('v1/customers/{id}')->controller('customer')->method('update')->auth($auth)->middlewareBefore(['customerExists', 'validateCustomerUpdate']);
});
```

## Enquanto o core não corrigir
Vale para o core até a 1.11.0, inclusive; confira o CHANGELOG do core instalado.

- **`middlewareBefore` atribui, não acumula.** Cada chamada substitui a anterior na mesma rota, então dois
  `middlewareBefore` seguidos deixam rodar só o último, em silêncio. Passe sempre todos num array:
  `->middlewareBefore(['invoiceExists', 'validateInvoiceUpdate'])`. O mesmo vale para `middlewareAfter`.
