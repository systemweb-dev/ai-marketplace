"""As perguntas canônicas — o que se quer saber, independente de quem responde.

O papel do componente escolhe as perguntas; o adaptador responde o que souber. Separar as duas
coisas é o que permite trocar a fonte (exporter, API de administração, log) sem reescrever o
relatório, e é o que faz `sem dados` ter motivo em vez de virar buraco.

Campos de cada pergunta:
  forma      escalar · lista · serie — o relatório desenha de acordo
  unidade    o que o número significa (requisicoes, ms, bytes…)
  limiar     o que transforma informação em ACHADO; sem limiar, é só informação
  desempate  obrigatório em lista: empate de valor não pode herdar a ordem da fonte
  faixa      a tolerância, quando ela EXISTE de verdade: {sentido, bom_ate, ruim_a_partir,
             maximo}. Só quem declara faixa vira mostrador no relatório — agulha sem
             tolerância declarada é enfeite que sugere uma leitura que ninguém definiu.
  por_ultimo a pergunta cara roda com o que sobrou do orçamento, depois de todas as outras.
"""

PERGUNTAS = {}
ORDEM = {}


def _p(id, papel, titulo, forma, unidade=None, limiar=None, desempate=None, faixa=None, opcional=False,
       por_ultimo=False):
    PERGUNTAS[id] = {"id": id, "papel": papel, "titulo": titulo, "forma": forma,
                     "unidade": unidade, "limiar": limiar, "desempate": desempate,
                     "faixa": faixa, "opcional": opcional, "por_ultimo": por_ultimo}
    ORDEM.setdefault(papel, []).append(id)
    return id


# --- papel `entrada`: nesta versão, só o que QUALQUER família de exporter responde.
_p("entrada.volume_na_janela", "entrada", "Requisições na janela", "escalar",
   unidade="requisições")
_p("entrada.distribuicao_de_status", "entrada", "Distribuição de status", "lista",
   unidade="requisições", desempate="chave")
# volume não tem faixa: 12 mil requisições é muito para um painel interno e pouco para uma
# API pública — "bom" depende do serviço, e inventar um número aqui seria chute com agulha.
_p("entrada.latencia", "entrada", "Latência (p95)", "escalar", unidade="ms",
   faixa={"sentido": "menor_melhor", "bom_ate": 700, "ruim_a_partir": 1500, "maximo": 3000})
# Opcional: exige a etiqueta `router`, que nem todo proxy publica, e a ausência não é defeito.
_p("entrada.por_servico", "entrada", "Acessos por serviço web", "lista", desempate="nome",
   opcional=True)
# Opcional: só existe com `logs_url`. São 24 consultas ao Loki, e por isso vão por último: uma
# rodada lenta perde janelas de log, não a CPU dos serviços.
_p("entrada.urls_mais_acessadas", "entrada", "URLs mais acessadas", "lista", unidade="acessos",
   desempate="nome", opcional=True, por_ultimo=True)


# --- papel `fila`: tudo sai do mesmo endpoint de listagem de filas, então o custo marginal de
# cada pergunta é uma extração, não uma requisição. A ordem é a do relatório: o que existe (e,
# pelo limiar, o que está parado), quem consome e a que ritmo.
#
# "Filas" e "Filas com acúmulo" eram duas perguntas e saíam no relatório como a MESMA lista,
# ordenada do mesmo jeito, duas vezes. Viraram uma: a lista é "Filas", e as paradas aparecem
# como achado, uma por linha, na seção de achados. (Decisão do dono, 2026-09-21.)
#
# Fila morta NÃO entra nesta versão: a visão geral da API traz o total de mensagens do broker,
# não o da fila morta, e distinguir as duas exigiria filtrar por convenção de nome (`dlq`,
# `dead`). Convenção de nome é expressão, e expressão não cabe na linguagem fechada — publicar
# o total do broker com aquele rótulo seria mentir com número certo.
_p("fila.filas", "fila", "Filas", "lista", unidade="mensagens", desempate="nome",
   limiar={"quando": "consumidores == 0 e prontas > 0",
           "regra": "fila_sem_consumidor", "severidade": "high"})
_p("fila.consumidores_por_fila", "fila", "Consumidores por fila", "lista",
   unidade="consumidores", desempate="nome")
_p("fila.taxa_entrada_saida", "fila", "Entrada × saída", "lista", unidade="mensagens/s",
   desempate="nome")


