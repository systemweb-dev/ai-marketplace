from lib.capa import _nomes_por_estado, saude_por_sistema
from lib.nota import nota_geral
from lib import servicos_host


def _comp(nome, ativo=None, papel="banco"):
    respostas = [] if ativo is None else [{"pergunta": "servico.ativo", "valor": ativo, "fonte": "ssh"}]
    return {"nome": nome, "papel": papel, "respostas": respostas, "achados": []}


def _host(componentes, achados=()):
    return {"nome": "banco-01", "tipo": "host", "coletado": True, "saude": "🟢", "fatos": {},
            "componentes": [{"nome": "banco-01", "papel": "maquina", "respostas": [], "achados": []},
                            *componentes], "achados": list(achados), "dimensoes": {}}


AUSENTE = {"regra": "servico_declarado_ausente", "componente": "pg", "objeto": "pg", "alvo": "banco-01",
           "severidade": "high"}


def test_ativo_parado_ausente_e_nao_medido():
    alvo = _host([_comp("mariadb", "ativo"), _comp("redis", "failed", "cache"), _comp("pg"), _comp("qdrant")],
                 [AUSENTE])
    assert {s["name"]: s["replicas"] for s in servicos_host.servicos(alvo)} == \
        {"mariadb": "1/1", "redis": "0/1", "pg": "0/1", "qdrant": None}


def test_nota_conta_o_host_e_deixa_o_nao_medido_fora_da_base():
    alvo = _host([_comp("mariadb", "ativo"), _comp("pg"), _comp("qdrant")], [AUSENTE])
    nota = nota_geral([alvo], [])
    assert (nota["online"], nota["base"]) == (1, 2) and nota["limites"]["fora"] == 1


def test_aceite_do_ausente_vale_por_componente():
    alvo = _host([_comp("mariadb", "ativo"), _comp("pg")], [AUSENTE])
    aceite = {"alvo": "banco-01", "regra": "servico_declarado_ausente", "objeto": "pg", "vencido": False}
    nota = nota_geral([alvo], [aceite])
    assert (nota["online"], nota["base"]) == (1, 1)


def test_host_sem_vpn_nao_tem_base_e_fica_parcial():
    alvo = {"nome": "banco-01", "tipo": "host", "coletado": True, "saude": "sem dados", "fatos": {},
            "componentes": [], "achados": [], "dimensoes": {}}
    docker = {"nome": "c", "tipo": "docker", "coletado": True, "dimensoes": {}, "achados": [],
              "fatos": {"services": [{"name": "x_api", "replicas": "1/1", "tasks_failed": 0}]}}
    nota = nota_geral([alvo, docker], [])
    assert nota["base"] == 1 and nota["parcial"] is True


def test_capa_lista_o_servico_parado_do_host():
    alvo = _host([_comp("mariadb", "ativo"), _comp("pg")], [AUSENTE])
    assert _nomes_por_estado({"alvos": [alvo], "aceites": []})["fora"] == ["pg"]


def test_saude_por_sistema_mostra_o_host_como_um_sistema():
    alvo = _host([_comp("mariadb", "ativo"), _comp("pg")], [AUSENTE])
    html = saude_por_sistema([alvo], [])
    assert "banco-01" in html and "1/2" in html


def test_host_sem_vpn_aparece_na_saude_como_sem_dado():
    alvo = {"nome": "cache-02", "tipo": "host", "coletado": True, "saude": "sem dados", "fatos": {},
            "componentes": [], "achados": [], "dimensoes": {}}
    html = saude_por_sistema([alvo], [])
    assert "cache-02" in html and "Sem dado" in html


def test_aceite_com_componente_e_sem_objeto_vale_so_para_o_componente():
    """`aceitar --componente pg` grava objeto vazio: o aceite não pode calar o redis parado."""
    alvo = _host([_comp("mariadb", "ativo"), _comp("redis", "failed", "cache"), _comp("pg")], [AUSENTE])
    aceite = {"alvo": "banco-01", "regra": "servico_declarado_ausente", "componente": "pg", "objeto": None,
              "vencido": False}
    nota = nota_geral([alvo], [aceite])
    assert (nota["online"], nota["base"], nota["limites"]["fora"]) == (1, 2, 1)


def test_host_que_respondeu_so_com_a_maquina_nao_sai_sem_dado():
    alvo = _host([])
    alvo["fatos"] = {"sistema": "Debian GNU/Linux 12 (bookworm)"}
    assert "Sem dado" not in saude_por_sistema([alvo], [])
