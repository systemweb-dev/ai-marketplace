---
regra: memoria_sem_folga
titulo: Memória acima de 90% em uso
severidade_padrao: medium
---

## Por que importa

Com menos de 10% de memória disponível, o kernel começa a tirar página de cache e, no limite, o
OOM killer encerra um processo — normalmente o maior, que costuma ser o banco. O sintoma aparece
como lentidão intermitente antes de virar queda.

## Como resolver

1. Veja quem consome: `ps -eo pid,comm,rss --sort=-rss | head` no servidor (é leitura).
2. Banco: confira o tamanho do buffer pool ou do `shared_buffers` contra a memória da máquina.
3. Container sem limite de memória cresce até onde a máquina deixa; declare limite no serviço.
4. Se o consumo é legítimo, aumente a máquina.

## Como confirmar

A próxima auditoria mostra a memória abaixo de 90%. Na mão: `free -m`, coluna `available`.

## Quando NÃO fazer

Não desligue swap nem mate processo de banco para "liberar memória" sem o dono do serviço: o
remédio vira a queda que se queria evitar.
