---
regra: OPS_TLS_EXPIRED
titulo: Certificado do daemon expirou
---

## Por que importa

Com o certificado vencido, **todo acesso remoto ao daemon para**: CLI, pipeline de deploy,
painel. O cluster continua rodando o que já estava no ar — mas você perdeu o controle remoto
dele, e descobrir isso no meio de um incidente é o pior momento possível.

## Como resolver

Este caso tem runbook próprio: **leia `references/tls-renewal.md`** antes de agir. O resumo:

1. Renove **mantendo a mesma autoridade certificadora**; trocar de CA obriga a atualizar todos
   os clientes ao mesmo tempo.
2. Valide o par **antes** de aplicar.
3. Reinicie o daemon (ele só relê o certificado ao subir) e confira os outros clientes.

```bash
openssl x509 -noout -dates -in cert.pem
openssl verify -CAfile ca.pem cert.pem
```

## Como confirmar

A auditoria volta a coletar o alvo (o achado de daemon inacessível some junto), e
`docker --context <alvo> info` responde.

## Quando NÃO fazer

Não há caso de deixar expirado. Se o plano é migrar o context para `ssh://` — que dispensa
certificado —, faça a migração; mas não deixe o acesso quebrado no meio do caminho.
