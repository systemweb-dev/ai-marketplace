---
titulo: Insights por sistema e remediacao na sw-infra-audit
slug: 2026-09-19-insights-por-sistema-e-remediacao-na-sw-infra-audit
criado: 2026-09-19
estado: concluido
---

# Insights por sistema e remediação na sw-infra-audit

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `plan.md` é o passo a
> passo de execução; `referencias/` guarda o material de apoio.

## Objetivo & outcome

A `sw-infra-audit` hoje responde **"o que existe e em que estado"**. Ela precisa responder
também **"o que está acontecendo"** e **"o que fazer a respeito"** — sem virar uma coleção de
integrações por produto.

Outcome observável: para um alvo com fonte de dados disponível, o relatório sai com pelo menos
um bloco de insight por componente relevante (não `sem dados`), e **todo achado traz passo a
passo de correção e como confirmar que resolveu**.

Referência visual aprovada: `referencias/direcao-visual-analytics.png` e
`referencias/direcao-visual-insights-e-remediacao.png` (dados fictícios).

## O que muda, em uma frase

Um **componente** passa a ser interrogado pelas **perguntas do seu papel**, respondidas por
**adaptadores de protocolo**, cada resposta carimbada com a **fonte** — e cada achado passa a
carregar a remediação vinda de um catálogo versionado.

## Arquitetura

### Vocabulário

| Conceito | Definição |
|---|---|
| **Alvo** | o que já existe: declarado em `docs/infra/alvos.toml`, confirmado com `--confirmar` |
| **Componente** | unidade dentro do alvo: um service do swarm, um endpoint HTTP |
| **Papel** | classificação do componente, derivada do `kind` existente (ver adiante) |
| **Pergunta canônica** | id estável do que se quer saber: `entrada.top_rotas`, `fila.filas_com_acumulo` |
| **Adaptador** | fala **um** protocolo; declara as perguntas que responde e como saber se está disponível |
| **Fonte** | qual adaptador respondeu; vai em cada resposta e aparece no relatório |

### Papel deriva de `kind`, não o substitui

`detect_kind` (`scripts/lib/coletores/docker.py`) devolve hoje `ingress/proxy`, `proxy`,
`api-gateway`, `fila`, `fila/broker`, `banco`, `cache`, `cache/fila`, `busca`,
`observabilidade`, `object-storage` e `app` — e essas strings
são **comparadas literalmente** por `lib/metrics.py` (`STATEFUL`) e `lib/impact.py`
(`CRITICAL_PATH`). Trocá-las quebraria saúde e impacto em silêncio.

Decisão: `lib/papel.py` expõe `papel_de(kind, declarado=None)` — uma tabela de tradução
`kind → papel`, sem tocar em `detect_kind`. Regras:

- `ingress/proxy`, `proxy`, `api-gateway` → `entrada`; `fila`, `fila/broker` → `fila`;
  `cache/fila` → `cache` por padrão (Redis é cache na maioria das instalações);
- papel sem adaptador que fale o protocolo daquele componente (ex.: `fila/broker` de Kafka)
  responde `sem_dados: "nenhum adaptador fala com este componente"` — não fica mudo;
- o alvo pode sobrescrever: `papel = "fila"` no bloco do componente, em `alvos.toml`;
- **teste de consistência**: todo `kind` de `_KINDS` tem papel, e todo papel do catálogo de
  perguntas existe na tabela. Um `kind` novo sem papel **falha o teste**, não vira `app` calado.

### Fluxo por componente

```
alvo confirmado
  └─ coleta de estado (como hoje)
      └─ para cada componente:
          papel_de(kind) → perguntas do papel (ordem declarada, barata → cara)
             └─ adaptadores que respondem a pergunta E estão disponíveis
                 └─ ordenação: prioridade (no arquivo de dados) ▸ id do adaptador
                     └─ resposta { pergunta, fonte, valor } | { pergunta, sem_dados, motivo }
```

**"Disponível"** tem definição fechada: o alvo declara o endereço/credencial que o adaptador
exige **e** a identificação responde dentro do timeout. Qualquer outro caso é `sem_dados` com o
motivo real (`"o alvo não declara admin_url"`, `"401 sem credencial"`, `"timeout"`).

**Empate é proibido.** Cada adaptador declara `prioridade` (inteiro) no seu arquivo de dados;
empate resolve por id do adaptador em ordem lexical. Sem isso, duas fontes equivalentes
produziriam relatórios diferentes para a mesma entrada.

## Catálogo de perguntas (v1)

Papéis atendidos na primeira versão: `entrada`, `fila`, `banco`, `cache`.
`busca`, `storage`, `observabilidade` e `app` existem no vocabulário mas **não têm perguntas
até existir adaptador que as responda** — pergunta sem quem responda só produz `sem dados`.

| Papel | Perguntas |
|---|---|
| `entrada` | `volume_na_janela` · `distribuicao_de_status` · `top_rotas` · `top_dominios` · `serie_por_hora` · `latencia` (p50/p95) · `erros_por_rota` · `rotas_sem_tls` · *(log)* `caminhos_sondados` |
| `fila` | `filas` · `filas_com_acumulo` · `consumidores_por_fila` · `taxa_entrada_saida` · `fila_morta` |
| `banco` | `consultas_mais_caras` · `leitura_vs_escrita` · `cache_hit` · `conexoes` · `maiores_tabelas` · `indices_sem_uso` · `atraso_de_replicacao` · `transacoes_longas` |
| `cache` | `hit_ratio` · `chaves` · `memoria` · `eviccoes` · `persistencia` |

