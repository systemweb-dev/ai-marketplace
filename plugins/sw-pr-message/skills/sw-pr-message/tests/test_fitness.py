import ast
import hashlib
import re
import socket
from pathlib import Path

import collect
import render
from fluxo import escrever_mudancas
from lib.gitcmd import caminho_git

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PYS = sorted(SCRIPTS.rglob("*.py"))
REDE = {"socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "telnetlib"}
EXECUCAO_OS = ("system", "popen", "spawn", "exec", "fork", "posix_spawn")


def _arvores():
    return {p.relative_to(SCRIPTS): ast.parse(p.read_text(encoding="utf-8")) for p in PYS}


def _importados(arvore):
    """Módulos trazidos por import, from-import, __import__("x") e importlib.import_module("x")."""
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module.split(".")[0])
        elif isinstance(no, ast.Call) and no.args and isinstance(no.args[0], ast.Constant):
            alvo = no.func
            nome = alvo.id if isinstance(alvo, ast.Name) else getattr(alvo, "attr", "")
            if nome in ("__import__", "import_module"):
                nomes.add(str(no.args[0].value).split(".")[0])
    return nomes


def _feature(repo):
    repo.branch("feature/x")
    return repo.commit("feat: tela de login", {"login.py": "def entrar():\n    return True\n"})


def test_ff1_subprocess_so_dentro_do_gitcmd():
    fora = sorted(str(rel) for rel, arvore in _arvores().items()
                  if rel.name != "gitcmd.py" and "subprocess" in _importados(arvore))

    assert PYS, "nenhum script encontrado — caminho errado?"
    assert fora == []


def test_ff1_nenhuma_execucao_de_processo_pelo_os():
    achados = []
    for rel, arvore in _arvores().items():
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module == "os":
                achados += [f"{rel}: from os import {a.name}" for a in no.names if a.name.startswith(EXECUCAO_OS)]
            elif (isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name) and no.value.id == "os"
                  and no.attr.startswith(EXECUCAO_OS)):
                achados.append(f"{rel}: os.{no.attr}")

    assert achados == []


def test_ff1_nenhum_shell_true():
    com_shell = [p.relative_to(SCRIPTS) for p in PYS if "shell=True" in p.read_text(encoding="utf-8")]

    assert com_shell == []


def test_ff1_nenhum_formato_que_verifica_assinatura():
    # %G? no log e %(signature) no for-each-ref chamam o gpg configurado
    com_assinatura = [p.relative_to(SCRIPTS) for p in PYS
                      if re.search(r"%G|%\(signature", p.read_text(encoding="utf-8"))]

    assert com_assinatura == []


def test_ff2_nenhum_import_de_rede():
    com_rede = sorted(f"{rel}: {sorted(_importados(arvore) & REDE)}"
                      for rel, arvore in _arvores().items() if _importados(arvore) & REDE)

    assert com_rede == []


def test_ff2_collect_e_render_nao_tentam_abrir_conexao(repo, monkeypatch):
    tentativas = []

    def registrar(*args, **kwargs):
        # registra ANTES de falhar: um `except Exception` no script engoliria a exceção, não o registro
        tentativas.append(args)
        raise OSError("rede proibida neste teste")

    monkeypatch.setattr(socket, "socket", registrar)
    monkeypatch.setattr(socket, "create_connection", registrar)
    sha = _feature(repo)

    assert collect.main(["--repo", str(repo.path)]) == 0
    escrever_mudancas(caminho_git(repo.path, "sw-pr-message"), sha)
    assert render.main(["--repo", str(repo.path)]) == 0

    assert tentativas == []


def _retrato(raiz: Path) -> dict:
    """Conteúdo e data de modificação dos arquivos, e as pastas: pega reescrita, `utime` e pasta criada."""
    retrato = {}
    for p in raiz.rglob("*"):
        if p.is_symlink() or p.is_file():
            st = p.lstat()
            retrato[p] = (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "link", st.st_mtime_ns)
        elif p.is_dir():
            retrato[p] = "pasta"
    return retrato


def test_ff3_scripts_so_escrevem_no_git_path_no_exclude_e_no_pr_message(repo, monkeypatch):
    # tudo que o TESTE escreve acontece antes do retrato: entre os retratos, só os dois scripts
    sha = _feature(repo)
    pasta = caminho_git(repo.path, "sw-pr-message")
    pasta.mkdir(parents=True, exist_ok=True)
    escrever_mudancas(pasta, sha)
    monkeypatch.chdir(repo.path)          # escrita em caminho relativo cairia dentro do retrato
    raiz = repo.path.resolve()
    antes = _retrato(raiz)

    assert collect.main(["--repo", str(repo.path)]) == 0
    assert render.main(["--repo", str(repo.path)]) == 0

    depois = _retrato(raiz)
    permitidos = {caminho_git(repo.path, "info/exclude"), (repo.path / "PR-MESSAGE.md").resolve()}
    mudou = {p for p in set(antes) | set(depois) if antes.get(p) != depois.get(p)}
    fora = sorted(str(p) for p in mudou if p not in permitidos and p != pasta and pasta not in p.parents)
    assert fora == []
