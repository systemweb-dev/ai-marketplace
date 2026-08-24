#!/usr/bin/env python3
"""Dossiê de trabalho: uma pasta por iniciativa, com spec, plano, briefing e referências.

Por que um script e não instruções: o índice e o estado precisam estar sempre certos.
Deixar isso a cargo do agente significa que, no dia em que ele esquecer, o índice mente —
e um índice que mente é pior que nenhum.

Uso:
  dossie.py novo   --titulo "Auditoria de cluster"   [--raiz docs/specs]
  dossie.py listar [--json]
  dossie.py estado <slug> <rascunho|aprovado|em-execucao|concluido>
  dossie.py indice
"""
import argparse
import datetime
import json
import os
import re
import sys
import unicodedata

RAIZ_PADRAO = os.path.join("docs", "specs")
ESTADOS = ["rascunho", "aprovado", "em-execucao", "concluido"]
ROTULO = {"rascunho": "🟡 rascunho", "aprovado": "🟢 aprovado",
          "em-execucao": "🔵 em execução", "concluido": "⚪ concluído"}
INICIO = "<!-- DOSSIES:START -->"
FIM = "<!-- DOSSIES:END -->"


def slugify(txt: str) -> str:
    txt = unicodedata.normalize("NFD", txt).encode("ascii", "ignore").decode()
    txt = re.sub(r"[^a-zA-Z0-9]+", "-", txt).strip("-").lower()
    return txt or "sem-titulo"


