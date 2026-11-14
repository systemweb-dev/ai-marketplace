from apoio_host import Falha, runner_falso
from lib.adaptadores import ssh
from lib.perguntas import COMUNS, ORDEM, PERGUNTAS
from test_leitura_servico import INSPECT, LS, SHOW

COMP = {"nome": "mariadb", "papel": "banco", "ssh_destino": "root@banco-01", "porta": None,
        "origem": "unidade:mariadb.service"}


def _ctx():
    return {"timeout": 20, "cache": {}, "at": "2026-11-13T10:00:00Z"}


def _respostas(componente, monkeypatch, saidas, chamadas=None):
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso(saidas, chamadas=chamadas))
    contexto = _ctx()
    return {p: ssh.perguntar(p, componente, contexto) for p in ssh.SERVICO}


def test_comuns_ficam_registradas_fora_de_todo_papel():
    assert COMUNS == ["servico.ativo", "servico.desde", "servico.reinicios", "servico.memoria"]
    novas = [*COMUNS, "banco.backup_idade"]
    assert all(PERGUNTAS[p]["opcional"] and PERGUNTAS[p]["limiar"] is None for p in novas)
    assert not any(p in ids for ids in ORDEM.values() for p in novas)


def test_unit_responde_as_quatro_comuns_com_uma_leitura(monkeypatch):
    chamadas = []
    respostas = _respostas(COMP, monkeypatch, {"servico_unidade:mariadb.service": SHOW,
                                               "boot": "259200.00 1.00\n"}, chamadas)
    assert {p: r["valor"] for p, r in respostas.items()} == {
        "servico.ativo": "ativo", "servico.desde": 2.0, "servico.reinicios": 2,
        "servico.memoria": 524288000}
    assert {r["fonte"] for r in respostas.values()} == {"ssh"}
    assert chamadas.count("servico_unidade:mariadb.service") == 1


def test_reinicio_de_processo_e_nao_medido_por_desenho(monkeypatch):
    componente = {**COMP, "nome": "qdrant", "origem": "processo:qdrant"}
    respostas = _respostas(componente, monkeypatch, {"processos": "qdrant 524288 86400\n"})
    assert respostas["servico.reinicios"]["sem_dados"] and respostas["servico.reinicios"]["nao_publica"]
    assert respostas["servico.memoria"]["valor"] == 524288 * 1024


def test_container_usa_inspect_e_stats_com_o_instante_da_rodada(monkeypatch):
    componente = {**COMP, "nome": "cache", "origem": "container:cache-exemplo"}
    respostas = _respostas(componente, monkeypatch, {
        "servico_container:cache-exemplo": INSPECT,
        "memoria_container:cache-exemplo": "512MiB / 2GiB\n"})
    assert respostas["servico.desde"]["valor"] == 3.0
    assert respostas["servico.reinicios"]["valor"] == 3
    assert respostas["servico.memoria"]["valor"] == 536870912


def test_leitura_que_falha_e_lacuna_com_motivo(monkeypatch):
    respostas = _respostas(COMP, monkeypatch, {})
    ativo = respostas["servico.ativo"]
    assert ativo["sem_dados"] and "falhou" in ativo["motivo"] and "nao_publica" not in ativo


def test_componente_sem_origem_nao_recebe_as_comuns():
    resposta = ssh.perguntar("servico.ativo", {**COMP, "origem": None}, _ctx())
    assert resposta["sem_dados"] and resposta["nao_se_aplica"]


def test_backup_pela_pasta_declarada(monkeypatch):
    componente = {**COMP, "backup_pasta": "/var/backups/mysql"}
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso({"backup:/var/backups/mysql": LS}))
    assert ssh.perguntar("banco.backup_idade", componente, _ctx()) == {
        "pergunta": "banco.backup_idade", "fonte": "ssh", "valor": 5}


def test_backup_vazio_ou_inexistente_e_sem_dados_nunca_numero(monkeypatch):
    componente = {**COMP, "backup_pasta": "/var/backups/mysql"}
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso({"backup:/var/backups/mysql": "total 0\n"}))
    assert "vazia" in ssh.perguntar("banco.backup_idade", componente, _ctx())["motivo"]
    ausente = Falha("ls: cannot access '/var/backups/mysql': No such file or directory", 2)
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso({"backup:/var/backups/mysql": ausente}))
    resposta = ssh.perguntar("banco.backup_idade", componente, _ctx())
    assert resposta["sem_dados"] and "inexistente ou ilegível" in resposta["motivo"]


def test_quem_responde_inclui_as_comuns_e_o_backup():
    assert {*ssh.SERVICO, "banco.backup_idade", "maquina.disco"} <= ssh.RESPONDE
