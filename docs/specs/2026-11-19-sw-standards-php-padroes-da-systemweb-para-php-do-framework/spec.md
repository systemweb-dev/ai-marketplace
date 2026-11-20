---
titulo: sw-standards-php padroes da systemweb para PHP do framework
slug: 2026-11-19-sw-standards-php-padroes-da-systemweb-para-php-do-framework
criado: 2026-11-19
estado: concluido
---

# sw-standards-php — padrões da systemweb para PHP do framework

> Skill nova do marketplace. As 31 regras decididas ponto a ponto, com exemplos, estão em
> [`referencias/decisoes-em-andamento.md`](referencias/decisoes-em-andamento.md): é o catálogo que vira os
> arquivos de `references/regras/`. Este spec define a skill que carrega e aplica esse catálogo.

## Objetivo & outcome

Projetos PHP feitos às pressas sobre o framework `system-web/system-web-framework-core` saem do padrão:

- validação no controller;
- SQL espalhado;
- regra de negócio em Helper;
- cast defensivo em todo lugar;
- estilo misturado.

Cada projeto também carrega uma regra escrita própria que contradiz a dos outros. [usuário]

A análise de 5 APIs e 2 websites mostrou, por exemplo:

- ~250 queries fora de model;
- ~550 `ResponseApi::error` com HTTP 200;
- ~3600 `(int)`;
- só 1 dos 5 projetos com o estilo do dono.

[visto: referencias/decisoes-em-andamento.md:12]

**Outcome** — os três critérios de sucesso, juntos [usuário]:

1. Abrir qualquer projeto e saber onde está cada coisa: validação no middleware, query no model, regra em
   `Services/<Domínio>`.
2. Nada de lixo passa: a skill acusa toda violação das regras, com arquivo e linha.
3. Os projetos convergem para a mesma arquitetura, o mesmo estilo e a mesma suíte de testes.

## Não-objetivos

- **Vue:** fica para a `sw-standards-vue`, no mesmo formato. [usuário]
- **Rodar a skill nos 7 projetos:** cada projeto é uma rodada própria da skill depois de publicada, com a
  etapa 0 e as etapas por domínio. Este trabalho constrói a skill.
- **Mudar o core:** os pedidos ao framework ficam numa lista interna, fora deste repositório. [usuário]
- **CI, segurança extra, auditoria de dependências e índices de banco:** recusados pelo dono. [usuário]
- **Script de checagem:** a detecção é só por IA, com subagentes. A única ferramenta é o formatador. [usuário]
- **Seguir a `sw-refactor`:** a skill ignora a `sw-refactor` e o `patterns.md` dela; o projeto se adapta a
  esta. [usuário]

## Design

### 1. Estrutura da skill

Abordagem A, com um arquivo por regra [usuário]:

```
plugins/sw-standards-php/skills/sw-standards-php/
  SKILL.md                      gatilhos, os dois modos, etapa 0, perguntas por projeto, arsenal
  references/regras/            uma regra por arquivo (lista abaixo)
  references/etapa-0.md         o que preparar antes de corrigir
  references/config-projeto.md  molde do docs/sw-standards/config.md e andamento.md
  references/subagentes.md      o prompt de cada família de varredura
  assets/php-cs-fixer/          .php-cs-fixer.dist.php e o fixer próprio da systemweb
  assets/tests-support/         Pest.php, Boot, TestDatabase, TestServer, Fakes, Fixtures, Http
  assets/exception-handler.php  tratador global do projeto
```

**Formato de cada arquivo de regra.** Cada arquivo tem seis seções: **Regra**, **Por quê**, **Certo**,
**Errado**, **Como reconhecer** e **Como corrigir**. Quando o core impõe um contorno, há também a nota
**Enquanto o core não corrigir**, com a versão a partir da qual ela deixa de valer.

Os exemplos são genéricos, como `Invoice`, `Company` e `Billing`, e já vêm no estilo da casa. Nenhum nome de
projeto real aparece.

