---
titulo: sw-refactor: refatoração pelos padrões do projeto
slug: 2026-11-03-sw-refactor-refatoracao-pelos-padroes-do-projeto
criado: 2026-11-03
estado: concluido
---

# sw-refactor: refatoração pelos padrões do projeto

> Skill nova, em `~/.claude/skills/sw-refactor/`, publicada com `make sync`. Caminhos de skills
> vizinhas são relativos à raiz deste repositório.

## Objetivo & outcome

O mesmo problema aparece resolvido de vários jeitos no projeto: código inconsistente, herdado,
gerado por IA e com complexidade local, as quatro dores. [usuário] Nenhuma skill descobre o padrão no
próprio código e alinha o resto a ele sem mudar comportamento. A `sw-code-review` olha só o diff e
aplica só regra escrita [visto: plugins/sw-code-review/skills/sw-code-review/SKILL.md:39].

**Outcome de uma rodada** [usuário]:
1. testes verdes antes e depois de cada etapa;
2. nova varredura no escopo sem desvio nos itens aprovados; os pulados ou recusados vão para os
   desvios pendentes do `state.md`;
3. a skill **pergunta** se grava o padrão como regra do projeto.

Genérica para qualquer linguagem e framework. Toda decisão ao usuário é via `AskUserQuestion`. [usuário]

## Não-objetivos

- Revisar diff, remover código morto e escrever teste de propósito geral: são da `sw-code-review`,
  da `sw-dead-code-scan` e da `sw-auto-test`, que a skill **oferece** no momento certo, sem fazer.
- Migrar versão de framework, mudar arquitetura (monólito para serviços) e formatação (espaço, ordem
  de import, quebra de linha), que é trabalho do formatter.
- Commit e push.
- Script de medição, cache e banco de padrões entre projetos. [usuário]

## Exploração & decisões

- **Problema:** padrão do projeto não é descoberto nem aplicado; o que existe revisa diff.
- **Ângulos:** modo dentro da `sw-code-review` (descartado: escopo diff, 1.456 linhas, dois
  gatilhos); maioria vence ou idiomático vence (descartados: o usuário decide conflito); script
  determinístico `scan.py` (descartado pelo usuário: "IA sempre, com subagentes").
- **Suposições:** regra escrita vence sempre (confirmada); decidir sozinho em conflito ou em trecho
  sem teste (derrubada: vira pergunta).
- **Direção:** subagentes descobrem com evidência, o usuário decide conflitos, a refatoração vai em
  etapas com prova por teste, e o padrão aprovado vira arquivo que outras skills leem.

## Design

### Fluxo de uma rodada

1. **Entrada.** Lê `docs/sw-refactor/state.md` do projeto.
   - Sem ele: **primeira rodada, projeto inteiro**. [usuário]
   - Com ele: pergunta o escopo (projeto, diretório ou arquivos) e mostra o que mudou desde o commit
     registrado. Padrões já decididos não são perguntados de novo.
   - Árvore suja: avisa e pergunta se segue. Arquivo que o usuário já tinha alterado só entra numa
     etapa com pergunta.
2. **Fontes, por autoridade:** regra escrita (`.claude/rules/`, `CONTRIBUTING`, `.editorconfig`,
   `AGENTS.md`, `CLAUDE.md`, `docs/sw-refactor/patterns.md`) > configuração de linter e formatter >
   o que o código faz. Regra escrita vence sem perguntar. [usuário]
3. **Mapa rápido** (agente principal): linguagens, frameworks e versões pelos manifestos; camadas
   pelas pastas; regras escritas. Define a divisão dos subagentes.
