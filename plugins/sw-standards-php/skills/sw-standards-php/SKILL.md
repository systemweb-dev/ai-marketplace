---
name: sw-standards-php
description: >
  Impõe os padrões da systemweb em projetos PHP do framework system-web-framework-core (API e website
  Twig): validação no middleware, controller fino, banco só no model, Services/<Domínio>, erro com
  status explícito, sem ruído defensivo, guard clause sem else, estilo da casa com fixer próprio e
  testes com banco próprio. Dois modos: guarda ao escrever e auditoria com correção por domínio, com
  teste antes de mexer. Use SEMPRE que for criar ou alterar PHP num projeto do framework, mesmo sem
  falar em padrão — "cria o endpoint", "faz o service", "adiciona um middleware", "cria a model",
  "faz o job", "nova rota", "escreve os testes do service" (a skill dá a estrutura de tests/ e a sw-auto-test escreve os testes), "create the endpoint", "add a middleware", "write the service" — ou
  padronizar um — "padroniza este projeto", "audita o padrão", "o que está fora do padrão?", "segue
  o padrão systemweb", "prepara o projeto para os padrões", "audit this project against our
  standards", "enforce the systemweb PHP standards". NÃO use para Vue, PHP fora do framework
  (Laravel, Symfony, WordPress), revisar um diff (sw-code-review), caçar código morto
  (sw-dead-code-scan) nem refatorar pelo padrão que o próprio projeto já tem (sw-refactor).
  Interação em português, toda decisão via AskUserQuestion.
---

# sw-standards-php — o padrão da systemweb, imposto

Os projetos PHP do framework saem do padrão quando feitos às pressas: validação no controller, SQL espalhado,
regra em Helper, cast defensivo em todo lugar, estilo misturado. Esta skill é a **fonte única** do padrão: o
projeto se adapta a ela, não o contrário. Por isso ela ignora a `sw-refactor` e o `patterns.md` dela, e as regras
velhas do projeto (`.claude/rules/*`, `.claude/skills/create-*`) saem na etapa 0, com aprovação.

O resultado que se quer: abrir qualquer projeto e saber onde está cada coisa, nenhuma violação passar sem
`arquivo:linha` e todos os projetos convergirem para a mesma arquitetura, o mesmo estilo e a mesma suíte.

## Regras de trabalho

- **Toda decisão via `AskUserQuestion`**, com opções e o padrão da skill como primeira. Nunca termine um turno
  com pergunta em texto: o usuário pode não ver.
- **Arquivo do projeto que a skill não criou** (`composer.json`, `config/Database.php`, `www/index.php`,
  `AGENTS.md`, regras velhas): mostre o trecho antes e depois e só grave com aprovação.
- **Nunca instale nada sem perguntar.** Não rode `composer install` nem `composer update`. Não dê push.
- **As respostas do projeto valem mais que o padrão das regras** (`docs/sw-standards/config.md`). Exceção aceita
  pelo dono não é violação.
- **A IA julga e o fixer formata.** Não formate na mão o que o fixer faz; não peça ao fixer o que é julgamento.
- `$SKILL` nas referências é a pasta deste `SKILL.md`.

## 1. É um projeto do framework?

Antes de qualquer coisa, na raiz do projeto:

```bash
grep -q '"system-web/system-web-framework-core"' composer.json && echo framework
grep -A3 '"name": "system-web/system-web-framework-core"' composer.lock | grep '"version"'
```

- **Sem o pacote no `composer.json`:** não é do framework. Diga isso e pare; a skill não se aplica.
- **A versão real** é a do `composer.lock`, não a faixa do `composer.json`. Abaixo da 1.10 não há
  `Request::share`, e a correção depende da etapa 0 subir o core.
- **API ou website:** o `application` em `config/Env.php`. Website traz as regras de Twig.
- **Versão do PHP:** a do projeto (`require.php` do `composer.json` ou a imagem do Docker). Nenhum recurso de
  versão mais nova entra no código.
- **Config:** leia `docs/sw-standards/config.md`. Se não existir, é a primeira vez (ver a seção 4).

Depois, escolha o modo pelo pedido:

| Pedido | Modo |
|---|---|
| criar ou alterar PHP ("cria o endpoint", "faz o service", "corrige esse middleware") | escrever (seção 2) |
| padronizar, auditar, "o que está fora do padrão?", preparar o projeto | auditar e corrigir (seção 3) |

