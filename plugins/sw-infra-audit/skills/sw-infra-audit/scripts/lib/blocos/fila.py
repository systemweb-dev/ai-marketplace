import math

from lib.blocos import bloco
from lib.html_comum import _e, inteiro, medido, nao_medido, painel

ORDEM = {"Parada": 0, "Lenta": 1, "Em trânsito": 1, "Com consumidor": 2, "Fluindo": 2, "Sem dado": 3, "Vazia": 4,
         "Ociosa": 4}
PLURAL = {"Parada": "paradas", "Lenta": "lentas", "Fluindo": "fluindo", "Sem dado": "sem dado",
          "Ociosa": "ociosas", "Com consumidor": "com consumidor", "Vazia": "vazias",
          "Em trânsito": "em trânsito"}
URGENCIA = {"Parada": 0, "Lenta": 1}


def _ociosa(f):
    """A API não traz taxa de fila sem movimento. Só vale quando a fonte mediu o ritmo e não há
    mensagem nem em trânsito: zero prontas com 80 mil sem confirmação é fila travada."""
    return (f.get("prontas") == 0 and not f.get("nao_confirmadas")
            and not f.get("ritmo_nao_medido")
            and f.get("entrada") is None and f.get("saida") is None)


def _estado(f):
    if f.get("prontas") and f.get("consumidores") == 0:
        return "crit", "Parada"
    if _ociosa(f):
        return "neutro", "Ociosa"
    # Sem ritmo, a contagem ainda diz o estado: quem tem consumidor e quem está vazia são fatos
    # medidos, e chamá-las de "sem dado" esconderia 61 de 67 filas numa rodada real.
    if f.get("ritmo_nao_medido") and f.get("consumidores") is not None:
        if not f.get("prontas") and not f.get("nao_confirmadas"):
            return "neutro", "Vazia"
        if not f.get("prontas"):
            return "warn", "Em trânsito"
        if f.get("consumidores"):
            return "ok", "Com consumidor"
    if None in (f.get("consumidores"), f.get("entrada"), f.get("saida")):
        return "warn", "Sem dado"
    return ("warn", "Lenta") if f["entrada"] > f["saida"] else ("ok", "Fluindo")


def _saldo(f):
    if None in (f.get("entrada"), f.get("saida")):
        return None
    return f["entrada"] - f["saida"]


def _por_minuto(n):
    return f"{inteiro(n)}/min"


def _com_sinal(n):
    return f"+{inteiro(n)}/min" if n > 0 else f"−{inteiro(-n)}/min" if n < 0 else "0/min"


def _frase(rotulo, saldo):
    if rotulo == "Ociosa":
        return "Sem movimento"
    if saldo is None:
        return "Ritmo não medido"
    if rotulo == "Parada":
        return "Crescendo sem parar" if saldo > 0 else "Sem consumidor"
    return {"Lenta": "Crescendo devagar", "Fluindo": "Sob controle"}.get(rotulo, "Consumidores não medidos")


def _consumidores(n):
    if n is None:
        return f"Consumidores: {medido(n)}"
    return f"{inteiro(n)} {'consumidor' if n == 1 else 'consumidores'}"


def _largura(prontas, maior):
    """Raiz quadrada: 86 ao lado de 18 mil ainda se enxerga, e a maior fila ocupa o tubo todo."""
    if not prontas or not maior:
        return 0
    return max(2, round(100 * math.sqrt(prontas / maior)))


def _resumo(filas, separador=" · "):
    contagem = {}
    for f in filas:
        rotulo = _estado(f)[1]
        contagem[rotulo] = contagem.get(rotulo, 0) + 1
    partes = []
    for rotulo in sorted(contagem, key=ORDEM.get):
        n = contagem[rotulo]
        partes.append(f"{n} {rotulo.lower() if n == 1 else PLURAL[rotulo]}")
    return separador.join(partes)


def _linha(f, maior):
    tom, rotulo = _estado(f)
    saldo = _saldo(f)
    largura = _largura(f.get("prontas"), maior)
    tubo = (f'<div class="bl-qt"><span class="bl-qnum"><b>{medido(f.get("prontas"), inteiro)}</b> na fila</span>'
            f'<span class="bl-qbar"><i class="bl-fl-{tom}" style="width:{largura}%"></i></span></div>')
    if saldo is None and rotulo == "Parada":
        fluxo = f'<div class="bl-qf bl-qf-so">{tubo}</div>'
    else:
        fluxo = (f'<div class="bl-qf"><div class="bl-qv"><span>Entra</span><b>{medido(f.get("entrada"), _por_minuto)}</b></div>'
                 f'{tubo}<div class="bl-qv bl-d"><span>Sai</span><b>{medido(f.get("saida"), _por_minuto)}</b></div></div>')
    numero = "" if saldo is None else f'<b class="bl-c-{tom}">{_com_sinal(saldo)}</b>'
    return (
        f'<div class="bl-q bl-q-{tom}"><div class="bl-qn"><span class="bl-tag-{tom}">{rotulo}</span>'
        f'<b>{medido(f.get("nome"))}</b><span>{_consumidores(f.get("consumidores"))}</span></div>'
        f'{fluxo}<div class="bl-qs">{numero}<span>{_e(_frase(rotulo, saldo))}</span></div></div>')


def _chave(f):
    """Parada e lenta na frente; o resto por volume, com o acumulado antes do ritmo."""
    rotulo = _estado(f)[1]
    acumulado = (f.get("prontas") or 0) + (f.get("nao_confirmadas") or 0)
    ritmo = (f.get("entrada") or 0) + (f.get("saida") or 0)
    return (URGENCIA.get(rotulo, len(URGENCIA)), -acumulado, -ritmo, ORDEM[rotulo], str(f.get("nome") or ""))


def _demais(filas):
    if not filas:
        return ""
    return f'<p class="bl-qresto">Outras {inteiro(len(filas))}: {_e(_resumo(filas, ", "))}.</p>'


@bloco("fila")
def render(dados):
    filas = dados.get("filas")
    if not filas:
        return painel("Filas", "", nao_medido(dados.get("motivo", "sem fonte")), cheio=True)
    ordenadas = sorted(filas, key=_chave)
    limite = dados.get("filas_max")
    maior = max((f.get("prontas") or 0) for f in filas)
    corpo = "".join(_linha(f, maior) for f in ordenadas[:limite])
    return painel("Filas", _resumo(filas),
                  f'<div class="bl-qs-l">{corpo}</div>{_demais(ordenadas[limite:] if limite else [])}', cheio=True)
