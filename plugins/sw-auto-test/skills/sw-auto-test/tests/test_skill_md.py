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


def test_todo_sinal_emitido_tem_verbete_no_catalogo():
    """O agente recebe o id do sinal e vai procurar o significado em diagnostico.md. Sinal que
    o script emite e o catálogo não explica deixa o agente sem chão — foi o que aconteceu com
    `runner_ausente`, que existia no diagnose.py e em lugar nenhum da referência."""
    scripts = SKILL.parent / "scripts"
    emitidos = set()
    for arquivo in (scripts / "diagnose.py", scripts / "lib" / "sinais.py"):
        if arquivo.exists():
            emitidos |= set(re.findall(r'"regra":\s*"([a-z_]+)"', arquivo.read_text(encoding="utf-8")))
            emitidos |= set(re.findall(r"regra=[\"']([a-z_]+)[\"']", arquivo.read_text(encoding="utf-8")))

    catalogo = (REFERENCES / "diagnostico.md").read_text(encoding="utf-8")
    documentados = set(re.findall(r"^\|\s*`([a-z_]+)`", catalogo, re.M))

    assert emitidos, "nenhum sinal encontrado nos scripts — o teste perdeu o alvo"
    assert emitidos <= documentados, f"sinal sem verbete em diagnostico.md: {sorted(emitidos - documentados)}"


def test_scripts_citados_no_skill_md_existem():
    """O irmão do teste de references/: um `scripts/x.py` citado e inexistente só aparece no
    meio da execução, quando o agente tenta rodar."""
    texto = SKILL.read_text(encoding="utf-8")
    citados = set(re.findall(r"`(?:python3 )?scripts/([\w/-]+\.py)", texto))

    faltando = [nome for nome in citados if not (SKILL.parent / "scripts" / nome).exists()]
    assert faltando == []
