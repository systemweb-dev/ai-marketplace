---
regra: OPS_DAEMON_UNREACHABLE
titulo: Daemon do cluster inacessível
---

## Por que importa

A auditoria não conseguiu falar com o daemon deste alvo. Isso significa duas coisas ao mesmo
tempo: o relatório está **cego** sobre ele (o que aparecer como "sem dados" é consequência
disto, não diagnóstico), e quem opera provavelmente também está — CLI e pipeline usam o mesmo
caminho.

## Como resolver

1. Separe os três casos, que têm correções diferentes: rede bloqueada, daemon fora do ar,
   certificado vencido.
2. A mensagem do erro já diz qual é — ela aparece no próprio achado.

```bash
docker --context <alvo> info            # reproduz o erro exato
docker context inspect <alvo>           # confirma endereço e certificado em uso
```

## Como confirmar

`docker --context <alvo> info` responde, e a auditoria seguinte traz o alvo com dados em vez de
"sem dados".

## Quando NÃO fazer

Se o alvo está fora do ar de propósito (ambiente desligado), o certo é não confirmá-lo na
rodada: ele aparece como "sem dados" no inventário, sem achado, e o relatório não mente.
