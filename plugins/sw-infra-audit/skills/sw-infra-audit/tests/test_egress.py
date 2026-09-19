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
    "ftp://198.51.100.9/x",
])
def test_bloqueia_url_nao_confirmada(url):
    with pytest.raises(NotConfirmed):
        check_allowed(url, [("10.0.0.1", 9090)])


def test_permite_apenas_host_confirmado():
    assert check_allowed("http://10.0.0.1:9090/api/v1/query?query=up",
                         [("10.0.0.1", 9090)]) is True


def test_allowlist_derivada_do_cluster_bloqueia_host_de_fora():
    """No modo auto a allowlist é [host do context confirmado]; qualquer outro host é barrado —
    mesmo que um service do cluster anuncie uma URL apontando pra fora."""
    cluster_host = "203.0.113.10"
    with pytest.raises(NotConfirmed):
        check_allowed("http://attacker.example.com:9090/api/v1/query",
                      [(cluster_host, 9090)])
    assert check_allowed(f"http://{cluster_host}:9090/api/v1/query",
                         [(cluster_host, 9090)]) is True


def test_as_funcoes_novas_de_rede_passam_pela_allowlist():
    """Regex de import não prova nada sobre quem chama check_allowed — isto prova."""
    import pytest

    from lib import http_get

    with pytest.raises(http_get.NotConfirmed):
        http_get.get_com_status("http://exemplo.invalido/x",
                                [("outro.invalido", 80)], timeout=1)
    with pytest.raises(http_get.NotConfirmed):
        http_get.validade_do_certificado("https://exemplo.invalido/", [], timeout=1)


def test_porta_nao_declarada_e_recusada():
    """Confirmar um host não pode autorizar todas as portas dele: os adaptadores tentam
    portas de administração, e liberar o host inteiro seria varredura de portas."""
    permitido = [("metricas.interno", 9090)]

    assert check_allowed("http://metricas.interno:9090/api/v1/query?query=up", permitido) is True
    with pytest.raises(NotConfirmed):
        check_allowed("http://metricas.interno:15672/api/overview", permitido)


def test_porta_implicita_do_esquema_conta():
    assert check_allowed("https://painel.interno/metrics", [("painel.interno", 443)]) is True
    assert check_allowed("http://painel.interno/metrics", [("painel.interno", 80)]) is True
    with pytest.raises(NotConfirmed):
        check_allowed("https://painel.interno/metrics", [("painel.interno", 80)])


def test_porta_fora_da_faixa_e_recusada_com_mensagem():
    """Erro de digitação no alvos.toml tem que soar como configuração, não como bug interno."""
    with pytest.raises(NotConfirmed) as erro:
        check_allowed("http://site.interno:8080000/x", [("site.interno", 80)])
    assert "porta inválida" in str(erro.value)
