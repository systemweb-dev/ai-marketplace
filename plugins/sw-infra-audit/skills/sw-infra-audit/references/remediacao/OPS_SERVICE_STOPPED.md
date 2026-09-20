---
regra: OPS_SERVICE_STOPPED
titulo: Serviço sem nenhuma réplica no ar
---

## Por que importa

O serviço está declarado e não tem nada rodando. Ou ele nunca subiu, ou concluiu e não foi
reiniciado. A diferença importa: um job de migração em zero réplica é o estado normal (e a
skill não aponta esses), mas um serviço comum em zero significa **função indisponível** — e é
assim que banco fora do ar já se escondeu de painel.

## Como resolver

1. Veja por que a última tarefa terminou: erro de imagem, falta de recurso, saída com código.
2. Se foi falha, corrija a causa antes de subir de novo — subir sem entender repete o ciclo.

```bash
docker service ps <serviço> --no-trunc
docker service inspect <serviço> --format '{{.Spec.Mode}}'
```

## Como confirmar

`docker service ls` mostra réplicas no formato `N/N`, e a auditoria seguinte sai sem o achado.

## Quando NÃO fazer

Serviço desativado de propósito (feature desligada, ambiente encostado). Aí o certo é remover a
declaração, não deixar um serviço morto no inventário confundindo quem lê.
