# Code Review — Catalogo de patterns de deteccao

Lido pela skill `sw-code-review` no **Step 5**. Cada pattern e **language-agnostic** —
exemplos em linguagens especificas sao ilustracoes a adaptar. **SEMPRE** aplicar as
Regras de Supressao (Step 5.0 do SKILL.md) e a Verificacao (Step 5.5) antes de
registrar qualquer achado.

---

**5a. Seguranca**

Aplicar 5.0a (Data Origin Tracing) antes de flagear.

**5a.1. Patterns classicos de injection/XSS:**

| Pattern | Linguagens | Severidade |
|---|---|---|
| `v-html` com dados dinamicos | Vue | CRITICAL |
| `dangerouslySetInnerHTML` dinamico | React | CRITICAL |
| `innerHTML =` com input nao sanitizado | JS/TS | CRITICAL |
| `eval(`, `new Function(` com input dinamico | JS/TS/PHP/Python | CRITICAL |
| `exec(`, `shell_exec(`, `system(`, `Runtime.exec` | PHP/Python/Java/Go | CRITICAL |
| Concatenacao SQL sem parametrizacao | Qualquer | CRITICAL |
| `document.write(` | JS/TS | HIGH |
| Secrets/tokens/senhas hardcoded | Qualquer | CRITICAL |
| URLs `http://` em producao (nao https) | Qualquer | MEDIUM |
| CORS com wildcard `*` | Qualquer | HIGH |
| `unsafe` sem justificativa | Rust | HIGH |
| Protecao CSRF desabilitada | Qualquer | HIGH |
| `pickle.loads` com dados nao confiaveis | Python | CRITICAL |
| `yaml.load` sem SafeLoader | Python | HIGH |
| Deserializacao de dados nao confiaveis | Java/PHP/Python/.NET | CRITICAL |

**5a.2. Autorizacao/RBAC ausente:**

Pattern: endpoint/handler/middleware que modifica ou le recurso sensivel sem verificacao de role ou ownership.

**Deteccao language-agnostic:**

Em cada arquivo modificado que representa um endpoint (handler, controller, middleware, route, view):

1. Identificar se o endpoint faz operacao sensivel:
   - Escrita (CREATE/UPDATE/DELETE) em entidade de usuario ou admin
   - Leitura de recurso que pertence a outro usuario
   - Mudanca de permissao/role/level
   - Operacao administrativa (criar admin, mudar password de outro usuario, etc.)

2. Verificar se existe chamada a helper reconhecido de autorizacao DENTRO do handler ou em middleware encadeado:

| Padrao | Linguagens/Frameworks |
|---|---|
| `is_admin`, `isAdmin`, `isAdministrator`, `is_staff` | Qualquer |
| `has_role`, `hasRole`, `requireRole`, `requiresRole` | Qualquer |
| `can()`, `cannot()`, `authorize`, `gate` | Laravel, Pundit, CanCan |
| `@PreAuthorize`, `@RolesAllowed`, `@Secured` | Spring, JAX-RS |
| `[Authorize]`, `[AuthorizeRole]` | .NET |
| `login_required`, `permission_required`, `user_passes_test` | Django |
| `ensure_can`, `policy_scope`, `authorize!` | Rails/Pundit |
| `guard()`, `middleware(['auth'])`, `auth:sanctum` | Qualquer |
| `Gate::allows`, `Gate::check`, `Gate::denies` | Laravel |
| `is_owner`, `isOwner`, `ownsResource`, `currentUserOwns` | Qualquer |
| `isOwnerOrAdmin`, `isAuthorized` | Qualquer |

3. Se o endpoint NAO chama nenhum helper:
   - Se operacao e de escalacao de permissao (level/role/is_admin) -> **CRITICAL**
   - Se operacao modifica recurso de outro usuario (com ID vindo do request) -> **HIGH**
   - Se operacao e leitura de recurso sensivel sem ownership check -> **MEDIUM**

**Exemplos do pattern:**

