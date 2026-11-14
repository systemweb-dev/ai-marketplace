# scripts/lib/leitura_servico.py
"""Leitura pura do estado de um serviço de host e da idade do backup: texto entra, valor sai.

`PorDesenho` marca o dado que a fonte não tem por construção (reinícios de quem é só processo,
memória de unit sem contabilidade, tempo no ar de serviço parado): o adaptador o entrega como
`sem dados` com `nao_publica`, que a cobertura não conta como lacuna. None é saída fora do formato,
e essa conta. Número nunca passa por `float()` aqui: `extracao._numero` já filtra NaN e infinito.
"""
import json
import re
from datetime import date, datetime, timezone

from lib.extracao import _numero


class PorDesenho:
    """Não medido por construção — com o motivo que o relatório mostra."""

    __slots__ = ("motivo",)

    def __init__(self, motivo):
        self.motivo = motivo

    def __eq__(self, outro):
        return isinstance(outro, PorDesenho) and outro.motivo == self.motivo

    def __repr__(self):
        return f"PorDesenho({self.motivo!r})"


NAO_ATIVO = PorDesenho("o serviço não está no ar")
SEM_REINICIOS = PorDesenho("processo sem gerenciador: os reinícios não são contados")
SEM_MEMORIA_DA_UNIT = PorDesenho("o systemd não contabiliza a memória desta unit")
# o systemd antigo imprime UINT64_MAX no lugar de "[not set]"
NAO_DEFINIDO = str(2 ** 64 - 1)
UNIDADES_DE_MEMORIA = {"B": 1, "KIB": 1024, "MIB": 1024 ** 2, "GIB": 1024 ** 3, "TIB": 1024 ** 4,
                       "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4}
MEMORIA = re.compile(r"([0-9.]+)\s*([A-Za-z]+)")
DATA_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
DATA_COMPACTA = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")


def _dias(segundos):
    return round(max(0, segundos) / 86400, 1)


def de_unidade(show, uptime):
    """`systemctl show` + `/proc/uptime` → {pergunta: valor}. None quando não é saída do systemd.

    O tempo no ar sai de `ActiveEnterTimestampMonotonic` contra o uptime: os dois relógios são do
    servidor, e `--timestamp=unix` não existe no systemd antigo."""
    campos = {}
    for linha in (show or "").splitlines():
        chave, sep, valor = linha.partition("=")
        if sep:
            campos[chave.strip()] = valor.strip()
    estado = campos.get("ActiveState")
    if not estado:
        return None
    ativo = estado == "active"
    partes = (uptime or "").split()
    boot = _numero(partes[0]) if partes else None
    mono = campos.get("ActiveEnterTimestampMonotonic", "")
    if not ativo:
        desde = NAO_ATIVO
    elif mono.isdigit() and int(mono) > 0 and boot is not None:
        desde = _dias(boot - int(mono) / 1_000_000)
    else:
        desde = None
    reinicios = campos.get("NRestarts", "")
    memoria = campos.get("MemoryCurrent", "")
    if memoria in ("", "[not set]", NAO_DEFINIDO):
        memoria_valor = SEM_MEMORIA_DA_UNIT
    else:
        memoria_valor = int(memoria) if memoria.isdigit() else None
    return {"servico.ativo": "ativo" if ativo else estado, "servico.desde": desde,
            "servico.reinicios": int(reinicios) if reinicios.isdigit() else None,
            "servico.memoria": memoria_valor}


def _instante(texto):
    try:
        valor = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)


def memoria_do_stats(saida):
    """`123.4MiB / 1.944GiB` (do `docker stats`) → bytes em uso. None fora do formato."""
    usado = (saida or "").split("/")[0].strip()
    achado = MEMORIA.fullmatch(usado)
    if not achado:
        return None
    numero = _numero(achado.group(1))
    unidade = UNIDADES_DE_MEMORIA.get(achado.group(2).upper())
    if numero is None or unidade is None:
        return None
    return int(numero * unidade)


def de_container(inspect, stats, agora):
    """`docker inspect` (`<reinícios> <State em JSON>`) + `docker stats` → {pergunta: valor}."""
    contagem, _, bruto = (inspect or "").strip().partition(" ")
    try:
        estado = json.loads(bruto)
    except ValueError:
        return None
    if not isinstance(estado, dict) or not isinstance(estado.get("Status"), str):
        return None
    ativo = estado["Status"] == "running"
    inicio = _instante(estado.get("StartedAt"))
    if not ativo:
        desde = NAO_ATIVO
    elif inicio is None or agora is None:
        desde = None
    else:
        desde = _dias(agora - inicio.timestamp())
    return {"servico.ativo": "ativo" if ativo else estado["Status"],
            "servico.reinicios": int(contagem) if contagem.isdigit() else None,
            "servico.desde": desde,
            "servico.memoria": memoria_do_stats(stats) if ativo else NAO_ATIVO}


def de_processo(ps, processo):
    """`ps -e -o comm=,rss=,etimes=` → {pergunta: valor} do processo PRINCIPAL, o mais antigo.

    A soma dos workers não é a memória do serviço: eles compartilham páginas com o principal, e somar
    RSS conta a mesma memória várias vezes."""
    if not (ps or "").strip():
        return None
    candidatos = []
    for linha in ps.splitlines():
        partes = linha.split()
        if len(partes) < 3 or not partes[-1].isdigit() or not partes[-2].isdigit():
            continue
        if " ".join(partes[:-2]) == processo:
            candidatos.append((int(partes[-1]), int(partes[-2])))
    if not candidatos:
        return {"servico.ativo": "parado", "servico.desde": NAO_ATIVO,
                "servico.reinicios": SEM_REINICIOS, "servico.memoria": NAO_ATIVO}
    etimes, rss = max(candidatos)
    return {"servico.ativo": "ativo", "servico.desde": _dias(etimes),
            "servico.reinicios": SEM_REINICIOS, "servico.memoria": rss * 1024}


def _data_no_nome(nome):
    for padrao in (DATA_ISO, DATA_COMPACTA):
        for ano, mes, dia in padrao.findall(nome):
            try:
                return date(int(ano), int(mes), int(dia))
            except ValueError:
                continue
    return None


def idade_do_backup(ls, hoje):
    """`ls -l --time-style=full-iso <pasta>` → dias desde o backup mais novo, ou None.

    A data vem do NOME (`AAAA-MM-DD` ou `AAAAMMDD`) do arquivo de data mais nova; só quando nenhum
    nome traz data o mtime decide. Pasta sem arquivo nenhum devolve None: não é backup atrasado, é
    leitura que não achou o que medir."""
    nomes_com_data, mtimes = [], []
    for linha in (ls or "").splitlines():
        partes = linha.split()
        if len(partes) < 9 or linha.startswith("total"):
            continue
        try:
            mtimes.append(date.fromisoformat(partes[5]))
        except ValueError:
            continue
        data = _data_no_nome(" ".join(partes[8:]))
        if data is not None:
            nomes_com_data.append(data)
    referencia = max(nomes_com_data) if nomes_com_data else (max(mtimes) if mtimes else None)
    if referencia is None:
        return None
    return max(0, (hoje - referencia).days)
