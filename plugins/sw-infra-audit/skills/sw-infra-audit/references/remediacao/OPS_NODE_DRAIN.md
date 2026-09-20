---
regra: OPS_NODE_DRAIN
titulo: Nó em drenagem
---

## Por que importa

O nó está de pé, mas o orquestrador foi instruído a não colocar nada nele. Isso é normal
durante uma manutenção — e vira um problema quando alguém esquece: o cluster passa a ter menos
capacidade do que a conta de nós sugere, e ninguém percebe até faltar lugar.

## Como resolver

1. Descubra desde quando ele está assim e por quê.
2. Terminada a manutenção, devolva o nó ao ativo.

```bash
docker node update --availability active <nó>
```

## Como confirmar

`docker node ls` mostra `Active` na coluna de disponibilidade, e o nó volta a receber tarefa na
próxima distribuição.

## Quando NÃO fazer

Drenagem proposital de longo prazo (nó reservado, hardware em observação). Registre como risco
aceito para o relatório parar de apontar — e para a próxima pessoa entender que é intencional.
