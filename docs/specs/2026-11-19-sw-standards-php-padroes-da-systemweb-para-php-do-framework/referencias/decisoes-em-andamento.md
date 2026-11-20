# Decisões em andamento — sw-standards-php

Registro da discussão ponto a ponto, antes do spec. Os projetos analisados aparecem por letra (repositório
público): **P1** a **P7** são APIs e websites que usam o framework; **core** é o pacote do framework e
**esqueleto** é o projeto base.

## Precedência

A seção **Revisão do design**, no fim deste arquivo, e o `spec.md` vencem os itens numerados quando
discordarem. Os itens já foram corrigidos com a revisão; esta regra vale para o que escapar.

## Diagnóstico (análise de 2026-11-19, projetos por letra)

Foram analisados 5 APIs (P1 a P5) e 2 websites (P6 e P7), sobre o mesmo core, só lendo:

- **Query fora de model:** ~250 linhas em controllers e middlewares (P1, P3, P4), mais SQL cru em services (P2:
  382 linhas; P5: 121).
- **`ResponseApi::error` sem status**, que sai com HTTP 200: ~550 casos (P1 ~230, P4 ~160 e os demais).
- **`(int)`:** ~3600 no total (1626 fora dos testes); `(int) $this->company->id` aparece 154 vezes.
- **Estilo `if(cond){`:** só 1 dos 5 projetos (P4, 83% de linha em branco antes de `if`); nos outros, mais de 95%
  é `if (cond) {`.
- **`$e->getMessage()` devolvido ao cliente:** ~60 lugares (P1 43, P4 14).
- **Repasse com `Request::share`:** só P2 e P5; P1, P3 e P4 relêem a request no controller.
- **Banco de teste próprio:** só P2 e P5; um projeto grava no banco de dev durante os testes.

## Exploração

- **Trabalho:** guarda enquanto o código é escrito e auditoria com correção quando roda num projeto, com peso igual.
- **Sucesso:** abrir qualquer projeto e saber onde está cada coisa; nada de lixo passa; os projetos convergem.
- **Como age:** só IA (subagentes) para regras e arquitetura; `php-cs-fixer` com a config da systemweb para o
  estilo puro, com a IA conferindo.
- **Segurança:** só move código coberto por teste; sem teste, escreve antes (sw-auto-test), em etapas e com
  aprovação.
- **Alcance:** `sw-standards-php` cobre a API e o website Twig sobre o framework; Vue vira `sw-standards-vue`.
- **Fonte única:** ignora a sw-refactor e o `patterns.md` dela; o projeto se adapta a esta skill.
- **Abordagem:** A, um arquivo por regra em `references/regras/`, com dois modos (escrever e auditar) e uma
  linha no `AGENTS.md` do projeto apontando para a skill.

## Parte 1: arquitetura (aprovada)

1. **Validação no middleware.** O middleware valida, normaliza e repassa com `Request::share('chave', $dados)`,
   inclusive o registro já buscado. O controller lê só `$this->shared('chave')` e nunca lê a request nem busca
   de novo.
2. **Validador.** Usar `SysWeb\Validator\Validator::check`. Os casos em que o core falha (`min`/`max` numérico,
   zero, campo opcional) usam `if` manual com um comentário que aponta o pedido ao framework.
3. **Erro.** O padrão da casa é código específico com frase: `ResponseApi::error('url_is_required', 'URL is
   required', 422)`. O **status HTTP é sempre explícito** (422, 401, 403, 404, 409, 500). Quando um projeto
   usa outro formato (por exemplo, `errors[{field,code,detail}]`), a skill pergunta e grava a escolha no projeto.
4. **Banco.** Fora do model ninguém monta query nem `Model::where(...)`. Filtro é método com nome no model.
   Dentro do model, builder primeiro; `DB::query` só quando o builder não dá conta, com placeholder nomeado e
   comentário do motivo. Escrita pelo ORM: `find`, alterar e `save()`; `new` e `insert()`; `remove()`.
   O service pode `find`, `new`, `save`, `insert` e `remove`; o controller não faz nenhum dos dois.
