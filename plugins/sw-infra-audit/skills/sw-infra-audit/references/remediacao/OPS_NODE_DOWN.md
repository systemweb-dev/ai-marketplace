---
regra: OPS_NODE_DOWN
titulo: Nó do cluster não está pronto
---

## Por que importa

Um nó fora do `Ready` não recebe tarefa. O que rodava nele foi remanejado — se havia onde. A
capacidade do cluster caiu agora, e a próxima falha encontra menos lugar para cair. É a única
condição que esta skill trata como **degradação real**, não como risco.

## Como resolver

1. Veja o que o próprio cluster diz sobre o nó antes de mexer nele.
2. Se o daemon está fora, suba; se a máquina está fora, trate como incidente de infraestrutura.
3. Depois que voltar, confirme que as tarefas realmente voltaram a ser distribuídas.

```bash
docker node inspect <nó> --format '{{.Status.State}} · {{.Status.Message}}'
docker node ps <nó> --no-trunc
```

## Como confirmar

`docker node ls` mostra o nó como `Ready`, e a auditoria seguinte sai sem o achado — com o
número de nós de volta ao esperado no panorama.

## Quando NÃO fazer

Nó desligado de propósito (manutenção planejada, redução de custo à noite). Nesse caso, o certo
é tirá-lo do cluster ou registrá-lo como risco aceito com data — para o relatório não gritar
toda semana pela mesma razão conhecida.
