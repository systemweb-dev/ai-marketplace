#!/usr/bin/env python3
"""Apura os fatos da suíte de testes do projeto e grava `fatos.json`.

Sem `--executar`, NENHUM processo de runner é criado: só inventário e detectores textuais.
"""
import argparse
import json
import sys
from pathlib import Path

from lib import backup, gitinfo, inventario, pastas, sinais, stacks
from lib import execucao
from lib.stacks import base as stacks_base

EXIT_OK, EXIT_PARADA = 0, 2
VERSAO_DOS_FATOS = 1


def _repo_info(raiz) -> dict:
    if not gitinfo.dentro_de_repo(raiz):
        return {"toplevel": str(Path(raiz).resolve()), "branch": None, "head": None}
    return {"toplevel": str(gitinfo.toplevel(raiz)),
            "branch": gitinfo.branch(raiz), "head": gitinfo.head(raiz)}


def apurar(raiz, escopo) -> dict:
    """Fatos estáticos: inventário, stacks e sinais. Nada é executado aqui."""
    dados = inventario.varrer(escopo)
    achados = []
    for arquivo in dados["lista"]:
        caminho = Path(escopo) / arquivo["caminho"]
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        achados.extend(sinais.varrer(arquivo["caminho"], texto, arquivo["suite"]))
    return {
        "versao": VERSAO_DOS_FATOS,
        "repo": _repo_info(raiz),
        "escopo": {"tipo": "repo" if Path(escopo) == Path(raiz) else "pacote",
                   "raiz": str(Path(escopo).relative_to(Path(raiz).resolve()))
                           if Path(escopo) != Path(raiz) else "."},
        "stacks": stacks.detectar(escopo, dados),
        "ambiente": {"banco": execucao.banco_a_vista(Path(escopo))},
        "inventario": {k: dados[k] for k in ("arquivos", "testes", "por_suite", "lista")},
        "execucao": {"rodou": False, "comando": None, "verde": None, "timeout": False,
                     "passou": 0, "falhou": 0, "pulado": 0, "duracao_faixa": None, "lentos": []},
        "cobertura": {"disponivel": False, "ferramenta": None, "por_arquivo": []},
        "sinais": achados,
        "suspeitos": sorted({a["caminho"] for a in achados}),
    }


def executar(fatos, raiz, escopo, cobertura: bool, timeout: int) -> None:
    """Preenche fatos['execucao'], fatos['cobertura'] e acrescenta os sinais de execução."""
    nativas = [s for s in fatos["stacks"] if s["nativo"]]
    if not nativas:
        print("nenhuma stack com módulo nativo: seguindo pelo caminho heurístico, sem executar")
        return
    escolhida = nativas[0]
    ignoradas = [s["runner"] for s in nativas[1:]]
    if ignoradas:
        print("stacks nativas não executadas nesta rodada: " + ", ".join(ignoradas))
    try:
        stack = stacks.montar(escolhida["runner"])
    except KeyError:
        print(f"runner {escolhida['runner']} sem módulo nativo: caminho heurístico")
        return

    pasta_saida = pastas.saida(raiz)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    limite = stacks_base.LIMITE_DE_LENTO
    # o coverage grava `.coverage` no diretório atual se ninguém disser o contrário
    extra = {"COVERAGE_FILE": str(pasta_saida / ".coverage")}
    fatos["execucao"]["ambiente"] = {chave: execucao.ambiente_limpo(extra)[chave]
                                     for chave in ("CI", "NO_COLOR", "COVERAGE_FILE")}

    comando = stack.comando_descoberta(escopo)
    try:
        codigo, texto = execucao.rodar(comando, escopo, timeout, extra)
    except execucao.Estourou:
        fatos["execucao"].update({"rodou": True, "timeout": True,
                                  "comando": " ".join(str(p) for p in comando), "verde": None})
        fatos["sinais"].append({"regra": "execucao_estourou", "caminho": ".", "linha": 1,
                                "evidencia": f"descoberta passou de {timeout}s", "teste": ""})
        return
    if codigo == 127:
        fatos["sinais"].append({"regra": "runner_ausente", "caminho": ".", "linha": 1,
                                "evidencia": f"{stack.runner} não está instalado neste projeto",
                                "teste": ""})
        print(f"{stack.runner} não está instalado: seguindo sem executar")
        return
    descobertos = stack.ler_descoberta(texto)
    arquivos_descobertos = stack.arquivos(descobertos, escopo) if descobertos else None
    for arquivo in fatos["inventario"]["lista"]:
        if arquivos_descobertos is not None and arquivo["caminho"] not in arquivos_descobertos:
            fatos["sinais"].append({"regra": "nao_descoberto", "caminho": arquivo["caminho"],
                                    "linha": 1, "evidencia": f"{stack.runner} não coletou este arquivo",
                                    "teste": ""})

    comando = stack.comando_suite(escopo, pasta_saida, cobertura)
    fatos["execucao"]["comando"] = " ".join(str(p) for p in comando)
    try:
        codigo, texto = execucao.rodar(comando, escopo, timeout, extra)
    except execucao.Estourou:
        fatos["execucao"].update({"rodou": True, "timeout": True, "verde": None})
        fatos["sinais"].append({"regra": "execucao_estourou", "caminho": ".", "linha": 1,
                                "evidencia": f"a suíte passou de {timeout}s", "teste": ""})
        return

    # cobertura é medição independente: não pode se perder se o junit vier ilegível
    if cobertura:
        linhas = stack.ler_cobertura(pasta_saida, escopo)
        fatos["cobertura"] = {"disponivel": bool(linhas),
                              "ferramenta": stack.runner if linhas else None,
                              "por_arquivo": linhas}

    suite_mais_comum = max(fatos["inventario"]["por_suite"], key=fatos["inventario"]["por_suite"].get,
                           default="desconhecida")
    resultado = stack.ler_resultado(texto, pasta_saida, limite.get(suite_mais_comum, 1.0))
    if resultado is None:
        fatos["execucao"].update({"rodou": True, "verde": None})
        fatos["sinais"].append({"regra": "saida_ilegivel", "caminho": ".", "linha": 1,
                                "evidencia": f"não consegui ler a saída de {stack.runner}", "teste": ""})
        return
    # junit sem <failure> não prova nada se o runner saiu com erro: bootstrap pode ter quebrado antes
    resultado["verde"] = resultado["verde"] and codigo == 0
    fatos["execucao"].update({"rodou": True, "timeout": False, "codigo": codigo, **resultado})
    for lento in resultado["lentos"]:
        fatos["sinais"].append({"regra": "lento_para_o_tipo", "caminho": ".", "linha": 1,
                                "evidencia": f"{lento['teste']} levou {lento['faixa']}", "teste": lento["teste"]})