4. **Descoberta por subagentes**, em paralelo, até 10 por rodada; passar disso mostra quantos e por
   quê e pergunta. [usuário] Projeto pequeno usa um subagente por grupo; grande divide cada grupo por
   camada ou módulo.

   | Grupo | Dimensões |
   |---|---|
   | a. Nomes e layout | caixa de função, classe, constante e arquivo; sufixos e pastas; onde ficam os testes |
   | b. Erros e validação | como o erro é lançado e capturado; em que camada a entrada é validada |
   | c. Dados e camadas | ORM, repository ou query solta; quem chama quem; lógica fora da camada |
   | d. Resposta, log e config | formato de resposta e de log; env direto ou objeto de config; estilo de import |
   | e. Complexidade e duplicação | função longa, aninhamento, trecho repetido entre arquivos |

   **Contrato do subagente** (prompts em `references/subagente-descoberta.md`): por dimensão, as
   variantes, quantos arquivos leu, quantos seguem cada variante e **3 exemplos `arquivo:linha` por
   variante**; o que não conseguiu ler e por quê; não edita nada; ignora formatação.
5. **Verificação** (agente principal): confere com grep e leitura cada exemplo citado. Exemplo que
   não confere derruba a variante. Subagente sem resposta deixa a dimensão "não medida".
6. **Decisão por dimensão:**
   - ≥80% numa variante: candidato; o usuário confirma em lote.
   - <80%: conflito; um segundo subagente reconta só essa dimensão; depois pergunta (ver
     Revisões do spec).
   - Pergunta de conflito mostra contagem, dois exemplos reais e o idiomático do framework. [usuário]
   - Sem padrão nenhum: propõe o idiomático da linguagem e versão (ver Idiomático).
   - Limites de complexidade partem da 5l da `sw-code-review` (função >40 linhas, aninhamento >3)
     [visto: plugins/sw-code-review/skills/sw-code-review/references/patterns.md:435] e se ajustam ao
     que o projeto pratica: o limite é o percentil 80 do projeto, quando maior que o da 5l. Se 80% das
     funções têm até 60 linhas, o limite vira 60.
7. **Relatório de desvios** no chat, por padrão, com `arquivo:linha`. Desvio que muda o que alguém
   fora do código vê (rota, chave de JSON, status HTTP, mensagem, coluna, nome chamado por
   reflexão; símbolo só chamado dentro do projeto não conta) vem marcado
   **muda contrato**, com quem consome, e só entra se o usuário aprovar aquele item. [usuário] O
   usuário escolhe o que entra.
8. **Refatoração em etapas**, uma por padrão ou módulo:
   1. copia os arquivos da etapa para a pasta temporária da sessão, ou para uma criada com
      `mktemp -d` quando o ambiente não oferecer uma (ponto de restauração);
   2. roda os testes do trecho. Falha **antes** de mexer: a etapa não começa; pergunta pular, seguir
      sem prova (marcado no `state.md`) ou parar;
   3. sem teste: pergunta a cada caso [usuário], com as opções pular, seguir sem prova ou criar teste
      de caracterização pela `sw-auto-test`;
   4. aplica: ferramenta da linguagem quando já instalada (`references/refatoracoes-seguras.md`),
      senão o agente edita; nunca instala nada sem perguntar [usuário]. Projeto grande pode usar um
      subagente por etapa, e o principal confere o diff;
   5. roda os testes de novo. Falhou: restaura **só a cópia da etapa** (nunca `git checkout`), mostra
      o erro e pergunta tentar diferente, pular ou parar. Três falhas seguidas param a rodada.
9. **Fechamento:** nova varredura no escopo; oferece `sw-code-review` no diff e `sw-git-commit` com uma
   etapa por commit; grava `state.md` e `patterns.md`; oferece a linha no `AGENTS.md`/`CLAUDE.md`.

### Idiomático

`references/idiomatico.md` traz um resumo curto por linguagem e framework. Com busca na web na
sessão, a skill confere a documentação oficial da versão do manifesto antes de propor e cita a
fonte; sem web, usa o arquivo e marca "não conferido". [usuário]

### Arquivos gravados no projeto (só com aprovação, no fim)

Layout aprovado [usuário]; nomes e cabeçalhos em inglês, texto no idioma do projeto.

