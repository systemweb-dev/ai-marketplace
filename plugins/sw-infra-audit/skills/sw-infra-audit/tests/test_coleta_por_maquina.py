"""Máquina: nó do Swarm ligado às séries do exporter pelo container, com dados fictícios."""
import json

import pytest

import collect
from collect import componentes_de_maquina
from lib import catalogo, identificacao, perguntas, produtos
from lib.adaptadores import promql
from lib.blocos import render_bloco
from lib.cobertura import medir
from lib.coletores import docker
from lib.coletores.docker_allowlist import check
from lib.dados_blocos import dados_do_papel

FONTE = "http://p.exemplo.test:9090"
CTX = {"at": "2026-11-01T10:00:00Z", "janela": "24h", "timeout": 2}
ID_A, ID_B = "aaaaaaaaaaaa", "bbbbbbbbbbbb"
TASK_A, TASK_B = "taskaaaaaaaaaaaaaaaaaaaaa", "taskbbbbbbbbbbbbbbbbbbbbb"


def test_cada_no_vira_componente_com_a_fonte_do_alvo():
    alvo = {"metricas_url": "http://p"}
    assert componentes_de_maquina(alvo, {"nodes": [{"hostname": "db-1"}]}) == [
        {"nome": "db-1", "papel": "maquina", "papel_origem": "declarado",
         "metricas_url": "http://p", "respostas": [], "achados": []}]


def test_sem_fonte_nao_cria_componente():
    assert componentes_de_maquina({}, {"nodes": [{"hostname": "db-1"}]}) == []


def test_familia_carrega():
    from lib.catalogo import familias as carregar
    assert "node-exporter" in [f["familia"] for f in carregar()]


def test_nodes_fora_do_swarm_nao_quebra():
    assert componentes_de_maquina({"metricas_url": "http://p"}, {"nodes": {"status": "n/a"}}) == []


def test_componente_carrega_o_id_do_container_do_seu_no():
    fatos = {"nodes": [{"hostname": "db-1"}, {"hostname": "web-1"}, {"hostname": "sem-exporter"}],
             "exporter_por_container": {ID_A: "web-1", ID_B: "db-1"}}
    maquinas = {c["nome"]: c for c in componentes_de_maquina({"metricas_url": FONTE}, fatos)}
    assert maquinas["db-1"]["valor_de_etiqueta"] == ID_B
    assert maquinas["web-1"]["valor_de_etiqueta"] == ID_A
    assert "valor_de_etiqueta" not in maquinas["sem-exporter"]


def test_dois_containers_no_mesmo_no_nao_escolhem_um():
    fatos = {"nodes": [{"hostname": "db-1"}],
             "exporter_por_container": {ID_A: "db-1", ID_B: "db-1"}}
    assert "valor_de_etiqueta" not in componentes_de_maquina({"metricas_url": FONTE}, fatos)[0]


def test_perguntas_sao_opcionais_e_sem_limiar():
    assert [p["id"] for p in perguntas.do_papel("maquina")] == [
        "maquina.cpu", "maquina.memoria", "maquina.disco", "maquina.disco_dias"]
    assert all(p["opcional"] and not p["limiar"] for p in perguntas.do_papel("maquina"))


def _familia():
    return next(f for f in catalogo.familias() if f["familia"] == "node-exporter")


def test_catalogo_nao_prova_papel_e_usa_nodename():
    familia = _familia()
    assert familia["identifica_papel"] is False
    assert familia["seletor"] == {"etiqueta": "nodename", "valor_do_componente": True}
    assert familia["identificacao"]["metrica_presente"] == "node_uname_info"


def test_consultas_juntam_por_uname_com_seletor_por_ultimo():
    consultas = {p["id"]: p["query"] for p in _familia()["pergunta"]}
    assert set(consultas) == {"maquina.cpu", "maquina.memoria", "maquina.disco", "maquina.disco_dias"}
    for query in consultas.values():
        assert "on (instance, job)" in query and "node_uname_info{%SELETOR%}" in query
    assert 'mode="idle"' in consultas["maquina.cpu"]
    assert consultas["maquina.disco"].count('mountpoint="/"') == 2


