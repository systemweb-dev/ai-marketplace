"""Acrescenta `[[alvo.componente]]` a um alvos.toml escrito à mão — só acrescenta.

Sem parser que preserve comentário na stdlib, a inserção é por texto: acha o bloco `[[alvo]]` pelo
`nome = "..."` dele e insere antes do próximo `[[alvo]]`, recuando sobre linhas em branco e
comentários (que costumam ser do alvo seguinte). Toda linha que existia continua igual e na mesma
ordem. Quem chama relê o arquivo e restaura o `.bak` se algo não bater.
"""
import re

from lib.alvos import NOME_VALIDO, ORIGEM

CABECALHO = re.compile(r"^\s*\[\[\s*alvo\s*\]\]\s*(#.*)?$")
NOME = re.compile(r'^\s*nome\s*=\s*"([^"]*)"')
PRODUTO = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
PAPEL = re.compile(r"[a-z]{1,32}")


class GravacaoInvalida(Exception):
    """Gravação recusada antes de tocar no arquivo."""


def _validar(c):
    if not NOME_VALIDO.fullmatch(str(c.get("nome", ""))) or not ORIGEM.fullmatch(str(c.get("origem", ""))):
        raise GravacaoInvalida(f"componente com nome ou origem fora do formato: {c.get('nome')!r}")
    if c.get("produto") is not None and not PRODUTO.fullmatch(str(c["produto"])):
        raise GravacaoInvalida(f"produto fora do formato em {c['nome']!r}")
    if c.get("papel") is not None and not PAPEL.fullmatch(str(c["papel"])):
        raise GravacaoInvalida(f"papel fora do formato em {c['nome']!r}")
    if not all(type(p) is int and 1 <= p <= 65535 for p in c.get("portas", [])):
        raise GravacaoInvalida(f"portas fora do formato em {c['nome']!r}")


def _bloco(c, data):
    linhas = [f"# descoberto em {data}", "[[alvo.componente]]", f'nome = "{c["nome"]}"']
    if c.get("papel"):
        linhas.append(f'papel = "{c["papel"]}"')
    if c.get("produto"):
        linhas.append(f'produto = "{c["produto"]}"')
    linhas.append("portas = [" + ", ".join(str(p) for p in c.get("portas", [])) + "]")
    linhas.append(f'origem = "{c["origem"]}"')
    return "\n".join(linhas) + "\n"


def inserir(texto, alvo, componentes, data):
    for c in componentes:
        _validar(c)
    linhas = texto.splitlines(keepends=True)
    inicios = [i for i, l in enumerate(linhas) if CABECALHO.match(l)]
    intervalo = None
    for k, inicio in enumerate(inicios):
        fim = inicios[k + 1] if k + 1 < len(inicios) else len(linhas)
        for j in range(inicio + 1, fim):
            if linhas[j].lstrip().startswith("["):
                break
            achado = NOME.match(linhas[j])
            if achado:
                if achado.group(1) == alvo:
                    intervalo = (inicio, fim)
                break
    if intervalo is None:
        raise GravacaoInvalida(f"alvo {alvo!r} não encontrado no arquivo")
    inicio, pos = intervalo
    while pos > inicio + 1 and (not linhas[pos - 1].strip() or linhas[pos - 1].lstrip().startswith("#")):
        pos -= 1
    antes = "".join(linhas[:pos])
    if antes and not antes.endswith("\n"):
        antes += "\n"
    blocos = "\n".join(_bloco(c, data) for c in componentes)
    return antes + "\n" + blocos + ("\n" if pos < len(linhas) else "") + "".join(linhas[pos:])
