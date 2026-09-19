# Diagnóstico de testes na sw-auto-test — Implementation Plan

> **Execucao:** Implementar este plano task-by-task. Steps usam checkbox (`- [ ]`) para tracking. Ver secao "Execution Handoff" da skill `sw-plan` para os 2 modos de execucao disponiveis.

**Goal:** dar à skill `sw-auto-test` um modo **diagnóstico** dos testes que já existem (relatório + correção guiada) e fechar os furos do modo **gerar** (baseline, prova do vermelho, determinismo, proibição de forçar verde).

**Architecture:** script apura fatos com a ferramenta nativa da stack e grava JSON; o agente lê os fatos e só os arquivos suspeitos, e escreve `achados.json`; um segundo script valida e monta o `test-health-report.md`. Mesmo desenho da `sw-pr-message` (script decide o que tem resposta certa; agente decide o que exige leitura).

**Tech Stack:** Python 3 (só stdlib) · pytest para a suíte da própria skill · git de leitura · runners nativos (pytest, vitest/jest, phpunit) chamados por linha de comando.

Spec: [spec.md](spec.md)

---

## Como executar este plano

- **Onde:** a skill vive em `~/.claude/skills/sw-auto-test/` (fora do git). O marketplace
  `/var/www/ai-marketplace` recebe só a publicação, no **master**, com commit a cada checkpoint.
- **Suíte da skill:** `cd ~/.claude/skills/sw-auto-test && .venv/bin/python -m pytest -q`
- **Tipos de teste escolhidos:** só **unit**. As quatro restrições verificáveis são provadas
  chamando `main()` **no mesmo processo** dentro de um repositório git temporário, com runners
  falsos no `PATH` — sem infraestrutura, sem rede, sem suíte de integração separada.
- **Segurança (repositório público):** nenhum caminho de home, nome de projeto real, branch ou
  commit de cliente entra no dossiê nem nos commits. `make check` antes de todo commit.

## Ordem dos lotes (do spec)

| Lote | Tasks | Entrega |
|---|---|---|
| 1 | 0–4 | Fundação, backup, detectores e diagnóstico **estático** gravando `fatos.json` |
| 2 | 5–8 | Execução opt-in: descoberta, suíte, cobertura, três stacks nativas |
| 3 | 9–11 | `achados.json`, relatório, notas por dimensão e correção guiada no `SKILL.md` |
| 4 | 12–13 | Modo gerar: baseline, prova do vermelho, determinismo, anti-verde-forçado |
| 5 | 14–16 | `references/`, gatilhos PT-BR, validação real, publicação e bump das irmãs |

Parar depois do lote 3 entrega o diagnóstico inteiro.

## Decisões de implementação que o spec deixou em aberto

| Ponto | Decisão para este plano | Porquê |
|---|---|---|
| Ler estado do working tree | `git status --porcelain -- <arquivo>` é permitido | A `sw-pr-message` proíbe `status` porque executa filtros de limpeza configurados. **Aqui a skill já executa o runner do projeto**, que é ordens de grandeza mais invasivo; proibir `status` seria teatro |
| Descoberta de funções de teste | Regex por declaração, fatiando até a próxima | O spec proíbe o script de virar parser; o que a regex erra vira confiança média, nunca lote automático |
| Pasta de fatos | `<git-path>/sw-auto-test/`, ou `tempfile.gettempdir()/sw-auto-test-<hash do caminho>` sem git | Igual à `sw-pr-message`; fora da árvore de trabalho |

## Estrutura de arquivos

```
~/.claude/skills/sw-auto-test/
  SKILL.md                     (< 220 linhas ao fim do lote 5)
  references/
    frameworks.md              matriz linguagem × tipo (movida do SKILL.md)
    aaa-por-linguagem.md       os seis exemplos (movidos do SKILL.md)
    generation.md              detalhes do modo gerar
    diagnostico.md             catálogo de regras e o que cada uma significa
  scripts/
    diagnose.py                CLI da apuração        → fatos.json
    report.py                  CLI do relatório       → test-health-report.md
    backup.py                  CLI: varrer/restaurar resíduo
    lib/
      gitinfo.py               git de leitura: toplevel, git-path, branch, head, arquivo limpo
      pastas.py                onde ficam fatos, backups e saída do runner
      sinais.py                detectores textuais com id estável
      inventario.py            varre os diretórios de teste: arquivos, testes, suíte por caminho
      stacks/__init__.py       escolhe o módulo da stack
      stacks/base.py           contrato: detectar, descobrir, rodar, cobertura, normalizar
      stacks/py.py             pytest
      stacks/js.py             vitest e jest
      stacks/php.py            phpunit
      backup.py                guardar, restaurar, varrer resíduo
  tests/
    conftest.py                sys.path + isolamento de config do git
    gitrepo.py                 repositório git de verdade dentro do teste
    projeto.py                 monta projeto-fixture por stack (arquivos de teste realistas)
    runners.py                 fabrica runner FALSO no PATH com saída canônica
    test_*.py                  um arquivo por unidade
```

---

### Task 0: Ambiente e ajudantes de teste

**Files:**
- Create: `~/.claude/skills/sw-auto-test/scripts/lib/__init__.py`, `scripts/lib/stacks/__init__.py`
- Create: `~/.claude/skills/sw-auto-test/tests/conftest.py`, `tests/gitrepo.py`, `tests/projeto.py`, `tests/runners.py`
- Create: `~/.claude/skills/sw-auto-test/tests/test_ajudantes.py`

- [x] **Step 1: Criar venv e pastas**

```bash
cd ~/.claude/skills/sw-auto-test
python3 -m venv .venv && .venv/bin/pip -q install pytest
mkdir -p scripts/lib/stacks tests references
touch scripts/lib/__init__.py scripts/lib/stacks/__init__.py
.venv/bin/python -m pytest --version
```
Expected: `pytest 9.x`

- [x] **Step 2: `tests/conftest.py`**

```python
"""Deixa `import diagnose`, `import report` e `import lib.x` funcionarem nos testes."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gitrepo import Repo  # noqa: E402


@pytest.fixture(autouse=True)
def _git_isolado(monkeypatch):
    """Os scripts herdam o ambiente: sem isto, a config global de quem roda vazaria."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repo(tmp_path):
    """Repositório git novo, na branch master, com um commit inicial."""
    return Repo.novo(tmp_path / "projeto")
```

- [x] **Step 3: `tests/gitrepo.py`**

```python
"""Repositórios git de verdade para os testes — isolados da configuração de quem roda."""
import os
import subprocess
from pathlib import Path

ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Teste", "GIT_AUTHOR_EMAIL": "teste@example.com",
    "GIT_COMMITTER_NAME": "Teste", "GIT_COMMITTER_EMAIL": "teste@example.com",
    "GIT_TERMINAL_PROMPT": "0",
}


class Repo:
    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def novo(cls, path):
        path = Path(path)
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "master", str(path)], env=ENV, check=True)
        r = cls(path)
        r.escrever({"README.md": "inicial\n"})
        r.commit("chore: inicial")
        return r

    def git(self, *args, check=True) -> str:
        r = subprocess.run(["git", *args], cwd=self.path, env=ENV, capture_output=True, text=True)
        if check and r.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} falhou: {r.stderr}")
        return r.stdout

    def escrever(self, arquivos: dict):
        """Escreve arquivos (str) relativos à raiz, criando as pastas."""
        for nome, conteudo in arquivos.items():
            destino = self.path / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(conteudo, encoding="utf-8")

    def commit(self, mensagem) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", mensagem)
        return self.git("rev-parse", "HEAD").strip()
```

- [x] **Step 4: `tests/runners.py` — o runner FALSO**

```python
"""Runner falso no PATH: devolve saída canônica sem instalar pytest/vitest/phpunit de verdade.

Cada runner falso grava em `registro` (um arquivo texto) a linha de comando que recebeu — é
assim que os testes provam O QUE foi executado, e que nada rodou sem aprovação.
"""
import os
import stat
from pathlib import Path

MOLDE = """#!/usr/bin/env python3
import sys, pathlib
registro = pathlib.Path({registro!r})
with registro.open("a", encoding="utf-8") as f:
    f.write(" ".join([pathlib.Path(sys.argv[0]).name, *sys.argv[1:]]) + "\\n")
saidas = {saidas!r}
for gatilho, (texto, arquivo, conteudo, codigo) in saidas.items():
    # casa por CONTEÚDO do argumento: o runner recebe --junit-xml=<caminho> num argumento só
    if gatilho != "__padrao__" and any(gatilho in argumento for argumento in sys.argv):
        if arquivo:
            destino = pathlib.Path([a.split("=")[-1].split(":")[-1] for a in sys.argv if arquivo in a][0])
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(conteudo, encoding="utf-8")
        sys.stdout.write(texto)
        sys.exit(codigo)
sys.stdout.write(saidas["__padrao__"][0] if "__padrao__" in saidas else "")
sys.exit(0)
"""


def instalar(tmp_path, monkeypatch, nome, saidas) -> Path:
    """Cria o executável `nome` numa pasta que entra no início do PATH.

    `saidas` mapeia um argumento-gatilho para (stdout, marcador_de_arquivo, conteúdo, exit code).
    Use o gatilho "__padrao__" para o caso sem correspondência.
    Devolve o caminho do arquivo de registro das chamadas.
    """
    pasta = Path(tmp_path) / "bin"
    pasta.mkdir(exist_ok=True)
    registro = Path(tmp_path) / f"chamadas-{nome}.txt"
    alvo = pasta / nome
    alvo.write_text(MOLDE.format(registro=str(registro), saidas=saidas), encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{pasta}{os.pathsep}{os.environ['PATH']}")
    return registro


def chamadas(registro) -> list:
    """Linhas de comando que o runner falso recebeu (vazio se nunca foi chamado)."""
    caminho = Path(registro)
    return caminho.read_text(encoding="utf-8").splitlines() if caminho.exists() else []
```

- [x] **Step 5: `tests/projeto.py` — projetos-fixture por stack**

```python
"""Projetos de teste realistas o bastante para os detectores terem o que achar."""

PYTEST_BOM = '''\
def test_soma_dois_numeros():
    assert somar(2, 2) == 4
'''

PYTEST_RUIM = '''\
import time, random
from datetime import datetime


def test_sem_assercao():
    resultado = calcular(1)
    print(resultado)


@pytest.mark.skip(reason="quebrou")
def test_desligado():
    assert False


def test_espera_e_relogio():
    time.sleep(2)
    assert datetime.now().year > 2000


def test_aleatorio():
    assert random.randint(1, 10) > 0
'''

VITEST_RUIM = '''\
import { it, expect } from 'vitest';

it.skip('desligado', () => { expect(1).toBe(1); });

it('sem assercao', () => { montarCarrinho(); });

it('usa relogio real', async () => {
  await new Promise(r => setTimeout(r, 500));
  expect(new Date().getFullYear()).toBeGreaterThan(2000);
});

it('nome repetido', () => { expect(2).toBe(2); });

it('nome repetido', () => { expect(3).toBe(3); });
'''

PHPUNIT_RUIM = '''\
<?php
class CarrinhoTest extends TestCase
{
    public function test_sem_assercao(): void
    {
        $carrinho = new Carrinho();
        $carrinho->adicionar(1);
    }

    public function test_pulado(): void
    {
        $this->markTestSkipped('instavel');
    }

    public function test_rede(): void
    {
        $resposta = file_get_contents('http://api.exemplo/itens');
        $this->assertNotEmpty($resposta);
    }
}
'''


def projeto_pytest(repo):
    """pyproject + tests/unit com um teste bom e vários problemáticos."""
    repo.escrever({
        "pyproject.toml": "[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
        "src/calculadora.py": "def somar(a, b):\n    return a + b\n",
        "tests/unit/test_calculadora.py": PYTEST_BOM,
        "tests/unit/test_problemas.py": PYTEST_RUIM,
    })
    repo.commit("chore: projeto python")
    return repo


def projeto_vitest(repo):
    repo.escrever({
        "package.json": '{"name": "app", "devDependencies": {"vitest": "^2.0.0"}}\n',
        "vitest.config.ts": "export default {};\n",
        "src/carrinho.ts": "export function montarCarrinho() { return []; }\n",
        "tests/unit/carrinho.test.ts": VITEST_RUIM,
    })
    repo.commit("chore: projeto js")
    return repo


def projeto_phpunit(repo):
    repo.escrever({
        "composer.json": '{"require-dev": {"phpunit/phpunit": "^11.0"}}\n',
        "phpunit.xml": "<phpunit><testsuites><testsuite name='Unit'>"
                       "<directory>tests/Unit</directory></testsuite></testsuites></phpunit>\n",
        "src/Carrinho.php": "<?php class Carrinho { public function adicionar($id) {} }\n",
        "tests/Unit/CarrinhoTest.php": PHPUNIT_RUIM,
    })
    repo.commit("chore: projeto php")
    return repo
```

- [x] **Step 6: Escrever o teste dos ajudantes**

```python
from gitrepo import Repo
from projeto import projeto_phpunit, projeto_pytest, projeto_vitest
from runners import chamadas, instalar


def test_repo_nasce_em_master_com_um_commit(repo):
    assert repo.git("branch", "--show-current").strip() == "master"
    assert repo.git("rev-list", "--count", "HEAD").strip() == "1"


def test_projetos_fixture_ficam_versionados(repo):
    projeto_pytest(repo)

    assert (repo.path / "tests/unit/test_problemas.py").exists()
    assert repo.git("status", "--porcelain").strip() == ""


def test_runner_falso_responde_e_registra_a_chamada(tmp_path, monkeypatch):
    import subprocess

    registro = instalar(tmp_path, monkeypatch, "pytest", {
        "--collect-only": ("tests/unit/test_a.py::test_x\n", None, None, 0),
        "__padrao__": ("1 passed\n", None, None, 0),
    })

    saida = subprocess.run(["pytest", "--collect-only", "-q"], capture_output=True, text=True)

    assert saida.stdout == "tests/unit/test_a.py::test_x\n"
    assert chamadas(registro) == ["pytest --collect-only -q"]


def test_runner_falso_so_registra_quando_e_chamado(tmp_path, monkeypatch):
    import shutil
    import subprocess

    registro = instalar(tmp_path, monkeypatch, "vitest", {"__padrao__": ("ok\n", None, None, 0)})

    assert shutil.which("vitest"), "o runner falso precisa estar no PATH"
    assert chamadas(registro) == []

    subprocess.run(["vitest", "run"], capture_output=True, text=True)

    assert chamadas(registro) == ["vitest run"]


def test_projetos_js_e_php_montam_os_testes_esperados(repo, tmp_path):
    from lib import sinais

    projeto_vitest(repo)
    outro = projeto_phpunit(Repo.novo(tmp_path / "php"))

    js = (repo.path / "tests/unit/carrinho.test.ts").read_text(encoding="utf-8")
    php = (outro.path / "tests/Unit/CarrinhoTest.php").read_text(encoding="utf-8")

    assert [bloco[0] for bloco in sinais.blocos(js)] == [
        "desligado", "sem assercao", "usa relogio real", "nome repetido", "nome repetido"]
    assert [bloco[0] for bloco in sinais.blocos(php)] == [
        "test_sem_assercao", "test_pulado", "test_rede"]
```

- [x] **Step 7: Rodar**

Run: `cd ~/.claude/skills/sw-auto-test && .venv/bin/python -m pytest -q`
Expected: `5 passed`

- [x] **Step 8: Checkpoint** — pausa de aprovação (sem commit: nada aqui vive no marketplace ainda).

---

### Task 1: `lib/gitinfo.py` e `lib/pastas.py` — onde as coisas moram

**Files:**
- Create: `scripts/lib/gitinfo.py`, `scripts/lib/pastas.py`
- Test: `tests/test_gitinfo.py`, `tests/test_pastas.py`

- [x] **Step 1: Escrever os testes**

```python
# tests/test_gitinfo.py
from pathlib import Path

import pytest

from lib.gitinfo import GitIndisponivel, branch, dentro_de_repo, head, limpo, rastreado, toplevel, git_path


def test_reconhece_repositorio_e_devolve_a_raiz(repo):
    assert dentro_de_repo(repo.path) is True
    assert toplevel(repo.path) == repo.path.resolve()


def test_fora_de_repositorio_responde_falso(tmp_path):
    solto = tmp_path / "sem-git"
    solto.mkdir()

    assert dentro_de_repo(solto) is False
    with pytest.raises(GitIndisponivel):
        toplevel(solto)


def test_branch_e_head(repo):
    assert branch(repo.path) == "master"
    assert len(head(repo.path)) == 40


def test_git_path_funciona_tambem_em_worktree(repo, tmp_path):
    wt = tmp_path / "wt"
    repo.git("worktree", "add", "-q", str(wt), "-b", "outra")

    assert git_path(repo.path, "sw-auto-test") == (repo.path / ".git" / "sw-auto-test").resolve()
    assert git_path(wt, "info/exclude") == (repo.path / ".git" / "info" / "exclude").resolve()


def test_limpo_distingue_arquivo_intocado_de_alterado(repo):
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")

    assert limpo(repo.path, "src/a.py") is True
    (repo.path / "src/a.py").write_text("x = 2\n", encoding="utf-8")
    assert limpo(repo.path, "src/a.py") is False


def test_arquivo_nao_versionado_nao_conta_como_limpo(repo):
    (repo.path / "novo.py").write_text("x = 1\n", encoding="utf-8")

    assert rastreado(repo.path, "novo.py") is False
    assert limpo(repo.path, "novo.py") is False


def test_recusa_subcomando_de_escrita(repo):
    from lib import gitinfo

    with pytest.raises(ValueError):
        gitinfo._git(["commit", "-m", "x"], repo.path)
```

```python
# tests/test_pastas.py
import tempfile
from pathlib import Path

from lib import pastas


def test_com_git_grava_dentro_do_diretorio_do_git(repo):
    base = pastas.base(repo.path)

    assert base == (repo.path / ".git" / "sw-auto-test").resolve()
    assert pastas.fatos(repo.path).name == "fatos.json"
    assert pastas.achados(repo.path).name == "achados.json"
    assert pastas.backups(repo.path).parent == base
    assert pastas.saida(repo.path).parent == base


def test_sem_git_cai_no_temporario_do_sistema_por_caminho(tmp_path):
    solto = tmp_path / "sem-git"
    solto.mkdir()

    base = pastas.base(solto)

    assert base.parent == Path(tempfile.gettempdir())
    assert base.name.startswith("sw-auto-test-")
    assert pastas.base(solto) == base, "o mesmo projeto precisa cair sempre na mesma pasta"


def test_projetos_diferentes_nao_compartilham_pasta(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()

    assert pastas.base(a) != pastas.base(b)


def test_criar_faz_a_pasta_existir(repo):
    destino = pastas.criar(repo.path)

    assert destino.is_dir()
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_gitinfo.py tests/test_pastas.py -q`
Expected: erros de import (`ImportError: cannot import name 'branch' from 'lib.gitinfo'`) — os módulos ainda não existem.

- [x] **Step 3: `scripts/lib/gitinfo.py`**

```python
"""git de leitura para esta skill. Nenhum subcomando que escreve entra na lista.

Diferente da sw-pr-message, `status` é permitido: esta skill já executa o runner do projeto,
que é muito mais invasivo do que os filtros de limpeza que o `status` dispara. O que não muda é
a regra de nunca executar git que altere repositório.
"""
import os
import subprocess
from pathlib import Path

LEITURA = frozenset({"rev-parse", "status", "ls-files"})


class GitIndisponivel(Exception):
    """Não é repositório git, ou o comando falhou."""


def _git(args, cwd) -> str:
    args = list(args)
    if not args or args[0] not in LEITURA:
        raise ValueError(f"subcomando não permitido: {args[:1]!r}")
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    r = subprocess.run(["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise GitIndisponivel(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def dentro_de_repo(cwd) -> bool:
    try:
        return _git(["rev-parse", "--is-inside-work-tree"], cwd).strip() == "true"
    except (GitIndisponivel, FileNotFoundError):
        return False


def toplevel(cwd) -> Path:
    return Path(_git(["rev-parse", "--show-toplevel"], cwd).strip()).resolve()


def git_path(cwd, sub: str) -> Path:
    """Certo também em worktree e submódulo, onde `.git` é um arquivo."""
    saida = Path(_git(["rev-parse", "--git-path", sub], cwd).strip())
    return saida if saida.is_absolute() else (Path(cwd) / saida).resolve()


def branch(cwd):
    nome = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd).strip()
    return None if nome == "HEAD" else nome


def head(cwd) -> str:
    return _git(["rev-parse", "HEAD"], cwd).strip()


def rastreado(cwd, caminho) -> bool:
    try:
        return bool(_git(["ls-files", "--error-unmatch", "--", str(caminho)], cwd).strip())
    except GitIndisponivel:
        return False


def limpo(cwd, caminho) -> bool:
    """Versionado e sem alteração pendente — pré-requisito da prova do vermelho."""
    if not rastreado(cwd, caminho):
        return False
    return _git(["status", "--porcelain", "--", str(caminho)], cwd).strip() == ""
```

- [x] **Step 4: `scripts/lib/pastas.py`**

```python
"""Onde ficam fatos, achados, backups e a saída do runner — sempre fora da árvore de trabalho."""
import hashlib
import tempfile
from pathlib import Path

from lib import gitinfo

NOME = "sw-auto-test"


def base(raiz) -> Path:
    """`<git-path>/sw-auto-test` no repositório; no projeto sem git, uma pasta fixa no temp."""
    raiz = Path(raiz)
    if gitinfo.dentro_de_repo(raiz):
        return gitinfo.git_path(raiz, NOME)
    digitais = hashlib.sha256(str(raiz.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"{NOME}-{digitais}"


def criar(raiz) -> Path:
    destino = base(raiz)
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def fatos(raiz) -> Path:
    return base(raiz) / "fatos.json"


def achados(raiz) -> Path:
    return base(raiz) / "achados.json"


def backups(raiz) -> Path:
    return base(raiz) / "backup"


def saida(raiz) -> Path:
    """Onde o runner grava junit/cobertura, por flag explícita."""
    return base(raiz) / "saida"
```

