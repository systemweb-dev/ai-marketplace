---
name: sw-infra-audit
description: >-
  Audita a infraestrutura de forma READ-ONLY e gera um relatório técnico (HTML + PDF opcional)
  com inventário, nota geral, problemas agrupados, blocos por tipo de sistema e riscos aceitos.
  Trabalha por ALVOS: cluster Docker
  (context/Swarm) e endpoint HTTP (saúde + validade do certificado). Use SEMPRE que o usuário
  quiser um raio-x da infra ou de parte dela — "audita minha infra", "como está o cluster",
  "o que pode cair primeiro", "relatório da infraestrutura", "esse certificado vence quando?",
  "a API está no ar?", "o que eu tenho rodando e onde", "saúde do swarm", "como o traefik está
  roteando", "analisa meu cluster", "auditar o docker context X", "relatório do cluster",
  "o cluster está ok?", "como está a fila/o banco". Dispare mesmo sem a palavra "auditar" — basta a intenção de entender o ESTADO
  ATUAL da infraestrutura. É SÓ LEITURA: nunca altera, reinicia, escala nem cria nada; nunca
  expõe valor de secret, senha ou string de conexão; só fala com alvo que você declarou e
  confirmou na rodada. NÃO use para deploy, para mexer em serviço/stack, nem para código de
  aplicação. Substitui a sw-cluster-audit. Interação e relatório em português (PT-BR).
---

# Infra Audit — raio-x read-only por alvos

Tira uma **fotografia técnica** do que você tem rodando — cluster Docker, endpoint HTTP — e gera
um relatório em `docs/infra/<data_hora>/`. **Os fatos vêm de comandos read-only e regras
determinísticas; a interpretação é sua (agente).**

**Anuncie no início:** "Estou usando a skill sw-infra-audit para auditar a infraestrutura."

## Regra: toda decisão é via AskUserQuestion

**Toda pergunta ao usuário usa `AskUserQuestion` (menu clicável) — nunca pergunta em texto
solto, e nunca termine um turno com pergunta escrita.** Numa auditoria isso não é preferência
de interface: quem responde está decidindo **em que máquina de produção você vai tocar**, e
opção clicável com o alvo escrito por extenso erra menos que texto livre.

Vale em todos os pontos de decisão desta skill:

| Momento | O que perguntar |
|---|---|
| **Confirmar os alvos** (obrigatório, antes de qualquer conexão) | quais alvos entram nesta rodada, com nome, tipo e **onde** |
| Sem `alvos.toml` | criar o primeiro com `configurar.py migrar`? |
| Pasta do relatório fora do `.gitignore` | acertar agora com `configurar.py ignorar`? |
| **Componente calado** (passo 3b, antes de interpretar) | declarar a fonte agora — `metricas_url` para proxy e aplicação, `admin_url` + `senha_env` para fila — para o relatório sair com medida em vez de rótulo? |
| Achado que o dono já conhece | registrar como risco aceito, com motivo e prazo? |
| Aceite vencido no relatório | renovar, deixar vencer ou resolver o achado? |
| **Opções da rodada** (sempre, junto da confirmação dos alvos) | horas de acessos, top de sites e URLs, tempo de coleta — cada uma com o padrão como primeira opção |
| **No fim** | gerar o PDF também? |

Para resposta aberta (um motivo de aceite, um endereço), ofereça as opções prováveis e conte
com o campo **"Other"**. A exceção é o usuário descrevendo livremente o que quer — aí ele está
dirigindo, e forçar menu atrapalha.

**Nunca pergunte o que dá para descobrir sozinho.** Qual é o context, quantos nós tem, se há
exporter respondendo: isso a skill lê. Pergunta serve para **decisão e autorização**, não para
suprir leitura que você não fez.

## Garantias inegociáveis

- **Nada é alterado.** Só comandos de leitura, por allowlist.
  `exec` só para leitura, comando fixo do catálogo, sem shell. Tudo o mais continua proibido:
  `rm/kill/restart/create/update/scale/prune`, `logs`, `cp`, `secret inspect`.
- **Nenhum segredo sai.** O relatório mostra **nomes** de secrets e **chaves** de env, nunca
  valores, nunca string de conexão. A senha de um alvo nunca é gravada em lugar nenhum. Texto do
  agente e comando também são redigidos: flag, variável, `Authorization`, `-p` do mysql e URL com
  senha saem com `***`, enquanto `$SENHA` e nomes sem valor ficam como estão.
