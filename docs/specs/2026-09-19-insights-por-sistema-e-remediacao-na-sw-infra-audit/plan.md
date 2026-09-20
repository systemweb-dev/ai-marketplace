# Plano 1 — o eixo: papel, perguntas, schema v3, `promql` e remediação

> **Execução:** implementar task-by-task. Steps usam checkbox (`- [ ]`) para tracking.
> Ver "Execution Handoff" da skill `sw-plan` para os dois modos de execução.

Origem: [spec.md](spec.md) · seção "Ordem de execução: quatro planos", plano **1**.

**Goal:** dar à `sw-infra-audit` o esqueleto para interrogar componentes por papel — com um
adaptador real (`promql`), schema v3, orçamento que funciona, e **remediação em todo achado**.

**Architecture:** um componente ganha um **papel** derivado do `kind` que já existe; o papel
define as **perguntas canônicas**; um **adaptador** responde o que souber e carimba a **fonte**;
o que não tem resposta vira `sem_dados` com motivo. O conhecimento de cada família de exporter
vive em arquivo de dados, não em código.

**Tech Stack:** Python 3 (stdlib apenas), `tomllib`, pytest (venv em
`~/.claude/skills/sw-infra-audit/.venv`). Sem dependência nova.

**Testes deste plano:** **unit** + **integração com servidor HTTP local** (o padrão que
`tests/test_coletor_http.py` já usa). Sem rede, sem infraestrutura real, sem E2E de navegador.

**Branch:** `master` (decisão do dono).

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `scripts/lib/regras.py` | **novo** · registro explícito `REGRAS = {id: {...}}`; única fonte enumerável de regras |
| `scripts/lib/papel.py` | **novo** · `papel_de(kind, declarado)`; tabela `kind → papel` |
| `scripts/lib/perguntas.py` | **novo** · registro de perguntas canônicas por papel |
| `scripts/lib/catalogo.py` | **novo** · carrega e valida os `.toml` de `references/metricas/` |
| `scripts/lib/adaptadores/__init__.py` | **novo** · registro de adaptadores e escolha por prioridade |
| `scripts/lib/adaptadores/promql.py` | **novo** · o primeiro adaptador |
| `scripts/lib/remediacao.py` | **novo** · lê `references/remediacao/<regra>.md` e anexa ao achado |
| `scripts/lib/orcamento.py` | **novo** · prazo por alvo (relógio monotônico) |
| `references/metricas/*.toml` | **novo** · famílias de exporter |
| `references/remediacao/*.md` | **novo** · catálogo de remediação |
| `scripts/lib/http_get.py` | egress passa a exigir host **e** porta |
| `scripts/lib/runner.py` | `ambiente()` vira base positiva |
| `scripts/lib/config.py` | `insights` e `relatorio.ip_completo` |
| `scripts/lib/alvos.py` | bloco `[[alvo.componente]]` |
| `scripts/lib/report.py` | schema v3: `componentes[]`, ordenação determinística |
| `scripts/lib/aceites.py` | aceite conhece componente |
| `scripts/lib/historico.py` | aceita v2 e v3, avisando |
| `scripts/collect.py` | orquestra perguntas; promove achado; orçamento |
| `scripts/build_report.py` | sumário, insights por sistema, impacto de volta, "como resolver" |
| `assets/report-template/template_v3.html` | a direção visual aprovada |

---

## Task 1: egress exige host E porta

**Files:**
- Modify: `scripts/lib/http_get.py`
- Modify: `scripts/lib/coletores/http.py`
- Modify: `scripts/lib/coletores/docker.py`
- Test: `tests/test_egress.py`

- [x] **Step 1: escrever o teste que falha**

```python
def test_porta_nao_declarada_e_recusada():
    """Confirmar um host não pode autorizar todas as portas dele: os adaptadores tentam
    portas de administração, e isso viraria varredura no host declarado."""
    from lib.http_get import check_allowed, NotConfirmed
    import pytest

    permitido = [("metricas.interno", 9090)]

    assert check_allowed("http://metricas.interno:9090/api/v1/query?query=up", permitido) is True
    with pytest.raises(NotConfirmed):
        check_allowed("http://metricas.interno:15672/api/overview", permitido)


def test_porta_implicita_do_esquema_conta():
    from lib.http_get import check_allowed
    assert check_allowed("https://painel.interno/metrics", [("painel.interno", 443)]) is True
    assert check_allowed("http://painel.interno/metrics", [("painel.interno", 80)]) is True
```

- [x] **Step 2: rodar e ver falhar**

Run: `cd ~/.claude/skills/sw-infra-audit && .venv/bin/python -m pytest tests/test_egress.py -q`
Expected: FAIL — `check_allowed` hoje compara só `p.hostname` e aceita a porta 15672.

- [x] **Step 3: implementar**

```python
PORTA_PADRAO = {"http": 80, "https": 443}


def destino(url):
    """(host, porta) de uma URL, com a porta implícita do esquema resolvida."""
    p = urlparse(url or "")
    return p.hostname, (p.port or PORTA_PADRAO.get(p.scheme))


def check_allowed(url, permitidos):
    """`permitidos` é uma lista de (host, porta). Host declarado não autoriza porta não
    declarada: os adaptadores tentam portas de administração, e liberar todas seria varredura."""
    p = urlparse(url or "")
    if p.scheme not in ("http", "https"):
        raise NotConfirmed(f"esquema não permitido: {p.scheme!r}")
    host, porta = destino(url)
    if not host or (host, porta) not in {(h, int(n)) for h, n in (permitidos or [])}:
        raise NotConfirmed(f"destino não confirmado: {host!r}:{porta}")
    return True
```

- [x] **Step 4: atualizar os chamadores**

Em `scripts/lib/coletores/http.py`, onde hoje passa `[partes.hostname]`:

```python
permitido = [http_get.destino(url)]
codigo, _ = http_get.get_com_status(url, permitido, timeout=timeout)
...
certificado = http_get.validade_do_certificado(url, permitido, timeout)
```

Em `scripts/lib/coletores/docker.py`, onde hoje passa `[host_of(url)]`:

```python
permitido = [http_get.destino(url)]
```

- [x] **Step 5: rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — inclusive `tests/test_coletor_http.py` e `tests/test_metrics.py`.

- [x] **Step 6: prova por mutação**

Troque a comparação por `host in {h for h, _ in permitidos}` (ignorando a porta) e rode a suíte:
`test_porta_nao_declarada_e_recusada` **tem** que falhar. Reverta em seguida.

---

## Task 2: `runner.ambiente()` vira base positiva

**Files:**
- Modify: `scripts/lib/runner.py`
- Test: `tests/test_runner.py`, `tests/test_restricoes.py`

- [x] **Step 1: escrever o teste que falha**

```python
def test_ambiente_do_filho_e_base_positiva(monkeypatch):
    """A credencial de banco chega pelo ambiente (senha_env). Copiar o ambiente inteiro
    menos quatro variáveis deixaria PGPASSWORD alcançar todo comando docker."""
    from lib.runner import ambiente
    monkeypatch.setenv("PGPASSWORD", "segredo-do-banco")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "outro-segredo")
    monkeypatch.setenv("PATH", "/usr/bin")

    env = ambiente("prod")

    assert env["DOCKER_CONTEXT"] == "prod"
    assert env["PATH"] == "/usr/bin"
    assert "PGPASSWORD" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
```

- [x] **Step 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_runner.py -q`
Expected: FAIL — `PGPASSWORD` está no env, porque hoje a função copia tudo menos quatro nomes.

- [x] **Step 3: implementar**

```python
# o que o processo filho precisa para existir — e nada além disso. Lista negativa não serve:
# basta uma credencial nova no ambiente para ela vazar sem ninguém perceber.
BASE = ("PATH", "HOME", "LANG", "LC_ALL", "TZ")


def ambiente(context, extras=()):
    """Ambiente do processo filho: base mínima + o context do alvo + o que o chamador pedir.

    `extras` é uma tupla de NOMES de variáveis (o perfil de cada binário declara os seus —
    ver plano 3). Sem extras, nenhuma credencial do seu shell alcança o filho.
    """
    env = {nome: os.environ[nome] for nome in BASE + tuple(extras) if nome in os.environ}
    if context:
        env["DOCKER_CONTEXT"] = context
    return env
```

- [x] **Step 4: o teste de segredo passa a ver o `env` de verdade**

Em `tests/test_restricoes.py`, `test_nenhum_segredo_chega_ao_relatorio` substitui `runner.run`
e nunca enxerga o ambiente. Acrescente um teste irmão que captura o `subprocess.run` real:

```python
def test_segredo_nao_chega_ao_processo_filho(monkeypatch):
    """Restrição 2, a parte que faltava: nem argv, nem ambiente."""
    from unittest import mock
    from lib import runner
    monkeypatch.setenv("SENHA_DO_ALVO", "trocadilho-secreto")

    with mock.patch("lib.runner.subprocess.run") as m:
        m.return_value = mock.Mock(stdout="{}", returncode=0)
        runner.run(["docker", "info"], timeout=5, context="prod")
        env = m.call_args.kwargs["env"]
        argv = m.call_args[0][0]

    assert "trocadilho-secreto" not in " ".join(argv)
    assert not any("trocadilho-secreto" == v for v in env.values())
```

- [x] **Step 5: rodar a suíte**

Run: `.venv/bin/python -m pytest -q` — Expected: PASS.

- [x] **Step 6: commit**

```bash
git add scripts/lib/http_get.py scripts/lib/runner.py scripts/lib/coletores/ tests/
git commit -m "fix(sw-infra-audit): egress exige porta e ambiente do filho vira base positiva"
```

---

## Task 3: `lib/regras.py` — registro explícito de regras

**Files:**
- Create: `scripts/lib/regras.py`
- Modify: `scripts/lib/rules.py`, `scripts/lib/coletores/http.py`
- Test: `tests/test_regras.py`

Hoje os `rule_id` são literais dentro das funções de `rules.py`, e o coletor http cria as suas
por fora. Sem um registro, "toda regra tem remediação" não é verificável sem AST.

- [x] **Step 1: escrever o teste que falha**

```python
def test_todo_produtor_declara_suas_regras_no_registro():
    """O registro é a fonte enumerável. Regra que nasce fora dele não ganha remediação —
    e é assim que um achado chega ao relatório sem dizer o que fazer."""
    from lib import rules
    from lib.coletores import http as coletor_http
    from lib.regras import REGRAS

    assert rules.REGRAS_PRODUZIDAS <= set(REGRAS), sorted(rules.REGRAS_PRODUZIDAS - set(REGRAS))
    assert coletor_http.REGRAS_PRODUZIDAS <= set(REGRAS), \
        sorted(coletor_http.REGRAS_PRODUZIDAS - set(REGRAS))


