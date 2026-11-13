---
titulo: Auditoria do host por SSH somente leitura, com descoberta do que roda nele
slug: 2026-09-19-auditoria-do-host-por-ssh-somente-leitura
criado: 2026-09-19
estado: concluido
---

# Auditoria do host por SSH somente leitura, com descoberta do que roda nele

> **Revisado em 2026-11-13** (ver "Revisões do spec" no fim): a descoberta dentro do servidor entrou
> no escopo, e nada deste spec tinha sido construído ainda.

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `plan.md` é o passo a
> passo de execução; `referencias/` guarda o material de apoio.

## Objetivo & outcome

A skill hoje vê o servidor **pelos olhos do Docker**: nós `Ready`, versão de engine, serviços,
`docker system df`. Falta o que só o sistema operacional sabe — e a diferença é concreta:

> O daemon diz "3 nós Ready, convergido". O host diria "o disco de um deles está em 94%".

Os dois estão certos ao mesmo tempo, e só o segundo avisa que há poucos dias antes de tudo parar.

Outcome observável: um alvo `tipo = "host"` declarado com uma linha entra no relatório com
espaço em disco, memória, carga e tempo desde o último boot — e, quando cruzar limiar, vira
achado com remediação, como qualquer outro. **E** o que roda nele (banco, cache, Qdrant, proxy) é
descoberto, confirmado pelo dono e gravado como componente do alvo, para a coleta por produto
(parte B, spec próprio) saber o que perguntar. [usuário]

Motivação concreta: servidores de banco, de busca vetorial e de VPN ficam fora do cluster e não
aparecem em relatório nenhum, porque a skill só conhece os tipos `docker` e `http`
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/alvos.py:14].

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

> Acesso com a identidade SSH de quem executou a auditoria (`<usuário>`). A restrição de
> comandos é da skill, não do servidor.

`<usuário>` vem de `id -un`, que entra no catálogo: com apelido no `~/.ssh/config` o destino não
diz quem entrou. Nos servidores do dono é `root` [usuário], e o texto diz isso sem rodeio.

**O comando remoto passa pelo shell de login do servidor.** O `ssh` entrega o último elemento do
argv a esse shell; não existe "sem shell" do outro lado. Continua seguro porque o texto é literal
do catálogo, sem nenhuma vaga — mas aspas, como as do `docker ps --format`, são interpretadas lá,
e o spike 1 confere que chegam como esperado.

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

Portas em escuta **são lidas** desde a revisão de 2026-11-13, mas só servem à descoberta: o
relatório não traz lista de portas, só o achado de banco ou cache escutando em todas as
interfaces (ver "Descoberta do que roda no servidor"). [usuário] Firewall e tarefas agendadas
continuam fora.

## Descoberta do que roda no servidor

Passo próprio, **antes** da coleta: `configurar.py descobrir --alvo <host>`. [usuário] A coleta
continua determinística e só trabalha com o que está declarado.

**Comandos** (literais, em `references/host/linux.toml`):

| Lê | Comando | Sem ele |
|---|---|---|
| quem entrou | `id -un` | o texto diz "identidade de quem audita", sem nome |
| serviços ativos | `systemctl list-units --type=service --state=running --no-legend --plain --no-pager` | host sem systemd: fonte "não medida" |
| portas e processo | `ss -ltnpH` (com root, traz o nome do processo) | casa só por unidade e container |
| containers locais | `docker ps --format` com nome, imagem e portas | segue sem containers |

Fonte que falha ou devolve formato inesperado vira "não medida"; as outras seguem.

**Casamento com `references/produtos.toml`.** Cada produto ganha dois campos opcionais além de
`imagem`, e `imagem` passa a ser opcional quando há um deles — hoje ela é obrigatória
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/produtos.py:23]:

```toml
[[produto]]
nome = "mariadb"
imagem = ["mariadb"]
unidade = ["mariadb", "mysql"]      # trecho no nome da unit do systemd
processo = ["mariadbd", "mysqld"]   # nome do processo como o ss mostra (até 15 caracteres)
kind = "banco"
```

- **Força:** processo > unidade > imagem. Porta nunca identifica sozinha.
- **`ss` corta o nome do processo em 15 caracteres:** os valores de `processo` respeitam esse
  limite, e o carregador recusa valor maior.
- **Porta de container:** quando o `ss` mostra `docker-proxy` ou `dockerd` na porta, ela é
  cruzada com as portas do `docker ps`, que dão a imagem e, por ela, o produto.
- **Qdrant** entra como produto novo; o papel dele e as perguntas são da parte B.
- **Sem casamento:** processo que escuta sem produto conhecido aparece como "não reconhecido em
  :porta", e o dono decide se entra e com que papel.
