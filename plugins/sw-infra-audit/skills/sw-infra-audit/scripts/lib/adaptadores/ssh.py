"""Adaptador de máquina por SSH: responde as perguntas `maquina.*` lendo o host.

Mesmo contrato dos outros: valor com fonte, ou `sem_dados` com motivo — nunca levanta. Cada comando
roda uma vez por componente; a resposta (ou a falha) fica em `contexto["cache"]["ssh"]`, então a VPN
desligada custa UMA tentativa por comando, não uma por pergunta.
"""
from lib import catalogo_host, leitura_host, redact, runner

ID = "ssh"
LEITURAS = {
    "maquina.disco": (("disco",), leitura_host.disco),
    "maquina.memoria": (("memoria",), leitura_host.memoria),
    "maquina.carga": (("carga", "cpus"), leitura_host.carga),
    "maquina.desde_o_boot": (("boot",), leitura_host.desde_o_boot),
}


def _sem_dados(pergunta, motivo, **extra):
    return dict({"pergunta": pergunta, "sem_dados": True, "motivo": motivo}, **extra)


def _ler(componente, chave, contexto):
    cache = contexto.setdefault("cache", {}).setdefault("ssh", {})
    indice = (componente["ssh_destino"], componente.get("porta"), chave)
    if indice not in cache:
        erros = []
        comando = catalogo_host.carregar()["comandos"][chave]
        saida = runner.run_ssh(componente["ssh_destino"], componente.get("porta"), comando,
                               contexto["timeout"], erros)
        cache[indice] = (saida, erros[0]["reason"] if erros else None)
    return cache[indice]


def perguntar(pergunta, componente, contexto):
    if not componente.get("ssh_destino"):
        return _sem_dados(pergunta, "o componente não tem destino ssh", nao_se_aplica=True)
    if pergunta not in LEITURAS:
        return _sem_dados(pergunta, "a leitura por ssh não mede este dado", nao_se_aplica=True)
    chaves, funcao = LEITURAS[pergunta]
    saidas = []
    for chave in chaves:
        saida, motivo = _ler(componente, chave, contexto)
        if saida is None:
            return _sem_dados(pergunta, redact.scrub_text(motivo or "o comando falhou sem detalhe"))
        saidas.append(saida)
    valor = funcao(*saidas)
    if valor is None:
        return _sem_dados(pergunta, "a saída do comando veio em formato inesperado")
    return {"pergunta": pergunta, "fonte": "ssh", "valor": valor}
