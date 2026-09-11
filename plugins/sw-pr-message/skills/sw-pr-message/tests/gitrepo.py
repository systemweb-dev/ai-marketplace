"""Repositórios git de verdade para os testes — isolados da configuração de quem roda."""
import os
import subprocess
from pathlib import Path

ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,      # sem config global (assinatura, hooks, aliases)
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Teste", "GIT_AUTHOR_EMAIL": "teste@example.com",
    "GIT_COMMITTER_NAME": "Teste", "GIT_COMMITTER_EMAIL": "teste@example.com",
    "GIT_EDITOR": "true",                 # rebase com conflito não abre editor
    "GIT_TERMINAL_PROMPT": "0",
}


class Repo:
    def __init__(self, path):
        self.path = Path(path)
        self._n = 0

    @classmethod
    def novo(cls, path):
        path = Path(path)
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "master", str(path)], env=ENV, check=True)
        r = cls(path)
        r.commit("chore: inicial", {"README.md": "inicial\n"})
        return r

    def git(self, *args, check=True) -> str:
        r = subprocess.run(["git", *args], cwd=self.path, env=ENV, capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} falhou: {r.stderr}")
        return r.stdout

    def commit(self, mensagem, arquivos=None) -> str:
        """Escreve os arquivos (str ou bytes), faz add de tudo e commita. Devolve o hash."""
        if arquivos is None:
            self._n += 1
            arquivos = {f"arquivo_{self._n}.txt": f"conteúdo {self._n}\n"}
        for nome, conteudo in arquivos.items():
            destino = self.path / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(conteudo, bytes):
                destino.write_bytes(conteudo)
            else:
                destino.write_text(conteudo, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", mensagem)
        return self.sha()

    def branch(self, nome, de=None):
        """Cria a branch (a partir de `de`, ou do HEAD) e faz checkout."""
        self.git("checkout", "-q", "-b", nome, *([de] if de else []))

    def checkout(self, ref):
        self.git("checkout", "-q", ref)

    def merge(self, ref, mensagem=None):
        self.git("merge", "-q", "--no-ff", "-m", mensagem or f"Merge {ref}", ref)

    def ref_remota(self, nome, ref="HEAD"):
        """Cria origin/<nome> sem rede: é só uma ref local em refs/remotes."""
        self.git("update-ref", f"refs/remotes/origin/{nome}", self.sha(ref))

    def origin_head(self, nome):
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{nome}")

    def sha(self, ref="HEAD") -> str:
        return self.git("rev-parse", ref).strip()