- [x] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest tests/test_gitinfo.py tests/test_pastas.py -q`
Expected: `11 passed`

---

### Task 2: `lib/backup.py` — a garantia de que o arquivo volta

**Files:**
- Create: `scripts/lib/backup.py`
- Test: `tests/test_backup.py`

Esta é a task que sustenta a **restrição verificável 3**. Sem ela, a prova do vermelho não pode existir.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_backup.py
import hashlib
import json

import pytest

from lib import backup, pastas


def sha(caminho):
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_guardar_registra_o_original_e_restaurar_devolve_os_bytes(repo):
    alvo = repo.path / "src/a.py"
    repo.escrever({"src/a.py": "def f():\n    return 1\n"})
    repo.commit("feat: a")
    antes = sha(alvo)

    backup.guardar(repo.path, "src/a.py")
    alvo.write_text("def f():\n    return 999\n", encoding="utf-8")
    backup.restaurar(repo.path, "src/a.py")

    assert sha(alvo) == antes


def test_mutacao_temporaria_restaura_mesmo_com_excecao_no_meio(repo):
    alvo = repo.path / "src/a.py"
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")
    antes = sha(alvo)

    with pytest.raises(RuntimeError):
        with backup.mutacao_temporaria(repo.path, "src/a.py"):
            alvo.write_text("x = 2\n", encoding="utf-8")
            raise RuntimeError("o teste morreu no meio da prova")

    assert sha(alvo) == antes
    assert backup.residuo(repo.path) == [], "backup usado e restaurado não pode ficar pendente"


def test_residuo_de_execucao_anterior_e_detectado_e_limpo(repo):
    alvo = repo.path / "src/a.py"
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")
    antes = sha(alvo)

    backup.guardar(repo.path, "src/a.py")          # simula a sessão morrendo aqui
    alvo.write_text("x = 2\n", encoding="utf-8")

    assert backup.residuo(repo.path) == ["src/a.py"]
    assert backup.restaurar_tudo(repo.path) == {"intacto": [], "sobrescrito": ["src/a.py"]}
    assert sha(alvo) == antes
    assert backup.residuo(repo.path) == []


def test_descartar_apaga_o_backup_sem_mexer_no_arquivo(repo):
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    (repo.path / "src/a.py").write_text("x = 2\n", encoding="utf-8")

    backup.descartar(repo.path, "src/a.py")

    assert backup.residuo(repo.path) == []
    assert (repo.path / "src/a.py").read_text(encoding="utf-8") == "x = 2\n"


def test_guardar_duas_vezes_preserva_o_original_da_primeira(repo):
    alvo = repo.path / "src/a.py"
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")

    backup.guardar(repo.path, "src/a.py")
    alvo.write_text("mexido\n", encoding="utf-8")
    backup.guardar(repo.path, "src/a.py")          # não pode sobrescrever o backup bom
    backup.restaurar(repo.path, "src/a.py")

    assert alvo.read_text(encoding="utf-8") == "original\n"


def test_arquivo_binario_e_sem_final_de_linha_voltam_identicos(repo):
    alvo = repo.path / "dados.bin"
    alvo.write_bytes(b"\x00\x01\x02sem quebra")
    repo.git("add", "-A"); repo.git("commit", "-qm", "chore: bin")
    antes = sha(alvo)

    with backup.mutacao_temporaria(repo.path, "dados.bin"):
        alvo.write_bytes(b"outra coisa")

    assert sha(alvo) == antes


def test_registro_guarda_caminho_relativo_e_hash(repo):
    repo.escrever({"src/a.py": "x = 1\n"})
    repo.commit("feat: a")

    backup.guardar(repo.path, "src/a.py")
    registro = json.loads((pastas.backups(repo.path) / "guardados.json").read_text(encoding="utf-8"))

    assert list(registro) == ["src/a.py"]
    assert len(registro["src/a.py"]["sha256"]) == 64


def test_backup_sumido_do_disco_nao_grava_o_arquivo_mutado_como_original(repo):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    copia = next(p for p in pastas.backups(repo.path).glob("*.bak"))
    copia.unlink()
    (repo.path / "src/a.py").write_text("mutado\n", encoding="utf-8")

    with pytest.raises(backup.BackupSumiu):
        backup.guardar(repo.path, "src/a.py")


def test_restaurar_diz_se_precisou_sobrescrever(repo):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")

    backup.guardar(repo.path, "src/a.py")
    assert backup.restaurar(repo.path, "src/a.py") == "intacto"

    backup.guardar(repo.path, "src/a.py")
    (repo.path / "src/a.py").write_text("mexido\n", encoding="utf-8")
    assert backup.restaurar(repo.path, "src/a.py") == "sobrescrito"


def test_restaurar_tudo_separa_o_que_foi_sobrescrito(repo):
    repo.escrever({"src/a.py": "a\n", "src/b.py": "b\n"})
    repo.commit("feat: dois")
    backup.guardar(repo.path, "src/a.py")
    backup.guardar(repo.path, "src/b.py")
    (repo.path / "src/b.py").write_text("mexido\n", encoding="utf-8")

    assert backup.restaurar_tudo(repo.path) == {"intacto": ["src/a.py"], "sobrescrito": ["src/b.py"]}
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_backup.py -q`
Expected: `ImportError: cannot import name 'backup' from 'lib'` — 7 falhas.

- [x] **Step 3: `scripts/lib/backup.py`**

```python
"""Guarda o original antes de qualquer edição e garante a volta.

Duas formas de uso:
- `mutacao_temporaria` — a alteração é sempre desfeita (prova do vermelho);
- `guardar` + `descartar`/`restaurar` — a alteração fica se der certo, volta se quebrar
  (correção guiada). A reversão usa o backup, nunca `git checkout`, que apagaria trabalho
  não commitado do usuário.
"""
import hashlib
import json
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lib import pastas

REGISTRO = "guardados.json"


class BackupSumiu(Exception):
    """O registro diz que há backup, mas a cópia não está no disco."""


def _registro(raiz) -> Path:
    return pastas.backups(raiz) / REGISTRO


def _ler(raiz) -> dict:
    arquivo = _registro(raiz)
    if not arquivo.exists():
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(raiz, dados):
    arquivo = _registro(raiz)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def _copia(raiz, relativo) -> Path:
    nome = hashlib.sha256(str(relativo).encode("utf-8")).hexdigest()[:16] + ".bak"
    return pastas.backups(raiz) / nome


def guardar(raiz, relativo) -> Path:
    """Copia os bytes do arquivo. Guardar de novo NÃO sobrescreve o backup bom."""
    raiz, relativo = Path(raiz), str(relativo)
    dados = _ler(raiz)
    destino = _copia(raiz, relativo)
    if relativo in dados:
        if destino.exists():
            return destino
        # sem isto, o arquivo JÁ MUTADO seria gravado como "original" e a restauração devolveria lixo
        raise BackupSumiu(f"{relativo}: registro existe, mas a cópia sumiu de {destino}")
    origem = raiz / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origem, destino)
    dados[relativo] = {
        "sha256": hashlib.sha256(origem.read_bytes()).hexdigest(),
        "quando": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _gravar(raiz, dados)
    return destino


def restaurar(raiz, relativo):
    """Devolve "intacto", "sobrescrito" ou False (sem backup).

    O hash guardado serve aqui: ele diz se o arquivo mudou desde o backup, e é isso que o
    chamador informa ao usuário — restaurar por cima de edição feita depois seria perda calada.
    """
    raiz, relativo = Path(raiz), str(relativo)
    dados = _ler(raiz)
    copia = _copia(raiz, relativo)
    if relativo not in dados or not copia.exists():
        return False
    alvo = raiz / relativo
    atual = hashlib.sha256(alvo.read_bytes()).hexdigest() if alvo.exists() else None
    estado = "intacto" if atual == dados[relativo].get("sha256") else "sobrescrito"
    shutil.copyfile(copia, alvo)
    copia.unlink()
    dados.pop(relativo)
    _gravar(raiz, dados)
    return estado


def descartar(raiz, relativo) -> bool:
    """A edição ficou boa: joga fora o backup, sem tocar no arquivo."""
    raiz, relativo = Path(raiz), str(relativo)
    dados = _ler(raiz)
    copia = _copia(raiz, relativo)
    if relativo not in dados:
        return False
    copia.unlink(missing_ok=True)
    dados.pop(relativo)
    _gravar(raiz, dados)
    return True


def residuo(raiz) -> list:
    """O que continua guardado — sobra de execução que morreu no meio."""
    return sorted(_ler(raiz))


def restaurar_tudo(raiz) -> dict:
    """Restaura tudo que ficou pendente, separando o que precisou ser sobrescrito."""
    saida = {"intacto": [], "sobrescrito": []}
    for relativo in residuo(raiz):
        estado = restaurar(raiz, relativo)
        if estado:
            saida[estado].append(relativo)
    return saida


@contextmanager
def mutacao_temporaria(raiz, relativo):
    """Alteração que SEMPRE volta — inclusive se o bloco levantar exceção."""
    guardar(raiz, relativo)
    try:
        yield raiz / relativo
    finally:
        restaurar(raiz, relativo)
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_backup.py -q`
Expected: `7 passed`

- [x] **Step 5: Provar a restrição 3 com o processo morrendo de verdade**

Run:
```bash
cd ~/.claude/skills/sw-auto-test && .venv/bin/python - <<'PY'
import os, signal, subprocess, sys, tempfile, hashlib, pathlib
sys.path.insert(0, "scripts")
from lib import backup
raiz = pathlib.Path(tempfile.mkdtemp())
subprocess.run(["git", "init", "-q", str(raiz)], check=True)
alvo = raiz / "a.py"; alvo.write_text("original\n", encoding="utf-8")
antes = hashlib.sha256(alvo.read_bytes()).hexdigest()
backup.guardar(raiz, "a.py"); alvo.write_text("mutado\n", encoding="utf-8")
print("resíduo detectado:", backup.residuo(raiz))
print("restaurados:", backup.restaurar_tudo(raiz))
print("voltou igual:", hashlib.sha256(alvo.read_bytes()).hexdigest() == antes)
PY
```
Expected: `resíduo detectado: ['a.py']`, `restaurados: ['a.py']`, `voltou igual: True`

- [x] **Step 6: Checkpoint** — pausa de aprovação.

---

### Task 3: `lib/sinais.py` — os detectores textuais

**Files:**
- Create: `scripts/lib/sinais.py`
- Test: `tests/test_sinais.py`

Cada regra tem **id estável** — é o que liga achado do agente a fato do script na validação do
`report.py`. Nenhum detector faz parsing de verdade: o que a regex erra sai como confiança média.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_sinais.py
from pathlib import Path

from lib import sinais
from projeto import PHPUNIT_RUIM, PYTEST_BOM, PYTEST_RUIM, VITEST_RUIM


def regras(achados):
    return sorted({a["regra"] for a in achados})


def test_teste_bom_nao_gera_sinal(tmp_path):
    achados = sinais.varrer(Path("tests/unit/test_calculadora.py"), PYTEST_BOM, "unit")

    assert achados == []


def test_python_ruim_gera_os_sinais_esperados():
    achados = sinais.varrer(Path("tests/unit/test_problemas.py"), PYTEST_RUIM, "unit")

    assert regras(achados) == ["aleatorio_sem_semente", "espera_fixa", "marcado_para_pular",
                               "relogio_real", "sem_assercao_aparente"]


def test_cada_sinal_aponta_o_teste_e_a_linha():
    achados = sinais.varrer(Path("tests/unit/test_problemas.py"), PYTEST_RUIM, "unit")
    pulado = next(a for a in achados if a["regra"] == "marcado_para_pular")

    assert pulado["teste"] == "test_desligado"
    assert PYTEST_RUIM.splitlines()[pulado["linha"] - 1].strip().startswith("@pytest.mark.skip")


def test_js_pega_skip_espera_relogio_e_nome_repetido():
    achados = sinais.varrer(Path("tests/unit/carrinho.test.ts"), VITEST_RUIM, "unit")

    assert regras(achados) == ["espera_fixa", "marcado_para_pular", "nome_duplicado",
                               "relogio_real", "sem_assercao_aparente"]
    duplicado = next(a for a in achados if a["regra"] == "nome_duplicado")
    assert duplicado["teste"] == "nome repetido"


def test_php_pega_skip_sem_assercao_e_rede():
    achados = sinais.varrer(Path("tests/Unit/CarrinhoTest.php"), PHPUNIT_RUIM, "unit")

    assert regras(achados) == ["marcado_para_pular", "rede_em_unit", "sem_assercao_aparente"]


def test_rede_so_vira_sinal_em_suite_unitaria():
    achados = sinais.varrer(Path("tests/Integration/CarrinhoTest.php"), PHPUNIT_RUIM, "integracao")

    assert "rede_em_unit" not in regras(achados)


def test_relogio_congelado_no_arquivo_desliga_o_sinal():
    texto = "from freezegun import freeze_time\n\n\n@freeze_time('2026-01-01')\n" \
            "def test_x():\n    assert datetime.now().year == 2026\n"

    achados = sinais.varrer(Path("tests/unit/test_x.py"), texto, "unit")

    assert regras(achados) == []


def test_aleatorio_com_semente_nao_vira_sinal():
    texto = "import random\n\n\ndef test_x():\n    random.seed(7)\n    assert random.random() < 1\n"

    assert sinais.varrer(Path("tests/unit/test_x.py"), texto, "unit") == []


def test_helper_de_assercao_ainda_gera_sinal_mas_de_confianca_media():
    texto = "def test_x():\n    conferir_total(10)\n"

    achados = sinais.varrer(Path("tests/unit/test_x.py"), texto, "unit")

    assert [a["regra"] for a in achados] == ["sem_assercao_aparente"]
    assert sinais.REGRAS["sem_assercao_aparente"][2] == "media", \
        "helper de asserção dá falso positivo; alta confiança só com plugin de lint"


def test_toda_regra_declara_descricao_dimensao_e_confianca():
    dimensoes = {"confiabilidade", "isolamento", "cobertura", "legibilidade", "velocidade"}

    for identificador, (descricao, dimensao, confianca) in sinais.REGRAS.items():
        assert identificador.islower() and " " not in identificador
        assert descricao and dimensao in dimensoes and confianca in {"alta", "media", "baixa"}


def test_sleep_em_comentario_ou_string_nao_vira_sinal():
    texto = ("def test_x():\n"
             "    # aqui tinha um time.sleep(2) que foi removido\n"
             "    mensagem = 'evite sleep( no teste'\n"
             "    assert mensagem\n")

    assert sinais.varrer(Path("tests/unit/test_x.py"), texto, "unit") == []


def test_only_dentro_de_texto_nao_desliga_o_teste():
    texto = "it('explica o .only( do vitest', () => { expect(1).toBe(1); });\n"

    assert sinais.varrer(Path("tests/unit/a.test.ts"), texto, "unit") == []


def test_rede_mockada_no_arquivo_nao_vira_sinal():
    texto = ("import { vi, it, expect } from 'vitest';\n"
             "vi.mock('./api');\n\n"
             "it('busca itens', async () => {\n"
             "  const r = await fetch('/itens');\n"
             "  expect(r).toBeTruthy();\n"
             "});\n")

    assert sinais.varrer(Path("tests/unit/a.test.ts"), texto, "unit") == []


def test_reconhece_teste_de_go_ruby_e_anotacao():
    go = "func TestSoma(t *testing.T) {\n    t.Error(\"x\")\n}\n"
    ruby = "it 'soma dois numeros' do\n  expect(somar(2, 2)).to eq 4\nend\n"
    java = "@Test\npublic void somaDoisNumeros() {\n    assertEquals(4, somar(2, 2));\n}\n"

    assert [b[0] for b in sinais.blocos(go)] == ["TestSoma"]
    assert [b[0] for b in sinais.blocos(ruby)] == ["soma dois numeros"]
    assert len(sinais.blocos(java)) == 1


def test_catalogo_de_regras_nao_esta_vazio():
    assert len(sinais.REGRAS) >= 7


def test_espera_de_atraso_zero_nao_e_espera_fixa():
    """`setTimeout(r, 0)` é o idioma para drenar promessas pendentes, não uma espera."""
    drenar = ("it('salva', async () => {\n"
              "  await new Promise(r => setTimeout(r, 0));\n"
              "  expect(salvo).toBe(true);\n"
              "});\n")
    esperar = ("it('salva', async () => {\n"
               "  await new Promise(r => setTimeout(r, 500));\n"
               "  expect(salvo).toBe(true);\n"
               "});\n")

    assert sinais.varrer(Path("tests/unit/a.test.ts"), drenar, "unit") == []
    assert [a["regra"] for a in sinais.varrer(Path("tests/unit/a.test.ts"), esperar, "unit")] == \
        ["espera_fixa"]
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_sinais.py -q`
Expected: `ImportError: cannot import name 'sinais' from 'lib'` — 10 falhas.

- [x] **Step 3: `scripts/lib/sinais.py`**

```python
"""Detectores textuais de problema em teste. Id estável por regra; nenhum parser de verdade.

O que a regex não consegue decidir com segurança sai como confiança **media** — e confiança média
nunca entra em lote de correção automática. Comentário e literal de texto são **mascarados** antes
da busca: `sleep(` citado num comentário não é espera fixa.
"""
import re

# id -> (descrição, dimensão, confiança)
REGRAS = {
    "sem_assercao_aparente": ("teste sem asserção aparente", "confiabilidade", "media"),
    "marcado_para_pular": ("teste desligado (skip/xfail/only)", "confiabilidade", "alta"),
    "espera_fixa": ("espera fixa dentro do teste", "isolamento", "alta"),
    "relogio_real": ("relógio real sem congelar", "isolamento", "media"),
    "aleatorio_sem_semente": ("aleatório sem semente", "isolamento", "media"),
    "rede_em_unit": ("chamada de rede em teste unitário", "isolamento", "alta"),
    "nome_duplicado": ("nome de teste repetido no arquivo", "legibilidade", "alta"),
}

_DECLARACAO = re.compile(
    r"^[ \t]*(?:async[ \t]+)?def[ \t]+(?P<py>test_\w+)"
    r"|^[ \t]*(?:it|test)(?:\.\w+)?[ \t]*\([ \t]*['\"`](?P<js>[^'\"`]+)"
    r"|^[ \t]*(?:public[ \t]+)?function[ \t]+(?P<php>test\w+)"
    r"|^[ \t]*func[ \t]+(?P<go>Test\w+)[ \t]*\("
    r"|^[ \t]*it[ \t]+['\"](?P<rb>[^'\"]+)['\"][ \t]*do",
    re.M)
# Java, C# e Rust marcam o teste por anotação; é o suficiente para CONTAR sem virar parser.
_ANOTACAO = re.compile(r"^[ \t]*(?:@Test\b|\[Fact\]|\[Test\]|#\[test\])", re.M)
_DECORADOR = re.compile(r"^[ \t]*(?:@|#\[)")

_ASSERCAO = re.compile(r"\bassert\w*\s*[\(\s]|\bexpect\s*\(|->assert|\$this->assert|\.should\b|t\.Error")
_PULAR = re.compile(r"@pytest\.mark\.(skip|xfail)|pytest\.skip\(|@unittest\.skip|"
                    r"\b(?:it|test|describe)\.(?:skip|only)\(|@Ignore\b|"
                    r"markTestSkipped|markTestIncomplete|t\.Skip\(")
_ESPERA = re.compile(r"time\.sleep\(|(?<![\w.])sleep\(|Thread\.sleep\(|usleep\(|"
                     r"setTimeout\(|waitForTimeout\(")
# `setTimeout(r, 0)` drena promessas pendentes; é idioma, não espera — validado em projeto real
_ATRASO_ZERO = re.compile(r"(setTimeout|waitForTimeout)\([^;\n]*?,\s*0\s*\)")
_RELOGIO = re.compile(r"datetime\.now\(|date\.today\(|time\.time\(|new Date\(\)|Date\.now\(\)|"
                      r"new DateTime\(|Carbon::now\(")
_CONGELA = re.compile(r"freezegun|freeze_time|time_machine|setSystemTime|Carbon::setTestNow|"
                      r"useFakeTimers")
_ALEATORIO = re.compile(r"\brandom\.\w|Math\.random\(|mt_rand\(|(?<![\w.])rand\(|\bfaker\b|\bFaker\b")
_SEMENTE = re.compile(r"\.seed\(|seed\s*=|Faker::seed|faker\.seed")
_REDE = re.compile(r"requests\.(get|post|put|delete)\(|httpx\.|urlopen\(|(?<![\w.])fetch\(|"
                   r"axios\.\w+\(|curl_exec\(|file_get_contents\(\s*['\"]http")
# rede mockada no arquivo não é rede de verdade — o falso positivo aqui custaria caro
_MOCK = re.compile(r"vi\.mock\(|jest\.mock\(|jest\.spyOn\(|nock\(|\bmsw\b|requests_mock|"
                   r"responses\.|Http::fake\(|mock_open\(|monkeypatch\.setattr\(|patch\(")


def _mascarar(texto: str, literais: bool = True) -> str:
    """Troca comentário (e, se `literais`, texto entre aspas) por espaço, mantendo as posições.

    A busca por rede precisa das aspas preservadas — a URL mora dentro delas.
    """
    saida = list(texto)
    tamanho = len(texto)
    posicao = 0
    while posicao < tamanho:
        letra = texto[posicao]
        if literais and letra in "'\"`":
            fim = posicao + 1
            while fim < tamanho and texto[fim] != letra:
                fim += 2 if texto[fim] == "\\" else 1
            for indice in range(posicao, min(fim + 1, tamanho)):
                if saida[indice] != "\n":
                    saida[indice] = " "
            posicao = fim + 1
            continue
        if letra == "#" or texto.startswith("//", posicao):
            fim = texto.find("\n", posicao)
            fim = tamanho if fim == -1 else fim
            for indice in range(posicao, fim):
                saida[indice] = " "
            posicao = fim
            continue
        if texto.startswith("/*", posicao):
            fim = texto.find("*/", posicao)
            fim = tamanho if fim == -1 else fim + 2
            for indice in range(posicao, fim):
                if saida[indice] != "\n":
                    saida[indice] = " "
            posicao = fim
            continue
        posicao += 1
    return "".join(saida)


