# Spike — regra verificável é extraível com precisão útil?

**Projeto 1:** `o projeto B` — Next.js/TypeScript, 536 arquivos de código,
493 commits. Domínio: certificados de aeronave (FAA/ANAC/EASA), carga de dados e leads.
**Data:** 2026-10-06
**Amostra:** 20 candidatas sorteadas de 293 achadas.

## Critério

Deu certo se ao menos 14 de 20 (70%) forem regra de negócio quando conferidas à mão.

## Resultado: 4 de 20 = 20%. **Reprovado.**

| # | Tipo | Arquivo:linha | Trecho | Negócio? |
|---|---|---|---|---|
| 1 | estado | `src/lead/crm-api.ts:84` | `status = 'ACKNOWLEDGED'` no ciclo do lead | **sim** |
| 2 | estado | `tests/load/run-load.test.ts:93` | asserção de teste | não |
| 3 | constante | `src/load/persist/aircraft.ts:8` | `CHUNK = 1000` — lote técnico | não |
| 4 | limiar | `scripts/load-faa.ts:10` | `maximo: 1` — contagem de argumento de CLI | não |
| 5 | constante | `src/load/anac/scan.ts:10` | `TAIL_MISSES = 200` — quando parar a varredura ANAC | **sim** |
| 6 | limiar | `tests/load/after-load.test.ts:22` | teste | não |
| 7 | estado | `tests/site/record.test.ts:84` | teste | não |
| 8 | estado | `tests/site/lead-register.test.ts:138` | teste | não |
| 9 | constante | `tests/fixtures/load/generate.ts:33` | fixture | não |
| 10 | constante | `src/load/http-client.ts:11` | `REQUEST_TIMEOUT_MS` — infraestrutura | não |
| 11 | constante | `src/search/search.ts:146` | `HIT_COLUMNS` — lista de colunas SQL | não |
| 12 | constante | `src/security/csp.ts:9` | domínios de CSP | não |
| 13 | constante | `tests/helpers/site-db.ts:17` | helper de teste | não |
| 14 | estado | `tests/site/email-token.test.ts:75` | teste | não |
| 15 | estado | `tests/site/partner.test.ts:13` | teste | não |
| 16 | constante | `src/app/_components/mini-search.tsx:8` | rotas com campo grande — config de UI | não |
| 17 | estado | `src/load/run-load.ts:107` | `status: "DONE"` da carga | **sim** |
| 18 | estado | `tests/site/identity-routes.test.ts:144` | teste | não |
| 19 | constante | `src/load/anac/scan.ts:12` | `TTL_MS = 30 dias` — validade da varredura | **sim** |
| 20 | constante | `tests/served/served-html.test.ts:21` | teste | não |

## Por que falhou, e o que isso ensina

**Metade do ruído é teste.** 9 das 20 estão em `tests/`. Nenhuma é regra: são asserção e
fixture. Excluir `tests/` resolve isso sem custo nenhum.

**Excluindo testes, a precisão sobe para 4 de 10 = 40%** — ainda abaixo do critério, mas o
quadro por tipo é o que importa:

| Tipo | Em `src/` | Regra de negócio | Precisão |
|---|---|---|---|
| **estado** | 2 | 2 | **100%** |
| constante | 7 | 2 | 29% |
| limiar | 1 | 0 | 0% |

**Estado é sinal; constante nomeada é ruído.** `status = 'ACKNOWLEDGED'`, `status: "DONE"` —
os dois achados de estado em código de produção eram regra de negócio, os dois. Já constante
maiúscula pega `CHUNK`, `HIT_COLUMNS`, `GA_IMG`, `REQUEST_TIMEOUT_MS`: lote, SQL, CSP e
timeout. O nome ser maiúsculo diz que é constante, não que é decisão de negócio.

**Três dos seis padrões acharam zero.** `enum`, `validacao` e `cron` são moldados em PHP
(`'campo' => 'required|min:3'`) e o projeto é TypeScript. Não é que o projeto não tenha
validação — é que o padrão não a reconhece nesta stack. Isso confirma, por outro caminho, o
que o spec já decidiu: **regra verificável exige TOML da stack**, não dá para ser universal.

## Decisão

**`regras.py` NÃO entra como foi desenhado.** A versão genérica, de seis padrões sobre
qualquer linguagem, extrai 20% — entregaria ao consultor uma lista em que 4 de 5 itens são
lixo técnico, e ele levaria isso ao cliente como "regras do sistema".

O que sobrevive, para o Plano 2:

1. **Só o padrão de estado**, e só em código de produção (fora `tests/`, `spec/`, `__tests__/`).
2. **Dentro do TOML da stack**, não no piso — cada stack declara como reconhece máquina de
   estados (campo de enum, união de literais em TypeScript, constante de classe em PHP).
