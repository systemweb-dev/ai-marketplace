---
titulo: Papel do componente provado pela evidencia, nao pelo nome da imagem
slug: 2026-10-05-papel-do-componente-provado-pela-evidencia-nao-pelo-nome-da-imagem
criado: 2026-10-05
estado: em-execucao
---

# Papel do componente provado pela evidência, não pelo nome da imagem

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `plan.md` é o passo a
> passo de execução; `referencias/` guarda o material de apoio.

Skill alvo: `sw-infra-audit`, em `~/.claude/skills/sw-infra-audit/` (venv em `.venv`).
Publicação: `make sync SKILL=sw-infra-audit BUMP=minor` a partir de `/var/www/ai-marketplace`.
Ciclo anterior: ver "Ciclo 0.14.0 — o caminho único de métrica" no spec do dossiê
`2026-09-19-insights-por-sistema-e-remediacao-na-sw-infra-audit`.

## Objetivo & outcome

O papel de um componente (`entrada`, `fila`, `banco`, `cache`, `busca`, `storage`,
`observabilidade`, `app`) deve ser **provado pela evidência**, não adivinhado pelo nome da
imagem.

**Outcome medível:** a proporção de componentes com papel `confirmado` numa rodada com
Prometheus — hoje é zero, porque a noção não existe. E o fim do caso "fork, imagem interna ou
tag genérica vira `app` e perde as perguntas do papel certo".

**O caso concreto que prova o desenho.** Um fork de cache compatível em protocolo com o
produto original é raspado pelo **mesmo exporter**, e publica a **mesma série**
(`redis_memory_used_bytes`). O `produtos.toml` não conhece o fork pelo nome e o classifica como
`app`; o exporter o identifica como `cache` sem saber que é um fork — porque identifica a
série, não a imagem. É a mesma assimetria que o catálogo de métrica já explora, aplicada ao
papel. Se o desenho não resolver este caso, ele não resolveu nada.

**Por que agora.** A skill documenta, em `lib/catalogo.py` e no cabeçalho de
`lib/adaptadores/promql.py`, que nome de imagem **mente** com fork e tag genérica — e por isso
a família de exporter é identificada pela **série que existe**. O papel é a última coisa que
viola esse princípio, e é a mais consequente: ele decide quais perguntas o componente recebe
e, desde a v0.14.0, quais famílias do catálogo concorrem por ele.

## Exploração & decisões

Três lentes rodadas antes do design.

**Enquadramento (desafiar suposições).** O pedido era "inferir melhor o papel". A suposição
embutida — que o papel deve ser decidido **antes** de falar com as fontes — foi derrubada: ele
só é problema porque virou **portão**. Direção escolhida: inverter.

**Alternativas descartadas, com motivo:**

- *Melhorar a evidência local* (porta publicada, chaves de env, mounts, labels, com pesos
  declarados): troca uma convenção que mente por outra. Porta 5432 não prova Postgres, e
  `DATABASE_URL` aparece em quem **usa** banco, não em quem **é** banco.
- *Sem prova, papel `indefinido`*: honesto e mais duro, mas pioraria a skill para quem não tem
  stack de métricas — um cluster sem Prometheus viraria uma lista de indefinidos.
- *Motor de regras com pesos em arquivo*: a skill já recusou duas vezes linguagem de expressão
  em dado (a gramática de `lib/limiar.py` é mínima e sem aritmética, de propósito; o
  `lib/catalogo_api.py` recusa expressão arbitrária). Expressão em arquivo de dados é código.

**Suposição derrubada por medição.** "Testar toda família contra todo componente é caro" é
falso: a consulta de descoberta `count by (etiqueta) (serie)` depende de `(fonte, família)`, e
não do componente. A medição encontrou, de passagem, um defeito vivo — ver "Defeitos
pré-existentes" abaixo.

**Revisão independente derrubou a primeira versão da regra de confirmação.** Ver "Decisões"
D1: "casamento de etiqueta" sozinho não é evidência de papel.

