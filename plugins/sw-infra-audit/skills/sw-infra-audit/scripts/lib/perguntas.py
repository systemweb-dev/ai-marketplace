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
       por_ultimo=False, na_ordem=True):
    PERGUNTAS[id] = {"id": id, "papel": papel, "titulo": titulo, "forma": forma,
                     "unidade": unidade, "limiar": limiar, "desempate": desempate,
                     "faixa": faixa, "opcional": opcional, "por_ultimo": por_ultimo}
    if na_ordem:
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
# Sem limiar (o catálogo recusa limiar em opcional): o achado de capacidade vem de
# lib/capacidade.py, que só lê resposta com número — para host e nó do cluster.
_p("maquina.cpu", "maquina", "CPU", "escalar", unidade="%", opcional=True)
_p("maquina.memoria", "maquina", "Memória", "escalar", unidade="%", opcional=True)
_p("maquina.disco", "maquina", "Disco", "escalar", unidade="%", opcional=True)
# Negativo quer dizer "não está enchendo": a consulta devolve -1 e o bloco escreve "estável".
_p("maquina.disco_dias", "maquina", "Dias até encher o disco", "escalar", unidade="dias", opcional=True)
_p("maquina.carga", "maquina", "Carga (5 min, por CPU)", "escalar", unidade="%", opcional=True)
_p("maquina.desde_o_boot", "maquina", "Desde o último boot", "escalar", unidade="dias", opcional=True)


# --- perguntas de componente de HOST: fora do `ORDEM[papel]` de propósito. Ali elas cairiam também
# nos clusters, sem quem respondesse, e a cobertura contaria cada uma como lacuna. Quem as escolhe é
# `perguntas_do_componente`, só para componente com `origem` (veio de um servidor).
#
# As comuns valem para QUALQUER serviço de host, do banco ao app próprio. O papel delas é o
# pseudo-papel `servico`, que não existe em `lib/papel.py`: nenhum componente É um serviço genérico.
# Opcionais, sem CPU (uma leitura só daria a média desde o início) e sem limiar: serviço parado já é
# `servico_declarado_ausente`.
PAPEL_COMUM = "servico"
COMUNS = []


def _comum(id, titulo, forma, unidade=None):
    _p(id, PAPEL_COMUM, titulo, forma, unidade=unidade, opcional=True, na_ordem=False)
    COMUNS.append(id)


_comum("servico.ativo", "Estado do serviço", "escalar")
_comum("servico.desde", "No ar há", "escalar", unidade="dias")
_comum("servico.reinicios", "Reinícios", "escalar", unidade="reinícios")
_comum("servico.memoria", "Memória do serviço", "escalar", unidade="bytes")
# Só para componente com `backup_pasta`; o achado de atraso nasce em lib/limites_produto.py.
_p("banco.backup_idade", "banco", "Idade do backup mais novo", "escalar", unidade="dias",
   opcional=True, na_ordem=False)

# Só os catálogos de produto (references/produtos-host/) respondem estas: nenhum exporter conhecido
# as publica no mesmo formato. Sem faixa e sem limiar; os achados vêm de lib/limites_produto.py.
_p("banco.tamanho_por_banco", "banco", "Tamanho por banco", "lista", unidade="bytes",
   desempate="nome", opcional=True, na_ordem=False)
_p("banco.uso_de_conexoes", "banco", "Conexões em uso contra o limite", "escalar", unidade="%",
   opcional=True, na_ordem=False)
_p("banco.consultas_lentas", "banco", "Consultas lentas desde o início", "escalar",
   unidade="consultas", opcional=True, na_ordem=False)
_p("banco.binlog", "banco", "Arquivos de binlog", "lista", unidade="bytes", desempate="nome",
   opcional=True, na_ordem=False)
_p("busca.colecoes", "busca", "Coleções", "lista", unidade="pontos", desempate="nome",
   opcional=True, na_ordem=False)


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


def perguntas_do_componente(componente):
    """As perguntas DESTE componente, na ordem: as do papel; e, só se ele veio de um host
    (`origem`), as comuns, a idade do backup (com `backup_pasta`) e as do catálogo do produto.
    Pergunta repetida (`banco.tamanho` do papel e do catálogo) entra uma vez, na primeira posição.

    Componente de alvo `docker` não tem `origem`: recebe exatamente `do_papel` — um `produto`
    declarado ali não puxa catálogo nenhum. Catálogo inválido não derruba a coleta: as perguntas dele
    ficam de fora aqui, e o adaptador de produto diz o motivo nas que o papel já pergunta.
    """
    ids = list(ORDEM.get(componente.get("papel"), []))
    if componente.get("origem"):
        from lib import catalogo_produto

        ids += COMUNS
        if componente.get("backup_pasta"):
            ids.append("banco.backup_idade")
        try:
            catalogo = catalogo_produto.do_produto(componente.get("produto"))
        except catalogo_produto.CatalogoInvalido:
            catalogo = None
        if catalogo:
            ids += [p["id"] for p in catalogo["pergunta"]]
    vistos, saida = set(), []
    for id_ in ids:
        if id_ not in vistos:
            vistos.add(id_)
            saida.append(PERGUNTAS[id_])
    return saida