## 2. Modo escrever: a guarda

O objetivo é que o código novo já nasça no padrão, sem gastar contexto com regras que não tocam o que está sendo
escrito.

1. **Carregue só as regras do que vai escrever,** pela tabela abaixo. Vai criar um middleware de validação: leia
   `validacao-no-middleware`, `dados-no-topo-e-sem-cadeia`, `guard-clause-sem-else` e `ruido-defensivo`, e pare
   aí. Mexe em mais de um tipo de arquivo: some as linhas.
2. **Sempre,** em todo PHP: [`estilo`](references/regras/estilo.md),
   [`nomes-e-enums`](references/regras/nomes-e-enums.md) e
   [`tipos-e-comentarios`](references/regras/tipos-e-comentarios.md).
3. **Escreva** seguindo as seções **Certo** e **Como corrigir** das regras lidas. Na dúvida entre duas formas, a
   do **Certo** vence.
4. **Ao terminar, rode o fixer só nos arquivos tocados** e confira que a segunda rodada não muda nada:

   ```bash
   vendor/bin/php-cs-fixer fix --using-cache=no <arquivos tocados>
   vendor/bin/php-cs-fixer fix --dry-run --diff --using-cache=no <arquivos tocados>
   ```

   Projeto sem `.php-cs-fixer.dist.php` na raiz ou sem `tools/php-cs-fixer/` ainda não passou pela etapa 0: não
   instale nada por conta própria. Escreva no estilo da regra `estilo` e pergunte se o usuário quer fazer a etapa 0
   (**Fazer a etapa 0 agora** · **Seguir sem o fixer**).
5. **Teste:** código novo de service, model, job ou endpoint pede teste na suíte padrão
   ([`testes`](references/regras/testes.md)). Ofereça a `sw-auto-test` (ver "Arsenal").

### Tipo de arquivo → regras

| Vai escrever | Regras a ler (`references/regras/`) |
|---|---|
| Controller da API | `controller-fino`, `erro-e-resposta`, `dados-no-topo-e-sem-cadeia`, `guard-clause-sem-else` |
| Middleware (validação ou existência) | `validacao-no-middleware`, `dados-no-topo-e-sem-cadeia`, `guard-clause-sem-else`, `ruido-defensivo` |
| Model | `banco-no-model`, `nomes-e-enums`, `ruido-defensivo`, `datas-dinheiro-pacotes` |
| Service (`Services/<Domínio>/`) | `services-e-integracoes`, `erro-e-resposta`, `transacao-e-fila`, `guard-clause-sem-else`, `ruido-defensivo`, `datas-dinheiro-pacotes` |
| Integração (`Integrations/<Fornecedor>/`) ou Helper | `services-e-integracoes`, `ruido-defensivo`, `seguranca-e-config` |
| Rota ou registro de middleware (`Rotas.php`, `config/Middleware.php`) | `rotas`, `seguranca-e-config` |
| Job ou scheduler | `jobs-e-scheduler`, `transacao-e-fila` |
| Enum | `nomes-e-enums`, `infra` (se for `ECache`), `jobs-e-scheduler` (se for `EQueue`) |
| Migration, cache, upload ou paginação | `infra` |
| Arquivo de `config/` ou `.env*` | `seguranca-e-config` |
| Controller do website ou `.twig` | `website-twig`, `controller-fino`, `dados-no-topo-e-sem-cadeia` |
| Teste (`tests/`) | `testes` |

Projeto multiempresa (veja o `config.md`): toda busca por id e toda rota com `{id}` também leem
`seguranca-e-config`.

## 3. Modo auditar e corrigir

A ordem existe para que nada mude sem prova: primeiro a base (etapa 0), depois o diagnóstico completo, e só então
as correções, uma etapa por vez, com teste verde antes e depois.

1. **Reconhecer o projeto** (seção 1) e ler o `config.md`.
2. **Etapa 0,** obrigatória antes de corrigir: siga [`references/etapa-0.md`](references/etapa-0.md) na ordem
   (core ≥ 1.10, fixer, banco `_test`, `tests/Support/`, tratador global de exceção, regras velhas, linha no
   `AGENTS.md`, config do projeto). Se o usuário recusar a etapa 0 ou algum passo dela, a skill **só audita**:
   faz o relatório e não corrige nada. Etapa 0 já marcada `feito` no `andamento.md`: confira rápido que os
   arquivos continuam lá e siga.
