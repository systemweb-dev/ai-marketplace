---
regra: OPS_TLS_EXPIRING
titulo: Certificado do daemon vence em breve
---

## Por que importa

É o mesmo problema do certificado vencido, com a diferença que ainda dá para agir com calma.
Quando ele vence, o acesso remoto para de funcionar de uma vez — e a fila de quem depende disso
inclui o pipeline de deploy, que você vai querer usar justamente para resolver.

## Como resolver

**Leia `references/tls-renewal.md`.** Em resumo: renove mantendo a mesma CA, valide o par antes
de aplicar, reinicie o daemon e atualize os outros clientes (CI, painel, máquinas de quem opera).

```bash
openssl x509 -noout -enddate -in cert.pem      # confirme o prazo real
```

## Como confirmar

A auditoria passa a mostrar a nova data de validade na seção de certificados, e o achado sai.

## Quando NÃO fazer

Se a decisão é migrar para `ssh://` antes do vencimento, a renovação vira trabalho jogado fora —
mas só se a migração acontecer **antes** da data. Prazo não negocia.