- **Egress fechado.** Só se fala com host declarado no `alvos.toml` **e** confirmado na rodada.
- **Não consegui ver ≠ está ruim.** Falha de acesso vira `nao_coletado` com motivo, nunca achado,
  e a dimensão fica sem nota.
- **Auditar não escreve** fora da pasta da execução. Quem escreve configuração é o modo
  configurar, e só com aprovação.
- **Comando de remediação é para EXIBIR, nunca para executar.** O relatório traz o passo a
  passo e o comando pronto; quem decide aplicar é o dono, depois de ler o "quando não fazer".
  Você não executa nada do catálogo de remediação — nem quando parecer óbvio.
- **Número sem fonte não existe.** Todo insight carrega o adaptador que respondeu; o que não
  foi respondido aparece com o motivo, nunca como zero.

## Antes de tudo

```bash
python3 <skill-dir>/scripts/configurar.py config --explicar
```

Mostra a configuração efetiva e **de onde veio cada valor** — são três camadas: `default.toml`
(padrões da skill) < `docs/infra/alvos.toml` (os alvos deste projeto, na mesma pasta do
relatório, que fica fora do git) < `docs/infra/config.toml` (do projeto, **versionado**).

**Tudo da skill vive em `docs/infra/`** — alvos, configuração do projeto e os relatórios de
cada rodada. O `.gitignore` esconde o conteúdo da pasta e **reabre só o `config.toml`**:

```gitignore
docs/infra/*
!docs/infra/config.toml
```

A forma antiga (`docs/infra/`) ignora o diretório inteiro e nenhuma negação resgata um arquivo
lá dentro — por isso `configurar.py ignorar` **substitui** essa linha quando a encontra.

A skill confere com `git check-ignore` antes de ler ou escrever o `alvos.toml`: pasta fora do
`.gitignore`, ela **recusa** — arquivo de conexão versionado é conexão publicada. Se
`relatorio.pasta` mudar, alvos e relatórios acompanham (duas pastas seriam duas verdades); o
`config.toml` é o ponto de entrada e por isso o caminho dele é fixo.

**O arquivo versionado nunca define conexão.** Ele só escolhe quais alvos entram, ajusta
severidade e registra aceites. Host, porta, usuário e credencial vivem só no `alvos.toml` — se o
`config.toml` trouxer uma dessas chaves, a auditoria para e diz qual.

Sem `alvos.toml`, **pergunte via `AskUserQuestion`** se cria o primeiro com
`configurar.py migrar`: ele cria a pasta, garante a linha no
`.gitignore` e escreve o primeiro arquivo — trazendo o conteúdo do antigo
`~/.config/sw-infra-audit/alvos.toml` quando ele existir, ou partindo dos seus contexts docker.
**Nunca sobrescreve** um existente.

## Insights por sistema

Cada componente do alvo (um serviço do swarm, um endpoint) recebe um **papel** — `entrada`,
`fila`, `banco`, `cache`, `busca`, `storage`, `observabilidade`, `app` — derivado da imagem e
sobrescrevível no `alvos.toml`.

O que a skill sabe **por nome de imagem** vive num arquivo só, `references/produtos.toml`: o
tipo do serviço, quem monta o `docker.sock` por desenho, quem só OBSERVA os outros, em que porta
cada produto expõe métrica e como ele publica rota em label do Docker. Acrescentar um produto é escrever um bloco. Repare na assimetria, que é deliberada: o
catálogo de **métrica** identifica pela série que EXISTE, porque nome de imagem mente com fork
e tag genérica; aqui o nome é o único sinal, porque antes de falar com qualquer fonte a skill
precisa saber que perguntas fazer — e essa derivação virou **palpite provisório**: quem
responde pela série CORRIGE o papel, e o relatório diz de onde cada um veio. É o elo fraco
reconhecido do inventário — e por isso o que
você declara vence sempre: `papel = "fila"` num `[[alvo.componente]]` corrige o que a imagem
não diz. Produto que o arquivo não conhece entra como `app` e recebe só CPU e memória. O papel define as **perguntas** que ele recebe; um **adaptador**
responde o que souber e carimba a **fonte**.

