---
titulo: Relatório de infra simples e por tipo de sistema
slug: 2026-11-01-relatorio-de-infra-simples-e-por-tipo-de-sistema
criado: 2026-11-01
estado: concluido
---

# Relatório de infra simples e por tipo de sistema

> Caminhos relativos a `plugins/sw-infra-audit/skills/sw-infra-audit`. Visual aprovado em
> `referencias/mockup-aprovado.html`, com dados fictícios. [usuário]

## Objetivo & outcome

O relatório atual chega a dezenas de páginas numa rodada real, e a maior parte dos achados vem de 4 regras. O
importante se perde, leigos não entendem e tudo tem o mesmo peso visual. [usuário]

**Outcome:** leigos e técnicos entendem o estado da infraestrutura na primeira página, em um PDF de
**1 página + até 20**, com os serviços online como dado principal. [usuário]

## Não-objetivos

- Consulta direta ao banco, logs e troca do cAdvisor.
- Alterar qualquer sistema auditado: a skill continua só de leitura. Ativar exporter ou rota no
  Traefik é decisão do dono, e a skill só informa o que falta.
- Tema escuro novo. O atual continua funcionando.

## Exploração & decisões

Leitor: leigo e técnico no mesmo documento. Dor: tamanho, linguagem e peso visual. A primeira versão
do design foi revista contra o código, e o revisor derrubou duas premissas: "online" não estava
definido, e a etiqueta `service` do Traefik não é domínio. A nota também não caía com serviço fora.

## Design

### Estrutura do relatório

Evolui `render_html_v3` [visto: scripts/build_report.py] e o `template_v3.html`.

1. **Primeira página:** nota, serviços online, tendências, veredito, resumo de até duas frases,
   prioridades, o que mudou, certificados e uma linha do que não foi medido.
2. **Saúde por sistema:** tabela com um sistema por linha.
3. **Detalhes técnicos:** blocos por papel, conforme o mockup.
4. **Problemas agrupados:** cada problema explicado uma vez, com afetados, ação e verificação.
5. **Registro:** riscos aceitos, com vencidos em destaque, e o que falta declarar. Fica no PDF porque
   é garantia da skill. Redes, secrets e configs saem do HTML e do PDF e ficam no `report.json`.

"O que fazer primeiro" vira as prioridades da capa. Cada recomendação ganha o campo opcional `regra`;
com ele, o comando vai para o problema agrupado, e sem ele aparece em "Outras recomendações", para nunca
sumir. "Se isto falhar" vira o bloco de pontos únicos de falha.

### Blocos por papel

Um renderizador por tipo em `scripts/lib/blocos/`: máquinas, entrada, fila, banco, cache, consumo e
pontos de falha. Papel sem bloco usa a tabela genérica. Os helpers usados por `build_report.py` e
pelos blocos vão para um módulo comum, evitando import circular, e a trava de classes CSS passa a
varrer a pasta nova, porque hoje só lê `build_report.py`
[visto: tests/test_template_conhece_o_que_o_relatorio_emite.py:23].

### Serviço online

Cada serviço cai em um único estado, calculado depois de aplicar os aceites:

| Estado | Regra | Conta na nota |
|---|---|---|
| Online | todas as réplicas desejadas no ar; falha no histórico marca **com alerta**, sem mudar o estado | sim, como online |
| Parcial | parte das réplicas no ar | sim, como não online |
| Fora do ar | desejado acima de 0 e nenhuma réplica, sem aceite vigente | sim, como não online |
| Parado de propósito | desejado 0, job concluído ou `OPS_SERVICE_STOPPED` com aceite vigente | não |
| Sem dado | réplicas desconhecidas | não |

"Online" da capa é `online / (online + parcial + fora do ar)`. Com alerta é contado à parte em
`com_alerta`, aparece em amarelo na capa e mantém o achado `OPS_TASK_FAILING` em Problemas. [usuário] O campo atual `services_up`
não serve, porque só desconta serviço parado [visto: scripts/lib/metrics.py:102]. Endpoint HTTP conta
como um serviço: responde é online; `http_fora_do_ar`, timeout ou conexão recusada é fora do ar. [usuário]

### Nota geral

Cálculo determinístico em `nota.py`, gravado com as parcelas no `report.json`. A soma de serviços é
feita sobre todos os alvos medidos, sem média entre alvos, e o pior estado limita o total. [usuário]

- **70% serviços online:** percentual acima.
- **20% estabilidade:** a pontuação atual de disponibilidade, que é o percentual de serviços com mais
  de uma réplica [visto: scripts/lib/nota.py:72]. Pontos únicos não entram na conta e aparecem no bloco.
- **10% boas práticas:** média das pontuações de segurança e higiene.

Tetos [usuário]: até **59** com serviço ou nó fora do ar; até **79** com problema alto ou serviço
parcial. Alerta não tem teto. `critical` conta como alto. Os tetos são calculados depois dos aceites, e aceite vencido
volta a contar. Aceite vigente em `OPS_SERVICE_STOPPED` significa parado de propósito; em `OPS_NODE_DOWN`
não remove o teto, porque nó fora continua sendo queda.

