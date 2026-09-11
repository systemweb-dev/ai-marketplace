# sw-pr-message Implementation Plan

> Design aprovado: [`spec.md`](spec.md) · Evidência: [`referencias/`](referencias/)

> **Execucao:** Implementar este plano task-by-task. Steps usam checkbox (`- [ ]`) para tracking. Ver secao "Execution Handoff" da skill `sw-plan` para os 2 modos de execucao disponiveis.

**Goal:** Skill `sw-pr-message` que gera o `PR-MESSAGE.md` de uma branch, com mudanças agrupadas por tipo, base detectada corretamente e nenhum commit esquecido.

**Architecture:** `collect.py` detecta a base e coleta commits/diff em `fatos.json`; o agente escreve `mudancas.json`; `render.py` valida contra os fatos e monta o markdown com ordem, títulos e idioma fixos. Todo `git` passa por `lib/gitcmd.py`, que só aceita leitura.

**Tech Stack:** Python 3 (stdlib apenas nos scripts) · git ≥ 2.31 · pytest (só para desenvolvimento, num `.venv` local).

---

## Como executar este plano

- **A skill nasce em `~/.claude/skills/sw-pr-message/`, que não é repositório git.** Por isso as tasks
  não têm step de commit: cada task termina num **checkpoint** de aprovação. Commits só acontecem no
  marketplace, depois do sync (Tasks 11–13), sempre com o "sim" do usuário.
- **Rode tudo a partir da pasta da skill**, com o Python do `.venv`:
  `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest …`. O sync já exclui `.venv`,
  `__pycache__` e `.pytest_cache`.
- **O marketplace é público.** Nenhum nome de repositório, branch, arquivo ou commit de projeto real
  entra em código, teste, dossiê ou mensagem de commit.
- Ao iniciar: `cd /var/www/ai-marketplace && python3 ~/.claude/skills/sw-brainstorming/scripts/dossie.py estado 2026-09-10-sw-pr-message em-execucao`.

## Ajustes em relação ao spec (verificados com git 2.48 antes de planejar; spec já atualizado)

| Tema | Ajuste | Por quê |
|---|---|---|
| Versão mínima | git **≥ 2.31** (era 2.24) | `GIT_CONFIG_COUNT`, usado para desligar o fsmonitor, só existe a partir da 2.31 |
| Lista de subcomandos | `version` entra (sem argumentos) | `git --version` é opção antes do subcomando, proibida pela FF1 |
| Existência de ref | `rev-list --max-count=0 --end-of-options <ref>` | mantém `--end-of-options` sem depender do `rev-parse` |
| Diff de renomeação | passa `-- antigo novo` | só o caminho novo faz o git mostrar o arquivo inteiro como adicionado |
| Validação | também recusa item com `texto` vazio e `sem_item` com `motivo` vazio | item vazio passaria pela conferência de commits |
| Submódulo | `--submodule=short` forçado em `diff` e `log` | com `diff.submodule=diff` o diff filho no submódulo não herdava as defesas e rodava o diff externo de lá (juiz, Lote 1) |
| Argumentos | recusa também `--textconv`, `--show-signature` e `--submodule` | religariam, depois, o que as defesas desligam — a última opção vence (juiz, Lote 1) |
| Ambiente | descarta `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_CONFIG_PARAMETERS` e `GIT_EXTERNAL_DIFF` herdados | `GIT_DIR` desviava a leitura para outro repositório (juiz, Lote 1) |
| `git status` | **removido** da lista e da coleta: sem aviso de mudança não commitada, lembrete fixo no relatório | executa filtros de limpeza configurados; nenhuma variável desliga (decisão do usuário) |
| Refs da base | `refs/heads/<nome>` e `refs/remotes/origin/<nome>`, com `--` no fim do `rev-list` | tag homônima virava candidata; pasta `staging/` fazia a branch sumir por ambiguidade (juiz, Lote 2) |
| Empate | registrado em `base.empate` e mostrado no relatório; o 3º sinal de hotfix não dispara se `develop` empata | git-flow: branch anterior ao último release gerava hotfix falso (juiz, Lote 2; decisão do usuário) |
| Log | `log -z` com NUL entre campos | `\x1e`/`\x1f` na mensagem forjavam commits (juiz, Lote 2) |
| Caminho no diff | `:(literal)<caminho>` | `[id].tsx` trazia `i.tsx`; `--output.txt` derrubava a coleta (juiz, Lote 2) |
| Corte | conta só `\n` | `splitlines()` cortava arquivo com form feed abaixo do teto (juiz, Lote 2) |
| Pré-checagem | `--is-inside-work-tree` precisa responder `true` | repositório bare passava (juiz, Lote 2) |
| Validação de tipos | cada campo do `mudancas.json` tem o tipo conferido; erro vira problema listado | tipo errado dava traceback em vez de exit 3, e `como_testar` em texto saía uma letra por passo (juiz, Lote 3) |
| Texto do agente | uma linha só; resumo que começa com `#`, `<`, ` ``` `, `~~~` é escapado | quebra de linha criava seção falsa; `<!--` no resumo engolia o resto do PR (juiz, Lote 3) |
| Emoji | inclui os de apresentação fora dos blocos (⭐ ⏳ ✊) e o keycap `U+20E3` | escapavam, e o usuário pediu "sem emoji" (juiz, Lote 3) |
| Link simbólico | render recusa `PR-MESSAGE.md` que é link (exit 2) | link versionado apontando para fora fazia o render sobrescrever arquivo fora do repositório (juiz, Lote 4) |
| `fatos.json` | ilegível ou de outra branch → exit 2, "rode collect.py de novo" | corrompido dava traceback; de outra branch gravava a mensagem errada com sucesso (juiz, Lote 4) |
| Clone parcial | pré-checagem barra; `GIT_NO_LAZY_FETCH=1` como segunda barreira | o diff buscava arquivos do remoto e escrevia em `.git/objects` (juiz, Lote 4; decisão do usuário) |
| FF2 e FF3 | FF3 tira o retrato depois de preparar o repositório, sem lista de ignorados, com data de modificação, pastas e `chdir`; FF2 registra a tentativa; estáticas por árvore sintática | a FF3 ignorava `.git/refs`, `index` e `objects` e não pegava escrita neles (juiz, Lote 4) |
| Robustez | anterior comparado em bytes; `--repo` inexistente → exit 2 nos dois scripts | não-UTF-8 e diretório inexistente davam traceback (juiz, Lote 4) |
| `SKILL.md` | lembrete de commit de fato na última linha; linha `base:` e mensagem de base inexistente iguais às dos scripts; exit 2 do render sem mexer no `mudancas.json`; clone parcial nos limites | a versão anterior punha a "última linha" no meio da lista e citava mensagens que os scripts não imprimem (conferido antes de gravar, Lote 5) |
| Validação real | num clone temporário, não no repositório original | trocar a branch de um repositório de trabalho mexe no estado dele; o clone reproduz as mesmas refs (Lote 5) |
| `SKILL.md` (juiz, Lote 5) | base vinda do PR relatada como tal; onde rodar os scripts; nova coleta sem `--base` que também para; qualquer outro código de saída → mostra e para | a linha `base:` diz `informada` mesmo quando quem informou foi o `gh`; o resto eram lacunas de orientação |
| Nome de código entre crases | regra no `SKILL.md`, fora do spec | o GitHub some com `<Select>` solto; o render só escapa o início do resumo, então a proteção dentro do texto é do agente |

## Estrutura de arquivos

```
~/.claude/skills/sw-pr-message/
├── SKILL.md                      fluxo do agente (Task 9)
├── scripts/
│   ├── collect.py                pré-checagens + base + coleta → fatos.json (Task 4)
│   ├── render.py                 validação + montagem + gravação (Tasks 5–7)
│   └── lib/
│       ├── __init__.py
│       ├── gitcmd.py             único executor de git: lista fechada, recusas, defesas (Task 1)
│       ├── base.py               pré-checagens e detecção da base (Task 2)
│       └── coleta.py             commits, numstat, ruído, corte, hotfix, avisos (Task 3)
└── tests/                        sem __init__.py: o conftest põe scripts/ e tests/ no sys.path
    ├── conftest.py               sys.path + fixture `repo` + isolamento de config (Task 0)
    ├── gitrepo.py                repositórios git reais para teste (Task 0)
    ├── fluxo.py                  ajudantes de ponta a ponta (Task 7)
    ├── test_gitrepo.py           (Task 0)
    ├── test_gitcmd.py            FF1 (Task 1)
    ├── test_base.py              (Task 2)
    ├── test_coleta.py            (Task 3)
    ├── test_collect.py           (Task 4)
    ├── test_render_validar.py    (Task 5)
    ├── test_render_montar.py     FF4 (Task 6)
    ├── test_render_gravar.py     (Task 7)
    └── test_fitness.py           FF1 estática, FF2, FF3 (Task 8)
```

---

### Task 0: Ambiente e ajudantes de teste

**Files:**
- Create: `~/.claude/skills/sw-pr-message/scripts/lib/__init__.py` (vazio)
- Create: `~/.claude/skills/sw-pr-message/tests/conftest.py`
- Create: `~/.claude/skills/sw-pr-message/tests/gitrepo.py`
- Test: `~/.claude/skills/sw-pr-message/tests/test_gitrepo.py`

- [x] **Step 1: Marcar o dossiê em execução**

Run: `cd /var/www/ai-marketplace && python3 ~/.claude/skills/sw-brainstorming/scripts/dossie.py estado 2026-09-10-sw-pr-message em-execucao`
Expected: `2026-09-10-sw-pr-message → em-execucao`

- [x] **Step 2: Criar pastas e o ambiente de teste**

Run:
```bash
mkdir -p ~/.claude/skills/sw-pr-message/scripts/lib ~/.claude/skills/sw-pr-message/tests
touch ~/.claude/skills/sw-pr-message/scripts/lib/__init__.py
cd ~/.claude/skills/sw-pr-message && python3 -m venv .venv && .venv/bin/pip install -q pytest
.venv/bin/python -m pytest --version
git --version
```
Expected: `pytest 8.x` (ou maior) e `git version 2.31` ou maior.

- [x] **Step 3: Escrever `tests/conftest.py`**

```python
"""Deixa `import collect`, `import render`, `import lib.x` e os ajudantes de teste funcionarem."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gitrepo import Repo  # noqa: E402


@pytest.fixture(autouse=True)
def _git_isolado(monkeypatch):
    """Os scripts sob teste herdam o ambiente: sem isto, a config global de quem roda vazaria."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repo(tmp_path):
    """Repositório novo na branch master com um commit inicial."""
    return Repo.novo(tmp_path / "repo")
```

- [x] **Step 4: Escrever `tests/gitrepo.py`**

```python
"""Repositórios git de verdade para os testes — isolados da configuração de quem roda."""
import os
import subprocess
from pathlib import Path

ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,      # sem config global (assinatura, hooks, aliases)
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Teste", "GIT_AUTHOR_EMAIL": "teste@example.com",
    "GIT_COMMITTER_NAME": "Teste", "GIT_COMMITTER_EMAIL": "teste@example.com",
    "GIT_EDITOR": "true",                 # rebase com conflito não abre editor
    "GIT_TERMINAL_PROMPT": "0",
}