def test_o_relatorio_nunca_traz_regra_fora_do_registro(tmp_path):
    """Prova pelo comportamento: roda a coleta com o coletor http real (endpoint morto,
    achados reais) e confere que todo `regra` do report.json está registrado."""
    import json
    import collect
    from lib.coletores import http as coletor_http
    from lib.regras import REGRAS

    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / "config.toml").write_text('alvos = ["site"]\n', encoding="utf-8")

    collect.main(["--padrao", str(tmp_path / "default.toml"),
                  "--infra", str(tmp_path / "alvos.toml"),
                  "--projeto", str(tmp_path / "config.toml"),
                  "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z",
                  "--confirmar", "site"], coletores={"http": coletor_http.coletar})
    relatorio = json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))

    regras = {a.get("regra") for alvo in relatorio["alvos"] for a in alvo["achados"]}
    assert regras <= set(REGRAS), sorted(regras - set(REGRAS))


def test_registro_descreve_severidade_e_origem():
    from lib.regras import REGRAS
    assert REGRAS["SEC_PORT_EXPOSED"]["severidade_padrao"] == "medium"
    assert REGRAS["certificado_vencendo"]["origem"] == "coletor_http"
    assert REGRAS["SEC_DOCKER_SOCK_EXPECTED"]["esperada"] is True
```

- [x] **Step 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_regras.py -q`
Expected: FAIL — `ModuleNotFoundError: lib.regras`.

- [x] **Step 3: implementar o registro**

```python
"""Registro explícito de regras — a única lista enumerável de tudo que vira achado.

Antes, os identificadores eram literais espalhados pelo corpo das funções de `rules.py` e do
coletor http. Enumerar isso exigia ler AST; e o que não se enumera não se cobra — por isso
existia achado sem remediação e `RULE_META` com entrada morta.

`esperada = True` marca a regra que descreve um comportamento normal (o proxy monta o
docker.sock porque é assim que ele funciona): ela não pesa na nota e não exige remediação.
"""

REGRAS = {
    # --- segurança (produzidas por lib/rules.py)
    "SEC_PRIVILEGED":        {"severidade_padrao": "high",   "origem": "rules", "esperada": False},
    "SEC_DOCKER_SOCK":       {"severidade_padrao": "high",   "origem": "rules", "esperada": False},
    "SEC_DOCKER_SOCK_EXPECTED": {"severidade_padrao": "info", "origem": "rules", "esperada": True},
    "SEC_PORT_EXPOSED":      {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    "SEC_IMAGE_UNPINNED":    {"severidade_padrao": "low",    "origem": "rules", "esperada": False},
    "SEC_USER_ROOT":         {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    # --- operação
    "OPS_NODE_DOWN":         {"severidade_padrao": "critical", "origem": "rules", "esperada": False},
    "OPS_SERVICE_DEGRADED":  {"severidade_padrao": "high",   "origem": "rules", "esperada": False},
    # --- coletor http
    "certificado_vencendo":   {"severidade_padrao": "high",   "origem": "coletor_http", "esperada": False},
    "sem_tls":                {"severidade_padrao": "medium", "origem": "coletor_http", "esperada": False},
    "http_fora_do_ar":        {"severidade_padrao": "critical","origem": "coletor_http", "esperada": False},
    "http_resposta_de_erro":  {"severidade_padrao": "medium", "origem": "coletor_http", "esperada": False},
}


def severidade(regra, padrao="info"):
    return REGRAS.get(regra, {}).get("severidade_padrao", padrao)


def esperada(regra):
    return REGRAS.get(regra, {}).get("esperada", False)


def exigem_remediacao():
    """As regras que precisam de arquivo em references/remediacao/."""
    return {id_ for id_, meta in REGRAS.items() if not meta["esperada"]}
```

> **Atenção ao executar:** a lista acima cobre as regras que existem HOJE. Antes de fechar a
> task, rode `grep -rn 'rule_id' scripts/lib/rules.py` e confira uma a uma — se aparecer regra
> que não está no dicionário, acrescente (e escreva a remediação dela na Task 16).

- [x] **Step 4: cada produtor declara o que produz**

No topo de `scripts/lib/rules.py`:

```python
from lib.regras import REGRAS

REGRAS_PRODUZIDAS = {
    "SEC_PRIVILEGED", "SEC_DOCKER_SOCK", "SEC_DOCKER_SOCK_EXPECTED", "SEC_PORT_EXPOSED",
    "SEC_IMAGE_UNPINNED", "SEC_USER_ROOT", "OPS_NODE_DOWN", "OPS_SERVICE_DEGRADED",
}
```

No topo de `scripts/lib/coletores/http.py`:

```python
from lib.regras import REGRAS

REGRAS_PRODUZIDAS = {"certificado_vencendo", "sem_tls", "http_fora_do_ar", "http_resposta_de_erro"}
```

- [x] **Step 5: rodar**

Run: `.venv/bin/python -m pytest tests/test_regras.py -q` — Expected: PASS.

- [x] **Step 6: commit**

```bash
git add scripts/lib/regras.py scripts/lib/rules.py scripts/lib/coletores/http.py tests/test_regras.py
git commit -m "feat(sw-infra-audit): registro explicito de regras"
```

---

## Task 4: `lib/papel.py` — papel derivado de `kind`

**Files:**
- Create: `scripts/lib/papel.py`
- Test: `tests/test_papel.py`

`detect_kind` devolve strings que `lib/metrics.py` (`STATEFUL`) e `lib/impact.py`
(`CRITICAL_PATH`) comparam literalmente. **Não as renomeie** — traduza.

- [x] **Step 1: escrever o teste que falha**

```python
def test_papel_traduz_o_kind_existente():
    from lib.papel import papel_de
    assert papel_de("ingress/proxy") == "entrada"
    assert papel_de("api-gateway") == "entrada"
    assert papel_de("fila/broker") == "fila"
    assert papel_de("banco") == "banco"


def test_cache_fila_resolve_para_cache_e_o_alvo_pode_corrigir():
    """Redis é cache na maioria das instalações — mas quando ele é o broker do Celery,
    quem sabe disso é o dono, não a imagem."""
    from lib.papel import papel_de
    assert papel_de("cache/fila") == "cache"
    assert papel_de("cache/fila", declarado="fila") == "fila"


def test_todo_kind_conhecido_tem_papel():
    """Um kind novo em _KINDS sem papel viraria `app` calado, e o componente perderia todas
    as perguntas do papel certo sem ninguém notar."""
    from lib.coletores.docker import _KINDS
    from lib.papel import POR_KIND
    faltando = sorted({kind for _, kind in _KINDS} - set(POR_KIND))
    assert faltando == [], f"kind sem papel: {faltando}"


def test_papel_declarado_invalido_e_recusado():
    import pytest
    from lib.papel import papel_de, PapelInvalido
    with pytest.raises(PapelInvalido):
        papel_de("banco", declarado="bananco")
```

- [x] **Step 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_papel.py -q` — Expected: FAIL (`lib.papel` não existe).

- [x] **Step 3: implementar**

```python
"""Papel do componente — derivado do `kind`, nunca em lugar dele.

`detect_kind` já classifica por imagem, e `metrics.py`/`impact.py` comparam aquelas strings
LITERALMENTE. Renomeá-las quebraria saúde e impacto em silêncio; por isso aqui só se traduz.
"""

PAPEIS = ("entrada", "fila", "banco", "cache", "busca", "storage", "observabilidade", "app")

POR_KIND = {
    "ingress/proxy": "entrada", "proxy": "entrada", "api-gateway": "entrada",
    "fila": "fila", "fila/broker": "fila",
    "banco": "banco",
    "cache": "cache", "cache/fila": "cache",
    "busca": "busca",
    "observabilidade": "observabilidade",
    "object-storage": "storage",
    "app": "app",
}


class PapelInvalido(Exception):
    """Papel declarado que não existe."""


def papel_de(kind, declarado=None):
    """O papel do componente. `declarado` vem do alvos.toml e vence a imagem — quando a
    imagem mente (um `worker` que é broker), quem sabe é o dono."""
    if declarado is not None:
        if declarado not in PAPEIS:
            raise PapelInvalido(
                f"papel {declarado!r} não existe; os papéis são {', '.join(PAPEIS)}")
        return declarado
    return POR_KIND.get(kind, "app")
```

- [x] **Step 4: rodar** — `.venv/bin/python -m pytest tests/test_papel.py -q` → PASS.

- [x] **Step 5: commit**

```bash
git add scripts/lib/papel.py tests/test_papel.py
git commit -m "feat(sw-infra-audit): papel do componente derivado do kind"
```

---

## Task 5: `lib/perguntas.py` — registro de perguntas canônicas

**Files:**
- Create: `scripts/lib/perguntas.py`
- Test: `tests/test_perguntas.py`

Só as perguntas do plano 1 (papel `entrada`, o que qualquer família responde). As de rota
entram no plano 4; fila/banco/cache nos planos 2 e 3.

- [x] **Step 1: escrever o teste que falha**

```python
def test_perguntas_do_papel_vem_na_ordem_declarada():
    """A ordem é contrato: o orçamento corta da última para a primeira, então ela vai da
    pergunta mais barata para a mais cara."""
    from lib.perguntas import do_papel
    ids = [p["id"] for p in do_papel("entrada")]
    assert ids == ["entrada.volume_na_janela", "entrada.distribuicao_de_status",
                   "entrada.latencia"]


def test_pergunta_de_lista_exige_desempate():
    """Empate de valor no top N herdaria a ordem da API e mudaria o relatório entre rodadas."""
    from lib.perguntas import PERGUNTAS
    for pergunta in PERGUNTAS.values():
        if pergunta["forma"] == "lista":
            assert pergunta.get("desempate"), f"{pergunta['id']} é lista e não declara desempate"


def test_papel_sem_pergunta_devolve_lista_vazia():
    from lib.perguntas import do_papel
    assert do_papel("storage") == []
```

- [x] **Step 2: rodar e ver falhar** — `ModuleNotFoundError: lib.perguntas`.

- [x] **Step 3: implementar**

```python
"""As perguntas canônicas — o que se quer saber, independente de quem responde.

`forma` diz o formato do valor (escalar, lista, serie) e o relatório desenha de acordo.
`limiar` é o que transforma informação em achado; sem limiar, a resposta é só informação.
"""

PERGUNTAS = {}


def _p(id, papel, titulo, forma, unidade=None, limiar=None, desempate=None):
    PERGUNTAS[id] = {"id": id, "papel": papel, "titulo": titulo, "forma": forma,
                     "unidade": unidade, "limiar": limiar, "desempate": desempate}
    return id


# --- papel `entrada`: só o que QUALQUER família de exporter responde (o resto, plano 4)
_p("entrada.volume_na_janela", "entrada", "Requisições na janela", "escalar", "requisicoes")
_p("entrada.distribuicao_de_status", "entrada", "Distribuição de status", "lista",
   unidade="requisicoes", desempate="chave")
_p("entrada.latencia", "entrada", "Latência (p50 e p95)", "escalar", "ms")

ORDEM = {"entrada": ["entrada.volume_na_janela", "entrada.distribuicao_de_status",
                     "entrada.latencia"]}


def do_papel(papel):
    """As perguntas daquele papel, na ordem declarada (barata → cara)."""
    return [PERGUNTAS[id] for id in ORDEM.get(papel, [])]