`nota_geral` grava `com_alerta`, `limites` (a causa de cada teto) e `pendencias` (pontos que faltam para
100 em cada parcela). A capa traz a linha "Por que esta nota", com fatos das parcelas, do teto e dos
nomes: por exemplo, "Serviços: 12 de 12 online. Redundância baixa: 30%. Boas práticas: 40%." [usuário]

Faixas: **80 ou mais Bom**, **60 a 79 Atenção**, **abaixo de 60 Crítico**. O rótulo e a cor saem da
faixa. O veredito é uma frase fixa por faixa, e o resumo de até duas frases é o campo `resumo` do agente.

Parcela não medida sai da conta, os pesos restantes são renormalizados e a nota aparece como
**parcial**, sem verde. O verde também exige o alvo sem a trava de cobertura [visto: scripts/lib/cobertura.py:102].
Sem nenhum serviço medido, não há nota. A nota substitui a frase de `nota_de_estabilidade`.

Revoga "não existe nota única" em `SKILL.md:342`, `SKILL.md:348`, `SKILL.md:404`,
[visto: scripts/lib/nota.py:8] e no teste `test_nao_existe_nota_unica_da_infraestrutura`
[visto: tests/test_build_report_v3.py:59].

### Sistema

"Sistema" é a stack do Swarm. O nome vem da tabela opcional `rotulos` do alvo em `alvos.toml` e, sem ele, do nome
da stack. Estado do sistema é o pior estado entre seus serviços. "Resposta" e "Disponível" só aparecem
quando a etiqueta do proxy liga o backend à stack; senão, ficam como sem dado.

### Coleta

- **Alvo não confirmado:** continua no `report.json`, porque aceites e testes dependem dele
  [visto: scripts/lib/aceites.py:76]. O HTML mostra só uma linha de contagem. A regra de "aparecer
  com o nome" é ajustada para essa linha citar os nomes.
- **Sites:** o spike verifica se existe rota no Traefik. Com rota, mostra top 10 por acessos, sempre
  somando quem teve erro 5xx. Sem rota, o bloco se chama "Serviços web", porque `service` identifica
  o backend [visto: references/metricas/traefik.toml:14]. A ordem é decidida em Python, com desempate.
- **Máquinas:** família `node-exporter` e um caminho novo de coleta por alvo, porque hoje toda pergunta
  é por componente [visto: scripts/collect.py:433]. O nó é ligado a `fatos.nodes`.
