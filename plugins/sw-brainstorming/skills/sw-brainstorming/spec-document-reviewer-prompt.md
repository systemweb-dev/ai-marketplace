# Prompts do revisor (brainstorming)

Duas variantes, despachadas conforme o **nível de revisão** escolhido (ver "Revisor opcional" no
SKILL.md):

- **"spec"** — revisa o documento de spec completo (abaixo).
- **"design/checkpoint"** — revisa o design acumulado num gate, antes de existir spec (no fim).

O revisor é **consultivo**: retorna status, problemas e recomendações; **não edita nada e não
aprova no lugar do usuário**. Como ele conversa com o usuário no fim, o prompt e a resposta são
em português, como o resto da skill.

---

## Variante "spec"

Use este template ao despachar um revisor do documento de spec.

**Para quê:** conferir se o spec está completo, coerente e pronto para virar plano.

**Quando despachar:** depois que o spec foi escrito no dossiê — `docs/specs/<data>-<slug>/spec.md`
(ou a raiz que o trabalho estiver usando: veja o caminho que o `dossie.py` imprimiu).

```
Task tool (general-purpose):
  description: "Revisar o spec"
  prompt: |
    Você revisa um documento de spec. Confira se ele está completo e pronto para o plano.

    **Spec a revisar:** [CAMINHO_DO_SPEC]

    ## O que checar

    | Categoria | O que procurar |
    |---|---|
    | Completude | TODO, "TBD", placeholder, seção pela metade |
    | Coerência | Contradições internas; requisitos que brigam entre si |
    | Clareza | Requisito ambíguo o bastante para alguém construir a coisa errada |
    | Escopo | Cabe num plano só, sem cobrir vários subsistemas independentes |
    | Não-objetivos | Estão explícitos? Sem eles, o escopo escorrega na execução |
    | Simplicidade | É a menor solução que resolve? Tem abstração especulativa ou generalização prematura? |
    | Appetite e MVP | O esforço que o trabalho merece está dito, e o corte (validar rápido × encantar) está claro? |
    | Decisões | As estruturais têm contexto, alternativas descartadas e consequências? |
    | Restrições verificáveis | As fitness functions dão para CHECAR (ex.: "p95 < 200ms", "o módulo A não importa B") ou são desejo solto ("deve ser rápido", "código limpo")? |
    | YAGNI | Feature que ninguém pediu, engenharia a mais |

    ## Calibragem

    **Só aponte o que causaria problema real ao planejar.** Seção faltando, contradição, ou
    requisito que admite duas leituras são problemas. Melhoria de redação, preferência de
    estilo e "essa seção está menos detalhada que a outra" não são.

    Aprove, a não ser que haja lacuna séria o bastante para gerar um plano errado.

    ## Formato da resposta

    ## Revisão do spec

    **Status:** Aprovado | Com problemas

    **Problemas (se houver):**
    - [Seção X]: [problema específico] — [por que atrapalha o plano]

    **Recomendações (não bloqueiam a aprovação):**
    - [sugestões]
```

**O revisor devolve:** status, problemas (se houver) e recomendações.

---

## Variante "design/checkpoint"

Use este template ao despachar um revisor **durante** o design (depois de um gate), quando
ainda não existe arquivo de spec.

**Para quê:** pegar cedo o que está torto — lacuna, contradição, caso-limite esquecido,
engenharia a mais — enquanto mudar ainda é barato.

**Quando despachar:** depois que o design (ou, no modo "cada checkpoint", o gate atual) foi
aprovado pelo usuário. **Passe o design acumulado no próprio prompt** (não há arquivo ainda) e,
em "cada checkpoint", inclua o design inteiro até aqui, nunca só a seção isolada.

```
Task tool (general-purpose):
  description: "Revisar o design (antes do spec)"
  prompt: |
    Você revisa um design em andamento numa sessão de brainstorming. Ainda não existe spec.
    Leia com olhos frescos.

    **Design até aqui:**
    [COLE O DESIGN ACUMULADO: problema, abordagem escolhida, seções aprovadas, restrições]

    ## O que checar

    | Categoria | O que procurar |
    |---|---|
    | Lacunas | Fluxo, estado ou erro não coberto; dependência não resolvida |
    | Coerência | Decisões que se contradizem; abordagem que não bate com as restrições |
    | Casos-limite | Situações de borda e modos de falha plausíveis ignorados |
    | Fronteiras | Unidade fazendo coisa demais; interfaces confusas |
    | YAGNI | Complexidade ou feature que ninguém pediu |
    | Risco | A suposição mais arriscada: o que, se estiver errado, derruba o design? |

    ## Calibragem

    **Só aponte o que causaria retrabalho de verdade ou levaria a construir a coisa errada.**
    Não levante preferência de estilo nem detalhe que cabe na fase de plano. Na dúvida sobre
    algo pequeno, deixe como recomendação, não como bloqueio.

    ## Formato da resposta

    ## Revisão do design

    **Status:** Parece sólido | Com problemas

    **Problemas (se houver):**
    - [Área]: [problema específico] — [por que importa agora]

    **Perguntas em aberto para levar ao usuário (se houver):**
    - [pergunta]

    **Recomendações (não bloqueiam):**
    - [sugestões]
```

**O revisor devolve:** status, problemas, perguntas em aberto e recomendações.
