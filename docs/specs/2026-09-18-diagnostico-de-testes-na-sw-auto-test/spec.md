---
titulo: Diagnóstico de testes na sw-auto-test
slug: 2026-09-18-diagnostico-de-testes-na-sw-auto-test
criado: 2026-09-18
estado: concluido
---

# Diagnóstico de testes na sw-auto-test

## Objetivo & outcome

A `sw-auto-test` gera testes, mas nunca olha para os que já existem nem prova o que escreveu.
Este trabalho dá a ela um segundo modo — **diagnosticar** — e fecha os furos da geração.

**Outcome:** quem roda a skill sai sabendo **o que na suíte não presta e o que consertar
primeiro**, com cada achado apontando `arquivo:linha`. Mede-se por: todo achado de confiança alta
é verificável por ferramenta (não por opinião), e nenhum teste gerado passa quando o
comportamento que ele descreve está quebrado.

## Decisões do usuário (fechadas)

| Tema | Decisão |
|---|---|
| Onde mora | Mesma skill, dois modos: **gerar** e **diagnosticar** |
| Alcance do diagnóstico | Relatório + **correção guiada por menu**, em lotes |
| Execução da suíte | Só com confirmação; por padrão unitária + cobertura. Integração e e2e só sob pedido |
| Apuração | Ferramenta nativa quando existir, script fino normalizando, agente julgando o resto |
| Stacks nativas na v1 | **PHP (phpunit), JS/TS (vitest/jest), Python (pytest)**; o resto pelo caminho heurístico |
| Prova do vermelho | **No lugar**, com backup do original e checagem de resíduo |
| Monorepo | Pacote afetado por padrão, com oferta de ampliar para o repositório |
| Idioma | Gatilhos PT-BR na `description`; corpo da skill segue em inglês |

## Arquitetura

```
/sw-auto-test
  modo gerar        (o que já existe) + baseline, prova do vermelho, regras de qualidade
  modo diagnosticar (novo)
     1. agente   escopo (pacote/repo) e stacks; pergunta o que executar
     2. diagnose.py  → <git-path>/sw-auto-test/fatos.json   [--executar] [--cobertura]
     3. agente      → lê fatos + só os arquivos suspeitos → <git-path>/sw-auto-test/achados.json
     4. report.py   → <raiz>/test-health-report.md  (+ linha em <git-path>/info/exclude)
     5. agente      → menu de correção em lotes, suíte a cada lote, revert por backup
```

`<git-path>` vem de `git rev-parse --git-path`; sem git, a pasta de fatos vai para o temp do
sistema e a prova do vermelho **não roda**. O relatório é sempre na raiz do escopo diagnosticado.

### Unidades

| Unidade | Responsabilidade | Não faz |
|---|---|---|
| `scripts/diagnose.py` | Detectar stacks, inventariar, rodar detectores, chamar a ferramenta nativa, normalizar para o schema, gravar `fatos.json` | Julgar, escrever relatório, alterar teste |
| `scripts/report.py` | Validar `achados.json` contra `fatos.json` e montar o `test-health-report.md` | Decidir o que é problema |
| `scripts/lib/stacks/*.py` | Um módulo por stack nativa (php, js, py): comando, parsing da saída, cobertura | Conhecer outras stacks |
| `scripts/lib/sinais.py` | Detectores textuais que valem para qualquer linguagem | Parsing sintático profundo |
| `scripts/lib/backup.py` | Guardar o original antes de qualquer edição, restaurar, e varrer resíduo no início de toda execução | Decidir o que editar |
| `SKILL.md` | Conduzir: roteamento entre modos, perguntas, julgamento, correção guiada | Apurar fatos |
| `references/` | Matriz de frameworks, exemplos AAA por linguagem, detalhes da geração | — |

**Contrato do script (limite contra o inchaço):** ele **roda a ferramenta nativa e normaliza**
para um schema versionado. Detector que exigiria entender a sintaxe da linguagem vira: (a) regra
de plugin de lint, quando o projeto tiver (`eslint-plugin-vitest`, `flake8-pytest-style`,
PHPStan), ou (b) marcação de **suspeito** para o agente ler. O script nunca vira um parser.

## Modo diagnóstico

### Fase 1 — Escopo e stacks

Reaproveita a detecção que já existe (linguagem, framework, diretórios por tipo) e acrescenta
quais **ferramentas nativas estão instaladas**. Em monorepo, o padrão é o pacote em que o usuário
está ou que ele apontou; a oferta de ampliar para o repositório é um menu.

### Fase 2 — Apurar (`diagnose.py`)