## Arquitetura

De `imagem → kind → papel → filtra famílias → pergunta`
para `fonte → quem publica lá → casa com os componentes → papel → pergunta`.

### O contrato novo: `reconhecer()`

Cada adaptador passa a saber responder uma pergunta que hoje ninguém faz:

```python
# lib/adaptadores/promql.py
def reconhecer(fonte, contexto):
    """Quem está publicando nesta fonte. UMA consulta por família, não por componente.

    → [{"familia": "traefik", "papel": "entrada", "identifica_papel": True,
        "etiqueta": "job", "valores": ["edge"]}, ...]
    """
```

Só o `promql` implementa agora. O contrato é desenhado para o `admin_http` fazer o mesmo
depois (ele já tem `_cache` no contexto compartilhado e identifica família pelas chaves do
JSON) — implementar isso é **não-objetivo** deste ciclo.

### O orquestrador: `lib/identificacao.py`

Função pura, fora a chamada ao adaptador. Recebe os componentes do alvo e o que cada fonte
reconheceu; devolve, **por componente**, o conjunto de famílias que o cobrem:

```python
{
  "dados_pg": {
     "papel": "banco", "papel_origem": "exporter postgres-exporter",
     "familias": [
        {"familia": "postgres-exporter", "seletor": 'job="dados_pg"'},
        {"familia": "cadvisor", "seletor": 'container_label_com_docker_swarm_service_name="dados_pg"'},
     ],
  },
}
```

É o **único** lugar da skill que casa nome de componente com valor de etiqueta.
`promql.familia_do_componente` deixa de re-derivar e passa a consultar este resultado,
escolhendo, **por pergunta**, a família que declara aquela pergunta.

**Mudança de assinatura, declarada aqui porque o plano precisa dela:**
`familia_do_componente(componente, contexto)` passa a receber também a `pergunta`. Sem ela não
há como escolher por pergunta.

**Desempate, quando duas famílias casadas declaram o MESMO id de pergunta.** Isso é alcançável
com os 7 arquivos de hoje: `postgres-exporter` e `mysqld-exporter` declaram ambos
`banco.conexoes` e `banco.tamanho`; `traefik` e `http-generico` declaram os mesmos três
`entrada.*`. A regra, em duas linhas:

1. vence a família com `identifica_papel = true` — a que provou o papel responde por ele;
2. empate persistindo, vence a `prioridade` do catálogo, que é o critério que já existia.

**Seletor por família no conjunto.** Cada entrada carrega `seletor` com o valor que casou, ou
`""` quando a família foi reconhecida na fonte mas nenhum valor casou aquele componente (a
resposta sai como exporter inteiro, como hoje). Família que não foi reconhecida na fonte
simplesmente **não entra** no conjunto — o estado `seletor = None` de `promql.py` desaparece,
e com ele o ramo `familia is not None and seletor is None`, cujo motivo passa a ser produzido
pelo orquestrador.

**Por que o conjunto, e não um par.** Um Postgres coberto por cAdvisor *e* postgres-exporter
precisa legitimamente dos dois: um responde `app.*`, o outro `banco.*`. Com um par só, e sem o
filtro por papel, a ordem de `catalogo.familias()` (`prioridade`, depois nome) faria o Postgres
casar `cadvisor` — que vem antes de `mysqld`/`postgres`/`redis` em ordem alfabética na
prioridade 40 — e `banco.conexoes` voltaria "o exporter cadvisor não expõe o dado desta
pergunta". Correto no formato, errado no fato.

### O que o `produtos.toml` vira

Palpite, não autoridade. Continua dando papel **provisório**, que escolhe perguntas e **não
bloqueia nenhuma família**. O filtro por papel introduzido na v0.14.0
(`promql.familia_do_componente`) é **removido**; a proteção que ele dava passa a ser a
declaração `identifica_papel` (D1) mais o casamento de etiqueta.

## Decisões (ADR)

