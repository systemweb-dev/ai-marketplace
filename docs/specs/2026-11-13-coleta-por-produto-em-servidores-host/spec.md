---
titulo: Coleta por produto em servidores host
slug: 2026-11-13-coleta-por-produto-em-servidores-host
criado: 2026-11-13
estado: concluido
---

# Coleta por produto em servidores host

> Parte B da evolução da `sw-infra-audit`. A parte A (v0.20.0, dossiê
> `docs/specs/2026-09-19-auditoria-do-host-por-ssh-somente-leitura`) trouxe o alvo `host` por SSH e a
> descoberta. Caminhos relativos a `plugins/sw-infra-audit/skills/sw-infra-audit/`.

## Objetivo & outcome

Os componentes descobertos num servidor (banco, cache, busca vetorial, app próprio) aparecem no
inventário, mas sem dado nenhum: o papel `banco` tem só `banco.conexoes` e `banco.tamanho`, respondidas
por exporter [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/perguntas.py:94], e o
papel `busca` não tem pergunta. O dono quer a coleta **genérica**: qualquer serviço medido, e os
produtos conhecidos com os dados deles. [usuário]

**Outcome:**
1. todo componente de host tem estado, tempo no ar, reinícios e memória, seja qual for o produto;
2. MariaDB/MySQL, Postgres, Redis e Qdrant trazem os dados específicos (tamanho por banco, conexões
   contra o limite, lentas, binlog, idade do backup; memória e descartes; coleções e pontos);
3. produto novo é medido escrevendo um arquivo de catálogo, sem mudar código. [usuário]

## Não-objetivos

- Blocos do relatório para estes dados: parte C.
- Qdrant com chave de API, Redis com senha, lentas no Postgres, CPU por processo.
- Dois bancos do mesmo produto no mesmo host: só o socket padrão nesta versão.
- Firewall; qualquer escrita no banco ou no servidor.
- Mudar o que os alvos `docker` perguntam hoje.

## Design

### 1. Que perguntas cada componente recebe

`do_papel(papel)` só lê `ORDEM[papel]`
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/perguntas.py:139], e a cobertura
usa a mesma função [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/cobertura.py:70].
Perguntas novas no `ORDEM` de `banco` ou `cache` cairiam também nos clusters, sem quem respondesse, e a
cobertura conta opcional sem resposta como lacuna
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/cobertura.py:79].

Função nova `perguntas_do_componente(componente)`: as do papel; mais, **só se o componente tem
`origem`** (veio de um host), as **comuns** e as do **catálogo do produto**, quando existe
`references/produtos-host/<produto>.toml`. Um `produto` declarado num componente de alvo `docker` não
puxa catálogo nenhum. Pergunta repetida (`banco.tamanho` vem do papel e do catálogo) entra uma vez só. Um
banco de host **sem** catálogo (Mongo, por exemplo) recebe as perguntas do papel como hoje, e a lacuna
dele diz "não medido: falta catálogo ou exporter". As comuns e as de catálogo ficam registradas em `PERGUNTAS`
mas fora de `ORDEM[papel]`. `collect.responder`
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/collect.py:287] e `cobertura` passam a
usar a função nova, juntos.

### 2. Camada comum

| Pergunta | Unit (`systemctl show {unidade} --property=…`) | Container (`docker inspect`/`docker stats`) | Só processo (`ps -C {processo} -o rss=,etimes=`) |
|---|---|---|---|
| `servico.ativo` | `ActiveState` | `State.Status` | processo existe |
| `servico.desde` (dias) | `ActiveEnterTimestamp` | `State.StartedAt` | `etimes` |
| `servico.reinicios` | `NRestarts` | `RestartCount` | não medido |
| `servico.memoria` (bytes) | `MemoryCurrent` | `docker stats` | RSS do processo principal (maior `etimes`), nunca a soma dos workers |

As quatro são **opcionais**. O "não medido por desenho" (reinícios de quem é só processo,
`MemoryCurrent=[not set]`) sai como `sem dados` com `nao_publica`, que a cobertura já não conta como
lacuna; falha de leitura de verdade continua contando. Sem CPU (uma leitura só dá a média desde o início) e sem achado
novo: serviço parado já é `servico_declarado_ausente`. [usuário]

### 3. Catálogo por produto e o adaptador `produto_ssh`

Um arquivo por produto em `references/produtos-host/`. O produto precisa existir também em
`references/produtos.toml`. Exemplo:

```toml
produto = "mariadb"
[cliente]
socket    = 'mysql -N -B -e "{sql}"'
senha     = 'mysql --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
container = 'docker exec {container} mysql -N -B -e "{sql}"'
[[pergunta]]
id = "banco.tamanho_por_banco"
sql = "SELECT table_schema, SUM(data_length+index_length) FROM information_schema.tables GROUP BY 1"
formato = "tsv"
colunas = ["nome", "bytes"]
```

