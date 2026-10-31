# Prompt da revisão final com contexto vazio

Usado quando o usuário pediu, no Execution Handoff, a `sw-code-review` ao terminar a execução.
Contexto vazio só vale enquanto o prompt continuar vazio de opinião: não acrescente resumo do que
foi feito, dificuldades, decisões nem o que parece arriscado. Quem recebe a sua conclusão tende a
devolvê-la confirmada.

Preencha só os três caminhos/valores abaixo. `[BASE]` é o SHA registrado no `plan.md`.

```
Agent (general-purpose):
  description: "Code review final"
  prompt: |
    Leia [CAMINHO_DA_SKILL_SW_CODE_REVIEW]/SKILL.md e siga o workflow dela para revisar as
    mudanças deste repositório desde o commit [BASE], incluindo o que não foi commitado:

        git diff [BASE]

    Contrato do que devia ser construído (leia, não assuma):
    - Plano: [CAMINHO_DO_PLAN]
    - Spec: [CAMINHO_DO_SPEC, ou "não há"]

    Você roda sem usuário por perto, então estas regras substituem os passos interativos:
    - Escopo fixo: `git diff [BASE]`. Não pergunte modo PR ou modo local.
    - Foco: todas as categorias. Não pergunte o filtro de foco.
    - NÃO aplique fix, NÃO edite arquivo, NÃO faça commit. Pare antes do passo de aplicar.
    - Mantenha a verificação de cada achado: só reporte o que confirmou no código.

    Responda com os achados por severidade, cada um com caminho:linha, o problema e como
    reproduzir. Sem achados, diga isso e diga o que foi lido.
```

**Quem decide é o usuário.** Mostre os achados como vieram e pergunte via `AskUserQuestion` o que
corrigir (**Corrigir todos** / **Escolher** / **Só registrar**). A correção acontece na sessão
principal, seguindo as regras do projeto.
