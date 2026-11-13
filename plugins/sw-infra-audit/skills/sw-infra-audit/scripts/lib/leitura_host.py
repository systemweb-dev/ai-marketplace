"""Leitura pura das saídas do catálogo de host: texto entra, número sai, ou None.

None nunca vira "está tudo bem": quem chama transforma em `sem_dados` com motivo. NaN e infinito
também viram None — um NaN aborta a gravação do report.json inteiro.
"""
from lib.extracao import _numero   # o conversor que já filtra NaN e infinito

SISTEMAS_IGNORADOS = ("tmpfs", "devtmpfs", "udev", "overlay", "squashfs", "efivarfs", "shm")
PONTOS_IGNORADOS = ("/dev", "/run", "/sys", "/proc", "/snap", "/boot/efi")


def disco(saida):
    usos = []
    for linha in (saida or "").splitlines()[1:]:
        partes = linha.split()
        if len(partes) < 6 or not partes[4].endswith("%") or not partes[4][:-1].isdigit():
            continue
        sistema, ponto = partes[0], partes[5]
        if sistema.startswith(SISTEMAS_IGNORADOS) or any(
                ponto == p or ponto.startswith(p + "/") for p in PONTOS_IGNORADOS):
            continue
        usos.append(int(partes[4][:-1]))
    return max(usos) if usos else None


def memoria(saida):
    campos = {}
    for linha in (saida or "").splitlines():
        chave, _, resto = linha.partition(":")
        valor = resto.split()
        if valor and valor[0].isdigit():
            campos[chave.strip()] = int(valor[0])
    total, disponivel = campos.get("MemTotal"), campos.get("MemAvailable")
    if not total or disponivel is None:
        return None
    return round(100 * (total - disponivel) / total, 1)


def carga(loadavg, nproc):
    try:
        cinco, cpus = _numero(loadavg.split()[1]), int(nproc.strip())
    except (AttributeError, IndexError, ValueError):
        return None
    if cinco is None or cpus <= 0:
        return None
    return round(100 * cinco / cpus, 1)


def desde_o_boot(uptime):
    try:
        segundos = _numero(uptime.split()[0])
    except (AttributeError, IndexError):
        return None
    return None if segundos is None else round(segundos / 86400, 1)


def sistema(os_release):
    for linha in (os_release or "").splitlines():
        if linha.startswith("PRETTY_NAME="):
            return linha.split("=", 1)[1].strip().strip('"') or None
    return None
