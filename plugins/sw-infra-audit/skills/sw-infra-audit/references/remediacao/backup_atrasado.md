---
regra: backup_atrasado
titulo: Backup do banco mais velho que o limite
severidade_padrao: high
---

## Por que importa

O backup mais novo da pasta declarada tem mais dias do que o limite definido para este banco
(`backup_max_dias`, 2 por padrão). Se o banco se perder hoje — disco, exclusão errada, invasão —, tudo
o que foi gravado desde aquele backup se perde junto. Rotina de backup que para de rodar não avisa:
costuma ser descoberta no dia em que se precisa dela.

## Como resolver

1. Veja se a rotina rodou: `systemctl list-timers` ou `crontab -l` no servidor (é leitura).
2. Rotina com erro: o log dela (`journalctl -u <unit>` ou o arquivo que o cron grava) mostra o motivo;
   disco cheio e senha trocada são os mais comuns.
3. Rotina que grava em outra pasta: corrija `backup_pasta` no `alvos.toml`.
4. Backup semanal de propósito: declare `backup_max_dias = 7` no componente.
5. Depois de corrigir, rode um backup na hora e confira que o arquivo novo aparece na pasta.

## Como confirmar

A próxima auditoria mostra a idade do backup dentro do limite e o achado some. Na mão:
`ls -l --time-style=full-iso <pasta>`.

## Quando NÃO fazer

Não apague backups antigos para "organizar" a pasta enquanto o novo não estiver confirmado: o antigo é
o único que existe. E backup que nunca foi restaurado é suposição: teste a restauração num ambiente
separado antes de contar com ele.
