# Blocos reutilizáveis da apostila

**Vocabulário:** **Tema** (o assunto, ex.: Go) → **Módulo** (uma *fase* que agrupa, ex.: "Fundamentos")
→ **Tópico** (cada item de estudo da trilha, ex.: "Setup + primeiro programa"). O **tópico é a unidade
de conteúdo** — cada um tem seu fragmento e vira uma página/section. Os tópicos são numerados
globalmente na ordem (1..N); o fragmento de cada tópico é `topicos/<seq>.html` (ex.: `topicos/01.html`).
A sidebar mostra os módulos como cabeçalhos de grupo e os tópicos como itens numerados sob eles.

Uso de `<h3>` por modo: na **apostila** (Aprender) são subseções de leitura dentro do tópico (não entram na sidebar). Nas **fichas** (Explicar) cada `<h3>` é uma **seção da explicação** e vira um item do **índice lateral** (que aparece quando há 2+ seções) — por isso, no modo Explicar, estruture a explicação em `<h3>`.

Estes são os "componentes" do template. Use-os ao escrever cada `topicos/NN.html`
(que contém só o **miolo** do tópico — o cabeçalho com eyebrow do módulo, título e meta é
injetado automaticamente pelo `build_study_page.py` a partir do `meta.json`, então **não**
repita `<h2>` do título do tópico no fragmento).

Todos são HTML puro estilizado pelo CSS do template. Mantenha a semântica e as classes exatas.

## Code block com label de arquivo
Use quando o código pertence a um arquivo nomeado (dá contexto de "onde isso mora").
```html
<div class="codeblock">
  <div class="codeblock__file">main.go</div>
  <pre><code class="language-go">package main

func main() {
    // ...
}</code></pre>
</div>
```
Para um trecho solto sem arquivo, um `<pre><code class="language-xxx">…</code></pre>` simples basta.

## Callout (nota / aviso / dica)
Variantes: padrão (nota), `.warning`, `.tip`.
```html
<div class="callout">
  <span class="callout__label">Nota</span>
  <p>Texto da observação.</p>
</div>

<div class="callout warning">
  <span class="callout__label">Cuidado</span>
  <p>Armadilha comum que pega quem está aprendendo.</p>
</div>

<div class="callout tip">
  <span class="callout__label">Dica</span>
  <p>Atalho prático, ex.: rodar via Docker sem instalar nada.</p>
</div>
```

## Conceito-chave
Para a definição central do módulo — destaque editorial em itálico.
```html
<div class="keyconcept">
  <span class="label">Conceito-chave</span>
  <p>Em Go, o ponto de entrada é sempre <code>package main</code> + <code>func main()</code>.</p>
</div>
```

## Comparação lado-a-lado
Ótimo pra contrastar a linguagem nova com o que a pessoa já sabe (ex.: PHP ↔ Go).
Marque o lado "novo" com `is-accent`.
```html
<div class="compare">
  <div class="compare__side">
    <div class="compare__head">PHP</div>
    <div class="compare__body">
      <pre><code class="language-php">echo "olá";</code></pre>
    </div>
  </div>
  <div class="compare__side is-accent">
    <div class="compare__head">Go</div>
    <div class="compare__body">
      <pre><code class="language-go">fmt.Println("olá")</code></pre>
    </div>
  </div>
</div>
```

## Card de exercício
Fecha o módulo com prática. O enunciado vai aqui; a resolução acontece no chat.
```html
<div class="exercise">
  <span class="exercise__tag">Exercício</span>
  <h4>Título curto do desafio</h4>
  <p>Enunciado. Peça pra pessoa tentar antes de revelar a resposta.</p>
</div>
```

## Dica em spoiler (modo Praticar)
Esconde a dica até a pessoa clicar — preserva o esforço produtivo. Usado nas fichas de prática.
```html
<details class="hint">
  <summary>Dica</summary>
  <div class="body">
    <p>A pista vai aqui. Pode dar uma escada: <code>&lt;details&gt;</code> separados pra dica 1, dica 2…</p>
  </div>
</details>
```

