---
regra: conexoes_no_limite
titulo: Conexões do banco acima de 80% do limite
severidade_padrao: medium
---

## Por que importa

Mais de 80% das conexões permitidas (`max_connections`) estão abertas. Quando o limite chega, o banco
recusa conexão nova ("Too many connections") e a aplicação cai, mesmo com CPU e memória sobrando. Um
pico de acesso ou um worker que não devolve a conexão bastam para cruzar o limite.

## Como resolver

1. Veja quem está conectado: `SHOW PROCESSLIST` no MariaDB/MySQL, `pg_stat_activity` no Postgres (é
   leitura).
2. Conexão ociosa acumulada: confira o pool da aplicação (tamanho máximo, tempo ocioso) e se o código
   devolve a conexão.
3. Várias instâncias da aplicação, cada uma com o seu pool: some os máximos; o total precisa caber no
   limite.
4. Se o uso é legítimo, aumente `max_connections` com memória para isso (cada conexão reserva buffer),
   ou ponha um pooler (ProxySQL, PgBouncer) na frente.

## Como confirmar

A próxima auditoria mostra o uso abaixo de 80% e o achado some. Na mão: `Threads_connected` em
`SHOW GLOBAL STATUS` contra `max_connections` em `SHOW GLOBAL VARIABLES`.

## Quando NÃO fazer

Não derrube conexões em massa para baixar o número: são transações da aplicação em andamento. E não
suba `max_connections` sem olhar a memória: o banco que não cai por conexão cai por falta de memória.