5. **Organização.** Regra de negócio em `app/LogicApp/Services/<Domínio>/<Nome>Service.php`; integração
   externa em `app/LogicApp/Integrations/<Fornecedor>/`; Helpers só com função pura, sem regra e sem banco.
   Nada solto na raiz de Services.
6. **Controller fino (Thin Controller).** Só métodos públicos de ação, um por rota: lê `shared()`, chama o
   service e responde. Sem `try/catch`, query, método privado ou regra de negócio. Padrões citados: Thin
   Controller, Service Layer, Middleware/Pipeline e Active Record.
7. **Erro do service.** O service devolve `['error' => código, 'message' => frase, 'status' => http]`, e o
   controller responde com `ResponseApi::error`. No sucesso, devolve o dado em si.
8. **Saída da API.** Sempre `Api::returnAttributes()` com a lista explícita de campos; nunca o model ou o
   `toArray()` direto.
9. **Transação.** Gravou em mais de uma tabela: o service abre a transação, faz rollback em qualquer falha e
   devolve o array de erro. O `try/catch` do service existe só para transação e integração externa. Fila, e-mail e webhook só depois do commit.
   Controller e model nunca abrem transação.
10. **Models.** `protected static $_table`. Métodos estáticos com nome que diz o que devolve: `findBy{Campo}()`
    (um ou null), `listBy{Filtro}()` (lista), `countBy…`, `existsBy…`, e ação em lote com verbo
    (`markAsRead`). Sempre com tipo de retorno. **Sem trait para filtro repetido:** cada model tem os
    próprios métodos, e a ligação entre tabelas usa os relacionamentos do framework.
11. **Estático e arrays.** Service estático, sem estado. Integração externa com interface, `instance()` e
    `fake()`, para o teste não chamar o fornecedor real. Dados entre camadas em array associativo, sem DTO.

## Parte 2: código (aprovada)

12. **Dados no topo.** Tudo que chega de fora (`shared()`, parâmetro de rota, query string, `Auth::companyId()`)
    é lido em variáveis no começo do método, antes do primeiro `if`.
13. **Sem cadeia no cabeçalho.** Nenhum `foreach`, `if`, `while`, `switch` ou `return` tem query ou cadeia de
    chamadas no cabeçalho; o resultado vai antes para uma variável com nome. Chamada simples como argumento
    continua permitida.
14. **Estilo** (config do `php-cs-fixer` da systemweb):
    - `if(`, `foreach(`, `while(`, `switch(` e `catch(` sem espaço antes do parêntese, e `){` colado;
    - `}else{` e `}elseif(cond){` juntos, só para o raro caso que sobrar, porque o 18c manda evitar `else`;
    - linha em branco antes e depois de todo bloco e antes do `return` final;
    - chave de classe e de método na linha de baixo;
    - 4 espaços e LF;
    - `if` sem chaves proibido.
15. **Nomes.** Código em inglês. **Quando o banco está em português, a model e as colunas seguem o banco**
    (`Usuario`, `$usuario->nome_completo`); métodos, variáveis e códigos de resposta continuam em inglês.
    - Classe em PascalCase e singular; `{Recurso}Controller`; `Validate{Recurso}{Ação}Middleware`;
      `{Nome}Service` em `Services/<Domínio>/`.
    - Método público em camelCase; privado em `_camelCase`, abaixo dos públicos; variável sem abreviação.
    - Enum de coluna do banco é `EModel{Tabela}{Coluna}`, e enum comum é `E{Nome}`, em `app/LogicApp/Enums/`,
      com valor em string e casos em MAIÚSCULO iguais ao valor do banco.
    - Código de resposta em snake_case e frase do erro em inglês; tabela e coluna em snake_case.
16. **Tipos e PHP.** Tipo sempre em parâmetro e retorno, sem `strict_types`. A versão do PHP é a do projeto
    (`composer.json` ou Docker); o relatório sugere evoluir quando o projeto está abaixo do que o core suporta.
17. **Comentários.** Só o porquê, em português, com espaço depois de `//`; nunca narrar a linha. Na auditoria,
    a skill chama a `sw-dead-code-scan`.
