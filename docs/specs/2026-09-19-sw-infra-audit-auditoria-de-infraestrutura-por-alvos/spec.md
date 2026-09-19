---
titulo: "sw-infra-audit: auditoria de infraestrutura por alvos"
slug: 2026-09-19-sw-infra-audit-auditoria-de-infraestrutura-por-alvos
criado: 2026-09-19
estado: concluido
---

# sw-infra-audit — auditoria de infraestrutura por alvos

## Objetivo & outcome

A `sw-cluster-audit` só enxerga um cluster Docker. O que roda fora dele — banco noutro servidor,
API numa VPS, serviço gerenciado — fica invisível, e é justamente onde ninguém olha que quebra.

Este trabalho troca o objeto central: deixa de ser **o cluster** e passa a ser **o alvo**. A skill
vira `sw-infra-audit`, com três tipos de alvo na v1 (docker, banco, endpoint HTTP).

**Outcome:** numa página, o dono sabe **o que existe, onde vive e o que vai quebrar primeiro** —
sem repetir a cada auditoria o achado que ele já decidiu aceitar. Mede-se por: nenhum alvo real
fora do relatório, e nenhum achado repetido que já tenha justificativa registrada.

## Exploração & decisões

**Problema enquadrado:** a auditoria responde a quatro perguntas — o que vai quebrar antes de
quebrar, o que existe e onde, como mostrar isso a outra pessoa, e o que já foi decidido e não
precisa voltar.

**Ângulos levantados:** um relatório por alvo com índice; núcleo genérico plugável; relatório único
com coletor por tipo.

**Suposição derrubada:** a de que o relatório é sobre *um* cluster. Com alvos em lugares diferentes,
o cluster vira um caso particular.

**Suposição confirmada na revisão:** a camada de configuração versionada **não pode** mandar em
conexão. Arquivo versionado chega por clone e por pull request; se ele definir host ou credencial,
a auditoria conecta onde um terceiro mandar.

**Direção escolhida:** relatório único com um coletor por tipo, alvos definidos fora do repositório,
e um registro de risco aceito com justificativa e data de revisão.

## Decisões do usuário (fechadas)

| Tema | Decisão |
|---|---|
| Nome | `sw-infra-audit`, plugin novo; a `sw-cluster-audit` sai do marketplace com nota no CHANGELOG |
| Alvos na v1 | `docker` (o coletor atual), `banco` (Postgres e MySQL/MariaDB), `http` |
| Fora da v1 | SSH |
| Relatório | `docs/infra/` no projeto, com a pasta no `.gitignore` |
| Confirmação | Menu com **todos** os alvos, a cada execução |
| Usuário de banco | Se já existe um de leitura, declara no `alvos.toml`; se não, a skill **entrega o SQL** e o dono executa |
| Risco aceito | Seção própria no relatório, com justificativa e data de revisão; vencido volta a contar |

## Arquitetura

```
/sw-infra-audit  (dois modos, com poderes diferentes)

  configurar   escreve, com aprovação          migrar · alvos · aceitar · config --explicar
  auditar      NÃO escreve fora do relatório   confirmar → coletar → regras → aceites → relatório
```

```
1. agente    lê a configuração efetiva e mostra o MENU dos alvos → confirmação
2. collect.py --confirmar <nomes>   → coletores por tipo → report.json v2 (fatos + findings)
3. agente    escreve resumo, análise por alvo e recomendações no report.json
4. build_report.py                  → relatorio.html (+ .pdf)
```

### Unidades

| Unidade | Responsabilidade | Não faz |
|---|---|---|
| `lib/config.py` | Juntar as três camadas, resolver precedência, dizer a origem de cada valor | Conectar em nada |
| `lib/alvos.py` | Ler e validar `alvos.toml`; recusar alvo sem os campos obrigatórios | Guardar segredo |
| `lib/segredo.py` | Entregar a credencial ao subprocesso sem vazar (env do filho, `PGPASSFILE`, arquivo efêmero 600) | Gravar valor em lugar nenhum |
| `lib/runner.py` | **Único ponto que cria subprocesso**, para os três tipos: valida contra a allowlist do tipo e devolve saída redigida | Conhecer regra de negócio |
| `lib/coletores/docker.py` | O coletor de hoje, agora como tipo de alvo | Mudar de comportamento |
| `lib/coletores/banco.py` | Sondar versão, escolher o conjunto de consultas, executar a allowlist literal | Montar SQL dinâmico |
| `lib/coletores/http.py` | GET e validade do certificado, pelo ponto de rede único que já existe | Seguir redirect, mandar credencial |
| `lib/aceites.py` | Casar achado com aceite, marcar origem, expirar por data | Filtrar a coleta |
| `lib/report.py` | Schema v2, com alvo no centro | Decidir narrativa |

