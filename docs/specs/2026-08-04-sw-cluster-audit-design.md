# sw-cluster-audit — auditoria read-only de cluster → relatório

> Spec de design de uma skill nova do marketplace. Snapshot on-demand, técnico, de um cluster
> Docker (context/Swarm), com relatório em HTML (primário) + PDF (opt-in). **Read-only** e sem
> vazar segredo — inegociável. Escrito como contexto pro agente executor (sw-plan), não prosa.

## Objetivo & outcome
Em 1 acionamento, um retrato **técnico confiável e honesto** do estado atual de um cluster Docker
— saúde, nodes, services, segurança, rede — sem rodar 20 comandos na mão, **sem mutar nada** e
**sem vazar segredo**. Outcome/métrica: relatório gerado com **zero mutação** no cluster e **zero
valor de secret/env** no output.

## Exploração & decisões
- **Snapshot on-demand** ("como está tudo agora"), público **técnico**.
- **Docker-first** (context/Swarm) em v1; extensível a k8s depois, **mas sem framework de plugin
  agora** (YAGNI — o modelo k8s é diferente; abstrair cedo é chute).
- **Degrada com honestidade**: o que não dá pra coletar vira `n/a (motivo)`; nunca finge dado.
- **Abordagem A**: `collect.py` (read-only) → `report.json` → agente prioriza/escreve → `build_report.py` → HTML/PDF.
- **Hardening do revisor** (aplicado abaixo): redação field-allowlist, findings por regra, HTML-primary, escopo honesto cross-node.

## Não-objetivos (v1)
- **Não altera NADA** (read-only estrito). Não instala ferramenta sem pedir.
- **Sem k8s/cloud** (só um módulo de coletor Docker limpo, sem framework de plugin).
- Sem monitoramento contínuo/alertas, sem APM/tracing de app, **sem histórico/tendência** (é snapshot).
- **Não afirma alcançabilidade externa real** (firewall/security-group da cloud é invisível) — só config de publicação.
- **Não coleta uso de recurso por nó** (não existe sem stack de métricas) — só capacidade.

## Restrição de simplicidade
A menor solução: `collect.py` + `build_report.py` + template HTML + `SKILL.md` + `references/`.
**Sem** framework de plugin, **sem** lib de PDF (usa Chromium se houver, senão HTML). Findings por
**regra simples**, não engine. Nada de abstração especulativa.

## Appetite
Médio — ~3-5 dias. Se estourar: cortar a seção **Rede** antes da **Segurança**; **PDF** antes do **HTML**.

## MVP vs MLP
**MVP** — retrato técnico confiável. O "bonito" é um MLP **leve** (template caprichado: semáforo,
cards, badges) que **não trava** a coleta.

## Arquitetura & fluxo
```
1. Detecta orquestrador + lista contexts → CONFIRMA o alvo (mostra `docker context ls` + ativo,
   confirma a identidade via AskUserQuestion — sobretudo produção)
2. collect.py --context <ctx> --out <dir>
     → runner: subprocess ARGS-ARRAY (nunca shell=True), timeout por comando, allowlist de VERBO
       checada programaticamente + deny-list explícita
     → coletores por seção (só leitura)
     → REDATOR (field-allowlist; env = só chaves; scrub de token/cred) ANTES de escrever JSON
     → REGRAS derivam findings determinísticos (privileged=true, porta=0.0.0.0, imagem :latest…)
     → report.json (schema versionado; coleta parcial é válida — timeout vira n/a)
3. Agente lê report.json → PRIORIZA findings + escreve prosa/recomendações (NÃO inventa fato)
4. build_report.py --dir <dir> → HTML (primário) → PDF (opt-in, se Chromium)
5. Grava docs/infra/<cluster>/<AAAA-MM-DD_HHMM>-relatorio.{html,pdf} + report.json
   (docs/infra/ garantido no .gitignore ANTES do primeiro arquivo)
```

