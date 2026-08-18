# sw-cluster-audit Implementation Plan

> **Execução:** Implementar este plano task-by-task. Steps usam checkbox (`- [ ]`) para tracking.
> Ver seção "Execution Handoff" da skill `sw-plan` para os 2 modos de execução disponíveis.

**Goal:** Uma skill read-only que audita um cluster Docker (context/Swarm) e gera um relatório
técnico (HTML + PDF opt-in), sem mutar nada e sem vazar segredo.

**Architecture:** `collect.py` orquestra coleta read-only (runner com allowlist `(noun,verb)` +
timeout → coletores → redator field-allowlist positivo → regras determinísticas de finding →
`report.json` schema v1). O agente prioriza/escreve prosa a partir dos findings; `build_report.py`
transforma `report.json` em HTML self-contained → PDF opt-in. Módulos de segurança isolados e
unit-testados (são as fitness functions).

**Tech Stack:** Python 3 (stdlib puro, sem deps), pytest (unit), HTML/CSS self-contained, Chromium
headless opt-in pra PDF.

**Base dir:** `~/.claude/skills/sw-cluster-audit/` (fora do git; sync pro marketplace no fim).
**Spec:** `/var/www/ai-marketplace/docs/specs/2026-08-04-sw-cluster-audit-design.md`.

---

## File Structure

```
~/.claude/skills/sw-cluster-audit/
├─ SKILL.md                         # fluxo + gates AskUserQuestion + garantias de segurança
├─ scripts/
│  ├─ collect.py                    # CLI + orquestra: runner→coletores→redação→regras→writer
│  ├─ build_report.py               # report.json → HTML (self-contained) → PDF opt-in
│  └─ lib/
│     ├─ __init__.py
│     ├─ allowlist.py               # (noun,verb) allow + deny explícito + enforcement
│     ├─ runner.py                  # subprocess args-array + timeout (usa allowlist)
│     ├─ redact.py                  # field-allowlist POSITIVA + env-keys + scrub docker info
│     ├─ rules.py                   # findings determinísticos (SEC_*/HEALTH_*)
│     └─ report.py                  # schema v1: n/a marker, montagem, parcial-válido
├─ tests/
│  ├─ __init__.py
│  ├─ conftest.py                   # sys.path pro lib
│  ├─ test_allowlist.py  test_runner.py  test_redact.py  test_rules.py
│  ├─ test_report.py     test_collect.py  test_build_report.py  test_egress.py
│  └─ fixtures/
│     ├─ inspect_container_secret.json   # container com -e DB_PASSWORD=x
│     ├─ inspect_service_secret.json     # service com command/args/Spec.Labels
│     ├─ docker_info_proxy.json          # registry-mirror http://user:pass@proxy
│     └─ report_sample.json              # report.json v1 pro build_report
├─ references/
│  ├─ commands-allowlist.md   what-to-collect.md   finding-rules.md
└─ assets/report-template/
   └─ template.html                # HTML+CSS+fontes INLINE, zero asset remoto
```

**Responsabilidades (fronteiras):** cada módulo `lib/` tem 1 responsabilidade e é testável
isolado — é o que torna as fitness functions verificáveis. `collect.py`/`build_report.py` são
só orquestração + CLI.

---

## Task 1: Skeleton + pytest

**Files:** Create `scripts/lib/__init__.py`, `tests/__init__.py`, `tests/conftest.py`.

- [ ] **Step 1: Criar diretórios e conftest**

```python
# tests/conftest.py — deixa `import lib.x` funcionar a partir de scripts/
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
```
`scripts/lib/__init__.py` e `tests/__init__.py` ficam vazios.

- [ ] **Step 2: Teste-âncora que roda**

```python
# tests/test_smoke.py
def test_pytest_runs():
    assert True
```

- [ ] **Step 3: Rodar**

Run: `cd ~/.claude/skills/sw-cluster-audit && python3 -m pytest -q`
Expected: 1 passed.

---

## Task 2: Allowlist `(noun, verb)` — FF1

**Files:** Create `scripts/lib/allowlist.py`, `tests/test_allowlist.py`.

