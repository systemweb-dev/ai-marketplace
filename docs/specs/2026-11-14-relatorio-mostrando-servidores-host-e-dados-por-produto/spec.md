---
titulo: Relatório mostrando servidores host e dados por produto
slug: 2026-11-14-relatorio-mostrando-servidores-host-e-dados-por-produto
criado: 2026-11-14
estado: concluido
---

# Relatório mostrando servidores host e dados por produto

> Parte C da evolução da `sw-infra-audit`. A parte A (v0.20.0) trouxe o alvo `host` por SSH, e a
> parte B (v0.21.0, dossiê `docs/specs/2026-11-13-coleta-por-produto-em-servidores-host`) trouxe a
> coleta por produto. Caminhos relativos a `plugins/sw-infra-audit/skills/sw-infra-audit/`.

## Objetivo & outcome

O `report.json` já guarda os dados de host, mas o relatório HTML e o PDF não mostram:

- o sistema e o acesso de cada servidor;
- o estado, os reinícios e a memória de cada serviço;
- o tamanho por banco, as conexões contra o limite, as lentas e o binlog;
- a idade do backup;
- as coleções do Qdrant;
- os achados novos.

Hoje o bloco `banco` só lê `banco.conexoes` e `banco.tamanho`
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/dados_blocos.py:195]. Só os papéis de
`PAPEIS_COM_BLOCO = {"entrada", "fila", "banco", "cache", "maquina", "app"}` ganham bloco, e `busca`
fica de fora [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/build_report.py:1705].

O dono quer três coisas [usuário]:

- **design bonito, fácil de entender e bem separado**;
- **todo problema com a solução ao lado**;
- **gráficos e espaçamento melhores**.

**Outcome:**
1. Cada servidor host tem uma área própria. Ela mostra o sistema e o acesso, os problemas com o que
   fazer, o estado dos serviços e o informativo, nesta ordem e com rótulos.
2. Os bancos do cluster e os do host aparecem no mesmo bloco e no mesmo formato. Cada campo aparece só
   quando existe no dado.
3. Todo problema exibido traz a caixa "O que fazer" com o primeiro passo da remediação da regra.
4. Os gráficos (medidor e barras) são SVG inline, legíveis no claro, no escuro e no PDF.
5. Fora de Máquinas e Bancos, um relatório sem host fica igual ao de hoje. Esses dois blocos mudam
   também para os clusters, para o relatório ter um formato só. [usuário: "melhorar os design para ficar mais bonito tudo"]

Direção visual aprovada: [`referencias/mockup-aprovado.png`](referencias/mockup-aprovado.png)
(variação "Problema primeiro"; HTML em `referencias/mockup-aprovado.html`). [usuário]
O mockup diverge do spec em dois pontos, e quem vale é o spec:
- disco, memória e carga ficam em Máquinas, e não na área do servidor;
- o Qdrant não aparece mais como "sem regra própria", porque reinícios agora têm regra.

## Não-objetivos

- Tema novo: tipografia, cores base e tokens de espaço continuam os do `template_v3.html`
  [visto: plugins/sw-infra-audit/skills/sw-infra-audit/assets/report-template/template_v3.html:49].
- Série temporal, gráfico de linha, dado volátil.
- Interatividade além do `<title>` nativo do SVG. O relatório também vira PDF.
- Mudar o que é coletado, com uma exceção: o campo estruturado `fatos.descobertos` (seção 6).
- Mudar o relatório dos alvos `docker` e `http` fora de Máquinas e Bancos (restrição 3).

## Design

### 1. Bloco novo "Serviços dos servidores"

Aparece só se algum alvo for `host`. No topo fica o **índice de problemas**: uma linha por problema,
com a severidade, o servidor, o serviço e o título. Ele aponta para a área do servidor por âncora.

Depois vem uma área por servidor, que começa pelo cabeçalho com o nome, o sistema (`fatos.sistema`,
`fatos.kernel`) e o acesso (`fatos.acesso`). Abaixo, três grupos com rótulo visível:

- **Problemas e o que fazer:** um cartão por achado dos componentes que não têm bloco próprio
  (`app`, papel desconhecido) e pelos achados de serviço (`servico_declarado_ausente`,
  `SEC_BIND_ALL_INTERFACES`, `servico_reiniciando`) desses componentes (seção 2).