## Componentes (unidades isoladas)
- **`collect.py`** — orquestra a coleta. Sub-unidades: *runner* (args-array, timeout, allowlist/deny
  enforcement), *coletores docker* (por seção), *redator* (field-allowlist + env-keys-only + scrub),
  *regras* (findings determinísticos), *writer* (report.json schema v1, parcial-válido).
- **`build_report.py`** — `report.json` → HTML (template) → PDF opt-in (Chromium `--no-sandbox` se houver).
- **`assets/report-template/`** — HTML/CSS (semáforo, cards de resumo, tabelas, badges de severidade, tema claro imprimível).
- **`references/`** — allowlist de comandos + deny-list + o-que-coletar-por-seção + catálogo de regras de finding.
- **`SKILL.md`** — fluxo, gates via AskUserQuestion, garantias de segurança.

## Coleta (read-only) — allowlist `(noun, verb)` + field-allowlist POSITIVA
**Allowlist como pares `(noun, verb)` explícitos**, com match sobre os **dois primeiros tokens**
do comando (assim `("context","inspect")` é permitido e `("config","inspect")` NÃO):
`(context,ls)`, `(context,inspect)`, `(info,-)`, `(version,-)`, `(node,ls)`, `(node,inspect)`,
`(service,ls)`, `(service,ps)`, `(service,inspect)`, `(ps,-)`, `(container,inspect)`,
`(network,ls)`, `(network,inspect)`, `(secret,ls)`, `(config,ls)`, `(image,ls)`.
**Deny explícito** (mesmo parecendo "leitura"): `(container,logs)`/`(service,logs)`, `(container,cp)`,
`(container,export)`, `(image,save)`, `(system,events)`, `(container,stats)` (pendura + só 1 nó),
`(container,exec)`, **`(config,inspect)`** (devolve o valor do config), `(secret,inspect)`,
`(swarm,join-token)`, e **todo verbo mutante** (`rm/kill/restart/create/update/scale/prune/build/rmi/...`).
Qualquer par fora da allowlist → **aborta** (não executa).

**Field-allowlist POSITIVA e UNIVERSAL** (vale pra TODOS os `inspect`, não só container). O writer
serializa **SÓ** os campos abaixo por tipo de objeto e **descarta todo o resto por default** (campos
novos de versões futuras da API entram como descartados, não vazados):
- **container/service:** `image`+tag+digest, `Mounts` (source/target/type — sem conteúdo), `Ports`,
  `Privileged`, cap-add/drop, `User`, restart policy. **NUNCA** `Env`, `Cmd`/`Command`, `Args`,
  `Labels` (nem em `Config.*`, nem em `TaskTemplate.ContainerSpec.*`, nem `Spec.Labels`). **Env → só as CHAVES.**
- **node:** role, availability, state, addr (host), CAPACIDADE (NanoCPUs/MemoryBytes). Descarta `Labels`/`Options`.
- **network:** nome, driver, scope, `Attachable`, `Ingress`, subnets. Descarta `Options`/`Labels`.
- **context:** só nome + endpoint host (sem paths de cert, sem `TLSInfo`).

Por seção (cada item degrada pra `n/a` com motivo):
- **Saúde/visão geral:** `docker info` (com scrub de registry-mirror/proxy com cred), `node ls`,
  `service ls` (contagens), containers exited/unhealthy (do nó conectado — **escopo anotado**).
- **Nodes:** `node ls` + `node inspect` → role, availability, estado (Ready/Down), Leader,
  **CAPACIDADE** (NanoCPUs/MemoryBytes) + soma de *reservations* das services. **Uso real = `n/a (requer Prometheus/cAdvisor)`**.
- **Services:** `service ls` + `service ps` → réplicas desejadas×rodando, restarts, tasks falhas,
  imagem+tag+digest; estado.
- **Segurança (findings por REGRA, derivados de `service inspect` — cluster-wide — de preferência):**
  privileged, cap-add, mounts sensíveis (`docker.sock`, `/`, `/etc`), user root, imagem `:latest`/sem
  digest, portas em `0.0.0.0`, **NOMES** de secrets/configs (jamais valores). Checagens em nível de
  **container** (`ps`/`inspect`) cobrem **só o nó conectado** → o relatório diz isso explicitamente.
