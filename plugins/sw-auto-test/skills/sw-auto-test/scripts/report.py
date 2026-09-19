#!/usr/bin/env python3
"""Valida o `achados.json` contra o `fatos.json` e escreve o `test-health-report.md`."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from lib import gitinfo, pastas

EXIT_OK, EXIT_AMBIENTE, EXIT_RECUSA = 0, 2, 3

DIMENSOES = ("confiabilidade", "isolamento", "cobertura", "legibilidade", "velocidade")
CONFIANCAS = ("alta", "media", "baixa")


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def raiz_do_escopo(fatos) -> Path:
    """Caminhos do inventário são relativos ao ESCOPO, não ao topo do repositório."""
    return (Path(fatos["repo"]["toplevel"]) / fatos["escopo"]["raiz"]).resolve()


def _linhas_do_arquivo(raiz, relativo):
    caminho = Path(raiz) / relativo
    if not caminho.is_file():
        return None
    try:
        return len(caminho.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return None


def validar(fatos: dict, achados: dict) -> list:
    """Devolve a lista de problemas. Lista vazia = pode gravar."""
    problemas = []
    lista = achados.get("achados")
    if not isinstance(lista, list):
        return ["achados.json: 'achados' precisa ser uma lista"]
    nao_e_problema = achados.get("nao_e_problema", [])
    if not isinstance(nao_e_problema, list):
        problemas.append("achados.json: 'nao_e_problema' precisa ser uma lista")
        nao_e_problema = []

    conhecidos = {a["caminho"] for a in fatos["inventario"]["lista"]}
    sinais_por_caminho = {}
    for sinal in fatos.get("sinais", []):
        sinais_por_caminho.setdefault(sinal["caminho"], set()).add(sinal["regra"])

    vistos = set()
    for posicao, item in enumerate(lista, start=1):
        onde = f"achados[{posicao}]"
        if not isinstance(item, dict):
            problemas.append(f"{onde}: precisa ser um objeto")
            continue
        dimensao, confianca = item.get("dimensao"), item.get("confianca")
        caminho, linha, regra = item.get("caminho"), item.get("linha"), item.get("regra")
        if not isinstance(regra, str) or not regra.strip() or regra != " ".join(regra.split()):
            # a regra entra no markdown: com quebra de linha ela criaria seção ou tabela no relatório
            problemas.append(f"{onde}: regra precisa ser um texto curto, numa linha só")
        if dimensao not in DIMENSOES:
            problemas.append(f"{onde}: dimensao {dimensao!r} não é uma das {list(DIMENSOES)}")
        if confianca not in CONFIANCAS:
            problemas.append(f"{onde}: confianca {confianca!r} não é alta/media/baixa")
        if not isinstance(caminho, str):
            problemas.append(f"{onde}: caminho precisa ser texto")
        elif caminho not in conhecidos:
            problemas.append(f"{onde}: caminho {caminho!r} não está no inventário dos fatos")
        # bool é int em Python: `linha=True` passaria por inteiro positivo
        if not isinstance(linha, int) or isinstance(linha, bool) or linha <= 0:
            problemas.append(f"{onde}: linha precisa ser inteiro positivo")
        elif isinstance(caminho, str) and caminho in conhecidos:
            total = _linhas_do_arquivo(raiz_do_escopo(fatos), caminho)
            if total is not None and linha > total:
                problemas.append(f"{onde}: linha {linha} não existe em {caminho} ({total} linhas)")
        if not _texto(item.get("problema")):
            problemas.append(f"{onde}: problema vazio")
        if not _texto(item.get("correcao")):
            problemas.append(f"{onde}: correcao vazia")
        if confianca == "alta":
            sinal = item.get("sinal")
            if sinal not in sinais_por_caminho.get(caminho, set()):
                problemas.append(f"{onde}: confiança alta sem lastro — nenhum sinal {sinal!r} "
                                 f"em {caminho} nos fatos")
        chave = (str(caminho), str(linha), str(regra))
        if chave in vistos:
            problemas.append(f"{onde}: achado repetido para {caminho}:{linha}")
        vistos.add(chave)

    for posicao, item in enumerate(nao_e_problema, start=1):
        if not isinstance(item, dict) or not _texto(item.get("caminho")):
            problemas.append(f"nao_e_problema[{posicao}]: precisa de caminho")
            continue
        if item["caminho"] not in conhecidos:
            problemas.append(f"nao_e_problema[{posicao}]: caminho {item['caminho']!r} "
                             "não está no inventário dos fatos")
        if not _texto(item.get("motivo")):
            problemas.append(f"nao_e_problema[{posicao}]: motivo vazio")
    return problemas


ROTULOS = {"confiabilidade": "Confiabilidade", "isolamento": "Isolamento", "cobertura": "Cobertura",
           "legibilidade": "Legibilidade", "velocidade": "Velocidade"}
LINHA = "/test-health-report.md"


def uma_linha(valor) -> str:
    """Texto do agente nunca cria seção: qualquer espaço em branco vira um espaço só."""
    return " ".join(_texto(valor).split())


def notas(fatos: dict, achados: list) -> dict:
    """Nota por dimensão, calculada dos fatos. Sem fato que sustente → ⚪ sem dados.

    A base de cada nota diz DE ONDE ela veio: "sem dados" por execução recusada é diferente de
    "sem dados" por cobertura não pedida, e timeout não é falta de autorização.
    """
    execucao, cobertura, inventario = fatos["execucao"], fatos["cobertura"], fatos["inventario"]
    varridos = f"nenhum sinal em {inventario['arquivos']} arquivo(s) varrido(s)"
    saida = {}
    for dimensao in DIMENSOES:
        desta = [a for a in achados if a.get("dimensao") == dimensao]
        altas = [a for a in desta if a.get("confianca") == "alta"]

        if dimensao == "cobertura":
            por_arquivo = cobertura.get("por_arquivo") or []
            if not cobertura.get("disponivel") or not por_arquivo:
                motivo = ("a execução não foi autorizada" if not execucao.get("rodou")
                          else "a execução não pediu cobertura")
                saida[dimensao] = ("⚪ sem dados", motivo)
                continue
            pior = min(int(a.get("linhas_pct") or 0) for a in por_arquivo)
            if altas or pior < 20:
                saida[dimensao] = ("🔴 grave", f"arquivo com {pior}% das linhas cobertas")
            elif pior < 60:
                saida[dimensao] = ("🟡 atenção", f"arquivo com {pior}% das linhas cobertas")
            else:
                saida[dimensao] = ("🟢 ok", f"pior arquivo com {pior}% das linhas cobertas")
            continue

        if dimensao == "velocidade":
            if not execucao.get("rodou"):
                saida[dimensao] = ("⚪ sem dados", "a execução não foi autorizada")
            elif execucao.get("timeout"):
                saida[dimensao] = ("🔴 grave", "a suíte estourou o tempo limite")
            elif altas:
                saida[dimensao] = ("🔴 grave", f"{len(altas)} achado(s) de confiança alta")
            elif execucao.get("lentos"):
                saida[dimensao] = ("🟡 atenção",
                                   f"{len(execucao['lentos'])} teste(s) acima do limite do tipo")
            else:
                saida[dimensao] = ("🟢 ok", f"suíte em {execucao.get('duracao_faixa') or 'n/a'}")
            continue

        if dimensao == "confiabilidade" and execucao.get("verde") is False:
            extra = f" e {len(altas)} achado(s) de confiança alta" if altas else ""
            saida[dimensao] = ("🔴 grave",
                               f"{execucao.get('falhou', 0)} teste(s) falhando na suíte{extra}")
        elif altas:
            saida[dimensao] = ("🔴 grave", f"{len(altas)} achado(s) de confiança alta")
        elif desta:
            saida[dimensao] = ("🟡 atenção", f"{len(desta)} achado(s) a revisar")
        else:
            saida[dimensao] = ("🟢 ok", varridos)
    return saida


def montar(fatos: dict, achados: dict, data: str) -> str:
    lista = [a for a in achados.get("achados", []) if isinstance(a, dict)]
    inv, execucao = fatos["inventario"], fatos["execucao"]
    linhas = [f"# Saúde dos testes — {fatos['escopo']['raiz']}", ""]
    runners = ", ".join(s["runner"] for s in fatos["stacks"]) or "nenhum runner reconhecido"
    resumo_suites = " · ".join(f"{suite} {qtd}" for suite, qtd in sorted(inv["por_suite"].items()))
    linhas += [f"{data} · {runners} · {inv['arquivos']} arquivo(s) · {inv['testes']} teste(s)"
               f"{' · ' + resumo_suites if resumo_suites else ''}", ""]

    linhas += ["## Resumo", ""]
    if execucao.get("rodou"):
        estado = "verde" if execucao.get("verde") else ("sem leitura" if execucao.get("verde") is None
                                                        else "VERMELHA")
        linhas.append(f"Suíte {estado}: {execucao.get('passou', 0)} passaram, "
                      f"{execucao.get('falhou', 0)} falharam, {execucao.get('pulado', 0)} pulados, "
                      f"duração {execucao.get('duracao_faixa') or 'n/a'}.")
    else:
        linhas.append("A suíte não foi executada: cobertura e velocidade ficam sem nota.")
    linhas += [f"{len(lista)} achado(s) em {len({a.get('caminho') for a in lista})} arquivo(s).", ""]

    linhas += ["## Notas por dimensão", "", "| Dimensão | Nota | Base |", "|---|---|---|"]
    for dimensao, (nota, base) in notas(fatos, lista).items():
        linhas.append(f"| {ROTULOS[dimensao]} | {nota} | {base} |")
    linhas.append("")

    grupos = (("Confiança alta", "alta"), ("Confiança média", "media"), ("Verificar", "baixa"))
    linhas += ["## Achados", ""]
    for titulo, confianca in grupos:
        desta = [a for a in lista if a.get("confianca") == confianca]
        if not desta:
            continue
        linhas += [f"### {titulo}", ""]
        for item in sorted(desta, key=lambda a: (a.get("caminho", ""), a.get("linha", 0))):
            linhas.append(f"- `{uma_linha(item.get('caminho'))}:{item.get('linha')}` — "
                          f"{uma_linha(item.get('problema'))} "
                          f"*({uma_linha(item.get('regra'))}, {ROTULOS.get(item.get('dimensao'), '')})*  "
                          f"→ {uma_linha(item.get('correcao'))}")
        linhas.append("")
    if not lista:
        linhas += ["Nenhum achado.", ""]

    nao_problema = [i for i in achados.get("nao_e_problema", []) if isinstance(i, dict)]
    if nao_problema:
        linhas += ["## O que não é problema", ""]
        for item in nao_problema:
            linhas.append(f"- `{uma_linha(item.get('caminho'))}` — {uma_linha(item.get('motivo'))}")
        linhas.append("")
    return "\n".join(linhas).rstrip("\n") + "\n"


def gravar(raiz, texto: str):
    """Grava o relatório na raiz e registra a linha no exclude. Devolve (destino, avisos)."""
    raiz = Path(raiz)
    avisos = []
    destino = raiz / "test-health-report.md"
    destino.write_text(texto, encoding="utf-8")
    if gitinfo.dentro_de_repo(raiz):
        if gitinfo.rastreado(raiz, "test-health-report.md"):
            avisos.append("test-health-report.md está versionado: o exclude não protege")
        else:
            # o exclude é lido a partir do topo: em monorepo a linha precisa do caminho do pacote
            linha = "/" + str(destino.relative_to(gitinfo.toplevel(raiz)))
            exclude = gitinfo.git_path(raiz, "info/exclude")
            exclude.parent.mkdir(parents=True, exist_ok=True)
            atual = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
            if linha not in atual.splitlines():
                separador = "" if atual.endswith("\n") or not atual else "\n"
                exclude.write_text(atual + separador + linha + "\n", encoding="utf-8")
    return destino, avisos


def _ambiente(mensagem) -> int:
    print(mensagem, file=sys.stderr)
    return EXIT_AMBIENTE


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Monta o test-health-report.md.")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--data", default=None, help="data do cabeçalho (padrão: hoje)")
    args = ap.parse_args(argv)

    raiz = Path(args.repo)
    if not raiz.is_dir():
        return _ambiente(f"--repo {raiz} não existe.")
    raiz = raiz.resolve()

    avisos_do_ambiente = []
    arquivo_fatos, arquivo_achados = pastas.fatos(raiz), pastas.achados(raiz)
    if not arquivo_fatos.exists():
        return _ambiente(f"fatos.json não encontrado em {arquivo_fatos} — rode diagnose.py antes.")
    try:
        fatos = json.loads(arquivo_fatos.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        fatos = None
    esperadas = ("versao", "repo", "escopo", "inventario", "execucao", "cobertura", "sinais")
    if not isinstance(fatos, dict) or any(chave not in fatos for chave in esperadas) \
            or not isinstance(fatos.get("sinais"), list) or fatos.get("versao") != 1:
        return _ambiente("fatos.json ilegível ou de outra versão — rode diagnose.py de novo.")
    if gitinfo.dentro_de_repo(raiz):
        atual = gitinfo.branch(raiz)
        if fatos["repo"].get("branch") != atual:
            return _ambiente(f"fatos.json é da branch {fatos['repo'].get('branch')!r}, "
                             f"mas você está em {atual!r} — rode diagnose.py de novo.")
        if fatos["repo"].get("head") and fatos["repo"]["head"] != gitinfo.head(raiz):
            # mesma branch, commit diferente: as linhas dos achados podem ter andado
            avisos_do_ambiente.append("os fatos são de outro commit desta branch: confira as linhas "
                                      "ou rode diagnose.py de novo")
    if not arquivo_achados.exists():
        print(f"achados.json não encontrado em {arquivo_achados}", file=sys.stderr)
        return EXIT_RECUSA
    try:
        achados = json.loads(arquivo_achados.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as erro:
        print(f"JSON malformado em achados.json: {erro}", file=sys.stderr)
        return EXIT_RECUSA
    if not isinstance(achados, dict):
        print("achados.json deve ser um objeto JSON", file=sys.stderr)
        return EXIT_RECUSA

    destino_raiz = raiz_do_escopo(fatos)
    if (destino_raiz / "test-health-report.md").is_symlink():
        # link versionado apontando para fora faria o relatório sobrescrever arquivo de qualquer lugar
        return _ambiente("test-health-report.md é um link simbólico: não escrevo através dele. "
                         "Remova o link e rode de novo.")

    problemas = validar(fatos, achados)
    if problemas:
        print("achados.json recusado — corrija todos os itens e rode de novo:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return EXIT_RECUSA

    data = args.data or date.today().isoformat()
    destino, avisos = gravar(destino_raiz, montar(fatos, achados, data))
    print(f"test-health-report.md gravado em {destino}")
    for aviso in avisos_do_ambiente + avisos:
        print(f"aviso: {aviso}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