3. **Varredura com subagentes:** um por família, todos na mesma mensagem, com os prompts de
   [`references/subagentes.md`](references/subagentes.md). Copie para dentro de cada prompt as respostas e as
   exceções do `config.md`, porque o subagente que só recebe o caminho pode não ler e acusar a exceção. O estilo
   não tem subagente: sai do `vendor/bin/php-cs-fixer fix --dry-run --diff --using-cache=no`. Família que não se
   aplica fica de fora (Website em projeto API).
4. **Conferir e juntar:** descarte repetidos, abra 2 ou 3 achados de cada família no arquivo e, se um não bater,
   confira os outros daquela regra. Tire o que estiver nas exceções aceitas.
5. **Relatório** em `docs/sw-standards/<AAAA-MM-DD>/relatorio.md`, **fora do git** (confira o `.gitignore`).
   Agrupado por regra, com a contagem, cada achado como `arquivo:linha · regra · trecho · correção`, e a ordem de
   ataque: vazamento de erro e query fora do model antes de estilo. Mostre o resumo no chat e pergunte por onde
   começar (multiSelect por domínio, na ordem proposta).
6. **Etapas de correção.** A etapa 1 é sempre só o formatador no projeto inteiro, num commit separado, porque não
   muda comportamento. Da 2 em diante, **uma etapa por domínio** (`Billing`, `Customer`...), com todas as regras
   juntas: um teste de endpoint prova o domínio inteiro de uma vez. Cada etapa segue o ciclo:
   1. **teste antes:** rode os testes que cobrem o domínio. Faltam: ofereça a `sw-auto-test` para escrever o
      teste de caracterização na suíte padrão. Recusou: pergunte (**Seguir sem prova** · **Pular o domínio**), e
      "seguir sem prova" fica anotado no `andamento.md`;
   2. **verde antes:** teste vermelho antes de mexer para a etapa; mostre a falha e pergunte;
   3. **corrige** pelas seções **Como corrigir** das regras;
   4. **verde depois:** falhou, desfaça só os arquivos da etapa e pergunte (**Tentar de outro jeito** · **Pular**
      · **Parar**);
   5. **fixer** nos arquivos tocados;
   6. **aprovação:** mostre o diff resumido e pergunte (**Aprovar** · **Ajustar** · **Desfazer**);
   7. **`sw-code-review` de contexto vazio** no diff da etapa;
   8. **`sw-git-commit`,** um commit por etapa;
   9. **andamento:** marque a etapa como `feito` no `docs/sw-standards/andamento.md`, com a data e o hash curto.
7. **Exceção durante a correção:** se o usuário disser que um ponto deve ficar como está, pergunte se vira
   exceção aceita e, com o "sim", grave no `config.md` com motivo, quem aceitou e data.

Rodadas seguintes partem do `andamento.md`: mostre o que já está `feito` e pergunte se audita de novo o projeto
inteiro ou segue do próximo domínio `pendente`.

## 4. Perguntas por projeto e onde gravar

Na primeira vez (passo 8 da etapa 0, ou antes da varredura se o usuário só quer auditar), pergunte de uma vez,
por `AskUserQuestion`, e grave em `docs/sw-standards/config.md` com o molde de
[`references/config-projeto.md`](references/config-projeto.md):

- **formato do erro:** código específico + frase (padrão) ou outro;
- **e-mail:** SendGrid (padrão) ou outro pacote;
- **multiempresa:** não, ou sim, com a coluna que separa os dados e o mecanismo que protege a rota.

O que a skill grava no projeto:

| Arquivo | Vai para o git | Conteúdo |
|---|---|---|
| `AGENTS.md` (uma linha) | sim | aponta para a skill; no `CLAUDE.md` só se ele já existir |
| `docs/sw-standards/config.md` | sim | respostas e exceções aceitas |
| `docs/sw-standards/andamento.md` | sim | etapas de correção e seu estado |
| `docs/sw-standards/<data>/relatorio.md` | não | o relatório de cada auditoria |
| `.php-cs-fixer.dist.php` e `tools/php-cs-fixer/` | sim | config e fixer próprio, copiados de `assets/php-cs-fixer/` |
| `tests/Pest.php` e `tests/Support/*` | sim | suíte padrão, copiada de `assets/tests-support/` |
| `config/ExceptionHandler.php` | sim | tratador global, copiado de `assets/exception-handler.php` |