Cada pergunta declara: `id`, `papel`, `titulo` (o que aparece no relatório), `forma`
(`escalar` · `lista` · `serie`), `unidade` e **`limiar`** opcional.

**Limiar é o que liga insight a achado.** Quando a resposta cruza o limiar declarado, nasce um
achado com `regra` própria — `fila_sem_consumidor`, `consulta_sem_indice`,
`replicacao_atrasada`, `cache_com_eviccao_alta` — e o achado puxa a remediação do catálogo.
Sem limiar, a resposta é só informação.

**Janela:** 24 h por padrão, configurável em `config.toml` (`insights.janela = "24h"`), impressa
no relatório. **Top 10** no corpo; a lista completa fica no `report.json`.

## Adaptadores

| id | prioridade | Protocolo | Papéis |
|---|---|---|---|
| `promql` | 30 | Prometheus / exporter | todos |
| `admin_http` | 20 | API de administração do componente | fila, cache, busca |
| `sql` | 20 | cliente de linha de comando do motor | banco |
| `logql` | 40 | agregador de log (Loki e compatíveis) | entrada |

Menor prioridade vence (mais específico primeiro). `promql` é o mais agnóstico e o único que
funciona sem credencial; `admin_http` é o mais frágil e o primeiro a cair em `sem_dados`.

### O conhecimento de produto vive em arquivo, não em código

`references/apis/<familia>.toml` e `references/sql/<motor>.toml`. A **linguagem de extração é
fechada** — não há expressão arbitrária:

```toml
familia = "amqp-mgmt"
prioridade = 20

[identificacao]
caminho = "/api/overview"
exige_chaves = ["product_name"]     # precisam existir no JSON
aceita_401 = true                   # 401 = provável match, falta credencial

[[pergunta]]
id = "fila.filas_com_acumulo"
caminho = "/api/queues"
lista = ""                          # JSON pointer (RFC 6901) para o array; "" = raiz
campos = { nome = "/name", prontas = "/messages_ready", consumidores = "/consumers" }
transformar = { prontas = "inteiro", consumidores = "inteiro" }
ordenar_por = "prontas"
ordem = "desc"
limite = 10
limiar = { quando = "consumidores == 0 e prontas > 0", regra = "fila_sem_consumidor", severidade = "high" }
```

Transformações permitidas, e só elas: `inteiro`, `decimal`, `texto`, `bytes`, `segundos`,
`percentual`, `data_iso`.

**Derivações** (conjunto fechado) cobrem o que é razão entre campos — `hit_ratio`,
`cache_hit`, `leitura_vs_escrita`, memória usada sobre máxima, conexões sobre limite:

```toml
derivar = { hit_ratio = { tipo = "razao", numerador = "/hits", denominador_soma = ["/hits", "/misses"] } }
# tipos: razao · percentual_de · diferenca · soma
```

Expressão de limiar aceita comparação entre **campo (ou derivado) e literal**, combinada por
`e`/`ou` — parser próprio, sem `eval`. Sem aritmética na expressão: o que precisa de conta vira
derivação declarada.

**Regra de ouro:** o que não couber nessa linguagem **não ganha arquivo** — vira adaptador
próprio, com código e teste. É isso que impede o `if produto == …` disfarçado.

### `promql`: catálogo de métricas por família de exporter

Mesmo protocolo não significa mesmo esquema: `traefik_router_requests_total{router=…}` e o
exporter do nginx não expõem as mesmas etiquetas. Por isso o `promql` também tem catálogo de
dados — `references/metricas/<familia>.toml`:

```toml
familia = "traefik"
prioridade = 30

[identificacao]
metrica_presente = "traefik_router_requests_total"   # se a série não existe, a família não é esta

[seletor]
# como amarrar o componente do inventário à série: por etiqueta, em ordem de tentativa
etiquetas = ["service", "job", "instance"]

[[pergunta]]
id = "entrada.top_rotas"
query = 'topk(10, sum by (router) (increase(traefik_router_requests_total{%SELETOR%}[%JANELA%])))'
chave = "router"
valor = "inteiro"
desempate = "chave"        # empate de valor resolve pelo nome da chave, em ordem lexical
```

`%SELETOR%` e `%JANELA%` são as **únicas** interpolações; o resto da query é literal do arquivo.

**Regra honesta sobre rota:** pergunta que depende de etiqueta que a família não expõe responde
`sem_dados: "o exporter deste componente não expõe rota"`. Não se inventa rota a partir de
caminho, nem se cai em outra família silenciosamente. O papel `entrada` tem, portanto, dois
níveis: o que **qualquer** família responde (`volume_na_janela`, `distribuicao_de_status`,
`latencia`) e o que **só algumas** respondem (`top_rotas`, `top_dominios`, `erros_por_rota`).

### `sql` e o runner

`psql`/`mysql` não cabem na allowlist `(noun, verb)` do docker, e `lib/runner.py` é o único
ponto de subprocesso. Decisão: o runner ganha **perfis**.

