---
titulo: Auditoria do host por SSH somente leitura
slug: 2026-09-19-auditoria-do-host-por-ssh-somente-leitura
criado: 2026-09-19
estado: aprovado
---

# Auditoria do host por SSH somente leitura

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `plan.md` é o passo a
> passo de execução; `referencias/` guarda o material de apoio.

## Objetivo & outcome

A skill hoje vê o servidor **pelos olhos do Docker**: nós `Ready`, versão de engine, serviços,
`docker system df`. Falta o que só o sistema operacional sabe — e a diferença é concreta:

> O daemon diz "3 nós Ready, convergido". O host diria "o disco de um deles está em 94%".

Os dois estão certos ao mesmo tempo, e só o segundo avisa que há poucos dias antes de tudo parar.

Outcome observável: um alvo `tipo = "host"` declarado com uma linha entra no relatório com
espaço em disco, memória, carga e tempo desde o último boot — e, quando cruzar limiar, vira
achado com remediação, como qualquer outro.

## O que o dono declara — e nada além disso

```toml
[[alvo]]
nome = "web-01"
tipo = "host"
ssh_destino = "usuario@10.0.0.10"
```

Sem chave, sem `known_hosts`, sem usuário dedicado. **A skill usa o SSH que já existe na
máquina de quem audita**: agente, chaves e `~/.ssh/config` como estão. No cenário do dono, o
acesso depende da VPN estar ligada; com ela ligada, funciona sem mais nada.

## A postura de segurança, dita como ela é

Esta é a decisão central, e o relatório precisa repeti-la em vez de sugerir garantia maior:

**A auditoria roda com a identidade SSH de quem a executa** — que, normalmente, tem acesso
pleno àquele servidor. A restrição **não** vem do servidor: vem da skill, na forma de uma lista
fechada de comandos de leitura. Quem confia na auditoria está confiando no cliente, não no
`authorized_keys`.

O que **continua inegociável**, porque é buraco e não política:

1. **O destino é validado, e o primeiro caractere é ancorado.**

   ```python
   DESTINO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*@[A-Za-z0-9][A-Za-z0-9._-]*")
   DESTINO.fullmatch(valor)      # fullmatch, não `$`: `$` casa com "\n" no fim
   ```

   Ancorar o primeiro caractere é o ponto inteiro: com o hífen dentro da classe e sem âncora,
   `-Jevil@host` **passa** e vira **opção**, não destino — e executa comando **na máquina de
   quem audita**, fora de qualquer allowlist. O mesmo cuidado vale para todo campo que entre
   no argv, inclusive `nome` (que vira caminho de pasta).

   **Porta é campo próprio** (`porta = 2222` → `-p 2222`), não parte do destino:
   `usuario@host:2222` não é sintaxe que o `ssh` entenda — ele procuraria um host chamado
   `host:2222`, falharia, e a skill imprimiria "a VPN está ligada?", mentindo sobre a causa.
   Destino com `:` é recusado na leitura do `alvos.toml`, com mensagem própria.
2. **Allowlist por forma do argv, escrita por extenso.** O perfil `ssh` do runner não valida
   "o binário é ssh": valida o argv inteiro contra **um molde único**, e o comando remoto é um
   **elemento só**, literal do catálogo:

   ```python
   ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=<n>",
           "-o", "RemoteCommand=none", "-o", "RequestTTY=no",
           *(["-p", str(porta)] if porta else []),
           destino, comando_do_catalogo]
   ```

   **Zero interpolação no comando remoto.** O `lib/catalogo.py` que já existe permite
   `%SELETOR%`/`%JANELA%` — copiar aquele módulo traria a interpolação junto, e com ela `;`,
   `|` e `$()` voltariam a existir do outro lado, onde há um shell de verdade. O catálogo de
   host **não interpola nada**: o comando é literal, e a allowlist valida contra o conjunto
   carregado do arquivo.

   `RemoteCommand=none` e `RequestTTY=no` são consequência direta de manter o `~/.ssh/config`
   ligado (ADR 3): um `RemoteCommand` no config **troca o que roda no servidor**, e aí a
   allowlist descreveria uma execução que não acontece.