| Adaptador | Fala com | Estado |
|---|---|---|
| `promql` | o Prometheus declarado em `metricas_url`, só leitura (`/api/v1/query` e `/api/v1/query_range`) | funciona |
| `admin_http` | API de administração do componente — hoje, filas de broker AMQP | funciona |
| `exec_leitura` | comando fixo de `references/execs/<familia>.toml` dentro do container, sem senha e só no nó do context; última fonte | funciona |
| `logql` | o Loki declarado em `logs_url`, só `GET` em `/loki/api/v1/query_range`, com a consulta fixa de `references/logs/<familia>.toml`; responde às URLs mais acessadas | funciona |
| `sql` | Postgres/MySQL por cliente de linha de comando | próximo ciclo |

O conhecimento de cada família de exporter vive em `references/metricas/<familia>.toml` —
identificação pela **série que existe** (não pelo nome da imagem, que mente com fork e tag
genérica), etiqueta de seletor e uma consulta por pergunta. Acrescentar um produto é escrever
um arquivo; nenhum `if produto ==` no código.

**Tendências da capa:** erros, resposta, CPU, memória e disco, em 24 horas com passo de 1 hora, via
`/api/v1/query_range`. **Máquinas:** a família `node-exporter` responde pelo papel `maquina`, e o nó é
ligado a `fatos.nodes` pelo container do exporter. **Disponibilidade e previsão de disco** usam 7 dias,
a retenção real medida, e não 30: a consulta nunca promete janela que o Prometheus não guarda.

Duas coisas valem saber sobre como o `promql` liga série a componente, porque é onde ele erra
quando erra. Primeiro, a família só concorre se **responde pergunta do papel** daquele
componente — sem isso, um banco apontando para o mesmo Prometheus do proxy era identificado
como o proxy, já que a série existe naquele Prometheus. Segundo, o valor da etiqueta é
**descoberto**, não suposto: ele vale o que o scrape config disser, e supor que vale o nome do
serviço fazia dois componentes receberem o MESMO número, cada um carimbado como se fosse dele.
Quando nenhum valor casa e o exporter cobre **um** componente, a resposta sai do exporter
inteiro e a fonte diz `(exporter inteiro)`; cobrindo vários, vira `sem dados` — o número sem
filtro seria a soma de todos.

Uma pergunta em forma de **lista** pode ter itens de vários campos, com **uma consulta por
campo**, juntas pela etiqueta declarada em `chave`. É o que permite um limiar comparar dois
campos do mesmo item (`consumidores == 0 e prontas > 0`). O carregador recusa a família que
responda uma pergunta com limiar **sem medir os campos que o limiar compara** — senão o achado
nunca dispararia, com a suíte toda verde.

O `admin_http` segue a mesma ideia com `references/apis/<familia>.toml`: identifica a família
pelas chaves do JSON de identificação e extrai por uma **linguagem fechada** (ponteiro JSON,
campos, transformações e contas declaradas). Não há expressão arbitrária — o que não cabe nela
vira adaptador próprio, com código e teste.

**Papel `fila`** — três fontes respondem, e a mais específica vence. A **API de administração**
traz vhost e taxa de entrada × saída, e por isso vem primeiro; o **exporter no Prometheus**
responde filas e consumidores sem credencial nenhuma, para quem não quer criar usuário no
broker. Por último, o **`exec_leitura`** lê as filas por dentro do container, sem senha e sem taxa
(o ritmo sai como "não medido"), com fonte `exec:rabbitmq`; se o container estiver em outro nó, a
resposta fica `sem dados` com o motivo. Vale saber que o plugin oficial **agrega** por padrão: sem
`prometheus.return_per_object_metrics` (ou um scrape em `/metrics/per-object`), a etiqueta por
fila não existe, e a resposta sai como `sem dados` dizendo exatamente isso — não como "a fonte
não respondeu", que mandaria caçar problema de rede.

A API de administração responde três perguntas: **filas** (com mensagens
prontas, não confirmadas, consumidores e o total acumulado), **consumidores por fila** e
**entrada × saída**. A lista de filas é ordenada pelo que está **acumulado** (prontas + não
confirmadas), então a fila travada — consumidor conectado que recebe e nunca confirma —
aparece no topo. Fila
com mensagem pronta e **nenhum consumidor** vira o achado `fila_sem_consumidor` (alto), um por
fila, identificado como `nome@vhost` (ex.: `emails@staging`). O limiar vê **todas** as filas; o
relatório mostra as 10 primeiras de cada lista e diz quantas ficaram de fora — a lista completa
fica no `report.json`.

Declare o componente quando quiser corrigir o papel ou apontar a fonte. A tabela opcional `rotulos`
dá nome legível à stack em "Saúde por sistema":