```
docs/sw-refactor/
  patterns.md   ← um bloco por padrão: Rule, Decided by (regra/dono/maioria + data), Evidence, Correct, Wrong
  state.md      ← commit-base, commit final (se houve), data, escopo, arquivos tocados,
                  padrões tratados, desvios pendentes, etapas "sem prova"
AGENTS.md       ← seção "Code patterns" apontando para patterns.md e state.md
CLAUDE.md       ← a mesma seção
                  (AGENTS.md ou CLAUDE.md inexistente: pergunta se cria cada um)
```

**Commit no `state.md`:** registra o commit-base e os arquivos tocados. Se o usuário commitar pela
`sw-git-commit`, registra o HEAD novo; se não, marca "refatoração não commitada" e a próxima rodada
não conta esses arquivos como mudança nova. Commit registrado que não existe mais (rebase, outro
clone): trata como primeira rodada e mantém os padrões decididos. O relatório de desvios não vira
arquivo.

### Arquivos da skill

- `SKILL.md`: fluxo, regras de pergunta, contrato dos subagentes, ofertas às outras skills.
- `references/subagente-descoberta.md`: prompt de cada grupo (a a e) e do recontador.
- `references/idiomatico.md`: base por linguagem e framework.
- `references/refatoracoes-seguras.md`: mudanças mecânicas por ferramenta (Rector, ruff `--fix`,
  ESLint `--fix`, gopls rename), usadas só quando já instaladas.

### Integração com outras skills

Oferecidas por menu, nunca automáticas; sem a skill instalada, avisa e segue. [usuário]

| Momento | Skill | Pedido |
|---|---|---|
| 1ª rodada, se a descoberta achar código sem uso | `sw-dead-code-scan` | limpar antes, para não refatorar código morto |
| Trecho sem teste, se o usuário escolher criar | `sw-auto-test` | pedido explícito: "fixe o comportamento atual, inclusive o estranho; não corrija bug" |
| Fim da rodada | `sw-code-review` | revisar o diff da refatoração |
| Fim da rodada | `sw-git-commit` | uma etapa por commit |

A `sw-auto-test` não tem modo de caracterização: o único "golden" é uma linha sobre snapshot
[visto: plugins/sw-auto-test/skills/sw-auto-test/references/generation.md:83]. Por isso o pedido vai
explícito, e a `sw-auto-test` não muda.

**Mudança na `sw-code-review`** (bump patch): incluir `docs/sw-refactor/patterns.md` na busca do
Step 0, que hoje lê `.claude/rules/`, `CONTRIBUTING.md`, `STYLE.md` e `.editorconfig` e não lê o
`AGENTS.md` da raiz [visto: plugins/sw-code-review/skills/sw-code-review/SKILL.md:49]; e sugerir a
`sw-refactor` quando um achado 5l ou 5m se repetir em 3 ou mais arquivos
[visto: plugins/sw-code-review/skills/sw-code-review/references/patterns.md:441].

### Testes da skill

Sem script, então sem pytest. Validação pela `sw-skill-test`, que roda a skill sobre um fixture e
pula etapas interativas
[visto: plugins/sw-skill-test/skills/sw-skill-test/SKILL.md:64]. Por isso o artefato verificável
inclui a **lista de perguntas que seriam feitas**.

Fixture em Python e PHP (runtimes presentes na máquina [visto: /usr/bin/php] [visto: /usr/bin/python3]),
com um padrão dominante, um conflito 55/45, código fora do padrão, um desvio que muda contrato, uma
armadilha (diferença intencional escrita em `.claude/rules`), um trecho sem teste e uma etapa que
quebra um teste de propósito, de forma determinística. Passa quando acha os desvios do gabarito,
pergunta no conflito, no item de contrato e no trecho sem teste, respeita a armadilha, restaura só os
arquivos da etapa que falhou e os demais testes do fixture seguem verdes.

## Decisões

