# Allowlist de comandos (read-only)

Fonte da verdade no código: `scripts/lib/allowlist.py` (o `runner` só executa o que passa aqui).
Match sobre os **dois primeiros tokens** após `docker` — par `(noun, verb)`.

## Permitidos `(noun, verb)`
`(context, ls)` · `(context, inspect)` · `(info, -)` · `(version, -)` · `(node, ls)` ·
`(node, inspect)` · `(service, ls)` · `(service, ps)` · `(service, inspect)` · `(ps, -)` ·
`(container, inspect)` · `(network, ls)` · `(network, inspect)` · `(secret, ls)` ·
`(config, ls)` · `(image, ls)`

## Proibidos explicitamente (mesmo parecendo "leitura")
`logs`, `cp`, `export`, `save`, `events`, `stats` (streaming/só 1 nó), `exec`,
**`config inspect`** (devolve o VALOR do config), `secret inspect`, `swarm join-token`
(vaza token de entrada no cluster), e **todo verbo mutante**
(`rm`, `kill`, `restart`, `create`, `update`, `scale`, `prune`, `build`, `rmi`, `promote`, `demote`…).

## Regras de ouro
- **Nunca** `shell=True`; sempre args-array (sem injeção via nome de objeto).
- Seleção de cluster via **env `DOCKER_CONTEXT`** — a flag `--context`/`-H` é bloqueada (viraria "noun").
- Qualquer par fora da allowlist → exceção (não executa).
