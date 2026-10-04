"""A cobertura mede quanto das perguntas que a skill SABE fazer foi respondido.

Papel sem pergunta registrada fica fora do denominador: contá-lo deixaria a cobertura
permanentemente péssima e, portanto, inútil — ninguém olha um número que não se move
quando se conserta o que dá para consertar.
"""
from lib.cobertura import medir


def alvo(componentes):
    return {"nome": "cluster", "saude": "🟢", "achados": [], "componentes": componentes}


def resp(pergunta, valor=None, sem_dados=False, motivo=None):
    r = {"pergunta": pergunta}
    if sem_dados:
        r["sem_dados"] = True
        r["motivo"] = motivo or "a fonte não respondeu"
    else:
        r["valor"] = valor
        r["fonte"] = "promql:teste"
    return r


def test_conta_so_as_perguntas_que_a_skill_sabe_fazer():
    """49 componentes de papel `app` não têm pergunta: não entram no denominador."""
    c = [{"nome": "proxy", "papel": "entrada", "respostas": [resp("entrada.latencia", 12)]},
         {"nome": "prom", "papel": "observabilidade", "respostas": []},
         {"nome": "loki", "papel": "observabilidade", "respostas": []}]

    m = medir(alvo(c))

    assert m["perguntadas"] == 3, \
        "`entrada` tem 3 perguntas; `observabilidade` segue sem nenhuma, de propósito"
    assert m["respondidas"] == 1


def test_sem_dados_nao_conta_como_resposta():
    c = [{"nome": "proxy", "papel": "entrada",
          "respostas": [resp("entrada.latencia", sem_dados=True, motivo="sem fonte")]}]

    m = medir(alvo(c))

    assert m["respondidas"] == 0
    assert m["pct"] == 0


def test_erro_interno_nao_conta_como_resposta():
    r = resp("entrada.latencia", 12)
    r["erro_interno"] = True
    c = [{"nome": "proxy", "papel": "entrada", "respostas": [r]}]

    assert medir(alvo(c))["respondidas"] == 0


def test_lista_vazia_em_pergunta_com_limiar_nao_conta():
    """`fila.filas` devolvida como [] passaria por respondida — e a cobertura diria 100%
    sem nada ter sido medido. É a mesma cegueira por outra porta."""
    c = [{"nome": "broker", "papel": "fila", "respostas": [resp("fila.filas", [])]}]

    assert medir(alvo(c))["respondidas"] == 0


def test_nada_a_perguntar_e_sem_dados_nao_zero_por_cento():
    """Alvo sem componente com pergunta: cobertura indefinida, não 0%. Tratar
    "nada a perguntar" como 0% é a mesma mentira ao contrário."""
    c = [{"nome": "prom", "papel": "observabilidade", "respostas": []}]

    m = medir(alvo(c))

    assert m["perguntadas"] == 0
    assert m["pct"] is None, "0% afirmaria que perguntei e não fui respondido"


def test_mudos_trazem_componente_pergunta_e_motivo():
    """Um 🟡 sem nada que o explique inverte o problema. A cobertura carrega o porquê."""
    c = [{"nome": "broker", "papel": "fila",
          "respostas": [resp("fila.filas", sem_dados=True, motivo="senha_env ausente")]}]

    mudos = medir(alvo(c))["mudos"]

    assert {"componente": "broker", "pergunta": "fila.filas",
            "motivo": "senha_env ausente"} in mudos


# ------------------------------------------------- a lista vazia no próprio dado
import collect


def test_lista_vazia_com_limiar_vira_sem_dados_no_report():
    """A fonte respondeu "nenhum item". Isso não é uma medida de zero filas paradas —
    é a ausência da medida, e o report.json tem de dizer isso."""
    limiar = {"quando": "consumidores == 0", "regra": "fila_sem_consumidor",
              "severidade": "high"}
    resposta = {"pergunta": "fila.filas", "valor": [], "fonte": "admin_http:amqp"}

    saida = collect._sem_contadores(resposta, limiar)

    assert saida.get("sem_dados") is True
    assert "nenhum item" in saida.get("motivo", "")


