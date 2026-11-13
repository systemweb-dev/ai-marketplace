import json

from lib import catalogo_host, produtos
from lib.descoberta import descobrir

SERVICOS = ("mariadb.service loaded active running MariaDB 10.11.6 database server\n"
            "ssh.service loaded active running OpenBSD Secure Shell server\n"
            "qdrant.service loaded active running Qdrant\n")
PORTAS = ('LISTEN 0 80 0.0.0.0:3306 0.0.0.0:* users:(("mariadbd",pid=812,fd=22))\n'
          'LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=600,fd=3))\n'
          'LISTEN 0 1024 127.0.0.1:6333 0.0.0.0:* users:(("qdrant",pid=900,fd=9))\n'
          'LISTEN 0 1024 127.0.0.1:6334 0.0.0.0:* users:(("qdrant",pid=900,fd=10))\n'
          'LISTEN 0 4096 0.0.0.0:6379 0.0.0.0:* users:(("docker-proxy",pid=1300,fd=4))\n'
          'LISTEN 0 4096 [::]:9100 [::]:* users:(("meu-agente",pid=1400,fd=3))\n')
CONTAINERS = "cache-exemplo\tredis:7-alpine\t0.0.0.0:6379->6379/tcp, :::6379->6379/tcp\n"


def _rodar(**trocas):
    saidas = {"servicos": SERVICOS, "portas": PORTAS, "containers": CONTAINERS, **trocas}
    return descobrir(saidas, produtos.carregar(), catalogo_host.carregar()["ignorar"])


def _por_origem(resultado):
    return {c["origem"]: c for c in resultado["candidatos"]}


def test_casa_por_processo_e_usa_a_unidade_como_origem():
    mariadb = _por_origem(_rodar())["unidade:mariadb.service"]
    assert (mariadb["produto"], mariadb["papel"], mariadb["portas"], mariadb["todas_interfaces"]) == \
        ("mariadb", "banco", [3306], True)


def test_varias_portas_do_mesmo_processo_e_loopback_nao_e_todas():
    qdrant = _por_origem(_rodar())["unidade:qdrant.service"]
    assert qdrant["portas"] == [6333, 6334] and qdrant["todas_interfaces"] is False


def test_porta_do_docker_proxy_vira_o_container_pela_imagem():
    redis = _por_origem(_rodar())["container:cache-exemplo"]
    assert redis["produto"] == "redis" and redis["portas"] == [6379] and redis["todas_interfaces"]


def test_sshd_some_e_processo_desconhecido_aparece_nao_reconhecido():
    candidatos = _por_origem(_rodar())
    assert not any("sshd" in o or o == "unidade:ssh.service" for o in candidatos)
    agente = candidatos["processo:meu-agente"]
    assert agente["reconhecido"] is False and agente["produto"] is None and agente["portas"] == [9100]


def test_fonte_que_falhou_vira_nao_medida_e_as_outras_seguem():
    resultado = _rodar(portas=None)
    assert resultado["nao_medidas"] == ["portas"]
    assert "unidade:mariadb.service" in _por_origem(resultado)


def test_nada_de_pid_cmdline_ou_ambiente_no_resultado():
    texto = json.dumps(_rodar())
    assert "812" not in texto and "pid" not in texto and "fd=" not in texto
    for candidato in _rodar()["candidatos"]:
        assert set(candidato) == {"nome", "produto", "papel", "origem", "portas",
                                  "todas_interfaces", "reconhecido", "gravavel", "motivo"}


def test_nome_malicioso_nao_e_gravavel():
    portas = 'LISTEN 0 80 0.0.0.0:7000 0.0.0.0:* users:(("x\\"]\\n[[alvo]]",pid=1,fd=1))\n'
    candidato = _rodar(portas=portas, servicos="", containers="")["candidatos"][0]
    assert candidato["gravavel"] is False and "caractere" in candidato["motivo"]


def test_unit_com_arroba_vira_nome_valido():
    servicos = "postgresql@15-main.service loaded active running PostgreSQL Cluster 15-main\n"
    pg = _rodar(servicos=servicos, portas="", containers="")["candidatos"][0]
    assert pg["nome"] == "postgresql-15-main" and pg["origem"] == "unidade:postgresql@15-main.service"


def test_unit_do_exporter_nao_rouba_o_produto_do_banco():
    """A revisão final reproduziu: `prometheus-redis-exporter.service` vem antes de
    `redis-server.service` em ordem alfabética e ficava com o produto `redis` — o Redis gravado
    virava "serviço ausente" (high) com ele rodando."""
    servicos = ("prometheus-redis-exporter.service loaded active running Prometheus exporter\n"
                "redis-server.service loaded active running Advanced key-value store\n")
    portas = 'LISTEN 0 511 127.0.0.1:6379 0.0.0.0:* users:(("redis-server",pid=7,fd=6))\n'
    candidatos = _rodar(servicos=servicos, portas=portas, containers="")["candidatos"]
    assert [(c["origem"], c["produto"]) for c in candidatos] == \
        [("unidade:redis-server.service", "redis")]


def test_nomes_repetidos_ganham_sufixo_e_continuam_gravaveis():
    servicos = "qdrant.service loaded active running Qdrant\n"
    containers = "qdrant\tqdrant/qdrant:v1\t0.0.0.0:6334->6333/tcp\n"
    candidatos = _rodar(servicos=servicos, portas="", containers=containers)["candidatos"]
    nomes = sorted(c["nome"] for c in candidatos)
    assert nomes == ["qdrant-container", "qdrant-unidade"]