18. **N+1, datas e dinheiro.** Nenhuma query nem relação dentro de laço: traz tudo antes, por método do model.
    Datas com Carbon (`CarbonImmutable`). Dinheiro em centavos inteiros, ou `brick/money`, nunca float.
    - **Pacotes preferidos:**
      - HTTP: `php-curl-class`, nunca Guzzle direto;
      - `nesbot/carbon` e `brick/money`;
      - fila, cache e JWT pelo core (`Queue`, `Cache`, `Jwt`), sem o pacote direto;
      - `aws/aws-sdk-php`, `dompdf/dompdf`, `stripe/stripe-php` e Pest.
    - **Regra para pacote novo:** ver se o core resolve; se não, usar o da lista; se não houver na lista, um
      pacote consolidado com o motivo registrado.
    - **E-mail:** SendGrid por padrão; quando o projeto usa outro, a skill pergunta e grava.

18b. **Ruído defensivo.**
    1. Converter só uma vez, na borda: o middleware entrega no `share` já tipado, assim como o payload externo
       e o DECIMAL/SUM. Depois disso, nenhum cast.
    2. Sem `(int)` em id ou coluna INT do model, e sem cast antes de parâmetro tipado.
    3. `??` só para o que é opcional de verdade, nunca em chave já validada.
    4. `json_decode` sempre com `JSON_THROW_ON_ERROR`, sem indexar o resultado direto.
    5. Para conferir existência ou vazio, `if($x)` ou `if(!$x)` direto, sem `empty()`, `count() > 0` ou
       `=== null`. O `=== null` só quando `0` ou `''` são valores válidos.
    6. Ternário aninhado proibido: `match` ou guard clause.
    7. No máximo duas funções aninhadas por linha; acima disso, uma variável com nome.
    8. Sem `@`, exceto em limpeza com comentário; sem `print_r`, `var_dump` ou `dd`.
18c. **Guard clause (early return) e sem `else`.** Cada erro é testado no topo e sai na hora: no service com
     `return` do array de erro; no controller e no middleware com `ResponseApi::error`, que já encerra a
     execução, então um `return` depois dele é ruído. O caminho feliz fica embaixo. **Evitar `else` e `elseif` sempre:** guard clause para erro, valor padrão antes do
     `if` para atribuição, `match` para três ou mais caminhos. A config de estilo ainda formata `}else{` para o
     raro caso que sobrar.

## Parte 3: erro e segurança (aprovada)

19. **Erro inesperado.** Um **tratador global do projeto** (`set_exception_handler`, registrado uma vez)
    registra o detalhe com `DiscordLogger` (`ELogger::ERROR`, com contexto: rota, empresa, id) e responde
    `server_error` com 500. O service só captura quando abre transação ou chama integração externa, e aí devolve
    o array `server_error`. Nunca `getMessage()`, trace ou SQL na resposta.
20. **Segredo e config.** `sw_env` só em `config/*.php`; o código lê `sw_config`. Nenhum segredo, senha, token
    ou URL de ambiente no código nem nos testes (o teste lê de um `.env.testing`). `.env` fora do git.
21. **Escopo de dados.** Depende do projeto: a skill pergunta se ele é multiempresa, qual coluna separa os
    dados e como protege, e grava a resposta. Sendo multiempresa, toda busca por id passa pela empresa, e a
    sugestão de mecanismo é o middleware `{Recurso}ExistsMiddleware`, que busca por
    `Model::findByCompany($idCompany, $id)`, responde 404 e compartilha o registro.

## Parte 4: rotas, jobs, scheduler e infra (aprovada)

22. **Rotas.** URL com versão (`v1/recurso`). Toda rota POST/PUT/PATCH/DELETE e toda rota com `{id}` tem
    middleware. O apelido é o nome da classe sem o sufixo, em camelCase (`validateInvoiceCreate`). Um arquivo de
    rotas por tema (`app/<Tema>/Rotas.php`), agrupado por recurso.