### D1 — Família declara se ela prova papel (`identifica_papel`)

**Contexto.** A primeira versão da regra era "confirma quando a etiqueta casa e só uma família
casa". A revisão independente derrubou isso, e a verificação confirmou: `cadvisor` tem
`etiqueta = "container_label_com_docker_swarm_service_name"`, cujo valor **é** o nome do
serviço no Swarm. `casar_valor_da_etiqueta` casa por igualdade exata, então **todo** componente
do cluster casa cAdvisor. Medido: 5 de 5 num cluster de teste.

Consequências da regra antiga: ou nada confirma nunca (todo componente casa duas famílias), ou
— pior — um componente cujo exporter real tem outro nome de job casa **só** o cAdvisor, uma
família, com casamento de etiqueta, e recebe papel `app` **confirmado**. O caso que motivou o
ciclo (um fork de cache cujo scrape job não repete o nome do serviço) passaria a falhar com
carimbo de autoridade. Vale o mesmo para `http-generico`, que identifica por
`http_requests_total` — métrica que qualquer aplicação instrumentada publica: sem o filtro, uma
API viraria `entrada` confirmado e mudaria de camada na topologia.

**Decisão.** Cada arquivo de família declara:

```toml
papel = "entrada"
identifica_papel = true    # esta série PROVA o papel de quem a publica
```

- `identifica_papel = true` — a série é assinatura do produto: `rabbitmq_queue_messages_ready`
  só existe em broker, `pg_stat_database_numbackends` só em Postgres. Famílias: `traefik`,
  `rabbitmq-prometheus`, `postgres-exporter`, `mysqld-exporter`, `redis-exporter`.
- `identifica_papel = false` — a série é **sonda de medida**, não asserção de papel.
  Famílias: `cadvisor` (mede qualquer container), `http-generico` (mede qualquer coisa que
  fale HTTP). Elas **medem e não votam**.

`catalogo.carregar_arquivo` valida: `papel` é obrigatório, tem de estar em `papel.PAPEIS`, e
**todo** id de pergunta do arquivo precisa ter aquele prefixo. Hoje nenhuma família mistura
prefixos (verificado nos 7 arquivos), mas `papel.POR_KIND` já prevê `cache/fila` — a família
multi-papel vai existir, e a validação é o que faz isso doer no carregamento e não no
relatório.

**Alternativas descartadas.** *Derivar o papel do prefixo do id da pergunta* (a primeira
versão): não distingue "prova papel" de "mede qualquer um", que é exatamente a distinção que
falta. *Desempatar pela `prioridade`*: ela foi escrita para ordenar identificação, não para
arbitrar papel; e com `identifica_papel` o empate quase não acontece mais.

**Consequências.** Conhecimento de produto continua em arquivo de dados — a trava AST em
`tests/test_produto_nao_mora_no_codigo.py` segue verde. O formato dos 7 arquivos muda de uma
vez, com o validador recusando quem não declarar.

### D2 — Precedência do papel

| Origem | Quando | Carimbo |
|---|---|---|
| `declarado` | `papel` no `[[alvo.componente]]` | vence sempre |
| `exporter <família>` | **uma** família com `identifica_papel = true` casa a etiqueta | confirmado |
| `imagem` | `produtos.toml` reconhece o trecho | provisório |
| `padrão` | ninguém reconhece | provisório, `app` |

**A declaração vence o PAPEL, não a identificação.** O componente declarado passa pelo passe
normalmente — é ele que produz `(familia, seletor)`, sem o qual nenhuma pergunta é respondida.
E não haveria economia em pulá-lo: a consulta é por `(fonte, família)`, não por componente.

### D3 — Bordas

- **Duas famílias com `identifica_papel = true` casam o mesmo componente** → não confirma.
  Fica provisório e entra em "o que falta declarar", nomeando as duas. Carimbar palpite de
  autoridade é pior que não carimbar.
