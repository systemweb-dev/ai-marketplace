# Prompt do revisor do plano

Use este template ao despachar o revisor do **documento do plano** (ver "Revisor do plano" no
SKILL.md). Ele roda **depois** do self-review e do `plan_check.py`, e **antes** do gate de
aprovação do usuário.

**Para quê:** conferir se o plano está completo, cobre o spec e está bem dividido em tasks.

**Quando despachar:** com o plano inteiro escrito e o lint limpo.

O revisor é **consultivo**: devolve status, problemas e recomendações; **não edita o plano e
não aprova no lugar do usuário**.

```
Agent (subagent_type: general-purpose):
  description: "Revisar o plano"
  prompt: |
    Você revisa um plano de implementação. Confira se ele está completo e pronto para alguém
    executar sem travar.

    **Plano a revisar:** [CAMINHO_DO_PLANO]
    **Spec de referência:** [CAMINHO_DO_SPEC]

    ## O que checar

    | Categoria | O que procurar |
    |---|---|
    | Completude | TODO, placeholder, task pela metade, step faltando |
    | Aderência ao spec | O plano cobre os requisitos do spec, sem escopo a mais |
    | Restrições verificáveis | Cada fitness function do spec aponta para a task e o step que a checa? |
    | Ordem por risco | A suposição mais arriscada é atacada primeiro (spike), ou o plano deixa o risco para o fim? |
    | Divisão em tasks | Fronteiras claras, steps executáveis, tasks que se sustentam sozinhas |
    | Contratos | Tipos, assinaturas e nomes usados nas tasks finais batem com os definidos antes |
    | Executabilidade | Alguém que não conhece o projeto conseguiria seguir sem adivinhar? |

    ## Calibragem

    **Só aponte o que causaria problema real na implementação.** Quem executa construir a
    coisa errada, ou travar sem saber o que fazer, é problema. Redação, preferência de estilo
    e "seria bom ter" não são.

    Aprove, a não ser que haja lacuna séria: requisito do spec sem task, steps que se
    contradizem, conteúdo placeholder, ou task vaga demais para ser executada.

    ## Formato da resposta

    ## Revisão do plano

    **Status:** Aprovado | Com problemas

    **Problemas (se houver):**
    - [Task X, Step Y]: [problema específico] — [por que atrapalha a implementação]

    **Recomendações (não bloqueiam a aprovação):**
    - [sugestões]
```

**O revisor devolve:** status, problemas (se houver) e recomendações.
