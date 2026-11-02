import math
import re
from datetime import datetime

from lib import remediacao
from lib.blocos.consumo import _cores as nucleos
from lib.blocos.entrada import FAIXA_DE_LATENCIA
from lib.blocos.maquinas import _tom as tom_de_uso
from lib.coletores.http import DIAS_DE_ALERTA
from lib.estado_servico import com_alerta, estado_de, replicas_de
from lib.html_comum import SEM_DADO, _e, inteiro, medido, nao_medido, painel, percentual, plural, tamanho
from lib.nota import _aceitos, _conta_do_alvo
from lib.regras import REGRAS, esperada
from lib.rule_meta import meta
from lib.stacks import no_alvo, stack_of, varios_alvos
from lib.triagem import ORDEM_SEVERIDADE

VEREDITOS = {"bom": "Tudo em ordem nos serviços.",
             "atencao": "Quase tudo no ar, com pontos que pedem atenção.",
             "critico": "Há falha grave que exige ação agora."}
ROTULO_FAIXA = {"bom": "Bom", "atencao": "Atenção", "critico": "Crítico"}
TOM_IMPACTO = {"crítico": "crit", "critico": "crit", "alto": "crit",
               "médio": "warn", "medio": "warn", "baixo": "ok"}
METRICAS = (("erros", "Erros nos sites"), ("resposta", "Tempo de resposta"),
            ("cpu", "CPU das máquinas"), ("memoria", "Memória"), ("disco", "Disco"))
ERROS_ATENCAO, ERROS_CRITICO = 1, 5
CIRCUNFERENCIA = 2 * math.pi * 46
MAXIMO_DE_PRIORIDADES = 5
MAXIMO_DE_NOMES = 5
REDUNDANCIA_BOA, REDUNDANCIA_MEDIA = 80, 60
MAXIMO_DE_CERTIFICADOS = 3
MAXIMO_DE_FALTOU = 6
GRAVIDADE = {"critical": "crítico", "high": "alto", "medium": "médio", "low": "baixo"}
ORDEM_ESTADO = ("fora", "parcial", "sem_dado", "online", "proposital")
ROTULO_ESTADO = {"fora": "Fora do ar", "parcial": "Parcial",
                 "sem_dado": "Sem dado", "online": "Online", "proposital": "Parado de propósito"}
TOM_ESTADO = {"fora": "crit", "parcial": "warn", "sem_dado": "warn",
              "online": "ok", "proposital": "neutro"}
ID_DE_REGRA = re.compile(r"\b(?:" + "|".join(sorted(REGRAS, key=len, reverse=True))
                         + r"|(?:OPS|SEC)_[A-Z0-9_]+)\b")
COLUNAS_SAUDE = (("Sistema", "bl-e", 21), ("Online", "bl-d", 8), ("Estado", "bl-e", 14),
                 ("Disponível (7 dias)", "bl-d", 13), ("Resposta", "bl-d", 10), ("CPU", "bl-e", 17),
                 ("Memória", "bl-e", 17))


def _nome_da_regra(regra):
    rotulo = meta(regra)["label"]
    if rotulo != regra:
        return rotulo
    bloco = remediacao.para(regra)
    return bloco["titulo"] if bloco else regra.split("_", 1)[-1].replace("_", " ").capitalize()


def _legivel(texto):
    """A recomendação vem do agente e o histórico traz a chave do achado: nos dois pode vir id."""
    return ID_DE_REGRA.sub(lambda casou: _nome_da_regra(casou.group()),
                           "" if texto is None else str(texto))


def _e_mais(total, visiveis):
    return f" e mais {total - visiveis}" if total > visiveis else ""


def _data_curta(texto):
    casou = re.search(r"\d{4}-(\d{2})-(\d{2})", str(texto))
    return f"{casou.group(2)}/{casou.group(1)}" if casou else str(texto)