```

- [x] **Step 4: rodar** → PASS. **Step 5: commit**

```bash
git add scripts/lib/perguntas.py tests/test_perguntas.py
git commit -m "feat(sw-infra-audit): registro de perguntas canonicas"
```

---

## Task 6: configuração — `insights` e o bloco de componente

**Files:**
- Modify: `scripts/lib/config.py`, `scripts/lib/alvos.py`
- Test: `tests/test_config.py`, `tests/test_alvos.py`

As duas validações recusam chave desconhecida **de propósito** — é a trava que impede o arquivo
versionado de declarar conexão. Aqui a lista de conhecidos cresce; a trava continua.

- [x] **Step 1: escrever os testes que falham**

```python
def test_projeto_pode_ajustar_a_janela_dos_insights(tmp_path):
    from lib.config import carregar
    (tmp_path / "config.toml").write_text(
        'alvos = ["cluster"]\n\n[insights]\njanela = "7d"\n', encoding="utf-8")
    cfg = carregar(padrao=None, infra=None, projeto=tmp_path / "config.toml")
    assert cfg.valor("insights.janela") == "7d"


def test_projeto_pode_liberar_o_ip_completo(tmp_path):
    from lib.config import carregar
    (tmp_path / "config.toml").write_text(
        '[relatorio]\nip_completo = true\n', encoding="utf-8")
    cfg = carregar(padrao=None, infra=None, projeto=tmp_path / "config.toml")
    assert cfg.valor("relatorio.ip_completo") is True


def test_componente_do_alvo_aceita_papel_e_metricas(tmp_path):
    from lib.alvos import ler
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "cluster"\ntipo = "docker"\ncontext = "prod"\n\n'
        '[[alvo.componente]]\nnome = "proxy"\npapel = "entrada"\n'
        'metricas_url = "http://127.0.0.1:9090"\n', encoding="utf-8")
    alvos, _ = ler(tmp_path / "alvos.toml")
    assert alvos[0]["componente"][0] == {"nome": "proxy", "papel": "entrada",
                                         "metricas_url": "http://127.0.0.1:9090"}


def test_componente_com_campo_inexistente_e_recusado(tmp_path):
    import pytest
    from lib.alvos import ler, AlvoInvalido
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "p"\n\n'
        '[[alvo.componente]]\nnome = "x"\nmetrica_url = "http://127.0.0.1:9090"\n',
        encoding="utf-8")
    with pytest.raises(AlvoInvalido) as erro:
        ler(tmp_path / "alvos.toml")
    assert "metrica_url" in str(erro.value)


def test_componente_com_papel_invalido_e_recusado(tmp_path):
    import pytest
    from lib.alvos import ler, AlvoInvalido
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "p"\n\n'
        '[[alvo.componente]]\nnome = "x"\npapel = "bananco"\n', encoding="utf-8")
    with pytest.raises(AlvoInvalido):
        ler(tmp_path / "alvos.toml")
```

- [x] **Step 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_config.py tests/test_alvos.py -q`
Expected: FAIL — `config.py` recusa `insights`; `alvos.py` recusa `componente`.

- [x] **Step 3: implementar em `config.py`**

```python
PROJETO_PERMITE = ("alvos", "aceite", "relatorio", "severidade", "insights")
RELATORIO_PERMITE = ("pasta", "formato", "ignorar_em", "ip_completo")
```

> `insights` NÃO entra em `CHAVES_DE_CONEXAO` — `janela` e limites de lista não descrevem
> conexão. A trava contra conexão no arquivo versionado continua exatamente como está.

- [x] **Step 4: implementar em `alvos.py`**

```python
COMPONENTE_PERMITE = ("nome", "papel", "admin_url", "metricas_url", "senha_env")


def _checar_componentes(caminho, nome_do_alvo, brutos):
    """Valida `[[alvo.componente]]`. O papel declarado vence a imagem; campo desconhecido
    é erro, como em todo o resto deste arquivo — erro de digitação que passa mudo vira
    'a skill não coletou e não disse por quê'."""
    from lib.papel import PAPEIS
    saida = []
    for bruto in brutos:
        if not isinstance(bruto, dict):
            raise AlvoInvalido(f"{caminho.name}: componente de {nome_do_alvo!r} precisa ser "
                               f"um bloco [[alvo.componente]]")
        desconhecidos = sorted(set(bruto) - set(COMPONENTE_PERMITE))
        if desconhecidos:
            raise AlvoInvalido(f"{caminho.name}: componente de {nome_do_alvo!r} tem campo que "
                               f"não existe: {', '.join(desconhecidos)}. Permitidos: "
                               f"{', '.join(COMPONENTE_PERMITE)}")
        if not bruto.get("nome"):
            raise AlvoInvalido(f"{caminho.name}: componente de {nome_do_alvo!r} sem nome")
        papel = bruto.get("papel")
        if papel is not None and papel not in PAPEIS:
            raise AlvoInvalido(f"{caminho.name}: componente {bruto['nome']!r} tem papel "
                               f"{papel!r}; os papéis são {', '.join(PAPEIS)}")
        for campo in ("admin_url", "metricas_url"):
            if bruto.get(campo):
                _checar_url(bruto["nome"], campo, bruto[campo])
        saida.append(dict(bruto))
    return saida
```

No laço de `ler`, antes do `alvos.append(dict(bruto))`:

```python
        componentes = bruto.pop("componente", [])
        registro = dict(bruto)
        registro["componente"] = _checar_componentes(caminho, nome, componentes)
        alvos.append(registro)
```

> **Atenção:** `permitidos` (a allowlist de campos do alvo) precisa passar a aceitar
> `componente` — acrescente-o a `COMUNS`.

- [x] **Step 5: rodar a suíte inteira** — `.venv/bin/python -m pytest -q` → PASS.

- [x] **Step 6: commit**

```bash
git add scripts/lib/config.py scripts/lib/alvos.py tests/
git commit -m "feat(sw-infra-audit): config de insights e bloco de componente no alvo"
```

---

## Task 7: schema v3 — componentes e ordenação determinística

**Files:**
- Modify: `scripts/lib/report.py`
- Test: `tests/test_report_v3.py`

- [x] **Step 1: escrever o teste que falha**

```python
def test_alvo_nasce_com_lista_de_componentes():
    from lib.report import novo, novo_alvo, SCHEMA_VERSION
    assert SCHEMA_VERSION == 3
    assert novo(generated_at="2026-09-19T10:00:00Z")["schema_version"] == 3
    assert novo_alvo("cluster", "docker", "context: prod")["componentes"] == []


def test_componente_guarda_papel_respostas_e_achados():
    from lib.report import novo_componente
    c = novo_componente("proxy", "entrada")
    assert c == {"nome": "proxy", "papel": "entrada", "respostas": [], "achados": [],
                 "analise": ""}


def test_ordenar_deixa_componentes_e_respostas_em_ordem_estavel():
    """Sem isso a ordem vem do dicionário da coleta e dois relatórios da mesma entrada
    saem diferentes — o teste de determinismo viraria teatro."""
    from lib.report import novo, novo_alvo, novo_componente, ordenar
    r = novo("2026-09-19T10:00:00Z")
    alvo = novo_alvo("cluster", "docker", "context: prod")
    b = novo_componente("banco", "banco"); b["respostas"] = [
        {"pergunta": "entrada.latencia", "fonte": "promql", "valor": 1},
        {"pergunta": "entrada.volume_na_janela", "fonte": "promql", "valor": 2}]
    a = novo_componente("proxy", "entrada")
    alvo["componentes"] = [b, a]
    r["alvos"] = [alvo]

    saida = ordenar(r)

    assert [c["nome"] for c in saida["alvos"][0]["componentes"]] == ["banco", "proxy"]
    assert [x["pergunta"] for x in saida["alvos"][0]["componentes"][0]["respostas"]] == [
        "entrada.volume_na_janela", "entrada.latencia"]


def test_ordenar_nao_muta_a_entrada():
    from lib.report import novo, novo_alvo, novo_componente, ordenar
    r = novo("2026-09-19T10:00:00Z")
    alvo = novo_alvo("cluster", "docker", "onde")
    alvo["componentes"] = [novo_componente("z", "app"), novo_componente("a", "app")]
    r["alvos"] = [alvo]
    ordenar(r)
    assert [c["nome"] for c in r["alvos"][0]["componentes"]] == ["z", "a"]
```

- [x] **Step 2: rodar e ver falhar** — `SCHEMA_VERSION` é 2 e `novo_componente` não existe.

- [x] **Step 3: implementar**

```python
SCHEMA_VERSION = 3


def novo_componente(nome, papel):
    """Uma unidade dentro do alvo. `respostas` é o que as perguntas do papel devolveram;
    `analise` é do agente."""
    return {"nome": nome, "papel": papel, "respostas": [], "achados": [], "analise": ""}
```

Em `novo_alvo`, acrescente `"componentes": []` ao dicionário.

Em `ordenar`, substitua a construção de `copia["alvos"]`:

```python
def _componente_ordenado(componente):
    """Respostas na ordem declarada do catálogo (não na ordem em que chegaram), achados por
    severidade. A ordem da coleta depende de dicionário e de rede — não pode vazar pro arquivo."""
    from lib.perguntas import PERGUNTAS
    ordem = {id: pos for pos, id in enumerate(PERGUNTAS)}
    return dict(componente,
                respostas=sorted(componente.get("respostas", []),
                                 key=lambda r: (ordem.get(r.get("pergunta"), len(ordem)),
                                                str(r.get("pergunta")))),
                achados=sorted(componente.get("achados", []), key=_chave_do_achado))


def ordenar(relatorio):
    copia = dict(relatorio)
    copia["alvos"] = [
        dict(alvo,
             achados=sorted(alvo.get("achados", []), key=_chave_do_achado),
             componentes=[_componente_ordenado(c)
                          for c in sorted(alvo.get("componentes", []),
                                          key=lambda c: str(c.get("nome", "")))])
        for alvo in relatorio.get("alvos", [])]
    copia["aceites"] = sorted(relatorio.get("aceites", []),
                              key=lambda a: (a.get("alvo", ""), a.get("componente") or "",
                                             a.get("regra", "")))
    return copia
```

- [x] **Step 4: rodar** — `.venv/bin/python -m pytest tests/test_report_v3.py -q` → PASS.

- [x] **Step 5: `build_report` recusa v2 com mensagem clara**

Em `scripts/build_report.py`, as duas checagens `!= 2` viram `!= 3`, e a mensagem passa a ser:
`f"schema {r.get('schema_version')!r}: este build lê o v3; relatórios anteriores ficam onde estão"`.
Atualize as fixtures de `tests/test_build_report_v2.py` para `schema_version: 3` e renomeie o
arquivo para `tests/test_build_report_v3.py`.

- [x] **Step 6: commit**

```bash
git add scripts/lib/report.py scripts/build_report.py tests/
git commit -m "feat(sw-infra-audit)!: report.json v3 com componentes"
```

---

## Task 8: promoção de achado e aceite por componente

