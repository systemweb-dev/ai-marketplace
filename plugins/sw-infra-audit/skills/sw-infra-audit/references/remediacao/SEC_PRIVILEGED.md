---
regra: SEC_PRIVILEGED
titulo: Container roda em modo privilegiado
---

## Por que importa

`--privileged` desliga quase toda a separação entre o container e o host: ele enxerga os
dispositivos, monta o que quiser e escapa com facilidade. Uma falha na aplicação deixa de ser
um problema daquele serviço e passa a ser um problema do nó inteiro — e, num cluster, do
cluster inteiro, porque o nó tem credencial para conversar com os outros.

## Como resolver

1. Descubra **o que exatamente** o container precisa: quase sempre é uma capacidade só
   (montar sistema de arquivos, mexer em rede, acessar um dispositivo).
2. Troque o privilégio total pela capacidade específica.
3. Se for acesso a um dispositivo, passe só aquele dispositivo.

```yaml
# em vez de:  privileged: true
cap_add: ["NET_ADMIN"]        # só a capacidade que falta
devices: ["/dev/fuse"]        # só o dispositivo que falta
```

## Como confirmar

Rode a auditoria de novo: o achado sai. Para conferir na mão,
`docker inspect <container> --format '{{.HostConfig.Privileged}}'` responde `false`.

## Quando NÃO fazer

Ferramenta de infraestrutura que precisa mesmo do host — agente de storage, driver de rede,
runner que constrói imagem. Nesses casos, registre como risco aceito com data de revisão, e
garanta que a imagem venha de origem confiável e com digest fixo.