def test_previsao_do_disco_fica_finita_e_olha_a_raiz_em_sete_dias():
    """`_converter` descarta infinito, então a consulta é quem marca o disco que não enche."""
    query = next(p["query"] for p in _familia()["pergunta"] if p["id"] == "maquina.disco_dias")
    ramo_que_enche, ramo_estavel = query.split(" or ")
    assert ">= 0 < Inf" in ramo_que_enche and ramo_estavel.endswith(", -1, -1))")
    assert query.count("deriv(") == 2 and query.count('mountpoint="/"') == 4
    assert query.count('mountpoint="/"}[7d]') == 2 and "%JANELA%" not in query
    assert all(ramo.startswith("min(") for ramo in (ramo_que_enche, ramo_estavel))


@pytest.mark.parametrize("bruto,esperado", [("-1", "estável"), ("12.6", "enche em 13 dias"),
                                            ("+Inf", "Não medido"), ("NaN", "Não medido")])
def test_previsao_do_disco_da_fonte_ao_bloco(monkeypatch, bruto, esperado):
    _prometheus(monkeypatch, [ID_A], {ID_A: bruto})
    registro = _coletar(["db-1"], {ID_A: "db-1"})
    html = render_bloco("maquinas", dados_do_papel("maquinas", [registro]))
    assert esperado in html


def test_valor_booleano_do_seletor_e_validado(tmp_path):
    arquivo = tmp_path / "x.toml"
    arquivo.write_text('familia="x"\nprioridade=1\npapel="maquina"\nidentifica_papel=false\n'
                       '[identificacao]\nmetrica_presente="x"\n'
                       '[seletor]\netiqueta="y"\nvalor_do_componente="sim"\n', encoding="utf-8")
    with pytest.raises(catalogo.CatalogoInvalido, match="booleano"):
        catalogo.carregar_arquivo(arquivo)


def _reconhecida(valores):
    return dict(_familia(), valores=valores)


def _maquina(valor=None):
    componente = {"nome": "db-1", "papel": "maquina", "papel_origem": "declarado",
                  "metricas_url": FONTE}
    return dict(componente, valor_de_etiqueta=valor) if valor else componente


def test_resolver_usa_o_valor_do_componente():
    saida = identificacao.resolver([_maquina(ID_A)], {FONTE: [_reconhecida([ID_A, ID_B])]})
    assert saida["db-1"]["familias"][0]["seletor"] == f'nodename="{ID_A}"'


def test_exporter_unico_nao_vira_medida_de_todas_as_maquinas():
    """Com um valor só, o caminho comum usaria o exporter inteiro para todo nó."""
    saida = identificacao.resolver([_maquina()], {FONTE: [_reconhecida([ID_A])]})
    assert saida["db-1"]["familias"] == []
    assert identificacao.motivo_da_falta(saida["db-1"], "maquina.cpu")


def test_id_que_a_fonte_nao_publica_nao_vira_seletor():
    saida = identificacao.resolver([_maquina(ID_B)], {FONTE: [_reconhecida([ID_A])]})
    assert saida["db-1"]["familias"] == []


def test_familia_que_prova_papel_nao_reclassifica_a_maquina():
    votante = {"familia": "z", "papel": "banco", "identifica_papel": True,
               "seletor": {"etiqueta": "job"}, "valores": ["db-1"]}
    saida = identificacao.resolver([_maquina()], {FONTE: [votante]})
    assert (saida["db-1"]["papel"], saida["db-1"]["papel_origem"]) == ("maquina", "declarado")


@pytest.mark.parametrize("rotulo,esperado", [
    ("prom/node-exporter:v1.5.0 mon_nodes", True),
    ("exemplo/template-swarm-monitoring:node-exporter-v1.5.0 mon_nodes", True),
    ("exemplo/qualquer:1 mon_node-exporter", True),
    ("exemplo/cadvisor-fork:1 mon_cadvisor", False),
])
def test_produto_que_liga_o_container_ao_no(rotulo, esperado):
    assert produtos.container_liga_no(rotulo) is esperado


def test_produtos_recusa_marca_que_nao_e_booleana():
    with pytest.raises(produtos.ProdutosInvalidos, match="booleano"):
        produtos._validar({"nome": "x", "imagem": ["x"], "container_liga_no": "sim"}, "t")