23. **Jobs, filas e scheduler.** Job e scheduler finos, como o controller: o job lê a mensagem, chama o
    service e faz `ack` ou `nack` (sempre um dos dois); o scheduler busca por método do model e publica um
    item por registro. Filas num enum `EQueue`, com nome de teste separado. Publicação só depois do commit, e o
    payload leva só ids. Worker com `Jobs::create()`.
24. **Infra.**
    - Migration em `database/sql/V{n}__descricao.sql` (Flyway), e nunca alterar uma já aplicada.
    - Chave de cache num enum (`ECache`), com prefixo e TTL sempre, pelo `Cache` do core.
    - Upload de imagem pelo `Storage` do core (`(new Storage)->put()->image($file)`); arquivo comum por `Integrations/Aws`.
    - Paginação por `Help::pagination()`.

## Parte 5: website Twig (aprovada)

25. **Website.** A mesma arquitetura da API. O controller fino termina em `$this->view()`, com os dados prontos
    (quem monta é o service). O template só exibe: laço e condição de exibição, sem cálculo, query ou regra.
    Pedaço repetido vira macro em `macros/`. SEO no controller com `sw_seo()`. Asset sempre por `asset()`. CSS
    no padrão do esqueleto.

## Parte 6: testes (aprovada)

26. **Testes** (molde dos dois projetos mais maduros):
    - Pest, com as suítes `Unit/` (sem banco: Helpers, Enums), `Integration/` (banco de teste: `Models/`,
      `Services/<Domínio>/`, `Jobs/`) e `Http/` (endpoint de ponta a ponta: validação 422, auth 401, escopo
      404, formato da resposta).
    - **Raiz:** `Pest.php` com 5 linhas (`Boot::start()`, suítes, `Boot::reset()` no `beforeEach`) e
      `TestCase.php`.
    - **`Support/Boot.php`:** força `env=dev` e recusa outro, liga `APP_TESTING`, recarrega a config e recria o
      banco. Some quando o core ganhar `SysWeb\Testing::boot()`.
    - **`Support/TestDatabase.php`:** cria `<projeto>_test`, apaga as tabelas e aplica `database/sql/`; recusa
      nome que não termine em `_test`.
    - **`Support/Fakes.php`:** instala todos os fakes numa chamada (`Integração::fake()`), com as
      implementações falsas em `Support/Fake/`.
    - **`Support/Fixtures.php`:** dados com nome pelo ORM (`Fixtures::company()`, `Fixtures::invoice()`) e o
      `truncate()`.
    - **`Support/Http.php`:** cliente da API de teste (`Http::post`, `Http::as($company)`).
    - **`Support/TestServer.php`:** sobe o servidor embutido que o `Http/` chama. O `ResponseApi` termina com
      `exit()`, então o endpoint não pode rodar dentro do processo do Pest.
    - **O `Fakes.php` não cobre fila nem log:** `Queue` e `DiscordLogger` ficam desligados pelo `.env` de teste
      até o core ganhar `fake()` (Revisão do design).
    - Sem Mockery, sem SQL no teste e sem serviço externo real, nem no e2e.
    - O caminho do teste espelha o do código, e o nome do teste em português diz o comportamento.
    - Controller e middleware são testados pelo `Http/`, sem teste isolado.
    - Toda regra nova nasce com teste; código existente só é movido com teste antes.

## Pedidos ao framework

Ficam fora deste repositório, porque são internos. A skill só leva, em cada regra afetada, a nota "enquanto o
core não corrigir", e confere a versão do core instalada no projeto para saber quando a nota deixa de valer.

## Parte 7: como a skill trabalha (aprovada)

27. **Modo escrever.** A skill dispara pela descrição e grava uma linha no `AGENTS.md` do projeto mandando
    carregá-la. Ela vai no `CLAUDE.md` só se o projeto já tiver um, porque o esqueleto proíbe criá-lo. Ela lê só as regras do que está sendo escrito e roda o `php-cs-fixer` nos
    arquivos tocados. A linha não copia as regras.
