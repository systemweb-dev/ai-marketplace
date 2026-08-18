# Catálogo de regras de finding (determinísticas)

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

**Verdict de saúde:** `red` se houver finding `high`; `yellow` se houver `med`; senão `green`.

Adicionar regra nova = uma função pura em `rules.py` + um caso em `tests/test_rules.py`. Mantenha
o princípio: **fato objetivo** (não "parece inseguro"), com `fix` acionável.
