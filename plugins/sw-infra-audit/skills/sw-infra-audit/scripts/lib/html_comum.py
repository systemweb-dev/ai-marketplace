import html


def _e(x):
    return html.escape("" if x is None else str(x), quote=True)


def nao_medido(motivo):
    return f'<p class="bl-nm"><b>Não medido.</b> {_e(motivo)}</p>'


def painel(titulo, resumo, corpo, cheio=False):
    classe = "bl-pn bl-cheio" if cheio else "bl-pn"
    return (f'<section class="{classe}"><header><h3>{_e(titulo)}</h3>'
            f'<span>{_e(resumo)}</span></header>{corpo}</section>')


SEM_DADO = '<span class="bl-sd">sem dado</span>'


def medido(valor, formato=str):
    """Valor pronto para o HTML; ausência é "sem dado", nunca um 0 que ninguém mediu."""
    return SEM_DADO if valor is None else _e(formato(valor))


def inteiro(n):
    return f"{round(n):,}".replace(",", ".")


def plural(n, singular, varios):
    return f"{inteiro(n)} {singular if n == 1 else varios}"


def _curto(n):
    return f"{n:.1f}".replace(".", ",").removesuffix(",0")


def humano(n):
    """Sobe de degrau pelo número JÁ ARREDONDADO: 999.999 daria "1000 mil" no degrau de baixo."""
    base, sufixo = 1, ""
    for limite, proximo in ((1e3, "mil"), (1e6, "mi"), (1e9, "bi")):
        if round(abs(n) / base, 1 if sufixo else 0) < 1000:
            break
        base, sufixo = limite, proximo
    return f"{_curto(n / base)} {sufixo}" if sufixo else inteiro(n)


def tamanho(n):
    for limite, sufixo in ((1024 ** 3, "GB"), (1024 ** 2, "MB"), (1024, "KB")):
        if abs(n) >= limite:
            return f"{_curto(n / limite)} {sufixo}"
    return f"{inteiro(n)} B"


def percentual(n):
    return f"{round(n)}%"