- **Estado dos serviços:** uma linha por componente com o estado, o tempo no ar, os reinícios
  (destacados a partir de 5) e a memória. A memória vem em barras horizontais ordenadas, na mesma
  escala dentro do servidor.
- **Informativo:** "descoberto e não declarado" e "não medido". Cada item diz o motivo e o que fazer,
  por exemplo o comando `configurar.py descobrir --alvo <nome>`.

**Onde cada cartão aparece (uma vez só):** o achado vira cartão no bloco do papel do componente. Banco
vai para Bancos, busca para Busca e máquina para Máquinas; o resto fica em Serviços. O índice do
topo lista todos os problemas dos hosts e aponta para o cartão, onde quer que ele esteja. A seção
de problemas que já existe continua com a remediação completa [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/build_report.py:1882].
O cartão é curto: título, objeto e "O que fazer". O link "ver todos os passos" aponta para essa
seção, e o `<article class="bl-prob">` ganha `id` por regra para servir de âncora.

As perguntas lidas são `servico.ativo`, `servico.desde`, `servico.reinicios` e `servico.memoria`
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/perguntas.py:151].

A máquina do host **não** aparece aqui: disco, memória e carga vão para o bloco Máquinas (seção 3),
para não repetir.

### 2. "O que fazer" sem campo novo

A caixa mostra o **primeiro passo numerado** da seção `## Como resolver` da remediação da regra. As
remediações já têm essa seção, por exemplo [visto: plugins/sw-infra-audit/skills/sw-infra-audit/references/remediacao/backup_atrasado.md:14]. O
link "ver todos os passos" leva à remediação completa, que o relatório já monta. Não entra campo novo
no frontmatter.

- Medida do primeiro passo: é a primeira linha não vazia depois de `## Como resolver`. Ela começa com
  `1. ` e segue até a linha em branco ou o `2.`. Conta-se o texto sem o `1. `, com o markdown e com
  os espaços juntados num só.
- Fitness: toda regra de `exigem_remediacao()` [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/regras.py:67] tem uma remediação
  cujo `Como resolver` começa com um passo numerado curto, de até 160 caracteres. A remediação que
  falhar é ajustada no plano, só no primeiro passo. É ajuste de texto, não reescrita da skill. Por essa medida,
  24 das 27 passam. `OPS_TLS_EXPIRED` e `OPS_TLS_EXPIRING` abrem com um parágrafo que manda ler
  `references/tls-renewal.md`, e esse parágrafo vira o passo 1. `SEC_PORT_EXPOSED` tem 161
  caracteres e o passo 1 é encurtado [visto: plugins/sw-infra-audit/skills/sw-infra-audit/references/remediacao/OPS_TLS_EXPIRED.md:14].
- O cartão de informativo também orienta: "não medido" diz o motivo e como medir.
- **Regra nova `servico_reiniciando`:** severidade `medium`, origem `produto`. Dispara quando
  `servico.reinicios` for 5 ou mais. [usuário] Mexe em três lugares:
  - entra em `REGRAS_PRODUZIDAS` de `lib/limites_produto.py` [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/limites_produto.py:11];
  - entra em `regras.py`;
  - ganha `references/remediacao/servico_reiniciando.md`.
- `rule_meta` ganha rótulo para `servico_declarado_ausente`, `SEC_BIND_ALL_INTERFACES`,
  `backup_atrasado`, `conexoes_no_limite` e `servico_reiniciando`.

### 3. Blocos que mudam

- **Máquinas:** ganha carga e boot. Disco, memória e carga viram medidores com uma marca em 90%. A
  máquina do host entra aqui como as do cluster.
- **Bancos:** os bancos do cluster e os do host ficam no mesmo bloco e no mesmo formato. Cada campo
  aparece só quando existe:
  - conexões contra o limite: medidor com alerta em 80%;
  - tamanho por banco: barras ordenadas, top 5 e "e mais N";
  - lentas;
  - binlog;
  - idade do backup: medidor em dias, com a marca no `backup_max_dias`. Fora do limite fica vermelho,
    a cor grave. [usuário]

  O adaptador `banco` passa a ler `banco.tamanho_por_banco`, `banco.uso_de_conexoes`,
  `banco.consultas_lentas`, `banco.binlog` e `banco.backup_idade`
  [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/perguntas.py:156], e `_simples` continua para os papéis que não mudam
  [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/dados_blocos.py:93].