## Configuração: três camadas, com um limite duro

Precedência: **default → infra → projeto**, com uma exceção que é o ponto mais importante deste spec.

| Camada | Arquivo | Versionado | O que pode definir |
|---|---|---|---|
| Padrão | `default.toml`, dentro da skill | Com a skill | Caminhos, tempos limite, forma de ignorar, orçamento por alvo |
| Infra | `~/.config/sw-infra-audit/alvos.toml` (600) | **Nunca** | Os alvos: tipo, host, porta, usuário, nome da variável da senha, e aceites de infra |
| Projeto | `.sw-infra-audit.toml` na raiz | Sim | **Só**: quais alvos entram, severidade, aceites do produto, preferências de relatório |

**A camada do projeto não pode definir nem alterar conexão.** Host, porta, usuário, credencial e
tipo só existem na camada de infra. Chave de conexão encontrada no arquivo do projeto é **erro de
configuração**, não override: a auditoria para e diz qual chave e qual arquivo. Sem isso, um
`.sw-infra-audit.toml` vindo de um clone ou de um pull request redireciona conexão e credencial.

**Limiar de regra não é configurável na v1.** Fica fixo no código, para os achados continuarem
comparáveis entre projetos e para a matriz de teste não explodir.

`config --explicar` imprime a configuração efetiva com a origem de cada chave — com três camadas,
mais variável de ambiente e `~/.pgpass`, sem isso vira impossível de depurar.

## Segredos

- No `alvos.toml` fica o **nome** da variável de ambiente, nunca o valor. Alternativas aceitas:
  `~/.pgpass` (Postgres) e `mysql_config_editor` (MySQL).
- **Postgres:** `PGPASSWORD`/`PGPASSFILE` no ambiente **do subprocesso**, montado explicitamente.
  Nunca alterar o ambiente do processo da skill.
- **MySQL:** `--defaults-extra-file` apontando para arquivo efêmero com permissão 600, apagado ao
  fim mesmo em erro. **Nunca `-p<senha>`** (aparece no `ps`) e nunca `MYSQL_PWD` (emite aviso no
  stderr, que viraria texto do relatório).
- O redator de segredos passa a cobrir `password=`, `PGPASSWORD`, `MYSQL_PWD` e URI de conexão,
  além do `//usuario:senha@` que já cobre.
- **Saída de cliente nunca vira achado.** Falha de autenticação, cliente ausente ou permissão
  negada viram `nao_coletado` com motivo — hoje `findings_from_errors` promoveria isso a achado
  grave, o que confundiria "não consegui ver" com "está ruim".

## Confirmação por execução

Antes de qualquer conexão, o agente mostra o menu com **todos** os alvos da rodada — nome, tipo e
host — e espera o sim. O `collect.py` recebe `--confirmar <nomes>` e **recusa** tocar em alvo que
não esteja na lista. É o mesmo gate do `--confirmed-context` de hoje, agora por alvo.

## Coletores

Os quatro travamentos valem para os três tipos: **não escreve**, **não lê dado de aplicação**,
**não guarda segredo**, **não vira verde sem ter coletado**.

### docker
O coletor atual, sem mudança de comportamento: allowlist de 18 pares `(noun, verb)`; `logs`, `exec`
e `secret inspect` proibidos por construção. Vêm junto, agora sob o alvo: descoberta de stacks,
enriquecimento, `top_offenders` e os pontos de impacto.

**Métricas mudam de dono.** Hoje o endpoint é *descoberto* a partir do context e confirmado por
`--metrics-endpoint`, o que contraria a regra nova de egress. Passa a ser **campo do alvo docker**
no `alvos.toml` (`metricas_url`), confirmado junto com o alvo no menu da rodada. A descoberta
continua, mas só **propõe** o valor para você colar no `alvos.toml` — nunca alcança host que você
não declarou. Alvo docker sem `metricas_url` funciona: as métricas ficam `nao_coletado`.