- **A evidência contradiz a imagem** → o confirmado vence, e o relatório **diz que corrigiu**:
  `papel: fila (confirmado pelo exporter; a imagem sugeria banco)`. É a imagem mentindo, à
  vista — informação nova e acionável.
- **Série existe mas a etiqueta não nomeia o componente** → a resposta sai do exporter inteiro
  com `(exporter inteiro)` na fonte, como hoje, e o papel **não** é promovido. Medir não é
  provar.
- **Sem `metricas_url`, ou alvo sem Prometheus** → tudo provisório, saída idêntica à de hoje.

### D4 — O container do exportador nunca recebe papel provado

**Contexto.** Três das cinco famílias que provam papel são exporters **standalone**
(`postgres-exporter`, `mysqld-exporter`, `redis-exporter`). No Swarm eles são serviços, logo
são componentes do inventário — e a etiqueta `job` normalmente nomeia o **exporter**, não o
produto que ele observa. Verificado com `casar_valor_da_etiqueta`:

| Componente | Casa `["postgres-exporter"]`? | Papel que receberia |
|---|---|---|
| `<stack>_postgres-exporter` (o exporter) | **sim** | `banco` **confirmado** |
| `<stack>_pg` (o banco de verdade) | não | provisório |

O resultado é **perfeitamente invertido**: carimba o exporter como sendo o banco e deixa o
banco sem identidade. A causa é `casar_valor_da_etiqueta`, que reduz `<stack>_postgres-exporter`
e `postgres-exporter` ao mesmo núcleo `"exporter"` e casa por ele.

**Decisão.** `references/produtos.toml` ganha `exportador = true` nos produtos que são
exporters e agentes (cadvisor, node-exporter, promtail e os já marcados `socket_esperado` que
forem desse tipo). Componente que case um produto assim **nunca** é confirmado por evidência:
fica provisório.

É um filtro **negativo**, e é isso que o torna seguro: errar por omissão (um exporter que
ninguém listou) deixa algo provisório, que é o estado de hoje; nunca carimba errado. Mesma
forma do `socket_esperado`, que já existe no mesmo arquivo e pelo mesmo motivo.

**Alternativa descartada.** Recusar casamento cujo núcleo seja uma palavra genérica
(`exporter`, `metrics`, `agent`): pegaria também o exporter não listado, mas é regra sobre
PALAVRA, e é justamente disso que o ciclo está tirando a skill.

### D5 — Papel confirmado NÃO corrige `kind`

**Contexto.** `lib/metrics.py` (`STATEFUL`) e `lib/impact.py` (`CRITICAL_PATH`) comparam
`servico["kind"]`, derivado da imagem dentro do coletor. O docstring de `lib/papel.py` avisa
que renomear aquelas strings quebra saúde e impacto em silêncio.

**Decisão.** `kind` continua vindo da imagem. O papel confirmado não o reescreve.

**Consequência, que entra no relatório como texto:** o cartão pode dizer "papel: fila
(confirmado pelo exporter; a imagem sugeria app)" enquanto a saúde e o impacto do alvo
continuam classificando aquilo pela imagem. Essa limitação é **declarada no relatório**, não
deixada implícita. Corrigir o `kind` é outro ciclo, com raio de explosão em saúde e impacto.

### D6 — Papel não confirmado é lacuna de medição

**Contexto.** A primeira versão do design afirmava que papel provisório errado seria pego pela
cobertura e viraria teto de saúde. Falso, e a citação precisa ser exata para o plano não mexer
na função errada: quem tem `if not limiar: continue` é `teto_por_cobertura` (linha 103), **não**
`cobertura.medir`. E só `fila.filas` tem limiar, de 12 perguntas canônicas — ou seja, o **teto
de saúde** cobria um décimo segundo do problema.

`cobertura.medir` já registra em `mudos` toda pergunta sem resposta, com ou sem limiar; o que
falta nela é contar a **identidade não provada**, que não é pergunta nenhuma.

