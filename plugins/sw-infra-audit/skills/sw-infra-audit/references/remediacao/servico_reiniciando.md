---
regra: servico_reiniciando
titulo: Serviço reiniciando repetidamente
severidade_padrao: medium
---

## Por que importa

O serviço caiu e voltou pelo menos 5 vezes desde que o gerenciador (systemd ou Docker) começou a
contar. Cada queda derruba as conexões abertas e, num banco, pode deixar uma transação pela metade. O
reinício automático esconde o problema: na hora da auditoria o serviço parece de pé, mas está caindo.

## Como resolver

1. Leia o log da última queda: `journalctl -u <unit> -n 200` ou `docker logs --tail 200 <container>`.
2. Falta de memória é a causa mais comum: procure `Out of memory` em `journalctl -k`.
3. Erro de configuração ou de dependência (disco cheio, porta ocupada, senha trocada) aparece nas
   primeiras linhas depois de cada subida.
4. Corrigida a causa, acompanhe a contagem: ela não zera sozinha, mas não deve crescer.

## Como confirmar

Na próxima auditoria a contagem de reinícios fica igual à desta rodada. Na mão:
`systemctl show <unit> -p NRestarts` ou `docker inspect -f '{{.RestartCount}}' <container>`.

## Quando NÃO fazer

Não desligue o reinício automático para calar o alarme: é ele que mantém o serviço de pé enquanto a
causa não é corrigida. Reinício de propósito (uma rotina que reinicia todo dia) não é problema: aceite
o risco no `alvos.toml`, com o motivo.
