---
regra: servico_declarado_ausente
titulo: Serviço declarado não encontrado no servidor
severidade_padrao: high
---

## Por que importa

O componente está no `alvos.toml` porque alguém confirmou que ele roda neste servidor, e a leitura
desta rodada (que respondeu) não o encontrou. Na maioria das vezes é um banco ou um cache parado — e
as aplicações que dependem dele estão falhando agora.

## Como resolver

1. No servidor, veja o estado da unit: `systemctl status <unit>` (é leitura).
2. Parado por falha: `journalctl -u <unit> -n 50` mostra o motivo; resolva a causa antes de subir.
3. Container: `docker ps -a --filter name=<nome>` mostra se saiu e com que código.
4. Foi desligado ou migrado de propósito: apague o bloco `[[alvo.componente]]` dele no `alvos.toml`.

## Como confirmar

A próxima auditoria encontra o serviço e o achado some. Na mão: `systemctl is-active <unit>`.

## Quando NÃO fazer

Não suba de novo um banco que caiu por disco cheio ou por corrupção sem entender a causa: ele cai de
novo, ou pior, sobe com dado inconsistente.