**Decisão.** `cobertura.medir` passa a contar componente com papel **não confirmado** como
lacuna, do mesmo jeito que já conta pergunta sem resposta — "silêncio não é saúde" aplicado à
identidade. Ele aparece em "o que falta declarar" com a sugestão de declarar o papel.

**Não decidido aqui:** se isso impõe teto de saúde. O teto existente é por severidade de
limiar; papel não confirmado não tem severidade. Entra como contagem e texto, não como teto.

## Fluxo de dados

1. `coletar_alvo` monta os componentes com papel **provisório** (`produtos.toml` ou declarado).
2. **Passe de identificação**, por FONTE distinta do alvo (`alvo["metricas_url"]` mais todo
   `componente["metricas_url"]` declarado — K fontes):
   a. `promql.alcancavel(fonte)` **uma vez**. Não responde → a fonte inteira vira
      `nao_coletado` com motivo, e as F consultas de família são **curto-circuitadas**.
   b. `promql.reconhecer(fonte)` → F consultas `count by (etiqueta) (serie)`, uma por família.
3. `identificacao.resolver(componentes, reconhecidos_por_fonte)` → papel, origem e conjunto de
   famílias por componente. Pura, testável sem rede.
4. `responder()` faz as perguntas do papel **resolvido**, e `familia_do_componente` consulta o
   resultado em vez de re-derivar.

**O orçamento precisa existir antes do passe.** Hoje o `Prazo` é construído em
`collect.py:370`, depois de o coletor já ter rodado. O passe gasta orçamento antes da primeira
pergunta, então ele precisa de um `Prazo` criado antes do laço de `responder` — sem isso, o
item "orçamento esgotado durante o passe" em Tratamento de erro não tem como acontecer.

## Defeitos pré-existentes que entram neste ciclo

Entram porque o design depende deles, não por oportunismo.

1. **O cache de família não funciona.** `familia_do_componente` grava em
   `contexto.setdefault("_familia_por_base", {})`, mas `collect.py:236` faz
   `contexto_pergunta = dict(contexto, ...)` — uma cópia por pergunta — e a chave morre com
   ela. Medido numa rodada de ponta a ponta: a mesma consulta de identificação roda 3× para o
   mesmo componente. `collect.py:234-238` já cria `contexto["cache"]` compartilhado de
   propósito, e `admin_http._cache` o usa corretamente: é o molde. A chave passa de
   `(base, nome)` para `(base, familia)`.
2. **Dois docstrings mentem.** `familia_do_componente` diz "são duas consultas por família" (é
   uma desde a v0.12.4, quando a confirmação redundante saiu). `cobertura.medir` lista
   **quatro** papéis como sem pergunta registrada — `app`, `banco`, `cache` e
   `observabilidade`. Os três primeiros têm pergunta desde a v0.13.0; `observabilidade`
   continua legitimamente sem nenhuma (ver `lib/perguntas.py`), e por isso **permanece** no
   docstring corrigido.

## Tratamento de erro

- **Fonte não responde** → `nao_coletado` no alvo, com o endereço e o motivo; componentes
  daquela fonte ficam com papel provisório. Nunca vira achado — "não consegui ver ≠ está ruim".
- **Fonte responde e nenhuma família é reconhecida** → provisório, e o motivo de cada pergunta
  continua sendo "a fonte respondeu, mas não reconheci a família de métrica deste componente".
- **Arquivo de família sem `papel`/`identifica_papel`** → `CatalogoInvalido` no carregamento,
  não no relatório.
- **Orçamento esgotado durante o passe** → as fontes restantes não são sondadas e seus
  componentes ficam provisórios, com o motivo do prazo.

## Testes

Contra o Prometheus falso que responde pela **consulta recebida** (nunca igual a tudo — servidor
que responde igual esconde a query errada). Sem rede, sem infraestrutura real.