# --- papel `app`: 49 componentes heterogêneos. NÃO existe métrica que toda aplicação publique
# — uma API em Go, um worker em Python e um frontend estático não compartilham vocabulário.
# O que existe para qualquer uma é o que o CONTAINER consome, e quem responde isso é o
# exporter de container (cAdvisor e equivalentes), não a aplicação.
#
# Sem faixa: "CPU boa" depende do limite configurado para aquele serviço, e 80% num container
# com 2 vCPU reservadas é saúde, enquanto 80% sem limite nenhum é vizinho prestes a sofrer.
#
# Sem limiar: reinício em excesso JÁ vira `OPS_TASK_FAILING` no coletor docker, que lê
# `tasks_failed` direto do Swarm. Produzir o mesmo achado por outro caminho contaria duas
# vezes o mesmo problema.
_p("app.cpu", "app", "CPU em uso", "escalar", unidade="%")
_p("app.memoria", "app", "Memória em uso", "escalar", unidade="bytes")
# Opcional: cAdvisor sem `container_last_seen` não é defeito, e a coluna fica "sem dado". O
# período é o da retenção medida no Prometheus: 7 dias.
_p("app.disponibilidade_7d", "app", "Disponibilidade em 7 dias", "escalar", unidade="%", opcional=True)


# --- papel `banco`: o que qualquer exporter de banco responde. Conexões e tamanho são o
# vocabulário comum de Postgres, MySQL e Mongo; o resto diverge por motor.
#
# Sem faixa: "muitas conexões" só existe contra o limite configurado, e a razão entre as duas
# exige aritmética, que a linguagem de limiar não tem de propósito. Quando houver derivação
# declarada para a razão, ela vira limiar — não antes.
_p("banco.conexoes", "banco", "Conexões abertas", "escalar", unidade="conexões")
_p("banco.tamanho", "banco", "Tamanho dos dados", "escalar", unidade="bytes")


# --- papel `cache`: vocabulário comum de Redis e Memcached.
#
# Evicções sem faixa de propósito: cache com política LRU evicta POR DESENHO quando atinge o
# limite, e isso é funcionamento normal, não defeito. O número importa — ele diz que o cache
# está no teto —, mas transformá-lo em achado acusaria metade das instalações saudáveis.
#
# Taxa de acerto é opcional porque só a família do Redis responde hoje, com a razão calculada
# na própria consulta PromQL. Cache sem nenhuma leitura na janela não tem taxa: a consulta
# devolve NaN, e isso sai como `sem dados`, sem derrubar a cobertura.
_p("cache.memoria_usada", "cache", "Memória em uso", "escalar", unidade="bytes")
_p("cache.evicções", "cache", "Chaves descartadas", "escalar", unidade="chaves")
_p("cache.acerto", "cache", "Taxa de acerto", "escalar", unidade="%", opcional=True)


# --- papel `observabilidade`: NENHUMA pergunta nesta versão, de propósito.
# Prometheus, Loki e Grafana não compartilham vocabulário de métrica — alvo de scrape só
# existe no primeiro, taxa de ingestão de log só no segundo. Não há pergunta que QUALQUER
# família responda, e inventar uma só para o papel deixar de aparecer mudo seria preencher a
# lacuna com ruído. O relatório continua dizendo, em "O que falta declarar", que este papel
# não tem pergunta nesta versão — que é a verdade.


# --- papel `maquina`: um componente por nó do cluster, medido pelo exporter de nó. Opcionais
# porque o cluster pode não ter esse exporter, e a ausência dele não é defeito da medição.
# Sem limiar: o relatório já pinta os percentuais, e achado de capacidade é outra decisão.
_p("maquina.cpu", "maquina", "CPU", "escalar", unidade="%", opcional=True)
_p("maquina.memoria", "maquina", "Memória", "escalar", unidade="%", opcional=True)
_p("maquina.disco", "maquina", "Disco", "escalar", unidade="%", opcional=True)
# Negativo quer dizer "não está enchendo": a consulta devolve -1 e o bloco escreve "estável".
_p("maquina.disco_dias", "maquina", "Dias até encher o disco", "escalar", unidade="dias", opcional=True)


# O limiar é um produtor de achado, ao lado de `lib/rules.py` e do coletor http. Declarar o que
# ele produz — derivado, nunca digitado — é o que deixa o teste do registro de regras enxergar
# os três produtores em vez de dois.
REGRAS_PRODUZIDAS = {p["limiar"]["regra"] for p in PERGUNTAS.values() if p["limiar"]}


def do_papel(papel):
    """As perguntas daquele papel, na ordem declarada (barata → cara).

    Papel sem pergunta devolve lista vazia de propósito: perguntar sem quem responda só
    produziria `sem dados` em série, e isso é ruído, não honestidade.
    """
    return [PERGUNTAS[id] for id in ORDEM.get(papel, [])]