3. **`BatchMode=yes` e `ConnectTimeout`.** Nunca pergunta senha (falha rápido em vez de travar a
   auditoria) e não fica pendurado quando a VPN está desligada.
4. **Nada de escrita, nunca.** Os comandos do catálogo são de leitura; qualquer outro é recusado
   antes de tocar no subprocesso, como já acontece com o docker.

**O `~/.ssh/config` fica ligado de propósito.** A primeira revisão pediu `-F /dev/null` porque
um `ProxyCommand` no config executa comando local. Mas o config é **do próprio dono**, e é dele
que vêm apelido e *jump host* — desligá-lo quebraria justamente o acesso que se quer usar. Com
o destino validado (ponto 1), o vetor que a revisão temia deixa de existir: ninguém injeta
opção pelo `alvos.toml`.

**Endurecer é opcional, e a skill ensina.** Quem quiser que a garantia venha do servidor recebe
as três linhas prontas (usuário de leitura, script de coleta, `restrict,command=` no
`authorized_keys`) e **declara** `acesso_restrito = true` no alvo; só então o relatório troca a
ressalva. A skill **não tenta detectar** isso: detectar exigiria mandar um comando fora do
catálogo para ver se o servidor recusa — exatamente o que a restrição 2 proíbe.

**O texto que vai ao relatório**, na ficha do alvo e na seção de insights, sem eufemismo:

> Acesso com a identidade SSH de quem executou a auditoria. A restrição de comandos é da skill,
> não do servidor.

E, com `acesso_restrito = true`:

> Acesso restrito no servidor: a chave só executa o script de coleta.

## O que se lê — e o que nunca se lê

| Lê | Por que só o host sabe |
|---|---|
| partições e espaço livre (`/`, `/var/lib/docker`) | `docker system df` mostra o que o Docker usa, não o que sobra na partição |
| memória, swap, carga | o cluster pode estar convergido com a máquina em thrashing |
| tempo desde o último boot | reinício inesperado é sinal que some do relatório |
| kernel e versão do sistema | não aparece em lugar nenhum hoje — entra como **fato do inventário** na ficha do alvo, não como pergunta com faixa (não há limiar honesto para "versão do kernel") |

**Nunca lê:** conteúdo de arquivo de configuração · chave privada · `/etc/shadow` · log de
qualquer natureza · histórico de shell · variável de ambiente de processo · **conteúdo de tarefa
agendada** (linha de cron carrega senha com frequência; conta-se quantas são, não o que fazem).

Fora da v1, por decisão de escopo: firewall, portas em escuta e tarefas agendadas. As três
exigem privilégio elevado ou expõem mapa de exploração no relatório — entram num ciclo próprio,
se entrarem.

## Arquitetura: encaixa no que já existe

- **Tipo de alvo, não componente.** `[[alvo]] tipo = "host"`. Um servidor pode não ter Docker; e
  o nó do swarm que já aparece no inventário é a visão do daemon, não do sistema. Fundir os dois
  esconderia exatamente a diferença que motiva este trabalho.
- **Papel `host`** em `lib/papel.py`, com perguntas próprias em `lib/perguntas.py`
  (`host.espaco_em_disco`, `host.memoria`, `host.carga`, `host.desde_o_boot`), cada uma com
  **faixa declarada** — é o que permite o mostrador no relatório sem inventar tolerância.
- **Adaptador `ssh`** em `lib/adaptadores/ssh.py`, mesmo contrato dos outros: `perguntar(...)`
  devolve valor com fonte, ou `sem_dados` com motivo. Nunca levanta.
- **Perfil `ssh` no runner**, com `ambiente()` sem nenhuma variável extra — a autenticação é por
  agente ou arquivo, não por senha em variável. É a primeira vez que o runner roda binário que
  não é docker, e é por isso que a allowlist passa a validar forma, não binário.
- **Catálogo por família** (`references/host/linux.toml`): o comando de cada pergunta, o formato
  da saída e como extrair. Distribuição diferente vira arquivo novo, não `if`.

