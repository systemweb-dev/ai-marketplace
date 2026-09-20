---
regra: SEC_PORT_EXPOSED
titulo: Porta publicada em todas as interfaces do host
---

## Por que importa

A porta está publicada em `0.0.0.0`: todas as interfaces do host. Isso **não prova** que ela é
alcançável da internet — firewall e security group da nuvem são invisíveis para esta auditoria
—, mas é a superfície. Se a regra de rede mudar amanhã, o serviço fica exposto sem que ninguém
precise reconfigurar nada, e sem aviso.

## Como resolver

1. Descubra quem precisa alcançar a porta. Se for outro serviço do mesmo cluster, ela **não
   precisa ser publicada**: a rede interna já resolve pelo nome do serviço.
2. Precisando publicar, publique na interface interna em vez de em todas.
3. Se a porta é pública de propósito, deixe o firewall explícito — não conte com a sorte.

```yaml
ports:
  - target: 8080
    published: 8080
    mode: host          # publica só onde a task roda
# ou, melhor: remova a publicação e use a rede interna
```

## Como confirmar

A auditoria deixa de apontar. Na mão:
`docker service inspect <serviço> --format '{{json .Endpoint.Ports}}'` mostra o bind resultante.

## Quando NÃO fazer

O ponto de entrada público do cluster (o proxy nas portas 80 e 443). Ali a publicação é o
desenho, não o problema — registre como risco aceito, com a justificativa.
