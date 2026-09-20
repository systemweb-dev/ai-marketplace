---
regra: http_fora_do_ar
titulo: Endpoint respondendo com erro de servidor
---

## Por que importa

O servidor respondeu — e respondeu erro. Isso já descarta rede e DNS: o problema está na
aplicação ou numa dependência dela (banco, fila, serviço que ela chama). Para quem usa, a
diferença entre "fora do ar" e "respondendo 5xx" é nenhuma.

## Como resolver

1. Veja se as réplicas estão de pé e se alguma está reiniciando — sintoma de dependência fora.
2. Confira a dependência mais provável antes de mexer na aplicação.
3. Se o erro é só numa rota, o problema é dela, não do serviço inteiro.

```bash
docker service ps <serviço> --no-trunc
curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' https://<host>/health
```

## Como confirmar

O endpoint volta a responder abaixo de 400, e a auditoria seguinte traz o alvo como operacional.

## Quando NÃO fazer

Se o endereço auditado não é o certo (rota de saúde diferente da que foi declarada), a correção
é no `alvos.toml`, não na aplicação — e vale conferir isso antes de abrir incidente.