**O que o código precisa ganhar, e o plano não pode descobrir sozinho:**

| Onde | O quê |
|---|---|
| `lib/alvos.py` | tipo `host`, campos `ssh_destino` e `porta`, validação do destino |
| `lib/papel.py` | papel `host` em `PAPEIS` — e o teste de consistência passa a aceitar que um componente de docker **também** possa declará-lo |
| `lib/perguntas.py` | as perguntas do papel `host`, com faixa e a marca `volatil` |
| `collect.onde_de()` | ramo do host: hoje cai em `alvo.get("host","")` e o menu de confirmação mostraria alvo **sem "onde"**, contrariando a SKILL.md |
| `collect.coletores_padrao()` | coletor `host`, que monta **um componente** carregando `ssh_destino` — do mesmo jeito que o coletor docker hoje carrega `metricas_url` para dentro do componente. É assim que o endereço chega ao adaptador sem mudar o contrato `perguntar(pergunta, componente, contexto)` |
| `lib/adaptadores/__init__.py` | registro do `ssh` com prioridade **menor** que `promql` (mais específico ganha) |
| `lib/runner.py` | perfil `ssh`: allowlist por forma, `ambiente()` sem variável extra |
| `SKILL.md` | a seção **Limites** diz hoje "**SSH não**" — precisa mudar, senão a skill contradiz a si mesma |

## Erros: a VPN desligada é o caso comum

Falha de conexão **nunca vira achado** — vira `sem_dados` com o motivo real, e o motivo precisa
ser útil: *"não abri a sessão para `usuario@host` (a VPN está ligada?)"*. É o estado esperado
metade do tempo, não um problema da infraestrutura auditada.

Quando o alvo **também** declara `metricas_url` e existe um `references/metricas/node-exporter.toml`,
o adaptador `promql` responde disco, memória e carga, e o relatório degrada para **menos
detalhe** em vez de vazio. Nenhuma das duas coisas é obrigatória: sem elas, o host com a VPN
desligada aparece como `sem dados` com o motivo — que é o comportamento correto, não uma falha.

## Determinismo, e o que o teste consegue provar

Espaço livre, carga e uptime mudam a cada segundo: nenhuma coleta real se repete. O que
permanece verdadeiro é o que já vale para o resto da skill — **mesma entrada, mesmo byte**: com
as saídas gravadas nas fixtures e o mesmo `--at`, o `report.json` e o HTML saem idênticos. O
teste prova o **pipeline** (parsing, ordenação, faixa, achado), não a coleta; dizer o contrário
seria vender o que ele não faz.

Para a leitura diff-a-diff continuar útil, o relatório mostra **faixa** onde o número é volátil
(disco em 94% é "crítico", não "94,3%"), guardando o valor cru no `report.json`. Isso é uma
marca **por pergunta** (`volatil = True`), não mudança de comportamento global: `entrada.latencia`
já está publicada mostrando o número, e mudar isso por tabela alteraria relatório que já existe.
O alívio acontece no HTML; o `report.json` continua com o valor cru, e o diff dele continua
mudando a cada rodada — dizer o contrário seria prometer o que não se entrega.

## Regras novas e remediação

`disco_quase_cheio` · `memoria_sem_folga`. Cada uma com arquivo em `references/remediacao/` — a
fitness function que já existe derruba a suíte se faltar.

**Cortadas da v1** (entram no ciclo seguinte, se entrarem): `atualizacoes_de_seguranca_pendentes`
e `servico_falhou`. A primeira exige catálogo por gerenciador de pacotes (apt, dnf, apk) e a
segunda depende de systemd — cada uma puxa uma família nova de arquivo, e nenhuma cabe no mesmo
ciclo em que o transporte nasce.

**Achado nunca nasce de ausência.** `disco_quase_cheio` exige o número presente: linha que não
casou com o formato do catálogo vira `sem_dados`, nunca "há espaço de sobra" nem "está cheio".
Disco que não foi lido e disco com folga não podem terminar no mesmo lugar do relatório.

## Testes

Um `ssh` falso no `PATH` devolvendo saída gravada — nenhum servidor real, nenhuma rede. Mutação
obrigatória, cada uma tem que derrubar teste:

