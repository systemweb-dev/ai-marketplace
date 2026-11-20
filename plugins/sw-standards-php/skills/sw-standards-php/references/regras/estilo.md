# Estilo da casa

## Regra
Todo PHP do projeto segue o estilo da systemweb, aplicado pelo `php-cs-fixer` com a config e o fixer próprio que a
etapa 0 instala (`.php-cs-fixer.dist.php` na raiz e `tools/php-cs-fixer/`):

- `if(`, `elseif(`, `foreach(`, `for(`, `while(`, `switch(`, `catch(` e `match(` sem espaço antes do parêntese, e
  `){` colado;
- `}else{`, `}elseif(cond){`, `}catch(...){` e `}finally{` juntos, só para o raro caso que sobrar (o `else` se evita,
  ver `guard-clause-sem-else.md`);
- linha em branco antes e depois de todo bloco (`if`, `foreach`, `for`, `while`, `switch`, `try`) e antes do
  `return`;
- chave de classe e de método na linha de baixo;
- 4 espaços, LF e nada de `if` sem chaves.

Ninguém formata à mão: roda o fixer nos arquivos tocados e confere o resultado.

## Por quê
Um estilo só, aplicado por máquina, acaba com a discussão em review e com o diff de reformatação misturado ao de
lógica. O `php-cs-fixer` sozinho não chega neste estilo: ele garante um espaço depois de `if`, não cola `){` e não
põe a linha em branco depois do bloco. Por isso a systemweb tem três fixers próprios, testados por pares antes e
depois, que rodam junto com os nativos sem serem desfeitos. A linha em branco em volta do bloco separa os passos
do método e faz o desvio saltar aos olhos.

## Certo
```php
namespace App\LogicApp\Services\Billing;

use App\LogicApp\Models\Invoice;

final class InvoiceTotalService
{
    public static function total(Invoice $invoice, array $items): int
    {
        $total = 0;

        foreach($items as $item){
            $total += $item['amount_in_cents'] * $item['quantity'];
        }

        if($invoice->discount_in_cents){
            $total -= $invoice->discount_in_cents;
        }

        if($total < 0){
            return 0;
        }

        return $total;
    }
}
```

O que faz cada parte:

| Quem | Regra | O que faz |
|---|---|---|
| `Systemweb/no_space_after_control_keyword` | próprio | tira o espaço de `if (`, `foreach (`, `catch (`, `match (` |
| `Systemweb/no_space_before_control_brace` | próprio | cola `){`, `}else{`, `}catch(` |
| `Systemweb/blank_line_after_block` | próprio | linha em branco depois do `}` que fecha um bloco |
| `@PSR12` | nativo | chave de classe e de método embaixo, indentação, `use`, espaços |
| `control_structure_braces` | nativo | põe chaves no `if` sem chaves |
| `blank_line_before_statement` | nativo | linha em branco antes de `if`, `foreach`, `for`, `while`, `switch`, `try` e `return` |
| `setIndent` e `setLineEnding` | config | 4 espaços e LF |

## Errado
```php
final class InvoiceTotalService {
    public static function total(Invoice $invoice, array $items): int {
        $total = 0;
        foreach ($items as $item) {
            $total += $item['amount_in_cents'] * $item['quantity'];
        }
        if ($invoice->discount_in_cents) $total -= $invoice->discount_in_cents;
        if ($total < 0) {
            return 0;
        }
        return $total;
    }
}
```

O estilo `if (x) {` aparece aqui de propósito: espaço depois da palavra-chave e antes da chave, chave de classe e
de método na mesma linha, `if` sem chaves e blocos colados sem linha em branco.

## Como reconhecer
- `vendor/bin/php-cs-fixer fix --dry-run --diff` com saída diferente de vazia (a forma exata é a do bloco abaixo).
- Projeto sem `.php-cs-fixer.dist.php` na raiz, sem `tools/php-cs-fixer/Fixers.php`, ou com a config alterada
  (regra desligada, fixer próprio fora do `registerCustomFixers`).
- Pasta de PHP do projeto fora do `Finder` da config (além de `vendor`, `node_modules`, `storage` e `tools`).
- O que o fixer não decide e a IA confere: `}else{` que sobrou (é regra do `guard-clause-sem-else.md`), arquivo
  PHP que o fixer não alcança (fora do `Finder` ou com outra extensão) e código entregue sem passar pelo fixer.

## Como corrigir
1. Garanta a etapa 0: `friendsofphp/php-cs-fixer` no `require-dev`, `.php-cs-fixer.dist.php` na raiz e a pasta
   `tools/php-cs-fixer/` copiada de `assets/php-cs-fixer/` da skill, sem edição.
2. No modo escrever, rode o fixer só nos arquivos tocados, ao terminar.
3. Na auditoria, a primeira etapa de correção é só o formatador no projeto inteiro, num commit separado, porque ele
   não muda comportamento.
4. Rode de novo com `--dry-run`: a segunda rodada não pode mudar nada.
5. Revise o diff à procura do que o fixer não decide (o `else` que sobrou) e corrija pela regra certa.

```bash
vendor/bin/php-cs-fixer fix app/LogicApp/Services/Billing/InvoiceTotalService.php
vendor/bin/php-cs-fixer fix
vendor/bin/php-cs-fixer fix --dry-run --diff
```
