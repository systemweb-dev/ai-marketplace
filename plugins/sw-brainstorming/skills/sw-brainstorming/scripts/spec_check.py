#!/usr/bin/env python3
"""Lint do spec: o que o modelo declara ter conferido e não conferiu.

Irmão do `plan_check.py`. Um spec coerente pode citar arquivo que não existe, e o revisor que só
lê o documento não tem como notar. Aqui a evidência é confrontada com o sistema de arquivos.

O que ele NÃO faz: julgar se o design é bom, nem provar que `[visto: x.py:12]` diz o que o spec
afirma. Ele só garante que o lugar citado existe; quem lê o conteúdo é o revisor.

Uso:
  spec_check.py docs/specs/<slug>/spec.md [--projeto .]

Saída: 0 = limpo (pode haver avisos) · 2 = achados · 1 = não consegui ler o spec.
"""
import argparse
import os
import re
import sys
import unicodedata

SECOES = [
    ("objetivo", ("objetivo",)),
    ("não-objetivos", ("nao-objetivo", "nao objetivo", "fora de escopo")),
    ("decisões", ("decis",)),
    ("suposições", ("suposic",)),
]
# Sigla só em maiúscula: em português, "todo o repositório" não é pendência nenhuma.
PLACEHOLDERS = [
    (r"\bTODO\b", "TODO"),
    (r"\bTBD\b", "TBD"),
    (r"\bFIXME\b", "FIXME"),
    (r"\b[Aa] definir\b", "a definir"),
    (r"a skill sw-brainstorming preenche", "esqueleto do dossiê sem preencher"),
]
VISTO = re.compile(r"\[visto:\s*([^\]]+)\]", re.I)
DOC = re.compile(r"\[doc:\s*([^\]]*)\]", re.I)
SUPOSICAO = re.compile(r"\[suposi[cç][aã]o\]", re.I)
CITACAO = re.compile(r"`([^`\s]+/[^`\s]+\.[A-Za-z0-9]+)(?::\d+)?`")
INLINE = re.compile(r"`[^`]*`")
TITULO = re.compile(r"^#{1,6}\s+(.+?)\s*$")
BLOCO = re.compile(r"^\s*```")


def _sem_acento(texto):
    base = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in base if not unicodedata.combining(c)).lower()


def _achado(regra, linha, trecho, dica):
    return {"regra": regra, "linha": linha, "trecho": trecho.strip()[:120], "dica": dica}


def _fora_de_bloco(linhas):
    """As linhas numeradas que não estão dentro de um bloco de código."""
    dentro, saida = False, []
    for numero, linha in enumerate(linhas, 1):
        if BLOCO.match(linha):
            dentro = not dentro
        elif not dentro:
            saida.append((numero, linha))
    return saida


def _resolver(citado, spec_dir, projeto):
    """O caminho no disco. `referencias/` é relativo ao dossiê, o resto ao projeto."""
    if citado.startswith("referencias/"):
        return os.path.join(spec_dir, citado)
    return os.path.join(projeto, citado)


def _evidencia(numero, linha, spec_dir, projeto):
    achados = []
    for grupo in VISTO.findall(linha):
        for item in grupo.split(","):
            item = item.strip()
            caminho, _, resto = item.partition(":")
            alvo = _resolver(caminho, spec_dir, projeto)
            if not os.path.isfile(alvo):
                achados.append(_achado("evidência inexistente", numero, item,
                                       "o arquivo citado não existe: leia antes de afirmar"))
                continue
            if resto.isdigit():
                with open(alvo, encoding="utf-8", errors="replace") as f:
                    total = sum(1 for _ in f)
                if int(resto) > total or int(resto) < 1:
                    achados.append(_achado("linha inexistente", numero, item,
                                           f"o arquivo tem {total} linha(s)"))
    for conteudo in DOC.findall(linha):
        if not re.search(r"https?://|referencias/", conteudo):
            achados.append(_achado("documentação sem fonte", numero, conteudo or "[doc:]",
                                   "cite a URL ou o arquivo em referencias/"))
    return achados