- aceitar `ssh_destino` que começa com `-`;
- montar comando remoto fora do catálogo;
- tirar o `BatchMode=yes` (a auditoria trava esperando senha);
- fazer falha de conexão virar achado em vez de `sem_dados`;
- tirar `RemoteCommand=none` do argv.

## Não-objetivos

Escrever qualquer coisa no servidor · `sudo` · firewall, portas em escuta e tarefas agendadas na
v1 · ler log · exigir configuração no servidor · Windows · descobrir host sozinho (só entra o
que o dono declarou).

## Restrição de simplicidade

A menor solução que resolve: **um tipo de alvo, um adaptador, um arquivo de catálogo, quatro
perguntas (`espaco_em_disco`, `memoria`, `carga`, `desde_o_boot`) e duas regras**. Sem agente instalado, sem inventário automático, sem coletor paralelo.

## Appetite

Um ciclo curto — cabe num plano só, na mesma ordem dos anteriores: transporte e alvo primeiro,
perguntas e faixas depois, regras e remediação por último.

## Decisões (ADR)

| # | Contexto | Decisão | Alternativas descartadas | Consequência |
|---|---|---|---|---|
| 1 | Auditar o host exige acesso ao sistema | SSH com a identidade de quem audita | Publicar como métrica via textfile collector; agente instalado | Zero configuração por máquina; a garantia é do cliente, e o relatório diz isso |
| 2 | Campo do `alvos.toml` entra no argv do `ssh` | Validar `ssh_destino` por regex estrita | Confiar no arquivo, que é do dono | Fecha execução de comando local por injeção de opção |
| 3 | A revisão pediu `-F /dev/null` | Manter o `~/.ssh/config` do dono | Ignorar o config | Apelido e jump host continuam funcionando; o vetor temido morre com a decisão 2 |
| 4 | O runner era docker-only | Allowlist por **forma do argv**, não por binário | Checar só `cmd[0] == "ssh"` | Continua allowlist positiva de verdade |
| 5 | Nó do swarm e host são o mesmo ferro | Alvos separados, sem correlação inferida | Fundir; inferir por hostname | Duas leituras explícitas; correlacionar por hostname seria adivinhação |
| 6 | Número volátil quebra a leitura entre rodadas | Faixa no relatório, valor cru no JSON, marcada **por pergunta** (`volatil`) | Mostrar o número cru; aplicar a todas as perguntas por tabela | Diff entre auditorias volta a ser legível **sem** mexer em `entrada.latencia`, já publicada mostrando o número |

## Restrições verificáveis (fitness functions)

1. **`ssh_destino` fora do formato é recusado na leitura do `alvos.toml`.** O teste inclui, um a
   um: `-Jevil@host`, `-Fx@y`, `usuario@host:2222`, `usuario@host\n`, `@host`, `usuario@`.
   Tirar a âncora do primeiro caractere **tem** que derrubar o primeiro caso — foi exatamente
   por falta dela que a versão anterior deste spec tinha uma trava que não travava.
2. **Nenhum comando remoto fora do catálogo chega ao subprocesso**, e **nenhuma interpolação**
   acontece no comando: o teste captura o `subprocess.run` real, compara o argv inteiro com o
   molde e confere que o último elemento é idêntico a uma entrada do catálogo. Introduzir
   `%ALGO%` no comando derruba teste.
3. **Falha de conexão produz `sem_dados` com motivo, e zero achados** para aquele alvo.
4. **Mesma entrada, mesmo byte:** com as saídas gravadas e o mesmo `--at`, duas execuções geram
   `report.json` idêntico.
5. **Toda regra nova tem arquivo de remediação** — a fitness function que já existe, agora
   cobrindo `disco_quase_cheio` e `memoria_sem_folga`.
6. **O argv carrega `RemoteCommand=none` e `RequestTTY=no`.** Tirar qualquer um dos dois derruba
   teste: sem eles, um `RemoteCommand` no `~/.ssh/config` troca o que roda no servidor e a
   allowlist vira ficção.
