"""Adaptador de leitura por dentro do container: última fonte, sem credencial.

Só roda comando declarado em `references/execs/<familia>.toml`, pelo `lib/runner.py`, que confere
a forma exata na allowlist. O alcance é o nó do context: `docker ps` só vê os containers dele, e
container em outro nó vira `sem_dados` com motivo.

O broker é lido uma vez por componente, e o resultado fica em `contexto["cache"]`. Lista pela
metade esconderia fila órfã, então qualquer falha no meio vira `sem_dados` da leitura inteira.
"""
import copy
import json
import re

from lib import catalogo_exec, extracao, redact, runner
from lib.adaptadores.admin_http import _com_identidade
from lib.coletores.docker_allowlist import exec_de_leitura

ID = "exec_leitura"
NOME_DE_SERVICO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}")


class _Falha(Exception):
    """A leitura parou: o texto é o motivo do `sem_dados`."""


def _sem_dados(pergunta, motivo, **extra):
    return dict({"pergunta": pergunta, "sem_dados": True, "motivo": motivo}, **extra)


def _rodar(cmd, contexto, o_que):
    prazo = contexto.get("prazo")
    if prazo is not None and prazo.esgotado():
        raise _Falha(prazo.motivo())
    timeout = contexto["timeout"] if prazo is None else prazo.timeout(contexto["timeout"])
    erros = []
    saida = runner.run(cmd, timeout, erros, context=contexto["docker_context"])
    if saida is None:
        razao = erros[0]["reason"] if erros else "sem detalhe"
        raise _Falha(f"{o_que} falhou: {redact.scrub_text(razao)}")
    return saida


def _lista_json(saida, o_que):
    if not saida.strip():
        raise _Falha(f"{o_que} não devolveu saída")
    try:
        valor = json.loads(saida)
    except ValueError:
        raise _Falha(f"{o_que} não devolveu JSON") from None
    if not isinstance(valor, list) or not all(isinstance(item, dict) for item in valor):
        raise _Falha(f"{o_que} devolveu um formato inesperado")
    return valor


def _container(servico, contexto):
    saida = _rodar(["docker", "ps", "--filter", f"label=com.docker.swarm.service.name={servico}",
                    "--format", "{{.ID}}"], contexto, "a busca do container")
    ids = sorted(linha.strip() for linha in saida.splitlines()
                 if catalogo_exec.ID_DE_CONTAINER.fullmatch(linha.strip()))
    if not ids:
        raise _Falha(f"o serviço não tem container no nó do context {contexto['docker_context']}: "
                     f"ele pode estar em outro nó, e `exec` só alcança este")
    return ids[0]


def _escopos(familia, container, contexto):
    bloco = familia["enumerar"]
    itens = _lista_json(_rodar(exec_de_leitura(container, bloco["argv"]), contexto, "a lista de vhosts"),
                        "a lista de vhosts")
    escopos = [item.get(bloco["campo"]) for item in itens]
    if not escopos:
        raise _Falha("a lista de vhosts veio vazia")
    if not all(isinstance(e, str) and catalogo_exec.VALOR_DA_VAGA.fullmatch(e) for e in escopos):
        raise _Falha("a lista de vhosts trouxe nome fora do formato aceito, e nada foi consultado nele")
    return sorted(set(escopos))


def _ler(familia, componente, contexto):
    """Os itens crus de todas as filas, cada um com o vhost consultado."""
    servico = str(componente.get("nome") or "")
    if not NOME_DE_SERVICO.fullmatch(servico):
        raise _Falha("o nome do serviço está fora do formato aceito")
    container = _container(servico, contexto)
    itens = []
    for vhost in _escopos(familia, container, contexto):
        argv = [vhost if t == catalogo_exec.VAGA else t for t in familia["listar"]["argv"]]
        o_que = "a lista de filas"
        itens += [dict(item, vhost=vhost)
                  for item in _lista_json(_rodar(exec_de_leitura(container, argv), contexto, o_que), o_que)]
    return itens


def _leitura(familia, componente, contexto):
    """`(itens, motivo)` — um dos dois é None. Falha também fica no cache: repetir não ajuda."""
    cache = contexto.setdefault("cache", {}).setdefault(ID, {})
    chave = componente.get("nome")
    if chave not in cache:
        try:
            cache[chave] = (_ler(familia, componente, contexto), None)
        except _Falha as falha:
            cache[chave] = (None, str(falha))
    return cache[chave]


def perguntar(pergunta, componente, contexto):
    """Responde a pergunta, ou devolve `sem_dados` com o motivo real. Fora do catálogo, nada roda."""
    try:
        familias = catalogo_exec.familias()
    except catalogo_exec.CatalogoInvalido as erro:
        return _sem_dados(pergunta, f"catálogo de comandos inválido: {erro}", nao_se_aplica=True)
    familia = next((f for f in familias if f["familia"] == componente.get("produto")), None)
    if familia is None or componente.get("exportador"):
        return _sem_dados(pergunta, "nenhum comando de leitura no catálogo para este produto",
                          nao_se_aplica=True)
    declarada = next((p for p in familia.get("pergunta", []) if p["id"] == pergunta), None)
    if declarada is None:
        return _sem_dados(pergunta, "o comando de leitura não mede este dado", nao_se_aplica=True)
    if not contexto.get("docker_context"):
        return _sem_dados(pergunta, "o alvo não tem docker context para o comando de leitura",
                          nao_se_aplica=True)

    itens, motivo = _leitura(familia, componente, contexto)
    if motivo:
        return _sem_dados(pergunta, motivo)
    try:
        valor = extracao.extrair(copy.deepcopy(itens), declarada)
    except extracao.ExtracaoInvalida as erro:
        return _sem_dados(pergunta, f"o catálogo de {familia['familia']} não casa com a saída: {erro}")
    return {"pergunta": pergunta, "fonte": f"exec:{familia['familia']}",
            "valor": _com_identidade(valor, declarada["identidade"]),
            "identidade": list(declarada["identidade"])}
