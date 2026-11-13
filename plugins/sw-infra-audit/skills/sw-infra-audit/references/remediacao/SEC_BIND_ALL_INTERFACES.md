---
regra: SEC_BIND_ALL_INTERFACES
titulo: Banco ou cache escutando em todas as interfaces
severidade_padrao: medium
---

## Por que importa

O processo aceita conexão em qualquer endereço do servidor, inclusive o público. Se o firewall da
nuvem ou o do sistema deixar a porta passar, o banco fica alcançável da internet — e banco exposto é
alvo de varredura automática em minutos. A auditoria não vê o firewall: isto não prova exposição, mas
é a superfície.

## Como resolver

1. MariaDB/MySQL: `bind-address = 127.0.0.1` (ou o IP privado da VPN) no `[mysqld]` do arquivo de
   configuração, e reinicie em janela combinada.
2. PostgreSQL: `listen_addresses = 'localhost'` (ou o IP privado) no `postgresql.conf`.
3. Redis: `bind 127.0.0.1` (ou o IP privado) e `protected-mode yes` no `redis.conf`.
4. Qdrant: `service.host` no arquivo de configuração, apontando para o IP privado.
5. Container publicando a porta: troque `0.0.0.0:3306:3306` por `127.0.0.1:3306:3306` ou pela rede
   interna.
6. Se precisa mesmo de acesso externo, restrinja por firewall ao IP de quem conecta.

## Como confirmar

A próxima auditoria não acusa mais a porta. Na mão: `ss -ltn` mostra o endereço de escuta.

## Quando NÃO fazer

Não troque o endereço de escuta sem mapear quem conecta de outra máquina: aplicação em outro servidor
perde o banco na hora. Se o acesso remoto é necessário e o firewall já restringe, registre o risco
aceito.
