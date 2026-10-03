"""Cada trava da cobertura é quebrada de propósito, e a suíte TEM de cair.

Teste verde não prova que a trava funciona — prova que o teste roda. Nesta mesma skill uma
mutação sobreviveu em `lib/triagem.py` porque a `cascata()` não tinha teste; o único jeito de
saber é quebrar e olhar.
"""
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
# O interpretador que está rodando ESTE teste — não um `.venv` fixo. O `.venv` é ambiente
# local de quem desenvolve e nunca vai para o repositório: fixá-lo aqui fazia a suíte da
# skill PUBLICADA falhar com FileNotFoundError em qualquer máquina que a clonasse.
PY = sys.executable

MUTACOES = [
    ("teto vira piso",
     "scripts/lib/cobertura.py",
     'if exigido and _GRAVIDADE[exigido] > _GRAVIDADE[alvo["saude"]]:',
     "if exigido:"),
    ("low passa a travar",
     "scripts/lib/cobertura.py",
     '_TRAVA = {"critical": "🟡", "high": "🟡", "medium": "🟡"}',
     '_TRAVA = {"critical": "🟡", "high": "🟡", "medium": "🟡", "low": "🟡"}'),
    ("aceite deixa de dispensar",
     "scripts/lib/cobertura.py",
     'if limiar.get("regra") in aceites_vigentes:',
     "if False:"),
    ("estado fora da escala passa a ser tocado",
     "scripts/lib/cobertura.py",
     "if atual not in _GRAVIDADE:                                  # guarda 4\n        return",
     "if False:\n        return"),
    ("lista vazia volta a contar como resposta",
     "scripts/lib/cobertura.py",
     'if pergunta.get("limiar") and isinstance(valor, list) and not valor:\n        return False',
     "if False:\n        return False"),
    ("denominador zero vira 0%",
     "scripts/lib/cobertura.py",
     "pct = round(100 * respondidas / perguntadas) if perguntadas else None",
     "pct = round(100 * respondidas / perguntadas) if perguntadas else 0"),
]


@pytest.mark.parametrize("nome,arquivo,de,para", MUTACOES, ids=[m[0] for m in MUTACOES])
def test_quebrar_a_trava_derruba_a_suite(nome, arquivo, de, para):
    alvo = RAIZ / arquivo
    original = alvo.read_text(encoding="utf-8")
    assert de in original, f"o marcador da mutação {nome!r} não existe mais em {arquivo}"
    try:
        alvo.write_text(original.replace(de, para, 1), encoding="utf-8")
        r = subprocess.run([PY, "-m", "pytest", "tests/test_cobertura.py", "-q"],
                           cwd=RAIZ, capture_output=True, text=True)
        assert r.returncode != 0, f"a mutação {nome!r} SOBREVIVEU — a trava não tem teste"
    finally:
        alvo.write_text(original, encoding="utf-8")