| Teste | O que prova |
|---|---|
| Banco apontando para fonte com séries de proxy não vira `entrada` | a regressão que o filtro por papel protegia, agora protegida por `identifica_papel` |
| cAdvisor casa todo componente e **não** confirma ninguém | D1 — o achado que derrubou a primeira versão |
| `http-generico` casando uma API não a promove a `entrada` | D1, na direção mais provável de falso positivo |
| Imagem desconhecida publicando série de broker → `fila` confirmado | o caso que motiva o ciclo |
| Fork de cache (nome fora do `produtos.toml`) raspado pelo exporter do original → `cache` confirmado | o caso concreto do Objetivo, ponta a ponta |
| `produtos.toml` diz `banco`, exporter prova `fila` → `fila`, e o relatório diz que corrigiu | D3 |
| Duas famílias que provam papel casam → provisório + pendência | D3 |
| Postgres coberto por cAdvisor + postgres-exporter responde `app.*` E `banco.*` | o conjunto de famílias, não o par |
| Componente declarado passa pelo passe e recebe `(familia, seletor)` | D2 — declaração vence o papel, não a identificação |
| Container do exporter **não** recebe papel confirmado; o produto observado por ele não é prejudicado | D4 — o falso positivo invertido |
| Cluster com um proxy só continua recebendo a medida `(exporter inteiro)` | não-regressão do caso legítimo (`tests/test_medida_do_exporter_inteiro.py`) |
| Duas famílias declaram a mesma pergunta → responde a que prova papel | o desempate |
| Motivo do `sem_dados` continua "não reconheci a família" quando é esse o caso | o motivo não pode degradar em escala sem o filtro |
| Sem `metricas_url` → saída idêntica à de hoje | não-regressão para quem não tem Prometheus |
| Fonte morta: uma sonda, não F | orçamento |

**Prova por mutação, nas quatro travas:** afrouxar o casamento de etiqueta; afrouxar "família
única"; afrouxar `identifica_papel`; afrouxar `exportador`. **As duas últimas são as que
importam** — sem `identifica_papel`, as duas primeiras passam com o cAdvisor votando; sem
`exportador`, passam com o papel invertido. Nos dois casos, a suíte fica verde e o design está
quebrado.

## Restrições verificáveis

1. Numa rodada com K fontes distintas e F famílias no catálogo, o total de consultas de
   identificação é **no máximo K×(F+1)** — uma sonda `alcancavel` por fonte mais F consultas
   `count by`, e **menos** quando a sonda falha e as F são curto-circuitadas. É teto, não
   igualdade. Hoje o número é proporcional a componentes × perguntas.
   Para o teto valer, duas chamadas existentes precisam passar a consultar o resultado do
   passe em vez de sondar por conta própria: a sonda de alvo em `coletores/docker.py:346-351`
   e o `alcancavel(base, contexto)` que `promql.perguntar` faz **por pergunta** quando a
   família não foi resolvida. Enquanto elas existirem em paralelo, o teto é furado e a
   restrição não dá para checar.
2. Papel só é `confirmado` com casamento de etiqueta **e** família única **e**
   `identifica_papel = true` **e** o produto casado não marcado `exportador = true`. Afrouxar
   qualquer uma das quatro derruba um teste.
   **Duas delas são as que importam na prova por mutação**, porque sem elas as outras passam
   com a suíte verde: `identifica_papel` (sem ela o cAdvisor vota e tudo quebra em silêncio) e
   `exportador` (sem ela o papel sai invertido — o exporter vira o produto).
3. Papel declarado no `alvos.toml` nunca é sobrescrito, nem com evidência em contrário — e o
   componente declarado ainda recebe `(familia, seletor)`.
4. `tests/test_produto_nao_mora_no_codigo.py` continua verde: nenhum literal de nome de produto
   entra no código.
