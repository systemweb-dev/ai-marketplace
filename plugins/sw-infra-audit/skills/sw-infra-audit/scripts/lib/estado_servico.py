"""Um estado por serviço: é ele, e não `services_up`, que responde "está online?"."""
import re

from lib.papel import COM_ESTADO

ESTADOS = ("online", "parcial", "fora", "proposital", "sem_dado")
NA_BASE = ("online", "parcial", "fora")


def _concluiu(servico):
    """Job que terminou. O nome não prova nada: `seed` casaria com `x_seed_api`."""
    if str(servico.get("mode") or "").endswith("-job"):
        return True
    return bool(servico.get("completed_job")) and servico.get("kind") not in COM_ESTADO


def replicas_de(replicas):
    """`(rodando, desejado)` de "2/2" ou "0/1 (1/1 completed)"; None quando não dá para ler."""
    casou = re.match(r"(\d+)/(\d+)", str(replicas))
    return (int(casou.group(1)), int(casou.group(2))) if casou else None


def estado_de(servico, aceitos):
    """Só réplica ilegível é "sem dado". As réplicas dizem o estado: `N/N` é sempre "online", e as
    falhas do histórico viram alerta (`com_alerta`) e o achado `OPS_TASK_FAILING`."""
    lidas = replicas_de(servico.get("replicas"))
    if not lidas:
        return "sem_dado"
    rodando, desejado = lidas
    if desejado == 0:
        return "proposital"
    if rodando == 0 and (servico.get("name") in aceitos or None in aceitos):
        return "proposital"
    if rodando == 0 and _concluiu(servico) and servico.get("tasks_failed", 0) == 0:
        return "proposital"
    if rodando == 0:
        return "fora"
    if rodando < desejado:
        return "parcial"
    return "online"


def com_alerta(servico, aceitos):
    """Online com falha no histórico. `None` em `tasks_failed` é falta de dado, não alerta."""
    return estado_de(servico, aceitos) == "online" and bool(servico.get("tasks_failed"))


def contar(servicos, aceitos):
    conta = {e: 0 for e in ESTADOS}
    conta["falhas_desconhecidas"] = 0
    conta["com_alerta"] = 0
    for servico in servicos if isinstance(servicos, list) else []:
        estado = estado_de(servico, aceitos)
        conta[estado] += 1
        conta["com_alerta"] += com_alerta(servico, aceitos)
        if estado in NA_BASE and "tasks_failed" in servico and servico["tasks_failed"] is None:
            conta["falhas_desconhecidas"] += 1
    conta["base"] = sum(conta[e] for e in NA_BASE)
    return conta
