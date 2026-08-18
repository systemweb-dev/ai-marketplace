from lib import metrics


def _report():
    return {
        "services": [
            {"name": "db", "kind": "banco", "replicas": "1/1", "digest": None},        # SPOF stateful + unpinned
            {"name": "web", "kind": "proxy", "replicas": "2/2", "digest": "sha256:a"},  # HA + pinned
        ],
        "findings": [
            {"rule_id": "SEC_USER_ROOT", "severity": "med", "object": "db"},
            {"rule_id": "SEC_PRIVILEGED", "severity": "high", "object": "db"},
            {"rule_id": "SEC_IMAGE_UNPINNED", "severity": "med", "object": "db"},
        ],
    }


def test_dimensions():
    m = metrics.compute(_report())
    d = m["dimensions"]
    assert d["disponibilidade"]["spof_stateful"] == ["db"]      # banco 1/1 = SPOF
    assert d["disponibilidade"]["ha_pct"] == 50                 # 1 de 2 com HA
    assert d["higiene"]["pinned_pct"] == 50                     # 1 de 2 com digest
    assert d["higiene"]["nonroot_pct"] == 50                    # db é root (1 finding), web não
    assert d["seguranca"]["high"] == 1 and d["seguranca"]["note"] == "red"


def test_top_offenders():
    m = metrics.compute(_report())
    assert m["top_offenders"][0] == {"object": "db", "findings": 3}


def test_group_findings_ordena_por_severidade():
    groups = metrics.group_findings(_report()["findings"])
    assert groups[0]["severity"] == "high"                     # high primeiro
    assert {g["rule_id"] for g in groups} == {"SEC_PRIVILEGED", "SEC_USER_ROOT", "SEC_IMAGE_UNPINNED"}
    priv = [g for g in groups if g["rule_id"] == "SEC_PRIVILEGED"][0]
    assert priv["count"] == 1 and priv["objects"] == ["db"]
