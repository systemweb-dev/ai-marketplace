# Plano de implementação — sw-standards-php

[spec.md](spec.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** construir a skill `sw-standards-php`, que impõe os padrões da systemweb em projetos PHP do
framework (API e website Twig), em dois modos: escrever e auditar/corrigir. A skill vem com as regras, o fixer
próprio de estilo e os moldes da etapa 0.

**Arquitetura:**

- A fonte da skill é `~/.claude/skills/sw-standards-php/`, e ela chega ao repo pelo `make sync`.
- O conteúdo das regras sai do catálogo aprovado, `referencias/decisoes-em-andamento.md`. A seção "Revisão do
  design" e o `spec.md` vencem os itens numerados.
- O estilo que o `php-cs-fixer` não faz vira três fixers próprios, testados por pares antes e depois.
- A detecção é só IA: a qualidade é medida com a `sw-skill-test` sobre um projeto fixture com violações
  plantadas.
- O `SKILL.md` é escrito seguindo a `skill-creator` [usuário].

**Stack:**

- Markdown: as regras e o `SKILL.md`.
- PHP 8.4 (máquina) e Composer 2.9: o fixer e os moldes.
- `friendsofphp/php-cs-fixer` ^3.95, instalado num cache fora do repo para o teste do fixer.
- Python 3: o checador das regras.

**Restrições verificáveis (do spec):**

| Restrição | Como o plano checa |
|---|---|
| 1. A auditoria acha ≥ 16 das 18 violações plantadas e acusa ≤ 1 das 5 armadilhas | Task 13, step 2 (`sw-skill-test`, comportamento) |
| 2. O fixer passa nos pares antes e depois, é idempotente e não toca string nem comentário; roda por meta do `make` | Task 3, steps 1 a 5 (`make fixer-test`) |
| 3. Os blocos `php` de **Certo** e **Como corrigir** passam pelo fixer sem mudar | Tasks 6 a 9, step "checar" (`tests/checar_regras.py --estilo`) |
| 4. Cada arquivo de regra tem as seis seções | Tasks 6 a 9, step "checar" (`tests/checar_regras.py`) |
| 5. Nenhum nome de projeto real nem caminho do home na skill e no dossiê | Task 14, step 1 (`make check` mais grep manual) |

**Risco primeiro:** as tasks 1 e 2 são os dois spikes das suposições de maior risco do spec. A task 1 testa se
um fixer customizado consegue o estilo `if(`/`){` sem que os fixers nativos o desfaçam. A task 2 testa se o
`set_exception_handler` pega a exceção, inclusive a de SQL, no fluxo do core. O código dos spikes é
descartável e fica no scratchpad, fora da skill e do repo.

**Nunca edite os projetos reais.** Para ler ou testar em arquivos de um projeto, copie para o scratchpad.

---

### Task 1: spike — fixer customizado consegue o estilo da casa

**Arquivos:**
- Criar: `$SCRATCH/spike-fixer/` (descartável; `$SCRATCH=${TMPDIR:-/tmp}/sw-standards`)

**Depende de:** nada.

**Deu certo se:**

- `if (x) {` vira `if(x){`, e `} else {` vira `}else{`;
- uma linha em branco aparece depois de um bloco seguido de código;
- uma segunda rodada não muda nada;
- os fixers nativos do `@PSR12` não põem o espaço de volta.

**Se falhar:** pare e leve ao usuário. O plano muda: a regra 14 passa a "o `php-cs-fixer` faz o resto e a IA
ajusta `if(`/`){`", e a task 3 encolhe para só a config nativa.

- [x] **Step 1: montar o projeto do spike com o `php-cs-fixer`**

```bash
S=${TMPDIR:-/tmp}/sw-standards/spike-fixer
mkdir -p "$S/src" && cd "$S" && composer init -n --name=spike/fixer >/dev/null && composer require -n --dev friendsofphp/php-cs-fixer:^3.95
vendor/bin/php-cs-fixer --version
```

Esperado: `PHP CS Fixer 3.9x…`.

- [x] **Step 2: escrever os três fixers do spike em `$S/src/Fixers.php`**

```php
<?php

namespace Spike;

use PhpCsFixer\Fixer\FixerInterface;
use PhpCsFixer\FixerDefinition\CodeSample;
use PhpCsFixer\FixerDefinition\FixerDefinition;
use PhpCsFixer\FixerDefinition\FixerDefinitionInterface;
use PhpCsFixer\Tokenizer\Token;
use PhpCsFixer\Tokenizer\Tokens;

abstract class Base implements FixerInterface
{
    public function isRisky(): bool { return false; }
    public function supports(\SplFileInfo $file): bool { return true; }
    public function getPriority(): int { return -100; }   // roda depois dos nativos
    public function getDefinition(): FixerDefinitionInterface
    {
        return new FixerDefinition($this->getName(), [new CodeSample("<?php\nif (\$a) {\n}\n")]);
    }
}

final class NoSpaceAfterKeyword extends Base
{
    private const KEYWORDS = [T_IF, T_ELSEIF, T_FOREACH, T_FOR, T_WHILE, T_SWITCH, T_CATCH, T_MATCH];

    public function getName(): string { return 'Spike/no_space_after_control_keyword'; }
    public function isCandidate(Tokens $tokens): bool { return $tokens->isAnyTokenKindsFound(self::KEYWORDS); }

    public function fix(\SplFileInfo $file, Tokens $tokens): void
    {
        foreach ($tokens as $index => $token) {
            if (!$token->isGivenKind(self::KEYWORDS)) {
                continue;
            }
            $next = $index + 1;
            if ($tokens[$next]->isWhitespace() && $tokens[$next + 1]->equals('(')) {
                $tokens->clearAt($next);
            }
        }
    }
}

final class NoSpaceAroundBrace extends Base
{
    public function getName(): string { return 'Spike/no_space_before_control_brace'; }
    public function isCandidate(Tokens $tokens): bool { return true; }

    public function fix(\SplFileInfo $file, Tokens $tokens): void
    {
        for ($index = $tokens->count() - 1; $index > 0; --$index) {
            $token = $tokens[$index];
            // ") {" e "else {" / "try {" / "finally {" / "do {"
            if ($token->equals('{') && $tokens[$index - 1]->isWhitespace(" \t")) {
                $before = $tokens[$index - 2];
                if ($before->equals(')') && $this->closesControl($tokens, $index - 2)
                    || $before->isGivenKind([T_ELSE, T_TRY, T_FINALLY, T_DO])) {
                    $tokens->clearAt($index - 1);
                }
            }
            // "} else" / "} elseif" / "} catch" / "} finally"
            if ($token->isGivenKind([T_ELSE, T_ELSEIF, T_CATCH, T_FINALLY])
                && $tokens[$index - 1]->isWhitespace(" \t") && $tokens[$index - 2]->equals('}')) {
                $tokens->clearAt($index - 1);
            }
        }
    }

    private function closesControl(Tokens $tokens, int $close): bool
    {
        $open = $tokens->findBlockStart(Tokens::BLOCK_TYPE_PARENTHESIS_BRACE, $close);
        $keyword = $tokens->getPrevMeaningfulToken($open);

        return $keyword !== null && $tokens[$keyword]->isGivenKind([T_IF, T_ELSEIF, T_FOREACH, T_FOR, T_WHILE, T_SWITCH, T_CATCH]);
    }
}

final class BlankLineAfterBlock extends Base
{
    private const OPENERS = [T_IF, T_FOREACH, T_FOR, T_WHILE, T_SWITCH, T_TRY];
    private const CONTINUES = [T_ELSE, T_ELSEIF, T_CATCH, T_FINALLY, T_WHILE];

    public function getName(): string { return 'Spike/blank_line_after_block'; }
    public function isCandidate(Tokens $tokens): bool { return $tokens->isAnyTokenKindsFound(self::OPENERS); }

    public function fix(\SplFileInfo $file, Tokens $tokens): void
    {
        for ($index = $tokens->count() - 1; $index > 0; --$index) {
            if (!$tokens[$index]->equals('}') || !$this->closesControlBlock($tokens, $index)) {
                continue;
            }
            $nextMeaningful = $tokens->getNextMeaningfulToken($index);
            if ($nextMeaningful === null || $tokens[$nextMeaningful]->equals('}')
                || $tokens[$nextMeaningful]->isGivenKind(self::CONTINUES)) {
                continue;
            }
            $space = $tokens[$index + 1];
            if (!$space->isWhitespace() || substr_count($space->getContent(), "\n") !== 1) {
                continue;
            }
            $indent = substr($space->getContent(), strrpos($space->getContent(), "\n") + 1);
            $tokens[$index + 1] = new Token([T_WHITESPACE, "\n\n" . $indent]);
        }
    }

    private function closesControlBlock(Tokens $tokens, int $close): bool
    {
        $open = $tokens->findBlockStart(Tokens::BLOCK_TYPE_CURLY_BRACE, $close);
        $before = $tokens->getPrevMeaningfulToken($open);
        if ($before === null) {
            return false;
        }
        if ($tokens[$before]->isGivenKind([T_ELSE, T_TRY, T_FINALLY])) {
            return true;
        }
        if (!$tokens[$before]->equals(')')) {
            return false;
        }
        $parenOpen = $tokens->findBlockStart(Tokens::BLOCK_TYPE_PARENTHESIS_BRACE, $before);
        $keyword = $tokens->getPrevMeaningfulToken($parenOpen);

        return $keyword !== null && $tokens[$keyword]->isGivenKind([T_IF, T_ELSEIF, T_FOREACH, T_FOR, T_WHILE, T_SWITCH, T_CATCH]);
    }
}
```

- [x] **Step 3: config do spike e uma amostra**

`$S/.php-cs-fixer.php`:

```php
<?php

require __DIR__ . '/src/Fixers.php';

return (new PhpCsFixer\Config())
    ->registerCustomFixers([new Spike\NoSpaceAfterKeyword(), new Spike\NoSpaceAroundBrace(), new Spike\BlankLineAfterBlock()])
    ->setRules([
        '@PSR12' => true,
        'blank_line_before_statement' => ['statements' => ['if', 'foreach', 'for', 'while', 'switch', 'try', 'return']],
        'Spike/no_space_after_control_keyword' => true,
        'Spike/no_space_before_control_brace' => true,
        'Spike/blank_line_after_block' => true,
    ])
    ->setFinder(PhpCsFixer\Finder::create()->in(__DIR__ . '/amostra'));
```

`$S/amostra/Exemplo.php`:

```php
<?php

class Exemplo
{
    public function run($items, $flag)
    {
        $total = 0;
        foreach ($items as $item) {
            $total += $item;
        }
        if ($flag) {
            $total = 1;
        } else {
            $total = 2;
        }
        try {
            $x = 1;
        } catch (\Throwable $e) {
            $x = 2;
        }
        $texto = "if (nao) { mexe }"; // if (nem aqui) {
        return $total;
    }
}
```

- [x] **Step 4: rodar duas vezes e conferir**

```bash
cd "$S" && vendor/bin/php-cs-fixer fix --config=.php-cs-fixer.php --using-cache=no -v && cat amostra/Exemplo.php && vendor/bin/php-cs-fixer fix --config=.php-cs-fixer.php --using-cache=no --dry-run --diff; echo "segunda rodada: $?"
```

Esperado no arquivo:

- `foreach($items as $item){`;
- linha em branco depois do `}` do `foreach`, antes do `if`;
- `if($flag){`, `}else{`, `try{` e `}catch(\Throwable $e){`;
- linha em branco antes do `$texto` e do `return`;
- a string e o comentário intactos.

A segunda rodada deve dar `0` sem diff.

- [x] **Step 5: rodar em 10 arquivos reais copiados**

```bash
# os caminhos dos projetos reais ficam num arquivo local, fora do git
source ~/sw-standards-local/env.sh
mkdir -p "$S/amostra-real" && ls "$AMOSTRA_API_SERVICES"/*/*.php | head -5 | xargs -I{} cp {} "$S/amostra-real/" && ls "$AMOSTRA_ESTILO_CONTROLLERS"/*/Controllers/*.php | head -5 | xargs -I{} cp {} "$S/amostra-real/"
cd "$S" && sed -i "s#/amostra')#/amostra-real')#" .php-cs-fixer.php && vendor/bin/php-cs-fixer fix --config=.php-cs-fixer.php --using-cache=no && php -l amostra-real/*.php | grep -v "No syntax errors" ; vendor/bin/php-cs-fixer fix --config=.php-cs-fixer.php --using-cache=no --dry-run; echo "idempotente: $?"; grep -c "if (" amostra-real/*.php | awk -F: '{s+=$2} END {print "if ( restantes:", s}'
```

Esperado:

- nenhum erro de sintaxe;
- `idempotente: 0`;
- `if ( restantes: 0`, com exceção de `if (` dentro de string ou comentário, que deve ser conferido à mão com `grep -n "if ("`.

- [x] **Step 6: registrar o resultado** em "Ajustes durante a execução", acrescentando uma linha ao fim do plano:

```bash
cat >> /var/www/ai-marketplace/docs/specs/2026-11-19-sw-standards-php-padroes-da-systemweb-para-php-do-framework/plan.md <<'EOF2'
- **AAAA-MM-DD** — task N (spike): <deu certo | falhou>. <o que precisou mudar>. <versão da ferramenta>.
EOF2
```

A linha diz:

- deu certo ou não;
- o que precisou mudar nos fixers;
- a versão do `php-cs-fixer`.

Se deu certo, as tasks 3 e 4 usam este código como base, com o namespace `Systemweb\CsFixer`.

---

### Task 2: spike — tratador global de exceção no fluxo do core

**Arquivos:**
- Criar: `$SCRATCH/spike-handler/` (cópia descartável do esqueleto)

**Depende de:** nada. Pode rodar em paralelo com a task 1.

**Deu certo se:**

- uma exceção lançada num service sai como JSON `{"status":"error","message":"server_error",...}`, HTTP 500 e
  sem trace;
- a falha de SQL também sai assim, ou fica registrado como o core a trata (se o core engole o erro de banco, a
  regra ganha a nota "erro de banco: o core já captura; confira o retorno").

**Se falhar** (o tratador não é chamado): a regra 19 muda para `try/catch` no topo do service público e um
pedido urgente ao core. Leve ao usuário.

- [x] **Step 1: copiar o esqueleto e criar uma rota que lança**

```bash
S=${TMPDIR:-/tmp}/sw-standards/spike-handler
rm -rf "$S" && cp -r /var/www/systemweb-framework "$S" && cd "$S" && ls app/Site/Rotas.php www/index.php config/Env.php
```

- [x] **Step 2: trocar o esqueleto copiado para API e registrar o tratador no `www/index.php`, antes do `new SysWeb\System()`**

O esqueleto vem como `application => 'website'`. No `config/Env.php` da cópia, troque para `'api'`, porque a
regra vale para API.

```php
set_exception_handler(function (\Throwable $e): void {
    error_log('unhandled ' . $e::class . ' ' . $e->getMessage());
    \SysWeb\Api\ResponseApi::error('server_error', 'Unexpected error', 500);
});
```

Confira o namespace real do `ResponseApi` com
`grep -rn "class ResponseApi" vendor/system-web/system-web-framework-core/system`.

- [x] **Step 3: duas rotas de teste em `app/Site/Rotas.php` e um controller**

```php
Rota::get('spike/lanca')->controller('spike')->method('lanca');
Rota::get('spike/sql')->controller('spike')->method('sql');
Rota::get('spike/builder')->controller('spike')->method('builder');
```

`app/Site/Controllers/SpikeController.php`:

```php
<?php

namespace App\Site\Controllers;

use SysWeb\Controller;
use SysWeb\Database\DB;

class SpikeController extends Controller
{
    public function lanca()
    {
        throw new \RuntimeException('segredo interno');
    }

    public function sql()
    {
        DB::query('SELECT * FROM tabela_que_nao_existe WHERE x = :x', ['x' => 1])->get();
    }

    public function builder()
    {
        DB::table('tabela_que_nao_existe')->select()->all();
    }
}
```

- [x] **Step 4: subir e chamar as duas rotas**

O `php -S` não passa argv, então o ambiente sai do `Host`. Use o host de dev do `config/Env.php` da cópia
(`localhost:8008`, no esqueleto) e o de produção (`your-domain.com.br`), porque em dev o core pode responder
sozinho, antes do tratador:

```bash
cd "$S/www" && php -S 127.0.0.1:8791 index.php > "$S/server.log" 2>&1 & PID=$!
sleep 1
for host in localhost:8008 your-domain.com.br; do
    for rota in lanca sql builder; do
        echo "== $host /spike/$rota"
        curl -s -i -H "Host: $host" http://127.0.0.1:8791/spike/$rota | sed -n '1p;$p'
    done
done
kill $PID
cat "$S/server.log" | tail -20
```

Esperado na primeira: `HTTP/1.1 500` e `{"status":"error","message":"server_error","data":"Unexpected error"}`,
sem "segredo interno".

Para `sql` e `builder`, anote o que veio em cada host. Em dev, o `Error.php` do core pode responder 500
sozinho com `SQLSTATE`, arquivo e linha, sem chamar o tratador: isso precisa entrar na regra 19 como "em dev o
core expõe o erro de banco".

- [x] **Step 5: registrar o resultado** em "Ajustes durante a execução", acrescentando uma linha ao fim do plano:

```bash
cat >> /var/www/ai-marketplace/docs/specs/2026-11-19-sw-standards-php-padroes-da-systemweb-para-php-do-framework/plan.md <<'EOF2'
- **AAAA-MM-DD** — task N (spike): <deu certo | falhou>. <o que precisou mudar>. <versão da ferramenta>.
EOF2
```

A linha diz:

- o que cada rota devolveu;
- como o core trata o erro de banco;
- a versão final de `assets/exception-handler.php`, que a task 5 usa.

---

### Task 3: fixer da systemweb, com fixtures e teste

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/assets/php-cs-fixer/Fixers.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/php-cs-fixer/autoload.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/php-cs-fixer/.php-cs-fixer.dist.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/php-cs-fixer/fixtures/*.in.php` e `*.out.php`
- Criar: `~/.claude/skills/sw-standards-php/tests/testar_fixer.sh`
- Alterar: `Makefile:60` (meta `fixer-test`)

**Depende de:** Task 1 (deu certo).

**Contrato que esta task publica:**

- os fixers `Systemweb/no_space_after_control_keyword`, `Systemweb/no_space_before_control_brace` e
  `Systemweb/blank_line_after_block`;
- `Systemweb\CsFixer\Fixers::all(): array`;
- `tests/testar_fixer.sh [arquivo.php…]`: sem argumento roda as fixtures; com argumento, formata cópias dos
  arquivos e imprime o diff. Sai com código 0 se tudo bate e com código diferente de 0 se algum arquivo está
  fora do estilo.

- [x] **Step 1: escrever as fixtures antes do fixer (red)**

Cada par é um caso. `fixtures/controle.in.php`:

```php
<?php

class Controle
{
    public function run($a, $items)
    {
        if ($a) {
            $x = 1;
        } elseif ($a > 2) {
            $x = 2;
        } else {
            $x = 3;
        }
        foreach ($items as $item) {
            $x += $item;
        }
        while ($x > 10) {
            $x--;
        }
        switch ($x) {
            case 1:
                break;
        }
        $label = match ($x) {
            1 => 'um',
            default => 'outro',
        };
        return $label;
    }
}
```

`fixtures/controle.out.php`:

```php
<?php

class Controle
{
    public function run($a, $items)
    {
        if($a){
            $x = 1;
        }elseif($a > 2){
            $x = 2;
        }else{
            $x = 3;
        }

        foreach($items as $item){
            $x += $item;
        }

        while($x > 10){
            $x--;
        }

        switch($x){
            case 1:
                break;
        }

        $label = match($x){
            1 => 'um',
            default => 'outro',
        };

        return $label;
    }
}
```

`fixtures/try.in.php`:

```php
<?php

class TryCatch
{
    public function run()
    {
        try {
            $x = 1;
        } catch (\RuntimeException $e) {
            $x = 2;
        } finally {
            $x = 3;
        }
        return $x;
    }
}
```

`fixtures/try.out.php`:

```php
<?php

class TryCatch
{
    public function run()
    {
        try{
            $x = 1;
        }catch(\RuntimeException $e){
            $x = 2;
        }finally{
            $x = 3;
        }

        return $x;
    }
}
```

`fixtures/intocado.in.php`, com string, comentário, chamada de função e closure, que **não** mudam:

```php
<?php

class Intocado
{
    public function run()
    {
        $texto = 'if ($a) { nada }';
        // foreach ($x as $y) { comentário }
        $soma = array_sum([1, 2]);
        $fn = function ($a) {
            return $a;
        };

        return $fn($soma) . $texto;
    }
}
```

`fixtures/intocado.out.php` tem o **mesmo conteúdo** do `intocado.in.php`.

`fixtures/sem-chaves.in.php`, com `if` de uma linha que ganha chaves:

```php
<?php

class SemChaves
{
    public function run($a)
    {
        if ($a) return 1;

        return 2;
    }
}
```

`fixtures/sem-chaves.out.php`:

```php
<?php

class SemChaves
{
    public function run($a)
    {
        if($a){
            return 1;
        }

        return 2;
    }
}
```

- [x] **Step 2: escrever o `tests/testar_fixer.sh`**

```bash
#!/usr/bin/env bash
# Testa o fixer da systemweb: as fixtures (antes/depois) e a idempotência. Com arquivos como argumento,
# formata cópias deles e mostra o diff. O php-cs-fixer fica num cache fora do repo.
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/sw-standards-php/php-cs-fixer"
if [ ! -x "$CACHE/vendor/bin/php-cs-fixer" ]; then
    mkdir -p "$CACHE" && (cd "$CACHE" && composer init -n --name=sw/fixer-cache >/dev/null && composer require -n --dev -q friendsofphp/php-cs-fixer:^3.95)
fi
FIXER="$CACHE/vendor/bin/php-cs-fixer"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/tools/php-cs-fixer" "$WORK/src"
cp "$SKILL/assets/php-cs-fixer/Fixers.php" "$SKILL/assets/php-cs-fixer/autoload.php" "$WORK/tools/php-cs-fixer/"
cp "$SKILL/assets/php-cs-fixer/.php-cs-fixer.dist.php" "$WORK/"
falhas=0
if [ "$#" -gt 0 ]; then
    for f in "$@"; do cp "$f" "$WORK/src/"; done
    # mostra o diff e sai com código diferente de 0 quando algum arquivo está fora do estilo
    (cd "$WORK" && "$FIXER" fix --dry-run --diff --using-cache=no 2>/dev/null)
    exit $?
fi
for entrada in "$SKILL"/assets/php-cs-fixer/fixtures/*.in.php; do
    nome="$(basename "$entrada" .in.php)"
    cp "$entrada" "$WORK/src/$nome.php"
done
(cd "$WORK" && "$FIXER" fix -q --using-cache=no)
for entrada in "$SKILL"/assets/php-cs-fixer/fixtures/*.in.php; do
    nome="$(basename "$entrada" .in.php)"
    if ! diff -u "$SKILL/assets/php-cs-fixer/fixtures/$nome.out.php" "$WORK/src/$nome.php"; then
        echo "FALHOU: $nome"; falhas=$((falhas + 1))
    fi
done
# sem cache: com ele, a segunda rodada pularia os arquivos e sempre daria 0
if ! (cd "$WORK" && "$FIXER" fix --dry-run -q --using-cache=no); then
    echo "FALHOU: segunda rodada mudou arquivos (não é idempotente)"; falhas=$((falhas + 1))
fi
[ "$falhas" -eq 0 ] && echo "fixer ok" || { echo "$falhas falha(s)"; exit 1; }
```

Rode: `chmod +x ~/.claude/skills/sw-standards-php/tests/testar_fixer.sh`.

- [x] **Step 3: meta do `make` no repo**, no `Makefile`, depois da meta `hooks` (a linha `.PHONY` ganha
  `fixer-test`):

```makefile
fixer-test:
	@bash $$(ls plugins/sw-standards-php/skills/sw-standards-php/tests/testar_fixer.sh 2>/dev/null || echo $(HOME)/.claude/skills/sw-standards-php/tests/testar_fixer.sh)
```

E no `help`:

```makefile
	@echo "make fixer-test                - testa o fixer de estilo da sw-standards-php"
```

- [x] **Step 4: rodar e confirmar que falha (sem o fixer ainda)**

Rode: `cd /var/www/ai-marketplace && make fixer-test`
Esperado: erro ao copiar `Fixers.php`, que ainda não existe.

- [x] **Step 5: escrever o fixer, a config e o autoload a partir do spike**

`assets/php-cs-fixer/Fixers.php` é o código do spike, com quatro mudanças:

- o namespace vira `Systemweb\CsFixer`;
- os nomes trocam `Spike/` por `Systemweb/`;
- `T_MATCH` entra em `closesControl` e em `closesControlBlock`;
- no fim, a classe abaixo.

```php
final class Fixers
{
    /** @return list<FixerInterface> */
    public static function all(): array
    {
        return [new NoSpaceAfterKeyword(), new NoSpaceAroundBrace(), new BlankLineAfterBlock()];
    }
}
```

`assets/php-cs-fixer/autoload.php`:

```php
<?php

