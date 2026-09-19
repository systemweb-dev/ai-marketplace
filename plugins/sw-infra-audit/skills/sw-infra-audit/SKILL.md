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

## Antes de tudo

```bash
python3 <skill-dir>/scripts/configurar.py config --explicar
```

Mostra a configuração efetiva e **de onde veio cada valor** — são três camadas: `default.toml`
(padrões da skill) < `docs/infra/alvos.toml` (os alvos deste projeto, na mesma pasta do
relatório, que fica fora do git) < `.sw-infra-audit.toml` (na raiz do projeto, versionado).

**O `alvos.toml` mora dentro do projeto e fora do versionamento.** A skill confere com
`git check-ignore` antes de ler ou escrever: se a pasta não estiver no `.gitignore`, ela
**recusa** — arquivo de conexão versionado é conexão publicada. Se `relatorio.pasta` mudar, os
alvos acompanham (duas pastas seriam duas verdades).

**O arquivo versionado nunca define conexão.** Ele só escolhe quais alvos entram, ajusta
severidade e registra aceites. Host, porta, usuário e credencial vivem só no `alvos.toml` — se o
`.sw-infra-audit.toml` trouxer uma dessas chaves, a auditoria para e diz qual.

Sem `alvos.toml`, ofereça `configurar.py migrar`: ele cria a pasta, garante a linha no
`.gitignore` e escreve o primeiro arquivo — trazendo o conteúdo do antigo
`~/.config/sw-infra-audit/alvos.toml` quando ele existir, ou partindo dos seus contexts docker.
**Nunca sobrescreve** um existente.

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
python3 <skill-dir>/scripts/build_report.py --dir docs/infra/<AAAA-MM-DD_HHMM>
```

Gera `relatorio.html` (sempre) e `relatorio.pdf` (se houver Chromium). O HTML abre pelo
**inventário** — é ele que responde "o que eu tenho e onde".

### 6. Informar

Caminho do relatório · quantos alvos em cada estado (**não invente uma nota única da infra**) ·
achados por gravidade · o que ficou `sem dados` e por quê · riscos aceitos, com os vencidos em
destaque · e o que mudou desde a auditoria anterior.

## Riscos aceitos

Achado que o usuário já decidiu aceitar não deve voltar a cada auditoria — é assim que um
relatório perde credibilidade. Ofereça registrar:

```bash
python3 <skill-dir>/scripts/configurar.py aceitar --alvo <nome> --regra <regra> \
  --motivo "por que isso é aceitável" --meses 6
```

- O aceite **não filtra a coleta**: o achado nasce, é marcado, sai da nota e vai para a seção
  própria, com origem, motivo e data de revisão.
- **Vencido volta a contar**, com a observação de que a justificativa expirou.
- Aceite no `alvos.toml` vale para todos os alvos daquele arquivo; o do `.sw-infra-audit.toml`
  (versionado, revisado em PR) vence quando os dois existem.
- **Exija motivo.** Aceite sem justificativa é achado escondido.

## Modo configurar

| Comando | Para quê |
|---|---|
| `config --explicar` | Ver a configuração efetiva e a origem de cada chave |
| `migrar` | Criar o primeiro `alvos.toml` em `docs/infra/`, já ignorado pelo git |
| `alvos --sugerir --context <ctx>` | Propor uma `metricas_url` (só propõe; não alcança host) |
| `aceitar` | Registrar um risco aceito no arquivo do projeto |
| `ignorar` | Pôr a pasta do relatório no `.gitignore` |

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