## Card de quiz
Perguntas conceituais. Opções com `<ol class="options">` ganham marcadores A, B, C…
```html
<div class="quiz">
  <span class="quiz__tag">Quiz</span>
  <h4>O que acontece se você omitir <code>func main()</code>?</h4>
  <ol class="options">
    <li>Compila e roda normalmente</li>
    <li>Erro de compilação: falta o ponto de entrada</li>
    <li>Roda, mas não imprime nada</li>
  </ol>
</div>
```

> Lembre: a página é material de leitura. A correção de exercícios/quiz e o vai-e-volta
> socrático acontecem **no chat**, não na página (HTML não escuta a resposta).

---

## Blocos dos modos de retenção (fichas `--kind` novos)

### Flashcard (ficha `--kind flashcards`, em `revisoes/`)
Pergunta no `<summary>`, resposta no flip — a pessoa tenta antes de revelar (esforço
produtivo). Vários cards viram uma grade automaticamente:
```html
<div class="flashcards">
  <details class="flashcard">
    <summary>O que acontece se eu omitir a <code>func main()</code> em um binário Go?</summary>
    <div class="body"><p>Erro de compilação: falta o ponto de entrada.</p></div>
  </details>
  <details class="flashcard">
    <summary>Por que a interface em Go é implícita (sem <code>implements</code>)?</summary>
    <div class="body"><p>Qualquer tipo que tem os métodos satisfaz — o acoplamento é no
      consumidor, não no produtor.</p></div>
  </details>
</div>
```
Cards bons: "o que acontece se…", diferença entre dois conceitos, falsos amigos. 5–10 por módulo.

### Placar + lista de prova (ficha `--kind exame`, em `exames/`)
Placar em destaque + cada item marcado ok/errado (o "porquê" do erro no `<small>`):
```html
<div class="exam-score"><b>4/5</b><span>prova do módulo 1 · fundamentos</span></div>
<ul class="exam-list">
  <li class="ok">Pacotes e importação — acertou</li>
  <li class="miss">Ordem de drop em escopo<small>confundiu LIFO com ordem de declaração</small></li>
  <li class="ok">Slices: fundo vs. capacidade</li>
  <li class="ok">Estruturas e métodos</li>
  <li class="ok">Interfaces implícitas</li>
</ul>
```
Errados também entram em `fracos` via `review.py --action exam --missed …`.

### Glossário (ficha `--kind glossario`, em `glossario/`)
Não tem fragmento: o script lê `<dir>/glossario.json` e gera a página (nome fixo
`glossario.html`, link na sidebar da apostila):
```json
[
  {"termo": "goroutine", "def": "Thread leve gerenciada pelo runtime Go; começa com ~2KB e escala.", "topico": 4},
  {"termo": "channel", "def": "Tubo tipado pra comunicação entre goroutines (CSP).", "topico": 5}
]
```
`termo` + `def` são obrigatórios; `topico` (número) é opcional e vira etiqueta.

### Mapa do módulo (ficha `--kind mapa`, em `mapas/`)
SVG **inline** com 5–12 nós (os conceitos do módulo) e arestas de dependência
("X precisa de Y"). Use os **tokens do tema** nos fills/strokes — assim o mapa segue
light/dark automaticamente:
```html
<svg viewBox="0 0 760 360" xmlns="http://www.w3.org/2000/svg">
  <line x1="120" y1="80" x2="360" y2="80" stroke="var(--line)" stroke-width="2"/>
  <rect x="40" y="50" width="160" height="60" rx="12" fill="var(--tint)" stroke="var(--accent)"/>
  <text x="120" y="85" text-anchor="middle" fill="var(--ink)" font-family="Hanken Grotesk" font-size="15" font-weight="600">Pacotes</text>
  <rect x="360" y="50" width="180" height="60" rx="12" fill="var(--accent-wash)" stroke="var(--accent)"/>
  <text x="450" y="85" text-anchor="middle" fill="var(--accent-dk)" font-family="Hanken Grotesk" font-size="15" font-weight="700">Goroutines</text>
</svg>
```
Regras: nós do centro pra fora (base → avançado), arestas finas `var(--line)`, nó
destacado com `var(--accent-wash)` + borda `var(--accent)`, `viewBox` larga (≥720 de
largura) — o `min-width` do SVG já vem do CSS (`.map`).