| Produto | Perguntas |
|---|---|
| MariaDB/MySQL (`banco`) | `banco.tamanho`, `banco.conexoes` (existentes), `banco.tamanho_por_banco`, `banco.uso_de_conexoes` (de `SHOW GLOBAL STATUS` e `SHOW GLOBAL VARIABLES`, razão `Threads_connected / max_connections`), `banco.consultas_lentas` (`Slow_queries`), `banco.binlog` |
| Postgres (`banco`) | as mesmas, menos lentas e binlog; cliente `runuser -u postgres -- psql -At -c "{sql}"` (peer, sem senha) |
| Redis (`cache`) | `cache.memoria_usada`, `cache.evicções`, `cache.acerto` (existentes), de `redis-cli INFO` |
| Qdrant (`busca`) | `busca.colecoes` (nome, pontos, status), de `curl -s 127.0.0.1:{porta}/collections` e `/collections/{colecao}` |
| Banco com `backup_pasta` | `banco.backup_idade` (dias): data do nome mais novo em `AAAA-MM-DD` ou `AAAAMMDD`; fora disso, mtime de `ls -l --time-style=full-iso {backup_pasta}` |

**Formatos de saída:** `tsv`, `json` e `chave_valor` viram lista ou dicionário e passam pelo `extrair`
que já existe [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/extracao.py:282], hoje
só JSON. Sem segunda linguagem de extração; a razão das conexões usa o `razao` que `derivar` já tem
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/extracao.py:17].

**Prioridade:** `produto_ssh` = 38, depois do `promql` (30) e do `ssh` (35) e antes do `exec_leitura`
(40): exporter, quando existe, continua vencendo.

**Achados novos**, num produtor próprio no molde de `lib/capacidade.py` (só com número presente; a
função atual filtra `papel == "maquina"` [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/capacidade.py:15]):
`backup_atrasado` (high, idade acima de `backup_max_dias`, padrão 2) [usuário] e `conexoes_no_limite`
(medium, uso acima de 80%). Cada um com arquivo de remediação.

### 4. Vagas no catálogo (muda uma decisão da parte A)

A parte A proibia vaga: o runner compara o comando com o texto do catálogo
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/runner.py:95]. Agora o comando é
**molde + vagas validadas**, no padrão do `forma_aceita` do `catalogo_exec`
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/catalogo_exec.py:97]:

| Vaga | De onde vem | Validação |
|---|---|---|
| `{sql}` | literal do catálogo | sem `"`, `$`, crase, `\`, `%`, `<`, `>`, quebra de linha |
| `{unidade}` `{container}` `{processo}` | `origem` do componente | a `origem` inteira casa `alvos.ORIGEM`; a vaga recebe só o valor depois de `tipo:` |
| `{porta}` | `portas` do componente | inteiro 1–65535 |
| `{colecao}` | resposta do Qdrant | `[A-Za-z0-9_-]{1,64}`; fora disso, a coleção é pulada e dita |
| `{backup_pasta}` | `alvos.toml` | absoluto, `[A-Za-z0-9._/-]`, sem `..` |

O catálogo de host continua proibindo `;|&$` crase `<>%` e quebra de linha
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/catalogo_host.py:11].

### 5. Leitura perguntada e gravada

Campos novos em `[[alvo.componente]]`: `leitura` (`socket`, `senha`, `container` ou `nenhum`),
`usuario`, `senha_env` (existente), `backup_pasta`, `backup_max_dias`. O nome `leitura` evita confundir
com `acesso_restrito` e `fatos["acesso"]`. [usuário]

- O agente pergunta no `descobrir --gravar` (para banco, cache e busca) e grava com
  `configurar.py leitura --alvo X --componente Y --modo … [--usuario U --senha-env NOME]
  [--backup-pasta P --backup-max-dias N]`.
- Componente com catálogo e sem `leitura`: as perguntas do catálogo saem `sem dados` com "leitura não
  declarada", e a SKILL.md manda o agente perguntar e gravar.
- A gravação só **acrescenta** linhas logo depois do `nome` do bloco do componente, com `.bak`,
  releitura e restauração. Campo existente nunca é trocado; o dono corrige à mão. [usuário] É função
  nova: `gravacao_alvos` só localiza `[[alvo]]`
  [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/gravacao_alvos.py:12].
- Componente em container com `leitura = "container"` usa o cliente `container` do catálogo. [usuário]
  `{container}` só sai de origem `container:`; com origem `unidade:` ou `processo:`, as perguntas do
  catálogo saem `sem dados` com esse motivo.

### 6. A senha (só MariaDB/MySQL nesta versão)

`credencial.de_componente` exige `admin_url`, e `USUARIO_PADRAO = "guest"`
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/credencial.py:20]: não serve para SSH.
Entra uma amarração nova, (alvo, `ssh_destino`, porta, componente), com usuário obrigatório.

A senha sai da variável de ambiente pelo `credencial.py` e vai pelo **stdin** do ssh como
`[client]\nuser="…"\npassword="…"`, com `"`, `\` e `#` escapados. Senha com quebra de linha é recusada.
Ela nunca entra no argv, no log nem no `report.json`. `run_ssh` ganha o parâmetro de entrada e, sem
ele, usa `stdin=DEVNULL` (hoje herda o da skill). Postgres não precisa (peer pelo `runuser`). Redis com
senha e Qdrant com chave viram `sem dados` dizendo que ficam para depois.

