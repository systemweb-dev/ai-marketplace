import json
import pathlib
from unittest import mock

import pytest

import collect
from lib.report import is_valid

FX = pathlib.Path(__file__).parent / "fixtures"


def test_aborta_sem_confirmacao_de_context(tmp_path):
    # FF5: sem confirmação do context, NENHUM comando roda e a coleta aborta
    with mock.patch("collect.confirm_context", return_value=False), \
         mock.patch("collect.run") as m:
        rc = collect.main(["--context", "prod", "--out", str(tmp_path),
                           "--at", "2026-08-18T00:00:00Z"])
        assert rc == 2 and m.call_count == 0


def test_gitignore_do_diretorio_antes_de_escrever(tmp_path):
    # FF6: a linha do DIRETÓRIO (não por extensão) entra no .gitignore
    (tmp_path / ".git").mkdir()
    collect.ensure_gitignore(tmp_path, "docs/infra/")
    assert "docs/infra/" in (tmp_path / ".gitignore").read_text().splitlines()


def test_gitignore_idempotente(tmp_path):
    collect.ensure_gitignore(tmp_path, "docs/infra/")
    collect.ensure_gitignore(tmp_path, "docs/infra/")
    linhas = (tmp_path / ".gitignore").read_text().splitlines()
    assert linhas.count("docs/infra/") == 1


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


def test_history_diff(tmp_path):
    base = tmp_path / "prod"
    (base / "2026-08-17_1000").mkdir(parents=True)
    (base / "2026-08-18_1000").mkdir(parents=True)
    prev = {"findings": [{"rule_id": "A", "object": "x"}, {"rule_id": "B", "object": "y"}]}
    (base / "2026-08-17_1000" / "report.json").write_text(json.dumps(prev))
    cur = {"findings": [{"rule_id": "B", "object": "y"}, {"rule_id": "C", "object": "z"}]}
    p = collect.find_previous_report(str(base / "2026-08-18_1000"))
    assert p["stamp"] == "2026-08-17_1000"
    d = collect.diff_findings(p, cur)
    assert d["vs"] == "2026-08-17_1000" and d["resolved"] == 1 and d["new"] == 1
    assert d["resolved_items"] == ["A · x"]          # histórico visível: o que saiu
    assert d["new_keys"] == [["C", "z"]]             # e o que entrou


@pytest.mark.parametrize("image,kind", [
    ("traefik:v3", "ingress/proxy"), ("library/rabbitmq:3", "fila"),
    ("postgres:16", "banco"), ("bitnami/redis:7", "cache/fila"), ("myorg/web-api:1.0", "app"),
])
def test_detect_kind(image, kind):
    assert collect.detect_kind(image) == kind


@pytest.mark.parametrize("ctx,confirmed,ok", [
    ("prod", None, False), ("prod", "", False), ("prod", "dev", False), ("prod", "prod", True),
])
def test_confirm_context(ctx, confirmed, ok):
    assert collect.confirm_context(ctx, confirmed) is ok


def test_confirmado_escreve_e_gitignore_vem_antes(tmp_path):
    (tmp_path / ".git").mkdir()
    out = tmp_path / "docs" / "infra" / "prod"
    gi_antes = {}

    def fake_assemble(run_fn, timeout, context, generated_at, connected_node):
        gi_antes["existe"] = (tmp_path / ".gitignore").exists()   # já criado antes da escrita?
        from lib.report import new_report
        return new_report(generated_at=generated_at, context=context)

    with mock.patch("collect.assemble_report", side_effect=fake_assemble), mock.patch("collect.run"):
        rc = collect.main(["--context", "prod", "--confirmed-context", "prod",
                           "--out", str(out), "--at", "2026-08-18T00:00:00Z"])
    assert rc == 0 and (out / "report.json").exists()
    assert gi_antes["existe"] is True                            # FF6: .gitignore ANTES de escrever
    assert "docs/infra/" in (tmp_path / ".gitignore").read_text().splitlines()


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
