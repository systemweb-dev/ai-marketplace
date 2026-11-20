# Subagentes da varredura

Na auditoria, dispare **um subagente por família**, todos na mesma mensagem, para rodarem em paralelo. Cada um lê só
as regras da sua família e só olha onde a família manda. Ninguém edita nada. Quem corrige é o agente principal,
depois do relatório e da aprovação.

O estilo não tem subagente: ele sai do `vendor/bin/php-cs-fixer fix --dry-run --diff --using-cache=no`
(`references/regras/estilo.md`). Família que não se aplica ao projeto fica de fora. Exemplo: Website em projeto
`application => 'api'` no `config/Env.php`.

| Família | Regras (`references/regras/`) | Onde olhar |
|---|---|---|
| Arquitetura | `validacao-no-middleware`, `controller-fino`, `banco-no-model`, `services-e-integracoes`, `transacao-e-fila` | `app/`, `middleware/` |
| Código | `dados-no-topo-e-sem-cadeia`, `ruido-defensivo`, `guard-clause-sem-else`, `nomes-e-enums`, `tipos-e-comentarios`, `datas-dinheiro-pacotes` | cada arquivo PHP fora de `vendor/` |
| Erro e segurança | `erro-e-resposta`, `seguranca-e-config` | `app/`, `middleware/`, `config/`, `tests/` |
| Rotas, jobs e infra | `rotas`, `jobs-e-scheduler`, `infra` | `app/*/Rotas.php`, `config/Middleware.php`, `jobs/`, `scheduler/`, `database/` |
| Testes | `testes` | `tests/`, `phpunit.xml` |
| Website | `website-twig` | `app/*/Views`, `macros/`, controllers do website |

## Antes de disparar

Troque nos prompts:

- `<RAIZ>`: o caminho absoluto do projeto;
- `<SKILL>`: o caminho absoluto desta skill;
- `<RESPOSTAS>`: a seção "Respostas" do `docs/sw-standards/config.md`, copiada;
- `<EXCECOES>`: a tabela "Exceções aceitas" do mesmo arquivo, copiada (ou "nenhuma").

Copie as respostas e as exceções para dentro do prompt. Não basta mandar o subagente ler o arquivo: o subagente
pode pular a leitura, e a exceção vira falso positivo.

## Bloco comum (vai no fim de todo prompt)

```text
Regras de trabalho:
- Só leia, não edite. Não crie, não apague e não formate nenhum arquivo. Não rode composer, git, testes nem o fixer.
- Leia primeiro os arquivos de regra acima, inteiros. A seção "Como reconhecer" diz o que procurar; "Certo" e
  "Errado" tiram a dúvida; "Enquanto o core não corrigir" diz o que é contorno aceito.
- Ignore vendor/, node_modules/, storage/ e tools/.
- Respostas deste projeto (valem mais que o padrão da regra):
<RESPOSTAS>
- Exceções aceitas: NÃO acuse nenhum ponto desta tabela (mesmo arquivo e mesma regra; se a linha mudou um pouco
  e o trecho é o mesmo, também não acuse):
<EXCECOES>
- Acuse só o que você viu no arquivo, com a linha conferida. Na dúvida, ponha no fim, em "Dúvidas", e não na lista.

Saída: uma violação por linha, neste formato exato, agrupada por regra:
arquivo:linha · regra · trecho · correção proposta

- arquivo: relativo à raiz do projeto;
- regra: o nome do arquivo de regra, sem .md;
- trecho: a linha (ou o pedaço dela) como está, até 100 caracteres;
- correção proposta: uma frase, no vocabulário da regra.

Depois da lista, escreva "Contagem:" com o total por regra e, se houver, "Dúvidas:". Se não achou nada, escreva
"Nenhuma violação." e a contagem zerada.
```

## Arquitetura

