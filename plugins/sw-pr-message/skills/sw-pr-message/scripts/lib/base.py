"""Pré-checagens e detecção da branch base (spec, seção "Detecção da base")."""
from lib.gitcmd import MIN_VERSAO, GitFalhou, caminho_git, git, git_ok, validar_ref, versao

CANDIDATOS = ("develop", "main", "master", "trunk", "staging")
DESEMPATE = ("main", "master")


class Parada(Exception):
    """Condição em que a coleta para (exit 2) com uma mensagem que diz o que fazer."""


def branch_atual(repo) -> str:
    if not git_ok(["symbolic-ref", "-q", "HEAD"], repo):
        raise Parada("HEAD destacado: faça checkout da branch que quer descrever.")
    return git(["symbolic-ref", "-q", "--short", "HEAD"], repo).strip()


def branch_padrao(repo):
    """Nome da branch padrão por origin/HEAD, ou None — repo criado com init + push não o tem."""
    if not git_ok(["symbolic-ref", "-q", "refs/remotes/origin/HEAD"], repo):
        return None
    nome = git(["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"], repo).strip()
    return nome.split("/", 1)[1] if nome.startswith("origin/") else nome


def refs_de(nome):
    """Refs completas: o git resolve tag antes de branch, então uma tag `main` se passaria pela branch."""
    return (f"refs/heads/{nome}", f"refs/remotes/origin/{nome}")


def curta(ref: str) -> str:
    """Forma de exibição: refs/heads/develop → develop; refs/remotes/origin/develop → origin/develop."""
    for prefixo in ("refs/heads/", "refs/remotes/"):
        if ref.startswith(prefixo):
            return ref[len(prefixo):]
    return ref


def ref_existe(repo, ref) -> bool:
    # O `--` final importa: sem ele, arquivo ou pasta com o mesmo nome deixa o argumento ambíguo,
    # o git falha, e a branch pareceria não existir — sumindo das candidatas sem aviso.
    return git_ok(["rev-list", "--max-count=0", "--end-of-options", validar_ref(ref), "--"], repo)


def existe(repo, nome) -> bool:
    return any(ref_existe(repo, r) for r in refs_de(nome))


def contar(repo, ref) -> int:
    saida = git(["rev-list", "--count", "--no-merges", "--end-of-options",
                 f"{validar_ref(ref)}..HEAD", "--"], repo)
    return int(saida.strip())


def melhor_ref(repo, nome):
    """(contagem, ref completa) da menor entre a branch local e a de origin; None se nenhuma existe.

    Com o develop local atrasado, o local contaria commits que já estão no remoto.
    """
    opcoes = [(contar(repo, r), r) for r in refs_de(nome) if ref_existe(repo, r)]
    return min(opcoes) if opcoes else None


def pre_checar(repo, tem_base: bool) -> str:
    """Devolve a branch atual se tudo estiver certo; senão levanta Parada."""
    try:
        # bare e o próprio .git respondem "false" com código 0: é preciso ler a saída
        dentro = git(["rev-parse", "--is-inside-work-tree"], repo).strip() == "true"
    except GitFalhou:
        dentro = False
    if not dentro:
        raise Parada("Não é um repositório git com working tree.")
    if versao(repo) < MIN_VERSAO:
        raise Parada(f"git {MIN_VERSAO[0]}.{MIN_VERSAO[1]} ou mais novo é necessário.")
    if git(["rev-parse", "--is-shallow-repository"], repo).strip() == "true":
        raise Parada("Clone raso: as contagens de commits ficariam erradas. Rode `git fetch --unshallow` antes.")
    pack = caminho_git(repo, "objects/pack")
    if pack.is_dir() and any(pack.glob("*.promisor")):
        # o diff buscaria do remoto os arquivos que faltam: rede e escrita em .git/objects
        raise Parada("Clone parcial: o diff precisaria baixar arquivos do remoto, e esta skill não usa a rede. "
                     "Rode num clone completo.")
    # antes do HEAD destacado: durante um rebase o HEAD também fica destacado
    for pasta in ("rebase-merge", "rebase-apply"):
        if caminho_git(repo, pasta).exists():
            raise Parada("Rebase em andamento: termine ou aborte o rebase antes.")
    atual = branch_atual(repo)
    if not tem_base:
        # sem --base, estar numa base faria a heurística descrever a base inteira contra outra
        nomes = set(CANDIDATOS) | ({branch_padrao(repo)} - {None})
        if atual in nomes:
            raise Parada(f"Você está em '{atual}', que é uma branch base. Faça checkout da branch de "
                         f"trabalho, ou informe --base para descrever '{atual}' contra outra branch.")
    return atual


def _contagens(contagens: dict) -> str:
    return " · ".join(f"{n}: {c}" for n, c in sorted(contagens.items(), key=lambda kv: (kv[1], kv[0])))


def detectar_base(repo, base=None) -> dict:
    if base is not None:
        validar_ref(base)
        nome = base[len("origin/"):] if base.startswith("origin/") else base
        melhor = melhor_ref(repo, nome)
        if melhor is None:
            raise Parada(f"A base '{base}' não existe localmente (nem como origin/{nome}).")
        contagem, ref = melhor
        if contagem == 0:
            raise Parada(f"A branch não tem commits à frente de '{curta(ref)}': nada para descrever.")
        return {"nome": nome, "ref": ref, "como": "informada", "a_frente": contagem,
                "candidatas": {nome: contagem}, "empate": []}

    padrao = branch_padrao(repo)
    nomes = list(CANDIDATOS) + ([padrao] if padrao and padrao not in CANDIDATOS else [])
    contagens, refs = {}, {}
    for nome in nomes:
        melhor = melhor_ref(repo, nome)
        if melhor:
            contagens[nome], refs[nome] = melhor
    if not contagens:
        raise Parada("Nenhuma branch base conhecida (develop, main, master, trunk, staging). Informe --base.")

    zerados = sorted(n for n, c in contagens.items() if c == 0)
    if zerados:
        positivos = {n: c for n, c in contagens.items() if c > 0}
        sugestao = (f" → rode com --base {min(positivos, key=lambda n: (positivos[n], n))}"
                    if positivos else "")
        raise Parada(f"{', '.join(zerados)} já contém a branch · {_contagens(contagens)}{sugestao}")

    menor = min(contagens.values())
    empatados = sorted(n for n, c in contagens.items() if c == menor)
    if len(empatados) == 1:
        escolhido = empatados[0]
    elif padrao in empatados:
        escolhido = padrao
    else:
        escolhido = next((n for n in DESEMPATE if n in empatados), None)
        if escolhido is None:
            raise Parada(f"Empate entre {', '.join(empatados)} · {_contagens(contagens)} → informe --base.")
    return {"nome": escolhido, "ref": refs[escolhido], "como": "heuristica",
            "a_frente": contagens[escolhido], "candidatas": contagens,
            # o conteúdo é o mesmo para todos os empatados (mesmo merge-base); só o rótulo muda
            "empate": empatados if len(empatados) > 1 else []}
