# Spike das fontes reais

Medido em 2026-11-01 num Prometheus real, só com leitura. Sem endereços nem nomes de serviços.

| Pergunta | Resultado | Decisão |
|---|---|---|
| Retenção | menor que 30 dias | "30 dias" vira 7 dias, conforme o spec prevê para retenção menor |
| node-exporter | presente em todos os nós | Task 14 segue |
| Ligação do nó | `nodename` é o id curto do container do exporter, e `instance` é IP interno | Ligar pelo `ContainerID` da task do exporter, lido com `docker inspect` |
| Traefik | `service` e `router` com dezenas de valores, ambos `<nome>@swarm` | Usar `router`; o domínio vem da regra `Host` em `routing_labels`, e sem regra aparece o nome da rota |
| cAdvisor | Série presente, etiqueta `container_label_com_docker_swarm_service_name` correta | Sem correção; Task 12 encerrada sem mudança de código |
| Exporters de banco e cache | Nenhum | Blocos continuam como não medido, com o motivo |
| Custo | consultas instantâneas e `query_range` abaixo de 0,7 s | Cabe no orçamento de 120 s |
| Disponibilidade | `count by (serviço)(container_last_seen)` existe | Uma consulta agrupada por serviço, em 7 dias |
| Sistema de arquivos | Milhares de valores de `mountpoint` | Filtrar sempre por `mountpoint="/"` |