Sem `--executar`, o script **não cria nenhum processo de runner**: só inventário e detectores
textuais. Com `--executar`, roda nesta ordem:

1. **Descoberta** (`pytest --collect-only`, `jest --listTests`, `vitest list`, `phpunit --list-tests`).
   Revela teste que **nunca roda** por estar fora do padrão de descoberta. **Também é execução:**
   a coleta importa `conftest.py`, setup de suíte e bootstrap, que podem tocar banco. Por isso a
   **detecção de DSN/env de banco acontece antes da descoberta**, e a descoberta também depende da
   confirmação — ela é apenas a opção mais barata, não uma opção inofensiva.
2. **Suíte unitária**, com timeout. O comando exato e a configuração/env detectada são mostrados
   **antes** da confirmação. Havendo DSN ou variável de banco no ambiente de teste, **segunda
   confirmação** — "unitário" não garante ausência de efeito colateral: `conftest`/bootstrap pode
   truncar banco.
3. **Cobertura**, quando a ferramenta existir.

Estouro de timeout **vira achado**, não trava a skill.

**Onde a saída do runner é gravada:** sempre na pasta de fatos, por flag explícita
(`--cov-report=xml:<pasta>/cobertura.xml`, `--log-junit <pasta>/junit.xml`,
`--reporter=json --outputFile=<pasta>/vitest.json`). O que o runner cria por conta própria
(`.pytest_cache`, `.phpunit.cache`, `coverage/`) é **exceção declarada**: a skill não cria nem
remove, e o relatório lista o que apareceu. Fingir que a execução não deixa rastro seria invariante
mentirosa.

**Schema dos fatos** (`versao` fixa; campos voláteis normalizados):

```json
{ "versao": 1,
  "repo": {"toplevel": "…", "branch": "…", "head": "<40 hex>"},
  "escopo": {"tipo": "pacote", "raiz": "packages/api"},
  "stacks": [{"linguagem": "php", "runner": "phpunit", "nativo": true, "config": "phpunit.xml"}],
  "inventario": {"arquivos": 84, "testes": 431, "por_suite": {"Unit": 300, "Feature": 131}},
  "execucao": {"rodou": true, "comando": "…", "verde": false, "passou": 428, "falhou": 3,
               "pulado": 7, "duracao_faixa": "10-60s", "lentos": [{"teste": "…", "faixa": "1-10s"}]},
  "cobertura": {"disponivel": true, "ferramenta": "pytest-cov",
                "por_arquivo": [{"caminho": "src/a.py", "linhas_pct": 12, "ramos_pct": 0}]},
  "sinais": [{"regra": "sem_assercao", "caminho": "tests/x.py", "linha": 42, "evidencia": "…"}],
  "suspeitos": ["tests/x.py", "tests/y.php"] }
```

Faixas de duração, fixas: `<1s`, `1-10s`, `10-60s`, `1-5min`, `>5min`. Cada detector tem id estável
(`sem_assercao_aparente`, `marcado_para_pular`, `nao_descoberto`, `espera_fixa`, `relogio_real`,
`aleatorio_sem_semente`, `rede_em_unit`, `nome_duplicado`, `teste_orfao`, `lento_para_o_tipo`), que é
o que liga achado a fato.

Os fatos guardam **repositório, branch e HEAD**; julgar com fato de outra branch é recusado, como
na `sw-pr-message`. Duração entra em **faixa**, caminho é **relativo** e a data é injetada — é o
que torna o relatório determinístico.

### Fase 3 — Julgar

O agente lê os fatos e **apenas os arquivos marcados como suspeitos**, e escreve `achados.json` na
pasta de fatos. Cada achado recebe confiança:

| Confiança | Origem |
|---|---|
| Alta | Ferramenta nativa ou fato objetivo do script |
| Média | Heurística textual forte |
| Baixa | Indício — entra como **verificar**, nunca como "corrigir" |

**Fato de script ou ferramenta:** `skip`/`only`/`xfail`/`@Ignore`/`t.Skip` e
teste comentado · teste não descoberto pelo runner · `sleep`, relógio real, aleatório sem semente,
rede em teste unitário · nome de teste duplicado · arquivo de teste órfão · tempo por teste e por
suíte · suíte verde ou vermelha · cobertura por arquivo e ramo.

**Confiança média (heurística textual, nunca entra em lote automático):** teste **sem asserção
aparente** — helper de asserção, matcher custom e `expect` encadeado geram falso positivo, então só
vira confiança alta quando quem apontou foi o plugin de lint da stack.

