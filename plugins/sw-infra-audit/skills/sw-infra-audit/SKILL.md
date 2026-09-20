---
name: sw-infra-audit
description: >-
  Audita a infraestrutura de forma READ-ONLY e gera um relatório técnico (HTML + PDF opcional)
  com inventário, achados por gravidade e riscos aceitos. Trabalha por ALVOS: cluster Docker
  (context/Swarm) e endpoint HTTP (saúde + validade do certificado). Use SEMPRE que o usuário
  quiser um raio-x da infra ou de parte dela — "audita minha infra", "como está o cluster",
  "o que pode cair primeiro", "relatório da infraestrutura", "esse certificado vence quando?",
  "a API está no ar?", "o que eu tenho rodando e onde", "saúde do swarm", "como o traefik está
  roteando". Dispare mesmo sem a palavra "auditar" — basta a intenção de entender o ESTADO
  ATUAL da infraestrutura. É SÓ LEITURA: nunca altera, reinicia, escala nem cria nada; nunca
  expõe valor de secret, senha ou string de conexão; só fala com alvo que você declarou e
  confirmou na rodada. NÃO use para deploy, para mexer em serviço/stack, nem para código de
  aplicação. Substitui a sw-cluster-audit. Interação e relatório em português (PT-BR).
---

# Infra Audit — raio-x read-only por alvos

Tira uma **fotografia técnica** do que você tem rodando — cluster Docker, endpoint HTTP — e gera
um relatório em `docs/infra/<data_hora>/`. **Os fatos vêm de comandos read-only e regras
determinísticas; a interpretação é sua (agente).**

**Anuncie no início:** "Estou usando a skill sw-infra-audit para auditar a infraestrutura."

## Regra: toda decisão é via AskUserQuestion

**Toda pergunta ao usuário usa `AskUserQuestion` (menu clicável) — nunca pergunta em texto
solto, e nunca termine um turno com pergunta escrita.** Numa auditoria isso não é preferência
de interface: quem responde está decidindo **em que máquina de produção você vai tocar**, e
opção clicável com o alvo escrito por extenso erra menos que texto livre.

Vale em todos os pontos de decisão desta skill:

| Momento | O que perguntar |
|---|---|
| **Confirmar os alvos** (obrigatório, antes de qualquer conexão) | quais alvos entram nesta rodada, com nome, tipo e **onde** |
| Sem `alvos.toml` | criar o primeiro com `configurar.py migrar`? |
| Pasta do relatório fora do `.gitignore` | acertar agora com `configurar.py ignorar`? |
| **Componente calado** (passo 3b, antes de interpretar) | declarar `metricas_url` agora, para o relatório sair com medida em vez de rótulo? |
| Achado que o dono já conhece | registrar como risco aceito, com motivo e prazo? |
| Aceite vencido no relatório | renovar, deixar vencer ou resolver o achado? |
| **No fim** | gerar o PDF também? |

Para resposta aberta (um motivo de aceite, um endereço), ofereça as opções prováveis e conte
com o campo **"Other"**. A exceção é o usuário descrevendo livremente o que quer — aí ele está
dirigindo, e forçar menu atrapalha.

**Nunca pergunte o que dá para descobrir sozinho.** Qual é o context, quantos nós tem, se há
exporter respondendo: isso a skill lê. Pergunta serve para **decisão e autorização**, não para
suprir leitura que você não fez.

## Garantias inegociáveis

- **Nada é alterado.** Só comandos de leitura, por allowlist. Nunca `rm/kill/restart/exec/create/
  update/scale/prune`, `logs`, `cp`, `secret inspect`.
- **Nenhum segredo sai.** O relatório mostra **nomes** de secrets e **chaves** de env, nunca
  valores, nunca string de conexão. A senha de um alvo nunca é gravada em lugar nenhum.
- **Egress fechado.** Só se fala com host declarado no `alvos.toml` **e** confirmado na rodada.
- **Não consegui ver ≠ está ruim.** Falha de acesso vira `nao_coletado` com motivo, nunca achado,
  e a dimensão fica sem nota.