**Files:**
- Modify: `scripts/collect.py`, `scripts/lib/aceites.py`, `scripts/lib/historico.py`
- Test: `tests/test_collect_orquestrador.py`, `tests/test_aceites.py`, `tests/test_historico.py`

- [x] **Step 1: escrever os testes que falham**

```python
def test_achado_do_componente_e_promovido_para_o_alvo(tmp_path):
    """O relatório ordena, inventaria e compara histórico a partir de UMA lista — a do alvo.
    Achado que fica só no componente some dessas três coisas."""
    coletores = {"docker": lambda alvo, ctx: {
        "saude": "🟡",
        "componentes": [{"nome": "proxy", "papel": "entrada", "respostas": [],
                         "achados": [{"regra": "SEC_PORT_EXPOSED", "objeto": "adminer",
                                      "severidade": "medium"}], "analise": ""}]}}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    alvo = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert [a["regra"] for a in alvo["achados"]] == ["SEC_PORT_EXPOSED"]
    assert alvo["achados"][0]["componente"] == "proxy"
    assert alvo["achados"][0]["alvo"] == "cluster"


def test_coletor_que_devolve_componentes_invalidos_nao_derruba_o_alvo(tmp_path):
    coletores = {"docker": lambda alvo, ctx: {"saude": "🟢", "componentes": "isto não é lista"}}
    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    alvo = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")
    assert alvo["componentes"] == []
    assert any("componentes" in n["motivo"] for n in alvo["nao_coletado"])
```

```python
# tests/test_aceites.py
def test_aceite_com_componente_so_apaga_o_achado_daquele_componente():
    from lib import aceites
    alvos = [{"nome": "cluster", "coletado": True,
              "achados": [{"regra": "r", "alvo": "cluster", "componente": "fila_a"},
                          {"regra": "r", "alvo": "cluster", "componente": "fila_b"}],
              "componentes": [
                  {"nome": "fila_a", "achados": [{"regra": "r", "alvo": "cluster",
                                                  "componente": "fila_a"}]},
                  {"nome": "fila_b", "achados": [{"regra": "r", "alvo": "cluster",
                                                  "componente": "fila_b"}]}]}]

    aceites.aplicar(alvos, [{"alvo": "cluster", "componente": "fila_a", "regra": "r",
                             "motivo": "fila de rascunho", "origem": "projeto"}],
                    hoje="2026-09-19")

    assert [a["componente"] for a in alvos[0]["achados"]] == ["fila_b"]
    assert alvos[0]["componentes"][0]["achados"] == []
    assert len(alvos[0]["componentes"][1]["achados"]) == 1
```

```python
# tests/test_historico.py
def test_rodada_anterior_em_v2_gera_diff_com_aviso(tmp_path):
    """Sumir com o histórico calado é pior que comparar com ressalva."""
    from lib import historico
    anterior = tmp_path / "2026-09-12_0900"; anterior.mkdir()
    (anterior / "report.json").write_text(json.dumps(
        {"schema_version": 2, "alvos": [{"nome": "cluster",
          "achados": [{"regra": "r1", "objeto": "x"}]}]}), encoding="utf-8")
    atual = tmp_path / "2026-09-19_1000"

    pasta = historico.pasta_anterior(atual)
    diff = historico.comparar(json.loads((pasta / "report.json").read_text()),
                              {"schema_version": 3, "alvos": [{"nome": "cluster", "achados": []}]},
                              nome_anterior=pasta.name)

    assert diff["resolvidos"] == ["cluster · r1 · x"]
    assert "formato anterior" in diff["aviso"]
```

- [x] **Step 2: rodar e ver falhar** — nenhum dos três comportamentos existe.

- [x] **Step 3: implementar a promoção em `collect.py`**

`CAMPOS_DO_COLETOR` ganha `componentes` (senão o campo some, como acontece hoje com
`impact_points`):

```python
CAMPOS_DO_COLETOR = ("saude", "dimensoes", "fatos", "achados", "componentes")
```

E, depois da cópia dos campos, a promoção:

```python
def promover_achados(registro):
    """Achado nasce no componente e sobe para o alvo, carregando de onde veio.

    O alvo é a fonte única para ordenação, inventário e histórico; o componente guarda a
    sua cópia para a ficha dele no relatório. Quem aceita um risco pode mirar os dois níveis.
    """
    for componente in registro.get("componentes", []):
        for achado in componente.get("achados", []):
            achado.setdefault("alvo", registro["nome"])
            achado["componente"] = componente["nome"]
            registro["achados"].append(dict(achado))
    return registro
```

> Chame `promover_achados(registro)` em `coletar_alvo`, logo antes do `return registro` do
> caminho de sucesso. O `isinstance` que já valida cada campo do coletor cobre
> `componentes` sem mudança — `novo_alvo` passa a trazer `"componentes": []`, então o tipo
> esperado é `list`.

- [x] **Step 4: implementar o aceite por componente em `aceites.py`**

```python
def _casa(achado, aceite):
    if aceite.get("alvo") != achado.get("alvo") or aceite.get("regra") != achado.get("regra"):
        return False
    componente = aceite.get("componente")
    if componente is not None and componente != achado.get("componente"):
        return False
    objeto = aceite.get("objeto")
    return objeto in (None, achado.get("objeto"))
```

A chave de precedência passa a incluir o componente:

```python
        chave = (aceite.get("alvo"), aceite.get("componente"), aceite.get("regra"),
                 aceite.get("objeto"))
```

E o laço que filtra passa a varrer os dois níveis:

```python
        for alvo in alvos:
            alvo["achados"] = _filtrar(alvo.get("achados", []), aceite, vencido)
            for componente in alvo.get("componentes", []):
                componente["achados"] = _filtrar(componente.get("achados", []), aceite, vencido)
```

com o auxiliar (que também sinaliza se casou):

```python
def _filtrar(achados, aceite, vencido, casou=None):
    """Remove os achados aceitos. Vencido continua na lista, marcado — o risco volta a contar
    quando a justificativa expira."""
    restantes = []
    for achado in achados:
        if not _casa(achado, aceite):
            restantes.append(achado)
            continue
        if casou is not None:
            casou.append(True)
        if vencido:
            achado["aceite_vencido"] = True
            restantes.append(achado)
    return restantes
```

> Ajuste o controle de `casou` que já existe na função para usar a lista auxiliar — o campo
> `obsoleto` do aceite depende dele.

- [x] **Step 5: implementar o histórico tolerante em `historico.py`**

```python
ESQUEMAS_COMPARAVEIS = (2, 3)


def _relatorio(pasta):
    ...
    return dados if dados.get("schema_version") in ESQUEMAS_COMPARAVEIS else None


def comparar(anterior, atual, nome_anterior):
    antes, agora = _chaves(anterior), _chaves(atual)
    saida = {"vs": nome_anterior, "resolvidos": _formatar(antes - agora),
             "novos": _formatar(agora - antes)}
    if anterior.get("schema_version") != atual.get("schema_version"):
        saida["aviso"] = ("formato anterior: comparação limitada a alvo, regra e objeto — "
                          "o componente não existia no relatório anterior")
    return saida
```

E `_chaves` passa a incluir o componente quando ele existir:

```python
def _chaves(relatorio):
    return {(a.get("nome"), f.get("componente") or "", f.get("regra"), f.get("objeto") or "")
            for a in relatorio.get("alvos", []) for f in a.get("achados", [])}
```

- [x] **Step 6: rodar a suíte inteira** — `.venv/bin/python -m pytest -q` → PASS.

- [x] **Step 7: commit**

```bash
git add scripts/collect.py scripts/lib/aceites.py scripts/lib/historico.py tests/
git commit -m "feat(sw-infra-audit): achado do componente sobe para o alvo, aceite mira os dois"
```

---

## Task 9: `lib/catalogo.py` — ler e validar os arquivos de família

**Files:**
- Create: `scripts/lib/catalogo.py`
- Create: `references/metricas/traefik.toml`, `references/metricas/http-generico.toml`
- Test: `tests/test_catalogo.py`

- [ ] **Step 1: escrever o teste que falha**

```python
def test_carrega_familia_com_identificacao_e_perguntas():
    from lib.catalogo import familias
    todas = {f["familia"]: f for f in familias()}
    assert "traefik" in todas and "http-generico" in todas
    traefik = todas["traefik"]
    assert traefik["identificacao"]["metrica_presente"] == "traefik_service_requests_total"
    assert traefik["prioridade"] == 30
    assert "entrada.volume_na_janela" in {p["id"] for p in traefik["pergunta"]}


def test_familia_que_cita_pergunta_inexistente_e_recusada(tmp_path):
    import pytest
    from lib.catalogo import carregar_arquivo, CatalogoInvalido
    (tmp_path / "x.toml").write_text(
        'familia = "x"\nprioridade = 10\n[identificacao]\nmetrica_presente = "m"\n'
        '[[pergunta]]\nid = "entrada.inexistente"\nquery = "up"\n', encoding="utf-8")
    with pytest.raises(CatalogoInvalido) as erro:
        carregar_arquivo(tmp_path / "x.toml")
    assert "entrada.inexistente" in str(erro.value)


def test_query_so_aceita_as_duas_interpolacoes(tmp_path):
    """%SELETOR% e %JANELA% são as únicas. Qualquer outro %ALGO% seria um buraco por onde
    entra conteúdo não previsto na consulta."""
    import pytest
    from lib.catalogo import carregar_arquivo, CatalogoInvalido
    (tmp_path / "x.toml").write_text(
        'familia = "x"\nprioridade = 10\n[identificacao]\nmetrica_presente = "m"\n'
        '[[pergunta]]\nid = "entrada.volume_na_janela"\nquery = "sum(m{%FILTRO%})"\n',
        encoding="utf-8")
    with pytest.raises(CatalogoInvalido) as erro:
        carregar_arquivo(tmp_path / "x.toml")
    assert "%FILTRO%" in str(erro.value)


def test_pergunta_de_lista_sem_desempate_e_recusada(tmp_path):
    import pytest
    from lib.catalogo import carregar_arquivo, CatalogoInvalido
    (tmp_path / "x.toml").write_text(
        'familia = "x"\nprioridade = 10\n[identificacao]\nmetrica_presente = "m"\n'
        '[[pergunta]]\nid = "entrada.distribuicao_de_status"\nquery = "sum by (code) (m)"\n'
        'chave = "code"\n', encoding="utf-8")
    with pytest.raises(CatalogoInvalido):
        carregar_arquivo(tmp_path / "x.toml")
```

- [ ] **Step 2: rodar e ver falhar** — `lib.catalogo` não existe.

- [ ] **Step 3: escrever os arquivos de família**

`references/metricas/traefik.toml`:

