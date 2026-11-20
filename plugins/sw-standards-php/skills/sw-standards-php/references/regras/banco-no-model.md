# Banco no model

## Regra
Fora do model ninguém monta query: nada de `DB::`, `Model::where(...)` ou SQL em controller, middleware, service,
job ou helper. Todo filtro é um método estático com nome no model, com tipo de retorno: `findBy{Campo}()` (um ou
`null`), `listBy{Filtro}()` (lista), `countBy…()`, `existsBy…()` e verbo para ação em lote (`markAsPaid()`).
Dentro do model, o builder vem primeiro; `DB::query` só quando o builder não dá conta, com placeholder nomeado e
um comentário do motivo. Escrita pelo ORM: `find`, alterar e `save()`; `new` e `insert()`; `remove()`. O service
pode `find`, `new`, `save`, `insert` e `remove`; o controller não faz nem busca nem escrita. Nenhuma query nem
relação dentro de laço: traga tudo antes, por um método do model, e monte um mapa por id. Cada model tem os
próprios métodos: sem trait para filtro repetido.

## Por quê
Active Record com consulta nomeada: quem lê `Invoice::listOverdueByCompany()` sabe o que vem sem abrir SQL, a
mesma consulta não é reescrita em cinco lugares e o escopo por empresa fica num lugar só. Query em laço (N+1)
derruba o banco quando a lista cresce. Trait de filtro esconde de qual tabela a consulta é e quebra quando uma
tabela foge do formato.

## Certo
```php
namespace App\LogicApp\Models;

use SysWeb\Collection\Collection;
use SysWeb\Database\DB;
use SysWeb\Model\Model;

final class Invoice extends Model
{
    protected static $_table = 'invoice';

    public static function findByCompany(int $idCompany, int $id): ?self
    {
        return static::where(['id_company =' => $idCompany, 'AND' => ['id =' => $id]])->first();
    }

    public static function listByCompany(int $idCompany): Collection
    {
        return static::where(['id_company =' => $idCompany])->get();
    }

    public static function existsByNumber(int $idCompany, string $number): bool
    {
        $invoice = static::where(['id_company =' => $idCompany, 'AND' => ['number =' => $number]])->first();

        return (bool) $invoice;
    }

    public static function sumOpenByCompany(int $idCompany): int
    {
        // o builder do core não faz SUM
        $sql = 'SELECT COALESCE(SUM(amount_in_cents), 0) AS total FROM invoice WHERE id_company = :id_company AND status = :status';

        $row = DB::query($sql, ['id_company' => $idCompany, 'status' => 'open'])->get(true);

        return (int) $row['total'];
    }

    public function customer(): ?Customer
    {
        return $this->belongsTo(Customer::class, 'id_customer');
    }
}
```

Escrita no service, sempre pelo ORM:

```php
$invoice = new Invoice();
$invoice->id_company = $idCompany;
$invoice->id_customer = $invoiceData['id_customer'];
$invoice->amount_in_cents = $invoiceData['amount_in_cents'];
$invoice->status = 'open';

$created = $invoice->insert();

$draft = Invoice::find($idDraft);
$draft->status = 'discarded';
$draft->save();
```

Lista com dado relacionado, sem N+1:

```php
$invoices = Invoice::listByCompany($idCompany);
$customerIds = array_unique($invoices->map(fn ($invoice) => $invoice->id_customer));
$customers = Customer::listByIds($customerIds);

$customersById = [];

foreach($customers as $customer){
    $customersById[$customer->id] = $customer;
}

foreach($invoices as $invoice){
    $invoice->customer_name = $customersById[$invoice->id_customer]->name;
}
```

## Errado
```php
// no controller
$invoices = DB::query("SELECT * FROM invoice WHERE id_company = " . $this->company->id . " AND status = '" . $status . "'")->get();

// no service
$invoice = Invoice::where(['id =' => $id])->first();
DB::table('invoice')->update(['status' => 'paid'])->where(['id =' => $id])->result();

foreach ($invoices as $invoice) {
    $customer = $invoice->customer();
    $total = Payment::where(['id_invoice =' => $invoice->id])->get()->count();
}

// trait compartilhada por vários models
trait FilterByCompany
{
    public static function byCompany($id) { return static::where(['id_company =' => $id])->get(); }
}
```

SQL concatenado fora do model, `where` no service, escrita sem ORM, duas queries por volta do laço e filtro
genérico num trait.

## Como reconhecer
- Fora de `app/LogicApp/Models/`: `DB::query(`, `DB::table(`, `DB::select(`, `::where(`, `::orderBy(`,
  `::limit(`, `->innerJoin(`, `SELECT `, `UPDATE `, `INSERT `, `DELETE `.
- Em controller e middleware, além disso: `::find(`, `->save(`, `->insert(`, `->remove(`, `new <Model>(`.
  A busca de middleware passa por método do model (`findByCompany`).
- `DB::table(...)->insert/update/delete` onde caberia `insert()`, `save()` ou `remove()` do model.
- `DB::query` com variável concatenada ou interpolada no SQL, com `?` ou sem o comentário do motivo.
- Método de model sem tipo de retorno ou com nome que não diz o que devolve (`get`, `buscar`, `filter`).
- `trait` em `Models/` com `where`.
- Dentro de `foreach`/`while`/`map`: chamada a método de model, `::where(`, `::find(`, `DB::`, ou relação
  (`->customer()`, `->hasMany(`, `->belongsTo(`).
- **Exceção:** `tests/Support/` (`TestDatabase` e `Fixtures::truncate()`) é infraestrutura de teste e pode usar PDO e `DB::query` para recriar e limpar o banco, com o comentário da exceção no topo do arquivo. Não acuse.

## Como corrigir
1. Para cada consulta fora do model, crie no model o método com o nome do que devolve e mova a consulta para lá,
   com o builder. Use `DB::query` só se o builder não resolver (SUM, subquery complexa, UNION), com placeholder
   nomeado (`:id_company`) e o comentário do motivo.
2. Troque o uso de fora pela chamada ao método novo.
3. Troque escrita por `DB::table` pelo ORM: `find` + alterar + `save()`, `new` + `insert()`, `remove()`. Se a
   escrita está no controller, leve-a para o service (`controller-fino.md`).
4. Apague o trait de filtro e escreva o método em cada model que o usava.
5. Para N+1: junte os ids antes do laço, traga tudo com um método `listByIds` (com `IN`) e monte o mapa por id.
   Lista vazia não vai para o `IN`:

```php
public static function listByIds(array $ids): Collection
{
    if(!$ids){
        return new Collection();
    }

    return static::where(['id IN' => $ids])->get();
}
```
