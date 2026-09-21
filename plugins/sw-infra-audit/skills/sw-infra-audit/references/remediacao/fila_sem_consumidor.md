---
regra: fila_sem_consumidor
titulo: Fila com mensagem presa e nenhum consumidor
severidade_padrao: high
---

## Por que importa

Mensagem numa fila sem consumidor não está atrasada: está parada. Nada a tira de lá, e o
tamanho só cresce. O efeito aparece longe da causa — o pedido que não confirmou, o e-mail que
não saiu, o relatório que não gerou — e a fila é o último lugar onde se procura, porque o
serviço que publica continua respondendo normalmente.

Quando a fila tem limite de tamanho ou de idade, o broker começa a **descartar** mensagem, e aí
o prejuízo deixa de ser atraso e passa a ser perda.

## Como resolver

1. Descubra quem deveria consumir esta fila. O nome dela costuma dizer, mas quem confirma é o
   código que declara a assinatura.
2. Veja se o serviço consumidor está no ar e com réplica saudável — fila sem consumidor
   normalmente é um worker em crash loop, não um problema do broker.
3. Se o consumidor está de pé, verifique se ele assinou a fila certa: renomear a fila no
   publicador sem renomear no consumidor deixa exatamente este rastro.
4. Se a fila ficou órfã de propósito (serviço desativado), remova-a em vez de deixá-la
   acumulando — pelo painel do broker, com o dono do serviço ciente.

```sh
# consumidores e mensagens prontas de cada fila, por vhost. O `-u` só com o usuário faz o
# curl PERGUNTAR a senha: escrita no comando, ela ficaria visível em `ps` e no histórico.
curl -s -u "$USUARIO" "$ADMIN_URL/api/queues" \
  | jq -r '.[] | "\(.vhost)\t\(.name)\t\(.consumers)\t\(.messages_ready)"'
```

## Como confirmar

A auditoria deixa de apontar a fila. Na mão, o número de consumidores sai de 0 e a contagem de
mensagens prontas começa a cair entre duas leituras.

**O que esta regra não vê:** fila com consumidor conectado que não confirma mensagem. Ali
`consumers` é maior que zero e a regra fica calada — mas as mensagens `unacknowledged` crescem
e nada sai. É o caso pior: ele não vira achado, mas encabeça a lista de filas do relatório,
que é ordenada pelo total acumulado (prontas + não confirmadas).

## Quando NÃO fazer

A regra acusa toda fila com mensagem e sem consumidor, e algumas estão assim **por desenho**:

- **fila morta** (dead letter): guarda o que falhou, e ninguém a consome de propósito. Aqui a
  mensagem presa é o registro da falha — investigue a origem, não crie um consumidor;
- **fila de espera para nova tentativa** (com TTL e dead letter exchange): as mensagens voltam
  sozinhas para a fila original quando o tempo acaba;
- **stream**: `messages_ready` é o log retido, e ficar sem consumidor conectado é normal;
- **fila sazonal**: lote noturno, reprocessamento manual.

Nesses casos registre como risco aceito, com motivo e prazo de revisão, em vez de criar um
consumidor para calar o alerta. Aceitar o componente inteiro também silencia filas órfãs que
aparecerem no futuro — prefira aceitar fila a fila.
