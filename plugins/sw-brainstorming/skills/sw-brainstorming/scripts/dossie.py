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


TASK = re.compile(r"^#{2,4}\s*Task\s+\d+\s*:", re.I)
FEITO = re.compile(r"^\s*[-*]\s*\[x\]", re.I)
PENDENTE = re.compile(r"^\s*[-*]\s*\[ \]")


def progresso_do_plano(caminho: str):
    """(tasks feitas, total). Uma task está feita quando TODOS os seus steps estão marcados —
    'tem plano' não diz nada sobre andamento, e um índice que não diz a verdade é o que este
    script existe para evitar. Plano sem task ainda devolve None: não invente 0/0."""
    try:
        with open(caminho, encoding="utf-8") as f:
            linhas = f.read().split("\n")
    except OSError:
        return None
    tasks, atual = [], None
    for linha in linhas:
        if TASK.match(linha):
            atual = {"feitos": 0, "pendentes": 0}
            tasks.append(atual)
        elif atual is not None:
            if FEITO.match(linha):
                atual["feitos"] += 1
            elif PENDENTE.match(linha):
                atual["pendentes"] += 1
    if not tasks:
        return None
    feitas = sum(1 for t in tasks if t["feitos"] and not t["pendentes"])
    return [feitas, len(tasks)]


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
            "progresso": progresso_do_plano(os.path.join(pasta, "plan.md")),
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


def rotulo_do_plano(d: dict) -> str:
    p = d.get("progresso")
    return f"plano {p[0]}/{p[1]}" if p else "plano"


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
            extras.append(rotulo_do_plano(d))
        if d["tem_briefing"]:
            extras.append("briefing")
        if d["referencias"]:
            extras.append(f"{len(d['referencias'])} ref")
        print(f"  {ROTULO.get(d['estado'], d['estado']):16} {d['slug']:44} {' · '.join(extras)}".rstrip())


def cmd_estado(args):
    if args.novo_estado not in ESTADOS:
        sys.exit(f"ERRO: estado deve ser um de {ESTADOS}")
    spec = os.path.join(args.raiz, args.slug, "spec.md")
    if not os.path.isfile(spec):
        # Esquecer o prefixo de data é o erro natural; o script sabe o slug certo, então diz.
        parecidos = [d["slug"] for d in dossies(args.raiz) if args.slug in d["slug"]]
        dica = f" — você quis dizer: {', '.join(parecidos)}?" if parecidos else ""
        sys.exit(f"ERRO: dossiê '{args.slug}' não encontrado em {args.raiz}{dica}")
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
            tem.append(rotulo_do_plano(d))
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
    # `--raiz` vale antes OU depois do subcomando: `novo --titulo X --raiz Y` é a ordem que
    # sai naturalmente de quem digita, e morria em "unrecognized arguments".
    # default=SUPPRESS: sem isso o subcomando reaplica o padrão POR CIMA do valor que veio
    # antes dele, e `--raiz Y novo` passaria a gravar em docs/specs.
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--raiz", default=argparse.SUPPRESS,
                       help=f"raiz dos dossiês (padrão: {RAIZ_PADRAO})")
    ap = argparse.ArgumentParser(description=__doc__, parents=[comum],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("novo", parents=[comum]); p.add_argument("--titulo", required=True); p.set_defaults(fn=cmd_novo)
    p = sub.add_parser("listar", parents=[comum]); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_listar)
    p = sub.add_parser("estado", parents=[comum]); p.add_argument("slug"); p.add_argument("novo_estado"); p.set_defaults(fn=cmd_estado)
    p = sub.add_parser("indice", parents=[comum]); p.set_defaults(fn=cmd_indice)
    args = ap.parse_args()
    if not hasattr(args, "raiz"):
        args.raiz = RAIZ_PADRAO
    args.fn(args)


if __name__ == "__main__":
    main()
