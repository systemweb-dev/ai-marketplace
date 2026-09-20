---
regra: SEC_IMAGE_UNPINNED
titulo: Imagem sem versão fixa
---

## Por que importa

Com `:latest` ou uma tag móvel, **o que roda pode mudar sem ninguém pedir**: basta um novo
`pull` num redeploy, ou um nó subir depois dos outros. O deploy deixa de ser reproduzível, dois
nós podem rodar código diferente ao mesmo tempo, e uma imagem comprometida entra sem alarde.

## Como resolver

1. Descubra o digest da imagem que está rodando hoje — é o que você já testou.
2. Fixe o digest no arquivo de deploy.
3. Atualize por decisão, trocando o digest, não por acidente.

```bash
docker image inspect <imagem>:<tag> --format '{{index .RepoDigests 0}}'
# image: registro/app@sha256:<digest>
```

## Como confirmar

A auditoria deixa de apontar o serviço, e `docker service inspect` mostra a imagem com `@sha256:`.

## Quando NÃO fazer

Ambiente de desenvolvimento onde a intenção é justamente pegar a última. Em produção, não há
caso bom: se a atualização automática é desejada, ela deve vir de um pipeline que troca o
digest e registra o que mudou.
