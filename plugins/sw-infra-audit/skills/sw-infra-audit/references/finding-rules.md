# Catálogo de regras de finding (determinísticas)

> **Esta página cobre só a família `SEC_*`.** O registro completo — hoje 21 regras, com as
> `OPS_*`, as do coletor HTTP e `fila_sem_consumidor` — é `scripts/lib/regras.py`, e é ele que
> vale. Regra que existe no código e não aqui não é regra inválida: é esta página atrasada.

Implementado em `scripts/lib/rules.py`. Cada finding tem `rule_id`, `severity`, `object`,
`evidence` (o fato cru), `fix` (correção sugerida) e `scope` (`cluster-wide` ou o nó conectado).
**Os findings vêm daqui (regra); o agente só prioriza e escreve a prosa — nunca inventa finding.**

| rule_id | sev | dispara quando | fix sugerido |
|---|---|---|---|
| `SEC_PRIVILEGED` | high | `Privileged=true` | remover `--privileged`; conceder só as capabilities necessárias |
| `SEC_DOCKER_SOCK` | high | bind de path sensível do host (`docker.sock`, `/`, `/etc`, `/root`, `/proc`, `/sys`) | remover o mount ou usar socket-proxy read-only |
| `SEC_PORT_EXPOSED` | med | porta publicada em `0.0.0.0`/`::` (todas as interfaces do host) | publicar só na interface interna, ou firewall |
| `SEC_IMAGE_UNPINNED` | med | tag `latest` **ou** sem digest fixo | fixar tag imutável + digest (`image@sha256:…`) |
| `SEC_USER_ROOT` | med | user `root`/uid `0`/`0:*` **ou** `USER` ausente (default root) | definir `USER` não-root na imagem/service |

**Verdict de saúde:** a saúde **não** vem da gravidade dos achados — vem da dimensão
`operacao`. 🔴 algo fora do ar · 🟡 rodando com risco conhecido · 🟢 convergido. Um achado
`high` de higiene (imagem sem digest, container privilegiado) aparece na lista de achados e
**não** pinta o alvo de vermelho. A regra está em `lib/metrics.py` e explicada em
"Como a saúde é calculada", no SKILL.md.

Adicionar regra nova = uma função pura em `rules.py` + um caso em `tests/test_rules.py`. Mantenha
o princípio: **fato objetivo** (não "parece inseguro"), com `fix` acionável.