- [ ] **Step 1: Testes que falham**

```python
# tests/test_allowlist.py
import pytest
from lib.allowlist import check, NotAllowed

def test_permite_par_read_only():
    check(["docker", "service", "inspect", "web"])      # (service,inspect) ∈ allow
    check(["docker", "context", "inspect", "prod"])     # permitido (só context)

@pytest.mark.parametrize("cmd", [
    ["docker", "config", "inspect", "c"],   # vaza valor do config
    ["docker", "container", "exec", "x"],
    ["docker", "container", "logs", "x"],
    ["docker", "service", "rm", "web"],     # mutante
    ["docker", "swarm", "join-token", "worker"],
])
def test_bloqueia_deny_e_fora_da_allowlist(cmd):
    with pytest.raises(NotAllowed):
        check(cmd)

def test_match_nos_dois_primeiros_tokens():
    # (config,ls) permitido; (config,inspect) não — mesmo noun, verbo diferente
    check(["docker", "config", "ls"])
    with pytest.raises(NotAllowed):
        check(["docker", "config", "inspect", "c"])
```

- [ ] **Step 2: Rodar (RED)** — `python3 -m pytest tests/test_allowlist.py -q` → FAIL (no module).

- [ ] **Step 3: Implementar**

```python
# scripts/lib/allowlist.py
class NotAllowed(Exception):
    pass

# Allowlist POSITIVA de pares (noun, verb). "-" = verbo ausente (comando de 1 token após docker).
ALLOW = {
    ("context", "ls"), ("context", "inspect"), ("info", "-"), ("version", "-"),
    ("node", "ls"), ("node", "inspect"), ("service", "ls"), ("service", "ps"),
    ("service", "inspect"), ("ps", "-"), ("container", "inspect"),
    ("network", "ls"), ("network", "inspect"), ("secret", "ls"),
    ("config", "ls"), ("image", "ls"),
}

def check(cmd):
    """cmd = ['docker', noun, verb?, ...]. Levanta NotAllowed se o par não estiver na allowlist."""
    if not cmd or cmd[0] != "docker" or len(cmd) < 2:
        raise NotAllowed(f"comando inesperado: {cmd!r}")
    noun = cmd[1]
    verb = cmd[2] if len(cmd) >= 3 and not cmd[2].startswith("-") else "-"
    if (noun, verb) not in ALLOW:
        raise NotAllowed(f"par não permitido: ({noun}, {verb})")
    return True
```

- [ ] **Step 4: Rodar (GREEN)** — `python3 -m pytest tests/test_allowlist.py -q` → PASS.

- [ ] **Step 5: Commit** (no checkpoint, após "sim"): `feat(sw-cluster-audit): allowlist (noun,verb) read-only`.

---

## Task 3: Runner (args-array + timeout) — FF3

**Files:** Create `scripts/lib/runner.py`, `tests/test_runner.py`.

- [ ] **Step 1: Testes que falham**

```python
# tests/test_runner.py
from unittest import mock
from lib.runner import run
from lib.allowlist import NotAllowed
import pytest

def test_chama_subprocess_com_args_array_sem_shell():
    with mock.patch("lib.runner.subprocess.run") as m:
        m.return_value = mock.Mock(stdout="{}", returncode=0)
        run(["docker", "ps", "--format", "{{json .}}"], timeout=5)
        args, kwargs = m.call_args
        assert args[0] == ["docker", "ps", "--format", "{{json .}}"]  # lista, não string
        assert kwargs.get("shell", False) is False                    # nunca shell=True

def test_nome_malicioso_nao_injeta():
    # um "nome" com ; não vira novo comando: continua sendo 1 argumento
    with mock.patch("lib.runner.subprocess.run") as m:
        m.return_value = mock.Mock(stdout="", returncode=0)
        run(["docker", "container", "inspect", "a; touch /tmp/pwned"], timeout=5)
        assert m.call_args[0][0][-1] == "a; touch /tmp/pwned"

def test_bloqueia_comando_fora_da_allowlist():
    with pytest.raises(NotAllowed):
        run(["docker", "service", "rm", "web"], timeout=5)

def test_timeout_vira_none(monkeypatch):
    import subprocess
    def boom(*a, **k): raise subprocess.TimeoutExpired(cmd="docker", timeout=1)
    monkeypatch.setattr("lib.runner.subprocess.run", boom)
    assert run(["docker", "info"], timeout=1) is None   # None = não coletado (n/a)
```

