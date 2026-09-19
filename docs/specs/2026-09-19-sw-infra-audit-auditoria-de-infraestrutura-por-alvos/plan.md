# sw-infra-audit — Plano 1 (o eixo)

> **Execucao:** Implementar este plano task-by-task. Steps usam checkbox (`- [ ]`) para tracking. Ver secao "Execution Handoff" da skill `sw-plan` para os 2 modos de execucao disponiveis.

**Goal:** trocar o eixo da auditoria de "um cluster" para "vários alvos" — configuração em três camadas, gate de confirmação por alvo, relatório v2 com inventário e aceites, coletores docker e HTTP — e publicar a `sw-infra-audit` no lugar da `sw-cluster-audit`.

**Architecture:** a skill nova nasce de uma cópia da atual, preservando runner, redator, regras de docker, métricas, enriquecimento e template. Por cima entram três módulos novos (`config`, `alvos`, `aceites`), o `collect.py` vira orquestrador de alvos, e o `report.json` passa a ter o alvo no centro.

**Tech Stack:** Python 3 (stdlib; `tomllib` para ler TOML) · pytest · docker CLI · o ponto de rede único que já existe.

Spec: [spec.md](spec.md) — este é o **Plano 1**; o coletor de banco é o Plano 2 e está **fora** daqui.

---

## Como executar este plano

- **Onde:** a skill nasce em `~/.claude/skills/sw-infra-audit/` (fora do git). O marketplace
  `/var/www/ai-marketplace` recebe só a publicação, no **master**, com commit a cada checkpoint.
- **Suíte:** `cd ~/.claude/skills/sw-infra-audit && .venv/bin/python -m pytest -q`
- **Tipos de teste:** só **unit**. As restrições verificáveis são provadas chamando `main()` **no
  mesmo processo**, com docker falso pelo runner e servidor HTTP local — sem infraestrutura, sem rede.
- **Segurança (repositório público):** nenhum host, IP, usuário ou nome de projeto real entra no
  dossiê nem nos commits. `make check` antes de todo commit.

## Lotes

| Lote | Tasks | Entrega |
|---|---|---|
| 1 | 0–3 | Skill nova a partir da atual, configuração em três camadas, alvos validados, `config --explicar` |
| 2 | 4–5 | `collect.py` como orquestrador com gate `--confirmar`, e o `report.json` v2 |
| 3 | 6–8 | Coletor docker (com métricas vindo do alvo), coletor HTTP e aceites |
| 4 | 9–11 | Histórico por alvo, relatório HTML v2 e as 4 restrições verificáveis |
| 5 | 12–14 | Modo configurar, `SKILL.md`, validação real e publicação |

## O que vem da skill atual, e como

| Arquivo | Destino no plano 1 |
|---|---|
| `lib/runner.py` | **Passa a ser o único ponto de subprocesso**; ganha allowlist por tipo de alvo |
| `lib/allowlist.py` | Vira a allowlist do coletor docker (`coletores/docker_allowlist.py`) |
| `lib/redact.py`, `rules.py`, `rule_meta.py`, `enrich.py`, `stacks.py`, `impact.py`, `metrics.py`, `cert.py` | Copiados como estão; passam a operar **dentro de um alvo docker** |
| `lib/http_get.py` | Base do coletor HTTP, com a allowlist de host vinda dos alvos confirmados |
| `lib/discover.py` | Vira **sugestão** de `metricas_url` no modo configurar; não alcança host sozinho |
| `lib/report.py` | Reescrito para o schema v2 |
| `scripts/collect.py` | Reescrito como orquestrador; o `assemble_report` atual vira o coletor docker |
| `scripts/build_report.py` | Adaptado para v2 (inventário primeiro, detalhe por alvo) |
| `tests/` | Vêm junto e continuam passando — é o baseline da Task 0 |

## Estrutura de arquivos ao fim do plano 1

```
~/.claude/skills/sw-infra-audit/
  SKILL.md
  default.toml                  padrões da skill (caminhos, tempos, ignore, orçamento)
  references/                   herdadas da skill atual + alvos.md (como declarar cada tipo)
  scripts/
    collect.py                  modo auditar: confirmar → coletar → regras → aceites → report.json
    configurar.py               modo configurar: migrar · alvos · aceitar · config --explicar
    build_report.py             report.json v2 → relatorio.html (+ .pdf)
    lib/
      config.py                 três camadas, precedência e origem de cada chave
      alvos.py                  leitura e validação do alvos.toml
      aceites.py                casamento, origem e expiração
      falhas.py                 FalhaDeColeta — falha esperada × bug do coletor
      runner.py                 único ponto de subprocesso
      report.py                 schema v2
      coletores/docker.py       o assemble_report de hoje, agora por alvo
      coletores/http.py         GET + validade de certificado
      (redact, rules, rule_meta, enrich, stacks, impact, metrics, cert, http_get, discover)
  tests/
```

---

### Task 0: A skill nova nasce da atual, com a suíte verde

**Files:**
- Create: `~/.claude/skills/sw-infra-audit/` (cópia de `sw-cluster-audit`)

- [x] **Step 1: Copiar sem lixo e criar o venv**

```bash
cd ~/.claude/skills
rsync -a --exclude .venv --exclude .pytest_cache --exclude .ruff_cache --exclude __pycache__ \
  sw-cluster-audit/ sw-infra-audit/
cd sw-infra-audit
python3 -m venv .venv && .venv/bin/pip -q install pytest
.venv/bin/python -m pytest -q -p no:cacheprovider | tail -2
```
Expected: a suíte herdada passa inteira. **Anote o número** — é o baseline; nenhuma task deste
plano pode reduzi-lo sem uma linha dizendo por quê.

- [x] **Step 2: Confirmar que a cópia não trouxe caminho da skill antiga**

Run: `grep -rn "sw-cluster-audit" --include="*.py" --include="*.md" . | grep -v "^./tests/fixtures" | head`
Expected: só menções em texto (`SKILL.md`, comentários). Nenhum import ou caminho de arquivo.

- [x] **Step 3: Marcar a origem no topo do `SKILL.md`** (uma linha, provisória — o `SKILL.md` é reescrito na Task 13)

```markdown
> Esta skill substitui a `sw-cluster-audit`: mesma auditoria read-only, agora por **alvos**.
```

- [x] **Step 4: Checkpoint** — pausa de aprovação.

---

### Task 1: `lib/config.py` — três camadas, precedência e origem

**Files:**
- Create: `~/.claude/skills/sw-infra-audit/default.toml`, `scripts/lib/config.py`
- Test: `tests/test_config.py`

A regra mais importante do spec mora aqui: **chave de conexão na camada do projeto é erro**.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_config.py
import pytest

from lib.config import ConfigInvalida, carregar

DEFAULT = """
[relatorio]
pasta = "docs/infra"
ignorar_em = "gitignore"

[limites]
timeout_por_comando = 20
orcamento_por_alvo = 120
"""

PROJETO_OK = """
alvos = ["cluster", "site"]

[relatorio]
pasta = "docs/auditoria"

[[aceite]]
alvo = "cluster"
regra = "sem_replica"
motivo = "base de cache"
desde = "2026-09-19"
revisar_em = "2027-03-19"
"""


def escrever(tmp_path, nome, texto):
    caminho = tmp_path / nome
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def test_projeto_sobrescreve_o_default_e_a_origem_fica_registrada(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", PROJETO_OK)

    cfg = carregar(padrao=padrao, infra=None, projeto=projeto)

    assert cfg.valor("relatorio.pasta") == "docs/auditoria"
    assert cfg.origem("relatorio.pasta") == "projeto"
    assert cfg.valor("limites.timeout_por_comando") == 20
    assert cfg.origem("limites.timeout_por_comando") == "default"


def test_arquivos_ausentes_caem_no_default(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)

    cfg = carregar(padrao=padrao, infra=tmp_path / "nao-existe.toml",
                   projeto=tmp_path / "tambem-nao.toml")

    assert cfg.valor("relatorio.pasta") == "docs/infra"
    assert cfg.alvos_escolhidos() == []


def test_chave_de_conexao_no_arquivo_do_projeto_e_erro(tmp_path):
    """O arquivo do projeto é versionado: se ele pudesse definir host, um clone redirecionaria
    a conexão e a credencial para o servidor de quem mandou o arquivo."""
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml",
                       '[[alvo]]\nnome = "banco"\nhost = "exemplo.invalido"\n')

    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=padrao, infra=None, projeto=projeto)

    assert "host" in str(erro.value) and ".sw-infra-audit.toml" in str(erro.value)


@pytest.mark.parametrize("chave", ["host", "porta", "usuario", "senha_env", "tipo", "metricas_url"])
def test_toda_chave_de_conexao_e_recusada_no_projeto(tmp_path, chave):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", f'[[alvo]]\nnome = "x"\n{chave} = "y"\n')

    with pytest.raises(ConfigInvalida):
        carregar(padrao=padrao, infra=None, projeto=projeto)


