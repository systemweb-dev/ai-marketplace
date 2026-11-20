# Tipos e comentários

## Regra
Todo parâmetro e todo retorno de método e de função têm tipo (`int`, `?Invoice`, `Invoice|array`, `void`), sem
`declare(strict_types=1)`. A versão do PHP é a do projeto, lida no `composer.json` (`require.php`) ou na imagem do
Docker: nada de recurso de versão mais nova do que essa. Comentário só explica o **porquê** que o código não diz
(uma restrição, um pedido ao framework, uma decisão fora do óbvio), em português e com espaço depois de `//`;
nunca narra o que a linha faz.

## Por quê
O tipo na assinatura é documentação que o PHP confere: o erro aparece na chamada errada, não três camadas depois,
e some a vontade de converter de novo por desconfiança (`ruido-defensivo.md`). Sem `strict_types` porque o core e
os projetos não o usam, e ligá-lo num arquivo só muda a coerção daquele arquivo e cria comportamento diferente
entre vizinhos. Recurso de PHP acima da versão do projeto quebra em produção mesmo passando na máquina de quem
escreveu. Comentário que narra a linha envelhece mal e mente quando o código muda; o porquê é o que ninguém
recupera lendo o código.

## Certo
```php
namespace App\LogicApp\Services\Billing;

use App\LogicApp\Models\Invoice;
use Carbon\CarbonImmutable;

final class InvoiceDueDateService
{
    public static function dueDate(Invoice $invoice, int $graceDays): string
    {
        // o banco do fornecedor só aceita data em dia útil; feriado fica a cargo dele
        $dueDate = CarbonImmutable::parse($invoice->created_at)->addWeekdays($graceDays);

        return $dueDate->format('Y-m-d');
    }

    public static function findOpen(int $idCompany, int $id): ?Invoice
    {
        return Invoice::findByCompany($idCompany, $id);
    }

    public static function markReminded(Invoice $invoice): void
    {
        $invoice->reminders_sent++;
        $invoice->save();
    }
}
```

## Errado
```php
<?php
declare(strict_types=1);

class InvoiceDueDateService
{
    /**
     * Calcula a data de vencimento.
     *
     * @param Invoice $invoice a fatura
     * @param int $graceDays os dias
     * @return string a data
     */
    public static function dueDate($invoice, $graceDays)
    {
        //soma os dias úteis
        $dueDate = CarbonImmutable::parse($invoice->created_at)->addWeekdays($graceDays);
        // Return the formatted date
        return $dueDate->format('Y-m-d');
    }

    public static function findOpen($idCompany, $id)
    {
        // $invoice = Invoice::find($id);
        return Invoice::findByCompany($idCompany, $id);
    }
}
```

`strict_types`, parâmetro e retorno sem tipo, docblock que só repete a assinatura, comentário narrando a linha (em
inglês e sem espaço depois de `//`) e código comentado.

## Como reconhecer
- `declare(strict_types=1)`.
- `function nome(` com parâmetro sem tipo ou sem `: tipo` depois do `)`, exceto `__construct`, `__invoke` de
  middleware (assinatura do core) e closures curtas de `map`/`filter`.
- Recurso acima da versão do `composer.json`/Docker do projeto (por exemplo, `readonly class` abaixo do 8.2,
  property hooks e `new` sem parênteses na chamada abaixo do 8.4).
- `//` sem espaço depois; comentário em inglês; comentário que repete a linha de baixo (`// salva`, `// retorna`,
  `// loop nos itens`); docblock que só repete nomes e tipos da assinatura; código comentado.
- Versão do PHP do projeto abaixo da que o core instalado suporta (vai no relatório como sugestão, não como erro).

## Como corrigir
1. Leia a versão do PHP do projeto (`composer.json` e Docker) antes de escrever qualquer coisa, e use só o que ela
   tem. Se estiver abaixo do que o core suporta, registre a sugestão de subir no relatório.
2. Apague o `declare(strict_types=1)`.
3. Ponha tipo em cada parâmetro e retorno; `void` quando não devolve nada, `?Tipo` quando pode ser `null` e
   `Tipo|array` no service que devolve o dado ou o array de erro.
4. Apague o comentário que narra a linha e o docblock que só repete a assinatura. O que sobrar vira o porquê, em
   português, com `// ` na frente.
5. Na auditoria, chame a `sw-dead-code-scan` para o comentário desnecessário e o código comentado, perguntando antes;
   sem ela instalada, faça a limpeza à mão com a lista do "Como reconhecer".

```php
public static function dueDate(Invoice $invoice, int $graceDays): string
{
    // o banco do fornecedor só aceita data em dia útil; feriado fica a cargo dele
    $dueDate = CarbonImmutable::parse($invoice->created_at)->addWeekdays($graceDays);

    return $dueDate->format('Y-m-d');
}
```
