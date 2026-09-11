"""Ajudantes de ponta a ponta: coleta real num repositório de teste + mudancas.json válido."""
import json

import collect
from lib.gitcmd import caminho_git


def preparar(repo, mensagem="feat: tela de login", arquivos=None):
    """Branch de feature com um commit, coletada. Devolve (pasta dos intermediários, sha)."""
    repo.branch("feature/x")
    sha = repo.commit(mensagem, arquivos or {"login.py": "def entrar():\n    return True\n"})
    assert collect.main(["--repo", str(repo.path)]) == 0
    return caminho_git(repo.path, "sw-pr-message"), sha


def escrever_mudancas(pasta, *shas, **extra):
    dados = {
        "idioma": "pt",
        "titulo": "Tela de login",
        "resumo": "Permite entrar no sistema.",
        "secoes": {"novas": [{"texto": "Tela de login", "commits": [s[:7] for s in shas]}]},
        "como_testar": ["Abrir a tela de login"],
    }
    dados.update(extra)
    (pasta / "mudancas.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
