---
regra: OPS_NO_HEALTHCHECK
titulo: Serviço sem verificação de saúde
---

## Por que importa

Sem healthcheck, o orquestrador só sabe que **o processo existe** — não que ele funciona. Uma
aplicação travada, com o banco fora ou a fila cheia, continua recebendo tráfego e contando como
réplica saudável. É a diferença entre "está rodando" e "está atendendo".

## Como resolver

1. Exponha (ou use) um caminho barato que prove que a aplicação responde de verdade.
2. Declare o healthcheck com intervalo e tolerância compatíveis com o tempo de subida.

```yaml
healthcheck:
  test: ["CMD", "curl", "-fsS", "http://localhost:8080/health"]
  interval: 30s
  timeout: 3s
  retries: 3
  start_period: 20s     # tempo de subida, para não matar durante o boot
```

## Como confirmar

`docker ps` passa a mostrar `(healthy)` no container, e a auditoria seguinte não aponta mais o
serviço.

## Quando NÃO fazer

Serviço sem ponto de verificação barato (um worker de fila, por exemplo, onde qualquer checagem
significaria processar mensagem). Aí vale um healthcheck que olhe o estado interno — ou aceitar
o risco por escrito, sabendo que a réplica pode estar viva e inútil.
