"""O papel sai de quem respondeu, não do nome da imagem.

Testes puros: nenhum socket, nenhum Prometheus falso. O que fala com a fonte é
`promql.reconhecer`; aqui só se decide o que a resposta dela significa.
"""
from lib import identificacao


def _familia(nome, papel, prova=True, prioridade=30, etiqueta="job", perguntas=()):
    return {"familia": nome, "papel": papel, "identifica_papel": prova,
            "prioridade": prioridade, "seletor": {"etiqueta": etiqueta},
            "pergunta": [{"id": p} for p in perguntas]}


def _reconhecido(familia, valores):
    return dict(familia, valores=list(valores))


def _componente(nome, papel="app", origem="padrão", fonte="http://f", exportador=False):
    return {"nome": nome, "papel": papel, "papel_origem": origem,
            "metricas_url": fonte, "exportador": exportador}


BROKER = _familia("rabbitmq-prometheus", "fila", perguntas=["fila.filas"])
CADVISOR = _familia("cadvisor", "app", prova=False, prioridade=40,
                    etiqueta="container_label_com_docker_swarm_service_name",
                    perguntas=["app.cpu", "app.memoria"])
PG = _familia("postgres-exporter", "banco", prioridade=40, perguntas=["banco.conexoes"])
MYSQL = _familia("mysqld-exporter", "banco", prioridade=40, perguntas=["banco.conexoes"])
TRAEFIK = _familia("traefik", "entrada", perguntas=["entrada.latencia"])
# A prioridade EMPATA com a do traefik de propósito: com 50 contra 30, a terceira chave do
# desempate já decidia e a segunda (quem prova papel) ficava sem trava — removê-la deixava a
# suíte inteira verde.
HTTP = _familia("http-generico", "entrada", prova=False, prioridade=30,
                perguntas=["entrada.latencia"])


def test_familia_que_prova_confirma_o_papel():
    """O caso que motiva o ciclo: a imagem é desconhecida, a série não é."""
    comp = _componente("pilha_desconhecida", papel="app", origem="padrão")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(BROKER,
                                                                     ["pilha_desconhecida"])]})

    assert saida["pilha_desconhecida"]["papel"] == "fila"
    assert saida["pilha_desconhecida"]["papel_origem"] == "exporter rabbitmq-prometheus"


def test_cadvisor_casa_todo_mundo_e_nao_confirma_ninguem():
    """A etiqueta do cAdvisor É o nome do serviço: casar com ela não prova nada."""
    comps = [_componente(n) for n in ("app_api", "dados_pg", "cache_redis")]
    nomes = [c["nome"] for c in comps]

    saida = identificacao.resolver(comps, {"http://f": [_reconhecido(CADVISOR, nomes)]})

    for nome in nomes:
        assert saida[nome]["papel_origem"] == "padrão", nome
        assert saida[nome]["papel"] == "app"
        # mas ela MEDE: a família entra no conjunto, com o seletor casado
        assert [f["familia"]["familia"] for f in saida[nome]["familias"]] == ["cadvisor"]
        assert saida[nome]["familias"][0]["seletor"] == \
            f'container_label_com_docker_swarm_service_name="{nome}"'


def test_http_generico_nao_promove_uma_api_a_entrada():
    comp = _componente("app_api", papel="app", origem="padrão")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(HTTP, ["app_api"])]})

    assert saida["app_api"]["papel"] == "app"
    assert saida["app_api"]["papel_origem"] == "padrão"


def test_container_do_exportador_nunca_recebe_papel_provado():
    """D4, o falso positivo invertido: a etiqueta `job` nomeia o EXPORTER, e o núcleo de
    `<stack>_postgres-exporter` e de `postgres-exporter` é o mesmo `exporter`."""
    comp = _componente("infra_postgres-exporter", exportador=True)

    saida = identificacao.resolver([comp],
                                   {"http://f": [_reconhecido(PG, ["postgres-exporter"])]})

    assert saida["infra_postgres-exporter"]["papel"] == "app"
    assert saida["infra_postgres-exporter"]["papel_origem"] == "padrão"


def test_duas_familias_que_provam_nao_confirmam():
    comp = _componente("dados_db")
    reconhecido = [_reconhecido(PG, ["dados_db"]), _reconhecido(MYSQL, ["dados_db"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})

    assert saida["dados_db"]["papel_origem"] == "padrão"
    assert saida["dados_db"]["ambiguidade"] == ["mysqld-exporter", "postgres-exporter"]


def test_declarado_vence_o_papel_mas_passa_pelo_passe():
    """Restrição verificável 3: a declaração vence o PAPEL, não a identificação — sem
    `(familia, seletor)` nenhuma pergunta é respondida."""
    comp = _componente("infra_broker", papel="cache", origem="declarado")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(BROKER,
                                                                     ["infra_broker"])]})

    assert saida["infra_broker"]["papel"] == "cache"
    assert saida["infra_broker"]["papel_origem"] == "declarado"
    assert [f["familia"]["familia"] for f in saida["infra_broker"]["familias"]] \
        == ["rabbitmq-prometheus"]


def test_o_conjunto_guarda_as_duas_familias_que_cobrem_o_componente():
    """Um banco coberto por cAdvisor E postgres-exporter precisa dos dois: um responde
    `app.*`, o outro `banco.*`. Com um par só, a ordem alfabética daria o cAdvisor."""
    comp = _componente("dados_pg")
    reconhecido = [_reconhecido(CADVISOR, ["dados_pg"]), _reconhecido(PG, ["dados_pg"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})

    assert saida["dados_pg"]["papel"] == "banco"
    assert sorted(f["familia"]["familia"] for f in saida["dados_pg"]["familias"]) \
        == ["cadvisor", "postgres-exporter"]


def test_sem_casamento_a_familia_entra_com_seletor_vazio():
    """A série existe mas a etiqueta não nomeia o componente, e há UM valor só: a resposta sai
    do exporter inteiro, e o papel NÃO é promovido. Medir não é provar."""
    comp = _componente("borda_proxy")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(TRAEFIK, ["edge"])]})

    assert saida["borda_proxy"]["papel_origem"] == "padrão"
    assert saida["borda_proxy"]["familias"][0]["seletor"] == ""


