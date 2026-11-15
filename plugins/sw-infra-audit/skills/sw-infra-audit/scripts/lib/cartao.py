"""O cartão curto de um problema: o que é, onde e o primeiro passo de como resolver.

A remediação completa continua na seção Problemas, e o cartão aponta para ela pelo id `regra-<regra>`.
Problema nunca sai sem "O que fazer": sem ficha, o cartão manda para a seção Problemas.
"""
import re

from lib import remediacao
from lib.html_comum import _e
from lib.regras import esperada
from lib.rule_meta import meta

ROTULO = {"critical": "Crítico", "high": "Alto", "medium": "Médio", "low": "Baixo", "info": "Informativo"}
TOM = {"critical": "crit", "high": "crit", "medium": "warn"}


def cobrados(achados):
    return [a for a in achados if not a.get("esperada") and not esperada(a.get("regra"))]


def ancora(achado):
    partes = (achado.get("alvo"), achado.get("componente") or achado.get("alvo"), achado.get("regra"))
    return "p-" + re.sub(r"[^a-z0-9]+", "-", "-".join(str(p or "") for p in partes).lower()).strip("-")


def _inline(texto):
    """Escapa e só então traduz `código` e **negrito**: nada da ficha abre tag."""
    escapado = _e(texto)
    escapado = re.sub(r"`([^`]+)`", r"<code>\1</code>", escapado)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escapado)


def _titulo(achado):
    return (achado.get("como_resolver") or {}).get("titulo") or meta(achado.get("regra"))["label"]


def _onde(achado):
    """A máquina do host tem o nome do alvo: "banco-01 · banco-01" diria o mesmo duas vezes."""
    alvo, componente = achado.get("alvo"), achado.get("componente")
    return " · ".join(str(x) for x in dict.fromkeys((alvo, componente)) if x)


def _etiqueta(achado):
    sev = achado.get("severidade")
    tom = TOM.get(sev, "neutro")
    return (f'<span class="bl-tag-{tom}"><svg class="ic"><use href="#ic-achado"/></svg>'
            f'{_e(ROTULO.get(sev, sev))}</span>')


def cartao(achado):
    regra = achado.get("regra")
    ficha = achado.get("como_resolver") or remediacao.para(regra) or {}
    passo = remediacao.primeiro_passo(ficha.get("como_resolver"))
    fazer = _inline(passo) if passo else "Os passos estão na seção Problemas, mais abaixo."
    detalhe = f'<p class="fx-d">{_e(achado["detalhe"])}</p>' if achado.get("detalhe") else ""
    tom = TOM.get(achado.get("severidade"), "warn")
    return (f'<article class="fx {tom}" id="{ancora(achado)}">'
            f'<p class="fx-p">{_etiqueta(achado)}<span>{_e(_titulo(achado))}</span>'
            f'<span class="onde">{_e(_onde(achado))}</span></p>{detalhe}'
            f'<div class="fx-f"><svg class="ic fx-i"><use href="#ic-corrigir"/></svg>'
            f'<p><b>O que fazer</b>{fazer}</p></div>'
            f'<a class="fx-r" href="#regra-{_e(regra)}">ver todos os passos</a></article>')


def indice(achados):
    linhas = "".join(f'<li>{_etiqueta(a)}<a class="ix-p" href="#{ancora(a)}">{_e(_titulo(a))}</a>'
                     f'<span class="onde">{_e(_onde(a))}</span></li>' for a in achados)
    return f'<ol class="ix">{linhas}</ol>' if linhas else ""
