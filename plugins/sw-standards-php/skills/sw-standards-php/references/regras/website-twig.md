# Website Twig

## Regra
O website segue a mesma arquitetura da API: o middleware valida e repassa com `Request::share`, a regra fica em
`Services/<Domínio>/`, o banco fica no model. O controller fino lê `$this->shared()`, pede ao service os dados
**já prontos para exibir** (preço formatado, rótulo, URL, lista montada), define o SEO com `sw_seo()` e termina em
`$this->view('pasta/arquivo', $dados)`. O template só exibe: laço, condição de exibição e saída de variável, sem
cálculo, query, regra nem leitura da request. Pedaço repetido vira macro em `macros/`, na raiz do projeto. Todo
arquivo de `www/assets/` entra por `asset()`, todo arquivo enviado por `storage()`, e o SEO sai no layout por
`seo()`. CSS segue o padrão do esqueleto: SCSS em `webpack/css/` (o `main.scss` importa `modules/`), compilado para
`www/assets/css/*.min.css`.

## Por quê
É o Thin Controller com Service Layer de novo, agora com a view no fim: o que o template calcula não tem teste e
se repete na página seguinte que mostra o mesmo dado. Com os dados prontos, o service é testado no `Integration/`
e o template vira só marcação. O `asset()` do core monta o caminho com a constante `ASSET`, e o `storage()` com o
`Storage` do core: caminho fixo (`/assets/...`) quebra quando a constante ou o storage mudam. O core já procura
template em `app/<Tema>/Views` e em `macros/`, então a macro em `macros/` é encontrada por qualquer página sem
`include` de caminho relativo. O `seo()` do layout lê o que o controller gravou com `sw_seo()`: um título fixo no
template some do controle do controller e fica igual em toda página.

## Certo
O controller lê, chama o service, define o SEO e renderiza:

```php
namespace App\Site\Controllers;

use App\LogicApp\Models\Product;
use App\LogicApp\Services\Catalog\ProductPageService;
use SysWeb\Controller;

final class ProductController extends Controller
{
    public function show(): void
    {
        $product = $this->shared('product', Product::class);

        $page = ProductPageService::build($product);

        sw_seo()
            ->title($page['product']['name'] . ' | Loja')
            ->description($page['product']['summary'])
            ->canonical($page['product']['url']);

        $this->view('product/show', $page);
    }
}
```

O service entrega tudo pronto para exibir, em array:

```php
namespace App\LogicApp\Services\Catalog;

use App\LogicApp\Helpers\Money;
use App\LogicApp\Models\Product;

final class ProductPageService
{
    public static function build(Product $product): array
    {
        $related = [];

        foreach(Product::listRelatedTo($product, 4) as $item){
            $related[] = self::_card($item);
        }

        return [
            'product' => self::_card($product) + ['summary' => $product->summary, 'inStock' => $product->stock > 0],
            'related' => $related,
        ];
    }

    private static function _card(Product $product): array
    {
        return [
            'name' => $product->name,
            'url' => '/produtos/' . $product->slug,
            'priceLabel' => Money::centsToBrl($product->price_in_cents),
            'imagePath' => $product->image_path,
        ];
    }
}
```

O template só exibe, com a macro de `macros/` e as funções do core:

```twig
{% extends "layout.twig" %}
{% from "cards.twig" import productCard %}

{% block content %}
    <article class="product">
        <img src="{{ storage(product.imagePath) }}" alt="{{ product.name }}">
        <h1>{{ product.name }}</h1>
        <p class="product__price">{{ product.priceLabel }}</p>

        {% if not product.inStock %}
            <p class="product__out">Fora de estoque</p>
        {% endif %}
    </article>

    {% if related %}
        <section class="related">
            {% for item in related %}
                {{ productCard(item) }}
            {% endfor %}
        </section>
    {% endif %}
{% endblock %}
```

A macro, em `macros/cards.twig`, e o layout, com o SEO e o asset:

```twig
{% macro productCard(item) %}
    <a class="card" href="{{ item.url }}">
        <img src="{{ storage(item.imagePath) }}" alt="{{ item.name }}">
        <strong>{{ item.name }}</strong>
        <span>{{ item.priceLabel }}</span>
    </a>
{% endmacro %}
```

