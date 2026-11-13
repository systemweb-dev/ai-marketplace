"""O que roda num host: saídas de systemctl, ss e docker ps entram, candidatos saem. Puro, sem rede.

Força do casamento: processo > unidade > imagem; porta nunca identifica sozinha. Nada de pid, linha
de comando ou ambiente sai daqui — carregam senha, e o resultado vai para o terminal e para o
alvos.toml. Texto que vem do servidor só é gravável se casar `alvos.ORIGEM`.
"""
import re

from lib.alvos import NOME_VALIDO, ORIGEM
from lib.papel import POR_KIND

TODAS = {"0.0.0.0", "*", "[::]", "::"}
DO_DOCKER = {"docker-proxy", "dockerd"}
PROCESSO = re.compile(r'users:\(\("((?:[^"\\]|\\.)*)"')
PORTA_PUBLICADA = re.compile(r"(?:^|[\s,])([^\s,]*?):(\d+)->")


def _servicos(saida):
    return [linha.split()[0] for linha in (saida or "").splitlines() if linha.split()]


def _portas(saida):
    """{processo: [(endereco, porta)]}, na ordem em que aparecem."""
    por_processo = {}
    for linha in (saida or "").splitlines():
        partes = linha.split()
        if len(partes) < 4 or ":" not in partes[3]:
            continue
        endereco, _, porta = partes[3].rpartition(":")
        achado = PROCESSO.search(linha)
        if not porta.isdigit() or not achado:
            continue
        por_processo.setdefault(achado.group(1), []).append((endereco, int(porta)))
    return por_processo


def _containers(saida):
    lista = []
    for linha in (saida or "").splitlines():
        campos = linha.split("\t")
        if len(campos) < 2 or not campos[0]:
            continue
        publicadas = PORTA_PUBLICADA.findall(campos[2] if len(campos) > 2 else "")
        lista.append({"nome": campos[0], "imagem": campos[1],
                      "portas": sorted({int(p) for _, p in publicadas}),
                      "todas": any(e in ("0.0.0.0", "", "::", "[::]") for e, _ in publicadas)})
    return lista


def _nome_de(origem):
    bruto = origem.split(":", 1)[1].removesuffix(".service").replace("@", "-")
    limpo = re.sub(r"[^A-Za-z0-9._-]", "-", bruto)[:64]
    return limpo if NOME_VALIDO.fullmatch(limpo) else "componente"


def _candidato(origem, produto, portas, todas):
    gravavel = bool(ORIGEM.fullmatch(origem))
    return {"nome": _nome_de(origem) if gravavel else "componente",
            "produto": produto["nome"] if produto else None,
            "papel": POR_KIND.get(produto.get("kind")) if produto else None,
            "origem": origem if gravavel else "(não gravável)",
            "portas": sorted(set(portas)), "todas_interfaces": bool(todas),
            "reconhecido": produto is not None, "gravavel": gravavel,
            "motivo": "" if gravavel else "nome com caractere não aceito"}


def _melhor_unidade(units, processo, produto):
    """Entre as units de um produto, a de nome igual ao processo vence; depois, a de nome igual a
    um trecho de `unidade`; depois, a primeira em ordem. Sem isso, a primeira em ordem alfabética
    ficava com o produto, e um `prometheus-redis-exporter` roubava o Redis."""
    def nota(unit):
        base = unit.lower().removesuffix(".service").split("@")[0]
        if processo and base == processo.lower():
            return 0
        return 1 if base in produto.get("unidade", ()) else 2
    return min(units, key=lambda u: (nota(u), u)) if units else None


def _sem_repeticao(candidatos):
    """Nome repetido (a unit e o container `qdrant`) ganha o tipo da origem como sufixo: o
    `--gravar` escolhe por nome, e um dos dois ficaria impossível de escolher."""
    contagem = {}
    for c in candidatos:
        contagem[c["nome"]] = contagem.get(c["nome"], 0) + 1
    for c in candidatos:
        if c["gravavel"] and contagem[c["nome"]] > 1:
            novo = f"{c['nome']}-{c['origem'].split(':', 1)[0]}"[:64]
            c["nome"] = novo if NOME_VALIDO.fullmatch(novo) else c["nome"]
    return candidatos


def descobrir(saidas, produtos, ignorar):
    from lib.produtos import nome_do_caminho, por_processo, por_unidade

    nao_medidas = [fonte for fonte in ("servicos", "portas", "containers") if saidas.get(fonte) is None]
    # Exporter não é o que se audita: ele é FONTE de medida. Reconhecê-lo serve para que a unit
    # dele não seja confundida com a do produto que ele mede.
    unidades = {}
    for unit in _servicos(saidas.get("servicos")):
        produto = por_unidade(unit, produtos)
        if produto is not None and not produto.get("exportador"):
            unidades.setdefault(produto["nome"], []).append(unit)
    candidatos, produtos_vistos = [], set()
    for processo, escutas in _portas(saidas.get("portas")).items():
        if processo in ignorar or processo in DO_DOCKER:
            continue
        produto = por_processo(processo, produtos)
        if produto is not None and produto.get("exportador"):
            continue
        unit = _melhor_unidade(unidades.get(produto["nome"], []), processo, produto) if produto else None
        origem = f"unidade:{unit}" if unit else f"processo:{processo}"
        candidatos.append(_candidato(origem, produto, [p for _, p in escutas],
                                     any(e in TODAS for e, _ in escutas)))
        if produto:
            produtos_vistos.add(produto["nome"])
    for nome_produto, units in unidades.items():
        if nome_produto not in produtos_vistos:
            produto = next(p for p in produtos if p["nome"] == nome_produto)
            candidatos.append(_candidato(f"unidade:{_melhor_unidade(units, None, produto)}",
                                         produto, [], False))
    for container in _containers(saidas.get("containers")):
        nome_produto = nome_do_caminho(container["imagem"], produtos)
        produto = next((p for p in produtos if p["nome"] == nome_produto), None)
        if (produto is None and not container["portas"]) or (produto or {}).get("exportador"):
            continue
        candidatos.append(_candidato(f"container:{container['nome']}", produto,
                                     container["portas"], container["todas"]))
    candidatos.sort(key=lambda c: c["origem"])
    return {"candidatos": _sem_repeticao(candidatos), "nao_medidas": nao_medidas}