- **Cache:** acerto calculado por divisão dentro da própria query PromQL [doc: https://prometheus.io/docs/prometheus/latest/querying/operators/ · latest · 2026-11-01].
  Os comentários que dizem que isso é inviável são atualizados [visto: scripts/lib/perguntas.py:94].
- **30 dias e previsão de disco:** o spike define a série de disponibilidade, porque o Swarm não tem `up` por serviço. Sem série confiável, a coluna fica como sem dado. Consulta instantânea com `avg_over_time` e `predict_linear`
  [doc: https://prometheus.io/docs/prometheus/latest/querying/functions/ · latest · 2026-11-01]. O bloco
  informa a cobertura real da janela, porque a retenção pode ser menor.
- **Tendências:** erros, resposta, CPU, memória e disco, em 24 horas com passo de 1 hora, via `query_range` [doc: https://prometheus.io/docs/prometheus/latest/querying/api/ · latest · 2026-11-01],
  com nova forma `serie`. `--at` inválido vira `sem_dados`, nunca consulta sem âncora
  [visto: scripts/lib/adaptadores/promql.py:34].
- **cAdvisor:** na rodada real de 26/10, 20 respostas vieram vazias, enquanto o catálogo registra
  casamento de 5 em 5 [visto: references/metricas/cadvisor.toml:15]. A causa sai do spike.
- **Filas:** saldo e estado são derivados dos dados já coletados.

### Limite de páginas

O corte é determinístico e calculado por contagem de itens, antes de renderizar, e vale igual para HTML
e PDF. Não depende de Chromium. A ordem é: achados de baixa gravidade viram contagem; a lista de afetados
fica nos 8 primeiros; o bloco de consumo mostra top 4; a saúde por sistema junta os sistemas online.
O relatório informa cada corte, e o completo fica no `report.json`.

Riscos aceitos e o que falta declarar nunca são cortados. Quando eles sozinhos ultrapassarem o orçamento,
o limite de 20 páginas cede e o relatório diz isso. A garantia de 20 páginas vale para a fixture de
referência, verificada com Chromium; sem ele, o teste é pulado de forma visível.

### Erros

Sem fonte, o bloco mostra "não medido" com motivo, nunca zero. Falha de consulta nova não derruba o
restante da coleta, e pergunta nova que uma família não responde não reduz a cobertura sem haver o que
consertar.

## Decisões

**D1. Reorganizar o relatório atual.** Contexto: 87 arquivos de teste e catálogos prontos. Descartadas:
relatório novo, com dois para manter, e só cortar, que não resolve linguagem. Consequência: visual
evolui por partes.

**D2. Nota geral com tetos.** Contexto: pedido do dono, contra a regra anterior. Descartadas: sem nota e
teto único. Consequência: queda nunca sai com nota boa.

**D3. Prometheus como fonte.** Contexto: não guarda credencial de banco. Descartadas: consulta direta e
trocar o cAdvisor. Consequência: blocos dependem de exporters na infra.

**D4. Alvo não confirmado corta só na exibição.** Contexto: aceite e histórico dependem dele.
Descartada: tirar da coleta.

## Restrições verificáveis

- Fixture com 60 serviços e 216 achados gera PDF com no máximo 21 páginas; sem Chromium, o teste aparece como pulado.
- Serviço ou nó fora do ar, conforme a tabela de estados, nunca produz nota acima de 59.
- Toda recomendação do agente aparece no relatório.
- Parcela não medida nunca soma como zero.
- Todo bloco sem dado renderiza "não medido", sem o número 0.
- Classe CSS emitida por `scripts/lib/blocos/` existe no template.

## Suposições

| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| O Prometheus real tem node-exporter ou aceita recebê-lo | Bloco de máquinas fica como não medido | Spike: listar séries `node_` e etiqueta `instance` |
| A retenção cobre 30 dias | Disponibilidade cobre menos | Spike: consultar a retenção e a amostra mais antiga |
| O custo das consultas cabe em 120 s por alvo | Componentes finais ficam sem dados | Spike: medir tempo com 57 serviços |
| A causa do cAdvisor é uma etiqueta corrigível | Bloco de consumo segue incompleto | Spike: comparar valores da etiqueta com nomes de serviço |
| O Traefik expõe rota por domínio | Bloco vira "Serviços web" | Spike: listar séries `traefik_router_` |

## Appetite

Trabalho grande, dividido em etapas: spike, relatório com fixture no tamanho real, depois coleta por
fonte. MLP na primeira página; coleta entra por fonte, sem bloquear o relatório.

## Rollout

O relatório novo substitui o v3 na mesma versão da skill, e a reversão é o commit anterior. Sem migração
de dados. O `schema_version` só muda se o spec exigir campo incompatível, porque `historico.py` aceita
versões fixas [visto: scripts/lib/historico.py:9]. "O que mudou" usa novos, resolvidos e, quando houver
nas duas rodadas, a nota; o resto do histórico continua igual.

## Decisões da execução

- Retenção real de 7 dias: "Disponível" usa 7 dias, não 30. [visto: referencias/spike-fontes.md]
- Sites por `router`, com domínio vindo das regras do Traefik; banco e cache seguem como não medidos por falta de exporter.
- Falhas de tasks desconhecidas com réplicas conhecidas: o estado segue as réplicas, e a nota fica parcial.
- A fixture de páginas precisou imitar a rodada real: a primeira versão dava 17 páginas enquanto a real dava 43.
- Filas mostram até 8 linhas e contagem do restante; "Por aplicação" saiu do HTML.
- Réplicas todas no ar com falhas no histórico contam como online com alerta; "instável" saiu dos estados e do teto de 79. [usuário]
- Fila sem senha: `exec_leitura` é a última fonte, depois de `admin_http` e do exporter, só com comando fixo de `references/execs/<familia>.toml`, sem shell. Container em outro nó fica sem dados, e as taxas seguem como "ritmo não medido". [usuário]
- URLs mais acessadas: a pergunta é pedida depois de tudo, com o que sobrou do orçamento, porque 24 janelas de 4 s comeriam 96 dos 120 s do alvo. Sem orçamento ou sem `logs_url`, ela sai da cobertura. Fonte declarada que falha segue como lacuna, como em toda pergunta opcional, e não mexe no teto nem na nota. [usuário]
- A rota do Loki mora no catálogo, em `references/logs/traefik.toml`, porque nome de produto não entra em literal de código. O carregador só aceita `query_range` e a forma fixa com `line_format`.
- `logql` tem prioridade 25, antes do `promql`, para o motivo dele valer nesta pergunta; `admin_http` segue primeiro.
- Limite de 32 MB por janela, em vez dos 4 MB do `http_get`: cada linha volta como stream com rótulos. Tamanho não medido; acima disso a janela falha com o motivo dito.
- Normalização além do pedido: `%3F` decodificado antes do corte, `;` corta o segmento, segmento com `@` vira `:token` e qualquer segmento de 24 caracteres ou mais vira `:token`, inclusive slug longo. Hexa longo é a partir de 8 caracteres.
- Duas quedas de rede seguidas encerram a leitura, para Loki morto não gastar o orçamento. Linha com host inválido ou fora dos quatro campos é descartada.
- `report.json` guarda só o top 50 por site, por acessos; "mais erros" e "mais lentas" olham esse conjunto, e o bloco diz isso. O geral e a tabela de sites mostram o top 15, também no aperto de páginas; nele o restante cai para 2 por site em 3 sites e 3 destaques, com aviso.
