"""Diff contra a execução anterior. A chave inclui o ALVO — sem ele, dois serviços de mesmo nome
em alvos diferentes viram o mesmo achado, e o histórico mente.
"""
import json
from pathlib import Path


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
    return dados if dados.get("schema_version") == 2 else None


def pasta_anterior(pasta_atual):
    """A pasta irmã mais recente com report.json de schema 2. O layout v1 fica de fora."""
    atual = Path(pasta_atual).resolve()
    if not atual.parent.is_dir():
        return None          # primeira auditoria do projeto: a pasta ainda nem existe
    irmas = sorted(p for p in atual.parent.iterdir()
                   if p.is_dir() and p.name < atual.name and _relatorio(p) is not None)
    return irmas[-1] if irmas else None


def _chaves(relatorio):
    return {(a.get("nome"), f.get("regra"), f.get("objeto") or "")
            for a in relatorio.get("alvos", []) for f in a.get("achados", [])}


def _formatar(chaves):
    return sorted(f"{alvo} · {regra} · {objeto}" for alvo, regra, objeto in chaves)


def comparar(anterior, atual, nome_anterior):
    antes, agora = _chaves(anterior), _chaves(atual)
    return {"vs": nome_anterior,
            "resolvidos": _formatar(antes - agora),
            "novos": _formatar(agora - antes)}
