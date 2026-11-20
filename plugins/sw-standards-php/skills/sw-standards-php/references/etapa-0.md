# Etapa 0: preparar o projeto antes de corrigir

Sem a etapa 0, a skill só audita, não corrige. Siga os passos na ordem. Cada um tem o comando ou o arquivo e
**como conferir**. Passo conferido vira uma linha no resumo para o usuário. Passo que falhou para tudo: conserte ou
pergunte, e não pule para o próximo.

Convenções deste arquivo:

- `$SKILL` é a pasta desta skill (a que tem o `SKILL.md`). Todo comando roda na raiz do projeto.
- Arquivo do projeto que a skill não criou (`composer.json`, `config/Database.php`, `www/index.php`, `AGENTS.md`):
  mostre o trecho antes e depois e só grave com aprovação.
- Toda pergunta ao usuário vai por `AskUserQuestion`, com opções.
- Não rode `composer install` nem `composer update`. `composer require` só depois da aprovação do passo.

## Antes de começar

1. **Árvore limpa.** `git status --porcelain` tem que voltar vazio. Se houver mudança, pergunte (`AskUserQuestion`)
   se o usuário quer commitar ou guardar antes. Não misture a etapa 0 com trabalho dele.
2. **Testes que já existem.** Se o projeto já tem suíte (`vendor/bin/pest` ou `vendor/bin/phpunit`), rode e anote
   o resultado. É a base para comparar depois do passo 1.

## 1. Core ≥ 1.10

```bash
grep -A3 '"name": "system-web/system-web-framework-core"' composer.lock | grep '"version"'
```

- **1.10 ou mais nova:** passo feito.
- **Abaixo:** o `Request::share` não existe, e as regras de validação não funcionam. Pergunte antes de subir:

  > `AskUserQuestion`: "O core está na <versão>. A etapa 0 precisa da 1.10 ou mais nova. Posso rodar
  > `composer require system-web/system-web-framework-core:^1.10`?" Opções: **Subir agora** · **Não subir (a skill
  > fica só auditando)**.

  Com aprovação:

  ```bash
  composer require system-web/system-web-framework-core:^1.10
  ```

**Conferir:** o `grep` acima mostra `v1.10.x` ou mais. Rode de novo a suíte que já existia: o resultado tem que ser
igual ao anotado antes. Se piorou, mostre a falha e pare.

## 2. `php-cs-fixer` e o fixer da systemweb

Pergunte uma vez pelas dependências de dev desta etapa (o fixer aqui e o Pest no passo 4):

> `AskUserQuestion`: "Posso instalar como dependência de dev: `friendsofphp/php-cs-fixer` e, se faltar,
> `pestphp/pest`?" Opções: **Instalar** · **Não instalar**.

```bash
composer require --dev friendsofphp/php-cs-fixer
mkdir -p tools/php-cs-fixer
cp $SKILL/assets/php-cs-fixer/Fixers.php $SKILL/assets/php-cs-fixer/autoload.php tools/php-cs-fixer/
cp -n $SKILL/assets/php-cs-fixer/.php-cs-fixer.dist.php .php-cs-fixer.dist.php
```

Não copie a pasta `fixtures/` do asset: ela só serve para testar o fixer. Se o projeto já tinha um
`.php-cs-fixer.dist.php` ou `.php-cs-fixer.php`, o `cp -n` não sobrescreve: mostre a diferença para o usuário e
pergunte qual fica. A config da skill é a padrão.

**Conferir:**

```bash
vendor/bin/php-cs-fixer fix --dry-run --diff --using-cache=no > /dev/null; echo $?
```

`0` (nada a mudar) ou `8` (há o que formatar) servem. Qualquer outro código é erro de config ou de autoload: leia a
mensagem e conserte. **Não rode o `fix` de verdade aqui.** Formatar o projeto é a etapa 1, num commit separado.

## 3. Banco `_test` no `config/Database.php`

O `Boot` dos testes força `env=dev` e liga `APP_TESTING`. O bloco `dev` escolhe o banco por esse sinal. Mostre o
trecho e peça aprovação, porque o arquivo é do projeto:

> `AskUserQuestion`: "Vou trocar o `dbname` do bloco `dev` do `config/Database.php` para usar o banco `_test`
> quando `APP_TESTING` estiver ligado. Posso gravar?" Opções: **Gravar** · **Ajustar antes** · **Não gravar**.