```python
PERFIS = {
  "docker": {"binario": "docker", "valida": docker_allowlist.check, "env_extra": ()},
  "psql":   {"binario": "psql",   "valida": sql_catalogo.check,     "env_extra": ("PGPASSWORD",)},
  "mysql":  {"binario": "mysql",  "valida": sql_catalogo.check,     "env_extra": ("MYSQL_PWD",)},
}
```

- `ambiente(perfil, context, segredo)` passa a ser **base positiva**: começa vazio, copia só o
  mínimo declarado (`PATH`, `HOME`, `LANG`, `LC_ALL`, `TZ`) e acrescenta o que o perfil pede.
  Hoje (`lib/runner.py`) o ambiente é copiado inteiro menos quatro variáveis — e como a
  credencial vem do ambiente por `senha_env`, `PGPASSWORD` **já estaria** no filho docker.
  Remover quatro não resolve; só a base positiva resolve.
- A fitness function correspondente testa `runner.ambiente()` **diretamente** e captura o
  `subprocess.run` real. O teste atual (`tests/test_restricoes.py`) substitui `runner.run` e
  nunca vê o `env` — ele passa mesmo com o vazamento.
- `sql_catalogo.check` aceita **exclusivamente** SQL que veio do arquivo do motor, identificado
  por id — nada montado em tempo de execução, nada interpolado.

## Credencial, egress e privacidade

- Credencial por alvo no `alvos.toml` (que já vive fora do git, com permissão `600`):
  `senha_env = "NOME_DA_VARIAVEL"`. **O valor nunca fica no arquivo** — é lido do ambiente na
  hora da coleta, vai em header de autenticação (HTTP) ou em variável do perfil (SQL), e nunca
  no argv nem no `report.json`.
- A credencial é amarrada a **(alvo, host, porta)**. Não existe credencial "da rodada".
- **`check_allowed` passa a exigir host E porta**, com a porta implícita do esquema resolvida
  antes da comparação (`http`→80, `https`→443); os chamadores passam `(host, porta)` em vez de
  `[hostname]`. Hoje compara só o hostname
  (`scripts/lib/http_get.py`), então confirmar um host autoriza qualquer porta dele — e este
  design faz quatro adaptadores tentarem portas de administração. Isso seria varredura de portas
  no host declarado, com credencial junto.
- **Redirect (3xx) vira caso explícito.** Hoje `get_com_status` devolve `(301, "")` e o coletor
  http só marca achado em `>= 400`: um endpoint que redireciona sai 🟢. Passa a ter tratamento
  próprio, e a identificação de família ignora corpo vazio de 3xx.
- Sem credencial, a skill **entrega o comando para criar um usuário somente-leitura** (catálogo
  por motor/família) e segue com `sem_dados`.
- Privilégio além de leitura vira **aviso** no relatório (não achado, não bloqueia).
- **IP mascarado por padrão** (`203.0.113.xxx`); `relatorio.ip_completo = true` libera.
- `lib/redact.py` ganha: token em query string, e-mail, IP. Toda resposta de adaptador passa por
  ela antes de virar arquivo.
- Consulta de banco entra **só na forma normalizada**; utility statement e literal em `IN (…)`
  são descartados, não truncados.

## Remediação

Catálogo de dados, um arquivo por regra: `references/remediacao/<regra>.md`, com frontmatter
(`regra`, `titulo`, `severidade_padrao`) e quatro blocos fixos:

1. **Por que importa** — a consequência concreta.
2. **Como resolver** — passos numerados; comando em bloco.
3. **Como confirmar** — o que olhar depois; de preferência a própria auditoria.
4. **Quando NÃO fazer** — o caso em que aquilo é esperado.

**Pré-requisito: um registro explícito de regras.** Hoje os `rule_id` são literais dentro das
funções de `lib/rules.py`, e o coletor http cria as suas (`certificado_vencendo`, `sem_tls`,
`http_fora_do_ar`, `http_resposta_de_erro`) sem passar por lá — não dá para enumerar sem AST.
Nasce `lib/regras.py` com `REGRAS = {id: {severidade_padrao, origem, esperada}}`, alimentado
por todos os produtores; `rule_meta` passa a ser consultado a partir dele. O **id é o nome do
arquivo** de remediação, seja `SEC_PORT_EXPOSED` ou `fila_sem_consumidor` — os dois vocabulários
convivem, o registro é que unifica. Regra marcada `esperada` (o `expected=True` de hoje, como
docker.sock em ferramenta que precisa dele) **não exige** arquivo. O `fix` de uma linha que o
achado já carrega vira o resumo; o catálogo é o detalhe.

O script anexa ao achado (`como_resolver`); o agente pode **enriquecer** (`analise`), nunca
apagar. **Os comandos são para exibir, nunca para executar** — regra explícita no catálogo e na
`SKILL.md`, porque o agente que lê este relatório tem Bash.

## Relatório e schema

- **Sumário** no topo, listando as seções. **Sem número de página**: o Chromium headless não tem
  `target-counter`, e a segunda passada dependeria de um leitor de PDF instalado, gerando saída
  diferente por máquina — o que quebraria o determinismo. Fica como não-objetivo.
