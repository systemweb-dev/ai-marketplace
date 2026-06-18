---
name: dead-code-scan
description: >
  Varre o projeto inteiro e identifica código não utilizado — imports/uses órfãos,
  variáveis e parâmetros mortos, funções/métodos/classes nunca chamados, arquivos que
  ninguém importa e dependências do manifesto sem uso. Agnóstica a linguagem: usa a
  ferramenta nativa de dead-code quando existe (knip/ts-prune, vulture/ruff, deadcode/
  staticcheck, PHPStan, cargo-machete, etc.) e cai pra heurística genérica quando não tem.
  Classifica cada achado por nível de confiança pra evitar falso positivo (pontos de entrada,
  API pública, reflexão/DI, mágica de framework, referências em strings/configs). Gera um
  relatório markdown e, com aprovação via menu, remove o código morto de forma guiada e
  verificada. Use SEMPRE que o usuário quiser uma VARREDURA de código não usado/morto no
  projeto — "tem código morto?", "limpa o que não é usado", "o que dá pra remover com
  segurança", "faz uma faxina/uma geral no projeto", "acha classes/métodos/variáveis/imports/
  arquivos sem uso", "dependências que não uso mais", "dead/unused code", "arquivos órfãos".
  Dispare mesmo sem a palavra "scan" — basta a intenção de descobrir o que está sem uso pra
  limpar. NÃO use para: revisar bugs ou qualidade do código (isso é code-review), refatorar
  uma função específica, tirar console.log/prints de debug pontuais, nem deletar um arquivo ou
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
3. **App ou lib?** — procure campo `exports`/`main`/`bin` no manifesto, `publish`/registry, README de biblioteca. **Isso muda a confiança de tudo que é exportado.** Se não der pra saber, **pergunte via `AskUserQuestion`** ("Esse projeto é um app final ou uma lib consumida por fora?") — a resposta calibra o relatório inteiro.
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

### Fase 4 — Classificar e montar o relatório

Aplique o modelo de confiança a cada achado e escreva o relatório markdown (template abaixo) em `dead-code-report.md` na raiz do projeto (ou onde o usuário preferir). Agrupado por **confiança** e, dentro, por **categoria**. Cada item com `arquivo:linha`, o trecho, e **por que** caiu naquela confiança.

### Fase 5 — Ação guiada (via AskUserQuestion)

Depois do relatório, **toda decisão de remover é um `AskUserQuestion`**, nunca pergunta em texto solto. Conduza assim:

1. Abra com um menu de rumo: **"Achei N itens (X alta, Y média, Z baixa). Como seguir?"** → opções: **Remover os de alta confiança** / **Revisar item a item** / **Só o relatório, não mexer** / **Outra categoria primeiro**.
2. **Comece sempre pela alta confiança.** Para cada item (ou grupo por arquivo), dispare `AskUserQuestion`: **Remover** / **Pular** / **Ver detalhe**. Agrupe imports/vars do mesmo arquivo num item só (são baratos e correlatos).
3. **Verifique após remover.** Se o projeto tem build/testes/typecheck, rode depois de cada lote de remoção pra confirmar que nada quebrou — reporte o resultado. Se quebrou, **reverta aquele item** e marque como falso positivo no relatório.
4. **Nunca remova baixa confiança automaticamente.** Só com override explícito do usuário, e ainda assim com verificação.
5. Ordem de risco (do mais seguro ao mais arriscado): imports → variáveis locais → funções/métodos privados → dependências → classes → arquivos. Respeite essa ordem ao sugerir.

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

## 🔴 Alta confiança — seguro remover
### Imports/uses
- `src/x.ts:12` — `import { foo } from './foo'` · foo não é usado no arquivo
### Funções/métodos/classes
- `src/util.py:40` — `def _helper()` · privado, 0 referências no repo

## 🟡 Média confiança — revisar
- `src/api.ts:8` — `export function legacy()` · 0 referências, mas é export de app (pode ser consumo externo)

## ⚪ Baixa confiança — provável falso positivo
- `src/handlers.py:5` — `class PaymentHandler` · 0 chamadas diretas, mas o nome aparece em `config/routes.yaml` (dispatch dinâmico)

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

## Limites

- Esta skill **lê o projeto e propõe remoções com aprovação** — não faz commit, não cria PR, não instala dependências sem aprovação, e nunca deleta baixa confiança sozinha.
- Heurística de texto tem teto: reflexão dinâmica montando nomes em runtime, geração de código e meta-programação pesada podem esconder usos. Quando precisão é crítica, prefira a ferramenta nativa e rode os testes após cada remoção.
