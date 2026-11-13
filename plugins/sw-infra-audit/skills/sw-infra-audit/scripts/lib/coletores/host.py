"""Coletor do alvo `host`: a máquina por SSH, mais os componentes declarados nela.

A máquina vira um componente de papel `maquina`, carregando o destino ssh — é assim que o endereço
chega ao adaptador sem mudar o contrato `perguntar(pergunta, componente, contexto)`.
"""
from lib import catalogo_host, descoberta, leitura_host, produtos, redact, runner
from lib import report as report_mod

ACESSO = ("Acesso com a identidade SSH de quem executou a auditoria ({usuario}). "
          "A restrição de comandos é da skill, não do servidor.")
RESTRITO = "Acesso restrito no servidor: a chave só executa o script de coleta."


def _rodar(alvo, contexto, chave, erros):
    comando = catalogo_host.carregar()["comandos"][chave]
    return runner.run_ssh(alvo["ssh_destino"], alvo.get("porta"), comando, contexto["timeout"], erros)


REGRAS_PRODUZIDAS = {"servico_declarado_ausente", "SEC_BIND_ALL_INTERFACES"}
FONTE_DA_ORIGEM = {"unidade": "servicos", "processo": "portas", "container": "containers"}
PAPEIS_COM_DADO = {"banco", "cache", "busca", "fila"}


def _comparar(alvo, contexto, declarados, erros):
    """Declarado × encontrado, por `origem`. Ausência só vira achado se a fonte de origem respondeu."""
    saidas = {chave: _rodar(alvo, contexto, chave, erros) for chave in FONTE_DA_ORIGEM.values()}
    resultado = descoberta.descobrir(saidas, produtos.carregar(),
                                     catalogo_host.carregar()["ignorar"])
    encontrados = {c["origem"]: c for c in resultado["candidatos"]}
    notas = []
    for comp in declarados:
        origem = comp.get("origem")
        if not origem:
            continue
        fonte = FONTE_DA_ORIGEM[origem.split(":", 1)[0]]
        visto = encontrados.get(origem)
        if visto is None and saidas[fonte] is None:
            notas.append(report_mod.na(f"{comp['nome']}: não medido — a leitura de {fonte} falhou"))
        elif visto is None:
            comp["achados"].append({"regra": "servico_declarado_ausente", "objeto": comp["nome"],
                                    "severidade": "high"})
        elif visto["todas_interfaces"] and comp.get("papel") in PAPEIS_COM_DADO:
            comp["achados"].append({"regra": "SEC_BIND_ALL_INTERFACES", "severidade": "medium",
                                    "objeto": f"{comp['nome']}:{','.join(map(str, visto['portas']))}"})
    declaradas = {c.get("origem") for c in declarados}
    # pela LISTA, não pelo dicionário: candidatos não graváveis compartilham a origem
    # "(não gravável)" e colapsariam numa chave só, perdendo a nota.
    for visto in resultado["candidatos"]:
        origem = visto["origem"]
        if visto["reconhecido"] and origem not in declaradas:
            notas.append(report_mod.na(f"descoberto e não declarado: {visto['produto']} "
                                       f"({origem}) — rode `configurar.py descobrir --alvo "
                                       f"{alvo['nome']}`"))
    return notas


def coletar(alvo, contexto):
    erros = []
    usuario = _rodar(alvo, contexto, "usuario", erros)
    if usuario is None:
        motivo = redact.scrub_text(erros[0]["reason"]) if erros else "o ssh falhou sem detalhe"
        return {"saude": "sem dados", "fatos": {}, "componentes": [], "achados": [],
                "nao_coletado": [report_mod.na(motivo)]}
    usuario = usuario.strip()
    fatos = {"usuario": usuario,
             "acesso": RESTRITO if alvo.get("acesso_restrito") else ACESSO.format(usuario=usuario)}
    kernel = _rodar(alvo, contexto, "kernel", erros)
    if kernel:
        fatos["kernel"] = kernel.strip()
    sistema = leitura_host.sistema(_rodar(alvo, contexto, "sistema", erros) or "")
    if sistema:
        fatos["sistema"] = sistema
    maquina = {"nome": alvo["nome"], "papel": "maquina", "papel_origem": "declarado",
               "ssh_destino": alvo["ssh_destino"], "porta": alvo.get("porta"),
               "respostas": [], "achados": []}
    if alvo.get("metricas_url"):
        maquina["metricas_url"] = alvo["metricas_url"]
    declarados = [dict(c, papel_origem="declarado", respostas=[], achados=[])
                  for c in alvo.get("componente", []) if c.get("nome") != alvo["nome"]]
    notas = _comparar(alvo, contexto, declarados, erros)
    return {"saude": "🟢", "fatos": fatos, "componentes": [maquina, *declarados], "achados": [],
            "nao_coletado": notas}
