# Infra: migration, cache, upload e paginação

## Regra
- **Migration** em `database/sql/V{n}__descricao.sql` (Flyway): `n` sequencial, dois sublinhados, descrição em
  snake_case. Migration já aplicada em algum ambiente **nunca** é alterada nem apagada; a correção é uma nova.
- **Cache** pelo `SysWeb\Cache\Cache` do core, com a chave num enum `ECache` (`app/LogicApp/Enums/ECache.php`) que
  dá o prefixo do projeto e o TTL de cada chave. TTL sempre explícito e maior que zero; guarde array, não model.
- **Upload de imagem** pelo `Storage` do core: `(new Storage())->put()->image($file)`. Arquivo comum (PDF, XML,
  planilha) vai pela integração `Integrations/Aws/`, com `instance()` e `fake()` como qualquer integração.
- **Paginação** com `Help::pagination($total, $page, $perPage)`, com o total e a página vindos de métodos do model.

## Por quê
O Flyway guarda o checksum de cada migration aplicada: alterar uma já rodada quebra o deploy, e em outro ambiente
o banco fica diferente sem ninguém saber. Chave de cache solta em string colide entre projetos que dividem o
mesmo Redis e não deixa achar onde a chave é usada; sem TTL o dado velho fica para sempre, e o `Cache::set` do
core usa 3600 por padrão e grava sem expirar quando recebe 0. O `Storage` confere o tipo real da imagem pelos
bytes, não pelo que o navegador diz. O `Help::pagination` dá o mesmo formato de página em toda a API (`page`,
`per_page`, `total`, `total_pages`, `has_next`...), e o front trata todas as listas do mesmo jeito.

## Certo
Migration nova, nunca a antiga editada:

```sql
-- database/sql/V14__add_due_date_to_invoice.sql
ALTER TABLE invoices ADD COLUMN due_date DATE NULL AFTER status;
CREATE INDEX idx_invoice_company_due_date ON invoice (id_company, due_date);
```

O enum do cache, com prefixo e TTL:

```php
namespace App\LogicApp\Enums;

enum ECache: string
{
    case COMPANY_PLAN = 'company-plan';
    case EXCHANGE_RATE = 'exchange-rate';

    public function key(int|string $id): string
    {
        return "billing:{$this->value}:{$id}";
    }

    public function ttl(): int
    {
        return match($this){
            self::COMPANY_PLAN => 600,
            self::EXCHANGE_RATE => 3600,
        };
    }
}
```

O uso, no service:

```php
public static function findByCompany(int $idCompany): array
{
    $cacheKey = ECache::COMPANY_PLAN->key($idCompany);
    $cached = Cache::get($cacheKey);

    if($cached){
        return $cached;
    }

    $plan = Plan::findByCompany($idCompany);
    $planData = Api::returnAttributes($plan, ['id', 'name', 'limit_invoices']);

    Cache::set($cacheKey, $planData, ECache::COMPANY_PLAN->ttl());

    return $planData;
}
```

Upload de imagem, com o arquivo já conferido e compartilhado pelo middleware:

```php
public static function updateAvatar(User $user, array $photo): User|array
{
    $path = (new Storage())->put()->directoryName('avatars')->image($photo);

    if(!$path){
        return ['error' => 'avatar_upload_failed', 'message' => 'Avatar upload failed', 'status' => 500];
    }

    $user->avatar = $path;
    $user->save();

    return $user;
}
```

Paginação, com o total e a página pelo model:

```php
public static function listByCompany(int $idCompany, int $page, int $perPage): array
{
    $total = Invoice::countByCompany($idCompany);
    $invoices = Invoice::listByCompanyPage($idCompany, $perPage, ($page - 1) * $perPage);

    return [
        'items' => Api::returnAttributes($invoices, ['id', 'status', 'amount_in_cents']),
        'pagination' => Help::pagination($total, $page, $perPage),
    ];
}
```

