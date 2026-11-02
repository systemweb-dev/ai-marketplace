"""Traduz as respostas dos componentes para o formato de cada bloco."""
import json
import re

from lib.coletores.docker import USO_POR_NO
from lib.produtos import carregar, nome_da_rota

SEM_FONTE = "sem fonte medida para este tipo"
PERGUNTA_DE_URLS = "entrada.urls_mais_acessadas"
SEM_FONTE_DE_URLS = ("nenhum proxy mediu URLs nesta rodada — declare `logs_url` no alvo docker do "
                     "alvos.toml, apontando para o Loki que recebe o log de acesso")
FONTE_INTEIRA = " (exporter inteiro)"
# `!Host(...)` exclui o domínio: mostrá-lo seria afirmar o contrário da regra.
_HOST = re.compile(r"(?<![!\w])Host\(([^)]*)\)")
_ENTRE_ASPAS = re.compile(r"[`\"']([^`\"']+)[`\"']")


def _componentes(papel, alvos):
    return [c for a in alvos for c in a.get("componentes") or [] if c.get("papel") == papel]


def _resposta(comp, pergunta):
    for r in comp.get("respostas") or []:
        if r.get("pergunta") == pergunta and not r.get("sem_dados"):
            return r.get("valor")
    return None


def _por_minuto(taxa):
    """Fila ociosa não traz taxa: fica None, porque "sem ritmo medido" não é ritmo zero."""
    return None if taxa is None else round(taxa * 60)


def _identidade(item):
    return item.get("objeto") or item.get("nome")


def _filas(alvos):
    filas = []
    for comp in _componentes("fila", alvos):
        taxas = {_identidade(t): t for t in _resposta(comp, "fila.taxa_entrada_saida") or []}
        for f in _resposta(comp, "fila.filas") or []:
            taxa = taxas.get(_identidade(f), {})
            fila = {"nome": f.get("nome"), "prontas": f.get("prontas"),
                    "consumidores": f.get("consumidores"),
                    "entrada": _por_minuto(taxa.get("entrada")),
                    "saida": _por_minuto(taxa.get("saida"))}
            if f.get("nao_confirmadas"):
                fila["nao_confirmadas"] = f["nao_confirmadas"]
            # Lista toda sem número não prova fila parada: estatística desligada responde igual
            # ao broker ocioso, e dizer "Ociosa" afirmaria um ritmo que ninguém mediu.
            if _identidade(f) not in taxas:
                fila["ritmo_nao_medido"] = True
            filas.append(fila)
    return {"filas": filas} if filas else {"motivo": "nenhuma fila respondeu nesta rodada"}


def _medido(valor):
    """Zero é medida; `None`, lista vazia e dicionário vazio não são."""
    return valor is not None and valor != [] and valor != {}


def _fontes(comp):
    """As URLs têm bloco próprio: a fonte delas não diz se dois proxies trazem a mesma medida."""
    return {str(r.get("fonte")) for r in comp.get("respostas") or []
            if not r.get("sem_dados") and r.get("pergunta") != PERGUNTA_DE_URLS}


def _fundir(grupo, rotulo):
    primeiro = grupo[0]
    nomes = " · ".join(item["nome"] for item in grupo)
    return dict(primeiro, nome=rotulo, cobre=nomes) if rotulo else dict(primeiro, nome=nomes)


def _uma_linha_por_medida(medidos, rotulo):
    """Fonte sem filtro por componente traz o mesmo número para todos, e é uma medida só. Quem a
    fonte reconheceu como dono sai sem o carimbo, então a comparação é sem ele."""
    grupos = {}
    for comp, item in medidos:
        fontes = _fontes(comp)
        limpas = sorted({f.replace(FONTE_INTEIRA, "") for f in fontes})
        valores = json.dumps({k: v for k, v in item.items() if k != "nome"}, sort_keys=True, default=str)
        grupo = grupos.setdefault((tuple(limpas), valores), {"itens": [], "inteira": False})
        grupo["itens"].append(item)
        grupo["inteira"] = grupo["inteira"] or any(FONTE_INTEIRA in f for f in fontes)
    itens = []
    for grupo in grupos.values():
        funde = grupo["inteira"] and len(grupo["itens"]) > 1
        itens += [_fundir(grupo["itens"], rotulo)] if funde else grupo["itens"]
    return itens