- Seções novas: **Tráfego e desempenho**, **Segurança do tráfego**, **Insights por sistema**;
  cada achado com **Como resolver / Como confirmar**.
- `impact.py` volta a ser exibido: hoje `impact.build` roda em `coletores/docker.py` e some
  porque `coletar` só copia uma allowlist de chaves para `fatos`.
- Direção visual: a aprovada em `referencias/`.

**Schema v3:**

```jsonc
{ "schema_version": 3,
  "alvos": [ { "nome": "...", "componentes": [ { "nome": "...", "papel": "fila",
        "respostas": [ { "pergunta": "fila.filas_com_acumulo", "fonte": "admin_http:amqp-mgmt",
                         "valor": [...] },
                       { "pergunta": "fila.fila_morta", "sem_dados": true,
                         "motivo": "o alvo não declara admin_url" } ],
        "achados": [...] } ],
      "achados": [...] } ] }
```

- Achado **nasce no componente** e é **promovido** para `alvos[].achados` com o campo
  `componente` preenchido. `achados_ordenados`, `montar_inventario` e `historico._chaves`
  continuam lendo uma fonte só — a do alvo —, agora com `componente` na chave do histórico.
- A promoção obriga três mudanças que não são opcionais, e o plano precisa listá-las:
  1. `collect.CAMPOS_DO_COLETOR` ganha `componentes` — senão o campo some do relatório
     exatamente como acontece hoje com `impact_points`;
  2. `aceites.aplicar` passa a filtrar **também** `componentes[].achados` — hoje ele só mexe em
     `alvo["achados"]`, e o achado aceito continuaria vivo dentro do componente;
  3. `report.ordenar` passa a ordenar `componentes[]` por nome e `respostas[]` pela ordem
     declarada no catálogo — sem isso a ordem vem do dicionário da coleta e o determinismo cai.
- **Aceite ganha `componente`** (opcional): a chave passa a ser
  `(alvo, componente|∅, regra, objeto|∅)`; ausente = vale para o alvo inteiro, como hoje.
- **Histórico aceita v2 e v3.** Rodada anterior em v2 → diff sai com aviso
  *"formato anterior: comparação limitada a alvo + regra + objeto"*. Nunca sumir calado.
- `build_report` recusa v2 com mensagem, como hoje recusa v1.

## Mudanças de configuração (pré-requisito, não detalhe)

Nada disso funciona sem abrir espaço nos dois arquivos — e os dois têm validação estrita que
**recusa chave desconhecida**, de propósito:

- `lib/config.py`: `PROJETO_PERMITE` ganha `insights` (janela, limites de lista);
  `RELATORIO_PERMITE` ganha `ip_completo`.
- `lib/alvos.py`: nasce o bloco de componente, hoje inexistente —
  `[[alvo.componente]]` com `nome`, `papel` (sobrescreve o derivado), `admin_url`, `metricas_url`
  e `senha_env`. A validação de campo desconhecido continua; só a lista de conhecidos cresce.
- A mensagem "banco chega no plano 2" em `lib/alvos.py` passa a apontar o plano certo.

Isso entra no **plano 1**: sem o schema, nenhum adaptador tem como ser configurado.

## Orçamento, erros e determinismo

- `orcamento_por_alvo` **passa a existir de verdade**: hoje `collect.py` o coloca no contexto e
  nenhum coletor lê. Vira prazo absoluto (relógio monotônico) por alvo; cada pergunta recebe
  `min(timeout_por_pergunta, restante)`; estourou → `sem_dados: "orçamento do alvo esgotado"`.
- Ordem das perguntas é a declarada no catálogo (barata → cara), para o corte por orçamento ser
  previsível.
- Fonte indisponível → `sem_dados` + motivo. **Nunca achado.**
- Exceção inesperada do adaptador → `erro_interno` **daquela pergunta**, e a coleta segue. O
  `except Exception` de `collect.coletar_alvo` retorna cedo e apagaria o inventário inteiro do
  alvo por causa de uma pergunta — o adaptador tem o seu próprio contorno.
- **A janela é ancorada no `--at`**, nunca no relógio de parede: toda consulta calcula o fim da
  janela a partir do carimbo que já é injetado hoje. Sem isso, `serie_por_hora` e `latencia`
  mudariam a cada execução e o teste de determinismo viraria teatro.
- **Desempate obrigatório em toda pergunta de lista.** `sorted` é estável, então empate de valor
  herdaria a ordem do JSON da API — e como o corte é top 10, empate na fronteira mudaria o
  conteúdo do relatório **e os achados de limiar**. Cada pergunta de lista declara `desempate`
  (por padrão, a chave em ordem lexical).
- Determinismo: os **valores** mudam entre coletas (é a natureza do dado); a **estrutura e a
  ordem** não. Com as mesmas respostas gravadas, `report.json` e HTML saem byte a byte iguais.

## Testes

- Fixture por adaptador: servidor HTTP local devolvendo resposta gravada (API de administração,
  Loki), `psql`/`mysql` falsos em `PATH`. **Sem rede e sem infraestrutura real.**
- Prova por mutação nas travas: inverter a checagem de porta, vazar credencial para o report,
  aceitar SQL fora do catálogo, deixar `PGPASSWORD` no ambiente do docker — cada uma precisa
  derrubar pelo menos um teste.