- [ ] **Step 2: Rodar (RED).**

- [ ] **Step 3: Implementar**

```python
# scripts/lib/runner.py
import subprocess
from lib.allowlist import check

def run(cmd, timeout):
    """Roda um comando docker read-only (args-array, sem shell). Valida na allowlist.
    Retorna stdout (str) ou None se estourou o timeout. NÃO captura NotAllowed — é bug de dev."""
    check(cmd)  # levanta NotAllowed antes de executar qualquer coisa
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
    except subprocess.TimeoutExpired:
        return None
    return p.stdout if p.returncode == 0 else None
```

- [ ] **Step 4: Rodar (GREEN).**  - [ ] **Step 5: Commit** `feat(sw-cluster-audit): runner seguro (args-array, timeout)`.

---

## Task 4: Redator (field-allowlist POSITIVA + env-keys + scrub) — FF2

**Files:** Create `scripts/lib/redact.py`, `tests/test_redact.py`, fixtures.

- [ ] **Step 1: Fixtures** (`tests/fixtures/`):
  - `inspect_container_secret.json`: um container com `Config.Env: ["DB_PASSWORD=supersecret","PORT=80"]`, `Config.Labels`, `Config.Image`, `Mounts`, `HostConfig.Privileged:false`, `Config.User:"root"`.
  - `inspect_service_secret.json`: service com `Spec.TaskTemplate.ContainerSpec`: `Command:["server"]`, `Args:["--token","abc123"]`, `Env:["API_KEY=zzz"]`, `Labels`, `Image`.
  - `docker_info_proxy.json`: `{"RegistryConfig":{"Mirrors":["http://user:pass@proxy:3128"]}, "ServerVersion":"25.0"}`.

- [ ] **Step 2: Testes que falham**

```python
# tests/test_redact.py
import json, pathlib
from lib.redact import redact_container, redact_service, scrub_info
FX = pathlib.Path(__file__).parent / "fixtures"

def _load(n): return json.loads((FX/n).read_text())

def test_container_env_vira_chaves_sem_valor():
    out = redact_container(_load("inspect_container_secret.json"))
    assert out["env_keys"] == ["DB_PASSWORD", "PORT"]
    assert "supersecret" not in json.dumps(out)       # valor nunca aparece
    assert "Labels" not in out and "Cmd" not in out    # descartados por default (positivo)
    assert out["image"] and out["user"] == "root"

def test_service_command_args_labels_nao_vazam():
    out = redact_service(_load("inspect_service_secret.json"))
    dumped = json.dumps(out)
    assert "abc123" not in dumped and "zzz" not in dumped   # args/env não vazam
    assert out["env_keys"] == ["API_KEY"]

def test_scrub_info_redige_cred_do_proxy():
    out = scrub_info(_load("docker_info_proxy.json"))
    assert "user:pass" not in json.dumps(out)
    assert out["server_version"] == "25.0"

def test_campo_desconhecido_e_descartado():
    out = redact_container({"Config": {"Image": "x"}, "CampoNovoDaAPI": {"secret": "y"}})
    assert "CampoNovoDaAPI" not in out and "y" not in json.dumps(out)
```

- [ ] **Step 3: Rodar (RED).**

- [ ] **Step 4: Implementar** (serialização POSITIVA — só os campos listados saem)

