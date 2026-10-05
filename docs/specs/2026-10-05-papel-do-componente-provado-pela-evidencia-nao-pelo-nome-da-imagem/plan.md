# Plano de implementação — Papel do componente provado pela evidência

[spec.md](spec.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** o papel de um componente passa a ser provado pela série que ele publica, não
adivinhado pelo nome da imagem.

**Arquitetura:** um passe de identificação roda por FONTE antes das perguntas; cada adaptador
responde "quem está publicando aqui?" com uma consulta por família; um módulo puro
(`lib/identificacao.py`) casa esses valores com os componentes e decide o papel. O
`produtos.toml` cai de autoridade para palpite, e o filtro por papel da v0.14.0 é removido.

**Stack:** Python 3 puro, `pytest`. Skill em `~/.claude/skills/sw-infra-audit/`, venv em
`.venv`. Suíte: `./.venv/bin/python -m pytest -q` (1057 testes verdes na linha de base).
Publicação: `make sync SKILL=sw-infra-audit BUMP=minor` a partir de `/var/www/ai-marketplace`;
`make check` antes de todo commit. **O marketplace é público:** nenhum host, IP, domínio ou
nome real de projeto/cluster entra em código, teste, plano ou commit.

**Restrições verificáveis (do spec):**

| Restrição | Como o plano checa |
|---|---|
| 1. No máximo `K×(F+1)` consultas de identificação, independente de componentes e perguntas | Task 7, step 1 (`test_identificacao_nao_depende_do_numero_de_componentes`) |
| 2. Papel só confirmado com casamento + família única + `identifica_papel` + não-`exportador`; afrouxar qualquer uma derruba um teste | Task 10, steps 1-4 (prova por mutação nas quatro) |
| 3. Papel declarado nunca é sobrescrito, e o componente declarado ainda recebe `(familia, seletor)` | Task 5, step 1 (`test_declarado_vence_o_papel_mas_passa_pelo_passe`) |
| 4. `tests/test_produto_nao_mora_no_codigo.py` continua verde | Task 2, step 6 e Task 3, step 6 (suíte inteira após cada mudança de arquivo de dados) |
| 5. Todo arquivo em `references/metricas/` declara `papel` e `identifica_papel`, com prefixo de id coerente | Task 3, steps 1-4 (validação no carregamento + teste de contrato sobre o catálogo real) |

**Convenções deste plano.** Todos os caminhos são relativos a `~/.claude/skills/sw-infra-audit/`,
e todo comando roda a partir dali. `PY=./.venv/bin/python`.

---

## Task 1: SPIKE — a suposição que pode derrubar o plano

**Arquivos:**
- Criar: `/tmp/spike_etiqueta.py` (descartável — **não** entra no repositório)

**Depende de:** nada

**Produto desta task é uma RESPOSTA, não código de produção.**

O spec assume, na tabela de Suposições, que *"nenhum outro componente casa a etiqueta de uma
família sem ser o produto dela"*. D4 já fechou um caso (o container do exporter). Se existir um
**terceiro** tipo de falso positivo, o desenho de D1/D2 muda e o plano precisa ser refeito.

**Deu certo se:** os únicos casamentos inesperados forem os do próprio container do exporter —
que D4 fecha. **Deu errado se:** aparecer casamento de um componente com a família de outro
produto (ex.: um serviço de aplicação casando `postgres-exporter`). Nesse caso, **pare** e
registre em "Ajustes durante a execução": D1 precisa de uma trava a mais antes de seguir.

- [x] **Step 1: escrever o spike**

```python
# /tmp/spike_etiqueta.py
"""Mede o falso positivo de papel confirmado por VALOR DE ETIQUETA.

Não é teste: é uma pergunta à realidade do catálogo, antes de construir em cima dela.
"""
import sys, pathlib
RAIZ = pathlib.Path.home() / ".claude/skills/sw-infra-audit"
sys.path.insert(0, str(RAIZ / "scripts"))

from lib.adaptadores.promql import casar_valor_da_etiqueta as casar

# Nomes de serviço plausíveis num Swarm, no formato `<stack>_<servico>`.
COMPONENTES = [
    "borda_proxy", "borda_traefik", "web_nginx",
    "infra_broker", "infra_rabbitmq", "fila_worker",
    "dados_pg", "dados_postgres", "app_api", "app_web", "app_worker",
    "cache_redis", "cache_valkey", "busca_opensearch",
    # os exporters, que D4 fecha — esperados na lista de casamentos
    "infra_postgres-exporter", "infra_mysqld-exporter", "monitoring_redis-exporter",
    "monitoring_node-exporter", "monitoring_cadvisor",
]

# Valores de `job` típicos de cada família que PROVA papel (D1).
VALORES_POR_FAMILIA = {
    "traefik":             [["traefik"], ["proxy"], ["edge"]],
    "rabbitmq-prometheus": [["rabbitmq"], ["broker"], ["amqp"]],
    "postgres-exporter":   [["postgres-exporter"], ["postgres"], ["pg"]],
    "mysqld-exporter":     [["mysqld-exporter"], ["mysql"], ["db"]],
    "redis-exporter":      [["redis-exporter"], ["redis"], ["cache"]],
}

PRODUTO_DA_FAMILIA = {
    "traefik": ("borda_traefik", "borda_proxy"),
    "rabbitmq-prometheus": ("infra_rabbitmq", "infra_broker"),
    "postgres-exporter": ("dados_postgres", "dados_pg"),
    "mysqld-exporter": (),
    "redis-exporter": ("cache_redis", "cache_valkey"),
}

inesperados = []
for familia, conjuntos in VALORES_POR_FAMILIA.items():
    for valores in conjuntos:
        for comp in COMPONENTES:
            if casar(comp, valores) is None:
                continue
            if comp in PRODUTO_DA_FAMILIA[familia]:
                continue                      # o produto de verdade: é o que se quer
            if "exporter" in comp or "cadvisor" in comp:
                print(f"  [D4 fecha] {familia:20} {str(valores):26} <- {comp}")
                continue
            inesperados.append((familia, valores, comp))

print()
if inesperados:
    print(f"FALSO POSITIVO NÃO PREVISTO: {len(inesperados)}")
    for f, v, c in inesperados:
        print(f"  {f:20} {str(v):26} <- {c}")
    sys.exit(1)
print("Nenhum falso positivo além dos que D4 fecha.")
```

- [x] **Step 2: rodar o spike**

Rode: `cd ~/.claude/skills/sw-infra-audit && ./.venv/bin/python /tmp/spike_etiqueta.py`
Esperado: linhas `[D4 fecha]` para os exporters, e no fim
`Nenhum falso positivo além dos que D4 fecha.` com exit 0.

- [x] **Step 3: registrar o resultado**

Acrescente ao fim do `plan.md`, na seção "Ajustes durante a execução", uma linha com a data e o
veredito. Se o spike saiu com exit 1, **pare aqui** e leve os casos ao dono: o desenho de
D1/D2 precisa de revisão antes de qualquer código de produção.

---

## Task 2: `exportador` no catálogo de produtos (D4)

**Arquivos:**
- Alterar: `references/produtos.toml`
- Alterar: `scripts/lib/produtos.py`
- Teste: `tests/test_produtos.py`

**Depende de:** Task 1

**Contrato que esta task publica:** `produtos.e_exportador(texto) -> bool`

- [x] **Step 1: escrever o teste que falha**

Acrescente ao fim de `tests/test_produtos.py`:

```python
# ---------------------------------------------------------------- D4: quem só observa
EXPORTADORES = ("cadvisor", "node-exporter", "node_exporter", "promtail",
                "dockerd-exporter",
                # os três que D4 existe para travar, e que não existiam no arquivo
                "postgres-exporter", "mysqld-exporter", "redis-exporter")


@pytest.mark.parametrize("trecho", EXPORTADORES)
def test_exportador_e_reconhecido_como_tal(trecho):
    """Estes produtos OBSERVAM outros; o papel deles nunca pode ser provado pela série que
    eles publicam, porque a série é do observado, não deles."""
    assert produtos.e_exportador(f"org/{trecho}:latest") is True


def test_produto_normal_nao_e_exportador():
    assert produtos.e_exportador("registry.exemplo/postgres:16") is False
    assert produtos.e_exportador("registry.exemplo/minha-api:4.2") is False


def test_o_exportador_de_banco_nao_rouba_o_kind_do_banco():
    """O casamento é por trecho e o primeiro bloco que casa vence. Com `postgres-exporter`
    depois de `postgres`, o exporter herdaria `kind = "banco"` e entraria no inventário como
    um banco — mudando saúde e impacto, que são não-objetivos deste ciclo."""
    assert produtos.kind_do_caminho("org/postgres-exporter:0.15") is None
    assert produtos.kind_do_caminho("org/postgres:16") == "banco"


def test_exportador_fora_do_arquivo_e_recusado(tmp_path):
    """`exportador` tem de ser booleano: um `exportador = "sim"` passaria como verdadeiro e
    silenciaria o papel de um produto inteiro sem ninguém notar."""
    arquivo = tmp_path / "p.toml"
    arquivo.write_text('[[produto]]\nnome = "x"\nimagem = ["a"]\nexportador = "sim"\n',
                       encoding="utf-8")

    with pytest.raises(produtos.ProdutosInvalidos, match="exportador"):
        produtos.carregar(arquivo)
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_produtos.py -q`
Esperado: FALHA com `AttributeError: module 'lib.produtos' has no attribute 'e_exportador'`

- [x] **Step 3: declarar os exporters que ainda NÃO existem no arquivo**

`references/produtos.toml` hoje **não tem bloco nenhum** para `postgres-exporter`,
`mysqld-exporter` nem `redis-exporter` — conferido. Sem eles, `e_exportador` devolve `False`
para o serviço `<stack>_postgres-exporter`, e ele recebe `banco` **confirmado**: é linha por
linha a tabela de D4, que o spec marca como não-cortável.

Acrescente os três blocos. **Sem `kind`**, de propósito: dar `kind` a eles mudaria
`detect_kind` e o inventário, que é não-objetivo deste ciclo.

```toml
# --- exporters de produto: publicam a série do OBSERVADO, não a deles
#
# Sem estes blocos, o container do exporter casa a etiqueta da própria família — o núcleo de
# `<stack>_postgres-exporter` e de `postgres-exporter` é o mesmo `exporter` — e recebe o papel
# do produto que ele apenas observa, enquanto o produto de verdade fica provisório. O
# resultado é perfeitamente invertido. Ver D4 no spec.
#
# Sem `kind` de propósito: classificar o exporter como `banco` mudaria `detect_kind`, o
# inventário e `metrics.STATEFUL` — não-objetivo deste ciclo.
[[produto]]
nome = "postgres-exporter"
imagem = ["postgres-exporter", "postgres_exporter"]
exportador = true

[[produto]]
nome = "mysqld-exporter"
imagem = ["mysqld-exporter", "mysqld_exporter"]
exportador = true

[[produto]]
nome = "redis-exporter"
imagem = ["redis-exporter", "redis_exporter"]
exportador = true
```

**Posição importa:** estes blocos precisam vir **antes** dos blocos de `postgres`, `mysql`,
`mariadb` e `redis`, porque o casamento é por trecho e o primeiro que casa vence — senão
`postgres-exporter` cairia no bloco de `postgres` e ganharia `kind = "banco"`.

- [x] **Step 3b: marcar os exporters que já existem**

Em `references/produtos.toml`, acrescente `exportador = true` nos blocos `cadvisor`,
`node-exporter`, `promtail` e `dockerd-exporter` — logo abaixo da linha `imagem = [...]`.
Exemplo, no bloco do cadvisor:

```toml
[[produto]]
nome = "cadvisor"
imagem = ["cadvisor"]
# Observa OUTROS containers: a série que ele publica é do observado, nunca dele. Sem esta
# marca, o container do próprio exporter receberia papel confirmado a partir da série que ele
# só retransmite — e o produto observado ficaria sem identidade. Ver D4 no spec.
exportador = true
socket_esperado = true
```

Faça o mesmo para `node-exporter`, `promtail` e `dockerd-exporter`. Os demais blocos não mudam.

- [x] **Step 4: implementar a validação e o acessor**

Em `scripts/lib/produtos.py`, dentro de `_validar`, logo antes de `metricas = produto.get("metricas")`:

```python
    if "exportador" in produto and not isinstance(produto["exportador"], bool):
        raise ProdutosInvalidos(f"{onde}: `exportador` de {produto['nome']!r} precisa ser "
                                f"booleano — um texto qualquer passaria como verdadeiro e "
                                f"silenciaria o papel de um produto inteiro")
```

E no fim do arquivo, ao lado de `socket_esperado`:

```python
def e_exportador(texto, produtos=None):
    """Este produto OBSERVA outros, em vez de ser observado?

    A série que um exporter standalone publica é do produto que ele observa, não dele. Sem
    esta marca, o container do próprio exporter casaria a etiqueta da própria família e
    receberia papel confirmado — enquanto o produto de verdade ficaria provisório. O resultado
    é perfeitamente invertido, e com carimbo de autoridade. Ver D4 no spec.

    É um filtro NEGATIVO, e é isso que o torna seguro: errar por omissão (um exporter que
    ninguém listou) deixa algo provisório, que é o estado de hoje; nunca carimba errado.
    """
    alvo = (texto or "").lower()
    return any(any(t in alvo for t in produto["imagem"])
               for produto in (produtos if produtos is not None else carregar())
               if produto.get("exportador"))
```

- [x] **Step 5: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_produtos.py -q`
Esperado: PASSA

- [x] **Step 6: rodar a suíte inteira (restrição 4)**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: PASSA, incluindo `tests/test_produto_nao_mora_no_codigo.py` — o nome de produto
continua só no arquivo de dados.

---

## Task 3: `papel` e `identifica_papel` nos arquivos de família (D1)

**Arquivos:**
- Alterar: `references/metricas/traefik.toml`, `rabbitmq-prometheus.toml`,
  `postgres-exporter.toml`, `mysqld-exporter.toml`, `redis-exporter.toml`,
  `cadvisor.toml`, `http-generico.toml`
- Alterar: `scripts/lib/catalogo.py`
- Teste: `tests/test_catalogo_papel.py` (criar)

**Depende de:** Task 1

**Contrato que esta task publica:** todo dicionário de família devolvido por
`catalogo.familias()` tem as chaves `papel: str` e `identifica_papel: bool`.

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_catalogo_papel.py
"""A família declara o papel que ela prova — ou declara que não prova nenhum.

`cadvisor` publica `container_cpu_usage_seconds_total` com a etiqueta
`container_label_com_docker_swarm_service_name`, cujo valor É o nome do serviço no Swarm. Logo
TODO componente do cluster casa cAdvisor por igualdade exata (medido: 5 de 5). Se "casou a
etiqueta" bastasse para confirmar papel, ou nada seria confirmado nunca, ou — pior — um
componente cujo exporter real usa outro nome de job casaria só o cAdvisor e receberia papel
`app` CONFIRMADO. O caso que motiva o ciclo passaria a falhar com carimbo de autoridade.

`http-generico` tem o mesmo problema na outra direção: `http_requests_total` é publicado por
qualquer aplicação instrumentada, e promoveria uma API a `entrada`.

As duas MEDEM e NÃO VOTAM.
"""
import pytest

from lib import catalogo
from lib.papel import PAPEIS

BASE = """
familia = "exemplo"
prioridade = 50
[identificacao]
metrica_presente = "x_total"
[seletor]
etiqueta = "job"
"""


def _escrever(tmp_path, corpo):
    caminho = tmp_path / "familia.toml"
    caminho.write_text(BASE + corpo, encoding="utf-8")
    return caminho


def test_familia_sem_papel_e_recusada(tmp_path):
    corpo = '''
[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(x_total{%SELETOR%})'
'''
    with pytest.raises(catalogo.CatalogoInvalido, match="`papel`"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_papel_inexistente_e_recusado(tmp_path):
    corpo = '''
papel = "banco-de-dados"
identifica_papel = true
[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(x_total{%SELETOR%})'
'''
    with pytest.raises(catalogo.CatalogoInvalido, match="banco-de-dados"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_pergunta_de_outro_papel_e_recusada(tmp_path):
    """A família diz que prova `banco` e responde pergunta de `entrada`: uma das duas mente, e
    descobrir qual no relatório é tarde demais."""
    corpo = '''
papel = "banco"
identifica_papel = true
[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(x_total{%SELETOR%})'
'''
    with pytest.raises(catalogo.CatalogoInvalido, match="entrada.volume_na_janela"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


def test_identifica_papel_nao_booleano_e_recusado(tmp_path):
    corpo = '''
papel = "entrada"
identifica_papel = "sim"
[[pergunta]]
id = "entrada.volume_na_janela"
query = 'sum(x_total{%SELETOR%})'
'''
    with pytest.raises(catalogo.CatalogoInvalido, match="identifica_papel"):
        catalogo.carregar_arquivo(_escrever(tmp_path, corpo))


# ---------------------------------------------------------------- contrato sobre o catálogo REAL
def test_toda_familia_publicada_declara_papel_e_se_prova():
    for familia in catalogo.familias():
        assert familia["papel"] in PAPEIS, familia["familia"]
        assert isinstance(familia["identifica_papel"], bool), familia["familia"]


def test_as_sondas_de_medida_nao_provam_papel():
    """Fixa quais famílias MEDEM sem votar. Mudar esta lista é mudar como um cluster real é
    lido — tem de ser deliberado, com o diff à vista."""
    por_nome = {f["familia"]: f for f in catalogo.familias()}

    assert por_nome["cadvisor"]["identifica_papel"] is False
    assert por_nome["http-generico"]["identifica_papel"] is False
    for prova in ("traefik", "rabbitmq-prometheus", "postgres-exporter",
                  "mysqld-exporter", "redis-exporter"):
        assert por_nome[prova]["identifica_papel"] is True, prova
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_catalogo_papel.py -q`
Esperado: FALHA — `KeyError: 'papel'` nos dois últimos, e os quatro primeiros falham por não
haver validação nenhuma.

- [x] **Step 3: declarar nos 7 arquivos**

Em cada arquivo de `references/metricas/`, logo abaixo da linha `prioridade = ...`:

```toml
# traefik.toml
papel = "entrada"
identifica_papel = true    # `traefik_service_requests_total` só existe neste proxy

# rabbitmq-prometheus.toml
papel = "fila"
identifica_papel = true

# postgres-exporter.toml
papel = "banco"
identifica_papel = true

# mysqld-exporter.toml
papel = "banco"
identifica_papel = true

# redis-exporter.toml
papel = "cache"
identifica_papel = true

# cadvisor.toml
papel = "app"
# NÃO prova papel: a etiqueta desta família é o nome do serviço no Swarm, então TODO
# componente do cluster casa por igualdade exata (medido: 5 de 5). Ela MEDE qualquer
# container e não diz nada sobre o que ele É. Ver D1 no spec.
identifica_papel = false

# http-generico.toml
papel = "entrada"
# NÃO prova papel: `http_requests_total` é publicado por qualquer aplicação instrumentada.
# Sem esta marca, uma API viraria `entrada` confirmado e mudaria de camada na topologia.
identifica_papel = false
```

- [x] **Step 4: implementar a validação**

Em `scripts/lib/catalogo.py`, dentro de `carregar_arquivo`, logo depois do bloco que valida
`[seletor] etiqueta`:

```python
    from lib.papel import PAPEIS

    papel = dados.get("papel")
    if not papel:
        raise CatalogoInvalido(f"{caminho.name}: falta `papel` — é ele que diz de que papel "
                               f"esta família fala, e sem isso ela não pode nem responder "
                               f"pergunta nem provar identidade")
    if papel not in PAPEIS:
        raise CatalogoInvalido(f"{caminho.name}: papel {papel!r} não existe; os papéis são "
                               f"{', '.join(PAPEIS)}")
    if not isinstance(dados.get("identifica_papel"), bool):
        raise CatalogoInvalido(
            f"{caminho.name}: falta `identifica_papel` (booleano). `true` quando a série é "
            f"assinatura do produto e prova o papel de quem a publica; `false` quando ela só "
            f"MEDE — o exporter de container mede qualquer container, e a métrica HTTP "
            f"genérica mede qualquer coisa que fale HTTP. Deixar implícito foi o que quase "
            f"fez toda família votar")
```

E dentro do laço `for pergunta in dados.get("pergunta", []):`, logo depois da checagem de
`id_ not in PERGUNTAS`:

```python
        if str(id_).split(".")[0] != papel:
            raise CatalogoInvalido(f"{caminho.name}: a família diz falar de {papel!r} e "
                                   f"responde {id_!r}, que é de outro papel — uma das duas "
                                   f"afirmações mente, e descobrir qual no relatório é tarde")
```

- [x] **Step 5: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_catalogo_papel.py -q`
Esperado: PASSA (6 testes)

- [x] **Step 6: rodar a suíte inteira**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: PASSA. Se algum teste de catálogo existente quebrar por não declarar `papel` num
TOML de fixture, acrescente as duas linhas ao fixture — não afrouxe a validação.

---

## Task 4: `casar_valor_da_etiqueta` muda de casa

**Arquivos:**
- Criar: `scripts/lib/identificacao.py`
- Alterar: `scripts/lib/adaptadores/promql.py`

**Depende de:** Task 1

**Contrato que esta task publica:**
`identificacao.casar_valor_da_etiqueta(componente, valores) -> str | None`

O spec diz que `lib/identificacao.py` é "o **único** lugar da skill que casa nome de componente
com valor de etiqueta". A função já existe, mas mora no adaptador. Mover primeiro deixa as
tasks seguintes construírem em cima do lugar certo.

- [x] **Step 1: criar o módulo com a função movida**

Crie `scripts/lib/identificacao.py` com o cabeçalho abaixo e **o corpo de
`casar_valor_da_etiqueta` copiado literalmente** de `scripts/lib/adaptadores/promql.py`
(docstring inclusive — ela explica por que o casamento é estreito):

```python
"""Quem é cada componente, a partir de quem está publicando na fonte.

Este módulo é o ÚNICO lugar da skill que casa nome de componente com valor de etiqueta. Ele é
puro: não abre socket, não importa adaptador. Quem fala com a fonte é o adaptador, por
`reconhecer()`; aqui só se decide o que aquilo significa.

A inversão que ele implementa: em vez de `imagem → kind → papel → filtra famílias → pergunta`,
o caminho passa a ser `fonte → quem publica lá → casa com os componentes → papel → pergunta`.
É o mesmo princípio que o catálogo de métrica já aplica — a série que existe vence o nome.
"""


def casar_valor_da_etiqueta(componente, valores):
    ...  # corpo e docstring copiados de promql.py, sem alteração
```

- [x] **Step 2: apontar o adaptador para o módulo novo**

Em `scripts/lib/adaptadores/promql.py`, **remova** a definição de `casar_valor_da_etiqueta` e
acrescente ao bloco de imports:

```python
from lib.identificacao import casar_valor_da_etiqueta
```

O nome continua importável de `promql` (os testes existentes fazem
`from lib.adaptadores.promql import casar_valor_da_etiqueta`), então nada quebra.

- [x] **Step 3: rodar a suíte e confirmar que nada quebrou**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: PASSA, 1057+ testes. É um movimento puro: se algo falhou, o corpo foi copiado errado.

---

## Task 5: `identificacao.resolver` — a decisão de papel

**Arquivos:**
- Alterar: `scripts/lib/identificacao.py`
- Teste: `tests/test_identificacao.py` (criar)

**Depende de:** Task 2, Task 3, Task 4

**Contrato que esta task publica:**

```python
resolver(componentes, reconhecido_por_fonte)
  -> {nome: {"papel", "papel_origem", "familias", "ambiguidade", "soma_de_todos"}}
# componentes: [{"nome", "papel", "papel_origem", "metricas_url", "exportador": bool}]
#   `papel`/`papel_origem` chegam PROVISÓRIOS (de `produtos.toml`, ou `declarado`).
# reconhecido_por_fonte: {base: [{"familia","papel","identifica_papel","prioridade",
#                                 "etiqueta","valores"}]}
# familias: [{"familia": <dict da família>, "seletor": str}]  — "" = exporter inteiro
```

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_identificacao.py
"""O papel sai de quem respondeu, não do nome da imagem.

Testes puros: nenhum socket, nenhum Prometheus falso. O que fala com a fonte é
`promql.reconhecer`; aqui só se decide o que a resposta dela significa.
"""
from lib import identificacao


def _familia(nome, papel, prova=True, prioridade=30, etiqueta="job", perguntas=()):
    return {"familia": nome, "papel": papel, "identifica_papel": prova,
            "prioridade": prioridade, "seletor": {"etiqueta": etiqueta},
            "pergunta": [{"id": p} for p in perguntas]}


def _reconhecido(familia, valores):
    return dict(familia, valores=list(valores), etiqueta=familia["seletor"]["etiqueta"])


def _componente(nome, papel="app", origem="padrão", fonte="http://f", exportador=False):
    return {"nome": nome, "papel": papel, "papel_origem": origem,
            "metricas_url": fonte, "exportador": exportador}


BROKER = _familia("rabbitmq-prometheus", "fila", perguntas=["fila.filas"])
CADVISOR = _familia("cadvisor", "app", prova=False, prioridade=40,
                    etiqueta="container_label_com_docker_swarm_service_name",
                    perguntas=["app.cpu", "app.memoria"])
PG = _familia("postgres-exporter", "banco", prioridade=40, perguntas=["banco.conexoes"])
MYSQL = _familia("mysqld-exporter", "banco", prioridade=40, perguntas=["banco.conexoes"])
TRAEFIK = _familia("traefik", "entrada", perguntas=["entrada.latencia"])
HTTP = _familia("http-generico", "entrada", prova=False, prioridade=50,
                perguntas=["entrada.latencia"])


def test_familia_que_prova_confirma_o_papel():
    """O caso que motiva o ciclo: a imagem é desconhecida, a série não é."""
    comp = _componente("pilha_desconhecida", papel="app", origem="padrão")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(BROKER,
                                                                     ["pilha_desconhecida"])]})

    assert saida["pilha_desconhecida"]["papel"] == "fila"
    assert saida["pilha_desconhecida"]["papel_origem"] == "exporter rabbitmq-prometheus"


def test_cadvisor_casa_todo_mundo_e_nao_confirma_ninguem():
    """A etiqueta do cAdvisor É o nome do serviço: casar com ela não prova nada."""
    comps = [_componente(n) for n in ("app_api", "dados_pg", "cache_redis")]
    nomes = [c["nome"] for c in comps]

    saida = identificacao.resolver(comps, {"http://f": [_reconhecido(CADVISOR, nomes)]})

    for nome in nomes:
        assert saida[nome]["papel_origem"] == "padrão", nome
        assert saida[nome]["papel"] == "app"
        # mas ela MEDE: a família entra no conjunto, com o seletor casado
        assert [f["familia"]["familia"] for f in saida[nome]["familias"]] == ["cadvisor"]


def test_http_generico_nao_promove_uma_api_a_entrada():
    comp = _componente("app_api", papel="app", origem="padrão")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(HTTP, ["app_api"])]})

    assert saida["app_api"]["papel"] == "app"
    assert saida["app_api"]["papel_origem"] == "padrão"


def test_container_do_exportador_nunca_recebe_papel_provado():
    """D4, o falso positivo invertido: a etiqueta `job` nomeia o EXPORTER, e o núcleo de
    `<stack>_postgres-exporter` e de `postgres-exporter` é o mesmo `exporter`."""
    comp = _componente("infra_postgres-exporter", exportador=True)

    saida = identificacao.resolver([comp],
                                   {"http://f": [_reconhecido(PG, ["postgres-exporter"])]})

    assert saida["infra_postgres-exporter"]["papel"] == "app"
    assert saida["infra_postgres-exporter"]["papel_origem"] == "padrão"


def test_duas_familias_que_provam_nao_confirmam():
    comp = _componente("dados_db")
    reconhecido = [_reconhecido(PG, ["dados_db"]), _reconhecido(MYSQL, ["dados_db"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})

    assert saida["dados_db"]["papel_origem"] == "padrão"
    assert saida["dados_db"]["ambiguidade"] == ["mysqld-exporter", "postgres-exporter"]


def test_declarado_vence_o_papel_mas_passa_pelo_passe():
    """Restrição verificável 3: a declaração vence o PAPEL, não a identificação — sem
    `(familia, seletor)` nenhuma pergunta é respondida."""
    comp = _componente("infra_broker", papel="cache", origem="declarado")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(BROKER,
                                                                     ["infra_broker"])]})

    assert saida["infra_broker"]["papel"] == "cache"
    assert saida["infra_broker"]["papel_origem"] == "declarado"
    assert [f["familia"]["familia"] for f in saida["infra_broker"]["familias"]] \
        == ["rabbitmq-prometheus"]


def test_o_conjunto_guarda_as_duas_familias_que_cobrem_o_componente():
    """Um banco coberto por cAdvisor E postgres-exporter precisa dos dois: um responde
    `app.*`, o outro `banco.*`. Com um par só, a ordem alfabética daria o cAdvisor."""
    comp = _componente("dados_pg")
    reconhecido = [_reconhecido(CADVISOR, ["dados_pg"]), _reconhecido(PG, ["dados_pg"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})

    assert saida["dados_pg"]["papel"] == "banco"
    assert sorted(f["familia"]["familia"] for f in saida["dados_pg"]["familias"]) \
        == ["cadvisor", "postgres-exporter"]


def test_sem_casamento_a_familia_entra_com_seletor_vazio():
    """A série existe mas a etiqueta não nomeia o componente: a resposta sai do exporter
    inteiro, e o papel NÃO é promovido. Medir não é provar."""
    comp = _componente("borda_proxy")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(TRAEFIK, ["edge"])]})

    assert saida["borda_proxy"]["papel_origem"] == "padrão"
    assert saida["borda_proxy"]["familias"][0]["seletor"] == ""


def test_componente_sem_fonte_fica_como_chegou():
    comp = _componente("app_web", papel="app", origem="imagem", fonte=None)

    saida = identificacao.resolver([comp], {})

    assert saida["app_web"] == {"papel": "app", "papel_origem": "imagem", "familias": [],
                                "ambiguidade": []}
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_identificacao.py -q`
Esperado: FALHA com `AttributeError: module 'lib.identificacao' has no attribute 'resolver'`

- [x] **Step 3: implementar `resolver`**

Acrescente a `scripts/lib/identificacao.py`:

```python
def base_da_fonte(url):
    """A raiz da API, igual ao que `promql.base_de` faz — a chave de `reconhecido_por_fonte`.

    Pública de propósito: `collect.identificar` agrupa as fontes por ela, e nome privado usado
    entre módulos é contrato por acidente.
    """
    return str(url or "").split("/api/")[0].split("/metrics")[0].rstrip("/")


def resolver(componentes, reconhecido_por_fonte):
    """Papel, origem e as famílias que cobrem cada componente.

    Pura: recebe o que as fontes responderam e devolve o que aquilo significa. A precedência
    está em D2 do spec — `declarado` > `exporter <família>` > `imagem` > `padrão`.

    Uma família só VOTA no papel quando declara `identifica_papel = true` e o componente não é
    um exportador. As duas travas existem pelo mesmo motivo, em direções opostas: o cAdvisor
    casa todo componente (a etiqueta dele É o nome do serviço), e o container de um exporter
    casa a própria família (o núcleo de `<stack>_pg-exporter` e de `pg-exporter` é o mesmo).
    Sem elas o papel sai universalmente `app`, ou sai invertido — o exporter vira o produto.
    """
    saida = {}
    for componente in componentes:
        nome = componente.get("nome")
        familias, votos, soma = [], [], []
        fonte = base_da_fonte(componente.get("metricas_url"))
        for reconhecida in reconhecido_por_fonte.get(fonte, []):
            valores = reconhecida.get("valores") or []
            valor = casar_valor_da_etiqueta(nome, valores)
            if valor is not None:
                etiqueta = reconhecida["seletor"]["etiqueta"]
                familias.append({"familia": reconhecida, "seletor": f'{etiqueta}="{valor}"'})
                if reconhecida.get("identifica_papel") and not componente.get("exportador"):
                    votos.append(reconhecida)
            elif len(set(valores)) == 1:
                # UM valor só: o exporter cobre um componente e o número sem filtro é dele. A
                # fonte carimba `(exporter inteiro)` para quem lê saber de onde veio.
                familias.append({"familia": reconhecida, "seletor": ""})
            else:
                # Vários valores e nenhum casa: o número sem filtro é a SOMA de todos, e
                # entregá-lo como se fosse de um é a mentira que a v0.14.0 consertou. A família
                # NÃO entra no conjunto; o motivo sai por `motivo_da_falta`.
                soma.append(reconhecida["familia"])

        papel = componente.get("papel")
        origem = componente.get("papel_origem")
        ambiguidade = []
        if origem != "declarado":
            if len(votos) == 1:
                papel = votos[0]["papel"]
                origem = f"exporter {votos[0]['familia']}"
            elif len(votos) > 1:
                # Carimbar um palpite de autoridade é pior que não carimbar.
                ambiguidade = sorted(v["familia"] for v in votos)

        saida[nome] = {"papel": papel, "papel_origem": origem, "familias": familias,
                       "ambiguidade": ambiguidade, "soma_de_todos": sorted(soma)}
    return saida
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_identificacao.py -q`
Esperado: PASSA (9 testes)

- [x] **Step 5: escrever o teste do desempate e implementá-lo**

Acrescente a `tests/test_identificacao.py`:

```python
def test_quem_prova_papel_responde_a_pergunta_disputada():
    """`traefik` e `http-generico` declaram os mesmos três `entrada.*`. Sem regra, quem
    responde dependeria da ordem de `catalogo.familias()`."""
    comp = _componente("borda_proxy")
    reconhecido = [_reconhecido(HTTP, ["borda_proxy"]), _reconhecido(TRAEFIK, ["borda_proxy"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})

    assert identificacao.familia_da_pergunta(saida["borda_proxy"], "entrada.latencia") \
        ["familia"]["familia"] == "traefik"


def test_empate_entre_duas_que_provam_resolve_pela_prioridade():
    comp = _componente("dados_db")
    reconhecido = [_reconhecido(MYSQL, ["dados_db"]),
                   _reconhecido(dict(PG, prioridade=35), ["dados_db"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})

    assert identificacao.familia_da_pergunta(saida["dados_db"], "banco.conexoes") \
        ["familia"]["familia"] == "postgres-exporter"


def test_seletor_casado_vence_seletor_vazio_na_mesma_pergunta():
    """`postgres-exporter` e `mysqld-exporter` declaram ambos `banco.conexoes`, provam papel os
    dois e têm a MESMA prioridade 40 — o desempate cairia no nome, e `mysqld` venceria."""
    comp = _componente("dados_pg")
    reconhecido = [_reconhecido(MYSQL, ["mysqld"]),          # um valor, nenhum casa → vazio
                   _reconhecido(PG, ["dados_pg"])]           # casa

    saida = identificacao.resolver([comp], {"http://f": reconhecido})
    escolhida = identificacao.familia_da_pergunta(saida["dados_pg"], "banco.conexoes")

    assert escolhida["familia"]["familia"] == "postgres-exporter"
    assert escolhida["seletor"] == 'job="dados_pg"'


def test_varios_valores_e_nenhum_casa_nao_entrega_a_soma():
    """A garantia da v0.14.0: com vários valores e nenhum casando, o número sem filtro é a SOMA
    de todos, e entregá-lo como se fosse de um é a mentira que aquele ciclo consertou."""
    comp = _componente("cdn_borda")
    reconhecido = [_reconhecido(TRAEFIK, ["proxy", "borda"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})

    assert saida["cdn_borda"]["familias"] == []
    assert saida["cdn_borda"]["soma_de_todos"] == ["traefik"]
    assert "soma de todos" in identificacao.motivo_da_falta(saida["cdn_borda"],
                                                            "entrada.latencia")


def test_pergunta_que_ninguem_declara_nao_tem_familia():
    comp = _componente("app_api")
    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(CADVISOR, ["app_api"])]})

    assert identificacao.familia_da_pergunta(saida["app_api"], "fila.filas") is None
```

E implemente em `scripts/lib/identificacao.py`:

```python
def familia_da_pergunta(resolvido, pergunta):
    """Qual das famílias que cobrem o componente responde ESTA pergunta — ou None.

    Duas famílias casadas podem declarar o mesmo id: `postgres-exporter` e `mysqld-exporter`
    declaram ambos `banco.conexoes`, e `traefik` e `http-generico` declaram os mesmos três
    `entrada.*`. A regra, em duas linhas: vence quem prova papel (a que provou responde por
    ele); empate persistindo, vence a `prioridade`, que é o critério que já existia.
    """
    candidatas = [f for f in resolvido.get("familias") or []
                  if any(p["id"] == pergunta for p in f["familia"].get("pergunta", []))]
    if not candidatas:
        return None
    # A primeira chave é o seletor CASADO. `postgres-exporter` e `mysqld-exporter` declaram
    # ambos `banco.conexoes`, provam papel os dois, e têm a MESMA `prioridade = 40` — o
    # desempate cairia no nome, e `mysqld-exporter` venceria em ordem alfabética. Um Postgres
    # que casou a própria etiqueta receberia o total do exporter de MySQL.
    return min(candidatas, key=lambda f: (not f["seletor"],
                                          not f["familia"].get("identifica_papel"),
                                          f["familia"].get("prioridade", 99),
                                          f["familia"]["familia"]))


def motivo_da_falta(resolvido, pergunta):
    """Por que esta pergunta não tem família — na linguagem que manda o dono ao lugar certo.

    Antes este motivo nascia dentro do adaptador, a partir do estado `seletor = None` que o
    passe eliminou. Produzi-lo aqui mantém uma decisão num lugar só, e preserva a distinção que
    importa: "não reconheci a família deste componente" manda procurar exporter; "o número sem
    filtro seria a soma de todos" manda olhar a etiqueta do scrape.
    """
    if not resolvido:
        return None
    for familia in resolvido.get("soma_de_todos") or []:
        return (f"o exporter {familia} cobre vários componentes e nenhum valor da etiqueta "
                f"casa com este — o número sem filtro seria a soma de todos")
    return None
```

- [x] **Step 6: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_identificacao.py -q`
Esperado: PASSA (12 testes)

---

## Task 6: `promql.reconhecer` — uma consulta por família, com o cache consertado

**Arquivos:**
- Alterar: `scripts/lib/adaptadores/promql.py`
- Teste: `tests/test_reconhecer.py` (criar)

**Depende de:** Task 3

**Contrato que esta task publica:**
`promql.reconhecer(fonte, contexto) -> [familia_dict + {"valores": [...]}]`

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_reconhecer.py
"""`reconhecer` pergunta "quem está publicando aqui?" — uma consulta por família.

A consulta de descoberta depende de (fonte, família), NUNCA do componente. É isso que faz o
passe de identificação custar F consultas por fonte em vez de F por componente, e é por isso
que inverter a ordem sai mais barato do que o estado anterior.
"""
from lib.adaptadores import promql

from test_adaptador_promql import CONTEXTO, _vetor, prometheus  # noqa: F401


def test_uma_consulta_por_familia_e_devolve_os_valores(prometheus):
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "edge"}, 1)])))

    reconhecidas = promql.reconhecer(base, dict(CONTEXTO, cache={}))

    traefik = next(f for f in reconhecidas if f["familia"] == "traefik")
    assert traefik["valores"] == ["edge"]
    assert traefik["papel"] == "entrada" and traefik["identifica_papel"] is True
    assert len([q for q in falso.RECEBIDAS if "traefik_service_requests_total" in q]) == 1


def test_familia_sem_serie_na_fonte_nao_entra(prometheus):
    base, falso = prometheus

    reconhecidas = promql.reconhecer(base, dict(CONTEXTO, cache={}))

    assert reconhecidas == []


def test_o_cache_vale_para_a_fonte_inteira(prometheus):
    """O cache antigo era gravado numa CÓPIA do contexto feita por pergunta
    (`collect.py:236`), e morria com ela: a mesma consulta de identificação rodava 3× para o
    mesmo componente. O molde certo é `contexto["cache"]`, que `admin_http` já usa."""
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "edge"}, 1)])))
    contexto = dict(CONTEXTO, cache={})

    promql.reconhecer(base, contexto)
    promql.reconhecer(base, contexto)

    assert len([q for q in falso.RECEBIDAS if "traefik_service_requests_total" in q]) == 1
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_reconhecer.py -q`
Esperado: FALHA com `AttributeError: module 'lib.adaptadores.promql' has no attribute 'reconhecer'`

- [x] **Step 3: implementar**

Acrescente a `scripts/lib/adaptadores/promql.py`, logo depois de `_valores_da_etiqueta`:

```python
def reconhecer(fonte, contexto):
    """Quem está publicando nesta fonte. UMA consulta por família, nunca por componente.

    É o contrato que o passe de identificação consome. A consulta de descoberta depende só de
    (fonte, família) — por isso o resultado fica no cache COMPARTILHADO do alvo
    (`contexto["cache"]`, criado em `collect.py`), e não numa cópia por pergunta, que era onde
    o cache anterior morria.
    """
    base = base_de(fonte)
    cache = contexto.setdefault("cache", {}).setdefault("reconhecido", {})
    if base in cache:
        return cache[base]

    saida = []
    for familia in catalogo.familias():
        valores = _valores_da_etiqueta(base, familia, contexto)
        if valores:
            saida.append(dict(familia, valores=valores,
                              etiqueta=familia["seletor"]["etiqueta"]))
    cache[base] = saida
    return saida
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_reconhecer.py -q`
Esperado: PASSA (3 testes)

---

## Task 7: o passe por fonte, e o adaptador consultando o resultado

**Arquivos:**
- Alterar: `scripts/lib/adaptadores/promql.py` (`familia_do_componente`, `perguntar`)
- Alterar: `scripts/collect.py` (`coletar_alvo`, `responder`)
- Alterar: `scripts/lib/coletores/docker.py` (a sonda de alvo)
- Teste: `tests/test_passe_de_identificacao.py` (criar)

**Depende de:** Task 5, Task 6

**Contrato que esta task publica:**
`familia_do_componente(componente, contexto, pergunta)` — a assinatura ganha `pergunta`.

- [ ] **Step 1: escrever o teste que falha (restrição verificável 1)**

```python
# tests/test_passe_de_identificacao.py
"""O passe roda por FONTE, e o custo não depende de quantos componentes existem.

Restrição verificável nº 1 do spec: no máximo K×(F+1) consultas de identificação. É teto, não
igualdade — quando a sonda da fonte falha, as F consultas são curto-circuitadas.
"""
import collect
from lib.adaptadores import promql

from test_adaptador_promql import CONTEXTO, _vetor, prometheus  # noqa: F401


def _componente(nome, base, papel="app"):
    return {"nome": nome, "papel": papel, "papel_origem": "padrão",
            "metricas_url": base, "exportador": False, "respostas": []}


def test_identificacao_nao_depende_do_numero_de_componentes(prometheus):
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "borda_proxy"}, 1)])))
    componentes = [_componente(f"app_{i}", base) for i in range(20)]
    componentes.append(_componente("borda_proxy", base, papel="entrada"))

    contexto = dict(CONTEXTO, cache={})
    collect.identificar(componentes, contexto, [promql], collect.Prazo(120))

    # O teto é K×(F+1): as sondas `vector(1)` são o "+1" e PRECISAM entrar na conta — contando
    # só as `count by`, o teste provaria apenas "nenhuma descoberta repetida", que o teste da
    # Task 6 já prova, e não o teto.
    sondas = [q for q in falso.RECEBIDAS if q == "vector(1)"]
    descobertas = [q for q in falso.RECEBIDAS if q.startswith("count by")]
    familias = len(set(descobertas))
    assert len(sondas) == 1, "uma sonda por fonte, não por componente"
    assert len(descobertas) == familias, "uma consulta por família, não por componente"
    assert len(falso.RECEBIDAS) <= familias + 1, "o teto K×(F+1) foi furado"


def test_fonte_morta_nao_gasta_uma_consulta_por_familia(monkeypatch, prometheus):
    """A fonte está VIVA no teste; quem falha é a sonda, por monkeypatch.

    Apontar o componente para uma porta fechada faria as consultas irem para lá, e o
    `falso.RECEBIDAS == []` passaria com ou sem o curto-circuito — um teste que não pode falhar
    não prova nada.
    """
    base, falso = prometheus
    monkeypatch.setattr(promql, "alcancavel", lambda *a, **k: False)

    contexto = dict(CONTEXTO, cache={})
    collect.identificar([_componente("app_a", base)], contexto, [promql], collect.Prazo(120))

    assert [q for q in falso.RECEBIDAS if q.startswith("count by")] == []


def test_fork_de_cache_e_reconhecido_pelo_exporter_do_original(prometheus):
    """O caso que o Objetivo do spec diz que prova o desenho, ponta a ponta.

    Um fork compatível em protocolo é raspado pelo MESMO exporter e publica a MESMA série. O
    `produtos.toml` não o conhece pelo nome — ele chega como `app` — e o exporter o identifica
    como `cache` sem saber que é um fork, porque identifica a série, não a imagem. Se o desenho
    não resolver este caso, não resolveu nada.
    """
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (redis_memory_used_bytes)",
                         _vetor([({"job": "cache_fork"}, 1)])))
    componente = _componente("cache_fork", base)       # papel `app`, origem `padrão`

    contexto = dict(CONTEXTO, cache={})
    collect.identificar([componente], contexto, [promql], collect.Prazo(120))

    assert componente["papel"] == "cache"
    assert componente["papel_origem"] == "exporter redis-exporter"


def test_o_papel_confirmado_chega_ao_componente(prometheus):
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (rabbitmq_queue_messages_ready)",
                         _vetor([({"job": "pilha_desconhecida"}, 1)])))
    componente = _componente("pilha_desconhecida", base)

    contexto = dict(CONTEXTO, cache={})
    collect.identificar([componente], contexto, [promql], collect.Prazo(120))

    assert componente["papel"] == "fila"
    assert componente["papel_origem"] == "exporter rabbitmq-prometheus"
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_passe_de_identificacao.py -q`
Esperado: FALHA com `AttributeError: module 'collect' has no attribute 'identificar'`

- [ ] **Step 3: implementar o passe em `collect.py`**

Acrescente a `scripts/collect.py`, logo antes de `def responder(`:

```python
def identificar(componentes, contexto, adaptadores, prazo):
    """O passe de identificação: pergunta a cada FONTE quem está publicando nela.

    Roda ANTES das perguntas, porque é ele que decide quais perguntas cada componente recebe.
    O custo é por (fonte, família) — nunca por componente —, e por isso inverter a ordem saiu
    mais barato que o estado anterior, em que a mesma identificação rodava uma vez por
    pergunta.

    A sonda vem primeiro e vale pela fonte inteira: sem ela, uma fonte morta custaria F
    timeouts antes da primeira pergunta, e o alvo sairia todo `sem dados` em vez de "algumas
    respondidas, o resto sem orçamento".
    """
    from lib import identificacao

    fontes = {identificacao.base_da_fonte(c.get("metricas_url"))
              for c in componentes if c.get("metricas_url")}
    reconhecido = {}
    for fonte in sorted(fontes):
        if prazo.esgotado():
            break
        contexto_fonte = dict(contexto, timeout=prazo.timeout(contexto["timeout"]))
        for adaptador in adaptadores:
            if not hasattr(adaptador, "reconhecer"):
                continue
            if not adaptador.alcancavel(fonte, contexto_fonte):
                continue                       # curto-circuita as F consultas desta fonte
            reconhecido.setdefault(fonte, []).extend(
                adaptador.reconhecer(fonte, contexto_fonte))

    # `exportador` chega marcado pelo COLETOR, que é quem tem a imagem em mãos — ver a Task 7,
    # step 5. Marcá-lo aqui exigiria carregar o catálogo de produtos num módulo que não precisa
    # dele, e `novo_componente` não guarda a imagem.
    resolvido = identificacao.resolver(componentes, reconhecido)
    for componente in componentes:
        decidido = resolvido.get(componente["nome"])
        if not decidido:
            continue
        componente["papel"] = decidido["papel"]
        componente["papel_origem"] = decidido["papel_origem"]
        if decidido["ambiguidade"]:
            componente["papel_ambiguo"] = decidido["ambiguidade"]
        contexto.setdefault("cache", {}).setdefault("resolvido", {})[componente["nome"]] = decidido
    return resolvido
```

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_passe_de_identificacao.py -q`
Esperado: PASSA (3 testes)

- [ ] **Step 5: LIGAR o passe ao fluxo real**

Sem este step, `identificar` existe, é testado, e **nunca roda em produção**:
`contexto["cache"]["resolvido"]` fica vazio, `familia_do_componente` devolve sempre
`(None, None)` e todo componente sai `sem_dados`.

Em `scripts/collect.py`, dentro de `coletar_alvo`, **depois** de `peneirar_componentes(registro)`
e da criação do `prazo`, e **antes** do laço `for componente in registro["componentes"]`:

```python
    # O passe decide quais perguntas cada componente recebe, então roda ANTES delas. O `prazo`
    # já existe aqui, e é ele que impede uma fonte lenta de comer o alvo inteiro.
    passe = identificar(registro["componentes"], contexto, adaptadores, prazo)
    for fonte in passe["fontes_mortas"]:
        registro["nao_coletado"].append(report_mod.na(
            f"métricas: {fonte} não respondeu a uma consulta trivial — confira o endereço e "
            f"se é a API de um Prometheus (`/api/v1/query`)"))
```

Confira, ao editar, que `prazo` já está criado nesse ponto do arquivo. Se não estiver, mova a
criação dele para cima do passe — **não** crie um segundo `Prazo`: dois orçamentos para o mesmo
alvo é um alvo sem orçamento.

- [ ] **Step 6: o componente nasce com a origem do papel, e marcado se é exportador**

`papel_origem` **não existe no código hoje** (zero ocorrências em `scripts/`, `tests/` e
`references/`). Sem este step, `resolver` lê `None` em todo componente: a precedência
`if origem != "declarado"` deixa a evidência **sobrescrever a declaração** — restrição
verificável 3 quebrada em produção —, a origem `imagem` nunca aparece no relatório, e a
cobertura cobra declaração de quem já declarou.

E `novo_componente` guarda só `nome`, `papel`, `respostas`, `achados` e `analise` — **não** a
imagem. Sem marcar `exportador` aqui, onde a imagem está em mãos, `e_exportador` veria apenas o
nome, e um serviço chamado `monitoring_agent` rodando um exporter escaparia da trava de D4.

Em `scripts/lib/coletores/docker.py`, onde o componente é montado:

```python
        papel_da_imagem = papel_de(detect_kind(servico.get("image")), None)
        componente = report_mod.novo_componente(
            nome, papel_de(detect_kind(servico.get("image")), declarado.get("papel")))
        # De onde veio o papel. Toda medida carrega a fonte que respondeu; o papel carrega a
        # dele pelo mesmo motivo. `padrão` é "ninguém reconheceu"; `imagem` é palpite do
        # `produtos.toml`; `declarado` vence tudo, e o passe não o sobrescreve.
        componente["papel_origem"] = ("declarado" if declarado.get("papel")
                                      else "imagem" if papel_da_imagem != "app"
                                      else "padrão")
        # Guardado para o relatório poder dizer "a imagem sugeria X" quando a evidência
        # contradisser o palpite (D3).
        componente["papel_da_imagem"] = papel_da_imagem
        # D4: quem OBSERVA outros nunca recebe papel provado pela série que só retransmite.
        componente["exportador"] = produtos.e_exportador(
            f"{servico.get('image') or ''} {nome}")
```

E acrescente `produtos` ao import do topo do arquivo.

- [ ] **Step 7: o teste de que o passe roda de verdade**

Acrescente a `tests/test_passe_de_identificacao.py`:

```python
def test_o_passe_roda_dentro_da_coleta(monkeypatch, prometheus):
    """A ligação: `identificar` existe e é testado, mas se ninguém o chamar o ciclo inteiro
    fica morto fora dos testes — todo componente sai `sem_dados`."""
    base, falso = prometheus
    chamadas = []
    monkeypatch.setattr(collect, "identificar",
                        lambda *a, **k: chamadas.append(a) or {"resolvido": {},
                                                               "fontes_mortas": []})

    coletor = lambda alvo, contexto: {
        "saude": "\U0001F7E2", "dimensoes": {}, "fatos": {}, "achados": [],
        "componentes": [{"nome": "app_a", "papel": "app", "respostas": [], "achados": []}]}
    collect.coletar_alvo({"nome": "c", "tipo": "docker", "context": "ctx"}, coletor,
                         {"timeout": 5, "orcamento": 10, "at": "2026-10-05T00:00:00Z"})

    assert chamadas, "`identificar` não foi chamado dentro de `coletar_alvo`"


def test_fonte_morta_vira_nota_no_alvo(monkeypatch, prometheus):
    """A nota que o `else:` do coletor produzia hoje não pode sumir junto com a sonda."""
    base, falso = prometheus
    monkeypatch.setattr(promql, "alcancavel", lambda *a, **k: False)

    contexto = dict(CONTEXTO, cache={})
    passe = collect.identificar([_componente("app_a", base)], contexto, [promql],
                                collect.Prazo(120))

    assert passe["fontes_mortas"] == [base]
```

- [ ] **Step 8: fazer o adaptador consultar o resultado**

Em `scripts/lib/adaptadores/promql.py`, substitua `familia_do_componente` inteira por:

```python
def familia_do_componente(componente, contexto, pergunta):
    """(família, seletor) para ESTA pergunta — ou (None, None).

    Não identifica mais nada: quem identifica é o passe (`collect.identificar`), e este módulo
    só consulta o resultado. Foi assim que a decisão de papel deixou de ser efeito colateral de
    uma chamada de adaptador, e que o filtro por papel da v0.14.0 pôde sair — a proteção que
    ele dava passou a ser `identifica_papel` mais o casamento de etiqueta.

    A `pergunta` entrou na assinatura porque, sem o filtro, duas famílias casadas podem
    declarar o MESMO id: o desempate vive em `identificacao.familia_da_pergunta`.
    """
    from lib import identificacao

    resolvido = contexto.get("cache", {}).get("resolvido", {}).get(componente.get("nome"))
    if not resolvido:
        return (None, None)
    escolhida = identificacao.familia_da_pergunta(resolvido, pergunta)
    if escolhida is None:
        return (None, None)
    return (escolhida["familia"], escolhida["seletor"])
```

E em `perguntar`, substitua as linhas da resolução por:

```python
    from lib import identificacao

    base = base_de(base)
    familia, seletor = familia_do_componente(componente, contexto, pergunta)
    if familia is None:
        # A alcançabilidade vem do CACHE do passe, não de uma sonda nova. Sondar aqui rodava
        # uma vez por pergunta para todo componente não resolvido, e é a segunda das duas
        # chamadas que a restrição nº 1 manda tirar para o teto `K×(F+1)` valer.
        viva = contexto.get("cache", {}).get("fonte_viva", {})
        if viva.get(base) is False:
            return _sem_dados(pergunta, "a fonte de métrica não respondeu")
        resolvido = contexto.get("cache", {}).get("resolvido", {}).get(componente.get("nome"))
        motivo = identificacao.motivo_da_falta(resolvido, pergunta)
        return _sem_dados(pergunta, motivo or "a fonte respondeu, mas não reconheci a família "
                                              "de métrica deste componente")
```

O ramo `if familia is not None and seletor is None:` **desaparece**: o estado `seletor = None`
não existe mais (o conjunto de famílias só guarda `""` ou um seletor casado), e o motivo da
"soma de todos" passou a vir de `identificacao.motivo_da_falta`.

- [ ] **Step 9: a sonda de alvo deixa de duplicar o passe**

**Atenção:** o bloco `else:` de hoje (docker.py:344-351) tem a sonda **e** a nota
`nao_coletado` com o endereço e o motivo. Trocá-lo por `pass` apagaria a nota, contra o
"Tratamento de erro" do spec — e nenhum teste cobre essa string, então a regressão seria
silenciosa. A nota passou a ser emitida pelo step 5, a partir de `passe["fontes_mortas"]`.

Em `scripts/lib/coletores/docker.py`, **remova o bloco `else:` inteiro** e deixe só o `if not
url:` que já existe. Confirme, antes de remover, que a única coisa no `else:` são a sonda e a
nota — se houver mais alguma coisa, ela fica.

```python
    url = alvo.get("metricas_url")
    if not url:
        nao_coletado.append(report_mod.na(
            "métricas: o alvo não declara `metricas_url` — rode `configurar.py alvos --sugerir` "
            "para ver candidatos e colar um no alvos.toml"))
    # Sem `else`: a sonda e a nota de fonte morta moram no passe de identificação
    # (`collect.identificar`), que faz UMA sonda por fonte, curto-circuita as consultas de
    # família quando ela falha, e devolve as mortas para `coletar_alvo` registrar. Sondar aqui
    # também era a segunda chamada ao mesmo endereço, e furava o teto da restrição nº 1.
```

E remova o import de `promql` do topo do arquivo, que fica sem uso.

- [ ] **Step 10: rodar a suíte inteira**

Rode: `./.venv/bin/python -m pytest -q`
Esperado: muitos testes falham — `familia_do_componente` mudou de assinatura e o filtro saiu.
Ajuste os testes existentes que chamam `familia_do_componente(componente, contexto)` para
passar a pergunta, e os que dependiam do filtro por papel para montar o cache resolvido. **Não
afrouxe nenhuma asserção de garantia** — só os anexos mudam. Rode até ficar verde.

---

## Task 8: papel não confirmado é lacuna de cobertura (D6)

**Arquivos:**
- Alterar: `scripts/lib/cobertura.py`
- Teste: `tests/test_cobertura.py`

**Depende de:** Task 7

- [ ] **Step 1: escrever o teste que falha**

Acrescente ao fim de `tests/test_cobertura.py`:

```python
# ---------------------------------------------------------------- D6: identidade não provada
def test_papel_nao_confirmado_entra_como_lacuna():
    """"Silêncio não é saúde" aplicado à IDENTIDADE. Papel provisório errado faz as perguntas
    erradas, e sem isto a lacuna sai 100% calada: o teto de saúde só olha pergunta com limiar,
    e só `fila.filas` tem."""
    alvo = {"componentes": [
        {"nome": "app_a", "papel": "app", "papel_origem": "padrão", "respostas": []},
        {"nome": "infra_broker", "papel": "fila",
         "papel_origem": "exporter rabbitmq-prometheus", "respostas": []},
    ]}

    saida = cobertura.medir(alvo)

    nao_provados = [m for m in saida["mudos"] if m.get("pergunta") == "<identidade>"]
    assert [m["componente"] for m in nao_provados] == ["app_a"]
    assert "papel" in nao_provados[0]["motivo"]


def test_papel_declarado_nao_e_lacuna():
    """Quem o dono declarou está resolvido: cobrar declaração de quem já declarou é ruído."""
    alvo = {"componentes": [
        {"nome": "infra_broker", "papel": "fila", "papel_origem": "declarado", "respostas": []},
    ]}

    assert [m for m in cobertura.medir(alvo)["mudos"]
            if m.get("pergunta") == "<identidade>"] == []
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: FALHA — `assert [] == ['app_a']`

- [ ] **Step 3: implementar**

Em `scripts/lib/cobertura.py`, dentro de `medir`, no início do laço
`for componente in alvo.get("componentes") or []:`, antes de `catalogo = {...}`:

```python
        # D6 — identidade não provada é lacuna de medição, não detalhe cosmético. Papel
        # provisório errado faz as perguntas erradas, e o teto de saúde não pega isso: ele só
        # olha pergunta com `limiar`, e das 12 perguntas canônicas só `fila.filas` tem uma.
        if componente.get("papel_origem") in (None, "padrão", "imagem"):
            mudos.append({
                "componente": componente.get("nome"),
                "pergunta": "<identidade>",
                "motivo": ("o papel deste componente não foi provado por nenhuma fonte — "
                           "declare `papel` no `[[alvo.componente]]` do alvos.toml, ou aponte "
                           "uma `metricas_url` cujo exporter o reconheça"),
            })
```

- [ ] **Step 4: corrigir o docstring que mente**

No docstring de `medir`, troque a frase sobre os papéis sem pergunta por:

```python
    `perguntadas` conta só o que a skill SABE perguntar para aquele papel. Papel sem pergunta
    registrada (hoje só `observabilidade`) fica fora do denominador: ele é limite da skill, não
    falha de cobertura, e já é reportado em "O que falta declarar". `app`, `banco` e `cache`
    estavam nesta lista e ganharam perguntas na v0.13.0.
```

- [ ] **Step 5: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_cobertura.py -q`
Esperado: PASSA

---

## Task 9: o relatório mostra a origem do papel (D3, D5)

**Arquivos:**
- Alterar: `scripts/build_report.py`
- Alterar: `assets/report-template/template_v3.html`
- Teste: `tests/test_papel_no_relatorio.py` (criar)

**Depende de:** Task 7

- [ ] **Step 1: escrever o teste que falha**

```python
# tests/test_papel_no_relatorio.py
"""O papel chega ao relatório com a origem — pelo mesmo motivo que toda medida chega com a
fonte que respondeu. E quando a evidência CONTRADIZ a imagem, o relatório diz que corrigiu:
é a imagem mentindo, à vista, e isso é informação acionável."""
import build_report


def _componente(**kw):
    base = {"nome": "infra_broker", "papel": "fila", "papel_origem": "declarado",
            "respostas": []}
    return dict(base, **kw)


def test_papel_confirmado_mostra_a_fonte():
    html = build_report._papel_com_origem(
        _componente(papel_origem="exporter rabbitmq-prometheus"))

    assert "confirmado pelo exporter" in html


def test_papel_sugerido_pela_imagem_diz_que_e_palpite():
    html = build_report._papel_com_origem(_componente(papel_origem="imagem"))

    assert "sugerido pela imagem" in html
    assert "confirmado" not in html


def test_contradicao_entre_imagem_e_evidencia_aparece():
    html = build_report._papel_com_origem(
        _componente(papel="fila", papel_origem="exporter rabbitmq-prometheus",
                    papel_da_imagem="banco"))

    assert "a imagem sugeria banco" in html


def test_a_limitacao_do_kind_e_declarada_no_relatorio():
    """D5: saúde e impacto continuam classificando pela imagem. Deixar isso implícito faria o
    relatório dizer duas coisas sobre o mesmo componente sem explicar por quê."""
    assert "classificam pela imagem" in build_report.NOTA_DO_PAPEL
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `./.venv/bin/python -m pytest tests/test_papel_no_relatorio.py -q`
Esperado: FALHA com `AttributeError: module 'build_report' has no attribute '_papel_com_origem'`

- [ ] **Step 3: implementar**

Acrescente a `scripts/build_report.py`, na seção do relatório v3:

```python
NOTA_DO_PAPEL = ("O papel de cada componente vem da série que ele publica, quando alguma fonte "
                 "o reconhece; senão, do nome da imagem, e aí é palpite. A saúde e o impacto do "
                 "alvo <b>classificam pela imagem</b> em qualquer caso — eles não acompanham a "
                 "correção do papel nesta versão.")


def _papel_com_origem(componente):
    """O papel, e de onde ele veio. Toda medida carrega a fonte que respondeu; o papel carrega
    a dele pelo mesmo motivo."""
    papel = _e(componente.get("papel") or "—")
    origem = componente.get("papel_origem") or "padrão"
    if origem == "declarado":
        nota = "declarado no alvos.toml"
    elif origem.startswith("exporter "):
        nota = f"confirmado pelo {_e(origem)}"
        da_imagem = componente.get("papel_da_imagem")
        if da_imagem and da_imagem != componente.get("papel"):
            nota += f"; a imagem sugeria {_e(da_imagem)}"
    elif origem == "imagem":
        nota = "sugerido pela imagem, não confirmado"
    else:
        nota = "sem evidência: nenhuma fonte reconheceu este componente"
    return f'<span class="tag">{papel}</span><span class="pr-o">{nota}</span>'
```

O `papel_da_imagem` que este código compara já é gravado pelo coletor na Task 7, step 5.

- [ ] **Step 4: EMITIR no relatório**

Sem este step, `_papel_com_origem` e `NOTA_DO_PAPEL` existem, são testados e **nunca aparecem
no HTML** — D3 ("o relatório diz que corrigiu") e D5 ("a limitação é declarada no relatório")
não chegam a quem lê.

Em `scripts/build_report.py`, no cartão do componente (hoje
`f'<span class="tag">{_e(componente.get("papel"))}</span>'`), troque por:

```python
                f'{_papel_com_origem(componente)}'
```

E no cabeçalho da seção que lista os componentes, acrescente a nota uma vez:

```python
            f'<p class="nota-legenda">{NOTA_DO_PAPEL}</p>'
```

- [ ] **Step 5: dar CSS à classe nova**

Em `assets/report-template/template_v3.html`, no bloco de CSS acrescentado para as classes do
v3, acrescente:

```css
.pr-o{margin-left:9px;font:400 11.6px/1.4 var(--mono);color:var(--fraco)}
```

- [ ] **Step 6: rodar e confirmar que passa**

Rode: `./.venv/bin/python -m pytest tests/test_papel_no_relatorio.py tests/test_template_conhece_o_que_o_relatorio_emite.py -q`
Esperado: PASSA — inclusive a trava que recusa classe emitida sem regra no template.

---

## Task 10: prova por mutação nas quatro travas (restrição verificável 2)

**Arquivos:**
- Teste: `tests/test_mutacao_do_papel.py` (criar)
- Alterar: `scripts/lib/adaptadores/promql.py` (docstring)

**Depende de:** Task 7, Task 8, Task 9

**Teste verde prova que o teste roda, não que a trava funciona.** Esta task quebra cada trava e
confirma que um teste cai.

- [ ] **Step 1: escrever o teste de mutação**

```python
# tests/test_mutacao_do_papel.py
"""Quebrar cada trava e confirmar que um teste cai.

Das quatro, DUAS são as que importam: sem `identifica_papel` o cAdvisor volta a votar e todo
componente é confirmado `app`; sem `exportador` o papel sai invertido — o container do exporter
vira o produto. Nas duas, as outras travas continuam passando e a suíte fica verde com o
design quebrado.
"""
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]

MUTACOES = [
    ("identifica_papel", "scripts/lib/identificacao.py",
     'if reconhecida.get("identifica_papel") and not componente.get("exportador"):',
     'if not componente.get("exportador"):',
     "tests/test_identificacao.py::test_cadvisor_casa_todo_mundo_e_nao_confirma_ninguem"),
    ("exportador", "scripts/lib/identificacao.py",
     'if reconhecida.get("identifica_papel") and not componente.get("exportador"):',
     'if reconhecida.get("identifica_papel"):',
     "tests/test_identificacao.py::test_container_do_exportador_nunca_recebe_papel_provado"),
    ("familia unica", "scripts/lib/identificacao.py",
     "elif len(votos) > 1:",
     "elif False:",
     "tests/test_identificacao.py::test_duas_familias_que_provam_nao_confirmam"),
    # A quarta trava da restrição 2 é o CASAMENTO DE ETIQUETA. A do prefixo da pergunta é a
    # restrição 5, e fica abaixo — as duas entram, mas não se confundem.
    ("casamento de etiqueta", "scripts/lib/identificacao.py",
     "if len(candidatos) == 1:",
     "if candidatos:",
     "tests/test_seletor_por_componente.py"),
    ("prefixo da pergunta (restrição 5)", "scripts/lib/catalogo.py",
     'if str(id_).split(".")[0] != papel:',
     "if False:",
     "tests/test_catalogo_papel.py::test_pergunta_de_outro_papel_e_recusada"),
]


def _rodar(teste):
    return subprocess.run([sys.executable, "-m", "pytest", teste, "-q"],
                          cwd=RAIZ, capture_output=True, text=True).returncode


def test_cada_trava_sustenta_um_teste(tmp_path):
    for nome, arquivo, original, mutado, teste in MUTACOES:
        caminho = RAIZ / arquivo
        antes = caminho.read_text(encoding="utf-8")
        assert original in antes, f"{nome}: a trava mudou de forma; reveja esta mutação"
        try:
            caminho.write_text(antes.replace(original, mutado, 1), encoding="utf-8")
            assert _rodar(teste) != 0, f"a trava `{nome}` não sustenta nenhum teste"
        finally:
            caminho.write_text(antes, encoding="utf-8")
```

- [ ] **Step 2: rodar a prova por mutação**

Rode: `./.venv/bin/python -m pytest tests/test_mutacao_do_papel.py -q`
Esperado: PASSA. Se falhar com "a trava X não sustenta nenhum teste", **a trava é decorativa** —
escreva o teste que falta antes de seguir.

- [ ] **Step 3: conferir que o docstring que mentia foi embora**

A frase "são duas consultas por família" morava no docstring de `familia_do_componente`, que a
Task 7 substituiu inteiro. Rode `grep -rn "duas consultas" scripts/` e confirme que não há
resultado. Se sobrou em `_valores_da_etiqueta` ou em outro lugar, remova: é **uma** desde a
v0.12.4, quando a confirmação redundante saiu.

- [ ] **Step 4: rodar a suíte inteira e o gate**

```bash
cd ~/.claude/skills/sw-infra-audit && ./.venv/bin/python -m pytest -q
cd /var/www/ai-marketplace && make check
```
Esperado: suíte verde; gate sem nada sensível.

- [ ] **Step 5: conferir a árvore publicada**

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit BUMP=minor
D=$(mktemp -d) && cp -r plugins/sw-infra-audit/skills/sw-infra-audit/. $D/ \
  && cd $D && ~/.claude/skills/sw-infra-audit/.venv/bin/python -m pytest -q
```
Esperado: a suíte inteira passa a partir de um diretório qualquer — é como alguém que clona o
marketplace a recebe.

---

## Ajustes durante a execução

- **2026-10-05 — Task 1 (spike): PASSOU, exit 0.** Nenhum falso positivo além dos que D4 fecha.
  Nenhum produto de verdade (`app_api`, `cache_valkey`, `dados_pg`…) casa a família de outro
  produto. O desenho de D1/D2 fica como está.

  **Mas o resultado é mais largo do que D4 descrevia, e isso muda o peso dela.** `nucleo()`
  reduz `postgres-exporter`, `infra_mysqld-exporter` e `monitoring_node-exporter` todos ao
  mesmo núcleo `"exporter"` — então **toda** família de exporter casa **todo** container de
  exporter, não só o seu. Dois efeitos:
  - um exporter com várias famílias presentes na fonte casa VÁRIAS, cai em "duas famílias → não
    confirma" e já ficaria provisório sozinho;
  - um exporter com só a sua família presente casaria UMA e seria confirmado. É esse que D4
    pega, e é o caso comum em quem roda um exporter por produto.
  D4 continua não-cortável, e agora com a medida do quanto ela segura: 12 casamentos espúrios
  em 5 famílias × 19 nomes plausíveis.

- **2026-10-05 — Task 2, ajuste de plano.** `kind_do_caminho` **pulava** produto sem `kind`
  (`if produto.get("kind") and ...`), então o bloco de `postgres-exporter` nem era considerado e
  `postgres` casava por substring: o exporter herdava `kind = "banco"` e entrava no inventário
  como um banco. "O primeiro que casa vence" não era verdade. Passou a ser: quem casa devolve
  o `kind` que tiver, `None` inclusive. O teste de equivalência dos 21 produtos conhecidos
  continua verde, o que prova que nenhum produto real mudou de classificação.

- **2026-10-05 — Task 3, armadilha do TOML nos fixtures.** `papel` escrito depois de um
  `[cabecalho]` pertence ÀQUELA tabela, não ao topo — três fixtures de teste declaravam o papel
  dentro de `[seletor]` e a validação os recusava com a mensagem errada. Os fixtures passaram a
  declarar antes da primeira tabela. E dois testes em `test_lista_de_varios_campos.py` usavam
  pergunta de `entrada` num fixture de `fila`: a validação nova os recusava antes da asserção
  que eles de fato testam. O `_escrever` ganhou o parâmetro `papel`, e a trava **não** foi
  afrouxada.

- **2026-10-05 — batch 1, o juiz achou dois.** (a) A trava de ORDEM dos blocos cobria só
  `postgres-exporter`: mover `mysqld-exporter` ou `redis-exporter` para o fim do arquivo
  reintroduzia o `kind` herdado com a suíte 1074 verde. O teste virou parametrizado nos cinco
  pares, e a mutação agora derruba. (b) Pior: `mysql-exporter` (sem o `d`) e
  `postgresql-exporter` recebiam `kind = "banco"` **e** escapavam de `e_exportador` — a tabela
  invertida de D4 de volta, e no lado inseguro: não ficavam provisórios, ficavam `banco`
  confirmado. As variantes de nome entraram nas listas `imagem` (dado, não regra sobre palavra
  genérica, que D4 descartou). Fechado: `mysql-exporter`, `postgresql-exporter`, `pg-exporter`
  e `valkey-exporter` agora saem `kind=None, exportador=True`.

- **2026-10-05 — batch 2, um fixture meu provava o contrário do que afirmava.** O teste de
  "vários valores e nenhum casa" usava o componente `cdn_borda` contra os valores
  `["proxy", "borda"]` — e `cdn_borda` tem núcleo `borda`, então ele CASAVA. O teste teria
  passado verde provando o oposto se a implementação estivesse errada. Trocado por um nome que
  não compartilha núcleo com nenhum valor. É a terceira vez neste dossiê que um fixture inventa
  a condição que ele deveria testar.

- **2026-10-05 — batch 2, o juiz achou três travas decorativas.** As três passavam verdes com
  a mutação aplicada: (a) o teste do cache gravava pelo contexto ORIGINAL e lia pela cópia — e
  `collect` chama sempre PELA CÓPIA, então o bug antigo (chave no topo do contexto) também
  sobrevivia àquela ordem; o teste que existia para provar o conserto não provava nada;
  (b) a 2ª chave do desempate (quem prova papel) nunca mudava resultado, porque o fixture dava
  prioridades diferentes e a 3ª chave já decidia — e no catálogo real acontece o mesmo;
  (c) `motivo_da_falta` ignorava a `pergunta` e era estruturalmente incapaz de considerá-la,
  porque `soma_de_todos` guardava só o NOME da família: um componente medido pelo cAdvisor com
  um proxy na soma recebia "o exporter traefik cobre vários componentes" para `app.cpu`,
  pergunta que o traefik nem declara. As três foram consertadas e a mutação agora derruba cada
  uma.

- **2026-10-05 — batch 2, duas melhorias do juiz aceitas.** `promql.base_de` era a MESMA
  expressão de `identificacao.base_da_fonte` escrita duas vezes, e o passe agrupa por aquela —
  duas cópias derivam, e aí um componente é agrupado numa fonte e consultado noutra. Passou a
  delegar. E `reconhecer` acrescentava um campo `etiqueta` que ninguém lê (`resolver` usa
  `familia["seletor"]["etiqueta"]`): removido. `resolver` passou a devolver `papel_anterior`,
  que a D3 precisa para o relatório dizer "a imagem sugeria X".

- **2026-10-05 — limite descoberto no spike, para o spec registrar no fim.** O casamento exige
  que o valor de `job` nomeie o SERVIÇO. Num Prometheus cujo scrape config nomeia os jobs pelo
  PRODUTO (`job="redis"` para um serviço `cache_valkey`), o fork não casa e fica provisório — o
  caso do Objetivo só se realiza quando a descoberta de serviços dá o nome do serviço ao job.
  Não é defeito do desenho: é a honestidade dele, porque casar `valkey` com `redis` exigiria
  saber que um é fork do outro, que é conhecimento de produto por nome — o que o ciclo inteiro
  está tirando da skill. Vale uma linha nos Limites do `SKILL.md` ao fechar.
