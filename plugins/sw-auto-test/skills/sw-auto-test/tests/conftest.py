"""Deixa `import diagnose`, `import report` e `import lib.x` funcionarem nos testes."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gitrepo import Repo  # noqa: E402


@pytest.fixture(autouse=True)
def _git_isolado(monkeypatch):
    """Os scripts herdam o ambiente: sem isto, a config global de quem roda vazaria."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repo(tmp_path):
    """Repositório git novo, na branch master, com um commit inicial."""
    return Repo.novo(tmp_path / "projeto")