```toml
[alvo.rotulos]
loja = "Loja virtual"

[[alvo.componente]]
nome = "traefik"
papel = "entrada"
metricas_url = "http://prometheus.interno:9090"

[[alvo.componente]]
nome = "infra_rabbitmq"         # no Swarm, o nome do SERVIÇO: `<stack>_<serviço>`
papel = "fila"
admin_url = "http://198.51.100.20:15672"
senha_env = "SENHA_BROKER"      # o NOME da variável; o valor nunca fica no arquivo
usuario = "auditoria"           # opcional; o padrão é `guest`
```

**A senha** é lida do ambiente no momento da coleta, vai em header de autenticação e **não
entra** no `alvos.toml`, no argv, no `report.json`, no HTML nem no PDF. Ela é amarrada ao
(alvo, host, porta) daquele componente: não serve para outro destino. Senha escrita na própria
URL (`http://usuario:senha@host`) é **recusada** ao ler o `alvos.toml`.

**URLs mais acessadas** vêm do log de acesso do proxy, e só se o alvo docker declarar a `logs_url`
(opcional, a raiz do Loki, com egress só para ela):

```toml
[[alvo]]
nome = "producao"
tipo = "docker"
context = "producao"
logs_url = "http://loki.interno:3100"
```

- **Fonte:** 24 janelas de 1 hora ancoradas no `--at`, com `limit=5000` e `direction=backward`. A
  pergunta `entrada.urls_mais_acessadas` roda por último, com o que sobrou do orçamento do alvo; sem
  `logs_url` ela sai da conta da cobertura, e o bloco diz "não medido" com a instrução. Fonte declarada
  que falha vira `sem dados` com motivo, sem derrubar a coleta.
- **Amostra:** janela que bate no limite conta como amostrada, e janela não lida fica fora de
  `janelas.cobertas`. Quando não cobriu tudo, o relatório diz "amostra": os números valem como
  ordem de grandeza, não como contagem total.
- **Proteção de dados:** os logs brutos têm cabeçalhos com Cookie e Authorization. A consulta sempre
  passa por `line_format`, que reescreve a linha em host, caminho, status e duração; a skill nunca lê
  linha sem ele, nunca grava a linha bruta e nunca imprime cabeçalho. O catálogo só aceita essa forma, e linha
  fora dela é descartada. Consulta e fragmento saem do caminho, IDs numéricos, UUID e hexa viram `:id`,
  e segmento com 24 caracteres ou mais vira `:token`. Vão ao `report.json` só o caminho agregado, com
  até 200 caracteres e passado por `scrub_text`, e o top 50 por site, com acessos, % de 5xx e p95.
- **Limite do Loki:** agregar no LogQL (`sum by`) estoura `maximum of series (500)` por causa dos
  rótulos de arquivo. Por isso a consulta traz linhas e quem agrega é o Python.

O `nome` do componente é o nome do **serviço** como o Docker o mostra; declaração que não casa
com nenhum serviço aparece em "não coletado", com a sugestão do nome certo quando houver um
parecido.

**Crie um usuário só para a auditoria**, com a tag `monitoring` e **nenhuma** permissão de
configure ou write — no RabbitMQ, `monitoring` já lista filas de todos os vhosts sem precisar
de permissão neles. Não use `set_permissions ".*" ".*" ".*"`: isso dá escrita, e a senha no
ambiente passaria a poder purgar ou apagar fila pela API. Um usuário sem a tag e com acesso só
a alguns vhosts recebe a listagem incompleta com status 200, e as filas dos outros somem sem
aviso. Com `admin_url` em `http://`, a senha trafega em texto claro
na rede; prefira `https` ou uma rede em que isso seja aceitável.

A janela é 24 h por padrão (`[insights] janela` no `config.toml`) e é **ancorada no `--at`** —
duas execuções com o mesmo carimbo dão o mesmo número.

## Como resolver cada achado

Todo achado chega ao relatório com quatro blocos vindos de `references/remediacao/<regra>.md`:
**por que importa · como resolver (passos e comando) · como confirmar que resolveu · quando NÃO
fazer**. Você pode enriquecer a análise por cima; não reescreva o catálogo na hora — ele é
versionado e revisado em pull request, justamente para não variar a cada rodada.

Regra marcada como **esperada** (o proxy que monta o `docker.sock` porque é assim que ele
funciona, o job de migração concluído) não pede remediação: ela descreve o normal.

