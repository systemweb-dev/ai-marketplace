"""O passe roda por FONTE, e o custo não depende de quantos componentes existem.

Restrição verificável nº 1 do spec: no máximo K×(F+1) consultas de identificação. É teto, não
igualdade — quando a sonda da fonte falha, as F consultas são curto-circuitadas.
"""
import collect
from lib.adaptadores import promql

from test_adaptador_promql import CONTEXTO, _vetor, prometheus  # noqa: F401


def _componente(nome, base, papel="app"):
    return {"nome": nome, "papel": papel, "papel_origem": "padrão",
            "metricas_url": base, "exportador": False, "respostas": []}


def test_identificacao_nao_depende_do_numero_de_componentes(prometheus):
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (traefik_service_requests_total)",
                         _vetor([({"job": "borda_proxy"}, 1)])))
    componentes = [_componente(f"app_{i}", base) for i in range(20)]
    componentes.append(_componente("borda_proxy", base, papel="entrada"))

    contexto = dict(CONTEXTO, cache={})
    collect.identificar(componentes, contexto, [promql], collect.Prazo(120))

    # O teto é K×(F+1): as sondas `vector(1)` são o "+1" e PRECISAM entrar na conta — contando
    # só as `count by`, o teste provaria apenas "nenhuma descoberta repetida", que o teste do
    # `reconhecer` já prova, e não o teto.
    from lib import catalogo

    sondas = [q for q in falso.RECEBIDAS if q == "vector(1)"]
    descobertas = [q for q in falso.RECEBIDAS if q.startswith("count by")]
    # F vem do CATÁLOGO, não do observado: com `familias = len(set(descobertas))`, as três
    # asserções passavam até se o passe parasse na primeira família.
    familias = len(catalogo.familias())
    assert len(sondas) == 1, "uma sonda por fonte, não por componente"
    assert len(set(descobertas)) == familias, "toda família é perguntada, uma vez cada"
    assert len(descobertas) == familias, "uma consulta por família, não por componente"
    assert len(falso.RECEBIDAS) <= familias + 1, "o teto K×(F+1) foi furado"


def test_fonte_morta_nao_gasta_uma_consulta_por_familia(monkeypatch, prometheus):
    """A fonte está VIVA no teste; quem falha é a sonda, por monkeypatch.

    Apontar o componente para uma porta fechada faria as consultas irem para lá, e o
    `falso.RECEBIDAS == []` passaria com ou sem o curto-circuito — um teste que não pode falhar
    não prova nada.
    """
    base, falso = prometheus
    monkeypatch.setattr(promql, "alcancavel", lambda *a, **k: False)

    contexto = dict(CONTEXTO, cache={})
    passe = collect.identificar([_componente("app_a", base)], contexto, [promql],
                                collect.Prazo(120))

    assert [q for q in falso.RECEBIDAS if q.startswith("count by")] == []
    assert passe["fontes_mortas"] == [base], "a nota de fonte morta não pode sumir com a sonda"


def test_fork_de_cache_e_reconhecido_pelo_exporter_do_original(prometheus):
    """O caso que o Objetivo do spec diz que prova o desenho, ponta a ponta.

    Um fork compatível em protocolo é raspado pelo MESMO exporter e publica a MESMA série. O
    `produtos.toml` não o conhece pelo nome — ele chega como `app` — e o exporter o identifica
    como `cache` sem saber que é um fork, porque identifica a série, não a imagem.
    """
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (redis_memory_used_bytes)",
                         _vetor([({"job": "cache_fork"}, 1)])))
    componente = _componente("cache_fork", base)

    contexto = dict(CONTEXTO, cache={})
    collect.identificar([componente], contexto, [promql], collect.Prazo(120))

    assert componente["papel"] == "cache"
    assert componente["papel_origem"] == "exporter redis-exporter"


def test_o_papel_confirmado_chega_ao_componente(prometheus):
    base, falso = prometheus
    falso.REGRAS.append(("count by (job) (rabbitmq_queue_messages_ready)",
                         _vetor([({"job": "pilha_desconhecida"}, 1)])))
    componente = _componente("pilha_desconhecida", base)

    contexto = dict(CONTEXTO, cache={})
    collect.identificar([componente], contexto, [promql], collect.Prazo(120))

    assert componente["papel"] == "fila"
    assert componente["papel_origem"] == "exporter rabbitmq-prometheus"


def test_o_passe_roda_dentro_da_coleta(monkeypatch):
    """A ligação: `identificar` existe e é testado, mas se ninguém o chamar o ciclo inteiro fica
    morto fora dos testes — `contexto["cache"]["resolvido"]` nunca é preenchido,
    `familia_do_componente` devolve sempre `(None, None)` e todo componente sai `sem_dados`."""
    chamadas = []
    monkeypatch.setattr(collect, "identificar",
                        lambda *a, **k: chamadas.append(a) or {"resolvido": {},
                                                               "fontes_mortas": []})

    def coletor(alvo, contexto):
        return {"saude": "🟢", "dimensoes": {}, "fatos": {}, "achados": [],
                "componentes": [{"nome": "app_a", "papel": "app", "respostas": [],
                                 "achados": []}]}

    collect.coletar_alvo({"nome": "c", "tipo": "docker", "context": "ctx"}, coletor,
                         {"timeout": 5, "orcamento": 10, "at": "2026-10-05T00:00:00Z"})

    assert chamadas, "`identificar` não foi chamado dentro de `coletar_alvo`"


def test_fonte_morta_vira_nota_no_alvo(monkeypatch):
    """A nota que o `else:` do coletor produzia hoje não pode sumir junto com a sonda."""
    monkeypatch.setattr(collect, "identificar",
                        lambda *a, **k: {"resolvido": {},
                                         "fontes_mortas": ["http://fonte.invalida:9090"]})

    def coletor(alvo, contexto):
        return {"saude": "🟢", "dimensoes": {}, "fatos": {}, "achados": [], "componentes": []}

    registro = collect.coletar_alvo({"nome": "c", "tipo": "docker", "context": "ctx"}, coletor,
                                    {"timeout": 5, "orcamento": 10, "at": "2026-10-05T00:00:00Z"})

    assert any("não respondeu a uma consulta trivial" in n["motivo"]
               for n in registro["nao_coletado"])


def test_a_allowlist_de_rede_sai_do_alvo(monkeypatch):
    """A garantia mudou de casa junto com a sonda: antes vivia no coletor, agora no passe.

    Host não declarado não é alcançável, e a allowlist carrega HOST E PORTA. O `/metrics` colado
    no fim da URL tem de ser normalizado: sem isso a consulta vira `.../metrics/api/v1/query` →
    404 → "a fonte não respondeu", e o dono vai caçar problema de rede que não existe.
    """
    visto = {}

    def espiar(url, permitidos, timeout=8):
        visto.setdefault("url", url)
        visto["permitidos"] = permitidos
        return 200, '{"status":"success","data":{"result":[{"value":[0,"1"]}]}}'

    monkeypatch.setattr("lib.http_get.get_com_status", espiar)

    collect.identificar([_componente("app_a", "http://127.0.0.1:9090/metrics")],
                        dict(CONTEXTO, cache={}), [promql], collect.Prazo(120))

    assert visto["permitidos"] == [("127.0.0.1", 9090)], "host E porta, vindos do alvo"
    assert visto["url"].startswith("http://127.0.0.1:9090/api/v1/query")