def blocos(texto: str):
    """Fatia em (nome, linha da declaração, linha inicial do bloco, trecho até o próximo teste).

    O trecho começa nos decoradores/atributos imediatamente acima da declaração — é onde vivem
    `@pytest.mark.skip` e `#[Test]`. Sem declaração reconhecida, cai nas anotações (Java, C#, Rust).
    """
    linhas = texto.splitlines()
    marcas = []
    for achado in _DECLARACAO.finditer(texto):
        nome = next(valor for valor in achado.groupdict().values() if valor)
        linha = texto.count("\n", 0, achado.start()) + 1
        inicio = linha
        while inicio > 1 and _DECORADOR.match(linhas[inicio - 2]):
            inicio -= 1
        marcas.append((nome, linha, inicio))
    if not marcas:
        for posicao, achado in enumerate(_ANOTACAO.finditer(texto), start=1):
            linha = texto.count("\n", 0, achado.start()) + 1
            marcas.append((f"teste {posicao}", linha, linha))
    saida = []
    for posicao, (nome, linha, inicio) in enumerate(marcas):
        fim = marcas[posicao + 1][2] - 1 if posicao + 1 < len(marcas) else len(linhas)
        saida.append((nome, linha, inicio, "\n".join(linhas[inicio - 1:fim])))
    return saida


def _sinal(regra, caminho, linha, evidencia, teste):
    return {"regra": regra, "caminho": str(caminho), "linha": linha,
            "evidencia": evidencia.strip()[:120], "teste": teste}


def _linha_de(trecho_inicio, trecho, achado) -> int:
    return trecho_inicio + trecho.count("\n", 0, achado.start())


def varrer(caminho, texto: str, suite: str) -> list:
    """Devolve os sinais encontrados no arquivo, em ordem de linha."""
    achados = []
    mascarado = _mascarar(texto)
    linhas_mascaradas = mascarado.splitlines()
    linhas_com_texto = _mascarar(texto, literais=False).splitlines()
    congela_no_arquivo = bool(_CONGELA.search(mascarado))
    mock_no_arquivo = bool(_MOCK.search(mascarado))
    vistos = {}
    for nome, linha, inicio, trecho in blocos(texto):
        fatia = slice(inicio - 1, inicio - 1 + trecho.count("\n") + 1)
        limpo = "\n".join(linhas_mascaradas[fatia])
        com_texto = "\n".join(linhas_com_texto[fatia])
        if nome in vistos:
            achados.append(_sinal("nome_duplicado", caminho, linha,
                                  f"também na linha {vistos[nome]}", nome))
        else:
            vistos[nome] = linha
        pular = _PULAR.search(limpo)
        if pular:
            achados.append(_sinal("marcado_para_pular", caminho, _linha_de(inicio, limpo, pular),
                                  pular.group(0), nome))
            continue                      # teste desligado: os outros sinais não importam
        if not _ASSERCAO.search(limpo):
            achados.append(_sinal("sem_assercao_aparente", caminho, linha, trecho.splitlines()[0], nome))
        espera = _ESPERA.search(limpo)
        if espera and _ATRASO_ZERO.search(limpo[espera.start():]):
            espera = None
        if espera:
            achados.append(_sinal("espera_fixa", caminho, _linha_de(inicio, limpo, espera),
                                  espera.group(0), nome))
        relogio = _RELOGIO.search(limpo)
        if relogio and not congela_no_arquivo:
            achados.append(_sinal("relogio_real", caminho, _linha_de(inicio, limpo, relogio),
                                  relogio.group(0), nome))
        aleatorio = _ALEATORIO.search(limpo)
        if aleatorio and not _SEMENTE.search(mascarado):
            achados.append(_sinal("aleatorio_sem_semente", caminho,
                                  _linha_de(inicio, limpo, aleatorio), aleatorio.group(0), nome))
        rede = _REDE.search(com_texto)
        if rede and suite == "unit" and not mock_no_arquivo:
            achados.append(_sinal("rede_em_unit", caminho, _linha_de(inicio, com_texto, rede),
                                  rede.group(0), nome))
    return sorted(achados, key=lambda a: (a["linha"], a["regra"]))
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_sinais.py -q`
Expected: `10 passed`. Se a linha apontada sair errada, conserte `_linha_de`/`inicio` — a linha
é o que o usuário vai clicar no relatório, então teste que passa com linha errada é teste falso.

---

### Task 4: `lib/inventario.py` e `diagnose.py` estático

**Files:**
- Create: `scripts/lib/inventario.py`, `scripts/lib/stacks/__init__.py`, `scripts/diagnose.py`
- Test: `tests/test_inventario.py`, `tests/test_diagnose_estatico.py`

- [x] **Step 1: Escrever os testes do inventário**

```python
# tests/test_inventario.py
from lib import inventario
from projeto import projeto_phpunit, projeto_pytest, projeto_vitest


def test_conta_arquivos_e_testes_do_projeto_python(repo):
    projeto_pytest(repo)

    dados = inventario.varrer(repo.path)

    assert dados["arquivos"] == 2
    assert dados["testes"] == 5
    assert dados["por_suite"] == {"unit": 5}


def test_classifica_a_suite_pelo_caminho(repo):
    repo.escrever({
        "tests/unit/test_a.py": "def test_a():\n    assert 1\n",
        "tests/Integration/test_b.py": "def test_b():\n    assert 1\n",
        "e2e/compra.spec.ts": "it('compra', () => { expect(1).toBe(1); });\n",
        "tests/test_solto.py": "def test_c():\n    assert 1\n",
    })
    repo.commit("chore: suites")

    dados = inventario.varrer(repo.path)

    assert dados["por_suite"] == {"unit": 1, "integracao": 1, "e2e": 1, "desconhecida": 1}


def test_ignora_dependencias_e_artefatos(repo):
    projeto_vitest(repo)
    repo.escrever({
        "node_modules/lib/x.test.ts": "it('x', () => {});\n",
        "coverage/relatorio.test.ts": "it('y', () => {});\n",
    })

    dados = inventario.varrer(repo.path)

    assert [a["caminho"] for a in dados["lista"]] == ["tests/unit/carrinho.test.ts"]


def test_php_conta_metodos_de_teste(repo):
    projeto_phpunit(repo)

    dados = inventario.varrer(repo.path)

    assert dados["testes"] == 3
    assert dados["por_suite"] == {"unit": 3}


def test_escopo_limita_a_varredura_a_um_pacote(repo):
    repo.escrever({
        "packages/api/tests/unit/test_a.py": "def test_a():\n    assert 1\n",
        "packages/web/tests/unit/b.test.ts": "it('b', () => { expect(1).toBe(1); });\n",
    })
    repo.commit("chore: monorepo")

    dados = inventario.varrer(repo.path / "packages/api")

    assert dados["arquivos"] == 1
    assert dados["lista"][0]["caminho"] == "tests/unit/test_a.py"


def test_projeto_go_nao_some_do_inventario(repo):
    repo.escrever({"go.mod": "module exemplo\n",
                   "interno/soma_test.go": "func TestSoma(t *testing.T) {\n    t.Error(\"x\")\n}\n"})
    repo.commit("chore: go")

    dados = inventario.varrer(repo.path)

    assert dados["arquivos"] == 1 and dados["testes"] == 1
```

- [x] **Step 2: Escrever os testes do `diagnose.py` estático**

```python
# tests/test_diagnose_estatico.py
import json

import diagnose
from lib import pastas
from projeto import projeto_phpunit, projeto_pytest, projeto_vitest
from runners import chamadas, instalar


def rodar(repo, *args):
    return diagnose.main(["--repo", str(repo.path), *args])


def test_grava_fatos_com_repositorio_branch_e_head(repo, capsys):
    projeto_pytest(repo)

    assert rodar(repo) == 0
    fatos = json.loads(pastas.fatos(repo.path).read_text(encoding="utf-8"))

    assert fatos["versao"] == 1
    assert fatos["repo"]["branch"] == "master"
    assert len(fatos["repo"]["head"]) == 40
    assert fatos["execucao"]["rodou"] is False
    assert fatos["cobertura"]["disponivel"] is False


def test_detecta_a_stack_e_o_runner(repo):
    projeto_vitest(repo)
    rodar(repo)
    fatos = json.loads(pastas.fatos(repo.path).read_text(encoding="utf-8"))

    assert [(s["linguagem"], s["runner"], s["nativo"]) for s in fatos["stacks"]] == [("js", "vitest", True)]


def test_sinais_entram_nos_fatos_com_caminho_relativo(repo):
    projeto_pytest(repo)
    rodar(repo)
    fatos = json.loads(pastas.fatos(repo.path).read_text(encoding="utf-8"))

    regras = {s["regra"] for s in fatos["sinais"]}
    assert "marcado_para_pular" in regras
    assert all(not s["caminho"].startswith("/") for s in fatos["sinais"])
    assert "tests/unit/test_problemas.py" in fatos["suspeitos"]


def test_sem_executar_nenhum_runner_e_chamado(repo, tmp_path, monkeypatch):
    """Restrição verificável 2: nada executa sem aprovação."""
    projeto_pytest(repo)
    registros = [instalar(tmp_path, monkeypatch, nome, {"__padrao__": ("", None, None, 0)})
                 for nome in ("pytest", "vitest", "jest", "phpunit")]

    rodar(repo)

    assert [chamadas(r) for r in registros] == [[], [], [], []]


def test_projeto_sem_teste_nenhum_avisa_e_nao_grava_fatos(repo, capsys):
    codigo = rodar(repo)

    assert codigo == 2
    assert "nenhum arquivo de teste" in capsys.readouterr().err.lower()
    assert not pastas.fatos(repo.path).exists()


def test_repo_inexistente_para_com_mensagem(tmp_path, capsys):
    codigo = diagnose.main(["--repo", str(tmp_path / "nao-existe")])

    assert codigo == 2
    assert "não existe" in capsys.readouterr().err


def test_residuo_de_backup_e_restaurado_antes_de_qualquer_coisa(repo, capsys):
    projeto_pytest(repo)
    from lib import backup
    backup.guardar(repo.path, "src/calculadora.py")
    (repo.path / "src/calculadora.py").write_text("QUEBRADO\n", encoding="utf-8")

    rodar(repo)

    assert (repo.path / "src/calculadora.py").read_text(encoding="utf-8").startswith("def somar")
    assert "restaurado" in capsys.readouterr().out


def test_escopo_fora_da_raiz_para_com_mensagem(repo, capsys):
    codigo = diagnose.main(["--repo", str(repo.path), "--escopo", "../.."])

    assert codigo == 2
    assert "dentro" in capsys.readouterr().err
```

- [x] **Step 3: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_inventario.py tests/test_diagnose_estatico.py -q`
Expected: `ModuleNotFoundError: No module named 'diagnose'` e `ImportError` de `lib.inventario` — 12 falhas.

- [x] **Step 4: `scripts/lib/inventario.py`**

```python
"""Varre o escopo: quais arquivos são de teste, quantos testes cada um tem, e de que suíte é."""
import os
import re
from pathlib import Path

from lib import sinais

IGNORAR = {".git", "node_modules", "vendor", "dist", "build", "coverage", "__pycache__",
           ".venv", "venv", ".tox", ".next", ".pytest_cache", ".phpunit.cache"}
EXTENSOES = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".php", ".go", ".rb", ".java", ".cs", ".rs"}
_NOME_DE_TESTE = re.compile(r"(^test_.*|.*_test|.*\.test|.*\.spec|.*Test|.*Spec|.*_spec)$")

_SUITE = (
    ("e2e", ("e2e", "end-to-end", "acceptance", "cypress", "playwright")),
    ("integracao", ("integration", "integracao", "feature", "functional")),
    ("unit", ("unit", "unitario", "unitarios")),
)


def eh_arquivo_de_teste(caminho: Path) -> bool:
    if caminho.suffix not in EXTENSOES:
        return False
    return bool(_NOME_DE_TESTE.match(caminho.stem))


def suite_de(relativo) -> str:
    partes = [p.lower() for p in Path(relativo).parts]
    for nome, marcas in _SUITE:
        if any(parte in marcas for parte in partes):
            return nome
    return "desconhecida"


def varrer(raiz) -> dict:
    """Inventário do escopo, com a lista de arquivos e a contagem de testes por suíte."""
    raiz = Path(raiz)
    lista, por_suite, total = [], {}, 0
    for pasta, subpastas, arquivos in os.walk(raiz):
        # poda antes de descer: node_modules e vendor são grandes demais para varrer e descartar
        subpastas[:] = sorted(s for s in subpastas if s not in IGNORAR)
        for nome in sorted(arquivos):
            caminho = Path(pasta) / nome
            if not eh_arquivo_de_teste(caminho):
                continue
            relativo = caminho.relative_to(raiz)
            try:
                texto = caminho.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            quantos = len(sinais.blocos(texto))
            if quantos == 0:
                continue
            suite = suite_de(relativo)
            lista.append({"caminho": str(relativo), "testes": quantos, "suite": suite})
            por_suite[suite] = por_suite.get(suite, 0) + quantos
            total += quantos
    lista.sort(key=lambda a: a["caminho"])
    return {"arquivos": len(lista), "testes": total, "por_suite": por_suite, "lista": lista}
```

- [x] **Step 5: `scripts/lib/stacks/__init__.py` — só a detecção por enquanto**

```python
"""Escolhe o módulo da stack. Nesta task só detecta; rodar e normalizar entram no lote 2."""
from pathlib import Path

# (linguagem, runner, arquivos que provam a presença)
CANDIDATAS = [
    ("py", "pytest", ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")),
    ("js", "vitest", ("vitest.config.ts", "vitest.config.js", "vitest.config.mjs")),
    ("js", "jest", ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.json")),
    ("php", "phpunit", ("phpunit.xml", "phpunit.xml.dist", "phpunit.dist.xml")),
]


def _no_manifesto(raiz: Path, agulha: str) -> bool:
    for manifesto in ("package.json", "composer.json", "pyproject.toml"):
        arquivo = raiz / manifesto
        if arquivo.exists() and agulha in arquivo.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


# Extensão de teste → runner, quando NÃO há config nem manifesto. Só onde não há ambiguidade:
# entre vitest e jest não dá para adivinhar, e chutar errado faria a skill rodar o comando errado.
PALPITE_POR_EXTENSAO = {".py": ("py", "pytest"), ".php": ("php", "phpunit")}


def detectar(raiz, inventario=None) -> list:
    """Stacks presentes, na ordem em que aparecem em CANDIDATAS. `nativo` = temos módulo próprio.

    Config e manifesto vêm primeiro. Sem eles, o inventário decide: um projeto com `tests/test_x.py`
    rodado por `python -m pytest` não tem arquivo de config nenhum, e ficava de fora.
    """
    raiz = Path(raiz)
    achadas, vistos = [], set()
    for linguagem, runner, configs in CANDIDATAS:
        config = next((c for c in configs if (raiz / c).exists()), None)
        if config is None and not _no_manifesto(raiz, runner):
            continue
        if runner in vistos:
            continue
        vistos.add(runner)
        achadas.append({"linguagem": linguagem, "runner": runner, "nativo": True, "config": config})

    for arquivo in (inventario or {}).get("lista", []):
        palpite = PALPITE_POR_EXTENSAO.get(Path(arquivo["caminho"]).suffix)
        if palpite and palpite[1] not in vistos:
            vistos.add(palpite[1])
            achadas.append({"linguagem": palpite[0], "runner": palpite[1], "nativo": True,
                            "config": None})
    return achadas
```

- [x] **Step 6: `scripts/diagnose.py` (modo estático)**

```python
#!/usr/bin/env python3
"""Apura os fatos da suíte de testes do projeto e grava `fatos.json`.

Sem `--executar`, NENHUM processo de runner é criado: só inventário e detectores textuais.
"""
import argparse
import json
import sys
from pathlib import Path

from lib import backup, gitinfo, inventario, pastas, sinais, stacks
from lib import execucao
from lib.stacks import base as stacks_base

EXIT_OK, EXIT_PARADA = 0, 2
VERSAO_DOS_FATOS = 1


def _repo_info(raiz) -> dict:
    if not gitinfo.dentro_de_repo(raiz):
        return {"toplevel": str(Path(raiz).resolve()), "branch": None, "head": None}
    return {"toplevel": str(gitinfo.toplevel(raiz)),
            "branch": gitinfo.branch(raiz), "head": gitinfo.head(raiz)}


def apurar(raiz, escopo) -> dict:
    """Fatos estáticos: inventário, stacks e sinais. Nada é executado aqui."""
    dados = inventario.varrer(escopo)
    achados = []
    for arquivo in dados["lista"]:
        caminho = Path(escopo) / arquivo["caminho"]
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        achados.extend(sinais.varrer(arquivo["caminho"], texto, arquivo["suite"]))
    return {
        "versao": VERSAO_DOS_FATOS,
        "repo": _repo_info(raiz),
        "escopo": {"tipo": "repo" if Path(escopo) == Path(raiz) else "pacote",
                   "raiz": str(Path(escopo).relative_to(Path(raiz).resolve()))
                           if Path(escopo) != Path(raiz) else "."},
        "stacks": stacks.detectar(escopo, dados),
        "ambiente": {"banco": execucao.banco_a_vista(Path(escopo))},
        "inventario": {k: dados[k] for k in ("arquivos", "testes", "por_suite", "lista")},
        "execucao": {"rodou": False, "comando": None, "verde": None, "timeout": False,
                     "passou": 0, "falhou": 0, "pulado": 0, "duracao_faixa": None, "lentos": []},
        "cobertura": {"disponivel": False, "ferramenta": None, "por_arquivo": []},
        "sinais": achados,
        "suspeitos": sorted({a["caminho"] for a in achados}),
    }


def executar(fatos, raiz, escopo, cobertura: bool, timeout: int) -> None:
    """Preenche fatos['execucao'], fatos['cobertura'] e acrescenta os sinais de execução."""
    nativas = [s for s in fatos["stacks"] if s["nativo"]]
    if not nativas:
        print("nenhuma stack com módulo nativo: seguindo pelo caminho heurístico, sem executar")
        return
    escolhida = nativas[0]
    ignoradas = [s["runner"] for s in nativas[1:]]
    if ignoradas:
        print("stacks nativas não executadas nesta rodada: " + ", ".join(ignoradas))
    try:
        stack = stacks.montar(escolhida["runner"])
    except KeyError:
        print(f"runner {escolhida['runner']} sem módulo nativo: caminho heurístico")
        return

    pasta_saida = pastas.saida(raiz)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    limite = stacks_base.LIMITE_DE_LENTO
    # o coverage grava `.coverage` no diretório atual se ninguém disser o contrário
    extra = {"COVERAGE_FILE": str(pasta_saida / ".coverage")}
    fatos["execucao"]["ambiente"] = {chave: execucao.ambiente_limpo(extra)[chave]
                                     for chave in ("CI", "NO_COLOR", "COVERAGE_FILE")}

    comando = stack.comando_descoberta(escopo)
    try:
        codigo, texto = execucao.rodar(comando, escopo, timeout, extra)
    except execucao.Estourou:
        fatos["execucao"].update({"rodou": True, "timeout": True,
                                  "comando": " ".join(str(p) for p in comando), "verde": None})
        fatos["sinais"].append({"regra": "execucao_estourou", "caminho": ".", "linha": 1,
                                "evidencia": f"descoberta passou de {timeout}s", "teste": ""})
        return
    if codigo == 127:
        fatos["sinais"].append({"regra": "runner_ausente", "caminho": ".", "linha": 1,
                                "evidencia": f"{stack.runner} não está instalado neste projeto",
                                "teste": ""})
        print(f"{stack.runner} não está instalado: seguindo sem executar")
        return
    descobertos = stack.ler_descoberta(texto)
    arquivos_descobertos = stack.arquivos(descobertos, escopo) if descobertos else None
    for arquivo in fatos["inventario"]["lista"]:
        if arquivos_descobertos is not None and arquivo["caminho"] not in arquivos_descobertos:
            fatos["sinais"].append({"regra": "nao_descoberto", "caminho": arquivo["caminho"],
                                    "linha": 1, "evidencia": f"{stack.runner} não coletou este arquivo",
                                    "teste": ""})

    comando = stack.comando_suite(escopo, pasta_saida, cobertura)
    fatos["execucao"]["comando"] = " ".join(str(p) for p in comando)
    try:
        codigo, texto = execucao.rodar(comando, escopo, timeout, extra)
    except execucao.Estourou:
        fatos["execucao"].update({"rodou": True, "timeout": True, "verde": None})
        fatos["sinais"].append({"regra": "execucao_estourou", "caminho": ".", "linha": 1,
                                "evidencia": f"a suíte passou de {timeout}s", "teste": ""})
        return

    # cobertura é medição independente: não pode se perder se o junit vier ilegível
    if cobertura:
        linhas = stack.ler_cobertura(pasta_saida, escopo)
        fatos["cobertura"] = {"disponivel": bool(linhas),
                              "ferramenta": stack.runner if linhas else None,
                              "por_arquivo": linhas}

    suite_mais_comum = max(fatos["inventario"]["por_suite"], key=fatos["inventario"]["por_suite"].get,
                           default="desconhecida")
    resultado = stack.ler_resultado(texto, pasta_saida, limite.get(suite_mais_comum, 1.0))
    if resultado is None:
        fatos["execucao"].update({"rodou": True, "verde": None})
        fatos["sinais"].append({"regra": "saida_ilegivel", "caminho": ".", "linha": 1,
                                "evidencia": f"não consegui ler a saída de {stack.runner}", "teste": ""})
        return
    # junit sem <failure> não prova nada se o runner saiu com erro: bootstrap pode ter quebrado antes
    resultado["verde"] = resultado["verde"] and codigo == 0
    fatos["execucao"].update({"rodou": True, "timeout": False, "codigo": codigo, **resultado})
    for lento in resultado["lentos"]:
        fatos["sinais"].append({"regra": "lento_para_o_tipo", "caminho": ".", "linha": 1,
                                "evidencia": f"{lento['teste']} levou {lento['faixa']}", "teste": lento["teste"]})



def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Apura os fatos da suíte de testes.")
    ap.add_argument("--repo", default=".", help="raiz do projeto (padrão: diretório atual)")
    ap.add_argument("--escopo", default=None, help="subpasta a diagnosticar (monorepo)")
    ap.add_argument("--executar", action="store_true", help="roda descoberta e suíte (opt-in)")
    ap.add_argument("--cobertura", action="store_true", help="pede cobertura na execução")
    ap.add_argument("--banco-ok", action="store_true",
                    help="confirma que pode executar mesmo com banco configurado")
    ap.add_argument("--timeout", type=int, default=300, help="segundos por comando (padrão: 300)")
    args = ap.parse_args(argv)

    raiz = Path(args.repo)
    if not raiz.is_dir():
        print(f"--repo {raiz} não existe.", file=sys.stderr)
        return EXIT_PARADA
    raiz = raiz.resolve()
    escopo = (raiz / args.escopo).resolve() if args.escopo else raiz
    if not escopo.is_dir():
        print(f"--escopo {escopo} não existe.", file=sys.stderr)
        return EXIT_PARADA
    if not escopo.is_relative_to(raiz):
        print(f"--escopo precisa estar dentro de --repo ({raiz}).", file=sys.stderr)
        return EXIT_PARADA

    restaurados = backup.restaurar_tudo(raiz)
    sobrescritos = restaurados["sobrescrito"]
    if sobrescritos or restaurados["intacto"]:
        print("resíduo de execução anterior restaurado: "
              + ", ".join(sobrescritos + restaurados["intacto"]))
    if sobrescritos:
        print("atenção: estes arquivos tinham alteração posterior ao backup e foram sobrescritos: "
              + ", ".join(sobrescritos))

    fatos = apurar(raiz, escopo)
    if args.executar:
        marcas = execucao.banco_a_vista(escopo)
        if marcas and not args.banco_ok:
            print("Banco configurado no ambiente de teste: " + ", ".join(marcas) + ".\n"
                  "A coleta já importa conftest/bootstrap e pode conectar ou truncar banco. "
                  "Confirme com --banco-ok se este ambiente for descartável.", file=sys.stderr)
            return EXIT_PARADA
        fatos["execucao"]["timeout"] = False
        executar(fatos, raiz, escopo, args.cobertura, args.timeout)
    if fatos["inventario"]["arquivos"] == 0:
        print("Nenhum arquivo de teste encontrado no escopo — não há o que diagnosticar. "
              "Use o modo gerar.", file=sys.stderr)
        return EXIT_PARADA

    pastas.criar(raiz)
    destino = pastas.fatos(raiz)
    destino.write_text(json.dumps(fatos, ensure_ascii=False, indent=1), encoding="utf-8")

    inv = fatos["inventario"]
    print(f"fatos.json: {destino}")
    print(f"escopo: {fatos['escopo']['raiz']} · {inv['arquivos']} arquivo(s) · {inv['testes']} teste(s) · "
          + " · ".join(f"{suite} {qtd}" for suite, qtd in sorted(inv["por_suite"].items())))
    print("stacks: " + (", ".join(f"{s['runner']}" for s in fatos["stacks"]) or "nenhuma reconhecida"))
    print(f"sinais: {len(fatos['sinais'])} em {len(fatos['suspeitos'])} arquivo(s)")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 7: Rodar**

Run: `.venv/bin/python -m pytest -q`
Expected: `45 passed` (5 ajudantes + 11 git/pastas + 7 backup + 10 sinais + 5 inventário + 7 diagnose estático).

- [x] **Step 8: Provar na prática, fora do pytest**

Run:
```bash
cd ~/.claude/skills/sw-auto-test && .venv/bin/python scripts/diagnose.py --repo .
```
Expected: a própria skill é diagnosticada; imprime os arquivos de teste dela e os sinais encontrados.

- [x] **Step 9: Checkpoint do lote 1** — pausa de aprovação.

---

## Lote 2 — execução opt-in

### Task 5: `lib/stacks/base.py` — contrato, leitores de saída e faixas

**Files:**
- Create: `scripts/lib/stacks/base.py`
- Test: `tests/test_stacks_base.py`

`junit.xml` é lido por pytest **e** phpunit; cobertura Cobertura/clover tem o mesmo formato de
métrica. Tudo que é comum mora aqui, e cada stack só diz **qual comando** rodar.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_stacks_base.py
from lib.stacks import base

JUNIT = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="pytest" tests="4" failures="1" skipped="1" time="12.5">
    <testcase classname="tests.unit.test_a" name="test_rapido" time="0.01"/>
    <testcase classname="tests.unit.test_a" name="test_lento" time="7.2"/>
    <testcase classname="tests.unit.test_b" name="test_quebrado" time="0.4">
      <failure message="esperava 4">assert 3 == 4</failure>
    </testcase>
    <testcase classname="tests.unit.test_b" name="test_pulado" time="0">
      <skipped message="instavel"/>
    </testcase>
  </testsuite>
</testsuites>
"""

COBERTURA = """<?xml version="1.0"?>
<coverage>
  <packages><package><classes>
    <class filename="src/calculadora.py" line-rate="0.8" branch-rate="0.5"/>
    <class filename="src/pagamento.py" line-rate="0.1" branch-rate="0.0"/>
  </classes></package></packages>
</coverage>
"""

CLOVER = """<?xml version="1.0"?>
<coverage><project>
  <file name="/app/src/Carrinho.php">
    <metrics statements="10" coveredstatements="9" conditionals="4" coveredconditionals="1"/>
  </file>
</project></coverage>
"""


def test_le_junit_com_contagens_e_duracoes(tmp_path):
    arquivo = tmp_path / "junit.xml"
    arquivo.write_text(JUNIT, encoding="utf-8")

    resultado = base.ler_junit(arquivo)

    assert (resultado["passou"], resultado["falhou"], resultado["pulado"]) == (2, 1, 1)
    assert resultado["verde"] is False
    assert resultado["duracao_faixa"] == "10-60s"
    assert resultado["lentos"] == [{"teste": "tests.unit.test_a::test_lento", "faixa": "1-10s"}]


def test_junit_sem_falha_e_verde(tmp_path):
    arquivo = tmp_path / "junit.xml"
    arquivo.write_text(JUNIT.replace('<failure message="esperava 4">assert 3 == 4</failure>', "")
                            .replace('failures="1"', 'failures="0"'), encoding="utf-8")

    assert base.ler_junit(arquivo)["verde"] is True


def test_le_cobertura_formato_cobertura(tmp_path):
    arquivo = tmp_path / "cobertura.xml"
    arquivo.write_text(COBERTURA, encoding="utf-8")

    linhas = base.ler_cobertura_xml(arquivo)

    assert linhas == [{"caminho": "src/calculadora.py", "linhas_pct": 80, "ramos_pct": 50},
                      {"caminho": "src/pagamento.py", "linhas_pct": 10, "ramos_pct": 0}]


def test_le_cobertura_formato_clover_com_caminho_relativo(tmp_path):
    arquivo = tmp_path / "clover.xml"
    arquivo.write_text(CLOVER, encoding="utf-8")

    linhas = base.ler_clover(arquivo, raiz="/app")

    assert linhas == [{"caminho": "src/Carrinho.php", "linhas_pct": 90, "ramos_pct": 25}]


def test_arquivo_ausente_ou_corrompido_nao_explode(tmp_path):
    quebrado = tmp_path / "junit.xml"
    quebrado.write_text("<testsuites", encoding="utf-8")

    assert base.ler_junit(tmp_path / "nao-existe.xml") is None
    assert base.ler_junit(quebrado) is None
    assert base.ler_cobertura_xml(quebrado) == []


def test_faixas_de_duracao_sao_as_do_spec():
    assert [base.faixa(s) for s in (0.4, 5, 30, 200, 900)] == \
        ["<1s", "1-10s", "10-60s", "1-5min", ">5min"]
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_stacks_base.py -q`
Expected: `ImportError: cannot import name 'base' from 'lib.stacks'` — 6 falhas.

