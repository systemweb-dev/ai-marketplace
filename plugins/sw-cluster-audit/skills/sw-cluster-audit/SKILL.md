---
name: sw-cluster-audit
description: >-
  Audita um cluster Docker (context/Swarm) de forma READ-ONLY e gera um relatório técnico
  (HTML + PDF opcional) — saúde geral, nodes, services, segurança, rede e ANÁLISE POR COMPONENTE
  (identifica genericamente Traefik/nginx/filas/bancos/cache/etc. e analisa cada um: roteamento,
  réplicas, HA, exposição). Use SEMPRE que o usuário quiser um raio-x/auditoria/relatório do
  cluster ou da infra — "analisa meu cluster", "auditar o docker context systemweb-prod", "como
  está a infra/o swarm", "saúde do cluster", "relatório do cluster", "como o traefik está
  roteando pro app X", "como está a fila/o banco", "o cluster está ok?". Dispare mesmo sem a
  palavra "auditar" — basta a intenção de entender o ESTADO ATUAL de um cluster/infra Docker.
  É SÓ LEITURA: nunca altera, reinicia, escala ou mexe no cluster; nunca expõe valores de
  secret/env. NÃO use para: fazer deploy ou alterar/criar serviços/stacks, nem para código de
  app local (não é infra). Interação e relatório em português (PT-BR).
---

# Cluster Audit — raio-x read-only de um cluster Docker

Tira uma **fotografia técnica** do estado atual de um cluster Docker (context/Swarm) e gera um
**relatório** (HTML primário + PDF opcional) em `docs/infra/`. **Fatos vêm de comandos read-only
+ regras determinísticas; a análise/priorização é sua (agente).**

**Anuncie no início:** "Estou usando a skill sw-cluster-audit para auditar o cluster."

## 🔒 Garantias de segurança (inegociáveis)
- **100% read-only.** Só comandos de leitura (allowlist `(noun,verb)` em `scripts/lib/allowlist.py`).
  **NUNCA** rode `rm/kill/restart/exec/create/update/scale/prune/build`, `logs`, `cp`, `config inspect`,
  `secret inspect`, `swarm join-token`. Toda coleta passa pelo `collect.py` (que já barra isso).
- **Nunca exponha segredo.** O relatório mostra **nomes** de secrets/configs e **chaves** de env —
  jamais valores. O `collect.py` redige antes de gravar. Não contorne rodando `docker inspect` na mão.
- **Não vaza infra pro git.** O output vai em `docs/infra/`, adicionado ao `.gitignore` automaticamente.
- **Tudo local.** Zero telemetria/upload.

## Fluxo (toda decisão via AskUserQuestion)

### 1. Descobrir e CONFIRMAR o cluster-alvo
- Rode `docker context ls` e mostre os contexts. Se o usuário citou um (ex.: `systemweb-prod`), destaque-o.
- **`AskUserQuestion`**: confirme QUAL context auditar (mostrando o alvo). **Sobretudo produção** —
  não assuma o context ativo. A confirmação vira o `--confirmed-context`.

### 1b. Métricas de runtime — automático, nada fixo
O `collect.py` **descobre sozinho** as fontes de métrica olhando os próprios fatos do cluster
(quem é Prometheus/exporter, portas publicadas, host do context) e usa a melhor que responder:
**servidor Prometheus** (janelas de 24h, taxas) → senão **exporter cru** (`/metrics`, valores
instantâneos). Traz requests/24h e 5xx por app, profundidade de fila, CPU/memória.

**Segurança:** a allowlist de rede é **derivada** — só o **host do context que você já confirmou**.
Nenhum IP no código, nenhum host de fora do cluster auditado é alcançável. `--metrics off` desliga.
Se nada responder (firewall, porta fechada), o relatório diz **por quê** e segue sem — sem inventar.

### 2. Coletar (read-only)
Pegue o timestamp e monte o diretório de saída:
```bash
AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ"); STAMP=$(date +"%Y-%m-%d_%H%M")
OUT="docs/infra/<context>/$STAMP"
python3 <skill-dir>/scripts/collect.py --context <context> --confirmed-context <context> \
  --out "$OUT" --at "$AT"
```
Isso grava `$OUT/report.json` (schema v1, com os **fatos** + **findings por regra** + `kind`/
`routing_labels` por service). Se o context não bater `--confirmed-context`, a coleta aborta (gate).

### 3. Analisar (você, agente) — leia o `report.json` e ENRIQUEÇA
O `collect.py` já preencheu os **fatos**: `findings` (por regra), `dimensions` (notas de
Segurança/Disponibilidade/Higiene), `top_offenders` e `history` (diff vs a auditoria anterior).
Você escreve a **narrativa** — **NÃO invente findings** (eles vêm por regra); você **interpreta e
prioriza**. Grave estes campos de volta no `report.json`:

- **`summary`** — 2-4 frases dizendo **por que** o veredito é esse (a *situação*): ex. "Crítico
  porque o Traefik é ponto único de 17 apps, 3 bancos + fila estão sem HA, e 45 containers rodam root."