// O fixer não é pacote composer: a etapa 0 copia esta pasta para tools/php-cs-fixer/ do projeto.
require_once __DIR__ . '/Fixers.php';
```

`assets/php-cs-fixer/.php-cs-fixer.dist.php`:

```php
<?php

require_once __DIR__ . '/tools/php-cs-fixer/autoload.php';

$finder = PhpCsFixer\Finder::create()
    ->in(__DIR__)
    ->exclude(['vendor', 'node_modules', 'storage', 'tools'])
    ->name('*.php');

return (new PhpCsFixer\Config())
    ->registerCustomFixers(Systemweb\CsFixer\Fixers::all())
    ->setLineEnding("\n")
    ->setIndent('    ')
    ->setRules([
        '@PSR12' => true,
        'control_structure_braces' => true,
        'blank_line_before_statement' => ['statements' => ['if', 'foreach', 'for', 'while', 'switch', 'try', 'return']],
        'Systemweb/no_space_after_control_keyword' => true,
        'Systemweb/no_space_before_control_brace' => true,
        'Systemweb/blank_line_after_block' => true,
    ])
    ->setFinder($finder);
```

- [x] **Step 6: rodar e confirmar que passa (restrição 2)**

Rode: `cd /var/www/ai-marketplace && make fixer-test`
Esperado: `fixer ok`. Se um par falhar, corrija o **fixer**, nunca o `.out.php`, a menos que o `.out.php`
contradiga a regra 14 do catálogo.

---

### Task 4: moldes de `tests/Support` e o `Pest.php`

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/assets/tests-support/Pest.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/tests-support/Support/Boot.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/tests-support/Support/TestDatabase.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/tests-support/Support/TestServer.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/tests-support/Support/Http.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/tests-support/Support/Fakes.php`
- Criar: `~/.claude/skills/sw-standards-php/assets/tests-support/Support/Fixtures.php`

