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
CABECALHO_COMPONENTE = re.compile(r"^\s*\[\[\s*alvo\s*\.\s*componente\s*\]\]\s*(#.*)?$")
CHAVE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=")
CAMPOS_DE_LEITURA = ("leitura", "usuario", "senha_env", "backup_pasta", "backup_max_dias")
# Alfabeto fechado: o valor vai entre aspas no TOML, então aspas, `\`, espaço e quebra de linha não
# entram. Quem precisa de outro caractere edita o arquivo à mão.
TEXTO_GRAVAVEL = re.compile(r"[A-Za-z0-9._/@-]{1,255}")


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


def _intervalo_do_alvo(linhas, alvo):
    """`(início, fim)` do bloco `[[alvo]]` cujo `nome` é este; fim exclusivo, no próximo `[[alvo]]`."""
    inicios = [i for i, l in enumerate(linhas) if CABECALHO.match(l)]
    for k, inicio in enumerate(inicios):
        fim = inicios[k + 1] if k + 1 < len(inicios) else len(linhas)
        for j in range(inicio + 1, fim):
            if linhas[j].lstrip().startswith("["):
                break
            achado = NOME.match(linhas[j])
            if achado:
                if achado.group(1) == alvo:
                    return inicio, fim
                break
    raise GravacaoInvalida(f"alvo {alvo!r} não encontrado no arquivo")


def inserir(texto, alvo, componentes, data):
    for c in componentes:
        _validar(c)
    linhas = texto.splitlines(keepends=True)
    inicio, pos = _intervalo_do_alvo(linhas, alvo)
    while pos > inicio + 1 and (not linhas[pos - 1].strip() or linhas[pos - 1].lstrip().startswith("#")):
        pos -= 1
    antes = "".join(linhas[:pos])
    if antes and not antes.endswith("\n"):
        antes += "\n"
    blocos = "\n".join(_bloco(c, data) for c in componentes)
    return antes + "\n" + blocos + ("\n" if pos < len(linhas) else "") + "".join(linhas[pos:])


def _linha(chave, valor):
    if chave not in CAMPOS_DE_LEITURA:
        raise GravacaoInvalida(f"campo {chave!r} não é de leitura")
    if type(valor) is int:
        return f"{chave} = {valor}\n"
    if isinstance(valor, str) and TEXTO_GRAVAVEL.fullmatch(valor):
        return f'{chave} = "{valor}"\n'
    raise GravacaoInvalida(f"valor de {chave!r} fora do formato gravável")


def acrescentar_campos(texto, alvo, componente, campos):
    """Acrescenta `chave = valor` logo depois do `nome` do `[[alvo.componente]]` daquele componente,
    dentro daquele alvo. Só acrescenta: campo que o bloco já tem é recusado — quem troca valor é o
    dono, à mão. Toda linha que existia continua igual e na mesma ordem."""
    novas = "".join(_linha(chave, valor) for chave, valor in campos)
    linhas = texto.splitlines(keepends=True)
    inicio, fim = _intervalo_do_alvo(linhas, alvo)
    for de in [i for i in range(inicio, fim) if CABECALHO_COMPONENTE.match(linhas[i])]:
        ate = next((j for j in range(de + 1, fim) if linhas[j].lstrip().startswith("[")), fim)
        nome_em = next((j for j in range(de + 1, ate) if NOME.match(linhas[j])), None)
        if nome_em is None or NOME.match(linhas[nome_em]).group(1) != componente:
            continue
        existentes = {CHAVE.match(linhas[j]).group(1) for j in range(de + 1, ate)
                      if CHAVE.match(linhas[j])}
        repetidos = sorted(existentes & {chave for chave, _ in campos})
        if repetidos:
            raise GravacaoInvalida(f"o componente {componente!r} já tem {', '.join(repetidos)}; "
                                   f"para trocar, edite o alvos.toml à mão")
        linha_do_nome = linhas[nome_em] if linhas[nome_em].endswith("\n") else linhas[nome_em] + "\n"
        return "".join(linhas[:nome_em]) + linha_do_nome + novas + "".join(linhas[nome_em + 1:])
    raise GravacaoInvalida(f"componente {componente!r} não encontrado no alvo {alvo!r}")
