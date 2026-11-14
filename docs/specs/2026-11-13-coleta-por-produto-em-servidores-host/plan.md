# Plano de implementação — Coleta por produto em servidores host

[spec.md](spec.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** cada componente descoberto num alvo `host` passa a ter estado, tempo no ar, reinícios e
memória, e MariaDB, MySQL, Postgres, Redis e Qdrant trazem os dados do produto a partir de um catálogo
TOML por produto, sem mudar código para medir um produto novo.

**Arquitetura:** o comando remoto deixa de ser só texto literal: `lib/vagas.py` monta **molde + vagas
validadas** antes do subprocesso, e `runner.run_ssh` ganha `vagas` e `entrada` (stdin, com
`stdin=DEVNULL` por padrão). A camada comum (`systemctl show` / `docker inspect`+`stats` / `ps`) vive em
`lib/leitura_servico.py` (puro) e é respondida pelo adaptador `ssh` existente. O específico de produto
mora em `references/produtos-host/<produto>.toml`, carregado por `lib/catalogo_produto.py`, convertido
por `extracao.documento` (formatos `tsv`, `json`, `chave_valor`) e respondido pelo adaptador novo
`produto_ssh` (prioridade 38). `perguntas_do_componente` decide o que cada componente recebe (só quem
tem `origem` ganha as comuns e as de catálogo), e `responder` e `cobertura` passam a usá-la juntos.

**Stack:** Python 3.11+ só com stdlib (`tomllib`, `subprocess`, `re`, `json`), pytest no venv da skill;
Docker local só no spike da Task 1.

**Caminhos:** relativos a `~/.claude/skills/sw-infra-audit/`, salvo os que começam por `plugins/`,
`docs/` ou `CHANGELOG.md`, que são do repositório `/var/www/ai-marketplace`. O lint aponta como
inexistentes, e é esperado: `CHANGELOG.md` e `plugins/sw-infra-audit/` (do repositório, Task 16) e
`scripts/lib/vagas.py` (criado na Task 3, alterado na Task 4). Testes:
`.venv/bin/python -m pytest -q <arquivos>` **a partir da raiz da skill** (ela não é repositório git, e
`exigir_pasta_protegida` usa o cwd), **nunca duas execuções ao mesmo tempo**: há testes de mutação que
reescrevem arquivo de código durante a suíte. Suíte inteira: `timeout 900 .venv/bin/python -m pytest -q`.
Lint: `plan_check.py <plan> --projeto ~/.claude/skills/sw-infra-audit`.

**Restrições verificáveis (do spec):**
| Restrição | Como o plano checa |
|---|---|
| 1. Nenhum argv de ssh contém a senha; senha marcada varrida no argv e no `report.json` | Task 4, step 1 (`test_senha_vai_pelo_stdin_e_nunca_pelo_argv`); Task 10, step 1 (adaptador manda pela entrada); Task 14, step 1 (ponta a ponta pelo `collect.main`, argv e `report.json`) |
| 2. O runner recusa o que não é molde do catálogo com vagas validadas; coleção com `;` ou espaço é pulada | Task 4, step 1 (12 recusas, subprocesso nunca chamado); Task 10, step 1 (`test_colecao_fora_do_formato_e_pulada_e_dita`) |
| 3. Produto novo é medido sem mudar `.py` | Task 10, step 5 (`tests/test_produto_novo_sem_codigo.py`: produto inventado só com `produtos.toml` e catálogo temporários) |
| 4. Componentes de alvo `docker` recebem exatamente as mesmas perguntas de antes | Task 8, step 1 (lista literal por papel e coleta de um alvo docker comparada) |
| 5. Toda regra nova tem remediação | Task 13, steps 4 e 5 (`tests/test_remediacao.py`, fitness que já existe) |

**Decisões tomadas neste plano** (o spec deixava em aberto ou o código pediu):

- **Processo sem vaga.** A leitura de quem é só processo usa `ps -e -o comm=,rss=,etimes=` literal e
  filtra o nome na skill, em vez de `ps -C {processo}`: some uma vaga (menos superfície) e processo
  ausente vira `servico.ativo = "parado"` sem depender do código de saída do `ps`.
- **Tempo no ar da unit** vem de `ActiveEnterTimestampMonotonic` contra `/proc/uptime` (os dois relógios
  são do servidor e dispensam `--timestamp=unix`, que o systemd antigo não tem). O do container vem de
  `State.StartedAt` contra o `--at` da rodada.
- **Pseudo-papel `servico`** para as quatro comuns: `test_perguntas` exige que o prefixo do id seja o
  papel, e `servico` não entra em `lib/papel.py` (nenhum componente *é* um serviço genérico). O teste
  passa a aceitar `perguntas.PAPEL_COMUM`.
- **`percentual_de` aceita `denominador_soma`.** A taxa de acerto do Redis é
  `hits / (hits + misses) × 100`; `razao` não multiplica por 100 e `percentual_de` só tinha um
  denominador. É uma opção da derivação que já existe, não uma linguagem nova.
- **`#` não é escapado no arquivo de opções.** O leitor do MySQL/MariaDB só corta comentário fora das
  aspas, e `\#` deixaria a barra dentro da senha. Escapam-se `\` e `"`. O spike (Task 1) confirma; se
  ele mostrar o contrário, a Task 9 troca o escape.
- **Cliente `mariadb`, não `mysql`, no catálogo do MariaDB**: o binário `mariadb` existe desde a 10.4 e o
  apelido `mysql` não é garantido nas versões novas. O spike registra o que a imagem 11 traz.
- **Erros do produto no catálogo** (`[[erro]]` com `contem` ou `codigo`, `modo` e `nao_publica`
  opcionais): é o que deixa "root sem socket", "Redis com senha" e "Qdrant com chave" virarem motivo
  claro sem código por produto.
- **`explica_a_falta`**: o `promql` (30) responde `banco.conexoes` de componente de host com "declare
  `metricas_url`", que venceria o motivo do `produto_ssh` (38). A marca faz o motivo do adaptador de
  produto vencer, e o `responder` a retira antes de gravar, como já faz com `nao_se_aplica`.
- **`leitura = "container"` em origem que não é `container:`** é aceita na leitura do `alvos.toml` (o
  spec quer `sem dados` com motivo na coleta), mas o `configurar.py leitura` recusa gravá-la.

**Lições da parte A já embutidas:** suíte inteira ao fim de toda task que toca perguntas, regras ou
adaptadores, com os testes estáticos que quebram previstos no step (`test_nan_nunca_chega_ao_report`:
nenhum `float()` novo, número passa por `extracao._numero`; `test_toda_pergunta_declarada_tem_alguem_que_a_responda`:
soma `ssh.RESPONDE` e `produto_ssh.respondidas()`; `test_regras`: produtor novo nas duas somas;
`test_seguranca_batch6`: nenhum arquivo novo pode ter a palavra `environ` nem `getenv`, nem em comentário;
`test_catalogo_host`: a chave `processos` entra em `CHAVES`; as contagens de `do_papel` **não mudam**,
porque nada novo entra em `ORDEM`). Helpers de teste usam dict literal `{**base, **trocas}`. Testes de
recusa casam com a mensagem nova específica, nunca com uma palavra que a mensagem antiga
("campo que não existe: …") também tinha.

---

## Fase 0 — o risco primeiro

### Task 1: spike — senha pelo stdin num MariaDB local

**Arquivos:**
- Criar: `tests/fixtures/produto/mariadb/` (`status.txt`, `variaveis.txt`, `tamanho.txt`, `tamanho_por_banco.txt`)
- Criar: `docs/specs/2026-11-13-coleta-por-produto-em-servidores-host/referencias/spike-mysql-stdin.md`

**Depende de:** nada

**Por que primeiro:** a suposição "`--defaults-extra-file=/dev/stdin` funciona com stdin redirecionado"
decide se o modo `senha` existe nesta versão (Tasks 9, 10, 11, 12 e 14 dependem dele).

**Deu certo se:** o arquivo de opções com aspas e barra escapadas (variante A) devolve `1`, tanto
chamando o cliente direto quanto por `sh -c '…'` (que imita o shell de login que o ssh usa do outro
lado). **Se não:**
- a variante B (com `\#`) funciona e a A não → na Task 9, `_escapar` passa a trocar também `#` por `\#`
  e o teste `test_entrada_e_o_client_com_aspas_e_barra_escapadas` espera `c\\#d`; registre em "Ajustes";
- nenhuma funciona → **o modo senha sai desta versão**: a Task 9 é executada assim mesmo (não é
  chamada sem `senha`); na Task 11 os catálogos `mariadb.toml` e `mysql.toml` **não** declaram a chave
  `senha` em `[cliente]`, e `test_senha_so_no_mariadb_e_no_mysql` espera `set()`; o adaptador já
  responde "não tem cliente para leitura senha; leitura com senha fica para uma próxima versão neste
  produto" e o `configurar.py leitura --modo senha` já recusa; na Task 14 o componente usa
  `leitura = "socket"` e a asserção "alguma entrada contém a marca" sai; SKILL.md e CHANGELOG dizem
  que senha fica para depois. Registre em "Ajustes".

Spike descartável: o container é apagado; ficam só as saídas (dados fictícios de um banco vazio) e o
relatório. Docker é **local**, nunca servidor do dono.

- [x] **Step 1: conferir o Docker local**

Rode: `docker version --format '{{.Server.Version}}'; echo "rc=$?"`
Esperado: uma versão e `rc=0`. Com `rc` diferente de 0, grave o relatório do Step 7 com
"Veredito: **não executado** (Docker indisponível nesta máquina)", deixe as fixtures de fora e siga para
a Task 2 — o modo senha segue no plano, marcado como não verificado no CHANGELOG da Task 16.

- [x] **Step 2: subir um MariaDB 11 descartável**

```bash
docker run --rm -d --name spike-mariadb -e MARIADB_ROOT_PASSWORD=spike-raiz-123 mariadb:11
timeout 120 sh -c 'until docker exec spike-mariadb mariadb-admin ping -uroot -pspike-raiz-123 --silent >/dev/null 2>&1; do sleep 2; done'; echo "pronto rc=$?"
```

Esperado: `pronto rc=0`. (Se o ambiente bloquear `sleep` em primeiro plano, rode o laço `until` em
segundo plano e espere o fim dele antes do Step 3.)

- [x] **Step 3: criar um usuário de leitura com senha difícil**

A senha é `a"b\c#d`: aspas, barra e `#`, os três caracteres que o arquivo de opções trata de forma
especial.

```bash
docker exec -i spike-mariadb mariadb -uroot -pspike-raiz-123 <<'SQL'
CREATE USER 'leitor'@'localhost' IDENTIFIED BY 'a"b\\c#d';
GRANT SELECT, PROCESS, REPLICATION CLIENT ON *.* TO 'leitor'@'localhost';
SQL
echo "usuario rc=$?"
```

Esperado: `usuario rc=0`.

- [x] **Step 4: senha pelo stdin — as quatro sondas**

```bash
printf '%s\n' '[client]' 'user="leitor"' 'password="a\"b\\c#d"' \
  | docker exec -i spike-mariadb mariadb --defaults-extra-file=/dev/stdin -N -B -e "SELECT 1"; echo "A direto rc=$?"
printf '%s\n' '[client]' 'user="leitor"' 'password="a\"b\\c#d"' \
  | docker exec -i spike-mariadb sh -c 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "SELECT 1"'; echo "A via shell rc=$?"
printf '%s\n' '[client]' 'user="leitor"' 'password="a\"b\\c\#d"' \
  | docker exec -i spike-mariadb mariadb --defaults-extra-file=/dev/stdin -N -B -e "SELECT 1"; echo "B rc=$?"
docker exec spike-mariadb sh -c 'command -v mariadb; command -v mysql'; echo "binarios rc=$?"
```

Esperado: `1` e `A direto rc=0`; `1` e `A via shell rc=0`; `B` com `ERROR 1045` e `rc=1` (informativo);
o caminho do `mariadb` e, talvez, nenhum `mysql` (anote).

- [x] **Step 5: socket do root e as leituras do catálogo**

```bash
S=/tmp/claude-1000/spike-mysql && mkdir -p "$S"
docker exec spike-mariadb mariadb -N -B -e "SELECT 1"; echo "socket root rc=$?"
R="docker exec spike-mariadb mariadb -uroot -pspike-raiz-123 -N -B -e"
$R "SHOW GLOBAL STATUS" > "$S/status.txt"; echo "status rc=$?"
$R "SHOW GLOBAL VARIABLES" > "$S/variaveis.txt"; echo "variaveis rc=$?"
$R "SELECT SUM(data_length + index_length) FROM information_schema.tables" > "$S/tamanho.txt"; echo "tamanho rc=$?"
$R "SELECT table_schema, SUM(data_length + index_length) FROM information_schema.tables GROUP BY table_schema" > "$S/tamanho_por_banco.txt"; echo "por banco rc=$?"
$R "SHOW BINARY LOGS" > "$S/binlog.txt" 2>&1; echo "binlog rc=$?"
echo "linhas: $(wc -l < "$S/status.txt") com TAB: $(grep -c $'\t' "$S/status.txt")"
grep -E '^(Threads_connected|Slow_queries)'$'\t' "$S/status.txt"; grep -E '^max_connections'$'\t' "$S/variaveis.txt"
cat "$S/binlog.txt"
```

Esperado: `status`, `variaveis`, `tamanho` e `por banco` com `rc=0`; o número de linhas de
`status.txt` igual ao número de linhas com TAB; as três chaves presentes; `binlog` com
`You are not using binary logging` (texto exato que vai para o `[[erro]]` da Task 11). O
`socket root` pode falhar no container (o root da imagem tem senha): anote, não decide nada — o
servidor do dono é que responde isso na primeira auditoria.

- [x] **Step 6: gravar as fixtures e apagar o container**

```bash
S=/tmp/claude-1000/spike-mysql; F=~/.claude/skills/sw-infra-audit/tests/fixtures/produto/mariadb
mkdir -p "$F" && cp "$S/status.txt" "$S/variaveis.txt" "$S/tamanho.txt" "$S/tamanho_por_banco.txt" "$F/"
docker rm -f spike-mariadb
grep -rnE "/(home|Users)/" "$F"; echo "home rc=$?"
cd /var/www/ai-marketplace && [ -f .scan-denylist ] && grep -rniFf .scan-denylist "$F"; echo "denylist rc=$?"
```

Esperado: `home rc=1` e `denylist rc=1` (é um banco vazio de container; nada do dono).

- [x] **Step 7: registrar o spike**

Grave `docs/specs/2026-11-13-coleta-por-produto-em-servidores-host/referencias/spike-mysql-stdin.md`:

```markdown
# Spike: senha do MariaDB pelo stdin

Executado em <data>, com `mariadb:11` num Docker local (container descartável, apagado no fim).

| Sonda | Resultado | Observação |
|---|---|---|
| A direto: `"` e `\` escapados, `#` literal | | |
| A via `sh -c` (como o ssh entrega) | | |
| B: também `\#` | | |
| `command -v mariadb` / `mysql` | | |
| root pelo socket, sem senha | | não decide: o root da imagem tem senha |
| `SHOW GLOBAL STATUS` separado por TAB | | |
| texto do binlog desligado | | |

Veredito: <modo senha confirmado | muda o plano assim: …>.
```

---

## Fase 1 — a base: formatos, vagas, runner

### Task 2: formatos de saída no `extracao` e `percentual_de` com soma

**Arquivos:**
- Alterar: `scripts/lib/extracao.py` (import, `derivar`, `_OBRIGATORIAS`, `_validar_derivacao`; função nova `documento`)
- Teste: `tests/test_extracao_formatos.py`

**Depende de:** nada

**Contrato que esta task publica:** `extracao.FORMATOS = ("tsv", "json", "chave_valor")`;
`extracao.documento(texto, formato, colunas=None, separador=None) -> dict | list | None` (`tsv` vira
`{"linhas": [{coluna: texto}]}`; `None` = saída fora do formato; formato desconhecido levanta
`ExtracaoInvalida`); derivação `percentual_de` com `denominador` **ou** `denominador_soma`.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_extracao_formatos.py
import pytest

from lib.extracao import ExtracaoInvalida, documento, extrair, validar_declaracao

STATUS = "Aborted_clients\t3\nThreads_connected\t12\nSlow_queries\t7\n"
VARIAVEIS = "max_connections\t151\nversion\t11.4.2-MariaDB\n"
INFO = ("# Server\r\nredis_version:7.2.4\r\n\r\n# Memory\r\nused_memory:1048576\r\n"
        "# Stats\r\nkeyspace_hits:90\r\nkeyspace_misses:10\r\nevicted_keys:0\r\n")


def test_chave_valor_le_a_saida_do_mysql():
    assert documento(STATUS, "chave_valor") == {
        "Aborted_clients": "3", "Threads_connected": "12", "Slow_queries": "7"}


def test_chave_valor_do_redis_usa_dois_pontos_tira_o_cr_e_pula_secao():
    doc = documento(INFO, "chave_valor", separador=":")
    assert doc["used_memory"] == "1048576" and doc["keyspace_misses"] == "10"
    assert "# Server" not in doc and doc["redis_version"] == "7.2.4"


def test_tsv_vira_linhas_com_as_colunas_declaradas():
    assert documento("app\t2048\nlogs\tNULL\n", "tsv", colunas=["nome", "bytes"]) == {
        "linhas": [{"nome": "app", "bytes": "2048"}, {"nome": "logs", "bytes": "NULL"}]}


def test_tsv_com_campo_a_menos_e_saida_que_nao_se_entendeu():
    assert documento("so-um-campo\n", "tsv", colunas=["nome", "bytes"]) is None


def test_tsv_com_coluna_a_mais_fica_com_as_declaradas():
    assert documento("binlog.000001\t4096\tNo\n", "tsv", colunas=["nome", "bytes"]) == {
        "linhas": [{"nome": "binlog.000001", "bytes": "4096"}]}


def test_tsv_com_o_separador_do_psql():
    assert documento("12|100\n", "tsv", colunas=["usadas", "limite"], separador="|") == {
        "linhas": [{"usadas": "12", "limite": "100"}]}


def test_json_invalido_e_chave_valor_sem_par_viram_none():
    assert documento("<html>", "json") is None
    assert documento("NOAUTH Authentication required.", "chave_valor", separador=":") is None


def test_formato_desconhecido_e_recusado():
    with pytest.raises(ExtracaoInvalida, match="formato 'xml' não existe"):
        documento("x", "xml")


def test_escalar_de_tsv_aponta_para_a_primeira_linha():
    doc = documento("734003200\n", "tsv", colunas=["valor"])
    assert extrair(doc, {"campos": {"valor": "/linhas/0/valor"},
                         "transformar": {"valor": "bytes"}}) == {"valor": 734003200}


def test_uso_de_conexoes_junta_status_e_variaveis():
    doc = {**documento(STATUS, "chave_valor"), **documento(VARIAVEIS, "chave_valor")}
    declarada = {"derivar": {"valor": {"tipo": "percentual_de", "numerador": "/Threads_connected",
                                       "denominador": "/max_connections"}}}
    assert extrair(doc, declarada) == {"valor": 7.95}


def test_percentual_de_aceita_denominador_somado():
    doc = documento(INFO, "chave_valor", separador=":")
    declarada = {"derivar": {"valor": {"tipo": "percentual_de", "numerador": "/keyspace_hits",
                                       "denominador_soma": ["/keyspace_hits", "/keyspace_misses"]}}}
    assert extrair(doc, declarada) == {"valor": 90.0}


def test_percentual_sem_leitura_nenhuma_nao_e_zero():
    declarada = {"derivar": {"valor": {"tipo": "percentual_de", "numerador": "/h",
                                       "denominador_soma": ["/h", "/m"]}}}
    assert extrair({"h": "0", "m": "0"}, declarada) == {"valor": None}


def test_percentual_com_os_dois_denominadores_e_recusado():
    with pytest.raises(ExtracaoInvalida, match="um dos dois"):
        validar_declaracao({"derivar": {"v": {"tipo": "percentual_de", "numerador": "/a",
                                              "denominador": "/b", "denominador_soma": ["/c"]}}})
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_extracao_formatos.py`
Esperado: FALHA na coleta com `ImportError: cannot import name 'documento' from 'lib.extracao'`.

- [x] **Step 3: escrever o mínimo que faz passar**

Em `scripts/lib/extracao.py`, troque `import math` por:

```python
import json
import math
```

Em `derivar`, troque o bloco

```python
    if tipo == "razao":
        caminhos = [declarada["numerador"], *declarada["denominador_soma"]]
    else:                                   # percentual_de
        caminhos = [declarada["numerador"], declarada["denominador"]]
```

por

```python
    if tipo == "razao" or "denominador_soma" in declarada:
        # `percentual_de` sobre uma soma é a taxa de acerto do Redis: hits / (hits + misses)
        caminhos = [declarada["numerador"], *declarada["denominador_soma"]]
    else:                                   # percentual_de sobre um denominador só
        caminhos = [declarada["numerador"], declarada["denominador"]]
```

Troque a linha `"percentual_de": ("numerador", "denominador"),` de `_OBRIGATORIAS` por
`"percentual_de": ("numerador",),` e, no fim de `_validar_derivacao` (depois do laço de `_LISTAS`),
acrescente:

```python
    if tipo == "percentual_de":
        presentes = [c for c in ("denominador", "denominador_soma") if c in declarada]
        if len(presentes) != 1:
            raise ExtracaoInvalida(
                f"a derivação {nome!r} é do tipo 'percentual_de' e declara `denominador` ou "
                f"`denominador_soma` — um dos dois")
        if presentes == ["denominador_soma"] and (
                not isinstance(declarada["denominador_soma"], list)
                or not declarada["denominador_soma"]):
            raise ExtracaoInvalida(
                f"{nome!r}: 'denominador_soma' precisa ser uma lista de ponteiros não vazia")
```

No fim do arquivo:

```python
FORMATOS = ("tsv", "json", "chave_valor")


def documento(texto, formato, colunas=None, separador=None):
    """A saída de um cliente de produto como documento para `extrair`. None = fora do formato.

    `tsv` vira `{"linhas": [{coluna: texto}]}` — objeto, e não lista, porque `extrair` sem `lista`
    lê um objeto: o escalar aponta para `/linhas/0/<coluna>`. Linha com menos campos que `colunas` é
    saída que não se entendeu, e a leitura inteira vira None; campo a mais (coluna nova numa versão
    do produto) fica de fora. `chave_valor` junta `chave<separador>valor`, ignorando linha vazia,
    seção (`# Memory`) e linha sem separador. `json` é o JSON da saída. Nada aqui converte número:
    quem converte é `transformar`, que já filtra NaN.
    """
    if formato not in FORMATOS:
        raise ExtracaoInvalida(f"formato {formato!r} não existe; os permitidos são "
                               f"{', '.join(FORMATOS)}")
    texto = texto if isinstance(texto, str) else ""
    if formato == "json":
        try:
            return json.loads(texto)
        except ValueError:
            return None
    sep = separador or "\t"
    linhas = [linha.rstrip("\r") for linha in texto.splitlines() if linha.strip()]
    if formato == "chave_valor":
        pares = {}
        for linha in linhas:
            if linha.lstrip().startswith("#") or sep not in linha:
                continue
            chave, _, valor = linha.partition(sep)
            pares[chave.strip()] = valor.strip()
        return pares or None
    if not colunas:
        raise ExtracaoInvalida("formato tsv sem `colunas`")
    saida = []
    for linha in linhas:
        campos = linha.split(sep)
        if len(campos) < len(colunas):
            return None
        saida.append({coluna: campo.strip() for coluna, campo in zip(colunas, campos)})
    return {"linhas": saida}
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_extracao_formatos.py tests/test_extracao.py tests/test_extracao_declaracao.py tests/test_extracao_derivacoes.py tests/test_nan_nunca_chega_ao_report.py`
Esperado: PASSA (o caso antigo `({"tipo": "percentual_de", "numerador": "/a"}, "denominador")` continua
casando com a mensagem nova, que contém "denominador").

---

### Task 3: vagas (validadores) e o carregador de catálogo de produto

**Arquivos:**
- Criar: `scripts/lib/vagas.py`
- Criar: `scripts/lib/catalogo_produto.py`
- Criar: `tests/apoio_produto.py`
- Teste: `tests/test_vagas.py`, `tests/test_catalogo_produto.py`

**Depende de:** Task 2

**Contrato que esta task publica:** `vagas.VAGA` (regex), `vagas.nomes(texto) -> set[str]`,
`vagas.NOME_DE_ORIGEM`, `vagas.COLECAO`, `vagas.PASTA`, `vagas.SQL_PROIBIDOS`,
`vagas.pasta_valida(valor) -> bool`, `vagas.sql_valido(valor) -> bool`, `vagas.VagaInvalida`;
`catalogo_produto.PASTA`, `catalogo_produto.MODOS = ("socket", "senha", "container")`,
`catalogo_produto.CatalogoInvalido`, `catalogo_produto.carregar_arquivo(caminho) -> dict`
(`{"produto", "porta_padrao", "cliente": {modo: molde}, "erro": [dict], "pergunta": [{"id", "sql":
list[str], "formato", "colunas", "separador", "enumerar", "extracao"}]}`),
`catalogo_produto.do_produto(nome, pasta=None) -> dict | None`, `catalogo_produto.todos(pasta=None) ->
list[dict]`; `tests/apoio_produto.MARIADB`, `QDRANT`, `PERGUNTA_DE_LISTA`,
`gravar(tmp_path, monkeypatch, **catalogos) -> Path`.

- [x] **Step 1: escrever o apoio e os testes que falham**

```python
# tests/apoio_produto.py
"""Catálogos de produto de mentira numa pasta temporária.

Os testes não dependem dos catálogos de verdade de `references/produtos-host/` (Task 11): `gravar`
aponta o carregador para a pasta do teste e registra uma pergunta de LISTA temporária, para o caminho
de `enumerar` ter o que responder sem amarrar o teste a uma pergunta real.
"""
from lib import catalogo_produto, perguntas

PERGUNTA_DE_LISTA = "busca.teste_colecoes"

MARIADB = """produto = "mariadb"

[cliente]
socket = 'mariadb -N -B -e "{sql}"'
senha = 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
container = 'docker exec {container} mariadb -N -B -e "{sql}"'

[[erro]]
contem = "ERROR 1698"
motivo = 'o root não entra pelo socket: declare leitura = "senha" com um usuário de leitura'

[[erro]]
contem = "ERROR 1045"
modo = "senha"
motivo = "o banco recusou o usuário e a senha declarados"

[[erro]]
contem = "You are not using binary logging"
motivo = "o binlog está desligado neste servidor"
nao_publica = true

[[pergunta]]
id = "banco.conexoes"
sql = "SHOW GLOBAL STATUS"
formato = "chave_valor"
campos = { valor = "/Threads_connected" }
transformar = { valor = "inteiro" }

[[pergunta]]
id = "banco.tamanho"
sql = "SELECT SUM(data_length + index_length) FROM information_schema.tables"
formato = "tsv"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }
transformar = { valor = "bytes" }
"""

QDRANT = """produto = "qdrant"
porta_padrao = 6333

[cliente]
socket = 'curl -s -f -m 5 "http://127.0.0.1:{porta}{sql}"'

[[erro]]
codigo = 22
motivo = "o Qdrant recusou a leitura (pede chave de API?)"

