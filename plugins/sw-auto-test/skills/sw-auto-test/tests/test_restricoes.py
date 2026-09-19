# tests/test_restricoes.py
"""Restrições verificáveis do spec — o teste é a regra, não a documentação."""
import ast
import json
import os
from pathlib import Path

import diagnose
from lib import pastas
from projeto import projeto_pytest
from runners import chamadas, instalar
from test_diagnose_executar import pytest_falso

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PODEM_EXECUTAR = {"lib/execucao.py", "lib/gitinfo.py"}


def retrato(raiz: Path) -> dict:
    """Conteúdo, data de modificação e pastas — a árvore inteira, .git incluído."""
    saida = {}
    for caminho in sorted(raiz.rglob("*")):
        relativo = str(caminho.relative_to(raiz))
        if caminho.is_dir():
            saida[relativo + "/"] = "dir"
        else:
            marca = caminho.stat().st_mtime_ns
            saida[relativo] = (caminho.read_bytes(), marca)
    return saida


def test_escrita_confinada(repo, tmp_path, monkeypatch):
    """Restrição 1: só a pasta de fatos muda."""
    projeto_pytest(repo)
    # runner que GRAVA onde as flags mandam: com um runner mudo, este teste passaria mesmo se a
    # skill apontasse a saída para dentro do projeto
    pytest_falso(tmp_path, monkeypatch)
    monkeypatch.chdir(repo.path)
    antes = retrato(repo.path)

    diagnose.main(["--repo", str(repo.path), "--executar", "--cobertura"])

    depois = retrato(repo.path)
    mexidos = {caminho for caminho in set(antes) | set(depois)
               if antes.get(caminho) != depois.get(caminho)}
    permitido = str(pastas.base(repo.path).relative_to(repo.path))
    fora = {c for c in mexidos if not c.startswith(permitido)}
    assert fora == set(), f"escreveu fora da pasta de fatos: {sorted(fora)}"


def test_nada_executa_sem_aprovacao(repo, tmp_path, monkeypatch):
    """Restrição 2: sem --executar, nenhum runner é chamado; com banco à vista, idem."""
    projeto_pytest(repo)
    registro = instalar(tmp_path, monkeypatch, "pytest", {"__padrao__": ("", None, None, 0)})

    diagnose.main(["--repo", str(repo.path)])
    assert chamadas(registro) == []

    monkeypatch.setenv("DATABASE_URL", "postgres://usuario@host/banco")
    diagnose.main(["--repo", str(repo.path), "--executar"])
    assert chamadas(registro) == []


def test_so_execucao_e_gitinfo_executam_processo():
    """Quem importa subprocess é auditável: dois módulos, e ninguém mais."""
    executores = {"subprocess", "multiprocessing", "pty"}
    culpados = []
    for arquivo in SCRIPTS.rglob("*.py"):
        relativo = str(arquivo.relative_to(SCRIPTS))
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                nomes = [no.module or ""]
            elif isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "__import__":
                nomes = [a.value for a in no.args if isinstance(a, ast.Constant)]
            if any(str(nome).split(".")[0] in executores for nome in nomes) \
                    and relativo not in PODEM_EXECUTAR:
                culpados.append(relativo)
    assert culpados == [], f"módulo fora da lista executando processo: {sorted(set(culpados))}"


def test_nenhum_modulo_usa_atalho_de_shell():
    """`shell=True`, os.system e amigos passariam por cima da lista de comandos."""
    proibidos = {"system", "popen", "execv", "execvp", "spawnl", "spawnv", "fork"}
    culpados = []
    for arquivo in SCRIPTS.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call):
                if any(isinstance(k, ast.keyword) and k.arg == "shell" and
                       getattr(k.value, "value", False) is True for k in no.keywords):
                    culpados.append(f"{arquivo.name}: shell=True")
                alvo = no.func.attr if isinstance(no.func, ast.Attribute) else ""
                if alvo in proibidos:
                    culpados.append(f"{arquivo.name}: {alvo}")
    assert culpados == []


def test_sem_rede_em_nenhum_script():
    proibidos = {"socket", "urllib", "http", "requests", "httpx", "ftplib", "telnetlib", "smtplib"}
    culpados = []
    for arquivo in SCRIPTS.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                culpados += [a.name for a in no.names if a.name.split(".")[0] in proibidos]
            elif isinstance(no, ast.ImportFrom) and (no.module or "").split(".")[0] in proibidos:
                culpados.append(no.module)
    assert culpados == [], f"import de rede em scripts/: {culpados}"