```toml
# Família de exporter: o proxy Traefik. Identificada pela série que só ele publica.
familia = "traefik"
prioridade = 30

[identificacao]
metrica_presente = "traefik_service_requests_total"

[seletor]
# como amarrar o componente do inventário à série, em ordem de tentativa
etiquetas = ["service", "job", "instance"]

[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(increase(traefik_service_requests_total{%SELETOR%}[%JANELA%]))'
valor = "inteiro"

[[pergunta]]
id = "entrada.distribuicao_de_status"
query = 'sum by (code) (increase(traefik_service_requests_total{%SELETOR%}[%JANELA%]))'
chave = "code"
valor = "inteiro"
desempate = "chave"

[[pergunta]]
id = "entrada.latencia"
query = 'histogram_quantile(0.95, sum by (le) (rate(traefik_service_request_duration_seconds_bucket{%SELETOR%}[%JANELA%]))) * 1000'
valor = "decimal"
unidade = "ms"
```

`references/metricas/http-generico.toml`:

```toml
# O padrão de facto das bibliotecas de instrumentação (client_golang, prometheus-client,
# micrometer): http_requests_total + http_request_duration_seconds. Vale para qualquer app
# instrumentado, e é o que faz o papel `entrada` funcionar fora do Traefik.
familia = "http-generico"
prioridade = 40

[identificacao]
metrica_presente = "http_requests_total"

[seletor]
etiquetas = ["job", "service", "instance"]

[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(increase(http_requests_total{%SELETOR%}[%JANELA%]))'
valor = "inteiro"

[[pergunta]]
id = "entrada.distribuicao_de_status"
query = 'sum by (status) (increase(http_requests_total{%SELETOR%}[%JANELA%]))'
chave = "status"
valor = "inteiro"
desempate = "chave"

[[pergunta]]
id = "entrada.latencia"
query = 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{%SELETOR%}[%JANELA%]))) * 1000'
valor = "decimal"
unidade = "ms"
```

- [ ] **Step 4: implementar o carregador**

```python
"""Carrega os arquivos de família de exporter — o conhecimento de produto que NÃO vira código.

A validação é dura de propósito: arquivo que cita pergunta inexistente, interpolação fora das
duas permitidas ou lista sem desempate é recusado no carregamento, não na hora da coleta.
Erro de catálogo tem que aparecer no teste, não no relatório do cliente.
"""
import re
import tomllib
from pathlib import Path

INTERPOLACOES = ("%SELETOR%", "%JANELA%")
VALORES = ("inteiro", "decimal", "texto")
PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "metricas"
_MARCA = re.compile(r"%[A-Z_]+%")


class CatalogoInvalido(Exception):
    """Arquivo de família que a skill se recusa a interpretar."""


def carregar_arquivo(caminho):
    from lib.perguntas import PERGUNTAS
    caminho = Path(caminho)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise CatalogoInvalido(f"{caminho.name}: TOML inválido — {erro}") from erro

    for obrigatorio in ("familia", "prioridade", "identificacao"):
        if obrigatorio not in dados:
            raise CatalogoInvalido(f"{caminho.name}: falta {obrigatorio!r}")
    if "metrica_presente" not in dados["identificacao"]:
        raise CatalogoInvalido(f"{caminho.name}: identificacao sem `metrica_presente`")

    for pergunta in dados.get("pergunta", []):
        id_ = pergunta.get("id")
        if id_ not in PERGUNTAS:
            raise CatalogoInvalido(f"{caminho.name}: pergunta {id_!r} não existe no registro")
        query = pergunta.get("query", "")
        for marca in set(_MARCA.findall(query)) - set(INTERPOLACOES):
            raise CatalogoInvalido(f"{caminho.name}: interpolação {marca} não é permitida; "
                                   f"só {' e '.join(INTERPOLACOES)}")
        if pergunta.get("valor", "inteiro") not in VALORES:
            raise CatalogoInvalido(f"{caminho.name}: valor {pergunta.get('valor')!r} não existe")
        if PERGUNTAS[id_]["forma"] == "lista" and not pergunta.get("desempate"):
            raise CatalogoInvalido(f"{caminho.name}: {id_} é lista e não declara `desempate` — "
                                   f"empate de valor mudaria o relatório entre rodadas")
    return dados


def familias(pasta=PASTA):
    """Todas as famílias, em ordem estável (prioridade, depois nome)."""
    carregadas = [carregar_arquivo(p) for p in sorted(Path(pasta).glob("*.toml"))]
    return sorted(carregadas, key=lambda f: (f["prioridade"], f["familia"]))
```

- [ ] **Step 5: rodar** → PASS. **Step 6: commit**

```bash
git add scripts/lib/catalogo.py references/metricas/ tests/test_catalogo.py
git commit -m "feat(sw-infra-audit): catalogo de familias de exporter em arquivo"
```

---

## Task 10: adaptador `promql`

**Files:**
- Create: `scripts/lib/adaptadores/__init__.py`, `scripts/lib/adaptadores/promql.py`
- Test: `tests/test_adaptador_promql.py`

- [ ] **Step 1: escrever o teste que falha (integração, servidor local)**

```python
import json, threading, http.server, pytest


class _Prometheus(http.server.BaseHTTPRequestHandler):
    """Prometheus de mentira: responde o que a query pedir, gravando o que recebeu."""
    RESPOSTAS = {}
    RECEBIDAS = []
    MOMENTOS = []

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parametros = parse_qs(urlparse(self.path).query)
        self.RECEBIDAS.append(parametros.get("query", [""])[0])
        self.MOMENTOS.extend(parametros.get("time", []))
        corpo = json.dumps(self.RESPOSTAS.get("padrao")).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo))); self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a): pass


@pytest.fixture
def prometheus():
    servidor = http.server.HTTPServer(("127.0.0.1", 0), _Prometheus)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    _Prometheus.RECEBIDAS.clear(); _Prometheus.MOMENTOS.clear()
    yield f"http://127.0.0.1:{servidor.server_port}", _Prometheus
    servidor.shutdown()


def _resultado(pares):
    return {"status": "success",
            "data": {"resultType": "vector",
                     "result": [{"metric": m, "value": [0, str(v)]} for m, v in pares]}}


def test_responde_a_pergunta_da_familia_identificada(prometheus):
    base, falso = prometheus
    falso.RESPOSTAS["padrao"] = _resultado([({"__name__": "traefik_service_requests_total"}, 1),
                                            ({}, 12480)])
    from lib.adaptadores import promql

    resposta = promql.perguntar(
        pergunta="entrada.volume_na_janela",
        componente={"nome": "proxy", "papel": "entrada", "metricas_url": base},
        contexto={"at": "2026-09-19T10:00:00Z", "janela": "24h", "timeout": 2})

    assert resposta["fonte"].startswith("promql:")
    assert resposta["valor"] == 12480


def test_a_consulta_e_avaliada_no_instante_do_at(prometheus):
    """Sem âncora no --at, a janela anda com o relógio e duas execuções da mesma entrada
    dariam números diferentes — o teste de determinismo viraria teatro."""
    base, falso = prometheus
    falso.RESPOSTAS["padrao"] = _resultado([({}, 1)])
    from datetime import datetime, timezone
    from lib.adaptadores import promql

    promql.perguntar("entrada.volume_na_janela",
                     {"nome": "proxy", "papel": "entrada", "metricas_url": base},
                     {"at": "2026-09-19T10:00:00Z", "janela": "24h", "timeout": 2})

    esperado = int(datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc).timestamp())
    assert any("[24h]" in q for q in falso.RECEBIDAS), falso.RECEBIDAS
    assert falso.MOMENTOS and all(m == str(esperado) for m in falso.MOMENTOS), falso.MOMENTOS


def test_lista_empatada_sai_em_ordem_estavel(prometheus):
    base, falso = prometheus
    falso.RESPOSTAS["padrao"] = _resultado([({"code": "500"}, 7), ({"code": "200"}, 7),
                                            ({"code": "404"}, 7)])
    from lib.adaptadores import promql

    resposta = promql.perguntar("entrada.distribuicao_de_status",
                                {"nome": "proxy", "papel": "entrada", "metricas_url": base},
                                {"at": "2026-09-19T10:00:00Z", "janela": "24h", "timeout": 2})

    assert [item["chave"] for item in resposta["valor"]] == ["200", "404", "500"]


def test_sem_metricas_url_responde_sem_dados_com_motivo():
    from lib.adaptadores import promql
    resposta = promql.perguntar("entrada.volume_na_janela",
                                {"nome": "proxy", "papel": "entrada"},
                                {"at": "2026-09-19T10:00:00Z", "janela": "24h", "timeout": 2})
    assert resposta["sem_dados"] is True
    assert "metricas_url" in resposta["motivo"]
```

- [ ] **Step 2: rodar e ver falhar** — o pacote `lib.adaptadores` não existe.

- [ ] **Step 3: implementar o adaptador**

```python
"""Adaptador PromQL — o único que funciona sem credencial, e por isso o primeiro.

Ele não sabe o que é Traefik: sabe perguntar "que família você é?" olhando qual série existe,
e a partir daí as consultas vêm do arquivo da família. Pergunta que a família não expõe
responde `sem_dados` com o motivo — nunca se cai em outra família silenciosamente.
"""
from lib import catalogo, http_get

ID = "promql"


def _permitido(url):
    return [http_get.destino(url)]


def momento(at):
    """O `--at` em segundos de época. É ele que ancora a consulta: `/api/v1/query` aceita
    `time=`, e sem isso a janela andaria com o relógio de quem rodou."""
    from datetime import datetime, timezone
    texto = str(at).replace("Z", "+00:00")
    try:
        instante = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return int(instante.timestamp())


def _consultar(base, query, timeout, at=None):
    from urllib.parse import quote
    url = f"{base.rstrip('/')}/api/v1/query?query={quote(query)}"
    instante = momento(at) if at else None
    if instante is not None:
        url += f"&time={instante}"
    codigo, corpo = http_get.get_com_status(url, _permitido(base), timeout=timeout)
    if codigo != 200 or not corpo:
        return None
    import json
    try:
        dados = json.loads(corpo)
    except ValueError:
        return None
    if dados.get("status") != "success":
        return None
    return dados.get("data", {}).get("result", [])


def familia_do_componente(componente, contexto):
    """A primeira família (em ordem de prioridade) cuja métrica de identificação existe."""
    base = componente.get("metricas_url")
    for familia in catalogo.familias():
        serie = familia["identificacao"]["metrica_presente"]
        if _consultar(base, f"count({serie})", contexto["timeout"], contexto.get("at")):
            return familia
    return None


def _seletor(familia, componente, contexto):
    """`service="proxy"` — a primeira etiqueta da família que casa com o nome do componente."""
    for etiqueta in familia.get("seletor", {}).get("etiquetas", []):
        return f'{etiqueta}="{componente["nome"]}"'
    return ""


def _converter(bruto, tipo):
    return int(float(bruto)) if tipo == "inteiro" else float(bruto)


def perguntar(pergunta, componente, contexto):
    """Responde a pergunta ou devolve `sem_dados` com o motivo real. Nunca levanta."""
    base = componente.get("metricas_url")
    if not base:
        return {"pergunta": pergunta, "sem_dados": True,
                "motivo": "o componente não declara `metricas_url` no alvos.toml"}
    familia = familia_do_componente(componente, contexto)
    if familia is None:
        return {"pergunta": pergunta, "sem_dados": True,
                "motivo": "nenhuma família de métrica conhecida respondeu neste endereço"}
    declarada = next((p for p in familia.get("pergunta", []) if p["id"] == pergunta), None)
    if declarada is None:
        return {"pergunta": pergunta, "sem_dados": True,
                "motivo": f"o exporter {familia['familia']} não expõe o dado desta pergunta"}

    query = (declarada["query"].replace("%SELETOR%", _seletor(familia, componente, contexto))
                               .replace("%JANELA%", contexto.get("janela", "24h")))
    resultado = _consultar(base, query, contexto["timeout"], contexto.get("at"))
    if resultado is None:
        return {"pergunta": pergunta, "sem_dados": True,
                "motivo": "a fonte de métrica não respondeu"}

    fonte = f"{ID}:{familia['familia']}"
    tipo = declarada.get("valor", "inteiro")
    chave = declarada.get("chave")
    if chave:
        itens = [{"chave": str(linha["metric"].get(chave, "")),
                  "valor": _converter(linha["value"][1], tipo)} for linha in resultado]
        # desempate declarado: empate de valor resolve pela chave, nunca pela ordem da resposta
        itens.sort(key=lambda i: (-i["valor"], i["chave"]))
        return {"pergunta": pergunta, "fonte": fonte, "valor": itens}
    if not resultado:
        return {"pergunta": pergunta, "sem_dados": True, "motivo": "a consulta não devolveu série"}
    return {"pergunta": pergunta, "fonte": fonte,
            "valor": _converter(resultado[-1]["value"][1], tipo)}
```