[[pergunta]]
id = "busca.teste_colecoes"
formato = "json"
enumerar = { sql = "/collections", lista = "/result/collections", campo = "name" }
sql = "/collections/{colecao}"
lista = "/itens"
campos = { nome = "/nome", pontos = "/resposta/result/points_count" }
transformar = { nome = "texto", pontos = "inteiro" }
ordenar_por = "pontos"
desempate = "nome"
"""


def gravar(tmp_path, monkeypatch, **catalogos):
    """Grava `<produto>.toml` numa pasta temporária e aponta o carregador para ela."""
    pasta = tmp_path / "produtos-host"
    pasta.mkdir(exist_ok=True)
    for produto, texto in catalogos.items():
        (pasta / f"{produto}.toml").write_text(texto, encoding="utf-8")
    monkeypatch.setattr(catalogo_produto, "PASTA", pasta)
    monkeypatch.setitem(perguntas.PERGUNTAS, PERGUNTA_DE_LISTA, {
        "id": PERGUNTA_DE_LISTA, "papel": "busca", "titulo": "Coleções de teste", "forma": "lista",
        "unidade": "pontos", "limiar": None, "desempate": "nome", "faixa": None, "opcional": True,
        "por_ultimo": False})
    return pasta
```

```python
# tests/test_vagas.py
import pytest

from lib import vagas


def test_vaga_e_nome_entre_uma_chave_e_o_formato_do_docker_nao_e():
    assert vagas.nomes("docker inspect --format '{{json .State}}' {container}") == {"container"}
    assert vagas.nomes('curl -s "http://127.0.0.1:{porta}{sql}"') == {"porta", "sql"}
    assert vagas.nomes("id -un") == set()


@pytest.mark.parametrize("pasta,aceita", [
    ("/var/backups/mysql", True), ("/srv/dump_2026.d", True), ("var/backups", False),
    ("/var/../etc", False), ("/var/back ups", False), ("/var/$HOME", False),
    ("/var/backups;reboot", False), ("/" + "a" * 300, False), (None, False)])
def test_pasta_de_backup_e_absoluta_e_nao_sobe_diretorio(pasta, aceita):
    assert vagas.pasta_valida(pasta) is aceita


@pytest.mark.parametrize("sql", ['SELECT "a"', "SELECT $HOME", "SELECT `id`", "SELECT 1 \\ 2",
                                 "SELECT 1 % 2", "SELECT 1 < 2", "SELECT 1 > 2",
                                 "SELECT 1\nSELECT 2", "", "   "])
def test_consulta_com_caractere_que_o_shell_interpreta_e_recusada(sql):
    assert vagas.sql_valido(sql) is False


def test_consulta_comum_e_aceita():
    assert vagas.sql_valido("SELECT table_schema, SUM(data_length + index_length) FROM "
                            "information_schema.tables GROUP BY table_schema") is True
    assert vagas.sql_valido("SELECT count(*), current_setting('max_connections') "
                            "FROM pg_stat_activity") is True
```

```python
# tests/test_catalogo_produto.py
import pytest

from apoio_produto import MARIADB, QDRANT, gravar
from lib import catalogo_produto as cp

CLIENTE = """[cliente]
socket = 'mariadb -N -B -e "{sql}"'
"""
PERGUNTA = """[[pergunta]]
id = "banco.conexoes"
sql = {sql}
formato = "chave_valor"
campos = {{ valor = "/Threads_connected" }}
transformar = {{ valor = "inteiro" }}
"""


def _arquivo(tmp_path, cliente=CLIENTE, sql='"SHOW GLOBAL STATUS"', produto="mariadb", nome=None,
             pergunta=None):
    caminho = tmp_path / f"{nome or produto}.toml"
    corpo = pergunta if pergunta is not None else PERGUNTA.format(sql=sql)
    caminho.write_text(f'produto = "{produto}"\n{cliente}{corpo}', encoding="utf-8")
    return caminho


def test_catalogo_carrega_com_a_extracao_separada(tmp_path, monkeypatch):
    pasta = gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    catalogo = cp.carregar_arquivo(pasta / "mariadb.toml")
    conexoes = catalogo["pergunta"][0]
    assert conexoes["sql"] == ["SHOW GLOBAL STATUS"] and conexoes["formato"] == "chave_valor"
    assert conexoes["extracao"] == {"campos": {"valor": "/Threads_connected"},
                                    "transformar": {"valor": "inteiro"}}
    assert set(catalogo["cliente"]) == {"socket", "senha", "container"}


def test_enumerar_carrega_com_json_e_vaga_colecao(tmp_path, monkeypatch):
    pasta = gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    pergunta = cp.carregar_arquivo(pasta / "qdrant.toml")["pergunta"][0]
    assert pergunta["enumerar"] == {"sql": "/collections", "lista": "/result/collections",
                                    "campo": "name"}


@pytest.mark.parametrize("sql", ["'SELECT $HOME'", "'SELECT `id`'", "'SELECT 1 % 2'",
                                 "'SELECT 1 > 0'", "'SELECT 1 < 0'", "'SELECT \"a\"'",
                                 "'SELECT \\N'", '"SELECT 1\\nSELECT 2"'])
def test_consulta_com_caractere_proibido_e_recusada(tmp_path, sql):
    with pytest.raises(cp.CatalogoInvalido, match="caractere proibido"):
        cp.carregar_arquivo(_arquivo(tmp_path, sql=sql))


def test_vaga_sql_fora_das_aspas_e_recusada(tmp_path):
    cliente = "[cliente]\nsocket = 'redis-cli {sql}'\n"
    with pytest.raises(cp.CatalogoInvalido, match="dentro de aspas duplas"):
        cp.carregar_arquivo(_arquivo(tmp_path, cliente=cliente))


def test_vaga_container_fora_do_modo_container_e_recusada(tmp_path):
    cliente = "[cliente]\nsocket = 'docker exec {container} mariadb -e \"{sql}\"'\n"
    with pytest.raises(cp.CatalogoInvalido, match="que este modo não preenche"):
        cp.carregar_arquivo(_arquivo(tmp_path, cliente=cliente))


def test_cliente_com_encadeamento_e_recusado(tmp_path):
    cliente = "[cliente]\nsocket = 'mariadb -e \"{sql}\" | cat'\n"
    with pytest.raises(cp.CatalogoInvalido, match="cliente 'socket' tem"):
        cp.carregar_arquivo(_arquivo(tmp_path, cliente=cliente))


def test_modo_desconhecido_e_recusado(tmp_path):
    cliente = "[cliente]\nsudo = 'mariadb -e \"{sql}\"'\n"
    with pytest.raises(cp.CatalogoInvalido, match="modo de leitura 'sudo' não existe"):
        cp.carregar_arquivo(_arquivo(tmp_path, cliente=cliente))


def test_pergunta_fora_do_registro_e_recusada(tmp_path):
    pergunta = PERGUNTA.format(sql='"SHOW GLOBAL STATUS"').replace("banco.conexoes", "banco.inventada")
    with pytest.raises(cp.CatalogoInvalido, match="não existe no registro"):
        cp.carregar_arquivo(_arquivo(tmp_path, pergunta=pergunta))


def test_escalar_sem_campo_valor_e_recusado(tmp_path):
    pergunta = PERGUNTA.format(sql='"SHOW GLOBAL STATUS"').replace("{ valor", "{ total")
    with pytest.raises(cp.CatalogoInvalido, match="é escalar"):
        cp.carregar_arquivo(_arquivo(tmp_path, pergunta=pergunta))


def test_varias_consultas_so_em_chave_valor(tmp_path):
    pergunta = ('[[pergunta]]\nid = "banco.tamanho"\nsql = ["SELECT 1", "SELECT 2"]\n'
                'formato = "tsv"\ncolunas = ["valor"]\ncampos = { valor = "/linhas/0/valor" }\n')
    with pytest.raises(cp.CatalogoInvalido, match="só `chave_valor` sabe juntar"):
        cp.carregar_arquivo(_arquivo(tmp_path, pergunta=pergunta))


def test_produto_fora_de_produtos_toml_e_recusado(tmp_path):
    with pytest.raises(cp.CatalogoInvalido, match="não está em references/produtos.toml"):
        cp.carregar_arquivo(_arquivo(tmp_path, produto="inventado"))


def test_nome_do_arquivo_precisa_ser_o_produto(tmp_path):
    with pytest.raises(cp.CatalogoInvalido, match="precisa ser o nome do arquivo"):
        cp.carregar_arquivo(_arquivo(tmp_path, produto="mysql", nome="mariadb"))


def test_enumerar_sem_vaga_colecao_e_recusado(tmp_path, monkeypatch):
    texto = QDRANT.replace('sql = "/collections/{colecao}"', 'sql = "/collections/docs"')
    pasta = gravar(tmp_path, monkeypatch, qdrant=texto)
    with pytest.raises(cp.CatalogoInvalido, match="usa a vaga {colecao}"):
        cp.carregar_arquivo(pasta / "qdrant.toml")


def test_do_produto_sem_arquivo_ou_com_nome_estranho_e_none(tmp_path):
    assert cp.do_produto("mongo", pasta=tmp_path) is None
    assert cp.do_produto("../etc/passwd", pasta=tmp_path) is None
    assert cp.do_produto(None, pasta=tmp_path) is None


def test_todos_le_a_pasta_inteira_em_ordem(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT, mariadb=MARIADB)
    assert [c["produto"] for c in cp.todos()] == ["mariadb", "qdrant"]
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_vagas.py tests/test_catalogo_produto.py`
Esperado: FALHA na coleta com `ImportError: cannot import name 'vagas' from 'lib'` (e o mesmo para
`catalogo_produto`).

- [x] **Step 3: escrever os dois módulos**

```python
# scripts/lib/vagas.py
"""As vagas de um comando remoto: o único lugar onde valor variável entra num comando de host.

A parte A proibia vaga: o comando era o texto do catálogo, e o runner comparava texto com texto.
Componente de host precisa de alvo variável (`systemctl show <unit>`), então o comando passou a ser
MOLDE + VAGAS, cada vaga com o seu validador — no padrão do `forma_aceita` do `catalogo_exec`.
Nenhuma mensagem daqui repete o valor recusado: ele veio de um servidor e pode ser qualquer coisa.
"""
import re

# `{nome}` com UMA chave de cada lado: `{{.Names}}` e `{{json .State}}` (formato do docker) não são vaga.
VAGA = re.compile(r"(?<!\{)\{([a-z_]+)\}(?!\})")
# o mesmo alfabeto do que vem depois de `tipo:` em `alvos.ORIGEM`; começa por letra ou número, então
# nunca vira opção do comando
NOME_DE_ORIGEM = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@:-]{0,127}")
COLECAO = re.compile(r"[A-Za-z0-9_-]{1,64}")
PASTA = re.compile(r"/[A-Za-z0-9._/-]{0,254}")
# Dentro de aspas duplas o shell ainda interpreta `$`, crase e `\`, e `"` fecharia as aspas. `%`, `<`
# e `>` ficam de fora como no resto dos catálogos: uma leitura não precisa deles.
SQL_PROIBIDOS = frozenset('"$`\\%<>\n\r')


class VagaInvalida(Exception):
    """Molde ou valor de vaga que a skill se recusa a montar."""


def nomes(texto):
    return set(VAGA.findall(texto or ""))


def pasta_valida(valor):
    return (isinstance(valor, str) and bool(PASTA.fullmatch(valor))
            and ".." not in valor.split("/"))


def sql_valido(valor):
    return isinstance(valor, str) and bool(valor.strip()) and not (SQL_PROIBIDOS & set(valor))
```

```python
# scripts/lib/catalogo_produto.py
"""Catálogos de produto para servidores host: `references/produtos-host/<produto>.toml`.

Produto novo é medido escrevendo um arquivo, sem mudar código: o cliente do produto por modo de
leitura, as consultas literais e como a saída vira resposta — pela linguagem fechada de
`lib/extracao.py`, nunca por expressão. O carregador recusa o que não é leitura fixa: vaga fora do
lugar, consulta com caractere que o shell interpretaria, pergunta que não existe no registro.
"""
import re
import tomllib
from pathlib import Path

from lib import catalogo_host, produtos
from lib.extracao import FORMATOS, ExtracaoInvalida, ponteiro, validar_declaracao
from lib.vagas import nomes, sql_valido

PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "produtos-host"
NOME_DE_PRODUTO = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
MODOS = ("socket", "senha", "container")
CHAVES = {"produto", "porta_padrao", "cliente", "erro", "pergunta"}
CHAVES_DO_ERRO = {"contem", "codigo", "modo", "motivo", "nao_publica"}
PROPRIAS = {"id", "sql", "formato", "colunas", "separador", "enumerar"}
DA_EXTRACAO = {"lista", "campos", "transformar", "derivar", "ordenar_por", "ordem", "desempate",
               "limite"}
VAGAS_DO_CLIENTE = {"socket": {"sql", "porta"}, "senha": {"sql", "porta"},
                    "container": {"sql", "container", "porta"}}
COLUNA = re.compile(r"[a-z_][a-z0-9_]{0,31}")


class CatalogoInvalido(Exception):
    """Catálogo de produto que a skill se recusa a usar."""


def _cliente(nome, modo, molde):
    if modo not in MODOS:
        raise CatalogoInvalido(f"{nome}: modo de leitura {modo!r} não existe; os modos são "
                               f"{', '.join(MODOS)}")
    if not isinstance(molde, str) or not molde.strip():
        raise CatalogoInvalido(f"{nome}: cliente {modo!r} vazio")
    ruins = sorted(catalogo_host.PROIBIDOS & set(molde))
    if ruins:
        raise CatalogoInvalido(f"{nome}: cliente {modo!r} tem {''.join(ruins)!r}; o cliente não "
                               f"encadeia nem interpola")
    sobrando = nomes(molde) - VAGAS_DO_CLIENTE[modo]
    if sobrando:
        raise CatalogoInvalido(f"{nome}: cliente {modo!r} usa a vaga {', '.join(sorted(sobrando))}, "
                               f"que este modo não preenche")
    partes = molde.split('"')
    if molde.count("{sql}") != 1 or len(partes) % 2 == 0 or any("{sql}" in p for p in partes[0::2]):
        raise CatalogoInvalido(f"{nome}: cliente {modo!r} precisa de UMA vaga {{sql}}, dentro de "
                               f"aspas duplas")


def _sql(nome, id_, sql, com_colecao):
    if not sql_valido(sql):
        raise CatalogoInvalido(f"{nome}: {id_} tem consulta vazia ou com caractere proibido "
                               f"(aspas duplas, $, crase, \\, %, <, > ou quebra de linha)")
    sobrando = nomes(sql) - ({"colecao"} if com_colecao else set())
    if sobrando:
        raise CatalogoInvalido(f"{nome}: {id_} tem a vaga {', '.join(sorted(sobrando))} na consulta")


def _enumerar(nome, id_, enumerar, formato, sqls):
    if not isinstance(enumerar, dict) or set(enumerar) != {"sql", "lista", "campo"} \
            or formato != "json":
        raise CatalogoInvalido(f"{nome}: {id_}: `enumerar` é {{sql, lista, campo}} e só vale com "
                               f"formato json")
    _sql(nome, id_, enumerar["sql"], com_colecao=False)
    try:
        ponteiro({}, enumerar["lista"])
    except ExtracaoInvalida as erro:
        raise CatalogoInvalido(f"{nome}: {id_}: `enumerar.lista` — {erro}") from erro
    if len(sqls) != 1 or "colecao" not in nomes(sqls[0]):
        raise CatalogoInvalido(f"{nome}: {id_}: com `enumerar`, a consulta é uma só e usa a vaga "
                               f"{{colecao}}")


def _pergunta(nome, pergunta, registro):
    id_ = pergunta.get("id")
    if id_ not in registro:
        raise CatalogoInvalido(f"{nome}: pergunta {id_!r} não existe no registro")
    desconhecidas = sorted(set(pergunta) - PROPRIAS - DA_EXTRACAO)
    if desconhecidas:
        raise CatalogoInvalido(f"{nome}: {id_} usa {', '.join(desconhecidas)}, fora da linguagem")
    formato = pergunta.get("formato")
    if formato not in FORMATOS:
        raise CatalogoInvalido(f"{nome}: {id_} tem formato {formato!r}; os formatos são "
                               f"{', '.join(FORMATOS)}")
    sqls = pergunta.get("sql")
    sqls = [sqls] if isinstance(sqls, str) else sqls
    if not isinstance(sqls, list) or not sqls:
        raise CatalogoInvalido(f"{nome}: {id_} sem `sql`")
    if len(sqls) > 1 and formato != "chave_valor":
        raise CatalogoInvalido(f"{nome}: {id_} junta {len(sqls)} consultas; só `chave_valor` sabe "
                               f"juntar")
    enumerar = pergunta.get("enumerar")
    if enumerar is not None:
        _enumerar(nome, id_, enumerar, formato, sqls)
    for sql in sqls:
        _sql(nome, id_, sql, com_colecao=enumerar is not None)
    colunas = pergunta.get("colunas")
    if formato == "tsv" and (not isinstance(colunas, list) or not colunas or not all(
            isinstance(c, str) and COLUNA.fullmatch(c) for c in colunas)):
        raise CatalogoInvalido(f"{nome}: {id_} em tsv precisa de `colunas` (nomes minúsculos)")
    separador = pergunta.get("separador")
    if separador is not None and (not isinstance(separador, str) or len(separador) != 1):
        raise CatalogoInvalido(f"{nome}: {id_}: `separador` é um caractere")
    extracao = {k: v for k, v in pergunta.items() if k in DA_EXTRACAO}
    try:
        validar_declaracao(extracao)
    except ExtracaoInvalida as erro:
        raise CatalogoInvalido(f"{nome}: {id_} — {erro}") from erro
    extraidos = set(extracao.get("campos") or {}) | set(extracao.get("derivar") or {})
    if registro[id_]["forma"] == "lista":
        if "lista" not in extracao:
            raise CatalogoInvalido(f"{nome}: {id_} é lista no registro e não declara `lista`")
    elif "lista" in extracao or "valor" not in extraidos:
        raise CatalogoInvalido(f"{nome}: {id_} é escalar: declare o campo ou a derivação `valor`, "
                               f"sem `lista`")
    return {"id": id_, "sql": list(sqls), "formato": formato, "colunas": colunas,
            "separador": separador, "enumerar": enumerar, "extracao": extracao}


def _erro(nome, erro, modos):
    if not isinstance(erro, dict) or set(erro) - CHAVES_DO_ERRO \
            or not isinstance(erro.get("motivo"), str) or not erro["motivo"].strip():
        raise CatalogoInvalido(f"{nome}: cada [[erro]] tem `motivo` e `contem` ou `codigo`")
    contem, codigo = erro.get("contem"), erro.get("codigo")
    if (contem is None and codigo is None) or (contem is not None and (
            not isinstance(contem, str) or not contem)) or (
            codigo is not None and type(codigo) is not int):
        raise CatalogoInvalido(f"{nome}: [[erro]] precisa de `contem` (texto) ou `codigo` (inteiro)")
    if erro.get("modo") is not None and erro["modo"] not in modos:
        raise CatalogoInvalido(f"{nome}: [[erro]] cita o modo {erro['modo']!r}, que o [cliente] "
                               f"não tem")
    if "nao_publica" in erro and type(erro["nao_publica"]) is not bool:
        raise CatalogoInvalido(f"{nome}: [[erro]]: `nao_publica` é true ou false")
    return dict(erro)


def carregar_arquivo(caminho):
    from lib.perguntas import PERGUNTAS

    caminho = Path(caminho)
    nome = caminho.name
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except (OSError, tomllib.TOMLDecodeError) as erro:
        raise CatalogoInvalido(f"{nome}: não consegui ler — {erro}") from erro
    desconhecidas = sorted(set(dados) - CHAVES)
    if desconhecidas:
        raise CatalogoInvalido(f"{nome}: chave desconhecida {', '.join(desconhecidas)}")
    produto = dados.get("produto")
    if produto != caminho.stem:
        raise CatalogoInvalido(f"{nome}: `produto` precisa ser o nome do arquivo ({caminho.stem!r})")
    if produto not in {p["nome"] for p in produtos.carregar()}:
        raise CatalogoInvalido(f"{nome}: o produto {produto!r} não está em references/produtos.toml")
    cliente = dados.get("cliente")
    if not isinstance(cliente, dict) or not cliente:
        raise CatalogoInvalido(f"{nome}: sem tabela [cliente]")
    for modo, molde in cliente.items():
        _cliente(nome, modo, molde)
    porta = dados.get("porta_padrao")
    if porta is not None and (type(porta) is not int or not 1 <= porta <= 65535):
        raise CatalogoInvalido(f"{nome}: `porta_padrao` é inteiro de 1 a 65535")
    if porta is None and any("porta" in nomes(m) for m in cliente.values()):
        raise CatalogoInvalido(f"{nome}: cliente com vaga {{porta}} precisa de `porta_padrao`")
    erros = [_erro(nome, e, cliente) for e in dados.get("erro", [])]
    perguntas = dados.get("pergunta")
    if not isinstance(perguntas, list) or not perguntas:
        raise CatalogoInvalido(f"{nome}: nenhuma [[pergunta]]")
    lidas = [_pergunta(nome, p, PERGUNTAS) for p in perguntas]
    ids = [p["id"] for p in lidas]
    if len(ids) != len(set(ids)):
        raise CatalogoInvalido(f"{nome}: pergunta repetida")
    return {"produto": produto, "porta_padrao": porta, "cliente": dict(cliente), "erro": erros,
            "pergunta": lidas}


def do_produto(nome, pasta=None):
    """O catálogo do produto; None quando não há arquivo. Arquivo inválido levanta."""
    if not isinstance(nome, str) or not NOME_DE_PRODUTO.fullmatch(nome):
        return None
    caminho = Path(pasta or PASTA) / f"{nome}.toml"
    return carregar_arquivo(caminho) if caminho.is_file() else None


def todos(pasta=None):
    return [carregar_arquivo(p) for p in sorted(Path(pasta or PASTA).glob("*.toml"))]
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_vagas.py tests/test_catalogo_produto.py tests/test_seguranca_batch6.py tests/test_nan_nunca_chega_ao_report.py`
Esperado: PASSA.

---

### Task 4: moldes no catálogo de host e o runner com vagas e entrada

**Arquivos:**
- Alterar: `references/host/linux.toml` (comando `processos` e tabela `[molde]`)
- Alterar: `scripts/lib/catalogo_host.py` (arquivo inteiro)
- Alterar: `scripts/lib/vagas.py` (acrescentar no fim)
- Alterar: `scripts/lib/runner.py` (`run_ssh` e `_codigo`)
- Alterar: `tests/apoio_host.py` (`runner_falso` e `Falha`)
- Alterar: `tests/test_catalogo_host.py` (`CHAVES`)
- Teste: `tests/test_catalogo_host_moldes.py`, `tests/test_runner_vagas.py`

**Depende de:** Task 3

**Contrato que esta task publica:** `catalogo_host.carregar() -> {"comandos", "moldes", "ignorar"}`;
`catalogo_host.VAGAS_DO_MOLDE`; moldes `servico_unidade`, `servico_container`, `memoria_container`,
`backup`; comando literal `processos`; `vagas.moldes_permitidos() -> frozenset`,
`vagas.sqls_permitidos() -> frozenset`, `vagas.preencher(molde, vagas) -> str` (levanta
`VagaInvalida`); `runner.run_ssh(destino, porta, comando, timeout, errors=None, vagas=None,
entrada=None)` (com `vagas`, `comando` é um molde; erro de execução traz `"codigo"`; sem `entrada`,
`stdin=DEVNULL`); `apoio_host.runner_falso(saidas, conexao=True, chamadas=None, registro=None)`
(chave literal, `"<molde>:<valor da vaga>"` para molde da camada comum, o texto da consulta para molde de
produto) e `apoio_host.Falha(motivo, codigo=1)` como valor de `saidas` para simular erro.

- [x] **Step 1: escrever os testes que falham**

```python
# tests/test_catalogo_host_moldes.py
import pytest

from lib import catalogo_host


def test_o_catalogo_traz_os_moldes_da_camada_comum_e_o_ps_literal():
    catalogo = catalogo_host.carregar()
    assert set(catalogo["moldes"]) == {"servico_unidade", "servico_container",
                                       "memoria_container", "backup"}
    assert catalogo["moldes"]["backup"] == "ls -l --time-style=full-iso {backup_pasta}"
    assert catalogo["comandos"]["processos"] == "ps -e -o comm=,rss=,etimes="


@pytest.mark.parametrize("tabela,texto", [
    ("comando", "systemctl show {unidade}"),
    ("molde", "cat {sql}"),
    ("molde", "ls {pasta}"),
    ("molde", "id -un"),
    ("molde", "systemctl show {unidade}; id"),
])
def test_vaga_fora_do_lugar_e_recusada(tmp_path, tabela, texto):
    base = 'ignorar = []\n[comando]\nusuario = "id -un"\n'
    corpo = (f'ignorar = []\n[comando]\nusuario = "{texto}"\n' if tabela == "comando"
             else f'{base}[molde]\nx = "{texto}"\n')
    caminho = tmp_path / "linux.toml"
    caminho.write_text(corpo, encoding="utf-8")
    with pytest.raises(catalogo_host.CatalogoInvalido):
        catalogo_host.carregar(caminho)
```

```python
# tests/test_runner_vagas.py
import subprocess
from unittest import mock

import pytest

from apoio_produto import MARIADB, QDRANT, gravar
from lib import catalogo_host, runner
from lib.coletores.docker_allowlist import NotAllowed

MOLDES = catalogo_host.carregar()["moldes"]
SENHA = 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
QDRANT_CLIENTE = 'curl -s -f -m 5 "http://127.0.0.1:{porta}{sql}"'


def _ok(stdout="ok\n"):
    return mock.Mock(stdout=stdout, returncode=0, stderr="")


def test_molde_da_camada_comum_monta_o_comando_e_fecha_o_stdin():
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("root@srv-exemplo", None, MOLDES["servico_unidade"], 20,
                       vagas={"unidade": "postgresql@15-main.service"})
    argv, kwargs = m.call_args[0][0], m.call_args[1]
    assert argv[-1] == ("systemctl show postgresql@15-main.service --property=ActiveState,"
                        "ActiveEnterTimestampMonotonic,NRestarts,MemoryCurrent --no-pager")
    assert kwargs["stdin"] is subprocess.DEVNULL and "input" not in kwargs


def test_comando_literal_tambem_fecha_o_stdin():
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("root@srv-exemplo", None, "id -un", 20)
    assert m.call_args[1]["stdin"] is subprocess.DEVNULL


def test_senha_vai_pelo_stdin_e_nunca_pelo_argv(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    entrada = '[client]\nuser="leitor"\npassword="MARCA-senha-123"\n'
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("root@banco-01", None, SENHA, 20, vagas={"sql": "SHOW GLOBAL STATUS"},
                       entrada=entrada)
    argv, kwargs = m.call_args[0][0], m.call_args[1]
    assert argv[-1] == 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "SHOW GLOBAL STATUS"'
    assert not any("MARCA-senha-123" in token for token in argv)
    assert kwargs["input"] == entrada and "stdin" not in kwargs


def test_colecao_valida_entra_na_consulta_do_catalogo(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("root@banco-01", None, QDRANT_CLIENTE, 20,
                       vagas={"sql": "/collections/{colecao}", "porta": 6333, "colecao": "docs_v2"})
    assert m.call_args[0][0][-1] == 'curl -s -f -m 5 "http://127.0.0.1:6333/collections/docs_v2"'


RECUSAS = [
    ("molde fora do catálogo", "systemctl show {unidade}", {"unidade": "a.service"}),
    ("unidade com ponto e vírgula", MOLDES["servico_unidade"], {"unidade": "a;reboot"}),
    ("unidade que vira opção", MOLDES["servico_unidade"], {"unidade": "-H evil"}),
    ("container com espaço", MOLDES["servico_container"], {"container": "a b"}),
    ("vaga faltando", MOLDES["servico_unidade"], {}),
    ("vaga sobrando", MOLDES["servico_unidade"], {"unidade": "a.service", "container": "b"}),
    ("pasta que sobe diretório", MOLDES["backup"], {"backup_pasta": "/var/../etc"}),
    ("sql fora do catálogo", SENHA, {"sql": "SELECT 1"}),
    ("sql em molde sem vaga sql", MOLDES["backup"],
     {"backup_pasta": "/var/backups", "sql": "SHOW GLOBAL STATUS"}),
    ("coleção com ponto e vírgula", QDRANT_CLIENTE,
     {"sql": "/collections/{colecao}", "porta": 6333, "colecao": "a;b"}),
    ("coleção com espaço", QDRANT_CLIENTE,
     {"sql": "/collections/{colecao}", "porta": 6333, "colecao": "a b"}),
    ("porta fora da faixa", QDRANT_CLIENTE, {"sql": "/collections", "porta": 0}),
]


@pytest.mark.parametrize("caso,molde,vagas", RECUSAS, ids=[r[0] for r in RECUSAS])
def test_runner_recusa_antes_do_subprocesso(tmp_path, monkeypatch, caso, molde, vagas):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB, qdrant=QDRANT)
    with mock.patch("lib.runner.subprocess.run") as m:
        with pytest.raises(NotAllowed):
            runner.run_ssh("root@banco-01", None, molde, 20, vagas=vagas)
    assert m.call_count == 0


def test_a_recusa_nao_repete_o_valor_recusado():
    with pytest.raises(NotAllowed) as erro:
        runner.run_ssh("root@banco-01", None, MOLDES["servico_unidade"], 20,
                       vagas={"unidade": "a;reboot"})
    assert "reboot" not in str(erro.value) and "{unidade}" in str(erro.value)


def test_codigo_de_saida_vai_junto_do_motivo():
    erros = []
    falha = mock.Mock(stdout="", returncode=127, stderr="bash: mariadb: command not found")
    with mock.patch("lib.runner.subprocess.run", return_value=falha):
        assert runner.run_ssh("root@banco-01", None, "id -un", 20, errors=erros) is None
    assert erros == [{"cmd": "ssh root@banco-01", "reason": "bash: mariadb: command not found",
                      "codigo": 127}]
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_catalogo_host_moldes.py tests/test_runner_vagas.py`
Esperado: FALHA — `KeyError: 'moldes'` na coleta de `test_runner_vagas.py` e em
`test_o_catalogo_traz_os_moldes…`; os casos de `[molde]` não levantam (o carregador atual ignora a tabela).

- [x] **Step 3: escrever o catálogo, o carregador, o preenchimento e o runner**

Em `references/host/linux.toml`, acrescente ao fim da tabela `[comando]` (depois de `containers`) e
depois dela a tabela nova:

```toml
# todos os processos com nome curto, memória e idade — sem linha de comando, que carrega senha.
# O filtro pelo nome do componente é feito na skill: o processo não vira vaga.
processos = "ps -e -o comm=,rss=,etimes="

# Moldes: comando com VAGA. Cada vaga tem validador em lib/vagas.py, e o runner monta o comando antes
# do subprocesso. Os caracteres proibidos são os mesmos dos comandos literais.
[molde]
servico_unidade = "systemctl show {unidade} --property=ActiveState,ActiveEnterTimestampMonotonic,NRestarts,MemoryCurrent --no-pager"
servico_container = '''docker inspect --format '{{.RestartCount}} {{json .State}}' {container}'''
memoria_container = '''docker stats --no-stream --format '{{.MemUsage}}' {container}'''
backup = "ls -l --time-style=full-iso {backup_pasta}"
```

Substitua `scripts/lib/catalogo_host.py` inteiro por:

```python
"""Catálogo de comandos de leitura do host: literais em [comando], moldes com vaga em [molde].

