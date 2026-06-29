# Reviewer Prompt Templates (brainstorming)

Two variants, dispatched conforme o **nível de revisão** escolhido (ver "Revisor opcional" no SKILL.md):

- **"spec"** — revisa o documento de spec completo (abaixo).
- **"design/checkpoint"** — revisa o design acumulado num gate, antes de existir spec (no fim).

O revisor é **consultivo**: retorna status + problemas + recomendações; **não edita nada e não
aprova no lugar do usuário**.

---

## Variante "spec"

Use this template when dispatching a spec document reviewer subagent.

**Purpose:** Verify the spec is complete, consistent, and ready for implementation planning.

**Dispatch after:** Spec document is written to `~/.claude/projects/<cwd-slug>/specs/`

```
Task tool (general-purpose):
  description: "Review spec document"
  prompt: |
    You are a spec document reviewer. Verify this spec is complete and ready for planning.

    **Spec to review:** [SPEC_FILE_PATH]

    ## What to Check

    | Category | What to Look For |
    |----------|------------------|
    | Completeness | TODOs, placeholders, "TBD", incomplete sections |
    | Consistency | Internal contradictions, conflicting requirements |
    | Clarity | Requirements ambiguous enough to cause someone to build the wrong thing |
    | Scope | Focused enough for a single plan — not covering multiple independent subsystems |
    | YAGNI | Unrequested features, over-engineering |

    ## Calibration

    **Only flag issues that would cause real problems during implementation planning.**
    A missing section, a contradiction, or a requirement so ambiguous it could be
    interpreted two different ways — those are issues. Minor wording improvements,
    stylistic preferences, and "sections less detailed than others" are not.

    Approve unless there are serious gaps that would lead to a flawed plan.

    ## Output Format

    ## Spec Review

    **Status:** Approved | Issues Found

    **Issues (if any):**
    - [Section X]: [specific issue] - [why it matters for planning]

    **Recommendations (advisory, do not block approval):**
    - [suggestions for improvement]
```

**Reviewer returns:** Status, Issues (if any), Recommendations

---

## Variante "design/checkpoint"

Use this template when dispatching a reviewer **during** the design phase (after a gate),
before a spec file exists.

**Purpose:** Catch design flaws early — gaps, contradictions, missed edge cases, over-engineering —
while the design is still cheap to change.

**Dispatch after:** the design (or, no modo "cada checkpoint", o gate atual) foi aprovado pelo usuário.
**Pass the accumulated design inline** (não há arquivo ainda) — e, em "cada checkpoint", inclua o
design inteiro até aqui, nunca só a seção isolada.

```
Task tool (general-purpose):
  description: "Review design (pre-spec)"
  prompt: |
    You are a design reviewer in a brainstorming session. The team is still shaping the
    design — no spec exists yet. Review the design below with fresh eyes.

    **Design so far:**
    [PASTE ACCUMULATED DESIGN: problema, abordagem escolhida, seções aprovadas, restrições]

    ## What to Check

    | Category | What to Look For |
    |----------|------------------|
    | Gaps | Fluxos/estados/erros não cobertos; dependência não resolvida |
    | Consistency | Decisões que se contradizem; abordagem que não bate com as restrições |
    | Edge cases | Casos-limite e modos de falha plausíveis ignorados |
    | Boundaries | Unidade fazendo coisa demais; fronteiras/interfaces confusas |
    | YAGNI | Complexidade ou feature não pedida |
    | Risk | A suposição mais arriscada — o que, se errado, derruba o design? |

    ## Calibration

    **Only flag what would cause real rework or a wrong build.** Não levante preferência de
    estilo nem detalhe que cabe na fase de plano. Na dúvida sobre algo pequeno, deixe como
    recomendação, não como bloqueio.

    ## Output Format

    ## Design Review

    **Status:** Looks solid | Issues Found

    **Issues (if any):**
    - [Área]: [problema específico] - [por que importa agora]

    **Open questions to resolve with the user (if any):**
    - [pergunta]

    **Recommendations (advisory):**
    - [sugestões]
```

**Reviewer returns:** Status, Issues, Open questions, Recommendations