| Contexto | Decisão | Alternativas descartadas | Consequências |
|---|---|---|---|
| Refatorar é escopo de projeto; review é de diff | skill nova `sw-refactor` [usuário] | modo da `sw-code-review` | duas skills pequenas; a review sugere a refactor |
| Como descobrir o padrão | subagentes com exemplos conferidos [usuário] | script `scan.py`; só o agente principal | contagem pode variar; mitigada por verificação e recontagem |
| Conflito entre padrões | pergunta com evidência [usuário] | maioria vence; idiomático vence | mais perguntas na 1ª rodada; nenhuma depois |
| Trecho sem teste | pergunta a cada caso [usuário] | criar teste sempre; só mudança mecânica | rodada mais lenta, sem surpresa |
| Desfazer etapa | cópia dos arquivos antes de editar | `git checkout` | não destrói etapa anterior nem mudança do usuário |
| Contrato externo | só com pergunta explícita por item [usuário] | fora de escopo; tratar como o resto | testes verdes não bastam para o que sai do processo |
| Registro entre rodadas | `docs/sw-refactor/` + seção no `AGENTS.md`/`CLAUDE.md` [usuário] | histórico no `AGENTS.md`; pasta fora do git | o time recebe o padrão; o `AGENTS.md` só aponta |
| Outras skills | ofertas por menu [usuário] | disparo automático | a skill fica menor e não duplica trabalho |

## Restrições verificáveis

- O `SKILL.md` da `sw-refactor` não referencia nenhum script: `grep -E "scripts/|python3 " SKILL.md` vazio.
- Nenhuma edição sem ponto de restauração: o passo de cópia aparece antes de toda instrução de
  edição no `SKILL.md`, e o teste da `sw-skill-test` confere que uma etapa falha restaura os
  arquivos sem tocar nos de outra etapa.
- No fixture, 100% dos desvios do gabarito são apontados, 0 edições na armadilha e 0 itens "muda
  contrato" aplicados sem pergunta.
- O repositório público não recebe nome real de projeto nem caminho do home: `make check` passa.

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| Subagentes contam variantes de forma estável o bastante para decidir conflito | o usuário decide sobre números inventados; a skill perde a confiança | spike: rodar a descoberta duas vezes no fixture e comparar contagens e exemplos |
| A `sw-auto-test` escreve teste de caracterização com o pedido explícito | trecho sem teste fica sem caminho seguro | spike: pedir a caracterização de uma função com comportamento estranho no fixture |
| A pasta temporária da sessão está sempre disponível para o ponto de restauração | desfazer etapa não funciona | conferir no teste de etapa falha do fixture |

## Appetite e MVP

Médio: uma skill sem script, com três references e uma mudança pequena na `sw-code-review`. MVP:
validar que descoberta e etapas funcionam no fixture antes de polir o `idiomatico.md`, que começa
com as linguagens do fixture e cresce depois.

## Rollout

Skill nova, publicada por `make sync` com versão 0.1.0; a `sw-code-review` sobe patch. Volta é
remover o plugin. Não toca dados.

## Revisões do spec

- **2026-11-03** — spike da contagem (`referencias/spike-contagem.md`): a unidade de contagem
  variava entre rodadas e "muda contrato" pegava símbolo interno. Decisão do dono: a unidade é o
  arquivo onde a decisão é tomada (auxiliar, arquivo que só captura e arquivo de teste não contam),
  "muda contrato" é só o que alguém fora do código vê, e toda dimensão abaixo de 80% é recontada
  antes de perguntar (antes: 70% a 79% perguntava direto).
- **2026-11-03** — validação (`referencias/validacao-skill-test.md`): dimensão "abstração sem uso
  real" no grupo e; etapas separadas por cobertura de teste; o auxiliar que a etapa deixou sem uso
  é removido nela, antes do teste final; o ponto de restauração usa `tar` com caminhos relativos à
  raiz, porque `cp --parents` com caminho absoluto não restaurava e não existe no macOS.
