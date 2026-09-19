# tests/test_skill_md.py
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
REFERENCES = SKILL.parent / "references"


def test_skill_md_cabe_no_limite():
    assert len(SKILL.read_text(encoding="utf-8").splitlines()) < 220


def test_referencias_citadas_existem():
    texto = SKILL.read_text(encoding="utf-8")
    citadas = set(re.findall(r"references/([\w.-]+\.md)", texto))

    assert citadas, "o SKILL.md precisa apontar para references/"
    faltando = [nome for nome in citadas if not (REFERENCES / nome).exists()]
    assert faltando == []


def test_description_dispara_em_portugues():
    frente = SKILL.read_text(encoding="utf-8").split("---")[1].lower()

    for frase in ("cria os testes", "cobre com testes", "meus testes", "diagnostica"):
        assert frase in frente, f"gatilho ausente: {frase}"


def test_matriz_e_exemplos_sairam_do_skill_md():
    texto = SKILL.read_text(encoding="utf-8")

    assert "```php" not in texto and "```go" not in texto, "exemplo de linguagem mora em references/"
    assert "| PHP | PHPUnit |" not in texto, "a matriz mora em references/frameworks.md"
    assert "| PHP | PHPUnit |" in (REFERENCES / "frameworks.md").read_text(encoding="utf-8"), \
        "mover não pode virar sumir"


def test_toda_reference_e_citada_por_alguem():
    """Conteúdo movido para um arquivo que ninguém aponta é conteúdo perdido."""
    skill_texto = SKILL.read_text(encoding="utf-8")

    for arquivo in sorted(REFERENCES.glob("*.md")):
        outras = [p.read_text(encoding="utf-8") for p in REFERENCES.glob("*.md") if p != arquivo]
        assert arquivo.name in skill_texto or any(arquivo.name in t for t in outras), \
            f"{arquivo.name} não é citado por ninguém"


def test_reference_nao_aponta_para_si_mesma_nem_usa_prefixo_errado():
    for arquivo in sorted(REFERENCES.glob("*.md")):
        texto = arquivo.read_text(encoding="utf-8")
        assert f"references/{arquivo.name}" not in texto, \
            f"{arquivo.name}: link para si mesma (ou caminho com prefixo references/ dentro de references/)"