- [x] **Step 3: `scripts/lib/stacks/base.py`**

```python
"""O que é comum a todas as stacks: leitura de junit/cobertura e faixas de duração.

Faixa em vez de segundo exato é o que deixa o relatório determinístico (restrição 4).
"""
import xml.etree.ElementTree as ET
from pathlib import Path

FAIXAS = ((1, "<1s"), (10, "1-10s"), (60, "10-60s"), (300, "1-5min"), (float("inf"), ">5min"))
LIMITE_DE_LENTO = {"unit": 1.0, "integracao": 10.0, "e2e": 60.0, "desconhecida": 10.0}


def faixa(segundos: float) -> str:
    for teto, nome in FAIXAS:
        if segundos < teto:
            return nome
    return FAIXAS[-1][1]


def _arvore(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return None
    try:
        return ET.parse(caminho).getroot()
    except ET.ParseError:
        return None


def ler_junit(caminho, limite_lento: float = 1.0):
    """Contagens, faixa de duração total e os testes acima do limite. `None` se não deu para ler."""
    raiz = _arvore(caminho)
    if raiz is None:
        return None
    casos = raiz.iter("testcase")
    passou = falhou = pulado = 0
    soma_dos_casos = 0.0
    lentos = []
    for caso in casos:
        duracao = float(caso.get("time") or 0)
        soma_dos_casos += duracao
        nome = f"{caso.get('classname', '')}::{caso.get('name', '')}".strip(":")
        if caso.find("failure") is not None or caso.find("error") is not None:
            falhou += 1
        elif caso.find("skipped") is not None:
            pulado += 1
        else:
            passou += 1
            if duracao >= limite_lento:
                lentos.append({"teste": nome, "faixa": faixa(duracao)})
    # o tempo da suíte inclui setup/teardown; a soma dos casos ignora isso e mente para menos.
    # Só os filhos diretos: `iter` desceria em suíte aninhada e contaria o mesmo tempo duas vezes.
    filhos = raiz.findall("testsuite") or ([raiz] if raiz.tag == "testsuite" else [])
    tempos = [float(s.get("time")) for s in filhos if s.get("time")]
    total = sum(tempos) if tempos else soma_dos_casos
    return {"passou": passou, "falhou": falhou, "pulado": pulado, "verde": falhou == 0,
            "duracao_faixa": faixa(total), "lentos": lentos}


def relativizar(caminho, raiz) -> str:
    """Caminho absoluto dentro da raiz vira relativo — caminho de máquina nos fatos quebraria
    o determinismo do relatório e ainda vazaria o diretório de quem rodou."""
    alvo = Path(caminho)
    if raiz and alvo.is_absolute():
        raiz = Path(raiz).resolve()
        if alvo.is_relative_to(raiz):
            return str(alvo.relative_to(raiz))
    return str(caminho)


def _pct(valor) -> int:
    return int(round(float(valor) * 100))


def ler_cobertura_xml(caminho, raiz=None) -> list:
    """Formato Cobertura (pytest-cov, coverage.py, istanbul --reporter=cobertura)."""
    arvore = _arvore(caminho)   # `raiz` aqui é o parâmetro do projeto, não a raiz do XML
    if arvore is None:
        return []
    saida = []
    for classe in arvore.iter("class"):
        nome = classe.get("filename")
        if not nome:
            continue
        saida.append({"caminho": relativizar(nome, raiz),
                      "linhas_pct": _pct(classe.get("line-rate") or 0),
                      "ramos_pct": _pct(classe.get("branch-rate") or 0)})
    return saida


def ler_clover(caminho, raiz=None) -> list:
    """Formato clover (phpunit). `raiz` recorta o caminho absoluto do container/CI."""
    arvore = _arvore(caminho)
    if arvore is None:
        return []
    saida = []
    for arquivo in arvore.iter("file"):
        metrica = arquivo.find("metrics")
        nome = arquivo.get("name")
        if metrica is None or not nome:
            continue
        nome = relativizar(nome, raiz)
        declaracoes = float(metrica.get("statements") or 0)
        condicionais = float(metrica.get("conditionals") or 0)
        saida.append({
            "caminho": nome,
            "linhas_pct": int(round(float(metrica.get("coveredstatements") or 0) / declaracoes * 100))
                          if declaracoes else 0,
            "ramos_pct": int(round(float(metrica.get("coveredconditionals") or 0) / condicionais * 100))
                         if condicionais else 0,
        })
    return saida


class Stack:
    """Contrato das stacks nativas. Cada uma só diz QUAL comando rodar e como ler a saída."""

    linguagem = runner = ""

    def comando_descoberta(self, escopo) -> list:
        raise NotImplementedError

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        raise NotImplementedError

    def ler_descoberta(self, texto: str) -> list:
        raise NotImplementedError

    def arquivos(self, ids, escopo):
        """Arquivos que a descoberta listou, relativos ao escopo.

        `None` quando a stack não sabe dizer (phpunit lista classe, não arquivo) — e aí a regra
        de "arquivo não descoberto" não se aplica, em vez de acusar a suíte inteira.
        """
        return None

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        raise NotImplementedError

    def ler_cobertura(self, saida: Path, escopo) -> list:
        return []
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_stacks_base.py -q`
Expected: `6 passed`

---

### Task 6: `lib/stacks/py.py`, `js.py` e `php.py`

**Files:**
- Create: `scripts/lib/stacks/py.py`, `scripts/lib/stacks/js.py`, `scripts/lib/stacks/php.py`
- Modify: `scripts/lib/stacks/__init__.py` (passa a devolver também a instância)
- Test: `tests/test_stacks.py`

- [x] **Step 1: Escrever os testes**

```python
# tests/test_stacks.py
import json
from pathlib import Path

from lib import stacks
from lib.stacks import base

VITEST_JSON = json.dumps({
    "numTotalTests": 3, "numPassedTests": 2, "numFailedTests": 1, "numPendingTests": 0,
    "testResults": [{"name": "/app/tests/unit/carrinho.test.ts", "assertionResults": [
        {"fullName": "soma itens", "status": "passed", "duration": 12},
        {"fullName": "aplica cupom", "status": "passed", "duration": 2300},
        {"fullName": "recusa cupom vencido", "status": "failed", "duration": 8}]}]})


def instancia(runner):
    return stacks.montar(runner)


def test_comandos_do_pytest_gravam_a_saida_na_pasta_de_fatos(tmp_path):
    stack = instancia("pytest")

    descoberta = stack.comando_descoberta(tmp_path / "projeto")
    suite = stack.comando_suite(tmp_path / "projeto", tmp_path / "saida", cobertura=True)

    assert descoberta[:2] == ["pytest", "--collect-only"]
    assert f"--junit-xml={tmp_path / 'saida' / 'junit.xml'}" in suite
    assert f"--cov-report=xml:{tmp_path / 'saida' / 'cobertura.xml'}" in suite
    assert all("--cov-report=html" not in parte for parte in suite), "nada de saída fora da pasta"


def test_pytest_le_a_descoberta_ignorando_rodape(tmp_path):
    stack = instancia("pytest")
    texto = ("tests/unit/test_a.py::test_x\n"
             "tests/unit/test_a.py::test_y\n"
             "\n2 tests collected in 0.01s\n")

    assert stack.ler_descoberta(texto) == ["tests/unit/test_a.py::test_x",
                                           "tests/unit/test_a.py::test_y"]


def test_vitest_le_resultado_do_json_com_lentos(tmp_path):
    stack = instancia("vitest")
    saida = tmp_path / "saida"
    saida.mkdir()
    (saida / "vitest.json").write_text(VITEST_JSON, encoding="utf-8")

    resultado = stack.ler_resultado("", saida, limite_lento=1.0)

    assert (resultado["passou"], resultado["falhou"], resultado["verde"]) == (2, 1, False)
    assert resultado["lentos"] == [{"teste": "aplica cupom", "faixa": "1-10s"}]


def test_jest_usa_flags_proprias_mas_o_mesmo_json(tmp_path):
    stack = instancia("jest")
    suite = stack.comando_suite(tmp_path, tmp_path / "saida", cobertura=True)

    assert "--json" in suite and f"--outputFile={tmp_path / 'saida' / 'jest.json'}" in suite
    assert f"--coverageDirectory={tmp_path / 'saida' / 'cobertura'}" in suite


def test_phpunit_usa_junit_e_clover(tmp_path):
    stack = instancia("phpunit")
    suite = stack.comando_suite(tmp_path, tmp_path / "saida", cobertura=True)

    assert suite[:1] == ["phpunit"]
    assert "--log-junit" in suite and str(tmp_path / "saida" / "junit.xml") in suite
    assert "--coverage-clover" in suite and str(tmp_path / "saida" / "clover.xml") in suite


def test_phpunit_le_lista_de_testes_do_formato_proprio():
    stack = instancia("phpunit")
    texto = ("PHPUnit 11.0.0\n\nAvailable test(s):\n"
             " - CarrinhoTest::test_soma\n - CarrinhoTest::test_cupom\n")

    assert stack.ler_descoberta(texto) == ["CarrinhoTest::test_soma", "CarrinhoTest::test_cupom"]


def test_montar_recusa_runner_desconhecido():
    import pytest

    with pytest.raises(KeyError):
        stacks.montar("mocha")


def test_detectar_devolve_stack_montavel(tmp_path):
    (tmp_path / "phpunit.xml").write_text("<phpunit/>", encoding="utf-8")

    achadas = stacks.detectar(tmp_path)

    assert achadas[0]["runner"] == "phpunit"
    assert isinstance(stacks.montar(achadas[0]["runner"]), base.Stack)


def test_cada_stack_sabe_dizer_o_arquivo_do_id(tmp_path):
    assert instancia("pytest").arquivos(["tests/unit/test_a.py::test_x[com espaço]"], tmp_path) == \
        {"tests/unit/test_a.py"}
    assert instancia("vitest").arquivos(["tests/unit/a.test.ts > carrinho > soma"], tmp_path) == \
        {"tests/unit/a.test.ts"}
    assert instancia("jest").arquivos([str(tmp_path / "tests/unit/a.test.ts")], tmp_path) == \
        {"tests/unit/a.test.ts"}
    assert instancia("phpunit").arquivos(["CarrinhoTest::test_soma"], tmp_path) is None, \
        "phpunit lista classe, não arquivo: a regra de não descoberto não se aplica"


def test_pytest_le_id_parametrizado_com_espaco():
    texto = "tests/unit/test_a.py::test_x[com espaço]\n\n1 test collected in 0.01s\n"

    assert instancia("pytest").ler_descoberta(texto) == ["tests/unit/test_a.py::test_x[com espaço]"]


def test_cobertura_sai_com_caminho_relativo_ao_escopo(tmp_path):
    saida = tmp_path / "saida"
    saida.mkdir()
    (saida / "cobertura.xml").write_text(
        '<?xml version="1.0"?><coverage><packages><package><classes>'
        f'<class filename="{tmp_path}/src/a.py" line-rate="0.5" branch-rate="0.5"/>'
        "</classes></package></packages></coverage>", encoding="utf-8")

    linhas = instancia("pytest").ler_cobertura(saida, tmp_path)

    assert linhas == [{"caminho": "src/a.py", "linhas_pct": 50, "ramos_pct": 50}]
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_stacks.py -q`
Expected: `AttributeError: module 'lib.stacks' has no attribute 'montar'` — 8 falhas.

- [x] **Step 3: `scripts/lib/stacks/py.py`**

```python
"""pytest."""
from pathlib import Path

from lib.stacks.base import Stack, ler_cobertura_xml, ler_junit


class Pytest(Stack):
    linguagem, runner = "py", "pytest"

    def comando_descoberta(self, escopo) -> list:
        return ["pytest", "--collect-only", "-q", "--no-header", "-p", "no:cacheprovider"]

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        comando = ["pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                   f"--junit-xml={Path(saida) / 'junit.xml'}"]
        if cobertura:
            comando += ["--cov", f"--cov-report=xml:{Path(saida) / 'cobertura.xml'}"]
        return comando

    def ler_descoberta(self, texto: str) -> list:
        # id parametrizado tem espaço e colchete: casar por "::" é mais fiel que uma regex estreita
        return [linha.strip() for linha in texto.splitlines()
                if "::" in linha and not linha.lstrip().startswith(("=", "-", "<"))]

    def arquivos(self, ids, escopo):
        return {identificador.split("::")[0] for identificador in ids}

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        return ler_junit(Path(saida) / "junit.xml", limite_lento)

    def ler_cobertura(self, saida: Path, escopo) -> list:
        return ler_cobertura_xml(Path(saida) / "cobertura.xml", raiz=escopo)
```

- [x] **Step 4: `scripts/lib/stacks/js.py`**

```python
"""vitest e jest — runners diferentes, mesmo formato de resultado em JSON."""
import json
from pathlib import Path

from lib.stacks.base import Stack, faixa, relativizar


def _ler_json(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _resultado(dados, limite_lento: float):
    """`testResults[].assertionResults[]` com status e duração em milissegundos."""
    if not isinstance(dados, dict):
        return None
    passou = falhou = pulado = 0
    total_ms = 0.0
    lentos = []
    for arquivo in dados.get("testResults", []):
        for caso in arquivo.get("assertionResults", []):
            duracao = float(caso.get("duration") or 0)
            total_ms += duracao
            estado = caso.get("status")
            if estado == "passed":
                passou += 1
                if duracao / 1000 >= limite_lento:
                    lentos.append({"teste": caso.get("fullName", ""), "faixa": faixa(duracao / 1000)})
            elif estado in ("failed", "broken"):
                falhou += 1
            else:
                pulado += 1
    return {"passou": passou, "falhou": falhou, "pulado": pulado, "verde": falhou == 0,
            "duracao_faixa": faixa(total_ms / 1000), "lentos": lentos}


class Vitest(Stack):
    linguagem, runner = "js", "vitest"

    def comando_descoberta(self, escopo) -> list:
        return ["vitest", "list", "--run"]

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        saida = Path(saida)
        comando = ["vitest", "run", "--reporter=json", f"--outputFile={saida / 'vitest.json'}"]
        if cobertura:
            comando += ["--coverage", "--coverage.reporter=cobertura",
                        f"--coverage.reportsDirectory={saida / 'cobertura'}"]
        return comando

    def ler_descoberta(self, texto: str) -> list:
        return [linha.strip() for linha in texto.splitlines()
                if linha.strip() and not linha.startswith(("✓", "RUN", "DEV"))]

    def arquivos(self, ids, escopo):
        # `vitest list` imprime "arquivo > suite > teste"
        return {identificador.split(" > ")[0].strip() for identificador in ids}

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        return _resultado(_ler_json(Path(saida) / "vitest.json"), limite_lento)

    def ler_cobertura(self, saida: Path, escopo) -> list:
        from lib.stacks.base import ler_cobertura_xml
        return ler_cobertura_xml(Path(saida) / "cobertura" / "cobertura-coverage.xml", raiz=escopo)


class Jest(Stack):
    linguagem, runner = "js", "jest"

    def comando_descoberta(self, escopo) -> list:
        return ["jest", "--listTests"]

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        saida = Path(saida)
        comando = ["jest", "--ci", "--json", f"--outputFile={saida / 'jest.json'}"]
        if cobertura:
            comando += ["--coverage", "--coverageReporters=cobertura",
                        f"--coverageDirectory={saida / 'cobertura'}"]
        return comando

    def ler_descoberta(self, texto: str) -> list:
        return [linha.strip() for linha in texto.splitlines() if linha.strip()]

    def arquivos(self, ids, escopo):
        # `jest --listTests` devolve caminho absoluto
        return {relativizar(identificador, escopo) for identificador in ids}

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        return _resultado(_ler_json(Path(saida) / "jest.json"), limite_lento)

    def ler_cobertura(self, saida: Path, escopo) -> list:
        from lib.stacks.base import ler_cobertura_xml
        return ler_cobertura_xml(Path(saida) / "cobertura" / "cobertura-coverage.xml", raiz=escopo)
```