- O teste de segredo existente cobre argv, `report.json` e HTML; passa a cobrir também **o
  ambiente do processo filho e o PDF**.

## Não-objetivos / fora de escopo

Escrever qualquer coisa nos sistemas auditados · alerta contínuo ou monitoramento · Kubernetes ·
**ler linha crua de log** (só agregação) · adivinhar endereço não declarado · número de página no
sumário · dashboard interativo · país e user-agent quando o agregador não os expõe por agregação
(aí é `sem_dados`, não parsing de linha) · papéis `busca`, `storage`, `observabilidade` e
`app` na v1.

## Restrição de simplicidade

A menor solução que resolve: **um registro de perguntas + um registro de adaptadores + um
catálogo de arquivos de dados**. Nada de plugin dinâmico, nada de cache de resposta entre
rodadas, nada de banco de séries próprio, nada de linguagem de consulta nova. Adaptador que não
couber na linguagem fechada vira código com teste — não uma extensão da linguagem.

## Appetite

Quatro ciclos curtos, um por plano; cada plano fecha sozinho e é publicável (a skill continua
funcionando com o que já existe se um plano não for executado).

## MVP vs MLP

MVP no plano 1 (o eixo). O que encanta — insight por sistema com dado real — chega no plano 2.

## Decisões (ADR)

| # | Contexto | Decisão | Alternativas descartadas | Consequência |
|---|---|---|---|---|
| 1 | Interrogar N produtos sem virar N integrações | Pergunta canônica por papel + adaptador por protocolo | Coletor por produto; só métricas | Duas camadas de indireção, extensível sem tocar no núcleo |
| 2 | Saber falar com a API do Rabbit exige saber a rota | Conhecimento por família em **arquivo de dados** com linguagem fechada | `if produto ==` no código | Adicionar produto = escrever arquivo; o que não couber vira código com teste |
| 3 | `kind` já é comparado literalmente por `metrics`/`impact` | `papel` é **derivado** de `kind`, com teste de consistência | Renomear `kind` para `papel` | Nada quebra em silêncio; uma tabela a manter |
| 4 | Duas fontes podem responder a mesma pergunta | `prioridade` declarada + desempate lexical | "vence o mais específico" | Ordem total, determinismo preservado |
| 5 | Log carrega token, e-mail, IP | Só agregador HTTP, só consulta agregada, IP mascarado | Ler log do container | Menos dado disponível; nenhuma linha crua passa pela skill |
| 6 | `psql` quebraria "runner é o único subprocesso" | Runner com **perfis** + allowlist de env por perfil | Subprocesso no adaptador | `PGPASSWORD` não alcança comando docker |
| 7 | Sumário numerado exigiria segunda passada dependente de ferramenta externa | Sumário sem números | Duas passadas com `pdftotext` | Determinismo preservado; o dono aceitou o corte |
| 8 | Remediação escrita pelo agente varia a cada rodada | Catálogo versionado, agente só enriquece | Texto gerado na hora | Mínimo garantido e revisável em PR |

## Restrições verificáveis (fitness functions)

1. **Toda regra que gera achado tem arquivo de remediação.** O teste enumera `lib/regras.py`
   (registro explícito, sem AST) e compara com `references/remediacao/`; regra marcada
   `esperada` fica de fora da exigência.
2. **Nenhum adaptador cria subprocesso nem abre socket.** Extensão do teste existente: só
   `lib/runner.py`, `build_report.py` e `lib/ignorado.py` importam `subprocess`; só
   `lib/http_get.py` importa rede.
3. **Egress exige host e porta declarados.** Inverter a checagem de porta derruba pelo menos um
   teste.
4. **Nenhum segredo em argv, `report.json`, HTML, PDF ou ambiente do processo filho.** O teste
   chama `runner.ambiente()` diretamente e captura o `subprocess.run` real — substituir
   `runner.run`, como o teste faz hoje, não enxergaria o vazamento.
5. **Mesma entrada, mesmo byte:** com as respostas gravadas das fixtures **e o mesmo `--at`**,
   duas execuções produzem `report.json` e `relatorio.html` idênticos — inclusive com empate de
   valor nas listas.

## Cobertura da medição (revisão de 2026-10-03)

> O nome é "cobertura **da medição**" para não colidir com a seção "Cobertura das práticas" que
> o relatório já tem, e que significa outra coisa.

### O problema que isto resolve

Entre 29/09 e 03/10 o cluster passou de 🔴 para 🟢 **sem nada ter melhorado na infraestrutura**.
Os 7 achados `fila_sem_consumidor` desapareceram porque a variável com a senha do broker não
estava no ambiente: a pergunta que os produz não foi respondida, nenhum achado nasceu, e não
havia o que `agravar_saude` agravasse.

A skill registrou a cegueira com honestidade — as 9 perguntas viraram `sem_dados` com motivo
exato. O buraco é que **o veredito não consulta essa informação**.

A skill prega "não consegui ver ≠ está ruim". O inverso — **"não consegui ver ≠ está bom"** —
está desprotegido.

### A medida

`cobertura = respondidas / perguntadas`, onde *perguntadas* conta apenas as perguntas que a
skill sabe fazer para aquele papel (`perguntas.do_papel`).