```text
Você audita a arquitetura de um projeto PHP do framework da systemweb, em <RAIZ>.

Leia estas regras:
- <SKILL>/references/regras/validacao-no-middleware.md
- <SKILL>/references/regras/controller-fino.md
- <SKILL>/references/regras/banco-no-model.md
- <SKILL>/references/regras/services-e-integracoes.md
- <SKILL>/references/regras/transacao-e-fila.md

Onde olhar: app/ e middleware/. Percorra cada controller, middleware, model, service, integração e helper.
Procure em especial: leitura de entrada ou validação no controller; query, SQL ou escrita fora de Models/;
consulta dentro de laço (N+1); controller com regra de negócio, try/catch ou método privado; service fora de
Services/<Domínio>/ ou não estático; SDK ou HTTP fora de Integrations/<Fornecedor>/; integração sem fake();
transação fora do service; Queue::send antes do commit.

<bloco comum>
```

## Código

```text
Você audita o código PHP de um projeto do framework da systemweb, em <RAIZ>.

Leia estas regras:
- <SKILL>/references/regras/dados-no-topo-e-sem-cadeia.md
- <SKILL>/references/regras/ruido-defensivo.md
- <SKILL>/references/regras/guard-clause-sem-else.md
- <SKILL>/references/regras/nomes-e-enums.md
- <SKILL>/references/regras/tipos-e-comentarios.md
- <SKILL>/references/regras/datas-dinheiro-pacotes.md

Onde olhar: cada arquivo .php do projeto fora de vendor/, e o composer.json (pacotes). Liste os arquivos com
find <RAIZ> -name '*.php' -not -path '*/vendor/*' -not -path '*/node_modules/*' -not -path '*/tools/*' e
percorra todos. A versão do PHP do projeto está nas respostas: recurso acima dela é violação.
Procure em especial: leitura de dado no meio do método e cadeia no foreach/if; cast, ?? e empty() redundantes;
json_decode sem JSON_THROW_ON_ERROR; else/elseif e return depois de ResponseApi::error; nome em português ou
abreviado, string solta onde cabe enum; parâmetro ou retorno sem tipo, strict_types, comentário que repete o
código ou código comentado; date()/strtotime(), float em dinheiro, pacote fora da lista.

<bloco comum>
```

## Erro e segurança

```text
Você audita o tratamento de erro e a segurança de um projeto PHP do framework da systemweb, em <RAIZ>.

Leia estas regras:
- <SKILL>/references/regras/erro-e-resposta.md
- <SKILL>/references/regras/seguranca-e-config.md

Onde olhar: app/, middleware/, config/ e tests/; também www/index.php e config/ExceptionHandler.php (tratador
global), .gitignore e os .env*
versionados (git -C <RAIZ> ls-files '.env*'). Não abra nem copie valor de .env: diga só se o arquivo está no git.
Procure em especial: ResponseApi::error com menos de três argumentos ou com frase no código; getMessage(), trace
ou exceção na resposta; ResponseApi ou exit em service, model ou helper; service que devolve false/null ou lança
para erro esperado; resposta sem Api::returnAttributes; try/catch fora de transação ou integração; tratador
global ausente (www/index.php sem require __DIR__ . '/../config/ExceptionHandler.php'; antes do new
SysWeb\System(), ou config/ExceptionHandler.php sem set_exception_handler; com os dois, o projeto está preparado:
não acuse); isset($x['error']) sem is_array($x) && na frente; sw_env fora de config/; segredo, token ou URL de ambiente no código ou no teste; e, se o
projeto for multiempresa (veja as respostas), busca por id sem a empresa e rota com {id} sem o mecanismo
registrado.
Não copie segredo para a saída: no trecho, troque o valor por ***.

<bloco comum>
```

## Rotas, jobs e infra

