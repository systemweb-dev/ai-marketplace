"""A marca `esperada` tem de atravessar do detector até o relatório.

`lib/rules.py` produz `expected: True` para o que descreve o NORMAL — o proxy que monta o
`docker.sock` porque é assim que ele funciona, o job de migração que terminou. A SKILL.md
promete que esse achado "não entra em faixa nenhuma, mas continua contado".

Numa rodada real de 212 achados, 19 deveriam estar marcados e ZERO estava: o coletor montava
o achado sem repassar a chave. A cascata do relatório imprimia "nenhum esperado" duas linhas
abaixo da dimensão dizendo "12 esperados" — e a triagem tratava um caso que nunca acontecia.
"""
from lib.coletores.docker import _para_achados_do_relatorio
from lib.rules import findings_for_workload


def _proxy_com_socket():
    """Traefik precisa do socket para service discovery: é o caso que `rules.py` marca."""
    return {"name": "traefik_traefik", "image": "traefik", "tag": "v3.4",
            "digest": "sha256:d", "privileged": False, "user": "1000",
            "mounts": [{"type": "bind", "source": "/var/run/docker.sock", "target": "/x"}],
            "ports": []}


def test_rules_marca_o_socket_esperado_como_expected():
    """Trava de contrato: se `rules.py` parar de marcar, este teste cai junto — em vez de
    o resto continuar verde validando um formato que não existe mais."""
    achados = findings_for_workload(_proxy_com_socket(), scope="cluster-wide")

    socket = [f for f in achados if "DOCKER_SOCK" in f["rule_id"]]
    assert socket and socket[0]["expected"] is True


def test_a_marca_atravessa_para_o_achado_do_relatorio():
    """É aqui que ela se perdia: `expected` existia no detector e sumia na conversão."""
    brutos = findings_for_workload(_proxy_com_socket(), scope="cluster-wide")

    achados = _para_achados_do_relatorio(brutos)

    socket = [a for a in achados if "DOCKER_SOCK" in a["regra"]]
    assert socket, "o achado do socket sumiu na conversão"
    assert socket[0].get("esperada") is True, "a marca não atravessou"


def test_achado_normal_nao_vira_esperado():
    """Só o que o detector marcou. Marcar a mais seria esconder achado de verdade."""
    wl = {"name": "app", "image": "app", "tag": "latest", "digest": None,
          "privileged": True, "user": "root", "mounts": [], "ports": []}

    achados = _para_achados_do_relatorio(findings_for_workload(wl, scope="s"))

    assert achados, "o caso de teste precisa produzir algum achado"
    assert not any(a.get("esperada") for a in achados)