O `lib/catalogo.py` permite `%SELETOR%`; copiar aquele módulo traria a interpolação junto, e do
outro lado do ssh há um shell de verdade. Comando literal é o texto do arquivo, e o runner só aceita
um texto que esteja nesta lista. Molde tem vaga (`{unidade}`, `{container}`, `{backup_pasta}`), e a
vaga só é preenchida por `lib/vagas.py`, com o validador dela — nunca por formatação de texto livre.
"""
import tomllib
from pathlib import Path

from lib.vagas import nomes

ARQUIVO = Path(__file__).resolve().parent.parent.parent / "references" / "host" / "linux.toml"
PROIBIDOS = set(";|&$`<>%\n\r")
VAGAS_DO_MOLDE = {"unidade", "container", "backup_pasta"}


class CatalogoInvalido(Exception):
    """Catálogo de host que a skill se recusa a usar."""


def _checar(caminho, tabela, chave, texto):
    if not isinstance(texto, str) or not texto.strip():
        raise CatalogoInvalido(f"{caminho.name}: {tabela} {chave!r} vazio")
    ruins = sorted(PROIBIDOS & set(texto))
    if ruins:
        raise CatalogoInvalido(f"{caminho.name}: {tabela} {chave!r} tem {''.join(ruins)!r}; "
                               f"o comando não encadeia nem interpola")


def carregar(caminho=None):
    caminho = Path(caminho or ARQUIVO)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except (OSError, tomllib.TOMLDecodeError) as erro:
        raise CatalogoInvalido(f"{caminho.name}: não consegui ler — {erro}") from erro
    comandos = dados.get("comando")
    if not isinstance(comandos, dict) or not comandos:
        raise CatalogoInvalido(f"{caminho.name}: sem tabela [comando]")
    for chave, texto in comandos.items():
        _checar(caminho, "comando", chave, texto)
        if nomes(texto):
            raise CatalogoInvalido(f"{caminho.name}: comando {chave!r} tem vaga; comando com vaga "
                                   f"mora em [molde]")
    moldes = dados.get("molde", {})
    if not isinstance(moldes, dict):
        raise CatalogoInvalido(f"{caminho.name}: [molde] é uma tabela")
    for chave, texto in moldes.items():
        _checar(caminho, "molde", chave, texto)
        vagas = nomes(texto)
        if not vagas or not vagas <= VAGAS_DO_MOLDE:
            raise CatalogoInvalido(f"{caminho.name}: molde {chave!r} precisa de vaga, só entre "
                                   f"{', '.join(sorted(VAGAS_DO_MOLDE))}")
    ignorar = dados.get("ignorar", [])
    if not isinstance(ignorar, list) or not all(isinstance(i, str) and i for i in ignorar):
        raise CatalogoInvalido(f"{caminho.name}: `ignorar` é lista de nomes de processo")
    return {"comandos": {k: v.strip() for k, v in comandos.items()},
            "moldes": {k: v.strip() for k, v in moldes.items()}, "ignorar": tuple(ignorar)}


def comandos_permitidos(caminho=None):
    return frozenset(carregar(caminho)["comandos"].values())
```

No fim de `scripts/lib/vagas.py`:

```python
def _validar(nome, valor, sqls):
    if nome in ("unidade", "container"):
        ok = isinstance(valor, str) and bool(NOME_DE_ORIGEM.fullmatch(valor))
    elif nome == "porta":
        ok = type(valor) is int and 1 <= valor <= 65535
    elif nome == "colecao":
        ok = isinstance(valor, str) and bool(COLECAO.fullmatch(valor))
    elif nome == "backup_pasta":
        ok = pasta_valida(valor)
    elif nome == "sql":
        ok = sql_valido(valor) and valor in sqls
    else:
        ok = False
    if not ok:
        raise VagaInvalida(f"valor recusado para a vaga {{{nome}}}")


def moldes_permitidos():
    """Os moldes de `references/host/linux.toml` e os clientes dos catálogos de produto."""
    from lib import catalogo_host, catalogo_produto

    moldes = set(catalogo_host.carregar()["moldes"].values())
    for catalogo in catalogo_produto.todos():
        moldes |= set(catalogo["cliente"].values())
    return frozenset(moldes)


def sqls_permitidos():
    """As consultas literais dos catálogos de produto — as únicas que entram em `{sql}`."""
    from lib import catalogo_produto

    sqls = set()
    for catalogo in catalogo_produto.todos():
        for pergunta in catalogo["pergunta"]:
            sqls |= set(pergunta["sql"])
            if pergunta["enumerar"]:
                sqls.add(pergunta["enumerar"]["sql"])
    return frozenset(sqls)


def preencher(molde, vagas):
    """O comando pronto, ou `VagaInvalida`.

    O molde precisa estar num catálogo; as vagas preenchidas precisam ser EXATAMENTE as que ele pede,
    contando as que vêm dentro do `{sql}` (`{colecao}`). Vaga sobrando é recusa, não descarte: quem
    manda uma vaga que o molde não usa está montando outro comando que não o do catálogo.
    """
    if not isinstance(molde, str) or molde not in moldes_permitidos():
        raise VagaInvalida("molde fora dos catálogos")
    if not isinstance(vagas, dict):
        raise VagaInvalida("as vagas precisam ser um dicionário")
    texto = molde
    if "sql" in nomes(molde):
        _validar("sql", vagas.get("sql"), sqls_permitidos())
        texto = texto.replace("{sql}", vagas["sql"])
    elif "sql" in vagas:
        raise VagaInvalida("vaga {sql} num molde que não a usa")
    pedidas = nomes(texto)
    if pedidas != set(vagas) - {"sql"}:
        raise VagaInvalida("as vagas preenchidas não são as que o molde pede")
    for nome in sorted(pedidas):
        _validar(nome, vagas[nome], ())
        texto = texto.replace("{" + nome + "}", str(vagas[nome]))
    return texto
```

Em `scripts/lib/runner.py`, substitua a função `run_ssh` inteira por:

```python
def run_ssh(destino, porta, comando, timeout, errors=None, vagas=None, entrada=None):
    """Roda UM comando de host. Sem `vagas`, o comando é um texto literal do catálogo de host; com
    `vagas`, é um molde dos catálogos, e `lib/vagas.py` o preenche com valores validados. Destino,
    porta e comando são conferidos ANTES do subprocesso; fora do permitido é bug de dev e levanta
    `NotAllowed`.

    `entrada` vai pelo stdin do ssh (o arquivo de opções com a senha do banco) e nunca pelo argv. Sem
    ela, o stdin é fechado: herdado da skill, um comando remoto poderia ler o terminal de quem audita.
    """
    from lib import vagas as vagas_mod
    from lib.alvos import DESTINO
    from lib.catalogo_host import comandos_permitidos

    if not isinstance(destino, str) or not DESTINO.fullmatch(destino):
        raise NotAllowed("destino ssh fora do formato usuario@host")
    if porta is not None and (type(porta) is not int or not 1 <= porta <= 65535):
        raise NotAllowed("porta ssh fora de 1 a 65535")
    if vagas is None:
        if comando not in comandos_permitidos():
            raise NotAllowed("comando remoto fora do catálogo de host")
        remoto = comando
    else:
        try:
            remoto = vagas_mod.preencher(comando, vagas)
        except vagas_mod.VagaInvalida as erro:
            raise NotAllowed(f"comando remoto recusado: {erro}") from None
    if entrada is not None and not isinstance(entrada, str):
        raise NotAllowed("a entrada do comando remoto precisa ser texto")
    label = f"ssh {destino}"
    cmd = argv_ssh(destino, porta, remoto, conexao=max(1, min(10, int(timeout))))
    kwargs = {"input": entrada} if entrada is not None else {"stdin": subprocess.DEVNULL}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False,
                           env=ambiente(None), **kwargs)
    except subprocess.TimeoutExpired:
        _err(errors, label, f"timeout após {timeout}s")
        return None
    except OSError as e:
        _err(errors, label, f"não foi possível executar o ssh ({e})")
        return None
    if p.returncode == 255:
        _err(errors, label, f"não abri a sessão para {destino} (a VPN está ligada?): "
                            f"{_clean(p.stderr)}")
        _codigo(errors, 255)
        return None
    if p.returncode != 0:
        _err(errors, label, _clean(p.stderr) or f"saiu com código {p.returncode}")
        _codigo(errors, p.returncode)
        return None
    return p.stdout


def _codigo(errors, codigo):
    """O código de saída junto do motivo: 127 (cliente ausente) e o código de um erro conhecido do
    produto decidem a mensagem no adaptador de produto."""
    if errors:
        errors[-1]["codigo"] = codigo
```

Substitua `tests/apoio_host.py` inteiro por:

```python
"""Um `run_ssh` de mentira: devolve a saída gravada, sem rede.

A chave é a do catálogo de host para comando literal (`"disco"`), `"<molde>:<valor da vaga>"` para
molde da camada comum (`"servico_unidade:mariadb.service"`) e o texto da consulta para molde de produto
(`"SHOW GLOBAL STATUS"`, com a `{colecao}` já trocada). Chave ausente simula comando que falhou; uma
`Falha` simula erro com motivo e código. `conexao=False` simula a VPN desligada.
"""
from typing import NamedTuple

from lib import catalogo_host


class Falha(NamedTuple):
    motivo: str
    codigo: int = 1


def runner_falso(saidas, conexao=True, chamadas=None, registro=None):
    catalogo = catalogo_host.carregar()
    por_texto = {v: k for k, v in catalogo["comandos"].items()}
    por_molde = {v: k for k, v in catalogo["moldes"].items()}

    def _chave(comando, vagas):
        if vagas is None:
            return por_texto[comando]
        if "sql" in vagas:
            return vagas["sql"].replace("{colecao}", str(vagas.get("colecao", "{colecao}")))
        return f"{por_molde[comando]}:{next(iter(vagas.values()))}"

    def run_ssh(destino, porta, comando, timeout, errors=None, vagas=None, entrada=None):
        chave = _chave(comando, vagas)
        if chamadas is not None:
            chamadas.append(chave)
        if registro is not None:
            registro.append({"comando": comando, "vagas": vagas, "entrada": entrada})
        if not conexao:
            if errors is not None:
                errors.append({"cmd": f"ssh {destino}", "codigo": 255,
                               "reason": f"não abri a sessão para {destino} (a VPN está ligada?)"})
            return None
        saida = saidas.get(chave)
        if saida is None or isinstance(saida, Falha):
            if errors is not None:
                falha = saida if isinstance(saida, Falha) else Falha(f"{chave} falhou")
                errors.append({"cmd": f"ssh {destino}", "reason": falha.motivo,
                               "codigo": falha.codigo})
            return None
        return saida
    return run_ssh


SAIDAS_PADRAO = {
    "usuario": "root\n", "kernel": "Linux 6.1.0-18-amd64\n",
    "sistema": 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n',
    "disco": "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
             "/dev/vda1 50000000 47000000 3000000 94% /\n",
    "memoria": "MemTotal: 4000000 kB\nMemAvailable: 2000000 kB\n",
    "carga": "0.40 0.80 0.60 1/100 1\n", "cpus": "2\n", "boot": "172800.00 10.00\n",
}
```

Em `tests/test_catalogo_host.py`, troque `CHAVES` por:

```python
CHAVES = {"usuario", "kernel", "sistema", "disco", "memoria", "carga", "cpus", "boot",
          "servicos", "portas", "containers", "processos"}
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_catalogo_host_moldes.py tests/test_runner_vagas.py tests/test_catalogo_host.py tests/test_runner_ssh.py tests/test_runner.py tests/test_adaptador_ssh.py`
Esperado: PASSA.

- [x] **Step 5: rodar a suíte inteira**

Rode: `timeout 900 .venv/bin/python -m pytest -q`
Esperado: tudo verde. O `runner_falso` novo devolve o mesmo que o antigo para chave literal, então os
testes de `coletor_host`, `descoberta` e `configurar` da parte A não mudam.

---

### Task 5: campos novos de componente no `alvos.toml`

**Arquivos:**
- Alterar: `scripts/lib/alvos.py` (imports, `COMPONENTE_PERMITE`, `LEITURAS`, `_checar_componentes`)
- Teste: `tests/test_alvos_leitura.py`

**Depende de:** Task 3

**Contrato que esta task publica:** componente aceita `leitura` (um de `alvos.LEITURAS = ("socket",
"senha", "container", "nenhum")`), `backup_pasta` (absoluta, `vagas.pasta_valida`) e `backup_max_dias`
(inteiro 1–365, só com `backup_pasta`); `leitura = "senha"` exige `usuario` e `senha_env`. `usuario` e
`senha_env` já existiam.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_alvos_leitura.py
import pytest

from lib import alvos

BASE = ('[[alvo]]\nnome = "banco-01"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
        '[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\nproduto = "mariadb"\n'
        'origem = "unidade:mariadb.service"\n')


def _ler(tmp_path, extra):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(BASE + extra, encoding="utf-8")
    caminho.chmod(0o600)
    return alvos.ler(caminho)[0][0]["componente"][0]


def test_leitura_e_backup_carregam(tmp_path):
    comp = _ler(tmp_path, 'leitura = "senha"\nusuario = "leitor"\nsenha_env = "SENHA_BANCO_01"\n'
                          'backup_pasta = "/var/backups/mysql"\nbackup_max_dias = 7\n')
    assert (comp["leitura"], comp["backup_pasta"], comp["backup_max_dias"]) == \
        ("senha", "/var/backups/mysql", 7)


def test_leitura_fora_da_lista_e_recusada(tmp_path):
    with pytest.raises(alvos.AlvoInvalido, match="leitura precisa ser uma de"):
        _ler(tmp_path, 'leitura = "sudo"\n')


@pytest.mark.parametrize("extra", ['leitura = "senha"\n',
                                   'leitura = "senha"\nusuario = "leitor"\n',
                                   'leitura = "senha"\nsenha_env = "SENHA_BANCO_01"\n'])
def test_leitura_senha_sem_usuario_ou_variavel_e_recusada(tmp_path, extra):
    with pytest.raises(alvos.AlvoInvalido, match="exige usuario e senha_env"):
        _ler(tmp_path, extra)


@pytest.mark.parametrize("pasta", ['"relativa/x"', '"/var/../etc"', '"/var/back ups"', "7"])
def test_pasta_de_backup_fora_do_formato_e_recusada(tmp_path, pasta):
    with pytest.raises(alvos.AlvoInvalido, match="backup_pasta precisa ser caminho absoluto"):
        _ler(tmp_path, f"backup_pasta = {pasta}\n")


@pytest.mark.parametrize("dias", ["0", "400", '"2"', "true"])
def test_dias_fora_da_faixa_e_recusado(tmp_path, dias):
    with pytest.raises(alvos.AlvoInvalido, match="backup_max_dias precisa ser inteiro de 1 a 365"):
        _ler(tmp_path, f'backup_pasta = "/var/backups"\nbackup_max_dias = {dias}\n')


def test_dias_sem_pasta_e_recusado(tmp_path):
    with pytest.raises(alvos.AlvoInvalido, match="backup_max_dias sem backup_pasta"):
        _ler(tmp_path, "backup_max_dias = 7\n")


def test_leitura_container_em_origem_de_unit_carrega(tmp_path):
    """O spec quer `sem dados` com motivo na COLETA, não recusa na leitura do arquivo."""
    assert _ler(tmp_path, 'leitura = "container"\n')["leitura"] == "container"
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_alvos_leitura.py`
Esperado: FALHA — todos os casos com `campo que não existe: …` (as mensagens novas não aparecem).

- [x] **Step 3: escrever o mínimo em alvos.py**

No topo de `scripts/lib/alvos.py`, depois de `from urllib.parse import urlparse`:

```python
from lib.vagas import pasta_valida
```

Troque `COMPONENTE_PERMITE` por:

```python
COMPONENTE_PERMITE = ("nome", "papel", "admin_url", "metricas_url", "senha_env",
                      "usuario", "produto", "portas", "origem",
                      "leitura", "backup_pasta", "backup_max_dias")
# Como a skill lê um componente de host. `senha` só funciona onde o catálogo do produto tem cliente
# com senha (MariaDB e MySQL): quem confere é o `configurar.py leitura` e o adaptador de produto.
LEITURAS = ("socket", "senha", "container", "nenhum")
```

Em `_checar_componentes`, logo depois do bloco que recusa `portas` (o `raise` que termina em
`f"é lista de inteiros de 1 a 65535")`), acrescente:

```python
        leitura = bruto.get("leitura")
        if leitura is not None and leitura not in LEITURAS:
            raise AlvoInvalido(f"{caminho.name}: componente {nome!r} de {nome_do_alvo!r}: leitura "
                               f"precisa ser uma de: {', '.join(LEITURAS)}")
        if leitura == "senha" and not (bruto.get("usuario") and bruto.get("senha_env")):
            raise AlvoInvalido(f"{caminho.name}: componente {nome!r} de {nome_do_alvo!r}: "
                               f'leitura = "senha" exige usuario e senha_env')
        pasta = bruto.get("backup_pasta")
        if pasta is not None and not pasta_valida(pasta):
            raise AlvoInvalido(f"{caminho.name}: componente {nome!r} de {nome_do_alvo!r}: "
                               f"backup_pasta precisa ser caminho absoluto só com letras, números, "
                               f"ponto, hífen, sublinhado e barra, sem `..`")
        dias = bruto.get("backup_max_dias")
        if dias is not None and (type(dias) is not int or not 1 <= dias <= 365):
            raise AlvoInvalido(f"{caminho.name}: componente {nome!r} de {nome_do_alvo!r}: "
                               f"backup_max_dias precisa ser inteiro de 1 a 365")
        if dias is not None and pasta is None:
            raise AlvoInvalido(f"{caminho.name}: componente {nome!r} de {nome_do_alvo!r}: "
                               f"backup_max_dias sem backup_pasta")
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_alvos_leitura.py tests/test_alvos.py tests/test_alvos_host.py tests/test_alvos_componente_descoberto.py`
Esperado: PASSA.

---

## Fase 2 — a camada comum

### Task 6: leitura pura do estado do serviço e da idade do backup

**Arquivos:**
- Criar: `scripts/lib/leitura_servico.py`
- Teste: `tests/test_leitura_servico.py`

**Depende de:** nada

**Contrato que esta task publica:** `leitura_servico.PorDesenho(motivo)` (com `.motivo`);
`NAO_ATIVO`, `SEM_REINICIOS`, `SEM_MEMORIA_DA_UNIT`; `de_unidade(show, uptime) -> dict | None`;
`de_container(inspect, stats, agora) -> dict | None` (`agora` em segundos de época);
`de_processo(ps, processo) -> dict | None`; `memoria_do_stats(saida) -> int | None`;
`idade_do_backup(ls, hoje: date) -> int | None`. Os dicionários têm as chaves `servico.ativo`
(`"ativo"` ou o estado cru), `servico.desde` (dias, uma casa), `servico.reinicios`, `servico.memoria`
(bytes); valor `None` = fora do formato, `PorDesenho` = não medido por construção.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_leitura_servico.py
from datetime import date

import pytest

from lib import leitura_servico as ls

SHOW = ("ActiveState=active\nActiveEnterTimestampMonotonic=86400000000\nNRestarts=2\n"
        "MemoryCurrent=524288000\n")
UPTIME = "259200.00 1000.00\n"
INSPECT = ('3 {"Status":"running","Running":true,"StartedAt":"2026-11-10T10:00:00.123456789Z",'
           '"Error":"falha antiga com espaço"}')
AGORA = 1794564000   # 2026-11-13T10:00:00Z
PS = ("systemd 1200 900000\nqdrant 524288 86400\nqdrant 1048576 3600\n"
      "meu worker 100 10\n")
LS = ("total 12\n"
      "-rw-r--r-- 1 root root 4096 2026-11-13 01:00:00.000000000 +0000 leia-me.txt\n"
      "-rw-r--r-- 1 root root 9999 2026-11-12 03:00:01.000000000 +0000 dump-2026-11-08.sql.gz\n"
      "-rw-r--r-- 1 root root 8888 2026-11-07 03:00:01.000000000 +0000 dump-20261107.sql.gz\n")


def test_unit_ativa_mede_as_quatro():
    assert ls.de_unidade(SHOW, UPTIME) == {"servico.ativo": "ativo", "servico.desde": 2.0,
                                           "servico.reinicios": 2, "servico.memoria": 524288000}


@pytest.mark.parametrize("memoria", ["[not set]", "18446744073709551615", ""])
def test_unit_sem_contabilidade_de_memoria_e_nao_medido_por_desenho(memoria):
    resposta = ls.de_unidade(SHOW.replace("524288000", memoria), UPTIME)
    assert resposta["servico.memoria"] == ls.SEM_MEMORIA_DA_UNIT


def test_unit_parada_diz_o_estado_e_nao_inventa_tempo_no_ar():
    show = ("ActiveState=failed\nActiveEnterTimestampMonotonic=0\nNRestarts=5\n"
            "MemoryCurrent=[not set]\n")
    resposta = ls.de_unidade(show, UPTIME)
    assert (resposta["servico.ativo"], resposta["servico.desde"], resposta["servico.reinicios"]) == \
        ("failed", ls.NAO_ATIVO, 5)


def test_saida_que_nao_e_do_systemd_e_none():
    assert ls.de_unidade("lixo", UPTIME) is None and ls.de_unidade("", UPTIME) is None


def test_container_rodando_usa_o_instante_da_rodada():
    assert ls.de_container(INSPECT, "512MiB / 2GiB\n", AGORA) == {
        "servico.ativo": "ativo", "servico.reinicios": 3, "servico.desde": 3.0,
        "servico.memoria": 536870912}


def test_container_parado_nao_mede_tempo_nem_memoria():
    resposta = ls.de_container('0 {"Status":"exited","StartedAt":"2026-11-10T10:00:00Z"}', "", AGORA)
    assert resposta == {"servico.ativo": "exited", "servico.reinicios": 0,
                        "servico.desde": ls.NAO_ATIVO, "servico.memoria": ls.NAO_ATIVO}


def test_inspect_fora_do_formato_e_none():
    assert ls.de_container("3 nada", "", AGORA) is None and ls.de_container("", "", AGORA) is None


@pytest.mark.parametrize("saida,bytes_", [("1.5GiB / 4GiB", 1610612736), ("0B / 0B", 0),
                                          ("812kB / 1GB", 812000), ("lixo", None),
                                          ("12XB / 1GB", None), ("nan MiB / 1GiB", None)])
def test_memoria_do_stats_em_varias_unidades(saida, bytes_):
    assert ls.memoria_do_stats(saida) == bytes_


def test_processo_principal_e_o_mais_antigo_nunca_a_soma_dos_workers():
    assert ls.de_processo(PS, "qdrant") == {
        "servico.ativo": "ativo", "servico.desde": 1.0,
        "servico.reinicios": ls.SEM_REINICIOS, "servico.memoria": 524288 * 1024}


def test_processo_com_espaco_no_nome():
    assert ls.de_processo(PS, "meu worker")["servico.memoria"] == 100 * 1024


def test_processo_ausente_e_parado():
    resposta = ls.de_processo(PS, "redis-server")
    assert resposta["servico.ativo"] == "parado" and resposta["servico.desde"] == ls.NAO_ATIVO


def test_ps_sem_saida_e_none():
    assert ls.de_processo("", "qdrant") is None


def test_backup_pela_data_do_nome_mais_novo_nao_pelo_mtime():
    assert ls.idade_do_backup(LS, date(2026, 11, 13)) == 5


def test_sem_data_no_nome_usa_o_mtime():
    saida = "total 4\n-rw-r--r-- 1 root root 10 2026-11-10 03:00:00.000000000 +0000 base.sql.gz\n"
    assert ls.idade_do_backup(saida, date(2026, 11, 13)) == 3


@pytest.mark.parametrize("nome", ["dump-20261399.sql", "dump_1699999999.sql"])
def test_numero_que_nao_e_data_cai_no_mtime(nome):
    saida = f"total 4\n-rw-r--r-- 1 root root 10 2026-11-11 03:00:00.000000000 +0000 {nome}\n"
    assert ls.idade_do_backup(saida, date(2026, 11, 13)) == 2


def test_pasta_vazia_e_none_nunca_atraso():
    assert ls.idade_do_backup("total 0\n", date(2026, 11, 13)) is None
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_leitura_servico.py`
Esperado: FALHA na coleta com `ImportError: cannot import name 'leitura_servico' from 'lib'`.

- [x] **Step 3: escrever o módulo**

```python
# scripts/lib/leitura_servico.py
"""Leitura pura do estado de um serviço de host e da idade do backup: texto entra, valor sai.

