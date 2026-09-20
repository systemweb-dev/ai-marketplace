---
regra: OPS_TASK_FAILING
titulo: Tarefas falhando e reiniciando
---

## Por que importa

O serviço aparenta estar no ar porque o orquestrador reinicia o que morre. Por baixo, ele está
num ciclo: sobe, falha, sobe. Cada volta descarta conexão, refaz trabalho e mascara a causa —
e o painel continua verde.

## Como resolver

1. Olhe o motivo da última falha (código de saída, mensagem do orquestrador).
2. Reproduza fora do cluster quando possível: quase sempre é configuração faltando, dependência
   indisponível no momento de subir, ou limite de memória apertado demais.
3. Corrija a causa. Aumentar a política de reinício só esconde melhor.

```bash
docker service ps <serviço> --no-trunc
docker service inspect <serviço> --format '{{json .Spec.TaskTemplate.RestartPolicy}}'
```

## Como confirmar

As tarefas param de reiniciar: `docker service ps` mostra a mesma tarefa rodando há tempo, e a
auditoria seguinte sai sem o achado.

## Quando NÃO fazer

Job de execução única que termina com sucesso — terminar é a função dele. A skill já distingue
esse caso; se um job legítimo aparecer aqui, o que falta é ele estar declarado como job.
