"""Um `run_ssh` de mentira: devolve a saída gravada pela CHAVE do catálogo, sem rede.

Chave ausente simula comando que falhou. `conexao=False` simula a VPN desligada."""
from lib import catalogo_host


def runner_falso(saidas, conexao=True, chamadas=None):
    por_texto = {v: k for k, v in catalogo_host.carregar()["comandos"].items()}

    def run_ssh(destino, porta, comando, timeout, errors=None):
        chave = por_texto[comando]
        if chamadas is not None:
            chamadas.append(chave)
        if not conexao:
            if errors is not None:
                errors.append({"cmd": f"ssh {destino}",
                               "reason": f"não abri a sessão para {destino} (a VPN está ligada?)"})
            return None
        if chave not in saidas:
            if errors is not None:
                errors.append({"cmd": f"ssh {destino}", "reason": f"{chave} falhou"})
            return None
        return saidas[chave]
    return run_ssh


SAIDAS_PADRAO = {
    "usuario": "root\n", "kernel": "Linux 6.1.0-18-amd64\n",
    "sistema": 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n',
    "disco": "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
             "/dev/vda1 50000000 47000000 3000000 94% /\n",
    "memoria": "MemTotal: 4000000 kB\nMemAvailable: 2000000 kB\n",
    "carga": "0.40 0.80 0.60 1/100 1\n", "cpus": "2\n", "boot": "172800.00 10.00\n",
}