```python
# scripts/lib/redact.py
import re

def _env_keys(env):   # ["K=v"] -> ["K"]
    return [e.split("=", 1)[0] for e in (env or [])]

def redact_container(insp):
    c = insp.get("Config", {}) or {}
    h = insp.get("HostConfig", {}) or {}
    return {                       # <-- só estes campos existem na saída
        "image": c.get("Image"),
        "user": c.get("User") or None,
        "env_keys": _env_keys(c.get("Env")),
        "privileged": bool(h.get("Privileged", False)),
        "cap_add": h.get("CapAdd") or [],
        "mounts": [{"type": m.get("Type"), "source": m.get("Source"), "target": m.get("Destination")}
                   for m in (insp.get("Mounts") or [])],
        "ports": list((insp.get("NetworkSettings", {}) or {}).get("Ports", {}) or {}),
    }

def redact_service(insp):
    spec = (insp.get("Spec", {}) or {})
    cs = (spec.get("TaskTemplate", {}) or {}).get("ContainerSpec", {}) or {}
    ep = (spec.get("EndpointSpec", {}) or {})
    return {
        "name": spec.get("Name"),
        "image": cs.get("Image"),
        "user": cs.get("User") or None,
        "env_keys": _env_keys(cs.get("Env")),
        "privileged": bool(((cs.get("Privileges", {}) or {}).get("Privileged")) or False),
        "mounts": [{"type": m.get("Type"), "source": m.get("Source"), "target": m.get("Target")}
                   for m in (cs.get("Mounts") or [])],
        "ports": [p.get("PublishedPort") for p in (ep.get("Ports") or [])],
    }

_CRED = re.compile(r"//[^/@\s]+:[^/@\s]+@")   # http://user:pass@host -> http://***@host

def scrub_info(info):
    mirrors = ((info.get("RegistryConfig", {}) or {}).get("Mirrors")) or []
    return {
        "server_version": info.get("ServerVersion"),
        "registry_mirrors": [_CRED.sub("//***@", m) for m in mirrors],
    }
```

- [ ] **Step 5: Rodar (GREEN).**  - [ ] **Step 6: Commit** `feat(sw-cluster-audit): redação positiva/universal (env-keys, scrub)`.

---

## Task 5: Regras de finding — parte da FF (determinístico, não agente)

**Files:** Create `scripts/lib/rules.py`, `tests/test_rules.py`.

- [ ] **Step 1: Testes que falham**

```python
# tests/test_rules.py
from lib.rules import findings_for_workload

def test_detecta_privileged_latest_e_docker_sock():
    wl = {"name": "web", "image": "nginx", "tag": "latest", "digest": None,
          "privileged": True, "user": "root",
          "mounts": [{"type": "bind", "source": "/var/run/docker.sock", "target": "/x"}],
          "ports": [80]}
    ids = {f["rule_id"] for f in findings_for_workload(wl, scope="cluster-wide")}
    assert {"SEC_PRIVILEGED", "SEC_IMAGE_LATEST", "SEC_DOCKER_SOCK", "SEC_USER_ROOT"} <= ids

def test_finding_tem_severity_evidence_fix_scope():
    wl = {"name": "web", "image": "nginx", "tag": "latest", "privileged": False,
          "user": None, "mounts": [], "ports": []}
    f = [x for x in findings_for_workload(wl, scope="node-1") if x["rule_id"] == "SEC_IMAGE_LATEST"][0]
    assert f["severity"] in {"high", "med", "low"} and f["evidence"] and f["fix"] and f["scope"] == "node-1"

def test_workload_limpo_sem_findings():
    wl = {"name": "ok", "image": "app", "tag": "1.2.3", "digest": "sha256:...",
          "privileged": False, "user": "1000", "mounts": [], "ports": []}
    assert findings_for_workload(wl, scope="cluster-wide") == []
```

- [ ] **Step 2: Rodar (RED).**

- [ ] **Step 3: Implementar**

