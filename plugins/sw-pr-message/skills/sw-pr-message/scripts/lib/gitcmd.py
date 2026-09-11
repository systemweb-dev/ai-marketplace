"""Único ponto que executa git nesta skill.

Lista fechada de subcomandos de leitura, recusa de argumentos perigosos por prefixo e defesas
forçadas contra configuração do repositório analisado. Tudo é validado ANTES de executar.
"""
import os
import re
import subprocess
from pathlib import Path

MIN_VERSAO = (2, 31)   # GIT_CONFIG_COUNT (ver ambiente()) existe a partir da 2.31

# Sem `status`: para comparar conteúdo do working tree ele executa os filtros de limpeza
# configurados (filter.<x>.clean), e nenhuma variável de ambiente desliga isso.
SUBCOMANDOS = frozenset({"log", "diff", "rev-list", "rev-parse", "for-each-ref", "merge-base",
                         "ls-files", "symbolic-ref", "version"})
# Por prefixo: `--output=/x` escreve arquivo tanto quanto `--output /x`. Os três últimos
# religariam, se passados depois, o que DEFESAS desliga (a última opção vence no git).
PREFIXOS_PROIBIDOS = ("--output", "--no-index", "--ext-diff",
                      "--textconv", "--show-signature", "--submodule")
# Logo após o subcomando, sempre: o repositório analisado pode ter conversores, diff externo
# ou verificação de assinatura configurados — todos executariam programas. `--submodule=short`
# impede o git de abrir um diff filho dentro do submódulo, que não herdaria estas defesas e
# rodaria o diff externo configurado lá.
DEFESAS = {
    "diff": ["--no-ext-diff", "--no-textconv", "--no-color", "--submodule=short"],
    "log": ["--no-ext-diff", "--no-textconv", "--no-color", "--no-show-signature", "--submodule=short"],
}
# Vêm do ambiente de quem roda: desviariam a leitura para outro repositório (GIT_DIR) ou
# religariam configuração que ambiente() desliga (GIT_CONFIG_PARAMETERS vence GIT_CONFIG_COUNT).
_HERDADAS_DESCARTADAS = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                                   "GIT_CONFIG_PARAMETERS", "GIT_EXTERNAL_DIFF"})
_FLAGS_SYMREF = frozenset({"-q", "--quiet", "--short"})


class GitRecusado(Exception):
    """Comando recusado antes de executar."""


class GitFalhou(Exception):
    def __init__(self, argv, codigo, stderr):
        super().__init__(f"git falhou ({codigo}): {' '.join(argv)}\n{stderr.strip()}")
        self.argv, self.codigo, self.stderr = argv, codigo, stderr


def validar_ref(ref) -> str:
    """Ref vinda de fora (--base, gh): não pode se passar por opção."""
    if not isinstance(ref, str) or not ref.strip():
        raise GitRecusado("ref vazia")
    if ref.startswith("-"):
        raise GitRecusado(f"ref não pode começar com '-': {ref!r}")
    return ref


def montar_argv(args) -> list:
    """Valida e devolve o argv final. Não executa nada."""
    args = list(args)
    if not args or args[0] not in SUBCOMANDOS:
        raise GitRecusado(f"subcomando não permitido: {args[:1]!r} (nada é aceito antes do subcomando)")
    sub, resto = args[0], args[1:]
    for a in resto:
        if not isinstance(a, str):
            raise GitRecusado(f"argumento não textual: {a!r}")
        if a.startswith(PREFIXOS_PROIBIDOS):
            raise GitRecusado(f"argumento proibido: {a!r}")
    if sub == "symbolic-ref":
        posicionais = [a for a in resto if not a.startswith("-")]
        flags = [a for a in resto if a.startswith("-")]
        # com dois argumentos, symbolic-ref ESCREVE (git symbolic-ref HEAD refs/heads/x)
        if len(posicionais) != 1 or any(f not in _FLAGS_SYMREF for f in flags):
            raise GitRecusado(f"symbolic-ref só na forma de leitura: {resto!r}")
    if sub == "version" and resto:
        raise GitRecusado("version não aceita argumentos")
    return ["git", sub, *DEFESAS.get(sub, []), *resto]


def ambiente() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _HERDADAS_DESCARTADAS}
    env.update({
        "GIT_OPTIONAL_LOCKS": "0",               # nenhum comando atualiza o índice por conta própria
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.fsmonitor",
        "GIT_CONFIG_VALUE_0": "false",           # fsmonitor configurado executaria um programa
        "GIT_TERMINAL_PROMPT": "0",
        # Em clone parcial, o diff buscaria do remoto os arquivos que faltam: rede e escrita em
        # .git/objects. A pré-checagem já barra o caso; isto é a segunda barreira (git ≥ 2.44).
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_PAGER": "cat",
        "PAGER": "cat",
        "LC_ALL": "C",                           # mensagens estáveis
    })
    return env


def _executar(args, cwd):
    argv = montar_argv(args)
    return subprocess.run(argv, cwd=str(cwd), env=ambiente(), capture_output=True, check=False)


def git(args, cwd) -> str:
    r = _executar(args, cwd)
    if r.returncode != 0:
        raise GitFalhou(r.args, r.returncode, r.stderr.decode("utf-8", "replace"))
    return r.stdout.decode("utf-8", "replace")


def git_ok(args, cwd) -> bool:
    """Para comandos em que código diferente de zero é resposta, não erro."""
    return _executar(args, cwd).returncode == 0


def caminho_git(cwd, sub: str) -> Path:
    """Caminho dentro do diretório git — certo também em worktree e submódulo."""
    saida = git(["rev-parse", "--git-path", sub], cwd).strip()
    p = Path(saida)
    return p if p.is_absolute() else (Path(cwd) / p).resolve()


def versao(cwd=".") -> tuple:
    m = re.search(r"(\d+)\.(\d+)", git(["version"], cwd))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