- [x] **Step 5: `scripts/lib/stacks/php.py`**

```python
"""phpunit."""
from pathlib import Path

from lib.stacks.base import Stack, ler_clover, ler_junit


class PHPUnit(Stack):
    linguagem, runner = "php", "phpunit"

    def _binario(self, escopo) -> str:
        local = Path(escopo) / "vendor" / "bin" / "phpunit"
        return str(local) if local.exists() else "phpunit"

    def comando_descoberta(self, escopo) -> list:
        return [self._binario(escopo), "--list-tests"]

    def comando_suite(self, escopo, saida: Path, cobertura: bool) -> list:
        saida = Path(saida)
        comando = [self._binario(escopo), "--log-junit", str(saida / "junit.xml")]
        if cobertura:
            comando += ["--coverage-clover", str(saida / "clover.xml")]
        return comando

    def ler_descoberta(self, texto: str) -> list:
        return [linha.strip(" -").strip() for linha in texto.splitlines()
                if linha.strip().startswith("-") and "::" in linha]

    def arquivos(self, ids, escopo):
        # phpunit lista "Classe::metodo": não dá para saber o arquivo sem parser — regra não se aplica
        return None

    def ler_resultado(self, texto: str, saida: Path, limite_lento: float):
        return ler_junit(Path(saida) / "junit.xml", limite_lento)

    def ler_cobertura(self, saida: Path, escopo) -> list:
        return ler_clover(Path(saida) / "clover.xml", raiz=Path(escopo).resolve())
```

- [x] **Step 6: `scripts/lib/stacks/__init__.py` — acrescentar `montar`**

```python
# acrescentar ao final do arquivo criado na Task 4
from lib.stacks.js import Jest, Vitest        # noqa: E402
from lib.stacks.php import PHPUnit            # noqa: E402
from lib.stacks.py import Pytest              # noqa: E402

MODULOS = {"pytest": Pytest, "vitest": Vitest, "jest": Jest, "phpunit": PHPUnit}


def montar(runner):
    """Instância da stack. `KeyError` no runner sem módulo nativo — o chamador cai no heurístico."""
    return MODULOS[runner]()
```

- [x] **Step 7: Rodar**

Run: `.venv/bin/python -m pytest tests/test_stacks.py -q`
Expected: `8 passed`

---

### Task 7: `lib/execucao.py` e o `--executar` do `diagnose.py`

**Files:**
- Create: `scripts/lib/execucao.py`
- Modify: `scripts/diagnose.py` (novas flags e a fase de execução)
- Test: `tests/test_diagnose_executar.py`

Regras do spec que esta task implementa: **DSN antes da descoberta**, descoberta **também** é
execução, timeout vira achado, e toda saída do runner cai na pasta de fatos.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_diagnose_executar.py
import json
import os
import stat
from pathlib import Path

import diagnose
from lib import pastas
from projeto import projeto_phpunit, projeto_pytest, projeto_vitest
from runners import chamadas, instalar

JUNIT_OK = """<?xml version="1.0"?>
<testsuites><testsuite name="pytest" tests="2" failures="0" skipped="0" time="3">
  <testcase classname="tests.unit.test_calculadora" name="test_soma_dois_numeros" time="0.01"/>
  <testcase classname="tests.unit.test_problemas" name="test_lento" time="4.5"/>
</testsuite></testsuites>
"""

COBERTURA_OK = """<?xml version="1.0"?>
<coverage><packages><package><classes>
  <class filename="src/calculadora.py" line-rate="0.9" branch-rate="1.0"/>
</classes></package></packages></coverage>
"""

DESCOBERTA = ("tests/unit/test_calculadora.py::test_soma_dois_numeros\n"
              "tests/unit/test_problemas.py::test_lento\n")


def pytest_falso(tmp_path, monkeypatch, descoberta=DESCOBERTA):
    return instalar(tmp_path, monkeypatch, "pytest", {
        "--collect-only": (descoberta, None, None, 0),
        "--junit-xml": ("2 passed\n", "junit.xml", JUNIT_OK, 0),
        "__padrao__": ("", None, None, 0),
    })


def fatos_de(repo):
    return json.loads(pastas.fatos(repo.path).read_text(encoding="utf-8"))


def rodar(repo, *args):
    return diagnose.main(["--repo", str(repo.path), *args])