| Arquivo | Decisões |
|---|---|
| `validacao-no-middleware.md` | 1, 2 (`Request::share` → `shared()`, `Validator::check`) |
| `erro-e-resposta.md` | 3, 7, 8, 19 (código + frase + status explícito, array de erro do service, `Api::returnAttributes`, tratador global). A assinatura é `error(string $message, array\|object\|string $data, int $status = 200)`: a frase vai no `$data`, e o padrão 200 explica os ~550 casos [visto: /var/www/system-web-framework-core/system/Api/ResponseApi.php:33] |
| `banco-no-model.md` | 4, 10, 18 (filtro só no model, escrita pelo ORM, `findBy`/`listBy`, sem trait, sem N+1) |
| `services-e-integracoes.md` | 5, 11 (`Services/<Domínio>`, `Integrations/<Fornecedor>` com `fake()`, Helpers puros, estático, arrays) |
| `controller-fino.md` | 6 (Thin Controller) |
| `transacao-e-fila.md` | 9, 23 (transação no service, fila depois do commit) |
| `dados-no-topo-e-sem-cadeia.md` | 12, 13 |
| `ruido-defensivo.md` | 18b (as 8 regras) |
| `guard-clause-sem-else.md` | 18c |
| `estilo.md` | 14 (o que o fixer faz e o que a IA confere) |
| `nomes-e-enums.md` | 15 (inglês, banco em português manda na model, `EModel{Tabela}{Coluna}`, `E{Nome}`) |
| `tipos-e-comentarios.md` | 16, 17 |
| `datas-dinheiro-pacotes.md` | 18 (Carbon, centavos, lista de pacotes, SendGrid) |
| `seguranca-e-config.md` | 20, 21 (`sw_env` só em `config/`, escopo por empresa perguntado) |
| `rotas.md` | 22 |
| `jobs-e-scheduler.md` | 23 |
| `infra.md` | 24 (Flyway, `ECache`, `Storage`, paginação) |
| `website-twig.md` | 25 |
| `testes.md` | 26 (estrutura de `tests/`, o que cada camada testa) |

### 2. Modo escrever: a guarda

- **Disparo:** a skill dispara pela descrição quando o pedido é criar ou alterar PHP de um projeto do
  framework.
- **Linha no `AGENTS.md`:** na primeira rodada, a skill grava no `AGENTS.md` do projeto:

  ```
  Este projeto segue a sw-standards-php. Antes de escrever ou alterar PHP, carregue a skill.
  ```

  A linha vai no `CLAUDE.md` só se o projeto já tiver um, porque o esqueleto proíbe criar esse arquivo
  [visto: /var/www/systemweb-framework/AGENTS.md:156]. [usuário]
- **Leitura enxuta:** a skill carrega só as regras do que está sendo escrito. Vai criar um middleware, lê a
  regra de middleware.
- **Ao terminar:** roda o fixer nos arquivos tocados.

### 3. Modo auditar e corrigir

1. **Reconhecer o projeto.**
   - É do framework se o `composer.json` tem `system-web/system-web-framework-core`, e a versão real vem do
     `composer.lock`.
   - API ou website: pelo `application` em `config/Env.php`.
   - Versão do PHP: a do projeto.
   - Lê `docs/sw-standards/config.md` ou, na primeira vez, pergunta e grava as respostas. São elas: o formato
     do erro, o e-mail e se o projeto é multiempresa (com a coluna e o mecanismo).
2. **Etapa 0, obrigatória antes de corrigir** (detalhe em `references/etapa-0.md`).
   - Core ≥ 1.10, porque `Request::share` só existe a partir dela
     [visto: /var/www/system-web-framework-core/system/Request/Request.php:199].
   - `friendsofphp/php-cs-fixer` instalado como dependência de dev.
   - Banco `_test` no `config/Database.php`.
   - `tests/Support/` padrão.
   - Fixer e config.
   - Tratador global de exceção.
   - Remoção das regras velhas (`.claude/rules/*`, `.claude/skills/create-*`), com aprovação.

   Sem a etapa 0, a skill só audita e não corrige. [usuário]
3. **Varredura.** Um subagente por família de regra:
   - arquitetura;
   - código;
   - erro e segurança;
   - rotas, jobs e scheduler;
   - testes;
   - website.

   Cada subagente devolve as violações com arquivo, linha e regra. As exceções aceitas em `config.md` não são
   acusadas.
4. **Relatório.** Fica em `docs/sw-standards/<data>/relatorio.md`, fora do git. Agrupa por regra, com
   contagem e ordem de ataque: vazamento de erro e query fora do model vêm antes de estilo.
5. **Correção.**
   - A primeira etapa é só o formatador, que não muda comportamento.
   - Depois vem **uma etapa por domínio**, com todas as regras juntas. [usuário]
   - Cada etapa segue o ciclo: teste antes (`sw-auto-test`, se faltar) → verde → corrige → verde → fixer →
     aprovação → `sw-code-review` de contexto vazio → `sw-git-commit`.
   - O andamento fica em `docs/sw-standards/andamento.md`.

### 4. Arquivos que a skill grava no projeto

| Arquivo | Vai para o git | Conteúdo |
|---|---|---|
| `AGENTS.md` (uma linha) | sim | aponta para a skill |
| `docs/sw-standards/config.md` | sim | respostas por projeto e exceções aceitas (motivo e quem aceitou) |
| `docs/sw-standards/andamento.md` | sim | domínios já corrigidos |
| `docs/sw-standards/<data>/relatorio.md` | não | o relatório de cada auditoria |
| `.php-cs-fixer.dist.php` e `tools/php-cs-fixer/` | sim | config e fixer próprio, copiados de `assets/` |
| `tests/Pest.php` e `tests/Support/*` | sim | a infraestrutura de teste padrão |