28. **Modo auditar e corrigir.**
    1. Reconhece o projeto (framework, API ou website, versão do PHP e do core) e lê a config, ou pergunta na
       primeira vez.
    2. Varre com um subagente por família de regra.
    3. Monta o relatório por regra, com ordem de ataque.
    4. Corrige **por domínio, com todas as regras juntas**. A primeira etapa é só o formatador, que não muda
       comportamento. Cada etapa: teste antes (sw-auto-test se faltar), verde, corrige, verde, formatador,
       aprovação e commit.
29. **Config do projeto.** `docs/sw-standards/config.md` guarda as respostas (formato do erro, e-mail,
    multiempresa) e as exceções aceitas, com o motivo e quem aceitou. `docs/sw-standards/andamento.md` guarda
    os domínios já corrigidos. Os dois vão para o git. O relatório de cada auditoria fica em
    `docs/sw-standards/<data>/`, fora do git.
30. **Arsenal**, sempre perguntando antes e seguindo sem a skill se ela não estiver instalada:
    - `sw-auto-test`: teste antes de mexer e diagnóstico no fim;
    - `sw-code-review`: contexto vazio no fim de cada etapa;
    - `sw-git-commit`: commit por etapa;
    - `sw-dead-code-scan`: comentário e código morto.
31. **Pedidos ao framework.** Fora da skill e do repositório, num arquivo local.

## Revisão do design (2026-11-19)

O revisor conferiu no core v1.11.0 o que o design dá como existente. As decisões a seguir saíram dos problemas
que ele apontou:

- **Formatador:** o `php-cs-fixer` (v3.95) não produz o estilo. Ele só garante um espaço depois de
  `if`/`foreach`, não cola `){` e não põe linha em branco **depois** do bloco. Decisão: **fixer próprio da
  systemweb**, que cuida de `if(`, `){`, `}else{` e da linha após o bloco, junto com a config. Ele vive em
  `assets/` da skill e a etapa 0 copia-o para o projeto [usuário: "ignorar" a distribuição; esta é a forma mais
  simples].
- **Erro inesperado:** um **tratador global do projeto** (`set_exception_handler`, registrado uma vez) loga o
  detalhe no `DiscordLogger` e responde `server_error` 500, sem trace. O service usa `try/catch` só para
  transação e integração externa. Sai quando o core ganhar o tratador.
- **Fila e log nos testes:** `Queue::send` e `DiscordLogger::send` não têm como virar falso no core. Até o core
  ganhar `fake()`, o `.env` de teste aponta a fila para a de teste (o `EQueue` já separa o nome com `-test`) e o
  Discord para vazio, com o logger tolerando isso. O teste confere o resultado do service, não a publicação.
- **Etapa 0 obrigatória de preparação**, antes de qualquer domínio:
  - sobe o core para **≥ 1.10**, porque `Request::share` só existe a partir dela;
  - configura o banco `_test` no `config/Database.php`;
  - instala o `Support/` padrão, que agora inclui o **`TestServer.php`**. O `ResponseApi` termina com
    `exit()`, então o `Http/` precisa de um servidor embutido;
  - instala o fixer e a config;
  - registra o tratador global de exceção;
  - remove as regras velhas (item abaixo).

  Sem a etapa 0, a skill só audita e não corrige.
- **Regras velhas dos projetos** (`.claude/rules/*` e `.claude/skills/create-*`, que contradizem as regras
  1, 4, 18b e 19): na etapa 0, com aprovação, a skill apaga ou reduz a um ponteiro, mantendo o que é só do
  projeto. A linha que carrega a skill vai **só no `AGENTS.md`**; no `CLAUDE.md` só se o projeto já tiver um,
  porque o esqueleto proíbe criá-lo. O esqueleto é atualizado do mesmo jeito.
- **Reconhecer o projeto:** pelo `require` de `system-web/system-web-framework-core` no `composer.json`, com a
  versão real lida no `composer.lock`.
- **Guard clause:** `ResponseApi::error` já encerra a execução, então um `return` depois dele é ruído.
- **Upload:** a forma certa é `(new Storage)->put()->image($file)`; o `Storage::image` estático não existe.
- **Vazamento:** nome de projeto real fora do dossiê e da skill. O `.scan-denylist` não foi alterado
  [usuário], então a conferência antes do commit é manual.