def _tabela_de_suposicoes(util):
    """As linhas da tabela sob o título de suposições, sem cabeçalho e separador."""
    dentro, tabela = False, []
    for numero, linha in util:
        titulo = TITULO.match(linha)
        if titulo:
            dentro = "suposic" in _sem_acento(titulo.group(1))
        elif dentro and linha.strip().startswith("|"):
            celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
            tabela.append((numero, celulas))
    return tabela


def _suposicoes(util):
    tabela = _tabela_de_suposicoes(util)
    linhas = tabela[2:] if len(tabela) >= 2 else []
    achados = []
    if tabela:
        cabecalho = [_sem_acento(c) for c in tabela[0][1]]
        coluna = next((i for i, c in enumerate(cabecalho) if "validar" in c), None)
        if coluna is None:
            achados.append(_achado("suposições sem 'Como validar'", tabela[0][0],
                                   " | ".join(tabela[0][1]), "a tabela precisa dessa coluna"))
        else:
            for numero, celulas in linhas:
                valor = celulas[coluna] if coluna < len(celulas) else ""
                if not valor.strip(" -—"):
                    achados.append(_achado("suposição sem validação", numero, celulas[0],
                                           "diga como descobrir se ela é falsa"))
    marcadas = [(n, l) for n, l in util if SUPOSICAO.search(l)]
    if marcadas and not linhas:
        numero, linha = marcadas[0]
        achados.append(_achado("suposição fora da tabela", numero, linha,
                               "leve a suposição para a tabela de Suposições"))
    return achados


def checar(caminho, projeto=None):
    """Devolve (achados, avisos). Achado reprova; aviso só pede um olhar."""
    with open(caminho, encoding="utf-8") as f:
        linhas = f.read().splitlines()
    spec_dir = os.path.dirname(os.path.abspath(caminho))
    projeto = projeto or os.getcwd()
    util = _fora_de_bloco(linhas)

    titulos = [_sem_acento(m.group(1)) for _, l in util if (m := TITULO.match(l))]
    achados = [_achado("seção faltando", 0, nome, "acrescente a seção; em spec pequeno, uma linha basta")
               for nome, chaves in SECOES
               if not any(c in t for c in chaves for t in titulos)]
    avisos = []
    for numero, linha in util:
        prosa = INLINE.sub("", linha)
        for padrao, nome in PLACEHOLDERS:
            if re.search(padrao, prosa):
                achados.append(_achado("placeholder", numero, linha, f"resolva '{nome}'"))
        achados += _evidencia(numero, linha, spec_dir, projeto)
        semente = VISTO.sub("", linha)
        for citado in CITACAO.findall(semente):
            if citado.startswith(("http://", "https://")) or any(c in citado for c in "*<>{}"):
                continue
            existe = os.path.exists(_resolver(citado, spec_dir, projeto))
            if not existe and citado.startswith("referencias/"):
                achados.append(_achado("referência faltando", numero, citado,
                                       "guarde o arquivo em referencias/ ou remova a citação"))
            elif not existe:
                avisos.append(_achado("caminho não encontrado", numero, citado,
                                      "se for arquivo novo, ignore; senão, corrija"))
    return achados + _suposicoes(util), avisos


def _imprimir(itens):
    for a in itens:
        print(f"  linha {a['linha']:>4}  {a['regra']}")
        if a["trecho"]:
            print(f"              {a['trecho']}")
        print(f"              → {a['dica']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--projeto", help="raiz do projeto, para conferir a evidência citada")
    args = ap.parse_args()
    try:
        achados, avisos = checar(args.spec, args.projeto)
    except OSError as erro:
        sys.exit(f"ERRO: não consegui ler o spec: {erro}")
    if avisos:
        print(f"{len(avisos)} aviso(s) em {args.spec}:\n")
        _imprimir(avisos)
    if not achados:
        print(f"✓ {args.spec}: nada a corrigir.")
        return
    print(f"{len(achados)} achado(s) em {args.spec}:\n")
    _imprimir(achados)
    sys.exit(2)


if __name__ == "__main__":
    main()
