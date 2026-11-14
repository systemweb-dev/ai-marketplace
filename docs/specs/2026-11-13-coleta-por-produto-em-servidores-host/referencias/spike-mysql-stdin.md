# Spike: senha do MariaDB pelo stdin

Executado em 2026-11-13, com `mariadb:11` (servidor `11.8.9-MariaDB-ubu2404`, cliente `mariadb` 15.2)
num Docker local (container descartável, apagado no fim). Senha de teste inventada: `a"b\c#d`.

| Sonda | Resultado | Observação |
|---|---|---|
| A direto: `"` e `\` escapados, `#` literal | `1`, rc=0 | `SELECT CURRENT_USER()` pela mesma entrada devolve `leitor@localhost`: o arquivo de opções foi lido |
| A via `sh -c` (como o ssh entrega) | `1`, rc=0 | stdin atravessa o shell intermediário sem perda |
| B: também `\#` | `ERROR 1045`, rc=1 | a barra fica dentro da senha, como o plano previa |
| controle: senha errada pela mesma via | `ERROR 1045`, rc=1 | prova que a A não passou por acaso |
| `command -v mariadb` / `mysql` | `/usr/bin/mariadb` / nenhum | a imagem 11 não traz o apelido `mysql` (nem nenhum `mysql*` em `/usr/bin`) |
| root pelo socket, sem senha | `ERROR 1045 (using password: NO)`, rc=1 | não decide: o root da imagem tem senha |
| `SHOW GLOBAL STATUS` separado por TAB | 571 linhas, 571 com TAB | `SHOW GLOBAL VARIABLES`: 684/684; `Threads_connected`, `Slow_queries` e `max_connections` presentes |
| texto do binlog desligado | `ERROR 1381 (HY000) at line 1: You are not using binary logging`, rc=1 | o cliente ecoa antes o comando entre linhas `--------------` (saída de erro) |

Nota de execução: o `mariadb-admin ping` responde também ao servidor temporário que o entrypoint
sobe na inicialização; esperar só pelo ping fez a primeira tentativa cair no reinício. A espera que
funcionou foi a linha `init process done` no log **e** o ping.

Fixtures gravadas em `tests/fixtures/produto/mariadb/` (`status.txt`, `variaveis.txt`, `tamanho.txt`,
`tamanho_por_banco.txt`), de um banco vazio de container; varredura de home e da denylist sem achados.

Veredito: **modo senha confirmado**. Variante A (escapar só `\` e `"`, `#` literal) funciona direto e
via `sh -c`; o catálogo do MariaDB usa o cliente `mariadb`. O plano não muda.