### 5. Fixer próprio da systemweb

O `php-cs-fixer` não produz o estilo da casa
[doc: https://cs.symfony.com/doc/rules/index.html · v3.95.32 · 2026-11-19]:

- `single_space_around_construct` só garante um espaço depois de `if`;
- `braces_position` não tem opção para `){`;
- não há fixer de linha em branco depois de bloco.

O fixer próprio, escrito sobre a API de fixers customizados do `php-cs-fixer`, cuida de:

- `if(`, `foreach(`, `while(`, `switch(` e `catch(` sem espaço;
- `){` colado;
- `}else{` e `}elseif(`;
- a linha em branco depois de bloco.

A config liga os fixers nativos para o resto:

- PSR-12, desligando o que brigaria com o estilo da casa;
- `blank_line_before_statement`;
- chave de classe e de método na linha de baixo;
- LF e 4 espaços;
- `if` sem chaves proibido.

O fixer vive em `assets/` e a etapa 0 o copia para o projeto. [usuário: distribuição deixada de lado; esta é a
forma mais simples]

## Exploração & decisões

- **Problema:** projetos às pressas saem do padrão, e cada um tem uma regra escrita diferente.
- **Trabalho da skill:** guarda e auditoria com peso igual. [usuário]
- **Como age:** a IA julga e o formatador formata. [usuário]
- **Segurança:** teste antes de mexer, em etapas. [usuário]
- **Alcance:** uma skill por stack, e a de PHP cobre também o website Twig. [usuário]
- **Molde:** de arquitetura, os dois projetos com `Request::share`, `Services/<Domínio>` e banco de teste; de
  formatação, o único projeto que já usa `if(`.

## Decisões

| Contexto | Decisão | Alternativas descartadas | Consequências |
|---|---|---|---|
| Onde moram as regras | Um arquivo por regra em `references/` | Tudo no `SKILL.md`; copiar as regras para o projeto | A IA lê só o necessário; nada envelhece em 7 cópias |
| Como garantir o padrão | Só IA, mais o formatador | Script de checagem | Julgamento onde precisa; estilo idêntico |
| Estilo que o `php-cs-fixer` não faz | Fixer próprio | IA formatar; aceitar PSR-12 | Código PHP a manter, com teste próprio |
| Erro inesperado | Tratador global do projeto | `try/catch` em todo service | Some quando o core ganhar o tratador |
| Projeto sem base | Etapa 0 obrigatória | Regra alternativa para core antigo | Uma regra só para todos; o upgrade vem antes |
| Regras velhas no projeto | Removidas na etapa 0 | Manter e "a skill vence" | Sem instrução oposta no modo escrever |
| Ordem da correção | Por domínio, regras juntas | Por regra; por gravidade | Um teste de endpoint prova o domínio inteiro |
| Respostas por projeto | `docs/sw-standards/` versionado | Arquivo na raiz; dentro do `AGENTS.md` | Quem clona sabe as decisões |

## Restrições verificáveis

1. **Detecção (`sw-skill-test`).** Um projeto fixture com uma violação plantada em cada um dos **18 arquivos de
   regra**. O `estilo.md` fica de fora, porque estilo é do fixer e entra na restrição 2. O fixture vem com o
   `docs/sw-standards/config.md` pronto e um `composer.lock` com core ≥ 1.10, porque o teste pula as etapas
   interativas. Limite conhecido: no teste, a skill roda num subagente e faz a varredura numa passada só, sem
   abrir um subagente por família. São 5 armadilhas legítimas:
   - SQL cru com motivo no model;
   - `??` em campo opcional;
   - `@unlink` com comentário;
   - `=== null` onde o zero vale;
   - `find`/`save` no service.

   A auditoria acha **pelo menos 16 das 18** e acusa **no máximo 1** armadilha.
2. **Fixer.** Os pares antes e depois de `assets/php-cs-fixer/fixtures/` passam, rodando no marketplace com o
   `php` e o `composer` da máquina, por uma meta do `make`. A pasta `fixtures/` não é copiada para o projeto. Uma segunda rodada do fixer
   não muda nada (idempotente). Texto dentro de string e de comentário fica intacto.
3. **Exemplos no estilo.** Todo bloco `php` das seções **Certo** e **Como corrigir** dos arquivos de regra,
   passado pelo fixer, sai igual. Trecho sem `<?php` é embrulhado num arquivo com `<?php` e numa classe para o
   fixer rodar. A seção **Errado** fica de fora de propósito, porque mostra o estilo proibido.
4. **Formato das regras.** Todo arquivo de `references/regras/` tem as seis seções.
5. **Sem vazamento.** Nenhum nome de projeto real nem caminho do home na skill e no dossiê: `make check` mais
   um grep manual com a lista local de nomes, antes do commit.

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| Um fixer customizado do `php-cs-fixer` consegue tirar o espaço de `if(` e colar `){` sem que os fixers nativos o desfaçam | O estilo volta a depender da IA, e a regra 14 muda | Spike: fixer mínimo, rodado com a config, em 10 arquivos reais |
| `set_exception_handler` registrado no projeto pega a exceção não capturada no fluxo do core | O tratador global não funciona, e o erro volta a vazar | Spike: lançar uma exceção num service e provocar uma falha de SQL. O core captura `Exception` em `DB.php` [visto: /var/www/system-web-framework-core/system/Database/DB.php:38], então o erro de banco talvez nunca chegue ao tratador |
| Subagentes acham as violações com boa precisão só lendo | O critério de sucesso 2 falha | Restrição 1, com `sw-skill-test` |
| O projeto na v1.9.4 sobe para ≥ 1.10 sem quebrar | A etapa 0 vira projeto à parte | Na rodada desse projeto, com os testes existentes |

## Appetite e MVP

Grande, um plano: cerca de 19 regras com exemplos, o fixer com teste, os moldes de `tests/Support` e a etapa 0.

MVP: o `SKILL.md` com os dois modos, as 19 regras, o fixer e os assets da etapa 0. Rodar nos projetos fica para
depois da publicação.

## Rollout

Skill nova, sem migração. Volta é despublicar. Nos projetos, o rollout é a própria etapa 0, com aprovação a cada
passo.

## Decisões da execução

Detalhe em "Ajustes durante a execução", no `plan.md`.

- **Spikes confirmados.**
  - Os três fixers próprios produzem o estilo da casa. Os nativos do @PSR12 não os desfazem, e a segunda rodada
    não muda nada (php-cs-fixer 3.95.32).
  - O tratador global pega a exceção e o `DB::query`. Em dev, o builder e a conexão respondem pelo `Error.php` do
    core com SQLSTATE; isso virou nota na regra e pedido interno ao framework.
  - O `DiscordLogger` precisa de `setTitle()` e de um `set_error_handler` em volta do envio, senão vaza a URL do
    webhook.
- **Servidor de teste:** sobe pelo `Support/app-router.php`, que instala os fakes dentro do processo do
  servidor. A etapa 0 exige o `autoload-dev` de `Tests\`.
- **Exceções escritas em `tests/Support/`:** o `TestDatabase` usa `sw_env` e PDO, e o `Fixtures::truncate()` usa
  `DB::query`. As regras mandam não acusar.
- **Erro do service:** o teste é `is_array($x) && isset($x['error'])`, porque o `Model` do core não é array.
- **Um `.env` só:** o core só lê o `.env`, e o `config/*.php` escolhe pelo `getenv('APP_TESTING')`.
- **Tratador em `config/ExceptionHandler.php`,** com o `require` no `www/index.php` antes do `new SysWeb\System()`.
- **Convenções dos exemplos:**
  - tabela no singular e FK `id_{tabela}`;
  - `sw_config('a')['b']`, porque o core não lê chave com ponto;
  - `namespace Middleware`;
  - a empresa vem de `shared('company')`, porque o core não tem `Auth::companyId()`.
- **Medição:** a skill achou 18 de 18 violações e acusou 0 de 5 armadilhas. O baseline achou 16 e acusou 2. O
  dono recusou a seção "Achados fora das regras" e aceitou o gatilho de testes na descrição.

## Revisões do spec

- **2026-11-19** — revisão do design, que mudou estes pontos:
  - fixer próprio, porque o `php-cs-fixer` não faz o estilo;
  - tratador global de exceção;
  - fila e log nos testes desligados por config;
  - etapa 0 obrigatória, com o core ≥ 1.10 e o `TestServer`;
  - regras velhas removidas e a linha só no `AGENTS.md`;
  - `Storage` corrigido;
  - nome de projeto real retirado do dossiê.
- **2026-11-19** — revisão do spec:
  - os números da análise entraram no catálogo, como diagnóstico por letra;
  - o catálogo foi atualizado com a revisão do design (itens 9, 14, 18c, 19, 26 e 27) e ganhou uma regra de
    precedência;
  - a restrição 1 passou a 18 arquivos de regra (16 de 18), com o limite do `sw-skill-test`;
  - a restrição 3 vale só para Certo e Como corrigir;
  - a etapa 0 instala o `php-cs-fixer`;
  - o spike do tratador inclui falha de SQL;
  - a assinatura do `ResponseApi::error` está citada.
