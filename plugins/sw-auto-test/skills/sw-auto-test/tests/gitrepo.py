"""Repositórios git de verdade para os testes — isolados da configuração de quem roda."""
import os
import subprocess
from pathlib import Path

ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Teste", "GIT_AUTHOR_EMAIL": "teste@example.com",
    "GIT_COMMITTER_NAME": "Teste", "GIT_COMMITTER_EMAIL": "teste@example.com",
    "GIT_TERMINAL_PROMPT": "0",
}


class Repo:
    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def novo(cls, path):
        path = Path(path)
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "master", str(path)], env=ENV, check=True)
        r = cls(path)
        r.escrever({"README.md": "inicial\n"})
        r.commit("chore: inicial")
        return r

    def git(self, *args, check=True) -> str:
        r = subprocess.run(["git", *args], cwd=self.path, env=ENV, capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} falhou: {r.stderr}")
        return r.stdout

    def escrever(self, arquivos: dict):
        """Escreve arquivos (str) relativos à raiz, criando as pastas."""
        for nome, conteudo in arquivos.items():
            destino = self.path / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(conteudo, encoding="utf-8")

    def commit(self, mensagem) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", mensagem)
        return self.git("rev-parse", "HEAD").strip()
