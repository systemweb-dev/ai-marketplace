#!/usr/bin/env python3
"""Confere os arquivos de references/regras/: as seis seções e, com --estilo, que os blocos php de Certo e
Como corrigir já estão no estilo da casa (passam pelo fixer sem mudar). O bloco de Errado fica de fora de
propósito: ele mostra o estilo proibido."""
import pathlib
import re
import subprocess
import sys
import tempfile
import textwrap

SECOES = ("Regra", "Por quê", "Certo", "Errado", "Como reconhecer", "Como corrigir")
PASTA = pathlib.Path(__file__).resolve().parent.parent / "references" / "regras"
FIXER = pathlib.Path(__file__).resolve().parent / "testar_fixer.sh"


def secoes(texto):
    return dict(re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", texto, re.S | re.M))


def blocos_php(texto):
    return re.findall(r"```php\n(.*?)```", texto, re.S)


def embrulhar(codigo):
    """Trecho solto vira um arquivo com <?php e uma classe, para o fixer poder rodar."""
    if codigo.lstrip().startswith("<?php"):
        return codigo
    codigo = textwrap.dedent(codigo)
    if re.search(r"^(final\s+)?(class|interface|enum|trait)\s", codigo, re.M):
        return "<?php\n\n" + codigo
    if re.search(r"^(public|private|protected)\s+(static\s+)?function", codigo, re.M):
        return "<?php\n\nclass Exemplo\n{\n" + textwrap.indent(codigo, "    ") + "}\n"
    corpo = textwrap.indent(codigo, "        ")
    return "<?php\n\nclass Exemplo\n{\n    public function exemplo()\n    {\n" + corpo + "    }\n}\n"


def main():
    estilo = "--estilo" in sys.argv
    arquivos = sorted(PASTA.glob("*.md"))
    if not arquivos:
        print("nenhuma regra em references/regras/")
        return 1
    erros = []
    with tempfile.TemporaryDirectory() as tmp:
        for arquivo in arquivos:
            partes = secoes(arquivo.read_text(encoding="utf-8"))
            faltando = [s for s in SECOES if s not in partes]
            if faltando:
                erros.append(f"{arquivo.name}: falta a seção {', '.join(faltando)}")
                continue
            if not estilo:
                continue
            for secao in ("Certo", "Como corrigir"):
                for n, codigo in enumerate(blocos_php(partes[secao]), 1):
                    alvo = pathlib.Path(tmp) / f"{arquivo.stem}-{secao.replace(' ', '_')}-{n}.php"
                    alvo.write_text(embrulhar(codigo), encoding="utf-8")
                    rodada = subprocess.run(["bash", str(FIXER), str(alvo)], capture_output=True, text=True)
                    if rodada.returncode != 0:
                        erros.append(f"{arquivo.name} [{secao} #{n}]: fora do estilo\n{rodada.stdout}")
    for erro in erros:
        print(erro)
    print(f"{len(arquivos)} regras, {len(erros)} problema(s)")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