- **Auditar não escreve** fora da pasta da execução. Quem escreve configuração é o modo
  configurar, e só com aprovação.
- **Comando de remediação é para EXIBIR, nunca para executar.** O relatório traz o passo a
  passo e o comando pronto; quem decide aplicar é o dono, depois de ler o "quando não fazer".
  Você não executa nada do catálogo de remediação — nem quando parecer óbvio.
- **Número sem fonte não existe.** Todo insight carrega o adaptador que respondeu; o que não
  foi respondido aparece com o motivo, nunca como zero.

## Antes de tudo

```bash
python3 <skill-dir>/scripts/configurar.py config --explicar
```

Mostra a configuração efetiva e **de onde veio cada valor** — são três camadas: `default.toml`
(padrões da skill) < `docs/infra/alvos.toml` (os alvos deste projeto, na mesma pasta do
relatório, que fica fora do git) < `docs/infra/config.toml` (do projeto, **versionado**).

**Tudo da skill vive em `docs/infra/`** — alvos, configuração do projeto e os relatórios de
cada rodada. O `.gitignore` esconde o conteúdo da pasta e **reabre só o `config.toml`**:

```gitignore
docs/infra/*
!docs/infra/config.toml
```

A forma antiga (`docs/infra/`) ignora o diretório inteiro e nenhuma negação resgata um arquivo
lá dentro — por isso `configurar.py ignorar` **substitui** essa linha quando a encontra.

A skill confere com `git check-ignore` antes de ler ou escrever o `alvos.toml`: pasta fora do
`.gitignore`, ela **recusa** — arquivo de conexão versionado é conexão publicada. Se
`relatorio.pasta` mudar, alvos e relatórios acompanham (duas pastas seriam duas verdades); o
`config.toml` é o ponto de entrada e por isso o caminho dele é fixo.

**O arquivo versionado nunca define conexão.** Ele só escolhe quais alvos entram, ajusta
severidade e registra aceites. Host, porta, usuário e credencial vivem só no `alvos.toml` — se o
`config.toml` trouxer uma dessas chaves, a auditoria para e diz qual.

Sem `alvos.toml`, **pergunte via `AskUserQuestion`** se cria o primeiro com
`configurar.py migrar`: ele cria a pasta, garante a linha no
`.gitignore` e escreve o primeiro arquivo — trazendo o conteúdo do antigo
`~/.config/sw-infra-audit/alvos.toml` quando ele existir, ou partindo dos seus contexts docker.
**Nunca sobrescreve** um existente.

## Insights por sistema

Cada componente do alvo (um serviço do swarm, um endpoint) recebe um **papel** — `entrada`,
`fila`, `banco`, `cache`, `busca`, `storage`, `observabilidade`, `app` — derivado da imagem e
sobrescrevível no `alvos.toml`. O papel define as **perguntas** que ele recebe; um **adaptador**
responde o que souber e carimba a **fonte**.

| Adaptador | Fala com | Estado |
|---|---|---|
| `promql` | Prometheus ou exporter declarado em `metricas_url` | funciona |
| `admin_http` | API de administração do componente (filas, índices) | próximo ciclo |
| `sql` | Postgres/MySQL por cliente de linha de comando | próximo ciclo |
| `logql` | agregador de log, só consulta agregada | próximo ciclo |

O conhecimento de cada família de exporter vive em `references/metricas/<familia>.toml` —
identificação pela **série que existe** (não pelo nome da imagem, que mente com fork e tag
genérica), etiqueta de seletor e uma consulta por pergunta. Acrescentar um produto é escrever
um arquivo; nenhum `if produto ==` no código.

Declare o componente quando quiser corrigir o papel ou apontar a fonte:

```toml
[[alvo.componente]]
nome = "traefik"
papel = "entrada"
metricas_url = "http://prometheus.interno:9090"
# senha_env = "SENHA_DA_FILA"   # o NOME da variável; o valor nunca fica no arquivo
```

A janela é 24 h por padrão (`[insights] janela` no `config.toml`) e é **ancorada no `--at`** —
duas execuções com o mesmo carimbo dão o mesmo número.

