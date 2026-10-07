# Medição: dá para resolver o import sem ler configuração?

**Data:** 2026-10-07 · **Script:** [`medir-resolucao.py`](medir-resolucao.py) (recebe as raízes
dos projetos como argumento) · os projetos são reais e ficam sem nome aqui porque o
repositório é público.

## A pergunta

Resolver a string do import em arquivo exige, em tese, ler a configuração: PSR-4 do
`composer.json`, `paths` do `tsconfig`, apelidos do bundler. O problema é que num dos projetos
os apelidos moram num `vue.config.js` — **JavaScript executando**, não dado:

```js
alias: { '@Component': Path.resolve(__dirname + '/src/components'), … }
```

Daí a hipótese: e se a gente resolver pelos **arquivos que existem** em vez de pelo que alguém
declarou?

## O que existe, por tipo de import

| Projeto | apelidado | pacote | relativo |
|---|---|---|---|
| painel Vue | 338 | 290 | 54 |
| site institucional | — | 145 | 128 |
| aplicação Next.js | 640 | 532 | 222 |

| Projeto PHP | `use` interno (PSR-4) | `use` externo/global |
|---|---|---|
| API | 569 | 424 |
| sistema fiscal | 767 | 379 |

## Passo 3 — casar o sufixo contra o índice de arquivos

Sem ler configuração nenhuma:

| Projeto | único | ambíguo | relativo resolvido | não achou |
|---|---|---|---|---|
| painel Vue | 276 | 56 | 54 | 50 |
| site | 45 | 0 | 128 | 10 |
| Next.js | 640 | 0 | 222 | 111 |

**Os "não achou" são todos pacotes npm com escopo** (`@vue/test-utils`, `@playwright/test`,
`@supabase/supabase-js`) — eles não casam com arquivo do projeto.

> **Correção (mesma data).** A primeira leitura desta tabela foi que *"pacote se separa
> sozinho"*. Está errada, e a conta denuncia: são 682 imports no painel e só 436 aqui. Faltam
> os **246 de nome puro** (`vuex`, `vitest/config`), que o script nem classificou — e portanto
> nunca foram testados contra o índice. Medindo em seguida: `import 'server-only'` **casaria**
> com `tests/helpers/server-only.ts`, oito vezes, num projeto real. Builtin do Node (`path`,
> `fs`, `url`) é a mesma armadilha com nome de utilitário comum. **Nome puro tem que ser
> externo por regra**, com a única exceção do `baseUrl` declarado e conferido.

## Passo 4 — inferir o apelido a partir do que já resolveu

Para cada prefixo, pega os imports que resolveram sozinhos e calcula a **base** (o destino
menos o sufixo que casou). Uma base está **provada** para um prefixo quando **≥ 5** imports
daquele prefixo resolveram sozinhos sob ela; o ambíguo resolve se **exatamente um** dos seus
candidatos está sob base provada. **Sem voto de maioria** — a primeira versão usava 80% de
concordância, e uma concordância de 80% é a prova explícita de que o prefixo nem sempre cai na
mesma pasta, que é onde a aresta errada nasceria. Medido: as duas regras desempatam 56 de 56.

No painel Vue:

```
@          -> src              (152 provas, 100% de concordância)
@Component -> src/components   (104 provas, 100%)
@View      -> src/views        ( 15 provas, 100%)
@Assets    -> src/assets       (  5 provas, 100%)
```

**Desempatou 56 dos 56 ambíguos.** E os quatro apelidos inferidos são **exatamente** os que
estão escritos no `vue.config.js` — o método redescobriu a configuração sem abrir o arquivo.

## O que isso decide

1. **A resolução é por evidência**, e a configuração vira atalho opcional e conferível. O
   risco número um do item D — apelido dentro de JavaScript executável — deixa de existir.
2. **O painel Vue vai de 76% para 100%** dos imports internos resolvidos; o Next.js já estava
   em 100%; o PHP tem PSR-4 declarado e resolve por substituição de prefixo.
3. **O limiar de 5 provas está no lugar certo, por pouco:** `@Assets` tem exatamente 5. Abaixo
   disso entra ruído; acima, perde-se um apelido real. É o **único** limiar do resolvedor.
4. **O limiar de concordância foi removido do desenho.** A primeira versão desta medição usava
   voto de maioria (≥ 80%) para desempatar. Uma concordância de 80% é a prova explícita de que
   aquele prefixo *nem sempre* cai na mesma pasta — e forçar o ambíguo para a maioria é
   exatamente onde a aresta errada nasceria, contra a invariante do trabalho. A regra por base
   provada dá o mesmo 56 de 56 sem o palpite.

## O que isto NÃO prova

Os cinco projetos são do mesmo dono e três deles usam o framework PHP da casa. O método é
genérico por construção, mas a medição não é uma amostra do mundo — ela mostra que a
abordagem se sustenta, não que o número se repete em qualquer projeto. Por isso a **taxa de
resolução** entra no documento gerado: cada execução publica o próprio número.
