# Plano de implementação — Relatório mostrando servidores host e dados por produto

[spec.md](spec.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** o relatório HTML e o PDF da `sw-infra-audit` passam a mostrar os servidores host e os
dados por produto. Cada problema exibido traz a caixa "O que fazer", e os gráficos são SVG inline.

**Arquitetura:**

- Um bloco novo, "Serviços dos servidores", tem índice de problemas e uma área por servidor.
- Um bloco novo, "Busca", mostra as coleções do Qdrant.
- Bancos e Máquinas ganham medidores e barras, vindos de `lib/graficos.py`.
- O cartão de problema (`lib/cartao.py`) mostra o primeiro passo de `## Como resolver` da remediação
  da regra.
- A capa e a nota leem os serviços do host por `lib/servicos_host.py`, no mesmo formato
  `name`/`replicas` dos serviços do cluster.

**Stack:** Python 3 só com stdlib e `pytest`. Os testes rodam da raiz da skill:
`cd ~/.claude/skills/sw-infra-audit && .venv/bin/python -m pytest -q` (hoje com 2250 testes).

**Onde mexer:** o código vive em `~/.claude/skills/sw-infra-audit/`, que é a fonte. O repositório
recebe as mudanças pelo `make sync` na task 13. Os caminhos das tasks são relativos à raiz da skill.
Para o lint do plano achar os arquivos, os caminhos "Alterar" apontam para a cópia do repo,
`plugins/sw-infra-audit/skills/sw-infra-audit/…`, que hoje é idêntica à fonte. **Edite sempre
em `~/.claude/skills/sw-infra-audit/`.**

**Restrições verificáveis (do spec):**

| Restrição | Como o plano checa |
|---|---|
| 1. Toda regra cobrada tem `Como resolver` começando por passo numerado de até 160 caracteres | Task 2, step 1 (`test_toda_regra_cobrada_comeca_por_um_passo_curto`) |
| 2. Nenhum cartão de problema sem "O que fazer"; cada achado vira cartão uma vez só | Task 12, steps 1 e 2 (`tests/test_relatorio_host.py`) |
| 3. Relatório sem host igual ao de antes, fora de Máquinas e Bancos | Task 1 (goldens gravados antes) e Task 12, step 4 |
| 4. Os 2 hosts somam no máximo 12 páginas e nenhuma página do meio fica quase vazia (revista com o dono) | Task 12, step 6 (`test_dois_hosts_somam_no_maximo_doze_paginas_e_nenhuma_fica_quase_vazia`) |
| 5. Nenhuma cor literal de dado no SVG | Task 4, step 1 (`test_svg_nao_tem_cor_literal`) |

**Risco primeiro:** a restrição 3 só vale se o golden for gravado **antes** de qualquer mudança. Por
isso a task 1 grava os goldens. Não há spike: o formato dos dados já foi confirmado na leitura do
código.

**Desvio do spec, registrado:** o golden "inteiro" da restrição 3 deveria sair de
`tests/fixtures/report_sample.json`. Esse arquivo usa o schema 1, e o build de hoje o recusa com
`ValueError: schema 1: este build lê o v3`. O golden passa a sair de
`tests/fixtures/relatorio_grande.py`, que é a rodada v3 de referência. Como ela também tem os
painéis Máquinas e Bancos, os dois goldens comparam o `<body>` sem esses painéis.

---

### Task 1: goldens do relatório sem host, gravados antes da mudança

**Arquivos:**
- Criar: `tests/fixtures/relatorio_docker.py`
- Criar: `tests/fixtures/golden/relatorio_grande.body.html` (gerado)
- Criar: `tests/fixtures/golden/relatorio_docker.body.html` (gerado)
- Teste: `tests/test_relatorio_sem_host.py`

**Depende de:** nada. **Rode antes de qualquer outra task.**

**Contrato que esta task publica:** `relatorio_docker() -> dict` (report v3 com um alvo docker, que
tem entrada, fila, cache, app, banco e máquina, e um alvo http); `corpo(html) -> str`, em
`tests/test_relatorio_sem_host.py`.

- [x] **Step 1: criar a fixture só com cluster e endpoint**

`tests/fixtures/relatorio_docker.py`:

```python
"""Rodada só com cluster e endpoint: a referência de que um relatório sem host não muda (parte C)."""
from lib import remediacao
from tests.fixtures.relatorio_grande import _nos


def _resposta(pergunta, valor, fonte):
    return {"pergunta": pergunta, "valor": valor, "fonte": fonte}


def _componentes():
    return [
        {"nome": "loja_proxy", "papel": "entrada", "achados": [], "respostas": [
            _resposta("entrada.volume_na_janela", 125000, "promql:traefik")]},
        {"nome": "loja_fila", "papel": "fila", "achados": [], "respostas": [
            _resposta("fila.filas", [{"nome": "pedidos", "objeto": "pedidos@/", "prontas": 3,
                                      "consumidores": 2}], "admin_http:broker")]},
        {"nome": "loja_cache", "papel": "cache", "achados": [], "respostas": [
            _resposta("cache.memoria_usada", 52428800, "promql:redis")]},
        {"nome": "loja_api", "papel": "app", "achados": [], "respostas": [
            _resposta("app.cpu", 12.5, "promql:cadvisor"), _resposta("app.memoria", 268435456, "promql:cadvisor")]},
        {"nome": "loja_db", "papel": "banco", "achados": [], "respostas": [
            _resposta("banco.conexoes", 18, "promql:mysqld"), _resposta("banco.tamanho", 1073741824, "promql:mysqld")]},
        {"nome": "no-0", "papel": "maquina", "achados": [], "respostas": [
            _resposta("maquina.cpu", 35.0, "promql:node"), _resposta("maquina.memoria", 62.0, "promql:node"),
            _resposta("maquina.disco", 71.0, "promql:node")]},
    ]


def _achados():
    achados = [{"regra": "SEC_USER_ROOT", "objeto": "loja_api", "alvo": "loja", "severidade": "medium",
                "detalhe": "roda como root"},
               {"regra": "OPS_NO_HEALTHCHECK", "objeto": "loja_fila", "alvo": "loja", "severidade": "low",
                "detalhe": "sem healthcheck"}]
    for achado in achados:
        achado["como_resolver"] = remediacao.para(achado["regra"])
    return achados


def relatorio_docker():
    componentes = _componentes()
    servicos = [{"name": c["nome"], "replicas": "1/1", "tasks_failed": 0, "image": "img", "kind": "app"}
                for c in componentes if c["papel"] != "maquina"]
    docker = {"nome": "loja", "tipo": "docker", "onde": "context: loja", "saude": "🟢", "coletado": True,
              "dimensoes": {}, "fatos": {"services": servicos, "nodes": _nos()[:1]},
              "componentes": componentes, "achados": _achados(), "cobertura": {}, "analise": "",
              "nao_coletado": []}
    http = {"nome": "site", "tipo": "http", "onde": "https://site.exemplo", "saude": "🟢", "coletado": True,
            "dimensoes": {}, "fatos": {"codigo": 200}, "componentes": [], "achados": [], "cobertura": {},
            "analise": "", "nao_coletado": []}
    alvos = [docker, http]
    return {"schema_version": 3, "generated_at": "2026-11-01T10:00:00Z", "alvos": alvos,
            "inventario": [{"nome": a["nome"], "tipo": a["tipo"], "onde": a["onde"], "saude": a["saude"]}
                           for a in alvos],
            "aceites": [], "historico": {}, "resumo": "", "fortes": [], "fracos": [], "recomendacoes": []}
```

- [x] **Step 2: escrever o teste dos goldens**

`tests/test_relatorio_sem_host.py`:

```python
"""Restrição 3 do spec da parte C: relatório sem host sai igual, fora dos painéis Máquinas e Bancos.

Os goldens foram gravados ANTES da mudança (task 1 do plano). Regravar um golden para o teste passar
apaga justamente o que ele protege: só regrave com decisão registrada no plano.
"""
import re
from pathlib import Path

import build_report as br
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_grande import relatorio_grande

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
# os dois painéis que o spec deixa mudar também nos clusters
_PAINEL_QUE_MUDA = re.compile(
    r'<section class="bl-pn[^"]*"><header><h3>(?:Máquinas|Bancos de dados)</h3>.*?</section>', re.S)
# a âncora que o "ver todos os passos" usa; não muda nada do que se lê
_ID_DA_REGRA = re.compile(r' id="regra-[^"]*"')


def corpo(html):
    body = re.search(r"<body.*?</body>", html, re.S).group(0)
    body = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
    return _PAINEL_QUE_MUDA.sub("", _ID_DA_REGRA.sub("", body))


def test_rodada_grande_de_cluster_sai_igual_fora_de_maquinas_e_bancos():
    esperado = (GOLDEN / "relatorio_grande.body.html").read_text(encoding="utf-8")
    assert corpo(br.render_html_v3(relatorio_grande())) == esperado


def test_cluster_e_endpoint_saem_iguais_fora_de_maquinas_e_bancos():
    esperado = (GOLDEN / "relatorio_docker.body.html").read_text(encoding="utf-8")
    assert corpo(br.render_html_v3(relatorio_docker())) == esperado
```

- [x] **Step 3: rodar e confirmar que falha pela falta do golden**

Rode: `.venv/bin/python -m pytest tests/test_relatorio_sem_host.py -q`
Esperado: 2 falhas com `FileNotFoundError` em `golden/…body.html`.

- [x] **Step 4: gravar os goldens com o código de hoje**

```bash
cd ~/.claude/skills/sw-infra-audit && mkdir -p tests/fixtures/golden && .venv/bin/python - <<'EOF'
import sys
sys.path[:0] = ["scripts", "."]
import build_report as br
from tests.test_relatorio_sem_host import GOLDEN, corpo
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_grande import relatorio_grande
for nome, fabrica in (("relatorio_grande", relatorio_grande), ("relatorio_docker", relatorio_docker)):
    um, dois = corpo(br.render_html_v3(fabrica())), corpo(br.render_html_v3(fabrica()))
    assert um == dois, f"{nome}: o corpo muda entre duas gerações; o golden não serve"
    (GOLDEN / f"{nome}.body.html").write_text(um, encoding="utf-8")
    print(nome, len(um))
EOF
```

Esperado: duas linhas com o nome e o tamanho, sem `AssertionError`. Confira também que o golden do
docker contém `loja_api` e `pedidos` (o `loja_db` não aparece, porque o painel Bancos é removido de propósito):
`grep -c "loja_api" tests/fixtures/golden/relatorio_docker.body.html` deve dar 1 ou mais.

- [x] **Step 5: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_relatorio_sem_host.py -q`
Esperado: 2 passed.

---

### Task 2: primeiro passo da remediação e a fitness function 1

**Arquivos:**
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/remediacao.py:58-61` (função nova no fim)
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/references/remediacao/OPS_TLS_EXPIRED.md`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/references/remediacao/OPS_TLS_EXPIRING.md`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/references/remediacao/SEC_PORT_EXPOSED.md`
- Teste: `tests/test_primeiro_passo.py`

**Depende de:** Task 1.

**Contrato que esta task publica:** `remediacao.primeiro_passo(texto: str | None) -> str | None`.
Recebe o conteúdo da seção `## Como resolver`, já sem o título, que é o que
`carregar_arquivo(...)["como_resolver"]` devolve. Devolve o texto do passo 1 sem o `1. `, com os
espaços juntados, ou `None` quando o bloco não abre com passo numerado.

- [x] **Step 1: escrever os testes que falham**

`tests/test_primeiro_passo.py`:

```python
from lib import regras, remediacao

LIMITE = 160


def test_passo_um_vai_ate_o_passo_dois_e_junta_as_linhas():
    texto = "1. Veja se a rotina rodou:\n   `systemctl list-timers`.\n2. Outro passo."
    assert remediacao.primeiro_passo(texto) == "Veja se a rotina rodou: `systemctl list-timers`."


def test_passo_um_para_na_linha_em_branco():
    assert remediacao.primeiro_passo("\n1. Só este.\n\n```bash\nls\n```") == "Só este."


def test_bloco_que_abre_com_paragrafo_nao_tem_primeiro_passo():
    assert remediacao.primeiro_passo("Leia o runbook antes.\n\n1. Depois isto.") is None


def test_bloco_vazio_nao_tem_primeiro_passo():
    assert remediacao.primeiro_passo(None) is None and remediacao.primeiro_passo("") is None


def test_toda_regra_cobrada_comeca_por_um_passo_curto():
    fora = {}
    for regra in sorted(regras.exigem_remediacao()):
        bloco = remediacao.para(regra)
        passo = remediacao.primeiro_passo(bloco["como_resolver"]) if bloco else None
        if passo is None or len(passo) > LIMITE:
            fora[regra] = passo if passo is None else len(passo)
    assert fora == {}
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_primeiro_passo.py -q`
Esperado: FALHA com `AttributeError: module 'lib.remediacao' has no attribute 'primeiro_passo'`.

- [x] **Step 3: escrever `primeiro_passo` no fim de `scripts/lib/remediacao.py`**

```python
def primeiro_passo(texto):
    """O passo 1 de "Como resolver": é o que o cartão de problema mostra em "O que fazer".

    Primeira linha não vazia, que abre com `1. `, até a linha em branco ou o `2.`, com os espaços
    juntados num só. Bloco que abre com parágrafo devolve None: o teste estático acusa a ficha.
    """
    linhas = (texto or "").splitlines()
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    if not linhas or not linhas[0].lstrip().startswith("1. "):
        return None
    passo = []
    for linha in linhas:
        if passo and (not linha.strip() or re.match(r"\s*2\.\s", linha)):
            break
        passo.append(linha.strip())
    return " ".join(" ".join(passo)[3:].split())
```

- [x] **Step 4: rodar e confirmar que só a fitness falha, nos três arquivos esperados**

Rode: `.venv/bin/python -m pytest tests/test_primeiro_passo.py -q`
Esperado: 4 passed e 1 falha, com
`{'OPS_TLS_EXPIRED': None, 'OPS_TLS_EXPIRING': None, 'SEC_PORT_EXPOSED': 161}`.

- [x] **Step 5: ajustar só o começo das três remediações**

Em `references/remediacao/OPS_TLS_EXPIRED.md`, troque o parágrafo de abertura e renumere:

```markdown
## Como resolver

1. Leia o runbook `references/tls-renewal.md` antes de agir: este caso tem procedimento próprio.
2. Renove **mantendo a mesma autoridade certificadora**; trocar de CA obriga a atualizar todos
   os clientes ao mesmo tempo.
3. Valide o par **antes** de aplicar.
4. Reinicie o daemon (ele só relê o certificado ao subir) e confira os outros clientes.
```

O bloco ` ```bash ` que vem depois continua igual.

Em `references/remediacao/OPS_TLS_EXPIRING.md`, troque o parágrafo por dois passos:

```markdown
## Como resolver

1. Leia o runbook `references/tls-renewal.md` antes de agir.
2. Renove mantendo a mesma CA, valide o par antes de aplicar, reinicie o daemon e atualize os outros
   clientes (CI, painel, máquinas de quem opera).
```

O bloco ` ```bash ` que vem depois continua igual.

Em `references/remediacao/SEC_PORT_EXPOSED.md`, encurte só o passo 1:

```markdown
1. Descubra quem precisa alcançar a porta. Se for outro serviço do mesmo cluster, ela **não
   precisa ser publicada**: a rede interna resolve pelo nome.
```

- [x] **Step 6: rodar e confirmar que passa, e que a suíte de remediação continua verde**

Rode: `.venv/bin/python -m pytest tests/test_primeiro_passo.py -q && .venv/bin/python -m pytest -q -k "remedia or tls"`
Esperado: tudo verde. Se algum teste citar o texto antigo ("Este caso tem runbook próprio" ou
"Leia `references/tls-renewal.md`."), troque a citação no teste pelo texto novo do passo 1.

---

### Task 3: regra `servico_reiniciando` e rótulos das regras de host

**Arquivos:**
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/regras.py:52-54`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/limites_produto.py:9-35`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/rule_meta.py:36` (entradas novas no `RULE_META.update`)
- Criar: `references/remediacao/servico_reiniciando.md`
- Teste: `tests/test_servico_reiniciando.py`

**Depende de:** Task 1. Pode rodar em paralelo com as tasks 2, 4 e 6: os arquivos não se cruzam.

**Contrato que esta task publica:** `limites_produto.LIMITE_DE_REINICIOS = 5` e a regra
`servico_reiniciando`, com severidade `medium`, origem `produto` e `objeto` igual ao nome do
componente.

- [x] **Step 1: escrever os testes que falham**

`tests/test_servico_reiniciando.py`:

```python
from lib import limites_produto, regras, remediacao
from lib.rule_meta import meta


def _comp(reinicios):
    return {"nome": "mariadb", "respostas": [
        {"pergunta": "servico.reinicios", "valor": reinicios, "fonte": "ssh"}]}


def test_cinco_reinicios_viram_achado_medio():
    achados = limites_produto.achados(_comp(5))
    assert [(a["regra"], a["severidade"], a["objeto"], a["valor"]) for a in achados] == \
        [("servico_reiniciando", "medium", "mariadb", 5)]


def test_quatro_reinicios_nao_viram_achado():
    assert limites_produto.achados(_comp(4)) == []


def test_reinicio_sem_dado_nao_vira_achado():
    comp = {"nome": "mariadb", "respostas": [{"pergunta": "servico.reinicios", "sem_dados": True}]}
    assert limites_produto.achados(comp) == []


def test_regra_registrada_com_produtor_e_remediacao():
    assert regras.REGRAS["servico_reiniciando"] == {"severidade_padrao": "medium", "origem": "produto",
                                                     "esperada": False}
    assert "servico_reiniciando" in limites_produto.REGRAS_PRODUZIDAS
    assert remediacao.para("servico_reiniciando")["titulo"] == "Serviço reiniciando repetidamente"


def test_regras_de_host_tem_rotulo_proprio():
    for regra in ("servico_declarado_ausente", "SEC_BIND_ALL_INTERFACES", "backup_atrasado",
                  "conexoes_no_limite", "servico_reiniciando"):
        assert meta(regra)["label"] != regra, regra
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_servico_reiniciando.py -q`
Esperado: FALHA em `test_cinco_reinicios_viram_achado_medio` (lista vazia) e `KeyError: 'servico_reiniciando'`.

- [x] **Step 3: registrar a regra em `scripts/lib/regras.py`**, logo depois de `conexoes_no_limite`:

```python
    "servico_reiniciando":      {"severidade_padrao": "medium",  "origem": "produto", "esperada": False},
```

- [x] **Step 4: produzir o achado em `scripts/lib/limites_produto.py`**

Troque a primeira linha da docstring por
`"""Achados de produto em host: backup atrasado, conexões no limite e serviço reiniciando.`. Troque
as constantes e o fim de `achados`:

```python
BACKUP_MAX_DIAS_PADRAO = 2
LIMITE_DE_CONEXOES = 80
LIMITE_DE_REINICIOS = 5
REGRAS_PRODUZIDAS = {"backup_atrasado", "conexoes_no_limite", "servico_reiniciando"}
```

```python
    uso = _medida(componente, "banco.uso_de_conexoes")
    if uso is not None and uso > LIMITE_DE_CONEXOES:
        saida.append({"regra": "conexoes_no_limite", "severidade": "medium",
                      "objeto": componente["nome"], "valor": uso,
                      "detalhe": f"{uso}% das conexões permitidas em uso"})
    reinicios = _medida(componente, "servico.reinicios")
    if reinicios is not None and reinicios >= LIMITE_DE_REINICIOS:
        saida.append({"regra": "servico_reiniciando", "severidade": "medium",
                      "objeto": componente["nome"], "valor": reinicios,
                      "detalhe": f"{round(reinicios)} reinícios registrados pelo gerenciador do serviço"})
    return saida
```

- [x] **Step 5: criar `references/remediacao/servico_reiniciando.md`**

```markdown
---
regra: servico_reiniciando
titulo: Serviço reiniciando repetidamente
severidade_padrao: medium
---

## Por que importa

O serviço caiu e voltou pelo menos 5 vezes desde que o gerenciador (systemd ou Docker) começou a
contar. Cada queda derruba as conexões abertas e, num banco, pode deixar uma transação pela metade. O
reinício automático esconde o problema: na hora da auditoria o serviço parece de pé, mas está caindo.

## Como resolver

1. Leia o log da última queda: `journalctl -u <unit> -n 200` ou `docker logs --tail 200 <container>`.
2. Falta de memória é a causa mais comum: procure `Out of memory` em `journalctl -k`.
3. Erro de configuração ou de dependência (disco cheio, porta ocupada, senha trocada) aparece nas
   primeiras linhas depois de cada subida.
4. Corrigida a causa, acompanhe a contagem: ela não zera sozinha, mas não deve crescer.

## Como confirmar

Na próxima auditoria a contagem de reinícios fica igual à desta rodada. Na mão:
`systemctl show <unit> -p NRestarts` ou `docker inspect -f '{{.RestartCount}}' <container>`.

## Quando NÃO fazer

Não desligue o reinício automático para calar o alarme: é ele que mantém o serviço de pé enquanto a
causa não é corrigida. Reinício de propósito (uma rotina que reinicia todo dia) não é problema: aceite
o risco no `alvos.toml`, com o motivo.
```

- [x] **Step 6: dar rótulo às cinco regras em `scripts/lib/rule_meta.py`**, dentro do
`RULE_META.update({...})` que começa na linha 36:

```python
    "servico_declarado_ausente": {
        "label": "Serviço declarado e não encontrado",
        "what": "O alvos.toml declara este serviço no servidor, e a leitura do servidor não o encontrou.",
        "why": "Ou o serviço caiu e não voltou, ou a declaração ficou velha: nos dois casos o relatório "
               "não está olhando o que roda de verdade.",
    },
    "SEC_BIND_ALL_INTERFACES": {
        "label": "Serviço de dados aberto em todas as interfaces",
        "what": "Banco, cache ou busca escuta em 0.0.0.0, e não só na interface interna.",
        "why": "Qualquer rede que alcance o servidor alcança o dado; uma senha fraca vira invasão.",
    },
    "backup_atrasado": {
        "label": "Backup do banco atrasado",
        "what": "O backup mais novo da pasta declarada é mais velho que o limite do banco.",
        "why": "Se o banco se perder hoje, tudo o que foi gravado desde o último backup se perde junto.",
    },
    "conexoes_no_limite": {
        "label": "Conexões do banco perto do limite",
        "what": "Mais de 80% das conexões que o banco aceita estão em uso.",
        "why": "No limite, conexão nova é recusada e a aplicação devolve erro para quem está usando.",
    },
    "servico_reiniciando": {
        "label": "Serviço reiniciando repetidamente",
        "what": "O serviço caiu e voltou 5 vezes ou mais desde que o gerenciador começou a contar.",
        "why": "Cada queda derruba conexões; o reinício automático esconde que o serviço está caindo.",
    },
```

- [x] **Step 7: rodar e confirmar que passa, com a suíte das regras verde**

Rode: `.venv/bin/python -m pytest tests/test_servico_reiniciando.py tests/test_primeiro_passo.py -q && .venv/bin/python -m pytest -q -k "regra or remedia or produzida or limites"`
Esperado: tudo verde. O teste que compara `REGRAS_PRODUZIDAS` com as regras de origem `produto` já
cobre a regra nova sem mudança.

---

### Task 4: gráficos em SVG inline e os tokens de cor

**Arquivos:**
- Criar: `scripts/lib/graficos.py`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/assets/report-template/template_v3.html:18-30` (tokens nos dois `:root`) e antes do `@media print` da linha 1075 (CSS dos gráficos)
- Teste: `tests/test_graficos.py`

**Depende de:** Task 1. Pode rodar em paralelo com as tasks 2, 3 e 6.

**Contrato que esta task publica:**
- `graficos.barra(pct: float, titulo: str, tom: str = "acc", marca: float | None = None) -> str`:
  barra de 10px com trilha, onde `tom` é `acc`, `ok`, `warn` ou `crit`.
- `graficos.medidor(valor, maximo, marca, rotulo, texto, sub="", acima="crit", marca_texto=None) -> str`:
  rótulo e número em texto, barra com a marca e, acima da marca, etiqueta com ícone e rótulo.
- `graficos.barras(itens: list[tuple[str, float | None]], formato, titulo: str, limite: int = 5) -> str`:
  barras ordenadas da maior para a menor; os itens sem dado vão por último, e passou do limite, "e mais N".
- As classes CSS: `gf`, `gf-trk`, `gf-acc`, `gf-ok`, `gf-warn`, `gf-crit`, `gf-lim`, `mt*`, `br*`.

- [x] **Step 1: escrever os testes que falham**

`tests/test_graficos.py`:

```python
import re
from pathlib import Path

from lib import graficos
from lib.html_comum import tamanho

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "report-template" / "template_v3.html"


def test_medidor_abaixo_da_marca_usa_o_acento_e_sem_etiqueta():
    html = graficos.medidor(42, 100, 80, "Conexões em uso", "42%", marca_texto="alerta em 80%")
    assert 'class="gf-acc"' in html and "bl-tag-" not in html and "42%" in html and "alerta em 80%" in html


def test_medidor_acima_da_marca_tem_cor_de_status_icone_e_rotulo():
    html = graficos.medidor(5, 4, 2, "Idade do backup", "5 dias", acima="crit")
    assert 'class="gf-crit"' in html and 'class="bl-tag-crit"' in html and "#ic-achado" in html
    assert "acima do limite" in html


def test_medidor_sem_valor_diz_sem_dado():
    html = graficos.medidor(None, 100, 80, "Conexões em uso", "")
    assert "sem dado" in html and "<svg" not in html


def test_barras_ordenam_e_cortam_com_e_mais():
    itens = [("a", 10), ("b", 300), ("c", None), ("d", 50), ("e", 1), ("f", 2), ("g", 3)]
    html = graficos.barras(itens, tamanho, "Tamanho por banco", limite=5)
    rotulos = re.findall(r'<span class="br-l">([^<]+)</span>', html)
    assert rotulos == ["b", "d", "a", "g", "f"] and "e mais 2" in html


def test_barras_sem_dado_vem_por_ultimo_e_escritas():
    html = graficos.barras([("x", None), ("y", 1024)], tamanho, "t")
    assert html.index(">y<") < html.index(">x<") and "sem dado" in html


def test_toda_marca_tem_title():
    html = graficos.medidor(42, 100, 80, "Conexões", "42%") + graficos.barras([("a", 1)], str, "t")
    assert html.count("<svg") == html.count("<title>")


def test_svg_nao_tem_cor_literal():
    html = (graficos.medidor(95, 100, 90, "Disco", "95%") + graficos.barras([("a", 1), ("b", 2)], str, "t")
            + graficos.barra(50, "Memória", tom="warn", marca=90))
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b|rgb\(|\b(fill|stroke)=", html)


def test_classes_dos_graficos_usam_tokens_nos_dois_temas():
    css = TEMPLATE.read_text(encoding="utf-8")
    for classe, token in (("gf-acc", "--g-acc"), ("gf-warn", "--g-warn"), ("gf-crit", "--g-crit"),
                          ("gf-trk", "--g-trk"), ("gf-lim", "--g-lim")):
        assert f".gf .{classe}{{fill:var({token})}}" in css, classe
        assert css.count(f"{token}:") == 2, token        # claro e escuro
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_graficos.py -q`
Esperado: FALHA com `ImportError: cannot import name 'graficos'`.

- [x] **Step 3: escrever `scripts/lib/graficos.py`**

```python
"""Gráficos em SVG inline: sem JS e sem biblioteca, iguais na tela, no escuro e no PDF.

A cor vem só de classe (`gf-*`), e a classe lê os tokens `--g-*` dos dois `:root` do template: cor
literal aqui quebraria o modo escuro. O número vai sempre escrito ao lado, e cada marca tem `<title>`.
Paleta validada (claro #22659e/#b7791f/#b02a37, escuro #3f8fd0/#bf8a17/#cc3b4c).
"""
from lib.html_comum import SEM_DADO, _e

TOM = {"acc": "gf-acc", "ok": "gf-ok", "warn": "gf-warn", "crit": "gf-crit"}
ICONE = {"warn": "achado", "crit": "achado", "ok": "bom"}


def _limitar(pct):
    # nan-ok: o valor vira só largura no SVG; quem chama já passou por resposta numérica
    return max(0.0, min(100.0, float(pct)))


def _svg(partes, alto, titulo):
    return (f'<svg class="gf" width="100%" height="{alto}" role="img" aria-label="{_e(titulo)}">'
            f'<title>{_e(titulo)}</title>{"".join(partes)}</svg>')


def barra(pct, titulo, tom="acc", marca=None, alto=10, trilha=True):
    p = _limitar(pct)
    partes = [f'<rect class="gf-trk" x="0" y="4" width="100%" height="{alto}" rx="4"/>'] if trilha else []
    if p > 0:
        partes.append(f'<rect class="{TOM[tom]}" x="0" y="4" width="{p:.2f}%" height="{alto}" rx="4"/>')
    if marca is not None:
        # sem `translate(-1 0)`: um "-1" no HTML quebra o teste do disco estável (test_blocos.py)
        partes.append(f'<rect class="gf-lim" x="{_limitar(marca):.2f}%" y="0" width="2" height="{alto + 8}"/>')
    return _svg(partes, alto + 8, titulo)


def etiqueta(tom, texto):
    return (f'<span class="bl-tag-{tom}"><svg class="ic"><use href="#ic-{ICONE.get(tom, "ruim")}"/></svg>'
            f'{_e(texto)}</span>')


def medidor(valor, maximo, marca, rotulo, texto, sub="", acima="crit", marca_texto=None):
    """`valor` e `marca` na unidade de `maximo`. Acima da marca a cor é de status, com etiqueta."""
    sub_html = f'<span class="mt-s">{_e(sub)}</span>' if sub else ""
    cabeca = f'<span class="mt-l">{_e(rotulo)}{sub_html}</span>'
    if valor is None:
        return f'<div class="mt"><div class="mt-h">{cabeca}<b class="mt-v">{SEM_DADO}</b></div></div>'
    passou = valor > marca
    tom = acima if passou else "acc"
    pct, pct_marca = valor * 100 / maximo, marca * 100 / maximo
    legenda = marca_texto or f"limite {marca}"
    numero = f' bl-c-{acima}' if passou else ""
    estado = f'<span class="mt-st">{etiqueta(acima, "acima do limite")}</span>' if passou else ""
    return (f'<div class="mt"><div class="mt-h">{cabeca}<b class="mt-v{numero}">{_e(texto)}</b></div>'
            f'<div class="mt-b">{barra(pct, f"{rotulo}: {texto}, {legenda}", tom, pct_marca)}'
            f'<span class="mt-lim" style="left:{_limitar(pct_marca):.2f}%">{_e(legenda)}</span></div>'
            f'{estado}</div>')


def barras(itens, formato, titulo, limite=5):
    com = sorted((i for i in itens if i[1] is not None), key=lambda i: (-i[1], str(i[0])))
    ordem = com + [i for i in itens if i[1] is None]
    maior = com[0][1] if com and com[0][1] > 0 else 1
    linhas = []
    for rotulo, valor in ordem[:limite]:
        if valor is None:
            grafico, texto = '<span class="br-sd">sem dado</span>', '<span class="br-v bl-sd">sem dado</span>'
        else:
            escrito = formato(valor)
            grafico = barra(max(valor * 100 / maior, 1.2), f"{rotulo}: {escrito}", alto=14, trilha=False)
            texto = f'<span class="br-v">{_e(escrito)}</span>'
        linhas.append(f'<div class="br-r" role="listitem"><span class="br-l">{_e(rotulo)}</span>{grafico}{texto}</div>')
    resto = len(ordem) - limite
    mais = f'<p class="br-mais">e mais {resto}</p>' if resto > 0 else ""
    return f'<div class="br" role="list" aria-label="{_e(titulo)}">{"".join(linhas)}</div>{mais}'
```

- [x] **Step 4: tokens nos dois `:root` do template**

No `:root` claro (linha 18), antes do `}` final:

```css
 --g-acc:#22659e;--g-ok:#12683f;--g-warn:#b7791f;--g-crit:#b02a37;--g-lim:#3f4046;
 --g-trk:color-mix(in srgb,#22659e 13%,#ffffff);
```

No `:root` escuro (dentro de `@media screen and (prefers-color-scheme: dark)`), antes do `}`:

```css
   --g-acc:#3f8fd0;--g-ok:#56d99a;--g-warn:#bf8a17;--g-crit:#cc3b4c;--g-lim:#c2c3c7;
   --g-trk:color-mix(in srgb,#3f8fd0 22%,#1a1a1d);
```

- [x] **Step 5: CSS dos gráficos no template**, logo antes do `@media print{` da linha 1075:

```css
/* GRAFICOS (lib/graficos.py). Cor so por token: o escuro tem os proprios passos, validados. */
.gf{display:block;overflow:visible}
.gf .gf-trk{fill:var(--g-trk)}
.gf .gf-acc{fill:var(--g-acc)}
.gf .gf-ok{fill:var(--g-ok)}
.gf .gf-warn{fill:var(--g-warn)}
.gf .gf-crit{fill:var(--g-crit)}
.gf .gf-lim{fill:var(--g-lim)}
.bl-tag-ok .ic,.bl-tag-warn .ic,.bl-tag-crit .ic,.bl-tag-neutro .ic{width:13px;height:13px;vertical-align:-2px;margin-right:4px}
.mt{display:grid;gap:var(--s1);min-width:0;margin-top:var(--s3);break-inside:avoid}
.mt-h{display:flex;align-items:baseline;justify-content:space-between;gap:var(--s2)}
.mt-l{display:grid;font-weight:600;font-size:14px;color:var(--tinta)}
.mt-s{font-weight:400;font-size:12.5px;color:var(--fraco)}
.mt-v{font:600 19px/1 var(--mono);font-variant-numeric:tabular-nums;letter-spacing:-.03em;white-space:nowrap}
.mt-b{position:relative;padding-bottom:var(--s3)}
.mt-lim{position:absolute;bottom:0;transform:translateX(-100%);padding-right:4px;font-size:11.5px;line-height:1.2;color:var(--fraco);white-space:nowrap}
.br{display:grid;grid-template-columns:minmax(0,9rem) minmax(0,1fr) 5.5rem;row-gap:2px;column-gap:var(--s3);align-items:center;margin-top:var(--s1)}
.br-r{display:contents}
.br-l{font:500 13px/18px var(--mono);color:var(--tinta2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.br-v{text-align:right;font:600 13.5px/18px var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.br-sd{font-size:12.5px;color:var(--fraco);line-height:18px}
.br-mais{font-size:12.5px;color:var(--fraco);margin-top:var(--s1)}
```

- [x] **Step 6: rodar e confirmar que passa, com os goldens ainda verdes**

Rode: `.venv/bin/python -m pytest tests/test_graficos.py tests/test_relatorio_sem_host.py tests/test_nan_nunca_chega_ao_report.py -q`
Esperado: tudo verde. O golden ignora o `<style>`, então o CSS novo não o afeta. O teste do NaN exige
que cada `float()` do pacote tenha `isnan` ou um comentário `# nan-ok:` numa linha própria dentro da
função; o comentário no fim da linha não serve, porque o teste lê o trecho com `ast.get_source_segment`.

---

### Task 5: a capa e a nota contam os serviços do host

**Arquivos:**
- Criar: `scripts/lib/servicos_host.py`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/nota.py:80-90`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/capa.py:93-114` e `:412-424`
- Teste: `tests/test_servicos_host.py`

**Depende de:** Task 1.

**Contrato que esta task publica:**
- `servicos_host.servicos(alvo) -> list[dict]` devolve `{"name", "replicas", "tasks_failed": 0}`
  por componente do host que não é a máquina:
  - `replicas` é `"1/1"` quando ativo;
  - `"0/1"` quando o estado é outro ou o componente tem `servico_declarado_ausente`;
  - `None` quando não foi medido, e aí o componente fica fora da base.
- `servicos_host.aceitos(alvo, aceites) -> set[str]`.

- [x] **Step 1: escrever os testes que falham**

`tests/test_servicos_host.py`:

```python
from lib.capa import _nomes_por_estado, saude_por_sistema
from lib.nota import nota_geral
from lib import servicos_host


def _comp(nome, ativo=None, papel="banco"):
    respostas = [] if ativo is None else [{"pergunta": "servico.ativo", "valor": ativo, "fonte": "ssh"}]
    return {"nome": nome, "papel": papel, "respostas": respostas, "achados": []}


def _host(componentes, achados=()):
    return {"nome": "banco-01", "tipo": "host", "coletado": True, "saude": "🟢", "fatos": {},
            "componentes": [{"nome": "banco-01", "papel": "maquina", "respostas": [], "achados": []},
                            *componentes], "achados": list(achados), "dimensoes": {}}


AUSENTE = {"regra": "servico_declarado_ausente", "componente": "pg", "objeto": "pg", "alvo": "banco-01",
           "severidade": "high"}


def test_ativo_parado_ausente_e_nao_medido():
    alvo = _host([_comp("mariadb", "ativo"), _comp("redis", "failed", "cache"), _comp("pg"), _comp("qdrant")],
                 [AUSENTE])
    assert {s["name"]: s["replicas"] for s in servicos_host.servicos(alvo)} == \
        {"mariadb": "1/1", "redis": "0/1", "pg": "0/1", "qdrant": None}


def test_nota_conta_o_host_e_deixa_o_nao_medido_fora_da_base():
    alvo = _host([_comp("mariadb", "ativo"), _comp("pg"), _comp("qdrant")], [AUSENTE])
    nota = nota_geral([alvo], [])
    assert (nota["online"], nota["base"]) == (1, 2) and nota["limites"]["fora"] == 1


def test_aceite_do_ausente_vale_por_componente():
    alvo = _host([_comp("mariadb", "ativo"), _comp("pg")], [AUSENTE])
    aceite = {"alvo": "banco-01", "regra": "servico_declarado_ausente", "objeto": "pg", "vencido": False}
    nota = nota_geral([alvo], [aceite])
    assert (nota["online"], nota["base"]) == (1, 1)


def test_host_sem_vpn_nao_tem_base_e_fica_parcial():
    alvo = {"nome": "banco-01", "tipo": "host", "coletado": True, "saude": "sem dados", "fatos": {},
            "componentes": [], "achados": [], "dimensoes": {}}
    docker = {"nome": "c", "tipo": "docker", "coletado": True, "dimensoes": {}, "achados": [],
              "fatos": {"services": [{"name": "x_api", "replicas": "1/1", "tasks_failed": 0}]}}
    nota = nota_geral([alvo, docker], [])
    assert nota["base"] == 1 and nota["parcial"] is True


def test_capa_lista_o_servico_parado_do_host():
    alvo = _host([_comp("mariadb", "ativo"), _comp("pg")], [AUSENTE])
    assert _nomes_por_estado({"alvos": [alvo], "aceites": []})["fora"] == ["pg"]


def test_saude_por_sistema_mostra_o_host_como_um_sistema():
    alvo = _host([_comp("mariadb", "ativo"), _comp("pg")], [AUSENTE])
    html = saude_por_sistema([alvo], [])
    assert "banco-01" in html and "1/2" in html


def test_host_sem_vpn_aparece_na_saude_como_sem_dado():
    alvo = {"nome": "cache-02", "tipo": "host", "coletado": True, "saude": "sem dados", "fatos": {},
            "componentes": [], "achados": [], "dimensoes": {}}
    html = saude_por_sistema([alvo], [])
    assert "cache-02" in html and "Sem dado" in html
```

O motivo do "não medido" já aparece na capa: `_faltou` cita pelo nome o alvo que não trouxe fatos.

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_servicos_host.py -q`
Esperado: FALHA com `ImportError: cannot import name 'servicos_host'`.

- [x] **Step 3: escrever `scripts/lib/servicos_host.py`**

```python
"""Os serviços de um alvo `host` no formato que a capa e a nota já leem (`name`, `replicas`).

Assim o host conta como o cluster, sem um segundo jeito de contar: ativo é "1/1", parado ou ausente
é "0/1", e não medido (`servico.ativo` sem resposta) é réplica ilegível, que `estado_de` trata como
"sem dado", fora da base da nota.
"""
from lib.dados_blocos import _resposta

AUSENTE = "servico_declarado_ausente"


def servicos(alvo):
    if alvo.get("tipo") != "host":
        return []
    ausentes = {a.get("componente") for a in alvo.get("achados") or [] if a.get("regra") == AUSENTE}
    saida = []
    for comp in alvo.get("componentes") or []:
        if comp.get("papel") == "maquina":
            continue
        ativo = _resposta(comp, "servico.ativo")
        if comp.get("nome") in ausentes or (ativo is not None and ativo != "ativo"):
            replicas = "0/1"
        else:
            replicas = "1/1" if ativo == "ativo" else None
        saida.append({"name": comp.get("nome"), "replicas": replicas, "tasks_failed": 0})
    return saida


def aceitos(alvo, aceites):
    """O aceite do ausente mira o componente: o `objeto` do achado é o nome dele."""
    return {a.get("objeto") for a in aceites
            if a.get("alvo") == alvo.get("nome") and a.get("regra") == AUSENTE and not a.get("vencido")}
```

- [x] **Step 4: ramo `host` em `_conta_do_alvo` (`scripts/lib/nota.py`)**, logo antes do `return contar(...)` final:

```python
    if alvo.get("tipo") == "host":
        from lib import servicos_host
        return contar(servicos_host.servicos(alvo), servicos_host.aceitos(alvo, aceites))
```

- [x] **Step 5: host em `_nomes_por_estado` (`scripts/lib/capa.py`)**

Troque:

```python
        servicos = (alvo.get("fatos") or {}).get("services")
        aceitos = _aceitos(alvo, aceites)
        for s in servicos if isinstance(servicos, list) else []:
```

por:

```python
        if alvo.get("tipo") == "host":
            servicos, aceitos = servicos_host.servicos(alvo), servicos_host.aceitos(alvo, aceites)
        else:
            servicos = (alvo.get("fatos") or {}).get("services")
            aceitos = _aceitos(alvo, aceites)
        for s in servicos if isinstance(servicos, list) else []:
```

Acrescente `from lib import remediacao, servicos_host` no lugar de `from lib import remediacao`.

- [x] **Step 6: host em `saude_por_sistema` (`scripts/lib/capa.py`)**, no começo do `for alvo in rodada:`:

```python
    for alvo in rodada:
        if alvo.get("tipo") == "host":
            aceitos = servicos_host.aceitos(alvo, aceites)
            linhas = [(estado_de(s, aceitos), s.get("replicas"), s.get("name"))
                      for s in servicos_host.servicos(alvo)]
            # host que não respondeu (VPN fora) fica visível como "Sem dado", nunca some da tabela
            sistemas[alvo.get("nome")] = linhas or [("sem_dado", None, alvo.get("nome"))]
            continue
        servicos = (alvo.get("fatos") or {}).get("services")
```

- [x] **Step 7: rodar e confirmar que passa, com a capa, a nota e os goldens verdes**

Rode: `.venv/bin/python -m pytest tests/test_servicos_host.py tests/test_relatorio_sem_host.py -q && .venv/bin/python -m pytest -q -k "capa or nota"`
Esperado: tudo verde. Se `test_saude_por_sistema_mostra_o_host_como_um_sistema` falhar por causa de
`_replicas` com `None`, a correção fica em `_replicas`: réplica `None` conta como "0/1" na soma
exibida. Não mude o teste.

---

### Task 6: campo estruturado `fatos.descobertos`

**Arquivos:**
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/coletores/host.py:23-56` e `:82-84`
- Teste: `tests/test_coletor_host_descoberta.py` (teste novo no fim)

**Depende de:** Task 1. Pode rodar em paralelo com as tasks 2, 3 e 4.

**Contrato que esta task publica:** `registro["fatos"]["descobertos"] = [{"produto": str, "origem": str}]`,
presente só quando há descoberto não declarado.

- [x] **Step 1: escrever o teste que falha**, no fim de `tests/test_coletor_host_descoberta.py`:

```python
def test_descoberto_e_nao_declarado_tambem_vai_estruturado_nos_fatos(monkeypatch):
    registro = _coletar(monkeypatch, SAIDAS, [MARIADB])
    descobertos = registro["fatos"]["descobertos"]
    assert [d["produto"] for d in descobertos] == ["redis", "qdrant"]
    assert all(set(d) == {"produto", "origem"} and d["origem"] for d in descobertos)


def test_sem_descoberto_nao_ha_campo(monkeypatch):
    saidas = {k: v for k, v in SAIDAS.items() if k not in ("servicos", "portas", "containers")}
    registro = _coletar(monkeypatch, saidas, [MARIADB])
    assert "descobertos" not in registro["fatos"]
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_coletor_host_descoberta.py -q -k fatos`
Esperado: FALHA com `KeyError: 'descobertos'` no primeiro teste. O segundo já passa antes da
mudança; ele fica como guarda de regressão, para o campo não aparecer vazio depois.

- [x] **Step 3: `_comparar` devolve também a lista**

Em `scripts/lib/coletores/host.py`, troque o laço final de `_comparar` e o `return`:

```python
    declaradas = {c.get("origem") for c in declarados}
    descobertos = []
    # pela LISTA, não pelo dicionário: candidatos não graváveis compartilham a origem
    # "(não gravável)" e colapsariam numa chave só, perdendo a nota.
    for visto in resultado["candidatos"]:
        origem = visto["origem"]
        if visto["reconhecido"] and origem not in declaradas:
            descobertos.append({"produto": visto["produto"], "origem": origem})
            notas.append(report_mod.na(f"descoberto e não declarado: {visto['produto']} "
                                       f"({origem}) — rode `configurar.py descobrir --alvo "
                                       f"{alvo['nome']}`"))
    return notas, descobertos
```

Atualize a primeira linha da docstring: `"""Declarado × encontrado, por \`origem\`. Devolve (notas, descobertos)."""`.

Em `coletar`, troque `notas = _comparar(alvo, contexto, declarados, erros)` por:

```python
    notas, descobertos = _comparar(alvo, contexto, declarados, erros)
    if descobertos:
        fatos["descobertos"] = descobertos
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_coletor_host_descoberta.py tests/test_coletor_host.py -q`
Esperado: tudo verde.

---

### Task 7: o cartão de problema e o índice

**Arquivos:**
- Criar: `scripts/lib/cartao.py`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/build_report.py:743-744` (`ROTULO_SEVERIDADE` passa a vir de `lib.cartao`)
- Teste: `tests/test_cartao.py`

**Depende de:** Task 2 (`primeiro_passo`) e Task 3 (rótulos).

**Contrato que esta task publica:**
- `cartao.ROTULO`: severidade → rótulo; é o mesmo dicionário de `ROTULO_SEVERIDADE`.
- `cartao.cobrados(achados) -> list` tira os achados esperados.
- `cartao.ancora(achado) -> str`, no formato `p-<alvo>-<componente>-<regra>`, só com `[a-z0-9-]`.
- `cartao.cartao(achado) -> str` devolve o `<article class="fx …" id="…">`. Ele traz a etiqueta com
  ícone, o título, onde, o detalhe, "O que fazer" e o link `#regra-<regra>`.
- `cartao.indice(achados) -> str` devolve uma linha por achado, cada uma com link para `#<ancora>`.

- [x] **Step 1: escrever os testes que falham**

`tests/test_cartao.py`:

```python
from lib import cartao, remediacao

BACKUP = {"regra": "backup_atrasado", "alvo": "banco-01", "componente": "mariadb", "objeto": "mariadb",
          "severidade": "high", "detalhe": "backup mais novo com 5 dias; o limite é 2",
          "como_resolver": remediacao.para("backup_atrasado")}


def test_cartao_traz_o_primeiro_passo_como_o_que_fazer():
    html = cartao.cartao(BACKUP)
    assert "<b>O que fazer</b>" in html and "Veja se a rotina rodou" in html
    assert "<code>systemctl list-timers</code>" in html
    assert 'href="#regra-backup_atrasado"' in html and "ver todos os passos" in html


def test_cartao_mostra_titulo_onde_e_detalhe_com_etiqueta_e_icone():
    html = cartao.cartao(BACKUP)
    assert "Backup do banco mais velho que o limite" in html and "banco-01 · mariadb" in html
    assert "backup mais novo com 5 dias" in html and 'class="bl-tag-crit"' in html and "Alto" in html
    assert 'id="p-banco-01-mariadb-backup-atrasado"' in html


def test_regra_sem_ficha_ainda_diz_o_que_fazer():
    html = cartao.cartao({"regra": "REGRA_NOVA", "alvo": "a", "severidade": "medium"})
    assert "<b>O que fazer</b>" in html and "seção Problemas" in html


def test_texto_da_ficha_e_escapado():
    achado = dict(BACKUP, detalhe="<script>x</script>")
    assert "<script>" not in cartao.cartao(achado)


def test_indice_tem_uma_linha_por_achado_com_link_para_o_cartao():
    outro = dict(BACKUP, regra="servico_reiniciando", severidade="medium", como_resolver=None)
    html = cartao.indice([BACKUP, outro])
    assert html.count("<li>") == 2
    assert 'href="#p-banco-01-mariadb-backup-atrasado"' in html and "Médio" in html


def test_cobrados_tira_o_esperado():
    esperado = {"regra": "OPS_JOB_COMPLETED", "alvo": "a", "severidade": "low"}
    assert cartao.cobrados([BACKUP, esperado]) == [BACKUP]
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_cartao.py -q`
Esperado: FALHA com `ImportError: cannot import name 'cartao'`.

- [x] **Step 3: escrever `scripts/lib/cartao.py`**

```python
"""O cartão curto de um problema: o que é, onde e o primeiro passo de como resolver.

A remediação completa continua na seção Problemas, e o cartão aponta para ela pelo id `regra-<regra>`.
Problema nunca sai sem "O que fazer": sem ficha, o cartão manda para a seção Problemas.
"""
import re

from lib import remediacao
from lib.html_comum import _e
from lib.regras import esperada
from lib.rule_meta import meta

ROTULO = {"critical": "Crítico", "high": "Alto", "medium": "Médio", "low": "Baixo", "info": "Informativo"}
TOM = {"critical": "crit", "high": "crit", "medium": "warn"}


def cobrados(achados):
    return [a for a in achados if not a.get("esperada") and not esperada(a.get("regra"))]


def ancora(achado):
    partes = (achado.get("alvo"), achado.get("componente") or achado.get("alvo"), achado.get("regra"))
    return "p-" + re.sub(r"[^a-z0-9]+", "-", "-".join(str(p or "") for p in partes).lower()).strip("-")


def _inline(texto):
    """Escapa e só então traduz `código` e **negrito**: nada da ficha abre tag."""
    escapado = _e(texto)
    escapado = re.sub(r"`([^`]+)`", r"<code>\1</code>", escapado)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escapado)


def _titulo(achado):
    return (achado.get("como_resolver") or {}).get("titulo") or meta(achado.get("regra"))["label"]


def _onde(achado):
    return " · ".join(str(x) for x in (achado.get("alvo"), achado.get("componente")) if x)


def _etiqueta(achado):
    sev = achado.get("severidade")
    tom = TOM.get(sev, "neutro")
    return (f'<span class="bl-tag-{tom}"><svg class="ic"><use href="#ic-achado"/></svg>'
            f'{_e(ROTULO.get(sev, sev))}</span>')


def cartao(achado):
    regra = achado.get("regra")
    ficha = achado.get("como_resolver") or remediacao.para(regra) or {}
    passo = remediacao.primeiro_passo(ficha.get("como_resolver"))
    fazer = _inline(passo) if passo else "Os passos estão na seção Problemas, mais abaixo."
    detalhe = f'<p class="fx-d">{_e(achado["detalhe"])}</p>' if achado.get("detalhe") else ""
    tom = TOM.get(achado.get("severidade"), "warn")
    return (f'<article class="fx {tom}" id="{ancora(achado)}">'
            f'<p class="fx-p">{_etiqueta(achado)}<span>{_e(_titulo(achado))}</span>'
            f'<span class="onde">{_e(_onde(achado))}</span></p>{detalhe}'
            f'<div class="fx-f"><svg class="ic fx-i"><use href="#ic-corrigir"/></svg>'
            f'<p><b>O que fazer</b>{fazer}</p></div>'
            f'<a class="fx-r" href="#regra-{_e(regra)}">ver todos os passos</a></article>')


def indice(achados):
    linhas = "".join(f'<li>{_etiqueta(a)}<a class="ix-p" href="#{ancora(a)}">{_e(_titulo(a))}</a>'
                     f'<span class="onde">{_e(_onde(a))}</span></li>' for a in achados)
    return f'<ol class="ix">{linhas}</ol>' if linhas else ""
```

- [x] **Step 4: um rótulo de severidade só**

Em `scripts/build_report.py:743-744`, troque a definição de `ROTULO_SEVERIDADE` por
`from lib.cartao import ROTULO as ROTULO_SEVERIDADE`.

- [x] **Step 5: rodar e confirmar que passa, com os goldens verdes**

Rode: `.venv/bin/python -m pytest tests/test_cartao.py tests/test_relatorio_sem_host.py -q`
Esperado: tudo verde.

---

### Task 8: fixture com dois servidores host

**Arquivos:**
- Criar: `tests/fixtures/relatorio_host.py`
- Teste: `tests/test_fixture_host.py`

**Depende de:** Tasks 3 e 6, porque usa a regra nova e o `fatos.descobertos`.

**Contrato que esta task publica:**
- `alvo_host_banco() -> dict` monta o host `banco-01`:
  - mariadb com conexões, tamanho por banco, lentas, binlog e backup de 5 dias contra o limite 2;
  - qdrant com 3 coleções, uma delas `yellow`;
  - redis parado e `pg` ausente;
  - os achados `backup_atrasado`, `servico_reiniciando` (redis, 7 reinícios),
    `servico_declarado_ausente` (pg) e `disco_quase_cheio` (máquina);
  - um descoberto não declarado.
- `alvo_host_sem_vpn() -> dict` monta o host `cache-02`, sem dados.
- `relatorio_com_hosts(base=None) -> dict` acrescenta os dois hosts ao report `base`, ou a um report
  vazio quando não há base.

- [x] **Step 1: escrever o teste que falha**

`tests/test_fixture_host.py`:

```python
from tests.fixtures.relatorio_host import alvo_host_banco, relatorio_com_hosts


def test_fixture_host_tem_os_casos_que_o_relatorio_precisa_mostrar():
    alvo = alvo_host_banco()
    regras = sorted(a["regra"] for a in alvo["achados"])
    assert regras == ["backup_atrasado", "disco_quase_cheio", "servico_declarado_ausente", "servico_reiniciando"]
    assert all(a.get("como_resolver") for a in alvo["achados"])
    assert {c["papel"] for c in alvo["componentes"]} == {"maquina", "banco", "busca", "cache", "app"}
    assert alvo["fatos"]["descobertos"] == [{"produto": "postgres", "origem": "unidade:postgresql.service"}]


def test_relatorio_com_hosts_soma_dois_alvos_ao_inventario():
    r = relatorio_com_hosts()
    assert [a["nome"] for a in r["alvos"]] == ["banco-01", "cache-02"]
    assert len(r["inventario"]) == 2 and r["schema_version"] == 3
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_fixture_host.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'tests.fixtures.relatorio_host'`.

- [x] **Step 3: escrever `tests/fixtures/relatorio_host.py`**

```python
"""Dois servidores host com números fictícios: um com banco, busca e problemas, outro sem VPN."""
import copy

from lib import remediacao


def _r(pergunta, valor):
    return {"pergunta": pergunta, "valor": valor, "fonte": "ssh"}


def _servico(ativo, desde, reinicios, memoria):
    return [_r("servico.ativo", ativo), _r("servico.desde", desde), _r("servico.reinicios", reinicios),
            _r("servico.memoria", memoria)]


def _achado(regra, componente, severidade, detalhe, objeto=None):
    return {"regra": regra, "alvo": "banco-01", "componente": componente, "objeto": objeto or componente,
            "severidade": severidade, "detalhe": detalhe, "como_resolver": remediacao.para(regra)}


def alvo_host_banco():
    maquina = {"nome": "banco-01", "papel": "maquina", "achados": [], "respostas": [
        _r("maquina.cpu", 24.0), _r("maquina.memoria", 78.0), _r("maquina.disco", 93.0),
        _r("maquina.carga", 24.0), _r("maquina.desde_o_boot", 41.0)]}
    mariadb = {"nome": "mariadb", "papel": "banco", "produto": "mariadb", "backup_max_dias": 2,
               "achados": [], "respostas": [
                   *_servico("ativo", 41.0, 0, 2147483648),
                   _r("banco.conexoes", 37), _r("banco.uso_de_conexoes", 24.7), _r("banco.tamanho", 9663676416),
                   _r("banco.tamanho_por_banco", [{"nome": "loja", "bytes": 7516192768},
                                                  {"nome": "erp", "bytes": 1610612736},
                                                  {"nome": "mysql", "bytes": 34003200},
                                                  {"nome": "information_schema", "bytes": None}]),
                   _r("banco.consultas_lentas", 12), _r("banco.binlog", [{"nome": "binlog.000041", "bytes": 1048576}]),
                   _r("banco.backup_idade", 5)]}
    qdrant = {"nome": "qdrant", "papel": "busca", "produto": "qdrant", "achados": [], "respostas": [
        *_servico("ativo", 12.0, 1, 805306368),
        _r("busca.colecoes", [{"nome": "docs", "pontos": 120400, "status": "green"},
                              {"nome": "faq", "pontos": 3100, "status": "yellow"},
                              {"nome": "vazia", "pontos": 0, "status": "green"}])]}
    redis = {"nome": "redis", "papel": "cache", "produto": "redis", "achados": [],
             "respostas": _servico("failed", None, 7, None)}
    pg = {"nome": "pg", "papel": "banco", "produto": "postgres", "achados": [], "respostas": []}
    api = {"nome": "loja-api", "papel": "app", "achados": [], "respostas": _servico("ativo", 3.0, 0, 314572800)}
    achados = [_achado("backup_atrasado", "mariadb", "high", "backup mais novo com 5 dias; o limite é 2"),
               _achado("servico_reiniciando", "redis", "medium", "7 reinícios registrados pelo gerenciador do serviço"),
               _achado("servico_declarado_ausente", "pg", "high", "declarado no alvos.toml e não encontrado"),
               _achado("disco_quase_cheio", "banco-01", "high", "93% do disco em uso", objeto="banco-01")]
    return {"nome": "banco-01", "tipo": "host", "onde": "ssh: banco-01", "saude": "🟡", "coletado": True,
            "dimensoes": {}, "cobertura": {}, "analise": "",
            "fatos": {"usuario": "root", "kernel": "Linux 6.1.0-18-amd64",
                      "sistema": "Debian GNU/Linux 12 (bookworm)",
                      "acesso": "Acesso com a identidade SSH de quem executou a auditoria (root).",
                      "descobertos": [{"produto": "postgres", "origem": "unidade:postgresql.service"}]},
            "componentes": [maquina, mariadb, qdrant, redis, pg, api], "achados": achados,
            "nao_coletado": [{"valor": None, "motivo": "descoberto e não declarado: postgres "
                                                       "(unidade:postgresql.service) — rode `configurar.py "
                                                       "descobrir --alvo banco-01`"}]}


def alvo_host_sem_vpn():
    return {"nome": "cache-02", "tipo": "host", "onde": "ssh: cache-02", "saude": "sem dados", "coletado": True,
            "dimensoes": {}, "cobertura": {}, "analise": "", "fatos": {}, "componentes": [], "achados": [],
            "nao_coletado": [{"valor": None, "motivo": "não abri a sessão para cache-02 (a VPN está ligada?)"}]}


def relatorio_com_hosts(base=None):
    r = copy.deepcopy(base) if base else {
        "schema_version": 3, "generated_at": "2026-11-14T09:12:00Z", "alvos": [], "inventario": [],
        "aceites": [], "historico": {}, "resumo": "", "fortes": [], "fracos": [], "recomendacoes": []}
    for alvo in (alvo_host_banco(), alvo_host_sem_vpn()):
        r["alvos"].append(alvo)
        r["inventario"].append({"nome": alvo["nome"], "tipo": "host", "onde": alvo["onde"], "saude": alvo["saude"]})
    r.pop("nota_geral", None)          # a nota recalcula com os hosts
    return r
```

Atenção: o achado `servico_reiniciando` do redis vem com 7 reinícios para casar com a resposta
`servico.reinicios` do componente.

- [x] **Step 4: rodar e confirmar que passa**

Rode: `.venv/bin/python -m pytest tests/test_fixture_host.py -q`
Esperado: 2 passed.

---

### Task 9: os adaptadores levam os dados novos aos blocos

**Arquivos:**
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/dados_blocos.py:93-112` (o `_simples` ganha o `ajustar` com o componente) e `:186-200` (`ADAPTADORES`)
- Teste: `tests/test_dados_blocos_host.py`

**Depende de:** Tasks 7 e 8.

**Contrato que esta task publica:**
- `dados_do_papel("banco", alvos)`: cada item ganha `uso`, `por_banco`, `lentas`, `binlog`,
  `backup`, `backup_max` (só com backup medido) e `problemas`. `problemas` só existe em alvo `host`
  e quando há achado.
- `dados_do_papel("busca", alvos)` → `{"itens": [{"nome", "alvo", "colecoes", "motivo", "problemas"}]}`
  ou `{"motivo": SEM_FONTE}`.
- `dados_do_papel("maquinas", alvos)`: os itens ganham `carga`, `boot` e `problemas`. `problemas` só
  existe em alvo `host` e quando há achado.
- `dados_do_papel("servidores", alvos)` → `{"itens": [...]}` com um item por alvo `host`. Sem host,
  devolve `{}`. Cada item traz:
  - `nome`, `sistema`, `kernel`, `acesso`;
  - `servicos`: lista de `{nome, papel, produto, ativo, ausente, desde, reinicios, memoria}`;
  - `problemas`: só os achados de componentes cujo papel não tem bloco próprio;
  - `todos`: todos os achados cobrados do servidor;
  - `descobertos` e `nao_medido`.
- `dados_blocos.PAPEIS_EM_BLOCO_PROPRIO = {"banco", "busca", "maquina"}`.

- [x] **Step 1: escrever os testes que falham**

`tests/test_dados_blocos_host.py`:

```python
from lib.dados_blocos import dados_do_papel
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_host import alvo_host_banco, alvo_host_sem_vpn


def _por_nome(itens):
    return {i["nome"]: i for i in itens}


def test_banco_do_host_traz_os_campos_do_produto_e_o_problema():
    mariadb = _por_nome(dados_do_papel("banco", [alvo_host_banco()])["itens"])["mariadb"]
    assert (mariadb["uso"], mariadb["lentas"], mariadb["backup"], mariadb["backup_max"]) == (24.7, 12, 5, 2)
    assert [b["nome"] for b in mariadb["por_banco"]][:2] == ["loja", "erp"]
    assert [p["regra"] for p in mariadb["problemas"]] == ["backup_atrasado"]


def test_banco_ausente_aparece_com_o_problema_mesmo_sem_medida():
    pg = _por_nome(dados_do_papel("banco", [alvo_host_banco()])["itens"])["pg"]
    assert [p["regra"] for p in pg["problemas"]] == ["servico_declarado_ausente"]


def test_banco_do_cluster_nao_ganha_problemas():
    item = dados_do_papel("banco", relatorio_docker()["alvos"])["itens"][0]
    assert "problemas" not in item and item["conexoes"] == 18


def test_busca_traz_as_colecoes():
    item = dados_do_papel("busca", [alvo_host_banco()])["itens"][0]
    assert item["nome"] == "qdrant" and [c["nome"] for c in item["colecoes"]] == ["docs", "faq", "vazia"]


def test_sem_busca_o_bloco_tem_so_o_motivo():
    assert set(dados_do_papel("busca", relatorio_docker()["alvos"])) == {"motivo"}


def test_maquina_do_host_traz_carga_boot_e_problema():
    item = _por_nome(dados_do_papel("maquinas", [alvo_host_banco()])["itens"])["banco-01"]
    assert (item["carga"], item["boot"]) == (24.0, 41.0)
    assert [p["regra"] for p in item["problemas"]] == ["disco_quase_cheio"]


def test_servidores_separa_os_problemas_que_tem_bloco_proprio():
    item = dados_do_papel("servidores", [alvo_host_banco()])["itens"][0]
    assert [p["regra"] for p in item["problemas"]] == ["servico_reiniciando"]
    assert len(item["todos"]) == 4
    assert [s["nome"] for s in item["servicos"]] == ["mariadb", "qdrant", "redis", "pg", "loja-api"]
    pg = _por_nome(item["servicos"])["pg"]
    assert pg["ausente"] is True and pg["ativo"] is None
    assert item["descobertos"] == [{"produto": "postgres", "origem": "unidade:postgresql.service"}]
    assert item["nao_medido"] == []


def test_servidor_sem_vpn_diz_por_que_nao_foi_medido():
    item = dados_do_papel("servidores", [alvo_host_sem_vpn()])["itens"][0]
    assert item["servicos"] == [] and "VPN" in item["nao_medido"][0]


def test_sem_host_nao_ha_servidores():
    assert dados_do_papel("servidores", relatorio_docker()["alvos"]) == {}
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_dados_blocos_host.py -q`
Esperado: FALHA com `KeyError: 'uso'` e asserções erradas nos de busca, máquina e servidores.

- [x] **Step 3: `_simples` passa o componente ao `ajustar`**

Hoje o `ajustar` recebe `(alvo, item)`. Ele passa a receber `(alvo, comp, item)`, porque o banco
precisa de `backup_max_dias`, que está no componente. Em `_simples`:

```python
                if ajustar:
                    ajustar(alvo, comp, item)
```

Em `_com_dominio`, troque só a assinatura; o corpo não usa o componente:

```python
def _com_dominio(alvo, _comp, item):
```

- [x] **Step 4: escrever os adaptadores novos em `scripts/lib/dados_blocos.py`**, antes de `ADAPTADORES`:

```python
PAPEIS_EM_BLOCO_PROPRIO = {"banco", "busca", "maquina"}
_DESCOBERTO = "descoberto e não declarado"


def _motivo(comp, pergunta):
    for r in comp.get("respostas") or []:
        if r.get("pergunta") == pergunta and r.get("sem_dados"):
            return r.get("motivo")
    return None


def _problemas_de(alvo, nome):
    """Só no host: o cartão no bloco é para o que a auditoria do servidor achou."""
    if alvo.get("tipo") != "host":
        return []
    from lib.cartao import cobrados
    return [a for a in cobrados(alvo.get("achados") or []) if (a.get("componente") or alvo.get("nome")) == nome]


def _com_problemas(alvo, comp, item):
    problemas = _problemas_de(alvo, comp.get("nome"))
    if problemas:
        item["problemas"] = problemas


def _do_banco(alvo, comp, item):
    from lib.limites_produto import BACKUP_MAX_DIAS_PADRAO
    if item.get("backup") is not None:
        item["backup_max"] = comp.get("backup_max_dias") or BACKUP_MAX_DIAS_PADRAO
    _com_problemas(alvo, comp, item)


def _busca(alvos):
    itens = [{"nome": c.get("nome"), "alvo": a.get("nome"), "colecoes": _resposta(c, "busca.colecoes"),
              "motivo": _motivo(c, "busca.colecoes"), "problemas": _problemas_de(a, c.get("nome"))}
             for a in alvos for c in _componentes("busca", [a])]
    return {"itens": itens} if itens else {"motivo": SEM_FONTE}


def _servico(alvo, comp):
    ausentes = {a.get("componente") for a in alvo.get("achados") or [] if a.get("regra") == "servico_declarado_ausente"}
    return {"nome": comp.get("nome"), "papel": comp.get("papel"), "produto": comp.get("produto"),
            "ativo": _resposta(comp, "servico.ativo"), "ausente": comp.get("nome") in ausentes,
            "desde": _resposta(comp, "servico.desde"), "reinicios": _resposta(comp, "servico.reinicios"),
            "memoria": _resposta(comp, "servico.memoria")}


def _servidores(alvos):
    from lib.cartao import cobrados
    itens = []
    for alvo in alvos:
        if alvo.get("tipo") != "host" or alvo.get("coletado") is False:
            continue
        fatos = alvo.get("fatos") or {}
        papeis = {c.get("nome"): c.get("papel") for c in alvo.get("componentes") or []}
        todos = cobrados(alvo.get("achados") or [])
        motivos = [str(n.get("motivo") or n.get("reason") or "") for n in alvo.get("nao_coletado") or []]
        itens.append({
            "nome": alvo.get("nome"), "sistema": fatos.get("sistema"), "kernel": fatos.get("kernel"),
            "acesso": fatos.get("acesso"),
            "servicos": [_servico(alvo, c) for c in alvo.get("componentes") or [] if c.get("papel") != "maquina"],
            "problemas": [a for a in todos
                          if papeis.get(a.get("componente") or alvo.get("nome")) not in PAPEIS_EM_BLOCO_PROPRIO],
            "todos": todos, "descobertos": fatos.get("descobertos") or [],
            "nao_medido": [m for m in motivos if m and not m.startswith(_DESCOBERTO)]})
    return {"itens": itens} if itens else {}
```

- [x] **Step 5: registrar em `ADAPTADORES`**

```python
    "banco": _simples("banco", {"conexoes": "banco.conexoes", "tamanho": "banco.tamanho",
                                "uso": "banco.uso_de_conexoes", "por_banco": "banco.tamanho_por_banco",
                                "lentas": "banco.consultas_lentas", "binlog": "banco.binlog",
                                "backup": "banco.backup_idade"}, ajustar=_do_banco),
    "busca": _busca,
    "servidores": _servidores,
```

e em `"maquinas"`:

```python
    "maquinas": _simples("maquina", {"cpu": "maquina.cpu", "memoria": "maquina.memoria",
                                     "disco": "maquina.disco", "dias": "maquina.disco_dias",
                                     "carga": "maquina.carga", "boot": "maquina.desde_o_boot"},
                        ajustar=_com_problemas, manter_sem_medida=True),
```

- [x] **Step 6: rodar e confirmar que passa, e ajustar os testes que comparam item inteiro**

Rode: `.venv/bin/python -m pytest tests/test_dados_blocos_host.py -q && .venv/bin/python -m pytest -q`
Esperado: os testes novos passam. Alguns testes antigos podem comparar o dicionário inteiro do item
de banco ou de máquina. Eles passam a ver `uso`, `por_banco`, `lentas`, `binlog`, `backup`, `carga`
e `boot`, todos `None`. Nesses testes, acrescente as chaves novas ao dicionário esperado, com valor
`None`, sem mudar mais nada. Os goldens (`tests/test_relatorio_sem_host.py`) têm que continuar
verdes.

---

### Task 10: Bancos, Máquinas e o bloco Busca

**Arquivos:**
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/blocos/banco.py` (inteiro)
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/blocos/maquinas.py:11-42` e `:72-81`
- Criar: `scripts/lib/blocos/busca.py`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/blocos/__init__.py:22` (importa `busca`)
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/assets/report-template/template_v3.html` (CSS dos cartões, servidores, informativo e busca)
- Teste: `tests/test_blocos_host.py`

**Depende de:** Tasks 4, 7 e 9.

- [x] **Step 1: escrever os testes que falham**

`tests/test_blocos_host.py`:

```python
from lib.blocos import render_bloco
from lib.dados_blocos import dados_do_papel
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_host import alvo_host_banco


def _html(papel, alvos):
    return render_bloco(papel, dados_do_papel(papel, alvos))


def test_banco_do_host_mostra_medidores_barras_e_o_cartao():
    html = _html("banco", [alvo_host_banco()])
    assert "Conexões em uso" in html and "alerta em 80%" in html
    assert "Idade do backup" in html and "limite 2 dias" in html and "acima do limite" in html
    assert "Tamanho por banco" in html and ">loja<" in html
    assert "Consultas lentas" in html and "Binlog" in html
    assert 'id="p-banco-01-mariadb-backup-atrasado"' in html and "<b>O que fazer</b>" in html


def test_banco_do_cluster_nao_ganha_campo_que_nao_existe():
    html = _html("banco", relatorio_docker()["alvos"])
    assert "Idade do backup" not in html and "Tamanho por banco" not in html and "Binlog" not in html
    assert "loja_db" in html and "18 conexões" in html


def test_maquinas_mostra_carga_boot_marca_de_90_e_o_cartao_fora_da_grade():
    html = _html("maquinas", [alvo_host_banco()])
    assert "Carga" in html and "Desde o boot" in html and "41 dias" in html
    assert 'class="gf-lim" x="90.00%"' in html
    assert html.index('class="bl-maqs"') < html.index('id="p-banco-01-banco-01-disco-quase-cheio"')


def test_busca_mostra_colecoes_com_status_em_icone_e_rotulo():
    html = _html("busca", [alvo_host_banco()])
    assert "Busca" in html and ">docs<" in html and "status yellow" in html
    assert 'class="bl-tag-warn"' in html and "Otimizando" in html


def test_sem_busca_o_bloco_some():
    assert _html("busca", relatorio_docker()["alvos"]) == ""
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_blocos_host.py -q`
Esperado: FALHA. Não há medidor nem cartão, e a Busca cai no painel genérico.

- [x] **Step 3: reescrever `scripts/lib/blocos/banco.py`**

```python
from lib import cartao, graficos
from lib.blocos import bloco
from lib.html_comum import inteiro, medido, nao_medido, painel, percentual, plural, tamanho
from lib.limites_produto import LIMITE_DE_CONEXOES


def _conexoes(n):
    return f"Conexões: {medido(n)}" if n is None else f"{inteiro(n)} {'conexão' if n == 1 else 'conexões'}"


def _dias(n):
    return plural(round(n), "dia", "dias")


def _fatos(i):
    """Cada campo só quando existe: banco do cluster não ganha linha de "sem dado" que nunca teria."""
    linhas = [f'<dt>Tamanho</dt><dd>{medido(i.get("tamanho"), tamanho)}</dd>']
    if i.get("lentas") is not None:
        linhas.append(f'<dt>Consultas lentas</dt><dd>{inteiro(i["lentas"])}</dd>')
    if i.get("binlog"):
        total = sum(b.get("bytes") or 0 for b in i["binlog"])
        linhas.append(f'<dt>Binlog</dt><dd>{plural(len(i["binlog"]), "arquivo", "arquivos")} · {tamanho(total)}</dd>')
    return f'<dl>{"".join(linhas)}</dl>'


def _graficos(i):
    partes = []
    if i.get("uso") is not None:
        partes.append(graficos.medidor(i["uso"], 100, LIMITE_DE_CONEXOES, "Conexões em uso",
                                       percentual(i["uso"]), sub="do máximo que o banco aceita",
                                       acima="warn", marca_texto=f"alerta em {LIMITE_DE_CONEXOES}%"))
    if i.get("backup") is not None:
        maximo = max(i["backup_max"] * 2, i["backup"] + 1)
        partes.append(graficos.medidor(i["backup"], maximo, i["backup_max"], "Idade do backup",
                                       _dias(i["backup"]), sub="backup mais novo da pasta",
                                       acima="crit", marca_texto=f'limite {_dias(i["backup_max"])}'))
    if i.get("por_banco"):
        partes.append('<h5 class="sub-h">Tamanho por banco</h5>' + graficos.barras(
            [(b.get("nome"), b.get("bytes")) for b in i["por_banco"]], tamanho,
            f'Tamanho por banco em {i.get("nome")}'))
    return "".join(partes)


def _item(i):
    problemas = "".join(cartao.cartao(p) for p in i.get("problemas") or [])
    cartoes = f'<div class="fxs">{problemas}</div>' if problemas else ""
    return (f'<div class="bl-db">{cartoes}<b>{medido(i.get("nome"))}</b><span>{_conexoes(i.get("conexoes"))}</span>'
            f'{_fatos(i)}{_graficos(i)}</div>')


@bloco("banco")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return painel("Bancos de dados", "", nao_medido(dados.get("motivo", "sem fonte")))
    return painel("Bancos de dados", plural(len(itens), "medido", "medidos"), "".join(_item(i) for i in itens))
```

- [x] **Step 4: Máquinas com barra em SVG, carga, boot e os cartões**

Em `scripts/lib/blocos/maquinas.py`, troque o import por
`from lib import cartao, graficos`, mais `from lib.html_comum import _e, inteiro, medido, nao_medido, painel, percentual, plural`.
Acrescente `MARCA_DE_USO = 90` e troque `_medida` e `_cartao`:

```python
MARCA_DE_USO = 90


def _medida(rotulo, uso):
    if uso is None:
        return f'<div class="bl-med"><span>{rotulo}</span><b>{medido(uso)}</b></div>'
    tom = _tom(uso)
    titulo = f"{rotulo}: {percentual(uso)}, limite {MARCA_DE_USO}%"
    return (f'<div class="bl-med"><span>{rotulo}</span><b class="bl-c-{tom}">{percentual(uso)}</b>'
            f'{graficos.barra(uso, titulo, "acc" if tom == "ok" else tom, MARCA_DE_USO)}</div>')


def _boot(dias):
    texto = "menos de 1 dia" if dias < 1 else plural(round(dias), "dia", "dias")
    return f'<div class="bl-med"><span>Desde o boot</span><b>{texto}</b></div>'


def _cartao(i):
    carga = _medida("Carga", i["carga"]) if i.get("carga") is not None else ""
    boot = _boot(i["boot"]) if i.get("boot") is not None else ""
    return (f'<article class="bl-maq"><header><b>{medido(i.get("nome"))}</b></header>'
            f'{_medida("CPU", i.get("cpu"))}{_medida("Memória", i.get("memoria"))}'
            f'{_medida("Disco", i.get("disco"))}{carga}{_previsao(i.get("dias"))}{boot}</article>')
```

No `render`, troque a última linha por:

```python
    problemas = "".join(cartao.cartao(p) for i in itens for p in i.get("problemas") or [])
    cartoes = f'<div class="fxs bl-maq-fx">{problemas}</div>' if problemas else ""
    return painel("Máquinas", resumo, f'<div class="bl-maqs">{"".join(_cartao(i) for i in itens)}</div>{cartoes}{nos}',
                  cheio=True)
```

E na contagem de `medidas`, inclua `carga` e `boot`:
`any(i.get(k) is not None for k in ("cpu", "memoria", "disco", "dias", "carga", "boot"))`.

- [x] **Step 5: criar `scripts/lib/blocos/busca.py`**

```python
"""Coleções da busca vetorial (Qdrant): pontos em barra, e o status em ícone e rótulo."""
from lib import cartao, graficos
from lib.blocos import bloco
from lib.html_comum import _e, humano, nao_medido, painel, plural

# o que o Qdrant quer dizer com cada cor: verde pronto, amarelo otimizando, vermelho com erro
STATUS = {"green": ("ok", "Pronta"), "yellow": ("warn", "Otimizando"), "red": ("crit", "Com erro"),
          "grey": ("neutro", "Otimização pendente")}
COLECOES_MAX = 8


def _colecao(c, maior):
    tom, rotulo = STATUS.get(c.get("status"), ("neutro", "sem status"))
    pontos = c.get("pontos")
    titulo = f'{c.get("nome")}: {humano(pontos) if pontos is not None else "sem dado"} pontos'
    grafico = graficos.barra(pontos * 100 / maior if pontos else 0, titulo, alto=12, trilha=False)
    valor = f'{humano(pontos)} pontos' if pontos is not None else "sem dado"
    return (f'<div class="qd-r"><div class="qd-t"><b class="qd-n">{_e(c.get("nome"))}</b>'
            f'<span class="tec">status {_e(c.get("status") or "—")}</span>{graficos.etiqueta(tom, rotulo)}</div>'
            f'<div class="qd-g">{grafico}<span class="br-v">{_e(valor)}</span></div></div>')


def _item(i):
    problemas = "".join(cartao.cartao(p) for p in i.get("problemas") or [])
    cartoes = f'<div class="fxs">{problemas}</div>' if problemas else ""
    colecoes = sorted(i.get("colecoes") or [], key=lambda c: (-(c.get("pontos") or 0), str(c.get("nome"))))
    if not colecoes:
        corpo = nao_medido(i.get("motivo") or "nenhuma coleção respondeu")
    else:
        maior = max((c.get("pontos") or 0) for c in colecoes) or 1
        resto = len(colecoes) - COLECOES_MAX
        mais = f'<p class="br-mais">e mais {resto}</p>' if resto > 0 else ""
        corpo = f'<div class="qd">{"".join(_colecao(c, maior) for c in colecoes[:COLECOES_MAX])}</div>{mais}'
    return f'<div class="bl-db">{cartoes}<b>{_e(i.get("nome"))} · {_e(i.get("alvo"))}</b>{corpo}</div>'


@bloco("busca")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return ""
    colecoes = sum(len(i.get("colecoes") or []) for i in itens)
    return painel("Busca", plural(colecoes, "coleção", "coleções"), "".join(_item(i) for i in itens), cheio=True)
```

Em `scripts/lib/blocos/__init__.py`, acrescente `"busca"` e `"servidores"` à tupla do laço
`for _modulo in (...)`. O módulo `servidores` nasce na task 11. Até lá, acrescente só `"busca"`.

- [x] **Step 6: CSS dos cartões, dos servidores, do informativo e da busca no template**, logo depois do
CSS dos gráficos (task 4), antes do `@media print{`. Entra aqui, e não na task 11, porque
`test_template_conhece_o_que_o_relatorio_emite.py` acusa classe emitida sem regra (`fxs`, `qd`, `bl-maq-fx`…):

```css
/* SERVICOS DOS SERVIDORES, CARTAO DE PROBLEMA, INFORMATIVO E BUSCA.
   Espaco pela escala --s*: grupo --s5, servidor --s7, itens --s3/--s4, linhas --s2. */
.sv-topo{padding:var(--s4) var(--s5);border-bottom:1px solid var(--fio);background:color-mix(in srgb,var(--crit) 4%,var(--campo))}
.sv-topo h4{font:700 19px/1.25 var(--disp);letter-spacing:-.012em;margin-bottom:var(--s2)}
.ix li{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:4px var(--s3);padding:var(--s2) 0;border-top:1px solid var(--linha)}
.ix li:first-child{border-top:0}
.ix-p{font-weight:600;color:var(--tinta);text-decoration:none}
.ix .onde,.fx-p .onde{font:500 12.5px/1.4 var(--mono);color:var(--fraco);text-align:right}
.srv{padding:var(--s5)}
.srv+.srv{border-top:var(--s3) solid var(--papel)}
.srv-h{display:grid;gap:var(--s2);padding-bottom:var(--s4);border-bottom:1px solid var(--fio);break-inside:avoid;break-after:avoid}
.srv-h h4{font:700 22px/1.2 var(--disp);letter-spacing:-.015em}
.srv-meta{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:4px var(--s3);margin:0;font-size:13.5px;color:var(--tinta2)}
.srv-meta dt{color:var(--fraco)}
.srv-meta dd{margin:0}
.grp{margin-top:var(--s5)}
.grp>h5{display:flex;align-items:center;gap:var(--s2);font:600 12px/1.3 var(--sans);color:var(--fraco);text-transform:uppercase;letter-spacing:.07em;margin:0 0 var(--s3);break-after:avoid}
.grp>h5::after{content:"";flex:1;height:1px;background:var(--linha)}
.sub-h{font:600 13.5px/1.3 var(--sans);color:var(--tinta2);margin:var(--s4) 0 var(--s2)}
.fxs{display:grid;gap:var(--s3);margin-bottom:var(--s3)}
.bl-maq-fx{padding:var(--s3)}
.fx{display:grid;gap:var(--s2);padding:var(--s4);border-radius:var(--r);break-inside:avoid;border:1px solid color-mix(in srgb,var(--warn) 32%,var(--fio));background:color-mix(in srgb,var(--warn) 5%,var(--campo))}
.fx.crit{border-color:color-mix(in srgb,var(--crit) 32%,var(--fio));background:color-mix(in srgb,var(--crit) 5%,var(--campo))}
.fx-p{display:flex;flex-wrap:wrap;align-items:center;gap:4px var(--s2);margin:0;font:600 15.5px/1.4 var(--sans);color:var(--tinta)}
.fx-p .onde{margin-left:auto}
.fx-d{font-size:14px;color:var(--tinta2);margin:0}
.fx-f{display:grid;grid-template-columns:auto minmax(0,1fr);gap:var(--s2);padding:var(--s3);border-radius:var(--r2);background:var(--campo);border:1px solid var(--linha)}
.fx-i{width:16px;height:16px;margin-top:3px;color:var(--acc)}
.fx-f p{font-size:14.5px;line-height:1.6;color:var(--tinta2);margin:0}
.fx-f b{display:block;font:600 13px/1.4 var(--sans);color:var(--tinta);margin-bottom:2px}
.fx-r{font:500 12px/1.4 var(--mono);color:var(--acc)}
.svc{padding:var(--s2) 0;border-top:1px solid var(--linha);break-inside:avoid}
.svc:first-child{border-top:0}
.svc.alerta{background:color-mix(in srgb,var(--warn) 6%,var(--campo));margin:0 calc(-1 * var(--s2));padding-left:var(--s2);padding-right:var(--s2);border-radius:var(--r2)}
.svc-t{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:4px var(--s3)}
.svc-t b{font:600 15px/1.3 var(--mono);letter-spacing:-.02em}
.tec{font:500 12px/1.4 var(--mono);color:var(--fraco);margin-left:var(--s1)}
.st-ok{display:inline-flex;align-items:center;gap:4px;font-weight:600;font-size:13.5px;color:var(--ok)}
.fatos{display:flex;flex-wrap:wrap;gap:4px var(--s5);margin:var(--s1) 0 0}
.fatos div{display:grid;min-width:7rem}
.fatos dt{font-size:12.5px;color:var(--fraco)}
.fatos dd{margin:0;font:600 14.5px/1.4 var(--mono);font-variant-numeric:tabular-nums}
.rei-alto{display:inline-flex;align-items:center;gap:4px}
.infs{display:grid;gap:var(--s2)}
.inf{display:grid;grid-template-columns:auto minmax(0,1fr);gap:var(--s2);padding:var(--s3);border:1px solid var(--fio);border-radius:var(--r);background:var(--papel);break-inside:avoid}
.inf-i{width:16px;height:16px;margin-top:3px;color:var(--fraco)}
.inf-p{font:600 14.5px/1.45 var(--sans);color:var(--tinta2);margin:0}
.inf-f{font-size:14px;line-height:1.6;color:var(--tinta2);margin:4px 0 0}
.qd{display:grid;gap:var(--s2);margin-top:var(--s2)}
.qd-r{display:grid;gap:var(--s1);padding-bottom:var(--s2);border-bottom:1px solid var(--linha)}
.qd-r:last-child{border-bottom:0;padding-bottom:0}
.qd-t{display:flex;flex-wrap:wrap;align-items:center;gap:4px var(--s2)}
.qd-n{font:600 14.5px/1.3 var(--mono)}
.qd-t .bl-tag-ok,.qd-t .bl-tag-warn,.qd-t .bl-tag-crit,.qd-t .bl-tag-neutro{margin-left:auto}
.qd-g{display:grid;grid-template-columns:minmax(0,1fr) 8.5rem;gap:var(--s3);align-items:center}
.bl-db .mt:first-of-type{margin-top:var(--s3)}
@media (max-width:640px){
  .srv{padding:var(--s4) var(--s3)}
  .sv-topo{padding:var(--s4) var(--s3)}
  .ix li{grid-template-columns:auto minmax(0,1fr)}
  .ix .onde{grid-column:2;text-align:left}
  .fx{padding:var(--s3)}
  .fx-p .onde{margin-left:0;flex-basis:100%;text-align:left}
  .br{grid-template-columns:minmax(0,6.5rem) minmax(0,1fr) 4.6rem;column-gap:var(--s2)}
  .srv-meta{grid-template-columns:minmax(0,1fr)}
}
```

E dentro do `@media print{` que já existe na linha 1075, logo depois de `.bl-pn{break-inside:avoid}`, acrescente:

```css
  .fx,.inf,.svc,.srv-h,.mt,.qd-r{break-inside:avoid}
  .srv{padding:var(--s3) var(--s4)}
  /* painel alto não pula de página inteiro: o `.bl-pn{break-inside:avoid}` deixava folha quase vazia */
  .bl-pn:has(.srv),.bl-pn:has(.qd),.bl-pn:has(.bl-db .mt),.bl-db:has(.mt){break-inside:auto}
```

- [x] **Step 7: rodar e confirmar que passa, com a suíte e os goldens verdes**

Rode: `.venv/bin/python -m pytest tests/test_blocos_host.py tests/test_relatorio_sem_host.py -q && .venv/bin/python -m pytest -q`
Esperado: tudo verde. Se um teste antigo de Máquinas procurar o `<span class="bl-bar">`, troque a
asserção pela presença de `class="gf"` no mesmo trecho. É a mudança de Máquinas que o spec autoriza.

---

### Task 11: bloco "Serviços dos servidores" e a ligação no relatório

**Arquivos:**
- Criar: `scripts/lib/blocos/servidores.py`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/blocos/__init__.py:22`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/build_report.py:1531-1550` (`id` no `bl-prob`), `:1705` (`PAPEIS_COM_BLOCO`), `:1993-1998` (`_outros_papeis`) e `:2016-2023` (`_blocos_tecnicos`)
- Teste: `tests/test_relatorio_host.py` (começa aqui; a task 12 completa)

**Depende de:** Task 10.

- [x] **Step 1: escrever os testes que falham**

`tests/test_relatorio_host.py`:

```python
import build_report as br
from tests.fixtures.relatorio_host import relatorio_com_hosts


def _html():
    return br.render_html_v3(relatorio_com_hosts())


def test_servicos_dos_servidores_tem_indice_e_uma_area_por_servidor():
    html = _html()
    assert "Serviços dos servidores" in html and html.count('<div class="srv">') == 2
    assert html.count('<ol class="ix">') == 1 and html.count('class="ix-p"') == 4


def test_area_do_servidor_tem_os_tres_grupos_na_ordem():
    html = _html()
    inicio = html.index('<div class="srv">')
    area = html[inicio:html.index('<div class="srv">', inicio + 1)]
    assert area.index("Problemas e o que fazer") < area.index("Estado dos serviços") < area.index("Informativo")
    assert "Debian GNU/Linux 12" in area and "Acesso com a identidade SSH" in area


def test_reinicio_alto_destacado_e_memoria_em_barras():
    html = _html()
    assert 'class="svc alerta"' in html and 'class="rei-alto bl-c-warn"' in html
    assert "Memória por serviço" in html


def test_informativo_diz_o_que_fazer_com_o_descoberto_e_o_nao_medido():
    html = _html()
    assert "Descoberto e não declarado: postgres" in html and "configurar.py descobrir --alvo banco-01" in html
    assert "a VPN está ligada?" in html


def test_problema_da_secao_problemas_tem_ancora_para_o_link_do_cartao():
    html = _html()
    assert 'id="regra-backup_atrasado"' in html and 'href="#regra-backup_atrasado"' in html


def test_busca_aparece_e_o_host_nao_vai_para_outros_sistemas():
    html = _html()
    assert "<h3>Busca</h3>" in html and "Outros sistemas" not in html
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `.venv/bin/python -m pytest tests/test_relatorio_host.py -q`
Esperado: FALHA. "Serviços dos servidores" ainda não existe.

- [x] **Step 3: criar `scripts/lib/blocos/servidores.py`**

```python
"""Um bloco para os servidores host: o índice de problemas no topo, e uma área por servidor com os
grupos "Problemas e o que fazer", "Estado dos serviços" e "Informativo", nesta ordem.

A máquina do servidor (disco, memória, carga) fica no bloco Máquinas, e o banco e a busca nos blocos
deles: aqui entram só os problemas de quem não tem bloco próprio.
"""
import re

from lib import cartao, graficos
from lib.blocos import bloco
from lib.html_comum import SEM_DADO, _e, inteiro, medido, painel, plural, tamanho
from lib.limites_produto import LIMITE_DE_REINICIOS


def _ic(nome, classe="ic"):
    return f'<svg class="{classe}"><use href="#ic-{nome}"/></svg>'


def _grupo(titulo, corpo):
    return f'<div class="grp"><h5>{_e(titulo)}</h5>{corpo}</div>'


def _dias(d):
    return "menos de 1 dia" if d < 1 else plural(round(d), "dia", "dias")


def _estado(sv):
    if sv["ausente"]:
        return f'<span class="bl-tag-crit">{_ic("ruim")}não encontrado</span>'
    if sv["ativo"] is None:
        return f'<span class="bl-tag-neutro">{_ic("ruim")}não medido</span>'
    if sv["ativo"] == "ativo":
        return f'<span class="st-ok">{_ic("bom")}ativo</span>'
    return f'<span class="bl-tag-crit">{_ic("ruim")}{_e(sv["ativo"])}</span>'


def _reinicios(n):
    if n is None:
        return SEM_DADO
    if n >= LIMITE_DE_REINICIOS:
        return f'<span class="rei-alto bl-c-warn">{_ic("achado")}{inteiro(n)}</span>'
    return inteiro(n)


def _servico(sv):
    reinicia = sv["reinicios"] is not None and sv["reinicios"] >= LIMITE_DE_REINICIOS
    parado = sv["ausente"] or sv["ativo"] not in (None, "ativo")
    classe = "svc alerta" if reinicia or parado else "svc"
    como = " · ".join(str(x) for x in (sv.get("produto"), sv.get("papel")) if x)
    return (f'<div class="{classe}"><div class="svc-t"><span><b>{_e(sv["nome"])}</b>'
            f'<span class="tec">{_e(como)}</span></span>{_estado(sv)}</div>'
            f'<dl class="fatos"><div><dt>No ar há</dt><dd>{medido(sv["desde"], _dias)}</dd></div>'
            f'<div><dt>Reinícios</dt><dd>{_reinicios(sv["reinicios"])}</dd></div>'
            f'<div><dt>Memória</dt><dd>{medido(sv["memoria"], tamanho)}</dd></div></dl></div>')


def _memoria(s):
    if not any(sv["memoria"] is not None for sv in s["servicos"]):
        return ""
    itens = [(sv["nome"], sv["memoria"]) for sv in s["servicos"]]
    return ('<h5 class="sub-h">Memória por serviço</h5>'
            + graficos.barras(itens, tamanho, f'Memória por serviço em {s["nome"]}', limite=8))


def _informativo(s):
    itens = [(f'Descoberto e não declarado: {d["produto"]}',
              f'Roda em <code>{_e(d["origem"])}</code> e o <code>alvos.toml</code> não o declara. Para medir, '
              f'rode <code>configurar.py descobrir --alvo {_e(s["nome"])}</code>.') for d in s["descobertos"]]
    itens += [("Não medido", f'{_e(m)}. Confira o acesso ao servidor e rode a auditoria de novo; sem a leitura, '
                             'o relatório não afirma que está tudo bem.') for m in s["nao_medido"]]
    return "".join(f'<div class="inf">{_ic("ruim", "ic inf-i")}<div><p class="inf-p">{_e(t)}</p>'
                   f'<p class="inf-f">{texto}</p></div></div>' for t, texto in itens)


def _area(s):
    meta = [("Sistema", " · ".join(x for x in (s["sistema"], s["kernel"]) if x)), ("Acesso", s["acesso"])]
    linhas = "".join(f"<dt>{r}</dt><dd>{_e(v)}</dd>" for r, v in meta if v)
    ident = "srv-" + re.sub(r"[^a-z0-9]+", "-", str(s["nome"]).lower()).strip("-")
    grupos = ""
    if s["problemas"]:
        grupos += _grupo("Problemas e o que fazer",
                         '<div class="fxs">' + "".join(cartao.cartao(a) for a in s["problemas"]) + "</div>")
    if s["servicos"]:
        grupos += _grupo("Estado dos serviços",
                         f'<div class="svcs">{"".join(_servico(sv) for sv in s["servicos"])}</div>{_memoria(s)}')
    informativo = _informativo(s)
    if informativo:
        grupos += _grupo("Informativo", f'<div class="infs">{informativo}</div>')
    return (f'<div class="srv"><header class="srv-h"><h4 id="{ident}">{_e(s["nome"])}</h4>'
            f'<dl class="srv-meta">{linhas}</dl></header>{grupos}</div>')


@bloco("servidores")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return ""
    todos = [a for s in itens for a in s["todos"]]
    if todos:
        topo = (f'<div class="sv-topo"><h4>{plural(len(todos), "problema", "problemas")} nos servidores</h4>'
                f'{cartao.indice(todos)}</div>')
    else:
        topo = '<p class="sv-topo bl-mini">Nenhum problema nos servidores.</p>'
    servicos = sum(len(s["servicos"]) for s in itens)
    resumo = f'{plural(len(itens), "servidor", "servidores")} · {plural(servicos, "serviço", "serviços")}'
    return painel("Serviços dos servidores", resumo, topo + "".join(_area(s) for s in itens), cheio=True)
```

Em `scripts/lib/blocos/__init__.py`, acrescente `"servidores"` à tupla do laço de import.

- [x] **Step 4: ligar no relatório (`scripts/build_report.py`)**

Em `_achado_bloco`, troque `<article class="bl-prob">` por
`<article class="bl-prob" id="regra-{_e(regra)}">`.

Na linha 1705:
`PAPEIS_COM_BLOCO = {"entrada", "fila", "banco", "cache", "maquina", "app", "busca"}`.

Em `_outros_papeis`, deixe os componentes de host de fora, porque eles já estão em Serviços:

```python
    outros = [c for a in alvos if a.get("tipo") != "host"
              for c in a.get("componentes") or [] if c.get("papel") not in PAPEIS_COM_BLOCO]
```

Em `_blocos_tecnicos`:

```python
    return (blocos("servidores", "maquinas", "entrada", "urls", "fila")
            + f'<div class="bl-par">{blocos("banco", "cache", "consumo", "falhas")}</div>'
            + blocos("busca") + _outros_papeis(alvos) + _fontes_das_medidas(alvos))
```

- [x] **Step 5: rodar e confirmar que passa, com os goldens e a suíte verdes**

Rode: `.venv/bin/python -m pytest tests/test_relatorio_host.py tests/test_relatorio_sem_host.py -q && .venv/bin/python -m pytest -q`
Esperado: tudo verde, menos dois testes antigos de `tests/test_build_report_insights.py`, que o plano
já prevê. Ajuste os dois assim:

1. `test_placeholder_escrito_pelo_agente_nao_injeta_secao` conta a regra no HTML, e o `id` novo soma
   uma ocorrência. Ele passa a contar fora do atributo:

```python
    html = build_report.render_html_v3(r)
    assert html.replace('id="regra-SEC_PORT_EXPOSED"', "").count("SEC_PORT_EXPOSED") == 1
```

2. `test_detalhes_seguem_a_ordem_dos_papeis_e_dizem_que_e_papel` usa `busca` como exemplo de papel
   sem bloco, e busca agora tem bloco. Troque o componente do exemplo por um papel desconhecido:

```python
    r["alvos"][0]["componentes"].append(
        {"nome": "outro", "papel": "desconhecido", "achados": [], "analise": "",
         "respostas": [{"pergunta": "x", "fonte": "promql:y", "valor": 1}]})
```

Rode de novo: `.venv/bin/python -m pytest -q`
Esperado: tudo verde.

---

### Task 12: fitness functions 2 a 4 e o orçamento do PDF

**Arquivos:**
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/orcamento_paginas.py:11-19`
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/scripts/build_report.py:2073-2083` (contagens que vão para `op.cortes`)
- Teste: `tests/test_relatorio_host.py` (testes novos no fim)
- Teste: `tests/test_limite_de_paginas.py` (teste novo no fim)

**Depende de:** Task 11.

- [x] **Step 1: escrever a fitness 2, sobre os cartões e o "O que fazer"**, no fim de `tests/test_relatorio_host.py`:

```python
import re


def test_nenhum_cartao_de_problema_sem_o_que_fazer():
    html = _html()
    cartoes = re.findall(r'<article class="fx (?:crit|warn)" id="p-[^"]+">.*?</article>', html, re.S)
    assert len(cartoes) == 4
    assert all("<b>O que fazer</b>" in c and 'href="#regra-' in c for c in cartoes)


def test_cada_achado_vira_cartao_uma_vez_so():
    ids = re.findall(r'<article class="fx (?:crit|warn)" id="(p-[^"]+)"', _html())
    assert sorted(ids) == sorted(set(ids)) and len(ids) == 4
```

- [x] **Step 2: rodar a fitness 2**

Rode: `.venv/bin/python -m pytest tests/test_relatorio_host.py -q`
Esperado: tudo verde. Os quatro cartões são `backup_atrasado` em Bancos, `servico_reiniciando` em
Serviços, `servico_declarado_ausente` em Bancos (`pg` é banco) e `disco_quase_cheio` em Máquinas.

- [x] **Step 3: pesos novos no orçamento (`scripts/lib/orcamento_paginas.py`)**

Os pesos de partida estão abaixo; a calibração vem no step 5. Em `_linhas`, some ao `return`:

```python
            + 8 * c.get("servidores", 0) + 3 * c.get("servicos_host", 0) + 6 * c.get("cartoes", 0)
            + 2 * min(c.get("colecoes", 0), 8) + 6 * c.get("bancos_host", 0))
```

Em `scripts/build_report.py`, no dicionário passado a `op.cortes`, acrescente as contagens:

```python
                       "servidores": len(dados_do_papel("servidores", alvos).get("itens") or []),
                       "servicos_host": sum(len(s["servicos"]) for s in
                                            dados_do_papel("servidores", alvos).get("itens") or []),
                       "cartoes": sum(len(s["todos"]) for s in
                                      dados_do_papel("servidores", alvos).get("itens") or []),
                       "colecoes": sum(len(i.get("colecoes") or []) for i in
                                       dados_do_papel("busca", alvos).get("itens") or []),
                       "bancos_host": sum(1 for a in alvos if a.get("tipo") == "host"
                                          for c in a.get("componentes") or [] if c.get("papel") == "banco"),
```

Para não chamar o adaptador três vezes, guarde antes numa variável:
`servidores = dados_do_papel("servidores", alvos).get("itens") or []`, e use `servidores` nas três
linhas.

- [x] **Step 4: teste de que os pesos novos contam, e os goldens continuam verdes**

No fim de `tests/test_limite_de_paginas.py`:

```python
def test_orcamento_conta_servidores_servicos_cartoes_colecoes_e_bancos_de_host():
    base = {"regras": 3, "sistemas": 5}
    for campo in ("servidores", "servicos_host", "cartoes", "colecoes", "bancos_host"):
        assert op._linhas({**base, campo: 2}, 8) > op._linhas(base, 8), campo
```

Rode: `.venv/bin/python -m pytest tests/test_limite_de_paginas.py tests/test_relatorio_sem_host.py -q`
Esperado: tudo verde. Sem host as contagens novas são zero, e o corte do cluster não muda.

- [x] **Step 5: calibrar os pesos contra um PDF real**

```bash
cd ~/.claude/skills/sw-infra-audit && D=$(mktemp -d) && .venv/bin/python - "$D" <<'EOF'
import sys
sys.path[:0] = ["scripts", "."]
import build_report as br
from lib import orcamento_paginas as op
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_host import relatorio_com_hosts
capturado = {}
original = op.cortes
def cortes(c):                       # guarda as contagens que o render calculou
    capturado.update(c)
    return original(c)
op.cortes = cortes
for nome, r in (("docker", relatorio_docker()), ("docker+hosts", relatorio_com_hosts(relatorio_docker()))):
    capturado.clear()
    pdf = br.build(r, f"{sys.argv[1]}/{nome}", formato="html+pdf")["pdf"]
    print(nome, pdf, "estimativa:", round(op._linhas(capturado, 40) / op.LINHAS_POR_PAGINA, 1))
EOF
for f in "$D"/*/*.pdf; do echo "$f"; pdfinfo "$f" | grep Pages; done
```

Compare, para cada relatório, as páginas medidas com a estimativa impressa. Na revisão do plano,
com o layout completo, deu 7 páginas sem host e 17 com os dois hosts. Se a diferença passar de 1 página, ajuste os pesos de
`servidores`, `servicos_host` e `cartoes` em `_linhas`. Repita até ficar dentro de 1 página.
Registre os pesos finais e as páginas medidas em "Ajustes durante a execução" deste plano.

- [x] **Step 6: fitness 4, os dois hosts somam no máximo 12 páginas e nenhuma fica quase vazia**

O dono decidiu manter o layout completo, sem corte novo para host [usuário, 2026-11-14]. A fitness
garante duas coisas: o custo dos hosts tem teto, e a paginação não deixa folha quase vazia, que é o
defeito que a revisão achou. No fim de `tests/test_limite_de_paginas.py`:

```python
@chromium
def test_dois_hosts_somam_no_maximo_doze_paginas_e_nenhuma_fica_quase_vazia(tmp_path):
    from tests.fixtures.relatorio_host import relatorio_com_hosts
    from tests.test_ajustes_da_rodada_real import _preenchimento
    (tmp_path / "sem").mkdir()
    (tmp_path / "com").mkdir()
    sem = br.build(relatorio_grande(), str(tmp_path / "sem"), formato="html+pdf")["pdf"]
    com = br.build(relatorio_com_hosts(relatorio_grande()), str(tmp_path / "com"), formato="html+pdf")["pdf"]
    assert paginas(com) - paginas(sem) <= 12
    assert min(_preenchimento(com)[:-1]) >= 0.15, [round(p, 2) for p in _preenchimento(com)]
```

Rode: `.venv/bin/python -m pytest tests/test_limite_de_paginas.py -q`
Esperado: verde. Na revisão, com o `:has(...)` do step 6 da task 10, deu 21 páginas sem host e 33
com host (+12). Se alguma página do meio ficar abaixo de 15%, corrija a quebra no CSS de impressão
(por exemplo, `break-before:avoid` no primeiro `.grp` de um servidor). Não mude o teste.

- [x] **Step 7: suíte inteira**

Rode: `.venv/bin/python -m pytest -q`
Esperado: tudo verde, com uns 2300 testes.

---

### Task 13: conferência visual, versão e changelog

**Arquivos:**
- Alterar: `plugins/sw-infra-audit/skills/sw-infra-audit/SKILL.md` (a frase sobre o relatório de host)
- Alterar: `/var/www/ai-marketplace/CHANGELOG.md` (entrada da v0.22.0)

**Depende de:** Task 12.

- [x] **Step 1: gerar o HTML de conferência e olhar no claro, no escuro e no celular**

```bash
cd ~/.claude/skills/sw-infra-audit && D="${TMPDIR:-/tmp}/relatorio-c" && mkdir -p "$D" && .venv/bin/python - "$D" <<'EOF'
import sys
sys.path[:0] = ["scripts", "."]
import build_report as br
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_host import relatorio_com_hosts
print(br.build(relatorio_com_hosts(relatorio_docker()), sys.argv[1], formato="html+pdf"))
EOF
```

Abra o HTML com o Playwright em 1280px e em 390px, no claro e no escuro (`emulate_media` com
`colorScheme: "dark"`), e abra também o PDF. Confira contra `referencias/mockup-aprovado.png`:

- [x] o índice aparece no topo e cada link leva ao cartão;
- [x] os três grupos aparecem com rótulo, separados;
- [x] o medidor do backup fica vermelho, com a etiqueta;
- [x] as barras estão ordenadas;
- [x] nenhum texto sai da página a 390px;
- [x] no escuro, as barras e o texto ficam legíveis;
- [x] no PDF, nenhum cartão é cortado ao meio.

Corrija no CSS o que estiver fora. Os goldens não olham o `<style>`, então não quebram com isso.

- [x] **Step 2: frase do relatório no `SKILL.md`**

Em `SKILL.md`, onde a skill descreve o que o relatório traz, acrescente:
"Servidores host ganham o bloco **Serviços dos servidores**, com índice de problemas e uma área por
servidor (problemas e o que fazer, estado dos serviços, informativo). Bancos mostram conexões contra o
limite, tamanho por banco, lentas, binlog e idade do backup. Busca mostra as coleções do Qdrant. Cada
problema exibido traz o primeiro passo de como resolver."

- [x] **Step 3: sincronizar com o repositório, com bump minor**

Rode: `cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit BUMP=minor`
Esperado: a versão vai de 0.21.0 para 0.22.0, e `marketplace.json` e o `README.md` são atualizados
pelo próprio sync.

- [x] **Step 4: entrada no `CHANGELOG.md`**, no topo de `## [Não publicado]` › `### Adicionado`:

```markdown
- `sw-infra-audit` (v0.22.0): **relatório com servidores host e dados por produto.** Bloco novo
  "Serviços dos servidores", com índice de problemas no topo e uma área por servidor (problemas e o que
  fazer, estado dos serviços com reinícios e memória, informativo com descobertos e não medidos). Bancos
  do cluster e do host no mesmo formato, com medidor de conexões contra o limite, tamanho por banco,
  lentas, binlog e idade do backup; bloco novo "Busca" com as coleções do Qdrant. Máquinas ganham carga,
  boot e medidores com marca em 90%. Todo cartão de problema traz "O que fazer" com o primeiro passo da
  remediação. Gráficos em SVG inline, legíveis no claro, no escuro e no PDF. Regra nova
  `servico_reiniciando` (5 reinícios ou mais). A capa e a nota passam a contar os serviços do host.
```

- [x] **Step 5: gate de segurança no que vai para o git**

```bash
cd /var/www/ai-marketplace && git add -N . && make check; git diff --name-only | xargs grep -nE "/(home|Users)/" ; [ -f .scan-denylist ] && grep -rniFf .scan-denylist plugins/sw-infra-audit docs/specs/2026-11-14-relatorio-mostrando-servidores-host-e-dados-por-produto
```

Esperado: `make check` sem achados, e os dois grep sem saída. A fixture usa só nomes fictícios
(`banco-01`, `cache-02`, `loja`).

---

## Ajustes durante a execução

- **2026-11-14** — juiz final e code review de contexto vazio. Os 10 pontos foram corrigidos, a pedido do dono:
  1. o aceite com `--componente`, sem `--objeto`, calava todos os serviços parados do host. `servicos_host.aceitos` passa a ler `objeto or componente`;
  2. cluster com Qdrant ou Elasticsearch ganhava um bloco Busca vazio. `busca` saiu de `PAPEIS_COM_BLOCO`, o `_busca` lê só alvo host, e o cluster volta a "Outros sistemas";
  3. host que respondeu só com a máquina saía "Sem dado" na Saúde. O "Sem dado" fica só para o host sem fatos;
  4. índice dos dossiês e stage do `plan.md`;
  5. caminho do `/tmp` com id de sessão no plano, trocado por `$TMPDIR`;
  6. `_a_cobrar` passa a usar `cartao.cobrados`;
  7. regra `.mt-st` no CSS, e a trava de classe órfã agora varre `graficos.py` e `cartao.py`;
  8. em Máquinas, a barra usa o acento abaixo de 90% e, acima, a cor de status com a etiqueta "acima do limite";
  9. a fitness 2 confere que cada link do índice leva a um cartão;
  10. o espaço entre servidores passou a `--s4` de borda mais `--s5` de padding (56px, o `--s7` do spec).

  Foram 5 testes novos, e a suíte está em 2316.
- **2026-11-14** — task 13: a conferência visual foi feita com screenshots do Chrome headless, nos temas claro e escuro, a 1280px e a 390px. O servidor HTTP local não funcionou neste ambiente. A conferência levou a três ajustes:
  - com dado de host, Bancos vai à largura toda (`_banco_de_host` em `build_report.py`, `.bl-dbs` no CSS); antes ficava espremido ao lado de um Cache vazio;
  - o "onde" do cartão não repete o nome da máquina (`banco-01 · banco-01`);
  - "Memória por serviço" ganhou espaço acima.

  O sync fez o bump para 0.22.0, e o `make check` ficou limpo. A suíte está em 2311.
- **2026-11-14** — task 12 concluída; suíte em 2311, com os testes Chromium rodando de verdade. Pesos finais: `40*servidores + 10*servicos_host + 13*cartoes`; `colecoes` (2, limitado a 8) e `bancos_host` (6) ficaram como no plano. Páginas medidas e estimadas: docker 7 (5,0), docker+hosts 17 (17,0), grande 21 (22,1), grande+hosts 33 (34,1). A primeira tentativa de pesos (64/14/22) estourou o orçamento, ligou o corte e derrubou o PDF para 16 páginas. O menor preenchimento das páginas do meio ficou em 0,27; o CSS não mudou. O +12 da fitness 4 está no limite exato.
- **2026-11-14** — task 11 concluída; suíte em 2307, com os dois testes antigos previstos ajustados.
- **2026-11-14** — task 10 concluída; suíte em 2301, sem teste antigo ajustado.
- **2026-11-14** — task 9 concluída; suíte em 2296, sem teste antigo ajustado.
- **2026-11-14** — lote 5, 7 e 8 concluído; suíte em 2287. `_replicas` não precisou de ajuste.
- **2026-11-14** — lote 2, 3, 4 e 6 concluído; suíte em 2272. Task 6: a frase "Ausência só vira achado se a fonte de origem respondeu" voltou à docstring de `_comparar`. Task 4: o CSS dos gráficos ficou acima do comentário da capa, que descreve o `@media print` seguinte.
- **2026-11-14** — task 1 concluída: goldens com 54465 (grande) e 13767 (docker) caracteres; suíte em 2252.
- **2026-11-14** — Base da revisão final: bcbda06adf81199e20028d3c33580bfddd80b9ca (repo; a fonte em `~/.claude/skills/sw-infra-audit` não é git, o diff aparece depois do `make sync`).
- **2026-11-14** — planejamento: `report_sample.json` é schema 1 e o build v3 o recusa. O golden
  "inteiro" da restrição 3 passa para `relatorio_grande()`, e os dois goldens tiram os painéis
  Máquinas e Bancos.
- **2026-11-14** — planejamento: no cluster, Bancos e Máquinas não ganham cartão. Só alvo `host` tem
  cartão nos blocos, porque o achado de cluster continua só na seção Problemas. A restrição 2 é
  checada num relatório com host.
- **2026-11-14** — revisão do plano (aplicado numa cópia; 2303 passando e 7 falhando antes destes
  ajustes):
  - `nan-ok` em `graficos._limitar`;
  - a marca do medidor sem `translate(-1 0)`;
  - a asserção da task 6 com `redis` e `qdrant`;
  - o CSS de cartões e busca passou para a task 10;
  - os dois testes antigos da task 11 estão previstos;
  - a calibração captura as contagens com monkeypatch em `op.cortes`;
  - host sem VPN aparece na Saúde como "Sem dado".
- **2026-11-14** — fitness 4 revista com o dono: o layout completo fica, sem corte novo para host.
  Medido na cópia: 7 → 17 páginas (cluster pequeno com os 2 hosts) e 21 → 33 (rodada grande). A
  causa das folhas quase vazias é o `.bl-pn{break-inside:avoid}` do print; os painéis novos ganham
  `break-inside:auto` via `:has(...)`. A fitness passou a ser "+12 páginas no máximo e nenhuma página
  do meio abaixo de 15%".
- **2026-11-14** — sem correção, só registro: com o corte de baixa gravidade ligado, um achado `low`
  de host perderia o `<article id="regra-…">` e o link do cartão. As regras de host são todas
  `medium` ou `high` hoje; regra `low` de host nova precisa tratar isso.
- **2026-11-14** — planejamento: os ícones reusam o sprite que já existe (`ic-achado`, `ic-corrigir`,
  `ic-bom`, `ic-ruim`). Um símbolo novo mudaria o `<body>` e quebraria o golden. As classes dos
  gráficos levam o prefixo `gf`, porque `.g` já existe no template.