5. Todo arquivo em `references/metricas/` declara `papel` e `identifica_papel`, e todo id de
   pergunta do arquivo tem o prefixo daquele papel — validado no carregamento.

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| As 5 famílias `identifica_papel = true` têm séries específicas do produto | falso positivo de papel confirmado, com autoridade | conferido: as 5 séries são específicas. O risco NÃO estava na série e sim no **valor da etiqueta** — ver D4, onde ele foi encontrado e fechado |
| Nenhum outro componente casa a etiqueta de uma família sem ser o produto dela | papel confirmado errado, em outra forma que D4 não cobre | rodar `casar_valor_da_etiqueta` contra nomes de componente plausíveis × os valores de `job` típicos de cada uma das 5 famílias, e contar os casamentos inesperados |
| Um componente é coberto por no máximo uma família que prova papel | a pendência de "duas famílias" dispara com frequência e vira ruído | rodar o passe contra o catálogo atual com nomes de componente plausíveis e contar |
| O passe cabe no orçamento do alvo | alvo com muitas fontes esgota o prazo antes da primeira pergunta | medir K×(F+1) com a sonda por fonte e o curto-circuito |

## Não-objetivos

- Inferir papel por porta publicada, chave de env, mount ou label — descartado na exploração.
- Motor de regras com pesos em arquivo de dados.
- Implementar `reconhecer()` no `admin_http`. O contrato é desenhado para ele; a implementação
  é outro ciclo.
- Remover o `references/produtos.toml`. Ele continua, rebaixado a palpite.
- Corrigir o `kind` a partir do papel confirmado (D5), e portanto mexer em `metrics.STATEFUL`
  ou `impact.CRITICAL_PATH`.
- Teto de saúde a partir de papel não confirmado (D6 entra como contagem e texto).
- **Apertar o fallback de "exporter inteiro"** para quando um só componente aponta para a
  fonte. Estava no design e foi **cortado depois da revisão**, por dois motivos verificados:
  (a) `coletores/docker.py:381` dá `metricas_url` a TODO serviço do alvo, então a condição
  nunca seria verdadeira num Swarm com mais de um serviço — implementado ao pé da letra,
  deletaria a resposta de exporter inteiro inclusive para o cluster-com-um-proxy-só que ela
  existe para atender; (b) o dano que a motivava já está mitigado: `build_report._instrumentos`
  desenha a medida **uma vez só**, nomeando os componentes que ela cobre, e `cobertura.medir`
  deduplica por `(pergunta, valor, fonte)`.
- Mexer no renderizador v2 (`build_report.render_html`), que `build()` não chama.

## Restrição de simplicidade

A menor solução que resolve: um campo novo por arquivo de família, uma função `reconhecer()`
num adaptador, um módulo orquestrador puro, uma deleção (o filtro por papel) e uma correção de
cache. **Não construir agora:** abstração de "fonte de evidência" plugável, pontuação de
confiança, cache em disco entre rodadas, nem reconhecimento para adaptador que ainda não existe.

## Appetite

Um ciclo do tamanho do 0.14.0 — que entregou o catálogo por família, o seletor por componente e
a lista de vários campos. Se passar muito disso, o corte é D6: ele melhora o
resultado mas não é o que torna o papel provado. D4 **não** é cortável — sem ela o ciclo
entrega papel confirmado invertido, que é pior que o estado atual.

## MVP vs MLP

MVP. O valor é a correção da classificação; o encanto viria de mostrar a correção bem no
relatório, e isso já está coberto por uma linha de texto em D3.

## Rollout e reversibilidade

Skill publicada em marketplace público, sem migração de dado e sem estado persistido entre
rodadas — o `report.json` de rodadas antigas continua legível, e o `historico.comparar` usa
chaves que não mudam.

Mudança visível para quem já usa: componente com papel **errado** pela imagem passa a ter o
certo, as perguntas mudam, e a comparação com a auditoria anterior mostra movimento numa
rodada. É o efeito desejado — e por isso o relatório diz "confirmado pelo exporter; a imagem
sugeria X" em vez de trocar em silêncio.

Caminho de volta: bump de versão para trás no marketplace. Não há flag, e não vale construir
uma — a skill é lida por rodada, não mantém processo no ar.