## Como resolver cada achado

Todo achado chega ao relatório com quatro blocos vindos de `references/remediacao/<regra>.md`:
**por que importa · como resolver (passos e comando) · como confirmar que resolveu · quando NÃO
fazer**. Você pode enriquecer a análise por cima; não reescreva o catálogo na hora — ele é
versionado e revisado em pull request, justamente para não variar a cada rodada.

Regra marcada como **esperada** (o proxy que monta o `docker.sock` porque é assim que ele
funciona, o job de migração concluído) não pede remediação: ela descreve o normal.

## Fluxo do modo auditar

### 1. Escopo e configuração

Leia a configuração efetiva e a lista de alvos. Se o projeto não escolheu nenhum (`alvos = []`),
todos os declarados entram.

### 2. Confirmação — obrigatória, e antes de qualquer conexão

Mostre via `AskUserQuestion` **todos** os alvos da rodada, com **nome, tipo e onde**, e peça a
confirmação. Alvo não confirmado **não é tocado** — mas ainda aparece no relatório como
`sem dados`, para o inventário não mentir por omissão.

Alvo de produção merece atenção redobrada na pergunta: diga o que será executado nele.

### 3. Coletar

```bash
python3 <skill-dir>/scripts/collect.py --out docs/infra/<AAAA-MM-DD_HHMM> \
  --at <ISO> --confirmar <nomes confirmados>
```

- **Exit 0** → imprime o caminho do `report.json` e uma linha por alvo com saúde e tipo.
- **Exit 2** → mostre a mensagem e **pare**: configuração inválida, nenhum alvo confirmado,
  `--confirmar` citando alvo fora da auditoria, ou `--at` fora do formato.

O `--at` é o carimbo da execução e **decide qual aceite venceu** — use a data real, em ISO.

### 3b. O relatório vai ter o que dizer? (antes de interpretar)

Coletar sem erro **não** quer dizer que a auditoria respondeu alguma coisa. Numa rodada real,
57 componentes entraram no inventário e nenhum respondeu pergunta nenhuma: os que tinham
pergunta não achavam `metricas_url` declarado, e o resto tinha papel sem pergunta registrada.
O `collect.py` terminou com exit 0, e o relatório saiu com nome, papel e silêncio.

Antes de escrever a interpretação, rode:

```bash
python3 <skill-dir>/scripts/pendencias.py --dir docs/infra/<AAAA-MM-DD_HHMM>
```

Ele lista o que está calado e por quê. Então, **via `AskUserQuestion`**:

- **Componente sem `metricas_url`** e existe Prometheus no alvo → ofereça rodar
  `alvos.py --sugerir` e declarar o endereço **antes** de seguir. Uma linha no `alvos.toml`
  costuma ser a diferença entre um relatório com medidas e um relatório com rótulos.
- **Papel sem pergunta nesta versão** → isso é limite da skill, não configuração. Diga qual
  papel, não ofereça conserto que não existe, e siga.

**Nunca entregue um relatório mudo sem ter perguntado.** Quem recebe não distingue "não há o
que medir" de "ninguém apontou a skill para a fonte" — e conclui que a auditoria não funciona.

### 4. Interpretar (é a sua parte)

Leia o `report.json` inteiro e escreva **por cima** dele, sem inventar achado — achado nasce de
regra:

| Campo | O que escrever |
|---|---|
| `resumo` | 2 a 4 frases dizendo **por que** o veredito é esse |
| `fortes` / `fracos` | o que está bom e o que preocupa, em lista |
| `recomendacoes` | `{alvo, titulo, porque, comando, impacto, esforco}` — **com o comando pronto** |
| `alvos[].analise` | o que aquele componente é e o que preocupa nele |

Use `dimensoes`, `fatos` e `achados` de cada alvo. O que estiver em `nao_coletado` **precisa
aparecer no resumo**: relatório com buraco explícito é honesto; relatório que cala é mentira.

### 5. Relatório

```bash
python3 <skill-dir>/scripts/build_report.py --dir docs/infra/<AAAA-MM-DD_HHMM> --formato html
```

