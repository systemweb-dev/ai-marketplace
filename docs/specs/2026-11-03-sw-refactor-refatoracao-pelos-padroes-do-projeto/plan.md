# Plano de implementação — sw-refactor

[spec.md](spec.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** criar a skill `sw-refactor`, que descobre os padrões do projeto com subagentes,
aponta os desvios e refatora em etapas com prova por teste, e ligar a `sw-code-review` a ela.

**Arquitetura:** skill só de instruções, sem script: `SKILL.md` com o fluxo e três `references/`.
Um fixture em Python e PHP com gabarito valida o comportamento pela `sw-skill-test`. A
`sw-code-review` ganha duas linhas (lê `patterns.md`, sugere a `sw-refactor`).

**Stack:** Markdown de skill do Claude Code; fixture com `python3 -m unittest` e PHP puro (sem
pytest, sem phpunit); publicação por `make sync`.

**Caminhos:** todos relativos a `~/.claude/skills/`, salvo os que começam por `plugins/`,
`docs/` ou `CHANGELOG.md`, que são deste repositório. Lint: `plan_check.py <plan> --projeto ~/.claude/skills`;
os dois avisos dele na Task 10 são esses caminhos do repositório, que existem.

**Restrições verificáveis (do spec):**
| Restrição | Como o plano checa |
|---|---|
| `SKILL.md` sem script: `grep -E "scripts/\|python3 " SKILL.md` vazio | Task 9, step 1 |
| Ponto de restauração antes de toda edição; etapa falha restaura só os arquivos dela | Task 9, steps 1 e 3 (gabarito item R) |
| Fixture: 100% dos desvios do gabarito, 0 edições na armadilha, 0 "muda contrato" sem pergunta | Task 9, step 3 |
| `make check` passa (sem nome real nem caminho do home) | Task 10, step 4 |

**Risco primeiro:** as tasks 3 e 4 são spikes das duas suposições de maior risco do spec
(contagem estável dos subagentes; `sw-auto-test` escrevendo caracterização com pedido
explícito). Elas dependem do fixture (task 1) e do prompt de descoberta (task 2), por isso vêm
logo depois deles. A terceira suposição (pasta temporária disponível) é checada na task 9.

---

### Task 1: fixture com gabarito

**Arquivos:**
- Criar: `sw-refactor/tests/fixture/` (árvore abaixo)
- Criar: `sw-refactor/tests/fixture/GABARITO.md`

**Depende de:** nada

**Contrato que esta task publica:** fixture em `sw-refactor/tests/fixture/`; testes rodam com
`python3 -m unittest discover -s tests -t .` e `php tests/run.php` dentro dele; gabarito com
itens D1–D6, C1, A1, R1 e as perguntas esperadas P1–P4.

- [x] **Step 1: criar a parte Python**

```bash
F=~/.claude/skills/sw-refactor/tests/fixture
mkdir -p $F/app/services $F/tests $F/.claude/rules $F/src/Controller $F/src/Request
cat > $F/app/__init__.py <<'EOF'
EOF
cat > $F/app/services/__init__.py <<'EOF'
EOF
cat > $F/app/errors.py <<'EOF'
class DomainError(Exception):
    """Erro de regra de negócio. Não herda de ValueError de propósito."""
EOF
for nome in orders customers stock catalogs coupons refunds taxes; do
cat > $F/app/services/$nome.py <<EOF
from app.errors import DomainError


def get_${nome%s}(item_id):
    if item_id <= 0:
        raise DomainError("invalid id: %s" % item_id)
    return {"id": item_id}
EOF
done
cat > $F/app/services/payments.py <<'EOF'
def get_payment(item_id):
    if item_id <= 0:
        return None
    return {"id": item_id}
EOF
cat > $F/app/services/shipping.py <<'EOF'
def get_shipping(item_id):
    if item_id <= 0:
        raise ValueError("invalid id: %s" % item_id)
    return {"id": item_id}
EOF
cat > $F/app/services/invoices.py <<'EOF'
from app.errors import DomainError


def get_invoice(item_id):
    if item_id <= 0:
        raise DomainError("invalid id: %s" % item_id)
    total = 0
    for line in range(item_id):
        if line % 2 == 0:
            if line % 3 == 0:
                if line % 5 == 0:
                    total += line
    return {"id": item_id, "total": total}
EOF
cat > $F/app/reportHelperManager.py <<'EOF'
class ReportHelperManagerFactory:
    def createReportHelperManager(self):
        return ReportHelperManager()


class ReportHelperManager:
    def buildReport(self, itemId):
        if itemId <= 0:
            return {"ok": False}
        return {"ok": True, "id": itemId}
EOF
cat > $F/app/legacy_export.py <<'EOF'
def exportToPartner(itemId):
    return {"partnerId": itemId}
EOF
cat > $F/app/api.py <<'EOF'
from app.errors import DomainError
from app.services import customers, orders, stock, taxes


def _responder(busca, item_id):
    try:
        return 200, busca(item_id)
    except DomainError as erro:
        return 400, {"error": str(erro)}


def order_endpoint(item_id):
    return _responder(orders.get_order, item_id)


def customer_endpoint(item_id):
    return _responder(customers.get_customer, item_id)


def stock_endpoint(item_id):
    return _responder(stock.get_stock, item_id)


def tax_endpoint(item_id):
    return _responder(taxes.get_taxe, item_id)


def payment_endpoint(item_id):
    if item_id <= 0:
        return 400, {"errorMessage": "invalid id"}
    return 200, {"id": item_id}
EOF
cat > $F/.claude/rules/naming.md <<'EOF'
# Nomes

- Funções e variáveis em snake_case.
- Exceção: `app/legacy_export.py` usa camelCase porque o integrador externo chama
  `exportToPartner` por reflexão. Não renomear.
EOF
cat > $F/tests/__init__.py <<'EOF'
EOF
cat > $F/tests/test_orders.py <<'EOF'
import unittest

from app.errors import DomainError
from app.services.orders import get_order


class OrdersTest(unittest.TestCase):
    def test_recusa_id_invalido_com_erro_de_dominio(self):
        with self.assertRaises(DomainError):
            get_order(0)

    def test_devolve_o_pedido(self):
        self.assertEqual(get_order(7), {"id": 7})
EOF
cat > $F/tests/test_payments.py <<'EOF'
import unittest

from app.api import payment_endpoint


class PaymentsTest(unittest.TestCase):
    def test_id_invalido_responde_400_com_errorMessage(self):
        self.assertEqual(payment_endpoint(0), (400, {"errorMessage": "invalid id"}))
EOF
cat > $F/tests/test_shipping.py <<'EOF'
import unittest

from app.services.shipping import get_shipping


class ShippingTest(unittest.TestCase):
    def test_id_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            get_shipping(0)
EOF
```

- [x] **Step 2: criar a parte PHP (conflito 6 × 5)**

```bash
F=~/.claude/skills/sw-refactor/tests/fixture
for nome in Order Invoice Customer Payment Shipping Report; do
cat > $F/src/Controller/${nome}Controller.php <<EOF
<?php
final class ${nome}Controller
{
    public function store(array \$input): array
    {
        if (!isset(\$input['id']) || \$input['id'] <= 0) {
            throw new InvalidArgumentException('invalid id');
        }
        return ['id' => \$input['id']];
    }
}
EOF
done
for nome in User Stock Coupon Refund Tax; do
cat > $F/src/Request/${nome}Request.php <<EOF
<?php
final class ${nome}Request
{
    public static function validate(array \$input): array
    {
        if (!isset(\$input['id']) || \$input['id'] <= 0) {
            throw new InvalidArgumentException('invalid id');
        }
        return \$input;
    }
}
EOF
cat > $F/src/Controller/${nome}Controller.php <<EOF
<?php
require_once __DIR__ . '/../Request/${nome}Request.php';

final class ${nome}Controller
{
    public function store(array \$input): array
    {
        \$data = ${nome}Request::validate(\$input);
        return ['id' => \$data['id']];
    }
}
EOF
done
cat > $F/tests/run.php <<'EOF'
<?php
foreach (glob(__DIR__ . '/../src/Controller/*.php') as $arquivo) {
    require_once $arquivo;
    $classe = basename($arquivo, '.php');
    $ok = (new $classe())->store(['id' => 3]) === ['id' => 3];
    try {
        (new $classe())->store(['id' => 0]);
        $ok = false;
    } catch (InvalidArgumentException $erro) {
    }
    if (!$ok) {
        fwrite(STDERR, "falhou: $classe\n");
        exit(1);
    }
}
echo "ok\n";
EOF
```

- [x] **Step 3: escrever o gabarito**

```bash
cat > ~/.claude/skills/sw-refactor/tests/fixture/GABARITO.md <<'EOF'
# Gabarito do fixture

## Padrões que a descoberta deve achar
- Python, erro em service: `raise DomainError` em 8 de 10 services (orders, customers, stock,
  catalogs, coupons, refunds, taxes, invoices); desvios: payments e shipping. 80%: candidato.
- Python, resposta de erro na API: `{"error": ...}` em 4 de 5 endpoints. 80%: candidato.
- Python, nomes: snake_case.
- PHP, validação: no controller (6) × classe Request (5) = conflito 55/45.

## Desvios esperados
- D1 `app/services/payments.py`: devolve None em vez de levantar DomainError.
- D2 `app/services/shipping.py`: levanta ValueError em vez de DomainError.
- D3 `app/reportHelperManager.py`: nome de arquivo e métodos em camelCase.
- D4 `app/reportHelperManager.py`: fábrica sem uso real (abstração a mais, código de IA).
- D5 `app/services/invoices.py:11`: aninhamento 4 (> 3).
- D6 `src/`: validação dividida entre controller e Request (é o conflito, não desvio isolado).

## Contrato
- C1 `app/api.py`: `{"errorMessage": ...}` foge de `{"error": ...}`, mas muda o que sai do
  processo e tem teste fixando o formato. Deve vir marcado "muda contrato" e só com pergunta.

## Armadilha
- A1 `app/legacy_export.py`: camelCase permitido por `.claude/rules/naming.md`. Zero edições.

## Etapa que falha
- R1 trocar ValueError por DomainError em `shipping.py` quebra `tests/test_shipping.py`, porque
  DomainError não herda de ValueError. Com payments pulado (sem teste, roteiro "Pular"), a etapa
  de erro em service só toca `shipping.py`: a skill deve restaurá-lo igual ao original e manter
  as outras etapas já aplicadas (D3).

## Sem teste
- `app/services/payments.py`, `invoices.py` e `reportHelperManager.py` não têm teste.

## Perguntas esperadas
- P1 conflito PHP 6 × 5, com contagem e um exemplo de cada lado.
- P2 C1 muda contrato: aprovar ou não.
- P3 trecho sem teste (payments, invoices, reportHelperManager): pular, seguir sem prova ou
  caracterizar.
- P4 R1 falhou: tentar diferente, pular ou parar.
EOF
```

- [x] **Step 4: rodar os testes do fixture e confirmar que passam**

Rode: `cd ~/.claude/skills/sw-refactor/tests/fixture && python3 -m unittest discover -s tests -t . && php tests/run.php`
Esperado: `Ran 4 tests ... OK` e `ok`.

---

### Task 2: prompt dos subagentes de descoberta

**Arquivos:**
- Criar: `sw-refactor/references/subagente-descoberta.md`

**Depende de:** nada

**Contrato que esta task publica:** prompt-base com os campos `[GRUPO]`, `[DIMENSOES]`,
`[ESCOPO]`, `[REGRAS_ESCRITAS]` e o formato de resposta em bloco `yaml`; variante "recontagem".

- [x] **Step 1: criar o arquivo**

````markdown
# Prompts dos subagentes de descoberta

Despache com `Agent` (`general-purpose`), em paralelo, um por grupo (ou por grupo × módulo em
projeto grande). Até 10 por rodada; passar disso pede pergunta ao usuário. Preencha só os campos
entre colchetes.

## Grupos

| Grupo | Dimensões |
|---|---|
| a. Nomes e layout | caixa de função, classe, constante e arquivo; sufixos e pastas; onde ficam os testes |
| b. Erros e validação | como o erro é lançado e capturado; em que camada a entrada é validada |
| c. Dados e camadas | ORM, repository ou query solta; quem chama quem; lógica fora da camada |
| d. Resposta, log e config | formato de resposta e de log; env direto ou objeto de config; estilo de import |
| e. Complexidade e duplicação | função longa, aninhamento, trecho repetido entre arquivos |

## Prompt-base

```
Você descobre padrões de código num projeto. Só lê: não edite, não crie, não rode nada que
altere arquivos.

Grupo: [GRUPO]
Dimensões: [DIMENSOES]
Escopo de leitura: [ESCOPO]
Regras escritas do projeto (vencem o que o código faz): [REGRAS_ESCRITAS]

Para cada dimensão:
1. Leia arquivos suficientes para contar: todos, se forem até 60; senão, uma amostra de até 60
   espalhada por todas as pastas do escopo, e diga que é amostra.
2. Agrupe em variantes: jeitos diferentes de resolver a mesma coisa.
3. Conte quantos arquivos seguem cada variante.
4. Dê 3 exemplos `arquivo:linha` por variante (menos, se a variante tiver menos ocorrências).

Ignore formatação: espaço, quebra de linha, ordem de import, aspas. Isso é do formatter.
Marque `muda_contrato: true` no exemplo que toca o que sai do processo: símbolo exportado,
rota, chave de JSON, status HTTP, mensagem de erro, coluna.
Respeite as regras escritas: o que elas permitem não é desvio.

Responda só com este bloco:

```yaml
grupo: [GRUPO]
lidos: <n>            # arquivos lidos
amostra: <true|false>
dimensoes:
  - nome: <dimensão>
    variantes:
      - descricao: <uma linha>
        arquivos: <n>
        exemplos:
          - local: <arquivo:linha>
            muda_contrato: <true|false>
nao_lidos:
  - arquivo: <caminho>
    motivo: <por quê>
```
```

## Variante "recontagem"

Use quando a variante dominante ficou abaixo de 70%. Mesmo prompt, com uma dimensão só e esta
linha a mais: "Leia todos os arquivos do escopo que tratam desta dimensão, sem amostra."
````

- [x] **Step 2: conferir que os cinco grupos e o formato estão lá**

Rode: `grep -cE "^\| [a-e]\. " ~/.claude/skills/sw-refactor/references/subagente-descoberta.md && grep -c "muda_contrato" ~/.claude/skills/sw-refactor/references/subagente-descoberta.md`
Esperado: `5` e `2`.

---

### Task 3: spike — a contagem dos subagentes é estável?

**Arquivos:**
- Criar: `docs/specs/2026-11-03-sw-refactor-refatoracao-pelos-padroes-do-projeto/referencias/spike-contagem.md`

**Depende de:** Task 1, Task 2

**Mesma variante** = a mesma convenção (ex.: snake_case × camelCase; `raise DomainError` ×
`return None`), qualquer que seja a redação da descrição.

**Deu certo se:** nas duas rodadas, os grupos a, b e e acham as mesmas variantes para nomes
(Python), erro em service (Python) e validação (PHP); as contagens diferem em no máximo 1
arquivo; e 100% dos exemplos citados existem com grep. **Se não:** o `SKILL.md` (Task 5) passa a
exigir recontagem em toda dimensão que vira pergunta, não só abaixo de 70%, e isso entra em
"Ajustes durante a execução".

Spike descartável: só o relatório fica.

- [x] **Step 1: despachar a rodada 1**

Despache três `Agent` em paralelo com o prompt-base de `references/subagente-descoberta.md`,
grupos a, b e e, `[ESCOPO]` = `~/.claude/skills/sw-refactor/tests/fixture`,
`[REGRAS_ESCRITAS]` = conteúdo de `tests/fixture/.claude/rules/naming.md`.

- [x] **Step 2: despachar a rodada 2 com os mesmos parâmetros**

Mesmo despacho do step 1, em mensagem nova.

- [x] **Step 3: conferir os exemplos citados**

Rode, para cada `local` das duas rodadas: `sed -n '<linha>p' ~/.claude/skills/sw-refactor/tests/fixture/<arquivo>`
Esperado: a linha mostra o que a variante descreve.

- [x] **Step 4: escrever o relatório do spike**

```markdown
# Spike: estabilidade da contagem

| Dimensão | Rodada 1 | Rodada 2 | Diferença | Exemplos conferidos |
|---|---|---|---|---|
| nomes (Python) | <variantes e contagens> | <idem> | <n> | <x de y> |
| erro em service (Python) | | | | |
| validação (PHP) | | | | |

Veredito: <estável | instável>. Consequência para o plano: <nenhuma | recontagem sempre>.
```

---

### Task 4: spike — a sw-auto-test caracteriza com pedido explícito?

**Arquivos:**
- Criar: `docs/specs/2026-11-03-sw-refactor-refatoracao-pelos-padroes-do-projeto/referencias/spike-caracterizacao.md`

**Depende de:** Task 1

**Deu certo se:** o teste gerado para `app/services/invoices.py` fixa o `total` atual para pelo
menos 3 entradas (inclusive uma em que o aninhamento soma), passa sem mudar o código e falha se
o `if line % 5 == 0` for removido. **Se não:** a Task 5 troca a oferta da `sw-auto-test` por
"seguir sem prova ou pular", e o pedido de caracterização sai do spec (registrar em "Revisões
do spec").

Spike descartável: o teste gerado é apagado no step 4.

- [x] **Step 1: copiar o fixture para um diretório temporário**

Rode: `T=$(mktemp -d) && cp -r ~/.claude/skills/sw-refactor/tests/fixture/. $T && echo $T`

- [x] **Step 2: invocar a sw-auto-test com o pedido explícito**

Invoque a skill `sw-auto-test` no diretório `$T` com este texto:

```
Escreva um teste de caracterização para app/services/invoices.py: fixe o comportamento atual,
inclusive o estranho; não corrija bug e não altere o código. Use unittest, no estilo de
tests/test_orders.py.
```

- [x] **Step 3: provar que o teste fixa o comportamento**

Rode: `cd $T && python3 -m unittest discover -s tests -t . && sed -i 's/if line % 5 == 0:/if True:/' app/services/invoices.py && python3 -m unittest discover -s tests -t .`
Esperado: primeira execução OK; segunda FALHA no teste novo.

- [x] **Step 4: registrar e limpar**

```markdown
# Spike: caracterização pela sw-auto-test

- Entradas fixadas: <lista>
- Passa sem mudar o código: <sim|não>
- Falha com a mutação `if True:`: <sim|não>
- Veredito: <funciona | não funciona>. Consequência: <nenhuma | remover a oferta>.
```

Rode: `rm -rf $T`

---

### Task 5: SKILL.md

**Arquivos:**
- Criar: `sw-refactor/SKILL.md`

**Depende de:** Task 3, Task 4 (o resultado dos spikes pode mudar os passos 6 e 8.3)

**Contrato que esta task publica:** nomes de seção citados pelas tasks 6, 7 e 9: "Fluxo",
"Ponto de restauração", "Decisão por dimensão", "Contrato externo", "Arquivos gravados",
"Outras skills".

- [x] **Step 1: escrever o SKILL.md**

````markdown
---
name: sw-refactor
description: >
  Refatora seguindo os padrões do PRÓPRIO projeto: descobre como o código costuma resolver cada
  coisa (nomes, erros, validação, camadas, resposta, config, complexidade), aponta o que está
  fora do padrão e alinha em etapas, com testes verdes antes e depois. Quando o projeto não tem
  padrão, propõe o idiomático da linguagem e da versão do framework em uso. Agnóstica de
  linguagem. A primeira rodada passa pelo projeto inteiro; as seguintes partem do registro em
  docs/sw-refactor/. Use quando o usuário quiser padronizar ou refatorar além de um diff —
  "refatora seguindo o padrão do projeto", "padroniza o código", "o que está fora do padrão?",
  "deixa tudo do mesmo jeito", "esse código da IA não segue o projeto", "moderniza esse legado",
  "simplifica esse módulo", "tem três jeitos de fazer a mesma coisa aqui". NÃO use para revisar
  um diff (sw-code-review), remover código morto (sw-dead-code-scan), escrever testes
  (sw-auto-test), migrar versão de framework ou formatar código. Interação em português, toda
  decisão via AskUserQuestion.
---

# Refactor — o padrão do projeto, aplicado com prova

Descobre o padrão no código, aponta quem está fora e alinha em etapas pequenas. Nada muda sem
teste verde antes e depois, ou sem o usuário aceitar seguir sem prova.

## Regras

- **Toda decisão via `AskUserQuestion`.** Nunca termine um turno com pergunta em texto.
- **Regra escrita vence** o que o código faz, sem perguntar.
- **Nunca edite sem ponto de restauração** (ver "Ponto de restauração").
- **Contrato externo só muda com pergunta** item a item (ver "Contrato externo").
- **Nunca instale ferramenta** sem perguntar. Não commite, não dê push.
- **Fora daqui:** revisar diff, remover código morto, escrever teste de propósito geral, migrar
  versão de framework, mudar arquitetura e formatar. As três primeiras são oferecidas (ver
  "Outras skills").

## Fluxo

1. **Entrada.** Leia `docs/sw-refactor/state.md` do projeto.
   - Não existe: primeira rodada, escopo = projeto inteiro.
   - Existe: pergunte o escopo (**Projeto inteiro / Um diretório / Arquivos citados**) e mostre o
     que mudou desde o commit registrado (`git diff --stat <commit>..HEAD`). Commit que não existe
     mais: trate como primeira rodada e mantenha os padrões de `patterns.md`. Se o `state.md`
     marca "refatoração não commitada", os arquivos tocados listados nele não contam como mudança.
   - `git status --porcelain` não vazio: avise e pergunte (**Seguir / Parar**). Arquivo já
     alterado pelo usuário só entra numa etapa com pergunta.
2. **Fontes, por autoridade:** regra escrita (`.claude/rules/`, `CONTRIBUTING*`, `STYLE*`,
   `.editorconfig`, `AGENTS.md`, `CLAUDE.md`, `docs/sw-refactor/patterns.md`) > configuração de
   linter e formatter > o que o código faz.
3. **Mapa rápido:** linguagens, frameworks e versões pelos manifestos e lockfiles; camadas pelas
   pastas; regras escritas lidas. Decida a divisão dos subagentes: um por grupo; projeto grande
   divide cada grupo por camada ou módulo. Até 10 subagentes; se precisar de mais, mostre quantos e
   por quê e pergunte (**Disparar N / Dividir em rodadas por módulo**).
4. **Descoberta:** despache os subagentes em paralelo com
   [`references/subagente-descoberta.md`](references/subagente-descoberta.md).
5. **Verificação:** para cada exemplo devolvido, confira com `sed -n '<linha>p' <arquivo>` que a
   linha mostra o que a variante descreve. Exemplo que não confere derruba a variante. Subagente
   sem resposta deixa as dimensões dele como "não medida" no relatório.
6. **Decisão por dimensão** (ver a seção).
7. **Relatório de desvios** no chat, por padrão: `arquivo:linha`, o que está e o que seria. Itens
   "muda contrato" separados e marcados. Pergunte o que entra (multiSelect, um item por padrão;
   **Other** para escolher arquivo a arquivo).
8. **Etapas,** uma por padrão (ou por módulo, se o padrão tocar mais de 10 arquivos):
   1. ponto de restauração (ver a seção);
   2. rode os testes que cobrem os arquivos da etapa. Falharam **antes** de mexer: não comece;
      mostre a falha e pergunte (**Pular / Seguir sem prova / Parar**);
   3. nenhum teste cobre: pergunte (**Pular / Seguir sem prova / Caracterizar com a
      sw-auto-test**). "Seguir sem prova" vai para o `state.md`;
   4. aplique: a ferramenta de [`references/refatoracoes-seguras.md`](references/refatoracoes-seguras.md)
      quando já estiver instalada; senão, edite. Projeto grande pode usar um subagente por etapa,
      com o padrão, os desvios da etapa e estas regras; confira o diff que ele produziu;
   5. rode os testes de novo. Falharam: restaure a etapa, mostre o erro e pergunte (**Tentar de
      outro jeito / Pular / Parar**). Três falhas seguidas param a rodada.
9. **Fechamento:**
   1. nova descoberta só nas dimensões tratadas, no escopo: os itens aprovados devem dar zero;
      pulados e recusados vão para pendentes;
   2. ofereça a `sw-code-review` no diff da rodada e a `sw-git-commit` com uma etapa por commit;
   3. mostre o que será gravado (ver "Arquivos gravados") e pergunte (**Gravar / Não gravar**);
   4. pergunte se adiciona a seção ao `AGENTS.md` e ao `CLAUDE.md`.

## Decisão por dimensão

| Variante dominante | O que fazer |
|---|---|
| ≥ 80% | candidato a padrão; confirme todos os candidatos numa pergunta só (multiSelect) |
| < 80% | conflito: recontagem (variante "recontagem" do prompt) e depois pergunte |
| nenhuma variante | proponha o idiomático (ver [`references/idiomatico.md`](references/idiomatico.md)) |

A pergunta de conflito mostra, por variante: contagem, um exemplo real `arquivo:linha` e qual é a
idiomática do framework. Opções: uma por variante, mais **Deixar sem padrão**.

**Idiomático:** use `references/idiomatico.md` como base. Com busca na web na sessão, confira a
documentação oficial da versão do manifesto e cite a fonte; sem web, marque "não conferido".

**Limites de complexidade:** função > 40 linhas e aninhamento > 3, ou o percentil 80 do projeto
quando for maior. Se 80% das funções têm até 60 linhas, o limite vira 60.

## Ponto de restauração

Antes de editar qualquer arquivo de uma etapa:

```bash
PONTO=${CLAUDE_SCRATCHPAD:-$(mktemp -d)}/sw-refactor/etapa-<n>
mkdir -p "$PONTO" && cp --parents <arquivos da etapa> "$PONTO"
```

Use a pasta temporária da sessão quando o ambiente oferecer uma; senão, `mktemp -d`. Para
restaurar, copie de volta **só** os arquivos dessa etapa (`cp -r "$PONTO"/. .`) e apague os
arquivos que a etapa criou. Nunca use `git checkout` nem `git stash`: eles levam junto as etapas
anteriores e as mudanças do usuário.

## Contrato externo

Desvio que toca o que sai do processo (símbolo exportado, rota, chave de JSON, status HTTP,
mensagem de erro, coluna) vem marcado **muda contrato**, com quem consome (grep pelo símbolo ou
pela chave). Só entra com pergunta própria (**Aplicar / Deixar como está**), mesmo que o padrão
já tenha sido aprovado.

## Arquivos gravados

Só no fechamento, com o "Gravar". Nomes e cabeçalhos em inglês; texto no idioma do projeto.

`docs/sw-refactor/patterns.md`, um bloco por padrão:

```markdown
## Error handling — services
- Rule: services raise DomainError; the API layer maps it to HTTP.
- Decided by: owner (2026-11-03)
- Evidence: 4 of 6 services
- Correct: app/services/orders.py:6
- Wrong: app/services/shipping.py:3
```

`docs/sw-refactor/state.md`:

```markdown
# sw-refactor state
- Last run: 2026-11-03
- Base commit: <hash>
- Final commit: <hash | refatoração não commitada>
- Scope: <projeto | diretório | arquivos>
- Touched files: <lista>
- Patterns applied: <lista>
- Pending deviations: <padrão: arquivo:linha — motivo (pulado | recusado | contrato)>
- Unproven steps: <etapa — motivo>
```

Seção para `AGENTS.md` e `CLAUDE.md` (arquivo inexistente: pergunte se cria cada um):

```markdown
## Code patterns
Follow docs/sw-refactor/patterns.md. Pending deviations: docs/sw-refactor/state.md.
```

O relatório de desvios não vira arquivo.

## Outras skills

Sempre oferta por `AskUserQuestion`, nunca automática. Não instalada: diga e siga.

| Momento | Skill | Pedido |
|---|---|---|
| 1ª rodada, se a descoberta achar arquivo ou função sem uso | `sw-dead-code-scan` | limpar antes de refatorar |
| Etapa sem teste, se o usuário escolher caracterizar | `sw-auto-test` | "Escreva um teste de caracterização para `<arquivo>`: fixe o comportamento atual, inclusive o estranho; não corrija bug e não altere o código." |
| Fechamento | `sw-code-review` | revisar o diff da rodada |
| Fechamento | `sw-git-commit` | uma etapa por commit |
````

- [x] **Step 2: conferir frontmatter e seções**

Rode: `cd ~/.claude/skills/sw-refactor && head -2 SKILL.md && grep -cE "^## (Regras|Fluxo|Decisão|Ponto|Contrato|Arquivos|Outras)" SKILL.md && grep -nE "scripts/|python3 " SKILL.md; echo "rc=$?"`
Esperado: `---` e `name: sw-refactor`; `7`; `rc=1` (grep vazio).

---

### Task 6: idiomático por linguagem

**Arquivos:**
- Criar: `sw-refactor/references/idiomatico.md`

**Depende de:** nada

- [x] **Step 1: escrever o arquivo**

```markdown
# Idiomático por linguagem e framework

Base para propor padrão quando o projeto não tem nenhum. Antes de propor, com busca na web,
confira a documentação oficial da versão do manifesto e cite `[doc: URL · versão · data]`. Sem
web, use esta tabela e diga "não conferido".

| Linguagem | Nomes | Erros | Validação | Config | Fonte a conferir |
|---|---|---|---|---|---|
| Python | snake_case; classes PascalCase; constantes MAIÚSCULAS (PEP 8) | exceções próprias por domínio; não devolver None como erro | na borda (API/CLI) | um objeto/módulo de settings, não `os.environ` espalhado | PEP 8; docs do framework |
| PHP | métodos camelCase; classes PascalCase (PSR-1/PSR-12) | exceções; não devolver false como erro | Form Request (Laravel) ou camada de validação do framework | `config()`/arquivo de config, não `env()` fora dele (Laravel) | PSR-1, PSR-12; docs do framework |
| JavaScript/TypeScript | camelCase; classes e tipos PascalCase | `throw` de `Error` ou subclasse; em async, rejeição | na borda, com schema (zod/joi/class-validator, o que o projeto usar) | um módulo de config que lê o env uma vez | docs do framework |
| Go | MixedCaps; exportado começa em maiúscula | `error` como último retorno; sem panic em fluxo normal | na borda | struct de config carregada no início | Effective Go |
| Java/Kotlin | camelCase; classes PascalCase | exceções; checked só quando o chamador pode reagir | Bean Validation na borda | `@ConfigurationProperties` (Spring) | docs do framework |
| Ruby | snake_case; classes CamelCase | exceções próprias | no model (Rails) | `Rails.configuration`/credentials | Ruby Style Guide; Rails Guides |

Linguagem fora da tabela: proponha só depois de conferir a documentação oficial; sem web, não
proponha idiomático e deixe a dimensão sem padrão.
```

- [x] **Step 2: conferir**

Rode: `grep -c "^| " ~/.claude/skills/sw-refactor/references/idiomatico.md`
Esperado: `7` (cabeçalho e 6 linguagens; o separador `|---` não conta).

---

### Task 7: refatorações seguras por ferramenta

**Arquivos:**
- Criar: `sw-refactor/references/refatoracoes-seguras.md`

**Depende de:** nada

- [x] **Step 1: escrever o arquivo**

```markdown
# Refatorações mecânicas por ferramenta

Use só se a ferramenta **já estiver instalada** no projeto (no manifesto, no lockfile ou no
PATH). Nunca instale sem perguntar. Rode antes em modo de simulação quando houver, mostre o
diff e só então aplique. O ponto de restauração vem antes, como em qualquer etapa.

| Linguagem | Ferramenta | Simular | Aplicar | Serve para |
|---|---|---|---|---|
| PHP | Rector | `vendor/bin/rector process <arq> --dry-run` | `vendor/bin/rector process <arq>` | regras de modernização e renome configuradas no `rector.php` do projeto |
| Python | ruff | `ruff check <arq> --diff` | `ruff check <arq> --fix` | correções que o ruff marca como seguras |
| JS/TS | ESLint | `npx eslint <arq>` | `npx eslint <arq> --fix` | regras com autofix da config do projeto |
| Go | gopls | `gopls rename -d <arq>:#<offset> <novo>` | `gopls rename -w <arq>:#<offset> <novo>` | renomear símbolo com todas as referências |
| Java | OpenRewrite | `mvn rewrite:dryRun` | `mvn rewrite:run` | receitas já declaradas no `pom.xml` |

Sem ferramenta, o agente edita. Renomear símbolo à mão exige grep do nome em código, strings,
configs e templates antes, porque reflexão e injeção de dependência não aparecem no import.
```

- [x] **Step 2: conferir**

Rode: `grep -c "^| " ~/.claude/skills/sw-refactor/references/refatoracoes-seguras.md`
Esperado: `6`.

---

### Task 8: ligar a sw-code-review

**Arquivos:**
- Alterar: `sw-code-review/SKILL.md` (Step 0, bloco `find` da seção 0a)
- Alterar: `sw-code-review/references/patterns.md` (seção 5m)

**Depende de:** nada

- [x] **Step 1: incluir o patterns.md na busca do Step 0**

No bloco `find` da seção **0a**, troque:

```
  -name "CONTRIBUTING.md" -o \
```

por:

```
  -name "CONTRIBUTING.md" -o \
  -path "*docs/sw-refactor/patterns.md" -o \
```

- [x] **Step 2: sugerir a sw-refactor na 5m**

No fim da seção **5m. Regras do Projeto**, depois do exemplo, acrescente:

```markdown
**Padrão repetido:** quando um achado de 5l ou 5m se repete em 3 ou mais arquivos, inclua no fim
da review uma linha: "O mesmo desvio aparece em N arquivos. Para alinhar o projeto inteiro, use a
`sw-refactor`." Só sugere: não chama a skill.
```

- [x] **Step 3: conferir**

Rode: `grep -n "sw-refactor" ~/.claude/skills/sw-code-review/SKILL.md ~/.claude/skills/sw-code-review/references/patterns.md`
Esperado: uma linha em cada arquivo.

---

### Task 9: validar a skill no fixture

**Arquivos:**
- Criar: `docs/specs/2026-11-03-sw-refactor-refatoracao-pelos-padroes-do-projeto/referencias/validacao-skill-test.md`

**Depende de:** Task 1, Task 5, Task 6, Task 7

- [x] **Step 1: checar as restrições estáticas**

Rode: `cd ~/.claude/skills/sw-refactor && grep -nE "scripts/|python3 " SKILL.md; echo "sem-script rc=$?"; awk '/1\. ponto de restauração/{p=NR} /aplique: a ferramenta/{e=NR} END{print (p && e && p<e) ? "ponto-antes ok" : "ponto-antes FALHA"}' SKILL.md`
Esperado: `sem-script rc=1` e `ponto-antes ok`.

- [x] **Step 2: rodar a sw-skill-test**

Invoque a skill `sw-skill-test` com:

```
Skill-alvo: ~/.claude/skills/sw-refactor
Use o fixture pronto em ~/.claude/skills/sw-refactor/tests/fixture (copie para um diretório
temporário; não plante outro) e o gabarito tests/fixture/GABARITO.md.
Nas etapas interativas, não pule: produza como artefato a lista de perguntas que seriam feitas,
e responda assim: aprovar todos os padrões ≥80%; no conflito PHP, escolher "validação no
controller"; em C1, "Deixar como está"; em trecho sem teste, "Pular" para payments e "Seguir
sem prova" para os demais; em R1, "Pular".
Artefatos: relatório de desvios, lista de perguntas, diff final e saída dos testes do fixture.
```

- [x] **Step 3: comparar com o gabarito**

| Item | Esperado |
|---|---|
| D1–D5, D7 | todos no relatório de desvios |
| D6 / P1 | conflito perguntado com contagem 6 × 5 |
| C1 / P2 | marcado "muda contrato", perguntado, não aplicado |
| A1 | `app/legacy_export.py` igual ao original |
| P3 | pergunta de trecho sem teste presente; `payments.py` igual ao original (pulado) |
| R1 / P4 | `shipping.py` restaurado igual ao original; a etapa de D3 permanece aplicada |
| testes | `python3 -m unittest` e `php tests/run.php` verdes no fim |

Rode, no diretório temporário usado: `diff -q app/services/shipping.py ~/.claude/skills/sw-refactor/tests/fixture/app/services/shipping.py && diff -q app/legacy_export.py ~/.claude/skills/sw-refactor/tests/fixture/app/legacy_export.py && python3 -m unittest discover -s tests -t . && php tests/run.php`
Esperado: sem saída dos `diff`; testes OK.

- [x] **Step 4: registrar a validação**

```markdown
# Validação pela sw-skill-test

| Item | Resultado |
|---|---|
| D1–D5, D7 | <x de 6> |
| P1 conflito | <ok | falhou> |
| C1 contrato | <ok | falhou> |
| A1 armadilha | <0 edições | n edições> |
| P3 sem teste | <ok | falhou> |
| R1 restauração | <ok | falhou> |
| Testes finais | <verdes | vermelhos> |
| Disparo | <acertos/total> |

Recomendações da sw-skill-test: <lista>
```

Item que falhou: ajuste o `SKILL.md`, registre em "Ajustes durante a execução" e repita os
steps 2 a 4.

---

### Task 10: publicar no repositório

**Arquivos:**
- Alterar: `CHANGELOG.md` (seção "Não publicado", "Adicionado")
- Criar: `plugins/sw-refactor/` (gerado pelo `make sync`)
- Alterar: `plugins/sw-code-review/` (gerado pelo `make sync`)

**Depende de:** Task 8, Task 9

- [x] **Step 1: sincronizar as duas skills**

O fixture em `tests/` vai junto para `plugins/sw-refactor/` de propósito: quem instala o plugin
pode repetir a validação. Ele não tem nome real nem caminho do home.

Rode: `cd /var/www/ai-marketplace && make sync SKILL=sw-refactor CATEGORY=development && make sync SKILL=sw-code-review BUMP=patch`
Esperado: duas linhas `✓ plugin.json, marketplace.json e README atualizados.`

- [x] **Step 2: registrar no CHANGELOG**

No topo de "### Adicionado" em "## [Não publicado]":

```markdown
- `sw-refactor` (v0.1.0): **skill nova.** Descobre os padrões do próprio projeto com subagentes,
  aponta os desvios e refatora em etapas com testes verdes antes e depois. A primeira rodada passa
  pelo projeto inteiro e grava `docs/sw-refactor/patterns.md` e `state.md`, com aprovação.
- `sw-code-review` (patch): lê `docs/sw-refactor/patterns.md` no Step 0 e sugere a `sw-refactor`
  quando um desvio se repete em 3 ou mais arquivos.
```

- [x] **Step 3: varrer o que vai para o repo público**

Rode: `cd /var/www/ai-marketplace && D=docs/specs/2026-11-03-sw-refactor-refatoracao-pelos-padroes-do-projeto && grep -rnE "/(home|Users)/" plugins/sw-refactor $D/spec.md $D/referencias; echo "home rc=$?"; [ -f .scan-denylist ] && grep -rniFf .scan-denylist plugins/sw-refactor $D; echo "denylist rc=$?"`
Esperado: `home rc=1` e `denylist rc=1`. A lista de nomes reais mora na `.scan-denylist`, fora do git,
para nunca ser escrita num arquivo versionado.

- [x] **Step 4: rodar o gate**

Rode: `cd /var/www/ai-marketplace && git add plugins/sw-refactor plugins/sw-code-review CHANGELOG.md README.md .claude-plugin/marketplace.json docs/specs/2026-11-03-sw-refactor-refatoracao-pelos-padroes-do-projeto docs/specs/README.md && make check`
Esperado: `✓ gate de segurança: nada sensível detectado`. Commit e push só no checkpoint, com o "sim" do dono.

## Ajustes durante a execução

- **2026-11-03** — Base da revisão final: 4aeebe414bcd9b913caa22be171608bb7cc5f6c8
- **2026-11-03** — Task 3 (spike da contagem): variantes e exemplos estáveis (42 de 42 linhas
  conferidas), mas a unidade de contagem variou (Request 5 × 10 no PHP) e a marca "muda contrato"
  foi usada em símbolo interno numa rodada. Por decisão do dono: o prompt de descoberta define a
  unidade (arquivo onde a decisão é tomada; auxiliar não conta) e restringe "muda contrato" ao que
  alguém fora do código vê; e a Task 5 passa a recontar toda dimensão abaixo de 80% antes de
  perguntar. O spike roda de novo com o prompt corrigido.
- **2026-11-03** — Task 4 (spike da caracterização): funcionou; sem mudança no plano.
- **2026-11-03** — o fixture gerou `get_taxe` em `taxes.py` (o loop tira o "s" final). Fica como
  está: a descoberta o aponta como desvio de nome, e ele entra no gabarito como D7.
- **2026-11-03** — Task 5: o ponto de restauração não usa mais `${CLAUDE_SCRATCHPAD:-...}`, uma
  variável que não foi confirmada; o texto manda usar a pasta temporária indicada para a sessão e,
  sem ela, `mktemp -d`.
- **2026-11-03** — Task 9: a 1ª rodada errou o D4 e expôs lacunas no texto; corrigidas no
  `SKILL.md` e no prompt (lista em `referencias/validacao-skill-test.md`) e a rodada foi repetida
  com sucesso. A regra "desvio em código sem chamador não é refatorado" foi escrita e retirada:
  no fixture ela tiraria o D5, e em projeto real erra com rota de framework.
- **2026-11-03** — revisões finais (juiz + sw-code-review em contexto vazio): 7 achados, todos
  corrigidos. Restauração com `tar` e caminhos relativos à raiz (com `cp --parents` e caminho
  absoluto ela não desfazia nada, e o comando não existe no macOS); remoção do auxiliar antes do
  teste final da etapa; critério de contrato alinhado ao prompt; spec com "Revisões do spec";
  índice regenerado; ESLint com `--fix-dry-run`; exceção de remoção citada na regra e pergunta do
  `AGENTS.md` só depois de "Gravar".