class _Docker:
    """Responde só ao que a allowlist deixa: cada comando passa por `check` antes."""

    def __init__(self, tasks, containers, ps_falha=False):
        self.tasks, self.containers, self.ps_falha = tasks, containers, ps_falha
        self.comandos = []

    def __call__(self, cmd, timeout=None):
        check(cmd)
        self.comandos.append(cmd)
        if cmd[1:3] == ["service", "ps"]:
            return None if self.ps_falha else "\n".join(json.dumps(t) for t in self.tasks)
        return self.containers.get(cmd[-1])


def _task(id_, no, estado="Running 2 days ago"):
    return {"ID": id_, "Node": no, "CurrentState": estado}


EXPORTER = [{"name": "mon_exporter", "image": "prom/node-exporter", "tag": "v1.5.0"},
            {"name": "app_web", "image": "exemplo/web", "tag": "1"}]


def test_mapa_de_container_para_hostname_so_com_leitura():
    rodar = _Docker([_task(TASK_A, "db-1"), _task(TASK_B, "web-1")],
                    {TASK_A: f"{ID_A}0123456789\n", TASK_B: f"{ID_B}0123456789\n"})
    mapa, falhas = docker._exporter_por_container(EXPORTER, rodar)
    assert mapa == {ID_A: "db-1", ID_B: "web-1"} and falhas == []
    assert [c[1] for c in rodar.comandos] == ["service", "inspect", "inspect"]
    assert rodar.comandos[0][3] == "mon_exporter"


def test_task_que_nao_esta_em_execucao_fica_de_fora():
    rodar = _Docker([_task(TASK_A, "db-1", "Preparing 1 second ago"), _task(TASK_B, "")],
                    {TASK_A: f"{ID_A}\n", TASK_B: f"{ID_B}\n"})
    assert docker._exporter_por_container(EXPORTER, rodar) == ({}, [])
    assert len(rodar.comandos) == 1


@pytest.mark.parametrize("saida", ["<no value>\n", "", None])
def test_saida_que_nao_e_id_de_container_nao_liga(saida):
    rodar = _Docker([_task(TASK_A, "db-1")], {TASK_A: saida})
    assert docker._exporter_por_container(EXPORTER, rodar)[0] == {}


def test_id_de_task_estranho_nao_derruba_a_coleta():
    rodar = _Docker([_task("--format", "db-1")], {})
    assert docker._exporter_por_container(EXPORTER, rodar) == ({}, [])


def test_listagem_que_falha_e_dita():
    assert docker._exporter_por_container(EXPORTER, _Docker([], {}, ps_falha=True)) == (
        {}, ["mon_exporter"])


def test_servicos_fora_do_swarm_nao_quebram():
    assert docker._exporter_por_container({"status": "n/a"}, _Docker([], {})) == ({}, [])


def _prometheus(monkeypatch, valores, medidas):
    """Responde pela consulta recebida. `medidas` vai do id do container ao número."""
    from urllib.parse import parse_qs, urlparse
    consultas = []

    def falso(url, destinos, timeout=None):
        consulta = parse_qs(urlparse(url).query)["query"][0]
        consultas.append(consulta)
        resultado = []
        if consulta == "vector(1)":
            resultado = [{"metric": {}, "value": [0, "1"]}]
        elif consulta.startswith("count by (nodename)"):
            resultado = [{"metric": {"nodename": v}, "value": [0, "1"]} for v in valores]
        else:
            resultado = [{"metric": {}, "value": [0, str(numero)]}
                         for id_, numero in medidas.items() if f'nodename="{id_}"' in consulta]
        return 200, json.dumps({"status": "success", "data": {"result": resultado}})

    monkeypatch.setattr(promql.http_get, "get_com_status", falso)
    return consultas


def _coletar(nodes, mapa, servicos=()):
    fatos = {"nodes": [{"hostname": h} for h in nodes], "exporter_por_container": mapa}

    def coletor(alvo, contexto):
        return {"saude": "🟢", "fatos": fatos, "componentes": list(servicos)}

    return collect.coletar_alvo({"nome": "c", "tipo": "docker", "context": "x",
                                 "metricas_url": FONTE}, coletor, dict(CTX), [promql])


def _por_nome(registro):
    return {c["nome"]: c for c in registro["componentes"]}


