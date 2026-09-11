"""Coleta dos fatos: commits sem merge, arquivos com ruído e corte, sinais de hotfix, avisos."""
import fnmatch
import re

from lib.gitcmd import git, git_ok, validar_ref

TETO_LINHAS = 400          # por arquivo, linhas do patch
TETO_BYTES = 60_000        # conteúdo total — calibrado em referencias/calibracao-do-diff.md

_LOCKS = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "composer.lock", "Gemfile.lock",
          "poetry.lock", "Cargo.lock", "go.sum"}
_DIRS_RUIDO = {"dist", "build", "vendor", "node_modules", ".next", "coverage"}
_GLOBS_RUIDO = ("*.lock", "*.min.js", "*.min.css", "*.map", "*.snap")
_TIPO = re.compile(r"^(?P<tipo>[a-zA-Z]+)(\((?P<escopo>[^)]*)\))?!?:\s")
# Só "\n" é quebra de linha para o git; str.splitlines() também quebraria em \f, \x1c–\x1e e U+2028.
_LINHA = re.compile(r"[^\n]*\n|[^\n]+$")


def eh_ruido(caminho: str) -> bool:
    partes = caminho.split("/")
    nome = partes[-1]
    return (nome in _LOCKS
            or any(p in _DIRS_RUIDO for p in partes[:-1])
            or any(fnmatch.fnmatch(nome, g) for g in _GLOBS_RUIDO))


def tipo_escopo(assunto: str):
    m = _TIPO.match(assunto or "")
    return (m.group("tipo").lower(), m.group("escopo")) if m else (None, None)


def commits(repo, base_ref: str) -> list:
    # NUL entre campos e entre commits: é o único byte que o git recusa numa mensagem. Com outro
    # separador, uma mensagem que o contivesse forjaria commits que não existem.
    saida = git(["log", "-z", "--no-merges", "--reverse", "--format=%H%x00%s%x00%b",
                 "--end-of-options", f"{validar_ref(base_ref)}..HEAD", "--"], repo)
    campos = saida.split("\0")
    lista = []
    for i in range(0, len(campos) // 3 * 3, 3):
        h, assunto, corpo = campos[i:i + 3]
        tipo, escopo = tipo_escopo(assunto)
        lista.append({"hash": h.strip(), "tipo": tipo, "escopo": escopo,
                      "assunto": assunto, "corpo": corpo.strip()})
    return lista


def merges_ignorados(repo, base_ref: str) -> int:
    saida = git(["rev-list", "--count", "--merges", "--end-of-options",
                 f"{validar_ref(base_ref)}..HEAD", "--"], repo)
    return int(saida.strip())


def numstat(repo, base_ref: str) -> list:
    """Arquivos alterados desde o merge-base, em ordem de caminho.

    Com -z o caminho vem sem aspas de core.quotepath, e renomeação chega como
    "mais<TAB>menos<TAB>" seguido de dois tokens: caminho antigo e caminho novo.
    """
    tokens = git(["diff", "--numstat", "-z", "--end-of-options",
                  f"{validar_ref(base_ref)}...HEAD", "--"], repo).split("\0")
    arquivos, i = [], 0
    while i < len(tokens):
        if not tokens[i]:
            i += 1
            continue
        mais, menos, caminho = tokens[i].split("\t", 2)
        anterior = None
        if caminho == "":
            anterior, caminho = tokens[i + 1], tokens[i + 2]
            i += 3
        else:
            i += 1
        binario = mais == "-"
        arquivos.append({"caminho": caminho, "anterior": anterior,
                         "mais": 0 if binario else int(mais), "menos": 0 if binario else int(menos),
                         "binario": binario, "ruido": binario or eh_ruido(caminho),
                         "cortado": False, "diff": ""})
    return sorted(arquivos, key=lambda a: a["caminho"])


def preencher_diffs(repo, base_ref: str, arquivos: list, teto_linhas=TETO_LINHAS, teto_bytes=TETO_BYTES) -> None:
    """Pequenos entram inteiros; grandes recebem o que sobrar do orçamento e ficam marcados."""
    validar_ref(base_ref)
    orcamento = teto_bytes
    for a in sorted((x for x in arquivos if not x["ruido"]), key=lambda x: (x["mais"] + x["menos"], x["caminho"])):
        # renomeação: só o caminho novo faria o git mostrar o arquivo inteiro como adicionado
        caminhos = [a["anterior"], a["caminho"]] if a["anterior"] else [a["caminho"]]
        # :(literal) — sem ele o caminho é glob: o diff de `[id].tsx` traria `i.tsx`, `:foo` traria
        # `foo`; e um arquivo chamado `--output.txt` seria recusado como opção
        patch = git(["diff", "--end-of-options", f"{base_ref}...HEAD", "--",
                     *(f":(literal){c}" for c in caminhos)], repo)
        linhas = _LINHA.findall(patch)
        if len(linhas) > teto_linhas:
            linhas, a["cortado"] = linhas[:teto_linhas], True
        dados = "".join(linhas).encode("utf-8")
        if len(dados) > orcamento:
            dados, a["cortado"] = dados[:max(orcamento, 0)], True
        a["diff"] = dados.decode("utf-8", "ignore")
        orcamento -= len(a["diff"].encode("utf-8"))


def sinais_hotfix(branch: str, lista_commits: list, base_nome: str, tem_develop: bool,
                  develop_empata: bool = False) -> dict:
    sinais = []
    if branch.startswith("hotfix/"):
        sinais.append("branch hotfix/")
    if any(c.get("tipo") == "hotfix" for c in lista_commits):
        sinais.append("commit do tipo hotfix")
    # Sem develop, toda branch de correção sai de master e o sinal não distingue nada. E com
    # develop empatando (git-flow: branch criada antes do último release conta igual contra os
    # dois), a base "master" é só o desempate — não uma correção saindo de produção.
    if (tem_develop and not develop_empata and base_nome in ("main", "master") and lista_commits
            and all(c.get("tipo") == "fix" for c in lista_commits)):
        sinais.append("só correções saindo direto de main/master")
    return {"provavel": bool(sinais), "sinais": sinais}


def avisos(repo) -> list:
    """Só o que dá para saber sem ler o working tree.

    `git status` ficou de fora de propósito: para comparar conteúdo ele executa os filtros de
    limpeza configurados (filter.<x>.clean), e um repositório recebido pode trazer um malicioso.
    """
    lista = []
    if git_ok(["ls-files", "--error-unmatch", "--", "PR-MESSAGE.md"], repo):
        lista.append("pr_message_versionado")
    return lista
