---
regra: OPS_NO_LIMITS
titulo: Serviço sem teto de CPU ou memória
---

## Por que importa

Sem limite, um pico num serviço consome o nó inteiro e derruba os **vizinhos** — inclusive os
que não têm nada a ver com o problema. É como uma falha local vira incidente de cluster.

## Como resolver

1. Meça o consumo normal antes de escolher o número: limite abaixo do uso real causa reinício
   por falta de memória, que é pior que não ter limite.
2. Declare reserva (o que ele precisa) e limite (o teto).

```yaml
deploy:
  resources:
    reservations: { cpus: "0.25", memory: 256M }
    limits:       { cpus: "1.0",  memory: 512M }
```

## Como confirmar

`docker service inspect <serviço> --format '{{json .Spec.TaskTemplate.Resources}}'` mostra os
valores, e a auditoria seguinte sai sem o achado.

## Quando NÃO fazer

Antes de medir. Um limite chutado é troca de um problema raro (vizinho afetado no pico) por um
problema frequente (reinício por falta de memória). Meça primeiro, limite depois.
