"""Um `run_ssh` de mentira: devolve a saída gravada, sem rede.

A chave é a do catálogo de host para comando literal (`"disco"`), `"<molde>:<valor da vaga>"` para
molde da camada comum (`"servico_unidade:mariadb.service"`) e o texto da consulta para molde de produto
(`"SHOW GLOBAL STATUS"`, com a `{colecao}` já trocada). Chave ausente simula comando que falhou; uma
`Falha` simula erro com motivo e código. `conexao=False` simula a VPN desligada.
"""
from typing import NamedTuple

from lib import catalogo_host


class Falha(NamedTuple):
    motivo: str
    codigo: int = 1


def runner_falso(saidas, conexao=True, chamadas=None, registro=None):
    catalogo = catalogo_host.carregar()
    por_texto = {v: k for k, v in catalogo["comandos"].items()}
    por_molde = {v: k for k, v in catalogo["moldes"].items()}

    def _chave(comando, vagas):
        if vagas is None:
            return por_texto[comando]
        if "sql" in vagas:
            return vagas["sql"].replace("{colecao}", str(vagas.get("colecao", "{colecao}")))
        return f"{por_molde[comando]}:{next(iter(vagas.values()))}"

    def run_ssh(destino, porta, comando, timeout, errors=None, vagas=None, entrada=None):
        chave = _chave(comando, vagas)
        if chamadas is not None:
            chamadas.append(chave)
        if registro is not None:
            registro.append({"comando": comando, "vagas": vagas, "entrada": entrada})
        if not conexao:
            if errors is not None:
                errors.append({"cmd": f"ssh {destino}", "codigo": 255,
                               "reason": f"não abri a sessão para {destino} (a VPN está ligada?)"})
            return None
        saida = saidas.get(chave)
        if saida is None or isinstance(saida, Falha):
            if errors is not None:
                falha = saida if isinstance(saida, Falha) else Falha(f"{chave} falhou")
                errors.append({"cmd": f"ssh {destino}", "reason": falha.motivo,
                               "codigo": falha.codigo})
            return None
        return saida
    return run_ssh


SAIDAS_PADRAO = {
    "usuario": "root\n", "kernel": "Linux 6.1.0-18-amd64\n",
    "sistema": 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n',
    "disco": "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
             "/dev/vda1 50000000 47000000 3000000 94% /\n",
    "memoria": "MemTotal: 4000000 kB\nMemAvailable: 2000000 kB\n",
    "carga": "0.40 0.80 0.60 1/100 1\n", "cpus": "2\n", "boot": "172800.00 10.00\n",
}