```python
# scripts/lib/rules.py
_SENSITIVE = ("/var/run/docker.sock", "/", "/etc")

def _f(rid, sev, obj, evidence, fix, scope):
    return {"rule_id": rid, "severity": sev, "object": obj, "evidence": evidence, "fix": fix, "scope": scope}

def findings_for_workload(wl, scope):
    """Regras determinísticas sobre um workload já redigido (container ou service)."""
    out, name = [], wl.get("name") or wl.get("image")
    if wl.get("privileged"):
        out.append(_f("SEC_PRIVILEGED", "high", name, "Privileged=true",
                      "remover --privileged; conceder só as capabilities necessárias", scope))
    if any(m.get("source") in _SENSITIVE for m in (wl.get("mounts") or [])):
        out.append(_f("SEC_DOCKER_SOCK", "high", name, "mount de path sensível (docker.sock/host root)",
                      "remover o mount sensível ou usar socket-proxy read-only", scope))
    if wl.get("tag") == "latest" or not wl.get("digest"):
        out.append(_f("SEC_IMAGE_LATEST", "med", name, f"imagem {wl.get('image')}:{wl.get('tag')} sem digest fixo",
                      "fixar tag imutável + digest (image@sha256:...)", scope))
    if (wl.get("user") or "").lower() == "root":
        out.append(_f("SEC_USER_ROOT", "med", name, "container roda como root",
                      "definir USER não-root na imagem/service", scope))
    return out
```

- [ ] **Step 4: Rodar (GREEN).**  - [ ] **Step 5: Commit** `feat(sw-cluster-audit): regras determinísticas de finding`.

---

## Task 6: Schema report.json v1 (n/a + parcial-válido) — FF4

**Files:** Create `scripts/lib/report.py`, `tests/test_report.py`.

- [ ] **Step 1: Testes que falham**

```python
# tests/test_report.py
from lib.report import na, new_report, is_valid

def test_na_marker():
    v = na("requer Prometheus")
    assert v == {"status": "n/a", "reason": "requer Prometheus"}

def test_parcial_e_valido():
    r = new_report(generated_at="2026-08-04T00:00:00Z", context="prod")
    r["nodes"] = na("timeout")                 # seção inteira n/a
    assert is_valid(r) and r["schema_version"] == 1

def test_report_sem_generated_at_e_invalido():
    r = new_report(generated_at=None, context="prod")
    assert not is_valid(r)
```

- [ ] **Step 2: Rodar (RED).**  - [ ] **Step 3: Implementar**

```python
# scripts/lib/report.py
SCHEMA_VERSION = 1

def na(reason): return {"status": "n/a", "reason": reason}

def new_report(generated_at, context):
    return {"schema_version": SCHEMA_VERSION, "generated_at": generated_at,
            "cluster": {"context": context}, "scope": {}, "health": {},
            "nodes": [], "services": [], "networks": [],
            "secrets": [], "configs": [], "findings": [], "not_collected": []}

def is_valid(r):
    return r.get("schema_version") == SCHEMA_VERSION and bool(r.get("generated_at")) \
        and "context" in r.get("cluster", {})
```

- [ ] **Step 4: Rodar (GREEN).**  - [ ] **Step 5: Commit** `feat(sw-cluster-audit): schema report.json v1`.

---

## Task 7: collect.py — orquestração + gate de context + .gitignore — FF5

**Files:** Create `scripts/collect.py`; add tests to `tests/test_collect.py`.

- [ ] **Step 1: Testes que falham** (com daemon **mockado** via `lib.runner.run`)

```python
# tests/test_collect.py
from unittest import mock
import collect

def test_aborta_sem_confirmacao_de_context():
    # se confirm() retorna False, NENHUM comando roda
    with mock.patch("collect.confirm_context", return_value=False), \
         mock.patch("collect.run") as m:
        rc = collect.main(["--context", "prod", "--out", "/tmp/x", "--yes-cb", "reject"])
        assert rc != 0 and m.call_count == 0

def test_gitignore_do_diretorio_antes_de_escrever(tmp_path):
    repo = tmp_path; (repo/".git").mkdir(); gi = repo/".gitignore"
    collect.ensure_gitignore(repo, "docs/infra/")
    assert "docs/infra/" in gi.read_text().splitlines()
```

- [ ] **Step 2: Rodar (RED).**