E o registro, em `scripts/lib/adaptadores/__init__.py`:

```python
"""Registro de adaptadores. A ordem é por prioridade declarada — menor vence, porque mais
específico vence o mais genérico. Empate resolve pelo id, em ordem lexical: sem ordem total,
duas fontes equivalentes produziriam relatórios diferentes para a mesma entrada."""
from lib.adaptadores import promql

REGISTRO = {promql.ID: {"modulo": promql, "prioridade": 30}}


def todos():
    """Os adaptadores na ordem em que devem ser tentados."""
    return [item["modulo"] for _, item in
            sorted(REGISTRO.items(), key=lambda par: (par[1]["prioridade"], par[0]))]
```

- [ ] **Step 4: rodar** — `.venv/bin/python -m pytest tests/test_adaptador_promql.py -q` → PASS.

- [ ] **Step 5: prova por mutação do desempate**

Troque `itens.sort(key=lambda i: (-i["valor"], i["chave"]))` por `itens.sort(key=lambda i:
-i["valor"])` e rode: `test_lista_empatada_sai_em_ordem_estavel` **tem** que falhar. Reverta.

- [ ] **Step 6: a restrição de rede continua valendo**

Run: `.venv/bin/python -m pytest tests/test_restricoes.py -q`
Expected: PASS — `promql.py` não importa `urllib`/`socket`; toda rede passa por `http_get`.

- [ ] **Step 7: commit**

```bash
git add scripts/lib/adaptadores/ tests/test_adaptador_promql.py
git commit -m "feat(sw-infra-audit): adaptador promql com catalogo por familia"
```

---

## Task 11: orçamento por alvo que existe de verdade

**Files:**
- Create: `scripts/lib/orcamento.py`
- Modify: `scripts/collect.py`
- Test: `tests/test_orcamento.py`

Hoje `collect.py` põe `orcamento` no contexto e **nenhum coletor lê**. Com perguntas por
componente, uma fonte lenta seguraria a auditoria inteira.

- [ ] **Step 1: escrever o teste que falha**

```python
def test_prazo_corta_a_pergunta_seguinte_sem_derrubar_a_coleta():
    """Orçamento estourado não é erro: é `sem dados` com motivo, e o resto do relatório sai."""
    from lib.orcamento import Prazo
    relogio = iter([0.0, 5.0, 130.0, 130.0])
    prazo = Prazo(segundos=120, agora=lambda: next(relogio))

    assert prazo.restante() > 0
    assert prazo.esgotado() is False
    assert prazo.esgotado() is True
    assert prazo.motivo() == "orçamento do alvo esgotado"


def test_timeout_da_pergunta_nunca_passa_do_que_sobra():
    from lib.orcamento import Prazo
    relogio = iter([0.0, 115.0])
    prazo = Prazo(segundos=120, agora=lambda: next(relogio))
    assert prazo.timeout(pedido=20) == 5
```

- [ ] **Step 2: rodar e ver falhar** — `lib.orcamento` não existe.

- [ ] **Step 3: implementar**

```python
"""Prazo por alvo. Relógio monotônico, injetável para o teste não depender de dormir.

Estourar o prazo NÃO é erro: as perguntas que sobraram viram `sem dados` com motivo, e o
relatório sai com o que deu tempo de coletar. Fonte lenta atrasa um alvo, não a auditoria.
"""
import time


class Prazo:
    def __init__(self, segundos, agora=time.monotonic):
        self._agora = agora
        self._fim = agora() + float(segundos)

    def restante(self):
        return max(0.0, self._fim - self._agora())

    def esgotado(self):
        return self.restante() <= 0

    def timeout(self, pedido):
        """Nunca peça a uma fonte mais tempo do que o alvo ainda tem."""
        return int(min(float(pedido), self.restante()))

    @staticmethod
    def motivo():
        return "orçamento do alvo esgotado"
```

- [ ] **Step 4: ligar no `collect.py`**

Dentro do laço de perguntas de cada componente (Task 12), antes de cada pergunta:

```python
        if prazo.esgotado():
            componente["respostas"].append(
                {"pergunta": pergunta["id"], "sem_dados": True, "motivo": prazo.motivo()})
            continue
        contexto_da_pergunta = dict(contexto, timeout=prazo.timeout(contexto["timeout"]))
```

- [ ] **Step 5: rodar** → PASS. **Step 6: commit**

```bash
git add scripts/lib/orcamento.py tests/test_orcamento.py
git commit -m "feat(sw-infra-audit): orcamento por alvo passa a valer"
```

---

## Task 12: orquestrar as perguntas na coleta

**Files:**
- Modify: `scripts/collect.py`, `scripts/lib/coletores/docker.py`
- Test: `tests/test_collect_perguntas.py`

- [ ] **Step 1: escrever o teste que falha**

```python
def test_cada_componente_responde_as_perguntas_do_seu_papel(tmp_path):
    """O componente do inventário vira ficha com respostas carimbadas pela fonte."""
    import collect

    def coletor_falso(alvo, contexto):
        return {"saude": "🟢",
                "componentes": [{"nome": "proxy", "papel": "entrada", "respostas": [],
                                 "achados": [], "analise": "",
                                 "metricas_url": "http://127.0.0.1:1"}]}

    respostas = {"entrada.volume_na_janela": {"fonte": "promql:traefik", "valor": 12480}}

    class AdaptadorFalso:
        ID = "falso"
        @staticmethod
        def perguntar(pergunta, componente, contexto):
            if pergunta in respostas:
                return dict(respostas[pergunta], pergunta=pergunta)
            return {"pergunta": pergunta, "sem_dados": True, "motivo": "não sei responder"}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                 coletores={"docker": coletor_falso}, adaptadores=[AdaptadorFalso])
    alvo = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")
    componente = alvo["componentes"][0]

    assert [r["pergunta"] for r in componente["respostas"]] == [
        "entrada.volume_na_janela", "entrada.distribuicao_de_status", "entrada.latencia"]
    assert componente["respostas"][0]["valor"] == 12480
    assert componente["respostas"][0]["fonte"] == "promql:traefik"
    assert componente["respostas"][1]["motivo"] == "não sei responder"


def test_adaptador_que_estoura_nao_derruba_o_alvo(tmp_path):
    """O `except Exception` de coletar_alvo retorna cedo e apagaria o inventário inteiro por
    causa de UMA pergunta. O contorno é da pergunta, não do alvo."""
    import collect

    def coletor_falso(alvo, contexto):
        return {"saude": "🟢", "componentes": [{"nome": "proxy", "papel": "entrada",
                                                "respostas": [], "achados": [], "analise": ""}]}

    class AdaptadorQuebrado:
        ID = "quebrado"
        @staticmethod
        def perguntar(pergunta, componente, contexto):
            raise RuntimeError("bug do adaptador")

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                 coletores={"docker": coletor_falso}, adaptadores=[AdaptadorQuebrado])
    alvo = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert alvo["componentes"][0]["nome"] == "proxy"
    assert alvo["saude"] == "🟢", "o alvo não pode virar erro por causa de uma pergunta"
    assert all(r.get("erro_interno") for r in alvo["componentes"][0]["respostas"])
```

- [ ] **Step 2: rodar e ver falhar** — `main` ainda não aceita `adaptadores`.

> **Nota do juiz do lote 1 — a trava precisa de dente aqui.** Hoje os dois chamadores montam
> `permitido = [destino(url)]`, ou seja, a allowlist é derivada da própria URL que vai ser
> chamada: ela recusa host errado, mas se autoriza sozinha. Quando o adaptador for chamado,
> `responder()` deve passar a lista **declarada no alvo** (`metricas_url`/`admin_url` de cada
> componente mais os do alvo), não a derivada. Sem isso, a Restrição 3 vale menos do que parece.

- [ ] **Step 3: implementar em `collect.py`**

```python
def adaptadores_padrao():
    """O registro de verdade. Importado aqui dentro para o módulo não puxar rede à toa —
    e para o teste conseguir rodar com adaptadores falsos."""
    from lib import adaptadores
    return adaptadores.todos()


def responder(componente, contexto, adaptadores, prazo):
    """Faz as perguntas do papel do componente e guarda a resposta com a fonte.

    Cada pergunta tem o seu contorno: bug de adaptador vira `erro_interno` DAQUELA pergunta e
    a coleta segue. Sem isso, uma pergunta quebrada apagaria o inventário inteiro do alvo.
    """
    from lib.perguntas import do_papel
    for pergunta in do_papel(componente["papel"]):
        if prazo.esgotado():
            componente["respostas"].append({"pergunta": pergunta["id"], "sem_dados": True,
                                            "motivo": prazo.motivo()})
            continue
        contexto_pergunta = dict(contexto, timeout=prazo.timeout(contexto["timeout"]))
        resposta = None
        for adaptador in adaptadores:
            try:
                candidata = adaptador.perguntar(pergunta["id"], componente, contexto_pergunta)
            except Exception as erro:              # noqa: BLE001 — bug do adaptador
                candidata = {"pergunta": pergunta["id"], "erro_interno": True,
                             "motivo": f"{adaptador.ID}: {type(erro).__name__}: {erro}"}
            if not candidata.get("sem_dados"):
                resposta = candidata
                break
            resposta = resposta or candidata       # guarda o primeiro motivo real
        componente["respostas"].append(resposta)
    return componente
```

Em `coletar_alvo`, depois de copiar os campos do coletor e antes de promover os achados:

