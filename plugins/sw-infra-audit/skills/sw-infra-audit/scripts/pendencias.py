#!/usr/bin/env python3
"""Lista o que a auditoria não conseguiu perguntar — e o que declarar para ela conseguir.

Existe porque `collect.py` sair com exit 0 não quer dizer que alguém respondeu alguma coisa.
Numa rodada real, 57 componentes entraram no inventário e nenhum respondeu: os de papel
`entrada` não achavam `metricas_url` declarado, e os demais tinham papel sem pergunta
registrada. O relatório saiu com nome, papel e silêncio, e quem leu concluiu que a skill não
funcionava.

Somente leitura: abre o `report.json` e não toca em mais nada.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True, help="a pasta da rodada, com o report.json")
    args = ap.parse_args(argv)

    from build_report import pendencias_de_declaracao

    caminho = os.path.join(os.path.expanduser(args.dir), "report.json")
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            relatorio = json.load(arquivo)
    except (OSError, ValueError) as erro:
        print(f"não consegui ler {caminho}: {erro}", file=sys.stderr)
        return 2

    pendencias = pendencias_de_declaracao(relatorio.get("alvos") or [])
    if not pendencias:
        print("nenhuma pendência: todo componente respondeu às perguntas do seu papel.")
        return 0

    total = sum(len(p["componentes"]) for p in pendencias)
    print(f"{total} componente(s) sem responder:\n")
    for pendencia in pendencias:
        nomes = ", ".join(c["componente"] for c in pendencia["componentes"][:8])
        resto = len(pendencia["componentes"]) - 8
        if resto > 0:
            nomes += f" e mais {resto}"
        print(f"  papel {pendencia['papel']} · {len(pendencia['componentes'])} componente(s)")
        print(f"    {pendencia['motivo']}")
        print(f"    {nomes}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