PHP/SysWeb:
```php
public function __invoke(Request $Request, Response $Response, $Next)
{
    // Sem chamada a Auth::isAdministrator() ou similar
    $this->validateFields($Request); // apenas valida formato
    return $Next();
}
```

Express/Node:
```javascript
router.post('/admin/create', (req, res) => {
  // Sem middleware de auth
  createAdmin(req.body);
});
```

Django:
```python
def update_admin(request):
    # Sem @permission_required nem verificacao de is_staff
    admin = Admin.objects.get(id=request.POST['id'])
    admin.level = request.POST['level']
    admin.save()
```

**5a.3. Information Disclosure em erros:**

Pattern: mensagem interna de excecao vazando em response publica.

**Deteccao language-agnostic:**

Buscar dentro de blocos `catch`/`except`/`rescue`/`recover`:

1. Identificar response builders:

| Padrao | Linguagem |
|---|---|
| `response()`, `res.json`, `res.send`, `res.status().json` | JS/Node |
| `return jsonify(...)`, `return make_response(...)` | Python/Flask |
| `return Response(...)` | Python/Django/FastAPI |
| `return ResponseEntity.ok(...)` | Java/Spring |
| `c.JSON(...)`, `c.String(...)` | Go/Gin |
| `ResponseApi::error`, `response()->json` | PHP/Laravel/SysWeb |
| `render json:` | Rails |
| `HttpContext.Response.WriteAsync` | .NET |

2. Identificar extracao de mensagem interna:

| Padrao | Linguagem |
|---|---|
| `$e->getMessage()`, `$e->getTrace()`, `$e->getTraceAsString()` | PHP |
| `e.message`, `err.message`, `error.toString()`, `error.stack` | JS/TS |
| `str(e)`, `repr(e)`, `e.args`, `traceback.format_exc()` | Python |
| `err.Error()` (em producao sem wrap) | Go |
| `e.getMessage()`, `e.printStackTrace()`, `ExceptionUtils.getStackTrace` | Java |
| `ex.Message`, `ex.StackTrace` | C# |
| `e.message`, `e.backtrace` | Ruby |

3. Se extracao e interpolada/concatenada/passada direto para response builder -> flagear.

**Severidade:**
- Endpoint publico (sem auth) -> **HIGH**
- Endpoint autenticado -> **MEDIUM**
- Endpoint admin-only -> **LOW** (ainda recomenda correcao)

**Fix recomendado language-agnostic:**
1. Logar mensagem interna server-side (logger, discord, sentry)
2. Retornar mensagem generica ao cliente
3. Opcional: incluir ID de correlacao para rastrear no log

**5b. Bugs**

**5b.1. Typo consistency detection:**

Pattern: identificador (metodo, variavel, constante) escrito de forma incomum que aparece em multiplos lugares — provavel copy-paste de typo.

**Deteccao heuristica language-agnostic (sem AST):**

Para cada chamada de metodo/funcao em arquivos modificados:

1. Extrair identificadores chamados (ex: `.foo()`, `->foo()`, `::foo()`, `foo(`)
2. Para cada identificador raro (aparece < 5 vezes no projeto):
   a. Calcular distancia de Levenshtein contra palavras frequentes do projeto (mesmo prefixo, metodos da mesma classe)
   b. Se distancia 1-2 de uma palavra frequente E a raridade e nova -> provavel typo
3. Verificar se o identificador existe realmente:
   - Buscar por `function <nome>`, `def <nome>`, `func <nome>`, `public function <nome>`, `fn <nome>`, etc.
   - Se NAO encontrar declaracao em lugar nenhum -> **HIGH** (runtime error quando executado)
   - Se encontrar em 1 lugar mas e diferente do contexto esperado -> **MEDIUM**

**Exemplos de deteccao:**

```php
// roolback() aparece 3 vezes em diferentes arquivos
// rollback() aparece 0 vezes
// Levenshtein(roolback, rollback) = 1
// Metodos da classe DB tem rollback mas nao roolback
// -> HIGH: typo consistente em 3 arquivos
DB::roolback();
```

