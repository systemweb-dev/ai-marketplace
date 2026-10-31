---
name: sw-dead-code-scan
description: >
  Varre o projeto inteiro e identifica código não utilizado — imports/uses órfãos,
  variáveis e parâmetros mortos, funções/métodos/classes nunca chamados, arquivos que
  ninguém importa, dependências do manifesto sem uso e COMENTÁRIO desnecessário — inclusive
  o comentário que assistente de IA deixa: narração cerimonial ("Esta função é responsável
  por…", "Agora vamos…", "Retorna o resultado"), comentário comprido e genérico sem nada
  concreto, comentário EMPILHADO em cima de outro sobre o mesmo código, além de código
  comentado, repetição do que a linha já diz, divisória, lixo de scaffold e docblock que não
  bate com a assinatura. Agnóstica a linguagem: usa a
  ferramenta nativa de dead-code quando existe (knip/ts-prune, vulture/ruff, deadcode/
  staticcheck, PHPStan, cargo-machete, etc.) e cai pra heurística genérica quando não tem.
  Classifica cada achado por nível de confiança pra evitar falso positivo (pontos de entrada,
  API pública, reflexão/DI, mágica de framework, referências em strings/configs). Gera um
  relatório markdown e, com aprovação via menu, remove o código morto de forma guiada e
  verificada. Use SEMPRE que o usuário quiser uma VARREDURA de código não usado/morto no
  projeto — "tem código morto?", "limpa o que não é usado", "o que dá pra remover com
  segurança", "faz uma faxina/uma geral no projeto", "acha classes/métodos/variáveis/imports/
  arquivos sem uso", "dependências que não uso mais", "dead/unused code", "arquivos órfãos".
  Para comentários, dispara com "remove os comentários desnecessários", "limpa os
  comentários", "tem código comentado?", "tira os comentários inúteis/obsoletos", "comentário
  que não serve pra nada", "remove comentário morto", "dead comments", "a IA encheu de
  comentário", "comentário em cima de comentário", "comentário grande que não diz nada",
  "tira a narração do código", "limpa o que o Claude/Copilot comentou". Nunca remove o
  comentário que explica POR QUE, a licença, nem a diretiva que o linter/compilador/framework
  lê (`# type: ignore`, `// eslint-disable`, `//go:build`, `@ORM\Column`). Dispare mesmo sem a
  palavra "scan" — basta a intenção de descobrir o que está sem uso pra limpar. NÃO use para:
  revisar bugs ou qualidade do código (isso é sw-code-review), refatorar uma função
  específica, tirar console.log/prints de debug pontuais, nem deletar um arquivo ou
  dependência que o usuário JÁ decidiu remover — aqui o foco é *descobrir por varredura* o que
  está morto, não executar uma remoção já decidida. Interação e relatório em português (PT-BR).
---

# Dead Code Scan

Encontrar código não utilizado em qualquer projeto, de qualquer linguagem, **sem deletar coisa viva por engano**. Esse "sem deletar coisa viva" é a alma da skill: o desafio real não é achar o que parece morto — é distinguir o que está *de fato* morto do que só *parece*.

## O princípio que governa tudo: falso positivo mata

Um detector ingênuo ("buscar o símbolo; se tem 0 referências, é morto") apaga código que está em uso por caminhos que a busca textual não vê. Antes de classificar qualquer coisa como morta, **descarte estas armadilhas** — cada uma é uma fonte clássica de falso positivo:

- **Pontos de entrada** — `main`, `index.*`, `app.*`, binários/CLI, handlers de rota, jobs, listeners, migrations, seeders. Ninguém os "chama" no código, mas o framework/runtime chama.
- **API pública** — se o projeto é uma **lib** (tem campo `exports`/`main` no manifesto, é publicado), tudo que ela exporta é "usado" por consumidores fora do repo. Exportado de lib ≠ morto.
- **Reflexão / injeção de dependência / dispatch dinâmico** — chamado por **nome em string** em runtime: container de DI (Spring, Laravel), `getattr`/`__import__`, `Class.forName`, nomes de rota, eventos, `method_exists`.
- **Mágica de framework** — decorators/annotations (`@Component`, `@app.route`, `@Entity`), métodos de ciclo de vida (`ngOnInit`, `componentDidMount`, `__init__`), campos de serialização (DTOs, ORM), hooks.
- **Referências fora do código "normal"** — templates (Blade, JSX, ERB), configs (YAML/JSON/TOML), SQL, i18n, strings dinâmicas. Se o nome aparece numa string em qualquer lugar, trate como possivelmente vivo.
- **Polimorfismo** — método que implementa interface/abstrato ou faz override: usado por despacho dinâmico, mesmo sem chamada direta.
- **Uso só em teste** — usado apenas por testes não é "morto" do ponto de vista do teste; mas vale anotar (pode indicar feature sem uso em produção).

Por isso a skill **nunca** entrega uma lista chapada de "remova isto". Ela entrega achados **classificados por confiança** (alta/média/baixa) e só remove com aprovação, começando pelo mais seguro.

### Comentário tem a assimetria pior

Código apagado por engano volta: do git, dos testes, do comportamento do sistema. O comentário que registrava **por que** a linha é daquele jeito — o bug contornado, o trade-off, o número da issue — é a **única cópia** dessa informação que existe. Então nesta categoria a política é mais conservadora que no resto da skill, e deliberadamente assimétrica: a lista do que **fica** é maior que a do que sai, e o que não foi *provado* desnecessário fica.

Duas coisas que todo mundo confunde, e que mudam o resultado:

- **Diretiva não é comentário, é código.** `# type: ignore`, `// eslint-disable-next-line`, `//go:build linux`, `# frozen_string_literal: true`, `/*!40101 SET … */` num dump MySQL e um docblock com `@ORM\Column` (que **é** o schema do banco) são lidos por ferramenta ou framework. Remover muda comportamento ou quebra o build.
- **A suíte verde não prova que o comentário podia sair.** Teste nenhum lê comentário. Quem denuncia diretiva removida por engano é **lint, typecheck e build** — são eles o oráculo aqui.

O catálogo completo — o que nunca sai, por ecossistema, e o que sai com que sinal — está em **`references/comentarios.md`**. **Leia antes de propor a remoção de qualquer comentário.**

## Modelo de confiança

Atribua um nível a cada achado:

- 🔴 **Alta** — escopo **privado/local**, **0 referências** em qualquer lugar (código E strings/configs), não é ponto de entrada nem mágica de framework, e (quando há ferramenta nativa) ela **também** aponta. Ex.: import não usado, variável local nunca lida, método privado nunca chamado. *Seguro remover.*
- 🟡 **Média** — 0 referências, mas é **público/exportado num app** (não lib), ou só a ferramenta nativa **ou** a heurística apontou (não as duas), ou tem cara de framework mas sem confirmação. *Revisar antes.*
- ⚪ **Baixa** — exportado de **lib**, ou o nome **aparece em string/config**, ou é arquivo tipo-entrypoint, ou há indício de dispatch dinâmico. *Provável falso positivo — só com contexto humano.*

Na dúvida entre dois níveis, **escolha o mais baixo** (mais conservador). É barato manter código morto mais um dia; é caro deletar código vivo.

## Workflow

### Fase 1 — Mapear o projeto

Antes de procurar qualquer coisa, entenda o terreno:

1. **Linguagens e proporção** — pelas extensões e arquivos de config. Trate cada linguagem como uma sub-varredura.
2. **Gerenciadores/manifestos** — `package.json`, `composer.json`, `requirements.txt`/`pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`/`build.gradle`, `*.csproj`, `Gemfile`. Daqui saem as dependências.
3. **App ou lib?** — procure campo `exports`/`main`/`bin` no manifesto, `publish`/registry, README de biblioteca. **Isso muda a confiança de tudo que é exportado — e dos docblocks:** em lib, o docblock de um símbolo exportado é o **manual publicado**, lido por quem consome de fora e compilado pelo gerador de documentação. Se não der pra saber, **pergunte via `AskUserQuestion`** ("Esse projeto é um app final ou uma lib consumida por fora?") — a resposta calibra o relatório inteiro.
4. **Pontos de entrada e zonas mágicas** — identifique mains, rotas, controllers, migrations, DI/config. Esses ficam fora da varredura agressiva.

### Fase 2 — Escolher a estratégia por linguagem

Para cada linguagem, **prefira a ferramenta nativa de dead-code** — ela entende o AST e erra muito menos que busca textual. Veja a tabela completa em **`references/native-tools.md`** (ferramenta, como invocar, o que pega, como instalar). Regra:

- **Ferramenta nativa instalada/disponível** → rode-a; use a saída como base de **alta** confiança.
- **Não instalada mas trivial de rodar** (ex.: `npx knip`, `uvx vulture`, `ruff`) → ofereça rodar via `AskUserQuestion` ("Posso rodar `knip` pra uma varredura precisa de TS?"). Não instale dependência no projeto sem aprovação.
- **Sem ferramenta** → caia para a **heurística genérica** abaixo.

Idealmente combine: ferramenta nativa **+** heurística. Quando as duas concordam, é alta confiança; quando só uma aponta, é média.

### Fase 3 — Heurística genérica (o núcleo agnóstico)

Quando não há ferramenta nativa, busque por categoria. Use `rg` (ripgrep) se disponível, senão `grep -r`. Sempre com **fronteira de palavra** (`\b`) pra não casar substring.

- **Imports/uses não usados** — para cada símbolo importado num arquivo, verifique se ele aparece **naquele arquivo fora da linha de import**. Se não aparece → candidato (alta, é local e seguro).
- **Variáveis/parâmetros mortos** — declarados e nunca lidos no escopo. Difícil 100% sem AST; foque em locais óbvios; deixe pra ferramenta nativa quando precisão importa.
- **Funções/métodos/classes** — pegue o nome definido (`function foo`, `def foo`, `class Foo`, `func foo`…) e conte referências `\bfoo\b` no repo **menos** a própria definição. 0 referências → candidato. Aplique os guards (privado vs público, string-refs, override, entrypoint).
- **Arquivos órfãos** — um arquivo é órfão se seu nome/caminho de módulo **nunca** é importado/required/included em lugar nenhum **e** não é entrypoint (main/index/config/migration/teste). Cheque também referências por string (lazy import, rotas).
- **Dependências não usadas** — para cada dependência do manifesto, busque um import/require do pacote no código-fonte (não nos lockfiles). 0 → candidato (cuidado com deps usadas só em build/CLI/peer).

**Antes de registrar cada candidato, rode os guards da seção "falso positivo".** Um candidato cujo nome aparece numa string, ou que é exportado de lib, ou que tem decorator de framework → desce pra média/baixa, não some da lista.

### Fase 3b — Comentários (categoria própria, script próprio)

Comentário não se acha com `grep '^\s*//'`: a busca textual casa `//` dentro de
`url(http://cdn/x.png)`, `#` dentro de `${#lista}` e `#` dentro de `"""docstring"""` — e
cortar dali corta código vivo. Rode o analisador:

```bash
python3 <skill-dir>/scripts/comentarios.py --projeto .            # resumo por classe
python3 <skill-dir>/scripts/comentarios.py --projeto . --json     # com id, offset e sinal
```

Ele lê o projeto com um analisador léxico por família de sintaxe, agrupa linhas de comentário
seguidas num comentário só, e devolve cada achado com **a classe, o sinal que a decidiu e a
confiança**. Extensão que ele não conhece vira **lacuna com motivo** no resumo — não apurado ≠
não existe.

| Classe | Confiança | Ação |
|---|---|---|
| `diretiva` · `licenca` · `porque` · `legenda` · `marcador` · `pendencia` | 🛡 protegido | **manter** — nem entram na lista |
| `codigo_comentado` · `redundante` · `divisoria` · `scaffold` | 🔴 alta | remover com aprovação |
| `contradiz` | 🟡 média | **corrigir**, não remover: o docblock passa a dizer a assinatura |
| `orfao` · `gerador` | 🟡 média | decidir com contexto |
| `doc` · `prosa` | ⚪ baixa | o humano lê; `doc` depende de app ou lib (Fase 1) |

**Os três padrões de comentário de assistente** — o motivo pelo qual esta fase existe, porque
nenhum deles é código comentado nem repetição curta:

| Classe | O que é | Ação |
|---|---|---|
| `narracao` | conta o que o código faz: `Esta função é responsável por…`, `Agora vamos…`, `Primeiro,`, `Note que`, `Helper para`, `# Imports`, `Tratamento de erro`, `Retorna o resultado` | 🔴 alta quando é curta, repete a assinatura ou é ≥70% genérica **e não cita nada concreto**; 🟡 média quando cita — aí pode estar informando |
| `vago` | ≥10 palavras e **nenhuma âncora**: sem número, sem identificador, ≤30% fora do vocabulário genérico | 🟡 média |
| `empilhado` | 2+ comentários sobre a **mesma linha**, ou 2+ frases independentes no mesmo bloco | 🟡 **fundir**, não remover — exceto a camada que repete outra quase palavra por palavra, que sai |

A medida de `vago` é a **âncora, não a sobreposição com o código**. A primeira versão media
"fala de outra coisa que não a linha"; lida num projeto real, acusou dez comentários e **os
dez eram "porquê"** — sobreposição baixa é a assinatura do bom comentário de motivo, que fala
da razão e não da mecânica. Quem tem o que dizer cita alguma coisa.

**O trabalho que é seu, não do script:** a classe `prosa` é a maior de todas num projeto real,
e é de propósito — ela significa "não foi provado desnecessário". Leia-a com contexto e
proponha só o que você consegue justificar numa frase. **Não trate `prosa` como lista de
remoção**, e não some os números dela no total de candidatos.

Numa rodada real de 1.291 arquivos: 3.370 comentários, **33 candidatos de alta** e 19 de
média — contra 416 protegidos por explicarem um motivo. Na skill desta casa cujos comentários
são todos "porquê", **nenhum candidato de alta** e 2 `empilhado` de média.

### Fase 4 — Classificar e montar o relatório

Aplique o modelo de confiança a cada achado e escreva o relatório markdown (template abaixo) em `dead-code-report.md` na raiz do projeto (ou onde o usuário preferir). Agrupado por **confiança** e, dentro, por **categoria**. Cada item com `arquivo:linha`, o trecho, e **por que** caiu naquela confiança.

### Fase 5 — Ação guiada (via AskUserQuestion)

Depois do relatório, **toda decisão de remover é um `AskUserQuestion`**, nunca pergunta em texto solto. Conduza assim:

1. Abra com um menu de rumo: **"Achei N itens (X alta, Y média, Z baixa). Como seguir?"** → opções: **Remover os de alta confiança** / **Revisar item a item** / **Só o relatório, não mexer** / **Outra categoria primeiro**.
2. **Comece sempre pela alta confiança.** Para cada item (ou grupo por arquivo), dispare `AskUserQuestion`: **Remover** / **Pular** / **Ver detalhe**. Agrupe imports/vars do mesmo arquivo num item só (são baratos e correlatos).
3. **Verifique após remover.** Se o projeto tem build/testes/typecheck, rode depois de cada lote de remoção pra confirmar que nada quebrou — reporte o resultado. Se quebrou, **reverta aquele item** e marque como falso positivo no relatório. **Em comentário, o oráculo é outro:** teste nenhum lê comentário, então a suíte verde não prova nada — rode **lint, typecheck e build**, que são o que denuncia diretiva removida por engano.
4. **Nunca remova baixa confiança automaticamente.** Só com override explícito do usuário, e ainda assim com verificação.
5. Ordem de risco (do mais seguro ao mais arriscado): **comentários de alta** → imports → variáveis locais → funções/métodos privados → dependências → classes → arquivos. Respeite essa ordem ao sugerir.
6. **Comentário sai por recorte, nunca por regex sobre o arquivo cru:**

   ```bash
   # grave em escolhas.json só os achados aprovados (como saem do --json)
   python3 <skill-dir>/scripts/comentarios.py --projeto . --aplicar escolhas.json
   ```

   O `--aplicar` **recusa** cortar quando o texto do arquivo não é mais, byte a byte, o que foi
   apurado — offset velho corta no lugar errado —, e preserva a quebra de linha do arquivo.
   Num arquivo CRLF, reescrever com tradução de newline traz **todas** as linhas para o diff:
   num arquivo real de 280 linhas, tirar um comentário de uma linha trouxe as 280. Diff
   inflado é revisão impossível, e é aí que um erro de verdade passa sem ser visto.
7. **Olhe o diff antes de commitar.** É a última guarda, e a única que pega o que nenhuma regra
   pegou.

### Fase 6 — Resumo

Feche com: quantos achados por confiança/categoria, quantos removidos/pulados/falsos positivos, e o resultado do build/testes. Atualize o `dead-code-report.md` marcando o que foi tratado.

## Template do relatório

```markdown
# Relatório de código não utilizado — <projeto>
<data> · linguagens: <X, Y> · estratégia: <nativa (ferramenta) / heurística / híbrida> · tipo: <app | lib>

## Resumo
| Categoria              | 🔴 Alta | 🟡 Média | ⚪ Baixa |
|------------------------|--------:|---------:|--------:|
| Imports/uses           |       0 |        0 |       0 |
| Variáveis/parâmetros   |       0 |        0 |       0 |
| Funções/métodos/classes|       0 |        0 |       0 |
| Arquivos órfãos        |       0 |        0 |       0 |
| Dependências           |       0 |        0 |       0 |
| Comentários            |       0 |        0 |       0 |

Comentários protegidos (fora da lista): <N> diretiva · <N> licença · <N> porquê · <N> legenda
· <N> marcador · <N> pendência. Em `prosa`: <N> — não provados desnecessários.

## 🔴 Alta confiança — seguro remover
### Imports/uses
- `src/x.ts:12` — `import { foo } from './foo'` · foo não é usado no arquivo
### Funções/métodos/classes
- `src/util.py:40` — `def _helper()` · privado, 0 referências no repo
### Comentários
- `app/Email.php:19` — `//$this->mail->SMTPDebug = SMTP::DEBUG_SERVER;` · código desativado; o git guarda esta versão
- `src/conta.ts:12` — `// incrementa o contador` sobre `contador++` · toda palavra já está na linha

## 🟡 Média confiança — revisar
- `src/api.ts:8` — `export function legacy()` · 0 referências, mas é export de app (pode ser consumo externo)

## ⚪ Baixa confiança — provável falso positivo
- `src/handlers.py:5` — `class PaymentHandler` · 0 chamadas diretas, mas o nome aparece em `config/routes.yaml` (dispatch dinâmico)
- `src/util.py:88` — `# ver AuthLegacyService` · cita símbolo que não existe mais, mas pode ser classe de biblioteca

## Como foi detectado / limitações
- Ferramenta(s): <knip 5.x / heurística rg>
- Não cobre: <reflexão por string montada em runtime, geração de código, etc.>
```

## Guards de falso positivo (checklist por candidato)

Antes de manter um achado como **alta**, confirme que ele **não** é nenhum destes (se for, desça a confiança):

1. É ponto de entrada (main/index/rota/CLI/job/migration)?
2. É exportado e o projeto é lib?
3. O nome aparece em **alguma string** do repo (config, template, SQL, i18n, DI)?
4. Tem decorator/annotation de framework, ou é método de ciclo de vida / serialização?
5. Implementa interface/abstrato ou faz override (polimorfismo)?
6. É usado só em testes (vivo, mas anotar)?
7. É dependência de build/peer/CLI que não aparece como import direto?

**Se o candidato é comentário, some estas sete** (detalhe e catálogo por ecossistema em
`references/comentarios.md`):

8. É **diretiva** — alguma ferramenta, compilador ou framework LÊ esta linha?
9. Explica **por que**, cita issue/CVE/link, avisa, ou traz medida ou ordem que importa?
10. É **licença**, copyright, SPDX ou atribuição exigida pela licença de um asset?
11. É **legenda** de regex, bits ou fórmula — aquilo que o código não deixa ler?
12. É **marcador de estrutura** (`# Arrange/Act/Assert`, faixa de seção) ou dívida registrada com conteúdo?
13. É **doc de API** e o projeto é **lib** (então é o manual publicado)?
14. O comentário **mente** sobre a assinatura? Então o conserto é **corrigir**, não remover.
15. É `empilhado`? Então a ação é **fundir** — cada camada pode ter um pedaço da informação.

## Limites

- Esta skill **lê o projeto e propõe remoções com aprovação** — não faz commit, não cria PR, não instala dependências sem aprovação, e nunca deleta baixa confiança sozinha.
- Heurística de texto tem teto: reflexão dinâmica montando nomes em runtime, geração de código e meta-programação pesada podem esconder usos. Quando precisão é crítica, prefira a ferramenta nativa e rode os testes após cada remoção.
- Em comentário: **docstring de Python e Ruby não são lidas** (remover muda `__doc__` e pode quebrar doctest); Ruby heredoc, regex de JS com `/*` dentro de classe de caractere e `.php` com HTML entremeado não são reconhecidos perfeitamente — por isso o `--aplicar` confere o texto antes de cortar, e o pior caso é recusar, não corromper. Markdown, JSON, CSV e SVG ficam fora de propósito. `orfao` por texto é fraco e nunca sobe para alta.