- **Busca (bloco novo):** lê `busca.colecoes`, as coleções do Qdrant, com pontos em barras e status em ícone e rótulo. `busca`
  entra em `PAPEIS_COM_BLOCO`.

### 4. Capa e nota

- `_conta_do_alvo` [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/nota.py:80] ganha o ramo `host`. Os serviços do host contam na
  base da nota como os componentes do cluster.
- `_nomes_por_estado` [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/capa.py:93] e `saude_por_sistema`
  [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/capa.py:412] passam a ler os serviços do host.
- O aceite de `servico_declarado_ausente` é por componente: o `objeto` do achado é o nome do
  componente.
- Serviço ativo mas não medido (VPN fora, ssh caído) fica fora da base da nota. O host aparece como
  "não medido", com o motivo, e não como "ok".

### 5. Gráficos

Módulo novo `scripts/lib/graficos.py` com duas funções que devolvem SVG inline, sem JS e sem
biblioteca:

- `medidor(valor, maximo, marca, rotulo)`: barra horizontal com a marca de limite. Abaixo da marca usa
  o acento; acima, a cor de status com ícone e rótulo, nunca a cor sozinha.
- `barras(itens, unidade, limite=5)`: barras horizontais ordenadas da maior para a menor, com o valor
  em texto na cor de texto, e "e mais N" quando passa do limite.

Regras de dataviz:

- as cores vêm de `var(--…)`, para o modo escuro funcionar;
- o tom novo de barra entra nos dois blocos `:root` (claro e escuro);
- paleta validada: claro `#22659e/#b7791f/#b02a37`, escuro `#3f8fd0/#bf8a17/#cc3b4c`;
- um eixo só, e o valor sempre escrito ao lado;
- `<title>` em cada marca.

O espaçamento reusa a escala `--s1..--s8` (8 a 72px). Entre os grupos de uma área usa `--s5`, e entre
servidores, `--s7`.

### 6. Campo estruturado `fatos.descobertos`

Hoje "descoberto e não declarado" sai como nota de texto em `nao_coletado`
[visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/coletores/host.py:51]. O coletor passa a gravar também
`fatos.descobertos = [{produto, origem}]`, e o bloco lê esse campo. A nota continua, para o resumo de
lacunas.

### 7. PDF

`orcamento_paginas._linhas` [visto: plugins/sw-infra-audit/skills/sw-infra-audit/scripts/lib/orcamento_paginas.py:11] ganha pesos para Serviços e
Busca e para os medidores novos de Bancos e Máquinas. Os pesos são calibrados contra um PDF real,
gerado com o `google-chrome` da máquina. As barras têm top N com "e mais N"; os blocos de host não ganham
corte próprio quando o relatório corta, por decisão do dono. [usuário] Os painéis novos podem quebrar
entre páginas (`break-inside:auto`), para não deixar folha quase vazia.

## Exploração & decisões

O mockup testou três variações e o dono escolheu "Problema primeiro": quem abre o relatório quer saber
o que está errado e o que fazer, e só depois o estado. [usuário]

## Decisões

| Contexto | Decisão | Alternativas descartadas | Consequências |
|---|---|---|---|
| Onde o host aparece | Bloco "Serviços dos servidores" + máquina em Máquinas | Um bloco só com tudo do host | Sem repetir disco e memória |
| Bancos de host e de cluster | Mesmo bloco e formato, campo só se existe | Bloco separado para o host | Um lugar para olhar bancos |
| Texto do "O que fazer" | Primeiro passo de `Como resolver` | Campo novo no frontmatter | Sem duplicar texto; precisa de fitness |
| Reinícios | Regra `servico_reiniciando` a partir de 5 [usuário] | Só destaque visual | Vira problema com solução |
| Backup fora do limite | Vermelho, grave [usuário] | Âmbar | Coerente com a severidade `high` |
| Gráficos | SVG inline gerado em Python | Biblioteca JS | Funciona no PDF e sem rede |
| Descobertos | Campo `fatos.descobertos` | Ler a nota de texto | Bloco não depende de frase |
| Máquinas e Bancos nos clusters | Mudam também, formato único | Ramo só para host | Golden exclui só esses dois blocos |
| Onde o cartão aparece | Uma vez, no bloco do papel | Repetir em Serviços | Índice no topo cobre a busca |

## Restrições verificáveis