```javascript
// lenght usado em vez de length
arr.lenght
```

**Apresentacao:**

Listar TODAS as ocorrencias do typo como UM achado consolidado com cross-file reference:

```
Encontrado em 3 arquivos:
- file_a.php:85
- file_b.php:49
- file_c.php:63
```

**5b.2. Type coercion em external boundaries:**

Pattern: cast direto de input externo para bool/int/float/date sem validador.

**Deteccao language-agnostic:**

Combinar source externo (tabela 5.0a) + cast direto:

| Cast direto | Linguagem |
|---|---|
| `(bool)$var`, `(int)$var`, `(float)$var` | PHP |
| `Boolean(x)`, `Number(x)`, `parseInt(x)`, `parseFloat(x)` | JS |
| `bool(x)`, `int(x)`, `float(x)` sem try/except | Python |
| `strconv.Atoi(x)` sem check de erro | Go |
| `Convert.ToBoolean(x)`, `Int.Parse(x)` | C# |
| `x.to_i`, `x.to_f` sem validacao | Ruby |

Se cast e aplicado direto no source externo -> **MEDIUM** (bug silencioso) ou **HIGH** (afeta autorizacao/seguranca).

**Validadores recomendados (supressao automatica se aparecem):**

| Validador | Linguagem |
|---|---|
| `filter_var`, `FILTER_VALIDATE_*` | PHP |
| `zod`, `joi`, `yup`, `valibot` | JS/TS |
| `pydantic`, `marshmallow`, `voluptuous` | Python |
| `validator.v9` | Go |
| `FluentValidation`, `DataAnnotations` | .NET |

**Caso classico: boolean coercion em query strings**

```
// PHP: (bool)'false' === true
// JS: Boolean('false') === true
// Python: bool('false') === True (strings nao-vazias sao True)

// Truth table do bug:
// Input         | Cast direto | filter_var(FILTER_VALIDATE_BOOLEAN)
// 'false'       | true        | false
// 'true'        | true        | true
// '0'           | false (PHP)/true (JS) | false
// '1'           | true        | true
// ''            | false       | false
// null/missing  | false       | null (com flag strict)
```

**Fix recomendado:**

| Linguagem | Fix |
|---|---|
| PHP | `filter_var($value, FILTER_VALIDATE_BOOLEAN)` |
| JS | `['true','1','yes'].includes(String(value).toLowerCase())` ou lib de validacao |
| Python | `value.lower() in ('true', '1', 'yes')` |
| Go | `strconv.ParseBool(value)` com tratamento de erro |

**5b.3. Catch/exception discipline:**

| Pattern | Linguagens | Severidade |
|---|---|---|
| Catch de tipo estreito deixando outros escapar | PHP (`Exception` nao pega `Error`), Python (`Exception` nao pega `BaseException`), Java (catch especifico sem `Throwable`) | MEDIUM |
| Re-throw perdendo stack trace | Qualquer (ex: `throw new Exception($e->getMessage())` sem passar `$e` como cause) | MEDIUM |
| Chamada dentro do catch que pode lancar outra excecao nao tratada | Qualquer | MEDIUM |
| Excecao silenciada (catch vazio ou so `// TODO`) | Qualquer | HIGH |
| Error handling incorreto (swallowing sem log) | Qualquer | MEDIUM |

**Casos classicos:**

PHP 8+:
```php
// BAD: Error nao eh Exception em PHP 8
try { $obj->nonExistent(); }
catch (\Exception $e) { ... }  // nao pega TypeError, Error

// GOOD:
try { $obj->nonExistent(); }
catch (\Throwable $e) { ... }
```

Python:
```python
# BAD: esconde KeyboardInterrupt
try: do_stuff()
except BaseException: pass

# BAD: engole tudo silenciosamente
try: do_stuff()
except: pass

# GOOD:
try: do_stuff()
except Exception as e:
    logger.error("erro ao fazer stuff", exc_info=e)
    raise
```

**5b.X. Outros bugs:**

