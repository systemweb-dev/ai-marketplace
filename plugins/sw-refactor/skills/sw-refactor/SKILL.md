---
name: sw-refactor
description: >
  Refatora seguindo os padrões do PRÓPRIO projeto: descobre como o código costuma resolver cada
  coisa (nomes, erros, validação, camadas, resposta, config, complexidade), aponta o que está
  fora do padrão e alinha em etapas, com testes verdes antes e depois. Quando o projeto não tem
  padrão, propõe o idiomático da linguagem e da versão do framework em uso. Agnóstica de
  linguagem. A primeira rodada passa pelo projeto inteiro; as seguintes partem do registro em
  docs/sw-refactor/. Use quando o usuário quiser padronizar ou refatorar além de um diff —
  "refatora seguindo o padrão do projeto", "padroniza o código", "o que está fora do padrão?",
  "deixa tudo do mesmo jeito", "esse código da IA não segue o projeto", "moderniza esse legado",
  "simplifica esse módulo", "tem três jeitos de fazer a mesma coisa aqui". NÃO use para revisar
  um diff (sw-code-review), remover código morto (sw-dead-code-scan), escrever testes
  (sw-auto-test), migrar versão de framework ou formatar código. Interação em português, toda
  decisão via AskUserQuestion.
---

# Refactor — o padrão do projeto, aplicado com prova

Descobre o padrão no código, aponta quem está fora e alinha em etapas pequenas. Nada muda sem
teste verde antes e depois, ou sem o usuário aceitar seguir sem prova.

## Regras

- **Toda decisão via `AskUserQuestion`.** Nunca termine um turno com pergunta em texto.
- **Regra escrita vence** o que o código faz, sem perguntar.
- **Nunca edite sem ponto de restauração** (ver "Ponto de restauração").
- **Contrato externo só muda com pergunta** item a item (ver "Contrato externo").
- **Nunca instale ferramenta** sem perguntar. Não commite, não dê push.
- **Fora daqui:** revisar diff, remover código morto, escrever teste de propósito geral, migrar
  versão de framework, mudar arquitetura e formatar. As três primeiras são oferecidas (ver
  "Outras skills"). Única remoção feita aqui: o auxiliar que a própria etapa deixou sem uso
  (passo 8.5).

## Fluxo

1. **Entrada.** Leia `docs/sw-refactor/state.md` do projeto.
   - Não existe: primeira rodada, escopo = projeto inteiro.
   - Existe: pergunte o escopo (**Projeto inteiro / Um diretório / Arquivos citados**) e mostre o
     que mudou desde o commit registrado (`git diff --stat <commit>..HEAD`). Commit que não existe
     mais: trate como primeira rodada e mantenha os padrões de `patterns.md`. Se o `state.md`
     marca "refatoração não commitada", os arquivos tocados listados nele não contam como mudança.
   - `git status --porcelain` não vazio (ignorando artefato de build e cache, como `__pycache__/`,
     `node_modules/`, `vendor/`, `*.pyc`): avise e pergunte (**Seguir / Parar**). Arquivo já
     alterado pelo usuário só entra numa etapa com pergunta.
2. **Fontes, por autoridade:** regra escrita (`.claude/rules/`, `CONTRIBUTING*`, `STYLE*`,
   `.editorconfig`, `AGENTS.md`, `CLAUDE.md`, `docs/sw-refactor/patterns.md`) > configuração de
   linter e formatter > o que o código faz.
3. **Mapa rápido:** linguagens, frameworks e versões pelos manifestos e lockfiles; camadas pelas
   pastas; regras escritas lidas. Decida a divisão dos subagentes: um por grupo; projeto grande
   divide cada grupo por camada ou módulo. Até 10 subagentes; se precisar de mais, mostre quantos e
   por quê e pergunte (**Disparar N / Dividir em rodadas por módulo**).
4. **Descoberta:** despache os subagentes em paralelo com
   [`references/subagente-descoberta.md`](references/subagente-descoberta.md).
