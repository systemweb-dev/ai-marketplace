"""Testes herdados do coletor docker (eram do collect.py da sw-cluster-audit).

Os que checavam confirmação de context e .gitignore saíram daqui: viraram o gate
`--confirmar` (test_collect_orquestrador.py) e o modo configurar (Task 12).
"""
import json
import pathlib
from unittest import mock

import pytest

from lib.coletores import docker as collect
from lib.coletores.docker_report import is_valid

FX = pathlib.Path(__file__).parent / "fixtures"


def _fake_run(cmd, timeout):
    if cmd[:2] == ["docker", "info"]:
        return json.dumps({"ServerVersion": "25.0", "Swarm": {"LocalNodeState": "active"}})
    if cmd[:3] == ["docker", "service", "ls"]:
        return json.dumps({"Name": "web", "Replicas": "1/1"})
    if cmd[:3] == ["docker", "service", "inspect"]:
        return json.dumps([json.loads((FX / "inspect_service_secret.json").read_text())])
    return ""   # node/ps/network/secret/config ls vazios (sem daemon real)


def test_assemble_report_monta_sem_vazar_e_valido():
    r = collect.assemble_report(_fake_run, timeout=5, context="prod",
                                generated_at="2026-08-18T00:00:00Z", connected_node="node-1")
    assert is_valid(r)
    assert r["scope"]["connected_node"] == "node-1"
    assert r["cluster"]["swarm"] is True and r["cluster"]["engine_version"] == "25.0"
    assert [s["name"] for s in r["services"]] == ["web"]
    dumped = json.dumps(r)
    assert "abc123" not in dumped and "zzz" not in dumped   # Args/Env do service não vazam
    assert "hashedsecret-should-not-leak" not in dumped     # basicauth do traefik redigido
    svc = r["services"][0]
    assert svc["kind"] == "app"                             # 'web' não casa nenhum kind conhecido
    assert svc["routing_labels"]["traefik.http.routers.web.rule"] == "Host(`app.systemweb`)"
    assert r["health"]["verdict"] in {"green", "yellow", "red"}
    assert "seguranca" in r["dimensions"]                  # métricas computadas no assemble
    assert isinstance(r["top_offenders"], list)


@pytest.mark.parametrize("image,kind", [
    ("traefik:v3", "ingress/proxy"), ("library/rabbitmq:3", "fila"),
    ("postgres:16", "banco"), ("bitnami/redis:7", "cache/fila"), ("myorg/web-api:1.0", "app"),
])
def test_detect_kind(image, kind):
    assert collect.detect_kind(image) == kind


def test_degrada_com_run_none_sem_crashar():
    r = collect.assemble_report(lambda cmd, t: None, timeout=5, context="prod",
                                generated_at="2026-08-18T00:00:00Z", connected_node="n1")
    assert is_valid(r)
    assert r["services"]["status"] == "n/a" and r["nodes"]["status"] == "n/a"
    assert r["health"]["verdict"] == "unknown"   # sem dados não vira alarme


def test_no_worker_manager_status_null_nao_crasha():
    def frun(cmd, t):
        if cmd[:3] == ["docker", "node", "ls"]:
            return json.dumps({"ID": "n1", "Hostname": "w1", "Availability": "Active", "Status": "Ready"})
        if cmd[:3] == ["docker", "node", "inspect"]:
            return json.dumps([{"Description": {"Resources": {"NanoCPUs": 1, "MemoryBytes": 2}},
                                "ManagerStatus": None}])   # nó worker: null → não pode crashar
        return ""
    r = collect.assemble_report(frun, 5, "prod", "2026-08-18T00:00:00Z", "n1")
    assert r["nodes"][0]["leader"] is False and r["nodes"][0]["hostname"] == "w1"


def test_completed_job_exige_que_nada_esteja_rodando():
    """Worker que roda e reinicia saindo com 0 acumula task Complete — não pode virar
    'job', senão fica isento do check de serviço parado no dia em que cair de verdade."""
    from lib.coletores.docker import _completed_job
    rodando = {"CurrentState": "Running 3 days ago"}
    concluida = {"CurrentState": "Complete 2 hours ago"}
    assert _completed_job([concluida, concluida]) is True     # job de fato: nada ativo
    assert _completed_job([concluida, rodando]) is False      # ainda serve → não é job
    assert _completed_job([rodando]) is False
    assert _completed_job([]) is False                        # sem dado, não inventa
