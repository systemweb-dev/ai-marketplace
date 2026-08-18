from lib.report import na, new_report, is_valid, split_image


def test_na_marker():
    assert na("requer Prometheus") == {"status": "n/a", "reason": "requer Prometheus"}


def test_parcial_e_valido():
    r = new_report(generated_at="2026-08-04T00:00:00Z", context="prod")
    r["nodes"] = na("timeout")                 # seção inteira n/a
    assert is_valid(r) and r["schema_version"] == 1


def test_report_sem_generated_at_e_invalido():
    r = new_report(generated_at=None, context="prod")
    assert not is_valid(r)


def test_split_image():
    assert split_image("app:1.2") == {"image": "app", "tag": "1.2", "digest": None}
    assert split_image("web@sha256:abc") == {"image": "web", "tag": None, "digest": "sha256:abc"}
    assert split_image("registry.io:5000/app:2.0") == {
        "image": "registry.io:5000/app", "tag": "2.0", "digest": None}
    assert split_image("nginx") == {"image": "nginx", "tag": None, "digest": None}
    # host:port SEM tag — o ':' do host não vira tag
    assert split_image("registry.io:5000/app") == {
        "image": "registry.io:5000/app", "tag": None, "digest": None}
    # digest vazio normaliza pra None
    assert split_image("app@") == {"image": "app", "tag": None, "digest": None}