def test_lista_vazia_SEM_limiar_continua_como_resposta():
    """Sem limiar nenhum achado se perdeu: lista vazia ali é uma resposta legítima."""
    resposta = {"pergunta": "entrada.distribuicao_de_status", "valor": [], "fonte": "promql:x"}

    saida = collect._sem_contadores(resposta, None)

    assert not saida.get("sem_dados")


# ------------------------------------------------------- o teto do verde
from lib.cobertura import teto_por_cobertura


def com_limiar_mudo(saude="🟢"):
    """Alvo saudável cujo `fila.filas` (limiar `high`) não foi respondido."""
    a = alvo([{"nome": "broker", "papel": "fila",
               "respostas": [resp("fila.filas", sem_dados=True, motivo="senha ausente")]}])
    a["saude"] = saude
    return a


def test_limiar_sem_resposta_impede_o_verde():
    """Um achado podia ter nascido e não nasceu: não dá para assinar "convergido"."""
    a = com_limiar_mudo()

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🟡"


def test_teto_nunca_vira_vermelho():
    """Cegueira não é prova de que algo está fora do ar."""
    a = com_limiar_mudo()

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] != "🔴"


def test_teto_nunca_desce_um_alvo_ja_vermelho():
    a = com_limiar_mudo(saude="🔴")

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🔴", "é teto, não piso"


def test_limiar_de_severidade_baixa_nao_trava():
    """`_PIOR_ESTADO` ignora `low`: travar o verde por um limiar que o próprio achado não
    travaria seria mais rígido com a ausência do que com o fato."""
    a = alvo([{"nome": "x", "papel": "fila",
               "respostas": [resp("fila.filas", sem_dados=True)]}])
    a["saude"] = "🟢"

    teto_por_cobertura(a, aceites_vigentes=set(),
                       severidade_por_pergunta={"fila.filas": "low"})

    assert a["saude"] == "🟢"


def test_aceite_vigente_dispensa_a_trava():
    """O achado não contaria de qualquer forma: travar por ele cobra duas vezes."""
    a = com_limiar_mudo()

    teto_por_cobertura(a, aceites_vigentes={"fila_sem_consumidor"})

    assert a["saude"] == "🟢"


def test_estado_fora_da_escala_nao_e_tocado():
    """`sem dados` não é um estado bom a ser piorado: é ausência de leitura."""
    a = com_limiar_mudo(saude="sem dados")

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "sem dados"


def test_tudo_respondido_nao_mexe_na_saude():
    a = alvo([{"nome": "broker", "papel": "fila",
               "respostas": [resp("fila.filas", [{"nome": "q", "prontas": 0}]),
                             resp("fila.consumidores_por_fila", [{"nome": "q"}]),
                             resp("fila.taxa_entrada_saida", [{"nome": "q"}])]}])
    a["saude"] = "🟢"

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🟢"


# ------------------------------------------------ o campo chega ao report.json
def test_o_relatorio_carrega_a_cobertura_do_alvo():
    """A cobertura mora em campo próprio, FORA de `dimensoes`: entrar como 5ª dimensão faria
    `nota.py` elegê-la como a dimensão mais fraca e estourar em `ROTULO[pior]` (KeyError)."""
    a = alvo([{"nome": "broker", "papel": "fila",
               "respostas": [resp("fila.filas", sem_dados=True, motivo="senha ausente")]}])
    a["saude"] = "🟢"
    a["dimensoes"] = {}

    collect.aplicar_cobertura([a], aceites_vigentes=set())

    assert a["saude"] == "🟡"
    assert a["cobertura"]["pct"] == 0
    assert "cobertura" not in a["dimensoes"], "não é dimensão pontuada"
    assert a["cobertura"]["mudos"][0]["motivo"] == "senha ausente"


# ------------------------------------- restrição verificável nº 6 (do spec)
import json
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _fixture(nome):
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