5. **Verificação:** para cada exemplo devolvido, confira com `sed -n '<linha>p' <arquivo>` que a
   linha mostra o que a variante descreve. Exemplo que não confere derruba a variante. Subagente
   sem resposta deixa as dimensões dele como "não medida" no relatório.
6. **Decisão por dimensão** (ver a seção).
7. **Relatório de desvios** no chat, por padrão: `arquivo:linha`, o que está e o que seria. Itens
   "muda contrato" separados e marcados. Pergunte o que entra (multiSelect, um item por padrão;
   **Other** para escolher arquivo a arquivo).
8. **Etapas,** uma por padrão (ou por módulo, se o padrão tocar mais de 10 arquivos). Arquivos com
   teste e sem teste do mesmo padrão vão em etapas separadas, para que a falha de um não desfaça o
   outro. Teste que fixa o comportamento antigo não vira "muda contrato": ele é a prova, e a etapa
   falha e volta.
   1. ponto de restauração (ver a seção);
   2. rode os testes que cobrem os arquivos da etapa. **Cobre** = algum teste executa a função ou o
      método que a etapa muda; só importar o arquivo não conta. Falharam **antes** de mexer: não comece;
      mostre a falha e pergunte (**Pular / Seguir sem prova / Parar**);
   3. nenhum teste cobre: pergunte (**Pular / Seguir sem prova / Caracterizar com a
      sw-auto-test**). "Seguir sem prova" vai para o `state.md`;
   4. aplique: a ferramenta de [`references/refatoracoes-seguras.md`](references/refatoracoes-seguras.md)
      quando já estiver instalada; senão, edite. Projeto grande pode usar um subagente por etapa,
      com o padrão, os desvios da etapa e estas regras; confira o diff que ele produziu;
   5. auxiliar que a própria etapa deixou sem uso (a classe Request que nenhum controller chama
      mais) é removido nessa mesma etapa, já dentro do ponto de restauração, e citado no relatório.
      Código que já estava sem uso antes da rodada não é removido: é da `sw-dead-code-scan`;
   6. rode os testes de novo, já com a remoção do passo 5. Falharam: restaure a etapa, mostre o
      erro e pergunte (**Tentar de outro jeito / Pular / Parar**). Três falhas seguidas param a
      rodada;
   7. apague o cache que os testes criaram e que não existia antes (`__pycache__/`, `.pytest_cache/`).
9. **Fechamento:**
   1. nova descoberta só nas dimensões tratadas, no escopo: os itens aprovados devem dar zero;
      pulados e recusados vão para pendentes;
   2. ofereça a `sw-code-review` no diff da rodada e a `sw-git-commit` com uma etapa por commit;
   3. mostre o que será gravado (ver "Arquivos gravados") e pergunte (**Gravar / Não gravar**);
   4. só se o usuário escolheu **Gravar**: pergunte se adiciona a seção ao `AGENTS.md` e ao `CLAUDE.md`.

## Decisão por dimensão

| Variante dominante | O que fazer |
|---|---|
| ≥ 80% | candidato a padrão; confirme todos os candidatos numa pergunta só (multiSelect) |
| < 80% | conflito: recontagem (variante "recontagem" do prompt) e depois pergunte |
| nenhuma variante | proponha o idiomático (ver [`references/idiomatico.md`](references/idiomatico.md)) |

A pergunta de conflito mostra, por variante: contagem, um exemplo real `arquivo:linha` e qual é a
idiomática do framework. Opções: uma por variante, mais **Deixar sem padrão**.

**Idiomático:** use `references/idiomatico.md` como base. Com busca na web na sessão, confira a
documentação oficial da versão do manifesto e cite a fonte; sem web, marque "não conferido".

**Limites de complexidade:** função > 40 linhas e aninhamento > 3, ou o percentil 80 do projeto
quando for maior. Se 80% das funções têm até 60 linhas, o limite vira 60.