Papel sem pergunta registrada fica **fora do denominador** (hoje: 49 `app`, 2 `banco`,
2 `observabilidade`, 1 `cache`). Contá-los deixaria a cobertura permanentemente péssima e
portanto inútil — ninguém olha um número que não se move quando se conserta o que dá para
consertar. Esse limite já é reportado em "O que falta declarar".

**Conta como NÃO respondida:** `sem_dados`, `erro_interno`, e — este é o buraco que a revisão
achou — **pergunta com `limiar` cujo valor veio lista vazia**. Hoje `_sem_numero` e
`_sem_contadores` (`collect.py:157` e `:182`, ambos com `or not valor`) devolvem a resposta
intacta: a fonte responde `[]`, a cobertura marca 100%, nenhum achado nasce e o 🟢 se mantém.
É a mesma cegueira por outra porta. Lista vazia em pergunta com limiar vira
`sem_dados: "a fonte não devolveu nenhum item"`.

Três estados, porque zero e indefinido não são a mesma coisa:

| Situação | Cobertura |
|---|---|
| perguntou e não foi respondido | `0%` |
| perguntou e foi respondido | `100%` |
| **não havia o que perguntar** | `sem dados` — nunca `0%` |

**Cobertura NÃO é uma dimensão pontuada.** Ela mora em campo próprio (`alvo["cobertura"]`), não
em `dimensoes`. Entrar como 5ª dimensão quebra o código: `nota.py:93` elegeria `cobertura` como
`pior` sempre que ela fosse baixa, e `nota.py:110` faria `ROTULO["cobertura"]` → **KeyError**
(verificado). Desenhar a 5ª barra na capa é decisão separada, e exige entradas novas em
`ORDEM`/`ROTULO`/`VEREDITO`.

### Efeito no veredito

Cobertura baixa **não pode** pintar o cluster de vermelho — seria o espelho do problema atual.
A regra sai do modelo de dados: cada pergunta canônica declara, ou não, um `limiar`.

| Pergunta sem resposta | Tem `limiar`? | Consequência |
|---|---|---|
| `fila.filas` (→ `fila_sem_consumidor`, `high`) | sim | **um achado podia ter nascido e não nasceu** → a saúde não pode ser 🟢 |
| `entrada.latencia`, `entrada.volume_na_janela` | não | perdeu-se contexto, não achado → derruba a cobertura, não trava o 🟢 |

**Onde isso roda.** Função pura nova, chamada em `collect.main` **ao lado de `agravar_saude`**
(`collect.py:446`) — é lá que `alvo["saude"]` é escrito. A capa apenas **narra** o resultado:
`nota_de_estabilidade` roda em `build_report` e só recebe `dimensoes`, então não pode mudar a
saúde. O design anterior punha a correção nos dois lugares, que é impossível.

**Quatro guardas, todas verificadas contra o código:**

1. **Teto, nunca piso.** Só impede o 🟢; nunca produz 🔴. Mesma disciplina de `agravar_saude`
   ("só agrava: nunca desce").
2. **Só severidade que trava.** `_PIOR_ESTADO` (`collect.py:35`) ignora `low`. Um limiar `low`
   sem resposta não pode travar um 🟢 que o próprio achado não travaria. Trava só quando a
   severidade declarada no limiar mapeia para 🟡 ou 🔴.
3. **Aceite vigente dispensa a trava.** Se a regra daquele limiar já tem aceite válido
   (`aceites.py:22`, casando alvo/componente/regra/objeto), o achado não contaria de qualquer
   forma — travar o 🟢 por ele seria cobrar duas vezes. Aceite **vencido** não dispensa.
4. **Estado fora de `{🟢,🟡,🔴}` não é tocado.** `sem dados` continua `sem dados`; não é um
   estado bom a ser piorado, é ausência de leitura — mesma guarda de `collect.py:56`.

**Orçamento também é cegueira.** `prazo.esgotado()` (`collect.py:208`) produz `sem_dados`, e em
cluster grande isso faz o 🟢 depender de tempo de parede. Aceitamos a consequência: esgotar o
orçamento numa pergunta com limiar trava o 🟢 igual. A alternativa — ignorar — reabre o buraco.

**O 🟡 tem de se explicar.** Um 🟡 sem nenhum achado que o justifique inverte o problema que
`agravar_saude` documenta. A cobertura imprime, na capa e em "O que falta declarar", **qual
componente**, **qual pergunta** e **qual motivo** — reusando o motivo que o `sem_dados` já
carrega.

### Travas, com a mutação que mata cada uma

| Trava | Mutação |
|---|---|
| limiar sem resposta impede 🟢 | ignorar o limiar → a rodada sem fonte volta a sair 🟢 |
| cobertura nunca gera 🔴 | deixar descer → alvo sem fonte vira "fora do ar" |
| `0%` ≠ `sem dados` | denominador zero virar 0% → alvo sem nada a medir vira "cobertura péssima" |
| lista vazia não é resposta | manter o `or not valor` → 100% de cobertura sem medir nada |
| `low` não trava | tirar a checagem de severidade → 🟡 que o achado não produziria |
| aceite vigente dispensa | ignorar o aceite → cobra duas vezes pelo risco já aceito |

### Restrição verificável (nº 6)

