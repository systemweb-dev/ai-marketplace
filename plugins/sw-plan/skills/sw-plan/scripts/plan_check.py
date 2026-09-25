#!/usr/bin/env python3
"""Lint do plano de implementação: o que o olho deixa passar e só dói na execução.

Por que um script e não só o self-review: "confira se não ficou placeholder" é justamente o
tipo de checagem que o modelo declara ter feito e não fez. Aqui é regex e sistema de arquivos,
não boa vontade — mesma ideia do `dossie.py`, que existe para o índice nunca mentir.

O que ele NÃO faz: julgar se o plano é bom. Ordem por risco, cobertura do spec e qualidade dos
testes continuam sendo trabalho do self-review e do revisor. Este script pega o mecânico.

Uso:
  plan_check.py docs/specs/<slug>/plan.md [--projeto .]

Saída: 0 = limpo · 2 = achados · 1 = não consegui ler o plano.
"""
import argparse
import os
import re
import sys

# Cada padrão é um jeito real de o plano empurrar a decisão para quem executa.
PLACEHOLDERS = [
    (r"\bTODO\b", "TODO"),
    (r"\bTBD\b", "TBD"),
    (r"\bFIXME\b", "FIXME"),
    (r"implementar (?:depois|mais tarde)", "implementar depois"),
    (r"preencher (?:os )?detalhes", "preencher detalhes"),
    (r"adicionar valida(?:ção|cao)\b", "adicionar validação"),
    (r"tratar os erros adequadamente", "tratar os erros adequadamente"),
    (r"cobrir os casos[- ]limite", "cobrir os casos-limite"),
    (r"escreva os testes do que est[áa] acima", "escreva os testes do que está acima"),
    (r"igual (?:à|a) task \d+", "igual à Task N"),
    (r"similar to task \d+", "similar to Task N"),
]
# Step que muda código precisa mostrar o código. Estes verbos denunciam a intenção.
VERBOS_DE_CODIGO = re.compile(
    r"\b(escrev\w*|implement\w*|criar?|cria|adicion\w*|ligar?|liga|alter\w*|ajust\w*|"
    r"refator\w*|remov\w*|apagar?)\b", re.I)
# Step que só roda comando não precisa de bloco: a linha `Rode:` já é a instrução.
STEP_DE_COMANDO = re.compile(r"^\s*(rode|run|execute)\s*:", re.I | re.M)
CHECKBOX_OK = re.compile(r"^- \[[ x]\] ")
CHECKBOX_TORTO = re.compile(r"^\s*[-*]\s*\[\s*[^ x\]]?\s*\]")
TASK = re.compile(r"^#{2,4}\s*Task\s+(\d+)\s*:", re.I)
STEP = re.compile(r"^\s*[-*]\s*\[[ x]?\]?\s*\*\*\s*Step\b", re.I)
ARQUIVO = re.compile(r"^\s*[-*]\s*(Criar|Create|Alterar|Modify|Teste|Test)\s*:\s*`?([^`\s:]+)", re.I)
DEPENDE = re.compile(r"^\s*\*\*Depende de:?\*\*\s*(.+)$", re.I | re.M)
BLOCO = re.compile(r"^\s*```")


def _achado(regra, linha, trecho, dica):
    return {"regra": regra, "linha": linha, "trecho": trecho.strip()[:120], "dica": dica}


def _blocos_de_codigo(linhas):
    """Índices das linhas que estão DENTRO de um bloco de código (``` … ```)."""
    dentro, marcadas = False, set()
    for i, linha in enumerate(linhas):
        if BLOCO.match(linha):
            dentro = not dentro
            marcadas.add(i)
            continue
        if dentro:
            marcadas.add(i)
    return marcadas


def _secoes_de_step(linhas, inicio, fim):
    """Corta o pedaço da task em steps: [(linha_do_step, texto_do_step)]."""
    pontos = [i for i in range(inicio, fim) if STEP.match(linhas[i])]
    out = []
    for n, i in enumerate(pontos):
        ate = pontos[n + 1] if n + 1 < len(pontos) else fim
        out.append((i, "\n".join(linhas[i:ate])))
    return out