3. **Constante nomeada e limiar saem.** Reentram se alguém achar um sinal melhor que
   "está em maiúsculas" — por exemplo, constante citada numa comparação de fluxo de decisão.

O resto da camada "o que o sistema faz" fica com propósito-com-fonte-textual e perguntas em
aberto, como o spec já previa para o caso de o spike reprovar.

---

# Projeto 2 — e a decisão muda

**Projeto:** `o projeto A` — PHP (331 arquivos) + JS (158), **sem manifesto** e
**sem repositório git**. É o projeto legado típico: o caso que a skill existe para enfrentar.
**Amostra:** 20 candidatas sorteadas **só de código de produção** (a lição do projeto 1).

## Resultado: 10 de 20 = 50%

| # | Tipo | Onde | Negócio? | Por quê |
|---|---|---|---|---|
| 1 | limiar | `Admin/Controllers/CreatorController.php:128` | não | está num **comentário** de docblock, não no código que aplica |
| 2 | enum | `LogicApp/Enums/ECampaignDocumentCategory.php:5` | **sim** | |
| 3 | estado | `admin/src/constants/enums.js:63` | não | o próprio comentário avisa: "é valor de filtro, não estado de creator" |
| 4 | limiar | `store/model/imageSearch.js:41` | não | paginação |
| 5 | limiar | `assets/js/creators.min.js:228` | não | **arquivo gerado** (`.min.js`) |
| 6 | enum | `LogicApp/Enums/EIdentityStatus.php:6` | **sim** | estado do e-mail da conta |
| 7 | limiar | `assets/js/constants/index.js:169` | não | tempos de animação FAST/NORMAL/SLOW |
| 8 | enum | `LogicApp/Enums/ESocialNetworkPlatform.php:5` | **sim** | |
| 9 | limiar | `store/model/log.js:50` | não | paginação |
| 10 | limiar | `admin/src/constants/index.js:268` | **sim** | limite de armazenamento por plano |
| 11 | constante | `vuejs/services/workProfile.js:44` | não | mapa de listas, não regra |
| 12 | limiar | `Creators/Models/Niche.php:20` | não | default de paginação |
| 13 | limiar | `LogicApp/Models/LogSystem.php:22` | não | paginação |
| 14 | enum | `LogicApp/Enums/EConsentType.php:6` | **sim** | |
| 15 | estado | `LogicApp/Models/Creator.php:409` | **sim** | `status = 'ACTIVE'` |
| 16 | enum | `LogicApp/Enums/ENotificationType.php:5` | **sim** | |
| 17 | constante | `admin/src/mocks/newCampaignMock.js:18` | não | **mock** |
| 18 | limiar | `vuejs/services/channels.js:14` | **sim** | `MAX_LINKS = 5` |
| 19 | limiar | `LogicApp/Helpers/ContactRules.php:10` | **sim** | `MAX_LINKS = 5`, em `ContactRules` |
| 20 | estado | `LogicApp/Models/Creator.php:402` | **sim** | |

## O quadro juntando os dois projetos (só código de produção)

| Padrão | Achados | Regra de negócio | Precisão |
|---|---|---|---|
| **enum** | 5 | 5 | **100%** |
| **estado** | 5 | 4 | **80%** |
| limiar | 11 | 3 | 27% |
| constante | 9 | 2 | 22% |
| validacao | 0 | — | nenhum achado nos dois |
| cron | 0 | — | nenhum achado nos dois |

## Decisão revisada: `regras.py` sobrevive, com dois padrões dos seis

**Mantendo só `enum` e `estado`, a precisão é 9 de 10 = 90%** — acima do critério de 70%.
A média de 20% e 50% escondia isso: não é a extração que falha, são **quatro dos seis
padrões**. `limiar` e `constante` arrastam 20 candidatas para trazer 5 regras, e o
consultor não tem como saber quais 5.

**O que entra no Plano 2:**

1. **Só `enum` e `estado`.** `constante`, `limiar`, `validacao` e `cron` saem.
2. **Fora de `tests/`, `spec/`, `__tests__/`, `fixtures/`, `mocks/`** — no projeto 1, metade
   da amostra era teste.
3. **Fora de arquivo gerado** (`.min.js` e companhia) — já é campo do `arvore.py`.
4. **Fora de comentário.** O #1 era um docblock descrevendo o limite da API; o padrão não
   distingue, e regra lida de comentário pode nem estar implementada.
5. **Dentro do TOML da stack.** `enum` só rendeu em PHP 8.1 com `enum` nativo; no projeto
   TypeScript achou zero — não porque não haja domínio modelado, mas porque a sintaxe é
   outra (união de literais). Confirma o spec: regra verificável exige TOML, não é universal.

**Observação que vale para o piso, não só para o Plano 2:** o projeto 2 não tem manifesto
**nem git**. Ele exercita exatamente os dois caminhos de degradação que as tasks 3 e 5
constroem — é o fixture real para o Plano 1.