- **Rede/tráfego:** `network ls`, overlays, portas publicadas/ingress (no Swarm o **ingress mesh
  publica em TODOS os nós**, independentemente de onde a task roda), attachable.

## Análise por componente (app-aware)
A skill **identifica genericamente** o tipo de cada workload pela imagem (`detect_kind`: traefik→
ingress/proxy, nginx/haproxy/envoy/caddy→proxy, rabbitmq/kafka/nats→fila, redis→cache/fila,
postgres/mysql/mongo→banco, elasticsearch→busca, prometheus/grafana→observabilidade, senão `app`)
e coleta **fatos por tipo** (réplicas, restarts, portas, persistência) + os **labels de roteamento
do Traefik** (`traefik.*`). O **agente** — que entende essas ferramentas — escreve a **análise
específica** por componente (ex.: "Traefik roteia `Host(app.x)` → service X, 1 réplica = gargalo";
"fila com restarts altos = instável"; "DB com 1 réplica = sem HA") no campo `components_analysis`,
que o `build_report.py` renderiza numa seção "Análise por componente". **Fatos por regra; análise
pelo agente.**

**Segurança dos labels (extensão da FF2):** só labels com prefixo allowlisted (`traefik.`) são
extraídos; o **valor** de chaves que casam padrão sensível (`basicauth|.users|password|secret|
token|apikey|credential|authorization`) é **redigido** (`***`). Decisão do dono: "labels de
roteamento amplos" (extrai `traefik.*` inteiro, redigindo o sensível) — risco residual aceito em
chaves não-óbvias; labels fora do prefixo são 100% descartados.

## Contrato: `report.json` (schema v1)
Fonte única entre o writer (`collect.py`), o reader (`build_report.py`), o agente e as fixtures.
Coleta parcial é **válida**: qualquer valor pode ser `{"status":"n/a","reason":"..."}` em vez do dado.
```jsonc
{
  "schema_version": 1,
  "generated_at": "2026-08-04T14:32:00Z",   // passado pelo caller (não Date.now no script)
  "cluster": { "context": "systemweb-prod", "engine_version": "...", "swarm": true },
  "scope": { "connected_node": "node-1", "container_checks_cover": "only_connected_node" },
  "health": { "verdict": "green|yellow|red", "counts": { "nodes": 3, "services": 12, "unhealthy": 1 } },
  "nodes":    [ { "id", "role", "availability", "state", "leader": true, "capacity": {"nano_cpus","mem_bytes"}, "reservations_sum": {...} } ],
  "services": [ { "name", "image", "tag", "digest", "replicas", "ports", "env_keys": ["K"], "kind": "app|proxy|fila|banco|…", "routing_labels": {"traefik...": "..."} } ],
  "components_analysis": { "<service>": "análise específica escrita pelo agente" },
  "networks": [ { "name", "driver", "scope", "attachable", "ingress" } ],
  "secrets":  [ { "name" } ],   // NOMES only
  "configs":  [ { "name" } ],   // NOMES only
  "findings": [ { "rule_id": "SEC_PRIVILEGED", "severity": "high|med|low", "object": "service/web",
                  "evidence": "Privileged=true", "fix": "remover --privileged", "scope": "cluster-wide|node-1" } ],
  "not_collected": [ { "what": "uso de CPU/mem por nó", "reason": "requer Prometheus/cAdvisor" } ]
}
```
- **`findings`** são produzidos por REGRA no `collect.py` (não pelo agente). Cada regra tem `rule_id`
  estável, `severity`, `evidence` (o fato cru) e `fix` (comando/mudança). O agente **prioriza e
  escreve a prosa** a partir deles — nunca cria/edita `findings`.
- **`scope`** deixa explícito no dado (não só no texto) que checagens de container cobrem só o nó conectado.