```php
'dbname' => getenv('APP_TESTING') ? sw_env('MARIADB_DBNAME_TEST') : sw_env('MARIADB_DBNAME'),
```

Ponha `MARIADB_DBNAME_TEST=<banco>_test` no `.env` local, porque o core só lê o `.env`. Ponha a chave sem valor no
`.env.example`. O nome **tem que** terminar em `_test`: o `TestDatabase` apaga as tabelas desse banco e recusa
outro nome.

**Conferir:**

```bash
APP_TESTING=1 php -r 'require "vendor/autoload.php"; echo (include "config/Database.php")["dev"]["db"]["dbname"], PHP_EOL;'
php -r 'require "vendor/autoload.php"; echo (include "config/Database.php")["dev"]["db"]["dbname"], PHP_EOL;'
```

O primeiro mostra o nome com `_test`. O segundo mostra o banco de dev, que continua igual.

## 4. Testes: `tests/Support/` e o `Pest.php`

```bash
mkdir -p tests/Support
cp -n $SKILL/assets/tests-support/Pest.php tests/Pest.php
cp -n $SKILL/assets/tests-support/Support/*.php tests/Support/
test -f tests/TestCase.php || printf '<?php\n\nnamespace Tests;\n\nuse PHPUnit\\Framework\\TestCase as BaseTestCase;\n\nabstract class TestCase extends BaseTestCase\n{\n}\n' > tests/TestCase.php
```

O `cp -n` não sobrescreve. Se já existia `tests/Pest.php` ou algum `Support/*.php`, mostre a diferença para o
molde e pergunte se troca. Sem o molde, o `Http/` e o banco `_test` não funcionam.

1. **Pest.** Se `vendor/bin/pest` não existe, instale com a aprovação do passo 2:
   `composer require --dev pestphp/pest`. Não rode `pest --init`, porque ele sobrescreve o `Pest.php`.
2. **`composer.json`.** Precisa do `autoload-dev`. O `Support/app-router.php` carrega os fakes pelo autoload,
   dentro do servidor de teste. Mostre o trecho e grave com aprovação:

   ```json
   "autoload-dev": {
       "psr-4": {
           "Tests\\": "tests/"
       }
   }
   ```

   Depois, rode `composer dump-autoload`.