| Pattern | Severidade |
|---|---|
| Acesso null/undefined sem guard | HIGH |
| Operador de comparacao errado (`=` vs `==` vs `===`) | HIGH |
| Off-by-one em loops/slices | HIGH |
| Race conditions (estado mutavel compartilhado sem sync) | HIGH |
| Await faltando em chamadas async | HIGH |
| Mismatch de tipo de retorno | HIGH |
| Branches de condicao mortas (sempre true/false) | MEDIUM |
| Armadilhas gerais de coercao de tipo | MEDIUM |

**5c. Validacao**

| Pattern | Severidade |
|---|---|
| Campos obrigatorios sem regras de validacao | HIGH |
| Endpoints aceitando input sem validacao | HIGH |
| Verificacoes de length/range faltando em input do usuario | MEDIUM |
| Upload de arquivo sem validacao de tipo/tamanho | HIGH |
| Verificacoes null/empty faltando antes de operacoes | MEDIUM |

**5d. Codigo Morto**

| Pattern | Severidade |
|---|---|
| Modulos importados nunca usados | MEDIUM |
| Variaveis declaradas mas nunca lidas | MEDIUM |
| Parametros de funcao nunca utilizados no corpo | MEDIUM |
| Funcoes/metodos definidos mas nunca chamados | MEDIUM |
| Blocos de codigo comentados (> 3 linhas) | LOW |
| Arrays/objetos hardcoded nunca referenciados | MEDIUM |
| console.log / print / debug statements | LOW |
| Comentarios TODO/FIXME/HACK | LOW |

NAO flagear parametros quando: (1) sao de interface/contrato obrigatorio, (2) prefixados com `_`, (3) implementam interface/abstract.

**5e. Performance**

| Pattern | Severidade |
|---|---|
| Deep watchers em objetos grandes | MEDIUM |
| useEffect sem array de dependencias | MEDIUM |
| Patterns de query N+1 | HIGH |
| I/O sincrono em contexto async | MEDIUM |
| Paginacao faltando em endpoints de lista | MEDIUM |
| Re-renders / re-computacoes desnecessarias | MEDIUM |
| Memory leaks (listeners nao limpos, subscriptions nao desinscritas) | HIGH |
| Imports de bundle grandes | LOW |

**5f. Analise de Impacto**

Para cada arquivo modificado, verificar dependentes:
- Alguma funcao/classe/componente exportado mudou assinatura?
- Algum export foi removido?
- Algum arquivo deletado que outros ainda importam?
- Arquivo renomeado com referencias de import atualizadas?

Cada consumidor quebrado -> achado CRITICAL separado.

**5g. Analise de Contrato**

Comparar versoes antes/depois:
- Props/Parametros obrigatorios mudados ou removidos
- Tipos de retorno mudados
- Payloads de API (request/response)
- Eventos/Emit renomeados
- Interface/Type compartilhados alterados

Cada mudanca incompativel sem atualizacao de consumidor -> HIGH ou CRITICAL.

**5h. Analise de Fluxo**

- Rotas referenciadas estao definidas? Guards/middleware existem?
- Step machines: nomes de step consistentes?
- State management: actions/mutations definidas no store?
- Cadeias de eventos: emit -> listener correspondente?

**5i. Deteccao de Orfaos**

- Imports deletados: arquivo importado tem outros consumidores?
- Arquivos renomeados/movidos: ha referencias ao path antigo?
- Arquivos deletados: algum arquivo ainda tenta importa-los?

MEDIUM (codigo nao usado) ou HIGH (referencias quebradas).

**5j. Consistencia**

| Pattern | Severidade |
|---|---|
| Convencoes de nomenclatura mistas no arquivo | LOW |
| Patterns de error handling inconsistentes | LOW |
| Patterns async mistos (callbacks + promises + async/await) | LOW |
| Indentacao ou formatacao inconsistente | LOW |

**5k. Analise Cross-Repo (so em modo multi-repo)**

Detectar incompatibilidades entre client e server.

