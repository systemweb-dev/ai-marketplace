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
