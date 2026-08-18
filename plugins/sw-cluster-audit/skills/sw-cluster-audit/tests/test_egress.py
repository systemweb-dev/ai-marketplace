"""FF7 — zero rede de saída: scripts e template não fazem/ referenciam rede."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANNED = re.compile(r"\b(import\s+(requests|urllib|http\.client|socket)|from\s+(requests|urllib|http\.client|socket)\b|urlopen)\b")


def test_scripts_nao_importam_rede():
    for p in (ROOT / "scripts").rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert not BANNED.search(src), f"possível egress em {p}"


def test_template_sem_asset_remoto():
    html = (ROOT / "assets" / "report-template" / "template.html").read_text(encoding="utf-8")
    assert "http://" not in html and "https://" not in html