**Julgamento do agente:** asserção tautológica ou frouxa · mock do próprio sujeito, ou tudo
mockado a ponto de o teste verificar só o mock · asserção em detalhe interno em vez de
comportamento · nome que não descreve comportamento · teste que testa o framework · vários
comportamentos num teste só · caminho crítico sem teste (cobertura + leitura).

### Contrato `achados.json` (o que o agente escreve)

```json
{ "versao": 1,
  "achados": [{"regra": "assercao_tautologica", "dimensao": "confiabilidade",
               "confianca": "media", "caminho": "tests/x.py", "linha": 42,
               "problema": "…", "correcao": "…", "sinal": "sem_assercao_aparente"}],
  "nao_e_problema": [{"caminho": "tests/y.php", "motivo": "convenção diferente da nossa, porém consistente"}] }
```

**`report.py` recusa e lista todos os problemas de uma vez (exit 3):** `dimensao` fora das cinco ·
`confianca` fora de alta/média/baixa · `caminho` que não existe nos fatos · `linha` fora do arquivo ·
`problema` ou `correcao` vazios · achado de confiança **alta sem `sinal` correspondente** em
`fatos.sinais` — alta confiança precisa de lastro em ferramenta · mesmo `caminho:linha:regra`
repetido. Texto do agente vira uma linha só, como na `sw-pr-message`.

**Quem calcula as notas:** o `report.py`, a partir dos fatos e da contagem de achados por dimensão —
não o agente. Dimensão sem fato que a sustente sai como `⚪ sem dados`. Assim a nota é reprodutível e
o critério 4 fecha.

### Fase 4 — Relatório

`test-health-report.md` na raiz do escopo, registrado em `<git-path>/info/exclude` para não ir a
commit por engano. Traz, nesta ordem: resumo, **notas por dimensão**, achados agrupados por
confiança e dentro por dimensão, o que **não** é problema, e os próximos passos.

| Dimensão | Pergunta |
|---|---|
| Confiabilidade | O teste falha quando o código quebra? |
| Isolamento | Passa sozinho, fora de ordem e duas vezes seguidas? |
| Cobertura | O que não é exercitado, com foco em caminho crítico |
| Legibilidade | Dá para saber o que quebrou lendo o nome e a falha? |
| Velocidade | O tempo bate com o tipo declarado? |

**Dimensão sem dado é `⚪ sem dados`, nunca estimada** — se a execução foi recusada, cobertura e
velocidade não recebem nota. **Não existe nota agregada única**: um número só viraria o percentual
que este design rejeita.

### Fase 5 — Correção guiada

Menu de rumo, como na `sw-dead-code-scan`: corrigir os de confiança alta · revisar item a item ·
só o relatório. Em lotes; depois de cada lote, roda a suíte e reporta. **Antes de editar**, o
arquivo original é copiado para `<git-path>/sw-auto-test/backup/`; a reversão usa esse backup,
**nunca `git checkout`**, que apagaria alteração não commitada do usuário. Arquivo de teste com
alteração não commitada gera aviso antes da edição.

## Mudanças no modo gerar

- **Baseline antes de gerar.** Sem saber se a suíte já estava vermelha, "o teste novo falhou por
  bug do código" é indistinguível de quebra pré-existente. Sem baseline (execução recusada), o
  resumo diz isso explicitamente.
