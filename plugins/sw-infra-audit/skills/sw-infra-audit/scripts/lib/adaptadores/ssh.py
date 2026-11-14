"""Adaptador por SSH: a máquina (`maquina.*`), o estado de cada serviço de host (`servico.*`) e a
idade do backup declarado.

Mesmo contrato dos outros: valor com fonte, ou `sem_dados` com motivo — nunca levanta. Cada comando
roda uma vez por componente; a resposta (ou a falha) fica em `contexto["cache"]["ssh"]`, então a VPN
desligada custa UMA tentativa por comando, não uma por pergunta. O dado que a fonte não tem por
construção sai com `nao_publica`, que a cobertura não conta como lacuna.
"""
from datetime import date

from lib import catalogo_host, leitura_host, leitura_servico, redact, runner
from lib.adaptadores.promql import momento

ID = "ssh"
LEITURAS = {
    "maquina.disco": (("disco",), leitura_host.disco),
    "maquina.memoria": (("memoria",), leitura_host.memoria),
    "maquina.carga": (("carga", "cpus"), leitura_host.carga),
    "maquina.desde_o_boot": (("boot",), leitura_host.desde_o_boot),
}
SERVICO = ("servico.ativo", "servico.desde", "servico.reinicios", "servico.memoria")
BACKUP = "banco.backup_idade"
RESPONDE = frozenset(LEITURAS) | frozenset(SERVICO) | {BACKUP}
FORA_DO_FORMATO = "a saída do comando veio em formato inesperado"


def _sem_dados(pergunta, motivo, **extra):
    return dict({"pergunta": pergunta, "sem_dados": True, "motivo": motivo}, **extra)


def _ler(componente, chave, contexto, vagas=None):
    cache = contexto.setdefault("cache", {}).setdefault("ssh", {})
    indice = (componente["ssh_destino"], componente.get("porta"), chave,
              tuple(sorted((vagas or {}).items())))
    if indice not in cache:
        erros = []
        catalogo = catalogo_host.carregar()
        comando = catalogo["moldes"][chave] if vagas else catalogo["comandos"][chave]
        saida = runner.run_ssh(componente["ssh_destino"], componente.get("porta"), comando,
                               contexto["timeout"], erros, vagas=vagas)
        cache[indice] = (saida, erros[0]["reason"] if erros else None)
    return cache[indice]


def _estado(componente, contexto):
    """`(leitura, None)` ou `(None, motivo)`. `leitura` é o dicionário de `lib/leitura_servico`."""
    tipo, _, valor = str(componente.get("origem") or "").partition(":")
    if tipo == "unidade":
        show, motivo = _ler(componente, "servico_unidade", contexto, {"unidade": valor})
        if show is None:
            return None, motivo
        uptime, _ = _ler(componente, "boot", contexto)
        return leitura_servico.de_unidade(show, uptime or ""), None
    if tipo == "container":
        inspect, motivo = _ler(componente, "servico_container", contexto, {"container": valor})
        if inspect is None:
            return None, motivo
        stats, _ = _ler(componente, "memoria_container", contexto, {"container": valor})
        return leitura_servico.de_container(inspect, stats, momento(contexto.get("at"))), None
    if tipo == "processo":
        ps, motivo = _ler(componente, "processos", contexto)
        if ps is None:
            return None, motivo
        return leitura_servico.de_processo(ps, valor), None
    return None, "a origem do componente não é unidade, container nem processo"


def _servico(pergunta, componente, contexto):
    leitura, motivo = _estado(componente, contexto)
    if leitura is None:
        return _sem_dados(pergunta, redact.scrub_text(motivo or FORA_DO_FORMATO))
    valor = leitura.get(pergunta)
    if isinstance(valor, leitura_servico.PorDesenho):
        return _sem_dados(pergunta, valor.motivo, nao_publica=True)
    if valor is None:
        return _sem_dados(pergunta, FORA_DO_FORMATO)
    return {"pergunta": pergunta, "fonte": "ssh", "valor": valor}


def _backup(pergunta, componente, contexto):
    try:
        hoje = date.fromisoformat(str(contexto.get("at"))[:10])
    except ValueError:
        return _sem_dados(pergunta, "a rodada não tem data (--at) para medir a idade do backup")
    saida, motivo = _ler(componente, "backup", contexto, {"backup_pasta": componente["backup_pasta"]})
    if saida is None:
        return _sem_dados(pergunta, "pasta de backup inexistente ou ilegível: "
                                    + redact.scrub_text(motivo or "sem detalhe"))
    idade = leitura_servico.idade_do_backup(saida, hoje)
    if idade is None:
        return _sem_dados(pergunta, "a pasta de backup está vazia")
    return {"pergunta": pergunta, "fonte": "ssh", "valor": idade}


def perguntar(pergunta, componente, contexto):
    if not componente.get("ssh_destino"):
        return _sem_dados(pergunta, "o componente não tem destino ssh", nao_se_aplica=True)
    if pergunta in SERVICO:
        if not componente.get("origem"):
            return _sem_dados(pergunta, "o componente não veio de um host", nao_se_aplica=True)
        return _servico(pergunta, componente, contexto)
    if pergunta == BACKUP:
        if not componente.get("backup_pasta"):
            return _sem_dados(pergunta, "o componente não declara backup_pasta", nao_se_aplica=True)
        return _backup(pergunta, componente, contexto)
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
        return _sem_dados(pergunta, FORA_DO_FORMATO)
    return {"pergunta": pergunta, "fonte": "ssh", "valor": valor}
