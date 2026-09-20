---
regra: http_resposta_de_erro
titulo: Endpoint respondendo erro de requisição
---

## Por que importa

O servidor está de pé e recusou a requisição: rota que não existe, autenticação exigida,
permissão negada. Não é indisponibilidade — mas, num endereço que a auditoria deveria conseguir
consultar, quase sempre significa **endereço declarado errado** ou proteção nova no caminho.

## Como resolver

1. Confira qual caminho foi declarado no `alvos.toml`: a rota de saúde costuma ser outra.
2. Se a rota exige autenticação, aponte a auditoria para um caminho público de saúde — a
   auditoria não guarda credencial de aplicação.
3. Se a rota deveria ser pública e não é mais, aí o achado é real: alguém mudou o roteamento.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://<host><caminho-declarado>
```

## Como confirmar

O endereço responde abaixo de 400 e a auditoria seguinte traz o código de sucesso na ficha
do alvo.

## Quando NÃO fazer

Endpoint que **deve** responder 401 para anônimo (uma API fechada). Nesse caso o certo é
declarar um caminho de saúde público, ou aceitar o risco explicando que o 401 é o desenho.
