# Lentes de exploração (modo "Explorar a fundo")

Catálogo das **técnicas de ideação divergente** usadas quando o usuário escolhe
**"Explorar a fundo"** logo após a exploração de contexto. Cada lente é um mini-bloco de
perguntas que ABRE o espaço de possibilidades antes de convergir pro design.

## Como rodar o loop

1. **Escolha 2-3 lentes** que a ideia pede — não despeje as seis. (Ideia vaga/nova → JTBD +
   Divergir; algo com risco → + Riscos; algo preso a uma restrição → + Flip.) Anuncie quais vai usar.
2. **Uma pergunta por vez**, via `AskUserQuestion`. Sempre ofereça opções prováveis + o campo
   **"Other"** e uma opção **"Pular esta lente"**. Nunca pergunta em texto solto.
3. **Não repita** o que o usuário já respondeu na descrição inicial ou numa lente anterior.
   Reaproveite; aprofunde, não recomece.
4. **A cada ~2 lentes, ofereça convergir:** `AskUserQuestion` com **"Explorar mais uma lente"**
   vs **"Já dá — sintetiza"**. A saída pra convergência está SEMPRE disponível — o loop nunca
   é infinito nem obrigatório até o fim.
5. **Sintetize** (ver "Saída" abaixo) e siga pro passo de **abordagens** do fluxo normal.

> É divergência com rédea: o objetivo é enriquecer o design, não filosofar. Se as respostas já
> deram material pra 2-3 abordagens fortes, **convirja** — não force mais lentes.

## As lentes

### 1. Enquadrar o problema (Jobs-to-be-done)
**Pra quê:** garantir que estamos resolvendo a dor certa, não a primeira solução que apareceu.
**Quando:** quase sempre — é a lente-base. Especialmente se a ideia já vem como solução pronta.
**Perguntas (exemplos):**
- Qual é a **dor real** por trás disso? O que trava hoje?
- **Pra quem** é? Quem sente mais essa dor?
- **Por que agora** — o que mudou que torna isso importante neste momento?
- O que a pessoa **faz hoje** sem isso (a gambiarra atual)?
- Como saberemos que **resolveu**? (o critério de sucesso, em uma frase)

### 2. Divergir (ângulos alternativos)
**Pra quê:** fugir da primeira solução; gerar opções genuinamente diferentes.
**Quando:** sempre que existe mais de um caminho plausível.
**Perguntas (exemplos):**
- Que **outros jeitos** de resolver isso existem, sem ser o óbvio?
- Se um produto de **outro domínio** resolvesse isso, como faria? (analogia: como o Spotify/Uber/planilha faria?)
- E se fosse o **extremo**: a versão mais simples possível? a mais ambiciosa?
- E se **invertesse** — em vez de o usuário fazer X, o sistema faz sozinho?

### 3. Desafiar suposições
**Pra quê:** trazer à tona o que estamos assumindo sem checar — a fonte nº1 de retrabalho.
**Quando:** quando há "certezas" implícitas (formato, público, fluxo, tecnologia).
**Perguntas (exemplos):**
- Estamos **assumindo** que [X]. Isso é fato ou palpite?
- E se **[essa suposição] for falsa** — o design muda?
- Que parte disso a gente está tratando como "óbvio" e nunca confirmou com quem usa?

### 4. Flip de restrições
**Pra quê:** descobrir o essencial removendo (ou apertando) limites.
**Quando:** quando a ideia parece grande, ou presa a uma restrição específica.
**Perguntas (exemplos):**
- E se **não houvesse** [tal restrição] — o que faríamos diferente?
- Se tivesse **metade do tempo/tela/orçamento**, o que cortaria primeiro?
- Se fosse **uma tela só**, o que PRECISA estar nela? (revela o núcleo/MVP)
- Qual a **menor versão** que já entrega valor de verdade?

### 5. Referências / prior art
**Pra quê:** aprender com quem já resolveu — copiar o que funciona, evitar o que não.
**Quando:** problema comum (auth, busca, checkout, dashboard, onboarding…).
**Perguntas (exemplos):**
- Que **produtos conhecidos** fazem algo parecido? Qual você gosta e por quê?
- O que **copiar** desses exemplos? O que **evitar** (o que te irrita neles)?
- Tem um **padrão consagrado** pra isso que a gente deveria seguir em vez de inventar?

### 6. Riscos & bordas
**Pra quê:** antecipar o que quebra, os casos extremos e quem pode se prejudicar.
**Quando:** fluxos com dinheiro, dados sensíveis, permissões, ou muitos estados.
**Perguntas (exemplos):**
- O que pode **dar errado** no caminho feliz? E fora dele?
- **Casos extremos:** vazio, muito grande, offline, sem permissão, dado duplicado?
- **Quem pode se prejudicar** com isso (usuário, suporte, outro time)?
- Qual o **pior cenário** aceitável, e o que é inaceitável?

## Saída — o bloco "Exploração & decisões"

Ao convergir, sintetize (curto, escaneável) e leve pro design/spec:

- **Problema (1 frase):** a dor real, enquadrada.
- **Ângulos levantados:** as opções que surgiram (bullets).
- **Suposições:** as que confirmamos e as que derrubamos.
- **Direção escolhida:** o insight que virou o caminho — e por quê.

Esse bloco:
1. **Alimenta as 2-3 abordagens** do passo seguinte (que ficam bem fundamentadas).
2. Vira uma **seção do spec** — `## Exploração & decisões` (contexto + alternativas consideradas).
3. Se o usuário pedir **Briefing**, o resumo das decisões entra lá também (em linguagem de
   negócio: "consideramos X e Y, escolhemos Z porque…") — ajuda a explicar o "porquê" a stakeholders.