def ler_frontmatter(caminho: str) -> dict:
    """Frontmatter YAML simples (chave: valor). Evita dependência de PyYAML."""
    dados = {}
    try:
        with open(caminho, encoding="utf-8") as f:
            if f.readline().strip() != "---":
                return dados
            for linha in f:
                if linha.strip() == "---":
                    break
                if ":" in linha:
                    k, v = linha.split(":", 1)
                    dados[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return dados


def dossies(raiz: str) -> list:
    if not os.path.isdir(raiz):
        return []
    out = []
    for nome in sorted(os.listdir(raiz), reverse=True):
        pasta = os.path.join(raiz, nome)
        spec = os.path.join(pasta, "spec.md")
        if not os.path.isdir(pasta) or not os.path.isfile(spec):
            continue
        fm = ler_frontmatter(spec)
        out.append({
            "slug": nome,
            "pasta": pasta,
            "titulo": fm.get("titulo") or nome,
            "estado": fm.get("estado", "rascunho"),
            "criado": fm.get("criado", nome[:10]),
            "tem_plano": os.path.isfile(os.path.join(pasta, "plan.md")),
            "tem_briefing": any(os.path.isfile(os.path.join(pasta, f"briefing{e}"))
                                for e in (".md", ".html", ".pdf")),
            # ignora ocultos: .gitkeep existe só pra pasta vazia sobreviver ao git,
            # contá-lo faria o índice anunciar uma referência que não existe
            "referencias": sorted(f for f in os.listdir(os.path.join(pasta, "referencias"))
                                  if not f.startswith(".")) 
                           if os.path.isdir(os.path.join(pasta, "referencias")) else [],
        })
    return out


ESQUELETO = """---
titulo: {titulo}
slug: {slug}
criado: {data}
estado: rascunho
---

# {titulo}

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `plan.md` é o passo a
> passo de execução; `referencias/` guarda o material de apoio (prints, PDFs, diagramas).

*(a skill sw-brainstorming preenche as seções a partir da conversa)*
"""


def cmd_novo(args):
    data = datetime.date.today().isoformat()
    slug = f"{data}-{slugify(args.titulo)}"
    pasta = os.path.join(args.raiz, slug)
    if os.path.isdir(pasta):
        sys.exit(f"ERRO: já existe {pasta} — use `dossie.py listar` e continue o existente.")
    os.makedirs(os.path.join(pasta, "referencias"), exist_ok=True)
    with open(os.path.join(pasta, "spec.md"), "w", encoding="utf-8") as f:
        f.write(ESQUELETO.format(titulo=args.titulo, slug=slug, data=data))
    # .gitkeep pra pasta vazia sobreviver ao git
    open(os.path.join(pasta, "referencias", ".gitkeep"), "a").close()
    escrever_indice(args.raiz)
    print(pasta)


def cmd_listar(args):
    itens = dossies(args.raiz)
    if args.json:
        print(json.dumps(itens, ensure_ascii=False, indent=1))
        return
    if not itens:
        print("(nenhum dossiê ainda)")
        return
    for d in itens:
        extras = []
        if d["tem_plano"]:
            extras.append("plano")
        if d["tem_briefing"]:
            extras.append("briefing")
        if d["referencias"]:
            extras.append(f"{len(d['referencias'])} ref")
        print(f"  {ROTULO.get(d['estado'], d['estado']):16} {d['slug']:44} {' · '.join(extras)}")


def cmd_estado(args):
    if args.novo_estado not in ESTADOS:
        sys.exit(f"ERRO: estado deve ser um de {ESTADOS}")
    spec = os.path.join(args.raiz, args.slug, "spec.md")
    if not os.path.isfile(spec):
        sys.exit(f"ERRO: {spec} não encontrado")
    with open(spec, encoding="utf-8") as f:
        txt = f.read()
    novo, n = re.subn(r"^estado:.*$", f"estado: {args.novo_estado}", txt, count=1, flags=re.M)
    if not n:  # spec sem frontmatter (spec antigo): põe um
        novo = f"---\nslug: {args.slug}\nestado: {args.novo_estado}\n---\n\n" + txt
    with open(spec, "w", encoding="utf-8") as f:
        f.write(novo)
    escrever_indice(args.raiz)
    print(f"{args.slug} → {args.novo_estado}")


def escrever_indice(raiz: str):
    itens = dossies(raiz)
    linhas = ["| Trabalho | Estado | Criado | Tem |", "|---|---|---|---|"]
    for d in itens:
        tem = []
        if d["tem_plano"]:
            tem.append("plano")
        if d["tem_briefing"]:
            tem.append("briefing")
        if d["referencias"]:
            tem.append(f"{len(d['referencias'])} ref")
        linhas.append(f"| [{d['titulo']}]({d['slug']}/spec.md) | {ROTULO.get(d['estado'], d['estado'])} "
                      f"| {d['criado']} | {', '.join(tem) or '—'} |")
    tabela = "\n".join(linhas) if itens else "_(nenhum dossiê ainda)_"
    caminho = os.path.join(raiz, "README.md")
    cabecalho = ("# Specs\n\nUm diretório por trabalho: `spec.md` (design), `plan.md` (execução), "
                 "`briefing.*` (versão para negócio) e `referencias/`.\nTabela gerada por "
                 "`scripts/dossie.py indice` — não edite à mão.\n\n")
    corpo = f"{cabecalho}{INICIO}\n{tabela}\n{FIM}\n"
    if os.path.isfile(caminho):
        with open(caminho, encoding="utf-8") as f:
            atual = f.read()
        if INICIO in atual and FIM in atual:
            corpo = re.sub(re.escape(INICIO) + r".*?" + re.escape(FIM),
                           f"{INICIO}\n{tabela}\n{FIM}", atual, flags=re.S)
    os.makedirs(raiz, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(corpo)


def cmd_indice(args):
    escrever_indice(args.raiz)
    print(os.path.join(args.raiz, "README.md"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=RAIZ_PADRAO, help=f"raiz dos dossiês (padrão: {RAIZ_PADRAO})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("novo"); p.add_argument("--titulo", required=True); p.set_defaults(fn=cmd_novo)
    p = sub.add_parser("listar"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_listar)
    p = sub.add_parser("estado"); p.add_argument("slug"); p.add_argument("novo_estado"); p.set_defaults(fn=cmd_estado)
    p = sub.add_parser("indice"); p.set_defaults(fn=cmd_indice)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