def test_executar_roda_descoberta_e_suite_e_preenche_os_fatos(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    registro = pytest_falso(tmp_path, monkeypatch)

    assert rodar(repo, "--executar") == 0
    fatos = fatos_de(repo)

    assert [c.split()[1] for c in chamadas(registro)] == ["--collect-only", "-q"]  # descoberta primeiro
    assert fatos["execucao"]["rodou"] is True
    assert (fatos["execucao"]["passou"], fatos["execucao"]["falhou"]) == (2, 0)
    assert fatos["execucao"]["verde"] is True
    assert fatos["execucao"]["duracao_faixa"] == "1-10s"


def test_banco_no_ambiente_barra_antes_de_qualquer_execucao(repo, tmp_path, monkeypatch, capsys):
    projeto_pytest(repo)
    registro = pytest_falso(tmp_path, monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgres://usuario@host/banco")

    codigo = rodar(repo, "--executar")

    assert codigo == 2
    assert chamadas(registro) == [], "nem a descoberta pode rodar: a coleta importa conftest"
    erro = capsys.readouterr().err
    assert "DATABASE_URL" in erro and "--banco-ok" in erro


def test_com_banco_ok_a_execucao_segue(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    registro = pytest_falso(tmp_path, monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgres://usuario@host/banco")

    assert rodar(repo, "--executar", "--banco-ok") == 0
    assert len(chamadas(registro)) == 2


def test_env_de_banco_no_arquivo_do_projeto_tambem_barra(repo, tmp_path, monkeypatch, capsys):
    projeto_pytest(repo)
    repo.escrever({".env.testing": "DB_HOST=127.0.0.1\nDB_DATABASE=loja\n"})
    pytest_falso(tmp_path, monkeypatch)

    assert rodar(repo, "--executar") == 2
    assert ".env.testing" in capsys.readouterr().err


def test_timeout_vira_achado_e_a_skill_continua(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    pasta = tmp_path / "bin"
    pasta.mkdir(exist_ok=True)
    lento = pasta / "pytest"
    lento.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    lento.chmod(lento.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{pasta}{os.pathsep}{os.environ['PATH']}")

    assert rodar(repo, "--executar", "--timeout", "1") == 0
    fatos = fatos_de(repo)

    assert fatos["execucao"]["timeout"] is True
    assert fatos["execucao"]["verde"] is None
    assert any(s["regra"] == "execucao_estourou" for s in fatos["sinais"])


def test_arquivo_que_o_runner_nao_descobre_vira_sinal(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    pytest_falso(tmp_path, monkeypatch,
                 descoberta="tests/unit/test_calculadora.py::test_soma_dois_numeros\n")

    rodar(repo, "--executar")
    fatos = fatos_de(repo)

    orfaos = [s for s in fatos["sinais"] if s["regra"] == "nao_descoberto"]
    assert [s["caminho"] for s in orfaos] == ["tests/unit/test_problemas.py"]


def test_teste_lento_para_o_tipo_vira_sinal(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    pytest_falso(tmp_path, monkeypatch)

    rodar(repo, "--executar")
    fatos = fatos_de(repo)

    lentos = [s for s in fatos["sinais"] if s["regra"] == "lento_para_o_tipo"]
    assert lentos and "test_lento" in lentos[0]["evidencia"]


def test_cobertura_entra_nos_fatos_quando_pedida(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    instalar(tmp_path, monkeypatch, "pytest", {
        "--collect-only": (DESCOBERTA, None, None, 0),
        "--cov-report": ("2 passed\n", "cobertura.xml", COBERTURA_OK, 0),
        "__padrao__": ("", None, None, 0),
    })

    rodar(repo, "--executar", "--cobertura")
    fatos = fatos_de(repo)

    assert fatos["cobertura"]["disponivel"] is True
    assert fatos["cobertura"]["ferramenta"] == "pytest"
    assert fatos["cobertura"]["por_arquivo"] == [{"caminho": "src/calculadora.py",
                                                  "linhas_pct": 90, "ramos_pct": 100}]


def test_stack_sem_modulo_nativo_nao_executa_e_avisa(repo, capsys):
    repo.escrever({"go.mod": "module exemplo\n",
                   "interno/soma_test.go": "func TestSoma(t *testing.T) { t.Error(\"x\") }\n"})
    repo.commit("chore: go")

    assert rodar(repo, "--executar") == 0
    fatos = fatos_de(repo)

    assert fatos["execucao"]["rodou"] is False
    assert "heurístico" in capsys.readouterr().out


VITEST_JSON_OK = json.dumps({
    "testResults": [{"name": "/app/tests/unit/carrinho.test.ts", "assertionResults": [
        {"fullName": "soma itens", "status": "passed", "duration": 5}]}]})


def test_runner_ausente_nao_vira_suite_ilegivel(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))

    assert rodar(repo, "--executar") == 0
    fatos = fatos_de(repo)

    assert fatos["execucao"]["rodou"] is False
    assert any(s["regra"] == "runner_ausente" for s in fatos["sinais"])


def test_codigo_de_saida_do_runner_conta_para_o_verde(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    instalar(tmp_path, monkeypatch, "pytest", {
        "--collect-only": (DESCOBERTA, None, None, 0),
        "--junit-xml": ("bootstrap quebrou\n", "junit.xml", JUNIT_OK, 2),
        "__padrao__": ("", None, None, 0)})

    rodar(repo, "--executar")

    assert fatos_de(repo)["execucao"]["verde"] is False, \
        "junit sem falha, mas o runner saiu com erro: não é verde"


def test_ambiente_da_execucao_fica_registrado_nos_fatos(repo, tmp_path, monkeypatch):
    projeto_pytest(repo)
    pytest_falso(tmp_path, monkeypatch)

    rodar(repo, "--executar", "--cobertura")
    ambiente = fatos_de(repo)["execucao"]["ambiente"]

    assert ambiente["CI"] == "1"
    assert ambiente["COVERAGE_FILE"].endswith("sw-auto-test/saida/.coverage"), \
        "o coverage precisa gravar dentro da pasta de fatos, não no projeto"


def test_vitest_nao_gera_nao_descoberto_em_massa(repo, tmp_path, monkeypatch):
    projeto_vitest(repo)
    instalar(tmp_path, monkeypatch, "vitest", {
        "list": ("tests/unit/carrinho.test.ts > carrinho > soma\n", None, None, 0),
        "--reporter=json": ("", "vitest.json", VITEST_JSON_OK, 0),
        "__padrao__": ("", None, None, 0)})

    rodar(repo, "--executar")

    assert [s for s in fatos_de(repo)["sinais"] if s["regra"] == "nao_descoberto"] == []


def test_phpunit_nao_gera_nao_descoberto(repo, tmp_path, monkeypatch):
    projeto_phpunit(repo)
    instalar(tmp_path, monkeypatch, "phpunit", {
        "--list-tests": (" - CarrinhoTest::test_sem_assercao\n", None, None, 0),
        "junit.xml": ("", "junit.xml", JUNIT_OK, 0),
        "__padrao__": ("", None, None, 0)})

    rodar(repo, "--executar")

    assert [s for s in fatos_de(repo)["sinais"] if s["regra"] == "nao_descoberto"] == []


def test_banco_declarado_no_phpunit_xml_tambem_barra(repo, tmp_path, monkeypatch, capsys):
    projeto_phpunit(repo)
    repo.escrever({"phpunit.xml": "<phpunit><php><env name='DB_DATABASE' value='loja'/></php></phpunit>\n"})
    registro = instalar(tmp_path, monkeypatch, "phpunit", {"__padrao__": ("", None, None, 0)})

    assert rodar(repo, "--executar") == 2
    assert "phpunit.xml" in capsys.readouterr().err
    assert chamadas(registro) == []
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_diagnose_executar.py -q`
Expected: `error: unrecognized arguments: --executar` — 9 falhas.

- [x] **Step 3: `scripts/lib/execucao.py`**

```python
"""Único ponto que executa processo externo (fora do git, que mora em gitinfo).

Concentrar aqui é o que torna verificável a regra "nada executa sem aprovação": o teste
estático olha quem importa `subprocess`.
"""
import os
import subprocess
from pathlib import Path

MARCAS_DE_BANCO = ("DATABASE_URL", "DB_HOST", "DB_DATABASE", "DB_CONNECTION", "MYSQL_", "POSTGRES_",
                   "PGHOST", "MONGO_URL", "MONGODB_URI", "REDIS_URL")
ARQUIVOS_DE_AMBIENTE = (".env", ".env.test", ".env.testing", ".env.local",
                        "phpunit.xml", "phpunit.xml.dist", "phpunit.dist.xml")


class Estourou(Exception):
    """O comando passou do tempo."""


def ambiente_limpo(extra=None) -> dict:
    """Sem paginador e com mensagens estáveis; o resto do ambiente do projeto é preservado.

    `CI=1` muda o comportamento de alguns runners (retry, `forbidOnly`), então o que for usado
    aqui é registrado nos fatos — quem ler o relatório precisa saber em que ambiente rodou.
    """
    return {**os.environ, "PAGER": "cat", "CI": "1", "NO_COLOR": "1",
            "PYTHONDONTWRITEBYTECODE": "1", **(extra or {})}


def rodar(comando, cwd, timeout: int, extra=None):
    """Devolve (código, stdout+stderr). Levanta `Estourou` no timeout."""
    try:
        r = subprocess.run(comando, cwd=str(cwd), env=ambiente_limpo(extra), capture_output=True,
                           text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as erro:
        raise Estourou(" ".join(str(p) for p in comando)) from erro
    except FileNotFoundError as erro:
        return 127, str(erro)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def banco_a_vista(escopo) -> list:
    """Onde há sinal de banco configurado — variável de ambiente ou arquivo do projeto.

    Roda ANTES da descoberta: coletar testes já importa `conftest`/bootstrap, que pode
    conectar ou truncar banco.
    """
    escopo = Path(escopo)
    achados = [nome for nome in os.environ if nome.startswith(MARCAS_DE_BANCO)]
    for nome in ARQUIVOS_DE_AMBIENTE:
        arquivo = escopo / nome
        if not arquivo.exists():
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        if any(marca in texto for marca in MARCAS_DE_BANCO):
            achados.append(nome)
    return sorted(set(achados))
```

- [x] **Step 4: `scripts/diagnose.py` — flags e fase de execução**

```python
# acrescentar aos imports
from lib import execucao
from lib.stacks import base as stacks_base

# acrescentar ao argparse, dentro de main()
    ap.add_argument("--executar", action="store_true", help="roda descoberta e suíte (opt-in)")
    ap.add_argument("--cobertura", action="store_true", help="pede cobertura na execução")
    ap.add_argument("--banco-ok", action="store_true",
                    help="confirma que pode executar mesmo com banco configurado")
    ap.add_argument("--timeout", type=int, default=300, help="segundos por comando (padrão: 300)")

# nova função, antes de main()
def executar(fatos, escopo, cobertura: bool, timeout: int) -> None:
    """Preenche fatos['execucao'], fatos['cobertura'] e acrescenta os sinais de execução."""
    nativas = [s for s in fatos["stacks"] if s["nativo"]]
    if not nativas:
        print("nenhuma stack com módulo nativo: seguindo pelo caminho heurístico, sem executar")
        return
    escolhida = nativas[0]
    try:
        stack = stacks.montar(escolhida["runner"])
    except KeyError:
        print(f"runner {escolhida['runner']} sem módulo nativo: caminho heurístico")
        return

    pasta_saida = pastas.saida(fatos["_raiz"])
    pasta_saida.mkdir(parents=True, exist_ok=True)
    limite = stacks_base.LIMITE_DE_LENTO

    comando = stack.comando_descoberta(escopo)
    try:
        _, texto = execucao.rodar(comando, escopo, timeout)
    except execucao.Estourou:
        fatos["execucao"].update({"rodou": True, "timeout": True,
                                  "comando": " ".join(str(p) for p in comando), "verde": None})
        fatos["sinais"].append({"regra": "execucao_estourou", "caminho": ".", "linha": 1,
                                "evidencia": f"descoberta passou de {timeout}s", "teste": ""})
        return
    descobertos = stack.ler_descoberta(texto)
    arquivos_descobertos = {d.split("::")[0] for d in descobertos}
    for arquivo in fatos["inventario"]["lista"]:
        if descobertos and arquivo["caminho"] not in arquivos_descobertos:
            fatos["sinais"].append({"regra": "nao_descoberto", "caminho": arquivo["caminho"],
                                    "linha": 1, "evidencia": f"{stack.runner} não coletou este arquivo",
                                    "teste": ""})

    comando = stack.comando_suite(escopo, pasta_saida, cobertura)
    fatos["execucao"]["comando"] = " ".join(str(p) for p in comando)
    try:
        _, texto = execucao.rodar(comando, escopo, timeout)
    except execucao.Estourou:
        fatos["execucao"].update({"rodou": True, "timeout": True, "verde": None})
        fatos["sinais"].append({"regra": "execucao_estourou", "caminho": ".", "linha": 1,
                                "evidencia": f"a suíte passou de {timeout}s", "teste": ""})
        return

    suite_mais_comum = max(fatos["inventario"]["por_suite"], key=fatos["inventario"]["por_suite"].get,
                           default="desconhecida")
    resultado = stack.ler_resultado(texto, pasta_saida, limite.get(suite_mais_comum, 1.0))
    if resultado is None:
        fatos["execucao"].update({"rodou": True, "verde": None})
        fatos["sinais"].append({"regra": "saida_ilegivel", "caminho": ".", "linha": 1,
                                "evidencia": f"não consegui ler a saída de {stack.runner}", "teste": ""})
        return
    fatos["execucao"].update({"rodou": True, "timeout": False, **resultado})
    for lento in resultado["lentos"]:
        fatos["sinais"].append({"regra": "lento_para_o_tipo", "caminho": ".", "linha": 1,
                                "evidencia": f"{lento['teste']} levou {lento['faixa']}", "teste": lento["teste"]})

    if cobertura:
        linhas = stack.ler_cobertura(pasta_saida, escopo)
        fatos["cobertura"] = {"disponivel": bool(linhas), "ferramenta": stack.runner if linhas else None,
                              "por_arquivo": linhas}
```

E, dentro de `main()`, **depois** de montar os fatos e **antes** de gravar:

```python
    fatos["_raiz"] = raiz                      # usado só durante a execução; removido antes de gravar
    if args.executar:
        marcas = execucao.banco_a_vista(escopo)
        if marcas and not args.banco_ok:
            print("Banco configurado no ambiente de teste: " + ", ".join(marcas) + ".\n"
                  "A coleta já importa conftest/bootstrap e pode conectar ou truncar banco. "
                  "Confirme com --banco-ok se este ambiente for descartável.", file=sys.stderr)
            return EXIT_PARADA
        fatos["execucao"]["timeout"] = False
        executar(fatos, escopo, args.cobertura, args.timeout)
    fatos.pop("_raiz", None)
```

E acrescente `"timeout": False` ao dicionário inicial de `execucao` em `apurar()`, além de
`"ambiente": {"banco": execucao.banco_a_vista(escopo)}` junto de `repo`/`escopo`.

- [x] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest tests/test_diagnose_executar.py -q`
Expected: `9 passed`

- [x] **Step 6: Suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde (registre aqui a contagem real).

---

### Task 8: restrições verificáveis 1 e 2

**Files:**
- Create: `tests/test_restricoes.py`

Estas são as fitness functions do spec. Elas têm que falhar se alguém, no futuro, fizer o script
escrever fora do lugar ou executar sem aprovação.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_restricoes.py
"""Restrições verificáveis do spec — o teste é a regra, não a documentação."""
import ast
import json
import os
from pathlib import Path

import diagnose
from lib import pastas
from projeto import projeto_pytest
from runners import chamadas, instalar
from test_diagnose_executar import pytest_falso

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PODEM_EXECUTAR = {"lib/execucao.py", "lib/gitinfo.py"}


def retrato(raiz: Path) -> dict:
    """Conteúdo, data de modificação e pastas — a árvore inteira, .git incluído."""
    saida = {}
    for caminho in sorted(raiz.rglob("*")):
        relativo = str(caminho.relative_to(raiz))
        if caminho.is_dir():
            saida[relativo + "/"] = "dir"
        else:
            marca = caminho.stat().st_mtime_ns
            saida[relativo] = (caminho.read_bytes(), marca)
    return saida


def test_escrita_confinada(repo, tmp_path, monkeypatch):
    """Restrição 1: só a pasta de fatos muda."""
    projeto_pytest(repo)
    # runner que GRAVA onde as flags mandam: com um runner mudo, este teste passaria mesmo se a
    # skill apontasse a saída para dentro do projeto
    pytest_falso(tmp_path, monkeypatch)
    monkeypatch.chdir(repo.path)
    antes = retrato(repo.path)

    diagnose.main(["--repo", str(repo.path), "--executar", "--cobertura"])

    depois = retrato(repo.path)
    mexidos = {caminho for caminho in set(antes) | set(depois)
               if antes.get(caminho) != depois.get(caminho)}
    permitido = str(pastas.base(repo.path).relative_to(repo.path))
    fora = {c for c in mexidos if not c.startswith(permitido)}
    assert fora == set(), f"escreveu fora da pasta de fatos: {sorted(fora)}"


def test_nada_executa_sem_aprovacao(repo, tmp_path, monkeypatch):
    """Restrição 2: sem --executar, nenhum runner é chamado; com banco à vista, idem."""
    projeto_pytest(repo)
    registro = instalar(tmp_path, monkeypatch, "pytest", {"__padrao__": ("", None, None, 0)})

    diagnose.main(["--repo", str(repo.path)])
    assert chamadas(registro) == []

    monkeypatch.setenv("DATABASE_URL", "postgres://usuario@host/banco")
    diagnose.main(["--repo", str(repo.path), "--executar"])
    assert chamadas(registro) == []


def test_so_execucao_e_gitinfo_executam_processo():
    """Quem importa subprocess é auditável: dois módulos, e ninguém mais."""
    executores = {"subprocess", "multiprocessing", "pty"}
    culpados = []
    for arquivo in SCRIPTS.rglob("*.py"):
        relativo = str(arquivo.relative_to(SCRIPTS))
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                nomes = [no.module or ""]
            elif isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "__import__":
                nomes = [a.value for a in no.args if isinstance(a, ast.Constant)]
            if any(str(nome).split(".")[0] in executores for nome in nomes) \
                    and relativo not in PODEM_EXECUTAR:
                culpados.append(relativo)
    assert culpados == [], f"módulo fora da lista executando processo: {sorted(set(culpados))}"


def test_nenhum_modulo_usa_atalho_de_shell():
    """`shell=True`, os.system e amigos passariam por cima da lista de comandos."""
    proibidos = {"system", "popen", "execv", "execvp", "spawnl", "spawnv", "fork"}
    culpados = []
    for arquivo in SCRIPTS.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call):
                if any(isinstance(k, ast.keyword) and k.arg == "shell" and
                       getattr(k.value, "value", False) is True for k in no.keywords):
                    culpados.append(f"{arquivo.name}: shell=True")
                alvo = no.func.attr if isinstance(no.func, ast.Attribute) else ""
                if alvo in proibidos:
                    culpados.append(f"{arquivo.name}: {alvo}")
    assert culpados == []


def test_sem_rede_em_nenhum_script():
    proibidos = {"socket", "urllib", "http", "requests", "httpx", "ftplib", "telnetlib", "smtplib"}
    culpados = []
    for arquivo in SCRIPTS.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                culpados += [a.name for a in no.names if a.name.split(".")[0] in proibidos]
            elif isinstance(no, ast.ImportFrom) and (no.module or "").split(".")[0] in proibidos:
                culpados.append(no.module)
    assert culpados == [], f"import de rede em scripts/: {culpados}"
```

- [x] **Step 2: Rodar**

Run: `.venv/bin/python -m pytest tests/test_restricoes.py -q`
Expected: `5 passed`

> **O que este teste não cobre:** com runner falso, nada cria `.pytest_cache`/`.phpunit.cache`.
> Em projeto real esses caches aparecem — são **exceção declarada** no spec: a skill não os cria
> nem os remove, e o relatório lista o que apareceu. O teste garante o que a **skill** escreve,
> não o que o runner do projeto escreve.

- [x] **Step 3: Provar que as restrições pegam ataque de verdade (prova por mutação)**

Faça as três alterações abaixo, uma de cada vez, rode `tests/test_restricoes.py`, confirme o
**vermelho** e **desfaça**:

1. Em `diagnose.py`, antes de gravar os fatos, acrescente
   `(Path(escopo) / "sujeira.txt").write_text("oi", encoding="utf-8")` → `test_escrita_confinada` falha.
2. Em `diagnose.py`, chame `executar(...)` sem checar `args.executar` → `test_nada_executa_sem_aprovacao` falha.
3. Em `lib/sinais.py`, acrescente `import subprocess` → `test_so_execucao_e_gitinfo_executam_processo` falha.

Expected: cada alteração derruba exatamente o teste correspondente; a suíte volta verde ao desfazer.
Se alguma não derrubar, **o teste é falso** — conserte o teste antes de seguir.

- [x] **Step 4: Checkpoint do lote 2** — pausa de aprovação.

---

## Lote 3 — relatório e correção guiada

### Task 9: `report.py` — validação do `achados.json`

**Files:**
- Create: `scripts/report.py` (parte 1: validação)
- Test: `tests/test_report_validar.py`

O agente escreve `achados.json`; aqui ele é conferido contra os fatos. Recusa lista **todos** os
problemas de uma vez (exit 3) — igual à `sw-pr-message`.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_report_validar.py
import json

import pytest

from report import validar

FATOS = {
    "versao": 1,
    "repo": {"toplevel": "/x", "branch": "master", "head": "a" * 40},
    "escopo": {"tipo": "repo", "raiz": "."},
    "stacks": [{"linguagem": "py", "runner": "pytest", "nativo": True, "config": "pyproject.toml"}],
    "inventario": {"arquivos": 1, "testes": 2, "por_suite": {"unit": 2},
                   "lista": [{"caminho": "tests/unit/test_a.py", "testes": 2, "suite": "unit"}]},
    "execucao": {"rodou": False, "verde": None, "timeout": False, "passou": 0, "falhou": 0,
                 "pulado": 0, "duracao_faixa": None, "lentos": []},
    "cobertura": {"disponivel": False, "ferramenta": None, "por_arquivo": []},
    "sinais": [{"regra": "marcado_para_pular", "caminho": "tests/unit/test_a.py", "linha": 3,
                "evidencia": "@pytest.mark.skip", "teste": "test_x"}],
    "suspeitos": ["tests/unit/test_a.py"],
}


def achado(**extra):
    base = {"regra": "teste_desligado", "dimensao": "confiabilidade", "confianca": "alta",
            "caminho": "tests/unit/test_a.py", "linha": 3, "problema": "teste desligado há meses",
            "correcao": "reativar ou apagar", "sinal": "marcado_para_pular"}
    base.update(extra)
    return base


def test_achados_validos_passam():
    assert validar(FATOS, {"versao": 1, "achados": [achado()], "nao_e_problema": []}) == []


def test_lista_todos_os_problemas_de_uma_vez():
    """Cada achado carrega UM defeito, em linha própria: senão a regra de repetição soma junto."""
    ruins = {"versao": 1, "achados": [
        achado(dimensao="velocidade_maxima", linha=1),
        achado(confianca="altissima", linha=2),
        achado(caminho="tests/unit/nao-existe.py", linha=3, confianca="media", sinal=None),
        achado(problema="   ", linha=4, confianca="media", sinal=None),
        achado(correcao="", linha=5, confianca="media", sinal=None),
    ], "nao_e_problema": []}

    problemas = validar(FATOS, ruins)

    assert len(problemas) == 5, problemas
    assert any("dimensao" in p for p in problemas) and any("confianca" in p for p in problemas)
    assert any("nao-existe.py" in p for p in problemas)
    assert any("problema vazio" in p for p in problemas)
    assert any("correcao vazia" in p for p in problemas)


def test_confianca_alta_exige_sinal_do_script():
    sem_lastro = {"versao": 1, "achados": [achado(sinal="assercao_tautologica")], "nao_e_problema": []}

    problemas = validar(FATOS, sem_lastro)

    assert any("sem lastro" in p for p in problemas)


def test_confianca_media_nao_exige_sinal():
    julgado = {"versao": 1, "achados": [achado(confianca="media", sinal=None)], "nao_e_problema": []}

    assert validar(FATOS, julgado) == []


def test_achado_repetido_e_recusado():
    repetido = {"versao": 1, "achados": [achado(), achado()], "nao_e_problema": []}

    assert any("repetido" in p for p in validar(FATOS, repetido))


def test_linha_fora_do_arquivo_e_recusada(tmp_path):
    fatos = dict(FATOS, repo=dict(FATOS["repo"], toplevel=str(tmp_path)))
    (tmp_path / "tests/unit").mkdir(parents=True)
    (tmp_path / "tests/unit/test_a.py").write_text("um\ndois\n", encoding="utf-8")

    problemas = validar(fatos, {"versao": 1, "achados": [achado(linha=99, sinal=None,
                                                               confianca="media")],
                                "nao_e_problema": []})

    assert any("linha 99" in p for p in problemas)


def test_tipos_errados_viram_problema_e_nao_excecao():
    torto = {"versao": 1, "achados": "isto devia ser lista", "nao_e_problema": {}}

    problemas = validar(FATOS, torto)

    assert problemas and all(isinstance(p, str) for p in problemas)


def test_nao_e_problema_precisa_de_caminho_e_motivo():
    torto = {"versao": 1, "achados": [], "nao_e_problema": [{"caminho": "tests/unit/test_a.py"}]}

    assert any("motivo" in p for p in validar(FATOS, torto))


def test_regra_precisa_ser_texto_simples():
    injetado = {"versao": 1, "achados": [achado(regra="x\n\n## Seção falsa\n\n| a | b |")],
                "nao_e_problema": []}

    assert any("regra" in p for p in validar(FATOS, injetado))


def test_caminho_ou_linha_de_tipo_errado_viram_problema_e_nao_excecao():
    torto = {"versao": 1, "achados": [achado(caminho=["a"], linha=[3], confianca="media", sinal=None)],
             "nao_e_problema": []}

    problemas = validar(FATOS, torto)

    assert problemas and all(isinstance(p, str) for p in problemas)


def test_linha_booleana_nao_passa_por_inteiro():
    torto = {"versao": 1, "achados": [achado(linha=True, confianca="media", sinal=None)],
             "nao_e_problema": []}

    assert any("linha" in p for p in validar(FATOS, torto))


def test_ultima_linha_do_arquivo_e_valida_e_a_seguinte_nao(tmp_path):
    fatos = dict(FATOS, repo=dict(FATOS["repo"], toplevel=str(tmp_path)))
    (tmp_path / "tests/unit").mkdir(parents=True)
    (tmp_path / "tests/unit/test_a.py").write_text("um\ndois\n", encoding="utf-8")

    def com_linha(numero):
        return validar(fatos, {"versao": 1, "achados": [achado(linha=numero, confianca="media",
                                                              sinal=None)], "nao_e_problema": []})

    assert com_linha(2) == []
    assert any("linha 3" in p for p in com_linha(3)), "o arquivo tem 2 linhas"


def test_nao_e_problema_com_caminho_fora_do_inventario_e_recusado():
    torto = {"versao": 1, "achados": [],
             "nao_e_problema": [{"caminho": "tests/unit/nao-existe.py", "motivo": "convenção"}]}

    assert any("nao-existe.py" in p for p in validar(FATOS, torto))


def test_item_nulo_dentro_de_achados_vira_problema():
    problemas = validar(FATOS, {"versao": 1, "achados": [None, achado()], "nao_e_problema": []})

    assert any("objeto" in p for p in problemas)
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_report_validar.py -q`
Expected: `ModuleNotFoundError: No module named 'report'` — 8 falhas.

- [x] **Step 3: `scripts/report.py` (parte 1)**

```python
#!/usr/bin/env python3
"""Valida o `achados.json` contra o `fatos.json` e escreve o `test-health-report.md`."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from lib import gitinfo, pastas

EXIT_OK, EXIT_AMBIENTE, EXIT_RECUSA = 0, 2, 3

DIMENSOES = ("confiabilidade", "isolamento", "cobertura", "legibilidade", "velocidade")
CONFIANCAS = ("alta", "media", "baixa")


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def raiz_do_escopo(fatos) -> Path:
    """Caminhos do inventário são relativos ao ESCOPO, não ao topo do repositório."""
    return (Path(fatos["repo"]["toplevel"]) / fatos["escopo"]["raiz"]).resolve()


def _linhas_do_arquivo(raiz, relativo):
    caminho = Path(raiz) / relativo
    if not caminho.is_file():
        return None
    try:
        return len(caminho.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return None


def validar(fatos: dict, achados: dict) -> list:
    """Devolve a lista de problemas. Lista vazia = pode gravar."""
    problemas = []
    lista = achados.get("achados")
    if not isinstance(lista, list):
        return ["achados.json: 'achados' precisa ser uma lista"]
    nao_e_problema = achados.get("nao_e_problema", [])
    if not isinstance(nao_e_problema, list):
        problemas.append("achados.json: 'nao_e_problema' precisa ser uma lista")
        nao_e_problema = []

    conhecidos = {a["caminho"] for a in fatos["inventario"]["lista"]}
    sinais_por_caminho = {}
    for sinal in fatos.get("sinais", []):
        sinais_por_caminho.setdefault(sinal["caminho"], set()).add(sinal["regra"])

    vistos = set()
    for posicao, item in enumerate(lista, start=1):
        onde = f"achados[{posicao}]"
        if not isinstance(item, dict):
            problemas.append(f"{onde}: precisa ser um objeto")
            continue
        dimensao, confianca = item.get("dimensao"), item.get("confianca")
        caminho, linha, regra = item.get("caminho"), item.get("linha"), item.get("regra")
        if not isinstance(regra, str) or not regra.strip() or regra != " ".join(regra.split()):
            # a regra entra no markdown: com quebra de linha ela criaria seção ou tabela no relatório
            problemas.append(f"{onde}: regra precisa ser um texto curto, numa linha só")
        if dimensao not in DIMENSOES:
            problemas.append(f"{onde}: dimensao {dimensao!r} não é uma das {list(DIMENSOES)}")
        if confianca not in CONFIANCAS:
            problemas.append(f"{onde}: confianca {confianca!r} não é alta/media/baixa")
        if not isinstance(caminho, str):
            problemas.append(f"{onde}: caminho precisa ser texto")
        elif caminho not in conhecidos:
            problemas.append(f"{onde}: caminho {caminho!r} não está no inventário dos fatos")
        # bool é int em Python: `linha=True` passaria por inteiro positivo
        if not isinstance(linha, int) or isinstance(linha, bool) or linha <= 0:
            problemas.append(f"{onde}: linha precisa ser inteiro positivo")
        elif isinstance(caminho, str) and caminho in conhecidos:
            total = _linhas_do_arquivo(raiz_do_escopo(fatos), caminho)
            if total is not None and linha > total:
                problemas.append(f"{onde}: linha {linha} não existe em {caminho} ({total} linhas)")
        if not _texto(item.get("problema")):
            problemas.append(f"{onde}: problema vazio")
        if not _texto(item.get("correcao")):
            problemas.append(f"{onde}: correcao vazia")
        if confianca == "alta":
            sinal = item.get("sinal")
            if sinal not in sinais_por_caminho.get(caminho, set()):
                problemas.append(f"{onde}: confiança alta sem lastro — nenhum sinal {sinal!r} "
                                 f"em {caminho} nos fatos")
        chave = (str(caminho), str(linha), str(regra))
        if chave in vistos:
            problemas.append(f"{onde}: achado repetido para {caminho}:{linha}")
        vistos.add(chave)

    for posicao, item in enumerate(nao_e_problema, start=1):
        if not isinstance(item, dict) or not _texto(item.get("caminho")):
            problemas.append(f"nao_e_problema[{posicao}]: precisa de caminho")
            continue
        if item["caminho"] not in conhecidos:
            problemas.append(f"nao_e_problema[{posicao}]: caminho {item['caminho']!r} "
                             "não está no inventário dos fatos")
        if not _texto(item.get("motivo")):
            problemas.append(f"nao_e_problema[{posicao}]: motivo vazio")
    return problemas
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_report_validar.py -q`
Expected: `8 passed`

---

### Task 10: `report.py` — notas, markdown e a restrição 4

**Files:**
- Modify: `scripts/report.py` (parte 2: notas, montagem, gravação, `main`)
- Test: `tests/test_report_montar.py`

Quem calcula nota é o script, a partir dos fatos — o agente só traz achados. Dimensão sem fato
sai `⚪ sem dados`, e **não existe nota agregada**.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_report_montar.py
import json

import report
from lib import pastas
from test_report_validar import FATOS, achado


def montar(fatos=None, achados=None, data="2026-09-18"):
    corpo = {"versao": 1, "achados": [achado()], "nao_e_problema": []}
    return report.montar(fatos or FATOS, achados or corpo, data)


def test_cabecalho_traz_escopo_stack_e_inventario():
    texto = montar()

    assert texto.startswith("# Saúde dos testes — .\n")
    assert "pytest" in texto and "1 arquivo" in texto and "2 teste" in texto


def test_sem_execucao_cobertura_e_velocidade_ficam_sem_dados():
    texto = montar()

    assert "| Cobertura | ⚪ sem dados |" in texto
    assert "| Velocidade | ⚪ sem dados |" in texto


def test_suite_vermelha_derruba_a_confiabilidade():
    fatos = dict(FATOS, execucao=dict(FATOS["execucao"], rodou=True, verde=False, falhou=3,
                                      duracao_faixa="10-60s"))

    texto = montar(fatos=fatos)

    assert "| Confiabilidade | 🔴" in texto
    assert "3 teste(s) falhando" in texto


def test_achado_de_confianca_alta_vira_secao_propria_com_arquivo_e_linha():
    texto = montar()

    assert "### Confiança alta" in texto
    assert "`tests/unit/test_a.py:3`" in texto
    assert "reativar ou apagar" in texto


def test_confianca_baixa_entra_como_verificar_e_nunca_como_corrigir():
    corpo = {"versao": 1, "achados": [achado(confianca="baixa", sinal=None)], "nao_e_problema": []}

    texto = montar(achados=corpo)

    assert "### Verificar" in texto
    assert "### Confiança baixa" not in texto


def test_o_que_nao_e_problema_aparece_no_fim():
    corpo = {"versao": 1, "achados": [],
             "nao_e_problema": [{"caminho": "tests/unit/test_a.py", "motivo": "convenção do time"}]}

    texto = montar(achados=corpo)

    assert "## O que não é problema" in texto and "convenção do time" in texto


def test_texto_do_agente_vira_uma_linha_so():
    corpo = {"versao": 1, "achados": [achado(problema="linha um\n## título falso\nlinha dois")],
             "nao_e_problema": []}

    texto = montar(achados=corpo)

    assert "linha um ## título falso linha dois" in texto
    assert not any(linha.startswith("#") for linha in texto.splitlines()
                   if "título falso" in linha), "texto do agente não pode virar seção do relatório"


def test_relatorio_e_deterministico():
    """Restrição 4: a ordem em que o agente escreveu os achados não pode mudar o relatório."""
    um = achado(linha=1, caminho="tests/unit/test_a.py", regra="a", confianca="media", sinal=None)
    dois = achado(linha=2, caminho="tests/unit/test_a.py", regra="b", confianca="media", sinal=None)

    direto = montar(achados={"versao": 1, "achados": [um, dois], "nao_e_problema": []})
    invertido = montar(achados={"versao": 1, "achados": [dois, um], "nao_e_problema": []})

    assert direto == invertido
    assert direto.index("regra: a" if "regra: a" in direto else "*(a,") < \
        direto.index("*(b,"), "a ordem impressa é por arquivo e linha, não pela ordem de escrita"


def test_gravar_cria_o_arquivo_e_registra_no_exclude(repo):
    destino, avisos = report.gravar(repo.path, "# Saúde dos testes — .\n")
    exclude = (repo.path / ".git" / "info" / "exclude").read_text(encoding="utf-8")

    assert destino == repo.path / "test-health-report.md"
    assert destino.read_text(encoding="utf-8").startswith("# Saúde dos testes")
    assert exclude.count("/test-health-report.md") == 1
    assert avisos == []


def test_gravar_duas_vezes_nao_duplica_a_linha_do_exclude(repo):
    report.gravar(repo.path, "a\n")
    report.gravar(repo.path, "b\n")
    exclude = (repo.path / ".git" / "info" / "exclude").read_text(encoding="utf-8")

    assert exclude.count("/test-health-report.md") == 1


def test_relatorio_versionado_grava_e_avisa(repo):
    (repo.path / "test-health-report.md").write_text("antigo\n", encoding="utf-8")
    repo.git("add", "-A"); repo.git("commit", "-qm", "chore: relatorio")

    _, avisos = report.gravar(repo.path, "novo\n")

    assert any("versionado" in a for a in avisos)


def test_main_recusa_achados_invalidos_com_exit_3(repo, capsys, monkeypatch):
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps(dict(FATOS, repo=dict(FATOS["repo"],
        toplevel=str(repo.path), branch="master"))), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1, "achados": [achado(dimensao="x")],
                                                     "nao_e_problema": []}), encoding="utf-8")

    codigo = report.main(["--repo", str(repo.path), "--data", "2026-09-18"])

    assert codigo == 3
    assert "dimensao" in capsys.readouterr().err
    assert not (repo.path / "test-health-report.md").exists()


def test_main_recusa_fatos_de_outra_branch_com_exit_2(repo, capsys):
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps(dict(FATOS, repo=dict(FATOS["repo"],
        toplevel=str(repo.path), branch="outra"))), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1, "achados": [], "nao_e_problema": []}),
                                         encoding="utf-8")

    codigo = report.main(["--repo", str(repo.path)])

    assert codigo == 2
    assert "outra" in capsys.readouterr().err


def test_regra_do_agente_nao_cria_secao_nem_tabela():
    corpo = {"versao": 1, "achados": [achado(regra="x\n\n## Seção falsa\n\n| a | b |")],
             "nao_e_problema": []}

    texto = montar(achados=corpo)

    assert not any(linha.startswith(("#", "|")) for linha in texto.splitlines()
                   if "Seção falsa" in linha)


def test_cobertura_baixa_nao_sai_verde():
    fatos = dict(FATOS,
                 execucao=dict(FATOS["execucao"], rodou=True, verde=True, duracao_faixa="1-10s"),
                 cobertura={"disponivel": True, "ferramenta": "pytest",
                            "por_arquivo": [{"caminho": "src/a.py", "linhas_pct": 3, "ramos_pct": 0}]})

    texto = montar(fatos=fatos)

    assert "| Cobertura | 🔴" in texto and "3%" in texto


def test_timeout_nao_vira_sem_dados_por_falta_de_autorizacao():
    fatos = dict(FATOS, execucao=dict(FATOS["execucao"], rodou=True, timeout=True, verde=None))

    texto = montar(fatos=fatos)

    assert "a execução não foi autorizada" not in texto
    assert "| Velocidade | 🔴" in texto


def test_teste_lento_tira_a_velocidade_do_verde():
    fatos = dict(FATOS, execucao=dict(FATOS["execucao"], rodou=True, verde=True,
                                      duracao_faixa="1-10s",
                                      lentos=[{"teste": "test_x", "faixa": "1-10s"}]))

    texto = montar(fatos=fatos)

    assert "| Velocidade | 🟡" in texto


def test_relatorio_recusa_escrever_atraves_de_link_simbolico(repo, tmp_path):
    fora = tmp_path / "fora.txt"
    fora.write_text("não pode ser sobrescrito\n", encoding="utf-8")
    (repo.path / "test-health-report.md").symlink_to(fora)
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps(dict(FATOS, repo=dict(FATOS["repo"],
        toplevel=str(repo.path), branch="master"))), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1, "achados": [], "nao_e_problema": []}),
                                         encoding="utf-8")

    codigo = report.main(["--repo", str(repo.path), "--data", "2026-09-18"])

    assert codigo == 2
    assert fora.read_text(encoding="utf-8") == "não pode ser sobrescrito\n"


