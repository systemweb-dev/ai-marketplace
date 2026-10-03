# Revisão independente do design `exec_cli` — 2026-10-03

Revisor: subagente com acesso ao código real da skill, instruído a pensar como atacante com
acesso de escrita ao `alvos.toml` ou ao catálogo. O design foi **adiado** por causa desta
revisão; ela fica aqui para quem retomar não redescobrir do zero.

Três achados foram verificados por mim contra o código antes de aceitar.

## Os que derrubaram o design

**1. Validação circular (alta).** O catálogo declarava `binario` *e* `verbo`, e a regra era
"binário igual ao declarado". Quem escreve o TOML escolhe `binario = "sh"`, `verbo = ["-c", …]`
e ganha execução arbitrária como root. A allowlist positiva de binários tem de viver em Python;
o TOML só escolhe entre entradas que o código já conhece.

**2. Lista negativa de flags num código cuja regra é lista positiva (alta).** `-it` (um token
só), `--interactive`, `--tty`, `--user=root`, `--env=`, `--env-file`, `-d`, `-w` não casam com
nenhum dos seis literais que eu tinha listado. O certo é validar a **forma**: o argv tem de ser
exatamente `["docker","exec",<id>,<bin>,*verbo]`, sem nenhum token iniciado por `-` nas
posições 0 a 3.

**3. Flags globais do docker antes do `exec` (alta).** `docker --context evil exec`, `-H`,
`--config`. Hoje isso não fura porque a flag vira o "noun" na allowlist antiga — proteção que
o validador novo perderia. Fixar `cmd[0] == "docker"` e `cmd[1] == "exec"` por igualdade.

**4. Falta o equivalente de `ROTAS_PROIBIDAS` (alta).** `rabbitmq-diagnostics environment`,
`redis-cli config get *`, `mysqladmin variables` são leitura e **imprimem senha**. E a saída
iria para o `report.json` sem redação: só `detalhe` passa por `redact.scrub_text`, o `valor`
não. Precisa de verbos proibidos por família, `scrub_text` em toda saída e teto de bytes — o
HTTP tem `MAX_BYTES`, o `subprocess.run` não tem nenhum.

**5. Sem contrato de saída (alta).** O `admin_http` tem linguagem fechada validada no load. A
saída de CLI é texto humano com banner ("Asking node rabbit@…"), exigindo `--quiet
--formatter json`. Sem isso, **resposta errada passa por certa** — o pior modo de falha deste
código.

## Contradições com o que já existe (verificadas)

- `acesso_por_container` seria **recusado**: `lib/alvos.py` aceita só
  `componente, context, metricas_url, nome, tipo`. Com a linha, o arquivo inteiro para.
- `run()` **não tem perfil**: chama `check()` fixo e faz `ambiente(context)` ignorando
  `extras`. O `env_extra: ()` apresentado como garantia é um no-op.
- `banco`, `cache`, `app` e `observabilidade` têm **zero** perguntas canônicas. O adaptador
  destravaria só a `fila`.
- SKILL.md lista `exec` entre os "nunca", a *description* (que dispara a skill) promete "É SÓ
  LEITURA", e `references/commands-allowlist.md` põe `exec` em "proibidos explicitamente". O
  design não previa reescrever nenhum dos três.
- SKILL.md diz "SSH não: comando remoto é outra superfície" — mas `exec` por context `ssh://`
  é exatamente comando remoto no host.

## O que quebra na prática

- **Swarm:** o `exec` só alcança container no nó do context. Com 5 nós, a fila está no nó certo
  em ~1/5 das rodadas. A feature responderia por sorte do escalonador.
- **Orçamento:** sem cache do id, são `service ps` + `container inspect` + identificação +
  verbo **por pergunta** (3× no papel fila). Com 57 componentes, estoura.
- **`rabbitmq-diagnostics`** costuma falhar por `.erlang.cookie`, usuário do exec e nome de nó;
  imagem distroless não tem binário; container reiniciando não aceita exec.

## Frouxidão nas travas que eu tinha proposto

- "`env_extra` vazio" era **vacuamente verdadeira** (run ignora extras). Pior: toda trava
  provada com `runner.run` monkeypatchado passa com o vazamento intacto — é o que o
  `tests/test_restricoes.py` faz hoje, e o próprio spec já admitia.
- "flags proibidas": a mutação `-u` → `--user=root` passa.
- "origem do id" não é testável dentro de `check()`, que só vê strings. Precisa de
  `^[0-9a-f]{64}$` no slot do id.
- "opt-in obrigatório" precisa de espião no `subprocess.run` real afirmando que nenhum argv
  contém `exec` — não que o adaptador devolveu `sem_dados`.

## O que o revisor mandou manter

Manter a `docker_allowlist` intacta e o runner como único ponto de subprocesso; a preferência
por binário incapaz de escrever; a fonte carimbada `exec_cli:<familia>`; e o diagnóstico de que
a reserva precisa existir.