- [ ] **Step 3: Implementar** — CLI `argparse`; `confirm_context()` (no modo skill, a confirmação
  vem do AskUserQuestion — aqui é injetável pra teste); coletores por seção que chamam
  `run()` (timeout por comando), passam a saída por `redact.*`, rodam `rules.findings_for_workload`,
  e montam o `report.py`. `ensure_gitignore(repo, line)` acrescenta a **linha do diretório** se
  faltar, **antes** de escrever qualquer arquivo. Sem nenhum import de rede.

  **Seleção de context (achado do juiz — a allowlist bloqueia `docker --context ...` de propósito):**
  o `collect.py` seleciona o cluster-alvo via **variável de ambiente `DOCKER_CONTEXT`** passada ao
  `subprocess` (env=`{**os.environ, "DOCKER_CONTEXT": ctx}`), **nunca** pela flag `--context`/`-H`
  (que viram "noun" e caem no `NotAllowed`). Assim todo comando continua na forma `docker <noun> <verb>`.

  **Shape do workload (consistência com as regras da Task 5):** antes de chamar
  `rules.findings_for_workload`, o coletor monta cada workload como
  `{name, image, tag, digest, user, env_keys, privileged, mounts, ports}` — derivando `tag`/`digest`
  do `image` bruto do redator via um helper `split_image(ref)` (ex.: `nginx@sha256:..` /
  `app:1.2` → `image`, `tag`, `digest`). Assim o dict casa exatamente com o que `rules` lê
  (`wl["tag"]`, `wl["digest"]`). `split_image` vive em `lib/report.py` e tem seu próprio unit test.

  *(Cada seção do spec "Coleta" vira uma função `collect_<secao>(run)` que devolve dado já
  redigido ou `na(...)`. Ex.: `collect_nodes` → `node ls`+`node inspect` → capacidade +
  reservations_sum; `collect_services` → `service ls/ps/inspect` → réplicas/restarts + redact_service.)*

- [ ] **Step 4: Rodar (GREEN).**  - [ ] **Step 5: Commit** `feat(sw-cluster-audit): collect.py (coleta, gate de context, gitignore)`.

---

## Task 8: build_report.py + template self-contained

**Files:** Create `scripts/build_report.py`, `assets/report-template/template.html`, `tests/test_build_report.py`, `tests/fixtures/report_sample.json`.

- [ ] **Step 1: Fixture** `report_sample.json` — um report.json v1 completo (com 1 finding, 1 node,
  1 service, uma seção `n/a`, `env_keys` com `DB_PASSWORD` **sem valor**).

- [ ] **Step 2: Testes que falham**

```python
# tests/test_build_report.py
import json, pathlib, build_report
FX = pathlib.Path(__file__).parent / "fixtures"

def test_gera_html_sem_vazar_valor_de_secret(tmp_path):
    out = build_report.render_html(json.loads((FX/"report_sample.json").read_text()))
    assert "DB_PASSWORD" in out and "supersecret" not in out   # chave sim, valor não
    assert "🟢" in out or "🟡" in out or "🔴" in out            # semáforo
    assert "http://" not in out and "https://" not in out       # self-contained (sem asset remoto)

def test_degrada_sem_chromium(monkeypatch, tmp_path):
    monkeypatch.setattr(build_report, "find_chromium", lambda: None)
    res = build_report.build(json.loads((FX/"report_sample.json").read_text()), tmp_path)
    assert (tmp_path/ "relatorio.html").exists() and res["pdf"] is None   # HTML sai, PDF n/a
```

- [ ] **Step 3: Rodar (RED).**

- [ ] **Step 4: Implementar** — `render_html(report)` injeta os dados no `template.html`
  (CSS + fontes **inline**, zero `http(s)://`); `find_chromium()` procura binário; `build()`
  escreve `relatorio.html` sempre e gera `relatorio.pdf` via `chromium --headless --no-sandbox
  --disable-gpu --no-pdf-header-footer --print-to-pdf` **só se** houver Chromium (offline).

- [ ] **Step 5: Rodar (GREEN).**  - [ ] **Step 6: Commit** `feat(sw-cluster-audit): build_report + template self-contained`.

---

## Task 8.5: Análise por componente (app-aware) — ✅ implementada