## Errado
```php
// database/sql/V3__create_invoice.sql, já aplicada em prod, editada para "corrigir" a coluna
// database/sql/2024_05_10_add_due_date.sql, fora do padrão do Flyway

Cache::set('plan_' . $companyId, $plan);
$rate = Cache::get('rate');

move_uploaded_file($_FILES['photo']['tmp_name'], 'storage/avatars/' . $_FILES['photo']['name']);

$page = $_GET['page'] ?? 1;
$invoices = Invoice::where(['id_company =' => $companyId])->limit(20)->offset(($page - 1) * 20)->get();
ResponseApi::success('ok', ['data' => $invoices, 'page' => $page, 'pages' => ceil(Invoice::rows() / 20)]);
```

Migration aplicada alterada e nome fora do padrão, chave sem prefixo nem enum e sem TTL explícito, model no
cache, upload direto com o nome que o cliente mandou e sem conferir o tipo, e paginação montada à mão com query
fora do model e formato próprio.

## Como reconhecer
- Arquivo em `database/sql/` fora de `V{n}__descricao.sql`, número repetido ou pulando para trás.
- Diff que altera ou apaga uma migration que já está no branch principal (`git log -- database/sql/V3__*`).
- `Cache::set(`, `Cache::get(` ou `Cache::delete(` com chave em string montada ali, sem `ECache`.
- `Cache::set(` com dois argumentos (TTL padrão) ou TTL `0`; model ou `Collection` passado como valor.
- `move_uploaded_file`, `copy($_FILES`, `file_put_contents` com upload, ou `Storage::image(` estático (não existe).
- Arquivo comum enviado por SDK da AWS fora de `Integrations/Aws/`.
- Resposta de lista com `page`, `pages`, `total` montados à mão, ou `ceil(... / $perPage)` fora do core.

## Como corrigir
1. Migration alterada: devolva o arquivo ao que foi aplicado (`git show <commit>:database/sql/V3__...`) e escreva
   a correção num `V{próximo}__...sql`. Renomeie o que está fora do padrão só se ainda não foi aplicado; se foi,
   combine com o dono (o histórico do Flyway guarda o nome).
2. Crie o `ECache` com um caso por chave, `key()` com o prefixo do projeto e `ttl()`; troque toda chave solta por
   `ECache::CASO->key($id)` e passe o TTL do enum no `Cache::set`. Guarde o array do `Api::returnAttributes`, não o
   model.
3. Troque o upload de imagem por `(new Storage())->put()->image($file)`, com o arquivo validado no middleware; o
   arquivo comum vai pela integração `Integrations/Aws/`.
4. Na lista, crie no model o `countBy...` e o `listBy...Page($limit, $offset)`, e responda com
   `Help::pagination($total, $page, $perPage)`.

```php
public static function listByCompanyPage(int $idCompany, int $limit, int $offset): Collection
{
    return static::where(['id_company =' => $idCompany])->orderBy('id', 'DESC')->limit($limit)->offset($offset)->get();
}
```

## Enquanto o core não corrigir
Vale para o core até a 1.11.0, inclusive; confira o CHANGELOG do core instalado.

- **O `Storage` só sabe imagem.** `video()` e `file()` existem na interface, mas estão vazios no core; por isso o
  arquivo comum vai pela `Integrations/Aws/`. A nota sai quando o core implementar os dois.
- **`image()` lança exceção em formato inválido** em vez de devolver `null`. Confira o tipo no middleware (pelos
  bytes, com `finfo` e a lista `\SysWeb\Storage\Upload::IMAGE_ALLOWED`) e responda 422 ali; a exceção que sobrar é
  inesperada e vai para o tratador global.
- **O `Cache` não aplica prefixo nenhum na chave.** O prefixo do projeto vem do `ECache`; sem ele, dois projetos
  no mesmo Redis escrevem na mesma chave.