**Fixture sintética**, derivada das duas rodadas reais mas com nomes neutros — os `report.json`
de `docs/infra/` são **gitignored e carregam nomes reais de cluster e stack**; usá-los como
fixture da skill publicada contraria o CLAUDE.md e o commit `a7652b6`, além de tornar o teste
irreprodutível em outra máquina. Os arquivos reais ficam só como evidência neste dossiê.

Escrita sem ambiguidade: `teto_por_cobertura(alvo)` devolve **🔴** para a fixture "limiares
respondidos, 7 achados altos" e **🟡** para a fixture "mesmo alvo, `fila.filas` sem resposta" —
e mutar a checagem de limiar faz a segunda voltar a **🟢**.

### Casos decididos (para dois implementadores não fazerem coisas diferentes)

- `erro_interno` conta como **não respondida**.
- Componente que sumiu do inventário entre rodadas **não** zera o denominador: o histórico já
  compara, e zerar devolveria o 🟢 pela mesma cegueira.
- A trava é por **alvo**, não por componente: um limiar sem resposta em qualquer componente do
  alvo já impede o 🟢 daquele alvo.

## Acesso por container (`exec_cli`): decisão ADIADA

Desenhado e **não aprovado** em 2026-10-03. Fica registrado para não ser redescoberto do zero.

**A ideia:** alcançar fila/banco/cache por `docker exec` através do context, sem credencial de
rede — resolvendo o caso em que a fila fica muda por falta da variável de ambiente.

**Por que foi adiado**, depois da revisão independente:

1. **A validação proposta era circular.** O catálogo declarava o binário *e* o verbo, e a
   validação era "binário igual ao declarado". Quem escreve o TOML escolhe `binario = "sh"`,
   `verbo = ["-c", …]` e ganha execução arbitrária como root em container de produção. Uma
   allowlist positiva de binários teria de viver **em Python**, com o TOML escolhendo apenas
   entre entradas que o código já conhece.
2. **O ganho real é menor do que parecia.** `banco`, `cache`, `app` e `observabilidade` têm
   **zero** perguntas canônicas (`perguntas.do_papel` devolve `[]`). O adaptador destravaria
   só a `fila` — um componente, não quatro.
3. **Não resolve o problema que o motivou.** Mesmo com o `exec` funcionando, qualquer falha
   dele devolve o cluster ao 🟢 por cegueira. É a cobertura que resolve isso, e ela não precisa
   de `exec` nenhum.
4. **Em Swarm, responde por sorte do escalonador.** O `exec` só alcança container no nó do
   context: num cluster de 5 nós, acerta em ~1 de 5 rodadas. Isso contraria a restrição de
   determinismo deste mesmo spec.

**Reavaliar depois que a cobertura estiver em produção.** Com o 🟢 por cegueira resolvido, a
pergunta passa a ser só "vale a superfície de segurança nova para destravar uma fila?" — e aí
`admin_url` + `senha_env`, que já existe, pode bastar.

A revisão completa (30 achados, incluindo flags que a lista negativa não pega, falta de contrato
de saída e ausência de redação na saída do CLI) está em `referencias/revisao-exec-cli.md`.

## Revisões do spec

- **2026-10-03** — acrescentada a dimensão de **cobertura** (medida, efeito no veredito e
  travas), motivada por uma rodada real em que o cluster virou 🟢 por cegueira. O **plano 3**
  vira a **cobertura da medição** e o banco desce para plano 4 (tráfego vai para 5) — a
  cobertura não depende de adaptador novo e conserta uma mentira que já está em produção. O
  acesso por container (`exec_cli`), desenhado no mesmo dia, foi **adiado**; os quatro motivos
  estão na seção própria e a revisão completa em `referencias/revisao-exec-cli.md`.
  A segunda revisão independente achou 12 problemas nesta própria seção — entre eles que a
  fixture proposta vazaria nomes reais de cluster para a skill publicada, que cobertura como 5ª
  dimensão quebra `nota.py` com KeyError, e que lista vazia conta como resposta. Todos
  corrigidos antes deste texto.

## Ordem de execução: cinco planos

| Plano | Entrega | Por que nesta ordem |
|---|---|---|
| **1 — eixo** | `lib/papel.py` · `lib/regras.py` (registro explícito) · registro de perguntas · **schema do `alvos.toml` e do `config.toml`** · schema v3 (com as três mudanças da promoção) · adaptador `promql` com catálogo de família · papel `entrada` **nas perguntas que qualquer exporter responde** · `impact.py` de volta ao relatório · sumário · catálogo de remediação para as regras que já existem | É o esqueleto: sem ele nenhum adaptador tem onde encaixar, e sem o schema de configuração nenhum adaptador tem como ser declarado. Entrega valor sozinho: volume, status, latência e **remediação em todo achado** |
| **2 — aplicações que falam HTTP** | `admin_http` + linguagem de extração + derivações + papel `fila` (e `busca`, se houver alvo) | O pedido central — "no rabbitmq pegar as filas" — e o que valida a linguagem de arquivo. **`cache` não entra aqui**: Redis e memcached não têm API HTTP de administração; o papel `cache` é atendido por `promql` quando existir exporter, e um adaptador que fale o protocolo deles fica fora de escopo |
| **3 — cobertura da medição** | Função pura de teto do 🟢 chamada em `collect.main` · campo `alvo["cobertura"]` · lista vazia em pergunta com limiar vira `sem_dados` · o motivo na capa e em "O que falta declarar" | **Entrou em 2026-10-03.** Vem antes do banco porque conserta uma mentira que já está em produção: o relatório assinou 🟢 num cluster com 7 filas paradas, por cegueira. Não depende de adaptador novo |
| **4 — banco** | Perfis no runner com base positiva de ambiente · `sql` · catálogo por motor · papel `banco` | Absorve o plano 2 do dossiê anterior (coletor de banco), que nunca foi executado |
| **5 — tráfego e segurança** | `logql` · `caminhos_sondados` · seção de segurança do tráfego · as perguntas de `entrada` que dependem de rota, para as famílias que as expõem | Depende do papel `entrada` (plano 1) e é o de maior risco de privacidade |

