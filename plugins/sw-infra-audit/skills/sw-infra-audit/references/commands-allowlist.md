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

## Egresso HTTP autenticado (`admin_http`)

A única chamada de rede da skill que leva credencial. Tudo passa por
`lib/http_get.get_autenticado`, e nenhum outro módulo monta header de autenticação.

| O que | Como |
|---|---|
| Método | `GET`, sempre — fixado no código de `get_autenticado`, sem parâmetro que o troque |
| Destino | só `(host, porta)` da `admin_url` declarada e confirmada na rodada; outra porta do mesmo host é recusada |
| Caminhos | só os de `references/apis/<familia>.toml`. O carregador (`lib/catalogo_api.py`) recusa `//`, `..`, esquema absoluto, rota de escrita (`contents`, `purge`, `publish`, `actions`…), rota GET que devolve segredo (`definitions`, `users`, `permissions`, `parameters`, `connections`…) e qualquer parâmetro que não seja `columns` |
| Credencial | objeto `Credencial`, amarrado a (alvo, host, porta); `get_autenticado` chama `.para(url, alvo)` e recusa par solto ou string |
| Senha na URL | recusada em `check_allowed` (todas as funções de rede) e ao ler o `alvos.toml` |
| Origem da senha | variável de ambiente cujo **nome** está em `senha_env`, lida só por `lib/credencial.py` |
| Redirect | não é seguido — o header não viaja para outro host |
| Resposta acima de 4 MB | recusada com o motivo dito, nunca cortada em silêncio |