`PorDesenho` marca o dado que a fonte não tem por construção (reinícios de quem é só processo,
memória de unit sem contabilidade, tempo no ar de serviço parado): o adaptador o entrega como
`sem dados` com `nao_publica`, que a cobertura não conta como lacuna. None é saída fora do formato,
e essa conta. Número nunca passa por `float()` aqui: `extracao._numero` já filtra NaN e infinito.
"""
import json
import re
from datetime import date, datetime, timezone

from lib.extracao import _numero


class PorDesenho:
    """Não medido por construção — com o motivo que o relatório mostra."""

    __slots__ = ("motivo",)

    def __init__(self, motivo):
        self.motivo = motivo

    def __eq__(self, outro):
        return isinstance(outro, PorDesenho) and outro.motivo == self.motivo

    def __repr__(self):
        return f"PorDesenho({self.motivo!r})"


NAO_ATIVO = PorDesenho("o serviço não está no ar")
SEM_REINICIOS = PorDesenho("processo sem gerenciador: os reinícios não são contados")
SEM_MEMORIA_DA_UNIT = PorDesenho("o systemd não contabiliza a memória desta unit")
# o systemd antigo imprime UINT64_MAX no lugar de "[not set]"
NAO_DEFINIDO = str(2 ** 64 - 1)
UNIDADES_DE_MEMORIA = {"B": 1, "KIB": 1024, "MIB": 1024 ** 2, "GIB": 1024 ** 3, "TIB": 1024 ** 4,
                       "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4}
MEMORIA = re.compile(r"([0-9.]+)\s*([A-Za-z]+)")
DATA_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
DATA_COMPACTA = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")


def _dias(segundos):
    return round(max(0, segundos) / 86400, 1)


def de_unidade(show, uptime):
    """`systemctl show` + `/proc/uptime` → {pergunta: valor}. None quando não é saída do systemd.

    O tempo no ar sai de `ActiveEnterTimestampMonotonic` contra o uptime: os dois relógios são do
    servidor, e `--timestamp=unix` não existe no systemd antigo."""
    campos = {}
    for linha in (show or "").splitlines():
        chave, sep, valor = linha.partition("=")
        if sep:
            campos[chave.strip()] = valor.strip()
    estado = campos.get("ActiveState")
    if not estado:
        return None
    ativo = estado == "active"
    partes = (uptime or "").split()
    boot = _numero(partes[0]) if partes else None
    mono = campos.get("ActiveEnterTimestampMonotonic", "")
    if not ativo:
        desde = NAO_ATIVO
    elif mono.isdigit() and int(mono) > 0 and boot is not None:
        desde = _dias(boot - int(mono) / 1_000_000)
    else:
        desde = None
    reinicios = campos.get("NRestarts", "")
    memoria = campos.get("MemoryCurrent", "")
    if memoria in ("", "[not set]", NAO_DEFINIDO):
        memoria_valor = SEM_MEMORIA_DA_UNIT
    else:
        memoria_valor = int(memoria) if memoria.isdigit() else None
    return {"servico.ativo": "ativo" if ativo else estado, "servico.desde": desde,
            "servico.reinicios": int(reinicios) if reinicios.isdigit() else None,
            "servico.memoria": memoria_valor}


def _instante(texto):
    try:
        valor = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)


def memoria_do_stats(saida):
    """`123.4MiB / 1.944GiB` (do `docker stats`) → bytes em uso. None fora do formato."""
    usado = (saida or "").split("/")[0].strip()
    achado = MEMORIA.fullmatch(usado)
    if not achado:
        return None
    numero = _numero(achado.group(1))
    unidade = UNIDADES_DE_MEMORIA.get(achado.group(2).upper())
    if numero is None or unidade is None:
        return None
    return int(numero * unidade)


def de_container(inspect, stats, agora):
    """`docker inspect` (`<reinícios> <State em JSON>`) + `docker stats` → {pergunta: valor}."""
    contagem, _, bruto = (inspect or "").strip().partition(" ")
    try:
        estado = json.loads(bruto)
    except ValueError:
        return None
    if not isinstance(estado, dict) or not isinstance(estado.get("Status"), str):
        return None
    ativo = estado["Status"] == "running"
    inicio = _instante(estado.get("StartedAt"))
    if not ativo:
        desde = NAO_ATIVO
    elif inicio is None or agora is None:
        desde = None
    else:
        desde = _dias(agora - inicio.timestamp())
    return {"servico.ativo": "ativo" if ativo else estado["Status"],
            "servico.reinicios": int(contagem) if contagem.isdigit() else None,
            "servico.desde": desde,
            "servico.memoria": memoria_do_stats(stats) if ativo else NAO_ATIVO}


def de_processo(ps, processo):
    """`ps -e -o comm=,rss=,etimes=` → {pergunta: valor} do processo PRINCIPAL, o mais antigo.

    A soma dos workers não é a memória do serviço: eles compartilham páginas com o principal, e somar
    RSS conta a mesma memória várias vezes."""
    if not (ps or "").strip():
        return None
    candidatos = []
    for linha in ps.splitlines():
        partes = linha.split()
        if len(partes) < 3 or not partes[-1].isdigit() or not partes[-2].isdigit():
            continue
        if " ".join(partes[:-2]) == processo:
            candidatos.append((int(partes[-1]), int(partes[-2])))
    if not candidatos:
        return {"servico.ativo": "parado", "servico.desde": NAO_ATIVO,
                "servico.reinicios": SEM_REINICIOS, "servico.memoria": NAO_ATIVO}
    etimes, rss = max(candidatos)
    return {"servico.ativo": "ativo", "servico.desde": _dias(etimes),
            "servico.reinicios": SEM_REINICIOS, "servico.memoria": rss * 1024}


def _data_no_nome(nome):
    for padrao in (DATA_ISO, DATA_COMPACTA):
        for ano, mes, dia in padrao.findall(nome):
            try:
                return date(int(ano), int(mes), int(dia))
            except ValueError:
                continue
    return None


def idade_do_backup(ls, hoje):
    """`ls -l --time-style=full-iso <pasta>` → dias desde o backup mais novo, ou None.

    A data vem do NOME (`AAAA-MM-DD` ou `AAAAMMDD`) do arquivo de data mais nova; só quando nenhum
    nome traz data o mtime decide. Pasta sem arquivo nenhum devolve None: não é backup atrasado, é
    leitura que não achou o que medir."""
    nomes_com_data, mtimes = [], []
    for linha in (ls or "").splitlines():
        partes = linha.split()
        if len(partes) < 9 or linha.startswith("total"):
            continue
        try:
            mtimes.append(date.fromisoformat(partes[5]))
        except ValueError:
            continue
        data = _data_no_nome(" ".join(partes[8:]))
        if data is not None:
            nomes_com_data.append(data)
    referencia = max(nomes_com_data) if nomes_com_data else (max(mtimes) if mtimes else None)
    if referencia is None:
        return None
    return max(0, (hoje - referencia).days)
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_leitura_servico.py tests/test_nan_nunca_chega_ao_report.py`
Esperado: PASSA (o teste de NaN não acha `float()` novo).

---

### Task 7: perguntas comuns e de backup, respondidas pelo adaptador `ssh`

**Arquivos:**
- Alterar: `scripts/lib/perguntas.py` (`_p` ganha `na_ordem`; bloco novo antes de `REGRAS_PRODUZIDAS`)
- Alterar: `scripts/lib/adaptadores/ssh.py` (arquivo inteiro)
- Alterar: `tests/test_perguntas.py` (`test_toda_pergunta_pertence_a_um_papel_existente`)
- Alterar: `tests/test_perguntas_novos_papeis.py` (soma de `ssh.RESPONDE`)
- Teste: `tests/test_adaptador_ssh_servico.py`

**Depende de:** Task 4, Task 6

**Contrato que esta task publica:** `perguntas._p(..., na_ordem=True)`; `perguntas.PAPEL_COMUM =
"servico"`; `perguntas.COMUNS = ["servico.ativo", "servico.desde", "servico.reinicios",
"servico.memoria"]` (opcionais, fora de `ORDEM`); pergunta `banco.backup_idade` (opcional, dias, fora de
`ORDEM`); `adaptadores.ssh.SERVICO`, `ssh.BACKUP = "banco.backup_idade"`, `ssh.RESPONDE` (frozenset de
tudo que o adaptador responde). As comuns só respondem componente com `origem`; o backup, componente
com `backup_pasta`. Ninguém pergunta nada disso ainda: quem escolhe é `perguntas_do_componente`, na
Task 8.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_adaptador_ssh_servico.py
from apoio_host import Falha, runner_falso
from lib.adaptadores import ssh
from lib.perguntas import COMUNS, ORDEM, PERGUNTAS
from test_leitura_servico import INSPECT, LS, SHOW

COMP = {"nome": "mariadb", "papel": "banco", "ssh_destino": "root@banco-01", "porta": None,
        "origem": "unidade:mariadb.service"}


def _ctx():
    return {"timeout": 20, "cache": {}, "at": "2026-11-13T10:00:00Z"}


def _respostas(componente, monkeypatch, saidas, chamadas=None):
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso(saidas, chamadas=chamadas))
    contexto = _ctx()
    return {p: ssh.perguntar(p, componente, contexto) for p in ssh.SERVICO}


def test_comuns_ficam_registradas_fora_de_todo_papel():
    assert COMUNS == ["servico.ativo", "servico.desde", "servico.reinicios", "servico.memoria"]
    novas = [*COMUNS, "banco.backup_idade"]
    assert all(PERGUNTAS[p]["opcional"] and PERGUNTAS[p]["limiar"] is None for p in novas)
    assert not any(p in ids for ids in ORDEM.values() for p in novas)


def test_unit_responde_as_quatro_comuns_com_uma_leitura(monkeypatch):
    chamadas = []
    respostas = _respostas(COMP, monkeypatch, {"servico_unidade:mariadb.service": SHOW,
                                               "boot": "259200.00 1.00\n"}, chamadas)
    assert {p: r["valor"] for p, r in respostas.items()} == {
        "servico.ativo": "ativo", "servico.desde": 2.0, "servico.reinicios": 2,
        "servico.memoria": 524288000}
    assert {r["fonte"] for r in respostas.values()} == {"ssh"}
    assert chamadas.count("servico_unidade:mariadb.service") == 1


def test_reinicio_de_processo_e_nao_medido_por_desenho(monkeypatch):
    componente = {**COMP, "nome": "qdrant", "origem": "processo:qdrant"}
    respostas = _respostas(componente, monkeypatch, {"processos": "qdrant 524288 86400\n"})
    assert respostas["servico.reinicios"]["sem_dados"] and respostas["servico.reinicios"]["nao_publica"]
    assert respostas["servico.memoria"]["valor"] == 524288 * 1024


def test_container_usa_inspect_e_stats_com_o_instante_da_rodada(monkeypatch):
    componente = {**COMP, "nome": "cache", "origem": "container:cache-exemplo"}
    respostas = _respostas(componente, monkeypatch, {
        "servico_container:cache-exemplo": INSPECT,
        "memoria_container:cache-exemplo": "512MiB / 2GiB\n"})
    assert respostas["servico.desde"]["valor"] == 3.0
    assert respostas["servico.reinicios"]["valor"] == 3
    assert respostas["servico.memoria"]["valor"] == 536870912


def test_leitura_que_falha_e_lacuna_com_motivo(monkeypatch):
    respostas = _respostas(COMP, monkeypatch, {})
    ativo = respostas["servico.ativo"]
    assert ativo["sem_dados"] and "falhou" in ativo["motivo"] and "nao_publica" not in ativo


def test_componente_sem_origem_nao_recebe_as_comuns():
    resposta = ssh.perguntar("servico.ativo", {**COMP, "origem": None}, _ctx())
    assert resposta["sem_dados"] and resposta["nao_se_aplica"]


def test_backup_pela_pasta_declarada(monkeypatch):
    componente = {**COMP, "backup_pasta": "/var/backups/mysql"}
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso({"backup:/var/backups/mysql": LS}))
    assert ssh.perguntar("banco.backup_idade", componente, _ctx()) == {
        "pergunta": "banco.backup_idade", "fonte": "ssh", "valor": 5}


def test_backup_vazio_ou_inexistente_e_sem_dados_nunca_numero(monkeypatch):
    componente = {**COMP, "backup_pasta": "/var/backups/mysql"}
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso({"backup:/var/backups/mysql": "total 0\n"}))
    assert "vazia" in ssh.perguntar("banco.backup_idade", componente, _ctx())["motivo"]
    ausente = Falha("ls: cannot access '/var/backups/mysql': No such file or directory", 2)
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso({"backup:/var/backups/mysql": ausente}))
    resposta = ssh.perguntar("banco.backup_idade", componente, _ctx())
    assert resposta["sem_dados"] and "inexistente ou ilegível" in resposta["motivo"]


def test_quem_responde_inclui_as_comuns_e_o_backup():
    assert {*ssh.SERVICO, "banco.backup_idade", "maquina.disco"} <= ssh.RESPONDE
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_adaptador_ssh_servico.py`
Esperado: FALHA na coleta com `ImportError: cannot import name 'COMUNS' from 'lib.perguntas'`.

- [x] **Step 3: escrever as perguntas e o adaptador**

Em `scripts/lib/perguntas.py`, troque a função `_p` por:

```python
def _p(id, papel, titulo, forma, unidade=None, limiar=None, desempate=None, faixa=None, opcional=False,
       por_ultimo=False, na_ordem=True):
    PERGUNTAS[id] = {"id": id, "papel": papel, "titulo": titulo, "forma": forma,
                     "unidade": unidade, "limiar": limiar, "desempate": desempate,
                     "faixa": faixa, "opcional": opcional, "por_ultimo": por_ultimo}
    if na_ordem:
        ORDEM.setdefault(papel, []).append(id)
    return id
```

E acrescente, logo antes do comentário `# O limiar é um produtor de achado, …` (que precede
`REGRAS_PRODUZIDAS`):

```python
# --- perguntas de componente de HOST: fora do `ORDEM[papel]` de propósito. Ali elas cairiam também
# nos clusters, sem quem respondesse, e a cobertura contaria cada uma como lacuna. Quem as escolhe é
# `perguntas_do_componente`, só para componente com `origem` (veio de um servidor).
#
# As comuns valem para QUALQUER serviço de host, do banco ao app próprio. O papel delas é o
# pseudo-papel `servico`, que não existe em `lib/papel.py`: nenhum componente É um serviço genérico.
# Opcionais, sem CPU (uma leitura só daria a média desde o início) e sem limiar: serviço parado já é
# `servico_declarado_ausente`.
PAPEL_COMUM = "servico"
COMUNS = []


def _comum(id, titulo, forma, unidade=None):
    _p(id, PAPEL_COMUM, titulo, forma, unidade=unidade, opcional=True, na_ordem=False)
    COMUNS.append(id)


_comum("servico.ativo", "Estado do serviço", "escalar")
_comum("servico.desde", "No ar há", "escalar", unidade="dias")
_comum("servico.reinicios", "Reinícios", "escalar", unidade="reinícios")
_comum("servico.memoria", "Memória do serviço", "escalar", unidade="bytes")
# Só para componente com `backup_pasta`; o achado de atraso nasce em lib/limites_produto.py.
_p("banco.backup_idade", "banco", "Idade do backup mais novo", "escalar", unidade="dias",
   opcional=True, na_ordem=False)
```

Substitua `scripts/lib/adaptadores/ssh.py` inteiro por:

```python
"""Adaptador por SSH: a máquina (`maquina.*`), o estado de cada serviço de host (`servico.*`) e a
idade do backup declarado.

Mesmo contrato dos outros: valor com fonte, ou `sem_dados` com motivo — nunca levanta. Cada comando
roda uma vez por componente; a resposta (ou a falha) fica em `contexto["cache"]["ssh"]`, então a VPN
desligada custa UMA tentativa por comando, não uma por pergunta. O dado que a fonte não tem por
construção sai com `nao_publica`, que a cobertura não conta como lacuna.
"""
from datetime import date

from lib import catalogo_host, leitura_host, leitura_servico, redact, runner
from lib.adaptadores.promql import momento

ID = "ssh"
LEITURAS = {
    "maquina.disco": (("disco",), leitura_host.disco),
    "maquina.memoria": (("memoria",), leitura_host.memoria),
    "maquina.carga": (("carga", "cpus"), leitura_host.carga),
    "maquina.desde_o_boot": (("boot",), leitura_host.desde_o_boot),
}
SERVICO = ("servico.ativo", "servico.desde", "servico.reinicios", "servico.memoria")
BACKUP = "banco.backup_idade"
RESPONDE = frozenset(LEITURAS) | frozenset(SERVICO) | {BACKUP}
FORA_DO_FORMATO = "a saída do comando veio em formato inesperado"


def _sem_dados(pergunta, motivo, **extra):
    return dict({"pergunta": pergunta, "sem_dados": True, "motivo": motivo}, **extra)


def _ler(componente, chave, contexto, vagas=None):
    cache = contexto.setdefault("cache", {}).setdefault("ssh", {})
    indice = (componente["ssh_destino"], componente.get("porta"), chave,
              tuple(sorted((vagas or {}).items())))
    if indice not in cache:
        erros = []
        catalogo = catalogo_host.carregar()
        comando = catalogo["moldes"][chave] if vagas else catalogo["comandos"][chave]
        saida = runner.run_ssh(componente["ssh_destino"], componente.get("porta"), comando,
                               contexto["timeout"], erros, vagas=vagas)
        cache[indice] = (saida, erros[0]["reason"] if erros else None)
    return cache[indice]


def _estado(componente, contexto):
    """`(leitura, None)` ou `(None, motivo)`. `leitura` é o dicionário de `lib/leitura_servico`."""
    tipo, _, valor = str(componente.get("origem") or "").partition(":")
    if tipo == "unidade":
        show, motivo = _ler(componente, "servico_unidade", contexto, {"unidade": valor})
        if show is None:
            return None, motivo
        uptime, _ = _ler(componente, "boot", contexto)
        return leitura_servico.de_unidade(show, uptime or ""), None
    if tipo == "container":
        inspect, motivo = _ler(componente, "servico_container", contexto, {"container": valor})
        if inspect is None:
            return None, motivo
        stats, _ = _ler(componente, "memoria_container", contexto, {"container": valor})
        return leitura_servico.de_container(inspect, stats, momento(contexto.get("at"))), None
    if tipo == "processo":
        ps, motivo = _ler(componente, "processos", contexto)
        if ps is None:
            return None, motivo
        return leitura_servico.de_processo(ps, valor), None
    return None, "a origem do componente não é unidade, container nem processo"


def _servico(pergunta, componente, contexto):
    leitura, motivo = _estado(componente, contexto)
    if leitura is None:
        return _sem_dados(pergunta, redact.scrub_text(motivo or FORA_DO_FORMATO))
    valor = leitura.get(pergunta)
    if isinstance(valor, leitura_servico.PorDesenho):
        return _sem_dados(pergunta, valor.motivo, nao_publica=True)
    if valor is None:
        return _sem_dados(pergunta, FORA_DO_FORMATO)
    return {"pergunta": pergunta, "fonte": "ssh", "valor": valor}


def _backup(pergunta, componente, contexto):
    try:
        hoje = date.fromisoformat(str(contexto.get("at"))[:10])
    except ValueError:
        return _sem_dados(pergunta, "a rodada não tem data (--at) para medir a idade do backup")
    saida, motivo = _ler(componente, "backup", contexto, {"backup_pasta": componente["backup_pasta"]})
    if saida is None:
        return _sem_dados(pergunta, "pasta de backup inexistente ou ilegível: "
                                    + redact.scrub_text(motivo or "sem detalhe"))
    idade = leitura_servico.idade_do_backup(saida, hoje)
    if idade is None:
        return _sem_dados(pergunta, "a pasta de backup está vazia")
    return {"pergunta": pergunta, "fonte": "ssh", "valor": idade}


def perguntar(pergunta, componente, contexto):
    if not componente.get("ssh_destino"):
        return _sem_dados(pergunta, "o componente não tem destino ssh", nao_se_aplica=True)
    if pergunta in SERVICO:
        if not componente.get("origem"):
            return _sem_dados(pergunta, "o componente não veio de um host", nao_se_aplica=True)
        return _servico(pergunta, componente, contexto)
    if pergunta == BACKUP:
        if not componente.get("backup_pasta"):
            return _sem_dados(pergunta, "o componente não declara backup_pasta", nao_se_aplica=True)
        return _backup(pergunta, componente, contexto)
    if pergunta not in LEITURAS:
        return _sem_dados(pergunta, "a leitura por ssh não mede este dado", nao_se_aplica=True)
    chaves, funcao = LEITURAS[pergunta]
    saidas = []
    for chave in chaves:
        saida, motivo = _ler(componente, chave, contexto)
        if saida is None:
            return _sem_dados(pergunta, redact.scrub_text(motivo or "o comando falhou sem detalhe"))
        saidas.append(saida)
    valor = funcao(*saidas)
    if valor is None:
        return _sem_dados(pergunta, FORA_DO_FORMATO)
    return {"pergunta": pergunta, "fonte": "ssh", "valor": valor}
```

Em `tests/test_perguntas.py`, troque `test_toda_pergunta_pertence_a_um_papel_existente` por:

```python
def test_toda_pergunta_pertence_a_um_papel_existente():
    """`servico` é o pseudo-papel das perguntas comuns de host: ninguém o declara num componente."""
    from lib.perguntas import PAPEL_COMUM

    invalidos = sorted({p["papel"] for p in PERGUNTAS.values()} - set(PAPEIS) - {PAPEL_COMUM})
    assert invalidos == [], f"pergunta de papel inexistente: {invalidos}"
```

Em `tests/test_perguntas_novos_papeis.py`, em `test_toda_pergunta_declarada_tem_alguem_que_a_responda`,
troque a linha `respondidas |= set(ssh.LEITURAS)   # o adaptador ssh responde sem arquivo de família`
por:

```python
    respondidas |= set(ssh.RESPONDE)   # máquina, serviço e backup: o adaptador ssh, sem arquivo
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_adaptador_ssh_servico.py tests/test_adaptador_ssh.py tests/test_perguntas.py tests/test_perguntas_novos_papeis.py tests/test_capacidade.py`
Esperado: PASSA. As contagens de `test_papel_passa_a_ter_pergunta` não mudam (`banco` continua 2):
nada novo entrou em `ORDEM`.

- [x] **Step 5: rodar a suíte inteira**

Rode: `timeout 900 .venv/bin/python -m pytest -q`
Esperado: tudo verde. Os pontos de atenção já tratados: `test_perguntas` (pseudo-papel),
`test_perguntas_novos_papeis` (quem responde) e `test_adaptador_promql::pergunta_sem_familia`, que agora
pega `banco.backup_idade` como primeira pergunta sem família e continua recebendo o motivo com
"exporter".

---

### Task 8: `perguntas_do_componente`, ligada no `responder`, na cobertura e no coletor de host

**Arquivos:**
- Alterar: `scripts/lib/perguntas.py` (função nova no fim)
- Alterar: `scripts/collect.py` (`responder`)
- Alterar: `scripts/lib/cobertura.py` (`medir` e `_exigidos_pelas_mudas`)
- Alterar: `scripts/lib/coletores/host.py` (`coletar`, a lista `declarados`)
- Teste: `tests/test_perguntas_do_componente.py`

**Depende de:** Task 3, Task 7

**Contrato que esta task publica:** `perguntas.perguntas_do_componente(componente) -> list[dict]` (as do
papel; com `origem`, mais `COMUNS`, `banco.backup_idade` quando há `backup_pasta` e as do catálogo do
produto; sem repetição, na primeira posição; catálogo inválido fica de fora sem levantar); a marca
`explica_a_falta` numa resposta `sem_dados` faz o motivo dela vencer o dos adaptadores anteriores, e o
`responder` a retira antes de gravar; componentes declarados de um host carregam `ssh_destino` e `porta`
do alvo.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_perguntas_do_componente.py
import pytest

import collect
from apoio_host import SAIDAS_PADRAO, runner_falso
from apoio_produto import gravar
from lib import adaptadores
from lib.cobertura import medir
from lib.coletores import host
from lib.orcamento import Prazo
from lib.perguntas import COMUNS, perguntas_do_componente
from test_leitura_servico import SHOW

# O que `do_papel` devolvia na v0.20.0: é EXATAMENTE isto que um componente de alvo docker recebe.
ANTES = {
    "entrada": ["entrada.volume_na_janela", "entrada.distribuicao_de_status", "entrada.latencia",
                "entrada.por_servico", "entrada.urls_mais_acessadas"],
    "fila": ["fila.filas", "fila.consumidores_por_fila", "fila.taxa_entrada_saida"],
    "app": ["app.cpu", "app.memoria", "app.disponibilidade_7d"],
    "banco": ["banco.conexoes", "banco.tamanho"],
    "cache": ["cache.memoria_usada", "cache.evicções", "cache.acerto"],
    "busca": [], "storage": [], "observabilidade": [],
    "maquina": ["maquina.cpu", "maquina.memoria", "maquina.disco", "maquina.disco_dias",
                "maquina.carga", "maquina.desde_o_boot"],
}
CATALOGO = """produto = "mariadb"

[cliente]
socket = 'mariadb -N -B -e "{sql}"'

[[pergunta]]
id = "banco.tamanho"
sql = "SELECT 1"
formato = "tsv"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }

[[pergunta]]
id = "cache.acerto"
sql = "SELECT 2"
formato = "tsv"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }
"""


@pytest.mark.parametrize("papel", sorted(ANTES))
def test_componente_de_alvo_docker_recebe_as_mesmas_perguntas_de_antes(papel, tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=CATALOGO)
    componente = {"nome": "x", "papel": papel, "produto": "mariadb",
                  "backup_pasta": "/var/backups"}
    assert [p["id"] for p in perguntas_do_componente(componente)] == ANTES[papel]


class Anota:
    ID = "anota"

    def __init__(self):
        self.perguntas = []

    def perguntar(self, pergunta, componente, contexto):
        self.perguntas.append((componente["nome"], pergunta))
        return {"pergunta": pergunta, "fonte": "anota", "valor": 1}


def test_coleta_de_alvo_docker_pergunta_o_mesmo_que_antes(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=CATALOGO)
    anota = Anota()

    def coletor(alvo, contexto):
        return {"saude": "🟢", "componentes": [{"nome": "db", "papel": "banco",
                                                 "papel_origem": "declarado", "produto": "mariadb"}]}

    collect.coletar_alvo({"nome": "prod", "tipo": "docker", "context": "prod"}, coletor,
                         {"timeout": 5, "orcamento": 30, "orcamento_urls": 30,
                          "at": "2026-11-13T10:00:00Z"}, [anota])
    assert [p for nome, p in anota.perguntas if nome == "db"] == ANTES["banco"]


def test_componente_de_host_ganha_as_comuns_e_o_backup():
    componente = {"nome": "mariadb", "papel": "banco", "origem": "unidade:mariadb.service",
                  "backup_pasta": "/var/backups/mysql"}
    assert [p["id"] for p in perguntas_do_componente(componente)] == \
        ["banco.conexoes", "banco.tamanho", *COMUNS, "banco.backup_idade"]


def test_catalogo_do_produto_entra_uma_vez_so(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=CATALOGO)
    componente = {"nome": "mariadb", "papel": "banco", "produto": "mariadb",
                  "origem": "unidade:mariadb.service"}
    assert [p["id"] for p in perguntas_do_componente(componente)] == \
        ["banco.conexoes", "banco.tamanho", *COMUNS, "cache.acerto"]


def test_catalogo_invalido_nao_derruba_e_fica_de_fora(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb='produto = "mariadb"\n')
    componente = {"nome": "mariadb", "papel": "banco", "produto": "mariadb",
                  "origem": "unidade:mariadb.service"}
    assert [p["id"] for p in perguntas_do_componente(componente)] == \
        ["banco.conexoes", "banco.tamanho", *COMUNS]


def test_cobertura_conta_as_comuns_e_tira_o_nao_medido_por_desenho():
    componente = {"nome": "qdrant", "papel": "busca", "papel_origem": "declarado",
                  "origem": "processo:qdrant", "respostas": [
                      {"pergunta": "servico.ativo", "fonte": "ssh", "valor": "ativo"},
                      {"pergunta": "servico.desde", "fonte": "ssh", "valor": 3.0},
                      {"pergunta": "servico.reinicios", "sem_dados": True, "nao_publica": True,
                       "motivo": "processo sem gerenciador"},
                      {"pergunta": "servico.memoria", "sem_dados": True, "motivo": "ps falhou"}]}
    assert medir({"componentes": [componente]}) == {
        "perguntadas": 3, "respondidas": 2, "pct": 67,
        "mudos": [{"componente": "qdrant", "pergunta": "servico.memoria", "motivo": "ps falhou"}]}


class SemMetricas:
    ID = "promql_falso"

    def perguntar(self, pergunta, componente, contexto):
        return {"pergunta": pergunta, "sem_dados": True,
                "motivo": "o componente não declara `metricas_url` no alvos.toml"}


class DoHost:
    ID = "produto_falso"

    def perguntar(self, pergunta, componente, contexto):
        return {"pergunta": pergunta, "sem_dados": True, "explica_a_falta": True,
                "motivo": "leitura não declarada"}


def test_motivo_do_adaptador_de_host_vence_o_do_exporter_e_a_marca_nao_fica():
    componente = {"nome": "mariadb", "papel": "banco", "respostas": [], "achados": []}
    collect.responder(componente, {"timeout": 5}, [SemMetricas(), DoHost()], Prazo(30))
    assert [r["motivo"] for r in componente["respostas"]] == ["leitura não declarada"] * 2
    assert all("explica_a_falta" not in r for r in componente["respostas"])


def test_componente_declarado_no_host_recebe_as_comuns_pelo_ssh(monkeypatch):
    saidas = {**SAIDAS_PADRAO, "servico_unidade:mariadb.service": SHOW}
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(saidas))
    alvo = {"nome": "banco-01", "tipo": "host", "ssh_destino": "root@banco-01",
            "componente": [{"nome": "mariadb", "papel": "banco",
                            "origem": "unidade:mariadb.service"}]}
    contexto = {"timeout": 20, "http_timeout": 8, "orcamento": 120, "orcamento_urls": 120,
                "janela": "24h", "at": "2026-11-13T10:00:00Z"}
    registro = collect.coletar_alvo(alvo, host.coletar, contexto, adaptadores.todos())
    mariadb = next(c for c in registro["componentes"] if c["nome"] == "mariadb")
    ativo = next(r for r in mariadb["respostas"] if r["pergunta"] == "servico.ativo")
    assert ativo == {"pergunta": "servico.ativo", "fonte": "ssh", "valor": "ativo"}
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_perguntas_do_componente.py`
Esperado: FALHA na coleta com `ImportError: cannot import name 'perguntas_do_componente' from 'lib.perguntas'`.

- [x] **Step 3: escrever a função e ligá-la**

No fim de `scripts/lib/perguntas.py`:

```python
def perguntas_do_componente(componente):
    """As perguntas DESTE componente, na ordem: as do papel; e, só se ele veio de um host
    (`origem`), as comuns, a idade do backup (com `backup_pasta`) e as do catálogo do produto.
    Pergunta repetida (`banco.tamanho` do papel e do catálogo) entra uma vez, na primeira posição.

    Componente de alvo `docker` não tem `origem`: recebe exatamente `do_papel` — um `produto`
    declarado ali não puxa catálogo nenhum. Catálogo inválido não derruba a coleta: as perguntas dele
    ficam de fora aqui, e o adaptador de produto diz o motivo nas que o papel já pergunta.
    """
    ids = list(ORDEM.get(componente.get("papel"), []))
    if componente.get("origem"):
        from lib import catalogo_produto

        ids += COMUNS
        if componente.get("backup_pasta"):
            ids.append("banco.backup_idade")
        try:
            catalogo = catalogo_produto.do_produto(componente.get("produto"))
        except catalogo_produto.CatalogoInvalido:
            catalogo = None
        if catalogo:
            ids += [p["id"] for p in catalogo["pergunta"]]
    vistos, saida = set(), []
    for id_ in ids:
        if id_ not in vistos:
            vistos.add(id_)
            saida.append(PERGUNTAS[id_])
    return saida
```

Em `scripts/collect.py`, em `responder`, troque

```python
    from lib.perguntas import do_papel

    for pergunta in do_papel(componente.get("papel", "app")):
```

por

```python
    from lib.perguntas import perguntas_do_componente

    # o padrão `app` é o que o `do_papel` recebia aqui; `peneirar_componentes` já garante `papel`
    for pergunta in perguntas_do_componente({"papel": "app", **componente}):
```

e, no mesmo laço, troque

```python
            if resposta is None or (resposta.get("nao_se_aplica")
                                    and not candidata.get("nao_se_aplica")):
                resposta = candidata
        if resposta is not None:
            resposta.pop("nao_se_aplica", None)   # marca interna, não é do relatório
```

por

```python
            # `explica_a_falta` vem do adaptador de produto num host: lá, "declare metricas_url"
            # mandaria configurar o que não precisa, e o motivo dele é o que diz o que fazer.
            if (resposta is None or candidata.get("explica_a_falta")
                    or (resposta.get("nao_se_aplica") and not candidata.get("nao_se_aplica"))):
                resposta = candidata
        if resposta is not None:
            resposta.pop("nao_se_aplica", None)   # marca interna, não é do relatório
            resposta.pop("explica_a_falta", None)
```

Em `scripts/lib/cobertura.py`, as duas funções passam a perguntar pelo componente:

```bash
sed -i -e 's/from lib.perguntas import do_papel/from lib.perguntas import perguntas_do_componente/' \
       -e 's/do_papel(componente.get("papel"))/perguntas_do_componente(componente)/' scripts/lib/cobertura.py
grep -c "perguntas_do_componente" scripts/lib/cobertura.py; grep -c "do_papel" scripts/lib/cobertura.py
```

Esperado: `4` e `0`.

Em `scripts/lib/coletores/host.py`, em `coletar`, troque

```python
    declarados = [dict(c, papel_origem="declarado", respostas=[], achados=[])
                  for c in alvo.get("componente", []) if c.get("nome") != alvo["nome"]]
```

por

```python
    # o destino ssh vai junto: é por ele que as perguntas comuns e as de produto chegam ao servidor
    declarados = [{**c, "papel_origem": "declarado", "ssh_destino": alvo["ssh_destino"],
                   "porta": alvo.get("porta"), "respostas": [], "achados": []}
                  for c in alvo.get("componente", []) if c.get("nome") != alvo["nome"]]
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_perguntas_do_componente.py tests/test_cobertura.py tests/test_collect_perguntas.py tests/test_responder_em_producao.py tests/test_coletor_host.py tests/test_coletor_host_descoberta.py`
Esperado: PASSA.

- [x] **Step 5: rodar a suíte inteira**

Rode: `timeout 900 .venv/bin/python -m pytest -q`
Esperado: tudo verde, incluindo `test_cobertura_mutacao.py` e `test_mutacao_do_papel.py`: os marcadores
deles (`if exigido and _GRAVIDADE…`, `    passe = identificar(`, `responder(componente, contexto,
adaptadores, prazo)`) não mudaram de texto.

---

## Fase 3 — o produto

### Task 9: credencial amarrada ao destino ssh

**Arquivos:**
- Alterar: `scripts/lib/credencial.py` (acrescentar no fim)
- Teste: `tests/test_credencial_ssh.py`

**Depende de:** Task 1 (o escape), Task 5

**Contrato que esta task publica:** `credencial.CredencialRecusada`; `credencial.CredencialSsh`
(amarrada a `(alvo, destino, porta, componente)`, não se imprime, não serializa) com
`.entrada(alvo, destino, porta, componente) -> str | None` (o `[client]` do arquivo de opções, só para a
mesma amarração); `credencial.de_componente_ssh(componente, alvo, destino, porta, ambiente=None) ->
CredencialSsh | None` (None quando `leitura` não é `senha`; levanta `CredencialFaltando` sem usuário,
sem `senha_env` ou com a variável ausente, e `CredencialRecusada` com quebra de linha ou NUL).

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_credencial_ssh.py
import copy
import pickle

import pytest

from lib import credencial

COMP = {"nome": "mariadb", "leitura": "senha", "usuario": "leitor", "senha_env": "SENHA_BANCO_01"}
AMARRA = ("banco-01", "root@10.0.0.10", None, "mariadb")


def _cred(senha='a"b\\c#d', **trocas):
    return credencial.de_componente_ssh({**COMP, **trocas}, "banco-01", "root@10.0.0.10", None,
                                        ambiente={"SENHA_BANCO_01": senha})


def test_entrada_e_o_client_com_aspas_e_barra_escapadas():
    assert _cred().entrada(*AMARRA) == '[client]\nuser="leitor"\npassword="a\\"b\\\\c#d"\n'


@pytest.mark.parametrize("outra", [("prod", "root@10.0.0.10", None, "mariadb"),
                                   ("banco-01", "root@10.0.0.99", None, "mariadb"),
                                   ("banco-01", "root@10.0.0.10", 2222, "mariadb"),
                                   ("banco-01", "root@10.0.0.10", None, "postgres")])
def test_fora_da_amarracao_nao_sai_nada(outra):
    assert _cred().entrada(*outra) is None


def test_nao_se_imprime_nem_serializa():
    cred = _cred(senha="MARCA-123")
    assert "MARCA-123" not in repr(cred) and "MARCA-123" not in str(cred)
    with pytest.raises(TypeError):
        pickle.dumps(cred)
    with pytest.raises(TypeError):
        copy.deepcopy(cred)


def test_sem_leitura_senha_nao_ha_credencial():
    assert credencial.de_componente_ssh({**COMP, "leitura": "socket"}, "banco-01",
                                        "root@10.0.0.10", None, ambiente={}) is None


def test_variavel_ausente_diz_o_nome_sem_repetir_o_usuario():
    with pytest.raises(credencial.CredencialFaltando) as erro:
        credencial.de_componente_ssh(COMP, "banco-01", "root@10.0.0.10", None, ambiente={})
    assert "SENHA_BANCO_01" in str(erro.value) and "leitor" not in str(erro.value)


@pytest.mark.parametrize("senha", ["linha1\nlinha2", "a\rb", "a\0b"])
def test_senha_com_quebra_de_linha_e_recusada_sem_aparecer(senha):
    with pytest.raises(credencial.CredencialRecusada) as erro:
        _cred(senha=senha)
    assert senha not in str(erro.value)


def test_usuario_com_quebra_de_linha_tambem_e_recusado():
    with pytest.raises(credencial.CredencialRecusada):
        _cred(usuario="lei\ntor")
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_credencial_ssh.py`
Esperado: FALHA com `AttributeError: module 'lib.credencial' has no attribute 'de_componente_ssh'`.

- [x] **Step 3: escrever o mínimo que faz passar**

No fim de `scripts/lib/credencial.py`:

```python
class CredencialRecusada(Exception):
    """Credencial que não vira arquivo de opções do cliente sem mudar de sentido."""


def _escapar(texto):
    """Valor entre aspas duplas no arquivo de opções do MySQL/MariaDB: `\\` e `"` escapados.

    O `#` fica como está: dentro das aspas ele é literal (o leitor só corta comentário fora delas), e
    `\\#` deixaria a barra dentro da senha — conferido no spike, referencias/spike-mysql-stdin.md."""
    return texto.replace("\\", "\\\\").replace('"', '\\"')


class CredencialSsh:
    """Amarrada a (alvo, destino ssh, porta, componente). Sai só como o `[client]` do arquivo de
    opções, para o stdin do ssh, e só para a mesma amarração. Não serializa e não se imprime."""

    __slots__ = ("alvo", "destino", "porta", "componente", "usuario", "_senha")

    def __init__(self, alvo, destino, porta, componente, usuario, senha):
        self.alvo = alvo
        self.destino = destino
        self.porta = porta
        self.componente = componente
        self.usuario = usuario
        self._senha = senha

    def entrada(self, alvo, destino, porta, componente):
        """O arquivo de opções com usuário e senha — None fora da amarração."""
        if (alvo, destino, porta, componente) != (self.alvo, self.destino, self.porta, self.componente):
            return None
        return (f'[client]\nuser="{_escapar(self.usuario)}"\n'
                f'password="{_escapar(self._senha)}"\n')  # noscan: molde; a senha vem da variável

    def __repr__(self):
        return f"<CredencialSsh componente={self.componente!r} alvo={self.alvo!r}>"

    __str__ = __repr__

    def __getstate__(self):
        raise TypeError("CredencialSsh não serializa: a senha não pode sair deste objeto por "
                        "pickle, copy ou __getstate__")


def de_componente_ssh(componente, alvo, destino, porta, ambiente=None):
    """A credencial de leitura de um componente de host, ou None quando ele não lê com senha.

    Usuário é obrigatório: sem ele, o cliente usaria o usuário do SSH (root) com a senha de outro."""
    if componente.get("leitura") != "senha":
        return None
    nome_da_variavel, usuario = componente.get("senha_env"), componente.get("usuario")
    if not usuario or not nome_da_variavel:
        raise CredencialFaltando(f"o componente {componente.get('nome')!r} declara leitura = "
                                 f'"senha" sem usuario e senha_env')
    ambiente = os.environ if ambiente is None else ambiente
    if nome_da_variavel not in ambiente:
        raise CredencialFaltando(
            f"o componente {componente.get('nome')!r} declara senha_env={nome_da_variavel!r}, mas "
            f"essa variável não está no ambiente — exporte-a antes de rodar a auditoria")
    senha = ambiente[nome_da_variavel]
    for texto in (usuario, senha):
        if any(c in texto for c in "\n\r\0"):
            raise CredencialRecusada(
                f"o usuário ou a senha do componente {componente.get('nome')!r} tem quebra de "
                f"linha, que o arquivo de opções do cliente não representa")
    return CredencialSsh(alvo, destino, porta, componente.get("nome"), usuario, senha)
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_credencial_ssh.py tests/test_credencial.py tests/test_seguranca_batch6.py`
Esperado: PASSA (o `credencial.py` já é um dos dois arquivos que podem ler o ambiente).

---

### Task 10: adaptador `produto_ssh`

**Arquivos:**
- Criar: `scripts/lib/adaptadores/produto_ssh.py`
- Alterar: `scripts/lib/adaptadores/__init__.py`
- Alterar: `tests/test_perguntas_novos_papeis.py` (soma de `produto_ssh.respondidas()`)
- Teste: `tests/test_adaptador_produto_ssh.py`, `tests/test_produto_novo_sem_codigo.py`

**Depende de:** Task 2, Task 3, Task 4, Task 8, Task 9

**Contrato que esta task publica:** `adaptadores.produto_ssh.ID = "produto_ssh"`, prioridade 38 no
`REGISTRO`; `produto_ssh.perguntar(pergunta, componente, contexto)` (fonte `"ssh:<produto>"`; toda falha
é `sem_dados` com `explica_a_falta`; erro marcado `nao_publica` no catálogo sai com `nao_publica`;
lista enumerada traz `"nota"` quando algum item foi pulado); `produto_ssh.respondidas(pasta=None) ->
set[str]`.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_adaptador_produto_ssh.py
import json

from apoio_host import Falha, runner_falso
from apoio_produto import MARIADB, PERGUNTA_DE_LISTA, QDRANT, gravar
from lib.adaptadores import produto_ssh

COMP = {"nome": "mariadb", "papel": "banco", "produto": "mariadb", "leitura": "socket",
        "origem": "unidade:mariadb.service", "ssh_destino": "root@banco-01", "porta": None}
SAIDAS = {"SHOW GLOBAL STATUS": "Threads_connected\t12\nSlow_queries\t7\n",
          "SELECT SUM(data_length + index_length) FROM information_schema.tables": "734003200\n"}


def _ctx():
    return {"timeout": 20, "cache": {}, "alvo": "banco-01", "at": "2026-11-13T10:00:00Z"}


def _perguntar(monkeypatch, pergunta, componente, saidas, **opcoes):
    monkeypatch.setattr(produto_ssh.runner, "run_ssh", runner_falso(saidas, **opcoes))
    return produto_ssh.perguntar(pergunta, componente, _ctx())


def test_socket_responde_conexoes_e_tamanho(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    assert _perguntar(monkeypatch, "banco.conexoes", COMP, SAIDAS) == {
        "pergunta": "banco.conexoes", "fonte": "ssh:mariadb", "valor": 12}
    assert _perguntar(monkeypatch, "banco.tamanho", COMP, SAIDAS)["valor"] == 734003200


def test_a_mesma_consulta_roda_uma_vez_para_duas_perguntas(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    chamadas = []
    monkeypatch.setattr(produto_ssh.runner, "run_ssh", runner_falso(SAIDAS, chamadas=chamadas))
    contexto = _ctx()
    produto_ssh.perguntar("banco.conexoes", COMP, contexto)
    produto_ssh.perguntar("banco.conexoes", COMP, contexto)
    assert chamadas == ["SHOW GLOBAL STATUS"]


def test_sem_leitura_declarada_diz_o_comando_e_explica_a_falta(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    resposta = _perguntar(monkeypatch, "banco.conexoes", {**COMP, "leitura": None}, SAIDAS)
    assert resposta["sem_dados"] and resposta["explica_a_falta"]
    assert "leitura não declarada" in resposta["motivo"] and "configurar.py leitura" in resposta["motivo"]


def test_leitura_nenhum_e_escolha_do_dono_e_nao_conta_como_lacuna(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    resposta = _perguntar(monkeypatch, "banco.conexoes", {**COMP, "leitura": "nenhum"}, SAIDAS)
    assert resposta["sem_dados"] and resposta["nao_publica"]


def test_erro_conhecido_do_catalogo_vira_o_motivo_dele(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    saidas = {"SHOW GLOBAL STATUS": Falha("ERROR 1698 (28000): Access denied for user "
                                          "'root'@'localhost'")}
    resposta = _perguntar(monkeypatch, "banco.conexoes", COMP, saidas)
    assert resposta["motivo"].startswith('o root não entra pelo socket: declare leitura = "senha"')


def test_erro_marcado_no_catalogo_sai_como_nao_medido_por_desenho(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    saidas = {"SHOW GLOBAL STATUS": Falha("ERROR 1381 (HY000): You are not using binary logging")}
    resposta = _perguntar(monkeypatch, "banco.conexoes", COMP, saidas)
    assert resposta["nao_publica"] and "binlog está desligado" in resposta["motivo"]


def test_cliente_ausente_e_o_codigo_127(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    saidas = {"SHOW GLOBAL STATUS": Falha("bash: mariadb: command not found", 127)}
    resposta = _perguntar(monkeypatch, "banco.conexoes", COMP, saidas)
    assert resposta["motivo"] == "o cliente de mariadb não está instalado onde o comando roda"


def test_erro_desconhecido_nao_repete_o_usuario(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    saidas = {"SHOW GLOBAL STATUS": Falha("ERROR 1227 (42000): Access denied for 'leitor'@'%'")}
    resposta = _perguntar(monkeypatch, "banco.conexoes", COMP, saidas)
    assert resposta["sem_dados"] and "leitor" not in resposta["motivo"]
    assert resposta["motivo"].startswith("o cliente de mariadb saiu com erro:")


def test_senha_vai_pela_entrada_e_nunca_pelas_vagas(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    monkeypatch.setenv("SENHA_DO_BANCO_TESTE", "MARCA-123")
    componente = {**COMP, "leitura": "senha", "usuario": "leitor",
                  "senha_env": "SENHA_DO_BANCO_TESTE"}
    registro = []
    resposta = _perguntar(monkeypatch, "banco.conexoes", componente, SAIDAS, registro=registro)
    assert resposta["valor"] == 12
    assert registro[0]["comando"] == 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
    assert registro[0]["entrada"] == '[client]\nuser="leitor"\npassword="MARCA-123"\n'
    assert "MARCA-123" not in json.dumps(registro[0]["vagas"]) and "MARCA-123" not in json.dumps(resposta)


def test_senha_recusada_pelo_banco(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    monkeypatch.setenv("SENHA_DO_BANCO_TESTE", "MARCA-123")
    componente = {**COMP, "leitura": "senha", "usuario": "leitor",
                  "senha_env": "SENHA_DO_BANCO_TESTE"}
    saidas = {"SHOW GLOBAL STATUS": Falha("ERROR 1045 (28000): Access denied for user 'leitor'")}
    resposta = _perguntar(monkeypatch, "banco.conexoes", componente, saidas)
    assert resposta["motivo"] == "o banco recusou o usuário e a senha declarados"


def test_variavel_de_senha_ausente_nao_repete_o_usuario(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    monkeypatch.delenv("SENHA_AUSENTE_TESTE", raising=False)
    componente = {**COMP, "leitura": "senha", "usuario": "leitor", "senha_env": "SENHA_AUSENTE_TESTE"}
    resposta = _perguntar(monkeypatch, "banco.conexoes", componente, SAIDAS)
    assert "não está no ambiente" in resposta["motivo"] and "leitor" not in resposta["motivo"]


def test_produto_sem_cliente_com_senha_fica_para_depois(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    componente = {**COMP, "nome": "qdrant", "papel": "busca", "produto": "qdrant",
                  "leitura": "senha", "usuario": "x", "senha_env": "Y"}
    resposta = _perguntar(monkeypatch, PERGUNTA_DE_LISTA, componente, {})
    assert "fica para uma próxima versão" in resposta["motivo"]


def test_leitura_container_exige_origem_container(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    resposta = _perguntar(monkeypatch, "banco.conexoes", {**COMP, "leitura": "container"}, SAIDAS)
    assert "precisa de componente com origem container:" in resposta["motivo"]


def test_leitura_container_passa_o_nome_do_container(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    componente = {**COMP, "leitura": "container", "origem": "container:banco-exemplo"}
    registro = []
    assert _perguntar(monkeypatch, "banco.conexoes", componente, SAIDAS, registro=registro)["valor"] == 12
    assert registro[0]["vagas"] == {"container": "banco-exemplo", "sql": "SHOW GLOBAL STATUS"}


def test_banco_de_host_sem_catalogo_diz_que_falta_catalogo(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    componente = {**COMP, "nome": "mongo", "produto": "mongo"}
    resposta = _perguntar(monkeypatch, "banco.conexoes", componente, {})
    assert resposta["motivo"] == "não medido: falta catálogo ou exporter para mongo"
    assert _perguntar(monkeypatch, "servico.ativo", componente, {})["nao_se_aplica"]


def test_componente_sem_origem_nao_e_deste_adaptador(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    assert _perguntar(monkeypatch, "banco.conexoes", {**COMP, "origem": None}, SAIDAS)["nao_se_aplica"]


COLECOES = json.dumps({"result": {"collections": [{"name": "docs"}, {"name": "a;b"},
                                                  {"name": "x y"}, {"name": "faq"}]}})


def test_colecao_fora_do_formato_e_pulada_e_dita(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    componente = {**COMP, "nome": "qdrant", "papel": "busca", "produto": "qdrant",
                  "origem": "unidade:qdrant.service", "portas": [6333, 6334]}
    saidas = {"/collections": COLECOES,
              "/collections/docs": json.dumps({"result": {"points_count": 1200}}),
              "/collections/faq": json.dumps({"result": {"points_count": 30}})}
    chamadas, registro = [], []
    resposta = _perguntar(monkeypatch, PERGUNTA_DE_LISTA, componente, saidas, chamadas=chamadas,
                          registro=registro)
    assert resposta["valor"] == [{"nome": "docs", "pontos": 1200}, {"nome": "faq", "pontos": 30}]
    assert resposta["nota"].startswith("2 item(ns) com nome fora do formato")
    assert chamadas == ["/collections", "/collections/docs", "/collections/faq"]
    assert {r["vagas"]["porta"] for r in registro} == {6333}


def test_erro_por_codigo_do_qdrant(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    componente = {**COMP, "nome": "qdrant", "papel": "busca", "produto": "qdrant"}
    resposta = _perguntar(monkeypatch, PERGUNTA_DE_LISTA, componente,
                          {"/collections": Falha("", 22)})
    assert resposta["motivo"] == "o Qdrant recusou a leitura (pede chave de API?)"
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_adaptador_produto_ssh.py`
Esperado: FALHA na coleta com `ImportError: cannot import name 'produto_ssh' from 'lib.adaptadores'`.

- [x] **Step 3: escrever o adaptador e registrá-lo**

```python
# scripts/lib/adaptadores/produto_ssh.py
"""Adaptador de produto num host: lê banco, cache e busca pelo cliente do próprio servidor, via SSH.

Tudo o que é específico de produto mora em `references/produtos-host/<produto>.toml` — o cliente por
modo de leitura, as consultas literais, o formato da saída e a extração: produto novo é um arquivo,
não um módulo. Prioridade 38, depois do `promql` e do `ssh` e antes do `exec_leitura`: exporter,
quando existe, continua vencendo.