## Fluxo do modo auditar

### 1. Escopo e configuração

Leia a configuração efetiva e a lista de alvos. Se o projeto não escolheu nenhum (`alvos = []`),
todos os declarados entram.

### 2. Confirmação — obrigatória, e antes de qualquer conexão

Mostre via `AskUserQuestion` **todos** os alvos da rodada, com **nome, tipo e onde**, e peça a
confirmação. Alvo não confirmado **não é tocado**: fica no `report.json` e o relatório mostra uma linha
"Fora desta rodada" com os nomes, para o inventário não mentir por omissão.

Alvo de produção merece atenção redobrada na pergunta: diga o que será executado nele.

### 2b. Opções da rodada — sempre pergunte, sempre com padrão

Numa só chamada de `AskUserQuestion`, depois da confirmação dos alvos. O padrão é a **primeira opção**,
marcada "(Recomendado)", e vem do `config --explicar`. Sem resposta, siga com ele.

| Pergunta | Opções | Flag |
|---|---|---|
| Quantas horas de acessos? | **24 h** · 6 h · 12 h · 48 h | `--janela-horas` |
| Top de sites e URLs? | **15** · 10 · 20 | `--top` |
| Tempo de coleta por alvo? | **120 s** · 240 s · 300 s | `--orcamento` |

As horas valem para as URLs do Loki e para tráfego e latência do Prometheus. As tendências da capa seguem
em 24 horas. As URLs são lidas por último, com o tempo que sobrar: cada hora custa cerca de 3 s, então
janela maior pede mais tempo de coleta, senão o relatório sai como amostra. As escolhas ficam em
`opcoes` no `report.json`, e regerar o relatório as mantém.

### 3. Coletar

```bash
python3 <skill-dir>/scripts/collect.py --out docs/infra/<AAAA-MM-DD_HHMM> \
  --at <ISO> --confirmar <nomes confirmados> \
  --janela-horas <h> --top <n> --orcamento <s>
```

- **Exit 0** → imprime o caminho do `report.json` e uma linha por alvo com saúde e tipo.
- **Exit 2** → mostre a mensagem e **pare**: configuração inválida, nenhum alvo confirmado,
  `--confirmar` citando alvo fora da auditoria, ou `--at` fora do formato.

O `--at` é o carimbo da execução e **decide qual aceite venceu** — use a data real, em ISO.

### 3b. O relatório vai ter o que dizer? (antes de interpretar)

Coletar sem erro **não** quer dizer que a auditoria respondeu alguma coisa. Numa rodada real,
57 componentes entraram no inventário e nenhum respondeu pergunta nenhuma: os que tinham
pergunta não achavam `metricas_url` declarado, e o resto tinha papel sem pergunta registrada.
O `collect.py` terminou com exit 0, e o relatório saiu com nome, papel e silêncio.

Antes de escrever a interpretação, rode:

```bash
python3 <skill-dir>/scripts/pendencias.py --dir docs/infra/<AAAA-MM-DD_HHMM>
```

Ele lista o que está calado e por quê. Então, **via `AskUserQuestion`**:

- **Componente sem `metricas_url`** e existe Prometheus no alvo → ofereça rodar
  `configurar.py alvos --sugerir --context <ctx>` e declarar o endereço **antes** de seguir. Uma linha no `alvos.toml`
  costuma ser a diferença entre um relatório com medidas e um relatório com rótulos.
- **Componente de fila sem `admin_url`** → pergunte o endereço da API de administração e o
  **nome** da variável de ambiente que guarda a senha. Nunca peça a senha em si, nem a escreva
  em arquivo ou comando.
- **Papel sem pergunta nesta versão** → isso é limite da skill, não configuração. Diga qual
  papel, não ofereça conserto que não existe, e siga.

**Nunca entregue um relatório mudo sem ter perguntado.** Quem recebe não distingue "não há o
que medir" de "ninguém apontou a skill para a fonte" — e conclui que a auditoria não funciona.

### 4. Interpretar (é a sua parte)

Leia o `report.json` inteiro e escreva **por cima** dele, sem inventar achado — achado nasce de
regra:

