"""Único ponto que executa processo externo (fora do git, que mora em gitinfo).

Concentrar aqui é o que torna verificável a regra "nada executa sem aprovação": o teste
estático olha quem importa `subprocess`.
"""
import os
import subprocess
from pathlib import Path

MARCAS_DE_BANCO = ("DATABASE_URL", "DB_HOST", "DB_DATABASE", "DB_CONNECTION", "MYSQL_", "POSTGRES_",
                   "PGHOST", "MONGO_URL", "MONGODB_URI", "REDIS_URL")
ARQUIVOS_DE_AMBIENTE = (".env", ".env.test", ".env.testing", ".env.local",
                        "phpunit.xml", "phpunit.xml.dist", "phpunit.dist.xml")


class Estourou(Exception):
    """O comando passou do tempo."""


def ambiente_limpo(extra=None) -> dict:
    """Sem paginador e com mensagens estáveis; o resto do ambiente do projeto é preservado.

    `CI=1` muda o comportamento de alguns runners (retry, `forbidOnly`), então o que for usado
    aqui é registrado nos fatos — quem ler o relatório precisa saber em que ambiente rodou.
    """
    return {**os.environ, "PAGER": "cat", "CI": "1", "NO_COLOR": "1",
            "PYTHONDONTWRITEBYTECODE": "1", **(extra or {})}


def rodar(comando, cwd, timeout: int, extra=None):
    """Devolve (código, stdout+stderr). Levanta `Estourou` no timeout."""
    try:
        r = subprocess.run(comando, cwd=str(cwd), env=ambiente_limpo(extra), capture_output=True,
                           text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as erro:
        raise Estourou(" ".join(str(p) for p in comando)) from erro
    except FileNotFoundError as erro:
        return 127, str(erro)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def banco_a_vista(escopo) -> list:
    """Onde há sinal de banco configurado — variável de ambiente ou arquivo do projeto.

    Roda ANTES da descoberta: coletar testes já importa `conftest`/bootstrap, que pode
    conectar ou truncar banco.
    """
    escopo = Path(escopo)
    achados = [nome for nome in os.environ if nome.startswith(MARCAS_DE_BANCO)]
    for nome in ARQUIVOS_DE_AMBIENTE:
        arquivo = escopo / nome
        if not arquivo.exists():
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        if any(marca in texto for marca in MARCAS_DE_BANCO):
            achados.append(nome)
    return sorted(set(achados))