def test_aceites_das_duas_camadas_vem_com_a_origem(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    infra = escrever(tmp_path, "alvos.toml",
                     '[[aceite]]\nalvo = "cluster"\nregra = "spof"\nmotivo = "failover manual"\n'
                     'desde = "2026-01-01"\nrevisar_em = "2027-01-01"\n')
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", PROJETO_OK)

    cfg = carregar(padrao=padrao, infra=infra, projeto=projeto)
    origens = {(a["regra"], a["origem"]) for a in cfg.aceites()}

    assert origens == {("spof", "infra"), ("sem_replica", "projeto")}


def test_explicar_lista_chave_valor_e_origem(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", PROJETO_OK)

    linhas = carregar(padrao=padrao, infra=None, projeto=projeto).explicar()

    assert ("relatorio.pasta", "docs/auditoria", "projeto") in linhas
    assert ("limites.orcamento_por_alvo", 120, "default") in linhas
    assert linhas == sorted(linhas), "ordem estável: é saída que o usuário vai comparar"


def test_toml_quebrado_vira_erro_com_o_nome_do_arquivo(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", "isto [ não é toml")

    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=padrao, infra=None, projeto=projeto)

    assert ".sw-infra-audit.toml" in str(erro.value)


@pytest.mark.parametrize("texto", [
    '[alvo.banco]\nhost = "exemplo.invalido"\n',          # tabela aninhada em vez de [[alvo]]
    'host = "exemplo.invalido"\n',                          # chave solta no topo
    '[targets]\nhost = "exemplo.invalido"\n',              # tabela com outro nome
    '[relatorio]\nHOST = "exemplo.invalido"\n',            # caixa diferente
    '[[alvo]]\nnome = "x"\nsenha_env = "SEGREDO"\n',      # o caso que já era pego
])
def test_nenhum_caminho_do_arquivo_do_projeto_entrega_conexao(tmp_path, texto):
    """O arquivo do projeto é versionado: qualquer jeito de declarar conexão nele é erro."""
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", texto)

    with pytest.raises(ConfigInvalida):
        carregar(padrao=padrao, infra=None, projeto=projeto)


def test_o_projeto_so_pode_definir_o_que_esta_na_lista(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", '[limites]\ntimeout_por_comando = 999\n')

    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=padrao, infra=None, projeto=projeto)

    assert "limites" in str(erro.value) and "alvos" in str(erro.value)


def test_alvos_precisa_ser_lista_de_nomes(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml",
                       'alvos = [{nome = "x", host = "exemplo.invalido"}]\n')

    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=padrao, infra=None, projeto=projeto)

    assert "alvos" in str(erro.value)


@pytest.mark.parametrize("pasta", ["/etc/sw", "../fora", "docs/../../fora"])
def test_pasta_do_relatorio_precisa_ser_relativa_e_dentro_do_projeto(tmp_path, pasta):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", f'[relatorio]\npasta = "{pasta}"\n')

    with pytest.raises(ConfigInvalida):
        carregar(padrao=padrao, infra=None, projeto=projeto)


def test_lista_legitima_aparece_no_efetivo_e_no_explicar(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", 'alvos = ["cluster", "site"]\n')

    cfg = carregar(padrao=padrao, infra=None, projeto=projeto)

    assert cfg.valor("alvos") == ["cluster", "site"]
    assert ("alvos", ["cluster", "site"], "projeto") in cfg.explicar()
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: `ImportError: cannot import name 'carregar' from 'lib.config'` — 8 falhas.

- [x] **Step 3: `default.toml`**

```toml
# Padrões da sw-infra-audit. Não edite este arquivo: o que você quer diferente vai no
# ~/.config/sw-infra-audit/alvos.toml (infra) ou no .sw-infra-audit.toml do projeto.
# Serve também de documentação: tudo que dá para ajustar está aqui, com o valor de fábrica.

[relatorio]
pasta = "docs/infra"          # onde o relatório é gravado, dentro do projeto
ignorar_em = "gitignore"      # "gitignore" (vale para o time) ou "exclude" (só sua máquina)
formato = "html"              # "html" ou "html+pdf"

[limites]
timeout_por_comando = 20      # segundos por comando de coleta
orcamento_por_alvo = 120      # segundos por alvo; o que passar disso vira "sem dados"
http_timeout = 8              # segundos por requisição do coletor http

[historico]
comparar_com_anterior = true  # diff contra a execução anterior de schema 2
```

- [x] **Step 4: `scripts/lib/config.py`**

```python
"""As três camadas de configuração: default (skill) < infra (sua máquina) < projeto (versionado).

A camada do projeto é versionada e chega por clone ou pull request. Ela tem uma **lista positiva**
do que pode definir — qualquer outra coisa é erro. Lista de proibidos não serve aqui: basta um
jeito novo de escrever a mesma coisa (`[alvo.x]`, chave no topo, tabela com outro nome) para o
arquivo voltar a entregar conexão.
"""
import tomllib
from pathlib import PurePosixPath, Path

# o que o arquivo do projeto pode definir — nada além disto
PROJETO_PERMITE = ("alvos", "aceite", "relatorio", "severidade")
RELATORIO_PERMITE = ("pasta", "formato", "ignorar_em")
# defesa em profundidade: nenhum nome de conexão, em qualquer profundidade
CHAVES_DE_CONEXAO = ("tipo", "host", "porta", "usuario", "senha", "senha_env", "metricas_url",
                     "context", "url", "password", "token")


class ConfigInvalida(Exception):
    """Configuração que a skill se recusa a interpretar."""


def _ler(caminho):
    if caminho is None:
        return {}
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    try:
        with caminho.open("rb") as arquivo:
            return tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise ConfigInvalida(f"{caminho.name}: TOML inválido — {erro}") from erro
    except OSError as erro:
        raise ConfigInvalida(f"{caminho.name}: não consegui ler — {erro}") from erro


def _achatar(dados, prefixo=""):
    """{'a': {'b': 1}} -> {'a.b': 1}.

    Lista de tabelas (`[[alvo]]`, `[[aceite]]`) fica de fora: tem tratamento próprio. Lista de
    valores entra — senão `alvos = [...]` sumiria do efetivo e do `--explicar` sem uma palavra.
    """
    saida = {}
    for chave, valor in dados.items():
        nome = f"{prefixo}{chave}"
        if isinstance(valor, dict):
            saida.update(_achatar(valor, f"{nome}."))
        elif isinstance(valor, list) and valor and all(isinstance(i, dict) for i in valor):
            continue
        else:
            saida[nome] = valor
    return saida


def _validar_projeto(dados, nome_arquivo):
    """O arquivo versionado do projeto: só o que está na lista positiva, e nunca conexão."""
    for chave in dados:
        if chave not in PROJETO_PERMITE:
            raise ConfigInvalida(
                f"{nome_arquivo}: o arquivo do projeto não define {chave!r}. Aqui entram apenas "
                f"{', '.join(PROJETO_PERMITE)} — conexão (host, porta, usuário, credencial) mora "
                f"no alvos.toml da sua máquina, fora do repositório.")

    for chave in _achatar(dados):
        folha = chave.split(".")[-1].casefold()
        if folha in CHAVES_DE_CONEXAO:
            raise ConfigInvalida(
                f"{nome_arquivo}: a chave {chave!r} descreve conexão, e o arquivo do projeto é "
                f"versionado. Declare o alvo no alvos.toml da sua máquina.")

    alvos = dados.get("alvos", [])
    if not isinstance(alvos, list) or not all(isinstance(n, str) for n in alvos):
        raise ConfigInvalida(f"{nome_arquivo}: `alvos` precisa ser uma lista de NOMES de alvos "
                             f"declarados no alvos.toml, por exemplo alvos = [\"cluster\"].")

    relatorio = dados.get("relatorio", {})
    if not isinstance(relatorio, dict):
        raise ConfigInvalida(f"{nome_arquivo}: `relatorio` precisa ser uma tabela")
    for chave in relatorio:
        if chave not in RELATORIO_PERMITE:
            raise ConfigInvalida(f"{nome_arquivo}: relatorio.{chave} não existe; disponíveis: "
                                 f"{', '.join(RELATORIO_PERMITE)}")
    pasta = relatorio.get("pasta")
    if pasta is not None:
        caminho = PurePosixPath(str(pasta))
        if caminho.is_absolute() or ".." in caminho.parts:
            raise ConfigInvalida(f"{nome_arquivo}: relatorio.pasta precisa ser relativa e dentro do "
                                 f"projeto — {pasta!r} não é.")


class Config:
    def __init__(self, camadas, alvos_escolhidos, aceites):
        self._valores, self._origens = {}, {}
        for origem, dados in camadas:                  # ordem: default, infra, projeto
            for chave, valor in _achatar(dados).items():
                self._valores[chave] = valor
                self._origens[chave] = origem
        self._alvos = alvos_escolhidos
        self._aceites = aceites

    def valor(self, chave):
        return self._valores.get(chave)

    def origem(self, chave):
        return self._origens.get(chave)

    def alvos_escolhidos(self):
        return list(self._alvos)

    def aceites(self):
        return list(self._aceites)

    def explicar(self):
        """[(chave, valor, origem)] em ordem estável — saída que o usuário compara entre rodadas."""
        return sorted(((chave, self._valores[chave], self._origens[chave])
                       for chave in self._valores), key=lambda linha: linha[0])


def carregar(padrao, infra, projeto):
    dados_padrao, dados_infra, dados_projeto = _ler(padrao), _ler(infra), _ler(projeto)
    _validar_projeto(dados_projeto, Path(projeto).name if projeto else ".sw-infra-audit.toml")

    aceites = [dict(a, origem="infra") for a in dados_infra.get("aceite", [])]
    aceites += [dict(a, origem="projeto") for a in dados_projeto.get("aceite", [])]

    return Config(
        camadas=[("default", dados_padrao), ("infra", dados_infra), ("projeto", dados_projeto)],
        alvos_escolhidos=dados_projeto.get("alvos", []),
        aceites=aceites)
```

- [x] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: `8 passed`

---

### Task 2: `lib/alvos.py` — ler e validar os alvos

**Files:**
- Create: `scripts/lib/alvos.py`
- Test: `tests/test_alvos.py`

- [x] **Step 1: Escrever os testes**

```python
# tests/test_alvos.py
import os
import stat

import pytest

from lib.alvos import AlvoInvalido, ler, selecionar

ALVOS = """
[[alvo]]
nome = "cluster"
tipo = "docker"
context = "meu-context"
metricas_url = "http://127.0.0.1:9090"

[[alvo]]
nome = "site"
tipo = "http"
url = "https://exemplo.invalido/health"
"""


def escrever(tmp_path, texto, modo=0o600):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(modo)
    return caminho


def test_le_os_alvos_com_tipo_e_campos(tmp_path):
    lidos, avisos = ler(escrever(tmp_path, ALVOS))

    assert [(a["nome"], a["tipo"]) for a in lidos] == [("cluster", "docker"), ("site", "http")]
    assert lidos[0]["metricas_url"] == "http://127.0.0.1:9090"
    assert avisos == []


def test_alvo_sem_campo_obrigatorio_e_recusado_dizendo_qual(tmp_path):
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "site"\ntipo = "http"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "site" in str(erro.value) and "url" in str(erro.value)


def test_tipo_desconhecido_diz_quais_existem(tmp_path):
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "banco"\ntipo = "oracle"\nhost = "x"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "oracle" in str(erro.value) and "docker" in str(erro.value)


def test_nome_repetido_e_recusado(tmp_path):
    caminho = escrever(tmp_path, ALVOS + '\n[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://a.invalido"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "site" in str(erro.value)


def test_arquivo_legivel_por_outros_vira_aviso(tmp_path):
    caminho = escrever(tmp_path, ALVOS, modo=0o644)

    _, avisos = ler(caminho)

    assert any("permiss" in a for a in avisos)
    assert oct(stat.S_IMODE(os.stat(caminho).st_mode)) == "0o644", "a skill avisa, não conserta sozinha"


def test_arquivo_ausente_devolve_vazio_sem_explodir(tmp_path):
    lidos, avisos = ler(tmp_path / "nao-existe.toml")

    assert lidos == []
    assert any("não encontrei" in a for a in avisos)


def test_selecionar_respeita_a_ordem_declarada_no_projeto(tmp_path):
    lidos, _ = ler(escrever(tmp_path, ALVOS))

    assert [a["nome"] for a in selecionar(lidos, ["site", "cluster"])] == ["site", "cluster"]


def test_selecionar_sem_lista_devolve_todos(tmp_path):
    lidos, _ = ler(escrever(tmp_path, ALVOS))

    assert len(selecionar(lidos, [])) == 2


def test_nome_escolhido_que_nao_existe_e_recusado(tmp_path):
    lidos, _ = ler(escrever(tmp_path, ALVOS))

    with pytest.raises(AlvoInvalido) as erro:
        selecionar(lidos, ["fantasma"])

    assert "fantasma" in str(erro.value)


def test_tabela_aninhada_em_vez_de_lista_vira_erro_claro(tmp_path):
    caminho = escrever(tmp_path, '[alvo.cluster]\ntipo = "docker"\ncontext = "ctx"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "[[alvo]]" in str(erro.value)


def test_campo_desconhecido_no_alvo_e_recusado(tmp_path):
    """`metrica_url` (sem o s) passaria mudo e o usuário nunca saberia por que não funcionou."""
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "ctx"\n'
                                 'metrica_url = "http://127.0.0.1:9090"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "metrica_url" in str(erro.value)


def test_senha_dentro_do_alvo_e_recusada(tmp_path):
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "ctx"\n'
                                 'senha = "nao-faca-isso"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "senha" in str(erro.value)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "exemplo.invalido/x"])
def test_url_precisa_ser_http_ou_https_com_host(tmp_path, url):
    caminho = escrever(tmp_path, f'[[alvo]]\nnome = "s"\ntipo = "http"\nurl = "{url}"\n')

    with pytest.raises(AlvoInvalido):
        ler(caminho)


def test_nome_de_alvo_nao_pode_virar_caminho(tmp_path):
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "../../etc/x"\ntipo = "docker"\ncontext = "c"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "nome" in str(erro.value)
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_alvos.py -q`
Expected: `ImportError: cannot import name 'ler' from 'lib.alvos'` — 9 falhas.

- [x] **Step 3: `scripts/lib/alvos.py`**

```python
"""Leitura e validação do alvos.toml — o arquivo que fica FORA do repositório.

Validação apertada de propósito: campo com erro de digitação (`metrica_url`) que passasse mudo
viraria "a skill não coleta métricas e não diz por quê". Tipo que o plano 1 ainda não implementa
é recusado aqui, com mensagem clara, em vez de chegar quebrado no coletor.
"""
import os
import re
import stat
import tomllib
from pathlib import Path
from urllib.parse import urlparse

OBRIGATORIOS = {
    "docker": ("context",),
    "http": ("url",),
}
OPCIONAIS = {
    "docker": ("metricas_url",),
    "http": (),
}
COMUNS = ("nome", "tipo")
NOME_VALIDO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ESQUEMAS = ("http", "https")


class AlvoInvalido(Exception):
    """Alvo que a skill se recusa a usar."""


def _checar_url(nome, campo, valor):
    partes = urlparse(str(valor))
    if partes.scheme not in ESQUEMAS or not partes.hostname:
        raise AlvoInvalido(f"alvo {nome!r}: {campo} precisa ser http(s) com host — {valor!r} não é")


def ler(caminho):
    """Devolve (alvos, avisos). Arquivo ausente não é erro: é projeto ainda sem configurar."""
    caminho = Path(caminho)
    avisos = []
    if not caminho.exists():
        return [], [f"não encontrei {caminho} — rode `configurar.py migrar` para criar o primeiro"]

    modo = stat.S_IMODE(os.stat(caminho).st_mode)
    if modo & 0o077:
        avisos.append(f"permissão {oct(modo)} em {caminho.name}: outros usuários da máquina leem "
                      f"seus alvos. O recomendado é 600")

    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise AlvoInvalido(f"{caminho.name}: TOML inválido — {erro}") from erro
    except OSError as erro:
        raise AlvoInvalido(f"{caminho.name}: não consegui ler — {erro}") from erro

    brutos = dados.get("alvo", [])
    if not isinstance(brutos, list) or not all(isinstance(a, dict) for a in brutos):
        raise AlvoInvalido(f"{caminho.name}: cada alvo é um bloco [[alvo]] (lista de tabelas); "
                           f"[alvo.nome] não funciona")

    alvos, vistos = [], set()
    for bruto in brutos:
        nome = bruto.get("nome")
        if not isinstance(nome, str) or not NOME_VALIDO.match(nome):
            raise AlvoInvalido(f"{caminho.name}: nome de alvo inválido: {nome!r} — use letras, "
                               f"números, ponto, hífen ou sublinhado (o nome vira pasta e chave "
                               f"de histórico)")
        if nome.casefold() in vistos:
            raise AlvoInvalido(f"{caminho.name}: o alvo {nome!r} aparece duas vezes")
        vistos.add(nome.casefold())

        tipo = bruto.get("tipo")
        if tipo not in OBRIGATORIOS:
            extra = " (banco chega no plano 2)" if tipo in ("postgres", "mysql", "mariadb") else ""
            raise AlvoInvalido(f"{caminho.name}: alvo {nome!r} tem tipo {tipo!r}; os tipos desta "
                               f"versão são {', '.join(sorted(OBRIGATORIOS))}{extra}")

        permitidos = set(COMUNS) | set(OBRIGATORIOS[tipo]) | set(OPCIONAIS[tipo])
        desconhecidos = sorted(set(bruto) - permitidos)
        if desconhecidos:
            raise AlvoInvalido(f"{caminho.name}: alvo {nome!r} ({tipo}) tem campo que não existe: "
                               f"{', '.join(desconhecidos)}. Permitidos: {', '.join(sorted(permitidos))}")

        faltando = [campo for campo in OBRIGATORIOS[tipo] if not bruto.get(campo)]
        if faltando:
            raise AlvoInvalido(f"{caminho.name}: alvo {nome!r} ({tipo}) sem {', '.join(faltando)}")

        for campo in ("url", "metricas_url"):
            if bruto.get(campo):
                _checar_url(nome, campo, bruto[campo])

        alvos.append(dict(bruto))
    return alvos, avisos


def selecionar(alvos, escolhidos):
    """Filtra pelos nomes do arquivo do projeto, **na ordem em que ele declarou**.

    Lista vazia = todos. Nome inexistente é erro: silenciar viraria auditoria incompleta sem aviso.
    """
    if not escolhidos:
        return list(alvos)
    por_nome = {a["nome"]: a for a in alvos}
    faltando = [nome for nome in escolhidos if nome not in por_nome]
    if faltando:
        raise AlvoInvalido(f"alvo(s) {', '.join(faltando)} não existem no alvos.toml")
    return [por_nome[nome] for nome in escolhidos]
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_alvos.py -q`
Expected: `9 passed`

---

### Task 3: `configurar.py` e o `config --explicar`

**Files:**
- Create: `scripts/configurar.py`
- Test: `tests/test_configurar.py`

Este é o script do **modo configurar** — o único que escreve fora do relatório. Nesta task ele
só ganha o `config --explicar`; `migrar` e `aceitar` entram na Task 12.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_configurar.py
import configurar


def preparar(tmp_path, projeto_texto='alvos = ["cluster"]\n[relatorio]\npasta = "docs/auditoria"\n'):
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n'
                                           '[limites]\ntimeout_por_comando = 20\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text('[[alvo]]\nnome = "cluster"\ntipo = "docker"\n'
                                         'context = "ctx"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text(projeto_texto, encoding="utf-8")
    return ["--padrao", str(tmp_path / "default.toml"),
            "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml")]


def test_explicar_mostra_valor_e_origem_de_cada_chave(tmp_path, capsys):
    codigo = configurar.main(["config", "--explicar", *preparar(tmp_path)])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "relatorio.pasta" in saida and "docs/auditoria" in saida and "projeto" in saida
    assert "limites.timeout_por_comando" in saida and "default" in saida


def test_explicar_lista_os_alvos_e_de_onde_vieram(tmp_path, capsys):
    configurar.main(["config", "--explicar", *preparar(tmp_path)])
    saida = capsys.readouterr().out

    assert "cluster" in saida and "docker" in saida


def test_chave_de_conexao_no_projeto_sai_com_dois_e_explica(tmp_path, capsys):
    args = preparar(tmp_path, projeto_texto='[[alvo]]\nnome = "x"\nhost = "exemplo.invalido"\n')

    codigo = configurar.main(["config", "--explicar", *args])

    assert codigo == 2
    assert "host" in capsys.readouterr().err


def test_saida_e_estavel_entre_execucoes(tmp_path, capsys):
    args = preparar(tmp_path)
    configurar.main(["config", "--explicar", *args])
    primeira = capsys.readouterr().out
    configurar.main(["config", "--explicar", *args])

    assert capsys.readouterr().out == primeira


def test_explicar_nao_imprime_valor_que_parece_segredo(tmp_path, capsys):
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "ctx"\n\n'
        '[pg]\npassword = "nao-pode-vazar"\ntoken = "nem-isso"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["c"]\n', encoding="utf-8")

    configurar.main(["config", "--explicar",
                     "--padrao", str(tmp_path / "default.toml"),
                     "--infra", str(tmp_path / "alvos.toml"),
                     "--projeto", str(tmp_path / ".sw-infra-audit.toml")])
    saida = capsys.readouterr().out

    assert "nao-pode-vazar" not in saida and "nem-isso" not in saida
    assert "pg.password" in saida and "***" in saida
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_configurar.py -q`
Expected: `ModuleNotFoundError: No module named 'configurar'` — 4 falhas.

- [x] **Step 3: `scripts/configurar.py`**

```python
#!/usr/bin/env python3
"""Modo configurar: o único que escreve fora da pasta do relatório.

Nesta versão: `config --explicar`. `migrar` e `aceitar` entram na Task 12.
"""
import argparse
import re
import sys
from pathlib import Path

from lib import alvos as alvos_mod
from lib.config import ConfigInvalida, carregar

EXIT_OK, EXIT_ERRO = 0, 2

# o alvos.toml não deveria ter segredo, mas se alguém colar um, não é aqui que ele vaza
PARECE_SEGREDO = re.compile(r"senha|password|token|secret|pass|key|credential", re.IGNORECASE)

PADRAO_DA_SKILL = Path(__file__).resolve().parent.parent / "default.toml"
INFRA_PADRAO = Path.home() / ".config" / "sw-infra-audit" / "alvos.toml"
PROJETO_PADRAO = Path(".sw-infra-audit.toml")


def _caminhos(args):
    return (Path(args.padrao) if args.padrao else PADRAO_DA_SKILL,
            Path(args.infra) if args.infra else INFRA_PADRAO,
            Path(args.projeto) if args.projeto else PROJETO_PADRAO)


def explicar(args) -> int:
    padrao, infra, projeto = _caminhos(args)
    try:
        cfg = carregar(padrao=padrao, infra=infra, projeto=projeto)
        declarados, avisos = alvos_mod.ler(infra)
    except (ConfigInvalida, alvos_mod.AlvoInvalido) as erro:
        print(str(erro), file=sys.stderr)
        return EXIT_ERRO

    print(f"padrão:  {padrao}\ninfra:   {infra}\nprojeto: {projeto}\n")
    print("chave                                valor                origem")
    for chave, valor, origem in cfg.explicar():
        mostrado = "***" if PARECE_SEGREDO.search(chave) else str(valor)
        print(f"{chave:<36} {mostrado:<20} {origem}")
    escolhidos = cfg.alvos_escolhidos()
    print("\nalvos declarados na infra:")
    for alvo in declarados:
        marca = "•" if not escolhidos or alvo["nome"] in escolhidos else " "
        print(f" {marca} {alvo['nome']:<24} {alvo['tipo']}")
    if escolhidos:
        print(f"\nescolhidos por este projeto: {', '.join(escolhidos)}")
    for aceite in cfg.aceites():
        print(f"aceite ({aceite['origem']}): {aceite.get('alvo')} · {aceite.get('regra')} · "
              f"revisar em {aceite.get('revisar_em')}")
    for aviso in avisos:
        print(f"aviso: {aviso}")
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Configuração da sw-infra-audit.")
    sub = ap.add_subparsers(dest="comando", required=True)
    cfg = sub.add_parser("config", help="inspecionar a configuração efetiva")
    cfg.add_argument("--explicar", action="store_true", required=True)
    for parser in (cfg,):
        parser.add_argument("--padrao", default=None)
        parser.add_argument("--infra", default=None)
        parser.add_argument("--projeto", default=None)
    args = ap.parse_args(argv)
    return explicar(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest -q`
Expected: baseline da Task 0 + 21 testes novos (8 config + 9 alvos + 4 configurar).

- [x] **Step 5: Ver na prática**

Run: `.venv/bin/python scripts/configurar.py config --explicar`
Expected: imprime os padrões da skill e avisa que não encontrou o `alvos.toml` — que é o estado
esperado antes do `migrar`.

- [x] **Step 6: Checkpoint do lote 1** — pausa de aprovação.

---

## Lote 2 — orquestração e o relatório v2

### Task 4: `lib/report.py` — o schema v2

**Files:**
- Modify: `scripts/lib/report.py` (reescrito; o v1 fica no histórico do git da skill antiga)
- Test: `tests/test_report_v2.py`

- [x] **Step 1: Escrever os testes**

```python
# tests/test_report_v2.py
import json

from lib.report import (SCHEMA_VERSION, achados_ordenados, montar_inventario, na, novo,
                        novo_alvo, ordenar, valido)


def achado(regra, objeto, severidade, alvo):
    return {"regra": regra, "objeto": objeto, "severidade": severidade, "alvo": alvo}


def test_relatorio_novo_tem_o_esqueleto_do_v2():
    r = novo(generated_at="2026-09-19T10:00:00Z")

    assert r["schema_version"] == SCHEMA_VERSION == 2
    assert r["alvos"] == [] and r["aceites"] == [] and r["inventario"] == []
    assert r["resumo"] == "" and r["recomendacoes"] == []


def test_alvo_novo_nasce_sem_dados_ate_alguem_coletar():
    a = novo_alvo(nome="cluster", tipo="docker", onde="context: ctx")

    assert a["saude"] == "sem dados"
    assert a["achados"] == [] and a["nao_coletado"] == []
    assert a["analise"] == ""


def test_marcador_de_nao_coletado_carrega_o_motivo():
    assert na("alvo não confirmado nesta execução") == {"valor": None,
                                                        "motivo": "alvo não confirmado nesta execução"}


def relatorio_com_dois_alvos():
    r = novo(generated_at="x")
    r["alvos"] = [{"nome": "b", "achados": [achado("z", "2", "high", "b"),
                                            achado("a", "1", "critical", "b")]},
                  {"nome": "a", "achados": [achado("m", "9", "high", "a")]}]
    return r


def test_dentro_do_alvo_os_achados_vao_do_mais_grave_ao_menos():
    ordenado = ordenar(relatorio_com_dois_alvos())

    assert [f["regra"] for f in ordenado["alvos"][0]["achados"]] == ["a", "z"]


def test_a_lista_do_relatorio_e_global_por_severidade_e_nao_por_alvo():
    """A seção "Achados" abre pelo mais grave: se fosse agrupada por alvo, um crítico do
    segundo alvo ficaria abaixo de um aviso do primeiro."""
    chaves = [(f["severidade"], f["alvo"], f["regra"])
              for f in achados_ordenados(ordenar(relatorio_com_dois_alvos()))]

    assert chaves == [("critical", "b", "a"), ("high", "a", "m"), ("high", "b", "z")]


def test_ordem_dos_alvos_e_a_declarada_nao_a_alfabetica():
    r = novo(generated_at="x")
    r["alvos"] = [{"nome": "site", "achados": []}, {"nome": "cluster", "achados": []}]

    assert [a["nome"] for a in ordenar(r)["alvos"]] == ["site", "cluster"]


def test_inventario_sai_dos_alvos_com_o_que_interessa_para_o_mapa():
    r = novo(generated_at="x")
    r["alvos"] = [novo_alvo("cluster", "docker", "context: ctx"),
                  novo_alvo("site", "http", "https://exemplo.invalido/health")]
    r["alvos"][0]["saude"] = "🟢"

    assert montar_inventario(r) == [
        {"nome": "cluster", "tipo": "docker", "onde": "context: ctx", "saude": "🟢"},
        {"nome": "site", "tipo": "http", "onde": "https://exemplo.invalido/health",
         "saude": "sem dados"}]





def test_valido_exige_versao_e_lista_de_alvos():
    assert valido(novo(generated_at="x")) is True
    assert valido({"schema_version": 1, "alvos": []}) is False
    assert valido({"schema_version": 2}) is False


def test_determinismo_nao_depende_da_ordem_em_que_o_agente_escreveu():
    """Ordem de inserção diferente, mesmo relatório: é isso que a restrição 4 promete."""
    um = novo(generated_at="x")
    um["alvos"] = [{"nome": "a", "achados": [achado("z", "2", "high", "a"),
                                             achado("a", "1", "critical", "a")]}]
    dois = novo(generated_at="x")
    dois["alvos"] = [{"nome": "a", "achados": [achado("a", "1", "critical", "a"),
                                               achado("z", "2", "high", "a")]}]

    assert json.dumps(ordenar(um), ensure_ascii=False, indent=1) == \
        json.dumps(ordenar(dois), ensure_ascii=False, indent=1)


def test_ordenar_nao_estraga_o_relatorio_recebido():
    """O histórico compara com o relatório anterior: mutar a entrada corromperia a comparação."""
    original = novo(generated_at="x")
    original["alvos"] = [{"nome": "a", "achados": [achado("z", "2", "high", "a"),
                                                   achado("a", "1", "critical", "a")]}]
    antes = json.dumps(original, ensure_ascii=False, sort_keys=True)

    ordenar(original)

    assert json.dumps(original, ensure_ascii=False, sort_keys=True) == antes
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_report_v2.py -q`
Expected: `ImportError: cannot import name 'novo' from 'lib.report'` — 8 falhas.

- [x] **Step 3: `scripts/lib/report.py`**

```python
"""Schema do report.json v2: o ALVO no centro.

Diferença essencial para o v1: não existe mais um cluster no topo. O topo é a lista de alvos,
mais o inventário (o mapa), os aceites e o histórico. Os quatro campos do agente (`resumo`,
`fortes`, `fracos`, `recomendacoes`) e o `analise` de cada alvo nascem vazios — é o script que
grava os fatos, e o agente que escreve a interpretação por cima.
"""
SCHEMA_VERSION = 2

SEVERIDADES = ("critical", "high", "medium", "low", "info")
_PESO = {nome: posicao for posicao, nome in enumerate(SEVERIDADES)}


def novo(generated_at):
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "alvos": [],
        "inventario": [],
        "aceites": [],
        "historico": None,
        # do agente:
        "resumo": "",
        "fortes": [],
        "fracos": [],
        "recomendacoes": [],
    }


def novo_alvo(nome, tipo, onde):
    """`onde` é o texto que identifica o alvo no relatório (context, URL, host:porta)."""
    return {
        "nome": nome, "tipo": tipo, "onde": onde,
        "saude": "sem dados",
        "dimensoes": {},
        "fatos": {},
        "achados": [],
        "nao_coletado": [],
        "analise": "",       # do agente
    }


def na(motivo):
    """Marcador de dado não coletado — o motivo é obrigatório, senão vira buraco sem explicação."""
    return {"valor": None, "motivo": motivo}


def _chave_do_achado(achado):
    return (_PESO.get(achado.get("severidade"), len(SEVERIDADES)), achado.get("alvo", ""),
            achado.get("regra", ""), str(achado.get("objeto", "")))


def ordenar(relatorio):
    """Devolve uma CÓPIA ordenada: alvos na ordem declarada, achados por severidade dentro de cada um.

    Sem o alvo na chave, dois serviços homônimos em alvos diferentes trocariam de lugar entre
    execuções e o histórico viraria ruído. E não muta a entrada: o histórico compara com o
    relatório anterior, e mutar a baseline durante a comparação a corromperia.
    """
    copia = dict(relatorio)
    copia["alvos"] = [dict(alvo, achados=sorted(alvo.get("achados", []), key=_chave_do_achado))
                      for alvo in relatorio.get("alvos", [])]
    copia["aceites"] = sorted(relatorio.get("aceites", []),
                              key=lambda a: (a.get("alvo", ""), a.get("regra", "")))
    return copia


def achados_ordenados(relatorio):
    """Todos os achados numa lista só, do mais grave ao menos — é o que a seção "Achados" mostra.

    Ordenar por alvo primeiro esconderia um crítico do segundo alvo abaixo de um aviso do primeiro.
    """
    achados = [f for alvo in relatorio.get("alvos", []) for f in alvo.get("achados", [])]
    return sorted(achados, key=_chave_do_achado)


def montar_inventario(relatorio):
    """O mapa: o que existe, de que tipo, onde vive e em que estado."""
    return [{"nome": a["nome"], "tipo": a["tipo"], "onde": a["onde"], "saude": a["saude"]}
            for a in relatorio.get("alvos", [])]


def valido(relatorio):
    return (isinstance(relatorio, dict)
            and relatorio.get("schema_version") == SCHEMA_VERSION
            and isinstance(relatorio.get("alvos"), list))
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_report_v2.py -q`
Expected: `8 passed`. Se o teste de ordem falhar, conserte o **teste** — ele foi escrito para
documentar a ordem e a expressão dele é confusa; a regra é: severidade, alvo, regra, objeto.

---

### Task 5: `collect.py` como orquestrador, com o gate `--confirmar`

**Files:**
- Create: `scripts/lib/falhas.py` (`FalhaDeColeta`: separa falha esperada de bug do coletor)
- Modify: `scripts/collect.py` (reescrito; o `assemble_report` atual vira o coletor docker na Task 6)
- Test: `tests/test_collect_orquestrador.py`

O gate substitui o `--confirmed-context` de hoje: **alvo não confirmado não é tocado**, e ainda
assim aparece no relatório — senão o inventário mentiria por omissão.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_collect_orquestrador.py
import json

import pytest

import collect


def ambiente(tmp_path, projeto='alvos = ["cluster", "site"]\n'):
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 10\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "cluster"\ntipo = "docker"\ncontext = "ctx"\n\n'
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/health"\n',
        encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text(projeto, encoding="utf-8")
    return ["--padrao", str(tmp_path / "default.toml"),
            "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z"]


def coletor_falso(registro, saude="🟢"):
    def coletar(alvo, contexto):
        registro.append(alvo["nome"])
        return {"saude": saude, "fatos": {"ok": True},
                "achados": [{"regra": "r1", "objeto": alvo["nome"], "severidade": "low",
                             "alvo": alvo["nome"]}]}
    return coletar


def ler_relatorio(tmp_path):
    return json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))


def test_so_o_alvo_confirmado_e_coletado(tmp_path):
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)

    assert codigo == 0
    assert visitados == ["cluster"], "site não foi confirmado: não pode ser tocado"


def test_alvo_nao_confirmado_aparece_no_relatorio_como_sem_dados(tmp_path):
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    r = ler_relatorio(tmp_path)

    site = next(a for a in r["alvos"] if a["nome"] == "site")
    assert site["saude"] == "sem dados"
    assert any("confirmad" in n["motivo"] for n in site["nao_coletado"])


def test_sem_confirmar_nada_nenhum_coletor_roda(tmp_path, capsys):
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}

    codigo = collect.main(ambiente(tmp_path), coletores=coletores)

    assert codigo == 2
    assert visitados == []
    assert "confirm" in capsys.readouterr().err


def test_confirmar_alvo_que_nao_existe_para_antes_de_coletar(tmp_path, capsys):
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "fantasma"], coletores=coletores)

    assert codigo == 2 and visitados == []
    assert "fantasma" in capsys.readouterr().err


def test_relatorio_sai_com_inventario_e_ordem_declarada(tmp_path):
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster", "site"], coletores=coletores)
    r = ler_relatorio(tmp_path)

    assert [a["nome"] for a in r["alvos"]] == ["cluster", "site"]
    assert [i["nome"] for i in r["inventario"]] == ["cluster", "site"]
    assert r["generated_at"] == "2026-09-19T10:00:00Z"
    assert r["schema_version"] == 2


def test_coletor_que_estoura_o_orcamento_vira_sem_dados_sem_derrubar_o_resto(tmp_path):
    def lento(alvo, contexto):
        raise TimeoutError("passou do orçamento")

    coletores = {"docker": lento, "http": coletor_falso([])}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "cluster", "site"],
                          coletores=coletores)
    r = ler_relatorio(tmp_path)

    assert codigo == 0, "um alvo travado não derruba a auditoria inteira"
    cluster = next(a for a in r["alvos"] if a["nome"] == "cluster")
    site = next(a for a in r["alvos"] if a["nome"] == "site")
    assert cluster["saude"] == "sem dados" and "orçamento" in cluster["nao_coletado"][0]["motivo"]
    assert site["saude"] == "🟢"


def test_falha_do_coletor_nao_vira_achado(tmp_path):
    def quebrado(alvo, contexto):
        raise RuntimeError("conexão recusada")

    coletores = {"docker": quebrado, "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster["achados"] == [], "não consegui ver ≠ está ruim"
    assert "conexão recusada" in cluster["nao_coletado"][0]["motivo"]


def test_nada_e_escrito_fora_da_pasta_de_saida(tmp_path):
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}
    args = ambiente(tmp_path)                 # cria a configuração ANTES do retrato
    antes = {p for p in tmp_path.rglob("*")}

    collect.main([*args, "--confirmar", "cluster"], coletores=coletores)

    novos = {p for p in tmp_path.rglob("*")} - antes
    assert all(str(p).startswith(str(tmp_path / "saida")) for p in novos), sorted(map(str, novos))


def test_coletor_que_devolve_lixo_nao_derruba_a_auditoria(tmp_path):
    """Coletor com bug devolvendo None não pode impedir o relatório dos outros alvos."""
    coletores = {"docker": lambda alvo, ctx: None, "http": coletor_falso([])}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "cluster", "site"],
                          coletores=coletores)
    r = ler_relatorio(tmp_path)

    assert codigo == 0
    cluster = next(a for a in r["alvos"] if a["nome"] == "cluster")
    assert cluster["saude"] == "sem dados" and cluster["nao_coletado"]
    assert next(a for a in r["alvos"] if a["nome"] == "site")["saude"] == "🟢"


def test_coletor_nao_pode_reescrever_a_identidade_do_alvo(tmp_path):
    """Se pudesse, o inventário mentiria e a chave de histórico trocaria de dono."""
    def mentiroso(alvo, contexto):
        return {"nome": "outro", "tipo": "http", "onde": "usuario:senha@host",
                "saude": "🟢", "fatos": {}, "achados": []}

    coletores = {"docker": mentiroso, "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster["tipo"] == "docker"
    assert cluster["onde"] == "context: ctx"
    assert "senha" not in json.dumps(ler_relatorio(tmp_path))


def test_achados_de_tipo_errado_viram_sem_dados(tmp_path):
    coletores = {"docker": lambda alvo, ctx: {"saude": "🟢", "achados": "isto devia ser lista"},
                 "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster["achados"] == []
    assert any("inválid" in n["motivo"] for n in cluster["nao_coletado"])


def test_erro_de_programacao_no_coletor_fica_marcado_como_tal(tmp_path):
    """"Não consegui conectar" e "o coletor tem bug" precisam ser distinguíveis."""
    def bugado(alvo, contexto):
        return {"saude": alvo["campo_que_nao_existe"]}

    coletores = {"docker": bugado, "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster["erro_interno"] is True
    assert "KeyError" in cluster["nao_coletado"][0]["motivo"]


def test_falha_esperada_de_coleta_nao_e_erro_interno(tmp_path):
    from lib.falhas import FalhaDeColeta

    def recusado(alvo, contexto):
        raise FalhaDeColeta("conexão recusada")

    coletores = {"docker": recusado, "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster.get("erro_interno") is not True
    assert cluster["nao_coletado"][0]["motivo"] == "conexão recusada"


def test_sem_alvos_toml_o_usuario_e_mandado_para_o_migrar(tmp_path, capsys):
    (tmp_path / "default.toml").write_text('[limites]\ntimeout_por_comando = 5\n',
                                           encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text("alvos = []\n", encoding="utf-8")
    args = ["--padrao", str(tmp_path / "default.toml"),
            "--infra", str(tmp_path / "nao-existe.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z"]

    codigo = collect.main([*args, "--confirmar", "qualquer"], coletores={})
    saida = capsys.readouterr()

    assert codigo == 2
    assert "migrar" in (saida.out + saida.err)


@pytest.mark.parametrize("confirmar", [[], [""], ["CLUSTER"], ["cluster extra"], ["site"]])
def test_gate_recusa_confirmacao_que_nao_casa_exatamente(tmp_path, confirmar):
    """`site` está no alvos.toml mas fora da seleção do projeto: confirmar não o traz de volta."""
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}
    projeto = 'alvos = ["cluster"]\n'

    codigo = collect.main([*ambiente(tmp_path, projeto=projeto), "--confirmar", *confirmar],
                          coletores=coletores)

    assert codigo == 2 and visitados == []


def test_escrita_confinada_pega_sobrescrita_de_arquivo_existente(tmp_path, monkeypatch):
    """Comparar só a lista de caminhos deixaria passar sobrescrita de arquivo que já existia."""
    import hashlib

    def retrato():
        return {str(p.relative_to(tmp_path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in tmp_path.rglob("*") if p.is_file()}

    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}
    args = ambiente(tmp_path)
    monkeypatch.chdir(tmp_path)
    antes = retrato()

    collect.main([*args, "--confirmar", "cluster"], coletores=coletores)

    mexidos = {c for c in set(antes) | set(retrato()) if antes.get(c) != retrato().get(c)}
    assert all(c.startswith("saida/") for c in mexidos), sorted(mexidos)


def test_carimbo_de_tempo_invalido_para_antes_de_coletar(tmp_path, capsys):
    """O carimbo vira a data que decide aceite vencido: aceitar lixo aqui é silenciar aceites."""
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}
    args = [a if a != "2026-09-19T10:00:00Z" else "ontem" for a in ambiente(tmp_path)]

    codigo = collect.main([*args, "--confirmar", "cluster"], coletores=coletores)

    assert codigo == 2 and visitados == []
    assert "--at" in capsys.readouterr().err


def test_aceite_do_projeto_tira_o_achado_da_nota(tmp_path):
    """Integração: o aceite configurado no projeto precisa chegar ao relatório final."""
    projeto = ('alvos = ["cluster"]\n\n[[aceite]]\nalvo = "cluster"\nregra = "r1"\n'
               'motivo = "risco assumido"\ndesde = "2026-01-01"\nrevisar_em = "2027-01-01"\n')
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path, projeto=projeto), "--confirmar", "cluster"],
                 coletores=coletores)
    r = ler_relatorio(tmp_path)

    cluster = next(a for a in r["alvos"] if a["nome"] == "cluster")
    assert cluster["achados"] == []
    assert r["aceites"][0]["motivo"] == "risco assumido" and r["aceites"][0]["origem"] == "projeto"


def test_sem_registro_explicito_a_skill_usa_os_coletores_de_verdade(tmp_path, monkeypatch):
    """Rodando pela linha de comando ninguém passa `coletores`: se o registro padrão não existir,
    a auditoria devolve "sem coletor nesta versão" para tudo — e foi o que aconteceu."""
    padrao = collect.coletores_padrao()
    assert set(padrao) == {"docker", "http"} and all(callable(f) for f in padrao.values())

    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["site"]\n', encoding="utf-8")
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 10\nhttp_timeout = 1\n', encoding="utf-8")
    args = ["--padrao", str(tmp_path / "default.toml"), "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z"]

    collect.main([*args, "--confirmar", "site"])          # sem `coletores=`
    site = json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))["alvos"][0]

    motivos = " ".join(n["motivo"] for n in site["nao_coletado"])
    assert "sem coletor" not in motivos, motivos
    assert "não consegui alcançar" in motivos, "o coletor http rodou de verdade e não alcançou"


```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_collect_orquestrador.py -q`
Expected: `TypeError: main() got an unexpected keyword argument 'coletores'` — 8 falhas.

- [x] **Step 3: `scripts/collect.py`**

```python
#!/usr/bin/env python3
"""Modo auditar: confirma os alvos, chama um coletor por tipo e grava o report.json v2.

Não escreve nada fora da pasta de saída. Falha de coleta nunca vira achado: vira `nao_coletado`
com o motivo — confundir "não consegui ver" com "está ruim" é o jeito mais fácil de mentir.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from lib import alvos as alvos_mod
from lib import report as report_mod
from lib.falhas import FalhaDeColeta
from lib.config import ConfigInvalida, carregar

EXIT_OK, EXIT_PARADA = 0, 2

PADRAO_DA_SKILL = Path(__file__).resolve().parent.parent / "default.toml"
INFRA_PADRAO = Path.home() / ".config" / "sw-infra-audit" / "alvos.toml"
PROJETO_PADRAO = Path(".sw-infra-audit.toml")


def onde_de(alvo):
    """Como o alvo é identificado no relatório — sem credencial, sempre."""
    if alvo["tipo"] == "docker":
        return f"context: {alvo['context']}"
    if alvo["tipo"] == "http":
        return alvo["url"]
    return alvo.get("host", "")


# o coletor só preenche estes campos: identidade do alvo é do orquestrador, não dele
CAMPOS_DO_COLETOR = ("saude", "dimensoes", "fatos", "achados")


def coletar_alvo(alvo, coletor, contexto):
    """Roda um coletor e traduz qualquer falha em `nao_coletado`.

    Nada que o coletor devolva pode derrubar a auditoria dos outros alvos, e nada que ele devolva
    pode reescrever `nome`, `tipo` ou `onde` — esses vão para o inventário e para a chave do
    histórico; deixá-los editáveis seria deixar o relatório mentir.
    """
    registro = report_mod.novo_alvo(alvo["nome"], alvo["tipo"], onde_de(alvo))
    if coletor is None:
        registro["nao_coletado"].append(report_mod.na(f"tipo {alvo['tipo']} sem coletor nesta versão"))
        return registro
    try:
        resultado = coletor(alvo, contexto)
        if not isinstance(resultado, dict):
            raise FalhaDeColeta(f"o coletor devolveu {type(resultado).__name__}, não um dicionário")
    except TimeoutError as erro:
        registro["nao_coletado"].append(report_mod.na(f"orçamento do alvo estourou: {erro}"))
        return registro
    except FalhaDeColeta as erro:
        registro["nao_coletado"].append(report_mod.na(str(erro)))
        return registro
    except Exception as erro:                      # noqa: BLE001 — bug do coletor, não falha de acesso
        registro["erro_interno"] = True
        registro["nao_coletado"].append(
            report_mod.na(f"erro interno do coletor {type(erro).__name__}: {erro}"))
        return registro

    for campo in CAMPOS_DO_COLETOR:
        if campo not in resultado:
            continue
        valor = resultado[campo]
        esperado = type(registro[campo])
        if not isinstance(valor, esperado):
            registro["nao_coletado"].append(report_mod.na(
                f"o coletor devolveu {campo} inválido ({type(valor).__name__})"))
            continue
        registro[campo] = valor

    extras = resultado.get("nao_coletado", [])
    if isinstance(extras, list):
        registro["nao_coletado"].extend(e for e in extras if isinstance(e, dict))
    elif extras:
        registro["nao_coletado"].append(report_mod.na("o coletor devolveu nao_coletado inválido"))
    return registro


def main(argv=None, coletores=None) -> int:
    ap = argparse.ArgumentParser(description="Auditoria read-only por alvos.")
    ap.add_argument("--out", required=True, help="pasta desta execução")
    ap.add_argument("--at", required=True, help="carimbo de tempo (injetado, para ser determinístico)")
    ap.add_argument("--confirmar", nargs="*", default=[], help="nomes dos alvos autorizados nesta rodada")
    ap.add_argument("--padrao", default=None)
    ap.add_argument("--infra", default=None)
    ap.add_argument("--projeto", default=None)
    args = ap.parse_args(argv)

    try:                                   # o carimbo vira a data que decide aceite vencido
        date.fromisoformat(args.at[:10])
    except ValueError:
        print(f"--at precisa começar com AAAA-MM-DD, veio {args.at!r}", file=sys.stderr)
        return EXIT_PARADA

    padrao = Path(args.padrao) if args.padrao else PADRAO_DA_SKILL
    infra = Path(args.infra) if args.infra else INFRA_PADRAO
    projeto = Path(args.projeto) if args.projeto else PROJETO_PADRAO

    try:
        cfg = carregar(padrao=padrao, infra=infra, projeto=projeto)
        declarados, avisos = alvos_mod.ler(infra)
        escolhidos = alvos_mod.selecionar(declarados, cfg.alvos_escolhidos())
    except (ConfigInvalida, alvos_mod.AlvoInvalido) as erro:
        print(str(erro), file=sys.stderr)
        return EXIT_PARADA

    for aviso in avisos:                    # antes do gate: sem alvos.toml, é isto que orienta
        print(f"aviso: {aviso}")

    confirmados = list(args.confirmar)
    desconhecidos = [n for n in confirmados if n not in {a["nome"] for a in escolhidos}]
    if desconhecidos:
        print(f"--confirmar cita alvo que não está na auditoria: {', '.join(desconhecidos)}",
              file=sys.stderr)
        return EXIT_PARADA
    if not confirmados:
        print("nenhum alvo confirmado: nada foi tocado. Confirme com --confirmar <nomes>.",
              file=sys.stderr)
        return EXIT_PARADA

    coletores = coletores or {}
    # sem padrão, um limite ausente viraria espera infinita no coletor
    contexto = {"timeout": cfg.valor("limites.timeout_por_comando") or 20,
                "orcamento": cfg.valor("limites.orcamento_por_alvo") or 120,
                "http_timeout": cfg.valor("limites.http_timeout") or 8,
                "at": args.at}

    relatorio = report_mod.novo(generated_at=args.at)
    for alvo in escolhidos:
        if alvo["nome"] not in confirmados:
            registro = report_mod.novo_alvo(alvo["nome"], alvo["tipo"], onde_de(alvo))
            registro["nao_coletado"].append(report_mod.na("alvo não confirmado nesta execução"))
            registro["coletado"] = False
            relatorio["alvos"].append(registro)
            continue
        registro = coletar_alvo(alvo, coletores.get(alvo["tipo"]), contexto)
        registro["coletado"] = True
        relatorio["alvos"].append(registro)

    from lib import aceites as aceites_mod
    relatorio["aceites"] = aceites_mod.aplicar(relatorio["alvos"], cfg.aceites(),
                                               hoje=args.at[:10])
    relatorio = report_mod.ordenar(relatorio)
    relatorio["inventario"] = report_mod.montar_inventario(relatorio)

    saida = Path(args.out)
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / "report.json"
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"report.json: {destino}")
    for alvo in relatorio["alvos"]:
        print(f"  {alvo['saude']:<10} {alvo['nome']:<24} {alvo['tipo']}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_collect_orquestrador.py -q`
Expected: `8 passed`

- [x] **Step 5: Suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: `tests/test_collect.py` e `tests/test_report.py` quebram — o `collect.py` foi reescrito e
o `assemble_report` saiu daqui. Erro de import **trava a coleta do pytest inteiro**, então marque os
dois como pendentes, com o motivo no próprio arquivo:

```python
import pytest

pytest.skip("v1: volta na Task 6, quando o coletor docker renascer como módulo "
            "(test_report.py é substituído por test_report_v2.py)", allow_module_level=True)
```

O `test_collect.py` volta na Task 6 apontando para `lib.coletores.docker`; o `test_report.py` é
**substituído** pelo `test_report_v2.py` e some. Se algum outro teste herdado falhar, pare e
diagnostique.

- [x] **Step 6: Checkpoint do lote 2** — pausa de aprovação.

---

## Lote 3 — coletores e aceites

### Task 6: `lib/coletores/docker.py` — o coletor de hoje, agora por alvo

**Files:**
- Create: `scripts/lib/coletores/__init__.py`, `scripts/lib/coletores/docker.py`
- Modify: `scripts/lib/runner.py` (allowlist por tipo), `tests/test_collect.py` (aponta para o módulo novo)

O miolo **não muda**: o `assemble_report` de hoje já faz a coleta certa. O que muda é a moldura —
ele passa a receber um alvo, devolver o bloco daquele alvo, e pegar a URL de métricas do alvo.

- [x] **Step 1: Mover o miolo**

```bash
cd ~/.claude/skills/sw-infra-audit
mkdir -p scripts/lib/coletores && touch scripts/lib/coletores/__init__.py
git -C . status >/dev/null 2>&1 || true            # a skill não é repositório: mova mesmo
mv scripts/lib/allowlist.py scripts/lib/coletores/docker_allowlist.py
grep -rl "lib.allowlist\|from lib import allowlist" scripts tests | xargs -r \
  sed -i 's/lib\.allowlist/lib.coletores.docker_allowlist/g; s/from lib import allowlist/from lib.coletores import docker_allowlist as allowlist/g'
```

Mova de `scripts/collect.py` (versão original, que está no git da skill antiga) para
`scripts/lib/coletores/docker.py`: `detect_kind`, `_jlines`, `_first`, `_first_json`, `_state`,
`_completed_job`, `assemble_report` e `host_from_context`. Mantenha o corpo **igual** — esta task
não é hora de melhorar a coleta de docker.

- [x] **Step 2: Escrever o teste da moldura nova**

```python
# tests/test_coletor_docker.py
from lib.coletores import docker as coletor

# o assemble_report grava `verdict` (green/yellow/red/unknown), NÃO `status`
BRUTO = {"health": {"verdict": "green"}, "nodes": [{"id": "n1"}],
         # forma REAL do achado v1: rule_id/severity(crit|high|med|low)/object/evidence
         "findings": [{"rule_id": "spof", "object": "traefik", "severity": "high",
                       "evidence": "1 réplica"}],
         "dimensions": {"seguranca": {"nota": "🟡"}}}


def test_devolve_o_bloco_do_alvo_com_saude_fatos_e_achados(monkeypatch):
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))

    bloco = coletor.coletar({"nome": "cluster", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": "2026-09-19T10:00:00Z"})

    assert bloco["saude"] == "🟢"
    assert bloco["fatos"]["nodes"] == [{"id": "n1"}]
    assert bloco["achados"] == [{"regra": "spof", "objeto": "traefik", "severidade": "high",
                                 "detalhe": "1 réplica", "alvo": "cluster"}]
    assert bloco["dimensoes"] == {"seguranca": {"nota": "🟡"}}


def test_metricas_usam_a_url_declarada_e_so_ela(monkeypatch):
    """A allowlist de rede sai do alvo: host não declarado não é alcançável."""
    permitidos = {}
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))
    monkeypatch.setattr(coletor.enrich, "probe",
                        lambda base, allowed, timeout: permitidos.update(base=base, allowed=allowed) or True)
    monkeypatch.setattr(coletor.enrich, "collect_runtime",
                        lambda base, allowed, timeout: {"requests_24h": 10})
    monkeypatch.setattr(coletor.enrich, "attach", lambda bruto, runtime: None)

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "metricas_url": "http://127.0.0.1:9090/metrics"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert permitidos == {"base": "http://127.0.0.1:9090", "allowed": ["127.0.0.1"]}
    assert bloco["fatos"]["runtime"] == {"requests_24h": 10}


def test_sem_metricas_url_o_alvo_segue_e_as_metricas_ficam_sem_dados(monkeypatch):
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert bloco["saude"] == "🟢"
    assert any("metricas_url" in n["motivo"] for n in bloco["nao_coletado"])


def test_endpoint_que_nao_responde_vira_sem_dados_e_nao_achado(monkeypatch):
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))
    monkeypatch.setattr(coletor.enrich, "probe", lambda *a, **k: False)
    monkeypatch.setattr(coletor.enrich, "probe_exporter", lambda *a, **k: False)

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "metricas_url": "http://127.0.0.1:9090"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert len(bloco["achados"]) == 1, "endpoint mudo não vira achado novo"
    assert any("não respondeu" in n["motivo"] for n in bloco["nao_coletado"])


def test_a_descoberta_nunca_roda_na_coleta(monkeypatch):
    """Descoberta alcançaria host que o usuário não declarou — ela só existe no modo configurar."""
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: dict(BRUTO))
    monkeypatch.setattr(coletor.discover, "propose",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("descobriu na coleta")))

    coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                    {"timeout": 5, "orcamento": 10, "at": ""})


import pytest


@pytest.mark.parametrize("verdict,saude", [("green", "🟢"), ("yellow", "🟡"), ("red", "🔴"),
                                           ("unknown", "sem dados")])
def test_veredito_do_coletor_vira_o_vocabulario_do_relatorio(monkeypatch, verdict, saude):
    """O v1 fala green/yellow/red; o relatório v2 fala 🟢/🟡/🔴 — misturar os dois faz o
    inventário mostrar alvos incomparáveis lado a lado."""
    monkeypatch.setattr(coletor, "assemble_report",
                        lambda **kwargs: {"health": {"verdict": verdict}, "findings": []})

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert bloco["saude"] == saude


def test_o_que_o_coletor_nao_conseguiu_ver_chega_ao_relatorio(monkeypatch):
    """`docker info indisponível` sumia: o relatório dizia "sem achados" sem dizer que faltou dado."""
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: {
        "health": {"verdict": "green"}, "findings": [],
        "not_collected": [{"what": "docker info", "reason": "indisponível"}],
        "collection_errors": ["timeout ao listar tasks"]})

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx",
                             "metricas_url": "http://127.0.0.1:9090"},
                            {"timeout": 5, "orcamento": 10, "at": ""})
    motivos = " | ".join(n["motivo"] for n in bloco["nao_coletado"])

    assert "docker info" in motivos and "indisponível" in motivos
    assert "timeout ao listar tasks" in motivos


def test_severidade_do_v1_vira_o_vocabulario_do_relatorio(monkeypatch):
    """O v1 fala "med"; o relatório e o coletor http falam "medium". Misturar os dois faz a
    ordenação por gravidade cair no fim da lista sem ninguém perceber."""
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: {
        "health": {"verdict": "yellow"},
        "findings": [{"rule_id": "sem_limite", "object": "api", "severity": "med",
                      "evidence": "sem limite de memória"}]})

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    assert bloco["achados"][0]["severidade"] == "medium"
    assert bloco["achados"][0]["regra"] == "sem_limite"


def test_erro_de_coleta_vira_texto_legivel_e_nao_dicionario(monkeypatch):
    monkeypatch.setattr(coletor, "assemble_report", lambda **kwargs: {
        "health": {"verdict": "unknown"}, "findings": [],
        "collection_errors": [{"cmd": "docker node ls", "reason": "não é swarm manager"}]})

    bloco = coletor.coletar({"nome": "c", "tipo": "docker", "context": "ctx"},
                            {"timeout": 5, "orcamento": 10, "at": ""})

    motivo = bloco["nao_coletado"][-1]["motivo"]
    assert motivo == "docker node ls: não é swarm manager"
```

- [x] **Step 3: A moldura, no fim de `lib/coletores/docker.py`**

```python
def coletar(alvo, contexto):
    """Traduz o alvo docker para o bloco do report v2.

    A URL de métricas vem do ALVO, nunca de descoberta: a descoberta alcançaria host que o usuário
    não declarou, e isso quebraria a regra de egress. Aqui ela nem é chamada — vive no modo
    configurar, como sugestão para você colar no alvos.toml.
    """
    from lib import report as report_mod
    from lib.http_get import host_of
    from lib.runner import run

    nao_coletado = []
    bruto = assemble_report(run_fn=run, timeout=contexto["timeout"], context=alvo["context"],
                            generated_at=contexto.get("at", ""), connected_node=None)

    url = alvo.get("metricas_url")
    if not url:
        nao_coletado.append(report_mod.na(
            "métricas: o alvo não declara `metricas_url` — rode `configurar.py alvos --sugerir` "
            "para ver candidatos e colar um no alvos.toml"))
    else:
        permitido = [host_of(url)]
        base = url.split("/api/")[0].split("/metrics")[0].rstrip("/")
        if enrich.probe(base, permitido, contexto["timeout"]):
            bruto["runtime"] = enrich.collect_runtime(base, permitido, contexto["timeout"])
        elif enrich.probe_exporter(base, permitido, contexto["timeout"]):
            bruto["runtime"] = enrich.collect_from_exporter(base, permitido, contexto["timeout"])
        else:
            nao_coletado.append(report_mod.na(
                f"métricas: {base} não respondeu como Prometheus nem como exporter"))

    achados = [{"regra": f.get("rule"), "objeto": f.get("object"),
                "severidade": f.get("severity"), "detalhe": f.get("detail"),
                "alvo": alvo["nome"]}
               for f in bruto.get("findings", [])]
    fatos = {chave: bruto.get(chave) for chave in
             ("nodes", "services", "networks", "secrets", "configs", "stacks", "tls", "scope",
              "runtime")
             if bruto.get(chave) is not None}

    return {"saude": (bruto.get("health") or {}).get("status", "sem dados"),
            "dimensoes": bruto.get("dimensions", {}),
            "fatos": fatos, "achados": achados, "nao_coletado": nao_coletado}
```

> **Correção do plano (descoberto na execução):** o `assemble_report` de hoje **não** busca
> métricas — quem faz isso é o `main()` do `collect.py` antigo, com `enrich.probe` /
> `collect_runtime`. Então `assemble_report` fica com a assinatura original, e é o `coletar` que
> chama o `enrich` com a URL do alvo. O módulo precisa importar `enrich` e `discover` no topo
> (`from lib import discover, enrich`) — `discover` só para o teste provar que ele **não** é usado.

- [x] **Step 4: `runner.py` com allowlist por tipo**

```python
# em scripts/lib/runner.py, trocar o import fixo da allowlist de docker por um despacho
from lib.coletores.docker_allowlist import check as check_docker   # a allowlist de hoje, renomeada

CHECAGENS = {"docker": check_docker}


def run(cmd, timeout, errors=None, tipo="docker"):
    """Único ponto de subprocesso da skill. `tipo` escolhe a allowlist; sem tipo conhecido, recusa."""
    checar = CHECAGENS.get(tipo)
    if checar is None:
        raise NotAllowed(f"sem allowlist para o tipo {tipo!r}")
    checar(cmd)
    ...  # o corpo de hoje segue igual daqui para baixo
```

- [x] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest -q`
Expected: os testes herdados do coletor voltam a passar (aponte-os para `lib.coletores.docker`),
mais os 3 novos. A suíte inteira verde, incluindo o baseline da Task 0.

---

### Task 7: `lib/coletores/http.py`

**Files:**
- Create: `scripts/lib/coletores/http.py`
- Test: `tests/test_coletor_http.py`

- [x] **Step 1: Escrever os testes**

```python
# tests/test_coletor_http.py
import http.server
import threading

import pytest

from lib.coletores import http as coletor


@pytest.fixture
def servidor():
    """Servidor local de verdade: testar HTTP com mock esconde justamente o que pode quebrar."""
    class Mão(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            corpo = b'{"status":"ok"}'
            self.send_response(200 if self.path == "/health" else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *args):
            pass

    s = http.server.HTTPServer(("127.0.0.1", 0), Mão)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()
    s.server_close()


def test_endpoint_saudavel_vira_alvo_verde(servidor):
    bloco = coletor.coletar({"nome": "site", "tipo": "http", "url": f"{servidor}/health"},
                            {"http_timeout": 5})

    assert bloco["saude"] == "🟢"
    assert bloco["fatos"]["codigo"] == 200
    assert bloco["fatos"]["tempo_faixa"] in ("<1s", "1-10s")
    assert bloco["achados"] == []


def test_codigo_de_erro_vira_achado_alto(servidor):
    bloco = coletor.coletar({"nome": "site", "tipo": "http", "url": f"{servidor}/quebrado"},
                            {"http_timeout": 5})

    assert bloco["saude"] == "🔴"
    assert [a["regra"] for a in bloco["achados"]] == ["http_fora_do_ar"]
    assert bloco["achados"][0]["severidade"] == "critical"


def test_host_que_nao_responde_vira_sem_dados_e_nao_achado():
    bloco = coletor.coletar({"nome": "site", "tipo": "http", "url": "http://127.0.0.1:1/x"},
                            {"http_timeout": 1})

    assert bloco["saude"] == "sem dados"
    assert bloco["achados"] == [], "não consegui alcançar ≠ está fora do ar"
    assert bloco["nao_coletado"]


def test_tempo_vai_em_faixa_para_o_relatorio_ser_deterministico(servidor):
    um = coletor.coletar({"nome": "s", "tipo": "http", "url": f"{servidor}/health"}, {"http_timeout": 5})
    dois = coletor.coletar({"nome": "s", "tipo": "http", "url": f"{servidor}/health"}, {"http_timeout": 5})

    assert um["fatos"]["tempo_faixa"] == dois["fatos"]["tempo_faixa"]
    assert "tempo_ms" not in um["fatos"], "milissegundo exato mudaria o relatório a cada rodada"


def test_certificado_vencendo_vira_achado(monkeypatch):
    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (200, ""))
    monkeypatch.setattr(coletor.http_get, "validade_do_certificado",
                        lambda url, allowed, timeout: {"dias": 9, "expira_em": "2026-09-28"})

    bloco = coletor.coletar({"nome": "site", "tipo": "http", "url": "https://exemplo.invalido/"},
                            {"http_timeout": 1})

    regras = [a["regra"] for a in bloco["achados"]]
    assert "certificado_vencendo" in regras


def test_http_simples_nao_gera_achado_de_certificado(servidor):
    bloco = coletor.coletar({"nome": "s", "tipo": "http", "url": f"{servidor}/health"},
                            {"http_timeout": 5})

    assert all(a["regra"] != "certificado_vencendo" for a in bloco["achados"])
    assert bloco["fatos"]["certificado"]["motivo"].startswith("http sem TLS")


def test_endpoint_local_em_http_nao_vira_achado_de_tls(servidor):
    """127.0.0.1 sem TLS é normal; cobrar certificado aí faria a regra virar ruído."""
    bloco = coletor.coletar({"nome": "s", "tipo": "http", "url": f"{servidor}/health"},
                            {"http_timeout": 5})

    assert [a["regra"] for a in bloco["achados"]] == []
    assert coletor.interno("127.0.0.1") and coletor.interno("10.0.0.5") and coletor.interno("localhost")


def test_endpoint_publico_em_http_vira_achado_de_tls(monkeypatch):
    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (200, ""))

    bloco = coletor.coletar({"nome": "s", "tipo": "http", "url": "http://exemplo.invalido/health"},
                            {"http_timeout": 1})

    assert [a["regra"] for a in bloco["achados"]] == ["sem_tls"]
    assert coletor.interno("exemplo.invalido") is False


def test_certificado_vencido_e_lido_mesmo_com_o_get_falhando(monkeypatch):
    """Certificado vencido derruba o GET — e era justamente o achado mais importante que sumia."""
    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (None, None))
    monkeypatch.setattr(coletor.http_get, "validade_do_certificado",
                        lambda url, allowed, timeout: {"dias": -3, "expira_em": "2026-09-16"})

    bloco = coletor.coletar({"nome": "s", "tipo": "http", "url": "https://exemplo.invalido/"},
                            {"http_timeout": 1})

    vencido = next(a for a in bloco["achados"] if a["regra"] == "certificado_vencendo")
    assert vencido["severidade"] == "critical"
    assert bloco["saude"] == "🔴"


def test_erro_do_servidor_e_fora_do_ar_mas_404_nao(monkeypatch):
    """5xx é o serviço quebrado; 404 é o servidor de pé respondendo que a rota não existe."""
    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (503, ""))
    quebrado = coletor.coletar({"nome": "s", "tipo": "http", "url": "http://127.0.0.1:1/x"},
                               {"http_timeout": 1})

    monkeypatch.setattr(coletor.http_get, "get_com_status", lambda *a, **k: (404, ""))
    ausente = coletor.coletar({"nome": "s", "tipo": "http", "url": "http://127.0.0.1:1/x"},
                              {"http_timeout": 1})

    assert [a["regra"] for a in quebrado["achados"]] == ["http_fora_do_ar"]
    assert quebrado["achados"][0]["severidade"] == "critical"
    assert [a["regra"] for a in ausente["achados"]] == ["http_resposta_de_erro"]
    assert ausente["achados"][0]["severidade"] == "medium"


def test_nome_de_servico_interno_nao_e_tratado_como_publico():
    """`traefik` é nome de serviço na rede do cluster, não um host público sem TLS."""
    assert coletor.interno("traefik") is True
    assert coletor.interno("api.exemplo.invalido") is False
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_coletor_http.py -q`
Expected: `ImportError` do módulo `lib.coletores.http` — 6 falhas.

- [x] **Step 2b: `http_get` ganha a função que devolve o código**

O `get` de hoje devolve só o corpo (ou `None`). O coletor precisa distinguir **fora do ar**
(código 5xx) de **não alcancei** (conexão recusada), então acrescente ao **mesmo ponto único de
rede** — nenhum outro módulo abre socket:

```python
def get_com_status(url, allowed_hosts, timeout=DEFAULT_TIMEOUT):
    """Como `get`, mas devolve (status, corpo). `(None, None)` quando não deu para alcançar.

    Código de erro HTTP não é falha de alcance: o servidor respondeu, e isso é um achado.
    """
    check_allowed(url, allowed_hosts)
    req = urllib.request.Request(url, method="GET")
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read(MAX_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as erro:          # respondeu, só que com erro
        return erro.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return None, None                           # não alcancei
```

- [x] **Step 3: `scripts/lib/coletores/http.py`**

```python
"""Coletor de endpoint HTTP: está no ar, que código devolve, e quando o certificado vence.

Reaproveita o ponto de rede único (`lib/http_get.py`): só GET, sem credencial, sem seguir
redirect, com teto de bytes e tempo.
"""
import ipaddress
import time
from urllib.parse import urlparse

from lib import http_get, report as report_mod

FAIXAS = ((1, "<1s"), (10, "1-10s"), (60, "10-60s"), (float("inf"), ">60s"))
HOSTS_LOCAIS = ("localhost", "localhost.localdomain")
DIAS_DE_ALERTA = 30


def faixa(segundos):
    for teto, nome in FAIXAS:
        if segundos < teto:
            return nome
    return FAIXAS[-1][1]


def interno(host):
    """Loopback, rede privada ou nome de serviço. Cobrar TLS de endpoint interno é ruído — e
    ruído faz a regra ser ignorada no dia em que ela aponta um endpoint público de verdade."""
    if not host or host.casefold() in HOSTS_LOCAIS:
        return True
    if "." not in host:            # rótulo único: nome de serviço na rede interna
        return True
    try:
        endereco = ipaddress.ip_address(host)
    except ValueError:
        return False
    return endereco.is_loopback or endereco.is_private


def coletar(alvo, contexto):
    url = alvo["url"]
    partes = urlparse(url)
    timeout = contexto.get("http_timeout", 8)
    fatos, achados, nao_coletado = {}, [], []

    inicio = time.monotonic()
    codigo, _ = http_get.get_com_status(url, [partes.hostname], timeout=timeout)
    if codigo is not None:
        fatos["codigo"] = codigo
        fatos["tempo_faixa"] = faixa(time.monotonic() - inicio)
    else:
        nao_coletado.append(report_mod.na(f"não consegui alcançar {partes.hostname}"))

    # o certificado é lido mesmo quando o GET falha: vencido derruba o handshake, e é o achado
    # que mais importa
    if partes.scheme == "https":
        certificado = http_get.validade_do_certificado(url, [partes.hostname], timeout)
        fatos["certificado"] = certificado
        if "erro" in certificado:
            fatos["certificado"] = report_mod.na(f"não li o certificado: {certificado['erro']}")
        else:
            if certificado["dias"] <= DIAS_DE_ALERTA:
                achados.append({"regra": "certificado_vencendo", "objeto": partes.hostname,
                                "severidade": "critical" if certificado["dias"] <= 0 else "high",
                                "detalhe": f"expira em {certificado['expira_em']}",
                                "alvo": alvo["nome"]})
    else:
        fatos["certificado"] = report_mod.na("http sem TLS: não há certificado para checar")
        if not interno(partes.hostname):
            achados.append({"regra": "sem_tls", "objeto": partes.hostname, "severidade": "medium",
                            "detalhe": "endpoint público servido em http", "alvo": alvo["nome"]})

    if codigo is None:
        saude = "sem dados" if not achados else "🔴"
    elif codigo >= 500:
        achados.append({"regra": "http_fora_do_ar", "objeto": url, "severidade": "critical",
                        "detalhe": f"código {codigo}", "alvo": alvo["nome"]})
        saude = "🔴"
    elif codigo >= 400:
        # 4xx é servidor de pé respondendo: rota errada ou sem permissão, não serviço caído
        achados.append({"regra": "http_resposta_de_erro", "objeto": url, "severidade": "medium",
                        "detalhe": f"código {codigo}", "alvo": alvo["nome"]})
        saude = "🟡"
    elif any(a["severidade"] in ("critical", "high") for a in achados):
        saude = "🔴"
    elif achados:
        saude = "🟡"
    else:
        saude = "🟢"
    return {"saude": saude, "fatos": fatos, "achados": achados, "nao_coletado": nao_coletado}
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest tests/test_coletor_http.py -q`
Expected: `6 passed`. Se `test_http_simples_nao_gera_achado_de_certificado` falhar por causa do
achado `sem_tls`, leia o teste: ele só proíbe `certificado_vencendo` — `sem_tls` é esperado.

---

### Task 8: `lib/aceites.py` — o risco que já foi decidido

**Files:**
- Create: `scripts/lib/aceites.py`
- Modify: `scripts/collect.py` (aplicar depois das regras)
- Test: `tests/test_aceites.py`

- [x] **Step 1: Escrever os testes**

```python
# tests/test_aceites.py
from lib.aceites import aplicar

HOJE = "2026-09-19"


def achado(regra="sem_replica", alvo="banco", objeto="principal"):
    return {"regra": regra, "objeto": objeto, "severidade": "high", "alvo": alvo}


def aceite(**extra):
    base = {"alvo": "banco", "regra": "sem_replica", "motivo": "base de cache",
            "desde": "2026-01-01", "revisar_em": "2027-01-01", "origem": "projeto"}
    base.update(extra)
    return base


def test_achado_aceito_sai_dos_achados_e_vai_para_a_lista():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite()], hoje=HOJE)

    assert alvos[0]["achados"] == []
    assert aceitos[0]["regra"] == "sem_replica" and aceitos[0]["origem"] == "projeto"
    assert aceitos[0]["motivo"] == "base de cache"


def test_aceite_de_outro_alvo_nao_vale():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite(alvo="cluster")], hoje=HOJE)

    assert len(alvos[0]["achados"]) == 1 and aceitos == []


def test_aceite_vencido_nao_silencia_e_marca_o_achado():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite(revisar_em="2026-01-01")], hoje=HOJE)

    assert len(alvos[0]["achados"]) == 1
    assert alvos[0]["achados"][0]["aceite_vencido"] is True
    assert aceitos[0]["vencido"] is True


def test_aceite_sem_data_de_revisao_vale_mas_fica_marcado():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite(revisar_em=None)], hoje=HOJE)

    assert alvos[0]["achados"] == []
    assert aceitos[0]["revisar_em"] is None


def test_projeto_vence_infra_quando_os_dois_existem():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite(origem="infra", motivo="decisão de infra"),
                              aceite(origem="projeto", motivo="decisão do produto")], hoje=HOJE)

    assert len(aceitos) == 1
    assert aceitos[0]["origem"] == "projeto" and aceitos[0]["sobrepoe"] == "infra"


def test_aceite_pode_mirar_um_objeto_especifico():
    alvos = [{"nome": "banco", "achados": [achado(objeto="principal"), achado(objeto="relatorios")]}]

    aplicar(alvos, [aceite(objeto="principal")], hoje=HOJE)

    assert [a["objeto"] for a in alvos[0]["achados"]] == ["relatorios"]


def test_aceite_que_nao_casa_com_nada_e_reportado_como_obsoleto():
    alvos = [{"nome": "banco", "achados": []}]

    aceitos = aplicar(alvos, [aceite()], hoje=HOJE)

    assert aceitos[0]["obsoleto"] is True, "o problema sumiu: a justificativa não é mais necessária"


import pytest


@pytest.mark.parametrize("data", ["31/12/2026", "2026-13-01", "amanhã", ""])
def test_data_de_revisao_fora_do_formato_e_recusada(data):
    """Comparação de texto: "31/12/2026" nunca vencia e "19/09/2026" vencia sempre."""
    alvos = [{"nome": "banco", "achados": [achado()], "coletado": True}]

    with pytest.raises(ValueError):
        aplicar(alvos, [aceite(revisar_em=data)], hoje=HOJE)


def test_aceite_de_alvo_que_nao_foi_coletado_nao_vira_obsoleto():
    """Sem achados porque ninguém coletou ≠ o problema acabou. Marcar obsoleto faria o usuário
    apagar uma justificativa que continua válida."""
    alvos = [{"nome": "banco", "achados": [], "coletado": False}]

    aceitos = aplicar(alvos, [aceite()], hoje=HOJE)

    assert aceitos[0]["obsoleto"] is False


def test_aceite_sem_alvo_e_recusado():
    with pytest.raises(ValueError):
        aplicar([{"nome": "banco", "achados": [], "coletado": True}], [aceite(alvo=None)], hoje=HOJE)
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_aceites.py -q`
Expected: `ImportError: cannot import name 'aplicar' from 'lib.aceites'` — 7 falhas.

- [x] **Step 3: `scripts/lib/aceites.py`**

```python
"""Risco já decidido: sai dos achados, vai para a lista de aceites, e volta quando vence.

Aplicado DEPOIS das regras, nunca antes: se o aceite filtrasse a coleta, ninguém veria o risco
mudar de tamanho. E aceite que não casa com nada é reportado — a justificativa envelheceu junto
com o problema que ela explicava.
"""

from datetime import date

PRECEDENCIA = {"infra": 0, "projeto": 1}     # o mais específico vence


def _data(valor, onde):
    """Data ISO, sempre. Comparar texto faria "31/12/2026" nunca vencer e "19/09/2026" vencer
    sempre — silenciosamente, que é o pior jeito de errar num registro de risco aceito."""
    try:
        return date.fromisoformat(str(valor))
    except (TypeError, ValueError) as erro:
        raise ValueError(f"{onde}: data precisa ser AAAA-MM-DD, veio {valor!r}") from erro


def _casa(achado, aceite):
    if aceite.get("alvo") != achado.get("alvo") or aceite.get("regra") != achado.get("regra"):
        return False
    alvo_objeto = aceite.get("objeto")
    return alvo_objeto in (None, achado.get("objeto"))


def _vencido(aceite, hoje):
    revisar = aceite.get("revisar_em")
    if revisar is None:
        return False                        # sem data de revisão: vale, e o relatório mostra isso
    return _data(revisar, f"aceite de {aceite.get('alvo')}") < _data(hoje, "--at")


def aplicar(alvos, aceites, hoje):
    """Remove dos `alvos` os achados aceitos e devolve a lista de aceites para o relatório.

    Muta `alvos` de propósito: o achado aceito não pode continuar contando para a nota.
    """
    escolhidos = {}
    for aceite in aceites:
        if not aceite.get("alvo") or not aceite.get("regra"):
            raise ValueError(f"aceite sem alvo ou regra: {aceite}")
        chave = (aceite.get("alvo"), aceite.get("regra"), aceite.get("objeto"))
        atual = escolhidos.get(chave)
        if atual is None or PRECEDENCIA.get(aceite.get("origem"), 0) > \
                PRECEDENCIA.get(atual.get("origem"), 0):
            novo = dict(aceite)
            if atual is not None:
                novo["sobrepoe"] = atual.get("origem")
            escolhidos[chave] = novo

    auditados = {alvo.get("nome") for alvo in alvos}
    # alvo sem coleta não tem achado: marcar obsoleto faria o usuário apagar justificativa válida
    coletados = {alvo.get("nome") for alvo in alvos if alvo.get("coletado", True)}
    saida = []
    for aceite in escolhidos.values():
        # aceite de alvo que não entrou nesta auditoria não é obsoleto: apenas não se aplica hoje
        if aceite.get("alvo") not in auditados:
            continue
        vencido = _vencido(aceite, hoje)
        casou = False
        for alvo in alvos:
            restantes = []
            for achado in alvo.get("achados", []):
                if not _casa(achado, aceite):
                    restantes.append(achado)
                    continue
                casou = True
                if vencido:
                    achado["aceite_vencido"] = True
                    restantes.append(achado)
            alvo["achados"] = restantes
        saida.append({**aceite, "vencido": vencido,
                      "obsoleto": not casou and aceite["alvo"] in coletados})
    return sorted(saida, key=lambda a: (a.get("alvo") or "", a.get("regra") or ""))
```

- [x] **Step 4: Ligar no `collect.py`** — depois de coletar todos os alvos, antes de ordenar:

```python
    from lib import aceites as aceites_mod
    relatorio["aceites"] = aceites_mod.aplicar(relatorio["alvos"], cfg.aceites(),
                                               hoje=args.at[:10])
```
(substituindo a linha `relatorio["aceites"] = cfg.aceites()` da Task 5)

- [x] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde, incluindo os 7 de aceites.

- [x] **Step 6: Checkpoint do lote 3** — pausa de aprovação.

---

## Lote 4 — histórico, relatório e as restrições

### Task 9: `lib/historico.py` — o que mudou desde a última auditoria

**Files:**
- Create: `scripts/lib/historico.py`
- Modify: `scripts/collect.py` (preencher `historico`)
- Test: `tests/test_historico.py`

- [x] **Step 1: Escrever os testes**

```python
# tests/test_historico.py
import json

from lib.historico import comparar, pasta_anterior


def gravar(pasta, relatorio):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "report.json").write_text(json.dumps(relatorio), encoding="utf-8")
    return pasta


def v2(alvos):
    return {"schema_version": 2, "alvos": alvos}


def test_acha_a_execucao_anterior_pelo_nome_da_pasta(tmp_path):
    raiz = tmp_path / "docs" / "infra"
    gravar(raiz / "2026-09-18_0900", v2([]))
    gravar(raiz / "2026-09-18_1500", v2([]))
    atual = gravar(raiz / "2026-09-19_1000", v2([]))

    assert pasta_anterior(atual).name == "2026-09-18_1500"


def test_ignora_relatorio_de_schema_antigo(tmp_path):
    raiz = tmp_path / "docs" / "infra"
    gravar(raiz / "2026-09-18_0900", {"schema_version": 1, "cluster": {}})
    atual = gravar(raiz / "2026-09-19_1000", v2([]))

    assert pasta_anterior(atual) is None


def test_sem_execucao_anterior_devolve_nada(tmp_path):
    atual = gravar(tmp_path / "docs" / "infra" / "2026-09-19_1000", v2([]))

    assert pasta_anterior(atual) is None


def test_diff_usa_alvo_regra_e_objeto_como_chave(tmp_path):
    anterior = v2([{"nome": "a", "achados": [{"regra": "spof", "objeto": "web", "alvo": "a"}]},
                   {"nome": "b", "achados": [{"regra": "spof", "objeto": "web", "alvo": "b"}]}])
    atual = v2([{"nome": "a", "achados": []},
                {"nome": "b", "achados": [{"regra": "spof", "objeto": "web", "alvo": "b"},
                                          {"regra": "sem_tls", "objeto": "api", "alvo": "b"}]}])

    diff = comparar(anterior, atual, nome_anterior="2026-09-18_1500")

    assert diff["vs"] == "2026-09-18_1500"
    assert diff["resolvidos"] == ["a · spof · web"]
    assert diff["novos"] == ["b · sem_tls · api"]


def test_serviço_homonimo_em_alvos_diferentes_nao_colide(tmp_path):
    """Sem o alvo na chave, 'spof · web' de dois clusters viraria o mesmo achado."""
    anterior = v2([{"nome": "a", "achados": [{"regra": "spof", "objeto": "web", "alvo": "a"}]}])
    atual = v2([{"nome": "b", "achados": [{"regra": "spof", "objeto": "web", "alvo": "b"}]}])

    diff = comparar(anterior, atual, nome_anterior="x")

    assert diff["resolvidos"] == ["a · spof · web"]
    assert diff["novos"] == ["b · spof · web"]
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_historico.py -q`
Expected: `ImportError` de `lib.historico` — 5 falhas.

- [x] **Step 3: `scripts/lib/historico.py`**

```python
"""Diff contra a execução anterior. A chave inclui o ALVO — sem ele, dois serviços de mesmo nome
em alvos diferentes viram o mesmo achado, e o histórico mente.
"""
import json
from pathlib import Path


def _relatorio(pasta):
    arquivo = Path(pasta) / "report.json"
    if not arquivo.exists():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError, OSError):
        return None                       # pasta-irmã com lixo não pode matar a auditoria
    if not isinstance(dados, dict):
        return None
    return dados if dados.get("schema_version") == 2 else None


def pasta_anterior(pasta_atual):
    """A pasta irmã mais recente com report.json de schema 2. O layout v1 fica de fora."""
    atual = Path(pasta_atual).resolve()
    if not atual.parent.is_dir():
        return None          # primeira auditoria do projeto: a pasta ainda nem existe
    irmas = sorted(p for p in atual.parent.iterdir()
                   if p.is_dir() and p.name < atual.name and _relatorio(p) is not None)
    return irmas[-1] if irmas else None


def _chaves(relatorio):
    return {(a.get("nome"), f.get("regra"), f.get("objeto") or "")
            for a in relatorio.get("alvos", []) for f in a.get("achados", [])}


def _formatar(chaves):
    return sorted(f"{alvo} · {regra} · {objeto}" for alvo, regra, objeto in chaves)


def comparar(anterior, atual, nome_anterior):
    antes, agora = _chaves(anterior), _chaves(atual)
    return {"vs": nome_anterior,
            "resolvidos": _formatar(antes - agora),
            "novos": _formatar(agora - antes)}
```

- [x] **Step 4: Ligar no `collect.py`**, depois de montar o inventário:

```python
    if cfg.valor("historico.comparar_com_anterior"):
        from lib import historico as hist
        anterior = hist.pasta_anterior(saida)
        if anterior is not None:
            relatorio["historico"] = hist.comparar(
                json.loads((anterior / "report.json").read_text(encoding="utf-8")),
                relatorio, nome_anterior=anterior.name)
```

- [x] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde.

---

### Task 10: `build_report.py` para o v2

**Files:**
- Modify: `scripts/build_report.py`, `assets/report-template/template.html`
- Test: `tests/test_build_report_v2.py`

O template atual já é print-first e bem resolvido. O que muda é **o que entra e em que ordem**.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_build_report_v2.py
import json

import build_report


def relatorio():
    return {
        "schema_version": 2, "generated_at": "2026-09-19T10:00:00Z",
        "alvos": [
            {"nome": "cluster", "tipo": "docker", "onde": "context: ctx", "saude": "🟡",
             "dimensoes": {"seguranca": {"nota": "🟡"}}, "fatos": {}, "analise": "Traefik sozinho.",
             "achados": [{"regra": "spof", "objeto": "traefik", "severidade": "high",
                          "detalhe": "1 réplica", "alvo": "cluster"}], "nao_coletado": []},
            {"nome": "site", "tipo": "http", "onde": "https://exemplo.invalido/health",
             "saude": "sem dados", "dimensoes": {}, "fatos": {}, "achados": [], "analise": "",
             "nao_coletado": [{"valor": None, "motivo": "alvo não confirmado nesta execução"}]}],
        "inventario": [{"nome": "cluster", "tipo": "docker", "onde": "context: ctx", "saude": "🟡"},
                       {"nome": "site", "tipo": "http", "onde": "https://exemplo.invalido/health",
                        "saude": "sem dados"}],
        "aceites": [{"alvo": "cluster", "regra": "sem_backup", "motivo": "backup no provedor",
                     "desde": "2026-01-01", "revisar_em": "2027-01-01", "origem": "infra",
                     "vencido": False, "obsoleto": False}],
        "historico": {"vs": "2026-09-18_1500", "resolvidos": ["cluster · sem_tls · api"], "novos": []},
        "resumo": "Um cluster com ponto único.", "fortes": ["TLS em dia"],
        "fracos": ["Traefik sem redundância"],
        "recomendacoes": [{"alvo": "cluster", "titulo": "Subir segunda réplica do Traefik",
                           "porque": "hoje é ponto único de 17 apps",
                           "comando": "docker service update --replicas 2 traefik_traefik",
                           "impacto": "alto", "esforco": "baixo"}]}


def montar(tmp_path, dados=None, monkeypatch=None):
    """Sem Chromium: o PDF tem teste próprio, e rodar o navegador em cada teste só deixa lixo."""
    pasta = tmp_path / "2026-09-19_1000"
    pasta.mkdir(parents=True)
    (pasta / "report.json").write_text(json.dumps(dados or relatorio()), encoding="utf-8")
    original = build_report.find_chromium
    build_report.find_chromium = lambda: None
    try:
        build_report.main(["--dir", str(pasta)])
    finally:
        build_report.find_chromium = original
    return (pasta / "relatorio.html").read_text(encoding="utf-8")


def test_o_inventario_vem_antes_dos_achados(tmp_path):
    html = montar(tmp_path)

    assert html.index("Inventário") < html.index("Achados")
    assert "context: ctx" in html and "exemplo.invalido" in html


def test_nao_existe_nota_unica_da_infraestrutura(tmp_path):
    html = montar(tmp_path)

    assert "Saúde geral" not in html and "Nota geral" not in html
    assert "1 alvo sem dados" in html or "sem dados" in html


def test_alvo_sem_dados_aparece_com_o_motivo(tmp_path):
    html = montar(tmp_path)

    assert "não confirmado nesta execução" in html


def test_aceites_aparecem_com_origem_motivo_e_revisao(tmp_path):
    html = montar(tmp_path)

    assert "Riscos aceitos" in html
    assert "backup no provedor" in html and "infra" in html and "2027-01-01" in html


def test_recomendacao_traz_o_comando_pronto_e_o_alvo(tmp_path):
    html = montar(tmp_path)

    assert "docker service update --replicas 2 traefik_traefik" in html
    assert "cluster" in html


def test_mesmo_json_gera_o_mesmo_html(tmp_path):
    """Restrição 4: com as mesmas entradas, mesmos bytes."""
    um = montar(tmp_path / "a")
    dois = montar(tmp_path / "b")

    assert um == dois


def test_relatorio_v1_e_recusado_com_mensagem(tmp_path, capsys):
    pasta = tmp_path / "antigo"
    pasta.mkdir()
    (pasta / "report.json").write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    codigo = build_report.main(["--dir", str(pasta)])

    assert codigo == 2
    assert "schema" in capsys.readouterr().err


def test_texto_do_agente_nao_injeta_secao_no_relatorio(tmp_path):
    """Substituir marcador em laço reprocessa o que já foi inserido: um %%ALVOS%% escrito no
    resumo duplicaria a seção inteira."""
    dados = relatorio()
    dados["resumo"] = "tudo certo %%ALVOS%% %%HISTORICO%%"

    html = montar(tmp_path, dados)

    assert html.count("<h2>Por alvo</h2>") == 1
    assert "%%ALVOS%%" in html, "o marcador aparece como texto, não como seção"
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_build_report_v2.py -q`
Expected: falha na leitura do v2 (o build atual espera `cluster`/`nodes`) — 7 falhas.

- [x] **Step 3: Adaptar o `build_report.py`**

A montagem de dados vira esta função, e o resto do arquivo (CSS, impressão, PDF) segue igual:

```python
def montar_contexto(r):
    """Do report v2 para o que o template desenha, na ordem em que o leitor precisa."""
    if r.get("schema_version") != 2:
        raise ValueError(f"schema {r.get('schema_version')!r}: este build só lê o v2")

    por_estado = {}
    for alvo in r["alvos"]:
        por_estado[alvo["saude"]] = por_estado.get(alvo["saude"], 0) + 1

    from lib.report import achados_ordenados
    achados = achados_ordenados(r)                       # global, do mais grave ao menos
    return {
        "gerado_em": r["generated_at"],
        "panorama": {"total": len(r["alvos"]), "por_estado": por_estado,
                     "achados": len(achados), "aceitos": len(r.get("aceites") or [])},
        "inventario": r["inventario"],                      # o mapa, primeiro
        "achados": achados,                                  # ordem global por severidade
        "aceites": r.get("aceites") or [],
        "alvos": r["alvos"],                                 # detalhe, por último
        "historico": r.get("historico"),
        "resumo": r.get("resumo", ""), "fortes": r.get("fortes", []),
        "fracos": r.get("fracos", []), "recomendacoes": r.get("recomendacoes", []),
    }
```

No `main`, trocar a leitura antiga por:

```python
    try:
        contexto = montar_contexto(dados)
    except ValueError as erro:
        print(str(erro), file=sys.stderr)
        return 2
```

- [x] **Step 4: Ajustar o template**

Seções, nesta ordem: **Panorama** (contagem por estado, sem nota única) · **Inventário** (tabela:
alvo, tipo, onde, estado) · **Achados** (agrupados por severidade, com o alvo ao lado e o detalhe) ·
**Riscos aceitos** (motivo, origem, desde, revisar em; vencido em destaque) · **Recomendações**
(com o comando pronto) · **Por alvo** (dimensões, análise do agente, fatos, não coletado) ·
**Desde a auditoria anterior**.

- [x] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde.

---

### Task 11: as quatro restrições verificáveis

**Files:**
- Create: `tests/test_restricoes.py`

- [x] **Step 1: Escrever os testes**

```python
# tests/test_restricoes.py
"""As restrições do spec — o teste é a regra, não a documentação."""
import ast
import json
from pathlib import Path

import collect
from lib.coletores import http as coletor_http

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
# o runner roda comando de coleta; o build chama o Chromium para o PDF — e mais ninguém
PODEM_EXECUTAR = {"lib/runner.py", "build_report.py"}
PODEM_ABRIR_REDE = {"lib/http_get.py"}
# urllib.parse é análise de texto, não rede: quem abre socket é o de baixo
MODULOS_DE_REDE = {"socket", "ssl", "http.client", "urllib.request", "urllib.error", "requests",
                   "httpx", "ftplib", "smtplib"}


def retrato(raiz):
    return {str(p.relative_to(raiz)): (p.read_bytes() if p.is_file() else b"dir")
            for p in sorted(raiz.rglob("*"))}


def ambiente(tmp_path):
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 10\nhttp_timeout = 1\n[historico]\ncomparar_com_anterior = true\n',
        encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["site"]\n', encoding="utf-8")
    return ["--padrao", str(tmp_path / "default.toml"), "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "docs/infra/2026-09-19_1000"), "--at", "2026-09-19T10:00:00Z"]


def test_auditar_so_escreve_na_pasta_da_execucao(tmp_path, monkeypatch):
    """Restrição 1."""
    args = ambiente(tmp_path)
    (tmp_path / "docs" / "infra").mkdir(parents=True)     # o projeto já tem auditorias anteriores
    monkeypatch.chdir(tmp_path)
    antes = retrato(tmp_path)

    collect.main([*args, "--confirmar", "site"],
                 coletores={"http": coletor_http.coletar})

    mexidos = {c for c in set(antes) | set(retrato(tmp_path)) if antes.get(c) != retrato(tmp_path).get(c)}
    fora = {c for c in mexidos if not c.startswith("docs/infra/2026-09-19_1000")}
    assert fora == set(), f"escreveu fora da pasta da execução: {sorted(fora)}"


def test_alvo_nao_confirmado_nao_gera_conexao(tmp_path, monkeypatch):
    """Restrição 3: o alvo que ficou fora do --confirmar não pode gerar UMA conexão sequer.

    Confirmar a lista vazia não prova isso: ela é barrada antes do laço. Aqui um alvo é
    confirmado e outro não, e qualquer tentativa de alcançar o segundo falha o teste.
    """
    tentativas = []
    monkeypatch.setattr(coletor_http.http_get, "get_com_status",
                        lambda url, *a, **k: tentativas.append(url) or (200, ""))
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "confirmado"\ntipo = "http"\nurl = "http://127.0.0.1:1/ok"\n\n'
        '[[alvo]]\nnome = "de_fora"\ntipo = "http"\nurl = "http://127.0.0.1:2/nao"\n',
        encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["confirmado", "de_fora"]\n',
                                                   encoding="utf-8")
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 10\nhttp_timeout = 1\n[historico]\ncomparar_com_anterior = true\n',
        encoding="utf-8")
    args = ["--padrao", str(tmp_path / "default.toml"), "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "docs/infra/2026-09-19_1000"), "--at", "2026-09-19T10:00:00Z"]

    codigo = collect.main([*args, "--confirmar", "confirmado"],
                          coletores={"http": coletor_http.coletar})

    assert codigo == 0
    assert tentativas == ["http://127.0.0.1:1/ok"], f"alcançou alvo não confirmado: {tentativas}"


def test_confirmar_vazio_para_antes_de_qualquer_coleta(tmp_path, monkeypatch):
    tentativas = []
    monkeypatch.setattr(coletor_http.http_get, "get_com_status",
                        lambda url, *a, **k: tentativas.append(url) or (200, ""))

    codigo = collect.main([*ambiente(tmp_path), "--confirmar"],
                          coletores={"http": coletor_http.coletar})

    assert codigo == 2 and tentativas == []


def test_so_o_runner_cria_subprocesso():
    """Restrição 2 depende disto: com um ponto só, o espião de argv cobre tudo."""
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
            if any(str(n).split(".")[0] in {"subprocess", "multiprocessing", "pty"} for n in nomes) \
                    and relativo not in PODEM_EXECUTAR:
                culpados.append(relativo)
    assert culpados == [], f"subprocesso fora do runner: {sorted(set(culpados))}"


def test_rede_so_nos_modulos_de_rede():
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
            if any(str(n) in MODULOS_DE_REDE or str(n).split(".")[0] in {"socket", "ssl"}
                   for n in nomes) and relativo not in PODEM_ABRIR_REDE:
                culpados.append(f"{relativo}: {nomes}")
    assert culpados == [], f"rede fora dos módulos de rede: {sorted(set(culpados))}"


def test_nenhum_segredo_chega_ao_relatorio(tmp_path, monkeypatch):
    """Restrição 2: a senha não aparece no report.json, no HTML, nem no argv de nenhum comando."""
    import build_report
    from lib import runner

    argv_vistos = []
    monkeypatch.setattr(runner, "run",
                        lambda cmd, timeout, errors=None, tipo="docker":
                        argv_vistos.append(list(cmd)) or "")
    monkeypatch.setenv("SENHA_DO_ALVO", "trocadilho-secreto")
    monkeypatch.setattr(coletor_http.http_get, "get_com_status", lambda *a, **k: (200, ""))
    args = ambiente(tmp_path)
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["site"]\n', encoding="utf-8")

    collect.main([*args, "--confirmar", "site"], coletores={"http": coletor_http.coletar})
    pasta = tmp_path / "docs/infra/2026-09-19_1000"
    monkeypatch.setattr(build_report, "find_chromium", lambda: None)
    build_report.main(["--dir", str(pasta)])

    corpo = (pasta / "report.json").read_text(encoding="utf-8") + \
        (pasta / "relatorio.html").read_text(encoding="utf-8")
    assert "trocadilho-secreto" not in corpo
    assert all("trocadilho-secreto" not in " ".join(cmd) for cmd in argv_vistos)


def test_mesmo_relatorio_com_as_mesmas_entradas(tmp_path, monkeypatch):
    """Restrição 4: byte a byte, sem normalizar nada na comparação."""
    monkeypatch.chdir(tmp_path)
    saida = []
    for rodada in ("a", "b"):
        (tmp_path / rodada).mkdir()
        args = ambiente(tmp_path / rodada)
        collect.main([*args, "--confirmar", "site"], coletores={"http": coletor_http.coletar})
        saida.append((tmp_path / rodada / "docs/infra/2026-09-19_1000" / "report.json").read_bytes())

    assert saida[0] == saida[1]
```

- [x] **Step 2: Rodar**

Run: `.venv/bin/python -m pytest tests/test_restricoes.py -q`
Expected: `5 passed`

- [x] **Step 3: Provar por mutação** — três ataques, um de cada vez, desfazendo depois:

1. No `collect.py`, escreva um arquivo qualquer na raiz do projeto antes de gravar o relatório →
   `test_auditar_so_escreve_na_pasta_da_execucao` falha.
2. No `collect.py`, ignore `--confirmar` e colete todos → `test_alvo_nao_confirmado_nao_gera_conexao` falha.
3. Em `lib/aceites.py`, acrescente `import subprocess` → `test_so_o_runner_cria_subprocesso` falha.

Expected: cada ataque derruba exatamente o teste correspondente, e a suíte volta verde ao desfazer.
Se algum não derrubar, **o teste é falso** — conserte antes de seguir.

- [x] **Step 4: Checkpoint do lote 4** — pausa de aprovação.

---

## Lote 5 — modo configurar, SKILL.md e publicação

### Task 12: `configurar.py` ganha `migrar`, `aceitar` e o ignore

**Files:**
- Modify: `scripts/configurar.py`
- Test: `tests/test_configurar_escrita.py`

Este é o **único** script que escreve fora do relatório — e por isso ele nunca sobrescreve o que
você já tem.

- [x] **Step 1: Escrever os testes**

```python
# tests/test_configurar_escrita.py
import configurar


def test_migrar_escreve_o_primeiro_alvos_toml_a_partir_dos_contexts(tmp_path, monkeypatch):
    monkeypatch.setattr(configurar, "contexts_docker",
                        lambda: [{"nome": "prod", "endpoint": "tcp://198.51.100.10:2376"},
                                 {"nome": "local", "endpoint": "unix:///var/run/docker.sock"}])
    destino = tmp_path / "alvos.toml"

    codigo = configurar.main(["migrar", "--infra", str(destino)])
    texto = destino.read_text(encoding="utf-8")

    assert codigo == 0
    assert 'nome = "prod"' in texto and 'tipo = "docker"' in texto
    assert 'context = "prod"' in texto
    assert oct(destino.stat().st_mode)[-3:] == "600"


def test_migrar_nunca_sobrescreve_o_que_ja_existe(tmp_path, capsys):
    destino = tmp_path / "alvos.toml"
    destino.write_text('[[alvo]]\nnome = "meu"\ntipo = "docker"\ncontext = "ctx"\n', encoding="utf-8")

    codigo = configurar.main(["migrar", "--infra", str(destino)])

    assert codigo == 2
    assert destino.read_text(encoding="utf-8").count("[[alvo]]") == 1
    assert "já existe" in capsys.readouterr().err


def test_aceitar_acrescenta_no_arquivo_do_projeto_com_as_datas(tmp_path):
    projeto = tmp_path / ".sw-infra-audit.toml"
    projeto.write_text('alvos = ["cluster"]\n', encoding="utf-8")

    codigo = configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "cluster",
                              "--regra", "spof", "--motivo", "failover manual assumido",
                              "--desde", "2026-09-19", "--meses", "6"])
    texto = projeto.read_text(encoding="utf-8")

    assert codigo == 0
    assert "[[aceite]]" in texto and "failover manual assumido" in texto
    assert 'revisar_em = "2027-03-19"' in texto
    assert 'alvos = ["cluster"]' in texto, "o que já estava no arquivo continua lá"


def test_aceitar_recusa_motivo_vazio(tmp_path, capsys):
    projeto = tmp_path / ".sw-infra-audit.toml"
    projeto.write_text("alvos = []\n", encoding="utf-8")

    codigo = configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "x",
                              "--regra", "y", "--motivo", "   "])

    assert codigo == 2
    assert "motivo" in capsys.readouterr().err
    assert "[[aceite]]" not in projeto.read_text(encoding="utf-8")


def test_sugerir_propoe_metricas_url_sem_alcancar_host(tmp_path, monkeypatch):
    """A descoberta só PROPÕE: quem alcança host é o coletor, e só depois de declarado."""
    tentativas = []
    import socket as socket_mod
    monkeypatch.setattr(socket_mod, "create_connection",
                        lambda *a, **k: tentativas.append(a))
    monkeypatch.setattr(configurar, "candidatos_de_metricas",
                        lambda context: [{"url": "http://198.51.100.10:9090/metrics",
                                          "por_que": "prometheus publicado na porta 9090"}])

    codigo = configurar.main(["alvos", "--sugerir", "--context", "prod"])

    assert codigo == 0 and tentativas == []


def test_ignorar_acrescenta_a_pasta_no_gitignore_uma_vez_so(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    configurar.main(["ignorar", "--repo", str(tmp_path), "--pasta", "docs/infra"])
    configurar.main(["ignorar", "--repo", str(tmp_path), "--pasta", "docs/infra"])
    texto = (tmp_path / ".gitignore").read_text(encoding="utf-8")

    assert texto.count("docs/infra/") == 1
    assert "node_modules/" in texto
```

- [x] **Step 2: Rodar e ver vermelho**

Run: `.venv/bin/python -m pytest tests/test_configurar_escrita.py -q`
Expected: `invalid choice: 'migrar'` — 5 falhas.

- [x] **Step 3: Acrescentar ao `configurar.py`**

```python
from datetime import date
from lib.runner import run


def contexts_docker():
    """Lista os contexts para a migração. Só leitura, pelo runner."""
    import json as _json
    saida = run(["docker", "context", "ls", "--format", "{{json .}}"], timeout=10)
    achados = []
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        dados = _json.loads(linha)
        achados.append({"nome": dados.get("Name"), "endpoint": dados.get("DockerEndpoint", "")})
    return achados


def migrar(args) -> int:
    destino = Path(args.infra) if args.infra else INFRA_PADRAO
    if destino.exists():
        print(f"{destino} já existe — não sobrescrevo. Acrescente os alvos à mão, ou aponte "
              f"--infra para outro caminho.", file=sys.stderr)
        return EXIT_ERRO
    linhas = ["# Alvos da sw-infra-audit. Este arquivo fica FORA de qualquer repositório.",
              "# A senha nunca vem aqui: declare o NOME da variável de ambiente em senha_env.", ""]
    for ctx in contexts_docker():
        linhas += ["[[alvo]]", f'nome = "{ctx["nome"]}"', 'tipo = "docker"',
                   f'context = "{ctx["nome"]}"',
                   "# metricas_url = \"http://host:9090\"   # opcional; veja `alvos --sugerir`", ""]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas), encoding="utf-8")
    destino.chmod(0o600)
    print(f"{destino} criado com {len(contexts_docker())} alvo(s) docker. Revise antes de auditar.")
    return EXIT_OK


def aceitar(args) -> int:
    if not (args.motivo or "").strip():
        print("aceitar exige --motivo: aceite sem justificativa é achado escondido.", file=sys.stderr)
        return EXIT_ERRO
    projeto = Path(args.projeto) if args.projeto else PROJETO_PADRAO
    desde = args.desde or date.today().isoformat()
    ano, mes, dia = (int(p) for p in desde.split("-"))
    mes_final = mes + args.meses
    revisar = f"{ano + (mes_final - 1) // 12:04d}-{(mes_final - 1) % 12 + 1:02d}-{dia:02d}"
    bloco = ["", "[[aceite]]", f'alvo = "{args.alvo}"', f'regra = "{args.regra}"',
             f'motivo = "{args.motivo.strip()}"', f'desde = "{desde}"', f'revisar_em = "{revisar}"']
    if args.objeto:
        bloco.insert(3, f'objeto = "{args.objeto}"')
    atual = projeto.read_text(encoding="utf-8") if projeto.exists() else ""
    projeto.write_text(atual.rstrip("\n") + "\n" + "\n".join(bloco) + "\n", encoding="utf-8")
    print(f"aceite registrado em {projeto} · revisar em {revisar}")
    return EXIT_OK


def candidatos_de_metricas(context):
    """Usa a descoberta que já existe para PROPOR uma `metricas_url` — sem alcançar host nenhum."""
    from lib import discover
    from lib.coletores.docker import assemble_report
    bruto = assemble_report(run_fn=lambda cmd, timeout, errors=None: run(cmd, timeout, errors),
                            timeout=10, context=context, generated_at="", connected_node=None,
                            metrics_url=None)
    host = discover.host_from_context_endpoint((bruto.get("scope") or {}).get("endpoint", ""))
    return discover.propose(bruto, host)


def sugerir(args) -> int:
    achados = candidatos_de_metricas(args.context)
    if not achados:
        print("nenhum candidato a métricas encontrado neste context")
        return EXIT_OK
    print("candidatos para `metricas_url` (cole no alvos.toml o que fizer sentido):")
    for candidato in achados:
        print(f"  {candidato['url']:<48} {candidato['por_que']}")
    return EXIT_OK


def ignorar(args) -> int:
    """Põe a pasta do relatório no .gitignore. É escrita em arquivo versionado: por isso mora aqui,
    no modo configurar, e não no modo auditar."""
    repo = Path(args.repo)
    linha = args.pasta.rstrip("/") + "/"
    gi = repo / ".gitignore"
    atual = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if linha in atual.splitlines():
        print(f"{linha} já está no .gitignore")
        return EXIT_OK
    gi.write_text(atual.rstrip("\n") + ("\n" if atual else "") + linha + "\n", encoding="utf-8")
    print(f"{linha} acrescentado ao .gitignore")
    return EXIT_OK
```

E no `main`, os subcomandos novos:

```python
    mig = sub.add_parser("migrar", help="cria o primeiro alvos.toml a partir dos contexts docker")
    mig.add_argument("--infra", default=None)

    ace = sub.add_parser("aceitar", help="registra um risco aceito no arquivo do projeto")
    ace.add_argument("--projeto", default=None)
    ace.add_argument("--alvo", required=True)
    ace.add_argument("--regra", required=True)
    ace.add_argument("--objeto", default=None)
    ace.add_argument("--motivo", required=True)
    ace.add_argument("--desde", default=None)
    ace.add_argument("--meses", type=int, default=6, help="prazo até a revisão (padrão: 6 meses)")

    alv = sub.add_parser("alvos", help="inspecionar e propor valores para os alvos")
    alv.add_argument("--sugerir", action="store_true", required=True)
    alv.add_argument("--context", required=True, help="context docker de onde partir")

    ign = sub.add_parser("ignorar", help="põe a pasta do relatório no .gitignore")
    ign.add_argument("--repo", default=".")
    ign.add_argument("--pasta", default="docs/infra")

    args = ap.parse_args(argv)
    return {"config": explicar, "migrar": migrar, "aceitar": aceitar, "alvos": sugerir,
            "ignorar": ignorar}[args.comando](args)
```

- [x] **Step 4: Rodar**

Run: `.venv/bin/python -m pytest -q`
Expected: tudo verde.

---

### Task 13: `SKILL.md`

**Files:**
- Modify: `~/.claude/skills/sw-infra-audit/SKILL.md`

- [x] **Step 1: Reescrever o `SKILL.md`**

Estrutura: frontmatter (`name: sw-infra-audit`, description com gatilhos em português — "audita
minha infra", "como está o cluster", "meu banco está saudável", "relatório da infraestrutura",
"o que pode cair" — e o limite explícito de que **não** altera nada) · Garantias · Antes de tudo
(configuração e `config --explicar`) · Fluxo do modo auditar (1. ler config e alvos · 2. **menu de
confirmação com todos os alvos, nome, tipo e onde** · 3. `collect.py --confirmar` · 4. escrever
`resumo`, `fortes`, `fracos`, `recomendacoes` e o `analise` de cada alvo · 5. `build_report.py` ·
6. informar) · Modo configurar · Aceites · Limites.

Regras que o texto precisa deixar explícitas:
- **O agente não inventa achado.** Achado nasce de regra; o agente interpreta o que está lá.
- **Confirmação é obrigatória** e mostra nome, tipo e onde de cada alvo antes de conectar.
- **"Sem dados" não é verde.** Dimensão sem fato aparece como tal, e o resumo diz o que faltou.
- **Recomendação vem com comando pronto** e amarrada a um alvo.
- Achado repetido que já tem aceite → orientar o `configurar.py aceitar`, em vez de repetir no texto.

- [x] **Step 2: Conferir o frontmatter e o tamanho**

Run: `head -3 SKILL.md && wc -l SKILL.md`
Expected: `---` / `name: sw-infra-audit` / `description: >-`, e o arquivo abaixo de 220 linhas
(o que passar disso vai para `references/`).

---

### Task 14: validação real, publicação e remoção da antiga

- [x] **Step 1: Validar em infraestrutura de verdade, começando pelo que já funcionava**

Rode `configurar.py migrar`, revise o `alvos.toml` à mão, e audite **só o alvo docker**,
comparando com a última auditoria v1 do mesmo cluster: os achados precisam bater. Divergência é
regressão — pare e diagnostique.

- [x] **Step 2: Acrescentar um alvo HTTP e auditar os dois**

Confira: o menu lista os dois alvos; o relatório abre pelo inventário; o alvo não confirmado
aparece como "sem dados"; a validade do certificado bate com o que o navegador mostra.

- [x] **Step 3: Registrar um aceite e rodar de novo**

`configurar.py aceitar --alvo <nome> --regra <regra> --motivo "..."`, audite de novo e confira: o
achado saiu dos achados, entrou em "Riscos aceitos" com origem e data, e a nota do alvo melhorou.

- [x] **Step 4: Anotar divergências** no chat, **não** no dossiê (nada de host, IP ou usuário real).

- [x] **Step 5: Publicar e remover a antiga**

```bash
cd ~/.claude/skills/sw-infra-audit && .venv/bin/python -m pytest -q
cd /var/www/ai-marketplace
make sync SKILL=sw-infra-audit CATEGORY=development
find plugins/sw-infra-audit \( -name .venv -o -name __pycache__ -o -name .pytest_cache \) | wc -l   # 0
make remove SKILL=sw-cluster-audit
```

- [x] **Step 6: `CHANGELOG.md`** — em `### Adicionado`, a entrada da skill nova; em `### Removido`
(criar a seção se não existir), a saída da antiga apontando a substituta e dizendo que o
`report.json` v1 não é lido pelo v2.

- [x] **Step 7: Gate e checkpoint com commit** — `make check`, e perguntar "Commitar agora?".
**Push só com aprovação explícita.**

- [x] **Step 8: Fechar o dossiê do plano 1**

Run: `cd /var/www/ai-marketplace && python3 ~/.claude/skills/sw-brainstorming/scripts/dossie.py estado 2026-09-19-sw-infra-audit-auditoria-de-infraestrutura-por-alvos concluido`
Expected: `→ concluido`. O **Plano 2** (coletor de banco) abre seu próprio dossiê.

---

## Contagem esperada de testes por task

| Task | Arquivo | Testes |
|---|---|---|
| 0 | (baseline herdado da sw-cluster-audit) | anotar na execução |
| 1 | `test_config.py` | 12 |
| 2 | `test_alvos.py` | 9 |
| 3 | `test_configurar.py` | 4 |
| 4 | `test_report_v2.py` | 11 |
| 5 | `test_collect_orquestrador.py` | 20 |
| 6 | `test_coletor_docker.py` + herdados repontados | 5 + 15 |
| 7 | `test_coletor_http.py` | 8 |
| 8 | `test_aceites.py` | 7 |
| 9 | `test_historico.py` | 5 |
| 10 | `test_build_report_v2.py` | 7 |
| 11 | `test_restricoes.py` | 6 |
| 12 | `test_configurar_escrita.py` | 6 |
| | **Novos neste plano** | **80** |
| | *Verificado: baseline 155 · lote 1 → 199 · lote 2 → 207 · lote 3 → 257 · lote 4 → 275* | |

Se a contagem real divergir, **atualize esta tabela** — ela é o alarme de teste sumido.

## O que a validação real encontrou (e nenhum teste pegou)

Três defeitos só apareceram rodando contra um cluster de verdade. Os dois primeiros passavam por
toda a suíte porque os testes usavam coletores falsos e exemplos inventados.

| Defeito | Por que a suíte não pegou | Correção |
|---|---|---|
| **O registro de coletores nunca foi ligado**: pela linha de comando, todo alvo respondia "tipo sem coletor nesta versão" | Todo teste passava `coletores=` explicitamente | `coletores_padrao()` no `collect.py`, com teste que roda `main` **sem** passar registro |
| **Os comandos rodavam no docker local, não no context do alvo** — o relatório sairia etiquetado com o nome do cluster errado | O `assemble_report` era sempre simulado; ninguém checava o ambiente do processo filho | `run(..., context=...)` põe `DOCKER_CONTEXT` no ambiente **do filho**; teste espiona o env do subprocesso |
| **O mapeamento dos achados estava errado**: `rule`/`severity` em vez de `rule_id`/`severity` do v1, e `med` não existe no vocabulário do v2 | O exemplo do teste tinha a forma que eu **supus**, não a real | Mapeamento corrigido e tradução `crit/med` → `critical/medium`, com o exemplo do teste copiado de um achado real |

**Comparação com a auditoria v1 do mesmo cluster:** 4 nós, 57 serviços e saúde verde nos dois.
A v1 tinha 236 achados e a v2 tem 212 — a diferença são os achados derivados de métricas, que só
aparecem quando o alvo declara `metricas_url`.

