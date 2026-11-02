# Plano de implementação — Relatório de infra simples e por tipo de sistema

[spec.md](spec.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** transformar o relatório da `sw-infra-audit` em 1 página + até 20, para leigos e técnicos, com serviços online como dado principal.

**Arquitetura:** o `render_html_v3` passa a montar capa, saúde por sistema, blocos por papel e problemas agrupados. Estados e nota nascem em módulos puros, gravados no `report.json` depois dos aceites. A coleta nova entra por fonte, e o que não tiver fonte aparece como não medido.

**Stack:** Python 3 da stdlib, pytest, HTML/CSS em `template_v3.html`, Prometheus HTTP API e Chromium para PDF.

**Local:** editar em `~/.claude/skills/sw-infra-audit`, rodar testes com `.venv/bin/pytest` a partir dessa pasta e publicar com `make sync`.

**Restrições verificáveis (do spec):**
| Restrição | Como o plano checa |
|---|---|
| Fixture de 60 serviços e 216 achados gera até 21 páginas | Task 10, step 1 e step 4 |
| Serviço ou nó fora nunca produz nota acima de 59 | Task 3, step 1 |
| Parcela não medida nunca soma como zero | Task 3, step 1 |
| Bloco sem dado renderiza "não medido" | Task 6, step 1 e step 6 |
| Classe CSS dos blocos existe no template | Task 5, step 1 |
| Toda recomendação aparece no relatório | Task 9, step 1 |

---

### Task 1: Spike das fontes reais

Spike descartável, somente leitura. Produto: `referencias/spike-fontes.md`. Deu certo se responder às cinco suposições do spec. Se uma fonte não existir, o bloco fica como não medido e as tasks 12 a 16 encolhem conforme o resultado.

**Arquivos:**
- Criar: `docs/specs/2026-11-01-relatorio-de-infra-simples-e-por-tipo-de-sistema/referencias/spike-fontes.md`

**Depende de:** nada

- [x] **Step 1: abrir o acesso já declarado**

Peça ao dono que abra o túnel do Prometheus declarado em `docs/infra/alvos.toml`. Rode só contra esse host, com a variável `P`.

- [x] **Step 2: medir as cinco perguntas**

```bash
curl -s "$P/api/v1/status/runtimeinfo" | python3 -m json.tool | grep -i retention
curl -s "$P/api/v1/label/__name__/values" | python3 -c "import json,sys; n=json.load(sys.stdin)['data']; print({p: sum(x.startswith(p) for x in n) for p in ('node_','traefik_router','traefik_service_req','container_last_seen')})"
curl -s "$P/api/v1/label/container_label_com_docker_swarm_service_name/values"
curl -s "$P/api/v1/label/service/values"; curl -s "$P/api/v1/label/router/values"
curl -s "$P/api/v1/label/instance/values"
curl -s "$P/api/v1/label/mountpoint/values"; curl -s "$P/api/v1/label/nodename/values"
curl -gs "$P/api/v1/query?query=min_over_time(timestamp(up)[90d:1d])" | head -c 400
time curl -s "$P/api/v1/query?query=count(container_last_seen)" > /dev/null
time curl -gs "$P/api/v1/query?query=avg_over_time((count(container_last_seen)%20%3E%20bool%200)[30d:1h])" > /dev/null
time curl -gs "$P/api/v1/query_range?query=sum(rate(container_cpu_usage_seconds_total[1h]))&start=$(date -d '-24 hours' +%s)&end=$(date +%s)&step=3600" > /dev/null
```

- [x] **Step 3: registrar as respostas**

Grave em `spike-fontes.md`, sem endereços nem nomes reais de serviços: retenção; existência de `node_`; rota no Traefik; por que 20 respostas do cAdvisor vieram vazias; custo por consulta com 57 serviços; série possível para disponibilidade. Registre em "Ajustes durante a execução", no fim deste arquivo, o que muda nas tasks 12 a 16.

### Task 2: Estado de cada serviço

**Arquivos:**
- Criar: `scripts/lib/estado_servico.py`
- Teste: `tests/test_estado_servico.py`

**Depende de:** nada

**Contrato que esta task publica:** `estado_de(servico: dict, aceitos: set) -> str` e `contar(servicos: list, aceitos: set) -> dict`.

- [x] **Step 1: escrever o teste que falha**

```python
from lib.estado_servico import contar, estado_de


def svc(replicas, falhas=0, nome="a_b", **extra):
    return {"name": nome, "replicas": replicas, "tasks_failed": falhas, **extra}


def test_estados_da_tabela_do_spec():
    assert estado_de(svc("3/3"), set()) == "online"
    assert estado_de(svc("3/3", falhas=2), set()) == "instavel"
    assert estado_de(svc("1/3"), set()) == "parcial"
    assert estado_de(svc("0/1"), set()) == "fora"
    assert estado_de(svc("0/0"), set()) == "proposital"
    assert estado_de(svc("0/1", nome="migrate_job", mode="replicated-job"), set()) == "proposital"
    assert estado_de(svc("0/1", falhas=1, nome="migrate_job", mode="replicated-job"), set()) == "fora"
    assert estado_de(svc("0/1"), {"a_b"}) == "proposital"
    assert estado_de(svc(None), set()) == "sem_dado"
    assert estado_de(svc("3/3"), {"a_b"}) == "online"
    assert estado_de(svc("0/2 (max 1 per node)"), set()) == "fora"


def test_contagem_ignora_lista_invalida_do_coletor():
    assert contar({"status": "n/a"}, set())["base"] == 0


def test_contagem_tira_proposital_e_sem_dado_do_denominador():
    r = contar([svc("3/3"), svc("0/1", nome="x"), svc("0/0", nome="y"), svc(None, nome="z")], set())
    assert (r["online"], r["base"], r["fora"]) == (1, 2, 1)


def test_falhas_desconhecidas_nao_escondem_as_replicas():
    assert estado_de(svc("0/1", falhas=None), set()) == "fora"
    assert estado_de(svc("1/3", falhas=None), set()) == "parcial"
    assert estado_de(svc("3/3", falhas=None), set()) == "online"
    assert estado_de(svc(None, falhas=None), set()) == "sem_dado"
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_estado_servico.py -q`
Esperado: FALHA com `ModuleNotFoundError: lib.estado_servico`

- [x] **Step 3: escrever o mínimo que faz passar**

```python
"""Um estado por serviço: é ele, e não `services_up`, que responde "está online?"."""
import re

from lib.papel import COM_ESTADO

ESTADOS = ("online", "instavel", "parcial", "fora", "proposital", "sem_dado")
NA_BASE = ("online", "instavel", "parcial", "fora")


def _concluiu(servico):
    """Job que terminou. O nome não prova nada: `seed` casaria com `x_seed_api`."""
    if str(servico.get("mode") or "").endswith("-job"):
        return True
    return bool(servico.get("completed_job")) and servico.get("kind") not in COM_ESTADO


def estado_de(servico, aceitos):
    casou = re.match(r"(\d+)/(\d+)", str(servico.get("replicas")))
    if not casou:
        return "sem_dado"
    rodando, desejado = int(casou.group(1)), int(casou.group(2))
    if desejado == 0:
        return "proposital"
    if rodando == 0 and (servico.get("name") in aceitos or None in aceitos):
        return "proposital"
    if rodando == 0 and _concluiu(servico) and servico.get("tasks_failed", 0) == 0:
        return "proposital"
    if rodando == 0:
        return "fora"
    if rodando < desejado:
        return "parcial"
    return "instavel" if servico.get("tasks_failed") else "online"


def contar(servicos, aceitos):
    conta = {e: 0 for e in ESTADOS}
    conta["falhas_desconhecidas"] = 0
    for servico in servicos if isinstance(servicos, list) else []:
        estado = estado_de(servico, aceitos)
        conta[estado] += 1
        if estado in NA_BASE and "tasks_failed" in servico and servico["tasks_failed"] is None:
            conta["falhas_desconhecidas"] += 1
    conta["base"] = sum(conta[e] for e in NA_BASE)
    return conta
```

- [x] **Step 4: rodar o teste e confirmar que passa**

Rode: `.venv/bin/pytest tests/test_estado_servico.py -q`
Esperado: PASSA

### Task 3: Nota geral

O aceite vigente remove o achado da lista, então a nota lê os aceites do relatório, e `nodes_down` vem de `dimensoes`, calculado antes do aceite.

**Arquivos:**
- Alterar: `scripts/lib/nota.py`
- Alterar: `scripts/lib/cobertura.py:125-138`
- Teste: `tests/test_nota_geral.py`

**Depende de:** Task 2

**Contrato que esta task publica:** `nota_geral(alvos: list, aceites: list) -> dict | None`, com `valor`, `faixa`, `parcial`, `parcelas`, `teto`, `online`, `base`.

- [x] **Step 1: escrever o teste que falha**

```python
from lib.nota import nota_geral


def alvo(servicos, dimensoes=None, achados=(), nome="c"):
    return {"nome": nome, "tipo": "docker", "coletado": True, "achados": list(achados),
            "fatos": {"services": servicos}, "dimensoes": dimensoes or {}}


BOM = {"disponibilidade": {"ha_pct": 100}, "seguranca": {"high": 0, "med": 0},
       "higiene": {"pinned_pct": 100, "nonroot_pct": 100, "limits_pct": 100, "healthcheck_pct": 100}}


def test_servico_fora_limita_a_59():
    servicos = [{"name": f"s{i}", "replicas": "1/1"} for i in range(99)]
    servicos.append({"name": "x", "replicas": "0/1"})
    assert nota_geral([alvo(servicos, BOM)], [])["valor"] == 59


def test_no_fora_com_aceite_continua_limitando():
    d = dict(BOM, operacao={"nodes_down": 1})
    assert nota_geral([alvo([{"name": "s", "replicas": "1/1"}], d)], [])["valor"] == 59


def test_parado_com_aceite_vigente_sai_da_conta():
    a = alvo([{"name": "s", "replicas": "1/1"}, {"name": "x", "replicas": "0/1"}], BOM)
    aceites = [{"alvo": "c", "regra": "OPS_SERVICE_STOPPED", "objeto": "x", "vencido": False}]
    r = nota_geral([a], aceites)
    assert (r["online"], r["base"], r["valor"]) == (1, 1, 100)


def test_problema_alto_limita_a_79():
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM,
                         [{"regra": "r", "severidade": "high"}])], [])
    assert r["valor"] == 79 and r["faixa"] == "atencao"


def test_parcela_nao_medida_sai_da_conta():
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}])], [])
    assert r["valor"] == 100 and r["parcial"] is True and r["faixa"] == "atencao"


def test_sem_servico_medido_nao_ha_nota():
    assert nota_geral([alvo([{"name": "s", "replicas": None}])], []) is None


def test_endpoint_fora_conta_como_servico_fora():
    http = {"nome": "h", "tipo": "http", "coletado": True, "fatos": {}, "dimensoes": {},
            "achados": [{"regra": "http_fora_do_ar", "severidade": "critical"}]}
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM), http], [])
    assert r["base"] == 2 and r["valor"] <= 59


def test_endpoint_sem_resposta_conta_como_fora():
    http = {"nome": "h", "tipo": "http", "coletado": True, "fatos": {}, "dimensoes": {}, "achados": []}
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM), http], [])
    assert r["online"] == 1 and r["base"] == 2 and r["valor"] <= 59


def test_aceite_sem_objeto_vale_para_o_alvo_inteiro():
    a = alvo([{"name": "x", "replicas": "0/1"}, {"name": "s", "replicas": "1/1"}], BOM)
    r = nota_geral([a], [{"alvo": "c", "regra": "OPS_SERVICE_STOPPED", "vencido": False}])
    assert r["teto"] is None


def test_trava_de_cobertura_impede_o_verde():
    a = alvo([{"name": "s", "replicas": "1/1"}], BOM)
    a["trava_cobertura"] = True
    assert nota_geral([a], [])["faixa"] == "atencao"
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_nota_geral.py -q`
Esperado: FALHA com `ImportError: nota_geral`

- [x] **Step 3: escrever o mínimo que faz passar**

```python
PESOS = {"online": 70, "estabilidade": 20, "praticas": 10}


def _aceitos(alvo, aceites):
    return {a.get("objeto") for a in aceites
            if a.get("alvo") == alvo.get("nome") and a.get("regra") == "OPS_SERVICE_STOPPED"
            and not a.get("vencido") and not a.get("componente")}


def _conta_do_alvo(alvo, aceites):
    from lib.estado_servico import contar
    if alvo.get("tipo") == "http":
        fatos = alvo.get("fatos") or {}
        if not fatos:
            return {"online": 0, "base": 0, "fora": 0, "parcial": 0, "instavel": 0, "falhas_desconhecidas": 0}
        codigo = fatos.get("codigo")
        fora = codigo is None or codigo >= 500
        return {"online": 0 if fora else 1, "base": 1, "fora": int(fora), "parcial": 0, "instavel": 0,
                "falhas_desconhecidas": 0}
    return contar((alvo.get("fatos") or {}).get("services") or [], _aceitos(alvo, aceites))


def nota_geral(alvos, aceites):
    medidos = [a for a in alvos if a.get("coletado", True)]
    contas = [_conta_do_alvo(a, aceites) for a in medidos]
    base = sum(c["base"] for c in contas)
    if not base:
        return None
    online = sum(c["online"] for c in contas)
    pts = [pontuacoes(a.get("dimensoes") or {}) for a in medidos]
    estab = _media([p["disponibilidade"] for p in pts])
    praticas = _media([v for p in pts for v in (p["seguranca"], p["higiene"])])
    parcelas = {"online": round(100 * online / base), "estabilidade": estab, "praticas": praticas}
    medidas = {k: v for k, v in parcelas.items() if v is not None}
    valor = round(sum(v * PESOS[k] for k, v in medidas.items()) / sum(PESOS[k] for k in medidas))
    achados = [x for a in medidos for x in a.get("achados") or []]
    alto = any(x.get("severidade") in ("high", "critical") for x in achados)
    nos_fora = sum(((a.get("dimensoes") or {}).get("operacao") or {}).get("nodes_down", 0) for a in medidos)
    teto = 100
    if alto or any(c["parcial"] or c["instavel"] for c in contas):
        teto = 79
    if nos_fora or any(c["fora"] for c in contas):
        teto = 59
    valor = min(valor, teto)
    parcial = (len(medidas) < len(PESOS) or any(not c["base"] for c in contas)
               or any(c["falhas_desconhecidas"] for c in contas))
    faixa = "bom" if valor >= 80 else ("atencao" if valor >= 60 else "critico")
    if (parcial or any(a.get("trava_cobertura") for a in medidos)) and faixa == "bom":
        faixa = "atencao"
    return {"valor": valor, "faixa": faixa, "parcial": parcial, "parcelas": parcelas,
            "teto": teto if teto < 100 else None, "online": online, "base": base}
```

Em `pontuacoes`, trate `disponibilidade` vazia como `None` e `seguranca` sem a chave `high` também como `None`. Em `teto_por_cobertura`, grave `alvo["trava_cobertura"] = True` sempre que uma pergunta com limiar que trava ficar sem resposta, mesmo se a saúde não mudar. Na falha de coleta docker, o alvo sem `fatos.services` fica sem base e não pesa na nota.

- [x] **Step 4: rodar o teste e confirmar que passa**

Rode: `.venv/bin/pytest tests/test_nota_geral.py tests/test_nota.py -q`
Esperado: PASSA

### Task 4: Gravar a nota no report.json

**Arquivos:**
- Alterar: `scripts/collect.py`
- Teste: `tests/test_collect_orquestrador.py`

**Depende de:** Task 3

- [x] **Step 1: escrever o teste que falha**

```python
def test_a_nota_entra_no_report_depois_dos_aceites(tmp_path):
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}
    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    assert "nota_geral" in ler_relatorio(tmp_path)
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_collect_orquestrador.py -q`
Esperado: FALHA na chave `nota_geral`

- [x] **Step 3: escrever o mínimo que faz passar**

Depois da chamada a `aplicar_cobertura`, em `main`:

```python
    from lib.nota import nota_geral
    relatorio["nota_geral"] = nota_geral(relatorio["alvos"], relatorio["aceites"])
```

- [x] **Step 4: rodar a suíte inteira e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 5: Base comum dos blocos e CSS

As classes novas usam o prefixo `bl-`, porque `.pn`, `.nm` e `.q` já têm outro sentido no template. Ao portar o CSS do mockup, troque os tokens: `--border-color` vira `--fio`, `--bg-card` vira `--campo`, `--bg-primary` vira `--papel`, `--text-primary` vira `--tinta`, `--text-secondary` vira `--fraco`, `--font-sans` vira `--sans`, `--radius-md` vira `--r2` e `--radius-lg` vira `--r`.

**Arquivos:**
- Criar: `scripts/lib/blocos/__init__.py`
- Criar: `scripts/lib/html_comum.py`
- Alterar: `scripts/build_report.py:36-60`
- Alterar: `assets/report-template/template_v3.html`
- Alterar: `tests/test_template_conhece_o_que_o_relatorio_emite.py:22-46`
- Teste: `tests/test_template_conhece_o_que_o_relatorio_emite.py`

**Depende de:** nada

**Contrato que esta task publica:** `painel(titulo, resumo, corpo, cheio=False) -> str`, `nao_medido(motivo) -> str`, `TONS`, `BLOCOS: dict`, `render_bloco(papel, dados) -> str`.

- [x] **Step 1: escrever o teste que falha**

```python
LIB = RAIZ / "scripts" / "lib"


def test_nenhuma_classe_dos_blocos_fica_sem_regra():
    fontes = list((LIB / "blocos").glob("*.py")) + [LIB / "html_comum.py", LIB / "capa.py"]
    css = _css()
    achadas = set()
    for p in fontes:
        if p.exists():
            texto = p.read_text(encoding="utf-8")
            achadas |= _classes(texto)
            for prefixo in re.findall(r'([\w-]+)-\{(?:tom|nota\["faixa"\])\}', texto):
                sufixos = ("bom", "atencao", "critico") if prefixo == "bl-f" else ("ok", "warn", "crit")
                achadas |= {f"{prefixo}-{t}" for t in sufixos}
    orfas = sorted(c for c in achadas if not re.search(r"[.]" + re.escape(c) + r"(?![\w-])", css))
    assert not orfas, orfas


def test_tokens_do_mockup_nao_vazam_para_o_template():
    assert "--border-color" not in TPL.read_text(encoding="utf-8")
```

- [x] **Step 2: escrever o mínimo que faz passar**

Mova `_e` de `build_report.py` para `html_comum.py` e reimporte-o ali.

```python
# scripts/lib/html_comum.py
import html

TONS = ("ok", "warn", "crit")


def _e(x):
    return html.escape("" if x is None else str(x), quote=True)


def nao_medido(motivo):
    return f'<p class="bl-nm"><b>Não medido.</b> {_e(motivo)}</p>'


def painel(titulo, resumo, corpo, cheio=False):
    classe = "bl-pn bl-cheio" if cheio else "bl-pn"
    return (f'<section class="{classe}"><header><h3>{_e(titulo)}</h3>'
            f'<span>{_e(resumo)}</span></header>{corpo}</section>')
```

```python
# scripts/lib/blocos/__init__.py
from importlib import import_module

from lib.html_comum import _e, painel

BLOCOS = {}


def bloco(papel):
    def registrar(funcao):
        BLOCOS[papel] = funcao
        return funcao
    return registrar


def render_bloco(papel, dados):
    funcao = BLOCOS.get(papel)
    if funcao:
        return funcao(dados)
    linhas = "".join(f"<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>" for k, v in sorted(dados.items()))
    return painel(papel.capitalize(), "dados coletados", f'<table class="bl-tb">{linhas}</table>')


for _modulo in ("fila", "entrada", "banco", "cache", "maquinas", "consumo", "falhas"):
    try:
        import_module(f"lib.blocos.{_modulo}")
    except ModuleNotFoundError:
        pass
```

Quando a Task 6 terminar, remova o `try`. Acrescente ao template `.bl-pn`, `.bl-cheio`, `.bl-tb`, `.bl-nm`, com os tokens convertidos.

- [x] **Step 3: rodar e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 6: Blocos por papel e adaptador de dados

**Arquivos:**
- Criar: `scripts/lib/blocos/fila.py`
- Criar: `scripts/lib/blocos/entrada.py`
- Criar: `scripts/lib/blocos/banco.py`
- Criar: `scripts/lib/blocos/cache.py`
- Criar: `scripts/lib/blocos/maquinas.py`
- Criar: `scripts/lib/blocos/consumo.py`
- Criar: `scripts/lib/blocos/falhas.py`
- Criar: `scripts/lib/dados_blocos.py`
- Alterar: `assets/report-template/template_v3.html`
- Teste: `tests/test_blocos.py`

**Depende de:** Task 5

**Contrato que esta task publica:** `dados_do_papel(papel: str, alvos: list) -> dict`.

- [x] **Step 1: escrever o teste que falha**

```python
import pytest

import lib.blocos as b
from lib.dados_blocos import dados_do_papel


@pytest.mark.parametrize("papel", ["fila", "entrada", "banco", "cache", "maquinas", "consumo", "falhas"])
def test_bloco_sem_dado_diz_nao_medido_e_nao_mostra_zero(papel):
    html = b.render_bloco(papel, {"motivo": "sem exporter"})
    assert "Não medido" in html and ">0<" not in html


def test_fila_parada_vem_primeiro_com_o_saldo():
    html = b.render_bloco("fila", {"filas": [
        {"nome": "ok", "prontas": 1, "consumidores": 2, "entrada": 5, "saida": 5},
        {"nome": "emails", "prontas": 900, "consumidores": 0, "entrada": 3, "saida": 0}]})
    assert html.index("emails") < html.index(">ok<") and "+3/min" in html


def test_papel_sem_bloco_usa_tabela_generica():
    assert 'class="bl-tb"' in b.render_bloco("storage", {"uso": "41%"})


def test_adaptador_junta_as_tres_perguntas_e_converte_para_minuto():
    alvo = {"componentes": [{"nome": "mq", "papel": "fila", "respostas": [
        {"pergunta": "fila.filas", "valor": [{"objeto": "e@/", "nome": "e", "prontas": 9, "consumidores": 0}]},
        {"pergunta": "fila.taxa_entrada_saida", "valor": [{"objeto": "e@/", "entrada": 0.5, "saida": 0.0}]}]}]}
    assert dados_do_papel("fila", [alvo])["filas"] == [
        {"nome": "e", "prontas": 9, "consumidores": 0, "entrada": 30, "saida": 0}]


def test_adaptador_sem_componente_informa_o_motivo():
    assert dados_do_papel("banco", [{"componentes": []}])["motivo"]
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_blocos.py -q`
Esperado: FALHA com `ModuleNotFoundError: lib.dados_blocos`

- [x] **Step 3: escrever o bloco de fila**

```python
# scripts/lib/blocos/fila.py
from lib.blocos import bloco
from lib.html_comum import _e, nao_medido, painel


def _estado(f):
    if f["prontas"] and not f["consumidores"]:
        return "crit", "Parada"
    return ("warn", "Lenta") if f["entrada"] > f["saida"] else ("ok", "Fluindo")


@bloco("fila")
def render(dados):
    filas = dados.get("filas")
    if not filas:
        return painel("Filas", "", nao_medido(dados.get("motivo", "sem fonte")), cheio=True)
    ordem = {"crit": 0, "warn": 1, "ok": 2}
    linhas = []
    for f in sorted(filas, key=lambda x: (ordem[_estado(x)[0]], -x["prontas"], x["nome"])):
        tom, rotulo = _estado(f)
        saldo = f["entrada"] - f["saida"]
        linhas.append(
            f'<div class="bl-q bl-q-{tom}"><div class="bl-qn"><span class="bl-tag-{tom}">{rotulo}</span>'
            f'<b>{_e(f["nome"])}</b><span>{f["consumidores"]} consumidores</span></div>'
            f'<div class="bl-qf"><div class="bl-qv"><span>Entra</span><b>{f["entrada"]}/min</b></div>'
            f'<div class="bl-qnum"><b>{f["prontas"]}</b> na fila</div>'
            f'<div class="bl-qv"><span>Sai</span><b>{f["saida"]}/min</b></div></div>'
            f'<div class="bl-qs"><b class="c-{tom}">{saldo:+d}/min</b></div></div>')
    return painel("Filas", f"{len(filas)} medidas", f'<div class="bl-qs-l">{"".join(linhas)}</div>', cheio=True)
```

- [x] **Step 4: escrever o adaptador**

```python
# scripts/lib/dados_blocos.py
"""Traduz as respostas dos componentes para o formato de cada bloco."""


def _componentes(papel, alvos):
    return [c for a in alvos for c in a.get("componentes") or [] if c.get("papel") == papel]


def _resposta(comp, pergunta):
    for r in comp.get("respostas") or []:
        if r.get("pergunta") == pergunta and not r.get("sem_dados"):
            return r.get("valor")
    return None


def _filas(alvos):
    filas = []
    for comp in _componentes("fila", alvos):
        taxas = {t.get("objeto"): t for t in _resposta(comp, "fila.taxa_entrada_saida") or []}
        for f in _resposta(comp, "fila.filas") or []:
            taxa = taxas.get(f.get("objeto"), {})
            filas.append({"nome": f.get("nome"), "prontas": f.get("prontas") or 0,
                          "consumidores": f.get("consumidores") or 0,
                          "entrada": round((taxa.get("entrada") or 0) * 60),
                          "saida": round((taxa.get("saida") or 0) * 60)})
    return {"filas": filas} if filas else {"motivo": "nenhuma fila respondeu nesta rodada"}


def _simples(papel, campos):
    def montar(alvos):
        itens = []
        for comp in _componentes(papel, alvos):
            item = {"nome": comp.get("nome")}
            item.update({k: _resposta(comp, p) for k, p in campos.items()})
            if any(v is not None for k, v in item.items() if k != "nome"):
                itens.append(item)
        return {"itens": itens} if itens else {"motivo": "sem fonte medida para este tipo"}
    return montar


ADAPTADORES = {
    "fila": _filas,
    "entrada": _simples("entrada", {"volume": "entrada.volume_na_janela",
                                    "status": "entrada.distribuicao_de_status",
                                    "latencia": "entrada.latencia",
                                    "servicos": "entrada.por_servico"}),
    "banco": _simples("banco", {"conexoes": "banco.conexoes", "tamanho": "banco.tamanho"}),
    "cache": _simples("cache", {"memoria": "cache.memoria_usada", "evictions": "cache.evicções",
                                "acerto": "cache.acerto"}),
    "maquinas": _simples("maquina", {"cpu": "maquina.cpu", "memoria": "maquina.memoria",
                                     "disco": "maquina.disco", "dias": "maquina.disco_dias"}),
    "consumo": _simples("app", {"cpu": "app.cpu", "memoria": "app.memoria"}),
}


def dados_do_papel(papel, alvos):
    if papel == "falhas":
        pontos = [p for a in alvos for p in (a.get("fatos") or {}).get("impact_points") or []]
        return {"itens": pontos} if pontos else {"motivo": "nenhum ponto de falha calculado"}
    return ADAPTADORES[papel](alvos)
```

- [x] **Step 5: escrever os outros seis blocos**

Todos seguem este modelo e o desenho de `referencias/mockup-aprovado.html`, com as classes prefixadas por `bl-` e o CSS portado conforme a Task 5.

```python
# scripts/lib/blocos/banco.py
from lib.blocos import bloco
from lib.html_comum import _e, nao_medido, painel


@bloco("banco")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return painel("Bancos de dados", "", nao_medido(dados.get("motivo", "sem fonte")))
    corpo = "".join(f'<div class="bl-db"><b>{_e(i["nome"])}</b><span>{_e(i["conexoes"])} conexões · '
                    f'{_e(i["tamanho"])}</span></div>' for i in itens)
    return painel("Bancos de dados", f"{len(itens)} medidos", corpo)
```

`consumo` ordena por `cpu` e desempata por nome; `falhas` mostra `cenario` e `consequencia`; `maquinas` mostra CPU, memória e disco em cartões; `entrada` mostra a barra de status, a latência e, havendo `servicos`, o top 10; `cache` mostra `acerto` e memória. Valor `None` vira "sem dado", nunca 0.

- [x] **Step 6: rodar os testes e confirmar que passam**

Rode: `.venv/bin/pytest tests/test_blocos.py tests/test_template_conhece_o_que_o_relatorio_emite.py -q`
Esperado: PASSA

### Task 7: Capa completa

**Arquivos:**
- Criar: `scripts/lib/capa.py`
- Alterar: `scripts/lib/historico.py`
- Alterar: `assets/report-template/template_v3.html:893-915`
- Teste: `tests/test_capa.py`

**Depende de:** Task 4, Task 5

**Contrato que esta task publica:** `render_capa(ctx: dict, nota: dict | None, resumo_html: str, faltou: list) -> str`.

- [x] **Step 1: escrever o teste que falha**

```python
from lib.capa import VEREDITOS, render_capa

NOTA = {"valor": 79, "faixa": "atencao", "parcial": False, "online": 64, "base": 67,
        "teto": 79, "parcelas": {}}


def ctx():
    return {"recomendacoes": [{"titulo": "Religar a fila", "porque": "avisos parados", "impacto": "alto"}],
            "historico": {"novos": ["c · r · a"], "resolvidos": ["c · r · b", "c · r · d"], "nota_anterior": 71},
            "tendencias": {"disco": [80.0, 91.0]},
            "certificados": [{"nome": "loja", "dias": 12}]}


def test_capa_tem_tudo_o_que_o_spec_pede():
    html = render_capa(ctx(), NOTA, "<p>Resumo.</p>", ["bancos"])
    for esperado in (">79<", ">64<", VEREDITOS["atencao"], "Resumo.", "Religar a fila",
                     "2 resolvidos", "1 novo", "nota 71 → 79", "polyline", "91%", "12 dias", "Não medido", "bancos"):
        assert esperado in html


def test_sem_nota_a_capa_diz_que_nao_mediu():
    assert "Não medido" in render_capa({}, None, "", [])
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_capa.py -q`
Esperado: FALHA com `ModuleNotFoundError: lib.capa`

- [x] **Step 3: escrever o mínimo que faz passar**

```python
# scripts/lib/capa.py
from lib.html_comum import _e, nao_medido

VEREDITOS = {"bom": "Tudo em ordem nos serviços.",
             "atencao": "Quase tudo no ar, com pontos que pedem atenção.",
             "critico": "Há serviço fora do ar agora."}


def _prioridades(recs):
    linhas = "".join(f'<li><b>{_e(r.get("titulo"))}</b><p>{_e(r.get("porque"))}</p></li>'
                     for r in recs[:5])
    return f'<ol class="bl-prio">{linhas}</ol>' if linhas else ""


def _mudou(h, nota):
    novos, resolvidos = len(h.get("novos") or []), len(h.get("resolvidos") or [])
    if not h:
        return ""
    anterior = h.get("nota_anterior")
    variacao = f' · nota {anterior} → {nota["valor"]}' if anterior is not None else ""
    return (f'<p class="bl-mudou"><b>{resolvidos} resolvidos</b> · '
            f'<b>{novos} {"novo" if novos == 1 else "novos"}</b>{variacao}</p>')


UNIDADE = {"erros": "%", "resposta": " ms", "cpu": "%", "memoria": "%", "disco": "%"}


def linha_tendencia(valores):
    if len(valores) < 2:
        return ""
    alto, baixo = max(valores), min(valores)
    amplitude = (alto - baixo) or 1
    pontos = " ".join(f"{i * 100 / (len(valores) - 1):.1f},{26 - (v - baixo) * 22 / amplitude:.1f}"
                      for i, v in enumerate(valores))
    return (f'<svg class="bl-spark" viewBox="0 0 100 30"><polyline points="{pontos}" '
            f'fill="none" stroke="currentColor" stroke-width="2"/></svg>')


def _tendencias(t):
    itens = "".join(f'<div class="bl-met"><span>{_e(n.capitalize())}</span>'
                    f'<b>{v[-1]:.0f}{UNIDADE[n]}</b>{linha_tendencia(v)}</div>'
                    for n, v in sorted(t.items()) if v)
    return f'<div class="bl-mets">{itens}</div>' if itens else ""


def _certificados(certs):
    linhas = "".join(f'<li>{_e(c.get("nome"))} <b>{_e(c.get("dias"))} dias</b></li>' for c in certs[:3])
    return f'<ul class="bl-cert">{linhas}</ul>' if linhas else ""


def render_capa(ctx, nota, resumo_html, faltou):
    if not nota:
        return f'<header class="bl-hero">{nao_medido("nenhum serviço foi medido nesta rodada")}</header>'
    rotulo = " (parcial)" if nota["parcial"] else ""
    falta = nao_medido(", ".join(faltou)) if faltou else ""
    return (f'<header class="bl-hero bl-f-{nota["faixa"]}"><div><h1>{_e(VEREDITOS[nota["faixa"]])}</h1>'
            f'{resumo_html}</div><div class="bl-hn"><b>{nota["valor"]}</b><span>Nota geral{rotulo}</span></div>'
            f'<div class="bl-hon"><b>{nota["online"]}</b><span>de {nota["base"]} serviços online</span></div>'
            f'</header>{_tendencias(ctx.get("tendencias") or {})}<div class="bl-corpo">{_prioridades(ctx.get("recomendacoes") or [])}'
            f'<aside>{_mudou(ctx.get("historico") or {}, nota)}{_certificados(ctx.get("certificados") or [])}</aside>'
            f'</div>{falta}')
```

Acrescente ao template as classes `bl-hero`, `bl-f-bom`, `bl-f-atencao`, `bl-f-critico`, `bl-hn`, `bl-hon`, `bl-corpo`, `bl-prio`, `bl-mudou`, `bl-cert`, `bl-mets`, `bl-met`, `bl-spark`, `bl-aviso` e `bl-fora`, com o desenho do mockup. Em `historico.comparar`, acrescente ao dicionário devolvido `"nota_anterior": (anterior.get("nota_geral") or {}).get("valor")`, usando o relatório anterior que a função já lê.

- [x] **Step 4: rodar os testes e confirmar que passam**

Rode: `.venv/bin/pytest tests/test_capa.py tests/test_template_conhece_o_que_o_relatorio_emite.py -q`
Esperado: PASSA

### Task 8: Saúde por sistema e rótulos

**Arquivos:**
- Alterar: `scripts/lib/capa.py`
- Alterar: `scripts/lib/alvos.py:18`
- Alterar: `scripts/collect.py`
- Teste: `tests/test_capa.py`

**Depende de:** Task 7, Task 2

**Contrato que esta task publica:** `saude_por_sistema(alvos: list, aceites: list, juntar_online=False, medidas=None) -> str`, com `medidas = {stack: {"disponivel": ..., "resposta": ...}}`.

- [x] **Step 1: escrever o teste que falha**

```python
from lib.alvos import OPCIONAIS
from lib.capa import saude_por_sistema


def alvo_sis():
    return {"nome": "c", "rotulos": {"loja": "Loja virtual"}, "fatos": {"services": [
        {"name": "loja_api", "replicas": "2/2"}, {"name": "loja_web", "replicas": "1/2"},
        {"name": "fila_mq", "replicas": "1/1"}]}}


def test_estado_do_sistema_e_o_pior_dos_servicos_e_usa_o_rotulo():
    html = saude_por_sistema([alvo_sis()], [])
    assert "Loja virtual" in html and "Parcial" in html and "1/2" in html


def test_resposta_e_disponivel_aparecem_ou_ficam_sem_dado():
    html = saude_por_sistema([alvo_sis()], [], medidas={"loja": {"disponivel": 99.5}})
    assert "Disponível" in html and "99.5%" in html and "sem dado" in html


def test_juntar_online_resume_os_saudaveis():
    html = saude_por_sistema([alvo_sis()], [], juntar_online=True)
    assert "fila" not in html and "1 sistema online" in html


def test_rotulos_e_campo_aceito_no_alvo():
    assert "rotulos" in OPCIONAIS["docker"]
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_capa.py -q`
Esperado: FALHA com `ImportError: saude_por_sistema`

- [x] **Step 3: escrever o mínimo que faz passar**

```python
ORDEM_ESTADO = ("fora", "instavel", "parcial", "sem_dado", "online", "proposital")
ROTULO_ESTADO = {"fora": "Fora do ar", "instavel": "Instável", "parcial": "Parcial",
                 "sem_dado": "Sem dado", "online": "Online", "proposital": "Parado de propósito"}


def saude_por_sistema(alvos, aceites, juntar_online=False, medidas=None):
    from lib.estado_servico import estado_de
    from lib.nota import _aceitos
    from lib.stacks import stack_of
    sistemas = {}
    for alvo in alvos:
        servicos = (alvo.get("fatos") or {}).get("services")
        if not isinstance(servicos, list):
            continue
        aceitos, rotulos = _aceitos(alvo, aceites), alvo.get("rotulos") or {}
        for s in servicos:
            pilha = stack_of(s.get("name"))
            sistemas.setdefault(rotulos.get(pilha, pilha), []).append(
                (estado_de(s, aceitos), s.get("replicas"), pilha))
    linhas, online, medidas = [], 0, medidas or {}
    for nome in sorted(sistemas):
        pior = min((e for e, _, _ in sistemas[nome]), key=ORDEM_ESTADO.index)
        if juntar_online and pior == "online":
            online += 1
            continue
        reps = ", ".join(str(r) for e, r, _ in sistemas[nome] if e == pior)
        m = medidas.get(sistemas[nome][0][2], {})
        disp = f'{m["disponivel"]}%' if m.get("disponivel") is not None else "sem dado"
        resp = f'{m["resposta"]} ms' if m.get("resposta") is not None else "sem dado"
        linhas.append(f'<tr><td>{_e(nome)}</td><td>{_e(ROTULO_ESTADO[pior])}</td><td>{_e(reps)}</td>'
                      f'<td>{_e(disp)}</td><td>{_e(resp)}</td></tr>')
    if online:
        linhas.append(f'<tr><td colspan="5">{online} sistema{"s" if online > 1 else ""} online</td></tr>')
    return ('<table class="bl-tb"><tr><th>Sistema</th><th>Estado</th><th>Réplicas</th><th>Disponível</th><th>Resposta</th></tr>'
            + "".join(linhas) + "</table>")
```

Em `OPCIONAIS["docker"]`, acrescente `"rotulos"`. Em `coletar_alvo`, copie `alvo.get("rotulos")` para `registro["rotulos"]`.

- [x] **Step 4: rodar a suíte e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 9: Reestruturar o relatório

Troca as faixas e seções atuais pelas cinco partes do spec.

**Arquivos:**
- Criar: `scripts/lib/orcamento_paginas.py`
- Alterar: `tests/test_template_conhece_o_que_o_relatorio_emite.py`
- Alterar: `scripts/build_report.py:1902-2010`
- Alterar: `scripts/build_report.py:2096-2110`
- Alterar: `scripts/build_report.py:2161-2230`
- Alterar: `scripts/build_report.py:2268-2395`
- Alterar: `assets/report-template/template_v3.html:893-915`
- Alterar: `tests/test_build_report_v3.py`
- Alterar: `tests/test_build_report.py`
- Alterar: `tests/test_build_report_insights.py`
- Alterar: `tests/test_dizer_uma_vez.py`
- Alterar: `tests/test_sumario_bate_com_template.py`
- Teste: `tests/test_estrutura_relatorio.py`

**Depende de:** Task 6, Task 7, Task 8

**Contrato que esta task publica:** `cortes(contagens: dict) -> dict`, `SEM_CORTE: dict`.

- [x] **Step 1: escrever o teste que falha**

```python
import build_report as br
from tests.test_build_report_v3 import relatorio


def dados():
    r = relatorio()
    r["nota_geral"] = {"valor": 79, "faixa": "atencao", "parcial": False, "online": 1, "base": 1,
                       "teto": 79, "parcelas": {}}
    return r


def test_as_cinco_partes_aparecem_na_ordem():
    html = br.render_html_v3(dados())
    ids = ["bl-capa", "saude-por-sistema", "detalhes-tecnicos", "problemas", "registro"]
    posicoes = [html.index(f'id="{i}"') for i in ids]
    assert posicoes == sorted(posicoes)


def test_seccoes_antigas_sairam():
    html = br.render_html_v3(dados())
    for fora in ("Agir agora", "Redes, secrets e configs", "Instrumentos", "Topologia"):
        assert fora not in html


def test_toda_recomendacao_aparece_mesmo_sem_regra_correspondente():
    r = dados()
    r["recomendacoes"] = [{"alvo": "cluster", "titulo": "Sem regra", "comando": "ls"},
                          {"alvo": "cluster", "titulo": "Com regra", "regra": "spof", "comando": "pwd"}]
    html = br.render_html_v3(r)
    assert "Sem regra" in html and "Outras recomendações" in html and "pwd" in html


def test_alvo_fora_da_rodada_vira_uma_linha_com_os_nomes():
    r = dados()
    r["alvos"][1]["coletado"] = False
    html = br.render_html_v3(r)
    assert "Fora desta rodada: site" in html and html.count("alvo não confirmado") == 0


def test_riscos_aceitos_e_o_que_falta_declarar_ficam():
    html = br.render_html_v3(dados())
    assert "Riscos aceitos" in html and "O que falta declarar" in html
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_estrutura_relatorio.py -q`
Esperado: FALHA com `ValueError: substring not found`

- [x] **Step 3: escrever o corte**

```python
"""Corte por contagem: determinístico, igual no HTML e no PDF, sem depender de Chromium."""
LINHAS_POR_PAGINA = 26
ORCAMENTO = 20 * LINHAS_POR_PAGINA
SEM_CORTE = {"baixos_em_contagem": False, "afetados_max": 40, "consumo_max": 10,
             "juntar_online": False, "avisos": []}


def _linhas(c, afetados):
    return (c.get("regras", 0) * (6 + afetados // 6) + c.get("sistemas", 0) + 40
            + 3 * c.get("aceites", 0) + c.get("pendencias", 0))


def cortes(c):
    r = dict(SEM_CORTE, avisos=[])
    if _linhas(c, 40) <= ORCAMENTO and c.get("achados", 0) <= 60:
        return r
    r.update(baixos_em_contagem=True, afetados_max=8, consumo_max=4)
    r["avisos"] = ["Achados de baixa gravidade aparecem só em contagem.",
                   "A lista de afetados mostra os 8 primeiros; o completo está no report.json.",
                   "O consumo mostra só os 4 maiores."]
    if c.get("sistemas", 0) > 12:
        r["juntar_online"] = True
        r["avisos"].append("Sistemas online foram agrupados em uma linha.")
    if 3 * c.get("aceites", 0) + c.get("pendencias", 0) > ORCAMENTO / 2:
        r["avisos"].append("O limite de 20 páginas foi ultrapassado para manter riscos aceitos e pendências.")
    return r
```

- [x] **Step 4: reescrever o miolo de render_html_v3**

Remova as montagens `cluster`, `faixa1`, `faixa2`, `faixa3`, `%%INDICE%%`, `%%CARTAO_ESTADO%%` e `%%FORA%%`. No lugar:

```python
    from lib.blocos import render_bloco
    from lib.capa import render_capa, saude_por_sistema
    from lib import orcamento_paginas as op
    from lib.dados_blocos import dados_do_papel, medidas_por_stack

    achados = ctx["achados"]
    corte = op.cortes({"achados": len(achados), "regras": len(_agrupar_por_regra(achados)),
                    "sistemas": _conta_sistemas(alvos), "aceites": len(ctx["aceites"]),
                    "pendencias": len(_mudos_de(alvos))})
    resumo = _rich(ctx["resumo"]) if ctx["resumo"] else ""
    ctx["certificados"] = _certificados_de(alvos)
    ctx["tendencias"] = next((a["tendencias"] for a in sorted(alvos, key=lambda x: x.get("nome") or "")
                              if a.get("tendencias")), {})
    capa = render_capa(ctx, r.get("nota_geral"), resumo, _faltou(alvos))
    avisos = "".join(f'<p class="bl-aviso">{_e(a)}</p>' for a in corte["avisos"])
    regras = {x.get("regra") for x in achados}
    saude = _sec("cluster", "Saúde por sistema", "um sistema por linha",
                 saude_por_sistema(alvos, ctx["aceites"], corte["juntar_online"], medidas_por_stack(alvos)), ident="saude-por-sistema")
    detalhes = _sec("metrica", "Detalhes técnicos", "por tipo de sistema",
                    "".join(render_bloco(p, _dados_com_corte(p, alvos, corte)) for p in
                            ("maquinas", "entrada", "fila", "banco", "cache", "consumo", "falhas")),
                    ident="detalhes-tecnicos")
    problemas = _sec("achado", "Problemas", "cada um explicado uma vez",
                     _problemas(achados, ctx["recomendacoes"], corte)
                     + _outras_recomendacoes(ctx["recomendacoes"], _regras_visiveis(achados, corte)),
                     ident="problemas")
    registro = _sec("aceito", "Registro", "riscos aceitos e o que falta declarar",
                    "<h3>Riscos aceitos</h3>" + _aceites_novo(ctx["aceites"])
                    + "<h3>O que falta declarar</h3>" + _pendencias_novo(alvos), ident="registro")
    repl = {"%%TITLE%%": _e(titulo), "%%FONTES%%": _fontes(),
            "%%CAPA%%": f'<div id="bl-capa">{capa}</div>{avisos}{_fora_da_rodada(alvos)}',
            "%%CORPO%%": saude + detalhes + problemas + registro}
```

Crie os auxiliares:

```python
def _outras_recomendacoes(recomendacoes, regras):
    soltas = [r for r in recomendacoes if r.get("regra") not in regras]
    if not soltas:
        return ""
    return "<h3>Outras recomendações</h3>" + _recomendacoes_novo(soltas)


def _fora_da_rodada(alvos):
    nomes = [a["nome"] for a in alvos if a.get("coletado") is False]
    return f'<p class="bl-fora">Fora desta rodada: {_e(", ".join(nomes))}</p>' if nomes else ""


def _regras_visiveis(achados, corte):
    return {x.get("regra") for x in achados
            if not (corte["baixos_em_contagem"] and x.get("severidade") in ("low", "info"))}


def _problemas(achados, recomendacoes, corte):
    baixos, corpo = [], ""
    for regra, itens in _agrupar_por_regra(achados):
        if corte["baixos_em_contagem"] and itens[0].get("severidade") in ("low", "info"):
            baixos.append((regra, len(itens)))
            continue
        recs = [r for r in recomendacoes if r.get("regra") == regra]
        corpo += _achado_bloco(regra, itens, completo=False, limite=corte["afetados_max"], recomendacoes=recs)
    if baixos:
        corpo += "<ul>" + "".join(f"<li>{_e(rule_meta(r).get('label', r))}: {n}</li>" for r, n in baixos) + "</ul>"
    return corpo


def _dados_com_corte(papel, alvos, corte):
    from lib.dados_blocos import dados_do_papel
    dados = dados_do_papel(papel, alvos)
    if papel == "consumo" and dados.get("itens"):
        ordem = sorted(dados["itens"], key=lambda i: (-(i.get("cpu") or 0), i.get("nome") or ""))
        dados["itens"] = ordem[:corte["consumo_max"]]
    return dados


def _faltou(alvos):
    return sorted({m.get("componente") for a in alvos
                   for m in (a.get("cobertura") or {}).get("mudos") or [] if m.get("componente")})[:3]
```

`_achado_bloco` ganha `limite` e `recomendacoes`, repassa `limite` a `_ocorrencias` e imprime o comando de cada recomendação. Em `_ocorrencias`, passe `limite` também a `_lista_de_nomes`, que hoje usa `TETO_DE_NOMES`, porque as regras de maior volume caem nesse caminho. Em `_pendencias_novo`, ignore alvos com `coletado is False`. No template, troque o conteúdo de `.wrap` por `%%CAPA%%` e `%%CORPO%%`. Implemente `_conta_sistemas`, `_mudos_de` e `_certificados_de` com os dados de `fatos.services`, `cobertura.mudos` e `fatos.certificado`.

- [x] **Step 5: atualizar os testes que descrevem a estrutura antiga**

Liste-os e reescreva cada asserção para o novo lugar da informação, sem apagar o que ela protege:

```bash
grep -n "Agir agora\|Cluster\|Programar\|Registrar\|Instrumentos\|Pontos positivos\|Por aplicação\|Topologia\|Redes, secrets\|faixa-1\|Nós e capacidade" tests/*.py
```

Inverta `test_nao_existe_nota_unica_da_infraestrutura` para exigir a nota quando `nota_geral` existe. Remova as funções do v3 que ficarem sem uso, porque `test_nenhuma_funcao_do_v3_fica_inalcancavel` as acusa, e acrescente `medidas_por_stack` a `dados_blocos.py`:

```python
def medidas_por_stack(alvos):
    from lib.stacks import stack_of
    medidas = {}
    for comp in _componentes("app", alvos):
        valor = _resposta(comp, "app.disponibilidade_30d")
        if valor is not None:
            atual = medidas.setdefault(stack_of(comp.get("nome")), {})
            atual["disponivel"] = min(valor, atual.get("disponivel", 100))
    for comp in _componentes("entrada", alvos):
        for item in _resposta(comp, "entrada.por_servico") or []:
            backend = str(item.get("nome") or "").split("@")[0]
            if item.get("resposta") is not None:
                medidas.setdefault(stack_of(backend), {})["resposta"] = item["resposta"]
    return medidas
```

- [x] **Step 6: rodar a suíte e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 10: Corte por orçamento e limite de páginas

**Arquivos:**
- Criar: `tests/fixtures/relatorio_grande.py`
- Teste: `tests/test_limite_de_paginas.py`

**Depende de:** Task 9

- [x] **Step 1: escrever o teste que falha**

```python
import re

import pytest

import build_report as br
from lib import orcamento_paginas as op
from tests.fixtures.relatorio_grande import relatorio_grande

chromium = pytest.mark.skipif(not br.find_chromium(), reason="Chromium ausente: limite não verificado")


def paginas(caminho):
    return len(re.findall(rb"/Type\s*/Page[^s]", open(caminho, "rb").read()))


def test_relatorio_pequeno_nao_corta():
    assert op.cortes({"achados": 10, "regras": 3, "sistemas": 5})["avisos"] == []


def test_cada_corte_tem_o_proprio_aviso():
    r = op.cortes({"achados": 204, "regras": 10, "sistemas": 30})
    assert r["afetados_max"] == 8 and r["juntar_online"] and len(r["avisos"]) >= 3


def test_registro_grande_avisa_que_o_limite_cedeu():
    r = op.cortes({"achados": 1, "regras": 1, "sistemas": 1, "aceites": 400})
    assert any("limite" in a for a in r["avisos"])


@chromium
def test_sem_corte_a_fixture_estoura(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "cortes", lambda c: dict(op.SEM_CORTE))
    assert paginas(br.build(relatorio_grande(), str(tmp_path), formato="html+pdf")["pdf"]) > 21


@chromium
def test_relatorio_de_57_servicos_tem_no_maximo_21_paginas(tmp_path):
    n = paginas(br.build(relatorio_grande(), str(tmp_path), formato="html+pdf")["pdf"])
    assert 0 < n <= 21
```

- [x] **Step 2: escrever a fixture no tamanho real**

Monte-a com o formato de uma rodada grande, com números fictícios: 60 serviços em 12 stacks, 4 nós, 10 pontos de impacto, 8 recomendações e os 216 achados com as severidades de `scripts/lib/regras.py`, com detalhe idêntico nas regras de maior volume. Depois de `montar_contexto`, cada achado recebe `como_resolver` por `remediacao.para`, como no relatório real.

```python
from lib.regras import REGRAS


def relatorio_grande():
    servicos = [{"name": f"stack{i % 12}_svc{i}", "replicas": "1/1", "tasks_failed": 0, "image": "img", "kind": "app"}
                for i in range(60)]
    contagem = {"SEC_USER_ROOT": 70, "OPS_NO_HEALTHCHECK": 58, "OPS_NO_LIMITS": 40, "SEC_IMAGE_UNPINNED": 24,
                "OPS_JOB_COMPLETED": 8, "OPS_TASK_FAILING": 7, "SEC_DOCKER_SOCK_EXPECTED": 5, "OPS_ENGINE_DRIFT": 1}
    achados = [{"regra": regra, "objeto": f"stack{i % 12}_svc{i % 60}", "alvo": "aurora",
                "severidade": REGRAS[regra]["severidade_padrao"],
                "detalhe": "detalhe igual na regra" if n > 20 else f"detalhe da ocorrência {i}"}
               for regra, n in contagem.items() for i in range(n)]
    achados += [{"regra": "fila_sem_consumidor", "objeto": f"f{i}@/", "alvo": "aurora",
                 "severidade": "high", "detalhe": "parada"} for i in range(3)]
    componentes = [{"nome": s["name"], "papel": "app", "respostas": [
        {"pergunta": "app.cpu", "valor": 1.2, "fonte": "promql:cadvisor"},
        {"pergunta": "app.memoria", "valor": 2.1e8, "fonte": "promql:cadvisor"}], "achados": []} for s in servicos]
    fatos = {"services": servicos, "nodes": [{"hostname": f"n{i}", "role": "worker", "state": "ready"} for i in range(4)],
             "impact_points": [{"cenario": f"Se o ponto {i} cair", "consequencia": "aplicações param",
                                "impacto": "alto", "esforco": "alto", "alvos": []} for i in range(10)]}
    alvo = {"nome": "aurora", "tipo": "docker", "onde": "context: aurora", "saude": "🟡", "coletado": True,
            "dimensoes": {}, "fatos": fatos, "componentes": componentes, "achados": achados,
            "analise": "", "nao_coletado": []}
    recs = [{"alvo": "aurora", "titulo": f"Recomendação {i}", "porque": "motivo", "comando": "docker ps",
             "impacto": "alto", "esforco": "baixo"} for i in range(8)]
    return {"schema_version": 3, "generated_at": "2026-11-01T10:00:00Z", "alvos": [alvo], "inventario": [],
            "aceites": [], "historico": {"vs": "x", "novos": [], "resolvidos": []}, "resumo": "Resumo.",
            "fortes": [], "fracos": [], "recomendacoes": recs,
            "nota_geral": {"valor": 79, "faixa": "atencao", "parcial": False, "online": 57, "base": 57,
                           "teto": 79, "parcelas": {}}}
```

- [x] **Step 3: rodar e calibrar**

Rode: `.venv/bin/pytest tests/test_limite_de_paginas.py -q -rs`
Esperado: PASSA, com o teste "sem corte" acima de 21 e o teste principal até 21. Se passar de 21, reduza primeiro `afetados_max` para 5 e depois mostre a ficha de remediação só em problemas médios ou altos. Nunca corte riscos aceitos nem o que falta declarar.

### Task 11: Perguntas opcionais na cobertura

Sem isto, cada pergunta nova sem fonte derrubaria a cobertura.

**Arquivos:**
- Alterar: `scripts/lib/perguntas.py:21`
- Alterar: `scripts/lib/cobertura.py:61-85`
- Teste: `tests/test_cobertura.py`

**Depende de:** nada

**Contrato que esta task publica:** `_p(..., opcional=False)`.

- [x] **Step 1: escrever o teste que falha**

```python
def test_pergunta_opcional_sem_resposta_nao_derruba_a_cobertura(monkeypatch):
    from lib import cobertura, perguntas
    monkeypatch.setitem(perguntas.PERGUNTAS, "cache.memoria_usada",
                        dict(perguntas.PERGUNTAS["cache.memoria_usada"], opcional=True))
    alvo = {"componentes": [{"nome": "r", "papel": "cache", "papel_origem": "declarado", "respostas": []}]}
    r = cobertura.medir(alvo)
    assert "cache.memoria_usada" not in [m["pergunta"] for m in r["mudos"]]
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_cobertura.py -q`
Esperado: FALHA porque a pergunta aparece em `mudos`

- [x] **Step 3: escrever o mínimo que faz passar**

```python
def _p(id, papel, titulo, forma, unidade=None, limiar=None, desempate=None, faixa=None, opcional=False):
    PERGUNTAS[id] = {"id": id, "papel": papel, "titulo": titulo, "forma": forma,
                     "unidade": unidade, "limiar": limiar, "desempate": desempate,
                     "faixa": faixa, "opcional": opcional}
    ORDEM.setdefault(papel, []).append(id)
    return id
```

Em `medir`, depois de buscar `resposta`:

```python
            if pergunta.get("opcional") and not (resposta is not None and _respondeu(resposta, pergunta)):
                perguntadas -= 1
                continue
```

- [x] **Step 4: rodar a suíte e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 12: Ligar o cAdvisor conforme o spike

**Arquivos:**
- Alterar: `references/metricas/cadvisor.toml`
- Teste: `tests/test_seletor_por_componente.py`

**Depende de:** Task 1

- [x] **Step 1: escrever o teste com os valores reais do spike**

Reproduza o caso: use os formatos de etiqueta registrados em `spike-fontes.md`, com nomes fictícios.

```python
def test_componente_casa_com_o_formato_de_etiqueta_do_spike():
    from lib.identificacao import casar_valor
    assert casar_valor("loja_api", ["loja_api.1.abc"]) == "loja_api.1.abc"
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_seletor_por_componente.py -q`
Esperado: FALHA reproduzindo as respostas vazias. Se o spike mostrar que a causa é a etiqueta não publicada pelo cAdvisor, remova este teste, registre em "Ajustes durante a execução" e deixe o motivo aparecer em "O que falta declarar".

- [x] **Step 3: escrever o mínimo que faz passar**

Ajuste só a etiqueta em `cadvisor.toml` se o nome real for outro. Se o valor tiver sufixo, crie `casar_valor` em `scripts/lib/identificacao.py` e chame-a dentro de `casar_valor_da_etiqueta`, para a correção valer na coleta:

```python
def casar_valor(nome, valores):
    for valor in sorted(valores):
        if valor == nome or valor.startswith(f"{nome}."):
            return valor
    return None
```

- [x] **Step 4: rodar a suíte e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 13: Sites e serviços web

Inclua a pergunta nova nas listas fixas dos testes indicados, sem relaxar as asserções.

**Arquivos:**
- Alterar: `references/metricas/traefik.toml`
- Alterar: `scripts/lib/perguntas.py:29`
- Alterar: `scripts/lib/blocos/entrada.py`
- Alterar: `tests/test_perguntas.py`
- Alterar: `tests/test_perguntas_fila.py`
- Alterar: `tests/test_perguntas_novos_papeis.py`
- Alterar: `tests/test_collect_perguntas.py`
- Alterar: `tests/test_responder_em_producao.py`
- Alterar: `tests/test_ciclo_ponta_a_ponta.py`
- Teste: `tests/test_catalogo.py`

**Depende de:** Task 1, Task 6, Task 11

- [x] **Step 1: escrever o teste que falha**

```python
def test_familia_do_traefik_carrega_com_a_lista_por_servico():
    from lib.catalogo import familias as carregar
    from lib.perguntas import PERGUNTAS
    por_nome = {f["familia"]: f for f in carregar()}
    ids = [p["id"] for p in por_nome["traefik"]["pergunta"]]
    assert "entrada.por_servico" in ids and PERGUNTAS["entrada.por_servico"]["opcional"]


def test_top_10_soma_quem_tem_erro():
    from lib.blocos.entrada import selecionar
    itens = [{"nome": f"s{i:02}", "acessos": 100 - i, "erros": 0} for i in range(12)]
    itens.append({"nome": "z", "acessos": 1, "erros": 3})
    nomes = [i["nome"] for i in selecionar(itens)]
    assert len(nomes) == 11 and "z" in nomes
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_catalogo.py -q`
Esperado: FALHA com `AssertionError` em `entrada.por_servico`

- [x] **Step 3: escrever o mínimo que faz passar**

```python
_p("entrada.por_servico", "entrada", "Acessos por serviço web", "lista", desempate="nome", opcional=True)
```

```toml
[[pergunta]]
id = "entrada.por_servico"
chave = "service"
ordenar_por = "acessos"
desempate = "nome"
[[pergunta.campo]]
nome = "acessos"
query = 'sum by (service) (increase(traefik_service_requests_total{%SELETOR%}[%JANELA%]))'
[[pergunta.campo]]
nome = "erros"
query = 'sum by (service) (increase(traefik_service_requests_total{code=~"5..",%SELETOR%}[%JANELA%]))'
[[pergunta.campo]]
nome = "resposta"
query = '1000 * histogram_quantile(0.95, sum by (le, service) (rate(traefik_service_request_duration_seconds_bucket{%SELETOR%}[%JANELA%])))'
```

```python
def selecionar(itens):
    ordem = sorted(itens, key=lambda i: (-(i.get("acessos") or 0), i.get("nome") or ""))
    topo = ordem[:10]
    return topo + [i for i in ordem[10:] if i.get("erros")]
```

Confira a forma exata de `pergunta.campo` em `references/metricas/rabbitmq-prometheus.toml` e copie-a. Se o spike confirmar rota, use `router` e o título "Sites". Sem rota, tente ligar o backend ao domínio por `routing_labels` dos serviços; não dando, o bloco se chama "Serviços web".

- [x] **Step 4: rodar a suíte e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 14: Coleta por máquina

Como na Task 13, inclua as perguntas novas nas listas fixas dos testes indicados.

**Arquivos:**
- Criar: `references/metricas/node-exporter.toml`
- Alterar: `scripts/lib/papel.py:12`
- Alterar: `scripts/lib/perguntas.py`
- Alterar: `scripts/collect.py:425-435`
- Alterar: `tests/test_perguntas.py`
- Alterar: `tests/test_perguntas_fila.py`
- Alterar: `tests/test_perguntas_novos_papeis.py`
- Alterar: `tests/test_collect_perguntas.py`
- Alterar: `tests/test_responder_em_producao.py`
- Alterar: `tests/test_ciclo_ponta_a_ponta.py`
- Teste: `tests/test_coleta_por_maquina.py`

**Depende de:** Task 1, Task 11

**Contrato que esta task publica:** `componentes_de_maquina(alvo: dict, fatos: dict) -> list`.

- [x] **Step 1: escrever o teste que falha**

```python
from collect import componentes_de_maquina


def test_cada_no_vira_componente_com_a_fonte_do_alvo():
    alvo = {"metricas_url": "http://p"}
    assert componentes_de_maquina(alvo, {"nodes": [{"hostname": "db-1"}]}) == [
        {"nome": "db-1", "papel": "maquina", "papel_origem": "declarado",
         "metricas_url": "http://p", "respostas": [], "achados": []}]


def test_sem_fonte_nao_cria_componente():
    assert componentes_de_maquina({}, {"nodes": [{"hostname": "db-1"}]}) == []


def test_familia_carrega():
    from lib.catalogo import familias as carregar
    assert "node-exporter" in [f["familia"] for f in carregar()]
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_coleta_por_maquina.py -q`
Esperado: FALHA com `ImportError`

- [x] **Step 3: escrever o mínimo que faz passar**

```python
def componentes_de_maquina(alvo, fatos):
    url, nos = alvo.get("metricas_url"), fatos.get("nodes")
    if not url or not isinstance(nos, list):
        return []
    return [{"nome": n.get("hostname"), "papel": "maquina", "papel_origem": "declarado",
             "metricas_url": url, "respostas": [], "achados": []}
            for n in nos if isinstance(n, dict) and n.get("hostname")]
```

Chame-a em `coletar_alvo` antes de `identificar`, somando à lista de componentes. Acrescente `"maquina"` a `PAPEIS`, e em `perguntas.py`:

```python
_p("maquina.cpu", "maquina", "CPU", "escalar", unidade="%", opcional=True)
_p("maquina.memoria", "maquina", "Memória", "escalar", unidade="%", opcional=True)
_p("maquina.disco", "maquina", "Disco", "escalar", unidade="%", opcional=True)
```

```toml
familia = "node-exporter"
prioridade = 50
papel = "maquina"
identifica_papel = false

[identificacao]
metrica_presente = "node_cpu_seconds_total"

[seletor]
etiqueta = "instance"

[[pergunta]]
id = "maquina.cpu"
query = '100 - avg(rate(node_cpu_seconds_total{mode="idle",%SELETOR%}[%JANELA%])) * 100'
valor = "decimal"

[[pergunta]]
id = "maquina.memoria"
query = '100 * (1 - node_memory_MemAvailable_bytes{%SELETOR%} / node_memory_MemTotal_bytes{%SELETOR%})'
valor = "decimal"

[[pergunta]]
id = "maquina.disco"
query = '100 * (1 - node_filesystem_avail_bytes{mountpoint="/",%SELETOR%} / node_filesystem_size_bytes{mountpoint="/",%SELETOR%})'
valor = "decimal"
```

Se o spike mostrar `instance` diferente do hostname, use a etiqueta `nodename` por `node_uname_info`, ou registre em "Ajustes durante a execução" e deixe como não medido. Um spike sem `node_` encerra esta task: nenhum nó recebe perguntas, e o bloco diz não medido.

- [x] **Step 4: rodar a suíte e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 15: Acerto de cache, previsão de disco e 30 dias

Previsão usa `deriv`, a mesma regressão linear de `predict_linear`, porque responde "em quantos dias enche" sem fixar um horizonte.

**Arquivos:**
- Alterar: `references/metricas/redis-exporter.toml`
- Alterar: `references/metricas/node-exporter.toml`
- Alterar: `references/metricas/cadvisor.toml`
- Alterar: `scripts/lib/perguntas.py:94`
- Alterar: `tests/test_perguntas.py`
- Alterar: `tests/test_perguntas_fila.py`
- Alterar: `tests/test_perguntas_novos_papeis.py`
- Alterar: `tests/test_collect_perguntas.py`
- Alterar: `tests/test_responder_em_producao.py`
- Alterar: `tests/test_ciclo_ponta_a_ponta.py`
- Teste: `tests/test_perguntas_novos_papeis.py`

**Depende de:** Task 14

- [x] **Step 1: escrever o teste que falha**

```python
def test_perguntas_novas_sao_opcionais():
    from lib.perguntas import PERGUNTAS
    for id_ in ("cache.acerto", "maquina.disco_dias", "app.disponibilidade_30d"):
        assert PERGUNTAS[id_]["forma"] == "escalar" and PERGUNTAS[id_]["opcional"]
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_perguntas_novos_papeis.py -q`
Esperado: FALHA com `KeyError`

- [x] **Step 3: escrever o mínimo que faz passar**

```python
_p("cache.acerto", "cache", "Taxa de acerto", "escalar", unidade="%", opcional=True)
_p("maquina.disco_dias", "maquina", "Dias até encher o disco", "escalar", unidade="dias", opcional=True)
_p("app.disponibilidade_30d", "app", "Disponibilidade em 30 dias", "escalar", unidade="%", opcional=True)
```

```toml
# redis-exporter.toml
[[pergunta]]
id = "cache.acerto"
query = '100 * sum(rate(redis_keyspace_hits_total{%SELETOR%}[%JANELA%])) / (sum(rate(redis_keyspace_hits_total{%SELETOR%}[%JANELA%])) + sum(rate(redis_keyspace_misses_total{%SELETOR%}[%JANELA%])))'
valor = "decimal"
```

```toml
# node-exporter.toml
[[pergunta]]
id = "maquina.disco_dias"
query = 'node_filesystem_avail_bytes{mountpoint="/",%SELETOR%} / (-deriv(node_filesystem_avail_bytes{mountpoint="/",%SELETOR%}[7d]) * 86400)'
valor = "decimal"
```

```toml
# cadvisor.toml: só com a série confirmada pelo spike
[[pergunta]]
id = "app.disponibilidade_30d"
query = '100 * avg_over_time((count(container_last_seen{%SELETOR%}) > bool 0)[30d:1h])'
valor = "decimal"
```

Atualize o comentário das linhas 94 a 99 de `perguntas.py` e o de `redis-exporter.toml`, inclua as perguntas nas listas fixas dos testes e leia `app.disponibilidade_30d` por `medidas_por_stack`. `disco_dias` negativo vira "estável". Se a retenção do spike for menor que 30 dias, troque `30d` pela retenção e mude o título da pergunta e do cabeçalho "Disponível" para o período real. Sem série confiável, não registre a query: a coluna fica "sem dado".

- [x] **Step 4: rodar a suíte e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 16: Tendências por período

**Arquivos:**
- Criar: `scripts/lib/tendencias.py`
- Alterar: `scripts/lib/adaptadores/promql.py:54`
- Alterar: `scripts/collect.py`
- Teste: `tests/test_tendencias.py`

**Depende de:** Task 7

**Contrato que esta task publica:** `serie(base, query, fim, timeout, horas=24, passo=3600) -> list | None`, `coletar_tendencias(alvo: dict, at: str, timeout: int) -> dict`.

- [x] **Step 1: escrever o teste que falha**

```python
import math

from lib import tendencias
from lib.adaptadores import promql
from lib.capa import linha_tendencia


def test_serie_exige_momento_valido():
    assert promql.serie("http://p", "up", None, 1) is None


def test_serie_devolve_os_valores_e_ignora_nan(monkeypatch):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: {"status": "success", "data": {
        "result": [{"values": [[1, "2"], [2, "NaN"], [3, "3.5"]]}]}})
    assert promql.serie("http://p", "up", 3, 1) == [2.0, 3.5]


def test_falha_da_consulta_devolve_none(monkeypatch):
    monkeypatch.setattr(promql, "_baixar", lambda url, timeout: None)
    assert promql.serie("http://p", "up", 3, 1) is None


def test_alvo_sem_fonte_nao_tem_tendencia():
    assert tendencias.coletar_tendencias({}, "2026-11-01T10:00:00Z", 1) == {}


def test_svg_so_com_dois_pontos():
    assert linha_tendencia([1.0]) == "" and "polyline" in linha_tendencia([1.0, 2.0])
```

- [x] **Step 2: rodar o teste e confirmar que falha**

Rode: `.venv/bin/pytest tests/test_tendencias.py -q`
Esperado: FALHA com `ModuleNotFoundError: lib.tendencias`

- [x] **Step 3: escrever o mínimo que faz passar**

Extraia de `_consultar` a função `_baixar(url, timeout)`, sem mudar o comportamento, e acrescente:

```python
def serie(base, query, fim, timeout, horas=24, passo=3600):
    if not fim:
        return None
    url = (f"{base.rstrip('/')}/api/v1/query_range?query={quote(query)}"
           f"&start={fim - horas * 3600}&end={fim}&step={passo}")
    corpo = _baixar(url, timeout) or {}
    resultado = (corpo.get("data") or {}).get("result") or []
    if corpo.get("status") != "success" or len(resultado) != 1:
        return None
    valores = [float(v) for _, v in resultado[0]["values"]]
    return [v for v in valores if math.isfinite(v)] or None
```

```python
# scripts/lib/tendencias.py
from lib.adaptadores import promql

CONSULTAS = {
    "erros": 'sum(rate(traefik_service_requests_total{code=~"5.."}[1h])) / sum(rate(traefik_service_requests_total[1h])) * 100',
    "resposta": 'histogram_quantile(0.95, sum by (le) (rate(traefik_service_request_duration_seconds_bucket[1h]))) * 1000',
    "cpu": '100 - avg(rate(node_cpu_seconds_total{mode="idle"}[1h])) * 100',
    "memoria": '100 * (1 - sum(node_memory_MemAvailable_bytes) / sum(node_memory_MemTotal_bytes))',
    "disco": 'max(100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}))',
}


def coletar_tendencias(alvo, at, timeout, prazo=None):
    if not alvo.get("metricas_url"):
        return {}
    base = promql.base_de(alvo["metricas_url"])
    fim = promql.momento(at)
    saida = {}
    for nome, query in sorted(CONSULTAS.items()):
        if prazo is not None and prazo.esgotado():
            break
        valores = promql.serie(base, query, fim, timeout)
        if valores:
            saida[nome] = valores
    return saida
```

Em `coletar_alvo`, depois das respostas:

```python
    registro["tendencias"] = coletar_tendencias(alvo, contexto["at"], contexto["timeout"], prazo)
```

A capa já desenha `ctx["tendencias"]` desde a Task 7, e a Task 9 usa o primeiro alvo com série, em ordem de nome. `momento` devolve segundos de época, ou `None` para `--at` inválido.

- [x] **Step 4: rodar a suíte e confirmar que passa**

Rode: `.venv/bin/pytest -q`
Esperado: PASSA

### Task 17: Documentar, validar e publicar localmente

**Arquivos:**
- Alterar: `SKILL.md:126`
- Alterar: `SKILL.md:285`
- Alterar: `SKILL.md:303`
- Alterar: `SKILL.md:342`
- Alterar: `SKILL.md:404`
- Alterar: `scripts/lib/nota.py:8`
- Teste: `tests/test_sumario_bate_com_template.py`

**Depende de:** Task 16

- [x] **Step 1: atualizar a documentação**

Remova a proibição de nota única em `SKILL.md:342`, `:348`, `:404` e `nota.py:8`. Descreva a conta, os tetos, as faixas, o campo `regra` em `:285`, a nova estrutura em `:303` e a consulta por período em `:126`.

- [x] **Step 2: rodar uma coleta real**

Com o acesso aberto e a confirmação do dono, rode:

```bash
S=~/.claude/skills/sw-infra-audit/scripts
cd <pasta do projeto que tem docs/infra/alvos.toml>
python3 $S/collect.py --out docs/infra/<AAAA-MM-DD_HHMM> --at <ISO> --confirmar <alvo>
python3 $S/build_report.py --dir docs/infra/<AAAA-MM-DD_HHMM> --formato html+pdf
```

Esperado: PDF com até 21 páginas. Leia a capa e cada bloco e compare com `referencias/mockup-aprovado.html`.

- [x] **Step 3: rodar tudo e sincronizar**

Rode: `.venv/bin/pytest -q && cd <raiz do repo> && make sync SKILL=sw-infra-audit BUMP=minor`
Esperado: suíte verde e versão 0.19.0. Registre no `CHANGELOG.md` e rode `make check` antes do commit.

## Ajustes durante a execução

- **2026-11-01** — Task 1 concluída sem túnel; ver `referencias/spike-fontes.md`. Task 12 encerrada sem código. Task 13 usa `router` e o domínio de `routing_labels`. Task 14 liga o nó pelo `ContainerID` da task do exporter. Task 15 usa 7 dias e consulta agrupada; banco e cache seguem sem fonte.
- **2026-11-01** — Tasks 2 a 11 concluídas. Validação com rodada real mostrou 43 páginas contra 17 da fixture; filas passam a ter corte, "Por aplicação" saiu e a fixture foi refeita. Rodada real: 21 páginas.
- **2026-11-01** — Task 1 adiada por decisão do dono: o túnel do Prometheus estava fechado. Execução começa pela Task 2; tasks 1 e 12 a 16 ficam para depois.
- **2026-11-01** — Base da revisão final: 4f5e18fbbbc9874517e9a7d0907386d2870def4a
