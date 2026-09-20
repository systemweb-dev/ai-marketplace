"""Diff contra a execução anterior. A chave inclui o ALVO — sem ele, dois serviços de mesmo nome
em alvos diferentes viram o mesmo achado, e o histórico mente.
"""
import json
from pathlib import Path

# o v2 não tinha componentes; comparar com ele vale, desde que o relatório diga a ressalva.
# Recusar em silêncio faria a seção "desde a auditoria anterior" mentir por omissão.
ESQUEMAS_COMPARAVEIS = (2, 3)


def _relatorio(pasta):
    arquivo = Path(pasta) / "report.json"
    if not arquivo.exists():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError, OSError):
        return None                       # pasta-irmã com lixo não pode matar a auditoria
    if not isinstance(dados, dict):
        return None
    return dados if dados.get("schema_version") in ESQUEMAS_COMPARAVEIS else None


def pasta_anterior(pasta_atual):
    """A pasta irmã mais recente com report.json comparável (schema 2 ou 3).
    O layout v1 fica de fora."""
    atual = Path(pasta_atual).resolve()
    if not atual.parent.is_dir():
        return None          # primeira auditoria do projeto: a pasta ainda nem existe
    irmas = sorted(p for p in atual.parent.iterdir()
                   if p.is_dir() and p.name < atual.name and _relatorio(p) is not None)
    return irmas[-1] if irmas else None


def _chaves(relatorio, com_componente=True):
    """A chave inclui o COMPONENTE: duas filas com o mesmo problema no mesmo alvo são dois
    achados distintos, e o histórico precisa distinguir 'resolveu uma' de 'resolveu as duas'.

    `com_componente=False` é para comparar com um relatório v2, que não tinha essa dimensão:
    lá, o mesmo achado teria chave diferente dos dois lados e apareceria como resolvido E como
    novo ao mesmo tempo — a primeira rodada v3 de qualquer projeto existente anunciaria como
    resolvido o que continua no ar.
    """
    return {(a.get("nome"), (f.get("componente") or "") if com_componente else "",
             f.get("regra"), f.get("objeto") or "")
            for a in relatorio.get("alvos", []) for f in a.get("achados", [])}


def _formatar(chaves):
    """`alvo · componente · regra · objeto`, pulando o componente quando não há — o texto vai
    para o relatório e um separador vazio no meio só confunde quem lê."""
    return sorted(" · ".join(parte for parte in (alvo, componente, regra, objeto) if parte)
                  for alvo, componente, regra, objeto in chaves)


def comparar(anterior, atual, nome_anterior):
    mesmo_formato = anterior.get("schema_version") == atual.get("schema_version")
    antes = _chaves(anterior, com_componente=mesmo_formato)
    agora = _chaves(atual, com_componente=mesmo_formato)
    saida = {"vs": nome_anterior,
             "resolvidos": _formatar(antes - agora),
             "novos": _formatar(agora - antes)}
    if not mesmo_formato:
        saida["aviso"] = ("formato anterior: a comparação ignora o componente, que não existia "
                          "no relatório anterior")
    return saida
