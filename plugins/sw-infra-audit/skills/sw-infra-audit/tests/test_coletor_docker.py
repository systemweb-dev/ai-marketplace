# tests/test_coletor_docker.py
from lib.coletores import docker as coletor

# o assemble_report grava `verdict` (green/yellow/red/unknown), NÃO `status`
BRUTO = {"health": {"verdict": "green"}, "nodes": [{"id": "n1"}],
         # forma REAL do achado v1: rule_id/severity(crit|high|med|low)/object/evidence
         "findings": [{"rule_id": "spof", "object": "traefik", "severity": "high",
                       "evidence": "1 réplica"}],
         "dimensions": {"seguranca": {"nota": "🟡"}}}


def test_devolve_o_bloco_do_alvo_com_saude_fatos_e_achados(monkeypatch):
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))

    bloco = coletor.coletar({"nome": "cluster", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": "2026-09-19T10:00:00Z"})

    assert bloco["saude"] == "🟢"
    assert bloco["fatos"]["nodes"] == [{"id": "n1"}]
    assert bloco["achados"] == [{"regra": "spof", "objeto": "traefik", "severidade": "high",
                                 "detalhe": "1 réplica", "alvo": "cluster"}]
    assert bloco["dimensoes"] == {"seguranca": {"nota": "🟡"}}


def test_sem_metricas_url_o_alvo_segue_e_as_metricas_ficam_sem_dados(monkeypatch):
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert bloco["saude"] == "🟢"
    assert any("metricas_url" in n["motivo"] for n in bloco["nao_coletado"])


def test_endpoint_que_nao_responde_vira_sem_dados_e_nao_achado(monkeypatch):
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))
    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "metricas_url": "http://127.0.0.1:9090"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    # A outra metade desta garantia — a NOTA de fonte morta — mudou de casa junto com a sonda:
    # ela nasce no passe de identificação e é registrada por `coletar_alvo`. Ver
    # `test_passe_de_identificacao.py::test_fonte_morta_vira_nota_no_alvo`.
    assert len(bloco["achados"]) == 1, "endpoint mudo não vira achado novo"


def test_a_descoberta_nunca_roda_na_coleta(monkeypatch):
    """Descoberta alcançaria host que o usuário não declarou — ela só existe no modo configurar."""
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))
    monkeypatch.setattr(coletor.discover, "propose",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("descobriu na coleta")))

    coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                    {"timeout": 5, "orcamento": 10, "at": ""})


import pytest


@pytest.mark.parametrize("verdict,saude", [("green", "🟢"), ("yellow", "🟡"), ("red", "🔴"),
                                           ("unknown", "sem dados")])
def test_veredito_do_coletor_vira_o_vocabulario_do_relatorio(monkeypatch, verdict, saude):
    """O v1 fala green/yellow/red; o relatório v2 fala 🟢/🟡/🔴 — misturar os dois faz o
    inventário mostrar alvos incomparáveis lado a lado."""
    monkeypatch.setattr(coletor, "assemble_report",
                        lambda **kwargs: {"health": {"verdict": verdict}, "findings": []})

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert bloco["saude"] == saude


def test_o_que_o_coletor_nao_conseguiu_ver_chega_ao_relatorio(monkeypatch):
    """`docker info indisponível` sumia: o relatório dizia "sem achados" sem dizer que faltou dado."""
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: {
        "health": {"verdict": "green"}, "findings": [],
        "not_collected": [{"what": "docker info", "reason": "indisponível"}],
        "collection_errors": ["timeout ao listar tasks"]})

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "metricas_url": "http://127.0.0.1:9090"},
                            {"timeout": 5, "orcamento": 10, "at": ""})
    motivos = " | ".join(n["motivo"] for n in bloco["nao_coletado"])

    assert "docker info" in motivos and "indisponível" in motivos
    assert "timeout ao listar tasks" in motivos


def test_severidade_do_v1_vira_o_vocabulario_do_relatorio(monkeypatch):
    """O v1 fala "med"; o relatório e o coletor http falam "medium". Misturar os dois faz a
    ordenação por gravidade cair no fim da lista sem ninguém perceber."""
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: {
        "health": {"verdict": "yellow"},
        "findings": [{"rule_id": "sem_limite", "object": "api", "severity": "med",
                      "evidence": "sem limite de memória"}]})

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert bloco["achados"][0]["severidade"] == "medium"
    assert bloco["achados"][0]["regra"] == "sem_limite"