def _simples(papel, campos, rotulo_do_total=None, ajustar=None, manter_sem_medida=False):
    """`manter_sem_medida` mantém quem não respondeu depois dos medidos, com "sem dado". Se ninguém
    respondeu, o bloco inteiro diz o motivo: uma lista de "sem dado" não explicaria nada."""
    def montar(alvos):
        medidos, sem_medida = [], []
        for alvo in alvos:
            for comp in _componentes(papel, [alvo]):
                item = {"nome": comp.get("nome")}
                item.update({k: _resposta(comp, p) for k, p in campos.items()})
                if ajustar:
                    ajustar(alvo, item)
                if any(_medido(v) for k, v in item.items() if k != "nome"):
                    medidos.append((comp, item))
                else:
                    sem_medida.append(item)
        itens = _uma_linha_por_medida(medidos, rotulo_do_total)
        if not itens:
            return {"motivo": SEM_FONTE}
        return {"itens": itens + sem_medida if manter_sem_medida else itens}
    return montar


def _dominios(regra):
    return sorted({d for trecho in _HOST.findall(str(regra)) for d in _ENTRE_ASPAS.findall(trecho)})


def _rotas(alvo):
    """Por nome de rota, quem a declara e seus domínios. É por alvo: o mesmo nome de rota em
    dois clusters são duas rotas."""
    servicos = (alvo.get("fatos") or {}).get("services")
    produtos = carregar()
    rotas = {}
    for servico in sorted(servicos if isinstance(servicos, list) else [], key=lambda s: str(s.get("name") or "")):
        for chave, regra in sorted((servico.get("routing_labels") or {}).items()):
            nome = nome_da_rota(chave, produtos)
            if nome:
                rotas.setdefault(nome, {"servico": servico.get("name"), "hosts": _dominios(regra)})
    return rotas


def _nome_da_rota_medida(item):
    """O proxy publica `<nome>@<origem>`; a label do serviço declara só `<nome>`."""
    return str(item.get("nome") or "").split("@")[0]


def _com_dominio(alvo, item):
    if not item.get("servicos"):
        return
    rotas = _rotas(alvo)
    servicos = []
    for servico in item["servicos"]:
        nome = _nome_da_rota_medida(servico)
        dominios = rotas.get(nome, {}).get("hosts") or []
        servicos.append(dict(servico, nome=" · ".join(dominios) or nome or servico.get("nome"),
                             site=bool(dominios)))
    item["servicos"] = servicos


def _resposta_de_urls(alvo):
    """Dois proxies no alvo leem o mesmo Loki: vale a primeira medida, ou a primeira falta."""
    respostas = [r for c in _componentes("entrada", [alvo]) for r in c.get("respostas") or []
                 if r.get("pergunta") == PERGUNTA_DE_URLS]
    return next((r for r in respostas if not r.get("sem_dados") and not r.get("erro_interno")),
                respostas[0] if respostas else None)


def _sites_de_urls(medidas, itens):
    somas = {}
    for medida in medidas:
        for site in medida.get("sites") or []:
            somas[site["site"]] = somas.get(site["site"], 0) + site["acessos"]
    return [{"site": site, "acessos": acessos, "urls": [i for i in itens if i["site"] == site]}
            for site, acessos in sorted(somas.items(), key=lambda par: (-par[1], par[0]))]


def _urls(alvos):
    medidas, faltas = [], []
    for alvo in alvos:
        resposta = _resposta_de_urls(alvo)
        if resposta is None:
            continue
        if resposta.get("sem_dados") or resposta.get("erro_interno"):
            faltas.append({"alvo": alvo.get("nome"), "motivo": resposta.get("motivo")})
        elif not any(m.get("valor") == resposta.get("valor") for m in medidas):
            medidas.append(resposta)        # dois alvos no mesmo Loki leem as mesmas linhas
    if not medidas:
        return {"motivo": faltas[0]["motivo"] if faltas else SEM_FONTE_DE_URLS}
    itens = sorted((i for m in medidas for i in m.get("valor") or []),
                   key=lambda i: (-i["acessos"], i["nome"]))
    return {"geral": itens, "sites": _sites_de_urls(medidas, itens), "faltas": faltas,
            "erros": sorted((i for i in itens if i["erros"]), key=lambda i: (-i["erros"], i["nome"])),
            "lentas": sorted(itens, key=lambda i: (-i["p95_ms"], i["nome"])),
            "janelas": [m["janelas"] for m in medidas]}


