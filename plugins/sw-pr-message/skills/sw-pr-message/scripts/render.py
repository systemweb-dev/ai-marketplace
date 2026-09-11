#!/usr/bin/env python3
"""Valida o mudancas.json contra o fatos.json e grava o PR-MESSAGE.md.

O agente escreve o conteúdo; este script garante o padrão: ordem e títulos das seções,
idioma, sem emoji, título sem prefixo — e que nenhum commit ficou de fora.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.gitcmd import GitFalhou, caminho_git, git, git_ok  # noqa: E402

SECOES = ("novas", "ajustes", "correcoes", "removido", "seguranca", "interno")
CAMPOS_HOTFIX = ("causa", "impacto", "rollback")
IDIOMAS = ("pt", "en")
HASH_MIN = 7
EXIT_OK, EXIT_AMBIENTE, EXIT_RECUSA = 0, 2, 3


def _faixa(inicio, fim=None):
    return chr(inicio) if fim is None else f"{chr(inicio)}-{chr(fim)}"


# Emoji por código, não por caractere colado: vários são invisíveis (U+FE0F, U+200D, U+20E3) e
# sumiriam ao copiar. Dingbats vai item a item porque ✓ e ✔ moram no mesmo bloco e devem ficar.
_EMOJI = re.compile("[" + "".join([
    _faixa(0x1F000, 0x1FAFF), _faixa(0x2600, 0x26FF),                       # pictográficos e símbolos
    _faixa(0x2705), _faixa(0x270A, 0x270B), _faixa(0x2728), _faixa(0x274C), _faixa(0x274E),
    _faixa(0x2753, 0x2755), _faixa(0x2757), _faixa(0x2763, 0x2764), _faixa(0x2795, 0x2797),
    _faixa(0x27B0), _faixa(0x27BF),                                          # emoji de Dingbats
    _faixa(0x231A, 0x231B), _faixa(0x23E9, 0x23F3), _faixa(0x23F8, 0x23FA),
    _faixa(0x2B1B, 0x2B1C), _faixa(0x2B50), _faixa(0x2B55),                  # apresentação fora dos blocos
    _faixa(0xFE0F), _faixa(0x200D), _faixa(0x20E3),                          # seletor, ZWJ, keycap
]) + "]")
# Só tipos Conventional: "Checkout: novo fluxo" é título legítimo e não pode perder a palavra.
_PREFIXO_CC = re.compile(
    r"^(feat|fix|chore|refactor|docs|test|ci|build|perf|style|revert|hotfix)(\([^)]*\))?!?:\s*",
    re.IGNORECASE,
)
_PREFIXO_COLCHETE = re.compile(r"^\[[^\]]+\]\s*")


def limpar(texto) -> str:
    """Texto do agente numa linha só e sem emoji. Não-texto vira vazio: a validação acusa o tipo.

    Todo espaço em branco vira um espaço — uma quebra de linha seguida de "## X" num item criaria
    uma seção que não é do render.
    """
    if not isinstance(texto, str):
        return ""
    return re.sub(r"\s+", " ", _EMOJI.sub("", texto)).strip()


def limpar_titulo(titulo) -> str:
    t = _PREFIXO_COLCHETE.sub("", limpar(titulo))
    return _PREFIXO_CC.sub("", t).strip()


def _resolver(prefixo, hashes):
    """Hash completo para um prefixo, ou o motivo de não resolver."""
    if not isinstance(prefixo, str) or len(prefixo) < HASH_MIN:
        return None, "curto"
    achados = [h for h in hashes if h.startswith(prefixo.lower())]
    if not achados:
        return None, "desconhecido"
    if len(achados) > 1:
        return None, "ambiguo"
    return achados[0], None


def _lista(valor):
    """Ausente ou null valem lista vazia; o que não for lista segue adiante para ser acusado."""
    return [] if valor is None else valor


def validar(fatos: dict, mudancas: dict) -> list:
    """Todos os problemas de uma vez, e só problemas — nunca exceção, seja o que for que o agente
    escreveu. É o que permite ao agente corrigir tudo numa rodada."""
    problemas = []
    hashes = [c["hash"] for c in fatos.get("commits", [])]

    if mudancas.get("idioma") not in IDIOMAS:
        problemas.append(f"idioma inválido: {mudancas.get('idioma')!r} (use 'pt' ou 'en')")
    titulo = mudancas.get("titulo")
    if not isinstance(titulo, str):
        problemas.append("titulo deve ser texto")
    elif not limpar(titulo):
        problemas.append("titulo vazio")
    elif not limpar_titulo(titulo):
        problemas.append("titulo vazio depois de remover o prefixo")
    resumo = mudancas.get("resumo")
    if not isinstance(resumo, str):
        problemas.append("resumo deve ser texto")
    elif not limpar(resumo):
        problemas.append("resumo vazio")

    secoes = _lista(mudancas.get("secoes")) if mudancas.get("secoes") is not None else {}
    if not isinstance(secoes, dict):
        problemas.append("secoes deve ser um objeto")
        secoes = {}
    for chave in secoes:
        if chave not in SECOES:
            problemas.append(f"seção desconhecida: {chave!r}")

    em_itens = set()
    for chave in SECOES:
        itens = _lista(secoes.get(chave))
        if not isinstance(itens, list):
            problemas.append(f"secoes.{chave} deve ser uma lista")
            continue
        for n, item in enumerate(itens, 1):
            if not isinstance(item, dict):
                problemas.append(f"{chave}[{n}] deve ser um objeto com texto e commits")
                continue
            texto = item.get("texto")
            if not isinstance(texto, str):
                problemas.append(f"{chave}[{n}]: texto deve ser texto")
            elif not limpar(texto):
                problemas.append(f"{chave}[{n}]: texto vazio")
            refs = _lista(item.get("commits"))
            if not isinstance(refs, list):
                problemas.append(f"{chave}[{n}]: commits deve ser uma lista")
                continue
            if not refs:
                problemas.append(f"{chave}[{n}]: item sem commits")
            for ref in refs:
                h, erro = _resolver(ref, hashes)
                if erro:
                    problemas.append(f"{chave}[{n}]: hash {erro}: {ref!r}")
                else:
                    em_itens.add(h)

    em_sem_item = set()
    sem_item = _lista(mudancas.get("sem_item"))
    if not isinstance(sem_item, list):
        problemas.append("sem_item deve ser uma lista")
        sem_item = []
    for n, s in enumerate(sem_item, 1):
        if not isinstance(s, dict):
            problemas.append(f"sem_item[{n}] deve ser um objeto com hash e motivo")
            continue
        h, erro = _resolver(s.get("hash"), hashes)
        if erro:
            problemas.append(f"sem_item[{n}]: hash {erro}: {s.get('hash')!r}")
            continue
        if not limpar(s.get("motivo")):
            problemas.append(f"sem_item[{n}]: motivo vazio")
        em_sem_item.add(h)

    passos = _lista(mudancas.get("como_testar"))
    if not isinstance(passos, list) or not all(isinstance(p, str) for p in passos):
        problemas.append("como_testar deve ser uma lista de textos")

    for h in sorted(em_itens & em_sem_item):
        problemas.append(f"commit {h[:HASH_MIN]} está num item e em sem_item")
    for c in fatos.get("commits", []):
        if c["hash"] not in em_itens | em_sem_item:
            problemas.append(f"commit esquecido: {c['hash'][:HASH_MIN]} {c.get('assunto', '')}")

    provavel = bool((fatos.get("hotfix") or {}).get("provavel"))
    hotfix = mudancas.get("hotfix")
    if hotfix is not None:
        if not isinstance(hotfix, dict):
            problemas.append("hotfix deve ser um objeto com causa, impacto e rollback")
        else:
            for campo in CAMPOS_HOTFIX:
                valor = hotfix.get(campo)
                if valor is not None and not isinstance(valor, str):
                    problemas.append(f"hotfix.{campo} deve ser texto ou null")
    if provavel and hotfix is None:
        problemas.append("hotfix obrigatório: fatos indicam hotfix (use null nos campos sem evidência)")
    if not provavel and hotfix is not None:
        problemas.append("hotfix não permitido: fatos não indicam hotfix")
    return problemas


ROTULOS = {
    "pt": {"resumo": "Resumo", "hotfix": "Hotfix", "novas": "Novas funcionalidades",
           "ajustes": "Ajustes", "correcoes": "Correções", "removido": "Removido",
           "seguranca": "Segurança", "interno": "Interno", "como_testar": "Como testar",
           "causa": "Causa", "impacto": "Impacto", "rollback": "Rollback", "preencher": "preencher"},
    "en": {"resumo": "Summary", "hotfix": "Hotfix", "novas": "New features",
           "ajustes": "Changes", "correcoes": "Fixes", "removido": "Removed",
           "seguranca": "Security", "interno": "Internal", "como_testar": "How to test",
           "causa": "Root cause", "impacto": "Impact", "rollback": "Rollback", "preencher": "fill in"},
}
# Início que tiraria o resumo de dentro do parágrafo: título, HTML (um "<!--" sem fechar vira
# comentário que engole o resto do PR) ou bloco de código que não termina.
_INICIO_DE_BLOCO = re.compile(r"^(#|<|```|~~~)")


def _paragrafo(texto: str) -> str:
    return "\\" + texto if _INICIO_DE_BLOCO.match(texto) else texto


def _bloco_hotfix(hotfix, r: dict) -> list:
    """Campo sem evidência vira comentário: lembra no editor, some no GitHub.

    Com os três vazios, o título entra no comentário também — senão sobraria um
    "## Hotfix" sem nada embaixo no PR colado sem preencher.
    """
    campos = [(r[k], limpar((hotfix or {}).get(k))) for k in CAMPOS_HOTFIX]
    if not any(valor for _, valor in campos):
        return [f"<!-- {r['preencher']}:", f"## {r['hotfix']}", ""] + \
               [f"**{rotulo}:**" for rotulo, _ in campos] + ["-->", ""]
    linhas = [f"## {r['hotfix']}", ""]
    for rotulo, valor in campos:
        linhas.append(f"**{rotulo}:** {valor}" if valor else f"<!-- {r['preencher']}: **{rotulo}:** -->")
        linhas.append("")
    return linhas


def montar(fatos: dict, mudancas: dict) -> str:
    """Markdown final. Ordem e títulos fixos; o agente só fornece o conteúdo."""
    r = ROTULOS[mudancas["idioma"]]
    linhas = [f"# {limpar_titulo(mudancas['titulo'])}", "",
              f"## {r['resumo']}", "", _paragrafo(limpar(mudancas["resumo"])), ""]

    if (fatos.get("hotfix") or {}).get("provavel"):
        linhas += _bloco_hotfix(mudancas.get("hotfix"), r)

    secoes = mudancas.get("secoes") or {}
    for chave in SECOES:
        itens = [limpar(item["texto"]) for item in secoes.get(chave) or []]
        if itens:
            linhas += [f"## {r[chave]}", ""] + [f"- {t}" for t in itens] + [""]

    passos = [p for p in (limpar(x) for x in mudancas.get("como_testar") or []) if p]
    if passos:
        linhas += [f"## {r['como_testar']}", ""] + [f"{n}. {p}" for n, p in enumerate(passos, 1)] + [""]

    return "\n".join(linhas).rstrip("\n") + "\n"


def gravar(repo: Path, texto: str):
    """Grava o PR-MESSAGE.md na raiz e o protege pelo info/exclude. Devolve (destino, avisos).

    Quem chama garante que o destino não é link simbólico (ver main).
    """
    topo = Path(git(["rev-parse", "--show-toplevel"], repo).strip())
    destino = topo / "PR-MESSAGE.md"
    pasta = caminho_git(repo, "sw-pr-message")
    pasta.mkdir(parents=True, exist_ok=True)
    # compara bytes: um anterior que não seja UTF-8 também merece ser preservado
    if destino.exists() and destino.read_bytes() != texto.encode("utf-8"):
        shutil.copyfile(destino, pasta / "PR-MESSAGE.anterior.md")
    destino.write_text(texto, encoding="utf-8")

    # --git-path: em worktree aponta o exclude do diretório comum, que é o que o git lê
    exclude = caminho_git(repo, "info/exclude")
    exclude.parent.mkdir(parents=True, exist_ok=True)
    atual = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if "/PR-MESSAGE.md" not in atual.splitlines():
        separador = "" if not atual or atual.endswith("\n") else "\n"
        exclude.write_text(f"{atual}{separador}/PR-MESSAGE.md\n", encoding="utf-8")

    avisos = []
    if git_ok(["ls-files", "--error-unmatch", "--", "PR-MESSAGE.md"], topo):
        avisos.append("PR-MESSAGE.md é versionado neste repositório: o info/exclude "
                      "não impede que ele entre num commit.")
    return destino, avisos


def _recusar(problemas) -> int:
    print("mudancas.json recusado — corrija todos os itens e rode de novo:", file=sys.stderr)
    for p in problemas:
        print(f"  - {p}", file=sys.stderr)
    return EXIT_RECUSA


def _ambiente(mensagem: str) -> int:
    print(mensagem, file=sys.stderr)
    return EXIT_AMBIENTE


def _branch_atual(repo):
    if not git_ok(["symbolic-ref", "-q", "HEAD"], repo):
        return None
    return git(["symbolic-ref", "-q", "--short", "HEAD"], repo).strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Valida o mudancas.json e grava o PR-MESSAGE.md.")
    ap.add_argument("--repo", default=".", help="repositório (padrão: diretório atual)")
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    if not repo.is_dir():
        return _ambiente(f"--repo {repo} não existe.")

    try:
        pasta = caminho_git(repo, "sw-pr-message")
        topo = Path(git(["rev-parse", "--show-toplevel"], repo).strip())
    except GitFalhou:
        return _ambiente("Não é um repositório git.")

    # --- ambiente primeiro: com ele errado, corrigir o mudancas.json não adiantaria
    arq_fatos, arq_mudancas = pasta / "fatos.json", pasta / "mudancas.json"
    if not arq_fatos.exists():
        return _ambiente(f"fatos.json não encontrado em {arq_fatos} — rode collect.py antes.")
    try:
        fatos = json.loads(arq_fatos.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        fatos = None
    if not isinstance(fatos, dict) or not isinstance(fatos.get("commits"), list):
        return _ambiente("fatos.json ilegível — rode collect.py de novo.")
    atual = _branch_atual(repo)
    if fatos.get("branch") != atual:
        # sem isto, a mensagem de uma branch seria gravada com sucesso estando em outra
        return _ambiente(f"fatos.json é da branch '{fatos.get('branch')}', mas você está em '{atual}' "
                         "— rode collect.py de novo.")
    if (topo / "PR-MESSAGE.md").is_symlink():
        # um link versionado apontando para fora faria o render sobrescrever qualquer arquivo
        return _ambiente("PR-MESSAGE.md é um link simbólico: não escrevo através dele, porque pode apontar "
                         "para fora do repositório. Remova o link e rode de novo.")

    # --- conteúdo
    if not arq_mudancas.exists():
        return _recusar([f"mudancas.json não encontrado em {arq_mudancas}"])
    try:
        mudancas = json.loads(arq_mudancas.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as erro:
        return _recusar([f"JSON malformado em mudancas.json: {erro}"])
    if not isinstance(mudancas, dict):
        return _recusar(["mudancas.json deve ser um objeto JSON"])

    problemas = validar(fatos, mudancas)
    if problemas:
        return _recusar(problemas)

    destino, avisos = gravar(repo, montar(fatos, mudancas))
    print(f"PR-MESSAGE.md gravado em {destino}")
    for aviso in avisos:
        print(f"aviso: {aviso}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