- **Prova do vermelho**, em amostra de **até 3** testes novos — os que cobrem regra de negócio, não
  glue code: altera o código sob
  teste de propósito, confirma que o teste falha, restaura. Regras:
  - **como muta:** uma alteração por vez no trecho que aquele teste cobre — inverter uma condição,
    trocar o retorno por constante, ou neutralizar a validação. Nunca mais de um teste por vez;
  - **se o teste continuar passando**, esse é o defeito procurado: vira achado ("o teste não prova o
    comportamento que o nome promete"), entra no resumo e no relatório. A skill **não reescreve o
    teste sozinha** — reescrever teste fraco é não-objetivo;
  - **"arquivo limpo" é o arquivo de produção mutado**, que precisa estar versionado e sem alteração
    pendente. O teste recém-gerado é untracked, e isso não impede a prova;
  - o original vai para `<git-path>/sw-auto-test/backup/` **antes** da alteração;
  - **toda execução da skill (qualquer modo) começa checando resíduo** de backup: achou, restaura e
    avisa — é o que protege o caso de a sessão morrer no meio;
  - só roda com git e com o arquivo **limpo**; sem isso, pula e avisa por quê;
  - watcher, dev server ou formatador ao salvar podem reescrever o arquivo na janela alterada: a
    skill pergunta antes se algo assim está rodando e, na dúvida, pula a prova.
- **Determinismo por padrão** no teste gerado: semente fixa, relógio congelado, sem `sleep`, estado
  montado por teste.
- **Proibido forçar verde:** não alterar código de produção para o teste passar; não usar
  `skip`/`xfail` para esconder falha; nada de asserção que passa de qualquer jeito. Teste novo
  falhando por bug do código vira **relato de bug**, não conserto no teste.
- **Cobertura vem da ferramenta nativa**, com o aviso de que percentual alto não significa suíte boa.

## Arrumação e integração

- `references/frameworks.md` (matriz linguagem × tipo), `references/aaa-por-linguagem.md` (os seis
  exemplos), `references/generation.md` (detalhes do modo gerar). `SKILL.md` fica abaixo de 220
  linhas.
- Toda decisão vira `AskUserQuestion`, inclusive a de onde gravar os testes, hoje em texto solto.
- **Roteamento entre modos:** frase ambígua ("olha meus testes") abre menu gerar/diagnosticar.
- **Limite contra a `sw-code-review`:** qualidade do **código de produção** é lá; qualidade dos
  **testes** é aqui. A `sw-plan` já pergunta tipos de teste e pode chamar esta skill; teste órfão
  encontrado aqui é assunto da `sw-dead-code-scan`.
- Gatilhos PT-BR na `description`: "cria os testes", "cobre com testes", "meus testes estão bons?",
  "diagnostica os testes", "a suíte presta?".

## Erros e casos de borda

| Situação | Comportamento |
|---|---|
| Sem git | Fatos no temp do SO; prova do vermelho não roda |
| Backup residual de execução anterior | Restaura e avisa, antes de qualquer outra coisa |
| Fatos de outra branch ou outro repositório | Recusa julgar; manda rodar a apuração de novo |
| Execução recusada pelo usuário | Diagnóstico segue estático; cobertura e velocidade ficam `⚪ sem dados` |
| Suíte vermelha antes de corrigir | Vira o achado nº 1; correções param até o usuário decidir |
| Timeout na suíte | Achado, com o comando e o tempo; a skill continua |
| Arquivo de teste órfão | É o arquivo dentro do diretório de testes que o runner **não descobre** e que não é helper nem fixture importado por outro teste |
| DSN/env de banco no ambiente de teste | Segunda confirmação, com o que foi detectado |
| Nenhum teste no projeto | Não é diagnóstico: oferece o modo gerar |
| Stack sem ferramenta nativa | Caminho heurístico, e o relatório diz que a precisão é menor |
| `test-health-report.md` versionado | Grava e avisa que o exclude não protege |

## Testes (pytest, na própria skill)

Como na `sw-pr-message`: repositórios git criados dentro do teste, **sem rede**. Runners são
**falsos** — executáveis no `PATH` que devolvem saída canônica de `phpunit`, `vitest` e `pytest` —
para a suíte ser hermética e rápida. Cobrem: schema dos fatos; normalização das três stacks;
`--collect-only` sem efeito colateral; cada detector textual; recusa de fatos de outra branch;
relatório determinístico; restauração de backup com falha no meio; correção em lotes revertendo
pelo backup; escopo de monorepo.

## Restrições verificáveis (fitness functions)

1. **Escrita confinada.** O script só escreve em `<git-path>/sw-auto-test/` (fatos e backups), em
   `<git-path>/info/exclude` e no `test-health-report.md`. Teste com retrato da árvore inteira,
   incluindo `.git`, antes e depois.
2. **Nada executa sem aprovação.** Sem `--executar`, nenhum processo de runner é criado — teste que
   registra toda chamada de `subprocess` e falha se algo além da detecção rodar.
3. **Restauração garantida.** Teste que interrompe a prova do vermelho no meio e confere, por hash,
   que o arquivo voltou ao original; e que a execução seguinte detecta e limpa o resíduo.
4. **Relatório determinístico.** Mesmos fatos normalizados produzem o mesmo markdown byte a byte, e
   `SKILL.md` fica abaixo de 220 linhas.

## Não-objetivos

- Reescrever teste fraco sozinha.
- Mutation testing de verdade (ferramenta, score, matriz de mutantes) — a prova do vermelho é
  pontual e por amostra.
- Configurar CI; instalar ferramenta sem aprovação; traduzir a skill.
- Perseguir percentual de cobertura como meta.
- Apuração nativa fora de PHP, JS/TS e Python nesta versão.

## Restrição de simplicidade

A menor solução: dois scripts, uma biblioteca com um módulo por stack, `references/` e o `SKILL.md`.
Se um detector exigir parser, ele não entra: vira suspeito para o agente. Se a normalização de uma
stack ficar maior que o módulo de outra inteira, essa stack cai no caminho heurístico.

## Appetite · MVP vs MLP

**Appetite médio** — maior que a `sw-pr-message`, porque são dois modos e três stacks.
**MVP:** diagnóstico confiável em PHP, JS/TS e Python, com relatório e correção guiada.

**Um plano só, em lotes, nesta ordem** — cada lote termina entregando algo que funciona sozinho:

1. `lib/backup.py` (usado pelos dois modos) e diagnóstico **estático**: inventário, detectores, fatos.
2. Execução opt-in: descoberta, suíte, cobertura, normalização das três stacks nativas.
3. `achados.json`, `report.py`, notas por dimensão, `test-health-report.md` e correção guiada.
4. Modo gerar: baseline, prova do vermelho, determinismo e proibição de forçar verde.
5. Arrumação (`references/`, `AskUserQuestion`, gatilhos PT-BR), publicação e bump das irmãs.

Parar depois do lote 3 já entrega o diagnóstico inteiro; os lotes 4 e 5 melhoram a geração.

## Decisões (ADR)

**1. Diagnóstico na mesma skill, não numa skill nova.**
Contexto: gerar e diagnosticar compartilham detecção de stack, convenções e catálogo de qualidade.
Decisão: dois modos na `sw-auto-test`, com roteamento por menu quando a frase é ambígua.
Alternativas: skill separada (duplicaria a detecção e brigaria por gatilho com esta).
Consequência: `SKILL.md` precisa de `references/` para não inchar.

**2. Ferramenta nativa na frente.**
Contexto: runner e plugin de lint entendem a linguagem; regex não.
Decisão: nativo quando existir; heurística como degradação explícita no relatório.
Alternativas: script próprio completo (envelhece mal em 9 linguagens); só instruções (caro e sem números).
Consequência: precisão varia conforme o que está instalado, e isso aparece no relatório.

**3. Execução é opt-in, com descoberta primeiro.**
Contexto: suíte "unitária" pode tocar banco, e-mail e rede no bootstrap.
Decisão: `--collect-only` sempre; suíte só após ver o comando e a config; segunda confirmação com env de banco.
Alternativas: rodar sempre (risco em projeto alheio); nunca rodar (perde cobertura, suíte vermelha e tempo).
Consequência: relatório frequentemente sai com dimensões `⚪ sem dados`, e está certo assim.

**4. Prova do vermelho no lugar, com backup e checagem de resíduo.**
Contexto: teste que passa com o código quebrado é o pior defeito, e é invisível.
Decisão: alterar o arquivo real por segundos, com backup antes e varredura de resíduo em toda execução.
Alternativas: worktree isolado (depende de `node_modules`/`vendor`/venv lá, então pularia na maioria);
não provar (deixa o defeito passar).
Consequência: a skill assume uma janela curta de risco, e precisa da regra do watcher.

**5. Reversão por backup, nunca por git.**
Contexto: `git checkout -- <arquivo>` apagaria trabalho não commitado do usuário.
Decisão: toda edição guiada guarda o original e reverte a partir dele.
Consequência: a pasta de fatos precisa ser limpa ao fim de cada lote bem-sucedido.

**6. Sem nota agregada.**
Contexto: o design rejeita percentual como meta; um score único vira exatamente isso.
Decisão: notas por dimensão, com `⚪ sem dados` quando faltar fato.
Consequência: não dá para "comparar projetos" por um número — de propósito.

## Migração e publicação

1. Implementar em `~/.claude/skills/sw-auto-test/`, preservando a matriz de frameworks e as regras
   por tipo de teste (unit/integração/e2e), que hoje estão corretas.
2. Validar em projeto real, **somente leitura primeiro** (diagnóstico sem execução), depois com
   execução autorizada. Nada do projeto validado entra neste dossiê — o marketplace é público.
3. Publicar: `make sync SKILL=sw-auto-test CATEGORY=development` + `CHANGELOG.md` (skill nova no
   marketplace, v0.1.0).
4. `sw-code-review` e `sw-plan`: apontar para esta skill no que for qualidade de teste. Bump patch/minor.

## Suposições a testar

- **Os três runners cobrem o uso real** do dono; Go/Java/Ruby/Rust/C# no caminho heurístico bastam.
- **A janela da prova do vermelho é aceitável** — validar com watcher rodando num projeto de verdade.
- **Plugins de lint de teste estão instalados com frequência suficiente** para valer a integração;
  se não estiverem, o caminho heurístico vira o normal e não a exceção.