3. **`phpunit.xml`.** Se não existir, crie com as três suítes:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <phpunit bootstrap="vendor/autoload.php" colors="true">
       <testsuites>
           <testsuite name="Unit"><directory>tests/Unit</directory></testsuite>
           <testsuite name="Integration"><directory>tests/Integration</directory></testsuite>
           <testsuite name="Http"><directory>tests/Http</directory></testsuite>
       </testsuites>
   </phpunit>
   ```

   Crie também as pastas `tests/Unit`, `tests/Integration` e `tests/Http`.
4. **Ajuste os moldes ao projeto** (veja `references/regras/testes.md`, "Como corrigir"):
   - a constante `HOST` do `Http.php`: um host do bloco `dev` do `config/Env.php`;
   - o payload do `Http::as()`: o que o middleware de auth do projeto lê;
   - a lista `KEEP` do `Fixtures.php`;
   - uma linha no `Fakes.php` por integração com `fake()`.
5. **Fila e log no teste.** O `EQueue` já separa a fila com `-test` quando `APP_TESTING` está ligado. Confira onde o
   projeto chama `DiscordLogger::config(` (`grep -rn "DiscordLogger::config" --include=*.php . | grep -v vendor`).
   Em teste, o webhook tem que ficar vazio. Se não ficar, mostre ao usuário e proponha o ajuste.

**Conferir:**

```bash
composer dump-autoload && vendor/bin/pest
```

O boot não pode falhar: o banco `_test` é recriado e o servidor sobe na porta 18080. "No tests found" é normal num
projeto sem teste. Se houver suíte antiga, ela tem que continuar passando. Se não passar, mostre a falha ao usuário
antes de seguir.

## 5. Tratador global de exceção

Copie o asset para `config/`. Ele não pode ir para `www/`, que é pasta pública.

```bash
cp -n $SKILL/assets/exception-handler.php config/ExceptionHandler.php
```

O `require` entra no `www/index.php` **depois do autoload e antes do `new SysWeb\System()`**. O construtor já faz o
boot, e o que for lançado nele escaparia do tratador. Mostre o trecho e peça aprovação:

> `AskUserQuestion`: "Vou registrar o tratador global de exceção no `www/index.php`, antes do
> `new SysWeb\System()`. Posso gravar?" Opções: **Gravar** · **Não gravar**.

```php
include_once __DIR__ . '/../vendor/autoload.php';

require __DIR__ . '/../config/ExceptionHandler.php';

$start = new SysWeb\System();
$start->start();
```

Se o projeto já tem um `set_exception_handler`, não registre dois. Mostre os dois ao usuário e pergunte qual fica.

**Conferir:**

```bash
php -l config/ExceptionHandler.php
grep -n "ExceptionHandler.php\|new SysWeb" www/index.php
```

O `php -l` não acusa erro, e a linha do `ExceptionHandler.php` vem antes da linha do `new SysWeb\System`.

Lembre-se de que, **em dev**, erro do builder e de conexão é respondido pelo `Error.php` do core, com SQLSTATE,
antes do tratador (veja `references/regras/erro-e-resposta.md`, "Enquanto o core não corrigir"). Não use a
resposta de dev para conferir o formato do erro.

## 6. Regras velhas do projeto

```bash
ls .claude/rules/ 2>/dev/null
ls -d .claude/skills/create-* 2>/dev/null
```

Leia cada arquivo e monte uma tabela: arquivo · o que manda · regra da skill que ele contradiz · proposta. As
contradições mais comuns são com estas regras:

- `references/regras/validacao-no-middleware.md`;
- `references/regras/banco-no-model.md`;
- `references/regras/ruido-defensivo.md`;
- `references/regras/erro-e-resposta.md`.

Para cada arquivo, a proposta é uma de três:

- **apagar:** tudo nele está coberto pela skill;
- **reduzir a um ponteiro:** fica só o que é do projeto, mais a linha "Os padrões gerais estão na sw-standards-php.";
- **manter:** é só do projeto e não contradiz nada.

> `AskUserQuestion`, uma pergunta por arquivo (ou por grupo, se forem muitos): "`<arquivo>` contradiz `<regra>`
> em <ponto>. O que faço?" Opções: **Apagar** · **Reduzir a ponteiro** · **Manter**.

Só apague ou edite com a resposta. **Conferir:** `git status` mostra só os arquivos aprovados como alterados ou
apagados, e nenhum `.claude/rules/*` que sobrou contradiz uma regra da skill.

## 7. Linha no `AGENTS.md`

```bash
grep -qF 'Este projeto segue a sw-standards-php' AGENTS.md 2>/dev/null || echo 'falta'
```

Se faltar, grave a linha no fim do `AGENTS.md` (crie o arquivo se ele não existir):

```
Este projeto segue a sw-standards-php. Antes de escrever ou alterar PHP, carregue a skill.
```

Faça o mesmo no `CLAUDE.md` **só se ele já existir**. Não crie `CLAUDE.md`, porque ele faz o Claude Code ignorar o
`AGENTS.md`. Não copie regras para esses arquivos: a linha basta.

**Conferir:** o `grep` acima não mostra mais `falta`. Se `ls CLAUDE.md` falha, o arquivo continua sem existir.

## 8. Config do projeto

Crie `docs/sw-standards/config.md` e `docs/sw-standards/andamento.md` com os moldes de
`references/config-projeto.md`. Se o `config.md` já existe, só complete o que falta.

- Leia `PHP` no `composer.json` (`"php"`) ou no `Dockerfile`, e `Core` no `composer.lock` (passo 1).
- Pergunte o resto, de uma vez, por `AskUserQuestion`: o formato do erro, o e-mail e se o projeto é multiempresa
  (se for, a coluna e o mecanismo).
- No `andamento.md`, marque a linha `0 | preparação` como `feito`, com a data.

**Conferir:** os dois arquivos existem, nenhum campo do `config.md` ficou com `<...>`, e o `.gitignore` não os
ignora (`git check-ignore docs/sw-standards/config.md` volta vazio). O relatório de auditoria
(`docs/sw-standards/<data>/`) é que fica fora do git: confira se o `.gitignore` tem
`docs/sw-standards/*/relatorio.md` ou equivalente, e acrescente se faltar.

## Fechamento

1. Rode `vendor/bin/pest` uma última vez: o mesmo resultado do passo 4.
2. Mostre o resumo: um item por passo, com o que mudou e a conferência.
3. Ofereça o commit da etapa 0 com a `sw-git-commit` (se estiver instalada; senão, proponha a mensagem
   `chore: prepara o projeto para a sw-standards-php`). Depois do commit, preencha a coluna `Commit` da etapa 0 no
   `andamento.md`.
