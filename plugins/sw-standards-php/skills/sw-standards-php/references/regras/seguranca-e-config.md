# Segurança e config

## Regra
`sw_env('CHAVE')` só aparece em `config/*.php`, onde a config monta os valores a partir do `.env`; o código da
aplicação lê com `sw_config('chave')`. Nenhum segredo, senha, token, chave de API ou URL de ambiente fica no
código nem nos testes: o core só lê o `.env`, então as chaves de teste ficam nele (ex.: `MARIADB_DBNAME_TEST`) e o
`config/*.php` escolhe pelo `getenv('APP_TESTING')` (banco `_test`, webhook do Discord vazio, fila de teste); todo
`.env*` com valor real fica fora do git (só o `.env.example`, sem valores, entra). **Escopo de dados depende do projeto:** na primeira vez, a skill pergunta se
ele é multiempresa, qual coluna separa os dados e como protege, e grava a resposta em
`docs/sw-standards/config.md`. Sendo multiempresa, toda busca por id passa pela empresa. A sugestão de mecanismo é
o middleware `{Recurso}ExistsMiddleware`, que busca por `Model::findByCompany($idCompany, $id)`, responde 404 e
compartilha o registro com `Request::share`.

## Por quê
O repositório vai para muitas mãos, e segredo no código vaza com o primeiro clone ou o primeiro print. Com
`sw_env` só na config, o mapa do que o projeto precisa do ambiente está num lugar só, e trocar de ambiente não
mexe em código. Em projeto multiempresa, buscar só pelo id deixa uma empresa ler, alterar ou apagar o registro da
outra trocando o número na URL (IDOR). Um middleware por recurso faz a checagem uma vez, na borda, e entrega o
registro já buscado: o controller não tem como esquecer o filtro. O 404 (e não o 403) não confirma que o id
existe em outra empresa.

## Certo
A config monta os valores do ambiente:

```php
return [
    'both' => [
        'acme' => [
            'api_key' => sw_env('ACME_API_KEY'),
            'base_url' => sw_env('ACME_BASE_URL'),
        ],
    ],
    'prod' => [],
    'test' => [],
    'dev' => [],
];
```

O código lê a config, nunca o ambiente. O `sw_config` recebe só a chave de primeiro nível:

```php
public static function instance(): AcmePayments
{
    $acme = sw_config('acme');

    return self::$instance ??= new AcmeHttpPayments($acme['base_url'], $acme['api_key']);
}
```

Os valores ficam fora do git; o exemplo entra sem valor:

```text
# .env.example (no git)
ACME_API_KEY=
ACME_BASE_URL=

# .gitignore
.env
.env.*
!.env.example
```

Em projeto multiempresa, o filtro mora no model e o middleware faz a checagem na borda:

```php
public static function findByCompany(int $idCompany, int $id): ?self
{
    return static::where(['id_company =' => $idCompany, 'AND' => ['id =' => $id]])->first();
}
```

```php
namespace Middleware;

use App\LogicApp\Models\Company;
use App\LogicApp\Models\Invoice;
use SysWeb\Api\ResponseApi;
use SysWeb\Request\Request;
use SysWeb\Response\Response;
use SysWeb\Router\Router;

final class InvoiceExistsMiddleware
{
    public function __invoke(Request $request, Response $response, callable $next)
    {
        $company = Request::shared('company', Company::class);
        $idInvoice = filter_var(Router::param('id'), FILTER_VALIDATE_INT);

        if(!$idInvoice){
            ResponseApi::error('invoice_not_found', 'Invoice not found', 404);
        }

        $invoice = Invoice::findByCompany($company->id, $idInvoice);

        if(!$invoice){
            ResponseApi::error('invoice_not_found', 'Invoice not found', 404);
        }

        Request::share('invoice', $invoice);

        return $next();
    }
}
```

O controller só lê o que o middleware entregou: `$invoice = $this->shared('invoice', Invoice::class);`.

## Errado
```php
// no service
$client = new AcmeHttpPayments('https://api.acme.example', 'sk_live_51H...');
$webhook = sw_env('DISCORD_WEBHOOK');

// no teste
$token = 'eyJhbGciOiJIUzI1NiJ9...';

// no controller de um projeto multiempresa
public function show()
{
    $invoice = Invoice::find(Router::param('id'));
    ResponseApi::success('ok', Api::returnAttributes($invoice, ['id', 'amount_in_cents']));
}
```

Chave e URL de produção no código, `sw_env` fora da config, token fixo no teste e busca só pelo id: qualquer
empresa logada lê a fatura de outra trocando o número na URL.

## Como reconhecer
- `sw_env(` fora de `config/`.
- `getenv(`, `$_ENV[` ou `$_SERVER['...']` lendo segredo fora de `config/`.
- String com cara de segredo em código ou teste: `sk_`, `pk_`, `Bearer `, `eyJ` (JWT), `AKIA` (AWS), `-----BEGIN`,
  `password =>`, URL de webhook, IP ou domínio de ambiente.
- `.env` ou outro `.env*` com valor versionado; `.gitignore` sem `.env`.
- Em projeto multiempresa: `Model::find($id)` ou `findBy...` sem a empresa, sobre id que veio da rota ou da
  request; rota com `{id}` sem o `{Recurso}ExistsMiddleware` (ou o mecanismo registrado no projeto).
- Projeto sem a resposta de escopo em `docs/sw-standards/config.md`: pergunte antes de auditar esta parte.
- **Exceção:** `tests/Support/TestDatabase.php` lê as credenciais com `sw_env`, porque cria o banco de teste antes de a config de banco existir, com o comentário da exceção no topo. Não acuse.

## Como corrigir
1. Leia `docs/sw-standards/config.md`. Se não houver a resposta de escopo, pergunte ao dono se o projeto é
   multiempresa, qual coluna separa os dados e como protege hoje, e grave.
2. Para cada `sw_env` fora da config, crie a chave em `config/Config.php` (no bloco `both` ou no do ambiente) e
   troque a leitura por `sw_config('chave')`.
3. Tire o segredo do código: a chave vai para o `.env`, o nome para o `.env.example` sem valor e a leitura para
   a config. Segredo que já esteve no git está vazado: avise o dono para trocar a credencial.
4. No teste, a chave vem do `.env` (fora do git), escolhida pela config com `getenv('APP_TESTING')`, ou o valor
   é gerado no próprio teste (`Jwt::generate`).
5. Sendo multiempresa, crie no model o `findByCompany($idCompany, $id)`, crie o `{Recurso}ExistsMiddleware`,
   registre-o em `config/Middleware.php` e na rota, e troque a busca do controller por `$this->shared()`.

```php
public function show(): void
{
    $invoice = $this->shared('invoice', Invoice::class);

    ResponseApi::success('invoice_found', Api::returnAttributes($invoice, ['id', 'status', 'amount_in_cents']));
}
```