## Ponto de restauração

Antes de editar qualquer arquivo de uma etapa:

Rode sempre **na raiz do projeto** e passe os arquivos com caminho **relativo** a ela: caminho
absoluto faria a restauração recriar a árvore dentro do projeto sem desfazer nada.

```bash
cd <raiz do projeto>
PONTO=<pasta temporária da sessão>/sw-refactor/etapa-<n>   # sem pasta da sessão: PONTO=$(mktemp -d)
mkdir -p "$PONTO" && tar -cf "$PONTO/arquivos.tar" <arquivos da etapa, relativos à raiz>
```

`tar` funciona igual em Linux e macOS (`cp --parents` só existe no GNU). Use a pasta temporária que
o ambiente indicar para a sessão; sem ela, `mktemp -d`. Guarde o caminho: é por ele que a etapa é
restaurada. Todo arquivo que a etapa **criar** (inclusive o novo nome de um arquivo renomeado) vai,
um por linha e relativo à raiz, em `"$PONTO/criados"`.

Para restaurar, na raiz do projeto:

```bash
tar -xf "$PONTO/arquivos.tar"
[ -f "$PONTO/criados" ] && while IFS= read -r f; do rm -f -- "$f"; done < "$PONTO/criados"
```

Isso volta **só** os arquivos dessa etapa. Nunca use `git checkout` nem `git stash`: eles levam
junto as etapas anteriores e as mudanças do usuário.

## Contrato externo

Desvio que muda o que alguém **fora deste código** vê (rota, chave de JSON, status HTTP, mensagem
de erro devolvida, coluna, nome chamado por reflexão ou por outro sistema) vem marcado **muda
contrato**, com quem consome (grep pelo símbolo ou pela chave). Função ou método só chamado
dentro do projeto não é contrato, mesmo sendo público: o renome alcança todos os chamadores na
mesma etapa. Só entra com pergunta própria (**Aplicar / Deixar como está**), mesmo que o padrão
já tenha sido aprovado.

## Arquivos gravados

Só no fechamento, com o "Gravar". Nomes e cabeçalhos em inglês; texto no idioma do projeto.

`docs/sw-refactor/patterns.md`, um bloco por padrão:

```markdown
## Error handling — services
- Rule: services raise DomainError; the API layer maps it to HTTP.
- Decided by: owner (2026-11-03)
- Evidence: 4 of 6 services
- Correct: app/services/orders.py:6
- Wrong: app/services/shipping.py:3
```

`docs/sw-refactor/state.md`:

```markdown
# sw-refactor state
- Last run: 2026-11-03
- Base commit: <hash>
- Final commit: <hash | refatoração não commitada>
- Scope: <projeto | diretório | arquivos>
- Touched files: <lista>
- Patterns applied: <lista>
- Pending deviations: <padrão: arquivo:linha — motivo (pulado | recusado | contrato)>
- Unproven steps: <etapa — motivo>
```

Seção para `AGENTS.md` e `CLAUDE.md` (arquivo inexistente: pergunte se cria cada um):

```markdown
## Code patterns
Follow docs/sw-refactor/patterns.md. Pending deviations: docs/sw-refactor/state.md.
```

O relatório de desvios não vira arquivo.

## Outras skills

Sempre oferta por `AskUserQuestion`, nunca automática. Não instalada: diga e siga.

| Momento | Skill | Pedido |
|---|---|---|
| 1ª rodada, se a descoberta achar arquivo ou função sem uso | `sw-dead-code-scan` | limpar antes de refatorar |
| Etapa sem teste, se o usuário escolher caracterizar | `sw-auto-test` | "Escreva um teste de caracterização para `<arquivo>`: fixe o comportamento atual, inclusive o estranho; não corrija bug e não altere o código." |
| Fechamento | `sw-code-review` | revisar o diff da rodada |
| Fechamento | `sw-git-commit` | uma etapa por commit |
