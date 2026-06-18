---
name: skill-test
description: >
  Testa rápido se uma skill JÁ EXISTENTE funciona de verdade — sem navegador, sem benchmark
  pesado, sem API key. Faz duas verificações: (1) COMPORTAMENTO — planta um fixture realista
  com casos claros + armadilhas (gabarito conhecido) no diretório temporário do SO, roda a
  skill-alvo nele COM e SEM a skill (baseline) e compara contra o gabarito; (2) DISPARO — gera
  frases que devem e não devem disparar a skill e checa, via juiz independente que vê só o
  nome+descrição, se ela ativa nas certas e fica quieta nas pegadinhas. Fecha com um relatório
  markdown de veredito + recomendações concretas (ex.: "essa frase não dispara → adicione tal
  gatilho"). Use SEMPRE que o usuário quiser validar/testar uma skill que ele criou — "testa
  essa skill", "a skill X tá funcionando?", "valida a skill que acabei de fazer", "checa se a
  skill dispara certo", "será que a skill ficou boa?", "smoke test da skill", "minha skill tá
  pegando os casos?". NÃO use para: criar ou melhorar uma skill (isso é o skill-creator), nem
  para testar o código de um app (isso é auto-test) — aqui o alvo do teste é uma SKILL.
  Interação e relatório em português (PT-BR).
---

# Skill Test

Um teste **rápido** (exame de saúde) de uma skill já criada. O objetivo é responder, em poucos minutos e sem máquina pesada, a duas perguntas que decidem se uma skill presta:

1. **Comportamento** — quando disparada, ela *faz o trabalho direito*?
2. **Disparo (triggering)** — ela *ativa nas frases certas* e fica quieta nas erradas?

Uma skill pode falhar em qualquer uma das duas de forma independente (faz o trabalho bem mas nunca dispara; ou dispara sempre mas faz besteira). Por isso checamos as duas.

## Quando NÃO usar (pra não competir com o que já existe)

- **Criar ou melhorar** uma skill → é o `skill-creator` (este teste é só pra *validar* uma que já está escrita).
- **Avaliação rigorosa com benchmark/navegador** ou **otimização automática da descrição** → também é o `skill-creator` (eval-viewer, `run_loop`). Use lá quando quiser nota quantitativa e iteração formal.
- **Testar código de um app** (gerar testes unit/integração/e2e) → é o `auto-test`.

Este teste é o **caminho leve**: fixture descartável + comparação com/sem + juiz de disparo, tudo no terminal, sem depender de API key.

## Fase 0 — Identificar a skill-alvo

Descubra QUAL skill testar (o usuário aponta pelo nome/caminho; se ambíguo, **dispare `AskUserQuestion`** com as skills candidatas). Leia o `SKILL.md` dela por completo — `name`, `description` e o corpo. Extraia:

- **O que ela faz** e o **domínio** (linguagem-agnóstica? só PHP? gera arquivo? transforma dado?).
- **O artefato verificável** que ela produz (um relatório? um arquivo? uma edição? um fluxo?).
- **As armadilhas do domínio** — onde um detector/transformador ingênuo erraria (a skill deveria acertar).

## Fase A — Teste de comportamento

### A1. Derivar casos + armadilhas + gabarito

Do domínio da skill, monte uma **lista de casos com resposta conhecida** (o gabarito). Inclua sempre:

- **Casos claros** que a skill deve acertar (o "feijão com arroz" do que ela promete).
- **Armadilhas** — coisas que *parecem* o caso mas não são, ou vice-versa. É aqui que skills medíocres caem. Pense no falso positivo/negativo típico do domínio.
- Para cada caso, anote o **esperado** (o que a skill deveria fazer/dizer).

> Exemplo (testando a `dead-code-scan`): casos claros = import não usado, função privada morta; armadilhas = função chamada por `getattr("handle_"+tipo)` (viva, parece morta) e classe registrada por string num YAML. Gabarito: os claros são "morto"; as armadilhas são "vivo, não remover".

### A2. Plantar o fixture (em diretório temporário, nunca no repo)

Crie um projeto/arquivo de teste mínimo que materialize os casos, num diretório **temporário do SO**: `mktemp -d` (Linux/macOS → algo em `/tmp`; outros SOs → o temp equivalente). Nunca dentro do repositório da skill. Documente no próprio fixture (comentários) qual caso é qual, pra leitura fácil.

### A3. Rodar com a skill E sem (baseline), em paralelo

Lance **dois subagents na mesma rodada**:

- **Com a skill**: passe o caminho da skill-alvo, mande ler e **seguir o método dela** sobre o fixture, e produzir o artefato verificável. **Pule etapas interativas** (a skill pode usar `AskUserQuestion` que depende do usuário) — instrua o subagent a parar no artefato (ex.: gerar o relatório, sem a remoção guiada) ou simular a escolha mais comum.
- **Sem a skill (baseline)**: o mesmo pedido, em linguagem natural, **sem** apontar a skill. É o "Claude puro".

Rodar os dois mostra o que a skill **realmente agrega** — às vezes o modelo já faz bem sozinho, e o valor da skill está em consistência/estrutura/fluxo, não em "acertar o que o baseline erra". Seja honesto sobre isso no veredito.

### A4. Comparar contra o gabarito

Monte uma tabela: **caso → esperado → com-skill → baseline → ✓/✗**. Destaque:

- Onde a skill **acertou e o baseline errou** (valor real da skill).
- Onde **os dois acertaram** (o modelo já é bom nisso — a skill agrega por outro motivo, diga qual).
- Onde a **skill errou** (bug da skill — prioridade de conserto).

## Fase B — Teste de disparo

### B1. Gerar as frases

Crie ~12–16 frases realistas (como um usuário falaria, com contexto/detalhe), metade **deve disparar** e metade **pegadinhas** (não devem). As pegadinhas valiosas são os *quase-acertos*: compartilham palavras/tema com a skill mas precisam de outra coisa. Evite negativas óbvias (não testam nada).

### B2. Julgar o disparo (juiz independente, sem API key)

Para cada frase, use um **subagent-juiz** que recebe **só o `name` + `description` da skill** (é exatamente o que o roteador real enxerga — NÃO mostre o corpo) e a mensagem, e responde **SIM/NÃO** ("você consultaria essa skill pra essa mensagem?"). Rode o lote 2× (ou com 2 juízes) pra estabilidade e tire a maioria.

> Por que só nome+descrição: o disparo da skill no Claude Code é decidido a partir da descrição na lista de skills disponíveis. Testar com o corpo inteiro daria um resultado otimista e irreal.

### B3. Apurar

Tabela: **frase → esperado (dispara?) → juiz → ✓/✗**. Some os erros em dois baldes:
- **Não disparou onde devia** (sub-disparo) → a descrição não cobre esse jeito de pedir.
- **Disparou na pegadinha** (sobre-disparo) → falta fronteira negativa na descrição.

## Fase C — Veredito + relatório

Escreva um relatório markdown (template abaixo) no diretório temporário e mostre o resumo no chat. O mais importante são as **recomendações concretas e acionáveis** — ligando cada falha a um conserto específico na skill.

```markdown
# Teste de skill — <skill-alvo>
<data> · fixture: <tmp dir> · método: comportamento (com vs sem) + disparo (juiz)

## Veredito
<1–2 frases: a skill está saudável? onde brilha, onde falha.>

## Comportamento
| Caso | Esperado | Com skill | Baseline | Skill agrega? |
|------|----------|-----------|----------|---------------|
| ...  | morto    | morto ✓   | hesitou  | sim (consistência) |

## Disparo
| Frase | Deve disparar? | Juiz | OK? |
|-------|----------------|------|-----|
| "limpa o que não uso" | sim | sim | ✓ |
| "deleta o arquivo X que já decidi" | não | sim | ✗ sobre-disparo |

## Recomendações (acionáveis)
- [Disparo] A frase "<...>" não dispara → adicione "<gatilho>" na descrição.
- [Disparo] Dispara em "<pegadinha>" → adicione fronteira negativa ("NÃO use para ...").
- [Comportamento] No caso <X> a skill <falhou assim> → ajuste <tal regra> no corpo.

## Limitações deste teste
- O juiz de disparo é um proxy (não roda o roteador real com todas as skills competindo).
- O fixture é sintético; vale também um teste num projeto real depois.
```

## Princípios

- **Gabarito sempre.** Sem resposta conhecida, "testar" vira achismo. O fixture auto-gerado existe pra ter gabarito; por isso é o padrão.
- **Plante armadilhas, não só o caminho feliz.** O caminho feliz quase toda skill acerta. A diferença aparece nas armadilhas.
- **Juiz vê só nome+descrição.** Fidelidade ao mecanismo real de disparo.
- **Seja honesto sobre o baseline.** Se o Claude puro já resolve, diga — e identifique o valor verdadeiro da skill (consistência, estrutura, fluxo, ferramentas).
- **Descartável.** Fixture e relatório vivem no temp do SO; somem no reboot, não sujam repo nenhum.

## Limites

Este teste **valida** uma skill existente de forma leve — não cria, não melhora automaticamente, e não substitui o eval rigoroso do `skill-creator` (benchmark quantitativo, eval-viewer, otimização da descrição com `run_loop`). Quando o usuário quiser nota quantitativa, iteração formal ou otimização automática do disparo, aponte pro `skill-creator`. O juiz de disparo e o fixture sintético são aproximações úteis, não verdades absolutas — trate o veredito como um sinal forte, não um selo.