**Depende de:** Task 3 (os moldes já nascem no estilo).

**Contrato que esta task publica:**

- `Boot::start()`: força `env=dev`, liga `APP_TESTING`, recarrega a config e recria o banco;
- `Boot::reset()`: limpa as tabelas, instala os fakes e volta o relógio;
- `TestDatabase::recreate()`;
- `TestServer::url(): string`;
- `Http::post`, `Http::get`, `Http::as($company)` devolvem `['status' => int, 'json' => array]`;
- `Fakes::install()`;
- `Fixtures::truncate()`.

- [x] **Step 1: ler os moldes reais antes de escrever**

```bash
source ~/sw-standards-local/env.sh   # caminhos locais, fora do git
P="$MOLDE_TESTES"
sed -n 1,80p $P/Pest.php $P/Support/TestDatabase.php; ls $P/Http/Support; sed -n 1,80p $P/Http/Support/TestServer.php $P/Http/Support/Http.php
```

Use-os como base. Tire tudo o que é do projeto (nomes, tabelas, fornecedores) e deixe só o genérico.

- [x] **Step 2: escrever os sete arquivos**

O `Pest.php` e o `Boot.php` são os do catálogo (item 26). O `Pest.php`:

```php
<?php

\Tests\Support\Boot::start();

pest()->extend(Tests\TestCase::class)->in('Unit', 'Integration', 'Http');

uses()->beforeEach(fn () => \Tests\Support\Boot::reset())->in('Integration', 'Http');
```