## Segurança da própria skill (invariantes → viram fitness functions)
1. Todo comando passa por **allowlist de verbo checada em código** + deny-list explícita; `subprocess`
   com **args-array**, nunca `shell=True` (injeção via nome de container/serviço).
2. **Redação no `collect.py` ANTES do JSON**: nenhum valor de `Env/Cmd/Args/Labels`/config; env = chaves;
   scrub de tokens/URLs-com-cred no `docker info`. (O `report.json` entra no contexto do agente e pode ir a logs.)
3. **`docs/infra/` no `.gitignore` do projeto-alvo, escrito ANTES** de qualquer arquivo (não-opcional);
   alternativa: gravar fora do repo. Infra (hostnames/IPs/portas/nomes) não vai pro git.
4. **Zero rede de saída** (nenhuma telemetria/upload; único socket é o daemon Docker).
5. **Confirma a identidade do context-alvo** via AskUserQuestion antes de coletar.

## Relatório (HTML primário, PDF opt-in)
Header (cluster, context, data-hora, versão do engine, **semáforo** 🟢🟡🔴) → sumário técnico
(contagens + top achados) → **Nodes** (tabela) → **Services** (tabela) → **Segurança** (por
severidade; cada finding com a **regra que disparou** + **comando de correção** sugerido) → **Rede**
→ **Recomendações priorizadas** → **Apêndice**: "o que não foi coletado e por quê" + **escopo**
(quais nós as checagens de container cobriram). Template caprichado (cards, badges).
**Template 100% self-contained** — CSS e fontes **inline**, **zero asset remoto** (nada de Google
Fonts/CDN), pra não violar o "zero rede de saída". PDF via Chromium headless (`--no-sandbox`,
**offline**) se disponível; senão entrega o HTML e avisa.

## Fluxo de dados
`docker (read-only) → collect.py (redige + regras) → report.json (schema v1, parcial-válido) →
agente (prioriza/prosa) → build_report.py → HTML/PDF em docs/infra/`. O `report.json` fica junto
(auditável), **gitignored** por padrão.

## Tratamento de erro
- Verbo fora da allowlist → **aborta** (bug de dev), nunca executa.
- **Timeout** por comando → aquele dado vira `n/a`, o resto do relatório sai.
- **Docker standalone** (não-Swarm) → node/service = `n/a`; foca em containers/redes locais.
- **Sem Chromium** → HTML + aviso (exit 0).
- **Context inacessível/TLS** → erro claro, não parcial silencioso.
- `report.json` **parcial é válido** (campos ausentes = `n/a`); `build_report.py` tolera.

## Testes
- **Unit — allowlist:** pares fora da allowlist (`(config,inspect)`, `(container,exec)`, `(service,rm)`)
  são rejeitados; match nos 2 primeiros tokens.
- **Unit — redação (positiva/universal):** env vira chaves; `service` com `command`/`args`/`Spec.Labels`
  não vaza; valor de config nunca aparece; `docker info` com `http://user:pass@proxy` é redigido;
  campo desconhecido no inspect é **descartado** (não vaza por default).
- **Unit — regras:** privileged/`:latest`/`0.0.0.0`/mount `docker.sock` viram `findings` com `rule_id`+`fix`.
- **Unit — resiliência:** `report.json` parcial (com `n/a`) é válido; timeout de comando não derruba o run.
- **Unit — confirmação:** sem resposta ao gate de context, nenhum comando de coleta é executado.
- **Estático — egress:** `collect.py`/`build_report.py`/template sem `requests`/`urllib`/`http.client`/`socket`
  (fora do daemon) e template sem URL `http(s)://`.
- **Integração:** fixture de `report.json` → `build_report.py` gera HTML sem quebrar; degrada sem Chromium (só HTML).
- **Fixture maliciosa:** container nomeado `a; touch /tmp/pwned` **não** cria o arquivo (args-array).