### banco
Sonda a versão **primeiro** e escolhe o conjunto de consultas por `(motor, faixa de versão)` — uma
allowlist literal por conjunto, nenhuma montada dinamicamente. `SHOW REPLICA STATUS` (MySQL ≥ 8.0.22)
e `SHOW SLAVE STATUS` (anteriores e MariaDB) são conjuntos diferentes, não um `if` no meio da string.

| Pergunta | Fonte |
|---|---|
| Versão e se ainda tem suporte | `version()` / `SELECT VERSION()` |
| Conexões usadas contra o limite | `pg_stat_activity` / `SHOW STATUS` |
| Réplica existe, e o atraso | `pg_stat_replication` / `SHOW REPLICA STATUS` |
| Tamanho por base e schema | catálogo, agregado |
| Transação aberta há muito tempo | `pg_stat_activity` — **só a duração**, nunca o texto da query |
| Privilégio além do necessário | `pg_roles` / `mysql.user` — nomes e flags |
| Conexão exige TLS | `pg_settings` / `SHOW VARIABLES` |
| Manutenção atrasada | `pg_stat_user_tables`, agregado |

**Privilégio insuficiente vira `nao_coletado`,** com o nome da permissão que falta. Quando o
usuário declarado não tem o necessário, a skill imprime o **SQL pronto** (`pg_monitor`; `PROCESS`,
`REPLICATION CLIENT` e `SELECT` no catálogo) para o dono executar. A skill nunca executa DDL.
Usuário administrador funciona, mas gera achado de segurança: privilégio maior que a tarefa.

### http
Só GET, sem credencial, sem seguir redirect, com teto de bytes e tempo — o ponto de rede único que
já existe. Coleta código, tempo de resposta em faixa, e **validade do certificado**.

**Egress:** só host declarado no `alvos.toml` **e** confirmado na rodada.

## Relatório v2

```json
{ "schema_version": 2, "generated_at": "...",
  "alvos": [{"nome": "...", "tipo": "docker|postgres|mysql|http", "saude": "...",
             "dimensoes": {...}, "fatos": {...}, "achados": [...], "nao_coletado": [...]}],
  "inventario": [...], "aceites": [...], "historico": {...},
  "resumo": "", "fortes": [], "fracos": [],
  "recomendacoes": [{"alvo": "...", "titulo": "...", "porque": "...", "comando": "...",
                     "impacto": "alto|medio|baixo", "esforco": "alto|medio|baixo"}] }
```

**O que o script grava e o que o agente escreve.** O script preenche tudo menos quatro campos:
`resumo` (2-4 frases dizendo por que o veredito é esse), `fortes`, `fracos` e `recomendacoes` — cada
recomendação **amarrada a um alvo** e com `comando` pronto para rodar. Dentro de cada alvo, o agente
preenche só `analise` (o que aquele componente é e o que preocupa nele). **O agente não inventa
achado:** achado nasce de regra, e o que ele escreve é interpretação do que já está lá.

- **Abre pelo inventário** — o mapa do que existe e onde. É a resposta que não existe hoje.
- **Nota por alvo. Não existe nota única da infraestrutura**; o topo mostra a contagem de alvos por
  estado. Número único vira meta, e meta vira teatro.
- **Dimensões comuns** (operação, disponibilidade, segurança, higiene), com dois marcadores
  distintos: `n/a` quando a dimensão **não se aplica** àquele tipo, e `sem dados` quando se aplica
  mas **não foi coletada**. Confundir os dois é o jeito mais fácil de mentir num relatório.
- **Histórico** chaveado por `(alvo, regra, objeto)` — sem o alvo na chave, dois serviços homônimos
  em alvos diferentes colidem. Relatório v1 **não** é comparado com v2.
- **Layout:** `docs/infra/<AAAA-MM-DD_HHMM>/` por execução, uma pasta por rodada, com todos os
  alvos dentro. A execução anterior é a pasta irmã mais recente cujo `report.json` tenha
  `schema_version` 2 — o `docs/infra/<context>/` antigo fica onde está, é ignorado na comparação e
  não é apagado.

**Determinismo:** com as mesmas entradas, o mesmo relatório byte a byte. As entradas voláteis são
fixadas de fora: `generated_at` vem de `--at` (como hoje), o diretório de saída é parâmetro, e os
quatro campos do agente entram iguais. Ordem fixa: alvos na ordem declarada; achados por severidade,
alvo, regra e objeto. Valores voláteis — latência, bytes, duração — gravados em **faixas**. Sem
isso, o histórico vira ruído e nada é comparável.