O `Boot.php`:

```php
<?php

namespace Tests\Support;

use Carbon\CarbonImmutable;

// Quando o core ganhar um boot de teste, este arquivo some e o Pest.php chama o core.
final class Boot
{
    public static function start(): void
    {
        self::_forceDevEnv();
        putenv('APP_TESTING=1');

        // o core lê a config antes do teste: recarrega já no modo de teste
        $GLOBALS['_ENVS'] = include __DIR__ . '/../../config/Env.php';
        $GLOBALS['_SWCONFIGS'] = include __DIR__ . '/../../config/Config.php';

        TestDatabase::recreate();
        TestServer::start();
    }

    public static function reset(): void
    {
        Fixtures::truncate();
        Fakes::install();
        CarbonImmutable::setTestNow();
    }

    private static function _forceDevEnv(): void
    {
        $envs = array_values(array_filter($_SERVER['argv'], fn ($arg) => str_starts_with($arg, 'env=')));

        if($envs && $envs !== ['env=dev']){
            fwrite(STDERR, "Testes só rodam com env=dev\n");
            exit(1);
        }

        $_SERVER['argv'][] = 'env=dev';
    }
}
```

Os outros cinco seguem o contrato acima e trazem, no topo, um comentário em português com o porquê:

- **`TestDatabase.php`**: recusa nome sem `_test`, apaga as tabelas (não o banco) e aplica `database/sql/*.sql`
  em ordem.
- **`TestServer.php`**: sobe `php -S` com `APP_TESTING=1` uma vez por rodada e derruba no `register_shutdown_function`.
- **`Http.php`**: chama o `TestServer` com `php-curl-class` e devolve status e JSON. O `as($company)` gera o
  token pelo `Jwt` do core.
- **`Fakes.php`**: o corpo é só `// uma linha por integração: Integracao::fake(new FakeIntegracao());`,
  mais um exemplo comentado. O comentário diz que fila e log ficam desligados pelo `.env` de teste.
- **`Fixtures.php`**: um `truncate()` genérico (`SET FOREIGN_KEY_CHECKS=0` e `TRUNCATE` de cada tabela) e um
  exemplo comentado de `Fixtures::company()` pelo ORM.

- [x] **Step 3: conferir a sintaxe e o estilo**

```bash
cd ~/.claude/skills/sw-standards-php && for f in assets/tests-support/*.php assets/tests-support/Support/*.php; do php -l "$f"; done && bash tests/testar_fixer.sh assets/tests-support/Pest.php assets/tests-support/Support/*.php
```

Esperado: `No syntax errors` em todos e nenhum diff impresso pelo fixer.

---

### Task 5: tratador global de exceção (asset)

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/assets/exception-handler.php`

**Depende de:** Task 2.

- [x] **Step 1: escrever o asset com a versão validada no spike**

Este é o ponto de partida. Troque o que o spike mostrou de diferente e anote em "Ajustes".

```php
<?php

// Tratador global do projeto: a exceção que ninguém capturou vira server_error 500, sem trace, e o detalhe vai
// para o log. Some quando o core ganhar o tratador dele. Registre uma vez, no www/index.php, antes do
// new SysWeb\System(): o construtor já faz o boot, e o que for lançado ali escaparia.
set_exception_handler(function (\Throwable $exception): void {
    $contexto = ($_SERVER['REQUEST_METHOD'] ?? 'cli') . ' ' . ($_SERVER['REQUEST_URI'] ?? '');

    $classe = $exception::class;

    // o warning de um envio que falha cairia no Error.php do core, que em dev responde sozinho com a URL do webhook
    set_error_handler(static function (int $tipo, string $mensagem): never {
        throw new \ErrorException($mensagem, 0, $tipo);
    });

    try{
        // sem o setTitle o DiscordLogger do core falha (propriedade estática não inicializada)
        \SysWeb\Logger\DiscordLogger::setTitle('Unhandled exception');
        \SysWeb\Logger\DiscordLogger::send("unhandled {$classe} {$contexto}: {$exception->getMessage()}", \SysWeb\Logger\ELogger::ERROR);
    }catch(\Throwable){
        error_log("unhandled {$classe} {$contexto}");
    }finally{
        restore_error_handler();
    }

    \SysWeb\Api\ResponseApi::error('server_error', 'Unexpected error', 500);
});
```

Confira os namespaces reais do `DiscordLogger`, do `ELogger` e do `ResponseApi`:

```bash
grep -rn "^namespace\|class DiscordLogger\|enum ELogger\|class ResponseApi" /var/www/system-web-framework-core/system/Logger /var/www/system-web-framework-core/system/Api 2>/dev/null | head
```

- [x] **Step 2: sintaxe e estilo**

Rode:

```bash
php -l ~/.claude/skills/sw-standards-php/assets/exception-handler.php && bash ~/.claude/skills/sw-standards-php/tests/testar_fixer.sh ~/.claude/skills/sw-standards-php/assets/exception-handler.php
```

Esperado: sem erro e sem diff.

---

### Task 6: checador das regras e as regras de arquitetura

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/tests/checar_regras.py`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/validacao-no-middleware.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/controller-fino.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/banco-no-model.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/services-e-integracoes.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/erro-e-resposta.md`

**Depende de:** Task 3.

**Contrato que esta task publica:**

- `tests/checar_regras.py [--estilo]` sai com 0 quando cada arquivo de `references/regras/` tem as seis seções.
- Com `--estilo`, também roda o fixer nos blocos `php` de **Certo** e **Como corrigir**.
- O formato de arquivo de regra, que as tasks 7 a 9 repetem.

**Fonte do conteúdo:** o catálogo `docs/specs/2026-11-19-sw-standards-php-padroes-da-systemweb-para-php-do-framework/referencias/decisoes-em-andamento.md`,
com os itens indicados em cada arquivo e a seção "Revisão do design" por cima. Exemplos genéricos (`Invoice`,
`Company`, `Billing`), **nunca** nome de projeto real.

- [x] **Step 1: escrever o checador (red: ainda não há regras)**

```python
#!/usr/bin/env python3
"""Confere os arquivos de references/regras/: as seis seções e, com --estilo, que os blocos php de Certo e
Como corrigir já estão no estilo da casa (passam pelo fixer sem mudar). O bloco de Errado fica de fora de
propósito: ele mostra o estilo proibido."""
import pathlib
import re
import subprocess
import sys
import tempfile
import textwrap

SECOES = ("Regra", "Por quê", "Certo", "Errado", "Como reconhecer", "Como corrigir")
PASTA = pathlib.Path(__file__).resolve().parent.parent / "references" / "regras"
FIXER = pathlib.Path(__file__).resolve().parent / "testar_fixer.sh"