- **Ruído de sistema** (`sshd`, `systemd-resolved`, `chronyd` e afins): lista `ignorar` no
  catálogo de host, não no código.
- **Todas as interfaces** = `0.0.0.0`, `*` ou `[::]`/`::`. `127.0.0.1`, `::1` e IP privado não são.

**Saída:** por candidato, produto, origem, portas e endereço de escuta. **Nunca** linha de
comando do processo, ambiente ou caminho de arquivo de configuração: carregam senha.

## Gravação no `alvos.toml`

`configurar.py descobrir --alvo <host> --gravar <nomes> [--papel nome=papel]`, depois de o dono
escolher por `AskUserQuestion` o que entra. [usuário] É a primeira vez que a skill escreve num
`alvos.toml` existente — hoje ela só cria o arquivo e nunca sobrescreve
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/configurar.py:97].

- **Onde:** um bloco `[[alvo.componente]]` por item, **logo depois do bloco daquele alvo**. No fim
  do arquivo, o TOML penduraria o componente no último alvo.
- **O quê:** comentário `# descoberto em <data>` e os campos `nome`, `papel`, `produto`,
  `portas` e `origem`. `produto`, `portas` e `origem` são campos novos em
  `COMPONENTE_PERMITE` [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/alvos.py:25]; `produto` desconhecido é
  recusado na leitura, como `papel` já é.
- **Identidade entre rodadas:** `origem` (`unidade:<unit>`, `container:<nome>` ou
  `processo:<nome>`). O `nome` deriva dela — sem `.service`, `@` vira `-` — para passar no
  `NOME_VALIDO` [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/alvos.py:27], que recusa `@`.