```twig
<title>{{ seo('title') }}</title>
<meta name="description" content="{{ seo('description') }}">
<link rel="canonical" href="{{ seo('canonical') }}">
<link rel="stylesheet" href="{{ asset('css/style.min.css') }}">
```

## Errado
```php
class ProductController extends Controller
{
    public function show($slug)
    {
        $product = Product::where(['slug =' => $slug])->first();
        $related = DB::query("SELECT * FROM product WHERE id_category = " . $product->id_category . " LIMIT 4")->get();

        $this->view('product/show', ['product' => $product, 'related' => $related]);
    }
}
```

```twig
{% extends "layout.twig" %}

{% block styleHead %}
    <title>Produto - Loja</title>
    <link rel="stylesheet" href="/assets/css/product.css">
    <style>.product{display:flex}</style>
{% endblock %}

{% block content %}
    <img src="/storage/{{ product.image_path }}">
    <h1>{{ product.name }}</h1>
    <p>R$ {{ (product.price_in_cents / 100)|number_format(2, ',', '.') }}</p>

    {% if product.stock > 0 and app.global.get.preview != '1' %}
        <button>Comprar</button>
    {% endif %}

    {% for item in related %}
        <a class="card" href="/produtos/{{ item.slug }}">
            <strong>{{ item.name }}</strong>
            <span>R$ {{ (item.price_in_cents / 100)|number_format(2, ',', '.') }}</span>
        </a>
    {% endfor %}
{% endblock %}
```

Query e SQL concatenado no controller, model cru na view, cálculo de preço repetido no template, regra (estoque,
preview) decidida pela leitura da request no template, card repetido em vez de macro, título fixo no lugar do
`sw_seo()`, caminho de asset e de storage escrito à mão e CSS dentro do template.

## Como reconhecer
- Em `app/<Tema>/Controllers/`: os mesmos sinais de `controller-fino.md` (`DB::`, `::where(`, `->save(`,
  `private function`, `try{`), `Request::get()`/`$this->request->get()` ou parâmetro de rota lido na ação, e
  `$this->view(` recebendo model ou `Collection` em vez de array montado pelo service.
- Ação de página sem `sw_seo()`, ou `sw_seo` chamado em service, middleware ou template.
- Em `*.twig`:
  - aritmética (`+`, `-`, `*`, `/`, `%`) ou `number_format` sobre valor de negócio, e `|date` sobre campo cru;
  - condição que decide regra (status, estoque, permissão, comparação de valores), e não só se algo aparece;
  - `app.global.get`, `app.global.post` ou `app.global.session` decidindo o que exibir;
  - `src="/assets/`, `href="/assets/`, `/storage/` ou URL de CDN do próprio projeto escrita à mão;
  - `<title>` ou `<meta name="description"` com texto fixo, fora do `seo()`;
  - bloco `<style>` ou `.css` fora de `asset()`;
  - o mesmo trecho de marcação em dois ou mais templates, ou `{% macro %}` definido dentro de `app/<Tema>/Views/`.
- SCSS fora de `webpack/css/` ou CSS solto em `www/assets/css/` sem fonte em `webpack/css/`.

## Como corrigir
1. Mova busca e validação para o middleware (`{Recurso}ExistsMiddleware`, `Request::share`), como na API (ver
   `validacao-no-middleware.md`).
2. Crie ou complete o service em `Services/<Domínio>/` com um método que devolve o array da página, com cada valor
   já no formato de exibição (rótulo de preço, data por extenso, URL, flag de exibição).
3. Deixe a ação com a forma do bloco abaixo: `shared()`, service, `sw_seo()` e `$this->view()`.
4. No template, troque cada cálculo e cada regra pela chave pronta do array; o que sobrar de `if` só decide se um
   pedaço aparece.
5. Trecho repetido vira `{% macro %}` em `macros/<assunto>.twig`, importado com `{% from "<assunto>.twig" import ... %}`.
6. Troque caminho escrito à mão por `asset('...')` ou `storage('...')`, título e descrição por `seo('...')` no
   layout, e mova o CSS para `webpack/css/modules/`, importado no `main.scss`.

```php
public function show(): void
{
    $product = $this->shared('product', Product::class);

    $page = ProductPageService::build($product);

    sw_seo()
        ->title($page['product']['name'] . ' | Loja')
        ->description($page['product']['summary'])
        ->canonical($page['product']['url']);

    $this->view('product/show', $page);
}
```