| Campo | O que escrever |
|---|---|
| `resumo` | até 2 frases e 280 caracteres dizendo **por que** o veredito é esse. Acima disso, `build_report.py` sai com código 2 e não gera relatório: reescreva. Sem 🔴🟡🟢 |
| `fortes` / `fracos` | só o que as medidas não dizem: o relatório já monta os pontos positivos e de atenção a partir delas, e estes itens entram depois |
| `recomendacoes` | `{alvo, titulo, porque, comando, impacto, esforco, regra?}` — **com o comando pronto**. Com `regra`, o comando vai para o problema agrupado; sem ela, para "Outras recomendações". Nenhuma some |
| `alvos[].analise` | o que aquele componente é e o que preocupa nele |

Use `dimensoes`, `fatos` e `achados` de cada alvo. O que estiver em `nao_coletado` **precisa
aparecer no resumo**, em poucas palavras: relatório com buraco explícito é honesto; relatório que cala é mentira. A exceção é o aviso de uso
por nó quando todas as máquinas foram medidas: ele nasce antes da medida e o relatório o omite.
`resumo`, `fortes`, `fracos`, `recomendacoes` e `analise` passam por redação antes de sair no relatório.

### 5. Relatório

```bash
python3 <skill-dir>/scripts/build_report.py --dir docs/infra/<AAAA-MM-DD_HHMM> --formato html
```

Gera `relatorio.html` — arquivo único, A4 **paisagem**, com as fontes embutidas em base64 (o PDF é
gerado sem rede). Cinco partes, nesta ordem:

1. **Capa:** nota, serviços online, tendências, veredito, seu `resumo`, "O que fazer primeiro", o que
   mudou, certificados e uma linha do que não foi medido, por categoria e com o motivo mais comum.
2. **Saúde por sistema:** uma linha por stack, com o nome de `rotulos` quando houver, seguida de
   **Pontos positivos e pontos de atenção**, montados por `lib/balanco.py` a partir das medidas.
3. **Detalhes técnicos:** blocos por papel em `scripts/lib/blocos/`: máquinas, entrada, fila, banco,
   cache, consumo e pontos únicos de falha. Papel sem bloco usa a tabela genérica. Sem fonte, o bloco
   diz "não medido" com o motivo, nunca zero. Em sites, rota medida sem série de 5xx mostra "nenhum";
   sem medida de acessos ou com a consulta de erros falhando, "sem dado".
4. **Problemas:** um bloco por regra, explicado uma vez, com afetados, ação e verificação.
5. **Registro:** riscos aceitos com vencidos em destaque e o que falta declarar.

Redes, secrets e configs ficam só no `report.json`.

**"O que fazer primeiro"** mostra até 5 itens. Suas `recomendacoes` vêm antes; as vagas restantes usam
os problemas mais graves, com rótulo legível, gravidade e quem age derivado da categoria (Segurança,
Infraestrutura ou Aplicação). Achado esperado ou informativo não entra.

**Limite de 1 página + 20.** O corte é por contagem, antes de renderizar, igual no HTML e no PDF:
achados baixos viram contagem, afetados ficam nos 8 primeiros, consumo em top 4, filas em 8 e sistemas
online se juntam numa linha. O relatório avisa cada corte, e o completo fica no `report.json`. Riscos
aceitos e o que falta declarar nunca são cortados: se só eles passarem do limite, ele cede e o
relatório diz isso.

### 6. Informar

Caminho do relatório · a nota geral e os serviços online · quantos problemas por gravidade · o que ficou `sem dados` e por quê · riscos aceitos, com
os vencidos em destaque · e o que mudou desde a auditoria anterior.

### 7. Ofereça o PDF — no fim, não antes

**`AskUserQuestion`**: "Gerar o PDF também?" Só então rode com `--formato html+pdf`. O PDF custa
alguns segundos de Chromium e nem toda rodada vira documento para enviar; perguntar no começo
gasta a atenção de quem só queria ver o estado da infra.

```bash
python3 <skill-dir>/scripts/build_report.py --dir docs/infra/<AAAA-MM-DD_HHMM> --formato html+pdf
```

Sem Chromium na máquina, diga isso e entregue o HTML — não é falha da auditoria.

## Riscos aceitos

Achado que o usuário já decidiu aceitar não deve voltar a cada auditoria — é assim que um
relatório perde credibilidade. **Ofereça via `AskUserQuestion`** registrar — e, se houver
aceite vencido na rodada, pergunte o que fazer com ele (renovar, deixar vencer, resolver):

```bash
python3 <skill-dir>/scripts/configurar.py aceitar --alvo <nome> --regra <regra> \
  [--componente <componente>] [--objeto <objeto>] \
  --motivo "por que isso é aceitável" --meses 6
```