```python
    prazo = Prazo(contexto.get("orcamento", 120))
    for componente in registro.get("componentes", []):
        responder(componente, contexto, adaptadores, prazo)
```

E `main` ganha o parâmetro, do mesmo jeito que já faz com `coletores`:

```python
def main(argv=None, coletores=None, adaptadores=None):
    ...
    adaptadores = adaptadores_padrao() if adaptadores is None else adaptadores
    contexto = {..., "janela": cfg.valor("insights.janela") or "24h"}
```

- [ ] **Step 4: o coletor docker passa a devolver componentes — e o impacto para de sumir**

Em `scripts/lib/coletores/docker.py`, a allowlist de `fatos` ganha `impact_points`: hoje
`impact.build(r)` roda e o resultado é jogado fora porque a chave não está na lista copiada.

```python
    fatos = {chave: bruto.get(chave) for chave in
             ("nodes", "services", "networks", "secrets", "configs", "stacks", "tls", "scope",
              "runtime", "impact_points")
             if bruto.get(chave) is not None}
```

- [ ] **Step 5: o coletor docker monta os componentes**

Em `scripts/lib/coletores/docker.py`, no fim de `coletar`, monte a lista a partir dos serviços
que o inventário já tem:

```python
    from lib.papel import papel_de
    from lib import report as report_mod

    declarados = {c["nome"]: c for c in alvo.get("componente", [])}
    componentes = []
    for servico in bruto.get("services", []):
        nome = servico.get("name")
        declarado = declarados.get(nome, {})
        componente = report_mod.novo_componente(
            nome, papel_de(detect_kind(servico.get("image")), declarado.get("papel")))
        # o endereço de métrica do componente: o declarado nele, ou o do alvo
        componente["metricas_url"] = declarado.get("metricas_url") or alvo.get("metricas_url")
        componentes.append(componente)
```

e acrescente `"componentes": componentes` ao dicionário devolvido.

- [ ] **Step 6: rodar a suíte inteira** — `.venv/bin/python -m pytest -q` → PASS.

- [ ] **Step 7: commit**

```bash
git add scripts/collect.py scripts/lib/coletores/docker.py tests/test_collect_perguntas.py
git commit -m "feat(sw-infra-audit): componentes respondem as perguntas do seu papel"
```

---

## Task 13: catálogo de remediação

**Files:**
- Create: `scripts/lib/remediacao.py`, `references/remediacao/*.md`
- Modify: `scripts/collect.py`
- Test: `tests/test_remediacao.py`

- [ ] **Step 1: escrever o teste que falha (é a fitness function nº 1)**

```python
def test_toda_regra_que_vira_achado_tem_remediacao():
    """Achado sem o que fazer é meia informação. Regra `esperada` não precisa: ela descreve
    um comportamento normal, não um problema."""
    from lib.regras import exigem_remediacao
    from lib.remediacao import disponiveis
    faltando = sorted(exigem_remediacao() - disponiveis())
    assert faltando == [], f"regras sem arquivo em references/remediacao/: {faltando}"


def test_remediacao_traz_os_quatro_blocos():
    from lib.remediacao import para
    bloco = para("SEC_PORT_EXPOSED")
    assert bloco["titulo"]
    assert bloco["por_que_importa"] and bloco["como_resolver"]
    assert bloco["como_confirmar"] and bloco["quando_nao_fazer"]


def test_arquivo_sem_um_dos_blocos_e_recusado(tmp_path):
    import pytest
    from lib.remediacao import carregar_arquivo, RemediacaoInvalida
    (tmp_path / "x.md").write_text("---\nregra: x\ntitulo: X\n---\n## Por que importa\nnada\n",
                                   encoding="utf-8")
    with pytest.raises(RemediacaoInvalida):
        carregar_arquivo(tmp_path / "x.md")


def test_achado_chega_ao_relatorio_com_o_passo_a_passo(tmp_path):
    import collect
    coletores = {"docker": lambda alvo, ctx: {"saude": "🟡", "componentes": [],
        "achados": [{"regra": "SEC_PORT_EXPOSED", "objeto": "adminer", "severidade": "medium",
                     "alvo": "cluster"}]}}
    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    achado = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")["achados"][0]
    assert "como_resolver" in achado and achado["como_resolver"]["como_confirmar"]
```

- [ ] **Step 2: rodar e ver falhar** — `lib.remediacao` não existe.

- [ ] **Step 3: escrever um arquivo por regra**

Modelo (`references/remediacao/SEC_PORT_EXPOSED.md`) — repita a estrutura para **todas** as
regras de `exigem_remediacao()`:

```markdown
---
regra: SEC_PORT_EXPOSED
titulo: Porta publicada em todas as interfaces do host
---

## Por que importa

A porta está publicada em `0.0.0.0`, ou seja, em todas as interfaces do host. Isso não prova
que ela é alcançável da internet — firewall e security group da nuvem são invisíveis para esta
auditoria —, mas é a superfície: se a regra de rede mudar, o serviço fica exposto sem que
ninguém precise reconfigurar nada.

## Como resolver

1. Descubra quem precisa alcançar a porta. Se for só outro serviço do cluster, ela não precisa
   ser publicada: a rede interna já resolve pelo nome do serviço.
2. Publique na interface interna, em vez de em todas.
3. Se a porta precisa mesmo ser pública, deixe o firewall explícito — não conte com a sorte.

```yaml
# docker-compose / stack: em vez de "8080:8080"
ports:
  - target: 8080
    published: 8080
    protocol: tcp
    mode: host          # publica só onde a task roda
```

## Como confirmar

Rode a auditoria de novo: o achado sai da lista. Para conferir na mão, `docker service inspect
<serviço> --format '{{json .Endpoint.Ports}}'` mostra o bind resultante.

## Quando NÃO fazer

Quando a porta é justamente o ponto de entrada público do cluster (o proxy na 80/443). Aí a
publicação é o desenho, não o problema — registre como risco aceito com justificativa.
```

> **Comandos são para exibir, nunca para executar.** A skill não roda nada disto; quem executa
> é o dono, depois de ler. Isto vale para todo arquivo do catálogo e está na `SKILL.md`.

- [ ] **Step 4: implementar o leitor**

```python
"""Catálogo de remediação: o que fazer, em arquivo versionado, não em prosa gerada na hora.

Texto gerado varia a cada rodada e não passa por revisão. Aqui o mínimo é garantido e revisável
em pull request; o agente pode ENRIQUECER a análise, nunca substituir isto.
"""
import re
from pathlib import Path

BLOCOS = {"Por que importa": "por_que_importa", "Como resolver": "como_resolver",
          "Como confirmar": "como_confirmar", "Quando NÃO fazer": "quando_nao_fazer"}
PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "remediacao"


class RemediacaoInvalida(Exception):
    """Arquivo de remediação fora do formato de quatro blocos."""


def carregar_arquivo(caminho):
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8")
    cabecalho = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not cabecalho:
        raise RemediacaoInvalida(f"{caminho.name}: falta o cabeçalho com `regra` e `titulo`")
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", cabecalho.group(1), re.M))
    corpo = texto[cabecalho.end():]
    secoes = {t.strip(): c.strip() for t, c in
              re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", corpo, re.S | re.M)}
    faltando = [titulo for titulo in BLOCOS if titulo not in secoes]
    if faltando:
        raise RemediacaoInvalida(f"{caminho.name}: falta o bloco {faltando[0]!r}")
    bloco = {"regra": meta.get("regra"), "titulo": meta.get("titulo")}
    bloco.update({chave: secoes[titulo] for titulo, chave in BLOCOS.items()})
    return bloco


def disponiveis(pasta=PASTA):
    return {p.stem for p in Path(pasta).glob("*.md")}


def para(regra, pasta=PASTA):
    """O bloco daquela regra, ou None. Regra sem arquivo não quebra o relatório — quebra o
    teste, que é onde esse erro tem que aparecer."""
    caminho = Path(pasta) / f"{regra}.md"
    return carregar_arquivo(caminho) if caminho.exists() else None
```

- [ ] **Step 5: anexar ao achado em `collect.py`**

Depois de `aceites_mod.aplicar(...)`, antes de `ordenar`:

```python
    from lib import remediacao
    for alvo in relatorio["alvos"]:
        for achado in alvo["achados"]:
            bloco = remediacao.para(achado.get("regra"))
            if bloco:
                achado["como_resolver"] = bloco
```

- [ ] **Step 6: rodar** → PASS, inclusive a fitness function nº 1.

- [ ] **Step 7: commit**

```bash
git add scripts/lib/remediacao.py references/remediacao/ scripts/collect.py tests/test_remediacao.py
git commit -m "feat(sw-infra-audit): catalogo de remediacao por regra"
```

---

## Task 14: relatório v3 — sumário, insights por sistema, impacto de volta, como resolver

**Files:**
- Create: `assets/report-template/template_v3.html`
- Modify: `scripts/build_report.py`
- Test: `tests/test_build_report_v3.py`

A direção visual é a aprovada no dossiê (`referencias/direcao-visual-analytics.png` e
`referencias/direcao-visual-insights-e-remediacao.png`): cartões com ar, cor com função,
gráficos desenhados em CSS, `%%PLACEHOLDER%%` substituído em **uma passada**.

- [ ] **Step 1: escrever o teste que falha**

```python
def _relatorio_v3():
    return {"schema_version": 3, "generated_at": "2026-09-19T10:00:00Z",
            "resumo": "", "fortes": [], "fracos": [], "recomendacoes": [], "aceites": [],
            "historico": None, "inventario": [],
            "alvos": [{"nome": "cluster", "tipo": "docker", "onde": "context: prod",
                       "saude": "🟡", "dimensoes": {}, "nao_coletado": [],
                       "fatos": {"impact_points": [
                           {"titulo": "Proxy é ponto único", "cenario": "se o proxy cair",
                            "consequencia": "17 aplicações saem do ar"}]},
                       "analise": "",
                       "achados": [{"regra": "SEC_PORT_EXPOSED", "objeto": "adminer",
                                    "severidade": "medium", "alvo": "cluster",
                                    "componente": "adminer",
                                    "como_resolver": {"titulo": "Porta publicada",
                                        "por_que_importa": "é a superfície",
                                        "como_resolver": "1. publique na interna",
                                        "como_confirmar": "rode a auditoria de novo",
                                        "quando_nao_fazer": "quando é o proxy público"}}],
                       "componentes": [{"nome": "proxy", "papel": "entrada", "achados": [],
                                        "analise": "",
                                        "respostas": [
                                            {"pergunta": "entrada.volume_na_janela",
                                             "fonte": "promql:traefik", "valor": 12480},
                                            {"pergunta": "entrada.latencia", "sem_dados": True,
                                             "motivo": "o exporter não expõe histograma"}]}]}]}


def test_sumario_lista_as_secoes_sem_numero_de_pagina():
    """Número de página exigiria segunda passada dependente de ferramenta externa — saída
    diferente por máquina. O sumário fica; os números, não."""
    import build_report
    html = build_report.render_html_v3(_relatorio_v3())
    assert "Sumário" in html
    assert "Insights por sistema" in html and "Achados" in html
    assert "pág." not in html


def test_insight_mostra_valor_e_fonte_e_o_sem_dados_mostra_o_motivo():
    import build_report
    html = build_report.render_html_v3(_relatorio_v3())
    assert "12.480" in html or "12480" in html
    assert "promql:traefik" in html
    assert "o exporter não expõe histograma" in html


def test_achado_traz_como_resolver_e_como_confirmar():
    import build_report
    html = build_report.render_html_v3(_relatorio_v3())
    assert "Como resolver" in html and "Como confirmar" in html
    assert "rode a auditoria de novo" in html


def test_impacto_volta_a_aparecer():
    """Hoje `impact.build` roda em coletores/docker.py e o resultado é descartado, porque a
    chave não está na allowlist copiada para `fatos`. O relatório precisa mostrá-lo."""
    import build_report
    html = build_report.render_html_v3(_relatorio_v3())
    assert "17 aplicações saem do ar" in html


def test_valor_dinamico_continua_escapado():
    import build_report
    r = _relatorio_v3()
    r["alvos"][0]["componentes"][0]["nome"] = '<script>alert(1)</script>'
    html = build_report.render_html_v3(r)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_placeholder_escrito_pelo_agente_nao_injeta_secao():
    """Substituição em UMA passada: %%ALVOS%% escrito dentro do resumo é texto, não seção."""
    import build_report
    r = _relatorio_v3()
    r["resumo"] = "o agente escreveu %%ALVOS%% aqui"
    html = build_report.render_html_v3(r)
    assert html.count('id="alvos"') == 1
```