1. Toda regra de `exigem_remediacao()` tem `Como resolver` começando por um passo numerado de até 160
   caracteres (teste estático).
2. Nenhum cartão de problema fica sem "O que fazer": o teste conta os cartões e as caixas no HTML de
   um relatório com host. O teste também confere que cada achado vira cartão uma vez só, fora da
   seção de remediação completa.
3. Dois goldens do `<body>`, sem o `<style>`, gerados **antes** da mudança:
   - um de `plugins/sw-infra-audit/skills/sw-infra-audit/tests/fixtures/report_sample.json` (schema antigo), comparado inteiro;
   - um de uma fixture nova com `alvos` docker e http (entrada, fila, cache, app, banco e máquina),
     comparado com as seções Máquinas e Bancos removidas.
4. No PDF, os 2 hosts da fixture somam no máximo 12 páginas à rodada grande, e nenhuma página do
   meio fica abaixo de 15% de preenchimento (teste com o `google-chrome`; pulado se não houver).
   Revisto com o dono: layout completo, sem corte novo para host. [usuário]
5. Nenhuma cor literal de dado no SVG: todo `fill` e `stroke` usa `var(--…)` (teste estático).

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| Os pesos de linha calibram o PDF de host como calibram o do cluster | página quebrada no meio do cartão | gerar PDF real com 2 hosts na task de calibração |
| O `<body>` sem host não muda quando o CSS ganha tokens | golden falha por diferença inofensiva | o golden compara o `<body>` sem o `<style>` |

## Appetite e MVP

Médio, um plano. MVP: o bloco Serviços com "O que fazer", e Bancos com os campos de host. Busca,
medidores de Máquinas e calibração do PDF entram no mesmo plano.

## Rollout

Versão minor. Relatório sem host não muda (restrição 3). Volta é voltar a versão.

## Decisões da execução

Detalhe em "Ajustes durante a execução", no `plan.md`.

- **Golden da restrição 3:** sai de `relatorio_grande()` e de uma fixture docker com http. O
  `report_sample.json` usa o schema 1, que o build recusa. Os dois goldens comparam o `<body>` sem os
  painéis Máquinas e Bancos, e sem o `id="regra-…"`.
- **Fitness 4:** o layout completo fica [usuário]. Os 2 hosts somam no máximo 12 páginas e nenhuma
  página do meio fica abaixo de 15%. Medido: 21 → 33 páginas na rodada grande. Os painéis novos quebram
  entre páginas por `:has(...)`, porque o `.bl-pn{break-inside:avoid}` deixava folhas quase vazias.
- **Bancos:** com dado de host, o bloco vai à largura toda, com os bancos lado a lado. Sem dado de host,
  continua na meia coluna de hoje.
- **Busca:** o bloco é só do host. No cluster, `busca` não tem pergunta e segue em "Outros sistemas",
  para o relatório sem host não mudar.
- **Cartões:** só alvo `host` tem cartão nos blocos. O achado de cluster continua só na seção Problemas.
- **Aceite do ausente:** vale pelo `objeto` ou, se ele estiver vazio, pelo `componente`. Assim, o
  `aceitar --componente` não cala o servidor inteiro.
- **Máquinas:** a barra usa o acento até a marca de 90% e, acima dela, a cor de status com a etiqueta.
- **Pesos do orçamento:** `40*servidores + 10*servicos_host + 13*cartoes`, calibrados no PDF real.

## Revisões do spec

- **2026-11-14** — revisão do design: a máquina do host só em Máquinas; "O que fazer" vem do primeiro
  passo, sem campo novo; o não medido fica fora da base; `fatos.descobertos` estruturado; golden do
  `<body>` antes da mudança; o tom de barra nos dois `:root`.
- **2026-11-14** — revisão do spec: citação de `_simples` corrigida; Máquinas e Bancos mudam também nos
  clusters, e o golden novo exclui só esses blocos; medida do primeiro passo definida (24 de 27
  passam); cartão uma vez só, no bloco do papel, com âncora para a remediação completa; ids das
  perguntas citados; divergências do mockup registradas.
- **2026-11-14** — revisão do plano: restrição 4 trocada. A rodada grande já tem 21 páginas, então "cabe
  no orçamento" nunca passaria. Os 2 hosts medidos somam 12 páginas; o dono manteve o layout completo.
  O golden inteiro sai de `relatorio_grande()`, porque `report_sample.json` é schema 1 e o build o recusa.
