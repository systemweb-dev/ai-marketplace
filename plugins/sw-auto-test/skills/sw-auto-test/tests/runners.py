"""Runner falso no PATH: devolve saída canônica sem instalar pytest/vitest/phpunit de verdade.

Cada runner falso grava em `registro` (um arquivo texto) a linha de comando que recebeu — é
assim que os testes provam O QUE foi executado, e que nada rodou sem aprovação.
"""
import os
import stat
from pathlib import Path

MOLDE = """#!/usr/bin/env python3
import sys, pathlib
registro = pathlib.Path({registro!r})
with registro.open("a", encoding="utf-8") as f:
    f.write(" ".join([pathlib.Path(sys.argv[0]).name, *sys.argv[1:]]) + "\\n")
saidas = {saidas!r}
for gatilho, (texto, arquivo, conteudo, codigo) in saidas.items():
    # casa por CONTEÚDO do argumento: o runner recebe --junit-xml=<caminho> num argumento só
    if gatilho != "__padrao__" and any(gatilho in argumento for argumento in sys.argv):
        if arquivo:
            destino = pathlib.Path([a.split("=")[-1].split(":")[-1] for a in sys.argv if arquivo in a][0])
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(conteudo, encoding="utf-8")
        sys.stdout.write(texto)
        sys.exit(codigo)
sys.stdout.write(saidas["__padrao__"][0] if "__padrao__" in saidas else "")
sys.exit(0)
"""


def instalar(tmp_path, monkeypatch, nome, saidas) -> Path:
    """Cria o executável `nome` numa pasta que entra no início do PATH.

    `saidas` mapeia um argumento-gatilho para (stdout, marcador_de_arquivo, conteúdo, exit code).
    Use o gatilho "__padrao__" para o caso sem correspondência.
    Devolve o caminho do arquivo de registro das chamadas.
    """
    pasta = Path(tmp_path) / "bin"
    pasta.mkdir(exist_ok=True)
    registro = Path(tmp_path) / f"chamadas-{nome}.txt"
    alvo = pasta / nome
    alvo.write_text(MOLDE.format(registro=str(registro), saidas=saidas), encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{pasta}{os.pathsep}{os.environ['PATH']}")
    return registro


def chamadas(registro) -> list:
    """Linhas de comando que o runner falso recebeu (vazio se nunca foi chamado)."""
    caminho = Path(registro)
    return caminho.read_text(encoding="utf-8").splitlines() if caminho.exists() else []
