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
"""

PERGUNTAS = {}
ORDEM = {}


def _p(id, papel, titulo, forma, unidade=None, limiar=None, desempate=None, faixa=None):
    PERGUNTAS[id] = {"id": id, "papel": papel, "titulo": titulo, "forma": forma,
                     "unidade": unidade, "limiar": limiar, "desempate": desempate,
                     "faixa": faixa}
    ORDEM.setdefault(papel, []).append(id)
    return id


# --- papel `entrada`: nesta versão, só o que QUALQUER família de exporter responde.
# As que dependem de etiqueta de rota (top_rotas, top_dominios, erros_por_rota) exigem
# exporter que exponha rota — entram junto com o adaptador de log, no plano 4.
_p("entrada.volume_na_janela", "entrada", "Requisições na janela", "escalar",
   unidade="requisições")
_p("entrada.distribuicao_de_status", "entrada", "Distribuição de status", "lista",
   unidade="requisições", desempate="chave")
# volume não tem faixa: 12 mil requisições é muito para um painel interno e pouco para uma
# API pública — "bom" depende do serviço, e inventar um número aqui seria chute com agulha.
_p("entrada.latencia", "entrada", "Latência (p95)", "escalar", unidade="ms",
   faixa={"sentido": "menor_melhor", "bom_ate": 700, "ruim_a_partir": 1500, "maximo": 3000})


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
# Taxa de acerto NÃO entra nesta versão, embora fosse a pergunta mais útil do papel: o Redis
# publica acertos e erros como dois contadores separados, e a razão entre eles exige
# aritmética que a linguagem de extração não tem de propósito. Declarar a pergunta sem
# ninguém capaz de respondê-la deixaria todo cache com uma linha `sem dados` permanente e
# derrubaria a cobertura sem que houvesse nada a consertar. Entra junto com a derivação
# declarada de razão.
_p("cache.memoria_usada", "cache", "Memória em uso", "escalar", unidade="bytes")
_p("cache.evicções", "cache", "Chaves descartadas", "escalar", unidade="chaves")


# --- papel `observabilidade`: NENHUMA pergunta nesta versão, de propósito.
# Prometheus, Loki e Grafana não compartilham vocabulário de métrica — alvo de scrape só
# existe no primeiro, taxa de ingestão de log só no segundo. Não há pergunta que QUALQUER
# família responda, e inventar uma só para o papel deixar de aparecer mudo seria preencher a
# lacuna com ruído. O relatório continua dizendo, em "O que falta declarar", que este papel
# não tem pergunta nesta versão — que é a verdade.


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