Nunca levanta. Toda falha é `sem dados` com motivo, marcada `explica_a_falta`: num componente de host,
"declare metricas_url" mandaria o dono configurar algo de que ele não precisa. A senha vai só pela
entrada (stdin do ssh): nunca pelas vagas, pelo cache nem pela resposta.
"""
import copy
import re

from lib import catalogo_produto, credencial, extracao, redact, runner
from lib.perguntas import PERGUNTAS
from lib.vagas import COLECAO

ID = "produto_ssh"
SEM_CLIENTE = 127
FORA_DO_FORMATO = "a saída do cliente veio em formato inesperado"


class _Falha(Exception):
    def __init__(self, motivo, nao_publica=False):
        super().__init__(motivo)
        self.motivo, self.nao_publica = motivo, nao_publica


def _sem_dados(pergunta, motivo, **extra):
    return {"pergunta": pergunta, "sem_dados": True, "motivo": motivo, "explica_a_falta": True,
            **extra}


def _fora(pergunta, motivo):
    return {"pergunta": pergunta, "sem_dados": True, "motivo": motivo, "nao_se_aplica": True}


def respondidas(pasta=None):
    """As perguntas que algum catálogo de produto responde — para a trava de pergunta órfã."""
    return {p["id"] for catalogo in catalogo_produto.todos(pasta) for p in catalogo["pergunta"]}


def _vagas_do_cliente(molde, catalogo, componente):
    if "{container}" in molde:
        tipo, _, nome = str(componente.get("origem") or "").partition(":")
        if tipo != "container":
            raise _Falha('leitura = "container" precisa de componente com origem container:<nome>; '
                         f"este veio de {tipo or 'origem nenhuma'}")
        vagas = {"container": nome}
    else:
        vagas = {}
    if "{porta}" in molde:
        portas, padrao = componente.get("portas") or [], catalogo["porta_padrao"]
        vagas["porta"] = padrao if (not portas or padrao in portas) else min(portas)
    return vagas


def _motivo_da_falha(catalogo, modo, erro):
    texto, codigo = erro.get("reason") or "", erro.get("codigo")
    for item in catalogo["erro"]:
        if item.get("modo") not in (None, modo):
            continue
        if ("contem" in item and item["contem"] in texto) or ("codigo" in item
                                                             and item["codigo"] == codigo):
            return _Falha(item["motivo"], bool(item.get("nao_publica")))
    if codigo == SEM_CLIENTE:
        return _Falha(f"o cliente de {catalogo['produto']} não está instalado onde o comando roda")
    if codigo == 255:
        return _Falha(redact.scrub_text(texto))
    # o stderr do cliente costuma repetir o usuário (`'leitor'@'localhost'`): o que vem entre
    # aspas simples sai
    limpo = re.sub(r"'[^']*'", "'…'", redact.scrub_text(texto or "sem detalhe"))
    return _Falha(f"o cliente de {catalogo['produto']} saiu com erro: {limpo}")


def _texto(leitura, sql, componente, contexto, extra=None):
    """A saída de UMA consulta, em cache por componente e consulta — nunca pela senha."""
    vagas = {**leitura["vagas"], **(extra or {})}
    cache = contexto.setdefault("cache", {}).setdefault(ID, {})
    chave = (componente["nome"], leitura["molde"], sql, tuple(sorted(vagas.items())))
    if chave not in cache:
        erros = []
        saida = runner.run_ssh(componente["ssh_destino"], componente.get("porta"), leitura["molde"],
                               contexto["timeout"], erros, vagas={**vagas, "sql": sql},
                               entrada=leitura["entrada"])
        cache[chave] = (saida, erros[0] if erros else {"reason": "o comando falhou sem detalhe"})
    saida, erro = cache[chave]
    catalogo, modo = leitura["catalogo"], leitura["modo"]
    if saida is None:
        raise _motivo_da_falha(catalogo, modo, erro)
    for item in catalogo["erro"]:            # erro que o cliente escreve na SAÍDA com código 0
        if item.get("modo") in (None, modo) and item.get("contem") and item["contem"] in saida:
            raise _Falha(item["motivo"], bool(item.get("nao_publica")))
    return saida


def _parse(texto, declarada):
    doc = extracao.documento(texto, declarada["formato"], declarada["colunas"], declarada["separador"])
    if doc is None:
        raise _Falha(FORA_DO_FORMATO)
    return doc


def _montar(declarada, leitura, componente, contexto):
    """`(documento, nota)` da pergunta, ou `_Falha`."""
    enumerar = declarada["enumerar"]
    if enumerar is None:
        documento = {}
        for sql in declarada["sql"]:
            parte = _parse(_texto(leitura, sql, componente, contexto), declarada)
            if len(declarada["sql"]) == 1:
                return parte, None
            documento.update(parte)          # só `chave_valor` junta consultas (o catálogo garante)
        return documento, None
    indice = _parse(_texto(leitura, enumerar["sql"], componente, contexto), declarada)
    lista = extracao.ponteiro(indice, enumerar["lista"])
    if not isinstance(lista, list):
        raise _Falha("a lista a enumerar não veio na saída")
    nomes = [item.get(enumerar["campo"]) if isinstance(item, dict) else None for item in lista]
    aceitos = [n for n in nomes if isinstance(n, str) and COLECAO.fullmatch(n)]
    validos = sorted({n for n in nomes if isinstance(n, str) and COLECAO.fullmatch(n)})
    puladas = len(nomes) - len(aceitos)
    itens = [{"nome": nome, "resposta": _parse(_texto(leitura, declarada["sql"][0], componente,
                                                      contexto, {"colecao": nome}), declarada)}
             for nome in validos]
    nota = (f"{puladas} item(ns) com nome fora do formato aceito ficaram de fora, sem consulta"
            if puladas else None)
    return {"itens": itens}, nota


def perguntar(pergunta, componente, contexto):
    if not componente.get("origem") or not componente.get("ssh_destino"):
        return _fora(pergunta, "o componente não veio de um host")
    try:
        catalogo = catalogo_produto.do_produto(componente.get("produto"))
    except catalogo_produto.CatalogoInvalido as erro:
        return _sem_dados(pergunta, f"catálogo de produto inválido: {erro}")
    if catalogo is None:
        if PERGUNTAS.get(pergunta, {}).get("papel") == componente.get("papel"):
            return _sem_dados(pergunta, "não medido: falta catálogo ou exporter para "
                                        f"{componente.get('produto') or 'este produto'}")
        return _fora(pergunta, "nenhum catálogo de produto para este componente")
    declarada = next((p for p in catalogo["pergunta"] if p["id"] == pergunta), None)
    if declarada is None:
        return _fora(pergunta, f"o catálogo de {catalogo['produto']} não mede este dado")
    modo = componente.get("leitura")
    if not modo:
        return _sem_dados(pergunta, "leitura não declarada — rode `configurar.py leitura --alvo "
                                    f"<alvo> --componente {componente['nome']} --modo "
                                    "socket|senha|container|nenhum`")
    if modo == "nenhum":
        return _sem_dados(pergunta, 'leitura desligada pelo dono (leitura = "nenhum")',
                          nao_publica=True)
    molde = catalogo["cliente"].get(modo)
    if molde is None:
        depois = "; leitura com senha fica para uma próxima versão neste produto" if modo == "senha" else ""
        return _sem_dados(pergunta, f"o catálogo de {catalogo['produto']} não tem cliente para "
                                    f"leitura {modo}{depois}")
    destino, porta, alvo = componente["ssh_destino"], componente.get("porta"), contexto.get("alvo")
    try:
        vagas = _vagas_do_cliente(molde, catalogo, componente)
        cred = credencial.de_componente_ssh(componente, alvo, destino, porta)
        entrada = cred.entrada(alvo, destino, porta, componente["nome"]) if cred else None
        leitura = {"catalogo": catalogo, "modo": modo, "molde": molde, "vagas": vagas,
                   "entrada": entrada}
        documento, nota = _montar(declarada, leitura, componente, contexto)
        valor = extracao.extrair(copy.deepcopy(documento), declarada["extracao"])
    except _Falha as falha:
        return _sem_dados(pergunta, falha.motivo, **({"nao_publica": True} if falha.nao_publica else {}))
    except (credencial.CredencialFaltando, credencial.CredencialRecusada) as erro:
        return _sem_dados(pergunta, str(erro))
    except extracao.ExtracaoInvalida as erro:
        return _sem_dados(pergunta, f"o catálogo de {catalogo['produto']} não casa com a saída: {erro}")
    if PERGUNTAS[pergunta]["forma"] != "lista":
        valor = valor.get("valor")
        if valor is None:
            return _sem_dados(pergunta, FORA_DO_FORMATO)
    resposta = {"pergunta": pergunta, "fonte": f"ssh:{catalogo['produto']}", "valor": valor}
    if nota:
        resposta["nota"] = nota
    return resposta
```

Em `scripts/lib/adaptadores/__init__.py`, troque o import e o registro:

```python
from lib.adaptadores import admin_http, exec_leitura, logql, produto_ssh, promql, ssh

# `logql` antes do `promql`: nesta pergunta o motivo dele é o que explica a falta, não o "o
# exporter não expõe". Nas outras ele passa a vez sem custo.
REGISTRO = {
    admin_http.ID: {"modulo": admin_http, "prioridade": 20},
    logql.ID: {"modulo": logql, "prioridade": 25},
    promql.ID: {"modulo": promql, "prioridade": 30},
    # depois do promql: o exporter de nó, quando existe, é a fonte mais rica da máquina
    ssh.ID: {"modulo": ssh, "prioridade": 35},
    # cliente do produto no host: depois do exporter (que, quando existe, vence) e antes do exec
    produto_ssh.ID: {"modulo": produto_ssh, "prioridade": 38},
    exec_leitura.ID: {"modulo": exec_leitura, "prioridade": 40},
}
```

Em `tests/test_perguntas_novos_papeis.py`, logo depois da linha `respondidas |= set(ssh.RESPONDE)` da
Task 7, acrescente:

```python
    from lib.adaptadores import produto_ssh
    respondidas |= produto_ssh.respondidas()   # catálogos de produto em references/produtos-host/
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_adaptador_produto_ssh.py tests/test_perguntas_novos_papeis.py tests/test_seguranca_batch6.py`
Esperado: PASSA (o `produto_ssh.py` não tem a palavra `environ`: quem lê a variável é o `credencial.py`).

- [x] **Step 5: escrever o teste da restrição 3 (produto novo sem código)**

```python
# tests/test_produto_novo_sem_codigo.py
"""Restrição 3 do spec: produto novo é medido escrevendo arquivos, sem mudar `.py`.

O produto é inventado; o `produtos.toml` e o catálogo são temporários. O runner é o de verdade, com o
subprocesso trocado: é ele que prova que o molde novo foi aceito sem lista no código."""
from unittest import mock

from lib import catalogo_produto, produtos
from lib.adaptadores import produto_ssh
from lib.perguntas import perguntas_do_componente

PRODUTOS = '[[produto]]\nnome = "kvexemplo"\nprocesso = ["kvexemplod"]\nkind = "cache"\n'
CATALOGO = """produto = "kvexemplo"

[cliente]
socket = 'kvexemplo-cli --raw "{sql}"'