def test_fatos_sem_as_chaves_esperadas_sai_com_dois(repo, capsys):
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps({"versao": 1, "sinais": []}), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1, "achados": [], "nao_e_problema": []}),
                                         encoding="utf-8")

    assert report.main(["--repo", str(repo.path)]) == 2
    assert "ilegível" in capsys.readouterr().err


def test_em_monorepo_o_relatorio_vai_para_a_raiz_do_pacote(repo):
    (repo.path / "packages/api/tests/unit").mkdir(parents=True)
    (repo.path / "packages/api/tests/unit/test_a.py").write_text("def test_a():\n    assert 1\n",
                                                                 encoding="utf-8")
    fatos = dict(FATOS, repo=dict(FATOS["repo"], toplevel=str(repo.path), branch="master"),
                 escopo={"tipo": "pacote", "raiz": "packages/api"})
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps(fatos), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1,
        "achados": [achado(linha=1, confianca="media", sinal=None)], "nao_e_problema": []}),
        encoding="utf-8")

    assert report.main(["--repo", str(repo.path), "--data", "2026-09-18"]) == 0
    assert (repo.path / "packages/api/test-health-report.md").exists()
    assert not (repo.path / "test-health-report.md").exists()
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_report_montar.py -q`
Expected: `AttributeError: module 'report' has no attribute 'montar'` — 13 falhas.

- [x] **Step 3: `scripts/report.py` (parte 2)**

```python
# acrescentar ao report.py

ROTULOS = {"confiabilidade": "Confiabilidade", "isolamento": "Isolamento", "cobertura": "Cobertura",
           "legibilidade": "Legibilidade", "velocidade": "Velocidade"}
LINHA = "/test-health-report.md"


def uma_linha(valor) -> str:
    """Texto do agente nunca cria seção: qualquer espaço em branco vira um espaço só."""
    return " ".join(_texto(valor).split())


def notas(fatos: dict, achados: list) -> dict:
    """Nota por dimensão, calculada dos fatos. Sem fato que sustente → ⚪ sem dados.

    A base de cada nota diz DE ONDE ela veio: "sem dados" por execução recusada é diferente de
    "sem dados" por cobertura não pedida, e timeout não é falta de autorização.
    """
    execucao, cobertura, inventario = fatos["execucao"], fatos["cobertura"], fatos["inventario"]
    varridos = f"nenhum sinal em {inventario['arquivos']} arquivo(s) varrido(s)"
    saida = {}
    for dimensao in DIMENSOES:
        desta = [a for a in achados if a.get("dimensao") == dimensao]
        altas = [a for a in desta if a.get("confianca") == "alta"]

        if dimensao == "cobertura":
            por_arquivo = cobertura.get("por_arquivo") or []
            if not cobertura.get("disponivel") or not por_arquivo:
                motivo = ("a execução não foi autorizada" if not execucao.get("rodou")
                          else "a execução não pediu cobertura")
                saida[dimensao] = ("⚪ sem dados", motivo)
                continue
            pior = min(int(a.get("linhas_pct") or 0) for a in por_arquivo)
            if altas or pior < 20:
                saida[dimensao] = ("🔴 grave", f"arquivo com {pior}% das linhas cobertas")
            elif pior < 60:
                saida[dimensao] = ("🟡 atenção", f"arquivo com {pior}% das linhas cobertas")
            else:
                saida[dimensao] = ("🟢 ok", f"pior arquivo com {pior}% das linhas cobertas")
            continue

        if dimensao == "velocidade":
            if not execucao.get("rodou"):
                saida[dimensao] = ("⚪ sem dados", "a execução não foi autorizada")
            elif execucao.get("timeout"):
                saida[dimensao] = ("🔴 grave", "a suíte estourou o tempo limite")
            elif altas:
                saida[dimensao] = ("🔴 grave", f"{len(altas)} achado(s) de confiança alta")
            elif execucao.get("lentos"):
                saida[dimensao] = ("🟡 atenção",
                                   f"{len(execucao['lentos'])} teste(s) acima do limite do tipo")
            else:
                saida[dimensao] = ("🟢 ok", f"suíte em {execucao.get('duracao_faixa') or 'n/a'}")
            continue

        if dimensao == "confiabilidade" and execucao.get("verde") is False:
            extra = f" e {len(altas)} achado(s) de confiança alta" if altas else ""
            saida[dimensao] = ("🔴 grave",
                               f"{execucao.get('falhou', 0)} teste(s) falhando na suíte{extra}")
        elif altas:
            saida[dimensao] = ("🔴 grave", f"{len(altas)} achado(s) de confiança alta")
        elif desta:
            saida[dimensao] = ("🟡 atenção", f"{len(desta)} achado(s) a revisar")
        else:
            saida[dimensao] = ("🟢 ok", varridos)
    return saida


def montar(fatos: dict, achados: dict, data: str) -> str:
    lista = [a for a in achados.get("achados", []) if isinstance(a, dict)]
    inv, execucao = fatos["inventario"], fatos["execucao"]
    linhas = [f"# Saúde dos testes — {fatos['escopo']['raiz']}", ""]
    runners = ", ".join(s["runner"] for s in fatos["stacks"]) or "nenhum runner reconhecido"
    resumo_suites = " · ".join(f"{suite} {qtd}" for suite, qtd in sorted(inv["por_suite"].items()))
    linhas += [f"{data} · {runners} · {inv['arquivos']} arquivo(s) · {inv['testes']} teste(s)"
               f"{' · ' + resumo_suites if resumo_suites else ''}", ""]

    linhas += ["## Resumo", ""]
    if execucao.get("rodou"):
        estado = "verde" if execucao.get("verde") else ("sem leitura" if execucao.get("verde") is None
                                                        else "VERMELHA")
        linhas.append(f"Suíte {estado}: {execucao.get('passou', 0)} passaram, "
                      f"{execucao.get('falhou', 0)} falharam, {execucao.get('pulado', 0)} pulados, "
                      f"duração {execucao.get('duracao_faixa') or 'n/a'}.")
    else:
        linhas.append("A suíte não foi executada: cobertura e velocidade ficam sem nota.")
    linhas += [f"{len(lista)} achado(s) em {len({a.get('caminho') for a in lista})} arquivo(s).", ""]

    linhas += ["## Notas por dimensão", "", "| Dimensão | Nota | Base |", "|---|---|---|"]
    for dimensao, (nota, base) in notas(fatos, lista).items():
        linhas.append(f"| {ROTULOS[dimensao]} | {nota} | {base} |")
    linhas.append("")

    grupos = (("Confiança alta", "alta"), ("Confiança média", "media"), ("Verificar", "baixa"))
    linhas += ["## Achados", ""]
    for titulo, confianca in grupos:
        desta = [a for a in lista if a.get("confianca") == confianca]
        if not desta:
            continue
        linhas += [f"### {titulo}", ""]
        for item in sorted(desta, key=lambda a: (a.get("caminho", ""), a.get("linha", 0))):
            linhas.append(f"- `{uma_linha(item.get('caminho'))}:{item.get('linha')}` — "
                          f"{uma_linha(item.get('problema'))} "
                          f"*({uma_linha(item.get('regra'))}, {ROTULOS.get(item.get('dimensao'), '')})*  "
                          f"→ {uma_linha(item.get('correcao'))}")
        linhas.append("")
    if not lista:
        linhas += ["Nenhum achado.", ""]

    nao_problema = [i for i in achados.get("nao_e_problema", []) if isinstance(i, dict)]
    if nao_problema:
        linhas += ["## O que não é problema", ""]
        for item in nao_problema:
            linhas.append(f"- `{uma_linha(item.get('caminho'))}` — {uma_linha(item.get('motivo'))}")
        linhas.append("")
    return "\n".join(linhas).rstrip("\n") + "\n"


def gravar(raiz, texto: str):
    """Grava o relatório na raiz e registra a linha no exclude. Devolve (destino, avisos)."""
    raiz = Path(raiz)
    avisos = []
    destino = raiz / "test-health-report.md"
    destino.write_text(texto, encoding="utf-8")
    if gitinfo.dentro_de_repo(raiz):
        if gitinfo.rastreado(raiz, "test-health-report.md"):
            avisos.append("test-health-report.md está versionado: o exclude não protege")
        else:
            # o exclude é lido a partir do topo: em monorepo a linha precisa do caminho do pacote
            linha = "/" + str(destino.relative_to(gitinfo.toplevel(raiz)))
            exclude = gitinfo.git_path(raiz, "info/exclude")
            exclude.parent.mkdir(parents=True, exist_ok=True)
            atual = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
            if linha not in atual.splitlines():
                separador = "" if atual.endswith("\n") or not atual else "\n"
                exclude.write_text(atual + separador + linha + "\n", encoding="utf-8")
    return destino, avisos