def _data_completa(carimbo):
    try:
        return datetime.fromisoformat(str(carimbo).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return str(carimbo)


def _contexto(ctx):
    nomes = [a.get("nome") for a in ctx.get("alvos") or [] if a.get("coletado", True) and a.get("nome")]
    partes = [", ".join(nomes)] if nomes else []
    if ctx.get("gerado_em"):
        partes.append(f'Auditoria de {_data_completa(ctx["gerado_em"])}')
    anterior = (ctx.get("historico") or {}).get("vs")
    if anterior:
        partes.append(f"comparada com {_data_curta(anterior)}")
    return f'<div class="bl-hm">{_e(" · ".join(partes))}</div>' if partes else ""


def _curtos(nomes):
    """Sem o prefixo da stack, exceto quando dois serviços ficariam com o mesmo nome."""
    sem_stack = [n.split("_", 1)[-1] for n in nomes]
    return [curto if sem_stack.count(curto) == 1 else nome for nome, curto in zip(nomes, sem_stack)]


def _nomes_por_estado(ctx):
    """Quem pede atenção, em ordem de gravidade: `fora`, `parcial` e `alerta`."""
    aceites = ctx.get("aceites") or []
    nomes = {"fora": [], "parcial": [], "alerta": []}
    for alvo in ctx.get("alvos") or []:
        if not alvo.get("coletado", True):
            continue
        if alvo.get("tipo") == "http":
            if _conta_do_alvo(alvo, aceites)["fora"]:
                nomes["fora"].append(alvo.get("nome"))
            continue
        servicos = (alvo.get("fatos") or {}).get("services")
        aceitos = _aceitos(alvo, aceites)
        for s in servicos if isinstance(servicos, list) else []:
            estado = estado_de(s, aceitos)
            if com_alerta(s, aceitos):
                nomes["alerta"].append(s.get("name"))
            elif estado in ("fora", "parcial"):
                nomes[estado].append(s.get("name"))
    todos = [str(n) for grupo in nomes.values() for n in grupo]
    curto = dict(zip(todos, _curtos(todos)))
    return {estado: [curto[n] for n in sorted(map(str, grupo))] for estado, grupo in nomes.items()}


def _anel(nota):
    arco = CIRCUNFERENCIA * min(max(nota["valor"], 0), 100) / 100
    return (f'<svg class="bl-nota" viewBox="0 0 112 112" role="img" aria-label="Nota {nota["valor"]} de 100">'
            '<circle class="bl-nota-f" cx="56" cy="56" r="46"/>'
            f'<circle class="bl-nota-v" cx="56" cy="56" r="46" stroke-dasharray="{arco:.1f} '
            f'{CIRCUNFERENCIA:.1f}" transform="rotate(-90 56 56)"/>'
            f'<text x="56" y="67" text-anchor="middle" class="bl-nota-n">{nota["valor"]}</text></svg>')


def _nota(nota):
    rotulo = "Nota geral (parcial)" if nota["parcial"] else "Nota geral"
    if _limitada(nota):
        rotulo += f', limitada a {nota["teto"]}'
    return (f'<div class="bl-hn">{_anel(nota)}<div><b>{_e(ROTULO_FAIXA[nota["faixa"]])}</b>'
            f'<span>{_e(rotulo)}</span></div></div>')


def _limitada(nota):
    return nota.get("teto") is not None and nota["valor"] == nota["teto"]


def _nomes_da_barra(nomes):
    """Até cinco nomes no total, do mais grave ao mais leve. Grupo sem vaga mostra só a contagem."""
    vagas, partes = MAXIMO_DE_NOMES, []
    for estado, rotulo in (("fora", "Fora"), ("parcial", "Parcial"), ("alerta", "Com alerta")):
        grupo = nomes[estado]
        if not grupo:
            continue
        visiveis = grupo[:vagas]
        vagas -= len(visiveis)
        lista = f'{", ".join(visiveis)}{_e_mais(len(grupo), len(visiveis))}' if visiveis else str(len(grupo))
        partes.append(f"{rotulo}: {lista}")
    return f'<small>{_e(". ".join(partes))}</small>' if partes else ""


def _online(nota, nomes):
    online, alerta = nota["online"], nota.get("com_alerta", 0)
    parciais = (nota.get("limites") or {}).get("parciais", 0)
    fora = nota["base"] - online - parciais
    amarelos = parciais + alerta
    barra = (f'<i style="flex:{online - alerta}"></i>' if online - alerta else "") \
        + (f'<s style="flex:{amarelos}"></s>' if amarelos else "") \
        + (f'<u style="flex:{fora}"></u>' if fora else "")
    aviso = f'<em class="bl-hal">{alerta} com alerta</em>' if alerta else ""
    return (f'<div class="bl-hon"><b>{online}</b><span>de {nota["base"]} serviços online</span>{aviso}'
            f'<div class="bl-seg">{barra}</div>{_nomes_da_barra(nomes)}</div>')


def _citados(nomes):
    visiveis = nomes[:MAXIMO_DE_NOMES]
    return f' ({", ".join(visiveis)}{_e_mais(len(nomes), len(visiveis))})' if visiveis else ""


def _causas_do_teto(nota, nomes):
    limites = nota.get("limites") or {}
    if nota["teto"] <= 59:
        return [c for c in (
            limites.get("fora") and plural(limites["fora"], "serviço fora do ar", "serviços fora do ar")
            + _citados(nomes["fora"]),
            limites.get("nos_fora") and plural(limites["nos_fora"], "nó fora do ar", "nós fora do ar")) if c]
    regras = [_nome_da_regra(r) for r in limites.get("regras_altas") or []]
    return [c for c in (
        limites.get("parciais") and plural(limites["parciais"], "serviço parcial", "serviços parciais")
        + _citados(nomes["parcial"]),
        limites.get("altos") and plural(limites["altos"], "problema alto", "problemas altos")
        + _citados(regras)) if c]


def _por_que(nota, nomes):
    alerta = nota.get("com_alerta", 0)
    fatos = [f'Serviços: {nota["online"]} de {nota["base"]} online'
             + (f", {alerta} com alerta." if alerta else ".")]
    parcelas = nota.get("parcelas") or {}
    if "estabilidade" in parcelas:
        valor = parcelas["estabilidade"]
        nivel = ("boa" if valor >= REDUNDANCIA_BOA else "média" if valor >= REDUNDANCIA_MEDIA else "baixa") \
            if valor is not None else None
        fatos.append(f"Redundância {nivel}: {valor}%." if nivel else "Redundância não medida.")
    if "praticas" in parcelas:
        valor = parcelas["praticas"]
        fatos.append("Boas práticas não medidas." if valor is None else f"Boas práticas: {valor}%.")
    if _limitada(nota):
        causas = _causas_do_teto(nota, nomes)
        fatos.append(f'Nota limitada a {nota["teto"]}: {_lista(causas)}.' if causas
                     else f'Nota limitada a {nota["teto"]}.')
    return f'<p class="bl-porque"><b>Por que esta nota:</b> {_e(" ".join(fatos))}</p>'


def _hero(ctx, nota, resumo_html):
    if not nota:
        return (f'<header class="bl-hero"><div class="bl-ht">{_contexto(ctx)}<h1>Sem nota nesta rodada.</h1>'
                f'{resumo_html}{nao_medido("nenhum serviço foi medido nesta rodada")}</div></header>')
    nomes = _nomes_por_estado(ctx)
    return (f'<header class="bl-hero bl-f-{nota["faixa"]}"><div class="bl-ht">{_contexto(ctx)}'
            f'<h1>{_e(_veredito(nota))}</h1>{resumo_html}</div>'
            f'{_nota(nota)}{_online(nota, nomes)}{_por_que(nota, nomes)}</header>')


def _nivel(impacto):
    texto = str(impacto or "").strip()
    if not texto:
        return "<span></span>"
    tom = TOM_IMPACTO.get(texto.lower(), "warn")
    return f'<span class="bl-nivel bl-nivel-{tom}">{_e(texto.capitalize())}</span>'


def _quem_age(regra):
    if regra.startswith("SEC_") or regra in ("sem_tls", "certificado_vencendo"):
        return "Segurança"
    return "Aplicação" if regra.startswith("fila_") else "Infraestrutura"


def _por_que_importa(regra, quantos):
    ocorrencias = plural(quantos, "ocorrência", "ocorrências")
    motivo = re.split(r"(?<=\.)\s", meta(regra)["why"], maxsplit=1)[0]
    return f"{ocorrencias}. {motivo}".strip()


def _problemas_prioritarios(achados, regras_das_recomendacoes):
    grupos = {}
    for a in achados:
        regra = a.get("regra")
        if regra and a.get("severidade") in GRAVIDADE and regra not in regras_das_recomendacoes \
                and not a.get("esperada") and not esperada(regra):
            grupos.setdefault(regra, []).append(ORDEM_SEVERIDADE.index(a["severidade"]))
    ordem = sorted(grupos, key=lambda regra: (min(grupos[regra]), -len(grupos[regra]), regra))
    return [{"impacto": GRAVIDADE[ORDEM_SEVERIDADE[min(grupos[regra])]], "titulo": _nome_da_regra(regra),
             "porque": _por_que_importa(regra, len(grupos[regra])), "alvo": _quem_age(regra)} for regra in ordem]


def _prioridades(recomendacoes, achados):
    """A do agente vem primeiro, porque sabe o contexto; o problema só ocupa a vaga que sobrou."""
    regras = {r.get("regra") for r in recomendacoes}
    vagas = max(0, MAXIMO_DE_PRIORIDADES - len(recomendacoes))
    recs = recomendacoes + _problemas_prioritarios(achados, regras)[:vagas]
    if not recs:
        return ""
    visiveis = recs[:MAXIMO_DE_PRIORIDADES]
    linhas = "".join(f'<li>{_nivel(r.get("impacto"))}<div><b>{_e(_legivel(r.get("titulo")))}</b>'
                     f'<p>{_e(_legivel(r.get("porque")))}</p></div><span class="bl-mini">{_e(r.get("alvo"))}</span></li>'
                     for r in visiveis)
    mais = _e_mais(len(recs), len(visiveis))
    resto = f'<p class="bl-mini">Recomendações{mais} nas próximas páginas.</p>' if mais else ""
    return f'<h2 class="bl-tit">O que fazer primeiro</h2><ol class="bl-prio">{linhas}</ol>{resto}'


def _exemplos(itens):
    return f'<span>{_e(_legivel(itens[0]))}{_e_mais(len(itens), 1)}</span>' if itens else ""


def _mudou(h, nota):
    if not h:
        return ""
    novos, resolvidos = h.get("novos") or [], h.get("resolvidos") or []
    titulo = f'Desde {_data_curta(h["vs"])}' if h.get("vs") else "Desde a última auditoria"
    linhas = (f'<li><b class="bl-c-ok">{len(resolvidos)} {"resolvido" if len(resolvidos) == 1 else "resolvidos"}</b>'
              f'{_exemplos(resolvidos)}</li>'
              f'<li><b class="bl-c-warn">{len(novos)} {"novo" if len(novos) == 1 else "novos"}</b>{_exemplos(novos)}</li>')
    anterior = h.get("nota_anterior")
    if anterior is not None and nota:
        tom = "ok" if nota["valor"] > anterior else "crit" if nota["valor"] < anterior else "warn"
        linhas += f'<li><b class="bl-c-{tom}">nota {_e(anterior)} → {nota["valor"]}</b></li>'
    aviso = f'<p class="bl-mini">{_e(h["aviso"])}</p>' if h.get("aviso") else ""
    return f'<h2 class="bl-tit">{_e(titulo)}</h2><ul class="bl-mudou">{linhas}</ul>{aviso}'


def linha_tendencia(valores):
    if len(valores) < 2:
        return ""
    alto, baixo = max(valores), min(valores)
    amplitude = (alto - baixo) or 1
    pontos = " ".join(f"{i * 100 / (len(valores) - 1):.1f},{26 - (v - baixo) * 22 / amplitude:.1f}"
                      for i, v in enumerate(valores))
    return ('<svg class="bl-spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline points="{pontos}" fill="none" stroke="currentColor" stroke-width="2" '
            'vector-effect="non-scaling-stroke"/></svg>')


def _valor_da_metrica(nome, valor):
    if nome == "erros":
        return f"{valor:.1f}%".replace(".", ",")
    return f"{inteiro(valor)} ms" if nome == "resposta" else percentual(valor)


def _tom_da_metrica(nome, valor):
    if nome == "erros":
        return "crit" if valor >= ERROS_CRITICO else "warn" if valor >= ERROS_ATENCAO else "ok"
    if nome == "resposta":
        return ("ok" if valor <= FAIXA_DE_LATENCIA["bom_ate"]
                else "crit" if valor >= FAIXA_DE_LATENCIA["ruim_a_partir"] else "warn")
    return tom_de_uso(valor)


def _tendencias(t):
    itens = ""
    for nome, rotulo in METRICAS:
        if nome not in t:
            continue
        serie = t[nome]
        if not serie:
            itens += f'<div class="bl-met"><span>{rotulo}</span><b>não medido</b></div>'
        else:
            tom = _tom_da_metrica(nome, serie[-1])
            itens += (f'<div class="bl-met bl-c-{tom}"><span>{rotulo}</span>'
                      f'<b>{_valor_da_metrica(nome, serie[-1])}</b>{linha_tendencia(serie)}</div>')
    return f'<div class="bl-mets">{itens}</div>' if itens else ""


def _validade(dias):
    if dias is None:
        return "ok", medido(None)
    if dias <= 0:
        return "crit", "vencido"
    tom = "warn" if dias <= DIAS_DE_ALERTA else "ok"
    return tom, f"{inteiro(dias)} {'dia' if dias == 1 else 'dias'}"


def _certificados(certs):
    if not certs:
        return ""
    ordem = sorted(certs, key=lambda c: (c.get("dias") is None, c.get("dias") or 0, str(c.get("nome") or "")))
    visiveis = ordem[:MAXIMO_DE_CERTIFICADOS]
    linhas = ""
    for c in visiveis:
        tom, texto = _validade(c.get("dias"))
        linhas += f'<div><span class="bl-n">{_e(c.get("nome"))}</span><b class="bl-c-{tom}">{texto}</b></div>'
    mais = _e_mais(len(certs), len(visiveis))
    resto = f'<p class="bl-mini">Certificados{mais} nas próximas páginas.</p>' if mais else ""
    return f'<h2 class="bl-tit">Certificados</h2><div class="bl-cert">{linhas}</div>{resto}'


def _pior(servicos):
    return min((estado for estado, _, _ in servicos), key=ORDEM_ESTADO.index)


def _resumo_da_saude(sistemas):
    conta = {}
    for servicos in sistemas.values():
        tom = TOM_ESTADO[_pior(servicos)]
        conta[tom] = conta.get(tom, 0) + 1
    partes = ((conta.get("ok"), "online"), (conta.get("warn"), "com atenção"), (conta.get("crit"), "fora do ar"),
              (conta.get("neutro"), "parado de propósito"))
    return " · ".join(f"{n} {rotulo}" for n, rotulo in partes if n)


def _celula_de_cpu(cpu):
    """A soma de `app.cpu` tem 100 por núcleo e passa de 100: não é percentual de nada."""
    return f'<td class="bl-e">{medido(cpu, nucleos)}</td>'


def _celula_de_memoria(bytes_em_uso):
    """`app.memoria` vem em bytes e nenhuma fonte diz o limite: sem denominador não há percentual."""
    return f'<td class="bl-e">{medido(bytes_em_uso, tamanho)}</td>'


def _replicas(servicos):
    """Soma do sistema. Parado de propósito não falta: `0/1` de job concluído daria "8/9" em "Online"."""
    contam = [r for estado, r, _ in servicos if estado != "proposital"] or [r for _, r, _ in servicos]
    lidas = [par for par in map(replicas_de, contam) if par]
    return f"{sum(p[0] for p in lidas)}/{sum(p[1] for p in lidas)}" if lidas else SEM_DADO


def _medidas_do_sistema(servicos, medidas):
    """Um rótulo pode juntar stacks: CPU e memória somam, disponível é o menor, resposta é a maior."""
    grupo = [medidas.get(stack, {}) for stack in sorted({s[2] for s in servicos})]
    regras = {"cpu": sum, "memoria": sum, "disponivel": min, "resposta": max}
    valores = {chave: [m[chave] for m in grupo if m.get(chave) is not None] for chave in regras}
    return {chave: regras[chave](lidos) for chave, lidos in valores.items() if lidos}


def _linha_do_sistema(nome, servicos, medidas):
    pior = _pior(servicos)
    tom = TOM_ESTADO[pior]
    m = _medidas_do_sistema(servicos, medidas)
    return (f'<tr><td class="bl-e"><span class="bl-nome"><i class="bl-pt bl-fl-{tom}"></i><b>{_e(nome)}</b></span></td>'
            f'<td class="bl-d">{_replicas(servicos)}</td><td class="bl-e"><b class="bl-c-{tom}">{_e(ROTULO_ESTADO[pior])}</b></td>'
            f'<td class="bl-d">{medido(m.get("disponivel"), lambda v: f"{v}%")}</td>'
            f'<td class="bl-d">{medido(m.get("resposta"), lambda v: f"{inteiro(v)} ms")}</td>'
            f'{_celula_de_cpu(m.get("cpu"))}{_celula_de_memoria(m.get("memoria"))}</tr>')


def _endpoints(alvos, aceites):
    """Só quando nenhum alvo trouxe serviço. Ninguém respondeu: fica "não medido", sem lista de "sem dado"."""
    http = [a for a in alvos if a.get("tipo") == "http"]
    if not any(a.get("fatos") for a in http):
        return {}
    sistemas = {}
    for alvo in http:
        conta = _conta_do_alvo(alvo, aceites)
        estado = "sem_dado" if not conta["base"] else "fora" if conta["fora"] else "online"
        replicas = f'{conta["online"]}/{conta["base"]}' if conta["base"] else None
        sistemas[alvo.get("nome")] = [(estado, replicas, alvo.get("nome"))]
    return sistemas


def saude_por_sistema(alvos, aceites, juntar_online=False, medidas=None):
    varios = varios_alvos(alvos)
    rodada = [a for a in alvos if a.get("coletado", True)]
    sistemas = {}
    for alvo in rodada:
        servicos = (alvo.get("fatos") or {}).get("services")
        if not isinstance(servicos, list):
            continue
        aceitos, rotulos = _aceitos(alvo, aceites), alvo.get("rotulos") or {}
        for s in servicos:
            pilha = stack_of(s.get("name"))
            sistemas.setdefault(no_alvo(alvo, rotulos.get(pilha, pilha), varios), []).append(
                (estado_de(s, aceitos), s.get("replicas"), no_alvo(alvo, pilha, varios)))
    rotulo = ("sistema", "sistemas")
    if not sistemas:
        sistemas, rotulo = _endpoints(rodada, aceites), ("endpoint", "endpoints")
    if not sistemas:
        return nao_medido("nenhum sistema foi medido nesta rodada")
    linhas, online = [], 0
    for nome in sorted(sistemas):
        if juntar_online and _pior(sistemas[nome]) == "online":
            online += 1
            continue
        linhas.append(_linha_do_sistema(nome, sistemas[nome], medidas or {}))
    if online:
        linhas.append(f'<tr><td colspan="{len(COLUNAS_SAUDE)}">{online} sistema{"s" if online > 1 else ""} online</td></tr>')
    larguras = "".join(f'<col style="width:{largura}%">' for _, _, largura in COLUNAS_SAUDE)
    titulos = "".join(f'<th class="{classe}">{titulo}</th>' for titulo, classe, _ in COLUNAS_SAUDE)
    tabela = (f'<table class="bl-tb bl-sis"><colgroup>{larguras}</colgroup><thead><tr>{titulos}</tr></thead>'
              f'<tbody>{"".join(linhas)}</tbody></table>')
    return painel(plural(len(sistemas), *rotulo), _resumo_da_saude(sistemas), tabela)


def _lista(itens):
    return f"{', '.join(itens[:-1])} e {itens[-1]}" if len(itens) > 1 else "".join(itens)


def _linha_do_que_faltou(faltou, motivo):
    visiveis = faltou[:MAXIMO_DE_FALTOU]
    if len(faltou) > len(visiveis):
        lista = f"{', '.join(visiveis)}{_e_mais(len(faltou), len(visiveis))}"
    else:
        lista = _lista(visiveis)
    porque = f" Motivo mais comum: {motivo}." if motivo else ""
    return (f'<div class="bl-naoviu"><p class="bl-nm"><b>Não medido:</b> {_e(lista)}.{_e(porque)} '
            'Isso não significa que estão bem.</p></div>')


def _veredito(nota):
    if nota["faixa"] == "bom" and nota.get("com_alerta"):
        return "Serviços no ar, com alertas para acompanhar."
    return VEREDITOS[nota["faixa"]]


def render_capa(ctx, nota, resumo_html, faltou):
    esquerda = _prioridades(ctx.get("recomendacoes") or [], ctx.get("achados") or [])
    direita = _mudou(ctx.get("historico") or {}, nota) + _certificados(ctx.get("certificados") or [])
    corpo = f'<div class="bl-corpo"><div>{esquerda}</div><aside>{direita}</aside></div>' if esquerda or direita else ""
    falta = _linha_do_que_faltou(faltou, ctx.get("motivo_do_que_faltou")) if faltou else ""
    return (f'<div class="bl-capa">{_hero(ctx, nota, resumo_html)}{_tendencias(ctx.get("tendencias") or {})}'
            f'{corpo}{falta}</div>')
