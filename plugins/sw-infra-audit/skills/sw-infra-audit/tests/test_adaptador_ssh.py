from apoio_host import SAIDAS_PADRAO, runner_falso
from lib.adaptadores import ssh

COMP = {"nome": "srv", "papel": "maquina", "ssh_destino": "root@srv", "porta": None}


def _ctx():
    return {"timeout": 20, "cache": {}}


def test_responde_as_quatro_perguntas_com_fonte_ssh(monkeypatch):
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso(SAIDAS_PADRAO))
    ctx = _ctx()
    valores = {p: ssh.perguntar(p, COMP, ctx)["valor"]
               for p in ("maquina.disco", "maquina.memoria", "maquina.carga", "maquina.desde_o_boot")}
    assert valores == {"maquina.disco": 94, "maquina.memoria": 50.0, "maquina.carga": 40.0,
                       "maquina.desde_o_boot": 2.0}
    assert ssh.perguntar("maquina.disco", COMP, ctx)["fonte"] == "ssh"


def test_cada_comando_roda_uma_vez_por_componente(monkeypatch):
    chamadas = []
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso(SAIDAS_PADRAO, chamadas=chamadas))
    ctx = _ctx()
    for _ in range(3):
        ssh.perguntar("maquina.disco", COMP, ctx)
    assert chamadas == ["disco"]


def test_vpn_desligada_vira_sem_dados_com_o_motivo(monkeypatch):
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso({}, conexao=False))
    resposta = ssh.perguntar("maquina.disco", COMP, _ctx())
    assert resposta["sem_dados"] and "VPN" in resposta["motivo"]


def test_componente_sem_destino_ou_pergunta_alheia_nao_se_aplica():
    assert ssh.perguntar("maquina.disco", {"nome": "x"}, _ctx())["nao_se_aplica"]
    assert ssh.perguntar("fila.filas", COMP, _ctx())["nao_se_aplica"]


def test_saida_estranha_vira_sem_dados(monkeypatch):
    monkeypatch.setattr(ssh.runner, "run_ssh", runner_falso({"disco": "lixo"}))
    assert "formato inesperado" in ssh.perguntar("maquina.disco", COMP, _ctx())["motivo"]
