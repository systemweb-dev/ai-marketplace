# Retenção — repetição espaçada, fracos, provas, calibração e XP

Por que existe: **o que não é revisado é esquecido.** A skill não termina quando o
conteúdo termina — com acompanhamento ativo, o que a pessoa aprendeu ressurfa no tempo
certo. Tudo isso vive em `meta.json` (campos `reviews`, `fracos`, `exams`, `streak`, `xp`)
e é escrito **SÓ por `review.py`** — nunca edite esses campos à mão (o script cuida de
datas, intervalos e streak).

## Comandos (`python3 ~/.claude/skills/sw-study-buddy/scripts/review.py`)

| Comando | Efeito |
|---|---|
| `--dir D --action due` | Lista (JSON) as revisões vencidas (`due <= hoje`) |
| `--dir D --action add --topic N --concept X` | Agenda a 1ª revisão de um tópico concluído (vence amanhã) |
| `--dir D --action ok --concept X` | Acerto na revisão: intervalo ×2 (cap 30), +5 XP, sai de fracos |
| `--dir D --action fail --concept X` | Erro: volta a 1 dia, zera a força, entra/++ em fracos |
| `--dir D --action done --concept X` | Acerto de verdade num fraco (prática/quiz): remove de fracos |
| `--dir D --action exam --module N --score S --total T [--missed X …]` | Registra prova, +10 XP; cada `--missed` vira fraco |
| `--dir D --action activity --xp N` | Atividade avulsa: some XP e atualiza streak |

`--concept` é a chave de lookup — use o nome curto do conceito (2–4 palavras), consistente
entre add/ok/fail (ex.: `ownership`, `slice capacity`). A saída é um JSON curto com `xp`,
`streak`, `reviews_total` e `fracos` atuais.

## Repetição espaçada

- **Intervalos:** 1 → 2 → 4 → 8 → 16 → 30 dias. Acerto dobra (cap 30); erro volta a 1 e
  zera a `strength`.
- **Quando agenda:** ao concluir um tópico (status `done`), `add` com o **conceito central**
  dele. Um tópico com vários conceitos → 1 `add` por conceito (até 2–3, os que mais importam).
- **"Revisão primeiro"** (início de sessão com acompanhamento): rode `due`. Se N > 0,
  ofereça via `AskUserQuestion`: "Tem **N** revisões pendentes — quer revisar antes? (1–2 min)"
  com **"Sim, revisar agora"** / **"Pular por hoje"**. A revisão é um quiz de **3–5 perguntas**
  (múltipla escolha via `AskUserQuestion`, uma de cada vez, misturando os conceitos vencidos):
  a cada acerto `ok --concept`, a cada erro `fail --concept`. Sem nada vencido → siga em silêncio.
- **Perguntas de revisão:** "o que acontece se…", "diferença entre X e Y", "por que se usa X
  em vez de Y" — nunca "decorra a definição".

## Pontos fracos (`fracos`)

- **Entra:** erro em quiz/exercício/prova (`fail` ou `--missed`).
- **Alvo de prática futura:** no modo Praticar, quando `fracos` não estiver vazio, inclua a
  opção **"Só os fracos"** no menu de formato.
- **Sai:** primeiro acerto de verdade no conceito (`done`, ou `ok` na revisão).
- Fraco com `fails >= 3`: a base anterior não fixou — volte ao tópico onde ele nasceu antes
  de insistir (regra do travamento abaixo).

## Travamento (detectar e voltar)

2–3 erros seguidos no **mesmo conceito** (quiz, exercício, prova) → pare de martelar.
Dispare o `AskUserQuestion` ("**X** parece travado — como seguir?") com:
**"Voltar ao conceito anterior e re-verificar"** / **"Mudar o ângulo (exemplo novo, analogia,
rodar o código)"** / **"Só uma dica e eu tento de novo"**.

## Calibração de módulo

Módulo 2+ (ou sempre, se nível avançado): no início do módulo, **2 MCQs** via
`AskUserQuestion` sobre a base que o módulo pressupõe.
- 2 acertos → ofereça **"Andar rápido neste módulo?"** (condensar/pular tópicos já dominados).
- 2 erros → desacelere: reforce o fundamento, mais exemplos, antes de seguir.
- Anote o resultado em `progresso.md`.

## Prova do módulo

No fim de cada módulo (padrão, antes do próximo):
- **5–8 perguntas:** 4–6 de múltipla escolha via `AskUserQuestion` + 1 aberta no chat.
- Misture os conceitos do módulo e inclua **≥1 falso amigo** (pegadinha de quem migra da
  linguagem-base, se houver).
- Some a nota → `exam --module N --score S --total T --missed <conceito> …` (errados → fracos).
- Gere a **ficha da prova**: `build_ficha.py --kind exame` com o placar (`.exam-score`) e a
  lista ok/erradas (`.exam-list`, "porquê" do erro em `<small>`).
- Placar < 70% → ofereça revisar os errados antes do próximo módulo.

## Flashcards

Ficha `--kind flashcards` (5–10 cards por módulo; bloco em `references/blocos.md`):
pergunta no `<summary>`, resposta no flip. Bons cards: casos "o que acontece se",
comparações, falsos amigos. Gere ao fechar o módulo (junto da prova, via
`AskUserQuestion`) ou sob pedido ("flashcards de X").

## Glossário

`glossario.json` no diretório do tema: `[{termo, def, topico}]`. Anote termos novos ao
terminar tópicos (1–3 por tópico no máximo — só o que a pessoa vai precisar de novo).
Ficha: `build_ficha.py --kind glossario --title "Glossário — <tema>" --dir <dir> --tema "<tema>"`
(gera `glossario/glossario.html`; link automático na sidebar da apostila).

## Streak e XP

- **Streak:** dias consecutivos com atividade (tópico, revisão, prova, prática) somam;
  pular um dia zera (`best` fica salvo). O `streak_bump` é idempotente no mesmo dia.
- **XP por tipo:** tópico concluído 10 · revisão acertada 5 · prova 10 · sessão de prática 5.
- Aparecem como chips na sidebar (a `build_study_page.py` lê do `meta.json` automaticamente).
