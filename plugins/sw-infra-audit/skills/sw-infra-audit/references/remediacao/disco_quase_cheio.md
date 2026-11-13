---
regra: disco_quase_cheio
titulo: Disco acima de 90%
severidade_padrao: high
---

## Por que importa

Disco cheio não degrada: para. Banco que não grava recusa transação, log que não escreve esconde o
erro seguinte, e o Docker deixa de puxar imagem. Acima de 90% sobra pouco para um pico de log ou um
backup local, e o dia em que acaba costuma ser o dia de mais movimento.

## Como resolver

1. Veja o que cresceu: `du -xh --max-depth=1 / | sort -h | tail` no servidor (é leitura).
2. Log sem rotação: configure o `logrotate` ou o limite do `journald` (`SystemMaxUse=`).
3. Docker: `docker system df` mostra imagem, volume e cache de build acumulados; limpe com o dono do
   serviço ciente.
4. Banco: binlog e WAL antigos têm política própria de retenção; não apague arquivo à mão.
5. Se o uso é legítimo, aumente o volume antes de chegar a 100%.

## Como confirmar

A próxima auditoria mostra o disco abaixo de 90% e o achado some. Na mão: `df -h /`.

## Quando NÃO fazer

Não apague arquivo de banco, de fila ou de volume de container para liberar espaço: é perda de dado.
Se o servidor é temporário e vai ser recriado, registre o risco aceito em vez de limpar.