```text
Você audita rotas, jobs, scheduler e infraestrutura de um projeto PHP do framework da systemweb, em <RAIZ>.

Leia estas regras:
- <SKILL>/references/regras/rotas.md
- <SKILL>/references/regras/jobs-e-scheduler.md
- <SKILL>/references/regras/infra.md

Onde olhar: app/*/Rotas.php e app/*/Middleware.php, config/Middleware.php, jobs/, scheduler/ e database/
(migrations em database/sql/). Para o Cache, o Storage e a paginação, procure também em app/
(grep -rn "Cache::\|Storage\|move_uploaded_file\|ceil(" app).
Procure em especial: URL sem a versão; POST/PUT/PATCH/DELETE sem middlewareBefore; {id} sem o middleware de
existência; middlewareBefore encadeado (o core substitui, não acumula); apelido de middleware fora do padrão;
job com regra, query ou sem ack/nack em algum caminho; json_decode sem JSON_THROW_ON_ERROR no job; scheduler que
faz o trabalho no laço em vez de Queue::send; fila fora do EQueue; migration fora de V{n}__descricao.sql ou com
número repetido; chave de cache sem ECache ou sem TTL; upload fora do (new Storage)->put()->image().

<bloco comum>
```

## Testes

```text
Você audita a suíte de testes de um projeto PHP do framework da systemweb, em <RAIZ>.

Leia esta regra:
- <SKILL>/references/regras/testes.md

Compare tests/Support/ com os moldes em <SKILL>/assets/tests-support/ (Pest.php e Support/*.php).

Onde olhar: tests/, phpunit.xml e o composer.json (autoload-dev e require-dev). Para saber o que falta testar,
liste os services, models e jobs (app/LogicApp/Services, app/LogicApp/Models, jobs/) e as rotas (app/*/Rotas.php)
e procure o teste de cada um.
Procure em especial: Support/ diferente dos moldes (sem app-router.php, sem recusa de banco sem _test, sem
env=dev forçado); falta do autoload-dev de Tests\; Mockery ou createMock; SQL ou insert fora do Fixtures.php;
controller ou middleware testado fora do Http/; token fixo, URL de fornecedor ou chave no teste; integração sem
linha no Fakes.php; teste na pasta errada ou com nome sem comportamento; service, model ou job sem teste;
endpoint sem os casos 401, 404 (multiempresa) e 422.
Para código sem teste, use o arquivo do código e a linha 1, e proponha o teste que falta.

<bloco comum>
```

## Website

```text
Você audita a camada de website (Twig) de um projeto PHP do framework da systemweb, em <RAIZ>.

Leia estas regras:
- <SKILL>/references/regras/website-twig.md
- <SKILL>/references/regras/controller-fino.md (só para comparar: os sinais de controller valem aqui)

Onde olhar: app/*/Views (todos os .twig), macros/ e os controllers do website (app/<Tema>/Controllers/ dos temas
que renderizam com $this->view). Ache-os com grep -rln '\->view(' <RAIZ>/app.
Procure em especial: controller do website com query, regra ou leitura de request na ação; $this->view recebendo
model ou Collection; ação de página sem sw_seo(); no .twig, aritmética ou number_format sobre valor de negócio,
|date sobre campo cru, condição que decide regra, app.global.* decidindo o que exibir, caminho de asset ou de
storage escrito à mão, <title>/<meta description> fixos, <style> solto, marcação repetida em dois templates e
macro definida dentro de Views/.

<bloco comum>
```

## Depois da varredura

1. Junte as saídas e descarte as linhas repetidas. O mesmo `arquivo:linha` com a mesma regra, vindo de duas
   famílias, conta uma vez.
2. Confira por amostra: abra 2 ou 3 achados de cada família no arquivo. Se um achado não bate, confira os outros
   daquela regra.
3. Tire o que estiver nas exceções aceitas, se algum escapou.
4. Monte o relatório em `docs/sw-standards/<data>/relatorio.md`, agrupado por regra, com a contagem e a ordem de
   ataque. Vazamento de erro e query fora do model vêm antes de estilo.