**5k.1. Mapear chamadas de API (lado client/consumidor):**

| Pattern | Framework |
|---|---|
| `dispatch('api/request'`, `store.dispatch('*/fetch` | Vuex |
| `axios.post(`, `axios.get(`, `axios.put(`, `axios.delete(` | Axios |
| `fetch(`, `$fetch(` | Fetch nativo / Nuxt |
| `$http.post(`, `this.http.` | Angular |
| `useFetch(`, `useMutation(` | React Query / composables |
| `api.`, `client.` seguido de `.post(`, `.get(` | Clientes customizados |

**5k.2. Mapear expectativas da API (lado server):**

| Pattern | Framework |
|---|---|
| `$Request->post('campo')`, `$Request->get('campo')` | SysWeb / PHP custom |
| `$request->input('campo')`, `$request->validated()` | Laravel |
| `$_POST['campo']`, `$_GET['campo']`, `$_REQUEST['campo']` | PHP nativo |
| `req.body.campo`, `req.query.campo`, `req.params.campo` | Express / Node |
| `request.data['campo']`, `request.GET['campo']` | Django |
| `params[:campo]`, `params.require(:campo)` | Rails |
| `c.Query("campo")`, `c.PostForm("campo")` | Gin / Go |

**5k.3. Comparar contratos:**

| Situacao | Severidade |
|---|---|
| Campo obrigatorio no server mas nao enviado pelo client | CRITICAL |
| Campo enviado pelo client mas nao acessado no server | MEDIUM |
| Nome de campo diferente (ex: `brandId` vs `id_brand`) | HIGH |
| Valor de enum incompativel (case-sensitive) | HIGH (LOW se server faz `upper()`) |
| Tipo incompativel (string vs int) | MEDIUM |
| Endpoint chamado mas nao existe no server | CRITICAL |

**5k.4. Comparar enums/constantes:**

Buscar definicoes em ambos os lados e reportar divergencias como MEDIUM.

**5l. Refatoracao**

| Pattern | Severidade |
|---|---|
| Cadeia if/elseif/else substituivel por early return | MEDIUM |
| Cadeia if/elseif substituivel por match/switch/mapa | MEDIUM |
| Variavel usada sem inicializacao default | MEDIUM |
| Retorno inconsistente entre branches | MEDIUM |
| Codigo duplicado no mesmo arquivo (>5 linhas identicas) | MEDIUM |
| Codigo duplicado entre arquivos diferentes | MEDIUM |
| Codigo duplicado com codigo existente no projeto | MEDIUM |
| Extracao para reduzir complexidade | MEDIUM |
| Uso de API nao-idiomatica do framework | LOW |
| Metodo/funcao com >40 linhas | LOW |
| Aninhamento >3 niveis | MEDIUM |
| Condicionais negativos complexos | LOW |
| Magic numbers/strings sem constante | LOW |
| Logica de dados fora da camada correta | MEDIUM |

**5m. Regras do Projeto**

Aplicar cada regra coletada no Step 0.

Para cada regra:
1. Verificar se algum arquivo modificado bate com o glob da regra
2. Aplicar o pattern de deteccao contra o conteudo
3. Para cada violacao:
   - Categoria: `consistency` ou `refactoring`
   - Severidade: conforme definido na regra (default LOW; MEDIUM se "obrigatorio"/"sempre"/"nunca")
   - Incluir no achado: **Regra aplicada:** `<arquivo-fonte>` linha X

Exemplo:

Regra em `.claude/rules/naming-conventions.md`:
> Metodos privados em `_camelCase` (underscore + camelCase)

Violacao em `AdminNewMiddleware.php:19`:
```php
private function validateNewParameters() { ... }
```

Achado:
```
[LOW] #42 Metodo privado sem underscore
AdminNewMiddleware.php:19 | consistency

Antes:
    private function validateNewParameters() { ... }

Depois:
    private function _validateNewParameters() { ... }

Regra aplicada: .claude/rules/naming-conventions.md (metodos privados em _camelCase)
```