def _ambiente(mensagem) -> int:
    print(mensagem, file=sys.stderr)
    return EXIT_AMBIENTE


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Monta o test-health-report.md.")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--data", default=None, help="data do cabeçalho (padrão: hoje)")
    args = ap.parse_args(argv)

    raiz = Path(args.repo)
    if not raiz.is_dir():
        return _ambiente(f"--repo {raiz} não existe.")
    raiz = raiz.resolve()

    avisos_do_ambiente = []
    arquivo_fatos, arquivo_achados = pastas.fatos(raiz), pastas.achados(raiz)
    if not arquivo_fatos.exists():
        return _ambiente(f"fatos.json não encontrado em {arquivo_fatos} — rode diagnose.py antes.")
    try:
        fatos = json.loads(arquivo_fatos.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        fatos = None
    esperadas = ("versao", "repo", "escopo", "inventario", "execucao", "cobertura", "sinais")
    if not isinstance(fatos, dict) or any(chave not in fatos for chave in esperadas) \
            or not isinstance(fatos.get("sinais"), list) or fatos.get("versao") != 1:
        return _ambiente("fatos.json ilegível ou de outra versão — rode diagnose.py de novo.")
    if gitinfo.dentro_de_repo(raiz):
        atual = gitinfo.branch(raiz)
        if fatos["repo"].get("branch") != atual:
            return _ambiente(f"fatos.json é da branch {fatos['repo'].get('branch')!r}, "
                             f"mas você está em {atual!r} — rode diagnose.py de novo.")
        if fatos["repo"].get("head") and fatos["repo"]["head"] != gitinfo.head(raiz):
            # mesma branch, commit diferente: as linhas dos achados podem ter andado
            avisos_do_ambiente.append("os fatos são de outro commit desta branch: confira as linhas "
                                      "ou rode diagnose.py de novo")
    if not arquivo_achados.exists():
        print(f"achados.json não encontrado em {arquivo_achados}", file=sys.stderr)
        return EXIT_RECUSA
    try:
        achados = json.loads(arquivo_achados.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as erro:
        print(f"JSON malformado em achados.json: {erro}", file=sys.stderr)
        return EXIT_RECUSA
    if not isinstance(achados, dict):
        print("achados.json deve ser um objeto JSON", file=sys.stderr)
        return EXIT_RECUSA

    destino_raiz = raiz_do_escopo(fatos)
    if (destino_raiz / "test-health-report.md").is_symlink():
        # link versionado apontando para fora faria o relatório sobrescrever arquivo de qualquer lugar
        return _ambiente("test-health-report.md é um link simbólico: não escrevo através dele. "
                         "Remova o link e rode de novo.")

    problemas = validar(fatos, achados)
    if problemas:
        print("achados.json recusado — corrija todos os itens e rode de novo:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return EXIT_RECUSA

    data = args.data or date.today().isoformat()
    destino, avisos = gravar(destino_raiz, montar(fatos, achados, data))
    print(f"test-health-report.md gravado em {destino}")
    for aviso in avisos_do_ambiente + avisos:
        print(f"aviso: {aviso}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
```

> `from datetime import date` vai no topo do `report.py`, junto dos outros imports: `__import__` é vigiado pela checagem de processos da Task 8.

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_report_montar.py -q`
Expected: `13 passed`

- [x] **Step 5: Suíte inteira e prova de determinismo fora do pytest**

Run:
```bash
cd ~/.claude/skills/sw-auto-test && .venv/bin/python -m pytest -q
.venv/bin/python scripts/diagnose.py --repo .
echo '{"versao":1,"achados":[],"nao_e_problema":[]}' > "$(git rev-parse --git-path sw-auto-test)/achados.json"
.venv/bin/python scripts/report.py --repo . --data 2026-01-01 && md5sum test-health-report.md
.venv/bin/python scripts/report.py --repo . --data 2026-01-01 && md5sum test-health-report.md
```
Expected: os dois `md5sum` iguais. (A skill não é repositório git; se `git rev-parse` falhar, use
o caminho que o `diagnose.py` imprimiu.)

---

### Task 11: `SKILL.md` — modo diagnóstico e correção guiada

**Files:**
- Modify: `~/.claude/skills/sw-auto-test/SKILL.md`

- [x] **Step 1: Inserir a seção do modo diagnóstico**

Acrescente **antes** da seção `## Examples`, exatamente este texto:

````markdown
## Modo diagnóstico — avaliar os testes que já existem

Rode este modo quando o pedido for sobre a **qualidade da suíte** ("meus testes estão bons?",
"diagnostica os testes", "a suíte presta?"), e o modo gerar quando o pedido for **escrever teste
novo**. Frase ambígua ("olha meus testes") → decida com `AskUserQuestion`, nunca no chute.
Qualidade do **código de produção** não é aqui: isso é `sw-code-review`.

### 1. Escopo

Em monorepo, o padrão é o pacote em que o usuário está ou que ele apontou. Ofereça ampliar para o
repositório inteiro via `AskUserQuestion` — não amplie sozinho.

### 2. Apurar sem executar nada

```bash
python3 <skill-dir>/scripts/diagnose.py [--escopo <pacote>]
```

Sai com 0 e imprime o caminho do `fatos.json`, o inventário, as stacks e quantos sinais achou.
Exit 2 → mostre a mensagem e pare (sem teste no escopo, `--repo`/`--escopo` inexistente).
Se ele restaurar resíduo de backup, **diga isso ao usuário**: algum uso anterior morreu no meio.

### 3. Perguntar sobre executar

A execução é o que traz suíte verde/vermelha, tempo por teste e cobertura — e é opt-in. Pergunte
via `AskUserQuestion`, **mostrando o comando** que será usado (está em `fatos.stacks`) e o que foi
detectado em `fatos.ambiente.banco`:

- **Só estática** → siga com o que já tem; cobertura e velocidade ficarão `⚪ sem dados`.
- **Descoberta + suíte** → `--executar`.
- **Com cobertura** → `--executar --cobertura`.

Havendo banco no ambiente, o script **para** e pede `--banco-ok`. Repasse o aviso ao usuário com
o que foi detectado e só acrescente a flag com o "sim" dele. Integração e e2e só sob pedido
explícito. Timeout padrão de 300s; estouro vira achado e a skill continua.

### 4. Julgar

Leia o `fatos.json` inteiro e **apenas os arquivos listados em `suspeitos`** — não leia a suíte
toda. Escreva `achados.json` na mesma pasta:

```json
{ "versao": 1,
  "achados": [{"regra": "assercao_tautologica", "dimensao": "confiabilidade", "confianca": "media",
               "caminho": "tests/unit/test_x.py", "linha": 42,
               "problema": "só verifica que o retorno não é nulo",
               "correcao": "asserte o valor esperado de `calcular_total`", "sinal": null}],
  "nao_e_problema": [{"caminho": "tests/unit/test_y.php", "motivo": "convenção diferente da nossa, porém consistente"}] }
```

Regras:
- **Confiança alta exige lastro**: só use quando existir um sinal do script para aquele arquivo, e
  cite o id dele em `sinal`. Sem lastro, o `report.py` recusa.
- **Confiança baixa** é para indício — ela entra no relatório como "verificar", nunca como corrigir.
- **Um achado por problema**, com `arquivo:linha` que o usuário possa clicar.
- O que você julgar e **não** for problema (convenção diferente, mas consistente) vai em
  `nao_e_problema` — evita que o relatório vire lista de falso positivo.
- O que procurar, além dos sinais: asserção tautológica ou frouxa; mock do próprio sujeito, ou
  tudo mockado a ponto de o teste verificar só o mock; asserção em detalhe interno; nome que não
  descreve comportamento; teste que testa o framework; vários comportamentos num teste; caminho
  crítico sem teste (cruze `fatos.cobertura` com o código).

### 5. Relatório

```bash
python3 <skill-dir>/scripts/report.py
```

Exit 3 → ele lista **todos** os problemas do `achados.json`; corrija todos e rode de novo. Na 3ª
recusa seguida, pare e mostre ao usuário. Exit 2 → ambiente (fatos de outra branch, por exemplo):
mostre e pare, sem mexer no `achados.json`.

### 6. Correção guiada

Abra um menu de rumo (`AskUserQuestion`): **corrigir os de confiança alta** · **revisar item a
item** · **só o relatório**. Depois:

1. **Antes de editar qualquer arquivo**, guarde o original:
   `python3 <skill-dir>/scripts/backup.py guardar <arquivo>`. Avise se o arquivo tiver alteração
   não commitada — a correção vai se misturar ao trabalho dele.
2. Corrija **em lotes pequenos** (3 a 5 arquivos).
3. Rode a suíte do lote. Verde → `backup.py descartar <arquivo>`. Vermelho →
   `backup.py restaurar <arquivo>` e registre no relatório por que aquele item ficou de fora.
   **Nunca use `git checkout`**: apagaria o trabalho não commitado do usuário.
4. **Suíte já vermelha antes de começar** é o achado nº 1: pare e pergunte se o usuário quer
   consertar isso primeiro. Corrigir teste sobre suíte quebrada esconde o que quebrou.

Feche informando: caminho do relatório, notas por dimensão, quantos achados por confiança, o que
foi corrigido, o que foi revertido, e o que ficou `⚪ sem dados` por falta de execução.
````

- [x] **Step 2: Conferir que o roteamento e os limites ficaram explícitos**

Run: `grep -n "sw-code-review\|AskUserQuestion\|banco-ok\|git checkout" ~/.claude/skills/sw-auto-test/SKILL.md`
Expected: pelo menos uma linha de cada.

- [x] **Step 3: Checkpoint do lote 3** — pausa de aprovação. **O diagnóstico está inteiro aqui.**

---

## Lote 4 — o modo gerar

### Task 12: `backup.py` CLI, baseline e prova do vermelho

**Files:**
- Create: `scripts/backup.py`
- Create: `references/generation.md`
- Modify: `~/.claude/skills/sw-auto-test/SKILL.md` (seção do modo gerar)
- Test: `tests/test_backup_cli.py`

- [x] **Step 1: Escrever os testes do CLI**

```python
# tests/test_backup_cli.py
import backup as cli
from lib import backup


def test_guardar_restaurar_e_descartar_pela_linha_de_comando(repo, capsys):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    alvo = repo.path / "src/a.py"

    assert cli.main(["--repo", str(repo.path), "guardar", "src/a.py"]) == 0
    alvo.write_text("mexido\n", encoding="utf-8")
    assert cli.main(["--repo", str(repo.path), "restaurar", "src/a.py"]) == 0
    assert alvo.read_text(encoding="utf-8") == "original\n"

    cli.main(["--repo", str(repo.path), "guardar", "src/a.py"])
    assert cli.main(["--repo", str(repo.path), "descartar", "src/a.py"]) == 0
    assert backup.residuo(repo.path) == []


def test_varrer_lista_e_restaura_residuo(repo, capsys):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    (repo.path / "src/a.py").write_text("mexido\n", encoding="utf-8")

    assert cli.main(["--repo", str(repo.path), "varrer"]) == 0

    assert (repo.path / "src/a.py").read_text(encoding="utf-8") == "original\n"
    assert "src/a.py" in capsys.readouterr().out


def test_guardar_arquivo_inexistente_sai_com_dois(repo, capsys):
    assert cli.main(["--repo", str(repo.path), "guardar", "nao-existe.py"]) == 2
    assert "não existe" in capsys.readouterr().err


def test_restaurar_sem_backup_avisa_e_sai_com_dois(repo, capsys):
    repo.escrever({"src/a.py": "x\n"})
    repo.commit("feat: a")

    assert cli.main(["--repo", str(repo.path), "restaurar", "src/a.py"]) == 2
    assert "sem backup" in capsys.readouterr().err


def test_recusa_caminho_fora_da_raiz(repo, capsys):
    assert cli.main(["--repo", str(repo.path), "guardar", "../fora.txt"]) == 2
    assert cli.main(["--repo", str(repo.path), "guardar", "/etc/hostname"]) == 2
    assert "fora" in capsys.readouterr().err.lower()


def test_restaurar_avisa_quando_sobrescreve_alteracao_posterior(repo, capsys):
    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    (repo.path / "src/a.py").write_text("mexido depois do backup\n", encoding="utf-8")

    assert cli.main(["--repo", str(repo.path), "restaurar", "src/a.py"]) == 0
    assert "alteração posterior ao backup" in capsys.readouterr().out


def test_varrer_com_a_copia_sumida_avisa_e_nao_sai_zero(repo, capsys):
    from lib import pastas

    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    next(pastas.backups(repo.path).glob("*.bak")).unlink()

    assert cli.main(["--repo", str(repo.path), "varrer"]) == 2
    assert "não consegui restaurar" in capsys.readouterr().err


def test_guardar_com_a_copia_sumida_sai_com_dois_e_sem_traceback(repo, capsys):
    from lib import pastas

    repo.escrever({"src/a.py": "original\n"})
    repo.commit("feat: a")
    backup.guardar(repo.path, "src/a.py")
    next(pastas.backups(repo.path).glob("*.bak")).unlink()

    assert cli.main(["--repo", str(repo.path), "guardar", "src/a.py"]) == 2
    assert "sumiu" in capsys.readouterr().err
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_backup_cli.py -q`
Expected: `ModuleNotFoundError: No module named 'backup'` — 4 falhas.

- [x] **Step 3: `scripts/backup.py`**

```python
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
        print("restaurado: " + ", ".join(restaurados["sobrescrito"] + restaurados["intacto"]))
        if restaurados["sobrescrito"]:
            print("atenção: sobrescrevi alteração posterior ao backup em "
                  + ", ".join(restaurados["sobrescrito"]))
        return EXIT_OK

    if not args.arquivo:
        print(f"{args.acao} precisa do caminho do arquivo.", file=sys.stderr)
        return EXIT_ERRO
    alvo = raiz / args.arquivo

    if args.acao == "guardar":
        if not alvo.is_file():
            print(f"{args.arquivo} não existe.", file=sys.stderr)
            return EXIT_ERRO
        backup.guardar(raiz, args.arquivo)
        print(f"guardado: {args.arquivo}")
        return EXIT_OK

    feito = backup.restaurar(raiz, args.arquivo) if args.acao == "restaurar" \
        else backup.descartar(raiz, args.arquivo)
    if not feito:
        print(f"{args.arquivo}: sem backup guardado.", file=sys.stderr)
        return EXIT_ERRO
    print(f"{args.acao}: {args.arquivo}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_backup_cli.py -q`
Expected: `4 passed`

- [x] **Step 5: `references/generation.md`** — criar com o texto abaixo

````markdown
# Modo gerar — detalhes

## Baseline antes de gerar

Antes de escrever teste novo, saiba se a suíte já estava vermelha. Ofereça rodar
(`diagnose.py --executar`) e guarde o resultado. **Sem baseline**, diga no resumo final: "não dá
para distinguir bug do código de quebra que já existia".

## Prova do vermelho

Depois de gerar, prove que o teste acusa o erro que promete acusar. Em **até 3 testes**, os que
cobrem regra de negócio — nunca glue code:

1. Pré-requisitos: é repositório git; o arquivo **de produção** a mutar está versionado e sem
   alteração pendente (`git status --porcelain -- <arquivo>` vazio); nenhum watcher, dev server ou
   formatador ao salvar está rodando (**pergunte ao usuário**; na dúvida, pule a prova e diga por quê).
2. `python3 <skill-dir>/scripts/backup.py guardar <arquivo de produção>`.
3. Mute **uma** coisa por vez no trecho que o teste cobre: inverter uma condição, trocar o retorno
   por constante, neutralizar a validação.
4. Rode **só aquele teste**.
5. `python3 <skill-dir>/scripts/backup.py restaurar <arquivo>` — sempre, inclusive se algo falhar.
6. **Teste ficou vermelho** → ele presta. **Continuou verde** → é o defeito que esta prova existe
   para achar: relate ("o teste não prova o comportamento que o nome promete") e proponha o ajuste.
   Não reescreva sozinho.

Sem git, não faça a prova: não há como garantir a volta com segurança.

## Determinismo no teste gerado

Semente fixa em qualquer aleatório; relógio congelado (freezegun, `vi.setSystemTime`,
`Carbon::setTestNow`) em vez de `datetime.now()`; nada de `sleep`; cada teste monta o próprio
estado, sem depender de ordem.

## Proibido forçar verde

- Não altere código de produção para o teste passar.
- Não use `skip`/`xfail`/`only` para esconder falha.
- Nada de asserção que passa de qualquer jeito ("não é nulo", "não lançou").
- Teste novo falhando por **bug do código** → relate o bug. Consertar o teste aí é apagar o achado.

## Cobertura

Só com a ferramenta nativa (`--cov`, `--coverage`, `--coverage-clover`). Diga sempre que percentual
alto não significa suíte boa — ele mede linha executada, não comportamento verificado.
````

- [x] **Step 6: Ligar o `SKILL.md` ao novo arquivo**

Na seção "After generating tests" do `SKILL.md`, acrescente como primeiros itens:

```markdown
1. **Rode a suíte** e mostre o resultado. Teste gerado que não roda não é entrega.
2. **Prove o vermelho** em até 3 testes — o passo a passo está em
   [`references/generation.md`](references/generation.md), que também traz baseline, determinismo
   e a regra de nunca forçar verde. **Leia antes de gerar.**
```

- [x] **Step 7: Suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde.

---

### Task 13: arrumação do `SKILL.md` e gatilhos PT-BR

**Files:**
- Create: `references/frameworks.md`, `references/aaa-por-linguagem.md`, `references/diagnostico.md`
- Modify: `~/.claude/skills/sw-auto-test/SKILL.md`
- Test: `tests/test_skill_md.py`

- [x] **Step 1: Escrever o teste da restrição 4 (tamanho e referências)**

```python
# tests/test_skill_md.py
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
REFERENCES = SKILL.parent / "references"


def test_skill_md_cabe_no_limite():
    assert len(SKILL.read_text(encoding="utf-8").splitlines()) < 220


def test_referencias_citadas_existem():
    texto = SKILL.read_text(encoding="utf-8")
    citadas = set(re.findall(r"references/([\w.-]+\.md)", texto))

    assert citadas, "o SKILL.md precisa apontar para references/"
    faltando = [nome for nome in citadas if not (REFERENCES / nome).exists()]
    assert faltando == []


def test_description_dispara_em_portugues():
    frente = SKILL.read_text(encoding="utf-8").split("---")[1].lower()

    for frase in ("cria os testes", "cobre com testes", "meus testes", "diagnostica"):
        assert frase in frente, f"gatilho ausente: {frase}"


def test_matriz_e_exemplos_sairam_do_skill_md():
    texto = SKILL.read_text(encoding="utf-8")

    assert "```php" not in texto and "```go" not in texto, "exemplo de linguagem mora em references/"
    assert "| PHP | PHPUnit |" not in texto, "a matriz mora em references/frameworks.md"
    assert "| PHP | PHPUnit |" in (REFERENCES / "frameworks.md").read_text(encoding="utf-8"), \
        "mover não pode virar sumir"


def test_toda_reference_e_citada_por_alguem():
    """Conteúdo movido para um arquivo que ninguém aponta é conteúdo perdido."""
    skill_texto = SKILL.read_text(encoding="utf-8")

    for arquivo in sorted(REFERENCES.glob("*.md")):
        outras = [p.read_text(encoding="utf-8") for p in REFERENCES.glob("*.md") if p != arquivo]
        assert arquivo.name in skill_texto or any(arquivo.name in t for t in outras), \
            f"{arquivo.name} não é citado por ninguém"


def test_reference_nao_aponta_para_si_mesma_nem_usa_prefixo_errado():
    for arquivo in sorted(REFERENCES.glob("*.md")):
        texto = arquivo.read_text(encoding="utf-8")
        assert f"references/{arquivo.name}" not in texto, \
            f"{arquivo.name}: link para si mesma (ou caminho com prefixo references/ dentro de references/)"
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_skill_md.py -q`
Expected: 4 falhas (o `SKILL.md` ainda tem 411+ linhas, os exemplos e a matriz).

- [x] **Step 3: Mover a matriz e os exemplos**

```bash
cd ~/.claude/skills/sw-auto-test
python3 - <<'PY'
from pathlib import Path
skill = Path("SKILL.md")
texto = skill.read_text(encoding="utf-8")

inicio = texto.index("**Framework matrix (language × test type):**")
fim = texto.index("**When two frameworks genuinely tie**")
matriz = texto[inicio:fim]

inicio_aaa = texto.index("Language examples (use the idiom of each framework):")
fim_aaa = texto.index("When AAA doesn't fit (and that's fine):")
exemplos = texto[inicio_aaa:fim_aaa]

Path("references/frameworks.md").write_text(
    "# Matriz de frameworks (linguagem × tipo de teste)\n\n" + matriz, encoding="utf-8")
Path("references/aaa-por-linguagem.md").write_text(
    "# AAA em cada linguagem\n\n" + exemplos, encoding="utf-8")

texto = texto.replace(matriz, "Veja a matriz completa em "
                      "[`references/frameworks.md`](references/frameworks.md).\n\n")
texto = texto.replace(exemplos, "Exemplos em PHP, Python, TypeScript, Go, Java e Ruby em "
                      "[`references/aaa-por-linguagem.md`](references/aaa-por-linguagem.md).\n\n")
skill.write_text(texto, encoding="utf-8")
print("linhas agora:", len(texto.splitlines()))
PY
```
Expected: imprime a contagem. **Só a matriz e os exemplos não bastam** (ficou em 391 linhas): para
chegar a 219 foi preciso mover também, com ponteiro de duas a três linhas no lugar de cada bloco —
para `references/frameworks.md`: tabela de sinal → linguagem, config por linguagem, sinais de
integração/e2e e os empates entre frameworks; para `references/generation.md`: detalhamento do AAA e
quando ele não se aplica, antipadrões, exemplos de ponta a ponta, infraestrutura de integração, local
e estilo do teste, a tabela do que muda por tipo, as três estratégias de análise, os mocks por tipo e
a pergunta do tipo de teste na íntegra.

- [x] **Step 4: `references/diagnostico.md`** — o catálogo das regras

````markdown
# Catálogo de regras do diagnóstico

Ids estáveis: é por eles que um achado do agente se liga a um fato do script.

| Id | O que é | Dimensão | Confiança |
|---|---|---|---|
| `marcado_para_pular` | `skip`, `xfail`, `only`, `@Ignore`, `markTestSkipped` | confiabilidade | alta |
| `sem_assercao_aparente` | nenhuma asserção reconhecível no corpo | confiabilidade | média |
| `nao_descoberto` | arquivo de teste que o runner não coleta | confiabilidade | alta |
| `espera_fixa` | `sleep`, `setTimeout`, `waitForTimeout` | isolamento | alta |
| `relogio_real` | data/hora real sem congelar | isolamento | média |
| `aleatorio_sem_semente` | aleatório sem semente fixa | isolamento | média |
| `rede_em_unit` | chamada de rede em suíte unitária | isolamento | alta |
| `nome_duplicado` | dois testes com o mesmo nome no arquivo | legibilidade | alta |
| `lento_para_o_tipo` | acima do limite do tipo (unit 1s, integração 10s, e2e 60s) | velocidade | alta |
| `execucao_estourou` | a suíte passou do timeout | velocidade | alta |
| `saida_ilegivel` | não deu para ler a saída do runner | — | alta |

**Confiança média nunca entra em lote automático.** Helper de asserção, matcher custom e `expect`
encadeado fazem `sem_assercao_aparente` errar — por isso ele só vira alta quando um plugin de lint
da stack apontar.

## O que o agente julga (sem sinal do script)

Asserção tautológica ou frouxa · mock do próprio sujeito · tudo mockado · asserção em detalhe
interno · nome que não descreve comportamento · teste que testa o framework · vários comportamentos
num teste · caminho crítico sem teste.
````

- [x] **Step 5: Gatilhos PT-BR na `description`**

Acrescente ao final da `description` do frontmatter, antes do fechamento:

```yaml
  Dispara também em português: "cria os testes", "escreve os testes de", "cobre com testes",
  "gera teste unitário", "meus testes estão bons?", "diagnostica os testes", "a suíte presta?",
  "revisa a bateria de testes", "que teste está faltando".
```

- [x] **Step 6: Rodar**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde, incluindo `tests/test_skill_md.py`.

- [x] **Step 7: Checkpoint do lote 4** — pausa de aprovação.

---

## Lote 5 — validação, publicação e integração

### Task 14: validação real (manual, primeiro sem executar)

Nada do projeto usado entra neste dossiê nem em commit — o marketplace é público.

- [x] **Step 1: Escolher o projeto**

Um projeto local **fora deste marketplace**, com suíte de testes de verdade, em PHP, JS/TS ou
Python. Se precisar mexer na branch, **clone para a pasta temporária** em vez de trocar a branch do
original: `git clone -q --no-local <projeto> <tmp>/validacao`.

- [x] **Step 2: Registrar o estado antes**

Run (dentro do projeto escolhido): `git status --porcelain | wc -l; git rev-parse HEAD`
Expected: anote as duas saídas.

- [x] **Step 3: Diagnóstico estático, sem executar nada**

Invoque `/sw-auto-test` pedindo o diagnóstico e escolha **só estática** quando ele perguntar.
Confira: o inventário bate com a realidade (conte os arquivos de teste na mão); os sinais apontam
linha certa; cobertura e velocidade saem `⚪ sem dados`.

- [x] **Step 4: Conferir que nada foi tocado**

Run: `git status --porcelain | wc -l; git rev-parse HEAD`
Expected: igual ao Step 2 (o `test-health-report.md` não aparece: está no `info/exclude`).

- [x] **Step 5: Diagnóstico com execução**

Rode de novo autorizando **descoberta + suíte + cobertura**. Confira: o comando mostrado antes da
confirmação é o certo; se houver banco no ambiente, ele parou e pediu confirmação; as notas de
cobertura e velocidade agora saem preenchidas; a contagem de passou/falhou bate com rodar o runner
na mão.

- [x] **Step 6: Correção guiada em um lote pequeno**

Aceite corrigir **um** achado de confiança alta. Confira que o backup foi criado, que a suíte rodou
depois, e que reverter (forçando uma quebra de propósito) devolve o arquivo ao original.

- [x] **Step 7: Anotar divergências**

Anote **no chat**, não no dossiê. Divergência de comportamento → atualize o plano com uma task de
correção antes de seguir. Apague o `test-health-report.md` gerado, se não quiser mantê-lo.

- [ ] **Step 8: Checkpoint** — pausa de aprovação.

---

### Task 15: publicar no marketplace

**Files:**
- Create (via sync): `/var/www/ai-marketplace/plugins/sw-auto-test/`
- Modify: `/var/www/ai-marketplace/CHANGELOG.md`

- [x] **Step 1: Suíte verde antes de publicar**

Run: `cd ~/.claude/skills/sw-auto-test && .venv/bin/python -m pytest -q`
Expected: todos passam.

- [x] **Step 2: Sincronizar**

Run: `cd /var/www/ai-marketplace && make sync SKILL=sw-auto-test CATEGORY=development`
Expected: `→ Sync 'sw-auto-test'  (categoria: development, versão: 0.1.0)` e nenhum `⚠`.

- [x] **Step 3: Conferir que o ambiente local não vazou**

Run: `find /var/www/ai-marketplace/plugins/sw-auto-test \( -name .venv -o -name __pycache__ -o -name .pytest_cache \) | wc -l`
Expected: `0`

- [x] **Step 4: Registrar no `CHANGELOG.md`** — em `## [Não publicado]`, primeiro item de `### Adicionado`:

```markdown
- `sw-auto-test` (v0.1.0): **publicada, com um modo novo de diagnóstico da suíte de testes**.
  Além de gerar testes, ela agora avalia os que já existem: apura os fatos com a ferramenta nativa
  da stack (pytest, vitest/jest, phpunit), o agente julga só os arquivos suspeitos, e sai um
  `test-health-report.md` com notas por dimensão (confiabilidade, isolamento, cobertura,
  legibilidade, velocidade) e achados por confiança, seguido de correção guiada em lotes. Dimensão
  sem dado fica `⚪ sem dados` em vez de estimativa, e não existe nota agregada — percentual único
  vira meta, e meta de cobertura não mede teste bom. A execução da suíte é opt-in: descoberta
  primeiro, comando à vista antes de confirmar, e parada quando há banco no ambiente de teste.
  No modo gerar entraram baseline, **prova do vermelho** (quebra o código de propósito para
  confirmar que o teste acusa, com backup e varredura de resíduo), determinismo por padrão e a
  proibição de forçar verde. Quatro restrições com teste: escrita confinada, nada executa sem
  aprovação, restauração garantida por hash e relatório determinístico.
```

- [x] **Step 5: Gate de segurança**

Run: `cd /var/www/ai-marketplace && git add plugins/sw-auto-test .claude-plugin/marketplace.json README.md CHANGELOG.md && make check`
Expected: `✓ gate de segurança: nada sensível detectado`

- [ ] **Step 6: Checkpoint com commit** — perguntar "Commitar agora?"; se sim,
`feat(sw-auto-test): …` só com os arquivos acima. **Sem push sem aprovação explícita.**

---

### Task 16: integrar as irmãs e fechar o dossiê

**Files:**
- Modify: `~/.claude/skills/sw-code-review/SKILL.md`, `~/.claude/skills/sw-plan/SKILL.md`
- Modify: `/var/www/ai-marketplace/CHANGELOG.md`

- [x] **Step 1: `sw-code-review` aponta para cá**

```bash
python3 - <<'PY'
from pathlib import Path
p = Path.home() / ".claude/skills/sw-code-review/SKILL.md"
antes = "Para gerar a mensagem do PR a partir dos commits, a `sw-pr-message`."
depois = ("Para gerar a mensagem do PR a partir dos commits, a `sw-pr-message`. Para qualidade dos "
          "**testes** (teste frouxo, desligado, instável ou faltando), a `sw-auto-test` no modo diagnóstico.")
t = p.read_text(encoding="utf-8")
assert t.count(antes) == 1, "trecho não encontrado exatamente uma vez"
p.write_text(t.replace(antes, depois), encoding="utf-8")
print("ok")
PY
```
Expected: `ok`

- [x] **Step 2: `sw-plan` oferece o diagnóstico**

```bash
python3 - <<'PY'
from pathlib import Path
p = Path.home() / ".claude/skills/sw-plan/SKILL.md"
ancora = "- **Mensagem de PR ao concluir (se for git):**"
novo = ("- **Testes ao concluir:** terminadas as tasks, se o plano criou ou alterou testes, "
        "**ofereça via `AskUserQuestion`** rodar o diagnóstico da **`sw-auto-test`** (se instalada) "
        "sobre o que foi mexido — é o que pega teste que passa sem provar nada. Só oferece.\n")
t = p.read_text(encoding="utf-8")
assert t.count(ancora) == 1 and "sw-auto-test" not in t
p.write_text(t.replace(ancora, novo + ancora), encoding="utf-8")
print("ok")
PY
```
Expected: `ok`

- [x] **Step 3: Sincronizar com bump**

```bash
cd /var/www/ai-marketplace
make sync SKILL=sw-code-review BUMP=patch
make sync SKILL=sw-plan BUMP=minor
```
Expected: `sw-code-review` em `0.1.2` e `sw-plan` em `0.5.0`, sem `⚠`.

- [x] **Step 4: `CHANGELOG.md`** — em `### Alterado`, como primeiros itens:

```markdown
- `sw-plan` (v0.5.0): ao concluir tasks que mexeram em teste, oferece o diagnóstico da `sw-auto-test`.
- `sw-code-review` (v0.1.2): passa a indicar a `sw-auto-test` para qualidade de teste.
```

- [x] **Step 5: Fechar o dossiê**

Run: `cd /var/www/ai-marketplace && python3 ~/.claude/skills/sw-brainstorming/scripts/dossie.py estado 2026-09-18-diagnostico-de-testes-na-sw-auto-test concluido`
Expected: `2026-09-18-diagnostico-de-testes-na-sw-auto-test → concluido`

- [x] **Step 6: Gate e commit final**

Run: `cd /var/www/ai-marketplace && git add plugins/sw-code-review plugins/sw-plan CHANGELOG.md docs/specs && make check`
Expected: `✓ gate de segurança: nada sensível detectado`

Checkpoint com commit (dossiê + integração). **Push só com aprovação explícita.**

- [x] **Step 7: Oferecer a `sw-pr-message`** — este plano roda no `master`, então não há branch para
descrever; registre isso no resumo final em vez de oferecer.

---

## Contagem esperada de testes por task

| Task | Arquivo | Testes |
|---|---|---|
| 0 | `test_ajudantes.py` | 5 |
| 1 | `test_gitinfo.py` + `test_pastas.py` | 11 |
| 2 | `test_backup.py` | 10 |
| 3 | `test_sinais.py` | 15 |
| 4 | `test_inventario.py` + `test_diagnose_estatico.py` | 14 |
| 5 | `test_stacks_base.py` | 6 |
| 6 | `test_stacks.py` | 11 |
| 7 | `test_diagnose_executar.py` | 15 |
| 8 | `test_restricoes.py` | 5 |
| 9 | `test_report_validar.py` | 14 |
| 10 | `test_report_montar.py` | 20 |
| 12 | `test_backup_cli.py` | 8 |
| 13 | `test_skill_md.py` | 6 |
| | **Total ao fim do lote 4** | **140** |
| | *Verificado: lote 1 → 55 · lote 2 → 92 · lote 4 → 140* | |

Se a contagem real divergir, **atualize esta tabela** — ela é o alarme de teste sumido.

## Ajustes durante a execução (o que os juízes mudaram)

| Lote | Achado | Correção |
|---|---|---|
| 1 | `sleep(` em comentário virava achado alto; `.only(` casava em texto e silenciava os outros sinais | comentário e literal de texto são mascarados antes da busca, preservando as posições; `.only(` ancorado em `it/test/describe` |
| 1 | Projeto Go, Ruby, Java, C# ou Rust sumia do inventário inteiro | `blocos` reconhece `func TestX`, `it 'x' do` e, por anotação, `@Test`/`[Fact]`/`#[test]` |
| 1 | Backup com a cópia sumida gravaria o arquivo mutado como "original"; o hash era gravado e nunca lido | `BackupSumiu`; `restaurar` devolve "intacto"/"sobrescrito" e a varredura avisa o que sobrescreveu |
| 2 | Em vitest, jest e phpunit **todo** arquivo viraria "não descoberto" | cada stack devolve os arquivos que a descoberta listou; phpunit devolve `None` e a regra não se aplica |
| 2 | `--cov` gravava `.coverage` no projeto; código de saída do runner era ignorado | `COVERAGE_FILE` aponta para a pasta de fatos e vai nos fatos; verde exige junit limpo **e** saída zero; 127 vira `runner_ausente` |
| 2 | Banco declarado no `phpunit.xml` escapava da segunda confirmação | os arquivos do phpunit entraram na varredura de ambiente |
| 3 | `regra` do agente entrava crua no markdown e criava seção/tabela; `nao_e_problema` não era conferido | `uma_linha` em `regra` e no caminho; `validar` exige regra numa linha e caminho no inventário |
| 3 | `gravar()` escrevia **através de link simbólico** | recusa com exit 2, como a `sw-pr-message` |
| 3 | Em monorepo os caminhos eram resolvidos contra o topo do repositório | `raiz_do_escopo()` passa a valer para validação, gravação e linha do `info/exclude` |
| 3 | Notas enganavam: cobertura de 3% saía verde, e timeout virava "execução não autorizada" | nota de cobertura vem do pior arquivo; velocidade separa timeout, lentos e falta de execução; cada base diz de onde veio |
| 4 | O CLI do backup aceitava `../fora.txt` e caminho absoluto | recusa o que não estiver sob a raiz |
| 4 | `varrer` não tinha chamador, e `references/diagnostico.md` ficou órfão | o `SKILL.md` abre os dois modos com a varredura e cita o catálogo de regras |
| 4 | Teste de arrumação era contornável (passava com conteúdo em arquivo que ninguém lê) | teste novo exige que toda reference seja citada por alguém e que a matriz esteja em `frameworks.md` |
