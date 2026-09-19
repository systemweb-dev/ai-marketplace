"""Guarda o original antes de qualquer edição e garante a volta.

Duas formas de uso:
- `mutacao_temporaria` — a alteração é sempre desfeita (prova do vermelho);
- `guardar` + `descartar`/`restaurar` — a alteração fica se der certo, volta se quebrar
  (correção guiada). A reversão usa o backup, nunca `git checkout`, que apagaria trabalho
  não commitado do usuário.
"""
import hashlib
import json
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lib import pastas

REGISTRO = "guardados.json"


class BackupSumiu(Exception):
    """O registro diz que há backup, mas a cópia não está no disco."""


def _registro(raiz) -> Path:
    return pastas.backups(raiz) / REGISTRO


def _ler(raiz) -> dict:
    arquivo = _registro(raiz)
    if not arquivo.exists():
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(raiz, dados):
    arquivo = _registro(raiz)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def _copia(raiz, relativo) -> Path:
    nome = hashlib.sha256(str(relativo).encode("utf-8")).hexdigest()[:16] + ".bak"
    return pastas.backups(raiz) / nome


def guardar(raiz, relativo) -> Path:
    """Copia os bytes do arquivo. Guardar de novo NÃO sobrescreve o backup bom."""
    raiz, relativo = Path(raiz), str(relativo)
    dados = _ler(raiz)
    destino = _copia(raiz, relativo)
    if relativo in dados:
        if destino.exists():
            return destino
        # sem isto, o arquivo JÁ MUTADO seria gravado como "original" e a restauração devolveria lixo
        raise BackupSumiu(f"{relativo}: registro existe, mas a cópia sumiu de {destino}")
    origem = raiz / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origem, destino)
    dados[relativo] = {
        "sha256": hashlib.sha256(origem.read_bytes()).hexdigest(),
        "quando": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _gravar(raiz, dados)
    return destino


def restaurar(raiz, relativo):
    """Devolve "intacto", "sobrescrito" ou False (sem backup).

    O hash guardado serve aqui: ele diz se o arquivo mudou desde o backup, e é isso que o
    chamador informa ao usuário — restaurar por cima de edição feita depois seria perda calada.
    """
    raiz, relativo = Path(raiz), str(relativo)
    dados = _ler(raiz)
    copia = _copia(raiz, relativo)
    if relativo not in dados or not copia.exists():
        return False
    alvo = raiz / relativo
    atual = hashlib.sha256(alvo.read_bytes()).hexdigest() if alvo.exists() else None
    estado = "intacto" if atual == dados[relativo].get("sha256") else "sobrescrito"
    shutil.copyfile(copia, alvo)
    copia.unlink()
    dados.pop(relativo)
    _gravar(raiz, dados)
    return estado


def descartar(raiz, relativo) -> bool:
    """A edição ficou boa: joga fora o backup, sem tocar no arquivo."""
    raiz, relativo = Path(raiz), str(relativo)
    dados = _ler(raiz)
    copia = _copia(raiz, relativo)
    if relativo not in dados:
        return False
    copia.unlink(missing_ok=True)
    dados.pop(relativo)
    _gravar(raiz, dados)
    return True


def residuo(raiz) -> list:
    """O que continua guardado — sobra de execução que morreu no meio."""
    return sorted(_ler(raiz))


def restaurar_tudo(raiz) -> dict:
    """Restaura tudo que ficou pendente, separando o que precisou ser sobrescrito."""
    saida = {"intacto": [], "sobrescrito": []}
    for relativo in residuo(raiz):
        estado = restaurar(raiz, relativo)
        if estado:
            saida[estado].append(relativo)
    return saida


@contextmanager
def mutacao_temporaria(raiz, relativo):
    """Alteração que SEMPRE volta — inclusive se o bloco levantar exceção."""
    guardar(raiz, relativo)
    try:
        yield raiz / relativo
    finally:
        restaurar(raiz, relativo)
