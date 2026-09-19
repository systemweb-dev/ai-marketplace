#!/usr/bin/env python3
"""Guarda, restaura e varre resíduo — a rede de segurança de toda edição que a skill faz."""
import argparse
import sys
from pathlib import Path

from lib import backup

EXIT_OK, EXIT_ERRO = 0, 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Backup dos arquivos que a skill vai editar.")
    ap.add_argument("--repo", default=".")
    ap.add_argument("acao", choices=("guardar", "restaurar", "descartar", "varrer"))
    ap.add_argument("arquivo", nargs="?", help="caminho relativo à raiz")
    args = ap.parse_args(argv)

    raiz = Path(args.repo)
    if not raiz.is_dir():
        print(f"--repo {raiz} não existe.", file=sys.stderr)
        return EXIT_ERRO
    raiz = raiz.resolve()

    if args.acao == "varrer":
        pendentes = backup.residuo(raiz)
        if not pendentes:
            print("nenhum resíduo pendente")
            return EXIT_OK
        restaurados = backup.restaurar_tudo(raiz)
        voltaram = restaurados["sobrescrito"] + restaurados["intacto"]
        if voltaram:
            print("restaurado: " + ", ".join(sorted(voltaram)))
        if restaurados["sobrescrito"]:
            print("atenção: sobrescrevi alteração posterior ao backup em "
                  + ", ".join(sorted(restaurados["sobrescrito"])))
        faltaram = sorted(set(pendentes) - set(voltaram))
        if faltaram:
            # a cópia sumiu: o arquivo fica como está e o registro continua pendente
            print("não consegui restaurar (cópia ausente): " + ", ".join(faltaram), file=sys.stderr)
            return EXIT_ERRO
        return EXIT_OK

    if not args.arquivo:
        print(f"{args.acao} precisa do caminho do arquivo.", file=sys.stderr)
        return EXIT_ERRO
    alvo = (raiz / args.arquivo).resolve()
    if not alvo.is_relative_to(raiz):
        # sem isto, `../fora.txt` ou um caminho absoluto faria a skill escrever fora do projeto
        print(f"{args.arquivo} está fora da raiz {raiz}.", file=sys.stderr)
        return EXIT_ERRO
    relativo = str(alvo.relative_to(raiz))

    if args.acao == "guardar":
        if not alvo.is_file():
            print(f"{args.arquivo} não existe.", file=sys.stderr)
            return EXIT_ERRO
        try:
            backup.guardar(raiz, relativo)
        except backup.BackupSumiu as erro:
            print(f"{erro} — rode `varrer` antes de guardar de novo.", file=sys.stderr)
            return EXIT_ERRO
        print(f"guardado: {relativo}")
        return EXIT_OK

    feito = backup.restaurar(raiz, relativo) if args.acao == "restaurar" \
        else backup.descartar(raiz, relativo)
    if not feito:
        print(f"{relativo}: sem backup guardado.", file=sys.stderr)
        return EXIT_ERRO
    print(f"{args.acao}: {relativo}")
    if feito == "sobrescrito":
        print(f"atenção: {relativo} tinha alteração posterior ao backup, e ela foi perdida")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