- [ ] **Step 2: rodar e ver falhar** — `render_html_v3` não existe.

- [ ] **Step 3: escrever o template**

Copie `assets/report-template/template_v2.html` para `template_v3.html` e substitua o corpo
pelos blocos da direção aprovada, nesta ordem, com estes placeholders:

```
%%TITLE%% %%GENERATED_AT%% %%CAPA_CHIPS%% %%RESUMO%%
%%SUMARIO%%
%%PANORAMA%% %%INVENTARIO%%
%%INSIGHTS%%          ← seção "Insights por sistema": um cartão por componente
%%ACHADOS%%           ← cada achado com "Como resolver" e "Como confirmar"
%%IMPACTO%%           ← o que impact.py produz
%%ACEITES%% %%RECOMENDACOES%% %%FORTES%% %%FRACOS%% %%ALVOS%% %%HISTORICO%%
```

O CSS sai do mockup aprovado (`/tmp/mockup-preview/relatorio-infra/estilo.css`, bloco `.rep.d7`);
copie-o inteiro para dentro do `<style>` do template, trocando o seletor `.rep.d7` por `body`.
Mantenha o bloco `@media print` do v2 (A4, `print-color-adjust`, quebras controladas).

- [ ] **Step 4: implementar o renderizador**

```python
def _insights_v3(alvos):
    """Um cartão por componente: papel, respostas com a fonte, e o que não foi respondido
    com o motivo. Insight sem fonte não existe — é isso que separa dado de chute."""
    from lib.perguntas import PERGUNTAS
    blocos = []
    for alvo in alvos:
        for componente in alvo.get("componentes", []):
            linhas = []
            for resposta in componente.get("respostas", []):
                titulo = _e(PERGUNTAS.get(resposta["pergunta"], {}).get(
                    "titulo", resposta["pergunta"]))
                if resposta.get("sem_dados") or resposta.get("erro_interno"):
                    linhas.append(f'<div class="semdados"><b>{titulo}</b> — '
                                  f'{_e(resposta.get("motivo"))}</div>')
                else:
                    linhas.append(
                        f'<div class="insight"><b>{titulo}</b>'
                        f'<span class="v">{_valor(resposta["valor"])}</span>'
                        f'<span class="src">fonte: {_e(resposta["fonte"])}</span></div>')
            blocos.append(f'<div class="card pad"><div class="sys">'
                          f'<span class="tag">{_e(componente["papel"])}</span>'
                          f'<h3>{_e(componente["nome"])}</h3></div>{"".join(linhas)}</div>')
    return "".join(blocos) or '<p class="muted">nenhum componente respondeu nesta rodada.</p>'


def _valor(valor):
    """Escalar vira número; lista vira barra de ranking. Sempre escapado."""
    if isinstance(valor, list):
        maior = max((item.get("valor", 0) for item in valor), default=0) or 1
        return "".join(
            f'<div class="rk"><span class="lb">{_e(item.get("chave"))}</span>'
            f'<span class="vl">{_e(item.get("valor"))}</span>'
            f'<span class="bar"><i style="width:{100 * item.get("valor", 0) / maior:.0f}%"></i>'
            f'</span></div>' for item in valor)
    return _e(valor)
```

O `render_html_v3` segue o mesmo desenho do `render_html_v2`: monta o `repl`, lê o template e
faz **uma** passada de `re.sub(r"%%[A-Z_]+%%", ...)`.

- [ ] **Step 5: rodar** — `.venv/bin/python -m pytest tests/test_build_report_v3.py -q` → PASS.

- [ ] **Step 6: conferir o A4 de verdade**

```bash
cd ~/.claude/skills/sw-infra-audit
.venv/bin/python -c "
import sys; sys.path.insert(0,'scripts')
import json, build_report, pathlib
d = pathlib.Path('/tmp/prova-v3'); d.mkdir(exist_ok=True)
json.dump(__import__('tests.test_build_report_v3', fromlist=['_relatorio_v3'])._relatorio_v3(),
          open(d/'report.json','w'))
print(build_report.build(json.load(open(d/'report.json')), str(d)))
"
```
Expected: gera `relatorio.html` e, havendo Chromium, `relatorio.pdf`. Abra o PDF e confira:
quebra de página não corta cartão de insight ao meio, o sumário está na primeira página, e os
blocos "Como resolver" não ficam órfãos do título.

- [ ] **Step 7: commit**

```bash
git add assets/report-template/template_v3.html scripts/build_report.py tests/
git commit -m "feat(sw-infra-audit): relatorio v3 com insights, remediacao e sumario"
```

---

## Task 15: fechar as restrições verificáveis

**Files:**
- Modify: `tests/test_restricoes.py`
- Test: o próprio arquivo

- [ ] **Step 1: escrever os testes que faltam**

```python
def test_mesma_entrada_mesmo_byte_com_perguntas(tmp_path, monkeypatch):
    """Restrição 5, agora com insights: mesmas respostas gravadas e mesmo --at, mesmo arquivo."""
    import json, collect

    class AdaptadorGravado:
        ID = "gravado"
        @staticmethod
        def perguntar(pergunta, componente, contexto):
            return {"pergunta": pergunta, "fonte": "gravado:x",
                    "valor": [{"chave": "200", "valor": 7}, {"chave": "404", "valor": 7}]}

    def coletor(alvo, ctx):
        return {"saude": "🟢", "componentes": [
            {"nome": "proxy", "papel": "entrada", "respostas": [], "achados": [], "analise": ""}]}

    saidas = []
    for rodada in ("a", "b"):
        destino = tmp_path / rodada; destino.mkdir()
        collect.main([*ambiente(destino), "--confirmar", "cluster"],
                     coletores={"docker": coletor}, adaptadores=[AdaptadorGravado])
        saidas.append((destino / "saida" / "report.json").read_bytes())

    assert saidas[0] == saidas[1]


def test_adaptador_nao_abre_rede_por_fora():
    """Restrição de rede, estendida: nenhum adaptador importa urllib/socket direto."""
    import ast, pathlib
    scripts = pathlib.Path(__file__).resolve().parents[1] / "scripts"
    for arquivo in (scripts / "lib" / "adaptadores").rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = ([a.name for a in no.names] if isinstance(no, ast.Import)
                     else [no.module or ""] if isinstance(no, ast.ImportFrom) else [])
            proibidos = {"socket", "ssl", "urllib", "http", "requests", "httpx"}
            assert not {str(n).split(".")[0] for n in nomes} & proibidos, \
                f"{arquivo.name} abre rede fora do lib/http_get.py"
```

- [ ] **Step 2: rodar a suíte inteira**

Run: `cd ~/.claude/skills/sw-infra-audit && .venv/bin/python -m pytest -q`
Expected: PASS, com contagem acima de 340 testes.

- [ ] **Step 3: rodar as cinco provas por mutação, uma a uma**

| Mutação | Teste que TEM que falhar |
|---|---|
| `check_allowed` ignora a porta | `test_porta_nao_declarada_e_recusada` |
| `ambiente()` volta a copiar `os.environ` | `test_ambiente_do_filho_e_base_positiva` |
| `itens.sort` sem o desempate por chave | `test_lista_empatada_sai_em_ordem_estavel` |
| `exigem_remediacao()` devolve `set()` | nenhum — **se nenhum falhar, a FF1 é decorativa**: conserte o teste |
| `_consultar` para de mandar `time=` | `test_a_consulta_e_avaliada_no_instante_do_at` |

Reverta cada mutação antes da próxima.

- [ ] **Step 4: commit**

```bash
git add tests/test_restricoes.py
git commit -m "test(sw-infra-audit): restricoes verificaveis do plano 1"
```

---

## Task 16: publicar

**Files:**
- Modify: `SKILL.md`, `CHANGELOG.md` (no marketplace)

- [ ] **Step 1: atualizar a `SKILL.md`**

Acrescente: a seção de insights por sistema (papel → perguntas → fonte), a regra
**"comando de remediação é para exibir, nunca para executar"**, o bloco `[[alvo.componente]]`
no exemplo de configuração, e a chave `insights.janela`. Mantenha o tom do arquivo.

- [ ] **Step 2: sincronizar e conferir o gate**

```bash
cd /var/www/ai-marketplace
make sync SKILL=sw-infra-audit BUMP=minor
make check
```
Expected: `✓ gate de segurança: nada sensível detectado`.

- [ ] **Step 3: CHANGELOG**

Entrada em `### Adicionado` descrevendo: insights por sistema com fonte declarada, remediação
por regra, schema v3, egress com porta, ambiente do filho como base positiva, orçamento que
passa a valer. Linguagem do arquivo: o que muda para quem usa, e por quê.

- [ ] **Step 4: marcar o dossiê**

```bash
python3 ~/.claude/skills/sw-brainstorming/scripts/dossie.py estado \
  2026-09-19-insights-por-sistema-e-remediacao-na-sw-infra-audit concluido
```

- [ ] **Step 5: commit**

```bash
git add plugins/sw-infra-audit CHANGELOG.md docs/specs README.md .claude-plugin/marketplace.json
git commit -m "feat(sw-infra-audit): insights por sistema e remediacao (plano 1)"
```

---

## Depois deste plano

Os planos 2, 3 e 4 do [spec.md](spec.md) continuam de pé e **não** entram aqui: `admin_http` +
fila (2), `sql` + banco (3), `logql` + segurança do tráfego (4). Cada um começa pelo seu
catálogo de dados e reaproveita tudo o que este plano construiu — papel, perguntas, adaptador,
orçamento, schema e remediação.