def checar(caminho: str, projeto: str | None = None) -> list:
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    linhas = texto.split("\n")
    no_codigo = _blocos_de_codigo(linhas)
    achados = []

    if not re.search(r"\[spec\.md\]\(spec\.md\)|Sem spec", texto, re.I):
        achados.append(_achado("sem-spec", 1, linhas[0] if linhas else "",
                               "o cabeçalho precisa do link [spec.md](spec.md) — ou dizer 'Sem spec: …'"))

    inicios = [i for i, l in enumerate(linhas) if TASK.match(l)]
    if not inicios:
        achados.append(_achado("sem-task", 1, "", "um plano sem `### Task N:` não é executável"))
        return achados

    numeros = {int(TASK.match(linhas[i]).group(1)) for i in inicios}
    for n, inicio in enumerate(inicios):
        fim = inicios[n + 1] if n + 1 < len(inicios) else len(linhas)
        corpo = "\n".join(linhas[inicio:fim])
        titulo = linhas[inicio].strip()

        arquivos = [(i, ARQUIVO.match(linhas[i])) for i in range(inicio, fim) if ARQUIVO.match(linhas[i])]
        if not arquivos:
            achados.append(_achado("task-sem-arquivos", inicio + 1, titulo,
                                   "diga quais arquivos criar, alterar e testar — caminho exato"))

        if projeto:
            for i, m in arquivos:
                acao, caminho_arq = m.group(1).lower(), m.group(2)
                if acao not in ("alterar", "modify"):
                    continue                       # "Criar" não existe ainda, é o ponto
                if not os.path.exists(os.path.join(projeto, caminho_arq)):
                    achados.append(_achado("arquivo-inexistente", i + 1, linhas[i],
                                           f"'{caminho_arq}' não existe no projeto: confira o caminho"))

        dep = DEPENDE.search(corpo)
        if dep:
            for citada in re.findall(r"task\s+(\d+)", dep.group(1), re.I):
                if int(citada) not in numeros:
                    achados.append(_achado("dependencia-inexistente", inicio + 1, dep.group(0).strip(),
                                           f"a Task {citada} não existe neste plano"))

        for i_step, texto_step in _secoes_de_step(linhas, inicio, fim):
            if not CHECKBOX_OK.match(linhas[i_step].lstrip()):
                achados.append(_achado("checkbox-torto", i_step + 1, linhas[i_step],
                                       "o step precisa começar com `- [ ] ` para dar para acompanhar"))
            tem_bloco = "```" in texto_step
            eh_comando = bool(STEP_DE_COMANDO.search(texto_step))
            if VERBOS_DE_CODIGO.search(linhas[i_step]) and not tem_bloco and not eh_comando:
                achados.append(_achado("step-sem-codigo", i_step + 1, linhas[i_step],
                                       "step que mexe em código mostra o código, não descreve"))

    for i, linha in enumerate(linhas):
        if i in no_codigo:
            continue                                # exemplo dentro de bloco não é placeholder
        for padrao, nome in PLACEHOLDERS:
            if re.search(padrao, linha, re.I):
                achados.append(_achado("placeholder", i + 1, linha,
                                       f"'{nome}' empurra a decisão para quem executa: escreva o conteúdo"))
                break

    achados.sort(key=lambda a: (a["linha"], a["regra"]))
    return achados


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plano")
    ap.add_argument("--projeto", help="raiz do projeto, para conferir os arquivos de 'Alterar'")
    args = ap.parse_args()
    try:
        achados = checar(args.plano, args.projeto)
    except OSError as erro:
        sys.exit(f"ERRO: não consegui ler o plano: {erro}")
    if not achados:
        print(f"✓ {args.plano}: nada a corrigir.")
        return
    print(f"{len(achados)} achado(s) em {args.plano}:\n")
    for a in achados:
        print(f"  linha {a['linha']:>4}  {a['regra']}")
        if a["trecho"]:
            print(f"              {a['trecho']}")
        print(f"              → {a['dica']}")
    sys.exit(2)


if __name__ == "__main__":
    main()
