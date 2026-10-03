# Plano de implementação — Cobertura da medição

[spec.md](spec.md) · seção "Cobertura da medição (revisão de 2026-10-03)"

> **Execução:** implementar task por task. Os steps usam checkbox (`- [x]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** impedir que a auditoria assine 🟢 num cluster que ela não conseguiu medir.

**Arquitetura:** um módulo puro novo (`lib/cobertura.py`) mede quanto das perguntas que a skill
sabe fazer foi de fato respondido, e devolve o teto de saúde que essa medição permite. O
`collect.main` aplica esse teto ao lado do `agravar_saude` que já existe — é lá que `saude` é
escrito. O relatório apenas **narra** o resultado; ele não decide saúde.

**Stack:** Python 3.13, pytest. Interpretador: `~/.claude/skills/sw-infra-audit/.venv/bin/python`.
Todos os comandos deste plano rodam de `~/.claude/skills/sw-infra-audit/`.

**Restrições verificáveis (do spec):**

| Restrição | Como o plano checa |
|---|---|
| nº 6 — `teto(alvo)` dá 🔴 na fixture com limiares respondidos e 🟡 na fixture com `fila.filas` sem resposta; mutar a checagem faz a 2ª voltar a 🟢 | Task 6 (fixture sintética) + Task 8 (mutação) |
| Teto, nunca piso: cobertura nunca produz 🔴 | Task 4, step 1; mutação na Task 8 |
| `0%` ≠ `sem dados` | Task 2, step 5 |
| Lista vazia em pergunta com limiar não conta como resposta | Task 3; mutação na Task 8 |
| `low` não trava o 🟢 | Task 4, step 5; mutação na Task 8 |
| Aceite vigente dispensa a trava | Task 4, step 7; mutação na Task 8 |

**Fora de escopo (do spec):** plano 4 (banco/`sql`), plano 5 (`logql`), e o `exec_cli`, que está
registrado no spec como decisão adiada. Nenhuma task deste plano toca `runner.py` nem a
allowlist do docker.

---

### Task 1: SPIKE: as respostas existem no ponto onde a saúde é escrita?

**Arquivos:**
- Criar: `/tmp/spike_cobertura.py` (descartável — o step 3 apaga)
- Nenhum arquivo do projeto é tocado nesta task

**Depende de:** nada

**Por que é a task 1:** se `componentes[].respostas` não estiver no registro do alvo no momento
em que `agravar_saude` roda, o teto não tem o que medir e **o desenho inteiro muda** — a
cobertura teria de ser calculada antes, dentro do laço de coleta.

- [x] **Step 1: escrever o script de verificação**

Crie `/tmp/spike_cobertura.py`:

```python
import json
import sys

# um report.json real de uma rodada já feita; qualquer um serve
caminho = sys.argv[1]
relatorio = json.load(open(caminho, encoding="utf-8"))

for alvo in relatorio["alvos"]:
    componentes = alvo.get("componentes") or []
    com_resposta = [c for c in componentes if c.get("respostas")]
    print(f'{alvo["nome"]:22} saude={alvo.get("saude")!r:12} '
          f'componentes={len(componentes):3} com_respostas={len(com_resposta):3}')
    for c in com_resposta[:1]:
        print(f'    exemplo: {sorted(c["respostas"][0])}')
```

- [x] **Step 2: rodar contra uma rodada real**

Rode:
```bash
~/.claude/skills/sw-infra-audit/.venv/bin/python /tmp/spike_cobertura.py \
  "$(ls -dt /var/www/ai-marketplace/docs/infra/*/report.json | head -1)"
```

Esperado: pelo menos um alvo com `com_respostas` maior que zero, e o `exemplo` listando as
chaves `['motivo', 'pergunta', 'sem_dados']` (resposta muda) ou `['fonte', 'pergunta', 'valor']`
(resposta boa).

**Deu certo se** as respostas aparecem no registro do alvo. **Se não aparecerem**, pare: o teto
precisa ser calculado dentro do laço de coleta, e as tasks 4 e 5 mudam de lugar — registre isso
em "Ajustes durante a execução" e volte ao spec.

- [x] **Step 3: apagar o script**

```bash
rm /tmp/spike_cobertura.py
```

---

### Task 2: `medir(alvo)`: quanto foi perguntado e quanto foi respondido

**Arquivos:**
- Criar: `scripts/lib/cobertura.py`
- Teste: `tests/test_cobertura.py`

**Depende de:** Task 1

**Contrato que esta task publica:**
`medir(alvo: dict) -> {"perguntadas": int, "respondidas": int, "pct": int | None, "mudos": list[dict]}`

- [x] **Step 1: escrever o teste que falha**

Crie `tests/test_cobertura.py`:

```python
"""A cobertura mede quanto das perguntas que a skill SABE fazer foi respondido.

Papel sem pergunta registrada fica fora do denominador: contá-lo deixaria a cobertura
permanentemente péssima e, portanto, inútil — ninguém olha um número que não se move
quando se conserta o que dá para consertar.
"""
from lib.cobertura import medir


def alvo(componentes):
    return {"nome": "cluster", "saude": "🟢", "achados": [], "componentes": componentes}


def resp(pergunta, valor=None, sem_dados=False, motivo=None):
    r = {"pergunta": pergunta}
    if sem_dados:
        r["sem_dados"] = True
        r["motivo"] = motivo or "a fonte não respondeu"
    else:
        r["valor"] = valor
        r["fonte"] = "promql:teste"
    return r


def test_conta_so_as_perguntas_que_a_skill_sabe_fazer():
    """49 componentes de papel `app` não têm pergunta: não entram no denominador."""
    c = [{"nome": "proxy", "papel": "entrada", "respostas": [resp("entrada.latencia", 12)]},
         {"nome": "app1", "papel": "app", "respostas": []},
         {"nome": "app2", "papel": "app", "respostas": []}]

    m = medir(alvo(c))

    assert m["perguntadas"] == 3, "o papel `entrada` tem 3 perguntas; `app` não tem nenhuma"
    assert m["respondidas"] == 1


def test_sem_dados_nao_conta_como_resposta():
    c = [{"nome": "proxy", "papel": "entrada",
          "respostas": [resp("entrada.latencia", sem_dados=True, motivo="sem fonte")]}]

    m = medir(alvo(c))

    assert m["respondidas"] == 0
    assert m["pct"] == 0


def test_erro_interno_nao_conta_como_resposta():
    r = resp("entrada.latencia", 12)
    r["erro_interno"] = True
    c = [{"nome": "proxy", "papel": "entrada", "respostas": [r]}]

    assert medir(alvo(c))["respondidas"] == 0


def test_lista_vazia_em_pergunta_com_limiar_nao_conta():
    """`fila.filas` devolvida como [] passaria por respondida — e a cobertura diria 100%
    sem nada ter sido medido. É a mesma cegueira por outra porta."""
    c = [{"nome": "broker", "papel": "fila", "respostas": [resp("fila.filas", [])]}]

    assert medir(alvo(c))["respondidas"] == 0


def test_nada_a_perguntar_e_sem_dados_nao_zero_por_cento():
    """Alvo sem componente com pergunta: cobertura indefinida, não 0%. Tratar
    "nada a perguntar" como 0% é a mesma mentira ao contrário."""
    c = [{"nome": "app1", "papel": "app", "respostas": []}]

    m = medir(alvo(c))

    assert m["perguntadas"] == 0
    assert m["pct"] is None, "0% afirmaria que perguntei e não fui respondido"


def test_mudos_trazem_componente_pergunta_e_motivo():
    """Um 🟡 sem nada que o explique inverte o problema. A cobertura carrega o porquê."""
    c = [{"nome": "broker", "papel": "fila",
          "respostas": [resp("fila.filas", sem_dados=True, motivo="senha_env ausente")]}]

    mudos = medir(alvo(c))["mudos"]

    assert {"componente": "broker", "pergunta": "fila.filas",
            "motivo": "senha_env ausente"} in mudos
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.cobertura'`

- [x] **Step 3: escrever o mínimo que faz passar**

Crie `scripts/lib/cobertura.py`:

```python
"""Quanto da medição a auditoria conseguiu fazer — e que teto isso impõe ao veredito.

A skill prega "não consegui ver ≠ está ruim". O inverso — "não consegui ver ≠ está bom" —
é o que este módulo protege: entre 29/09 e 03/10 um cluster passou de 🔴 para 🟢 sem nada ter
melhorado, porque a pergunta que produz o achado não foi respondida e não havia o que agravar.

Funções puras: recebem o registro do alvo e devolvem dado. Quem escreve `saude` é o
`collect.main`, ao lado do `agravar_saude` que já existe.
"""


def _respondeu(resposta, pergunta):
    """A resposta conta como respondida?

    Lista vazia em pergunta COM limiar não conta: `_sem_numero` e `_sem_contadores` devolvem
    a resposta intacta quando `valor` é `[]`, então a fonte responder "nenhum item" marcaria
    100% de cobertura sem nada ter sido medido.
    """
    if resposta.get("sem_dados") or resposta.get("erro_interno"):
        return False
    valor = resposta.get("valor")
    if pergunta.get("limiar") and isinstance(valor, list) and not valor:
        return False
    return True


def medir(alvo):
    """Mede a cobertura de um alvo.

    `perguntadas` conta só o que a skill SABE perguntar para aquele papel. Papel sem pergunta
    registrada (hoje `app`, `banco`, `cache`, `observabilidade`) fica fora do denominador: ele
    é limite da skill, não falha de cobertura, e já é reportado em "O que falta declarar".
    """
    from lib.perguntas import do_papel

    perguntadas = respondidas = 0
    mudos = []
    for componente in alvo.get("componentes") or []:
        catalogo = {p["id"]: p for p in do_papel(componente.get("papel"))}
        if not catalogo:
            continue
        perguntadas += len(catalogo)
        por_id = {r.get("pergunta"): r for r in (componente.get("respostas") or [])}
        for id_pergunta, pergunta in catalogo.items():
            resposta = por_id.get(id_pergunta)
            if resposta is not None and _respondeu(resposta, pergunta):
                respondidas += 1
                continue
            mudos.append({
                "componente": componente.get("nome"),
                "pergunta": id_pergunta,
                "motivo": (resposta or {}).get("motivo") or "a pergunta não foi feita",
            })
    pct = round(100 * respondidas / perguntadas) if perguntadas else None
    return {"perguntadas": perguntadas, "respondidas": respondidas, "pct": pct, "mudos": mudos}
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: `6 passed`

- [x] **Step 5: confirmar que a suíte inteira continua verde**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: `903 passed` (897 de antes + 6 novos)

---

### Task 3: lista vazia em pergunta com limiar vira `sem_dados`

**Arquivos:**
- Alterar: `scripts/collect.py` (função `_sem_contadores`)
- Teste: `tests/test_cobertura.py` (acrescentar)

**Depende de:** Task 2

**Por quê:** a Task 2 faz a *cobertura* ignorar a lista vazia, mas o `report.json` continua
gravando a resposta como boa, com fonte. Quem lê o relatório vê "Filas: fonte admin_http" e
nenhuma linha. O silêncio precisa estar no dado, não só na conta.

- [x] **Step 1: escrever o teste que falha**

Acrescente ao fim de `tests/test_cobertura.py`:

```python
# ------------------------------------------------- a lista vazia no próprio dado
import collect


def test_lista_vazia_com_limiar_vira_sem_dados_no_report():
    """A fonte respondeu "nenhum item". Isso não é uma medida de zero filas paradas —
    é a ausência da medida, e o report.json tem de dizer isso."""
    pergunta = {"id": "fila.filas", "unidade": "mensagens",
                "limiar": {"quando": "consumidores == 0", "regra": "fila_sem_consumidor",
                           "severidade": "high"}}
    resposta = {"pergunta": "fila.filas", "valor": [], "fonte": "admin_http:amqp"}

    saida = collect._sem_contadores(resposta, pergunta.get("limiar"))

    assert saida.get("sem_dados") is True
    assert "nenhum item" in saida.get("motivo", "")


def test_lista_vazia_SEM_limiar_continua_como_resposta():
    """Sem limiar nenhum achado se perdeu: lista vazia ali é uma resposta legítima."""
    resposta = {"pergunta": "entrada.distribuicao_de_status", "valor": [], "fonte": "promql:x"}

    saida = collect._sem_contadores(resposta, None)

    assert not saida.get("sem_dados")
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -k lista_vazia -q`
Esperado: FALHA — `assert None is True`, porque hoje `_sem_contadores` devolve a resposta
intacta quando `valor` é `[]`.

- [x] **Step 3: alterar `_sem_contadores`**

Em `scripts/collect.py`, na função `_sem_contadores`, troque a guarda de entrada:

```python
    valor = resposta.get("valor")
    if not limiar or resposta.get("sem_dados") or not isinstance(valor, list):
        return resposta
    if not valor:
        # A fonte respondeu "nenhum item". Com limiar, isso NÃO é uma medida de zero
        # ocorrências: é a ausência da medida. Deixar passar marcaria 100% de cobertura
        # sem nada ter sido medido, e o achado que o limiar produziria nunca nasceria.
        return {**resposta, "sem_dados": True,
                "motivo": "a fonte não devolveu nenhum item"}
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: `8 passed`

- [x] **Step 5: confirmar que nada mais quebrou**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: `905 passed`. Se algum teste de fila quebrar, leia-o: ele pode estar justamente
afirmando o comportamento antigo — nesse caso, corrija o teste e registre em "Ajustes".

---

### Task 4: `teto_por_cobertura(alvo)`: as quatro guardas

**Arquivos:**
- Alterar: `scripts/lib/cobertura.py`
- Teste: `tests/test_cobertura.py` (acrescentar)

**Depende de:** Task 2

**Contrato que esta task publica:** `teto_por_cobertura(alvo: dict, aceites_vigentes: set) -> None`
(altera `alvo["saude"]` no lugar; nunca a diminui)

- [x] **Step 1: escrever o teste que falha**

Acrescente ao fim de `tests/test_cobertura.py`:

```python
# ------------------------------------------------------- o teto do verde
from lib.cobertura import teto_por_cobertura


def com_limiar_mudo(saude="🟢"):
    """Alvo saudável cujo `fila.filas` (limiar `high`) não foi respondido."""
    a = alvo([{"nome": "broker", "papel": "fila",
               "respostas": [resp("fila.filas", sem_dados=True, motivo="senha ausente")]}])
    a["saude"] = saude
    return a


def test_limiar_sem_resposta_impede_o_verde():
    """Um achado podia ter nascido e não nasceu: não dá para assinar "convergido"."""
    a = com_limiar_mudo()

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🟡"


def test_teto_nunca_vira_vermelho():
    """Cegueira não é prova de que algo está fora do ar."""
    a = com_limiar_mudo()

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] != "🔴"


def test_teto_nunca_desce_um_alvo_ja_vermelho():
    a = com_limiar_mudo(saude="🔴")

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🔴", "é teto, não piso"


def test_limiar_de_severidade_baixa_nao_trava():
    """`_PIOR_ESTADO` ignora `low`: travar o verde por um limiar que o próprio achado não
    travaria seria mais rígido com a ausência do que com o fato."""
    a = alvo([{"nome": "x", "papel": "fila",
               "respostas": [resp("fila.filas", sem_dados=True)]}])
    a["saude"] = "🟢"

    teto_por_cobertura(a, aceites_vigentes=set(), severidade_por_pergunta={"fila.filas": "low"})

    assert a["saude"] == "🟢"


def test_aceite_vigente_dispensa_a_trava():
    """O achado não contaria de qualquer forma: travar por ele cobra duas vezes."""
    a = com_limiar_mudo()

    teto_por_cobertura(a, aceites_vigentes={"fila_sem_consumidor"})

    assert a["saude"] == "🟢"


def test_estado_fora_da_escala_nao_e_tocado():
    """`sem dados` não é um estado bom a ser piorado: é ausência de leitura."""
    a = com_limiar_mudo(saude="sem dados")

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "sem dados"


def test_tudo_respondido_nao_mexe_na_saude():
    a = alvo([{"nome": "broker", "papel": "fila",
               "respostas": [resp("fila.filas", [{"nome": "q", "prontas": 0}]),
                             resp("fila.consumidores_por_fila", [{"nome": "q"}]),
                             resp("fila.taxa_entrada_saida", [{"nome": "q"}])]}])
    a["saude"] = "🟢"

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🟢"
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -k teto -q`
Esperado: FALHA com `ImportError: cannot import name 'teto_por_cobertura'`

- [x] **Step 3: implementar**

Acrescente ao fim de `scripts/lib/cobertura.py`:

```python
# Estados que a cobertura pode impor. Espelha `_PIOR_ESTADO` do collect: `low` e `info` não
# aparecem porque um achado dessa severidade não derrubaria o alvo — e a AUSÊNCIA dele não
# pode ser mais severa que a presença.
_TRAVA = {"critical": "🟡", "high": "🟡", "medium": "🟡"}
_GRAVIDADE = {"🟢": 0, "🟡": 1, "🔴": 2}


def teto_por_cobertura(alvo, aceites_vigentes=(), severidade_por_pergunta=None):
    """Impede o 🟢 quando uma pergunta COM limiar ficou sem resposta.

    Quatro guardas, todas deliberadas:

    1. **Teto, nunca piso.** Só impede o 🟢; nunca produz 🔴 nem desce um alvo já pior.
       Vermelho significa "algo está fora do ar", e não ver não é prova disso.
    2. **Só severidade que trava.** Limiar `low` não derruba um 🟢 que o próprio achado não
       derrubaria.
    3. **Aceite vigente dispensa.** Se a regra daquele limiar já foi aceita, o achado não
       contaria de qualquer forma — travar por ele cobraria duas vezes. Aceite VENCIDO não
       dispensa: ele voltou a contar.
    4. **Estado fora da escala não é tocado.** `sem dados` continua `sem dados`.
    """
    from lib.perguntas import do_papel

    atual = alvo.get("saude")
    if atual not in _GRAVIDADE:                       # guarda 4
        return
    severidade_por_pergunta = severidade_por_pergunta or {}

    for componente in alvo.get("componentes") or []:
        catalogo = {p["id"]: p for p in do_papel(componente.get("papel"))}
        por_id = {r.get("pergunta"): r for r in (componente.get("respostas") or [])}
        for id_pergunta, pergunta in catalogo.items():
            limiar = pergunta.get("limiar")
            if not limiar:
                continue
            resposta = por_id.get(id_pergunta)
            if resposta is not None and _respondeu(resposta, pergunta):
                continue
            if limiar.get("regra") in aceites_vigentes:        # guarda 3
                continue
            severidade = severidade_por_pergunta.get(id_pergunta, limiar.get("severidade"))
            exigido = _TRAVA.get(severidade)                    # guarda 2
            if exigido and _GRAVIDADE[exigido] > _GRAVIDADE[alvo["saude"]]:   # guarda 1
                alvo["saude"] = exigido
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: `15 passed`

- [x] **Step 5: confirmar a suíte**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: `912 passed`

---

### Task 5: ligar no `collect.main`, ao lado do `agravar_saude`

**Arquivos:**
- Alterar: `scripts/collect.py` (laço do `agravar_saude`, por volta da linha 446)
- Teste: `tests/test_cobertura.py` (acrescentar)

**Depende de:** Task 4

- [x] **Step 1: escrever o teste que falha**

Acrescente ao fim de `tests/test_cobertura.py`:

```python
# ------------------------------------------------ o campo chega ao report.json
def test_o_relatorio_carrega_a_cobertura_do_alvo():
    """A cobertura mora em campo próprio, FORA de `dimensoes`: entrar como 5ª dimensão faria
    `nota.py` elegê-la como a dimensão mais fraca e estourar em `ROTULO[pior]` (KeyError)."""
    a = alvo([{"nome": "broker", "papel": "fila",
               "respostas": [resp("fila.filas", sem_dados=True, motivo="senha ausente")]}])
    a["saude"] = "🟢"

    collect.aplicar_cobertura([a], aceites_vigentes=set())

    assert a["saude"] == "🟡"
    assert a["cobertura"]["pct"] == 0
    assert "cobertura" not in a["dimensoes"], "não é dimensão pontuada"
    assert a["cobertura"]["mudos"][0]["motivo"] == "senha ausente"
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -k relatorio_carrega -q`
Esperado: FALHA com `AttributeError: module 'collect' has no attribute 'aplicar_cobertura'`

- [x] **Step 3: escrever a função em `collect.py`**

Acrescente em `scripts/collect.py`, logo depois de `agravar_saude`:

```python
def aplicar_cobertura(alvos, aceites_vigentes):
    """Mede a cobertura de cada alvo e aplica o teto de saúde que ela impõe.

    Roda DEPOIS do `agravar_saude` e depois dos aceites, pelo mesmo motivo que ele: um achado
    aceito não deve deixar o alvo vermelho, e uma regra já aceita não deve travar o verde.
    """
    from lib.cobertura import medir, teto_por_cobertura

    for alvo in alvos:
        alvo["cobertura"] = medir(alvo)
        teto_por_cobertura(alvo, aceites_vigentes=aceites_vigentes)
```

- [x] **Step 4: chamar no `main`**

Em `scripts/collect.py`, no `main`, logo depois do laço que chama `agravar_saude`:

```python
    for registro in relatorio["alvos"]:
        agravar_saude(registro)
    # a cobertura vem depois: o teto do verde não pode ser aplicado antes de os aceites
    # terem tirado de cena as regras que o dono já decidiu aceitar
    aplicar_cobertura(relatorio["alvos"],
                      aceites_vigentes={x.get("regra")
                                        for x in (relatorio.get("aceites") or [])
                                        if not x.get("vencido")})
```

- [x] **Step 5: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: `16 passed`

- [x] **Step 6: confirmar a suíte e uma coleta de verdade**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: `913 passed`

Depois, confirme contra o `report.json` real da rodada de 03/10 (que saiu 🟢 com cobertura 0%):
```bash
"$SKILL/.venv/bin/python" - <<'PY'
import json, os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/sw-infra-audit/scripts"))
import collect
caminho = sys.argv[1] if len(sys.argv) > 1 else os.environ["RODADA"]
r = json.load(open(caminho, encoding="utf-8"))
collect.aplicar_cobertura(r["alvos"], aceites_vigentes=set())
for a in r["alvos"]:
    print(a["nome"], a["saude"], a["cobertura"]["pct"])
PY
```
Esperado: o alvo que tem componente de fila sai **🟡 com cobertura 0%** — antes saía 🟢.
**Este é o defeito que o plano existe para consertar.**

---

### Task 6: fixture sintética e a restrição nº 6

**Arquivos:**
- Criar: `tests/fixtures/cobertura_limiar_respondido.json`
- Criar: `tests/fixtures/cobertura_limiar_mudo.json`
- Teste: `tests/test_cobertura.py` (acrescentar)

**Depende de:** Task 5

**Por que sintética:** os `report.json` de `docs/infra/` são **gitignored** e carregam nomes
reais de cluster e stack. Usá-los como fixture da skill publicada contraria o `CLAUDE.md` e o
commit `a7652b6`, além de tornar o teste irreprodutível em outra máquina.

- [x] **Step 1: criar a fixture com o limiar RESPONDIDO**

Crie `tests/fixtures/cobertura_limiar_respondido.json`:

```json
{
  "nome": "cluster-exemplo",
  "tipo": "docker",
  "onde": "context: exemplo",
  "saude": "🔴",
  "dimensoes": {},
  "achados": [
    {"regra": "fila_sem_consumidor", "severidade": "high", "objeto": "pedidos@/",
     "detalhe": "prontas: 940 · acumuladas: 940", "alvo": "cluster-exemplo",
     "componente": "pilha_fila"}
  ],
  "componentes": [
    {"nome": "pilha_fila", "papel": "fila", "achados": [], "analise": "",
     "respostas": [
       {"pergunta": "fila.filas", "fonte": "admin_http:exemplo",
        "valor": [{"nome": "pedidos", "vhost": "/", "prontas": 940, "consumidores": 0}]},
       {"pergunta": "fila.consumidores_por_fila", "fonte": "admin_http:exemplo",
        "valor": [{"nome": "pedidos", "consumidores": 0}]},
       {"pergunta": "fila.taxa_entrada_saida", "fonte": "admin_http:exemplo",
        "valor": [{"nome": "pedidos", "entrada": 1.0, "saida": 0.0}]}
     ]}
  ]
}
```

- [x] **Step 2: criar a fixture com o limiar MUDO**

Crie `tests/fixtures/cobertura_limiar_mudo.json`:

```json
{
  "nome": "cluster-exemplo",
  "tipo": "docker",
  "onde": "context: exemplo",
  "saude": "🟢",
  "dimensoes": {},
  "achados": [],
  "componentes": [
    {"nome": "pilha_fila", "papel": "fila", "achados": [], "analise": "",
     "respostas": [
       {"pergunta": "fila.filas", "sem_dados": true,
        "motivo": "a variável de ambiente com a senha não está definida"},
       {"pergunta": "fila.consumidores_por_fila", "sem_dados": true,
        "motivo": "a variável de ambiente com a senha não está definida"},
       {"pergunta": "fila.taxa_entrada_saida", "sem_dados": true,
        "motivo": "orçamento do alvo esgotado"}
     ]}
  ]
}
```

- [x] **Step 3: escrever o teste da restrição nº 6**

Acrescente ao fim de `tests/test_cobertura.py`:

```python
# ------------------------------------- restrição verificável nº 6 (do spec)
import json
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _fixture(nome):
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


def test_restricao_6_limiar_respondido_mantem_vermelho():
    a = _fixture("cobertura_limiar_respondido")

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🔴", "o achado existe; a cobertura não mexe num alvo já pior"


def test_restricao_6_limiar_mudo_vira_amarelo_e_nunca_verde():
    a = _fixture("cobertura_limiar_mudo")

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🟡"
    assert a["saude"] != "🟢", "assinar convergido sem ter medido é o defeito que isto conserta"


def test_restricao_6_a_fixture_muda_nao_tem_nome_real():
    """O repositório é público: fixture com nome de cluster real é vazamento."""
    cru = (FIXTURES / "cobertura_limiar_mudo.json").read_text(encoding="utf-8")
    estranhos = usados - NOMES_NEUTROS
        assert not estranhos, f"nome fora do vocabulário neutro: {sorted(estranhos)}"
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: `19 passed`

---

### Task 7: o motivo na capa e em "O que falta declarar"

**Arquivos:**
- Alterar: `scripts/build_report.py` (função `_pendencias_novo`, por volta da linha 1857)
- Alterar: `scripts/build_report.py` (montagem do topo, por volta da linha 1943)
- Teste: `tests/test_cobertura.py` (acrescentar)

**Depende de:** Task 5

**Por quê:** um 🟡 sem nenhum achado que o explique inverte o problema que `agravar_saude`
documenta. Quem lê precisa ver **qual componente**, **qual pergunta** e **qual motivo**.

- [x] **Step 1: escrever o teste que falha**

Acrescente ao fim de `tests/test_cobertura.py`:

```python
# ------------------------------------------------ o relatório explica o amarelo
import build_report


def _relatorio_com_cobertura_baixa():
    a = _fixture("cobertura_limiar_mudo")
    teto_por_cobertura(a, aceites_vigentes=set())
    a["cobertura"] = medir(a)
    a["nao_coletado"] = []
    a["fatos"] = {}
    return {"schema_version": 3, "generated_at": "2026-10-03T09:00:00Z",
            "resumo": "", "fortes": [], "fracos": [], "recomendacoes": [], "aceites": [],
            "historico": None,
            "inventario": [{"nome": a["nome"], "tipo": "docker", "onde": a["onde"],
                            "saude": a["saude"]}],
            "alvos": [a]}


def test_o_relatorio_diz_por_que_a_cobertura_caiu():
    html = build_report.render_html_v3(_relatorio_com_cobertura_baixa())

    assert "pilha_fila" in html, "qual componente"
    assert "fila.filas" in html, "qual pergunta"
    assert "senha não está definida" in html, "qual motivo"
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -k por_que_a_cobertura -q`
Esperado: FALHA — `assert 'fila.filas' in html`

- [x] **Step 3: emitir o bloco em `_pendencias_novo`**

Em `scripts/build_report.py`, dentro de `_pendencias_novo`, logo antes do `return`:

```python
        cobertura = a.get("cobertura") or {}
        if cobertura.get("mudos"):
            linhas_mudas = "".join(
                f'<div class="l"><span>{_e(m["componente"])} · <code>{_e(m["pergunta"])}</code></span>'
                f'<em>{_e(m["motivo"])}</em></div>' for m in cobertura["mudos"])
            linhas.append(
                f'<div class="item crit"><div class="dt">'
                f'<b>{_plural(len(cobertura["mudos"]), "pergunta sem resposta", "perguntas sem resposta")}</b>'
                f'<span class="p">cobertura {cobertura.get("pct")}%</span></div>'
                f'<p>Estas perguntas a skill sabe fazer e não foram respondidas. '
                f'<b>Silêncio não é saúde</b>: enquanto elas não responderem, a auditoria não '
                f'pode assinar que está tudo convergido.</p>{linhas_mudas}</div>')
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: `20 passed`

- [x] **Step 5: confirmar que o HTML real continua íntegro**

Rode:
```bash
./.venv/bin/python scripts/build_report.py \
  --dir "$RODADA" --formato html
```
Esperado: imprime o caminho do HTML, sem traceback. Abra e confirme que o bloco novo aparece
em "O que falta declarar", com as três perguntas de `rabbitmq_rabbitmq` e os motivos.

---

### Task 8: prova por mutação das seis travas

**Arquivos:**
- Criar: `tests/test_cobertura_mutacao.py`

**Depende de:** Task 7

**Por quê:** teste verde não prova que a trava funciona — prova que o teste roda. A mutação
quebra cada guarda de propósito e exige que a suíte caia. Nesta sessão uma mutação sobreviveu
em `lib/triagem.py` porque a `cascata()` não tinha teste; o mesmo pode acontecer aqui.

- [x] **Step 1: escrever o teste de mutação**

Crie `tests/test_cobertura_mutacao.py`:

```python
"""Cada trava da cobertura é quebrada de propósito, e a suíte TEM de cair.

Teste verde não prova que a trava funciona — prova que o teste roda.
"""
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PY = RAIZ / ".venv/bin/python"

MUTACOES = [
    ("teto vira piso",
     "scripts/lib/cobertura.py",
     "if exigido and _GRAVIDADE[exigido] > _GRAVIDADE[alvo[\"saude\"]]:",
     "if exigido:"),
    ("low passa a travar",
     "scripts/lib/cobertura.py",
     '_TRAVA = {"critical": "🟡", "high": "🟡", "medium": "🟡"}',
     '_TRAVA = {"critical": "🟡", "high": "🟡", "medium": "🟡", "low": "🟡"}'),
    ("aceite deixa de dispensar",
     "scripts/lib/cobertura.py",
     'if limiar.get("regra") in aceites_vigentes:',
     "if False:"),
    ("estado fora da escala passa a ser tocado",
     "scripts/lib/cobertura.py",
     "if atual not in _GRAVIDADE:\n        return",
     "if False:\n        return"),
    ("lista vazia volta a contar como resposta",
     "scripts/lib/cobertura.py",
     'if pergunta.get("limiar") and isinstance(valor, list) and not valor:\n        return False',
     "if False:\n        return False"),
    ("denominador zero vira 0%",
     "scripts/lib/cobertura.py",
     'pct = round(100 * respondidas / perguntadas) if perguntadas else None',
     'pct = round(100 * respondidas / perguntadas) if perguntadas else 0'),
]


@pytest.mark.parametrize("nome,arquivo,de,para", MUTACOES, ids=[m[0] for m in MUTACOES])
def test_quebrar_a_trava_derruba_a_suite(nome, arquivo, de, para):
    alvo = RAIZ / arquivo
    original = alvo.read_text(encoding="utf-8")
    assert de in original, f"o marcador da mutação {nome!r} não existe mais em {arquivo}"
    try:
        alvo.write_text(original.replace(de, para, 1), encoding="utf-8")
        r = subprocess.run([str(PY), "-m", "pytest", "tests/test_cobertura.py", "-q"],
                           cwd=RAIZ, capture_output=True, text=True)
        assert r.returncode != 0, f"a mutação {nome!r} SOBREVIVEU — a trava não tem teste"
    finally:
        alvo.write_text(original, encoding="utf-8")
```

- [x] **Step 2: rodar**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura_mutacao.py -q`
Esperado: `6 passed`.

**Se alguma mutação sobreviver**, o teste correspondente em `test_cobertura.py` não está
cobrindo a trava: escreva o teste que falta antes de seguir. Não relaxe a mutação.

- [x] **Step 3: confirmar a suíte inteira**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: `926 passed`

---

### Task 9: SKILL.md e CHANGELOG

**Arquivos:**
- Alterar: `SKILL.md` (seção "Como a saúde é calculada")
- Alterar: `/var/www/ai-marketplace/CHANGELOG.md`

**Depende de:** Task 8

**Por quê:** a `SKILL.md` descreve como a saúde é calculada. Mudar a regra e não mudar o texto é
o defeito que o commit `b2b0cb8` já corrigiu uma vez nesta skill.

- [x] **Step 1: alterar a seção da SKILL.md**

Em `SKILL.md`, na seção "Como a saúde é calculada", acrescente depois do parágrafo existente:

```markdown
**Cobertura da medição.** O verde exige ter medido. Se uma pergunta que produz achado
(a que declara `limiar`) fica sem resposta, um achado podia ter nascido e não nasceu — então o
alvo **não pode** ser 🟢, e sai 🟡 com o motivo por extenso em "O que falta declarar". É teto,
nunca piso: cegueira nunca produz 🔴, porque vermelho significa *algo está fora do ar* e não ter
visto não é prova disso. Limiar de severidade baixa não trava, e regra com aceite vigente
também não — ela já não contaria.
```

- [x] **Step 2: acrescentar ao CHANGELOG**

Em `/var/www/ai-marketplace/CHANGELOG.md`, na seção `## [Não publicado]`, bloco `### Corrigido`:

```markdown
- `sw-infra-audit`: **o relatório assinava 🟢 num cluster que ele não conseguiu medir.** Numa
  rodada real o mesmo cluster passou de 🔴 para 🟢 sem nada ter melhorado: a variável com a
  senha do broker não estava no ambiente, a pergunta que produz `fila_sem_consumidor` não foi
  respondida, nenhum achado nasceu e não havia o que agravar. A skill prega "não consegui ver
  ≠ está ruim"; o inverso, **"não consegui ver ≠ está bom"**, estava desprotegido. Agora
  pergunta com `limiar` sem resposta impede o 🟢 (teto, nunca piso) e o relatório diz qual
  componente, qual pergunta e qual motivo. Lista vazia numa pergunta com limiar deixou de
  contar como resposta — era a mesma cegueira por outra porta.
```

- [x] **Step 3: conferir que a documentação não ficou mentindo**

Rode:
```bash
grep -n "Cobertura da medição" SKILL.md && \
grep -c "não consegui ver" /var/www/ai-marketplace/CHANGELOG.md
```
Esperado: a linha da SKILL.md aparece e o CHANGELOG tem ao menos uma ocorrência.

---

## Ajustes durante a execução

- **2026-10-03 — task 5, step 4.** O plano mandava ler uma variável `aceites` no `main`, que
  **não existe**: o módulo é importado como `aceites_mod` e o resultado vai para
  `relatorio["aceites"]`. Quebrou 48 testes de uma vez. O step foi corrigido no plano para ler
  de `relatorio.get("aceites")`; quem reexecutar não repete o erro.