def test_restricao_6_limiar_respondido_mantem_vermelho():
    a = _fixture("cobertura_limiar_respondido")

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🔴", "o achado existe; a cobertura não mexe num alvo já pior"


def test_restricao_6_limiar_mudo_vira_amarelo_e_nunca_verde():
    a = _fixture("cobertura_limiar_mudo")

    teto_por_cobertura(a, aceites_vigentes=set())

    assert a["saude"] == "🟡"
    assert a["saude"] != "🟢", "assinar convergido sem ter medido é o defeito que isto conserta"


# Vocabulário NEUTRO que as fixturas desta skill podem usar. A asserção é POSITIVA de
# propósito: a primeira versão deste teste listava os nomes reais a proibir — e aí o próprio
# teste virava o vazamento que ele existe para impedir. O gate de segurança do repositório
# pegou isso antes do commit.
NOMES_NEUTROS = {"cluster-exemplo", "pilha_fila", "exemplo", "pedidos"}


def test_restricao_6_a_fixture_so_usa_nomes_neutros():
    """O repositório é público: fixture com nome de cluster real é vazamento."""
    import re

    for nome in ("cobertura_limiar_mudo", "cobertura_limiar_respondido"):
        dado = _fixture(nome)
        usados = {dado["nome"]} | {c["nome"] for c in dado["componentes"]}
        estranhos = usados - NOMES_NEUTROS
        assert not estranhos, f"{nome}: nome fora do vocabulário neutro: {sorted(estranhos)}"
        # o `onde` não pode carregar host, IP nem context real
        assert re.fullmatch(r"context: exemplo", dado["onde"]), dado["onde"]


# ------------------------------------------------ o relatório explica o amarelo
import build_report


def _relatorio_com_cobertura_baixa():
    a = _fixture("cobertura_limiar_mudo")
    teto_por_cobertura(a, aceites_vigentes=set())
    a["cobertura"] = medir(a)
    a["nao_coletado"] = []
    a["fatos"] = {}
    return {"schema_version": 3, "generated_at": "2026-10-03T09:00:00Z",
            "resumo": "", "fortes": [], "fracos": [], "recomendacoes": [], "aceites": [],
            "historico": None,
            "inventario": [{"nome": a["nome"], "tipo": "docker", "onde": a["onde"],
                            "saude": a["saude"]}],
            "alvos": [a]}


def test_o_relatorio_diz_por_que_a_cobertura_caiu():
    html = build_report.render_html_v3(_relatorio_com_cobertura_baixa())

    assert "pilha_fila" in html, "qual componente"
    assert "fila.filas" in html, "qual pergunta"
    assert "senha não está definida" in html, "qual motivo"


# ------------------- a mesma medida, contada uma vez (exporter inteiro)
def test_medida_do_exporter_inteiro_conta_uma_vez_na_cobertura():
    """Dois componentes recebendo o MESMO valor da MESMA fonte não são duas medidas.
    Contando duas, a cobertura dizia 6 de 9 quando o honesto era 3 de 6."""
    r = lambda n: {"pergunta": n, "valor": 652.63, "fonte": "promql:traefik (exporter inteiro)"}
    c = [{"nome": "nginx", "papel": "entrada",
          "respostas": [r("entrada.latencia"), r("entrada.volume_na_janela")]},
         {"nome": "traefik", "papel": "entrada",
          "respostas": [r("entrada.latencia"), r("entrada.volume_na_janela")]}]

    m = medir(alvo(c))

    assert m["respondidas"] == 2, "duas perguntas distintas, não quatro"


def test_medidas_distintas_continuam_contando_cada_uma():
    c = [{"nome": "a", "papel": "entrada",
          "respostas": [{"pergunta": "entrada.latencia", "valor": 10, "fonte": "promql:a"}]},
         {"nome": "b", "papel": "entrada",
          "respostas": [{"pergunta": "entrada.latencia", "valor": 99, "fonte": "promql:b"}]}]

    assert medir(alvo(c))["respondidas"] == 2