## Aceites

Aplicados **depois** das regras: o achado nasce, é casado com o aceite, sai da nota e vai para a
seção própria com origem, motivo, `desde` e `revisar_em`. Nunca filtram a coleta — se o aceite
filtrasse, ninguém veria o risco mudar de tamanho.

- Aceite de **infra** (no `alvos.toml`) vale para todo projeto que usa aquele alvo.
- Aceite de **projeto** (no arquivo versionado) vale só ali e, havendo os dois, **vence** — o mais
  específico ganha, e o relatório registra a sobreposição.
- Vencido volta a contar como achado, com a observação de que a justificativa expirou.

## Erros e casos de borda

| Situação | Comportamento |
|---|---|
| Alvo não confirmado na rodada | Não é tocado, mas **entra em `alvos[]`** com saúde `sem dados` e o motivo — senão o inventário mentiria por omissão |
| Chave de conexão no arquivo do projeto | Para com erro de configuração, dizendo chave e arquivo |
| Cliente (`psql`/`mysql`) ausente | `nao_coletado`, nunca achado |
| Autenticação falha | `nao_coletado` com o motivo redigido |
| Permissão insuficiente | `nao_coletado` + SQL pronto para o dono criar o usuário |
| Consulta inexistente na versão | Conjunto por faixa evita; sobrando, `nao_coletado` |
| Alvo trava | Orçamento de tempo por alvo; o resto vira `nao_coletado` e o relatório sai |
| Sem `alvos.toml` | Oferece `migrar`, que escreve o primeiro a partir dos contexts docker |
| Pasta do relatório não ignorada | **Auditar só avisa**; quem escreve o `.gitignore` é o modo configurar (ou o primeiro `migrar`) |
| `alvos.toml` já existe | `migrar` **nunca** sobrescreve: mostra o que acrescentaria |
| Usuário administrador no banco | Funciona, com achado de segurança |

## Testes

Suíte pytest com fixtures (sem infraestrutura real): saída canônica de `psql`/`mysql` por versão,
`docker` fake pelo runner que já existe, e servidor HTTP local para o coletor http.

Cobrem: precedência das três camadas; recusa de chave de conexão na camada do projeto; gate de
confirmação; allowlist por `(motor, faixa)`; permissão negada virando `nao_coletado`; senha fora do
`ps` e do relatório, **sem nenhum arquivo além do efêmero com permissão 600** — que é apagado
inclusive quando o coletor falha (teste força a falha e confere a remoção); aceite casando, vencendo
e expirando; chave de histórico com alvo; determinismo com faixas.

## Restrições verificáveis (fitness functions)

1. **Auditar não escreve.** O modo auditar só altera `docs/infra/<execução>/` e o arquivo efêmero
   de credencial, que ele mesmo apaga. Teste tira retrato da árvore antes e depois; o modo
   configurar — único que escreve fora, incluindo o `.gitignore` — é testado à parte.
2. **Nenhum segredo sai.** Todo subprocesso passa por `lib/runner` — é o que torna isto testável
   sem inspecionar o sistema operacional. Fixture com senha em variável, em `.pgpass` e em arquivo de
   config: um espião no runner varre o `argv` de cada chamada, e o `report.json` e o HTML são
   varridos. O valor não pode aparecer em nenhum dos três.
3. **Egress só para alvo declarado e confirmado.** Vale para os três tipos; alvo não confirmado não
   gera conexão nenhuma — teste registra toda tentativa de socket.
4. **Mesmos fatos, mesmo relatório**, byte a byte; e **aceite vencido volta a contar**.

## Não-objetivos

- SSH e execução de comando em host remoto.
- Ler dado de aplicação, amostra de linha ou texto de query.
- Executar DDL, criar usuário, alterar configuração de qualquer alvo.
- Nota única da infraestrutura.
- Limiar de regra configurável por projeto.
- Alerta contínuo ou monitoramento em tempo real — isto é uma fotografia sob demanda.

## Restrição de simplicidade

A menor solução: o coletor docker continua como está, e os dois novos nascem pequenos. Se a
allowlist de um motor de banco crescer mais que o coletor docker inteiro, corta-se escopo de
checagem, não se inventa abstração.

## Ordem de execução: dois planos