Gera `relatorio.html`. O sumário no topo é **clicável também no PDF** — o Chromium converte as
âncoras em link com destino de página —, então quem receber o arquivo navega sem rolar.

### 6. Informar

Caminho do relatório · quantos alvos em cada estado (**não invente uma nota única da infra**) ·
achados por gravidade · o que ficou `sem dados` e por quê · riscos aceitos, com os vencidos em
destaque · e o que mudou desde a auditoria anterior.

### 7. Ofereça o PDF — no fim, não antes

**`AskUserQuestion`**: "Gerar o PDF também?" Só então rode com `--formato html+pdf`. O PDF custa
alguns segundos de Chromium e nem toda rodada vira documento para enviar; perguntar no começo
gasta a atenção de quem só queria ver o estado da infra.

```bash
python3 <skill-dir>/scripts/build_report.py --dir docs/infra/<AAAA-MM-DD_HHMM> --formato html+pdf
```

Sem Chromium na máquina, diga isso e entregue o HTML — não é falha da auditoria.

## Riscos aceitos

Achado que o usuário já decidiu aceitar não deve voltar a cada auditoria — é assim que um
relatório perde credibilidade. **Ofereça via `AskUserQuestion`** registrar — e, se houver
aceite vencido na rodada, pergunte o que fazer com ele (renovar, deixar vencer, resolver):

```bash
python3 <skill-dir>/scripts/configurar.py aceitar --alvo <nome> --regra <regra> \
  --motivo "por que isso é aceitável" --meses 6
```

- O aceite **não filtra a coleta**: o achado nasce, é marcado, sai da nota e vai para a seção
  própria, com origem, motivo e data de revisão.
- **Vencido volta a contar**, com a observação de que a justificativa expirou.
- Aceite no `alvos.toml` vale para todos os alvos daquele arquivo; o do `config.toml`
  (versionado, revisado em PR) vence quando os dois existem.
- **Exija motivo.** Aceite sem justificativa é achado escondido.

## Modo configurar

| Comando | Para quê |
|---|---|
| `config --explicar` | Ver a configuração efetiva e a origem de cada chave |
| `migrar` | Criar o primeiro `alvos.toml` em `docs/infra/`, já ignorado pelo git |
| `alvos --sugerir --context <ctx>` | Propor uma `metricas_url` (só propõe; não alcança host) |
| `aceitar` | Registrar um risco aceito no `config.toml` do projeto |
| `ignorar` | Acertar o `.gitignore`: esconde a pasta, mantém o `config.toml` |

É o único que escreve fora da pasta do relatório, e nunca sobrescreve `alvos.toml` existente.

## Como a saúde é calculada

**Saúde é operação, não higiene.** Um cluster que está rodando não vira crítico porque tem
imagem sem digest. Por alvo: 🔴 algo fora do ar · 🟡 rodando com risco conhecido · 🟢 convergido
· `sem dados` quando não foi coletado. **Não existe nota única da infraestrutura** — o topo mostra
a contagem por estado. Número único vira meta, e meta vira teatro.

## Limites

- **Banco de dados ainda não** — Postgres e MySQL são o próximo ciclo. Alvo desse tipo no
  `alvos.toml` é recusado com mensagem clara.
- **SSH não** — auditar host por comando remoto é outra superfície, e fica para depois.
- **Não é monitoramento.** É fotografia sob demanda, não alerta contínuo.
- **Porta em 0.0.0.0** significa publicada em todas as interfaces, **não** alcançável da internet:
  firewall e security group são invisíveis daqui.
- **Métricas de runtime** só existem se o alvo declarar `metricas_url`.

## Referências

- [`references/what-to-collect.md`](references/what-to-collect.md) — o que a coleta traz de cada alvo
- [`references/finding-rules.md`](references/finding-rules.md) — as regras que geram achado
- [`references/commands-allowlist.md`](references/commands-allowlist.md) — a allowlist de comandos
- [`references/tls-renewal.md`](references/tls-renewal.md) — o que dizer ao recomendar renovação de certificado
