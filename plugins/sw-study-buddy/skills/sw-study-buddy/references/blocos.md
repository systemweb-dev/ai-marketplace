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
