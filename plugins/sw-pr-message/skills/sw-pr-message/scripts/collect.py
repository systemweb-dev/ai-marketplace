#!/usr/bin/env python3
"""Coleta, só com leitura, os fatos da branch para a mensagem de PR.

Grava <git-path>/sw-pr-message/fatos.json. Exit 2 quando precisa parar (mensagem no stderr).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import base as base_mod  # noqa: E402
from lib import coleta  # noqa: E402
from lib.gitcmd import GitFalhou, GitRecusado, caminho_git, git  # noqa: E402

EXIT_OK, EXIT_PARADA = 0, 2


def coletar(repo: Path, base=None) -> dict:
    atual = base_mod.pre_checar(repo, tem_base=base is not None)
    topo = Path(git(["rev-parse", "--show-toplevel"], repo).strip())
    b = base_mod.detectar_base(topo, base)
    lista = coleta.commits(topo, b["ref"])
    arquivos = coleta.numstat(topo, b["ref"])
    coleta.preencher_diffs(topo, b["ref"], arquivos)
    tem_develop = base_mod.existe(topo, "develop")
    return {
        "branch": atual,
        "base": b,
        "hotfix": coleta.sinais_hotfix(atual, lista, b["nome"], tem_develop,
                                       develop_empata="develop" in b["empate"]),
        "stats": {"arquivos": len(arquivos),
                  "insercoes": sum(a["mais"] for a in arquivos),
                  "delecoes": sum(a["menos"] for a in arquivos),
                  "ruido": [a["caminho"] for a in arquivos if a["ruido"]],
                  "merges_ignorados": coleta.merges_ignorados(topo, b["ref"])},
        "commits": lista,
        "arquivos": arquivos,
        "avisos": coleta.avisos(topo),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Coleta os fatos da branch para a mensagem de PR.")
    ap.add_argument("--repo", default=".", help="repositório (padrão: diretório atual)")
    ap.add_argument("--base", default=None, help="branch base; sem ela, a base é detectada")
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"--repo {repo} não existe.", file=sys.stderr)
        return EXIT_PARADA

    try:
        fatos = coletar(repo, args.base)
    except base_mod.Parada as parada:
        print(str(parada), file=sys.stderr)
        return EXIT_PARADA
    except GitRecusado as recusa:
        print(f"Recusado: {recusa}", file=sys.stderr)
        return EXIT_PARADA
    except GitFalhou as falha:
        print(f"Falha do git: {falha}", file=sys.stderr)
        return EXIT_PARADA

    pasta = caminho_git(repo, "sw-pr-message")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "fatos.json"
    destino.write_text(json.dumps(fatos, ensure_ascii=False, indent=1), encoding="utf-8")

    b = fatos["base"]
    print(f"fatos.json: {destino}")
    print(f"base: {b['nome']} ({base_mod.curta(b['ref'])}) · {b['como']} · {b['a_frente']} commit(s) · "
          + " · ".join(f"{n} {c}" for n, c in b["candidatas"].items()))
    if b["empate"]:
        print(f"empate: {', '.join(b['empate'])} — mesmo conteúdo para esta branch; a base acima veio do desempate")
    cortados = [a["caminho"] for a in fatos["arquivos"] if a["cortado"]]
    if cortados:
        print("cortados: " + ", ".join(cortados))
    for aviso in fatos["avisos"]:
        print(f"aviso: {aviso}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