def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Apura os fatos da suíte de testes.")
    ap.add_argument("--repo", default=".", help="raiz do projeto (padrão: diretório atual)")
    ap.add_argument("--escopo", default=None, help="subpasta a diagnosticar (monorepo)")
    ap.add_argument("--executar", action="store_true", help="roda descoberta e suíte (opt-in)")
    ap.add_argument("--cobertura", action="store_true", help="pede cobertura na execução")
    ap.add_argument("--banco-ok", action="store_true",
                    help="confirma que pode executar mesmo com banco configurado")
    ap.add_argument("--timeout", type=int, default=300, help="segundos por comando (padrão: 300)")
    args = ap.parse_args(argv)

    raiz = Path(args.repo)
    if not raiz.is_dir():
        print(f"--repo {raiz} não existe.", file=sys.stderr)
        return EXIT_PARADA
    raiz = raiz.resolve()
    escopo = (raiz / args.escopo).resolve() if args.escopo else raiz
    if not escopo.is_dir():
        print(f"--escopo {escopo} não existe.", file=sys.stderr)
        return EXIT_PARADA
    if not escopo.is_relative_to(raiz):
        print(f"--escopo precisa estar dentro de --repo ({raiz}).", file=sys.stderr)
        return EXIT_PARADA

    restaurados = backup.restaurar_tudo(raiz)
    sobrescritos = restaurados["sobrescrito"]
    if sobrescritos or restaurados["intacto"]:
        print("resíduo de execução anterior restaurado: "
              + ", ".join(sobrescritos + restaurados["intacto"]))
    if sobrescritos:
        print("atenção: estes arquivos tinham alteração posterior ao backup e foram sobrescritos: "
              + ", ".join(sobrescritos))

    fatos = apurar(raiz, escopo)
    if args.executar:
        marcas = execucao.banco_a_vista(escopo)
        if marcas and not args.banco_ok:
            print("Banco configurado no ambiente de teste: " + ", ".join(marcas) + ".\n"
                  "A coleta já importa conftest/bootstrap e pode conectar ou truncar banco. "
                  "Confirme com --banco-ok se este ambiente for descartável.", file=sys.stderr)
            return EXIT_PARADA
        fatos["execucao"]["timeout"] = False
        executar(fatos, raiz, escopo, args.cobertura, args.timeout)
    if fatos["inventario"]["arquivos"] == 0:
        print("Nenhum arquivo de teste encontrado no escopo — não há o que diagnosticar. "
              "Use o modo gerar.", file=sys.stderr)
        return EXIT_PARADA

    pastas.criar(raiz)
    destino = pastas.fatos(raiz)
    destino.write_text(json.dumps(fatos, ensure_ascii=False, indent=1), encoding="utf-8")

    inv = fatos["inventario"]
    print(f"fatos.json: {destino}")
    print(f"escopo: {fatos['escopo']['raiz']} · {inv['arquivos']} arquivo(s) · {inv['testes']} teste(s) · "
          + " · ".join(f"{suite} {qtd}" for suite, qtd in sorted(inv["por_suite"].items())))
    print("stacks: " + (", ".join(f"{s['runner']}" for s in fatos["stacks"]) or "nenhuma reconhecida"))
    print(f"sinais: {len(fatos['sinais'])} em {len(fatos['suspeitos'])} arquivo(s)")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