def test_varios_valores_e_nenhum_casa_nao_entrega_a_soma():
    """A garantia da v0.14.0: com vários valores e nenhum casando, o número sem filtro é a SOMA
    de todos, e entregá-lo como se fosse de um é a mentira que aquele ciclo consertou."""
    # O nome não pode compartilhar núcleo com nenhum dos valores: `cdn_borda` tem núcleo
    # `borda` e casaria o segundo valor, fazendo o teste provar o contrário do que afirma.
    comp = _componente("entrega_cdn")

    saida = identificacao.resolver([comp],
                                   {"http://f": [_reconhecido(TRAEFIK, ["proxy", "borda"])]})

    assert saida["entrega_cdn"]["familias"] == []
    assert [f["familia"] for f in saida["entrega_cdn"]["soma_de_todos"]] == ["traefik"]
    assert "soma de todos" in identificacao.motivo_da_falta(saida["entrega_cdn"],
                                                            "entrada.latencia")


def test_componente_sem_fonte_fica_como_chegou():
    comp = _componente("app_web", papel="app", origem="imagem", fonte=None)

    saida = identificacao.resolver([comp], {})

    assert saida["app_web"] == {"papel": "app", "papel_origem": "imagem", "familias": [],
                                "ambiguidade": [], "soma_de_todos": [],
                                "papel_anterior": "app"}


# ---------------------------------------------------------------- desempate por pergunta
def test_quem_prova_papel_responde_a_pergunta_disputada():
    """`traefik` e `http-generico` declaram os mesmos `entrada.*`. Sem regra, quem responde
    dependeria da ordem de `catalogo.familias()`."""
    comp = _componente("borda_proxy")
    reconhecido = [_reconhecido(HTTP, ["borda_proxy"]), _reconhecido(TRAEFIK, ["borda_proxy"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})
    escolhida = identificacao.familia_da_pergunta(saida["borda_proxy"], "entrada.latencia")

    assert escolhida["familia"]["familia"] == "traefik"


def test_seletor_casado_vence_seletor_vazio_na_mesma_pergunta():
    """`postgres-exporter` e `mysqld-exporter` declaram ambos `banco.conexoes`, provam papel os
    dois e têm a MESMA prioridade 40 — o desempate cairia no nome, e `mysqld` venceria."""
    comp = _componente("dados_pg")
    reconhecido = [_reconhecido(MYSQL, ["mysqld"]),          # um valor, nenhum casa → vazio
                   _reconhecido(PG, ["dados_pg"])]           # casa

    saida = identificacao.resolver([comp], {"http://f": reconhecido})
    escolhida = identificacao.familia_da_pergunta(saida["dados_pg"], "banco.conexoes")

    assert escolhida["familia"]["familia"] == "postgres-exporter"
    assert escolhida["seletor"] == 'job="dados_pg"'


def test_empate_entre_duas_que_provam_resolve_pela_prioridade():
    comp = _componente("dados_db")
    reconhecido = [_reconhecido(MYSQL, ["dados_db"]),
                   _reconhecido(dict(PG, prioridade=35), ["dados_db"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})
    escolhida = identificacao.familia_da_pergunta(saida["dados_db"], "banco.conexoes")

    assert escolhida["familia"]["familia"] == "postgres-exporter"


def test_pergunta_que_ninguem_declara_nao_tem_familia():
    comp = _componente("app_api")
    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(CADVISOR, ["app_api"])]})

    assert identificacao.familia_da_pergunta(saida["app_api"], "fila.filas") is None


def test_o_motivo_da_soma_so_vale_para_a_pergunta_daquela_familia():
    """O motivo errado em escala: um componente medido pelo cAdvisor e com traefik na soma
    recebia "o exporter traefik cobre vários componentes" para `app.cpu` — pergunta que o
    traefik nem declara. O motivo certo ali é "não reconheci a família", e ele é o fallback."""
    comp = _componente("app_api")
    reconhecido = [_reconhecido(CADVISOR, ["app_api"]),
                   _reconhecido(TRAEFIK, ["proxy", "borda"])]

    saida = identificacao.resolver([comp], {"http://f": reconhecido})

    assert identificacao.motivo_da_falta(saida["app_api"], "app.cpu") is None
    assert "soma de todos" in identificacao.motivo_da_falta(saida["app_api"],
                                                            "entrada.latencia")


def test_familia_sem_valor_nenhum_nao_entra_na_soma():
    """`valores == []` é "a família não respondeu nada aqui", não "cobre vários componentes".
    Com `else` em vez de `elif valores`, ela geraria motivo sobre uma família muda."""
    comp = _componente("app_api")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(TRAEFIK, [])]})

    assert saida["app_api"]["familias"] == []
    assert saida["app_api"]["soma_de_todos"] == []


def test_papel_anterior_fica_disponivel_para_o_relatorio():
    """D3 quer "confirmado pelo exporter; a imagem sugeria banco" — quem sobrescreve o papel
    precisa devolver o que havia antes, senão o relatório não tem como dizer isso."""
    comp = _componente("dados_db", papel="banco", origem="imagem")

    saida = identificacao.resolver([comp], {"http://f": [_reconhecido(BROKER, ["dados_db"])]})

    assert saida["dados_db"]["papel"] == "fila"
    assert saida["dados_db"]["papel_anterior"] == "banco"