def secoes(texto):
    return dict(re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", texto, re.S | re.M))


def blocos_php(texto):
    return re.findall(r"```php\n(.*?)```", texto, re.S)


def embrulhar(codigo):
    """Trecho solto vira um arquivo com <?php e uma classe, para o fixer poder rodar."""
    if codigo.lstrip().startswith("<?php"):
        return codigo
    codigo = textwrap.dedent(codigo)
    if re.search(r"^(final\s+)?(class|interface|enum|trait)\s", codigo, re.M):
        return "<?php\n\n" + codigo
    if re.search(r"^(public|private|protected)\s+(static\s+)?function", codigo, re.M):
        return "<?php\n\nclass Exemplo\n{\n" + textwrap.indent(codigo, "    ") + "}\n"
    corpo = textwrap.indent(codigo, "        ")
    return "<?php\n\nclass Exemplo\n{\n    public function exemplo()\n    {\n" + corpo + "    }\n}\n"


def main():
    estilo = "--estilo" in sys.argv
    arquivos = sorted(PASTA.glob("*.md"))
    if not arquivos:
        print("nenhuma regra em references/regras/")
        return 1
    erros = []
    with tempfile.TemporaryDirectory() as tmp:
        for arquivo in arquivos:
            partes = secoes(arquivo.read_text(encoding="utf-8"))
            faltando = [s for s in SECOES if s not in partes]
            if faltando:
                erros.append(f"{arquivo.name}: falta a seção {', '.join(faltando)}")
                continue
            if not estilo:
                continue
            for secao in ("Certo", "Como corrigir"):
                for n, codigo in enumerate(blocos_php(partes[secao]), 1):
                    alvo = pathlib.Path(tmp) / f"{arquivo.stem}-{secao.replace(' ', '_')}-{n}.php"
                    alvo.write_text(embrulhar(codigo), encoding="utf-8")
                    rodada = subprocess.run(["bash", str(FIXER), str(alvo)], capture_output=True, text=True)
                    if rodada.returncode != 0:
                        erros.append(f"{arquivo.name} [{secao} #{n}]: fora do estilo\n{rodada.stdout}")
    for erro in erros:
        print(erro)
    print(f"{len(arquivos)} regras, {len(erros)} problema(s)")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
```

Rode: `python3 ~/.claude/skills/sw-standards-php/tests/checar_regras.py`
Esperado: `nenhuma regra em references/regras/` e código 1.

Confira também que o checador falha de verdade: crie `references/regras/_teste.md` com as seis seções e um
bloco `if ($a) {` em **Certo**, rode `checar_regras.py --estilo` e confirme `1 problema(s)` apontando a seção
Certo. Depois apague o `_teste.md`.

- [x] **Step 2: escrever as cinco regras**, todas neste formato:

````markdown
# Validação no middleware

## Regra
<a regra em 2 a 5 linhas, no imperativo>

## Por quê
<o porquê em 2 a 4 linhas; cite o padrão quando houver (Thin Controller, Service Layer, Middleware/Pipeline)>

## Certo
```php
<exemplo genérico no estilo da casa>
```

## Errado
```php
<o mesmo caso feito errado>
```

## Como reconhecer
<sinais que o subagente procura: o que procurar no código e onde>

## Como corrigir
<passo a passo curto e, quando ajudar, um bloco php do resultado>

## Enquanto o core não corrigir
<só quando houver contorno; dizer a partir de qual versão do core a nota deixa de valer>
````

O que cada arquivo cobre:

| Arquivo | Itens do catálogo | O que não pode faltar |
|---|---|---|
| `validacao-no-middleware.md` | 1, 2, 12 (a leitura da entrada), 18b.1 | `Request::share` → `$this->shared()`; `Validator::check`; conversão de tipo uma vez, no `share`; nota do core: `min`/`max` numérico, zero e opcional com `if` manual e comentário |
| `controller-fino.md` | 6, 18c | só métodos públicos de ação; sem `try/catch`, query ou método privado; `ResponseApi::error` já encerra, então um `return` depois dele é ruído |
| `banco-no-model.md` | 4, 10, 18 (N+1) | filtro só no model; escrita pelo ORM (`find` → `save`, `new` → `insert`, `remove`); `findBy`/`listBy`/`countBy`/`existsBy`; sem trait de filtro; `DB::query` só com motivo e placeholder nomeado; N+1 com o mapa por id |
| `services-e-integracoes.md` | 5, 11 | `Services/<Domínio>/<Nome>Service.php` estático; `Integrations/<Fornecedor>/` com interface, `instance()` e `fake()`; Helpers puros; arrays entre camadas |
| `erro-e-resposta.md` | 3, 7, 8, 19 e a revisão | `ResponseApi::error('code', 'Frase', status)` com status sempre explícito; assinatura `error(string $message, array\|object\|string $data, int $status = 200)`; array de erro do service e como o controller responde; `Api::returnAttributes`; tratador global (`assets/exception-handler.php`); nunca `getMessage()`; formato por projeto via `docs/sw-standards/config.md` |

- [x] **Step 3: checar (restrições 3 e 4)**

Rode: `python3 ~/.claude/skills/sw-standards-php/tests/checar_regras.py --estilo`
Esperado: `5 regras, 0 problema(s)`.

---

### Task 7: regras de código

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/references/regras/dados-no-topo-e-sem-cadeia.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/ruido-defensivo.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/guard-clause-sem-else.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/estilo.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/nomes-e-enums.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/tipos-e-comentarios.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/datas-dinheiro-pacotes.md`

**Depende de:** Task 6 (formato e checador).

- [x] **Step 1: escrever as sete regras**

Cada arquivo segue o molde da task 6:

```markdown
# <Título da regra>

## Regra
## Por quê
## Certo
## Errado
## Como reconhecer
## Como corrigir
## Enquanto o core não corrigir   (só quando houver contorno)
```

O que cada arquivo cobre:

| Arquivo | Itens do catálogo | O que não pode faltar |
|---|---|---|
| `dados-no-topo-e-sem-cadeia.md` | 12, 13 | tudo que vem de fora lido no topo; nada de query ou cadeia no cabeçalho de `foreach`/`if`/`while`/`switch`/`return`; chamada simples como argumento continua valendo; antes e depois do caso `foreach (X::where(...)->get()->toArray() as …)` |
| `ruido-defensivo.md` | 18b (as 8) | os 8 antes e depois já aprovados; o 5 é `if($x)`/`if(!$x)` direto, com `=== null` só quando `0` ou `''` valem; a causa (o dado não foi tipado na borda) |
| `guard-clause-sem-else.md` | 18c | erro no topo e caminho feliz embaixo; evitar `else`/`elseif` sempre (valor padrão antes do `if`, `match` para três ou mais caminhos); no service `return` do array, no controller e no middleware `ResponseApi::error` sem `return` depois |
| `estilo.md` | 14 | o que o fixer faz (os três fixers próprios e os nativos) e o que a IA confere; como rodar (`vendor/bin/php-cs-fixer fix`); a seção **Errado** mostra `if (x) {` de propósito |
| `nomes-e-enums.md` | 15 | a tabela de nomes; banco em português manda na model e nas colunas; `EModel{Tabela}{Coluna}` e `E{Nome}` em `app/LogicApp/Enums/`; código de resposta snake_case e frase em inglês |
| `tipos-e-comentarios.md` | 16, 17 | tipo em parâmetro e retorno, sem `strict_types`; a versão do PHP é a do projeto; comentário só o porquê, em português, com espaço depois de `//` |
| `datas-dinheiro-pacotes.md` | 18 | `CarbonImmutable`; centavos inteiros ou `brick/money`; a tabela de pacotes preferidos (`php-curl-class`, nunca Guzzle direto; `Queue`/`Cache`/`Jwt` do core); a regra do pacote novo; SendGrid por padrão, com pergunta por projeto |

- [x] **Step 2: checar**

Rode: `python3 ~/.claude/skills/sw-standards-php/tests/checar_regras.py --estilo`
Esperado: `12 regras, 0 problema(s)`.

---

### Task 8: regras de segurança, rotas, jobs e infra

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/references/regras/transacao-e-fila.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/seguranca-e-config.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/rotas.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/jobs-e-scheduler.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/infra.md`

**Depende de:** Task 6. Pode rodar em paralelo com a task 7: os arquivos não se cruzam, e o checador só lê.

- [x] **Step 1: escrever as cinco regras**

Cada arquivo segue o molde da task 6:

```markdown
# <Título da regra>

## Regra
## Por quê
## Certo
## Errado
## Como reconhecer
## Como corrigir
## Enquanto o core não corrigir   (só quando houver contorno)
```

O que cada arquivo cobre:

| Arquivo | Itens do catálogo | O que não pode faltar |
|---|---|---|
| `transacao-e-fila.md` | 9, 23 (publicação) | transação no service; `try/catch` só para transação e integração externa; `DB::startTransaction`/`commit`/`roolback`; fila, e-mail e webhook só depois do commit; payload só com ids |
| `seguranca-e-config.md` | 20, 21 | `sw_env` só em `config/`; `sw_config` no código; nada de segredo no código nem nos testes; escopo por empresa perguntado por projeto, com a sugestão do `{Recurso}ExistsMiddleware` e do `Model::findByCompany($idCompany, $id)` |
| `rotas.md` | 22 | `v1/`; middleware em toda escrita e em toda rota com `{id}`; apelido = nome da classe sem o sufixo, em camelCase; um `Rotas.php` por tema, agrupado por recurso |
| `jobs-e-scheduler.md` | 23 | job e scheduler finos, com o exemplo aprovado; `ack`/`nack` sempre; `EQueue` com nome de teste separado; `Jobs::create()` |
| `infra.md` | 24 | Flyway `V{n}__descricao.sql`, sem alterar migration aplicada; `ECache` com prefixo e TTL; `(new Storage)->put()->image($file)`; arquivo comum por `Integrations/Aws`; `Help::pagination()` |

- [x] **Step 2: checar**

Rode: `python3 ~/.claude/skills/sw-standards-php/tests/checar_regras.py --estilo`
Esperado: o total de regras escritas até aqui e `0 problema(s)`.

---

### Task 9: regras de website e testes

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/references/regras/website-twig.md`
- Criar: `~/.claude/skills/sw-standards-php/references/regras/testes.md`

**Depende de:** Task 4 (os moldes que `testes.md` aponta) e Task 6.

- [x] **Step 1: escrever as duas regras**

Cada arquivo segue o molde da task 6:

```markdown
# <Título da regra>

## Regra
## Por quê
## Certo
## Errado
## Como reconhecer
## Como corrigir
## Enquanto o core não corrigir   (só quando houver contorno)
```

O que cada arquivo cobre:

| Arquivo | Itens do catálogo | O que não pode faltar |
|---|---|---|
| `website-twig.md` | 25 | a mesma arquitetura da API; controller fino com `$this->view()` e dados prontos do service; template só exibe; macro em `macros/`; `sw_seo()` no controller; `asset()` sempre. **Certo** e **Errado** têm um bloco `twig` além do `php` (o checador só roda o fixer nos blocos `php`) |
| `testes.md` | 26 e a revisão | a árvore de `tests/` aprovada e o que vai em cada pasta e arquivo; a tabela do que cada camada testa; os moldes em `assets/tests-support/`; `TestServer` por causa do `exit()`, subindo pelo `Support/app-router.php`, que instala os fakes dentro do servidor; fila e log desligados pelo `.env` de teste; sem Mockery, sem SQL no teste e sem serviço externo |

- [x] **Step 2: checar todas**

Rode: `python3 ~/.claude/skills/sw-standards-php/tests/checar_regras.py --estilo`
Esperado: `19 regras, 0 problema(s)`.

---

### Task 10: referências de fluxo (etapa 0, config do projeto, subagentes)

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/references/etapa-0.md`
- Criar: `~/.claude/skills/sw-standards-php/references/config-projeto.md`
- Criar: `~/.claude/skills/sw-standards-php/references/subagentes.md`

**Depende de:** Tasks 3, 4, 5 e 9 (os assets e as regras que estes arquivos citam).

- [x] **Step 1: `etapa-0.md`, um checklist em ordem, cada passo com o comando ou o arquivo e como conferir:**

1. **Core ≥ 1.10.** Ler o `composer.lock`
   (`grep -A3 '"name": "system-web/system-web-framework-core"' composer.lock | grep version`). Abaixo disso,
   propor `composer require system-web/system-web-framework-core:^1.10` e rodar os testes existentes.
2. **`friendsofphp/php-cs-fixer` em dev.** Copiar `assets/php-cs-fixer/{Fixers.php,autoload.php}` para
   `tools/php-cs-fixer/` e `.php-cs-fixer.dist.php` para a raiz.
3. **Banco `_test` no `config/Database.php`,** escolhido por `getenv('APP_TESTING')`. Mostrar o trecho, porque
   o arquivo é do projeto.
4. **Testes.** Copiar `assets/tests-support/` para `tests/`, sem sobrescrever o que já existe, e instalar o Pest
   se faltar. O `composer.json` precisa de `"autoload-dev": {"psr-4": {"Tests\\": "tests/"}}`, porque o
   `Support/app-router.php` carrega os fakes pelo autoload dentro do servidor de teste.
5. **Tratador de exceção.** Registrar `assets/exception-handler.php` no `www/index.php`.
6. **Regras velhas.** Listar `.claude/rules/*` e `.claude/skills/create-*` e marcar o que contradiz cada regra.
   Com aprovação, apagar ou reduzir a um ponteiro.
7. **Linha no `AGENTS.md`.** Gravar a linha; no `CLAUDE.md`, só se ele já existir.
8. **Config.** Criar `docs/sw-standards/config.md` e `andamento.md` a partir de `config-projeto.md`.

- [x] **Step 2: `config-projeto.md`**, com o molde dos dois arquivos:

```markdown
# Padrões deste projeto (sw-standards-php)

## Respostas
- Formato do erro: código específico + frase (padrão) | outro: <descrever>
- E-mail: SendGrid (padrão) | outro: <pacote>
- Multiempresa: não | sim — coluna `<id_company>`, mecanismo `<{Recurso}ExistsMiddleware>`
- PHP: <versão do composer.json/Docker>   · Core: <versão do composer.lock>

## Exceções aceitas
| Arquivo:linha | Regra | Motivo | Quem aceitou | Data |
|---|---|---|---|---|
```

```markdown
# Andamento da padronização

| Etapa | Domínio | Estado | Data | Commit |
|---|---|---|---|---|
| 0 | preparação | pendente | | |
| 1 | formatador | pendente | | |
```

- [x] **Step 3: `subagentes.md`**, com um prompt por família. Cada um traz:

- os arquivos de regra a ler;
- o que varrer;
- o formato da saída (`arquivo:linha · regra · trecho · correção proposta`);
- a instrução de ignorar as exceções aceitas do `config.md`;
- a instrução "só leia, não edite".

| Família | Regras | Onde olhar |
|---|---|---|
| Arquitetura | `validacao-no-middleware`, `controller-fino`, `banco-no-model`, `services-e-integracoes`, `transacao-e-fila` | `app/`, `middleware/` |
| Código | `dados-no-topo-e-sem-cadeia`, `ruido-defensivo`, `guard-clause-sem-else`, `nomes-e-enums`, `tipos-e-comentarios`, `datas-dinheiro-pacotes` | cada arquivo PHP fora de `vendor/` |
| Erro e segurança | `erro-e-resposta`, `seguranca-e-config` | `app/`, `middleware/`, `config/`, `tests/` |
| Rotas, jobs e infra | `rotas`, `jobs-e-scheduler`, `infra` | `app/*/Rotas.php`, `config/Middleware.php`, `jobs/`, `scheduler/`, `database/` |
| Testes | `testes` | `tests/`, `phpunit.xml` |
| Website | `website-twig` | `app/*/Views`, `macros/`, controllers do website |

---

### Task 11: `SKILL.md` (com a skill-creator)

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/SKILL.md`

**Depende de:** Task 10.

- [x] **Step 1: carregar a skill-creator e ler o molde da casa**

Invoque a skill `skill-creator:skill-creator` (ferramenta Skill) e siga o que ela diz sobre anatomia, tamanho
do `SKILL.md`, *progressive disclosure* e descrição. Leia também
`/var/www/ai-marketplace/plugins/sw-refactor/skills/sw-refactor/SKILL.md`, para o tom e o formato da casa:
frontmatter, PT-BR, "toda decisão via AskUserQuestion" e o arsenal.

- [x] **Step 2: escrever o `SKILL.md`**

O frontmatter começa assim (a `description` é refinada com a skill-creator e testada na task 13):

```markdown
---
name: sw-standards-php
description: Impõe os padrões da systemweb em projetos PHP do framework system-web-framework-core (API e website Twig): validação no middleware, controller fino, banco só no model, Services/<Domínio>, erro com status explícito, sem ruído defensivo, guard clause sem else, estilo da casa com fixer próprio e testes com banco próprio. Dois modos: guarda ao escrever e auditoria com correção por domínio. Use SEMPRE que for criar ou alterar PHP num projeto do framework ("cria o endpoint", "faz o service", "adiciona um middleware") ou padronizar um ("padroniza este projeto", "audita o padrão", "o que está fora do padrão?", "segue o padrão systemweb"). NÃO use para Vue, PHP fora do framework, revisar diff (sw-code-review) nem caçar código morto (sw-dead-code-scan).
---
```

**Frontmatter:**

- `name: sw-standards-php`;
- `description` com o que faz e os gatilhos, em português e em inglês:
  - "cria o endpoint", "faz o service", "adiciona um middleware" num projeto do framework;
  - "padroniza este projeto", "audita o padrão", "o que está fora do padrão?", "segue o padrão systemweb";
- o "NÃO use para": Vue, PHP fora do framework, revisar diff (`sw-code-review`), código morto
  (`sw-dead-code-scan`).

**Corpo, menos de 500 linhas:**

1. **O que é e a fonte única:** ignora a `sw-refactor`.
2. **Como saber que o projeto é do framework:** o `composer.json` e o `composer.lock`.
3. **Modo escrever:**
   - carregar só as regras do que vai escrever, com a tabela tipo de arquivo → regras;
   - rodar o fixer nos arquivos tocados.
4. **Modo auditar e corrigir:** reconhecer → etapa 0 (`references/etapa-0.md`) → varredura com subagentes
   (`references/subagentes.md`) → relatório → etapas por domínio, com o ciclo de teste antes.
5. **Perguntas por projeto e onde gravar** (`references/config-projeto.md`).
6. **Arsenal:** `sw-auto-test`, `sw-code-review`, `sw-git-commit` e `sw-dead-code-scan`, sempre perguntando
   antes e seguindo sem a skill se ela faltar.
7. **Regra: toda decisão via `AskUserQuestion`.**
8. **Índice das 19 regras,** com uma linha cada e o link.

- [x] **Step 3: conferir tamanho e links**

```bash
cd ~/.claude/skills/sw-standards-php && wc -l SKILL.md && grep -o 'references/[a-z0-9/_-]*\.md' SKILL.md | sort -u | while read f; do [ -f "$f" ] || echo "LINK QUEBRADO: $f"; done
```

Esperado: menos de 500 linhas e nenhum `LINK QUEBRADO`.

---

### Task 12: projeto fixture para a sw-skill-test

**Arquivos:**
- Criar: `~/.claude/skills/sw-standards-php/tests/fixture/` (um projeto mínimo do framework)
- Criar: `~/.claude/skills/sw-standards-php/tests/GABARITO.md` (fora do fixture, para a auditoria não lê-lo)

**Depende de:** Task 9.

- [x] **Step 1: montar o esqueleto do fixture**

Ele tem:

- `composer.json` com `system-web/system-web-framework-core` e um `composer.lock` mínimo com a versão `v1.11.0`;
- `config/Env.php` com `application => 'api'`;
- `docs/sw-standards/config.md` pronto, multiempresa com `id_company`;
- `app/Site/Rotas.php`, `config/Middleware.php`, `app/LogicApp/{Models,Services/Billing,Enums}`, `middleware/`,
  `jobs/`, `scheduler/` e `tests/`.

Os nomes são genéricos (`Invoice`, `Company`, `Billing`).

- [x] **Step 2: plantar uma violação por arquivo de regra (18, sem o `estilo.md`)** e as 5 armadilhas
  legítimas. O `GABARITO.md` tem duas tabelas:

```markdown
| # | Regra | Arquivo:linha | O que está errado |
|---|---|---|---|
| 1 | validacao-no-middleware | app/Site/Controllers/InvoiceController.php:14 | valida `amount` no controller |
| … | … (uma linha por regra, 18 no total) | | |

| # | Armadilha (legítima, não acusar) | Arquivo:linha |
|---|---|---|
| A1 | SQL cru com comentário do motivo no model | app/LogicApp/Models/Invoice.php:40 |
| A2 | `??` em campo opcional | app/LogicApp/Services/Billing/InvoiceService.php:22 |
| A3 | `@unlink($tmp)` com comentário de limpeza | app/LogicApp/Integrations/Aws/S3Storage.php:31 |
| A4 | `=== null` onde o zero é valor válido | app/LogicApp/Services/Billing/DiscountService.php:18 |
| A5 | `Invoice::find($id)` e `save()` no service | app/LogicApp/Services/Billing/InvoiceService.php:35 |
```

O código fora das violações segue todas as regras, para não haver ruído não planejado. As linhas do gabarito
são conferidas com `grep -n`.

- [x] **Step 3: conferir o fixture**

```bash
cd ~/.claude/skills/sw-standards-php/tests && find fixture -name '*.php' -exec php -l {} \; | grep -v "No syntax errors"; grep -c "^| [0-9]" GABARITO.md; grep -c "^| A[0-9]" GABARITO.md
# o código limpo do fixture também passa pelo fixer, para não haver ruído de estilo não planejado
bash testar_fixer.sh $(grep -rL "VIOLACAO-ESTILO" --include=*.php fixture)
```

Esperado: sem erros de sintaxe, `18`, `5` e nenhum diff do fixer.

---

### Task 13: medir a skill com a sw-skill-test

**Arquivos:**
- Teste: `~/.claude/skills/sw-standards-php/tests/fixture/` (usa; não altera)

**Depende de:** Tasks 11 e 12.

- [x] **Step 1: rodar a `sw-skill-test` em modo comportamento**

Copie só o fixture para uma pasta temporária, para a auditoria não ver o gabarito:

```bash
ALVO=$(mktemp -d) && cp -r ~/.claude/skills/sw-standards-php/tests/fixture/. "$ALVO/" && echo "$ALVO"
```

Invoque a skill `sw-skill-test` sobre a `sw-standards-php`, no modo auditar, apontando o fixture para `$ALVO`
e mandando usar **o gabarito dado**, `~/.claude/skills/sw-standards-php/tests/GABARITO.md`, em vez de derivar
um.

Limite conhecido: no teste, a skill roda num subagente e faz a varredura numa passada só.

- [x] **Step 2: conferir a restrição 1**

Esperado:

- **≥ 16 das 18** violações achadas;
- **≤ 1** armadilha acusada.

Se falhar, ajuste a seção **Como reconhecer** da regra que escapou, ou a que acusou a armadilha, e rode de
novo. Registre cada rodada em "Ajustes".

- [x] **Step 3: rodar a `sw-skill-test` em modo disparo**

Esperado: dispara nas frases certas e fica quieta nas pegadinhas (Vue, PHP sem o framework, revisar diff).
Ajuste a `description` se precisar.

---

### Task 14: segurança, sync e changelog

**Arquivos:**
- Alterar: `CHANGELOG.md` (entrada da skill nova em `## [Não publicado]`)

**Depende de:** Task 13.

- [x] **Step 1: conferir vazamento (restrição 5)**

```bash
cd /var/www/ai-marketplace && grep -rniFf ~/sw-standards-local/nomes.txt ~/.claude/skills/sw-standards-php docs/specs/2026-11-19-sw-standards-php-padroes-da-systemweb-para-php-do-framework; grep -rnE "/(home|Users)/" ~/.claude/skills/sw-standards-php docs/specs/2026-11-19-sw-standards-php-padroes-da-systemweb-para-php-do-framework; echo "fim"
```

Esperado: só `fim`. A lista de nomes fica em `~/sw-standards-local/nomes.txt`, fora do git.

- [x] **Step 2: sincronizar a skill nova**

Rode: `cd /var/www/ai-marketplace && make sync SKILL=sw-standards-php CATEGORY=development`
Esperado: o plugin é criado em `plugins/sw-standards-php/`, e `marketplace.json` e o `README.md` são atualizados.

- [x] **Step 3: entrada no `CHANGELOG.md`**, no topo de `### Adicionado`:

```markdown
- `sw-standards-php` (v0.1.0): **padrões da systemweb para PHP do framework** (API e website Twig). Dois modos:
  escrever (carrega só as regras do que está sendo escrito e formata com o fixer da casa) e auditar e corrigir
  (subagentes por família de regra, relatório e correção por domínio com teste antes). 19 regras com exemplo
  certo e errado: validação no middleware, controller fino, banco só no model, Services/Integrations, erro com
  status explícito, ruído defensivo, guard clause sem else, nomes, testes com banco próprio e mais. Etapa 0
  prepara o projeto (core ≥ 1.10, banco de teste, tests/Support, fixer, tratador de exceção). Fixer próprio do
  php-cs-fixer para `if(`/`){` e linha em branco depois de bloco.
```

- [x] **Step 4: gate de segurança**

```bash
cd /var/www/ai-marketplace && git add -A && make check && git diff --cached --name-only | xargs grep -lE "/(home|Users)/" 2>/dev/null; echo "fim"
```

Esperado: `nada sensível detectado` e só `fim`.

---

## Ajustes durante a execução

- **2026-11-20** — revisão do plano, que rodou os trechos críticos no scratchpad. Os três fixers funcionaram
  como escritos, com o php-cs-fixer 3.95.32 e o PHP 8.4.26, na amostra, em 10 arquivos reais e nos 118 do core:
  sem erro, os nativos não desfazem, string e comentário ficam intactos e as 4 fixtures passam. Ajustes feitos:
  - o `testar_fixer.sh` mostra o diff e propaga o código de saída;
  - `--using-cache=no` em toda rodada, porque o cache fazia a idempotência sempre passar;
  - `embrulhar()` faz dedent e indent;
  - a sintaxe do asset de exceção foi corrigida, com o `DiscordLogger::setTitle()` antes do `send`;
  - o tratador passa a ser registrado antes do `new SysWeb\System()`;
  - o spike 2 testa a API com Host de dev e de prod e inclui o builder;
  - os nomes reais saíram do plano, com os caminhos em `~/sw-standards-local/`, fora do git;
  - o gabarito saiu do fixture;
  - o `make fixer-test` prefere a cópia do repo.
- **2026-11-20** — Base da revisão final: f74d33de8414e6ad5c216f6bb4aa86efa81bc83c (repo; a fonte em `~/.claude/skills/sw-standards-php` não é git, e o diff aparece depois do `make sync`).
- **2026-11-20** — task 1 (spike): deu certo, sem nenhuma mudança nos fixers. Na amostra e em 10 arquivos reais: sem erro de sintaxe, idempotente, 0 `if (` restantes, string e comentário intactos, e os nativos do @PSR12 não desfazem. php-cs-fixer 3.95.32, PHP 8.4.26.
- **2026-11-20** — task 2 (spike): deu certo, com um ajuste. Com um MariaDB descartável no scratchpad, as três
  rotas deram 500. Em dev e em prod:
  - **exceção no service e `DB::query`:** chegam ao tratador e saem como `server_error`;
  - **builder (`DB::table()->select()->all()`) e conexão:** o core faz `trigger_error(E_USER_ERROR)`. Em prod
    chega ao tratador; **em dev, o `Error.php` responde sozinho com SQLSTATE, arquivo e linha**. Isso entra na
    regra 19 como nota.

  Ajuste no asset: um `set_error_handler` que lança durante o envio ao Discord, com `restore_error_handler()` no
  `finally`. Sem ele, o warning de um webhook fora do ar caía no `Error.php`, que em dev responde com a URL do
  webhook. Foram validados os casos sem webhook, com webhook inalcançável e com webhook ok.
- **2026-11-20** — tasks 3, 4 e 5 concluídas. Ajuste da task 4: o servidor de teste é outro processo, e os fakes
  do Pest não chegavam nele. Entrou `Support/app-router.php`, o roteador do `php -S`: ele recusa sem
  `APP_TESTING`, instala os fakes e entrega ao `www/index.php`, no molde do projeto mais maduro. O `TestServer`
  sobe por ele. A etapa 0 passa a exigir o `autoload-dev` de `Tests\`. Decisões da task 4:
  - `Http` com `__callStatic` e `__call`, para `Http::post` e `Http::as($c)->post`;
  - token por `SysWeb\Jwt\Jwt::generate`;
  - Host numa constante;
  - `Fixtures::truncate()` lê o `information_schema` e pula a lista `KEEP`.
- **2026-11-20** — task 6 concluída: 5 regras, 0 problemas, e o checador reprova o código fora do estilo
  (teste com `_teste.md`). O que se confirmou no core v1.11.0 e as tasks 7 a 9 seguem:
  - a regra do Validator é `require`;
  - o `where` usa `'col ='`, `'AND' => [...]` e `'col IN'`;
  - o middleware é `__invoke(Request, Response, callable $next)`;
  - **o core não tem `Auth::companyId()`**: a empresa vem de `$this->shared('company')`, que o middleware de
    auth compartilha.
- **2026-11-20** — tasks 7 e 8 concluídas, com 17 regras e 0 problemas. Correções feitas na conferência:
  - o enum `EModelInvoicesStatus` virou `EModelInvoiceStatus`, e a tabela de exemplo ficou no singular
    (`invoice`), porque é a convenção dos projetos e do core, cuja FK padrão é `id_{tabela}`;
  - `sw_config('a.b')` virou `sw_config('a')['b']`, porque o core não lê chave com ponto;
  - o namespace do middleware é `Middleware`, como no esqueleto.

  Fatos do core que as regras seguem:
  - o rollback é `DB::roolback()`;
  - erro de escrita do builder devolve `null`, não exceção;
  - `middlewareBefore` substitui em vez de acumular, então os middlewares vão num array só;
  - o worker de job não passa pelo tratador global, então o `handle` tem `try/catch` com `ack`/`nack`;
  - o `Cache` não tem prefixo;
  - o `Storage` só tem `image()`.
- **2026-11-20** — task 9 concluída: 19 regras, 0 problemas. Na conferência, 8 regras foram uniformizadas: a
  tabela de exemplo ficou no singular (`invoice`), e a FK virou `id_{tabela}` (`id_company`, `id_customer`,
  `id_invoice`), que é o padrão do core e dos projetos. Os blocos Pest de `testes.md` abrem com `<?php` por causa
  do `use` no topo, e o `TestCase.php` é criado vazio, sem molde.
- **2026-11-20** — task 10 concluída. Decisões:
  - o tratador vai para `config/ExceptionHandler.php`, porque `www/` é pública, com o `require` no
    `www/index.php` antes do `new SysWeb\System()`;
  - o `MARIADB_DBNAME_TEST` fica no `.env`, porque é o único lugar que o core lê;
  - a etapa 0 cria um `phpunit.xml` com as três suítes e proíbe o `pest --init`;
  - há pergunta antes de subir o core, antes do `composer require --dev` e antes de mexer em `Database.php`,
    `index.php`, `composer.json` e nas regras velhas;
  - os subagentes recebem as respostas e as exceções do projeto copiadas no prompt;
  - o estilo fica com o fixer `--dry-run`, sem subagente.
- **2026-11-20** — task 11 concluída: `SKILL.md` com 213 linhas e sem link quebrado, seguindo a skill-creator (description insistente com gatilhos em PT e EN, progressive disclosure, imperativo e o porquê de cada passo).
- **2026-11-20** — task 12 concluída: o fixture tem 18 violações, 5 armadilhas e a etapa 0 feita, e o gabarito
  está em `tests/GABARITO.md`. O `application` é `website`, porque o fixture tem os temas `Api` e `Site` (Twig) e
  a violação 17 é de website.

  Ajustes feitos na conferência:
  - **Moldes de `tests/Support` que quebravam regras da própria skill:**
    - o `Http.php` passa a usar `JSON_THROW_ON_ERROR`;
    - cada `@` do `TestServer.php` ganhou o comentário do motivo;
    - o `sw_env` e o PDO do `TestDatabase` e o `DB::query` do `Fixtures::truncate()` ficaram como **exceção
      documentada**: um comentário no topo e uma linha nas regras `banco-no-model`, `seguranca-e-config` e
      `testes`. O fixture foi atualizado do mesmo jeito.
  - **`testar_fixer.sh`:** os arquivos de mesmo nome se sobrescreviam no modo com arquivos; agora há um prefixo
    numérico. O fixture inteiro, menos o `tools/` que a config exclui, passa sem diff.
- **2026-11-20** — task 13 concluída, com a sw-skill-test sobre o fixture copiado para `/tmp` e o gabarito
  dado. **Restrição 1 cumprida:** a skill achou 18 de 18 violações e acusou 0 de 5 armadilhas, contra a meta de
  ≥ 16 e ≤ 1; também não acusou as exceções de `tests/Support`. O baseline sem a skill achou 16, acusou 2
  armadilhas (A1 e A3) e recomendou coisas contra as decisões da casa, mas achou bugs fora das regras que a
  skill ignora. O dono **não** quis a seção "Achados fora das regras".
  **Disparo:** os 2 juízes acertaram as 8 frases que devem disparar e as 7 pegadinhas, e divergiram em
  "escreve testes pro service". Por isso entrou na descrição o gatilho de testes, junto com a sw-auto-test
  [usuário].
- **2026-11-20** — task 14 concluída. O caminho do scratchpad, que tinha UID e id de sessão, saiu do plano e
  virou `${TMPDIR:-/tmp}/sw-standards`. A skill foi publicada com `make sync`, como v0.1.0 na categoria
  development, e o CHANGELOG foi escrito. O `make fixer-test` passa pela cópia do repo, o `make check` está limpo
  e o grep de nomes e caminhos não achou nada.
- **2026-11-20** — juiz final e code review de contexto vazio, com os 9 pontos corrigidos a pedido do dono.
  **Crítico:** o `Model` do core não é array, então `isset($result['error'])` lançava `Error` em todo caminho de
  sucesso. O teste passou a ser `is_array($result) && isset($result['error'])` em todas as regras e no fixture, e
  a correção foi provada contra o core. Os outros 8:
  - `.env.testing` saiu, porque o core só lê o `.env`; o `config/` escolhe pelo `APP_TESTING`;
  - o tratador ficou num caminho só, `config/ExceptionHandler.php`, com o `require` no `www/index.php`, e a
    auditoria procura os dois;
  - o `Http` de teste despacha pelo verbo;
  - o `insert()` do item é conferido dentro da transação;
  - o exemplo de `estilo.md` ficou neutro;
  - `testes.md` usa `v1/`;
  - a chave do array de entrada virou `invoiceData`;
  - o índice do dossiê foi atualizado.

  As linhas 5 e 15 do gabarito mudaram de lugar. A medição da task 13 foi feita antes dessas correções, que não
  mexem nas violações nem nas armadilhas.
