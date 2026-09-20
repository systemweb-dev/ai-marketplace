---
regra: OPS_REPLICAS_DEGRADED
titulo: Serviço rodando com menos réplicas do que o declarado
---

## Por que importa

O serviço está no ar, mas com menos instâncias do que você pediu. A redundância que você
acredita ter não existe neste momento, e a capacidade é menor do que a planilha diz — muitas
vezes sem sintoma visível, até o pico de tráfego.

## Como resolver

1. Veja por que as réplicas faltantes não sobem: falta de nó com recurso, restrição de
   posicionamento que ninguém satisfaz, imagem que falha em alguns nós.
2. Corrija a causa. Aumentar o número pedido não resolve — só aumenta a diferença.

```bash
docker service ps <serviço> --no-trunc --filter desired-state=running
docker service inspect <serviço> --format '{{json .Spec.TaskTemplate.Placement}}'
```

## Como confirmar

`docker service ls` mostra `N/N` e a auditoria seguinte não aponta mais o serviço.

## Quando NÃO fazer

Durante um deploy em andamento — aí a diferença é temporária e esperada. Se a auditoria pegou
exatamente nesse momento, rode de novo depois que a atualização terminar.
