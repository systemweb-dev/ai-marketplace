# O que coletar, por seção (read-only)

Implementado em `scripts/collect.py` (`assemble_report`). Tudo degrada pra `n/a` (com motivo) se
o comando falhar/timeout ou não se aplicar (ex.: não-Swarm).

- **Saúde/visão geral:** `docker info` (redigido — cred de registry-mirror é scrubbed), `node ls`,
  `service ls` (contagens), containers exited/unhealthy (do nó conectado).
- **Nodes:** `node ls` + `node inspect` → role, availability, estado, Leader, **CAPACIDADE**
  (NanoCPUs/MemoryBytes). **Uso real de CPU/mem/disco = `n/a`** (requer Prometheus/cAdvisor).
- **Services (cluster-wide):** `service ls` + `service inspect` → réplicas, imagem+tag+digest,
  portas, `env_keys` (só chaves), `kind` (tipo detectado), `routing_labels` (traefik.*, valores sensíveis redigidos).
- **Segurança (findings por REGRA — ver finding-rules.md):** derivados de `service inspect`
  (cluster-wide) de preferência; checagens de container (`ps`/`container inspect`) cobrem **só o nó conectado**.
- **Rede:** `network ls` (overlays, ingress). **Secrets/configs:** `secret ls` / `config ls` → só **NOMES**.

**Redação (field-allowlist POSITIVA):** os `inspect` só emitem campos whitelisted; `Env/Cmd/Args/
Labels`/valor de config **nunca** saem (env vira chaves). Labels de roteamento: só `traefik.*`, com
valores sensíveis (basicauth/token/cred em URL) redigidos.

## Logs de acesso (só com `logs_url`)

Do Loki declarado no alvo docker, por 24 janelas de 1 hora: host, caminho agregado, status e duração, sempre por `line_format`. Vão ao `report.json` só o top 50 por site, com acessos, % de 5xx e p95, e as janelas cobertas; a linha bruta nunca é gravada.

## Alvo `host` (SSH)

Lido com os comandos de `references/host/linux.toml`: usuário (`id -un`), kernel, sistema, disco
(maior uso entre sistemas de arquivos reais), memória (MemAvailable), carga de 5 min por CPU, tempo
desde o boot, e — para a descoberta e a comparação — serviços do systemd, portas em escuta com o
processo e containers locais. Nunca: linha de comando, pid, ambiente, arquivo de configuração, log.

## Componentes de um alvo `host`

Todo componente declarado com `origem` ganha quatro perguntas comuns, lidas por SSH com os moldes de
`references/host/linux.toml`: estado, tempo no ar, reinícios e memória — de `systemctl show` (unit),
`docker inspect` e `docker stats` (container) ou `ps -e -o comm=,rss=,etimes=` (processo; a memória é a
do processo mais antigo, nunca a soma dos workers). Banco com `backup_pasta` ganha a idade do backup
mais novo, pela data no nome do arquivo (`AAAA-MM-DD` ou `AAAAMMDD`) ou, sem data, pelo mtime da
listagem.

Com `leitura` declarada, o catálogo do produto (`references/produtos-host/<produto>.toml`) acrescenta
os dados dele, pelo cliente instalado no servidor: MariaDB/MySQL (tamanho, tamanho por banco, conexões e
uso contra `max_connections`, consultas lentas, binlog), Postgres (tamanho, por banco, conexões e uso),
Redis (memória, descartes, taxa de acerto) e Qdrant (coleções, pontos, status). Nunca: conteúdo de
tabela, valor de variável que não seja contador ou limite, linha de comando, ambiente.
