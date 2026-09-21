---
name: sw-infra-audit
description: >-
  Audita a infraestrutura de forma READ-ONLY e gera um relatório técnico (HTML + PDF opcional)
  com inventário, achados por gravidade e riscos aceitos. Trabalha por ALVOS: cluster Docker
  (context/Swarm) e endpoint HTTP (saúde + validade do certificado). Use SEMPRE que o usuário
  quiser um raio-x da infra ou de parte dela — "audita minha infra", "como está o cluster",
  "o que pode cair primeiro", "relatório da infraestrutura", "esse certificado vence quando?",
  "a API está no ar?", "o que eu tenho rodando e onde", "saúde do swarm", "como o traefik está
  roteando". Dispare mesmo sem a palavra "auditar" — basta a intenção de entender o ESTADO
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
| **No fim** | gerar o PDF também? |

Para resposta aberta (um motivo de aceite, um endereço), ofereça as opções prováveis e conte
com o campo **"Other"**. A exceção é o usuário descrevendo livremente o que quer — aí ele está
dirigindo, e forçar menu atrapalha.

**Nunca pergunte o que dá para descobrir sozinho.** Qual é o context, quantos nós tem, se há
exporter respondendo: isso a skill lê. Pergunta serve para **decisão e autorização**, não para
suprir leitura que você não fez.

## Garantias inegociáveis

- **Nada é alterado.** Só comandos de leitura, por allowlist. Nunca `rm/kill/restart/exec/create/
  update/scale/prune`, `logs`, `cp`, `secret inspect`.
- **Nenhum segredo sai.** O relatório mostra **nomes** de secrets e **chaves** de env, nunca
  valores, nunca string de conexão. A senha de um alvo nunca é gravada em lugar nenhum.
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
sobrescrevível no `alvos.toml`. O papel define as **perguntas** que ele recebe; um **adaptador**
responde o que souber e carimba a **fonte**.

| Adaptador | Fala com | Estado |
|---|---|---|
| `promql` | Prometheus ou exporter declarado em `metricas_url` | funciona |
| `admin_http` | API de administração do componente — hoje, filas de broker AMQP | funciona |
| `sql` | Postgres/MySQL por cliente de linha de comando | próximo ciclo |
| `logql` | agregador de log, só consulta agregada | próximo ciclo |

O conhecimento de cada família de exporter vive em `references/metricas/<familia>.toml` —
identificação pela **série que existe** (não pelo nome da imagem, que mente com fork e tag
genérica), etiqueta de seletor e uma consulta por pergunta. Acrescentar um produto é escrever
um arquivo; nenhum `if produto ==` no código.

O `admin_http` segue a mesma ideia com `references/apis/<familia>.toml`: identifica a família
pelas chaves do JSON de identificação e extrai por uma **linguagem fechada** (ponteiro JSON,
campos, transformações e contas declaradas). Não há expressão arbitrária — o que não cabe nela
vira adaptador próprio, com código e teste.

**Papel `fila`** — a API de administração responde três perguntas: **filas** (com mensagens
prontas, não confirmadas, consumidores e o total acumulado), **consumidores por fila** e
**entrada × saída**. A lista de filas é ordenada pelo que está **acumulado** (prontas + não
confirmadas), então a fila travada — consumidor conectado que recebe e nunca confirma —
aparece no topo. Fila
com mensagem pronta e **nenhum consumidor** vira o achado `fila_sem_consumidor` (alto), um por
fila, identificado como `nome@vhost` (ex.: `emails@staging`). O limiar vê **todas** as filas; o
relatório mostra as 10 primeiras de cada lista e diz quantas ficaram de fora — a lista completa
fica no `report.json`.

Declare o componente quando quiser corrigir o papel ou apontar a fonte:

```toml
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
confirmação. Alvo não confirmado **não é tocado** — mas ainda aparece no relatório como
`sem dados`, para o inventário não mentir por omissão.

Alvo de produção merece atenção redobrada na pergunta: diga o que será executado nele.

### 3. Coletar

```bash
python3 <skill-dir>/scripts/collect.py --out docs/infra/<AAAA-MM-DD_HHMM> \
  --at <ISO> --confirmar <nomes confirmados>
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
  `alvos.py --sugerir` e declarar o endereço **antes** de seguir. Uma linha no `alvos.toml`
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
| `resumo` | 2 a 4 frases dizendo **por que** o veredito é esse |
| `fortes` / `fracos` | o que está bom e o que preocupa, em lista |
| `recomendacoes` | `{alvo, titulo, porque, comando, impacto, esforco}` — **com o comando pronto** |
| `alvos[].analise` | o que aquele componente é e o que preocupa nele |

Use `dimensoes`, `fatos` e `achados` de cada alvo. O que estiver em `nao_coletado` **precisa
aparecer no resumo**: relatório com buraco explícito é honesto; relatório que cala é mentira.

### 5. Relatório

```bash
python3 <skill-dir>/scripts/build_report.py --dir docs/infra/<AAAA-MM-DD_HHMM> --formato html
```

Gera `relatorio.html`. O sumário no topo é **clicável também no PDF** — o Chromium converte as
âncoras em link com destino de página —, então quem receber o arquivo navega sem rolar.

### 6. Informar

Caminho do relatório · quantos alvos em cada estado (**não invente uma nota única da infra**) ·
achados por gravidade · o que ficou `sem dados` e por quê · riscos aceitos, com os vencidos em
destaque · e o que mudou desde a auditoria anterior.

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
· `sem dados` quando não foi coletado. **Não existe nota única da infraestrutura** — o topo mostra
a contagem por estado. Número único vira meta, e meta vira teatro.

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
- **Não é monitoramento.** É fotografia sob demanda, não alerta contínuo.
- **Porta em 0.0.0.0** significa publicada em todas as interfaces, **não** alcançável da internet:
  firewall e security group são invisíveis daqui.
- **Métricas de runtime** só existem se o alvo declarar `metricas_url`.

## Referências

- [`references/what-to-collect.md`](references/what-to-collect.md) — o que a coleta traz de cada alvo
- [`references/finding-rules.md`](references/finding-rules.md) — as regras que geram achado
- [`references/commands-allowlist.md`](references/commands-allowlist.md) — a allowlist de comandos
- [`references/tls-renewal.md`](references/tls-renewal.md) — o que dizer ao recomendar renovação de certificado
