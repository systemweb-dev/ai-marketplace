"""FF7 (revisada) — a skill não faz egress, EXCETO GETs para endpoints confirmados,
e esse acesso vive num ÚNICO módulo (lib/http_get.py) que enforça a allowlist de hosts."""
import pathlib
import re

import pytest

from lib.http_get import check_allowed, NotConfirmed

ROOT = pathlib.Path(__file__).resolve().parents[1]
# O que abre socket de fato. `urllib.parse` (quote/urlparse) é manipulação de string, não I/O.
NET = re.compile(r"(urllib\.request|urllib\.error|urlopen|\bimport\s+socket\b|\bfrom\s+socket\b"
                 r"|\bimport\s+requests\b|\bfrom\s+requests\b|http\.client)")
ALLOWED_NET_MODULE = "lib/http_get.py"


def test_rede_so_no_modulo_dedicado():
    for p in (ROOT / "scripts").rglob("*.py"):
        rel = str(p.relative_to(ROOT / "scripts")).replace("\\", "/")
        if rel == ALLOWED_NET_MODULE:
            continue
        assert not NET.search(p.read_text(encoding="utf-8")), f"egress fora do módulo dedicado: {p}"


def test_modulo_dedicado_realmente_faz_a_rede():
    """Guard-rail do teste acima: se o módulo permitido parar de conter a rede, o teste vira vácuo."""
    src = (ROOT / "scripts" / "lib" / "http_get.py").read_text(encoding="utf-8")
    assert "urllib.request" in src and "check_allowed" in src


def test_template_sem_asset_remoto():
    html = (ROOT / "assets" / "report-template" / "template.html").read_text(encoding="utf-8")
    assert "http://" not in html and "https://" not in html


@pytest.mark.parametrize("url", [
    "http://evil.com/x",                    # host não confirmado
    "file:///etc/passwd",                   # esquema não permitido
    "ftp://1.2.3.4/x",
])
def test_bloqueia_url_nao_confirmada(url):
    with pytest.raises(NotConfirmed):
        check_allowed(url, ["10.0.0.1"])


def test_permite_apenas_host_confirmado():
    assert check_allowed("http://10.0.0.1:9090/api/v1/query?query=up", ["10.0.0.1"]) is True


def test_allowlist_derivada_do_cluster_bloqueia_host_de_fora():
    """No modo auto a allowlist é [host do context confirmado]; qualquer outro host é barrado —
    mesmo que um service do cluster anuncie uma URL apontando pra fora."""
    cluster_host = "143.198.106.223"
    with pytest.raises(NotConfirmed):
        check_allowed("http://attacker.example.com:9090/api/v1/query", [cluster_host])
    assert check_allowed(f"http://{cluster_host}:9090/api/v1/query", [cluster_host]) is True