## Decisões (estilo ADR)
- **Coletores + agente-só-prosa (não agente-descobre).** Contexto: auditoria exige fatos confiáveis;
  LLM alucina/perde achado. Decisão: findings por **regra determinística** no `collect.py`; o agente
  prioriza e escreve. Alternativas descartadas: agente coleta+julga (não confiável); script faz-tudo
  com PDF próprio (perde recomendação contextual). Consequências: findings auditáveis; agente agrega na priorização/prosa.
- **Redação field-allowlist antes do JSON.** Contexto: `report.json` entra no contexto do agente e
  `inspect` vaza env/labels/config. Decisão: nunca serializar `Env/Cmd/Args/Labels`/valor de config;
  env=chaves; redigir pré-JSON. Alternativa descartada: redigir por regex depois (perde `DB_PASS`,
  connection strings). Consequências: segredo nunca sai do daemon.
- **HTML primário, PDF opt-in.** Contexto: Chromium headless em box de infra (root) é peso/frágil.
  Decisão: HTML é o entregável; PDF só se Chromium existir. Alternativas descartadas: weasyprint/reportlab
  (deps pesadas), PDF obrigatório (quebra em headless). Consequências: sempre entrega algo; PDF é bônus.
- **Docker-first sem framework de plugin.** Contexto: k8s tem modelo diferente; abstrair cedo é chute.
  Decisão: módulo de coletor Docker limpo; k8s depois. Alternativa descartada: framework pluggable já (YAGNI).
- **`.gitignore` não-opcional.** Contexto: relatório tem hostnames/IPs/portas; repo público. Decisão:
  garantir `docs/infra/` no `.gitignore` antes de gerar. Consequência: infra não vaza pro git.

## Restrições verificáveis (fitness functions)
1. **Só pares `(noun,verb)` da allowlist executam:** o runner rejeita `(config,inspect)`,
   `(container,exec)`, `(container,logs)`, `(service,rm)` etc. (match nos 2 primeiros tokens) →
   exceção, não execução.
2. **Zero valor de secret/env/config em QUALQUER inspect** (serialização positiva). Fixtures cobrindo:
   (a) container `-e DB_PASSWORD=x`; (b) **service** com `command:["--token","abc"]` / `args:["--password=x"]`
   / `Spec.Labels`; (c) `docker info` com registry-mirror `http://user:pass@proxy`. Em todos: o output
   (`report.json` **e** HTML) contém a **chave** mas **nunca** o valor, e a cred do proxy é redigida.
3. **Sem shell injection:** container nomeado `a; touch /tmp/pwned` não cria o arquivo (subprocess args-array).
4. **Degrada sem quebrar:** sem Chromium → gera HTML e exit 0 com aviso; comando em timeout → aquela
   seção vira `n/a` e o resto sai; `report.json` parcial é válido.
5. **Confirmação do context é obrigatória:** a coleta **aborta** se o gate de confirmação do context-alvo
   não foi respondido (inv. 5) — testável sem daemon real (mock do prompt → sem resposta → nenhum comando roda).
6. **`.gitignore` (caminho in-repo):** primeiro run num repo limpo adiciona a linha do **diretório**
   `docs/infra/` (cobre `.html`/`.pdf`/`.json`) **antes** de escrever qualquer arquivo. *(No caminho
   "gravar fora do repo" não há `.gitignore` — esta FF vale só in-repo.)*
7. **Zero rede de saída (método objetivo):** check estático de que `collect.py`, `build_report.py` **e**
   o template não usam `requests`/`urllib`/`http.client`/`urlopen`/`socket` (fora do socket do daemon) e
   o template **não referencia** nenhuma URL `http(s)://` (asset remoto). Cobre coleta, geração do PDF e o HTML.

## Hipóteses a testar
- O alvo é **Swarm multi-nó** — se for docker standalone, node/service viram `n/a` (tratado).
- **`service inspect` cobre os achados de segurança cluster-wide** o suficiente pra não depender do
  `ps` por-nó — validar num Swarm real; se não, o relatório assume o escopo "só o nó conectado".