- **`strengths`** (lista) — o que está **bom** (nodes Ready, TLS Let's Encrypt, services com 2+ réplicas…).
- **`weaknesses`** (lista) — o que **preocupa** (SPOFs stateful, root difundido, imagens sem digest…).
- **`recommendations`** (lista de `{title, why, command, impact, effort, scope}`) — as ações
  **priorizadas**. **Sempre inclua `command`**: o comando/trecho pronto pra rodar (ex.:
  `docker service update --replicas 2 traefik_traefik`), não só o "porquê". Multi-linha e
  comentários (`#`) são suportados. Foque no que move o ponteiro.
- **`components_analysis`** (`{ "<service>": "texto" }`) — análise específica por componente, usando
  `kind` + `routing_labels` + réplicas (você entende essas ferramentas):
  - **Traefik/proxy:** "roteia `Host(app.x)` → `app-x` via websecure (TLS on); 1 réplica = ponto único".
  - **Fila (rabbitmq/kafka):** "1 réplica = sem HA; se cair, mensageria para; confirmar persistência".
  - **Banco:** "1 réplica = sem HA/failover; garantir backup + volume".
  - **Cache/Redis:** "cache vs broker (Celery?) muda a criticidade; persistência?".
- Grave o `report.json` de volta com esses campos preenchidos (o resto é determinístico, não mexa).

### 4. Gerar o relatório
- **`AskUserQuestion`**: "Gerar PDF também, ou só o HTML?" (o PDF exige Chromium; sem ele, cai no HTML).
```bash
python3 <skill-dir>/scripts/build_report.py --dir "$OUT"
```
Gera `$OUT/relatorio.html` (sempre) e `$OUT/relatorio.pdf` (se houver Chromium).

### 5. Entregar
- Informe os paths (`$OUT/relatorio.html`, `.pdf`, `report.json`) e um **resumo no chat**: semáforo
  de saúde, top achados de segurança priorizados, e os destaques por componente.
- Confirme que `docs/infra/` está no `.gitignore` (o `collect.py` garante) — **não commite** o relatório.

## Como a saúde é calculada (não confunda risco com falha)
**Saúde = operação.** Um cluster que está rodando não vira "crítico" por higiene ruim.

- 🔴 **Degradado** — só quando algo está **realmente fora do ar**: nó não-Ready.
- 🟡 **Operacional com ressalvas** — está rodando, mas há risco conhecido: serviço parado a
  confirmar, réplicas degradadas, SPOF (1 réplica em banco/fila/ingress) ou achado crítico de segurança.
- 🟢 **Operacional** — convergido, redundante e sem achado crítico.
- ⚪ **Sem dados** — a coleta falhou; a skill não inventa nota.

Quatro dimensões separadas: **Operação · Disponibilidade · Segurança · Higiene**. Achados
**esperados** (`expected: true`) não pesam na nota — ex.: Traefik/cAdvisor/Promtail montam o
`docker.sock` porque é assim que funcionam; um `flyway`/`migrate` em 0 réplicas é job concluído,
não serviço caído. Ao escrever a narrativa, **respeite essa distinção**: risco ≠ incidente.

## O que o relatório traz

**Um único documento, tudo visível** (nada recolhível — no PDF não dá pra clicar):
1. **Panorama** (nós, serviços, aplicações, requests) · 2. **Notas por dimensão** ·
2b. **Desde a auditoria anterior** (resolvidos/novos) · 3. **Recomendações** com **comando pronto** ·
4. **Fortes × atenção** · 5. **Nós do cluster** (card por master/worker: estado, engine, plataforma,
capacidade, tasks rodando/falhadas) + **disco** · 6. **Por aplicação** (stacks agrupados com rotas
do Traefik e análise) · 7. **Achados** agrupados e explicados · 8. **Redes** · 9. **Secrets/configs** (nomes).

**PDF = HTML.** O template é *print-first* (`print-color-adjust:exact`, `@page A4`, quebras
controladas) — o Chrome não achata as cores e o layout não colapsa em uma coluna.

## Checagens além do estado atual
- **Certificado TLS do context** (`lib/cert.py`): lê **só a data** de `cert.pem` (nunca a chave
  privada) e avisa — crítico se expirado, atenção se faltam < 30 dias. Context `ssh://` não tem
  certificado → ignora em silêncio.
- **Falha de acesso vira achado:** se a coleta falhar por certificado expirado ou daemon
  inacessível, isso aparece como achado crítico com o motivo real (não um "indisponível" genérico).
- **Confiabilidade por serviço:** sem limite de CPU/memória, sem healthcheck, tasks que falharam
  recentemente, constraints de placement.

## Honestidade (o que a skill NÃO afirma)
- **Uso de CPU/mem por nó** não existe sem stack de métricas → aparece como `n/a`. Só **capacidade**.
- **Checagens em nível de container** cobrem só o **nó conectado** (o `scope` do report diz isso);
  achados de segurança de service são cluster-wide.
- **"Porta em 0.0.0.0"** = publicada em todas as interfaces do host, **não** significa alcançável da
  internet (firewall/security-group da cloud é invisível).
- v1 suporta **Docker (context/Swarm)**; Kubernetes fica pra depois.

## Arquivos da skill
- `scripts/collect.py` — coleta read-only → `report.json`. `scripts/build_report.py` — HTML/PDF.
- `scripts/lib/` — `allowlist` · `runner` · `redact` (redação) · `rules` (findings) · `report` (schema).
- `assets/report-template/template.html` — template self-contained. `references/` — allowlist, coleta, regras.
- `tests/` — suíte (as fitness functions de segurança). Rode com `pytest` num venv se for editar.
