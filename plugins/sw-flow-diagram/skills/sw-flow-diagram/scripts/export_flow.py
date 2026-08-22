#!/usr/bin/env python3
"""
Exporta um diagrama pra PNG (alta resolução) e/ou PDF, headless — sem abrir o navegador
nem clicar na toolbar. Usa um Chrome/Chromium instalado; se não achar nenhum, explica o
fallback (abrir o flow.html e usar os botões SVG/PNG da toolbar).

Uso:
  python3 export_flow.py --dir ./flows/<slug>                  # PNG @2x (padrão)
  python3 export_flow.py --dir ./flows/<slug> --format pdf     # PDF
  python3 export_flow.py --dir ./flows/<slug> --format both --scale 3 --theme dark

A página é carregada com ?export=1 (esconde a toolbar, tamanho natural, estático) e o
?theme= controla claro/escuro. Requer o flow.html já buildado (roda o build se faltar).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

BUILDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_flow.py")

# nomes comuns de binário do Chrome/Chromium por plataforma
CHROME_CANDIDATES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "chrome", "microsoft-edge", "brave-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        p = shutil.which(c) if os.sep not in c else (c if os.path.isfile(c) else None)
        if p:
            return p
    return None


def read_size(html_path):
    """Lê o tamanho natural do diagrama do atributo data-vb do flow.html."""
    with open(html_path, encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r'data-vb="0 0 ([\d.]+) ([\d.]+)"', txt)
    if not m:
        return 1200, 800
    return int(float(m[1])) + 2, int(float(m[2])) + 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="diretorio do fluxo (com flow.json/flow.html)")
    ap.add_argument("--format", choices=["png", "pdf", "both"], default="png")
    ap.add_argument("--scale", type=float, default=2, help="fator de resolucao do PNG (2 = @2x)")
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    args = ap.parse_args()

    d = os.path.expanduser(args.dir)
    flow_json = os.path.join(d, "flow.json")
    flow_html = os.path.join(d, "flow.html")
    if not os.path.isfile(flow_json):
        sys.exit(f"flow.json nao encontrado em {d}")
    # garante o html buildado/atualizado
    subprocess.run([sys.executable, BUILDER, "--dir", d], check=True, capture_output=True, text=True)

    chrome = find_chrome()
    if not chrome:
        sys.exit(
            "Nenhum Chrome/Chromium encontrado no PATH.\n"
            "Fallback: abra o flow.html no navegador e use os botoes SVG/PNG da toolbar\n"
            "(ou instale o chromium: `apt install chromium` / `brew install chromium`)."
        )

    w, h = read_size(flow_html)
    url = f"file://{os.path.abspath(flow_html)}?export=1&theme={args.theme}"
    base = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
            "--force-color-profile=srgb", f"--window-size={w},{h}"]
    outs = []

    if args.format in ("png", "both"):
        out = os.path.join(d, "flow.png")
        cmd = base + [f"--force-device-scale-factor={args.scale}",
                      f"--screenshot={out}", url]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        outs.append(out)

    if args.format in ("pdf", "both"):
        out = os.path.join(d, "flow.pdf")
        cmd = base + ["--no-pdf-header-footer", f"--print-to-pdf={out}", url]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        outs.append(out)

    for o in outs:
        print(o)


if __name__ == "__main__":
    main()
