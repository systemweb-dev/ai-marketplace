---
regra: certificado_vencendo
titulo: Certificado do endpoint vence em breve
---

## Por que importa

Quando o certificado vence, o handshake TLS falha e o endpoint **some para todo mundo** — para
o usuário, para as integrações e para o monitoramento que deveria avisar. Não há degradação
suave: funciona até a data, e para depois dela.

## Como resolver

1. Descubra quem emite: renovação automática (ACME) que falhou, ou certificado gerenciado à mão.
2. Se é automático, o problema costuma ser o desafio de validação — a rota do desafio bloqueada,
   DNS apontando para outro lugar, ou limite do emissor.
3. Se é manual, renove mantendo a mesma cadeia e recarregue o serviço que termina o TLS.

```bash
echo | openssl s_client -connect <host>:443 -servername <host> 2>/dev/null \
  | openssl x509 -noout -issuer -enddate
```

## Como confirmar

O comando acima mostra a data nova, e a auditoria seguinte traz o prazo renovado na ficha do
alvo, sem o achado.

## Quando NÃO fazer

Endpoint interno com certificado próprio de validade curta por desenho. Se for o caso, o que
falta é a renovação automática funcionar — não renovar à mão toda vez.