**Files:** `lib/redact.py` (redact_labels), `lib/report.py` (components_analysis), `collect.py`
(detect_kind + kind/routing_labels no service), `build_report.py` (seção "Análise por componente"),
`assets/report-template/template.html` (%%COMPONENTS%%), testes correspondentes.

- `detect_kind(image)` mapeia imagem → tipo (traefik/proxy/fila/banco/cache/busca/observ/app).
- `redact_labels` extrai `traefik.*` REDIGINDO valores sensíveis (basicauth/token/…). Labels fora do prefixo: descartados.
- `collect.py` põe `kind` + `routing_labels` em cada service; `components_analysis: {}` fica pro **agente** preencher.
- `build_report.py` renderiza a seção com Tipo + roteamento (Host(...)) + a análise do agente.
- **SKILL.md (Task 10)** instrui o agente a preencher `components_analysis` por componente (Traefik/fila/DB…).

## Task 9: Fitness function de egress (estático) — FF7

**Files:** Create `tests/test_egress.py`.

- [ ] **Step 1: Teste**

```python
# tests/test_egress.py
import pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
BANNED = re.compile(r"\b(import\s+(requests|urllib|http\.client|socket)|urlopen)\b")

def test_scripts_nao_fazem_rede():
    for p in (ROOT/"scripts").rglob("*.py"):
        assert not BANNED.search(p.read_text()), f"egress em {p}"

def test_template_sem_asset_remoto():
    html = (ROOT/"assets/report-template/template.html").read_text()
    assert "http://" not in html and "https://" not in html
```

- [ ] **Step 2: Rodar** → PASS (se algum módulo importou rede, corrige antes). - [ ] **Step 3: Commit** `test(sw-cluster-audit): fitness function de egress`.

---

## Task 10: SKILL.md + references

**Files:** Create `SKILL.md`, `references/{commands-allowlist,what-to-collect,finding-rules}.md`.

- [ ] **Step 1: `SKILL.md`** — frontmatter (`name: sw-cluster-audit`, description com gatilhos:
  "analisa meu cluster", "auditar o docker context X", "relatório da infra", "saúde do cluster")
  + fluxo: (1) `docker context ls` → **AskUserQuestion** confirmando o context-alvo (identidade,
  sobretudo produção); (2) rodar `collect.py`; (3) o agente lê `report.json`, **prioriza os
  findings e escreve a prosa/recomendações** (nunca inventa finding); (4) **AskUserQuestion**
  PDF opt-in; (5) `build_report.py`; (6) garantir `docs/infra/` no `.gitignore` e informar o path.
  Seção de **Segurança** (read-only, allowlist, nunca valores de secret). Toda pergunta via AskUserQuestion.
- [ ] **Step 2: `references/`** — allowlist completa, o-que-coletar por seção, catálogo de `rule_id`.
- [ ] **Step 3: Commit** `feat(sw-cluster-audit): SKILL.md + references`.

---

## Task 11: Publicar no marketplace

**Files:** repo `/var/www/ai-marketplace`.

- [ ] **Step 1: Rodar a suíte inteira** — `cd ~/.claude/skills/sw-cluster-audit && python3 -m pytest -q` → all green.
- [ ] **Step 2: Sync** — `cd /var/www/ai-marketplace && make sync SKILL=sw-cluster-audit CATEGORY=development`.
- [ ] **Step 3: CHANGELOG** — adicionar entrada; **`make check`** (gate de segurança) tem que passar.
- [ ] **Step 4: Commit** `feat(sw-cluster-audit): publica skill de auditoria read-only de cluster (v0.1.0)`. **Sem push sem aprovação.**

---

## Verificação final (as 7 fitness functions do spec)
1. allowlist rejeita par fora dela (Task 2) · 2. zero valor de secret/env/config (Task 4) ·
3. sem shell injection (Task 3) · 4. degrada sem quebrar (Tasks 6, 8) · 5. gate de context
obrigatório (Task 7) · 6. `.gitignore` do diretório antes de escrever (Task 7) ·
7. zero egress em scripts+template (Task 9).
