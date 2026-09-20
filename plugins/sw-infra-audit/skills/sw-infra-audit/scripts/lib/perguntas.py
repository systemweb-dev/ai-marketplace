"""As perguntas canônicas — o que se quer saber, independente de quem responde.

O papel do componente escolhe as perguntas; o adaptador responde o que souber. Separar as duas
coisas é o que permite trocar a fonte (exporter, API de administração, log) sem reescrever o
relatório, e é o que faz `sem dados` ter motivo em vez de virar buraco.

Campos de cada pergunta:
  forma      escalar · lista · serie — o relatório desenha de acordo
  unidade    o que o número significa (requisicoes, ms, bytes…)
  limiar     o que transforma informação em ACHADO; sem limiar, é só informação
  desempate  obrigatório em lista: empate de valor não pode herdar a ordem da fonte
"""

PERGUNTAS = {}
ORDEM = {}


def _p(id, papel, titulo, forma, unidade=None, limiar=None, desempate=None):
    PERGUNTAS[id] = {"id": id, "papel": papel, "titulo": titulo, "forma": forma,
                     "unidade": unidade, "limiar": limiar, "desempate": desempate}
    ORDEM.setdefault(papel, []).append(id)
    return id


# --- papel `entrada`: nesta versão, só o que QUALQUER família de exporter responde.
# As que dependem de etiqueta de rota (top_rotas, top_dominios, erros_por_rota) exigem
# exporter que exponha rota — entram junto com o adaptador de log, no plano 4.
_p("entrada.volume_na_janela", "entrada", "Requisições na janela", "escalar",
   unidade="requisições")
_p("entrada.distribuicao_de_status", "entrada", "Distribuição de status", "lista",
   unidade="requisições", desempate="chave")
_p("entrada.latencia", "entrada", "Latência (p95)", "escalar", unidade="ms")


def do_papel(papel):
    """As perguntas daquele papel, na ordem declarada (barata → cara).

    Papel sem pergunta devolve lista vazia de propósito: perguntar sem quem responda só
    produziria `sem dados` em série, e isso é ruído, não honestidade.
    """
    return [PERGUNTAS[id] for id in ORDEM.get(papel, [])]