### 7. Erros

Sempre `sem dados` com motivo, nunca achado: cliente não instalado; root sem entrada pelo socket ("declare
`leitura = "senha"`"); senha recusada ou variável ausente (sem repetir usuário nem valor); saída fora do
formato; pasta de backup vazia ou inexistente (não vira `backup_atrasado`).

## Exploração & decisões

Direção pedida pelo dono: genérico primeiro. A camada comum mede qualquer serviço; o catálogo acrescenta
o específico. Um módulo por produto foi descartado porque transforma produto novo em código.

## Decisões

| Contexto | Decisão | Alternativas descartadas | Consequências |
|---|---|---|---|
| Skill só stdlib, sem driver de banco | Cliente do produto no servidor, pelo SSH | Falar o protocolo direto; só exporter | Depende do cliente instalado; sem dependência nova |
| Medir qualquer serviço | Camada comum + catálogo por produto [usuário] | Só os quatro produtos | Produto desconhecido ainda tem dado |
| Formato do catálogo | TOML + adaptador único `produto_ssh` [usuário] | Módulo Python por produto | Produto novo = arquivo (mais entrada em `produtos.toml`) |
| Como autenticar | Perguntado e gravado por componente (`leitura`) [usuário] | Sempre socket; sempre senha | Uma pergunta na primeira vez; nada fixo no código |
| Perguntas sem quebrar os clusters | `perguntas_do_componente` decide por origem e catálogo | Pôr no `ORDEM[papel]` | Clusters não ganham lacuna |
| Comando com alvo variável | Molde + vagas validadas | Manter zero vaga | Muda a regra da parte A, com validação por vaga |
| Senha | Só pelo stdin, só MySQL/MariaDB | `passfile` do Postgres; `--askpass` do Redis | libpq não lê pipe como passfile; `--askpass` sem tty não verificado |
| Backup semanal | `backup_max_dias` por componente, padrão 2 [usuário] | Limite fixo | Sem alarme falso em backup semanal |
| Banco em container no host | `docker exec` pelo cliente `container` [usuário] | Só camada comum | Cobre o caso comum de Docker fora do cluster |

## Restrições verificáveis

1. Nenhum argv de ssh contém a senha: o teste usa uma senha marcada e varre o argv capturado e o
   `report.json`.
2. O runner recusa comando que não seja molde do catálogo com vagas preenchidas por valores validados;
   coleção com `;` ou espaço é pulada.
3. Produto novo é medido sem mudar `.py`: o teste cria um catálogo e um bloco de `produtos.toml`
   temporários para um produto inventado e obtém resposta.
4. Componentes de alvo `docker` recebem exatamente as mesmas perguntas de antes (lista comparada).
5. Toda regra nova tem remediação (fitness que já existe).

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| O root entra no MariaDB pelo socket nos servidores do dono | todo banco precisa de `leitura = "senha"` | primeira auditoria real; o motivo de erro já diz o que declarar |
| `mysql`, `curl`, `redis-cli` e `psql` estão instalados onde o produto roda | perguntas do catálogo saem "cliente não instalado" | primeira auditoria real; container cobre o caso do cliente só no container |
| `--defaults-extra-file=/dev/stdin` funciona pelo ssh com stdin redirecionado | modo senha não funciona | teste num MariaDB local antes de publicar; se falhar, o modo senha sai desta versão |
| O Qdrant responde em `127.0.0.1` sem chave | busca sem dados | primeira auditoria real |

## Appetite e MVP

Médio, um plano. MVP: camada comum + MariaDB, que é o que existe nos servidores do dono; Qdrant, Redis e
Postgres entram como catálogos no mesmo plano, porque o custo marginal é um arquivo cada.

## Rollout

Versão minor; os alvos `docker` não mudam (restrição 4). Volta é voltar a versão.

## Revisões do spec

- **2026-11-13** — revisão do spec: catálogo só para componente com `origem`; dedupe de perguntas;
  banco de host sem catálogo segue como hoje; perguntas comuns opcionais, com "não medido por
  desenho" fora da lacuna; `razao` já existia; prioridade 38; vaga recebe o valor sem o prefixo.
