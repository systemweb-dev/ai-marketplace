"""Adaptador de produto num host: lê banco, cache e busca pelo cliente do próprio servidor, via SSH.

Tudo o que é específico de produto mora em `references/produtos-host/<produto>.toml` — o cliente por
modo de leitura, as consultas literais, o formato da saída e a extração: produto novo é um arquivo,
não um módulo. Prioridade 38, depois do `promql` e do `ssh` e antes do `exec_leitura`: exporter,
quando existe, continua vencendo.

Nunca levanta. Toda falha é `sem dados` com motivo, marcada `explica_a_falta`: num componente de host,
"declare metricas_url" mandaria o dono configurar algo de que ele não precisa. A senha vai só pela
entrada (stdin do ssh): nunca pelas vagas, pelo cache nem pela resposta.
"""
import copy
import re

from lib import catalogo_produto, credencial, extracao, redact, runner
from lib.perguntas import PERGUNTAS
from lib.vagas import COLECAO

ID = "produto_ssh"
SEM_CLIENTE = 127
FORA_DO_FORMATO = "a saída do cliente veio em formato inesperado"
SEM_LEITURAS = "sem leituras ainda: taxa indefinida"


class _Falha(Exception):
    def __init__(self, motivo, nao_publica=False):
        super().__init__(motivo)
        self.motivo, self.nao_publica = motivo, nao_publica


def _sem_dados(pergunta, motivo, **extra):
    return {"pergunta": pergunta, "sem_dados": True, "motivo": motivo, "explica_a_falta": True,
            **extra}


def _fora(pergunta, motivo):
    return {"pergunta": pergunta, "sem_dados": True, "motivo": motivo, "nao_se_aplica": True}


def respondidas(pasta=None):
    """As perguntas que algum catálogo de produto responde — para a trava de pergunta órfã."""
    return {p["id"] for catalogo in catalogo_produto.todos(pasta) for p in catalogo["pergunta"]}


def _vagas_do_cliente(molde, catalogo, componente):
    if "{container}" in molde:
        tipo, _, nome = str(componente.get("origem") or "").partition(":")
        if tipo != "container":
            raise _Falha('leitura = "container" precisa de componente com origem container:<nome>; '
                         f"este veio de {tipo or 'origem nenhuma'}")
        vagas = {"container": nome}
    else:
        vagas = {}
    if "{porta}" in molde:
        portas, padrao = componente.get("portas") or [], catalogo["porta_padrao"]
        vagas["porta"] = padrao if (not portas or padrao in portas) else min(portas)
    return vagas


def _motivo_da_falha(catalogo, modo, erro):
    texto, codigo = erro.get("reason") or "", erro.get("codigo")
    for item in catalogo["erro"]:
        if item.get("modo") not in (None, modo):
            continue
        if ("contem" in item and item["contem"] in texto) or ("codigo" in item
                                                             and item["codigo"] == codigo):
            return _Falha(item["motivo"], bool(item.get("nao_publica")))
    if codigo == SEM_CLIENTE:
        return _Falha(f"o cliente de {catalogo['produto']} não está instalado onde o comando roda")
    if codigo == 255:
        return _Falha(redact.scrub_text(texto))
    # o stderr do cliente costuma repetir o usuário (`'leitor'@'localhost'`): o que vem entre
    # aspas simples sai
    limpo = re.sub(r"'[^']*'", "'…'", redact.scrub_text(texto or "sem detalhe"))
    return _Falha(f"o cliente de {catalogo['produto']} saiu com erro: {limpo}")


def _texto(leitura, sql, componente, contexto, extra=None):
    """A saída de UMA consulta, em cache por componente e consulta — nunca pela senha."""
    vagas = {**leitura["vagas"], **(extra or {})}
    cache = contexto.setdefault("cache", {}).setdefault(ID, {})
    chave = (componente["nome"], leitura["molde"], sql, tuple(sorted(vagas.items())))
    if chave not in cache:
        erros = []
        saida = runner.run_ssh(componente["ssh_destino"], componente.get("porta"), leitura["molde"],
                               contexto["timeout"], erros, vagas={**vagas, "sql": sql},
                               entrada=leitura["entrada"])
        cache[chave] = (saida, erros[0] if erros else {"reason": "o comando falhou sem detalhe"})
    saida, erro = cache[chave]
    catalogo, modo = leitura["catalogo"], leitura["modo"]
    if saida is None:
        raise _motivo_da_falha(catalogo, modo, erro)
    for item in catalogo["erro"]:            # erro que o cliente escreve na SAÍDA com código 0
        if item.get("modo") in (None, modo) and item.get("contem") and item["contem"] in saida:
            raise _Falha(item["motivo"], bool(item.get("nao_publica")))
    return saida


def _parse(texto, declarada):
    doc = extracao.documento(texto, declarada["formato"], declarada["colunas"], declarada["separador"])
    if doc is None:
        raise _Falha(FORA_DO_FORMATO)
    return doc