[[pergunta]]
id = "cache.memoria_usada"
sql = "STATS memory"
formato = "chave_valor"
separador = "="
campos = { valor = "/bytes_em_uso" }
transformar = { valor = "bytes" }
"""


def test_produto_inventado_e_medido_so_com_arquivos(tmp_path, monkeypatch):
    (tmp_path / "produtos.toml").write_text(PRODUTOS, encoding="utf-8")
    pasta = tmp_path / "produtos-host"
    pasta.mkdir()
    (pasta / "kvexemplo.toml").write_text(CATALOGO, encoding="utf-8")
    monkeypatch.setattr(produtos, "ARQUIVO", tmp_path / "produtos.toml")
    monkeypatch.setattr(catalogo_produto, "PASTA", pasta)
    # papel `app`: `cache.memoria_usada` não é do papel, então só o catálogo a faz ser perguntada
    componente = {"nome": "kv", "papel": "app", "produto": "kvexemplo",
                  "origem": "processo:kvexemplod", "leitura": "socket",
                  "ssh_destino": "root@10.0.0.10", "porta": None}
    saida = mock.Mock(stdout="bytes_em_uso=2048\nchaves=10\n", returncode=0, stderr="")

    with mock.patch("lib.runner.subprocess.run", return_value=saida) as rodou:
        resposta = produto_ssh.perguntar("cache.memoria_usada", componente,
                                         {"timeout": 20, "cache": {}, "alvo": "kv-01"})

    assert resposta == {"pergunta": "cache.memoria_usada", "fonte": "ssh:kvexemplo", "valor": 2048}
    assert rodou.call_args[0][0][-1] == 'kvexemplo-cli --raw "STATS memory"'
    assert "cache.memoria_usada" in [p["id"] for p in perguntas_do_componente(componente)]
```

- [x] **Step 6: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_produto_novo_sem_codigo.py`
Esperado: PASSA (o teste não depende de código novo além do desta task: se falhar, o defeito está no
adaptador, no carregador ou no `vagas.preencher`, nunca numa lista de produtos no código).

- [x] **Step 7: rodar a suíte inteira**

Rode: `timeout 900 .venv/bin/python -m pytest -q`
Esperado: tudo verde. Atenção: `test_coletor_host_descoberta` passa a ter o `produto_ssh` na fila de
adaptadores; sem catálogo de verdade ainda, ele responde "não medido: falta catálogo ou exporter" nas
perguntas de `banco`, o que não muda os achados que aquele teste confere.

---

### Task 11: os cinco catálogos e as perguntas que só eles respondem

**Arquivos:**
- Criar: `references/produtos-host/mariadb.toml`
- Criar: `references/produtos-host/mysql.toml`
- Criar: `references/produtos-host/postgres.toml`
- Criar: `references/produtos-host/redis.toml`
- Criar: `references/produtos-host/qdrant.toml`
- Alterar: `scripts/lib/perguntas.py` (cinco perguntas no bloco de host, depois de `banco.backup_idade`)
- Teste: `tests/test_catalogos_de_produto.py`

**Depende de:** Task 10

**Contrato que esta task publica:** perguntas `banco.tamanho_por_banco` (lista, bytes),
`banco.uso_de_conexoes` (escalar, %), `banco.consultas_lentas` (escalar), `banco.binlog` (lista, bytes),
`busca.colecoes` (lista: nome, pontos, status) — todas opcionais e fora de `ORDEM`; os cinco catálogos.
Os produtos já existem em `references/produtos.toml` (Task 9 da parte A): nenhum bloco novo lá.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_catalogos_de_produto.py
import json
import pathlib

import pytest

from apoio_host import Falha, runner_falso
from lib import catalogo_produto
from lib.adaptadores import produto_ssh

STATUS = "Aborted_clients\t3\nSlow_queries\t7\nThreads_connected\t12\n"
VARIAVEIS = "max_connections\t151\nversion\t11.4.2-MariaDB\n"
SQL_TAMANHO = "SELECT SUM(data_length + index_length) FROM information_schema.tables"
SQL_POR_BANCO = ("SELECT table_schema, SUM(data_length + index_length) FROM "
                 "information_schema.tables GROUP BY table_schema")
SAIDAS_MARIADB = {
    "SHOW GLOBAL STATUS": STATUS, "SHOW GLOBAL VARIABLES": VARIAVEIS,
    SQL_TAMANHO: "734003200\n",
    SQL_POR_BANCO: "app\t700000000\ninformation_schema\tNULL\nmysql\t34003200\n",
    "SHOW BINARY LOGS": "binlog.000001\t1048576\nbinlog.000002\t2048\n",
}
SAIDAS_POSTGRES = {
    "SELECT count(*) FROM pg_stat_activity": "9\n",
    "SELECT count(*), current_setting('max_connections') FROM pg_stat_activity": "9|100\n",
    "SELECT sum(pg_database_size(datname)) FROM pg_database": "52428800\n",
    "SELECT datname, pg_database_size(datname) FROM pg_database WHERE NOT datistemplate":
        "app|41943040\npostgres|10485760\n",
}
INFO = ("# Server\r\nredis_version:7.2.4\r\n\r\n# Memory\r\nused_memory:1048576\r\n\r\n"
        "# Stats\r\nkeyspace_hits:90\r\nkeyspace_misses:10\r\nevicted_keys:3\r\n")
SAIDAS_QDRANT = {
    "/collections": json.dumps({"result": {"collections": [{"name": "docs"}, {"name": "faq"}]},
                                "status": "ok", "time": 0.0001}),
    "/collections/docs": json.dumps({"result": {"status": "green", "points_count": 1200,
                                                "segments_count": 2}, "status": "ok"}),
    "/collections/faq": json.dumps({"result": {"status": "yellow", "points_count": 30},
                                    "status": "ok"}),
}


def _respostas(monkeypatch, produto, saidas, papel="banco", **campos):
    componente = {"nome": produto, "papel": papel, "produto": produto, "leitura": "socket",
                  "origem": f"processo:{produto}", "ssh_destino": "root@10.0.0.10", "porta": None,
                  **campos}
    monkeypatch.setattr(produto_ssh.runner, "run_ssh", runner_falso(saidas))
    contexto = {"timeout": 20, "cache": {}, "alvo": "banco-01"}
    catalogo = catalogo_produto.do_produto(produto)
    return {p["id"]: produto_ssh.perguntar(p["id"], componente, contexto)
            for p in catalogo["pergunta"]}


def _valores(monkeypatch, produto, saidas, **opcoes):
    respostas = _respostas(monkeypatch, produto, saidas, **opcoes)
    mudas = {p: r["motivo"] for p, r in respostas.items() if r.get("sem_dados")}
    assert mudas == {}
    return {p: r["valor"] for p, r in respostas.items()}


def test_os_cinco_catalogos_carregam():
    assert {c["produto"] for c in catalogo_produto.todos()} == \
        {"mariadb", "mysql", "postgres", "redis", "qdrant"}


def test_senha_so_no_mariadb_e_no_mysql():
    assert {c["produto"] for c in catalogo_produto.todos() if "senha" in c["cliente"]} == \
        {"mariadb", "mysql"}


def test_mariadb_responde_as_seis_perguntas(monkeypatch):
    assert _valores(monkeypatch, "mariadb", SAIDAS_MARIADB) == {
        "banco.conexoes": 12, "banco.consultas_lentas": 7, "banco.uso_de_conexoes": 7.95,
        "banco.tamanho": 734003200,
        "banco.tamanho_por_banco": [{"nome": "app", "bytes": 700000000},
                                    {"nome": "mysql", "bytes": 34003200},
                                    {"nome": "information_schema", "bytes": None}],
        "banco.binlog": [{"nome": "binlog.000001", "bytes": 1048576},
                         {"nome": "binlog.000002", "bytes": 2048}],
    }


def test_mysql_usa_o_binario_mysql_com_as_mesmas_consultas(monkeypatch):
    mysql = catalogo_produto.do_produto("mysql")
    assert {m.split()[0] for m in mysql["cliente"].values()} == {"mysql", "docker"}
    assert _valores(monkeypatch, "mysql", SAIDAS_MARIADB)["banco.uso_de_conexoes"] == 7.95


def test_binlog_desligado_e_nao_medido_por_desenho(monkeypatch):
    saidas = {**SAIDAS_MARIADB, "SHOW BINARY LOGS": Falha(
        "ERROR 1381 (HY000) at line 1: You are not using binary logging")}
    binlog = _respostas(monkeypatch, "mariadb", saidas)["banco.binlog"]
    assert binlog["nao_publica"] and binlog["motivo"] == "o binlog está desligado neste servidor"


def test_postgres_separa_por_barra_vertical(monkeypatch):
    assert _valores(monkeypatch, "postgres", SAIDAS_POSTGRES) == {
        "banco.conexoes": 9, "banco.uso_de_conexoes": 9.0, "banco.tamanho": 52428800,
        "banco.tamanho_por_banco": [{"nome": "app", "bytes": 41943040},
                                    {"nome": "postgres", "bytes": 10485760}]}


def test_postgres_sem_root_diz_o_motivo(monkeypatch):
    saidas = {"SELECT count(*) FROM pg_stat_activity": Falha(
        "runuser: may not be used by non-root users")}
    conexoes = _respostas(monkeypatch, "postgres", saidas)["banco.conexoes"]
    assert "exige o SSH como root" in conexoes["motivo"]


def test_redis_le_o_info(monkeypatch):
    assert _valores(monkeypatch, "redis", {"INFO": INFO}, papel="cache") == {
        "cache.memoria_usada": 1048576, "cache.evicções": 3, "cache.acerto": 90.0}


def test_redis_com_senha_fica_para_depois(monkeypatch):
    respostas = _respostas(monkeypatch, "redis", {"INFO": "NOAUTH Authentication required.\n"},
                           papel="cache")
    assert "Redis pede senha" in respostas["cache.memoria_usada"]["motivo"]


def test_qdrant_enumera_as_colecoes(monkeypatch):
    assert _valores(monkeypatch, "qdrant", SAIDAS_QDRANT, papel="busca", portas=[6333, 6334]) == {
        "busca.colecoes": [{"nome": "docs", "pontos": 1200, "status": "green"},
                           {"nome": "faq", "pontos": 30, "status": "yellow"}]}


def test_qdrant_com_chave_fica_para_depois(monkeypatch):
    respostas = _respostas(monkeypatch, "qdrant", {"/collections": Falha("", 22)}, papel="busca")
    assert "chave de API" in respostas["busca.colecoes"]["motivo"]


@pytest.mark.parametrize("pergunta", ["banco.tamanho_por_banco", "banco.uso_de_conexoes",
                                      "banco.consultas_lentas", "banco.binlog", "busca.colecoes"])
def test_perguntas_de_catalogo_sao_opcionais_e_fora_do_papel(pergunta):
    from lib.perguntas import ORDEM, PERGUNTAS

    assert PERGUNTAS[pergunta]["opcional"] and PERGUNTAS[pergunta]["limiar"] is None
    assert not any(pergunta in ids for ids in ORDEM.values())


FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "produto" / "mariadb"


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="spike da Task 1 não executado")
def test_saidas_reais_do_spike_viram_numero(monkeypatch):
    ler = lambda nome: (FIXTURES / nome).read_text(encoding="utf-8")
    saidas = {"SHOW GLOBAL STATUS": ler("status.txt"), "SHOW GLOBAL VARIABLES": ler("variaveis.txt"),
              SQL_TAMANHO: ler("tamanho.txt"), SQL_POR_BANCO: ler("tamanho_por_banco.txt")}
    respostas = _respostas(monkeypatch, "mariadb", saidas)
    for pergunta in ("banco.conexoes", "banco.consultas_lentas", "banco.uso_de_conexoes",
                     "banco.tamanho", "banco.tamanho_por_banco"):
        assert not respostas[pergunta].get("sem_dados"), (pergunta, respostas[pergunta])
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_catalogos_de_produto.py`
Esperado: FALHA — `test_os_cinco_catalogos_carregam` com `set() != {…}` e os outros com
`TypeError: 'NoneType' object is not subscriptable` (não há catálogo).

- [x] **Step 3: registrar as perguntas e escrever os catálogos**

Em `scripts/lib/perguntas.py`, logo depois da pergunta `banco.backup_idade` (Task 7):

```python
# Só os catálogos de produto (references/produtos-host/) respondem estas: nenhum exporter conhecido
# as publica no mesmo formato. Sem faixa e sem limiar; os achados vêm de lib/limites_produto.py.
_p("banco.tamanho_por_banco", "banco", "Tamanho por banco", "lista", unidade="bytes",
   desempate="nome", opcional=True, na_ordem=False)
_p("banco.uso_de_conexoes", "banco", "Conexões em uso contra o limite", "escalar", unidade="%",
   opcional=True, na_ordem=False)
_p("banco.consultas_lentas", "banco", "Consultas lentas desde o início", "escalar",
   unidade="consultas", opcional=True, na_ordem=False)
_p("banco.binlog", "banco", "Arquivos de binlog", "lista", unidade="bytes", desempate="nome",
   opcional=True, na_ordem=False)
_p("busca.colecoes", "busca", "Coleções", "lista", unidade="pontos", desempate="nome",
   opcional=True, na_ordem=False)
```

```toml
# references/produtos-host/mariadb.toml
# Leitura do MariaDB pelo cliente do próprio servidor, via SSH — só SHOW e SELECT.
#
# `mariadb` e não `mysql`: o binário `mariadb` existe desde a 10.4 e o apelido `mysql` não é
# garantido nas versões novas (spike, Task 1). `-N -B` tira o cabeçalho e separa por TAB. A consulta
# entra no lugar de `{sql}`, dentro das aspas; o carregador recusa nela aspas duplas, `$`, crase, `\`,
# `%`, `<`, `>` e quebra de linha.
produto = "mariadb"

[cliente]
socket = 'mariadb -N -B -e "{sql}"'
# a senha vai pelo stdin do ssh, num `[client]` que o cliente lê como arquivo de opções
senha = 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
container = 'docker exec {container} mariadb -N -B -e "{sql}"'

[[erro]]
contem = "ERROR 1698"
motivo = 'o root não entra pelo socket: declare leitura = "senha" com um usuário de leitura'

[[erro]]
contem = "ERROR 1045"
modo = "senha"
motivo = "o banco recusou o usuário e a senha declarados"

[[erro]]
contem = "ERROR 1045"
motivo = 'o banco pediu senha: declare leitura = "senha" com um usuário de leitura'

[[erro]]
contem = "ERROR 2002"
motivo = "o banco não respondeu no socket padrão (o serviço está no ar?)"

[[erro]]
contem = "You are not using binary logging"
motivo = "o binlog está desligado neste servidor"
nao_publica = true

[[pergunta]]
id = "banco.conexoes"
sql = "SHOW GLOBAL STATUS"
formato = "chave_valor"
campos = { valor = "/Threads_connected" }
transformar = { valor = "inteiro" }

[[pergunta]]
id = "banco.consultas_lentas"
sql = "SHOW GLOBAL STATUS"
formato = "chave_valor"
campos = { valor = "/Slow_queries" }
transformar = { valor = "inteiro" }

# as duas leituras juntas: conexões abertas contra o limite configurado
[[pergunta]]
id = "banco.uso_de_conexoes"
sql = ["SHOW GLOBAL STATUS", "SHOW GLOBAL VARIABLES"]
formato = "chave_valor"
derivar = { valor = { tipo = "percentual_de", numerador = "/Threads_connected", denominador = "/max_connections" } }

[[pergunta]]
id = "banco.tamanho"
sql = "SELECT SUM(data_length + index_length) FROM information_schema.tables"
formato = "tsv"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }
transformar = { valor = "bytes" }

[[pergunta]]
id = "banco.tamanho_por_banco"
sql = "SELECT table_schema, SUM(data_length + index_length) FROM information_schema.tables GROUP BY table_schema"
formato = "tsv"
colunas = ["nome", "bytes"]
lista = "/linhas"
campos = { nome = "/nome", bytes = "/bytes" }
transformar = { bytes = "bytes" }
ordenar_por = "bytes"
desempate = "nome"

[[pergunta]]
id = "banco.binlog"
sql = "SHOW BINARY LOGS"
formato = "tsv"
colunas = ["nome", "bytes"]
lista = "/linhas"
campos = { nome = "/nome", bytes = "/bytes" }
transformar = { bytes = "bytes" }
```

```toml
# references/produtos-host/mysql.toml
# Leitura do MySQL pelo cliente do próprio servidor, via SSH — só SHOW e SELECT. As consultas são as
# do MariaDB; o MySQL 8 traz uma terceira coluna em SHOW BINARY LOGS, que o tsv ignora.
produto = "mysql"

[cliente]
socket = 'mysql -N -B -e "{sql}"'
senha = 'mysql --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
container = 'docker exec {container} mysql -N -B -e "{sql}"'

[[erro]]
contem = "ERROR 1698"
motivo = 'o root não entra pelo socket: declare leitura = "senha" com um usuário de leitura'

[[erro]]
contem = "ERROR 1045"
modo = "senha"
motivo = "o banco recusou o usuário e a senha declarados"

[[erro]]
contem = "ERROR 1045"
motivo = 'o banco pediu senha: declare leitura = "senha" com um usuário de leitura'

[[erro]]
contem = "ERROR 2002"
motivo = "o banco não respondeu no socket padrão (o serviço está no ar?)"

[[erro]]
contem = "You are not using binary logging"
motivo = "o binlog está desligado neste servidor"
nao_publica = true

[[pergunta]]
id = "banco.conexoes"
sql = "SHOW GLOBAL STATUS"
formato = "chave_valor"
campos = { valor = "/Threads_connected" }
transformar = { valor = "inteiro" }

[[pergunta]]
id = "banco.consultas_lentas"
sql = "SHOW GLOBAL STATUS"
formato = "chave_valor"
campos = { valor = "/Slow_queries" }
transformar = { valor = "inteiro" }

[[pergunta]]
id = "banco.uso_de_conexoes"
sql = ["SHOW GLOBAL STATUS", "SHOW GLOBAL VARIABLES"]
formato = "chave_valor"
derivar = { valor = { tipo = "percentual_de", numerador = "/Threads_connected", denominador = "/max_connections" } }

[[pergunta]]
id = "banco.tamanho"
sql = "SELECT SUM(data_length + index_length) FROM information_schema.tables"
formato = "tsv"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }
transformar = { valor = "bytes" }

[[pergunta]]
id = "banco.tamanho_por_banco"
sql = "SELECT table_schema, SUM(data_length + index_length) FROM information_schema.tables GROUP BY table_schema"
formato = "tsv"
colunas = ["nome", "bytes"]
lista = "/linhas"
campos = { nome = "/nome", bytes = "/bytes" }
transformar = { bytes = "bytes" }
ordenar_por = "bytes"
desempate = "nome"

[[pergunta]]
id = "banco.binlog"
sql = "SHOW BINARY LOGS"
formato = "tsv"
colunas = ["nome", "bytes"]
lista = "/linhas"
campos = { nome = "/nome", bytes = "/bytes" }
transformar = { bytes = "bytes" }
```

```toml
# references/produtos-host/postgres.toml
# Leitura do Postgres como o usuário de sistema `postgres` (peer, sem senha), via `runuser` — que
# exige o SSH como root. `-X` ignora o .psqlrc, `-A -t` tira alinhamento e cabeçalho; o separador é
# `|`. Sem consultas lentas (exigiria pg_stat_statements) nem binlog, que o Postgres não tem.
produto = "postgres"

[cliente]
socket = 'runuser -u postgres -- psql -X -A -t -c "{sql}"'
container = 'docker exec -u postgres {container} psql -X -A -t -c "{sql}"'

[[erro]]
contem = "may not be used by non-root users"
motivo = "a leitura do Postgres entra como o usuário postgres pelo runuser, que exige o SSH como root"

[[erro]]
contem = "user postgres does not exist"
motivo = "o usuário de sistema postgres não existe neste servidor"

[[erro]]
contem = "could not connect to server"
motivo = "o Postgres não respondeu no socket padrão (o serviço está no ar?)"

[[erro]]
contem = "connection to server"
motivo = "o Postgres não respondeu no socket padrão (o serviço está no ar?)"

[[pergunta]]
id = "banco.conexoes"
sql = "SELECT count(*) FROM pg_stat_activity"
formato = "tsv"
separador = "|"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }
transformar = { valor = "inteiro" }

[[pergunta]]
id = "banco.uso_de_conexoes"
sql = "SELECT count(*), current_setting('max_connections') FROM pg_stat_activity"
formato = "tsv"
separador = "|"
colunas = ["usadas", "limite"]
derivar = { valor = { tipo = "percentual_de", numerador = "/linhas/0/usadas", denominador = "/linhas/0/limite" } }

[[pergunta]]
id = "banco.tamanho"
sql = "SELECT sum(pg_database_size(datname)) FROM pg_database"
formato = "tsv"
separador = "|"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }
transformar = { valor = "bytes" }

[[pergunta]]
id = "banco.tamanho_por_banco"
sql = "SELECT datname, pg_database_size(datname) FROM pg_database WHERE NOT datistemplate"
formato = "tsv"
separador = "|"
colunas = ["nome", "bytes"]
lista = "/linhas"
campos = { nome = "/nome", bytes = "/bytes" }
transformar = { bytes = "bytes" }
ordenar_por = "bytes"
desempate = "nome"
```

```toml
# references/produtos-host/redis.toml
# Leitura do Redis pelo `redis-cli` do próprio servidor: só o comando INFO, que traz memória,
# descartes e acertos de uma vez. Redis com senha fica para uma próxima versão.
produto = "redis"

[cliente]
socket = 'redis-cli "{sql}"'
container = 'docker exec {container} redis-cli "{sql}"'

# o redis-cli sai com código 0 e escreve o NOAUTH na saída: o adaptador procura o texto nos dois lugares
[[erro]]
contem = "NOAUTH"
motivo = "o Redis pede senha; leitura de Redis com senha fica para uma próxima versão"

[[erro]]
contem = "Connection refused"
motivo = "o Redis não respondeu em 127.0.0.1:6379 (o serviço está no ar?)"

[[pergunta]]
id = "cache.memoria_usada"
sql = "INFO"
formato = "chave_valor"
separador = ":"
campos = { valor = "/used_memory" }
transformar = { valor = "bytes" }

[[pergunta]]
id = "cache.evicções"
sql = "INFO"
formato = "chave_valor"
separador = ":"
campos = { valor = "/evicted_keys" }
transformar = { valor = "inteiro" }

# hits / (hits + misses), desde o início do processo; sem leitura nenhuma não há taxa (None, não 0%)
[[pergunta]]
id = "cache.acerto"
sql = "INFO"
formato = "chave_valor"
separador = ":"
derivar = { valor = { tipo = "percentual_de", numerador = "/keyspace_hits", denominador_soma = ["/keyspace_hits", "/keyspace_misses"] } }
```

```toml
# references/produtos-host/qdrant.toml
# Leitura do Qdrant pela API HTTP local, com o `curl` do servidor: a lista de coleções e, para cada
# uma, pontos e status. `-f` faz HTTP de erro virar código 22. Qdrant com chave de API fica para uma
# próxima versão. A porta é a de `portas` do componente quando a padrão não está lá.
produto = "qdrant"
porta_padrao = 6333

[cliente]
socket = 'curl -s -f -m 5 "http://127.0.0.1:{porta}{sql}"'

[[erro]]
codigo = 22
motivo = "o Qdrant recusou a leitura (pede chave de API?); Qdrant com chave fica para uma próxima versão"

[[erro]]
codigo = 7
motivo = "o Qdrant não respondeu em 127.0.0.1 na porta declarada"

[[erro]]
codigo = 28
motivo = "o Qdrant não respondeu em 5 segundos"

# nome de coleção fora de [A-Za-z0-9_-]{1,64} é pulado, sem consulta, e a resposta diz quantos
[[pergunta]]
id = "busca.colecoes"
formato = "json"
enumerar = { sql = "/collections", lista = "/result/collections", campo = "name" }
sql = "/collections/{colecao}"
lista = "/itens"
campos = { nome = "/nome", pontos = "/resposta/result/points_count", status = "/resposta/result/status" }
transformar = { nome = "texto", pontos = "inteiro", status = "texto" }
ordenar_por = "pontos"
desempate = "nome"
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_catalogos_de_produto.py tests/test_perguntas_novos_papeis.py tests/test_perguntas.py`
Esperado: PASSA (com o spike executado, `test_saidas_reais_do_spike_viram_numero` roda; sem ele, sai
`skipped`). Se ele falhar, o formato real diverge do catálogo: ajuste o catálogo, nunca a fixture, e
registre em "Ajustes".

- [x] **Step 5: rodar a suíte inteira**

Rode: `timeout 900 .venv/bin/python -m pytest -q`
Esperado: tudo verde. A trava de pergunta órfã agora fecha pelas duas somas (`ssh.RESPONDE` e
`produto_ssh.respondidas()`); `test_coletor_host_descoberta` ganha as perguntas do catálogo do
`mariadb` no componente declarado, todas `sem dados` com "leitura não declarada", sem mudar os achados.

---

### Task 12: `configurar.py leitura`

**Arquivos:**
- Alterar: `scripts/lib/gravacao_alvos.py` (`_intervalo_do_alvo`, `inserir`, `acrescentar_campos`)
- Alterar: `scripts/configurar.py` (`_campos_de_leitura`, `leitura`, subparser)
- Teste: `tests/test_configurar_leitura.py`

**Depende de:** Task 5, Task 11

**Contrato que esta task publica:** `gravacao_alvos.acrescentar_campos(texto, alvo, componente, campos:
list[tuple[str, str | int]]) -> str` (levanta `GravacaoInvalida`: alvo ou componente inexistente, campo
que o bloco já tem, valor fora de `[A-Za-z0-9._/@-]`); `configurar.main(["leitura", "--alvo", A,
"--componente", C, "--modo", M, ...])` → 0 gravado, 2 recusado (arquivo intacto).

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_configurar_leitura.py
import difflib

import pytest

import configurar
from lib import alvos
from lib import gravacao_alvos as g

TEXTO = ('# meus alvos\n[[alvo]]\nnome = "banco-01"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
         '\n# descoberto em 2026-11-13\n[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\n'
         'produto = "mariadb"\nportas = [3306]\norigem = "unidade:mariadb.service"\n'
         '\n[[alvo.componente]]\nnome = "qdrant"\npapel = "busca"\nproduto = "qdrant"\n'
         'portas = [6333]\norigem = "unidade:qdrant.service"\n'
         '\n[[alvo]]\nnome = "srv-exemplo"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
         '[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\nproduto = "mariadb"\n'
         'origem = "unidade:mariadb.service"\n')
SENHA = ["--modo", "senha", "--usuario", "leitor", "--senha-env", "SENHA_BANCO_01"]


def _arquivo(tmp_path):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(TEXTO, encoding="utf-8")
    caminho.chmod(0o600)
    return caminho


def _leitura(caminho, *extra, componente="mariadb", alvo="banco-01"):
    return configurar.main(["leitura", "--alvo", alvo, "--componente", componente, *extra,
                            "--infra", str(caminho)])


def test_acrescenta_logo_depois_do_nome_do_componente_certo_e_so_acrescenta():
    novo = g.acrescentar_campos(TEXTO, "banco-01", "mariadb", [("leitura", "socket"),
                                                               ("backup_max_dias", 7)])
    diff = [l for l in difflib.ndiff(TEXTO.splitlines(), novo.splitlines()) if l[:1] in "+-"]
    assert diff == ['+ leitura = "socket"', "+ backup_max_dias = 7"]
    assert novo.index('leitura = "socket"') < novo.index('nome = "qdrant"')


def test_componente_ou_alvo_inexistente_e_recusado():
    with pytest.raises(g.GravacaoInvalida, match="componente 'redis' não encontrado"):
        g.acrescentar_campos(TEXTO, "banco-01", "redis", [("leitura", "socket")])
    with pytest.raises(g.GravacaoInvalida, match="alvo 'nao-existe' não encontrado"):
        g.acrescentar_campos(TEXTO, "nao-existe", "mariadb", [("leitura", "socket")])


def test_campo_que_ja_existe_e_recusado():
    com_leitura = g.acrescentar_campos(TEXTO, "banco-01", "mariadb", [("leitura", "socket")])
    with pytest.raises(g.GravacaoInvalida, match="edite o alvos.toml à mão"):
        g.acrescentar_campos(com_leitura, "banco-01", "mariadb", [("leitura", "nenhum")])


@pytest.mark.parametrize("valor", ['a"b', "a\nb", "a b", "a\\b"])
def test_valor_fora_do_formato_nao_vira_toml(valor):
    with pytest.raises(g.GravacaoInvalida, match="fora do formato gravável"):
        g.acrescentar_campos(TEXTO, "banco-01", "mariadb", [("usuario", valor)])


def test_gravar_pelo_cli_deixa_o_bak_e_o_arquivo_relido(tmp_path):
    caminho = _arquivo(tmp_path)
    codigo = _leitura(caminho, *SENHA, "--backup-pasta", "/var/backups/mysql",
                      "--backup-max-dias", "7")
    texto = caminho.read_text(encoding="utf-8")
    assert codigo == 0
    assert ('nome = "mariadb"\nleitura = "senha"\nusuario = "leitor"\nsenha_env = "SENHA_BANCO_01"\n'
            'backup_pasta = "/var/backups/mysql"\nbackup_max_dias = 7\npapel = "banco"\n') in texto
    assert texto.endswith('[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\n'
                          'produto = "mariadb"\norigem = "unidade:mariadb.service"\n')
    assert (tmp_path / "alvos.toml.bak").read_text(encoding="utf-8") == TEXTO
    componente = alvos.ler(caminho)[0][0]["componente"][0]
    assert (componente["leitura"], componente["backup_max_dias"]) == ("senha", 7)


def test_segunda_gravacao_e_recusada_e_nao_muda_nada(tmp_path, capsys):
    caminho = _arquivo(tmp_path)
    assert _leitura(caminho, "--modo", "socket") == 0
    gravado = caminho.read_text(encoding="utf-8")
    assert _leitura(caminho, "--modo", "nenhum") == 2
    assert caminho.read_text(encoding="utf-8") == gravado
    assert "já tem leitura" in capsys.readouterr().err


@pytest.mark.parametrize("extra,mensagem", [
    (["--modo", "senha"], "--modo senha exige --usuario e --senha-env"),
    (["--modo", "socket", "--usuario", "leitor"], "--usuario e --senha-env só valem com --modo senha"),
    (["--modo", "senha", "--usuario", "leitor", "--senha-env", "minuscula"], "--senha-env é o NOME"),
    (["--modo", "senha", "--usuario", "lei tor", "--senha-env", "S"], "--usuario só com"),
    (["--modo", "container"], "--modo container só vale"),
    (["--modo", "socket", "--backup-pasta", "/var/../etc"], "--backup-pasta precisa ser caminho absoluto"),
    (["--modo", "socket", "--backup-max-dias", "7"], "--backup-max-dias precisa de --backup-pasta"),
    (["--modo", "socket", "--backup-pasta", "/b", "--backup-max-dias", "0"], "--backup-max-dias vai de 1 a 365"),
])
def test_entrada_ruim_e_recusada_antes_de_tocar_no_arquivo(tmp_path, capsys, extra, mensagem):
    caminho = _arquivo(tmp_path)
    assert _leitura(caminho, *extra) == 2
    assert caminho.read_text(encoding="utf-8") == TEXTO
    assert not (tmp_path / "alvos.toml.bak").exists()
    assert mensagem in capsys.readouterr().err


def test_senha_em_produto_sem_cliente_com_senha_e_recusada(tmp_path, capsys):
    caminho = _arquivo(tmp_path)
    assert _leitura(caminho, *SENHA, componente="qdrant") == 2
    assert "não tem leitura com senha" in capsys.readouterr().err
    assert caminho.read_text(encoding="utf-8") == TEXTO


def test_alvo_ou_componente_inexistente_no_cli(tmp_path, capsys):
    caminho = _arquivo(tmp_path)
    assert _leitura(caminho, "--modo", "socket", componente="redis") == 2
    assert "não tem componente 'redis'" in capsys.readouterr().err


def test_releitura_que_diverge_restaura_o_original(tmp_path, monkeypatch):
    caminho = _arquivo(tmp_path)
    invasor = '\n[[alvo]]\nnome = "invasor"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
    monkeypatch.setattr(g, "acrescentar_campos", lambda texto, *a: texto + invasor)
    assert _leitura(caminho, "--modo", "socket") == 2
    assert caminho.read_text(encoding="utf-8") == TEXTO
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_configurar_leitura.py`
Esperado: FALHA — `AttributeError: module 'lib.gravacao_alvos' has no attribute 'acrescentar_campos'`
e, nos testes de CLI, `invalid choice: 'leitura'`.

- [x] **Step 3: escrever a inserção de campos**

Em `scripts/lib/gravacao_alvos.py`, substitua a função `inserir` inteira por estas três (a busca do
bloco do alvo vira função, para as duas gravações usarem a mesma), e acrescente as constantes logo
depois de `PAPEL = re.compile(...)`:

```python
CABECALHO_COMPONENTE = re.compile(r"^\s*\[\[\s*alvo\s*\.\s*componente\s*\]\]\s*(#.*)?$")
CHAVE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=")
CAMPOS_DE_LEITURA = ("leitura", "usuario", "senha_env", "backup_pasta", "backup_max_dias")
# Alfabeto fechado: o valor vai entre aspas no TOML, então aspas, `\`, espaço e quebra de linha não
# entram. Quem precisa de outro caractere edita o arquivo à mão.
TEXTO_GRAVAVEL = re.compile(r"[A-Za-z0-9._/@-]{1,255}")
```

```python
def _intervalo_do_alvo(linhas, alvo):
    """`(início, fim)` do bloco `[[alvo]]` cujo `nome` é este; fim exclusivo, no próximo `[[alvo]]`."""
    inicios = [i for i, l in enumerate(linhas) if CABECALHO.match(l)]
    for k, inicio in enumerate(inicios):
        fim = inicios[k + 1] if k + 1 < len(inicios) else len(linhas)
        for j in range(inicio + 1, fim):
            if linhas[j].lstrip().startswith("["):
                break
            achado = NOME.match(linhas[j])
            if achado:
                if achado.group(1) == alvo:
                    return inicio, fim
                break
    raise GravacaoInvalida(f"alvo {alvo!r} não encontrado no arquivo")


def inserir(texto, alvo, componentes, data):
    for c in componentes:
        _validar(c)
    linhas = texto.splitlines(keepends=True)
    inicio, pos = _intervalo_do_alvo(linhas, alvo)
    while pos > inicio + 1 and (not linhas[pos - 1].strip() or linhas[pos - 1].lstrip().startswith("#")):
        pos -= 1
    antes = "".join(linhas[:pos])
    if antes and not antes.endswith("\n"):
        antes += "\n"
    blocos = "\n".join(_bloco(c, data) for c in componentes)
    return antes + "\n" + blocos + ("\n" if pos < len(linhas) else "") + "".join(linhas[pos:])


def _linha(chave, valor):
    if chave not in CAMPOS_DE_LEITURA:
        raise GravacaoInvalida(f"campo {chave!r} não é de leitura")
    if type(valor) is int:
        return f"{chave} = {valor}\n"
    if isinstance(valor, str) and TEXTO_GRAVAVEL.fullmatch(valor):
        return f'{chave} = "{valor}"\n'
    raise GravacaoInvalida(f"valor de {chave!r} fora do formato gravável")


def acrescentar_campos(texto, alvo, componente, campos):
    """Acrescenta `chave = valor` logo depois do `nome` do `[[alvo.componente]]` daquele componente,
    dentro daquele alvo. Só acrescenta: campo que o bloco já tem é recusado — quem troca valor é o
    dono, à mão. Toda linha que existia continua igual e na mesma ordem."""
    novas = "".join(_linha(chave, valor) for chave, valor in campos)
    linhas = texto.splitlines(keepends=True)
    inicio, fim = _intervalo_do_alvo(linhas, alvo)
    for de in [i for i in range(inicio, fim) if CABECALHO_COMPONENTE.match(linhas[i])]:
        ate = next((j for j in range(de + 1, fim) if linhas[j].lstrip().startswith("[")), fim)
        nome_em = next((j for j in range(de + 1, ate) if NOME.match(linhas[j])), None)
        if nome_em is None or NOME.match(linhas[nome_em]).group(1) != componente:
            continue
        existentes = {CHAVE.match(linhas[j]).group(1) for j in range(de + 1, ate)
                      if CHAVE.match(linhas[j])}
        repetidos = sorted(existentes & {chave for chave, _ in campos})
        if repetidos:
            raise GravacaoInvalida(f"o componente {componente!r} já tem {', '.join(repetidos)}; "
                                   f"para trocar, edite o alvos.toml à mão")
        linha_do_nome = linhas[nome_em] if linhas[nome_em].endswith("\n") else linhas[nome_em] + "\n"
        return "".join(linhas[:nome_em]) + linha_do_nome + novas + "".join(linhas[nome_em + 1:])
    raise GravacaoInvalida(f"componente {componente!r} não encontrado no alvo {alvo!r}")
```

- [x] **Step 4: escrever o subcomando**

Em `scripts/configurar.py`, antes de `def main`:

```python
USUARIO_DE_LEITURA = re.compile(r"[A-Za-z0-9._@-]{1,64}")
NOME_DE_VARIAVEL = re.compile(r"[A-Z_][A-Z0-9_]{0,63}")


def _campos_de_leitura(args, componente):
    """Os `(campo, valor)` a gravar, ou ValueError com a frase para o dono. Nada aqui toca arquivo."""
    from lib import catalogo_produto
    from lib.vagas import pasta_valida

    campos = [("leitura", args.modo)]
    if args.modo == "senha":
        if not args.usuario or not args.senha_env:
            raise ValueError("--modo senha exige --usuario e --senha-env (o NOME da variável de "
                             "ambiente, nunca a senha)")
        catalogo = catalogo_produto.do_produto(componente.get("produto"))
        if catalogo is None or "senha" not in catalogo["cliente"]:
            raise ValueError(f"o produto {componente.get('produto')!r} não tem leitura com senha "
                             f"nesta versão (só MariaDB e MySQL)")
        if not USUARIO_DE_LEITURA.fullmatch(args.usuario):
            raise ValueError("--usuario só com letras, números, ponto, hífen, sublinhado e @")
        if not NOME_DE_VARIAVEL.fullmatch(args.senha_env):
            raise ValueError("--senha-env é o NOME de uma variável de ambiente, em maiúsculas "
                             "(ex.: SENHA_BANCO_01)")
        campos += [("usuario", args.usuario), ("senha_env", args.senha_env)]
    elif args.usuario or args.senha_env:
        raise ValueError("--usuario e --senha-env só valem com --modo senha")
    if args.modo == "container" and not str(componente.get("origem") or "").startswith("container:"):
        raise ValueError("--modo container só vale para componente com origem container:<nome>")
    if args.backup_pasta is not None:
        if not pasta_valida(args.backup_pasta):
            raise ValueError("--backup-pasta precisa ser caminho absoluto só com letras, números, "
                             "ponto, hífen, sublinhado e barra, sem `..`")
        campos.append(("backup_pasta", args.backup_pasta))
    if args.backup_max_dias is not None:
        if args.backup_pasta is None and not componente.get("backup_pasta"):
            raise ValueError("--backup-max-dias precisa de --backup-pasta")
        if not 1 <= args.backup_max_dias <= 365:
            raise ValueError("--backup-max-dias vai de 1 a 365")
        campos.append(("backup_max_dias", args.backup_max_dias))
    return campos


def leitura(args) -> int:
    from lib import gravacao_alvos

    try:
        alvo, infra = _alvo_host(args)
        componente = next((c for c in alvo["componente"] if c["nome"] == args.componente), None)
        if componente is None:
            raise alvos_mod.AlvoInvalido(f"o alvo {args.alvo!r} não tem componente "
                                         f"{args.componente!r}")
        campos = _campos_de_leitura(args, componente)
        exigir_pasta_protegida(infra)
        original = Path(infra).read_text(encoding="utf-8")
        novo = gravacao_alvos.acrescentar_campos(original, alvo["nome"], componente["nome"], campos)
    except (alvos_mod.AlvoInvalido, ConfigInvalida, ValueError, gravacao_alvos.GravacaoInvalida) as erro:
        print(str(erro), file=sys.stderr)
        return EXIT_ERRO
    backup = Path(f"{infra}.bak")
    backup.touch(mode=0o600, exist_ok=True)
    backup.chmod(0o600)
    backup.write_text(original, encoding="utf-8")
    novos = dict(campos)
    esperado = [{**a, "componente": [{**c, **novos} if (a["nome"] == alvo["nome"]
                                                        and c["nome"] == componente["nome"]) else c
                                     for c in a["componente"]]}
                for a in alvos_mod.ler(infra)[0]]
    try:
        Path(infra).write_text(novo, encoding="utf-8")
        if alvos_mod.ler(infra)[0] != esperado:
            raise gravacao_alvos.GravacaoInvalida("a releitura não trouxe exatamente o pedido")
    except (gravacao_alvos.GravacaoInvalida, alvos_mod.AlvoInvalido) as erro:
        Path(infra).write_text(original, encoding="utf-8")
        print(f"gravação desfeita: {erro}. O arquivo voltou ao original; cópia em {backup}",
              file=sys.stderr)
        return EXIT_ERRO
    print(f"leitura de {componente['nome']} gravada ({', '.join(c for c, _ in campos)}); cópia "
          f"anterior em {backup}")
    return EXIT_OK
```

Em `main`, depois do subparser `descobrir`:

```python
    lei = sub.add_parser("leitura", help="grava como a skill lê um componente de host")
    lei.add_argument("--alvo", required=True)
    lei.add_argument("--componente", required=True)
    lei.add_argument("--modo", required=True, choices=alvos_mod.LEITURAS)
    lei.add_argument("--usuario", default=None)
    lei.add_argument("--senha-env", dest="senha_env", default=None,
                     help="o NOME da variável de ambiente, nunca a senha")
    lei.add_argument("--backup-pasta", dest="backup_pasta", default=None)
    lei.add_argument("--backup-max-dias", dest="backup_max_dias", type=int, default=None)
    lei.add_argument("--infra", default=None)
    lei.add_argument("--padrao", default=None)
    lei.add_argument("--projeto", default=None)
```

e troque o dicionário do `return` por:

```python
    return {"config": explicar, "migrar": migrar, "aceitar": aceitar, "alvos": sugerir,
            "ignorar": ignorar, "descobrir": descobrir, "leitura": leitura}[args.comando](args)
```

- [x] **Step 5: rodar e confirmar que passa**

Rode, **a partir da raiz da skill**:
`.venv/bin/python -m pytest -q tests/test_configurar_leitura.py tests/test_gravacao_alvos.py tests/test_configurar_descobrir.py tests/test_configurar.py tests/test_configurar_escrita.py`
Esperado: PASSA (os testes de `inserir` da parte A continuam verdes com a busca extraída).

---

### Task 13: achados `backup_atrasado` e `conexoes_no_limite`

**Arquivos:**
- Criar: `scripts/lib/limites_produto.py`
- Alterar: `scripts/collect.py` (`coletar_alvo`, o laço de `capacidade`)
- Alterar: `scripts/lib/regras.py`
- Alterar: `tests/test_regras.py` (import e as duas somas)
- Criar: `references/remediacao/backup_atrasado.md`
- Criar: `references/remediacao/conexoes_no_limite.md`
- Teste: `tests/test_limites_produto.py`

**Depende de:** Task 11

**Por que não é limiar:** as perguntas são opcionais, e `lib/catalogo.py` recusa limiar em opcional. O
achado nasce de um produtor no molde de `lib/capacidade.py`, que só lê resposta com número: pasta
vazia, leitura que falhou ou componente sem `backup_pasta` nunca viram `backup_atrasado`.

**Contrato que esta task publica:** `limites_produto.achados(componente) -> list[dict]`;
`limites_produto.REGRAS_PRODUZIDAS = {"backup_atrasado", "conexoes_no_limite"}`;
`BACKUP_MAX_DIAS_PADRAO = 2`; `LIMITE_DE_CONEXOES = 80`; `backup_atrasado` (high) quando
`banco.backup_idade` > `backup_max_dias`; `conexoes_no_limite` (medium) quando
`banco.uso_de_conexoes` > 80.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_limites_produto.py
from lib import limites_produto


def _banco(respostas, **campos):
    return {"nome": "mariadb", "papel": "banco", **campos,
            "respostas": [{"pergunta": p, "fonte": "ssh:mariadb", "valor": v}
                          for p, v in respostas.items()]}


def test_backup_acima_do_limite_padrao_e_high():
    assert limites_produto.achados(_banco({"banco.backup_idade": 3})) == [{
        "regra": "backup_atrasado", "severidade": "high", "objeto": "mariadb", "valor": 3,
        "detalhe": "backup mais novo com 3 dias; o limite é 2"}]


def test_backup_no_limite_ou_semanal_declarado_nao_acusa():
    assert limites_produto.achados(_banco({"banco.backup_idade": 2})) == []
    assert limites_produto.achados(_banco({"banco.backup_idade": 6}, backup_max_dias=7)) == []
    assert limites_produto.achados(_banco({"banco.backup_idade": 8}, backup_max_dias=7))[0][
        "detalhe"] == "backup mais novo com 8 dias; o limite é 7"


def test_conexoes_acima_de_80_por_cento_e_medium():
    assert limites_produto.achados(_banco({"banco.uso_de_conexoes": 85.71})) == [{
        "regra": "conexoes_no_limite", "severidade": "medium", "objeto": "mariadb",
        "valor": 85.71, "detalhe": "85.71% das conexões permitidas em uso"}]
    assert limites_produto.achados(_banco({"banco.uso_de_conexoes": 80})) == []


def test_sem_dados_e_valor_que_nao_e_numero_nunca_viram_achado():
    sem = {"nome": "mariadb", "papel": "banco", "respostas": [
        {"pergunta": "banco.backup_idade", "sem_dados": True, "motivo": "a pasta está vazia",
         "valor": 99}]}
    assert limites_produto.achados(sem) == []
    assert limites_produto.achados(_banco({"banco.backup_idade": True})) == []
    assert limites_produto.achados(_banco({"banco.uso_de_conexoes": "90"})) == []
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest -q tests/test_limites_produto.py`
Esperado: FALHA na coleta com `ImportError: cannot import name 'limites_produto' from 'lib'`.

- [x] **Step 3: escrever o produtor e ligá-lo**

```python
# scripts/lib/limites_produto.py
"""Achados de produto em host: backup atrasado e conexões no limite.

