# Allowlist de comandos (read-only)

Fonte da verdade no código: `scripts/lib/coletores/docker_allowlist.py` (o `runner` só executa o que passa aqui).
Match sobre os **dois primeiros tokens** após `docker` — par `(noun, verb)`.

## Permitidos `(noun, verb)`
`(context, ls)` · `(context, inspect)` · `(info, -)` · `(version, -)` · `(node, ls)` ·
`(node, inspect)` · `(node, ps)` · `(service, ls)` · `(service, ps)` · `(service, inspect)` · `(ps, -)` ·
`(container, inspect)` · `(network, ls)` · `(network, inspect)` · `(secret, ls)` ·
`(config, ls)` · `(image, ls)` · `(system, df)`

## Forma exata, fora dos pares
`docker inspect --type task --format '{{.Status.ContainerStatus.ContainerID}}' <id da task>`

É o que liga o container do exporter de nó ao hostname. O tipo e o formato são fixos, e só o id
varia. Qualquer outro `docker inspect` é recusado: outro `--type` lê config ou secret, e outro
`--format` devolveria o `Env` da task.

`docker exec <container> <comando do catálogo>`

É a leitura de filas sem senha, a última fonte depois da API e do exporter. O comando é uma forma
exata de `references/execs/<familia>.toml`, conferida token a token, com o id do container em
hexadecimal e nada entre `exec` e o id: sem flag, sem `-it`, sem `sh -c`, sem argumento livre. A
única vaga é o vhost, que vem da saída do próprio comando e passa por validação. Só serviço cujo
produto está no catálogo recebe `exec`, e catálogo inválido recusa todos. O id sai de
`docker ps --filter label=com.docker.swarm.service.name=<serviço> --format '{{.ID}}'`, com o
cluster escolhido por `DOCKER_CONTEXT`, e container em outro nó fica sem dados.

## Proibidos explicitamente (mesmo parecendo "leitura")
`logs`, `cp`, `export`, `save`, `events`, `stats` (streaming/só 1 nó), `exec` fora do catálogo,
**`config inspect`** (devolve o VALOR do config), `secret inspect`, `swarm join-token`
(vaza token de entrada no cluster), `inspect` genérico, e **todo verbo mutante**
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

## Egresso de logs (`logql`)

Anônimo, pelo mesmo `lib/http_get.py`, para as URLs mais acessadas.

| O que | Como |
|---|---|
| Método | `GET`, sempre |
| Destino | só `(host, porta)` da `logs_url` do alvo docker, declarada e confirmada na rodada |
| Caminho | só `/loki/api/v1/query_range`; o carregador (`lib/catalogo_logs.py`) recusa qualquer outra rota |
| Consulta | só a de `references/logs/<familia>.toml`, em forma fixa terminada em `line_format`; nada vem do `alvos.toml` |
| Parâmetros | `query`, `start`, `end`, `limit=5000` e `direction=backward` |
| Redirect | não é seguido |
| Resposta acima de 32 MB por janela | recusada com o motivo dito, nunca cortada em silêncio |
| Linha bruta | nunca lida, gravada ou impressa; `Cookie` e `Authorization` não saem da consulta |