**Aceite o mais estreito possível.** Sem `--componente` e `--objeto`, o aceite vale para a regra
no alvo inteiro — em `fila_sem_consumidor`, isso são todas as filas de todos os brokers,
inclusive as que ficarem órfãs no futuro. Para uma fila, use `--componente` e
`--objeto nome@vhost` (ex.: `--objeto emails@staging`).

- O aceite **não filtra a coleta**: o achado nasce, é marcado, sai da nota e vai para a seção
  própria, com origem, motivo e data de revisão.
- **Vencido volta a contar**, com a observação de que a justificativa expirou.
- Aceite no `alvos.toml` vale para todos os alvos daquele arquivo; o do `config.toml`
  (versionado, revisado em PR) vence quando os dois existem.
- **Exija motivo.** Aceite sem justificativa é achado escondido.

## Modo configurar

| Comando | Para quê |
|---|---|
| `config --explicar` | Ver a configuração efetiva e a origem de cada chave |
| `migrar` | Criar o primeiro `alvos.toml` em `docs/infra/`, já ignorado pelo git |
| `alvos --sugerir --context <ctx>` | Propor uma `metricas_url` (só propõe; não alcança host) |
| `aceitar` | Registrar um risco aceito no `config.toml` do projeto |
| `ignorar` | Acertar o `.gitignore`: esconde a pasta, mantém o `config.toml` |

É o único que escreve fora da pasta do relatório, e nunca sobrescreve `alvos.toml` existente.

## Como a saúde é calculada

**Saúde é operação, não higiene.** Um cluster que está rodando não vira crítico porque tem
imagem sem digest. Por alvo: 🔴 algo fora do ar · 🟡 rodando com risco conhecido · 🟢 convergido
· `sem dados` quando não foi coletado.

**Nota geral.** A nota da capa sai de `scripts/lib/nota.py`, nunca do agente, somando todos os alvos
medidos, sem média entre alvos: **70%** serviços online, **20%** estabilidade (serviços com mais de uma
réplica) e **10%** boas práticas (média de segurança e higiene).

- **Tetos:** até **59** com serviço ou nó fora do ar; até **79** com problema alto, crítico ou serviço
  parcial. Alerta não tem teto. Valem depois dos aceites: vencido volta a contar, e aceite em `OPS_NODE_DOWN`
  não tira o teto.
- **Faixas:** **80 ou mais** Bom · **60 a 79** Atenção · **abaixo de 60** Crítico. O veredito é fixo por faixa.
- **Parcela não medida** sai da conta, os pesos são renormalizados e a nota aparece como **parcial**,
  sem verde. A trava de cobertura também tira o verde. Sem nenhum serviço medido, não há nota.

| Estado do serviço | Regra | Na conta de online |
|---|---|---|
| Online | todas as réplicas no ar; com falha no histórico, conta como **com alerta** e mantém `OPS_TASK_FAILING` em Problemas | online |
| Parcial | parte das réplicas no ar | não online |
| Fora do ar | desejado acima de 0, nenhuma réplica, sem aceite vigente | não online |
| Parado de propósito | desejado 0, job concluído ou `OPS_SERVICE_STOPPED` com aceite vigente | fora da conta |
| Sem dado | réplicas desconhecidas | fora da conta |

Endpoint HTTP conta como um serviço: responde é online; `http_fora_do_ar`, timeout ou conexão
recusada é fora do ar.

A capa mostra "N com alerta" em amarelo. A barra usa vermelho só para fora do ar e amarelo para
parcial e alerta, e cita até 5 nomes curtos no total. A linha **Por que esta nota** sai das parcelas,
do teto e dos nomes, sem frase genérica. O `report.json` grava `com_alerta`, `limites` (a causa de
cada teto) e `pendencias` (pontos que faltam para 100 em cada parcela).

**Cobertura da medição: o verde exige ter medido.** Se uma pergunta que produz achado (a que
declara `limiar`) fica sem resposta, um achado podia ter nascido e não nasceu — então o alvo
**não pode** ser 🟢, e sai 🟡 com o motivo por extenso em "O que falta declarar". É teto, nunca
piso: cegueira nunca produz 🔴, porque vermelho significa *algo está fora do ar* e não ter visto
não é prova disso. Limiar de severidade baixa não trava, e regra com aceite vigente também não
— ela já não contaria. Numa rodada real o mesmo cluster passou de 🔴 para 🟢 sem nada ter
melhorado, só porque a senha do broker não estava no ambiente; é esse o defeito que isto fecha.

