from lib.blocos import bloco
from lib.html_comum import _curto, medido, nao_medido, painel, tamanho


def _cores(cpu):
    """`app.cpu` é `rate(...) * 100` no cAdvisor: 100% é um núcleo inteiro, 250% são dois e meio."""
    nucleos = cpu / 100
    if 0 < nucleos < 0.05:
        return "< 0,1 cores"
    texto = _curto(nucleos)
    return f"{texto} {'core' if texto == '1' else 'cores'}"


def _linha(posicao, i, maior):
    cpu = i.get("cpu")
    largura = round(100 * cpu / maior) if cpu is not None and maior else 0
    return (f'<div class="bl-rk"><span class="bl-pos">{posicao}</span><b>{medido(i.get("nome"))}</b>'
            f'<span class="bl-bar"><i class="bl-fl-acc" style="width:{largura}%"></i></span>'
            f'<span class="bl-v">{medido(cpu, _cores)}</span>'
            f'<span class="bl-v">{medido(i.get("memoria"), tamanho)}</span></div>')


@bloco("consumo")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return painel("Maiores consumidores", "", nao_medido(dados.get("motivo", "sem fonte")))
    ordem = sorted(itens, key=lambda i: (i.get("cpu") is None, -(i.get("cpu") or 0), str(i.get("nome") or "")))
    maior = max((i.get("cpu") or 0) for i in ordem)
    corpo = "".join(_linha(n, i, maior) for n, i in enumerate(ordem, 1))
    return painel("Maiores consumidores", f"Top {len(ordem)} por CPU", corpo)