class Repo:
    def __init__(self, path):
        self.path = Path(path)
        self._n = 0

    @classmethod
    def novo(cls, path):
        path = Path(path)
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "master", str(path)], env=ENV, check=True)
        r = cls(path)
        r.commit("chore: inicial", {"README.md": "inicial\n"})
        return r

    def git(self, *args, check=True) -> str:
        r = subprocess.run(["git", *args], cwd=self.path, env=ENV, capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} falhou: {r.stderr}")
        return r.stdout

    def commit(self, mensagem, arquivos=None) -> str:
        """Escreve os arquivos (str ou bytes), faz add de tudo e commita. Devolve o hash."""
        if arquivos is None:
            self._n += 1
            arquivos = {f"arquivo_{self._n}.txt": f"conteúdo {self._n}\n"}
        for nome, conteudo in arquivos.items():
            destino = self.path / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(conteudo, bytes):
                destino.write_bytes(conteudo)
            else:
                destino.write_text(conteudo, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", mensagem)
        return self.sha()

    def branch(self, nome, de=None):
        """Cria a branch (a partir de `de`, ou do HEAD) e faz checkout."""
        self.git("checkout", "-q", "-b", nome, *([de] if de else []))

    def checkout(self, ref):
        self.git("checkout", "-q", ref)

    def merge(self, ref, mensagem=None):
        self.git("merge", "-q", "--no-ff", "-m", mensagem or f"Merge {ref}", ref)

    def ref_remota(self, nome, ref="HEAD"):
        """Cria origin/<nome> sem rede: é só uma ref local em refs/remotes."""
        self.git("update-ref", f"refs/remotes/origin/{nome}", self.sha(ref))

    def origin_head(self, nome):
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{nome}")

    def sha(self, ref="HEAD") -> str:
        return self.git("rev-parse", ref).strip()
```

- [x] **Step 5: Escrever `tests/test_gitrepo.py`**

Confere só o que os outros testes assumem do ajudante — se isto falhar, todo o resto falharia por motivo errado.

```python
def test_repo_novo_nasce_em_master_com_um_commit(repo):
    assert repo.git("branch", "--show-current").strip() == "master"
    assert repo.git("rev-list", "--count", "HEAD").strip() == "1"


def test_ref_remota_e_origin_head_sem_rede(repo):
    repo.ref_remota("master")
    repo.origin_head("master")

    assert repo.git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip() == "origin/master"
```

- [x] **Step 6: Rodar**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_gitrepo.py -q`
Expected: `2 passed`

- [x] **Step 7: Checkpoint** — pausa de aprovação.

---

### Task 1: `lib/gitcmd.py` — único executor de git (FF1)

**Files:**
- Create: `~/.claude/skills/sw-pr-message/scripts/lib/gitcmd.py`
- Test: `~/.claude/skills/sw-pr-message/tests/test_gitcmd.py`

- [x] **Step 1: Escrever os testes que falham**

`tests/test_gitcmd.py`:

```python
from pathlib import Path

import pytest

from gitrepo import Repo
from lib import gitcmd
from lib.gitcmd import (MIN_VERSAO, GitFalhou, GitRecusado, ambiente, caminho_git, git, git_ok,
                        montar_argv, validar_ref, versao)


@pytest.fixture
def sem_execucao(monkeypatch):
    """Qualquer tentativa de executar processo falha o teste: a recusa tem que vir antes."""
    def proibido(*args, **kwargs):
        raise AssertionError(f"executou processo: {args}")
    monkeypatch.setattr(gitcmd.subprocess, "run", proibido)


@pytest.mark.parametrize("args", [
    ["push"], ["config", "user.name", "x"], ["-c", "core.pager=cat", "log"],
    ["--exec-path=/tmp", "log"], ["update-ref", "refs/heads/x", "HEAD"], [],
    ["status", "--porcelain"],  # para comparar conteúdo, executaria filtros de limpeza da config
])
def test_recusa_subcomando_fora_da_lista_e_opcao_antes_dele(args, sem_execucao):
    with pytest.raises(GitRecusado):
        git(args, ".")


@pytest.mark.parametrize("args", [
    ["diff", "--output=/tmp/x"], ["log", "--output", "/tmp/x"], ["diff", "--no-index", "a", "b"],
    ["diff", "--ext-diff"], ["log", "--end-of-options", "--output=/tmp/x..HEAD"],
    ["diff", "--end-of-options", "--output=/tmp/x...HEAD"],
    # reativariam, depois das defesas, o que elas desligam
    ["diff", "--textconv"], ["log", "--show-signature"], ["diff", "--submodule=diff"],
])
def test_recusa_argumento_proibido_por_prefixo_em_qualquer_posicao(args, sem_execucao):
    with pytest.raises(GitRecusado):
        git(args, ".")


@pytest.mark.parametrize("args", [
    ["symbolic-ref", "HEAD", "refs/heads/novo"], ["symbolic-ref", "-d", "HEAD"],
    ["symbolic-ref", "-m", "msg", "HEAD", "refs/heads/x"], ["symbolic-ref"],
])
def test_symbolic_ref_so_na_forma_de_leitura(args, sem_execucao):
    with pytest.raises(GitRecusado):
        git(args, ".")


def test_version_nao_aceita_argumentos(sem_execucao):
    with pytest.raises(GitRecusado):
        git(["version", "--build-options"], ".")


@pytest.mark.parametrize("ref", ["-x", "--output=/tmp/x", "", "   "])
def test_ref_externa_que_parece_opcao_e_recusada(ref):
    with pytest.raises(GitRecusado):
        validar_ref(ref)


def test_ref_externa_normal_passa():
    assert validar_ref("origin/develop") == "origin/develop"


def test_defesas_sao_injetadas_logo_apos_o_subcomando():
    assert montar_argv(["diff", "--numstat"]) == \
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--submodule=short", "--numstat"]
    assert montar_argv(["log", "--oneline"])[:7] == \
        ["git", "log", "--no-ext-diff", "--no-textconv", "--no-color", "--no-show-signature", "--submodule=short"]
    assert montar_argv(["symbolic-ref", "-q", "--short", "HEAD"]) == \
        ["git", "symbolic-ref", "-q", "--short", "HEAD"]


def test_ambiente_desliga_locks_opcionais_e_fsmonitor():
    env = ambiente()

    assert env["GIT_OPTIONAL_LOCKS"] == "0"
    assert (env["GIT_CONFIG_COUNT"], env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]) == \
        ("1", "core.fsmonitor", "false")


def test_ambiente_descarta_variaveis_herdadas_que_desviariam_o_git(repo, tmp_path, monkeypatch):
    outro = Repo.novo(tmp_path / "outro")
    monkeypatch.setenv("GIT_DIR", str(outro.path / ".git"))
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'core.fsmonitor'='false'")

    env = ambiente()
    git_dir = Path(git(["rev-parse", "--absolute-git-dir"], repo.path).strip())

    herdadas = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_PARAMETERS", "GIT_EXTERNAL_DIFF"}
    assert herdadas.isdisjoint(env)
    # prova que o ambiente limpo chega ao processo: com GIT_DIR herdado, leria o outro repo
    assert git_dir == (repo.path / ".git").resolve()


def test_submodulo_nao_executa_diff_externo_da_config(repo, tmp_path):
    marca = tmp_path / "rodou"
    script = tmp_path / "ext.sh"
    script.write_text(f"#!/bin/sh\ntouch '{marca}'\n", encoding="utf-8")
    script.chmod(0o755)
    origem = Repo.novo(tmp_path / "origem-do-sub")
    permitir = ("-c", "protocol.file.allow=always")
    repo.git(*permitir, "submodule", "add", "-q", str(origem.path), "sub")
    repo.git("commit", "-q", "-m", "chore: submódulo")
    origem.commit("feat: muda o submódulo")
    repo.git(*permitir, "submodule", "update", "--remote", "-q", "sub")
    repo.git("commit", "-qam", "chore: atualiza submódulo")
    repo.git("config", "diff.submodule", "diff")
    Repo(repo.path / "sub").git("config", "diff.external", str(script))

    git(["diff", "--end-of-options", "HEAD~1...HEAD", "--", "sub"], repo.path)
    git(["log", "-p", "-1"], repo.path)

    assert not marca.exists()


def test_executa_leitura_num_repositorio_real(repo):
    assert Path(git(["rev-parse", "--show-toplevel"], repo.path).strip()) == repo.path.resolve()
    assert git_ok(["ls-files", "--error-unmatch", "--", "README.md"], repo.path) is True
    assert git_ok(["ls-files", "--error-unmatch", "--", "nao-existe"], repo.path) is False


def test_falha_do_git_vira_excecao_com_codigo(repo):
    with pytest.raises(GitFalhou) as erro:
        git(["rev-list", "--end-of-options", "ref-que-nao-existe"], repo.path)

    assert erro.value.codigo != 0


def test_caminho_git_resolve_repo_normal_e_worktree(repo, tmp_path):
    wt = tmp_path / "wt"
    repo.git("worktree", "add", "-q", str(wt), "-b", "outra")

    assert caminho_git(repo.path, "sw-pr-message") == (repo.path / ".git" / "sw-pr-message").resolve()
    assert caminho_git(wt, "info/exclude") == (repo.path / ".git" / "info" / "exclude").resolve()


def test_versao_atende_o_minimo(repo):
    assert versao(repo.path) >= MIN_VERSAO


def test_ambiente_proibe_busca_preguicosa_de_objetos():
    # em clone parcial, o diff buscaria do remoto os arquivos que faltam — rede e escrita em .git/objects
    assert ambiente()["GIT_NO_LAZY_FETCH"] == "1"
```

- [x] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_gitcmd.py -q`
Expected: FAIL com `ImportError: cannot import name 'gitcmd' from 'lib'`.

- [x] **Step 3: Implementar**

`scripts/lib/gitcmd.py`:

```python
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
```

- [x] **Step 4: Rodar e confirmar que passa**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_gitcmd.py -q`
Expected: `35 passed`

- [x] **Step 5: Checkpoint** — pausa de aprovação.

---

### Task 2: `lib/base.py` — pré-checagens e detecção da base

**Files:**
- Create: `~/.claude/skills/sw-pr-message/scripts/lib/base.py`
- Test: `~/.claude/skills/sw-pr-message/tests/test_base.py`

- [x] **Step 1: Escrever os testes que falham**

`tests/test_base.py`:

```python
import subprocess

import pytest

from gitrepo import ENV
from lib import base
from lib.base import Parada, detectar_base, pre_checar
from lib.gitcmd import GitRecusado


def feature_de_develop(repo):
    """master ← develop (+1) ← feature/x (+1). Contagens: develop 1, master 2."""
    repo.branch("develop")
    repo.commit("feat: base do develop")
    repo.branch("feature/x")
    repo.commit("feat: trabalho da feature")


def develop_local_atrasado(repo):
    """develop local em A; origin/develop em B, à frente; feature/x saiu de origin/develop."""
    repo.branch("develop")
    repo.commit("feat: A")
    repo.branch("tmp")
    repo.commit("feat: B")
    repo.ref_remota("develop")
    repo.branch("feature/x")
    repo.git("branch", "-D", "tmp")
    repo.commit("feat: F")


def test_feature_de_develop_com_master_presente_escolhe_develop(repo):
    feature_de_develop(repo)

    b = detectar_base(repo.path)

    assert (b["nome"], b["ref"], b["como"], b["a_frente"]) == ("develop", "refs/heads/develop", "heuristica", 1)
    assert b["candidatas"] == {"develop": 1, "master": 2}


def test_candidato_que_ja_contem_a_branch_para_e_lista_contagens(repo):
    feature_de_develop(repo)
    repo.git("branch", "staging")

    with pytest.raises(Parada) as parada:
        detectar_base(repo.path)

    msg = str(parada.value)
    assert "staging já contém a branch" in msg
    assert "develop: 1" in msg and "master: 2" in msg
    assert "--base develop" in msg


def test_arquivo_ou_pasta_com_nome_de_candidato_nao_esconde_a_branch(repo):
    feature_de_develop(repo)
    repo.git("branch", "staging")
    (repo.path / "develop").write_text("arquivo solto com nome de branch\n", encoding="utf-8")
    (repo.path / "staging").mkdir()
    (repo.path / "staging" / "x.txt").write_text("x\n", encoding="utf-8")

    with pytest.raises(Parada, match="staging já contém a branch"):
        detectar_base(repo.path)


def test_tag_com_nome_de_candidato_nao_vira_candidata(repo):
    repo.git("tag", "main")
    repo.branch("feature/x")
    repo.commit("feat: x")

    b = detectar_base(repo.path)

    assert "main" not in b["candidatas"]
    assert b["nome"] == "master"


def test_empate_resolvido_pela_branch_padrao(repo):
    repo.git("branch", "main")
    repo.ref_remota("master")
    repo.origin_head("master")
    repo.branch("feature/x")
    repo.commit("feat: x")

    assert detectar_base(repo.path)["nome"] == "master"


def test_empate_sem_branch_padrao_prefere_main(repo):
    repo.git("branch", "main")
    repo.branch("feature/x")
    repo.commit("feat: x")

    assert detectar_base(repo.path)["nome"] == "main"


def test_empate_sem_padrao_nem_main_master_para(repo):
    repo.git("branch", "develop")
    repo.git("branch", "trunk")
    repo.branch("feature/x", "develop")
    repo.git("branch", "-D", "master")
    repo.commit("feat: x")

    with pytest.raises(Parada, match="Empate entre develop, trunk"):
        detectar_base(repo.path)


def test_branch_padrao_fora_da_lista_entra_como_candidata(repo):
    repo.git("branch", "-m", "master", "production")
    repo.ref_remota("production")
    repo.origin_head("production")
    repo.branch("feature/x")
    repo.commit("feat: x")

    assert detectar_base(repo.path)["nome"] == "production"


def test_develop_local_atrasado_perde_para_origin_develop_na_heuristica(repo):
    develop_local_atrasado(repo)

    b = detectar_base(repo.path)

    assert (b["nome"], b["ref"], b["a_frente"]) == ("develop", "refs/remotes/origin/develop", 1)


def test_develop_local_atrasado_perde_para_origin_develop_com_base_informada(repo):
    develop_local_atrasado(repo)

    b = detectar_base(repo.path, "develop")

    assert (b["ref"], b["como"], b["a_frente"]) == ("refs/remotes/origin/develop", "informada", 1)


def test_base_informada_com_prefixo_origin_e_normalizada(repo):
    develop_local_atrasado(repo)

    b = detectar_base(repo.path, "origin/develop")

    assert (b["nome"], b["ref"], b["a_frente"]) == ("develop", "refs/remotes/origin/develop", 1)


def test_base_informada_vence_a_heuristica(repo):
    feature_de_develop(repo)

    b = detectar_base(repo.path, "master")

    assert (b["nome"], b["como"], b["a_frente"]) == ("master", "informada", 2)


def test_base_informada_inexistente_para(repo):
    feature_de_develop(repo)

    with pytest.raises(Parada, match="não existe localmente"):
        detectar_base(repo.path, "release/9.9")


def test_base_informada_sem_commits_a_frente_para(repo):
    feature_de_develop(repo)
    repo.git("branch", "staging")

    with pytest.raises(Parada, match="não tem commits à frente"):
        detectar_base(repo.path, "staging")


def test_nenhum_candidato_existe_pede_base(repo):
    repo.git("branch", "-m", "master", "principal")
    repo.branch("feature/x")
    repo.commit("feat: x")

    with pytest.raises(Parada, match="Informe --base"):
        detectar_base(repo.path)


def test_base_que_parece_opcao_e_recusada(repo):
    feature_de_develop(repo)

    with pytest.raises(GitRecusado):
        detectar_base(repo.path, "--output=/tmp/x")


def test_pre_checagem_fora_de_repositorio(tmp_path):
    with pytest.raises(Parada, match="Não é um repositório git"):
        pre_checar(tmp_path, tem_base=False)


def test_pre_checagem_repositorio_bare(tmp_path):
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], env=ENV, check=True)

    with pytest.raises(Parada, match="Não é um repositório git"):
        pre_checar(bare, tem_base=False)


def test_pre_checagem_git_antigo(repo, monkeypatch):
    monkeypatch.setattr(base, "versao", lambda *a, **k: (2, 20))

    with pytest.raises(Parada, match="ou mais novo"):
        pre_checar(repo.path, tem_base=False)


def test_pre_checagem_clone_raso(repo, tmp_path):
    repo.commit("feat: segundo")
    raso = tmp_path / "raso"
    repo.git("clone", "-q", "--depth", "1", "--no-local", f"file://{repo.path}", str(raso))

    with pytest.raises(Parada, match="Clone raso"):
        pre_checar(raso, tem_base=False)


def test_pre_checagem_head_destacado(repo):
    repo.git("checkout", "-q", "--detach")

    with pytest.raises(Parada, match="HEAD destacado"):
        pre_checar(repo.path, tem_base=False)


def test_pre_checagem_rebase_em_andamento(repo):
    repo.branch("c1")
    repo.commit("feat: um", {"conflito.txt": "um\n"})
    repo.branch("c2", "master")
    repo.commit("feat: dois", {"conflito.txt": "dois\n"})
    repo.git("rebase", "c1", check=False)

    with pytest.raises(Parada, match="Rebase em andamento"):
        pre_checar(repo.path, tem_base=False)


def test_pre_checagem_em_develop_sem_base_para(repo):
    repo.branch("develop")
    repo.commit("feat: d")

    with pytest.raises(Parada, match="que é uma branch base"):
        pre_checar(repo.path, tem_base=False)


def test_pre_checagem_em_branch_padrao_fora_da_lista_para(repo):
    repo.git("branch", "-m", "master", "production")
    repo.ref_remota("production")
    repo.origin_head("production")

    with pytest.raises(Parada, match="que é uma branch base"):
        pre_checar(repo.path, tem_base=False)


def test_em_develop_com_base_master_segue_como_pr_de_release(repo):
    repo.branch("develop")
    repo.commit("feat: d")

    atual = pre_checar(repo.path, tem_base=True)
    b = detectar_base(repo.path, "master")

    assert atual == "develop"
    assert (b["nome"], b["a_frente"]) == ("master", 1)


def test_empate_fica_registrado_na_base_escolhida(repo):
    repo.git("branch", "develop")
    repo.branch("fix/checkout")
    repo.commit("fix: um")

    b = detectar_base(repo.path)

    assert (b["nome"], b["empate"]) == ("master", ["develop", "master"])


def test_pre_checagem_clone_parcial(repo, tmp_path):
    repo.commit("feat: segundo", {"dados.txt": "conteúdo\n"})
    repo.git("config", "uploadpack.allowfilter", "true")
    parcial = tmp_path / "parcial"
    repo.git("clone", "-q", "--filter=blob:none", "--no-local", f"file://{repo.path}", str(parcial))
    assert list((parcial / ".git" / "objects" / "pack").glob("*.promisor")), "o clone não saiu parcial (ambiente)"

    with pytest.raises(Parada, match="Clone parcial"):
        pre_checar(parcial, tem_base=False)
```

- [x] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_base.py -q`
Expected: FAIL com `ImportError: cannot import name 'base' from 'lib'`.

- [x] **Step 3: Implementar**

`scripts/lib/base.py`:

```python
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
```

- [x] **Step 4: Rodar e confirmar que passa**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_base.py -q`
Expected: `27 passed`

- [x] **Step 5: Checkpoint** — pausa de aprovação.

---

### Task 3: `lib/coleta.py` — commits, arquivos, ruído, corte, hotfix e avisos

**Files:**
- Create: `~/.claude/skills/sw-pr-message/scripts/lib/coleta.py`
- Test: `~/.claude/skills/sw-pr-message/tests/test_coleta.py`

- [x] **Step 1: Escrever os testes que falham**

`tests/test_coleta.py`:

```python
import pytest

from lib import coleta
from lib.coleta import (avisos, commits, eh_ruido, merges_ignorados, numstat, preencher_diffs,
                        sinais_hotfix, tipo_escopo)


@pytest.mark.parametrize("caminho,esperado", [
    ("package-lock.json", True), ("web/yarn.lock", True), ("go.sum", True), ("Pipfile.lock", True),
    ("web/dist/app.js", True), ("vendor/lib/x.php", True), ("src/app.min.js", True),
    ("static/app.js.map", True), ("tests/__snapshots__/a.snap", True),
    ("src/app.py", False), ("distribuicao.py", False), ("build.gradle", False), ("docs/build.md", False),
])
def test_classifica_ruido_pelo_caminho(caminho, esperado):
    assert eh_ruido(caminho) is esperado


@pytest.mark.parametrize("assunto,esperado", [
    ("feat(auth): login", ("feat", "auth")), ("Fix: checkout", ("fix", None)),
    ("feat!: quebra", ("feat", None)), ("ajustes", (None, None)),
])
def test_tipo_e_escopo_do_prefixo_conventional(assunto, esperado):
    assert tipo_escopo(assunto) == esperado


def test_commits_sem_merge_em_ordem_cronologica_com_corpo(repo):
    repo.branch("develop")
    repo.branch("feature/x")
    repo.commit("feat(login): tela\n\nMotivo: pedido do cliente.")
    repo.checkout("develop")
    repo.commit("feat: algo no develop", {"so_develop.txt": "d\n"})
    repo.checkout("feature/x")
    repo.merge("develop", "Merge branch 'develop' into feature/x")
    repo.commit("fix: ajuste")

    lista = commits(repo.path, "develop")

    assert [c["assunto"] for c in lista] == ["feat(login): tela", "fix: ajuste"]
    assert lista[0]["corpo"] == "Motivo: pedido do cliente."
    assert (lista[0]["tipo"], lista[0]["escopo"]) == ("feat", "login")
    assert len(lista[0]["hash"]) == 40
    assert merges_ignorados(repo.path, "develop") == 1
    assert "so_develop.txt" not in [a["caminho"] for a in numstat(repo.path, "develop")]


def test_mensagem_com_separadores_de_controle_nao_forja_commit(repo, tmp_path):
    repo.branch("feature/x")
    mensagem = tmp_path / "msg.txt"
    mensagem.write_text("feat: real\n\ncorpo\x1e" + "f" * 40 + "\x1ffix: FORJADO\x1fcorpo forjado\n",
                        encoding="utf-8")
    (repo.path / "x.txt").write_text("x\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-F", str(mensagem))

    lista = commits(repo.path, "master")

    assert [c["hash"] for c in lista] == [repo.sha()]
    assert lista[0]["assunto"] == "feat: real"
    assert "FORJADO" in lista[0]["corpo"]


def test_numstat_marca_ruido_binario_e_renomeacao_em_ordem_de_caminho(repo):
    repo.commit("chore: arquivo a mover", {"antigo.txt": "".join(f"linha {i}\n" for i in range(20))})
    repo.branch("feature/x")
    repo.git("mv", "antigo.txt", "novo.txt")
    repo.commit("refactor: renomeia", {"package-lock.json": '{"lock": 1}\n', "logo.png": b"\x89PNG\x00\x01"})

    arquivos = {a["caminho"]: a for a in numstat(repo.path, "master")}

    assert list(arquivos) == sorted(arquivos)
    assert arquivos["novo.txt"]["anterior"] == "antigo.txt" and arquivos["novo.txt"]["ruido"] is False
    assert arquivos["package-lock.json"]["ruido"] is True and arquivos["package-lock.json"]["mais"] == 1
    assert arquivos["logo.png"]["binario"] is True and arquivos["logo.png"]["ruido"] is True


def test_diff_de_renomeacao_usa_os_dois_caminhos(repo):
    repo.commit("chore: arquivo a mover", {"antigo.txt": "".join(f"linha {i}\n" for i in range(20))})
    repo.branch("feature/x")
    repo.git("mv", "antigo.txt", "novo.txt")
    repo.commit("refactor: renomeia")
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    novo = next(a for a in arquivos if a["caminho"] == "novo.txt")
    assert "rename from antigo.txt" in novo["diff"]
    assert "linha 5" not in novo["diff"]


def test_diff_de_um_arquivo_nao_traz_outros_por_glob_ou_magic(repo):
    repo.branch("feature/x")
    repo.commit("feat: nomes especiais", {
        "[ab].txt": "colchete\n", "a.txt": "letra A\n", "b.txt": "letra B\n",
        "pages/[id].tsx": "rota dinamica\n", "pages/i.tsx": "rota i\n",
        ":foo": "dois pontos\n", "foo": "sem dois pontos\n",
    })
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    por_nome = {a["caminho"]: a for a in arquivos}
    assert "+colchete" in por_nome["[ab].txt"]["diff"]
    assert "letra A" not in por_nome["[ab].txt"]["diff"] and "letra B" not in por_nome["[ab].txt"]["diff"]
    assert "rota i" not in por_nome["pages/[id].tsx"]["diff"]
    assert "+dois pontos" in por_nome[":foo"]["diff"]


def test_arquivo_com_nome_de_prefixo_proibido_nao_derruba_a_coleta(repo):
    repo.branch("feature/x")
    repo.commit("docs: nomes estranhos", {"--output.txt": "saida\n", "--submodule.md": "sub\n"})
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    por_nome = {a["caminho"]: a for a in arquivos}
    assert "+saida" in por_nome["--output.txt"]["diff"]
    assert "+sub" in por_nome["--submodule.md"]["diff"]


def test_corte_por_arquivo_e_ruido_sem_conteudo(repo):
    repo.branch("feature/x")
    repo.commit("feat: arquivos", {
        "grande.py": "".join(f"x_{i} = {i}\n" for i in range(1000)),
        "pequeno.py": "y = 1\n",
        "yarn.lock": "".join(f"pacote-{i}\n" for i in range(50)),
    })
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    por_nome = {a["caminho"]: a for a in arquivos}
    assert por_nome["pequeno.py"]["cortado"] is False and "+y = 1" in por_nome["pequeno.py"]["diff"]
    assert por_nome["grande.py"]["cortado"] is True
    assert por_nome["grande.py"]["diff"].count("\n") == coleta.TETO_LINHAS
    assert por_nome["yarn.lock"]["diff"] == ""


def test_so_quebra_de_linha_real_conta_para_o_corte(repo):
    repo.branch("feature/x")
    repo.commit("feat: form feed", {"ff.el": "".join(f"linha {i}\x0c\n" for i in range(300))})
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos)

    assert arquivos[0]["cortado"] is False


def test_orcamento_total_esgotado_deixa_diff_marcado_e_respeita_teto(repo):
    repo.branch("feature/x")
    repo.commit("feat: dois arquivos", {"a.py": "a = 1\n", "b.py": "".join(f"b{i} = {i}\n" for i in range(30))})
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos, teto_bytes=200)

    por_nome = {a["caminho"]: a for a in arquivos}
    assert por_nome["a.py"]["cortado"] is False
    assert por_nome["b.py"]["cortado"] is True
    assert sum(len(a["diff"].encode("utf-8")) for a in arquivos) <= 200


def test_arquivo_sem_orcamento_restante_fica_vazio_e_marcado(repo):
    repo.branch("feature/x")
    repo.commit("feat: dois", {"a.py": "a = 1\n", "b.py": "b = 1\n"})
    arquivos = numstat(repo.path, "master")

    preencher_diffs(repo.path, "master", arquivos, teto_bytes=0)

    assert [(a["diff"], a["cortado"]) for a in arquivos] == [("", True), ("", True)]


@pytest.mark.parametrize("branch,tipos,base_nome,tem_develop,provavel", [
    ("hotfix/login", ["feat"], "develop", True, True),
    ("feature/x", ["feat", "hotfix"], "develop", True, True),
    ("fix/checkout", ["fix", "fix"], "master", True, True),
    ("fix/checkout", ["fix", "fix"], "master", False, False),
    ("fix/checkout", ["fix", "feat"], "master", True, False),
    ("feature/x", ["fix"], "develop", True, False),
])
def test_sinais_de_hotfix(branch, tipos, base_nome, tem_develop, provavel):
    lista = [{"tipo": t} for t in tipos]

    assert sinais_hotfix(branch, lista, base_nome, tem_develop)["provavel"] is provavel


def test_avisos_so_apontam_pr_message_versionado_sem_ler_o_working_tree(repo):
    (repo.path / "rascunho.txt").write_text("não commitado\n", encoding="utf-8")
    assert avisos(repo.path) == []

    repo.commit("docs: pr antigo", {"PR-MESSAGE.md": "velho\n"})

    assert avisos(repo.path) == ["pr_message_versionado"]


def test_so_correcoes_com_base_master_nao_e_hotfix_quando_develop_empata():
    # git-flow: branch que saiu do develop antes do último release empata com master
    lista = [{"tipo": "fix"}, {"tipo": "fix"}]

    sinais = sinais_hotfix("fix/checkout", lista, "master", True, develop_empata=True)

    assert sinais["provavel"] is False
```

- [x] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_coleta.py -q`
Expected: FAIL com `ImportError: cannot import name 'coleta' from 'lib'`.

- [x] **Step 3: Implementar**

`scripts/lib/coleta.py`:

```python
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
```

- [x] **Step 4: Rodar e confirmar que passa**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_coleta.py -q`
Expected: `35 passed`

- [x] **Step 5: Checkpoint** — pausa de aprovação.

---

### Task 4: `collect.py` — linha de comando da coleta

**Files:**
- Create: `~/.claude/skills/sw-pr-message/scripts/collect.py`
- Test: `~/.claude/skills/sw-pr-message/tests/test_collect.py`

- [x] **Step 1: Escrever os testes que falham**

`tests/test_collect.py`:

```python
import json

import collect
from lib.gitcmd import caminho_git


def ler_fatos(repo):
    return json.loads((caminho_git(repo.path, "sw-pr-message") / "fatos.json").read_text(encoding="utf-8"))


def test_grava_fatos_no_git_path_com_o_esquema_do_spec(repo, capsys):
    repo.branch("develop")
    repo.commit("feat: base")
    repo.branch("feature/x")
    sha = repo.commit("feat: tela", {"tela.py": "x = 1\n"})

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_OK

    fatos = ler_fatos(repo)
    assert set(fatos) == {"branch", "base", "hotfix", "stats", "commits", "arquivos", "avisos"}
    assert fatos["branch"] == "feature/x"
    assert (fatos["base"]["nome"], fatos["base"]["a_frente"]) == ("develop", 1)
    assert [c["hash"] for c in fatos["commits"]] == [sha]
    assert fatos["stats"] == {"arquivos": 1, "insercoes": 1, "delecoes": 0, "ruido": [], "merges_ignorados": 0}
    assert fatos["hotfix"] == {"provavel": False, "sinais": []}
    assert "base: develop (develop) · heuristica · 1 commit(s)" in capsys.readouterr().out


def test_parada_retorna_2_com_mensagem_e_nao_grava(repo, capsys):
    repo.branch("develop")
    repo.commit("feat: d")

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_PARADA

    assert "que é uma branch base" in capsys.readouterr().err
    assert not (caminho_git(repo.path, "sw-pr-message") / "fatos.json").exists()


def test_fora_de_repositorio_retorna_2(tmp_path, capsys):
    assert collect.main(["--repo", str(tmp_path)]) == collect.EXIT_PARADA

    assert "Não é um repositório git" in capsys.readouterr().err


def test_base_que_parece_opcao_e_recusada(repo, capsys):
    repo.branch("feature/x")
    repo.commit("feat: x")

    assert collect.main(["--repo", str(repo.path), "--base=--output=/tmp/x"]) == collect.EXIT_PARADA

    assert "Recusado" in capsys.readouterr().err


def test_hotfix_detectado_pela_branch(repo):
    repo.git("branch", "develop")
    repo.branch("hotfix/pagamento")
    repo.commit("fix: timeout do gateway")

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_OK

    fatos = ler_fatos(repo)
    assert fatos["hotfix"]["provavel"] is True
    assert "branch hotfix/" in fatos["hotfix"]["sinais"]


def test_empate_develop_master_nao_vira_hotfix_e_aparece_na_saida(repo, capsys):
    repo.git("branch", "develop")
    repo.branch("fix/checkout")
    repo.commit("fix: um")

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_OK

    assert ler_fatos(repo)["hotfix"]["provavel"] is False
    assert "empate: develop, master" in capsys.readouterr().out


def test_pr_message_versionado_vira_aviso_na_saida(repo, capsys):
    repo.branch("feature/x")
    repo.commit("docs: mensagem antiga", {"PR-MESSAGE.md": "velho\n"})

    assert collect.main(["--repo", str(repo.path)]) == collect.EXIT_OK

    assert "aviso: pr_message_versionado" in capsys.readouterr().out


def test_repo_inexistente_retorna_2(tmp_path, capsys):
    assert collect.main(["--repo", str(tmp_path / "nao-existe")]) == collect.EXIT_PARADA

    assert "não existe" in capsys.readouterr().err
```

- [x] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_collect.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'collect'`.

- [x] **Step 3: Implementar**

`scripts/collect.py`:

```python
#!/usr/bin/env python3
"""Coleta, só com leitura, os fatos da branch para a mensagem de PR.

Grava <git-path>/sw-pr-message/fatos.json. Exit 2 quando precisa parar (mensagem no stderr).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import base as base_mod  # noqa: E402
from lib import coleta  # noqa: E402
from lib.gitcmd import GitFalhou, GitRecusado, caminho_git, git  # noqa: E402

EXIT_OK, EXIT_PARADA = 0, 2


def coletar(repo: Path, base=None) -> dict:
    atual = base_mod.pre_checar(repo, tem_base=base is not None)
    topo = Path(git(["rev-parse", "--show-toplevel"], repo).strip())
    b = base_mod.detectar_base(topo, base)
    lista = coleta.commits(topo, b["ref"])
    arquivos = coleta.numstat(topo, b["ref"])
    coleta.preencher_diffs(topo, b["ref"], arquivos)
    tem_develop = base_mod.existe(topo, "develop")
    return {
        "branch": atual,
        "base": b,
        "hotfix": coleta.sinais_hotfix(atual, lista, b["nome"], tem_develop,
                                       develop_empata="develop" in b["empate"]),
        "stats": {"arquivos": len(arquivos),
                  "insercoes": sum(a["mais"] for a in arquivos),
                  "delecoes": sum(a["menos"] for a in arquivos),
                  "ruido": [a["caminho"] for a in arquivos if a["ruido"]],
                  "merges_ignorados": coleta.merges_ignorados(topo, b["ref"])},
        "commits": lista,
        "arquivos": arquivos,
        "avisos": coleta.avisos(topo),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Coleta os fatos da branch para a mensagem de PR.")
    ap.add_argument("--repo", default=".", help="repositório (padrão: diretório atual)")
    ap.add_argument("--base", default=None, help="branch base; sem ela, a base é detectada")
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"--repo {repo} não existe.", file=sys.stderr)
        return EXIT_PARADA

    try:
        fatos = coletar(repo, args.base)
    except base_mod.Parada as parada:
        print(str(parada), file=sys.stderr)
        return EXIT_PARADA
    except GitRecusado as recusa:
        print(f"Recusado: {recusa}", file=sys.stderr)
        return EXIT_PARADA
    except GitFalhou as falha:
        print(f"Falha do git: {falha}", file=sys.stderr)
        return EXIT_PARADA

    pasta = caminho_git(repo, "sw-pr-message")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "fatos.json"
    destino.write_text(json.dumps(fatos, ensure_ascii=False, indent=1), encoding="utf-8")

    b = fatos["base"]
    print(f"fatos.json: {destino}")
    print(f"base: {b['nome']} ({base_mod.curta(b['ref'])}) · {b['como']} · {b['a_frente']} commit(s) · "
          + " · ".join(f"{n} {c}" for n, c in b["candidatas"].items()))
    if b["empate"]:
        print(f"empate: {', '.join(b['empate'])} — mesmo conteúdo para esta branch; a base acima veio do desempate")
    cortados = [a["caminho"] for a in fatos["arquivos"] if a["cortado"]]
    if cortados:
        print("cortados: " + ", ".join(cortados))
    for aviso in fatos["avisos"]:
        print(f"aviso: {aviso}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 4: Rodar e confirmar que passa**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest -q`
Expected: `107 passed` (Tasks 0–4: 2 + 35 + 27 + 35 + 8).

- [x] **Step 5: Checkpoint** — pausa de aprovação.

---

### Task 5: render — limpeza de texto e validação do `mudancas.json`

Tudo que a validação precisa checar vem do spec ("Render › Validação"). `limpar_titulo` fica aqui
porque a validação usa ("título vazio depois de remover o prefixo").

**Files:**
- Create: `~/.claude/skills/sw-pr-message/scripts/render.py`
- Test: `~/.claude/skills/sw-pr-message/tests/test_render_validar.py`

- [x] **Step 1: Escrever os testes que falham**

`tests/test_render_validar.py`:

```python
import pytest

from render import limpar, limpar_titulo, validar

H1 = "abcdef1" + "1" * 33
H2 = "abcdef1" + "2" * 33
H3 = "0123456" + "3" * 33


def fatos(*hashes, provavel=False):
    return {
        "commits": [{"hash": h, "assunto": f"commit {h[:7]}"} for h in hashes],
        "hotfix": {"provavel": provavel, "sinais": []},
    }


def mud(**extra):
    base = {
        "idioma": "pt",
        "titulo": "Tela de login",
        "resumo": "Permite entrar no sistema.",
        "secoes": {"novas": [{"texto": "Tela de login", "commits": [H3[:7]]}]},
        "como_testar": [],
    }
    base.update(extra)
    return base


def test_mudancas_completo_nao_tem_problema():
    assert validar(fatos(H3), mud()) == []


def test_lista_todos_os_problemas_de_uma_vez():
    ruim = {
        "idioma": "xx",
        "titulo": "",
        "resumo": "",
        "secoes": {"novidades": [], "novas": [{"texto": "algo", "commits": []}]},
    }

    problemas = validar(fatos(H3, provavel=True), ruim)

    texto = "\n".join(problemas)
    for esperado in ("idioma inválido", "titulo vazio", "resumo vazio", "seção desconhecida",
                     "item sem commits", "commit esquecido", "hotfix obrigatório"):
        assert esperado in texto, esperado
    assert len(problemas) == 7


def test_commit_esquecido_e_apontado():
    problemas = validar(fatos(H3, H1), mud())

    assert problemas == [f"commit esquecido: {H1[:7]} commit {H1[:7]}"]


def test_hash_curto_desconhecido_e_ambiguo_sao_recusados():
    m = mud(secoes={"novas": [{"texto": "x", "commits": ["abc", "fffffff", "abcdef1"]}]})

    problemas = "\n".join(validar(fatos(H1, H2), m))

    assert "hash curto: 'abc'" in problemas
    assert "hash desconhecido: 'fffffff'" in problemas
    assert "hash ambiguo: 'abcdef1'" in problemas


def test_prefixo_longo_o_bastante_resolve_sem_ambiguidade():
    m = mud(secoes={"novas": [{"texto": "a", "commits": ["abcdef11"]},
                              {"texto": "b", "commits": ["abcdef12"]}]})

    assert validar(fatos(H1, H2), m) == []


def test_sem_item_cobre_commit_sem_efeito_liquido():
    m = mud(sem_item=[{"hash": H1[:7], "motivo": "desfeito pelo commit seguinte"}])

    assert validar(fatos(H3, H1), m) == []


def test_commit_num_item_e_em_sem_item_ao_mesmo_tempo_e_recusado():
    m = mud(sem_item=[{"hash": H3[:7], "motivo": "nada"}])

    assert validar(fatos(H3), m) == [f"commit {H3[:7]} está num item e em sem_item"]


def test_mesmo_commit_em_dois_itens_e_permitido():
    m = mud(secoes={"novas": [{"texto": "a", "commits": [H3]}],
                    "ajustes": [{"texto": "b", "commits": [H3]}]})

    assert validar(fatos(H3), m) == []


def test_titulo_que_so_tinha_prefixo_e_recusado():
    assert validar(fatos(H3), mud(titulo="feat(auth): ")) == ["titulo vazio depois de remover o prefixo"]


def test_hotfix_inconsistente_nos_dois_sentidos():
    obrigatorio = validar(fatos(H3, provavel=True), mud())
    proibido = validar(fatos(H3, provavel=False), mud(hotfix={"causa": "x", "impacto": None, "rollback": None}))

    assert obrigatorio == ["hotfix obrigatório: fatos indicam hotfix (use null nos campos sem evidência)"]
    assert proibido == ["hotfix não permitido: fatos não indicam hotfix"]


def test_hotfix_com_todos_os_campos_null_e_aceito_quando_provavel():
    m = mud(hotfix={"causa": None, "impacto": None, "rollback": None})

    assert validar(fatos(H3, provavel=True), m) == []


def test_limpar_tira_emoji_e_preserva_marcas_tipograficas():
    assert limpar("Novo ✨ fluxo 🚀 → pronto ✓ ✔ • – — ⚠️") == "Novo fluxo → pronto ✓ ✔ • – —"


def test_limpar_titulo_tira_so_prefixo_conventional_ou_colchete():
    assert limpar_titulo("feat(auth)!: Login com Google") == "Login com Google"
    assert limpar_titulo("FIX: Corrige checkout") == "Corrige checkout"
    assert limpar_titulo("[Feature] Painel novo") == "Painel novo"
    assert limpar_titulo("✨ feat: Painel") == "Painel"
    assert limpar_titulo("Checkout: novo fluxo de pagamento") == "Checkout: novo fluxo de pagamento"


@pytest.mark.parametrize("extra,provavel,esperado", [
    ({"secoes": {"novas": ["texto solto"]}}, False, "novas[1] deve ser um objeto"),
    ({"secoes": {"ajustes": "x"}}, False, "secoes.ajustes deve ser uma lista"),
    ({"secoes": {"novas": [{"texto": "a", "commits": "0123456"}]}}, False, "novas[1]: commits deve ser uma lista"),
    ({"secoes": {"novas": [{"texto": {"a": "b"}, "commits": [H3]}]}}, False, "novas[1]: texto deve ser texto"),
    ({"sem_item": "x"}, False, "sem_item deve ser uma lista"),
    ({"sem_item": ["0123456"]}, False, "sem_item[1] deve ser um objeto"),
    ({"como_testar": "Abrir a tela"}, False, "como_testar deve ser uma lista de textos"),
    ({"como_testar": [1, 2]}, False, "como_testar deve ser uma lista de textos"),
    ({"hotfix": "causa X"}, True, "hotfix deve ser um objeto"),
    ({"hotfix": {"causa": 1, "impacto": None, "rollback": None}}, True, "hotfix.causa deve ser texto ou null"),
    ({"titulo": 42}, False, "titulo deve ser texto"),
    ({"resumo": {"a": 1}}, False, "resumo deve ser texto"),
])
def test_tipo_errado_vira_problema_listado_sem_excecao(extra, provavel, esperado):
    problemas = validar(fatos(H3, provavel=provavel), mud(**extra))

    assert esperado in "\n".join(problemas)


def test_commits_em_texto_nao_gera_um_problema_por_caractere():
    m = mud(secoes={"novas": [{"texto": "a", "commits": "0123456"}]})

    assert "hash curto" not in "\n".join(validar(fatos(H3), m))


def test_item_com_texto_vazio_e_recusado():
    m = mud(secoes={"novas": [{"texto": "   ", "commits": [H3]}]})

    assert validar(fatos(H3), m) == ["novas[1]: texto vazio"]


def test_sem_item_com_motivo_vazio_e_recusado():
    m = mud(sem_item=[{"hash": H1[:7], "motivo": ""}])

    assert validar(fatos(H3, H1), m) == ["sem_item[1]: motivo vazio"]


def test_hash_em_maiusculas_resolve():
    m = mud(secoes={"novas": [{"texto": "x", "commits": ["ABCDEF1"]}]})

    assert validar(fatos(H1), m) == []


def test_limpar_junta_quebras_de_linha_e_ignora_nao_texto():
    assert limpar("Tela\n## Falsa\n\n- item") == "Tela ## Falsa - item"
    assert limpar(42) == "" and limpar(None) == ""


def test_limpar_remove_emoji_composto_e_de_apresentacao():
    familia = chr(0x1F468) + chr(0x200D) + chr(0x1F469) + chr(0x200D) + chr(0x1F467)
    keycap = "1" + chr(0xFE0F) + chr(0x20E3)
    outros = "".join(map(chr, (0x2B50, 0x23F3, 0x270A, 0x231B)))

    assert limpar(f"família {familia} passo {keycap} ok {outros} fim") == "família passo 1 ok fim"
```

- [x] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_render_validar.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'render'`.

- [x] **Step 3: Implementar**

`scripts/render.py`:

```python
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
```

- [x] **Step 4: Rodar e confirmar que passa**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_render_validar.py -q`
Expected: `31 passed`

---

### Task 6: render — montagem do markdown

**Files:**
- Modify: `~/.claude/skills/sw-pr-message/scripts/render.py` (acrescentar ao final)
- Test: `~/.claude/skills/sw-pr-message/tests/test_render_montar.py`

- [x] **Step 1: Escrever os testes que falham**

`tests/test_render_montar.py`:

```python
import json

import pytest

from render import montar

H1 = "a1b2c3d" + "1" * 33
H2 = "e4f5a6b" + "2" * 33


def fatos(provavel=False):
    return {"commits": [{"hash": H1, "assunto": "a"}, {"hash": H2, "assunto": "b"}],
            "hotfix": {"provavel": provavel, "sinais": []}}


def mud(**extra):
    base = {
        "idioma": "pt",
        "titulo": "feat(pagamentos): Integração com gateway",
        "resumo": "Permite cobrar por Pix 🚀 no checkout.",
        "secoes": {
            "interno": [{"texto": "Serviço de cobrança extraído", "commits": [H2]}],
            "novas": [{"texto": "Pagamento por Pix → QR Code ✓", "commits": [H1]}],
            "ajustes": [],
        },
        "como_testar": ["Criar um pedido", "Escolher Pix"],
    }
    base.update(extra)
    return base


def test_titulo_e_secoes_na_ordem_fixa_com_vazias_omitidas():
    texto = montar(fatos(), mud())

    assert texto.startswith("# Integração com gateway\n\n## Resumo\n\nPermite cobrar por Pix no checkout.\n")
    assert texto.index("## Novas funcionalidades") < texto.index("## Interno") < texto.index("## Como testar")
    assert "## Ajustes" not in texto
    assert "## Correções" not in texto


def test_itens_em_lista_e_passos_numerados():
    texto = montar(fatos(), mud())

    assert "- Pagamento por Pix → QR Code ✓\n" in texto
    assert "1. Criar um pedido\n2. Escolher Pix\n" in texto


def test_como_testar_vazio_some():
    assert "Como testar" not in montar(fatos(), mud(como_testar=[]))


def test_hash_nunca_aparece_no_texto():
    texto = montar(fatos(), mud())

    assert H1[:7] not in texto and H2[:7] not in texto


def test_rotulos_em_ingles():
    texto = montar(fatos(), mud(idioma="en"))

    assert "## Summary" in texto and "## New features" in texto
    assert "## Internal" in texto and "## How to test" in texto


def test_hotfix_fica_logo_depois_do_resumo_e_campo_null_vira_comentario():
    m = mud(hotfix={"causa": "Timeout de 5s no gateway", "impacto": None, "rollback": "Reverter o deploy"})

    texto = montar(fatos(provavel=True), m)

    assert texto.index("## Resumo") < texto.index("## Hotfix") < texto.index("## Novas funcionalidades")
    assert "**Causa:** Timeout de 5s no gateway\n" in texto
    assert "<!-- preencher: **Impacto:** -->\n" in texto
    assert "**Rollback:** Reverter o deploy\n" in texto


def test_hotfix_com_tres_null_fica_inteiro_dentro_de_um_comentario():
    m = mud(hotfix={"causa": None, "impacto": None, "rollback": None})

    texto = montar(fatos(provavel=True), m)

    abre = texto.index("<!-- preencher:")
    titulo = texto.index("## Hotfix")
    fecha = texto.index("-->", titulo)
    assert abre < titulo < fecha
    assert texto.count("## Hotfix") == 1


def test_comentario_de_lacuna_em_ingles():
    m = mud(idioma="en", hotfix={"causa": "x", "impacto": None, "rollback": "y"})

    assert "<!-- fill in: **Impact:** -->" in montar(fatos(provavel=True), m)


def test_sem_hotfix_quando_fatos_nao_indicam():
    assert "Hotfix" not in montar(fatos(provavel=False), mud())


def test_ff4_render_deterministico_byte_a_byte():
    f, m = fatos(provavel=True), mud(hotfix={"causa": "a", "impacto": None, "rollback": None})

    primeira = montar(f, m).encode("utf-8")
    segunda = montar(json.loads(json.dumps(f)), json.loads(json.dumps(m))).encode("utf-8")

    assert primeira == segunda
    assert primeira.endswith(b"\n") and not primeira.endswith(b"\n\n")


@pytest.mark.parametrize("idioma,titulos,campos", [
    ("pt", ["## Resumo", "## Hotfix", "## Novas funcionalidades", "## Ajustes", "## Correções",
            "## Removido", "## Segurança", "## Interno", "## Como testar"],
     ["**Causa:** c", "**Impacto:** i", "**Rollback:** r"]),
    ("en", ["## Summary", "## Hotfix", "## New features", "## Changes", "## Fixes",
            "## Removed", "## Security", "## Internal", "## How to test"],
     ["**Root cause:** c", "**Impact:** i", "**Rollback:** r"]),
])
def test_todas_as_secoes_saem_na_ordem_e_com_os_rotulos_exatos(idioma, titulos, campos):
    cheio = {c: [{"texto": f"item de {c}", "commits": [H1]}]
             for c in ("seguranca", "novas", "interno", "correcoes", "removido", "ajustes")}
    m = mud(idioma=idioma, secoes=cheio, hotfix={"causa": "c", "impacto": "i", "rollback": "r"})

    texto = montar(fatos(provavel=True), m)

    assert [l for l in texto.splitlines() if l.startswith("## ")] == titulos
    assert [l for l in texto.splitlines() if l.startswith("**")] == campos


def test_quebra_de_linha_do_agente_nao_cria_secao():
    m = mud(titulo="Tela\n## Falsa", resumo="Um\n## Falsa no resumo",
            secoes={"novas": [{"texto": "Tela\n## Seção falsa\n- item falso", "commits": [H1]}]},
            como_testar=["Abrir\n## Falsa no passo"],
            hotfix={"causa": "x\n## Falsa", "impacto": None, "rollback": None})

    texto = montar(fatos(provavel=True), m)

    assert [l for l in texto.splitlines() if l.startswith("## ")] == \
        ["## Resumo", "## Hotfix", "## Novas funcionalidades", "## Como testar"]
    assert texto.splitlines()[0] == "# Tela ## Falsa"


@pytest.mark.parametrize("resumo,escapado", [
    ("## Falso", "\\## Falso"), ("<!-- rascunho", "\\<!-- rascunho"), ("```js", "\\```js"),
])
def test_resumo_que_comeca_como_bloco_vira_paragrafo(resumo, escapado):
    linhas = montar(fatos(), mud(resumo=resumo)).splitlines()

    assert linhas[linhas.index("## Resumo") + 2] == escapado
```

- [x] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_render_montar.py -q`
Expected: FAIL com `ImportError: cannot import name 'montar' from 'render'`.

- [x] **Step 3: Implementar** — acrescentar ao final de `scripts/render.py`:

```python
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
```

- [x] **Step 4: Rodar e confirmar que passa**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_render_montar.py tests/test_render_validar.py -q`
Expected: `47 passed`

---

### Task 7: render — gravação e linha de comando

**Files:**
- Modify: `~/.claude/skills/sw-pr-message/scripts/render.py` (acrescentar ao final)
- Create: `~/.claude/skills/sw-pr-message/tests/fluxo.py` (ajudantes reaproveitados na Task 8)
- Test: `~/.claude/skills/sw-pr-message/tests/test_render_gravar.py`

- [x] **Step 1: Criar os ajudantes de fluxo**

`tests/fluxo.py`:

```python
"""Ajudantes de ponta a ponta: coleta real num repositório de teste + mudancas.json válido."""
import json

import collect
from lib.gitcmd import caminho_git


def preparar(repo, mensagem="feat: tela de login", arquivos=None):
    """Branch de feature com um commit, coletada. Devolve (pasta dos intermediários, sha)."""
    repo.branch("feature/x")
    sha = repo.commit(mensagem, arquivos or {"login.py": "def entrar():\n    return True\n"})
    assert collect.main(["--repo", str(repo.path)]) == 0
    return caminho_git(repo.path, "sw-pr-message"), sha


def escrever_mudancas(pasta, *shas, **extra):
    dados = {
        "idioma": "pt",
        "titulo": "Tela de login",
        "resumo": "Permite entrar no sistema.",
        "secoes": {"novas": [{"texto": "Tela de login", "commits": [s[:7] for s in shas]}]},
        "como_testar": ["Abrir a tela de login"],
    }
    dados.update(extra)
    (pasta / "mudancas.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
```

- [x] **Step 2: Escrever os testes que falham**

`tests/test_render_gravar.py`:

```python
import shutil

import collect
import render
from fluxo import escrever_mudancas, preparar
from gitrepo import Repo
from lib.gitcmd import caminho_git


def test_grava_na_raiz_e_protege_pelo_exclude(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)

    assert render.main(["--repo", str(repo.path)]) == 0

    texto = (repo.path / "PR-MESSAGE.md").read_text(encoding="utf-8")
    assert texto.startswith("# Tela de login\n")
    assert repo.git("check-ignore", "PR-MESSAGE.md").strip() == "PR-MESSAGE.md"


def test_rodar_duas_vezes_nao_duplica_a_linha_do_exclude(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)

    render.main(["--repo", str(repo.path)])
    render.main(["--repo", str(repo.path)])

    linhas = caminho_git(repo.path, "info/exclude").read_text(encoding="utf-8").splitlines()
    assert linhas.count("/PR-MESSAGE.md") == 1


def test_versao_anterior_editada_a_mao_e_preservada(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    (repo.path / "PR-MESSAGE.md").write_text("editado à mão\n", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == 0

    assert (pasta / "PR-MESSAGE.anterior.md").read_text(encoding="utf-8") == "editado à mão\n"


def test_conteudo_igual_nao_gera_copia_anterior(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)

    render.main(["--repo", str(repo.path)])
    render.main(["--repo", str(repo.path)])

    assert not (pasta / "PR-MESSAGE.anterior.md").exists()


def test_pr_message_existente_que_nao_e_utf8_e_preservado(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    (repo.path / "PR-MESSAGE.md").write_bytes(b"\xff\xfe latin")

    assert render.main(["--repo", str(repo.path)]) == 0

    assert (pasta / "PR-MESSAGE.anterior.md").read_bytes() == b"\xff\xfe latin"


def test_avisa_quando_o_arquivo_ja_e_versionado(repo, capsys):
    repo.branch("feature/x")
    sha_doc = repo.commit("docs: mensagem antiga", {"PR-MESSAGE.md": "velho\n"})
    sha_feat = repo.commit("feat: tela de login", {"login.py": "x = 1\n"})
    assert collect.main(["--repo", str(repo.path)]) == 0
    capsys.readouterr()                       # descarta o aviso da coleta: aqui o teste é do render
    escrever_mudancas(caminho_git(repo.path, "sw-pr-message"), sha_feat, sha_doc)

    assert render.main(["--repo", str(repo.path)]) == 0

    assert "aviso: PR-MESSAGE.md é versionado" in capsys.readouterr().out


def test_pr_message_versionado_como_link_simbolico_e_recusado_sem_escrever_fora(repo, tmp_path, capsys):
    fora = tmp_path / "fora.txt"
    fora.write_text("intocado\n", encoding="utf-8")
    repo.branch("feature/x")
    (repo.path / "PR-MESSAGE.md").symlink_to(fora)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "chore: link")
    sha_link = repo.sha()
    sha_feat = repo.commit("feat: tela", {"tela.py": "x = 1\n"})
    assert collect.main(["--repo", str(repo.path)]) == 0
    escrever_mudancas(caminho_git(repo.path, "sw-pr-message"), sha_feat, sha_link)

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_AMBIENTE

    assert fora.read_text(encoding="utf-8") == "intocado\n"
    assert "link simbólico" in capsys.readouterr().err


def test_recusa_com_commit_esquecido_nao_grava(repo, capsys):
    repo.branch("feature/x")
    sha_a = repo.commit("feat: a", {"a.py": "a = 1\n"})
    repo.commit("fix: b", {"b.py": "b = 1\n"})
    assert collect.main(["--repo", str(repo.path)]) == 0
    escrever_mudancas(caminho_git(repo.path, "sw-pr-message"), sha_a)

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_RECUSA

    assert "commit esquecido" in capsys.readouterr().err
    assert not (repo.path / "PR-MESSAGE.md").exists()


def test_json_malformado_e_recusado(repo, capsys):
    pasta, _ = preparar(repo)
    (pasta / "mudancas.json").write_text("{ isto não é json", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_RECUSA

    assert "JSON malformado" in capsys.readouterr().err
    assert not (repo.path / "PR-MESSAGE.md").exists()


def test_mudancas_ausente_e_recusado(repo, capsys):
    preparar(repo)

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_RECUSA

    assert "mudancas.json não encontrado" in capsys.readouterr().err


def test_mudancas_que_nao_e_objeto_e_recusado(repo, capsys):
    pasta, _ = preparar(repo)
    (pasta / "mudancas.json").write_text("[]", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_RECUSA

    assert "deve ser um objeto JSON" in capsys.readouterr().err


def test_sem_fatos_e_erro_de_ambiente(repo, capsys):
    assert render.main(["--repo", str(repo.path)]) == render.EXIT_AMBIENTE

    assert "rode collect.py antes" in capsys.readouterr().err


def test_fatos_corrompido_e_erro_de_ambiente_sem_traceback(repo, capsys):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    (pasta / "fatos.json").write_text("{ truncado", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_AMBIENTE

    assert "rode collect.py de novo" in capsys.readouterr().err


def test_fatos_de_outra_branch_e_recusado(repo, capsys):
    pasta, sha = preparar(repo)               # coletado em feature/x
    escrever_mudancas(pasta, sha)
    repo.branch("feature/y")

    assert render.main(["--repo", str(repo.path)]) == render.EXIT_AMBIENTE

    assert "feature/x" in capsys.readouterr().err
    assert not (repo.path / "PR-MESSAGE.md").exists()


def test_render_fora_de_repositorio_e_erro_de_ambiente(tmp_path, capsys):
    assert render.main(["--repo", str(tmp_path)]) == render.EXIT_AMBIENTE

    assert "Não é um repositório git" in capsys.readouterr().err


def test_repo_inexistente_e_erro_de_ambiente(tmp_path, capsys):
    assert render.main(["--repo", str(tmp_path / "nao-existe")]) == render.EXIT_AMBIENTE

    assert "não existe" in capsys.readouterr().err


def test_repo_por_subdiretorio_grava_na_raiz(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    sub = repo.path / "src"
    sub.mkdir()

    assert render.main(["--repo", str(sub)]) == 0

    assert (repo.path / "PR-MESSAGE.md").exists() and not (sub / "PR-MESSAGE.md").exists()


def test_exclude_sem_quebra_final_recebe_linha_separada(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    exclude = caminho_git(repo.path, "info/exclude")
    exclude.write_text("*.log", encoding="utf-8")

    assert render.main(["--repo", str(repo.path)]) == 0

    assert exclude.read_text(encoding="utf-8").splitlines()[-2:] == ["*.log", "/PR-MESSAGE.md"]


def test_sem_pasta_info_ela_e_criada(repo):
    pasta, sha = preparar(repo)
    escrever_mudancas(pasta, sha)
    shutil.rmtree(caminho_git(repo.path, "info"))

    assert render.main(["--repo", str(repo.path)]) == 0

    assert caminho_git(repo.path, "info/exclude").read_text(encoding="utf-8").strip() == "/PR-MESSAGE.md"


def test_worktree_resolve_intermediarios_e_exclude_pelo_git_path(repo, tmp_path):
    wt = tmp_path / "wt"
    repo.git("worktree", "add", str(wt), "-b", "feature/wt")
    outro = Repo(wt)
    sha = outro.commit("feat: algo no worktree", {"wt.py": "x = 1\n"})

    assert collect.main(["--repo", str(wt)]) == 0
    pasta = caminho_git(wt, "sw-pr-message")
    escrever_mudancas(pasta, sha)
    assert render.main(["--repo", str(wt)]) == 0

    assert (wt / ".git").is_file()
    assert (pasta / "fatos.json").exists()
    assert (wt / "PR-MESSAGE.md").exists()
    assert outro.git("check-ignore", "PR-MESSAGE.md").strip() == "PR-MESSAGE.md"
```

- [x] **Step 3: Rodar e confirmar que falha pelo motivo certo**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_render_gravar.py -q`
Expected: FAIL com `AttributeError: module 'render' has no attribute 'main'`.

- [x] **Step 4: Implementar** — acrescentar ao final de `scripts/render.py`:

```python
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
```

- [x] **Step 5: Rodar e confirmar que passa**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest -q`
Expected: todos passam (suíte inteira, inclusive Tasks 1–6).

- [x] **Step 6: Checkpoint** — pausa de aprovação (ver "Execução" no topo). Sem commit: `~/.claude/skills` não é repositório git.

---

### Task 8: restrições verificáveis (fitness functions)

FF1 dinâmica já está nos testes do `gitcmd` (Task 1) e FF4 nos da montagem (Task 6). Aqui entram as
checagens estáticas e as de ponta a ponta.

**Files:**
- Test: `~/.claude/skills/sw-pr-message/tests/test_fitness.py`

- [x] **Step 1: Escrever os testes**

`tests/test_fitness.py`:

```python
import ast
import hashlib
import re
import socket
from pathlib import Path

import collect
import render
from fluxo import escrever_mudancas
from lib.gitcmd import caminho_git

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PYS = sorted(SCRIPTS.rglob("*.py"))
REDE = {"socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "telnetlib"}
EXECUCAO_OS = ("system", "popen", "spawn", "exec", "fork", "posix_spawn")


def _arvores():
    return {p.relative_to(SCRIPTS): ast.parse(p.read_text(encoding="utf-8")) for p in PYS}


def _importados(arvore):
    """Módulos trazidos por import, from-import, __import__("x") e importlib.import_module("x")."""
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module.split(".")[0])
        elif isinstance(no, ast.Call) and no.args and isinstance(no.args[0], ast.Constant):
            alvo = no.func
            nome = alvo.id if isinstance(alvo, ast.Name) else getattr(alvo, "attr", "")
            if nome in ("__import__", "import_module"):
                nomes.add(str(no.args[0].value).split(".")[0])
    return nomes


def _feature(repo):
    repo.branch("feature/x")
    return repo.commit("feat: tela de login", {"login.py": "def entrar():\n    return True\n"})


def test_ff1_subprocess_so_dentro_do_gitcmd():
    fora = sorted(str(rel) for rel, arvore in _arvores().items()
                  if rel.name != "gitcmd.py" and "subprocess" in _importados(arvore))

    assert PYS, "nenhum script encontrado — caminho errado?"
    assert fora == []


def test_ff1_nenhuma_execucao_de_processo_pelo_os():
    achados = []
    for rel, arvore in _arvores().items():
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module == "os":
                achados += [f"{rel}: from os import {a.name}" for a in no.names if a.name.startswith(EXECUCAO_OS)]
            elif (isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name) and no.value.id == "os"
                  and no.attr.startswith(EXECUCAO_OS)):
                achados.append(f"{rel}: os.{no.attr}")

    assert achados == []


def test_ff1_nenhum_shell_true():
    com_shell = [p.relative_to(SCRIPTS) for p in PYS if "shell=True" in p.read_text(encoding="utf-8")]

    assert com_shell == []


def test_ff1_nenhum_formato_que_verifica_assinatura():
    # %G? no log e %(signature) no for-each-ref chamam o gpg configurado
    com_assinatura = [p.relative_to(SCRIPTS) for p in PYS
                      if re.search(r"%G|%\(signature", p.read_text(encoding="utf-8"))]

    assert com_assinatura == []


def test_ff2_nenhum_import_de_rede():
    com_rede = sorted(f"{rel}: {sorted(_importados(arvore) & REDE)}"
                      for rel, arvore in _arvores().items() if _importados(arvore) & REDE)

    assert com_rede == []


def test_ff2_collect_e_render_nao_tentam_abrir_conexao(repo, monkeypatch):
    tentativas = []

    def registrar(*args, **kwargs):
        # registra ANTES de falhar: um `except Exception` no script engoliria a exceção, não o registro
        tentativas.append(args)
        raise OSError("rede proibida neste teste")

    monkeypatch.setattr(socket, "socket", registrar)
    monkeypatch.setattr(socket, "create_connection", registrar)
    sha = _feature(repo)

    assert collect.main(["--repo", str(repo.path)]) == 0
    escrever_mudancas(caminho_git(repo.path, "sw-pr-message"), sha)
    assert render.main(["--repo", str(repo.path)]) == 0

    assert tentativas == []


def _retrato(raiz: Path) -> dict:
    """Conteúdo e data de modificação dos arquivos, e as pastas: pega reescrita, `utime` e pasta criada."""
    retrato = {}
    for p in raiz.rglob("*"):
        if p.is_symlink() or p.is_file():
            st = p.lstat()
            retrato[p] = (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "link", st.st_mtime_ns)
        elif p.is_dir():
            retrato[p] = "pasta"
    return retrato


def test_ff3_scripts_so_escrevem_no_git_path_no_exclude_e_no_pr_message(repo, monkeypatch):
    # tudo que o TESTE escreve acontece antes do retrato: entre os retratos, só os dois scripts
    sha = _feature(repo)
    pasta = caminho_git(repo.path, "sw-pr-message")
    pasta.mkdir(parents=True, exist_ok=True)
    escrever_mudancas(pasta, sha)
    monkeypatch.chdir(repo.path)          # escrita em caminho relativo cairia dentro do retrato
    raiz = repo.path.resolve()
    antes = _retrato(raiz)

    assert collect.main(["--repo", str(repo.path)]) == 0
    assert render.main(["--repo", str(repo.path)]) == 0

    depois = _retrato(raiz)
    permitidos = {caminho_git(repo.path, "info/exclude"), (repo.path / "PR-MESSAGE.md").resolve()}
    mudou = {p for p in set(antes) | set(depois) if antes.get(p) != depois.get(p)}
    fora = sorted(str(p) for p in mudou if p not in permitidos and p != pasta and pasta not in p.parents)
    assert fora == []
```

- [x] **Step 2: Rodar**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest tests/test_fitness.py -q`
Expected: `7 passed`. Aqui não há "red" planejado: as restrições devem valer desde as Tasks 1–7. **Se
algum falhar, é defeito de verdade** — pare e reporte, não afrouxe o teste.

- [x] **Step 3: Suíte completa**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest -q`
Expected: todos passam.

- [x] **Step 4: Checkpoint** — pausa de aprovação.

---

### Task 9: `SKILL.md`

**Files:**
- Create: `~/.claude/skills/sw-pr-message/SKILL.md`

- [x] **Step 1: Escrever o `SKILL.md`**

````markdown
---
name: sw-pr-message
description: >-
  Gera o PR-MESSAGE.md de uma branch — a descrição do pull request pronta para colar no GitHub,
  com as mudanças agrupadas por tipo (Novas funcionalidades, Ajustes, Correções, Removido,
  Segurança, Interno), "Como testar" e, em hotfix, causa, impacto e rollback. Detecta sozinha a
  branch base certa (inclusive em fluxo develop + master), lê commits e diff, junta commits da
  mesma mudança num item só e não deixa commit de fora. Use SEMPRE que o usuário quiser
  descrever ou preparar um PR, ou resumir o que fez na branch — "gera a mensagem do PR",
  "cria a descrição do pull request", "resume o que fiz nessa branch", "o que mudou nessa
  branch", "prepara a branch pra review", "monta o PR", e em inglês "generate a PR message",
  "write the PR description", "summarize my branch". Dispare mesmo sem a palavra "PR".
  NÃO cria nem edita PR no GitHub e não dá push — só gera o arquivo local. NÃO use para
  escrever mensagem de commit (sw-git-commit) nem para revisar código (sw-code-review).
---

# PR Message

Transforma os commits e o diff de uma branch num `PR-MESSAGE.md` no mesmo padrão sempre.
**O script cuida do que tem resposta certa** (base, coleta, validação, formato); **você cuida do
que exige leitura** (juntar commits numa mudança, classificar, escrever).

**Anuncie no início:** "Estou usando a skill sw-pr-message para gerar a mensagem do PR."

## Garantias

- **Só leitura no git.** Os scripts executam apenas comandos git de leitura, por uma lista
  fechada. Não rode `git` de escrita por conta própria durante esta skill.
- **Nunca inventa.** Impacto ou rollback de hotfix sem evidência ficam como comentário
  `<!-- preencher: … -->`, que aparece no editor e some no GitHub.
- **Não cria nem edita PR, não dá push.** O `gh`, se usado, só consulta.
- **O arquivo não vai para commit por engano:** o render registra `/PR-MESSAGE.md` no
  `info/exclude` local.

## Fluxo

### 1. Idioma — a única pergunta

Se o pedido já disser ("em inglês", "in English"), use. Senão, pergunte via `AskUserQuestion`:
**Português** / **English**. Não faça nenhuma outra pergunta.

### 2. Base pelo PR aberto (se houver)

Se o usuário informou a base, use-a como `--base`. Senão, tente descobrir pelo PR já aberto:

```bash
gh auth status >/dev/null 2>&1 && \
  gh pr view --json baseRefName,state --jq 'select(.state=="OPEN") | .baseRefName' 2>/dev/null
```

Saída não vazia → use como `--base` e **anote que veio do `gh`**. Qualquer falha (sem `gh`, sem
login, sem PR) → siga sem `--base`, sem avisar.

### 3. Coletar

```bash
python3 <skill-dir>/scripts/collect.py [--base <nome>]
```

Rode os dois scripts **dentro do repositório** que vai descrever (qualquer subpasta serve): eles usam o
diretório atual. Não faça `cd` para `<skill-dir>`.

- **Exit 0** → imprime o caminho do `fatos.json`, a linha `base: …` com as contagens e, se houver,
  `empate:`, `cortados:` e `aviso:`. **Guarde essas linhas** — elas voltam no passo 6.
- **Exit 2** → mostre a mensagem ao usuário e **pare**. A mensagem já diz o que fazer (ex.: "staging
  já contém a branch · develop: 9 · master: 205 → rode com --base develop").
  **Única exceção:** se a `--base` veio do `gh` e a mensagem é `A base '…' não existe localmente`
  (fork com remoto `upstream`), rode de novo **sem** `--base` e avise o usuário disso no final. Se essa
  nova coleta também parar, mostre a mensagem dela e diga que a base do `gh` foi descartada.
- **Qualquer outro código** (erro inesperado, com traceback) → mostre a saída e pare.

### 4. Escrever o `mudancas.json`

Leia o `fatos.json` inteiro. Escreva `mudancas.json` **na mesma pasta**, todo o texto no idioma
escolhido:

```json
{ "idioma": "pt",
  "titulo": "Pagamento por Pix no checkout",
  "resumo": "Permite cobrar por Pix no checkout, com confirmação automática do gateway.",
  "secoes": { "novas":     [{"texto": "Pagamento por Pix com QR Code", "commits": ["a1b2c3d", "9f8e7d6"]}],
              "ajustes":   [{"texto": "Timeout da cobrança de 30s para 60s", "commits": ["5c4b3a2"]}],
              "correcoes": [], "removido": [], "seguranca": [],
              "interno":   [{"texto": "Serviço de cobrança extraído do controller", "commits": ["1a2b3c4"]}] },
  "como_testar": ["Criar um pedido e escolher Pix", "Pagar o QR Code no ambiente de teste"],
  "sem_item": [{"hash": "7e6d5c4", "motivo": "desfeito pelo commit seguinte"}] }
```

**Regras:**
- **Um item = uma mudança.** Commits do mesmo ajuste viram um item só, com todos os hashes
  (prefixo de 7+ caracteres).
- **Classifique pelo significado, não pelo prefixo do commit.**
  - `novas` — capacidade que não existia.
  - `ajustes` — comportamento existente que mudou (inclusive um `feat` que só altera algo).
  - `correcoes` — o que estava errado e foi corrigido.
  - `removido` — o que deixou de existir.
  - `seguranca` — vulnerabilidade fechada (inclusive um `chore(deps)` com esse efeito).
  - `interno` — refactor, testes, CI, build, docs: sem efeito para quem usa.
- **Commit vago** ("ajustes", "wip") → explique pelo diff. Arquivo com `"cortado": true` não é
  descrito além do que aparece.
- **`sem_item`** só para commit sem efeito líquido (desfeito depois, vazio, wip revertido) — nunca
  para commit difícil de descrever.
- **`titulo`** é uma frase descritiva, sem `feat(x):` nem `[Feature]`. **`resumo`**: 1–3 frases com
  o que muda e por quê. Todo texto vira uma linha só — não use quebra de linha, lista ou título dentro dele.
- **Nome de código** (componente, função, arquivo, comando) vai **entre crases**: `<Select>` solto some
  quando o GitHub renderiza.
- **`como_testar`** só com passos observáveis. Nada a observar (só refactor/testes) → lista vazia.
- **`hotfix`** — se `fatos.hotfix.provavel` for `true`, inclua **obrigatoriamente**
  `{"causa": …, "impacto": …, "rollback": …}`, com `null` em todo campo sem evidência nos commits ou
  no diff. Se for `false`, **não inclua** a chave. Nunca invente impacto ou rollback.

### 5. Renderizar

```bash
python3 <skill-dir>/scripts/render.py
```

- **Exit 0** → `PR-MESSAGE.md` gravado; pode imprimir avisos.
- **Exit 3** → o render lista **todos** os problemas. Corrija todos no `mudancas.json` e rode de
  novo. **Na 3ª recusa seguida, pare** e mostre os problemas ao usuário.
- **Exit 2** → problema de ambiente (`fatos.json` de outra branch, `PR-MESSAGE.md` como link
  simbólico…): mostre a mensagem e pare. Não mexa no `mudancas.json` — ele não é a causa.
- **Qualquer outro código** (erro inesperado, com traceback) → mostre a saída e pare.

### 6. Informar

Termine com:
- caminho do `PR-MESSAGE.md`;
- **base e como foi detectada**, copiando a linha `base:` da coleta (`base: develop (origin/develop) ·
  heuristica · 9 commit(s) · develop 9 · master 205`) e a de `empate:`, se houver — se a base estiver
  errada, o usuário refaz com `--base`;
- se a `--base` veio do PR aberto (`gh`), diga isso — a linha `base:` mostra `informada`, mas quem
  informou foi o PR, não o usuário; se ela foi descartada no passo 3, diga isso também;
- avisos da coleta e do render (ex.: `pr_message_versionado` — o exclude não protege arquivo versionado);
- arquivos cortados, se houver;
- quantos campos de hotfix ficaram como `<!-- preencher -->`;
- **sempre**, como última linha: "Só entram mudanças commitadas — o que não foi commitado ficou de fora."

## Limites

- Descreve **commits**: mudança não commitada fica de fora. Os scripts não leem o working tree (o
  `git status` executaria filtros configurados), por isso isso é um lembrete fixo, não uma detecção.
- Branch saída de `release/*` ou empilhada sobre outra feature pode ter a base errada — por isso a
  base aparece no final.
- Clone raso, clone parcial, HEAD destacado e rebase em andamento não são suportados (a coleta para).
````

- [x] **Step 2: Conferir o frontmatter**

Run: `head -3 ~/.claude/skills/sw-pr-message/SKILL.md`
Expected: `---` / `name: sw-pr-message` / `description: >-`

- [x] **Step 3: Checkpoint** — pausa de aprovação.

---

### Task 10: validação real (manual, somente leitura)

Comportamento do agente (uso do `gh`, nova tentativa sem `--base`, parada na 3ª recusa) não tem teste
em pytest — é validado aqui. **Nada do repositório usado entra neste dossiê nem em commit** (o
marketplace é público).

- [x] **Step 1: Escolher o repositório**

Um repositório local **fora deste marketplace** com `develop`, `master` e uma branch de feature
com alguns commits. **Não troque a branch do repositório original:** clone-o para a pasta temporária
(`git clone -q --no-local <repo> <tmp>/validacao`) e faça checkout da branch de feature no clone — as
`origin/*` do clone são as branches do original, então a detecção de base vê o mesmo cenário.

- [x] **Step 2: Registrar o estado antes**

Run (dentro do repositório escolhido): `git status --porcelain; git rev-parse HEAD`
Expected: anote a saída.

- [x] **Step 3: Rodar a skill explicitamente**

Invoque `/sw-pr-message` — **pelo nome**, porque a `sw-git-pr-generator` ainda existe e dispara nas
mesmas frases. Escolha **Português**.

- [x] **Step 4: Conferir o resultado**

- Base informada no final bate com `git rev-list --count --no-merges <base>..HEAD` para cada
  candidato, e é a de menor contagem.
- Todo commit de `git log --no-merges --format=%h <base>..HEAD` aparece em algum item ou em `sem_item`
  do `mudancas.json`.
- Seções na ordem fixa, sem emoji, título sem prefixo, sem hash no texto.

- [x] **Step 5: Conferir que só leu**

Run: `git status --porcelain; git rev-parse HEAD`
Expected: igual ao Step 2 (o `PR-MESSAGE.md` não aparece: está no `info/exclude`).

- [x] **Step 5b: Comportamento do agente com `gh` falso**

O `gh` de verdade não serve no clone (o remoto é local). Ponha um falso no `PATH`, só para esta checagem:

```sh
#!/bin/sh
# gh falso da validação: login ok e PR aberto cuja base vem do arquivo base-do-pr
case "$1 $2" in
  "auth status") exit 0 ;;
  "pr view") cat "$(dirname "$0")/base-do-pr"; exit 0 ;;
esac
exit 1
```

Siga os passos 2 e 3 do `SKILL.md` a partir de uma **subpasta** do clone, duas vezes:
- `base-do-pr` = uma branch que não existe → coleta para com `A base '…' não existe localmente`; nova
  coleta sem `--base` detecta a base pela heurística e o render grava.
- `base-do-pr` = a base certa → linha `base: … · informada ·`, relatada ao usuário como vinda do PR.

Resultado (Lote 5): os dois casos como descrito, e o clone igual ao do Step 2. Agrupamento conferido numa
branch: commits de dependência junto da funcionalidade que as usa, testes em `interno`. **Não exercitado:**
a parada na 3ª recusa — o render aceitou na primeira tentativa; a regra fica só no `SKILL.md`.

- [x] **Step 6: Registrar o que falhou**

Anote no chat (não no dossiê) o que divergiu. Divergência de comportamento → **atualize o plano** com
uma task de correção antes de seguir. Apague o `PR-MESSAGE.md` gerado se não quiser mantê-lo.

- [x] **Step 7: Checkpoint** — pausa de aprovação.

---

### Task 11: publicar no marketplace

**Files:**
- Create (via sync): `/var/www/ai-marketplace/plugins/sw-pr-message/`
- Modify: `/var/www/ai-marketplace/CHANGELOG.md`

- [x] **Step 1: Suíte verde antes de publicar**

Run: `cd ~/.claude/skills/sw-pr-message && .venv/bin/python -m pytest -q`
Expected: todos passam.

- [x] **Step 2: Sincronizar**

Run: `cd /var/www/ai-marketplace && make sync SKILL=sw-pr-message CATEGORY=development`
Expected: `→ Sync 'sw-pr-message'  (categoria: development, versão: 0.1.0)` e nenhum `⚠`.

- [x] **Step 3: Conferir que ambiente local não vazou para o plugin**

Run: `find /var/www/ai-marketplace/plugins/sw-pr-message \( -name .venv -o -name __pycache__ -o -name .pytest_cache \) | wc -l`
Expected: `0`

- [x] **Step 4: Registrar no `CHANGELOG.md`** — em `## [Não publicado]`, seção `### Adicionado`
(criar a seção se não existir), como primeiro item:

```markdown
- `sw-pr-message` (v0.1.0): **gera o `PR-MESSAGE.md` de uma branch com as mudanças agrupadas por
  tipo** — Novas funcionalidades, Ajustes, Correções, Removido, Segurança, Interno, Como testar e,
  em hotfix, causa/impacto/rollback. Substitui a `sw-git-pr-generator`, que listava um item por
  commit, lia só o assunto e escolhia a base em ordem fixa `main → master → develop` (num caso
  medido, descreveria 205 commits em vez de 9). A base agora é o candidato com menos commits à
  frente, parando quando a branch já está contida num deles; os commits vêm sem merges e o diff a
  partir do merge-base. Script coleta e valida, agente interpreta: o render recusa commit esquecido
  e garante ordem, títulos, idioma e ausência de emoji. Os scripts só executam git de leitura (lista
  fechada, recusa por prefixo, `--end-of-options`), não acessam a rede e só escrevem no `git-path`,
  no `info/exclude` e no `PR-MESSAGE.md` — as quatro restrições têm teste.
```

- [x] **Step 5: Gate de segurança**

Run: `cd /var/www/ai-marketplace && make check`
Expected: `✓ gate de segurança: nada sensível detectado`

- [x] **Step 6: Checkpoint com commit** — perguntar "Commitar agora?"; se sim, `sw-git-commit` (ou
`feat(sw-pr-message): …` só com `plugins/sw-pr-message/`, `.claude-plugin/marketplace.json`,
`README.md` e `CHANGELOG.md`).

---

### Task 12: integrar `sw-code-review` e `sw-plan`

**Files:**
- Modify: `~/.claude/skills/sw-code-review/SKILL.md` (seção "Limites")
- Modify: `~/.claude/skills/sw-plan/SKILL.md` (seção "Regras comuns aos dois modos")
- Modify: `/var/www/ai-marketplace/CHANGELOG.md`

- [x] **Step 1: Trocar a menção na `sw-code-review`**

Run:
```bash
python3 - <<'PY'
from pathlib import Path
p = Path.home() / ".claude/skills/sw-code-review/SKILL.md"
antes = "Para gerar a mensagem do PR a partir dos commits, a `sw-git-pr-generator`."
depois = "Para gerar a mensagem do PR a partir dos commits, a `sw-pr-message`."
t = p.read_text(encoding="utf-8")
assert t.count(antes) == 1, "trecho não encontrado exatamente uma vez"
p.write_text(t.replace(antes, depois), encoding="utf-8")
print("ok")
PY
```
Expected: `ok`

- [x] **Step 2: Acrescentar a oferta na `sw-plan`**

Run:
```bash
python3 - <<'PY'
from pathlib import Path
p = Path.home() / ".claude/skills/sw-plan/SKILL.md"
ancora = "- **Plano é a fonte da verdade:**"
novo = ("- **Mensagem de PR ao concluir (se for git):** ao terminar todas as tasks, se a branch atual\n"
        "  tiver commits que ainda não estão na base, **ofereça via `AskUserQuestion`** gerar a descrição\n"
        "  do PR com a skill **`sw-pr-message`** (se estiver disponível). Só oferece — não gera sem o \"sim\".\n")
t = p.read_text(encoding="utf-8")
assert t.count(ancora) == 1, "âncora não encontrada exatamente uma vez"
assert "sw-pr-message" not in t, "já integrado"
p.write_text(t.replace(ancora, novo + ancora), encoding="utf-8")
print("ok")
PY
```
Expected: `ok`

- [x] **Step 3: Sincronizar com bump**

Run:
```bash
cd /var/www/ai-marketplace
make sync SKILL=sw-code-review BUMP=patch
make sync SKILL=sw-plan BUMP=minor
```
Expected: `sw-code-review` em `0.1.1` e `sw-plan` em `0.4.0`, sem `⚠`.

- [x] **Step 4: Registrar no `CHANGELOG.md`** — em `## [Não publicado]`, `### Alterado`, como primeiros itens:

```markdown
- `sw-plan` (v0.4.0): ao concluir todas as tasks, oferece gerar a descrição do PR com a
  `sw-pr-message` quando a branch tem commits fora da base.
- `sw-code-review` (v0.1.1): passa a indicar a `sw-pr-message` para gerar a mensagem do PR.
```

- [x] **Step 5: Gate de segurança**

Run: `cd /var/www/ai-marketplace && make check`
Expected: `✓ gate de segurança: nada sensível detectado`

- [x] **Step 6: Checkpoint com commit** — perguntar "Commitar agora?".

---

### Task 13: remover a skill antiga e fechar o dossiê

- [x] **Step 1: Confirmar que nada mais aponta para a skill antiga**

Run: `grep -rn "sw-git-pr-generator" ~/.claude/skills --include="*.md" | grep -v "^$HOME/.claude/skills/sw-git-pr-generator/"`
Expected: nenhuma linha.

- [x] **Step 2: Apagar**

Run: `rm -rf ~/.claude/skills/sw-git-pr-generator && ls ~/.claude/skills | grep -c pr-generator`
Expected: `0`

- [x] **Step 3: Fechar o dossiê**

Run: `cd /var/www/ai-marketplace && python3 ~/.claude/skills/sw-brainstorming/scripts/dossie.py estado 2026-09-10-sw-pr-message concluido`
Expected: `2026-09-10-sw-pr-message → concluido`

- [x] **Step 4: Gate de segurança**

Run: `cd /var/www/ai-marketplace && make check`
Expected: `✓ gate de segurança: nada sensível detectado`

- [x] **Step 5: Checkpoint final com commit** — perguntar "Commitar agora?" (dossiê `spec.md`,
`plan.md`, `referencias/` e `docs/specs/README.md`). **Push só com aprovação explícita.**

- [x] **Step 6: Oferecer a própria `sw-pr-message`** — este plano rodou no `master`, então não há
branch para descrever aqui; registre isso no resumo final em vez de oferecer.