- **Texto que vem do servidor é validado antes de escrever.** `origem`, `produto` e `portas` vêm
  de nomes de unit, container e processo, e um nome malicioso com aspas, `\`, `[` ou quebra de
  linha injetaria TOML (um `[[alvo]]` novo passaria na releitura). Regra: `origem` casa
  `^(unidade|container|processo):[A-Za-z0-9][A-Za-z0-9._@:-]{0,127}$`, `produto` existe no catálogo,
  `portas` são inteiros de 1 a 65535. Candidato que não passa não é gravável e aparece como "nome
  com caractere não aceito". Esses textos também chegam ao agente no `AskUserQuestion`: são dado
  a mostrar, nunca instrução a seguir.
- **Antes:** confere o `.gitignore` (regra que já existe) e copia para `alvos.toml.bak`.
- **Depois:** relê com `tomllib`; se não abrir, ou o alvo não tiver exatamente os componentes
  pedidos, restaura o `.bak` e para com erro.
- Nunca reescreve nem reordena linhas existentes; `origem` repetida não duplica.

## Rodadas seguintes e achados da descoberta

A coleta do alvo `host` roda os mesmos comandos e compara o encontrado com o declarado, por
`origem`. A coleta **nunca escreve**.

- **Encontrado e não declarado:** nota no alvo, com a oferta de rodar `descobrir`.
- **Declarado e ausente:** achado `servico_declarado_ausente` (high), **só quando a fonte que
  originou aquele componente respondeu**. É a única exceção a "achado nunca nasce de ausência", e
  ela existe porque a fonte respondeu e o serviço não estava lá. Fonte que falhou deixa todos os
  componentes dela como "não medidos".
- **Banco ou cache declarado em todas as interfaces** (o encontrado e não declarado fica só na
  nota): achado `SEC_BIND_ALL_INTERFACES`, regra irmã de
  `SEC_PORT_EXPOSED` com remediação própria (`bind-address` e afins). A de hoje ensina YAML de
  Docker, que não serve para um processo do systemd. O texto diz que escutar em todas as
  interfaces não prova exposição à internet.
- **O mesmo servidor no cluster e como host:** os dois alvos acusam a porta pela própria leitura,
  e o achado do host diz que o servidor também é nó do cluster. Decisão do dono: aceitar em
  dobro, em vez de esconder num lado. [usuário]

## Arquitetura: encaixa no que já existe

- **Tipo de alvo, não componente.** `[[alvo]] tipo = "host"`. Um servidor pode não ter Docker; e
  o nó do swarm que já aparece no inventário é a visão do daemon, não do sistema. Fundir os dois
  esconderia exatamente a diferença que motiva este trabalho.
- **Papel `maquina`, que já existe** [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/papel.py:11], em vez de um papel
  `host` novo. [usuário] O SSH responde as mesmas perguntas que o node-exporter já responde para os
  nós do cluster (`maquina.cpu`, `maquina.memoria`, `maquina.disco`, `maquina.disco_dias`
  [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/perguntas.py:123]) e ganha `maquina.carga` e `maquina.desde_o_boot`.
  `maquina.disco` e `maquina.memoria` ganham **limiar**, e o achado vale para host **e** para nó do
  cluster: o mesmo disco a 94% não pode ser achado num lugar e silêncio no outro. Isso troca a
  decisão de hoje, "achado de capacidade é outra decisão"
  [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/perguntas.py:122], e o comentário muda junto.
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
| `lib/alvos.py` | tipo `host`, campos `ssh_destino`, `porta` (inteiro de 1 a 65535) e `acesso_restrito` (booleano), validação do destino |
| `lib/papel.py` | nada: o componente da máquina do host usa o papel `maquina`, que já existe |
| `lib/perguntas.py` | `maquina.carga` e `maquina.desde_o_boot`; limiar em `maquina.disco` e `maquina.memoria`; marca `volatil` |
| `collect.onde_de()` | ramo do host: hoje cai em `alvo.get("host","")` e o menu de confirmação mostraria alvo **sem "onde"**, contrariando a SKILL.md |
| `collect.coletores_padrao()` | coletor `host`, que monta **um componente** carregando `ssh_destino` — do mesmo jeito que o coletor docker hoje carrega `metricas_url` para dentro do componente. É assim que o endereço chega ao adaptador sem mudar o contrato `perguntar(pergunta, componente, contexto)` |
| `lib/adaptadores/__init__.py` | registro do `ssh` com prioridade **menor** que `promql` (mais específico ganha) |
| `lib/runner.py` | perfil `ssh`: allowlist por forma, `ambiente()` sem variável extra |
| `SKILL.md` | a seção **Limites** diz hoje "**SSH não**" [visto: plugins/sw-infra-audit/skills/sw-infra-audit/SKILL.md:508] — precisa mudar, senão a skill contradiz a si mesma |
| `lib/produtos.py` | campos `unidade` e `processo`; `imagem` opcional quando houver um deles; `processo` com até 15 caracteres |
| `references/produtos.toml` | `unidade`/`processo` nos produtos com estado; produto `qdrant` |
| `references/host/linux.toml` | os comandos das perguntas `maquina.*` (disco, memória, carga, boot), de kernel e versão do sistema (fato do inventário), de descoberta, `id -un` e a lista `ignorar` |
| `lib/descoberta.py` (novo) | pura: recebe as saídas gravadas e devolve candidatos casados; sem rede, testável por fixture |
| `configurar.py` | subcomando `descobrir` com `--gravar` e `--papel` |
| `lib/regras.py` (registro) + `lib/rule_meta.py` + `references/remediacao/` | `servico_declarado_ausente` e `SEC_BIND_ALL_INTERFACES`, cada uma com arquivo |

## Erros: a VPN desligada é o caso comum

Falha de conexão **nunca vira achado** — vira `sem_dados` com o motivo real, e o motivo precisa
ser útil: *"não abri a sessão para `usuario@host` (a VPN está ligada?)"*. É o estado esperado
metade do tempo, não um problema da infraestrutura auditada.

Quando o alvo **também** declara `metricas_url`, o adaptador `promql` responde as perguntas
`maquina.*` pelo `references/metricas/node-exporter.toml` que já existe — é a vantagem de reusar o
papel —, e o relatório degrada para **menos detalhe** em vez de vazio. Nenhuma das duas coisas é obrigatória: sem elas, o host com a VPN
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

`disco_quase_cheio` · `memoria_sem_folga` (limiar de `maquina.disco` e `maquina.memoria`, para host
e nó do cluster) · `servico_declarado_ausente` · `SEC_BIND_ALL_INTERFACES`. Cada uma com arquivo em
`references/remediacao/` — a fitness function que já existe derruba a suíte se faltar.

**Cortadas da v1** (entram no ciclo seguinte, se entrarem): `atualizacoes_de_seguranca_pendentes`
e `servico_falhou`. A primeira exige catálogo por gerenciador de pacotes (apt, dnf, apk) e a
segunda depende de systemd — cada uma puxa uma família nova de arquivo, e nenhuma cabe no mesmo
ciclo em que o transporte nasce.

**Achado nunca nasce de ausência** — com a única exceção de `servico_declarado_ausente`, descrita em
"Rodadas seguintes" (só com a fonte de origem respondendo). `disco_quase_cheio` exige o número presente: linha que não
casou com o formato do catálogo vira `sem_dados`, nunca "há espaço de sobra" nem "está cheio".
Disco que não foi lido e disco com folga não podem terminar no mesmo lugar do relatório.

## Testes

Um `ssh` falso no `PATH` devolvendo saída gravada — nenhum servidor real, nenhuma rede. Mutação
obrigatória, cada uma tem que derrubar teste:

- aceitar `ssh_destino` que começa com `-`;
- montar comando remoto fora do catálogo;
- tirar o `BatchMode=yes` (a auditoria trava esperando senha);
- fazer falha de conexão virar achado em vez de `sem_dados`;
- tirar `RemoteCommand=none` do argv;
- (fase 2) deixar passar linha de comando ou ambiente do processo para o resultado da descoberta;
- (fase 2) gravar `origem` com caractere fora da regex (aspas, `\`, quebra de linha, `[`);
- (fase 2) gravar sem criar o `.bak`;
- (fase 2) gerar `servico_declarado_ausente` com a fonte de origem falhando.

## Não-objetivos

Escrever qualquer coisa no servidor · `sudo` · firewall e tarefas agendadas · lista de portas no
relatório · ler log · exigir configuração no servidor · Windows · descobrir **host** sozinho (só
entra o servidor que o dono declarou; a descoberta é do que roda dentro dele) · coleta de dados de
cada produto (parte B) · blocos novos do relatório (parte C).

## Restrição de simplicidade

A menor solução que resolve: **um tipo de alvo, um adaptador, um arquivo de catálogo, quatro
perguntas `maquina.*` respondidas por SSH (duas delas novas: `carga` e `desde_o_boot`), um módulo
puro de descoberta, um subcomando de gravação e quatro regras**. Sem agente instalado no servidor e sem coletor paralelo.

## Appetite

Médio, em duas fases no mesmo plano: **(1) transporte** — alvo, runner `ssh`, adaptador, as quatro
perguntas e as duas regras de setembro; **(2) descoberta** — catálogo de produtos, módulo de
descoberta, gravação e as duas regras novas. Nada de setembro existe no código ainda: o runner só
aceita docker [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/runner.py:1].

## Decisões (ADR)

| # | Contexto | Decisão | Alternativas descartadas | Consequência |
|---|---|---|---|---|
| 1 | Auditar o host exige acesso ao sistema | SSH com a identidade de quem audita | Publicar como métrica via textfile collector; agente instalado | Zero configuração por máquina; a garantia é do cliente, e o relatório diz isso |
| 2 | Campo do `alvos.toml` entra no argv do `ssh` | Validar `ssh_destino` por regex estrita | Confiar no arquivo, que é do dono | Fecha execução de comando local por injeção de opção |
| 3 | A revisão pediu `-F /dev/null` | Manter o `~/.ssh/config` do dono | Ignorar o config | Apelido e jump host continuam funcionando; o vetor temido morre com a decisão 2 |
| 4 | O runner era docker-only | Allowlist por **forma do argv**, não por binário | Checar só `cmd[0] == "ssh"` | Continua allowlist positiva de verdade |
| 5 | Nó do swarm e host são o mesmo ferro | Alvos separados, sem correlação inferida | Fundir; inferir por hostname | Duas leituras explícitas; correlacionar por hostname seria adivinhação |
| 6 | Número volátil quebra a leitura entre rodadas | Faixa no relatório, valor cru no JSON, marcada **por pergunta** (`volatil`) | Mostrar o número cru; aplicar a todas as perguntas por tabela | Diff entre auditorias volta a ser legível **sem** mexer em `entrada.latencia`, já publicada mostrando o número |
| 7 | Servidor fora do cluster é invisível | Descoberta dentro do host declarado, confirmada pelo dono [usuário] | Só o declarado à mão; descobrir sem confirmar | O dono não precisa saber de antemão o que roda; nada é coletado sem o ok |
| 8 | Onde a descoberta mora | Passo próprio (`configurar.py descobrir`) antes da coleta [usuário] | Dentro do `collect.py` em duas passadas; só imprimir sugestão | A coleta segue determinística; primeira escrita num `alvos.toml` existente, com `.bak` e releitura |
| 9 | Portas expõem mapa | Lidas para descobrir; no relatório só o achado de banco/cache em todas as interfaces [usuário] | Lista completa; não ler | Relatório útil sem virar mapa de exploração |
| 10 | Chave entre rodadas | `origem` (unidade, container ou processo) | Nome do produto; produto + porta | Dois MariaDB no mesmo host continuam distintos; porta trocada não vira "sumiu" |
| 11 | Ausência como achado | `servico_declarado_ausente` só com a fonte de origem respondendo | Proibir (regra de setembro); acusar sempre | Banco parado aparece; fonte quebrada não gera high falso |
| 12 | Remediação de porta | Regra irmã `SEC_BIND_ALL_INTERFACES` | Reusar `SEC_PORT_EXPOSED` | A remediação ensina `bind-address`, não YAML de Docker |
| 13 | Mesmo servidor em dois alvos | Achado de porta pelos dois [usuário] | Só o cluster; só o host | Achado em dobro, com o texto dizendo por quê |
| 14 | Já existe o papel `maquina`, sem limiar | Reusar `maquina` e pôr limiar em disco e memória, para host e nó [usuário] | Papel `host` com perguntas próprias (setembro); reusar sem achado | Recuo para o node-exporter sai de graça; os relatórios do cluster passam a ter achado de capacidade |
| 15 | Texto do servidor vai para um arquivo local | Validar `origem`, `produto` e `portas` por regex e catálogo antes de gravar | Escapar e gravar qualquer texto | Fecha injeção de TOML por nome de processo; nome estranho fica de fora em vez de gravado |

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
   cobrindo `disco_quase_cheio`, `memoria_sem_folga`, `servico_declarado_ausente` e
   `SEC_BIND_ALL_INTERFACES`.
6. **O argv carrega `RemoteCommand=none` e `RequestTTY=no`.** Tirar qualquer um dos dois derruba
   teste: sem eles, um `RemoteCommand` no `~/.ssh/config` troca o que roda no servidor e a
   allowlist vira ficção.
7. **`descobrir` sem `--gravar` não altera nenhum arquivo:** hash do `alvos.toml` igual antes e
   depois.
8. **Depois de `--gravar`, o diff do `alvos.toml` só tem linhas `+`:** toda linha antiga continua
   igual e na mesma ordem. Gravação cuja releitura falha deixa o arquivo idêntico ao `.bak`.
9. **Nenhum campo da descoberta carrega linha de comando, ambiente ou caminho de configuração do
   processo:** o teste usa uma saída de `ss` e de `docker ps` com esses dados e confere que não
   chegam ao resultado.
10. **Componente com `produto` desconhecido é recusado** na leitura do `alvos.toml`, com mensagem
    que cita o alvo e o valor.
11. **Nome malicioso não vira TOML:** um processo chamado `x"]\n[[alvo]]` (e variantes com `\`,
    `[` e quebra de linha) não é gravável, e o `alvos.toml` sai idêntico.

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| O formato de saída de `systemctl`, `ss -ltnpH` e `docker ps` nos servidores do dono é o que o parser espera | a descoberta não acha nada, ou acha errado | spike 1: rodar os quatro comandos num servidor real, com ok do dono, e gravar a saída anonimizada como fixture — incluindo host com Docker publicando porta, IPv6 e processo com nome acima de 15 caracteres |
| As aspas do `docker ps --format` chegam intactas pelo shell de login remoto | a fonte de containers vira "não medida" em todo host | o mesmo spike, comparando a saída com a esperada |
| Inserir o bloco logo depois do alvo, sem parser que preserve comentários, não quebra arquivos escritos à mão | a gravação corrompe o `alvos.toml` do dono | testes com arquivos de vários formatos (comentário no fim, alvo no meio, tabela inline) e a releitura obrigatória com restauração do `.bak` |

## Revisões do spec

- **2026-11-13** — a descoberta dentro do servidor entrou no escopo, a pedido do dono, para que
  bancos e serviços fora do cluster apareçam. Mudou: portas em escuta passaram a ser lidas (só para
  descobrir), os componentes confirmados são gravados no `alvos.toml`, o relatório diz o usuário
  real (`id -un`), e entraram `servico_declarado_ausente` e `SEC_BIND_ALL_INTERFACES`. A revisão
  do design achou que nada de setembro existia no código, que o comando remoto passa pelo shell de
  login, que `produtos.py` exigia `imagem` e que ausência virava achado falso com fonte quebrada;
  os quatro estão tratados acima. O appetite deixou de ser "ciclo curto". A revisão do spec achou o
papel `maquina` já existente (decisão do dono: reusar, com achado de capacidade para host e nó do
cluster) e a injeção de TOML por nome vindo do servidor (validação antes de gravar).
- **2026-11-13** — revisão do plano: o achado de capacidade não pode ser limiar, porque o catálogo
  recusa limiar em pergunta opcional (sem resposta, travaria o verde sem motivo). Ele nasce em
  `lib/capacidade.py`, que só lê resposta com número. Onde este spec diz que `maquina.disco` e
  `maquina.memoria` "ganham limiar", leia "ganham achado de capacidade"; a decisão 14 não muda.