### O que o segundo revisor pediu para cortar, e o que eu mantive

- **Cortado:** `caminhos_sondados` sai da v1 (já era plano 4); papel `cache` sai do plano 2.
- **Mantido `top_dominios`:** é uma etiqueta que as famílias de proxy comuns expõem, custa a
  mesma consulta de `top_rotas` e é justamente o recorte que o dono mostrou como referência.
- **Mantido `indices_sem_uso`:** é uma consulta única no catálogo do motor, sem custo adicional
  de infraestrutura, e é um dos poucos achados de banco com correção óbvia e segura.

## Ciclo 0.14.0 — o caminho único de métrica

O que estava em pé ao fim do 0.13.0: **dois** caminhos falando com o mesmo Prometheus. O
catálogo de famílias (`references/metricas/*.toml`), lido pelo adaptador `promql`, e uma tabela
de consultas escrita no código (`lib/enrich.py`), chamada pelo coletor docker. Os dois pediam
os mesmos números ao mesmo endereço.

O segundo sobreviveu porque o **único consumidor dele era o renderizador anterior** — e
`build()` recusa schema < 3 desde que o relatório virou v3. Ninguém via a saída, então ninguém
notava. É o modo de falha mais barato de produzir e o mais caro de achar: código que roda, custa
requisição na infraestrutura do dono e alimenta nada.

Três coisas tiveram de existir antes de ele poder sair:

1. **Família filtrada por papel.** A família só concorre se responde pergunta do papel do
   componente. Sem isso, um `banco` apontando para o mesmo Prometheus do proxy era identificado
   como o proxy — a série existe lá, afinal — e recebia o número do exporter inteiro.
2. **Valor da etiqueta descoberto, não suposto.** O seletor valia `{etiqueta}="{nome do
   serviço}"`, verdade para o exporter de container e quase nunca para `job`. Dois componentes
   recebiam o MESMO número, cada um carimbado como seu. Agora os valores são consultados
   (`count by (etiqueta) (serie)`) e casados por igualdade ou composição (`<stack>_<serviço>`),
   nunca por substring: `db` dentro de `mariadb` atribuiria a medida do banco errado. Sem
   casamento: um valor só → exporter inteiro, com a fonte dizendo; vários → `sem dados`, porque
   o número sem filtro é a soma.
3. **Lista com vários campos por item.** Uma consulta PromQL devolve um número por série, e o
   limiar de `fila.filas` compara dois campos (`consumidores == 0 e prontas > 0`). Sem isso, o
   papel `fila` só tinha a API de administração, que exige credencial. Agora cada campo é uma
   consulta e elas se juntam pela etiqueta de `chave`.

A trava que vale mais que as três: o carregador **recusa a família que responda pergunta com
limiar sem medir os campos que o limiar compara**. Sem ela, uma família incompleta passaria, os
itens sairiam sem o campo, `_comparar` devolveria False para `None` por desenho, e o achado que
a pergunta existe para produzir nunca nasceria — com a suíte toda verde. É a forma de defeito
que mais se repetiu neste dossiê.

### O que ficou de fora, e por quê

- **Exporter cru (`/metrics` em texto) sem servidor Prometheus.** O `enrich` lia isso, com
  quatro séries hardcoded. As perguntas canônicas são consultas com janela
  (`increase(...[24h])`), e um raspão instantâneo não tem onde avaliá-las. Para voltar a ser
  suportado, cada pergunta precisaria declarar uma série instantânea equivalente — e aí o
  relatório teria de dizer que aquele número é instantâneo, não da janela. Não foi feito porque
  a capacidade alimentava só o renderizador morto: na prática ninguém a perdeu.
- **`fila.taxa_entrada_saida` pelo exporter.** Os contadores existem; os nomes exatos não foram
  conferidos contra um broker com per-object ligado. Série errada não vira `sem dados` — vira
  família que não identifica, em silêncio.
- **O exporter de terceiro do broker AMQP** publica `..._messages_unacknowledged` em vez de
  `..._messages_unacked`. É outra família, um arquivo próprio. Não foi escrito pelo mesmo
  motivo: publicar nome de série por palpite é pior que não publicar.
- **O renderizador v2 (`render_html`) é código morto**, mantido vivo por 15 testes próprios.
  `build()` não o chama. Retirá-lo é limpeza de outro ciclo, não deste.
