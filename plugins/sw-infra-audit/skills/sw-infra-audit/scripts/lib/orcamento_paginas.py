"""Corte por contagem: determinístico, igual no HTML e no PDF, sem depender de Chromium."""
LINHAS_POR_PAGINA = 26
ORCAMENTO = 20 * LINHAS_POR_PAGINA
FILAS_MAX = 8
SEM_CORTE = {"baixos_em_contagem": False, "afetados_max": 40, "consumo_max": 10, "filas_max": None,
             "juntar_online": False, "urls_geral": 15, "urls_por_site": 3, "urls_sites": 5,
             "urls_destaques": 5, "avisos": []}
URLS_NO_CORTE = {"urls_geral": 15, "urls_por_site": 2, "urls_sites": 3, "urls_destaques": 3}


def _linhas(c, afetados):
    """Calibrado no PDF de uma rodada real: 26 linhas por página, e cada peso é o que o item ocupa."""
    filas = min(c.get("filas", 0), FILAS_MAX)
    consumo = min(c.get("consumo", 0), SEM_CORTE["consumo_max"])
    return (c.get("regras", 0) * (22 + afetados // 6) + 2 * c.get("sistemas", 0) + 60
            + 5 * filas + 2 * consumo + 6 * c.get("recomendacoes", 0) + 5 * c.get("pontos_de_falha", 0)
            + 2 * c.get("nos", 0) + 3 * c.get("aceites", 0) + c.get("pendencias", 0)
            + c.get("urls", 0))


def linhas_de_urls(dados, top=None):
    """Sem medida é uma frase. Com medida, o peso é o do bloco inteiro: três cartões por linha,
    cada um com título e três URLs, e as duas tabelas de destaque lado a lado."""
    if not dados.get("geral"):
        return 2
    limite = SEM_CORTE
    sites = min(len(dados.get("sites") or []), limite["urls_sites"])
    fileiras = (sites + 2) // 3
    return (5 + min(len(dados["geral"]), top or limite["urls_geral"]) + fileiras * (2 + limite["urls_por_site"])
            + 3 + min(len(dados.get("lentas") or []), limite["urls_destaques"]))


def _aviso_das_urls(c, r):
    sites = c.get("urls_sites", 0)
    if not sites:
        return []
    if r["urls_por_site"] < SEM_CORTE["urls_por_site"]:
        return [f"As URLs mostram as {r['urls_geral']} mais acessadas, {r['urls_por_site']} por site em até "
                f"{r['urls_sites']} sites e {r['urls_destaques']} destaques. O top 50 por site está no report.json."]
    if sites > r["urls_sites"]:
        return [f"As URLs mostram {r['urls_sites']} de {sites} sites. O top 50 por site está no report.json."]
    return []


def _aviso_do_consumo(c, maximo):
    total = c.get("consumo", 0)
    return [f"O consumo mostra só os {maximo} maiores de {total}."] if total > maximo else []


def _aviso_das_filas(c):
    total = c.get("filas", 0)
    if total <= FILAS_MAX:
        return []
    return [f"As filas mostram {FILAS_MAX} de {total}: paradas e lentas primeiro, depois as de maior volume. "
            "O completo está no report.json."]


def cortes(c):
    top = {"urls_geral": c["top"]} if c.get("top") else {}
    r = dict(SEM_CORTE, avisos=[], filas_max=FILAS_MAX, **top)
    if _linhas(c, 40) <= ORCAMENTO and c.get("achados", 0) <= 60:
        r["avisos"] = _aviso_das_filas(c) + _aviso_do_consumo(c, r["consumo_max"]) + _aviso_das_urls(c, r)
        return r
    r.update(baixos_em_contagem=True, afetados_max=8, consumo_max=4, **{**URLS_NO_CORTE, **top})
    r["avisos"] = ["Achados de baixa gravidade aparecem só em contagem.",
                   "A lista de afetados mostra os 8 primeiros; o completo está no report.json.",
                   *_aviso_das_filas(c), *_aviso_do_consumo(c, r["consumo_max"]), *_aviso_das_urls(c, r)]
    if c.get("sistemas", 0) > 12:
        r["juntar_online"] = True
        r["avisos"].append("Sistemas online foram agrupados em uma linha.")
    if 3 * c.get("aceites", 0) + c.get("pendencias", 0) > ORCAMENTO / 2:
        r["avisos"].append("O limite de 20 páginas foi ultrapassado para manter riscos aceitos e pendências.")
    return r