## Depois de um restart do daemon: réplicas N/N não provam funcionamento

Serviço que mantém **cluster interno próprio** (agente de painel, service discovery, gossip)
pode ficar com estado partido depois que o daemon reinicia — aparecendo como `4/4` saudável
enquanto o painel alterna entre "vê tudo" e "vê nada". As réplicas dizem que o container subiu,
não que o processo voltou a conversar com os pares. Se o usuário reiniciou o daemon
recentemente e relata algo assim, sugira `docker service update --force <serviço-agente>`
(seguro para proxy sem estado; não toca em container de aplicação). Isso é conversa, não
achado: a skill não tem como medir estado interno de um agente.

## Limites

- **Banco de dados ainda não** — Postgres e MySQL são o próximo ciclo. Alvo desse tipo no
  `alvos.toml` é recusado com mensagem clara.
- **A API de administração tem rotas de escrita** (purgar fila, publicar mensagem, remover
  exchange) e rotas de leitura que devolvem segredo (definições exportadas, usuários,
  parâmetros de shovel, conexões). A skill **só faz GET**, e o catálogo em `references/apis/`
  é a lista completa do que ela alcança: o carregador recusa rota de escrita, rota que devolve
  segredo e qualquer parâmetro de URL que não seja `columns`.
- **`fila_sem_consumidor` não vê a fila travada** — consumidor conectado que não confirma
  mensagem. Ela não vira achado, mas encabeça a lista de filas, que é ordenada pelo total
  acumulado e mostra a coluna de não confirmadas. E acusa
  por desenho fila morta, fila de espera para nova tentativa e stream: a remediação diz como
  distinguir e registrar como risco aceito.
- **Broker com estatísticas desligadas** não informa contadores: a pergunta vira `sem dados`
  com esse motivo, em vez de "nenhuma fila parada".
- **SSH não** — auditar host por comando remoto é outra superfície, e fica para depois.
- **Uso de CPU e memória por nó exige `node-exporter`** no Prometheus de `metricas_url`. Sem ele, a
  coleta reporta só **capacidade** (vCPU e GB do nó), e o consumo sai como `sem dados`, nunca estimado.
- **Kubernetes não** — os alvos são Docker (context/Swarm) e endpoint HTTP.
- **Não é monitoramento.** É fotografia sob demanda, não alerta contínuo.
- **Porta em 0.0.0.0** significa publicada em todas as interfaces, **não** alcançável da internet:
  firewall e security group são invisíveis daqui.
- **O papel provado exige que o `job` nomeie o SERVIÇO.** A identificação casa o nome do
  componente com o valor da etiqueta do exporter. Num Prometheus cujo scrape config nomeia os
  jobs pelo PRODUTO (`job="redis"` para um serviço `cache_valkey`), não há casamento e o papel
  fica provisório — o relatório diz isso, em vez de carimbar um palpite. Casar `valkey` com
  `redis` exigiria saber que um é fork do outro, que é conhecimento de produto por nome, e é
  disto que a identificação está sendo tirada.
- **Métricas de runtime** só existem se o alvo declarar `metricas_url`.
- **URLs mais acessadas** só existem com `logs_url`, e erros e lentidão olham só o top 50 por site:
  uma URL pouco acessada com muito erro pode ficar de fora. Slug longo, com 24 caracteres ou mais, vira
  `:token` junto com os tokens, porque a skill prefere perder a rota a gravar um segredo.
- **`metricas_url` é a API de um Prometheus**, não um `/metrics` cru. As perguntas são
  consultas PromQL com janela (`increase(...[24h])`), e um raspão instantâneo de exporter não
  tem onde avaliá-las. Endereço que não responde a `/api/v1/query` vira uma nota no alvo
  dizendo isso. Houve um caminho paralelo que lia `/metrics` em texto, com uma tabela de
  métricas escrita no código; ele foi retirado porque alimentava só o renderizador anterior,
  que o relatório não usa mais — dois caminhos, um deles cego.

## Referências

- [`references/what-to-collect.md`](references/what-to-collect.md) — o que a coleta traz de cada alvo
- [`references/finding-rules.md`](references/finding-rules.md) — as regras que geram achado
- [`references/commands-allowlist.md`](references/commands-allowlist.md) — a allowlist de comandos
- [`references/tls-renewal.md`](references/tls-renewal.md) — o que dizer ao recomendar renovação de certificado