def _montar(declarada, leitura, componente, contexto):
    """`(documento, nota)` da pergunta, ou `_Falha`."""
    enumerar = declarada["enumerar"]
    if enumerar is None:
        documento = {}
        for sql in declarada["sql"]:
            parte = _parse(_texto(leitura, sql, componente, contexto), declarada)
            if len(declarada["sql"]) == 1:
                return parte, None
            documento.update(parte)          # só `chave_valor` junta consultas (o catálogo garante)
        return documento, None
    indice = _parse(_texto(leitura, enumerar["sql"], componente, contexto), declarada)
    lista = extracao.ponteiro(indice, enumerar["lista"])
    if not isinstance(lista, list):
        raise _Falha("a lista a enumerar não veio na saída")
    nomes = [item.get(enumerar["campo"]) if isinstance(item, dict) else None for item in lista]
    aceitos = [n for n in nomes if isinstance(n, str) and COLECAO.fullmatch(n)]
    validos = sorted({n for n in nomes if isinstance(n, str) and COLECAO.fullmatch(n)})
    puladas = len(nomes) - len(aceitos)
    itens = [{"nome": nome, "resposta": _parse(_texto(leitura, declarada["sql"][0], componente,
                                                      contexto, {"colecao": nome}), declarada)}
             for nome in validos]
    nota = (f"{puladas} item(ns) com nome fora do formato aceito ficaram de fora, sem consulta"
            if puladas else None)
    return {"itens": itens}, nota


def _denominador_zero(documento, declarada):
    """A razão do `valor` veio None porque o denominador lido é zero (cache sem leitura nenhuma):
    indefinido por desenho, não saída fora do formato."""
    regra = (declarada["extracao"].get("derivar") or {}).get("valor") or {}
    if regra.get("tipo") not in ("razao", "percentual_de"):
        return False
    caminhos = regra.get("denominador_soma") or [regra.get("denominador")]
    valores = extracao._valores(documento, caminhos)
    return valores is not None and sum(valores) == 0


def perguntar(pergunta, componente, contexto):
    if not componente.get("origem") or not componente.get("ssh_destino"):
        return _fora(pergunta, "o componente não veio de um host")
    try:
        catalogo = catalogo_produto.do_produto(componente.get("produto"))
    except catalogo_produto.CatalogoInvalido as erro:
        return _sem_dados(pergunta, f"catálogo de {componente.get('produto')} inválido: {erro}")
    if catalogo is None:
        if PERGUNTAS.get(pergunta, {}).get("papel") == componente.get("papel"):
            return _sem_dados(pergunta, "não medido: falta catálogo ou exporter para "
                                        f"{componente.get('produto') or 'este produto'}")
        return _fora(pergunta, "nenhum catálogo de produto para este componente")
    declarada = next((p for p in catalogo["pergunta"] if p["id"] == pergunta), None)
    if declarada is None:
        return _fora(pergunta, f"o catálogo de {catalogo['produto']} não mede este dado")
    modo = componente.get("leitura")
    if not modo:
        return _sem_dados(pergunta, "leitura não declarada — rode `configurar.py leitura --alvo "
                                    f"<alvo> --componente {componente['nome']} --modo "
                                    "socket|senha|container|nenhum`")
    if modo == "nenhum":
        return _sem_dados(pergunta, 'leitura desligada pelo dono (leitura = "nenhum")',
                          nao_publica=True)
    molde = catalogo["cliente"].get(modo)
    if molde is None:
        depois = "; leitura com senha fica para uma próxima versão neste produto" if modo == "senha" else ""
        return _sem_dados(pergunta, f"o catálogo de {catalogo['produto']} não tem cliente para "
                                    f"leitura {modo}{depois}")
    destino, porta, alvo = componente["ssh_destino"], componente.get("porta"), contexto.get("alvo")
    try:
        vagas = _vagas_do_cliente(molde, catalogo, componente)
        cred = credencial.de_componente_ssh(componente, alvo, destino, porta)
        entrada = cred.entrada(alvo, destino, porta, componente["nome"]) if cred else None
        leitura = {"catalogo": catalogo, "modo": modo, "molde": molde, "vagas": vagas,
                   "entrada": entrada}
        documento, nota = _montar(declarada, leitura, componente, contexto)
        valor = extracao.extrair(copy.deepcopy(documento), declarada["extracao"])
    except _Falha as falha:
        return _sem_dados(pergunta, falha.motivo, **({"nao_publica": True} if falha.nao_publica else {}))
    except (credencial.CredencialFaltando, credencial.CredencialRecusada) as erro:
        return _sem_dados(pergunta, str(erro))
    except extracao.ExtracaoInvalida as erro:
        return _sem_dados(pergunta, f"o catálogo de {catalogo['produto']} não casa com a saída: {erro}")
    if PERGUNTAS[pergunta]["forma"] != "lista":
        valor = valor.get("valor")
        if valor is None and _denominador_zero(documento, declarada):
            return _sem_dados(pergunta, SEM_LEITURAS, nao_publica=True)
        if valor is None:
            return _sem_dados(pergunta, FORA_DO_FORMATO)
    resposta = {"pergunta": pergunta, "fonte": f"ssh:{catalogo['produto']}", "valor": valor}
    if nota:
        resposta["nota"] = nota
    return resposta