ADAPTADORES = {
    "fila": _filas,
    "urls": _urls,
    "entrada": _simples("entrada", {"volume": "entrada.volume_na_janela",
                                    "status": "entrada.distribuicao_de_status",
                                    "latencia": "entrada.latencia",
                                    "servicos": "entrada.por_servico"}, "Proxy (total)", _com_dominio),
    "banco": _simples("banco", {"conexoes": "banco.conexoes", "tamanho": "banco.tamanho"}),
    "cache": _simples("cache", {"memoria": "cache.memoria_usada", "evictions": "cache.evicções",
                                "acerto": "cache.acerto"}),
    "maquinas": _simples("maquina", {"cpu": "maquina.cpu", "memoria": "maquina.memoria",
                                     "disco": "maquina.disco", "dias": "maquina.disco_dias"},
                        manter_sem_medida=True),
    "consumo": _simples("app", {"cpu": "app.cpu", "memoria": "app.memoria"}),
}


def dados_do_papel(papel, alvos):
    if papel == "falhas":
        pontos = [p for a in alvos for p in (a.get("fatos") or {}).get("impact_points") or []]
        return {"itens": pontos} if pontos else {"motivo": "nenhum ponto de falha calculado"}
    adaptador = ADAPTADORES.get(papel)
    return adaptador(alvos) if adaptador else {"motivo": SEM_FONTE}


def _soma_por_stack(medidas, sistema, comp, chave, pergunta):
    valor = _resposta(comp, pergunta)
    if valor is not None:
        atual = medidas.setdefault(sistema, {})
        atual[chave] = atual.get(chave, 0) + valor


def medidas_por_stack(alvos):
    """`cpu` é soma de `app.cpu` (100 = um núcleo), `memoria` é soma de `app.memoria` em bytes e
    `disponivel` é o menor `app.disponibilidade_7d` da stack. Com mais de um alvo, a chave leva o
    alvo: a mesma stack em dois clusters não soma."""
    from lib.stacks import no_alvo, stack_of, varios_alvos
    varios = varios_alvos(alvos)
    medidas = {}
    for alvo in alvos:
        for comp in _componentes("app", [alvo]):
            sistema = no_alvo(alvo, stack_of(comp.get("nome")), varios)
            valor = _resposta(comp, "app.disponibilidade_7d")
            if valor is not None:
                atual = medidas.setdefault(sistema, {})
                atual["disponivel"] = min(valor, atual.get("disponivel", 100))
            _soma_por_stack(medidas, sistema, comp, "cpu", "app.cpu")
            _soma_por_stack(medidas, sistema, comp, "memoria", "app.memoria")
        rotas = _rotas(alvo)
        for comp in _componentes("entrada", [alvo]):
            for item in _resposta(comp, "entrada.por_servico") or []:
                rota = rotas.get(_nome_da_rota_medida(item))
                if rota and item.get("resposta") is not None:
                    atual = medidas.setdefault(no_alvo(alvo, stack_of(rota["servico"]), varios), {})
                    atual["resposta"] = max(item["resposta"], atual.get("resposta", 0))
    return medidas


def _maquinas_medidas(alvo):
    """Todos os nós com CPU e memória: um nó sem medida mantém o aviso verdadeiro."""
    medidas = [c for c in _componentes("maquina", [alvo])
               if _resposta(c, "maquina.cpu") is not None and _resposta(c, "maquina.memoria") is not None]
    return bool(medidas) and len(medidas) >= len((alvo.get("fatos") or {}).get("nodes") or [])


def nao_coletado_vigente(alvo):
    """O coletor do Docker escreve o aviso de uso por nó antes de haver qualquer resposta de métrica."""
    lacunas = alvo.get("nao_coletado") or []
    if not _maquinas_medidas(alvo):
        return lacunas
    return [n for n in lacunas if not str(n.get("motivo") or n.get("reason")).startswith(USO_POR_NO)]