No molde de `lib/capacidade.py`: as perguntas são opcionais (o catálogo recusa limiar em opcional), e
só resposta COM número produz achado. Pasta vazia, leitura que falhou ou banco sem `backup_pasta`
nunca viram `backup_atrasado`: "não consegui ver" não é "está atrasado".
"""
import math

BACKUP_MAX_DIAS_PADRAO = 2
LIMITE_DE_CONEXOES = 80
REGRAS_PRODUZIDAS = {"backup_atrasado", "conexoes_no_limite"}


def _medida(componente, pergunta):
    for resposta in componente.get("respostas", []):
        valor = resposta.get("valor")
        if resposta.get("pergunta") == pergunta and not resposta.get("sem_dados") \
                and type(valor) in (int, float) and math.isfinite(valor):
            return valor
    return None


def achados(componente):
    saida = []
    idade = _medida(componente, "banco.backup_idade")
    maximo = componente.get("backup_max_dias") or BACKUP_MAX_DIAS_PADRAO
    if idade is not None and idade > maximo:
        saida.append({"regra": "backup_atrasado", "severidade": "high", "objeto": componente["nome"],
                      "valor": idade, "detalhe": f"backup mais novo com {idade} dias; o limite é {maximo}"})
    uso = _medida(componente, "banco.uso_de_conexoes")
    if uso is not None and uso > LIMITE_DE_CONEXOES:
        saida.append({"regra": "conexoes_no_limite", "severidade": "medium",
                      "objeto": componente["nome"], "valor": uso,
                      "detalhe": f"{uso}% das conexões permitidas em uso"})
    return saida
```

Em `scripts/collect.py`, em `coletar_alvo`, troque

```python
    from lib import capacidade
    for componente in registro["componentes"]:
        componente["achados"].extend(capacidade.achados(componente))
```

por

```python
    from lib import capacidade, limites_produto
    for componente in registro["componentes"]:
        componente["achados"].extend(capacidade.achados(componente))
        componente["achados"].extend(limites_produto.achados(componente))
```

Em `scripts/lib/regras.py`, depois da linha de `memoria_sem_folga`:

```python
    # --- produto em host (lib/limites_produto.py): só resposta com número produz achado
    "backup_atrasado":          {"severidade_padrao": "high",    "origem": "produto", "esperada": False},
    "conexoes_no_limite":       {"severidade_padrao": "medium",  "origem": "produto", "esperada": False},
```

Em `tests/test_regras.py`, troque o import `from lib import capacidade, perguntas, rules` por
`from lib import capacidade, limites_produto, perguntas, rules`; no fim de
`test_todo_produtor_declara_suas_regras_no_registro`, acrescente

```python
    assert limites_produto.REGRAS_PRODUZIDAS <= set(REGRAS), \
        sorted(limites_produto.REGRAS_PRODUZIDAS - set(REGRAS))
```

e, em `test_o_registro_nao_guarda_regra_que_ninguem_produz`, troque a soma por

```python
    produzidas = (rules.REGRAS_PRODUZIDAS | coletor_http.REGRAS_PRODUZIDAS
                  | perguntas.REGRAS_PRODUZIDAS | capacidade.REGRAS_PRODUZIDAS
                  | coletor_host.REGRAS_PRODUZIDAS | limites_produto.REGRAS_PRODUZIDAS)
```

- [x] **Step 4: escrever as duas remediações**

```markdown
---
regra: backup_atrasado
titulo: Backup do banco mais velho que o limite
severidade_padrao: high
---

## Por que importa

O backup mais novo da pasta declarada tem mais dias do que o limite definido para este banco
(`backup_max_dias`, 2 por padrão). Se o banco se perder hoje — disco, exclusão errada, invasão —, tudo
o que foi gravado desde aquele backup se perde junto. Rotina de backup que para de rodar não avisa:
costuma ser descoberta no dia em que se precisa dela.

## Como resolver

1. Veja se a rotina rodou: `systemctl list-timers` ou `crontab -l` no servidor (é leitura).
2. Rotina com erro: o log dela (`journalctl -u <unit>` ou o arquivo que o cron grava) mostra o motivo;
   disco cheio e senha trocada são os mais comuns.
3. Rotina que grava em outra pasta: corrija `backup_pasta` no `alvos.toml`.
4. Backup semanal de propósito: declare `backup_max_dias = 7` no componente.
5. Depois de corrigir, rode um backup na hora e confira que o arquivo novo aparece na pasta.

## Como confirmar

A próxima auditoria mostra a idade do backup dentro do limite e o achado some. Na mão:
`ls -l --time-style=full-iso <pasta>`.

## Quando NÃO fazer

Não apague backups antigos para "organizar" a pasta enquanto o novo não estiver confirmado: o antigo é
o único que existe. E backup que nunca foi restaurado é suposição: teste a restauração num ambiente
separado antes de contar com ele.
```

```markdown
---
regra: conexoes_no_limite
titulo: Conexões do banco acima de 80% do limite
severidade_padrao: medium
---

## Por que importa

Mais de 80% das conexões permitidas (`max_connections`) estão abertas. Quando o limite chega, o banco
recusa conexão nova ("Too many connections") e a aplicação cai, mesmo com CPU e memória sobrando. Um
pico de acesso ou um worker que não devolve a conexão bastam para cruzar o limite.

## Como resolver

1. Veja quem está conectado: `SHOW PROCESSLIST` no MariaDB/MySQL, `pg_stat_activity` no Postgres (é
   leitura).
2. Conexão ociosa acumulada: confira o pool da aplicação (tamanho máximo, tempo ocioso) e se o código
   devolve a conexão.
3. Várias instâncias da aplicação, cada uma com o seu pool: some os máximos; o total precisa caber no
   limite.
4. Se o uso é legítimo, aumente `max_connections` com memória para isso (cada conexão reserva buffer),
   ou ponha um pooler (ProxySQL, PgBouncer) na frente.

## Como confirmar

A próxima auditoria mostra o uso abaixo de 80% e o achado some. Na mão: `Threads_connected` em
`SHOW GLOBAL STATUS` contra `max_connections` em `SHOW GLOBAL VARIABLES`.

## Quando NÃO fazer

Não derrube conexões em massa para baixar o número: são transações da aplicação em andamento. E não
suba `max_connections` sem olhar a memória: o banco que não cai por conexão cai por falta de memória.
```

Salve em `references/remediacao/backup_atrasado.md` e `references/remediacao/conexoes_no_limite.md`.

- [x] **Step 5: rodar os testes da task e a suíte inteira**

Rode: `.venv/bin/python -m pytest -q tests/test_limites_produto.py tests/test_regras.py tests/test_remediacao.py tests/test_markdown_da_remediacao.py`
Esperado: PASSA — `test_toda_regra_que_vira_achado_tem_remediacao` (restrição 5) e
`test_nao_ha_remediacao_orfa` com as duas regras e os dois arquivos.

Rode: `timeout 900 .venv/bin/python -m pytest -q`
Esperado: tudo verde.

---

### Task 14: ponta a ponta — a senha nunca sai do stdin

**Arquivos:**
- Teste: `tests/test_host_produto_ponta_a_ponta.py`

**Depende de:** Task 12, Task 13

**Contrato que esta task publica:** nenhum código novo; o teste prova a restrição 1 pelo caminho real
(`collect.main` → coletor `host` → adaptadores de verdade → `runner.run_ssh` de verdade), trocando só o
`subprocess.run`.

- [x] **Step 1: escrever o teste**

```python
# tests/test_host_produto_ponta_a_ponta.py
"""Restrição 1 do spec, pelo caminho real: a senha marcada vai pelo stdin do ssh e não aparece em
nenhum argv nem no report.json. Só o subprocesso é de mentira."""
import json
from unittest import mock

import collect

MARCA = "MARCA7f3e"
SENHA = f'{MARCA}"#\\fim'          # aspas, `#` e barra: o escape é exercitado junto
ALVOS = """[[alvo]]
nome = "banco-01"
tipo = "host"
ssh_destino = "root@10.0.0.10"

[[alvo.componente]]
nome = "mariadb"
papel = "banco"
produto = "mariadb"
portas = [3306]
origem = "unidade:mariadb.service"
leitura = "senha"
usuario = "leitor"
senha_env = "SENHA_DO_BANCO_TESTE"
backup_pasta = "/var/backups/mysql"
"""
# (trecho do comando remoto, stdout, código, stderr) — o primeiro trecho contido no comando vence
RESPOSTAS = [
    ("id -un", "root\n", 0, ""),
    ("uname -sr", "Linux 6.1.0-18-amd64\n", 0, ""),
    ("cat /etc/os-release", 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n', 0, ""),
    ("df -P -k", "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                 "/dev/vda1 50000000 10000000 40000000 20% /\n", 0, ""),
    ("cat /proc/meminfo", "MemTotal: 4000000 kB\nMemAvailable: 2000000 kB\n", 0, ""),
    ("cat /proc/loadavg", "0.40 0.80 0.60 1/100 1\n", 0, ""),
    ("nproc", "2\n", 0, ""),
    ("cat /proc/uptime", "259200.00 10.00\n", 0, ""),
    ("systemctl show mariadb.service", "ActiveState=active\nActiveEnterTimestampMonotonic="
                                       "86400000000\nNRestarts=0\nMemoryCurrent=524288000\n", 0, ""),
    ("systemctl list-units", "mariadb.service loaded active running MariaDB\n", 0, ""),
    ("ss -ltnpH", 'LISTEN 0 80 127.0.0.1:3306 0.0.0.0:* users:(("mariadbd",pid=812,fd=22))\n', 0, ""),
    ("docker ps", "", 0, ""),
    ("SHOW GLOBAL STATUS", "Slow_queries\t7\nThreads_connected\t12\n", 0, ""),
    ("SHOW GLOBAL VARIABLES", "max_connections\t14\n", 0, ""),
    ("SHOW BINARY LOGS", "", 1, "ERROR 1381 (HY000) at line 1: You are not using binary logging"),
    ("GROUP BY table_schema", "app\t700000000\n", 0, ""),
    ("information_schema.tables", "700000000\n", 0, ""),
    ("ls -l --time-style=full-iso /var/backups/mysql",
     "total 4\n-rw-r--r-- 1 root root 10 2026-11-08 03:00:00.000000000 +0000 "
     "dump-2026-11-08.sql.gz\n", 0, ""),
]


def test_senha_so_pelo_stdin_e_o_resto_do_host_medido(tmp_path, monkeypatch):
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(ALVOS, encoding="utf-8")
    (tmp_path / "alvos.toml").chmod(0o600)
    (tmp_path / "config.toml").write_text('alvos = ["banco-01"]\n', encoding="utf-8")
    monkeypatch.setenv("SENHA_DO_BANCO_TESTE", SENHA)
    chamadas = []

    def falso(cmd, **kwargs):
        chamadas.append((list(cmd), kwargs))
        for trecho, stdout, codigo, stderr in RESPOSTAS:
            if trecho in cmd[-1]:
                return mock.Mock(stdout=stdout, returncode=codigo, stderr=stderr)
        return mock.Mock(stdout="", returncode=1, stderr="sem resposta falsa para este comando")

    with mock.patch("lib.runner.subprocess.run", side_effect=falso):
        codigo = collect.main(["--padrao", str(tmp_path / "default.toml"),
                               "--infra", str(tmp_path / "alvos.toml"),
                               "--projeto", str(tmp_path / "config.toml"),
                               "--out", str(tmp_path / "saida"), "--at", "2026-11-13T10:00:00Z",
                               "--confirmar", "banco-01"])
    texto = (tmp_path / "saida" / "report.json").read_text(encoding="utf-8")

    assert codigo == 0
    assert not any(MARCA in token for argv, _ in chamadas for token in argv)
    assert any(MARCA in (kwargs.get("input") or "") for _, kwargs in chamadas)
    assert MARCA not in texto
    # o patch troca TODO `subprocess.run` do módulo, inclusive o `git` de exigir_pasta_protegida:
    # a regra vale só para as chamadas de ssh
    assert all(("input" in kwargs) != ("stdin" in kwargs)
               for argv, kwargs in chamadas if argv[0] == "ssh")

    alvo = json.loads(texto)["alvos"][0]
    mariadb = next(c for c in alvo["componentes"] if c["nome"] == "mariadb")
    respostas = {r["pergunta"]: r for r in mariadb["respostas"]}
    assert respostas["banco.conexoes"]["valor"] == 12
    assert respostas["banco.conexoes"]["fonte"] == "ssh:mariadb"
    assert respostas["servico.ativo"]["valor"] == "ativo"
    assert respostas["banco.backup_idade"]["valor"] == 5
    assert respostas["banco.binlog"]["nao_publica"] is True
    assert {"backup_atrasado", "conexoes_no_limite"} <= {a["regra"] for a in alvo["achados"]}
```

- [x] **Step 2: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest -q tests/test_host_produto_ponta_a_ponta.py`
Esperado: PASSA. Se falhar, o defeito é de ligação entre as tasks (é o primeiro teste que passa por
todas): leia a asserção que caiu, conserte na task de origem, rode os testes dela e registre em
"Ajustes".

- [x] **Step 3: provar que o teste pega o vazamento**

```bash
cd ~/.claude/skills/sw-infra-audit
cp scripts/lib/runner.py /tmp/claude-1000/runner.py.orig
sed -i 's/    cmd = argv_ssh(destino, porta, remoto, conexao=max(1, min(10, int(timeout))))/    cmd = argv_ssh(destino, porta, remoto + (entrada or ""), conexao=max(1, min(10, int(timeout))))/' scripts/lib/runner.py
cmp -s scripts/lib/runner.py /tmp/claude-1000/runner.py.orig && echo "NÃO APLICOU"
.venv/bin/python -m pytest -q tests/test_host_produto_ponta_a_ponta.py >/dev/null 2>&1; echo "rc=$?"
cp /tmp/claude-1000/runner.py.orig scripts/lib/runner.py
```

Esperado: nenhuma linha `NÃO APLICOU` e `rc=1` (o teste cai quando a senha vai para o argv). Depois,
`.venv/bin/python -m pytest -q tests/test_host_produto_ponta_a_ponta.py` volta a passar.

---

## Fase 4 — prova e publicação

### Task 15: mutações obrigatórias

**Arquivos:**
- Teste: (nenhum arquivo novo; mutações temporárias com restauração)

**Depende de:** Task 14

- [x] **Step 1: rodar cada mutação e confirmar que derruba teste**

```bash
cd ~/.claude/skills/sw-infra-audit
P=/tmp/claude-1000/mutacao-b && mkdir -p "$P"
mutar() {  # arquivo, sed, testes
  cp "$1" "$P/orig" && sed -i "$2" "$1"
  if cmp -s "$1" "$P/orig"; then echo "NÃO APLICOU: $2"; return; fi
  if .venv/bin/python -m pytest -q $3 >/dev/null 2>&1; then echo "SOBREVIVEU: $2"; else echo "morta: $2"; fi
  cp "$P/orig" "$1"
}
mutar scripts/lib/vagas.py 's/ok = isinstance(valor, str) and bool(COLECAO.fullmatch(valor))/ok = isinstance(valor, str)/' tests/test_runner_vagas.py
mutar scripts/lib/vagas.py 's/ok = sql_valido(valor) and valor in sqls/ok = sql_valido(valor)/' tests/test_runner_vagas.py
mutar scripts/lib/vagas.py 's/    if pedidas != set(vagas) - {"sql"}:/    if False:/' tests/test_runner_vagas.py
mutar scripts/lib/runner.py 's/else {"stdin": subprocess.DEVNULL}/else {}/' tests/test_runner_vagas.py
mutar scripts/lib/catalogo_produto.py 's/    if not sql_valido(sql):/    if False:/' tests/test_catalogo_produto.py
mutar scripts/lib/perguntas.py 's/    if componente.get("origem"):/    if True:/' tests/test_perguntas_do_componente.py
mutar scripts/collect.py 's/            if (resposta is None or candidata.get("explica_a_falta")/            if (resposta is None/' tests/test_perguntas_do_componente.py
mutar scripts/lib/adaptadores/ssh.py 's/        if not componente.get("origem"):/        if False:/' tests/test_adaptador_ssh_servico.py
mutar scripts/lib/leitura_servico.py 's/    etimes, rss = max(candidatos)/    etimes, rss = min(candidatos)/' tests/test_leitura_servico.py
mutar scripts/lib/leitura_servico.py 's/referencia = max(nomes_com_data) if nomes_com_data else/referencia = max(mtimes) if mtimes else/' tests/test_leitura_servico.py
mutar scripts/lib/credencial.py 's/if (alvo, destino, porta, componente) != (self.alvo, self.destino, self.porta, self.componente):/if False:/' tests/test_credencial_ssh.py
mutar scripts/lib/credencial.py 's/if any(c in texto for c in /if False and any(c in texto for c in /' tests/test_credencial_ssh.py
mutar scripts/lib/adaptadores/produto_ssh.py 's/    if not modo:/    if False:/' tests/test_adaptador_produto_ssh.py
mutar scripts/lib/adaptadores/produto_ssh.py 's/validos = sorted({n for n in nomes if isinstance(n, str) and COLECAO.fullmatch(n)})/validos = sorted({n for n in nomes if isinstance(n, str)})/' tests/test_adaptador_produto_ssh.py
mutar scripts/lib/limites_produto.py 's/    if idade is not None and idade > maximo:/    if idade is not None:/' tests/test_limites_produto.py
mutar scripts/lib/gravacao_alvos.py 's/        if repetidos:/        if False:/' tests/test_configurar_leitura.py
mutar scripts/configurar.py 's/        if alvos_mod.ler(infra)\[0\] != esperado:/        if False:/' tests/test_configurar_leitura.py
echo fim
```

Esperado: dezessete linhas `morta:`, nenhuma `SOBREVIVEU:` e nenhuma `NÃO APLICOU:`. Mutação que
sobrevive revela teste fraco: fortaleça o teste daquela task e repita só a linha dela. `NÃO APLICOU`
quer dizer que o código executado diverge do plano: ajuste o sed ao texto real e registre em "Ajustes".

- [x] **Step 2: suíte inteira e nenhum arquivo mutado para trás**

Rode: `timeout 900 .venv/bin/python -m pytest -q`
Esperado: tudo verde. Rode também
`for f in vagas runner catalogo_produto perguntas leitura_servico credencial limites_produto gravacao_alvos; do grep -c "if False" scripts/lib/$f.py; done; grep -c "if False" scripts/collect.py scripts/configurar.py scripts/lib/adaptadores/ssh.py scripts/lib/adaptadores/produto_ssh.py`
Esperado: só zeros (nenhuma mutação ficou no código).

---

### Task 16: documentação, publicação e gate

**Arquivos:**
- Alterar: `SKILL.md` (seções "Antes de tudo", "2. Confirmação", "Modo configurar", "Limites")
- Alterar: `references/what-to-collect.md`
- Alterar: `references/commands-allowlist.md`
- Alterar: `CHANGELOG.md`
- Alterar: `plugins/sw-infra-audit/` (gerado pelo `make sync`)

**Depende de:** Task 15

- [x] **Step 1: atualizar a SKILL.md**

Em **Antes de tudo**, logo depois do parágrafo que termina em `…avisa o que é novo ou sumiu.`,
acrescente:

````markdown
**Como ler cada banco, cache e busca.** Depois do `--gravar`, para cada componente gravado de papel
`banco`, `cache` ou `busca`, pergunte via `AskUserQuestion` como a skill o lê, e grave a resposta:

- **Socket** (recomendado para MariaDB, Postgres e Redis instalados no servidor): o cliente do próprio
  servidor, com o usuário do SSH, sem senha. No Postgres é `runuser -u postgres`, que exige `root`. No
  Qdrant, é a API local em `127.0.0.1`.
- **Senha** (só MariaDB e MySQL nesta versão): pergunte o usuário de leitura e o **nome** da variável
  de ambiente que guarda a senha — nunca a senha. Diga ao dono para exportá-la antes da auditoria.
- **Container**: o cliente dentro do container (`docker exec`), só para componente com origem
  `container:`.
- **Nenhum**: não ler; as perguntas do produto saem `sem dados` por escolha do dono.

Para banco, pergunte também a pasta do backup (opcional) e o limite em dias (`2` é o padrão; backup
semanal pede `7`).

```bash
python3 <skill-dir>/scripts/configurar.py leitura --alvo banco-01 --componente mariadb --modo socket \
  --backup-pasta /var/backups/mysql --backup-max-dias 2
python3 <skill-dir>/scripts/configurar.py leitura --alvo banco-01 --componente mysql --modo senha \
  --usuario leitor --senha-env SENHA_BANCO_01
```

A gravação só acrescenta linhas no bloco do componente, com `alvos.toml.bak`; campo que já existe é
recusado, e o dono corrige à mão. Se a auditoria trouxer "leitura não declarada" num componente de
host, faça esta pergunta e grave antes da próxima rodada.
````

Em **2. Confirmação**, troque

```markdown
que a skill vai entrar por SSH, com qual usuário (o destino mostra) e que roda só os comandos de
`references/host/linux.toml`.
```

por

```markdown
que a skill vai entrar por SSH, com qual usuário (o destino mostra) e que roda só os comandos de
`references/host/linux.toml` e, nos componentes com `leitura`, os clientes de
`references/produtos-host/` (só `SHOW`, `SELECT`, `INFO` e `GET`).
```

Na tabela de **Modo configurar**, depois da linha de `descobrir`, acrescente:

```markdown
| `leitura --alvo <host> --componente <nome> --modo <modo>` | Gravar como a skill lê um banco, cache ou busca do host (`socket`, `senha`, `container`, `nenhum`) e, para banco, a pasta e o limite do backup |
```

Em **Limites**, troque o item

```markdown
- **Banco de dados ainda não** — Postgres e MySQL são o próximo ciclo. Alvo desse tipo no
  `alvos.toml` é recusado com mensagem clara.
```

por

```markdown
- **Banco como alvo próprio não**: banco, cache e busca são lidos como componentes de um alvo `host`,
  pelo cliente instalado no servidor (`mariadb`, `mysql`, `psql`, `redis-cli`, `curl`) e só com as
  consultas de `references/produtos-host/<produto>.toml`. Alvo com `tipo = "postgres"` ou `"mysql"`
  continua recusado.
- **Senha só para MariaDB e MySQL**, e só pelo stdin do ssh (`--defaults-extra-file=/dev/stdin`):
  nunca no argv, no log ou no `report.json`. Redis com senha e Qdrant com chave de API saem
  `sem dados` dizendo que ficam para depois; Postgres entra pelo `runuser`, sem senha.
- **Um banco por produto e host**: só o socket padrão. Dois MariaDB no mesmo servidor não se distinguem
  nesta versão.
- **Sem CPU por processo** e sem firewall. Os blocos do relatório para estes números são da parte C;
  por enquanto eles aparecem nas respostas do componente.
```

e, no item **SSH só para alvo `host` declarado**, troque
`roda só os comandos literais de `references/host/linux.toml`. A` por
`roda só os comandos e moldes de `references/host/linux.toml` e de `references/produtos-host/`, com cada vaga validada. A`
e `configuração (o único arquivo lido é `/etc/os-release`, para o nome do sistema). Host novo só entra`
por
`configuração (o único arquivo lido é `/etc/os-release`, para o nome do sistema; a pasta de backup declarada é só listada). Host novo só entra`.

Confira: `grep -c "configurar.py leitura" SKILL.md` → `3`; `grep -c "Banco de dados ainda não" SKILL.md` → `0`.

- [x] **Step 2: atualizar as duas references**

No fim de `references/what-to-collect.md`:

```markdown
## Componentes de um alvo `host`

Todo componente declarado com `origem` ganha quatro perguntas comuns, lidas por SSH com os moldes de
`references/host/linux.toml`: estado, tempo no ar, reinícios e memória — de `systemctl show` (unit),
`docker inspect` e `docker stats` (container) ou `ps -e -o comm=,rss=,etimes=` (processo; a memória é a
do processo mais antigo, nunca a soma dos workers). Banco com `backup_pasta` ganha a idade do backup
mais novo, pela data no nome do arquivo (`AAAA-MM-DD` ou `AAAAMMDD`) ou, sem data, pelo mtime da
listagem.

Com `leitura` declarada, o catálogo do produto (`references/produtos-host/<produto>.toml`) acrescenta
os dados dele, pelo cliente instalado no servidor: MariaDB/MySQL (tamanho, tamanho por banco, conexões e
uso contra `max_connections`, consultas lentas, binlog), Postgres (tamanho, por banco, conexões e uso),
Redis (memória, descartes, taxa de acerto) e Qdrant (coleções, pontos, status). Nunca: conteúdo de
tabela, valor de variável que não seja contador ou limite, linha de comando, ambiente.
```

No fim de `references/commands-allowlist.md`:

```markdown
## Moldes e vagas (alvo host)

Além dos comandos literais, `references/host/linux.toml` tem a tabela `[molde]`, e cada catálogo de
`references/produtos-host/` tem o `[cliente]` por modo de leitura. Molde é comando com vaga: o runner
recebe molde e vagas, confere que o molde está num catálogo e monta o comando com `lib/vagas.py`, antes
do subprocesso.

| Vaga | De onde vem | Validação |
|---|---|---|
| `{sql}` | literal de um catálogo de produto | precisa ser uma consulta de catálogo, sem `"`, `$`, crase, `\`, `%`, `<`, `>` ou quebra de linha; no molde, sempre entre aspas duplas |
| `{unidade}` `{container}` | `origem` do componente, sem o `tipo:` | `[A-Za-z0-9][A-Za-z0-9._@:-]{0,127}` |
| `{porta}` | `portas` do componente ou `porta_padrao` do catálogo | inteiro de 1 a 65535 |
| `{colecao}` | resposta do Qdrant | `[A-Za-z0-9_-]{1,64}`; fora disso o item é pulado e dito |
| `{backup_pasta}` | `alvos.toml` | absoluto, `[A-Za-z0-9._/-]`, sem `..` |

O processo não tem vaga: `ps -e -o comm=,rss=,etimes=` é literal e o filtro pelo nome é feito na skill.
A senha do MariaDB/MySQL vai pelo stdin do ssh (`--defaults-extra-file=/dev/stdin`); sem ela, o stdin
do ssh é fechado (`/dev/null`).
```

- [x] **Step 3: CHANGELOG e sincronização**

No topo de `### Adicionado` em `## [Não publicado]` do `CHANGELOG.md` do repositório:

```markdown
- `sw-infra-audit` (v0.21.0): **coleta por produto em servidores host.** Todo componente descoberto num
  host ganha estado, tempo no ar, reinícios e memória (systemd, container ou processo). MariaDB, MySQL,
  Postgres, Redis e Qdrant trazem os dados do produto (tamanho por banco, conexões contra o limite,
  lentas, binlog, memória e descartes, coleções e pontos) pelo cliente do próprio servidor, a partir de
  catálogos em `references/produtos-host/` — produto novo é um arquivo. `configurar.py leitura` grava
  como cada componente é lido (socket, senha, container ou nenhum) e a pasta do backup; a senha, só no
  MariaDB/MySQL, vai pelo stdin do ssh. O catálogo de host passa a aceitar molde com vaga validada.
  Regras novas: `backup_atrasado`, `conexoes_no_limite`.
```

(Se o spike da Task 1 ficou "não executado", acrescente ao fim do item: `O modo senha não foi
verificado num MariaDB real.`)

Rode: `cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit BUMP=minor`
Esperado: `✓ plugin.json, marketplace.json e README atualizados.` e `"version": "0.21.0"` em
`plugins/sw-infra-audit/.claude-plugin/plugin.json`.

- [x] **Step 4: varrer e rodar o gate**

```bash
cd /var/www/ai-marketplace
find plugins/sw-infra-audit -name __pycache__ | wc -l
D=docs/specs/2026-11-13-coleta-por-produto-em-servidores-host
grep -rnE "/(home|Users)/" plugins/sw-infra-audit $D; echo "home rc=$?"
[ -f .scan-denylist ] && grep -rniFf .scan-denylist plugins/sw-infra-audit $D; echo "denylist rc=$?"
grep -rnE "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b" plugins/sw-infra-audit/skills/sw-infra-audit/references/produtos-host $D \
  | grep -vE "\b(10\.0\.0\.[0-9]+|127\.0\.0\.1|0\.0\.0\.0)\b"; echo "ip rc=$?"
git add CHANGELOG.md README.md .claude-plugin/marketplace.json docs/specs/README.md $D plugins/sw-infra-audit
make check
```

Esperado: `0`, `home rc=1`, `denylist rc=1`, `ip rc=1` e `✓ gate de segurança: nada sensível
detectado`. Commit e push só no checkpoint, com o "sim" do dono.

## Ajustes durante a execução

Vazio até a execução começar: registre aqui, com data, o que divergir do plano (resultado do spike,
sed de mutação que não aplicou, formato real diferente do catálogo).

- **2026-11-13** — Base da revisão final: 4823326f26d4b7c4da1596d0c27e33a7172a4f45
- **2026-11-13** — Task 1 (spike) executada num MariaDB 11.8 local em container: senha pelo stdin
  funciona escapando só `\` e `"`; `#` vai literal (o `\#` falha); só existe o binário `mariadb`;
  `SHOW GLOBAL STATUS`/`VARIABLES` separados por TAB. Com binlog desligado o MariaDB responde
  `ERROR 1381 ... You are not using binary logging` com rc=1; o `[[erro]]` do catálogo (Task 11) já
  transforma isso em `sem dados` com o motivo "o binlog está desligado" e `nao_publica`. O plano não
  muda.
- **2026-11-13** — lote 2 (tasks 3–6): suíte inteira com 2142 testes verdes. O comentário do topo de
  `references/host/linux.toml` passou a descrever `[molde]` e as vagas validadas.
- **2026-11-13** — Task 10: o subagente não rodou o step 2 (ver o teste falhar antes do adaptador);
  as mutações da Task 15 que miram `produto_ssh.py` são a prova de que os testes pegam defeito.
- **2026-11-13** — tasks 7–13: suíte inteira com 2239 testes verdes depois de cada lote.
- **2026-11-13** — Task 14: o vazamento simulado derrubou o teste e o runner voltou idêntico. Task
  15: 17 de 17 mutações mortas; 2240 testes verdes.
- **2026-11-13** — Task 16: o `make check` barrou como "segredo atribuído" a linha que MONTA o arquivo
  de opções do MySQL (a linha `password=` do `[client]`), em `credencial.py` e neste plano. É
  falso positivo (interpola a variável, não guarda segredo): as duas linhas ganharam o pragma
  `# noscan:` com o motivo. Gate verde nos 63 arquivos; v0.21.0; 2240 testes.
- **2026-11-13** — revisões finais (juiz + sw-code-review em contexto vazio): 7 achados, todos
  corrigidos com teste que falhou antes. (1, médio) catálogo de produto inválido derrubava todas as
  leituras de host: `catalogo_produto.validos()` ignora o inválido e o motivo vai só para as perguntas
  daquele produto. (2) taxa com denominador zero vira "sem leituras ainda" com `nao_publica`. (3)
  Postgres conta só `backend_type = 'client backend'`. (4) `origem`, `leitura` e `backup_*` recusados
  fora de alvo host. (5) SKILL.md cita o `leitura` entre quem escreve. (6) o teste ponta a ponta varre
  também stdout/stderr. (7) `configurar.py leitura` só aceita banco, cache ou busca. 2250 testes.