O trabalho vai em **dois planos separados**, não em lotes de um plano só — o coletor de banco
concentra quase toda a matriz de teste (dois motores, versões, manejo de credencial), e o resto já
entrega valor sem ele.

**Plano 1 — o eixo.** Configuração em três camadas e `config --explicar` · gate `--confirmar` ·
`report.json` v2 com inventário, aceites e histórico · coletor docker (com métricas vindo do alvo) ·
coletor http · `migrar` · publicação da `sw-infra-audit` e remoção da `sw-cluster-audit`.
Ao fim dele a skill já responde "o que existe, onde, e o que vai quebrar" para docker e HTTP.

**Plano 2 — banco.** `lib/segredo.py` · coletor de Postgres e MySQL/MariaDB com allowlist por
`(motor, faixa)` · sonda de versão e de privilégio · entrega do SQL de criação do usuário ·
fixtures de `psql`/`mysql` por versão.

## Appetite · MVP vs MLP

**Appetite médio-grande** — é uma troca de eixo, não uma feature. **MVP:** os três tipos coletando,
relatório v2 com inventário e aceites, e a migração de nome fechada.

## Decisões (ADR)

**1. Alvo como objeto central, relatório único.**
Contexto: o dono precisa do inventário e de mostrar a situação a terceiros.
Decisão: `report.json` v2 com lista de alvos; docker vira um coletor.
Alternativas: um relatório por alvo (perde a visão e o mapa); núcleo genérico plugável (caro, e
arrisca regras de docker já calibradas).
Consequência: o schema muda, e o histórico v1 não é comparável.

**2. Conexão só na camada de infra.**
Contexto: o arquivo do projeto é versionado e chega por clone ou pull request.
Decisão: host, porta, usuário e credencial só existem no `alvos.toml`; chave dessas no arquivo do
projeto é erro.
Alternativa: precedência simples de três camadas (abre redirecionamento de credencial).
Consequência: o projeto escolhe alvos, nunca os define.

**3. Confirmação por execução, com menu de todos os alvos.**
Contexto: o gate de hoje (`--confirmed-context`) se perderia; agora há banco de produção na mesa.
Decisão: `--confirmar <nomes>`, e o script recusa alvo fora da lista.
Consequência: uma pergunta a mais por rodada, em troca de nunca conectar sem alguém dizer sim.

**4. Aceite depois das regras, com data de revisão.**
Contexto: achado repetido que já foi decidido faz o leitor abandonar o relatório.
Decisão: marca e separa, nunca filtra a coleta; vencido volta.
Alternativa: filtrar na coleta (esconde a mudança de tamanho do risco).
Consequência: o relatório carrega a lista de aceites, e ela precisa ser mantida.

**5. Credencial nunca em linha de comando.**
Contexto: `-p<senha>` aparece no `ps` para qualquer usuário da máquina.
Decisão: arquivo efêmero 600 no MySQL; `PGPASSFILE`/env do subprocesso no Postgres.
Consequência: um arquivo temporário a limpar, inclusive em falha.

**6. Falta de acesso é "sem dados", não achado.**
Contexto: hoje erro de acesso vira achado grave.
Decisão: `nao_coletado` com motivo; dimensão fica sem nota.
Consequência: relatório com buracos explícitos em vez de veredito falso.

## Migração e publicação

1. Implementar em `~/.claude/skills/sw-infra-audit/`, reaproveitando o que já existe da
   `sw-cluster-audit` (runner, redator, regras de docker, template do relatório).
2. `migrar`: escreve o primeiro `alvos.toml` a partir dos contexts docker; nunca sobrescreve.
3. Validar em infraestrutura real: primeiro docker (comparando com a auditoria v1), depois um banco
   com usuário de leitura, depois um endpoint. Nada de host, IP, usuário ou projeto real no dossiê.
4. Publicar `sw-infra-audit` (`make sync SKILL=sw-infra-audit CATEGORY=development`) e remover a
   antiga com `make remove SKILL=sw-cluster-audit`, com nota no CHANGELOG apontando a substituta.
5. `sw-code-review` e `sw-plan` não mudam; quem cita a skill antiga passa a citar a nova.

## Suposições a testar

- **A allowlist por faixa de versão cobre o parque real** do dono (Postgres e MySQL/MariaDB em uso).
- **O menu de confirmação a cada rodada não vira incômodo** a ponto de o dono querer pular.
- **`docs/infra/` continua o lugar certo** agora que o conteúdo não é só do cluster.