def test_erro_de_coleta_vira_texto_legivel_e_nao_dicionario(monkeypatch):
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: {
        "health": {"verdict": "unknown"}, "findings": [],
        "collection_errors": [{"cmd": "docker node ls", "reason": "não é swarm manager"}]})

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    motivo = bloco["nao_coletado"][-1]["motivo"]
    assert motivo == "docker node ls: não é swarm manager"


def test_o_comando_roda_no_context_do_alvo_e_nao_no_docker_local(monkeypatch):
    """O docker escolhe o cluster por DOCKER_CONTEXT. Sem isso, a coleta fala com o daemon local
    e o relatório sairia etiquetado com o nome do cluster errado — foi o que a validação pegou."""
    ambientes = []
    from lib import runner

    monkeypatch.setattr(runner.subprocess, "run",
                        lambda cmd, **kwargs: ambientes.append(kwargs.get("env")) or
                        type("R", (), {"returncode": 0, "stdout": "{}", "stderr": ""})())

    runner.run(["docker", "info"], timeout=5, context="meu-cluster")

    assert ambientes[0]["DOCKER_CONTEXT"] == "meu-cluster"


def test_coletor_passa_o_context_do_alvo_para_o_runner(monkeypatch):
    vistos = {}
    monkeypatch.setattr(coletor, "assemble_report",
                        lambda **kwargs: vistos.update(kwargs) or {"health": {"verdict": "green"},
                                                                   "findings": []})

    coletor.coletar({"nome": "c", "tipo": "docker", "context": "prod"},
                    {"timeout": 5, "orcamento": 10, "at": ""})

    assert vistos["context"] == "prod"


def test_cada_servico_vira_componente_com_o_papel_da_imagem(monkeypatch):
    """O inventário do cluster já sabe o que é cada serviço; o papel é o que decide quais
    perguntas ele recebe."""
    bruto = dict(BRUTO)
    bruto["services"] = [{"name": "traefik", "image": "traefik:v3"},
                         {"name": "postgres_principal", "image": "postgres:16"},
                         {"name": "api", "image": "registro.interno/api:1.2"}]
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: bruto)

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    papeis = {c["nome"]: c["papel"] for c in bloco["componentes"]}
    assert papeis == {"traefik": "entrada", "postgres_principal": "banco", "api": "app"}


def test_componente_herda_a_url_de_metricas_do_alvo_e_o_declarado_vence(monkeypatch):
    bruto = dict(BRUTO)
    bruto["services"] = [{"name": "traefik", "image": "traefik:v3"},
                         {"name": "api", "image": "api:1"}]
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: bruto)

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "metricas_url": "http://127.0.0.1:9090",
                             "componente": [{"nome": "api", "papel": "entrada",
                                             "metricas_url": "http://127.0.0.1:9091"}]},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    por_nome = {c["nome"]: c for c in bloco["componentes"]}
    assert por_nome["traefik"]["metricas_url"] == "http://127.0.0.1:9090"
    assert por_nome["api"]["metricas_url"] == "http://127.0.0.1:9091"
    assert por_nome["api"]["papel"] == "entrada", "o papel declarado vence o da imagem"


def test_o_impacto_calculado_chega_ao_relatorio(monkeypatch):
    """`impact.build` roda desde sempre e o resultado era descartado: a chave não estava na
    lista copiada para `fatos`."""
    bruto = dict(BRUTO)
    bruto["impact_points"] = [{"titulo": "Proxy é ponto único"}]
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: bruto)

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert bloco["fatos"]["impact_points"] == [{"titulo": "Proxy é ponto único"}]


def test_componente_declarado_que_nao_casa_com_servico_e_dito(monkeypatch):
    """No Swarm o serviço se chama `<stack>_<serviço>`. Declarar `nome = "rabbitmq"` para o
    serviço `infra_rabbitmq` fazia a declaração sumir calada — e a seção de pendências dizia
    "o componente não declara `admin_url`" a quem tinha declarado."""
    bruto = dict(BRUTO, services=[{"name": "infra_rabbitmq", "image": "rabbitmq:4"}])
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(bruto))

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "componente": [{"nome": "rabbitmq", "papel": "fila",
                                             "admin_url": "http://exemplo.test:15672"}]},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    motivos = [n["motivo"] for n in bloco["nao_coletado"]]
    assert any("rabbitmq" in m and "infra_rabbitmq" in m for m in motivos), motivos