def test_ponta_a_ponta_cada_no_recebe_o_numero_do_seu_container(monkeypatch):
    consultas = _prometheus(monkeypatch, [ID_A, ID_B], {ID_A: 11.5, ID_B: 77})
    registro = _coletar(["db-1", "web-1"], {ID_A: "db-1", ID_B: "web-1"})

    maquinas = _por_nome(registro)
    valor = {n: {r["pergunta"]: r.get("valor") for r in c["respostas"]} for n, c in maquinas.items()}
    assert valor == {"db-1": dict.fromkeys(perguntas.ORDEM["maquina"], 11.5),
                     "web-1": dict.fromkeys(perguntas.ORDEM["maquina"], 77.0)}
    assert maquinas["db-1"]["respostas"][0]["fonte"] == "promql:node-exporter"
    assert maquinas["db-1"]["papel_origem"] == "declarado"
    assert sum(1 for c in consultas if f'nodename="{ID_A}"' in c) == 4

    dados = dados_do_papel("maquinas", [registro])
    assert [i["nome"] for i in dados["itens"]] == ["db-1", "web-1"]
    assert dados["itens"][0]["disco"] == 11.5
    html = render_bloco("maquinas", dados)
    assert "<b>db-1</b>" in html and "77%" in html


def test_sem_mapeamento_fica_sem_dados_e_o_nome_do_no_continua_certo(monkeypatch):
    _prometheus(monkeypatch, [ID_A], {ID_A: 50})
    registro = _coletar(["db-1"], {})

    maquina = _por_nome(registro)["db-1"]
    assert all(r["sem_dados"] for r in maquina["respostas"])
    assert "não foi ligado" in maquina["respostas"][0]["motivo"]
    cobertura = medir(registro)
    assert (cobertura["perguntadas"], cobertura["respondidas"]) == (4, 0)
    assert {m["componente"] for m in cobertura["mudos"]} == {"db-1"}
    assert dados_do_papel("maquinas", [registro]) == {"motivo": "sem fonte medida para este tipo"}


def test_no_com_nome_de_servico_nao_toma_o_papel_do_servico(monkeypatch):
    _prometheus(monkeypatch, [ID_A], {})
    servico = {"nome": "db-1", "papel": "banco", "papel_origem": "imagem", "metricas_url": FONTE}
    registro = _coletar(["db-1", "web-1"], {}, [servico])

    maquinas = _por_nome(registro)
    assert maquinas["db-1"]["papel"] == "banco" and maquinas["web-1"]["papel"] == "maquina"
    assert any("db-1" in n["motivo"] for n in registro["nao_coletado"])


def test_hostname_repetido_vira_uma_linha_so(monkeypatch):
    _prometheus(monkeypatch, [ID_A], {})
    registro = _coletar(["db-1", "db-1"], {})
    assert [c["nome"] for c in registro["componentes"]] == ["db-1"]


def _montar(rodar, servico="mon_exporter"):
    linha = json.dumps({"Name": servico})
    inspecao = json.dumps([{"Spec": {"Name": servico, "TaskTemplate": {"ContainerSpec": {
        "Image": "prom/node-exporter:v1.5.0"}}, "Mode": {"Global": {}}}}])

    def run(cmd, timeout, errors=None):
        if cmd[1:3] == ["service", "ls"]:
            return linha
        if cmd[1:3] == ["service", "inspect"]:
            return inspecao
        if cmd[1:3] == ["service", "ps"] or cmd[1] == "inspect":
            return rodar(cmd, errors)
        return None

    return docker.assemble_report(run, 1, "x", "", None)


def test_inspect_de_task_que_falha_e_dito_com_o_motivo():
    def rodar(cmd, errors):
        if cmd[1] == "inspect":
            errors.append({"cmd": "docker inspect", "reason": "task sumiu do manager"})
            return None
        return json.dumps(_task(TASK_A, "db-1"))

    falhas = [n for n in _montar(rodar)["not_collected"] if "db-1" in n["what"]]
    assert [n["reason"] for n in falhas] == ["task sumiu do manager"]
    assert "mon_exporter" in falhas[0]["what"]


def test_inspect_que_nao_devolve_id_e_dito():
    def rodar(cmd, errors):
        return "<no value>\n" if cmd[1] == "inspect" else json.dumps(_task(TASK_A, "db-1"))

    falhas = [n for n in _montar(rodar)["not_collected"] if "db-1" in n["what"]]
    assert [n["reason"] for n in falhas] == ["o inspect não devolveu o id do container"]