## 5. Arsenal

Outras skills entram sempre como oferta por `AskUserQuestion`, nunca automáticas. Se a skill não estiver
instalada, diga e siga sem ela, fazendo o passo à mão quando der.

| Momento | Skill | Pedido |
|---|---|---|
| Etapa sem teste, ou código novo sem teste | `sw-auto-test` | "Escreva um teste de caracterização para `<arquivo>` na suíte padrão (`tests/`, Pest, `Support/`): fixe o comportamento atual, inclusive o estranho; não corrija bug e não altere o código." |
| Fim de cada etapa | `sw-code-review` | revisar o diff da etapa, de contexto vazio |
| Depois da aprovação da etapa | `sw-git-commit` | um commit por etapa |
| Varredura achou arquivo ou função sem uso | `sw-dead-code-scan` | limpar antes de corrigir o domínio |

## 6. As 19 regras

Cada arquivo tem **Regra**, **Por quê**, **Certo**, **Errado**, **Como reconhecer** e **Como corrigir**, e às
vezes **Enquanto o core não corrigir**, com o contorno aceito e a versão em que ele deixa de valer.

| Regra | Em uma linha |
|---|---|
| [`validacao-no-middleware`](references/regras/validacao-no-middleware.md) | entrada validada no `Validate{Recurso}{Ação}Middleware` com `Validator::check`, repassada por `Request::share` |
| [`controller-fino`](references/regras/controller-fino.md) | só ações públicas: lê `shared()`, chama o service, responde; sem query, `try/catch` nem regra |
| [`banco-no-model`](references/regras/banco-no-model.md) | query só no model, em métodos `findBy`/`listBy`; escrita pelo ORM; sem N+1 |
| [`services-e-integracoes`](references/regras/services-e-integracoes.md) | regra em `Services/<Domínio>/` estático; fornecedor em `Integrations/<Fornecedor>/` com `fake()`; Helper puro |
| [`transacao-e-fila`](references/regras/transacao-e-fila.md) | transação só no service; fila, e-mail e webhook depois do commit, com payload de ids |
| [`erro-e-resposta`](references/regras/erro-e-resposta.md) | `ResponseApi::error(código, frase, status)` com status explícito; array de erro do service; tratador global |
| [`dados-no-topo-e-sem-cadeia`](references/regras/dados-no-topo-e-sem-cadeia.md) | entrada lida em variáveis no topo; nada de query ou cadeia no cabeçalho de `if`/`foreach` |
| [`ruido-defensivo`](references/regras/ruido-defensivo.md) | converte uma vez na borda; sem cast, `??` e `empty()` redundantes |
| [`guard-clause-sem-else`](references/regras/guard-clause-sem-else.md) | erro no topo e sai na hora; evite `else` e `elseif` |
| [`estilo`](references/regras/estilo.md) | estilo da casa (`if(`, `){`) aplicado pelo `php-cs-fixer` e pelo fixer próprio |
| [`nomes-e-enums`](references/regras/nomes-e-enums.md) | código em inglês, model segue o banco; enums `EModel{Tabela}{Coluna}` e `E{Nome}` |
| [`tipos-e-comentarios`](references/regras/tipos-e-comentarios.md) | todo parâmetro e retorno tipado; comentário só para o porquê |
| [`datas-dinheiro-pacotes`](references/regras/datas-dinheiro-pacotes.md) | `CarbonImmutable`, centavos em inteiro, pacotes preferidos, SendGrid |
| [`seguranca-e-config`](references/regras/seguranca-e-config.md) | `sw_env` só em `config/`; nenhum segredo no código; escopo por empresa quando multiempresa |
| [`rotas`](references/regras/rotas.md) | URL versionada; escrita e `{id}` sempre com middleware; apelidos padronizados |
| [`jobs-e-scheduler`](references/regras/jobs-e-scheduler.md) | job fino com `ack`/`nack` em todo caminho; scheduler só publica; filas no `EQueue` |
| [`infra`](references/regras/infra.md) | migration Flyway `V{n}__`, cache com `ECache` e TTL, upload pelo `Storage`, paginação |
| [`website-twig`](references/regras/website-twig.md) | controller fino com `sw_seo()`; template só exibe; repetição vira macro |
| [`testes`](references/regras/testes.md) | Pest em `Unit/`, `Integration/` e `Http/`, banco `_test`, `Support/` padrão, sem Mockery |
