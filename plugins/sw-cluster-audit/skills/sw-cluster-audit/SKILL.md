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
- **NÃO invente findings** — eles vêm por regra. Você **prioriza** (o que é mais grave/urgente) e
  escreve a **prosa/recomendações**.
- **Análise por componente:** para cada service, use o `kind` + `routing_labels` + réplicas/portas
  e escreva a análise específica (você entende essas ferramentas) no campo `components_analysis`
  do `report.json` (`{ "<service>": "texto" }`), ex.:
  - **Traefik/proxy:** "roteia `Host(app.x)` → service `app-x` via `websecure` (TLS on); 1 réplica = ponto único".
  - **Fila (rabbitmq/kafka):** "restarts altos / sem réplica = instável; consumidores?".
  - **Banco:** "1 réplica = sem HA; volume presente (persistência ok)".
  - **Cache/Redis:** "usado como cache vs fila; persistência?".
- Grave o `report.json` de volta (só o `components_analysis` e, se quiser, um resumo em `health`).

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