def test_componente_declarado_que_casa_nao_gera_aviso(monkeypatch):
    bruto = dict(BRUTO, services=[{"name": "infra_rabbitmq", "image": "rabbitmq:4"}])
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(bruto))

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "componente": [{"nome": "infra_rabbitmq", "papel": "fila"}]},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert not any("não corresponde" in n["motivo"] for n in bloco["nao_coletado"])


def test_disco_e_stacks_chegam_aos_fatos(monkeypatch):
    """O relatório mostra disco e agrupa por aplicação a partir dos fatos. Antes, `disk` era
    coletado e descartado no filtro, e `stacks` nunca era preenchido — as duas seções do
    relatório não tinham de onde sair."""
    bruto = dict(BRUTO)
    bruto["disk"] = [{"tipo": "Images", "total": 42, "ativo": 12, "tamanho": "9GB",
                      "recuperavel": "4GB"}]
    bruto["services"] = [
        {"name": "loja_web", "image": "nginx", "tag": "1.27", "kind": "ingress",
         "routing_labels": {"traefik.http.routers.web.rule": "Host(`loja.exemplo.test`)"}},
        {"name": "loja_api", "image": "app", "tag": "2.1", "kind": "app", "routing_labels": {}},
        {"name": "avulso", "image": "redis", "tag": "7", "kind": "cache", "routing_labels": {}},
    ]
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: bruto)

    fatos = coletor.coletar({"nome": "cluster", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": "2026-09-19T10:00:00Z"})["fatos"]

    assert fatos["disk"][0]["recuperavel"] == "4GB"
    stacks = {g["stack"]: g for g in fatos["stacks"]}
    assert set(stacks) == {"loja", "avulso"}
    assert [s["name"] for s in stacks["loja"]["services"]] == ["loja_web", "loja_api"]
    assert stacks["loja"]["routes"], "a rota do Traefik é o que responde 'como está roteando'"


def test_sem_services_as_stacks_nao_quebram(monkeypatch):
    bruto = dict(BRUTO)
    bruto["services"] = {"status": "n/a", "reason": "não-swarm"}
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: bruto)

    fatos = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": "x"})["fatos"]

    assert fatos.get("stacks") in (None, [])


# ------------------------------------- a origem do papel, e quem só observa (D3, D4)
def test_o_componente_nasce_com_a_origem_do_papel(monkeypatch):
    """`papel_origem` é a ponta das restrições verificáveis 2 e 3 no caminho real: com ele
    fixo em `padrão`, a evidência sobrescreve o papel DECLARADO pelo dono."""
    bruto = dict(BRUTO)
    bruto["services"] = [{"name": "borda_proxy", "image": "traefik:v3"},
                         {"name": "app_api", "image": "registry.local/api:1"},
                         {"name": "infra_broker", "image": "rabbitmq:3.13"}]
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: bruto)

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "componente": [{"nome": "infra_broker", "papel": "cache"}]},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    por_nome = {c["nome"]: c for c in bloco["componentes"]}
    assert por_nome["borda_proxy"]["papel_origem"] == "imagem"
    assert por_nome["app_api"]["papel_origem"] == "padrão", "imagem desconhecida não é palpite"
    assert por_nome["infra_broker"]["papel_origem"] == "declarado"
    # guardado para o relatório dizer "a imagem sugeria X" quando a evidência contradisser
    assert por_nome["infra_broker"]["papel_da_imagem"] == "fila"


def test_o_componente_nasce_marcado_se_e_exportador(monkeypatch):
    """D4: a marca vem da IMAGEM, que `novo_componente` não guarda. Pelo nome do serviço, um
    `monitoring_agent` rodando um exporter escaparia da trava."""
    bruto = dict(BRUTO)
    bruto["services"] = [{"name": "monitoring_agent", "image": "org/cadvisor:v0.47"},
                         {"name": "dados_pg", "image": "postgres:16"}]
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: bruto)

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    por_nome = {c["nome"]: c for c in bloco["componentes"]}
    assert por_nome["monitoring_agent"]["exportador"] is True, "o nome não diz; a imagem diz"
    assert por_nome["dados_pg"]["exportador"] is False
