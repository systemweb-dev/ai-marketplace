---
regra: SEC_DOCKER_SOCK
titulo: Monta o socket do Docker ou um caminho sensível do host
---

## Por que importa

Quem alcança o `docker.sock` pode criar container com o host montado — ou seja, **acesso ao
socket é equivalente a root na máquina**. O mesmo vale para montar `/`, `/etc`, `/root`,
`/proc` ou `/sys`. Não é uma escalada teórica: é um comando.

## Como resolver

1. Pergunte se o serviço precisa **escrever** ou só **ler** o estado do Docker. Quase sempre é
   só ler (descobrir containers, coletar métrica, rotear).
2. Se for só leitura, ponha um proxy de socket somente-leitura no meio e aponte o serviço
   para ele, em vez do socket cru.
3. Para caminho do host, monte o diretório específico, em modo leitura (`:ro`).

```yaml
services:
  socket-proxy:                      # expõe só os verbos de leitura
    environment: { CONTAINERS: 1, SERVICES: 1, POST: 0 }
    volumes: ["/var/run/docker.sock:/var/run/docker.sock:ro"]
  a-ferramenta:
    environment: { DOCKER_HOST: "tcp://socket-proxy:2375" }
```

## Como confirmar

A auditoria deixa de apontar o serviço; o socket passa a aparecer montado **só** no proxy, e
`docker inspect <serviço>` não mostra mais `/var/run/docker.sock` na lista de mounts.

## Quando NÃO fazer

Ferramentas que precisam do socket para existir — o proxy que descobre serviços, o coletor de
métrica de container, o agente do painel. A skill já marca esses casos como esperados; o que
vale ali é limitar a imagem e fixar o digest.
