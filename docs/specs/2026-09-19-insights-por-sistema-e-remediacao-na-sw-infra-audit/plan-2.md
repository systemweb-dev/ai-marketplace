# Plano 2 — aplicações que falam HTTP (`admin_http` + papel `fila`)

> **Execucao:** Implementar este plano task-by-task. Steps usam checkbox (`- [ ]`) para tracking. Ver secao "Execution Handoff" da skill `sw-plan` para os 2 modos de execucao disponiveis.

Spec: [spec.md](spec.md) · Plano 1 (concluído, v0.8.0): [plan.md](plan.md)

**Goal:** Fazer a auditoria responder o que há dentro de uma aplicação que expõe API de administração — começando pelo pedido central do dono, *"no rabbitmq pegar as filas"* — sem que o nome do produto apareça no código.

**Architecture:** Um adaptador `admin_http` (prioridade 20, mais específico que o `promql` de 30) que não conhece produto nenhum: ele carrega `references/apis/<familia>.toml`, identifica a família pelo que o JSON de `/api/overview` contém, e extrai resposta por uma **linguagem fechada** (JSON pointer + campos + transformações + derivações declaradas). Limiar declarado no catálogo vira achado com regra própria — é a primeira vez na skill que uma resposta de insight vira achado, porque o campo `limiar` existe no registro de perguntas desde o plano 1 e **nada nunca o avaliou**.

**Tech Stack:** Python 3.13 (stdlib apenas: `tomllib`, `json`, `base64`, `urllib` via `lib/http_get.py`), pytest. A skill vive em `~/.claude/skills/sw-infra-audit` (venv em `.venv`) e é publicada com `make sync SKILL=sw-infra-audit BUMP=minor` a partir de `/var/www/ai-marketplace`.

---

## Decisões tomadas antes das tasks

| Decisão | Escolha | Por quê |
|---|---|---|
| Branch | continuar no `master` | mesma rotina dos planos anteriores; commit por batch, push só com aprovação do dono |
| Tipos de teste | **unit** | sem servidor HTTP de verdade na suíte: os testes atravessam `lib/http_get.py` substituindo o *opener*, que é onde a rede realmente acontece. Mais rápido e determinístico que subir socket |
| Credencial na requisição | `http_get.get_autenticado()` | mantém `get()`/`get_com_status()` anônimos e concentra a superfície autenticada numa função só, fácil de auditar |
| Perguntas do papel `fila` | as 5 do spec | todas saem do mesmo `/api/queues`; o custo marginal de cada uma é uma extração, não uma requisição |

**Fora de escopo, explicitamente:** papel `cache` (Redis e memcached não têm API HTTP de administração — o spec corta de propósito), adaptador `sql` (plano 3), `logql` e as perguntas de `entrada` que dependem de rota (plano 4), papéis `busca`, `storage`, `observabilidade` e `app`.

## O repositório é público

Nada de host, IP, domínio, nome de projeto real ou caminho do home no código, nos testes, nas fixtures ou nas mensagens de commit. Fixtures usam `exemplo.test` e IPs de TEST-NET (`203.0.113.0/24`). Antes de cada commit: `make check` a partir de `/var/www/ai-marketplace`.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `scripts/lib/http_get.py` *(modificar)* | ganha `get_autenticado()`; continua o único ponto de rede |
| `scripts/lib/credencial.py` *(criar)* | lê a senha do ambiente pelo `senha_env`, amarra a (alvo, host, porta) e não deixa vazar no `repr` |
| `scripts/lib/extracao.py` *(criar)* | a linguagem fechada: JSON pointer, `campos`, `transformar`, `derivar`, `ordenar_por`, `limite` |
| `scripts/lib/limiar.py` *(criar)* | parser próprio da expressão de limiar (sem `eval`) e a avaliação item a item |
| `scripts/lib/catalogo_api.py` *(criar)* | carrega e valida `references/apis/<familia>.toml` |
| `scripts/lib/adaptadores/admin_http.py` *(criar)* | o adaptador: identificação da família + `perguntar()` |
| `scripts/lib/adaptadores/__init__.py` *(modificar)* | registra `admin_http` com prioridade 20 |
| `scripts/lib/perguntas.py` *(modificar)* | as 4 perguntas do papel `fila` |
| `scripts/lib/regras.py` *(modificar)* | a regra `fila_sem_consumidor` |
| `scripts/collect.py` *(modificar)* | avalia o limiar da resposta e escreve em `componente["achados"]` |
| `references/apis/amqp-mgmt.toml` *(criar)* | o conhecimento de produto, em arquivo |
| `references/remediacao/fila_sem_consumidor.md` *(criar)* | os 4 blocos obrigatórios |

## Comandos

```bash
cd ~/.claude/skills/sw-infra-audit
.venv/bin/python -m pytest -q                      # suíte inteira (471 testes hoje)
.venv/bin/python -m pytest tests/test_X.py -q      # um arquivo
```

---

## Task 1: `get_autenticado()` — a única porta autenticada

**Files:**
- Modify: `scripts/lib/http_get.py`
- Test: `tests/test_http_autenticado.py`

O `http_get` hoje diz, no próprio docstring, *"sem credenciais/headers de auth"*. Isso vale para `get()` e `get_com_status()` e continua valendo — a função nova é a exceção declarada, e é a única.

- [x] **Step 1: Escrever os testes que falham**

```python
# tests/test_http_autenticado.py
"""A única porta autenticada da skill.

`get()` e `get_com_status()` continuam anônimos: quem precisa de credencial usa esta função, e
é só ela que um revisor precisa ler para saber por onde segredo sai da máquina.
"""
import base64
import urllib.error

import pytest

from lib import http_get

PERMITIDOS = [("exemplo.test", 15672)]


class _Resposta:
    status = 200

    def __init__(self, corpo=b'{"ok":true}'):
        self._corpo = corpo

    def read(self, _n):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def capturado(monkeypatch):
    """Captura o Request que chegaria na rede, sem abrir socket nenhum."""
    vistos = []

    def abrir(req, timeout=None):
        vistos.append(req)
        return _Resposta()

    monkeypatch.setattr(http_get._OPENER, "open", abrir)
    return vistos


def test_monta_o_header_basic_a_partir_do_par(capturado):
    http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                             ("leitor", "senha-secreta"))

    esperado = base64.b64encode(b"leitor:senha-secreta").decode("ascii")
    assert capturado[0].get_header("Authorization") == f"Basic {esperado}"


def test_sem_credencial_nao_manda_header(capturado):
    http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS, None)

    assert capturado[0].get_header("Authorization") is None


def test_a_senha_nunca_aparece_na_url(capturado):
    http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                             ("leitor", "senha-secreta"))

    assert "senha-secreta" not in capturado[0].full_url


def test_url_com_userinfo_e_recusada():
    """`https://user:senha@host/` passaria no check_allowed (urlparse tira o userinfo do
    hostname) e colocaria a senha na URL — que é exatamente o que esta função existe para
    evitar."""
    with pytest.raises(http_get.NotConfirmed):
        http_get.get_autenticado("http://leitor:senha@exemplo.test:15672/api/overview",
                                 PERMITIDOS, ("leitor", "senha"))


def test_destino_fora_da_allowlist_levanta():
    with pytest.raises(http_get.NotConfirmed):
        http_get.get_autenticado("http://outro.test:15672/api/overview", PERMITIDOS,
                                 ("leitor", "senha"))


def test_porta_diferente_do_mesmo_host_nao_passa():
    """Host declarado não autoriza porta não declarada — senão a coleta vira varredura."""
    with pytest.raises(http_get.NotConfirmed):
        http_get.get_autenticado("http://exemplo.test:5672/api/overview", PERMITIDOS,
                                 ("leitor", "senha"))


def test_devolve_status_e_corpo(capturado):
    status, corpo = http_get.get_autenticado("http://exemplo.test:15672/api/overview",
                                             PERMITIDOS, ("leitor", "senha"))

    assert (status, corpo) == (200, '{"ok":true}')


def test_401_volta_como_status_nao_como_excecao(monkeypatch):
    """401 é informação: quer dizer "a família é essa, falta credencial"."""
    def abrir(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(http_get._OPENER, "open", abrir)

    assert http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                                    ("leitor", "senha")) == (401, "")


def test_inalcancavel_volta_none(monkeypatch):
    def abrir(req, timeout=None):
        raise urllib.error.URLError("sem rota")

    monkeypatch.setattr(http_get._OPENER, "open", abrir)

    assert http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                                    ("leitor", "senha")) == (None, None)
```

- [x] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_http_autenticado.py -q`
Expected: FAIL — `AttributeError: module 'lib.http_get' has no attribute 'get_autenticado'`

- [x] **Step 3: Implementar**

Em `scripts/lib/http_get.py`, acrescentar o import no topo:

```python
import base64
```

E, logo depois de `get_com_status`, a função:

```python
def get_autenticado(url, allowed_hosts, credencial, timeout=DEFAULT_TIMEOUT):
    """GET com credencial — a ÚNICA função desta skill que manda header de autenticação.

    `get()` e `get_com_status()` continuam anônimos de propósito: concentrar o segredo aqui é o
    que faz "por onde sai credencial?" ser uma pergunta com uma resposta só.

    A senha entra em header, nunca na URL: URL vai para log de servidor, para histórico de
    proxy e para mensagem de erro. Por isso `userinfo` na URL é recusado em vez de ignorado —
    `urlparse().hostname` descarta o `user:senha@`, então `check_allowed` aprovaria sem ver.

    `credencial` é o par `(usuario, senha)` ou None. Devolve `(status, corpo)`, com
    `(None, None)` quando não deu para alcançar — 401 volta como status, porque "a família é
    essa, falta credencial" é informação, não falha.
    """
    if "@" in urlparse(url or "").netloc:
        raise NotConfirmed("credencial não vai na URL; use o parâmetro `credencial`")
    check_allowed(url, allowed_hosts)
    req = urllib.request.Request(url, method="GET")
    if credencial:
        usuario, senha = credencial
        cru = f"{usuario}:{senha}".encode("utf-8")
        req.add_header("Authorization", "Basic " + base64.b64encode(cru).decode("ascii"))
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read(MAX_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as erro:
        return erro.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return None, None
```

Atualizar o docstring do módulo, trocando a linha `- sem credenciais/headers de auth, sem cookies;` por:

```
  - sem cookies; e sem credencial, EXCETO em `get_autenticado`, que é a única porta
    autenticada e nunca aceita credencial embutida na URL;
```

- [x] **Step 4: Rodar e confirmar verde**

Run: `.venv/bin/python -m pytest tests/test_http_autenticado.py -q`
Expected: PASS (9 testes)

- [x] **Step 5: Prova por mutação**

Cada uma tem que derrubar teste. Aplique, rode, confirme o vermelho, desfaça:

| Mutação | Teste que precisa cair |
|---|---|
| remover o `if "@" in urlparse(...)` | `test_url_com_userinfo_e_recusada` |
| trocar o header por `url.replace("://", f"://{usuario}:{senha}@")` | `test_a_senha_nunca_aparece_na_url` |
| mandar header mesmo com `credencial=None` | `test_sem_credencial_nao_manda_header` |

- [x] **Step 6: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 471 + 9 = 480

- [x] **Step 7: Commit**

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): get_autenticado e a unica porta com credencial"
```

---

## Task 2: `lib/credencial.py` — a senha sai do ambiente e não vaza

**Files:**
- Create: `scripts/lib/credencial.py`
- Test: `tests/test_credencial.py`

O `alvos.toml` já aceita `senha_env` no componente (veio do plano 1). O valor **nunca** está no arquivo: `senha_env` é o **nome** da variável de ambiente.

- [x] **Step 1: Escrever os testes que falham**

```python
# tests/test_credencial.py
"""A senha vem do ambiente e morre no header.

O `alvos.toml` guarda o NOME da variável (`senha_env`), nunca o valor — o arquivo vive fora do
git com permissão 600, mas "fora do git" não é o mesmo que "seguro de imprimir".

A credencial é amarrada a (alvo, host, porta). Não existe credencial "da rodada": um alvo com
dois componentes autenticados não pode ter a senha de um usada no outro por descuido de código.
"""
import pytest

from lib.credencial import Credencial, CredencialFaltando, de_componente

COMPONENTE = {"nome": "broker", "papel": "fila",
              "admin_url": "http://exemplo.test:15672", "senha_env": "SENHA_BROKER"}


def test_le_a_senha_da_variavel_nomeada():
    cred = de_componente(COMPONENTE, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    assert cred.par() == ("guest", "abre-te")


def test_usuario_pode_vir_declarado():
    componente = dict(COMPONENTE, usuario="leitor")

    cred = de_componente(componente, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    assert cred.par() == ("leitor", "abre-te")


def test_variavel_ausente_levanta_com_o_nome_dela():
    """A mensagem precisa dizer QUAL variável exportar — senão o dono adivinha."""
    with pytest.raises(CredencialFaltando) as erro:
        de_componente(COMPONENTE, alvo="prod", ambiente={})

    assert "SENHA_BROKER" in str(erro.value)


def test_sem_senha_env_nao_ha_credencial():
    componente = {"nome": "broker", "admin_url": "http://exemplo.test:15672"}

    assert de_componente(componente, alvo="prod", ambiente={}) is None


def test_repr_nao_mostra_a_senha():
    """`repr` aparece em traceback, em log e em mensagem de teste que falhou."""
    cred = de_componente(COMPONENTE, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    assert "abre-te" not in repr(cred)
    assert "abre-te" not in str(cred)


def test_a_credencial_so_serve_para_o_destino_dela():
    """Amarrada a (alvo, host, porta): pedir o par para outro destino devolve None em vez de
    mandar a senha do broker para a primeira URL que aparecer."""
    cred = de_componente(COMPONENTE, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    assert cred.para("http://exemplo.test:15672/api/queues") == ("guest", "abre-te")
    assert cred.para("http://exemplo.test:9090/api/queues") is None
    assert cred.para("http://outro.test:15672/api/queues") is None


def test_credencial_nao_entra_em_json():
    """Se um dia alguém puser a credencial dentro do report, o serializador tem que recusar."""
    import json

    cred = de_componente(COMPONENTE, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    with pytest.raises(TypeError):
        json.dumps({"cred": cred})


def test_admin_url_sem_porta_usa_a_do_esquema():
    componente = dict(COMPONENTE, admin_url="https://exemplo.test")

    cred = de_componente(componente, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    assert cred.para("https://exemplo.test/api/queues") == ("guest", "abre-te")


def test_dois_componentes_do_mesmo_alvo_tem_credenciais_separadas():
    a = de_componente(COMPONENTE, alvo="prod", ambiente={"SENHA_BROKER": "um"})
    b = de_componente(dict(COMPONENTE, nome="outro", senha_env="SENHA_OUTRO",
                           admin_url="http://exemplo.test:15673"),
                      alvo="prod", ambiente={"SENHA_OUTRO": "dois"})

    assert a.para("http://exemplo.test:15673/x") is None
    assert b.para("http://exemplo.test:15673/x") == ("guest", "dois")


def test_e_uma_credencial():
    cred = de_componente(COMPONENTE, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    assert isinstance(cred, Credencial)
```

- [x] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_credencial.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.credencial'`

- [x] **Step 3: Implementar**

```python
# scripts/lib/credencial.py
"""A senha sai do ambiente, entra num header e não aparece em mais lugar nenhum.

O `alvos.toml` declara `senha_env = "NOME_DA_VARIAVEL"` — o NOME, nunca o valor. O arquivo vive
fora do git com permissão 600, mas "fora do git" não é o mesmo que "seguro de imprimir": basta
um traceback para o conteúdo dele virar log.

A credencial é amarrada a **(alvo, host, porta)**, e `para(url)` recusa qualquer outro destino.
Não existe credencial "da rodada": num alvo com dois componentes autenticados, a senha de um
não pode ir parar na requisição do outro por descuido de código.
"""
import os

from lib import http_get

USUARIO_PADRAO = "guest"


class CredencialFaltando(Exception):
    """`senha_env` declarado, variável ausente no ambiente."""


class Credencial:
    """Amarrada a (alvo, host, porta). Não serializa e não se imprime."""

    __slots__ = ("alvo", "componente", "usuario", "_senha", "_destino")

    def __init__(self, alvo, componente, usuario, senha, destino):
        self.alvo = alvo
        self.componente = componente
        self.usuario = usuario
        self._senha = senha
        self._destino = destino

    def par(self):
        """O `(usuario, senha)` que `http_get.get_autenticado` espera."""
        return (self.usuario, self._senha)

    def para(self, url):
        """O par, se a URL for o destino desta credencial. None em qualquer outro caso."""
        return self.par() if http_get.destino(url) == self._destino else None

    def __repr__(self):
        host, porta = self._destino
        return f"<Credencial {self.usuario}@{host}:{porta} alvo={self.alvo!r}>"

    __str__ = __repr__


def de_componente(componente, alvo, ambiente=None):
    """A credencial de um componente, ou None quando ele não declara `senha_env`.

    Componente sem `senha_env` não é erro: a API pode ser aberta em rede interna, e o adaptador
    tenta sem credencial e lida com o 401.
    """
    nome_da_variavel = componente.get("senha_env")
    if not nome_da_variavel:
        return None
    ambiente = os.environ if ambiente is None else ambiente
    if nome_da_variavel not in ambiente:
        raise CredencialFaltando(
            f"o componente {componente.get('nome')!r} declara senha_env="
            f"{nome_da_variavel!r}, mas essa variável não está no ambiente — exporte-a antes "
            f"de rodar a auditoria")
    return Credencial(alvo=alvo, componente=componente.get("nome"),
                      usuario=componente.get("usuario") or USUARIO_PADRAO,
                      senha=ambiente[nome_da_variavel],
                      destino=http_get.destino(componente.get("admin_url")))
```

- [x] **Step 4: Rodar e confirmar verde**

Run: `.venv/bin/python -m pytest tests/test_credencial.py -q`
Expected: PASS (10 testes)

> `test_credencial_nao_entra_em_json` passa de graça: `json.dumps` já levanta `TypeError` para objeto desconhecido. Ele existe como **regressão** — o dia em que alguém der um `__dict__` ou um `to_json` à classe, ele cai.

- [x] **Step 5: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| `para()` devolver `self.par()` sempre | `test_a_credencial_so_serve_para_o_destino_dela` |
| `__repr__` incluir `self._senha` | `test_repr_nao_mostra_a_senha` |
| variável ausente devolver `None` em vez de levantar | `test_variavel_ausente_levanta_com_o_nome_dela` |

- [x] **Step 6: Declarar `usuario` no schema do componente**

Em `scripts/lib/alvos.py`, a tupla `COMPONENTE_PERMITE` precisa aceitar o campo novo:

```python
COMPONENTE_PERMITE = ("nome", "papel", "admin_url", "metricas_url", "senha_env", "usuario")
```

Acrescentar o teste em `tests/test_alvos.py`:

```python
def test_componente_aceita_usuario_declarado():
    """Sem isto, declarar `usuario` no alvos.toml é recusado como chave desconhecida — e a
    recusa é de propósito, então o campo novo precisa entrar na lista."""
    from lib.alvos import COMPONENTE_PERMITE

    assert "usuario" in COMPONENTE_PERMITE
```

- [x] **Step 7: Rodar a suíte inteira e commitar**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 491

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): credencial sai do ambiente e nao vaza em repr"
```

---

> ### Ajustes das Tasks 1–2 após a revisão do juiz (2026-09-20)
>
> O revisor achou um vazamento real e cinco travas frouxas. O que mudou em relação ao escrito acima:
>
> 1. **A guarda de `userinfo` saiu de `get_autenticado` e foi para `check_allowed` e `alvos._checar_url`.** Estava na camada errada: `admin_url = "http://user:SENHA@host"` no `alvos.toml` passava na validação, era copiado cru para o componente e chegava ao `report.json`, ao HTML e ao PDF. Teste novo: `tests/test_userinfo_nao_entra.py`.
> 2. **`get_autenticado` passou a receber o objeto `Credencial`, não o par**, e chama `.para(url, alvo)` por dentro. Com o par solto a amarração era convenção: `par()` mandava a senha para qualquer host da allowlist. Assinatura: `get_autenticado(url, allowed_hosts, credencial, alvo=None, timeout=...)`.
> 3. **`Credencial.par()` deixou de existir**; a única via é `para(url, alvo)`, que agora compara **o alvo também** — prod e dr podem declarar o mesmo `host:porta` com senhas diferentes.
> 4. **`__getstate__` levanta**: `__slots__` bloqueava `vars()`, mas pickle, `copy` e `object.__getstate__` devolviam a senha inteira.
> 5. **`de_componente` recusa `senha_env` sem `admin_url`**, e `para()` recusa destino `(None, None)` — que casava com toda URL que não parseia.
> 6. **O coletor docker passou a copiar `usuario`**: o campo entrou no schema e não chegava a lugar nenhum, então declarar `usuario = "leitor"` autenticava como `guest` em silêncio.
>
> Testes decorativos trocados por reais: o de serialização agora cobre pickle/copy/`__getstate__`; o de URL agora olha `Request.host` (era só `full_url`, e foi por isso que o vazamento ficou invisível); o ramo `ambiente=None` ganhou teste — uma mutação nele sobrevivia à suíte inteira.

---

## Task 3: `lib/extracao.py` — ponteiro, campos e transformações

**Files:**
- Create: `scripts/lib/extracao.py`
- Test: `tests/test_extracao.py`

A linguagem é **fechada**: não há expressão arbitrária. O que não couber nela não ganha arquivo — vira adaptador próprio, com código e teste. É isso que impede o `if produto == …` disfarçado de configuração.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_extracao.py
"""A linguagem fechada de extração.

Regra de ouro do spec: o que não couber aqui NÃO ganha arquivo — vira adaptador com código e
teste. Uma linguagem que aceita expressão arbitrária é `eval` com outro nome, e um arquivo de
catálogo é dado, não código.
"""
import pytest

from lib.extracao import ExtracaoInvalida, extrair, ponteiro, transformar

FILAS = {"items": [
    {"name": "pedidos", "messages_ready": "42", "consumers": 3},
    {"name": "emails", "messages_ready": 7, "consumers": 0},
    {"name": "morta", "messages_ready": 900, "consumers": 0},
]}


# --- ponteiro (RFC 6901) ---

def test_ponteiro_vazio_e_o_documento_inteiro():
    assert ponteiro({"a": 1}, "") == {"a": 1}


def test_ponteiro_navega_objeto_e_indice():
    assert ponteiro(FILAS, "/items/1/name") == "emails"


def test_ponteiro_de_chave_ausente_e_none_nao_erro():
    """Campo que a família não expõe é `sem_dados` daquela pergunta, não exceção."""
    assert ponteiro(FILAS, "/items/0/nao_existe") is None


def test_ponteiro_sem_barra_inicial_e_recusado():
    """`items/0` parece funcionar e não é ponteiro: recusar no carregamento evita um arquivo
    que erra em silêncio."""
    with pytest.raises(ExtracaoInvalida):
        ponteiro(FILAS, "items/0")


def test_ponteiro_escapa_til_e_barra():
    documento = {"a/b": {"c~d": 9}}

    assert ponteiro(documento, "/a~1b/c~0d") == 9


def test_ponteiro_em_escalar_para_de_navegar():
    assert ponteiro({"a": 5}, "/a/b") is None


# --- transformações ---

@pytest.mark.parametrize("tipo, bruto, esperado", [
    ("inteiro", "42", 42),
    ("inteiro", 42.9, 42),
    ("decimal", "3.5", 3.5),
    ("texto", 42, "42"),
    ("bytes", 1536, 1536),
    ("segundos", "90", 90.0),
    ("percentual", 0.5, 50.0),
    ("data_iso", "2026-09-19T10:00:00Z", "2026-09-19T10:00:00+00:00"),
])
def test_transformacoes_permitidas(tipo, bruto, esperado):
    assert transformar(bruto, tipo) == esperado


def test_transformacao_de_valor_impossivel_e_none():
    """"n/a" onde se esperava número não vira 0: 0 é uma medida, None é a ausência dela."""
    assert transformar("n/a", "inteiro") is None


def test_transformacao_desconhecida_e_recusada():
    with pytest.raises(ExtracaoInvalida):
        transformar("1", "sql")


def test_nan_e_infinito_nao_passam():
    """NaN escrito no report.json produz JSON inválido para qualquer leitor fora do Python."""
    assert transformar(float("nan"), "decimal") is None
    assert transformar(float("inf"), "decimal") is None


# --- extração de lista ---

def test_extrai_lista_com_campos_e_transformacoes():
    itens = extrair(FILAS, {
        "lista": "/items",
        "campos": {"nome": "/name", "prontas": "/messages_ready",
                   "consumidores": "/consumers"},
        "transformar": {"prontas": "inteiro", "consumidores": "inteiro"},
    })

    assert itens[0] == {"nome": "pedidos", "prontas": 42, "consumidores": 3}


def test_ordena_e_corta_no_limite():
    itens = extrair(FILAS, {
        "lista": "/items",
        "campos": {"nome": "/name", "prontas": "/messages_ready"},
        "transformar": {"prontas": "inteiro"},
        "ordenar_por": "prontas", "ordem": "desc", "limite": 2,
    })

    assert [i["nome"] for i in itens] == ["morta", "pedidos"]


def test_empate_de_valor_desempata_pelo_nome():
    """Sem desempate, duas rodadas iguais dariam top N em ordens diferentes — e o diff entre
    auditorias acusaria mudança onde nada mudou."""
    documento = {"items": [{"name": "zulu", "n": 5}, {"name": "alfa", "n": 5}]}

    itens = extrair(documento, {
        "lista": "/items", "campos": {"nome": "/name", "n": "/n"},
        "transformar": {"n": "inteiro"}, "ordenar_por": "n", "ordem": "desc",
        "desempate": "nome",
    })

    assert [i["nome"] for i in itens] == ["alfa", "zulu"]


def test_lista_na_raiz_do_documento():
    documento = [{"name": "unica", "n": 1}]

    itens = extrair(documento, {"lista": "", "campos": {"nome": "/name"}})

    assert itens == [{"nome": "unica"}]


def test_lista_que_nao_e_lista_e_recusada():
    with pytest.raises(ExtracaoInvalida):
        extrair({"items": {"nao": "lista"}}, {"lista": "/items",
                                              "campos": {"nome": "/nao"}})


def test_escalar_sem_lista_declarada():
    assert extrair({"total": "17"}, {"campos": {"valor": "/total"},
                                     "transformar": {"valor": "inteiro"}}) == {"valor": 17}
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_extracao.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.extracao'`

- [ ] **Step 3: Implementar**

```python
# scripts/lib/extracao.py
"""A linguagem fechada que tira resposta de um JSON de API.

Fechada é o ponto: JSON pointer para achar, `campos` para nomear, `transformar` para tipar,
`ordenar_por`/`limite` para recortar. Não há expressão arbitrária — uma linguagem que aceita
expressão é `eval` com outro nome, e arquivo de catálogo é dado, não código.

O que não couber aqui não ganha arquivo: vira adaptador próprio, com código e teste.
"""
import math
from datetime import datetime

TRANSFORMACOES = ("inteiro", "decimal", "texto", "bytes", "segundos", "percentual", "data_iso")


class ExtracaoInvalida(Exception):
    """Arquivo de catálogo que a skill se recusa a interpretar."""


def ponteiro(documento, caminho):
    """JSON pointer (RFC 6901). `""` é o documento inteiro.

    Chave ausente devolve None em vez de levantar: a família pode não expor aquele campo, e
    isso é `sem_dados` daquela pergunta — não um defeito da skill.
    """
    if caminho in (None, ""):
        return documento
    if not str(caminho).startswith("/"):
        raise ExtracaoInvalida(
            f"ponteiro {caminho!r} não começa com '/' — ponteiro JSON sempre começa, e "
            f"'items/0' parece funcionar sem nunca achar nada")
    atual = documento
    for cru in str(caminho).split("/")[1:]:
        token = cru.replace("~1", "/").replace("~0", "~")
        if isinstance(atual, dict):
            if token not in atual:
                return None
            atual = atual[token]
        elif isinstance(atual, list):
            try:
                atual = atual[int(token)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return atual


def _numero(bruto):
    try:
        valor = float(bruto)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(valor) or math.isinf(valor) else valor


def transformar(bruto, tipo):
    """O valor tipado, ou None quando ele não é o que se declarou.

    None não é zero. Zero é uma medida ("nenhuma mensagem pronta"); None é a ausência dela
    ("não li"). Confundir os dois é o que faz relatório dizer "está tudo bem" sobre o que não
    olhou.
    """
    if tipo not in TRANSFORMACOES:
        raise ExtracaoInvalida(
            f"transformação {tipo!r} não existe; as permitidas são "
            f"{', '.join(TRANSFORMACOES)}")
    if bruto is None:
        return None
    if tipo == "texto":
        return str(bruto)
    if tipo == "data_iso":
        try:
            return datetime.fromisoformat(str(bruto).replace("Z", "+00:00")).isoformat()
        except ValueError:
            return None
    valor = _numero(bruto)
    if valor is None:
        return None
    if tipo in ("inteiro", "bytes"):
        return int(valor)
    if tipo == "percentual":
        return round(valor * 100, 2)
    return round(valor, 2)


def _item(bruto, declarada):
    campos = declarada.get("campos") or {}
    tipos = declarada.get("transformar") or {}
    saida = {}
    for nome, caminho in campos.items():
        valor = ponteiro(bruto, caminho)
        saida[nome] = transformar(valor, tipos[nome]) if nome in tipos else valor
    return saida


def extrair(documento, declarada):
    """Um item (quando não há `lista`) ou a lista de itens já ordenada e cortada."""
    if "lista" not in declarada:
        return _item(documento, declarada)

    cru = ponteiro(documento, declarada["lista"])
    if cru is None:
        return []
    if not isinstance(cru, list):
        raise ExtracaoInvalida(
            f"`lista = {declarada['lista']!r}` aponta para {type(cru).__name__}, não para um "
            f"array")

    itens = [_item(bruto, declarada) for bruto in cru]
    chave = declarada.get("ordenar_por")
    if chave:
        desempate = declarada.get("desempate")
        reverso = declarada.get("ordem", "desc") == "desc"
        # o valor ordena na direção pedida; o desempate SEMPRE sobe em ordem alfabética,
        # senão inverter a ordem inverteria o desempate junto e o top N dançaria
        itens.sort(key=lambda item: str(item.get(desempate, "")) if desempate else "")
        itens.sort(key=lambda item: (item.get(chave) is None, item.get(chave) or 0),
                   reverse=reverso)
    limite = declarada.get("limite")
    return itens[:limite] if limite else itens
```

- [ ] **Step 4: Rodar e confirmar verde**

Run: `.venv/bin/python -m pytest tests/test_extracao.py -q`
Expected: PASS (21 testes)

- [ ] **Step 5: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| `ponteiro` aceitar caminho sem `/` inicial | `test_ponteiro_sem_barra_inicial_e_recusado` |
| `transformar` devolver `0` em vez de `None` para `"n/a"` | `test_transformacao_de_valor_impossivel_e_none` |
| `transformar` aceitar qualquer `tipo` | `test_transformacao_desconhecida_e_recusada` |
| remover o `sort` de desempate | `test_empate_de_valor_desempata_pelo_nome` |
| `_numero` não checar NaN/inf | `test_nan_e_infinito_nao_passam` |

- [ ] **Step 6: Commit**

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): linguagem fechada de extracao por ponteiro JSON"
```

---

## Task 4: derivações — o que é razão entre campos

**Files:**
- Modify: `scripts/lib/extracao.py`
- Test: `tests/test_extracao_derivacoes.py`

O spec proíbe aritmética na expressão de limiar. O que precisa de conta vira **derivação declarada**, de um conjunto fechado: `razao`, `percentual_de`, `diferenca`, `soma`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_extracao_derivacoes.py
"""Derivações: a conta que o catálogo pode declarar.

A expressão de limiar não faz aritmética de propósito — abrir uma exceção ali seria abrir a
porta para uma linguagem inteira. O que precisa de conta vira derivação DECLARADA, de um
conjunto fechado, e o limiar compara o resultado.
"""
import pytest

from lib.extracao import ExtracaoInvalida, derivar, extrair


def test_razao_simples():
    assert derivar({"hits": 90, "misses": 10},
                   {"tipo": "razao", "numerador": "/hits",
                    "denominador_soma": ["/hits", "/misses"]}) == 0.9


def test_razao_com_denominador_zero_e_none():
    """Dividir por zero não é 0 nem infinito: é "não dá para dizer". Cache sem acesso nenhum
    não tem taxa de acerto — inventar 0% acusaria um problema que não existe."""
    assert derivar({"hits": 0, "misses": 0},
                   {"tipo": "razao", "numerador": "/hits",
                    "denominador_soma": ["/hits", "/misses"]}) is None


def test_percentual_de():
    assert derivar({"usada": 2, "total": 8},
                   {"tipo": "percentual_de", "numerador": "/usada",
                    "denominador": "/total"}) == 25.0


def test_diferenca():
    assert derivar({"entrada": 10.0, "saida": 4.0},
                   {"tipo": "diferenca", "de": "/entrada", "menos": "/saida"}) == 6.0


def test_soma():
    assert derivar({"a": 1, "b": 2, "c": 3},
                   {"tipo": "soma", "parcelas": ["/a", "/b", "/c"]}) == 6.0


def test_campo_ausente_torna_a_derivacao_none():
    assert derivar({"hits": 5},
                   {"tipo": "razao", "numerador": "/hits",
                    "denominador_soma": ["/hits", "/misses"]}) is None


def test_tipo_de_derivacao_desconhecido_e_recusado():
    with pytest.raises(ExtracaoInvalida):
        derivar({"a": 1}, {"tipo": "regressao", "de": "/a"})


def test_derivacao_entra_no_item_extraido():
    documento = {"items": [{"name": "c", "hits": 3, "misses": 1}]}

    itens = extrair(documento, {
        "lista": "/items",
        "campos": {"nome": "/name"},
        "derivar": {"hit_ratio": {"tipo": "razao", "numerador": "/hits",
                                  "denominador_soma": ["/hits", "/misses"]}},
    })

    assert itens[0] == {"nome": "c", "hit_ratio": 0.75}


def test_derivacao_pode_ser_a_chave_de_ordenacao():
    documento = {"items": [{"name": "ruim", "hits": 1, "misses": 9},
                           {"name": "bom", "hits": 9, "misses": 1}]}

    itens = extrair(documento, {
        "lista": "/items", "campos": {"nome": "/name"},
        "derivar": {"hit_ratio": {"tipo": "razao", "numerador": "/hits",
                                  "denominador_soma": ["/hits", "/misses"]}},
        "ordenar_por": "hit_ratio", "ordem": "desc", "desempate": "nome",
    })

    assert [i["nome"] for i in itens] == ["bom", "ruim"]


def test_derivacao_nao_sobrescreve_campo_declarado():
    """Nome repetido entre `campos` e `derivar` é erro de arquivo, não precedência silenciosa."""
    with pytest.raises(ExtracaoInvalida):
        extrair({"items": [{"n": 1}]},
                {"lista": "/items", "campos": {"x": "/n"},
                 "derivar": {"x": {"tipo": "soma", "parcelas": ["/n"]}}})
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_extracao_derivacoes.py -q`
Expected: FAIL — `ImportError: cannot import name 'derivar' from 'lib.extracao'`

- [ ] **Step 3: Implementar**

Em `scripts/lib/extracao.py`, acrescentar a constante junto das outras:

```python
DERIVACOES = ("razao", "percentual_de", "diferenca", "soma")
```

E as funções, logo antes de `_item`:

```python
def _valores(documento, caminhos):
    """Os números dos caminhos, ou None se QUALQUER um faltar.

    Um só ausente derruba a derivação inteira: somar o que existe e chamar de total seria
    inventar um denominador menor e, com ele, uma razão melhor do que a real.
    """
    saida = []
    for caminho in caminhos:
        valor = _numero(ponteiro(documento, caminho))
        if valor is None:
            return None
        saida.append(valor)
    return saida


def derivar(documento, declarada):
    """A conta declarada, ou None quando ela não pode ser feita com honestidade."""
    tipo = declarada.get("tipo")
    if tipo not in DERIVACOES:
        raise ExtracaoInvalida(
            f"derivação {tipo!r} não existe; as permitidas são {', '.join(DERIVACOES)}")

    if tipo == "soma":
        valores = _valores(documento, declarada.get("parcelas") or [])
        return None if valores is None else round(sum(valores), 4)

    if tipo == "diferenca":
        valores = _valores(documento, [declarada["de"], declarada["menos"]])
        return None if valores is None else round(valores[0] - valores[1], 4)

    if tipo == "razao":
        caminhos = [declarada["numerador"], *declarada["denominador_soma"]]
    else:                                   # percentual_de
        caminhos = [declarada["numerador"], declarada["denominador"]]
    valores = _valores(documento, caminhos)
    if valores is None:
        return None
    numerador, denominador = valores[0], sum(valores[1:])
    if denominador == 0:
        # não é 0 nem infinito: é "não dá para dizer". Cache sem acesso nenhum não tem taxa de
        # acerto, e escrever 0% acusaria um problema que não existe.
        return None
    bruto = numerador / denominador
    return round(bruto * 100, 2) if tipo == "percentual_de" else round(bruto, 4)
```

E, dentro de `_item`, depois do laço dos campos e antes do `return`:

```python
    for nome, regra in (declarada.get("derivar") or {}).items():
        if nome in saida:
            raise ExtracaoInvalida(
                f"`{nome}` está em `campos` e em `derivar` — nome repetido vira precedência "
                f"silenciosa, e o arquivo passa a depender da ordem de leitura")
        saida[nome] = derivar(bruto, regra)
```

- [ ] **Step 4: Rodar e confirmar verde**

Run: `.venv/bin/python -m pytest tests/test_extracao_derivacoes.py -q`
Expected: PASS (10 testes)

- [ ] **Step 5: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| denominador zero devolver `0` | `test_razao_com_denominador_zero_e_none` |
| `_valores` pular o ausente em vez de devolver `None` | `test_campo_ausente_torna_a_derivacao_none` |
| remover a checagem de nome repetido | `test_derivacao_nao_sobrescreve_campo_declarado` |

- [ ] **Step 6: Rodar a suíte inteira e commitar**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 522

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): derivacoes declaradas no lugar de aritmetica em expressao"
```

---

## Task 5: `lib/limiar.py` — a expressão, sem `eval`

**Files:**
- Create: `scripts/lib/limiar.py`
- Test: `tests/test_limiar.py`

Gramática fechada: `campo OP literal`, combinada por `e`/`ou`. Sem parênteses e **sem misturar `e` com `ou` na mesma expressão** — precedência implícita é a forma mais barata de um arquivo de catálogo dizer uma coisa e a skill entender outra.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_limiar.py
"""A expressão de limiar — parser próprio, sem `eval`.

`eval` num arquivo de catálogo é execução de código a partir de dado. Mesmo sendo arquivo da
própria skill hoje, a linguagem é o contrato: no dia em que alguém aceitar catálogo de terceiro,
a diferença entre parser e `eval` é a diferença entre dado e RCE.

Sem parênteses e sem misturar `e` com `ou`: precedência implícita é a forma mais barata de o
arquivo dizer uma coisa e a skill entender outra.
"""
import pytest

from lib.limiar import LimiarInvalido, avaliar, compilar

ITEM = {"nome": "pedidos", "prontas": 42, "consumidores": 0, "hit_ratio": 0.75}


@pytest.mark.parametrize("expressao, esperado", [
    ("consumidores == 0", True),
    ("consumidores != 0", False),
    ("prontas > 40", True),
    ("prontas > 42", False),
    ("prontas >= 42", True),
    ("prontas < 100", True),
    ("prontas <= 42", True),
    ("hit_ratio < 0.8", True),
    ("nome == 'pedidos'", True),
    ('nome == "pedidos"', True),
    ("nome == 'outra'", False),
])
def test_comparacoes(expressao, esperado):
    assert avaliar(expressao, ITEM) is esperado


def test_conjuncao():
    assert avaliar("consumidores == 0 e prontas > 0", ITEM) is True
    assert avaliar("consumidores == 0 e prontas > 100", ITEM) is False


def test_disjuncao():
    assert avaliar("consumidores > 5 ou prontas > 40", ITEM) is True
    assert avaliar("consumidores > 5 ou prontas > 100", ITEM) is False


def test_misturar_e_com_ou_e_recusado():
    """`a e b ou c` tem duas leituras. Recusar é melhor que escolher uma em silêncio."""
    with pytest.raises(LimiarInvalido) as erro:
        compilar("consumidores == 0 e prontas > 0 ou nome == 'x'")

    assert "e" in str(erro.value) and "ou" in str(erro.value)


def test_campo_ausente_nao_dispara():
    """Campo que a família não expõe não pode virar achado: ausência não é evidência."""
    assert avaliar("consumidores == 0", {"nome": "x"}) is False


def test_campo_none_nao_dispara():
    """`consumidores = None` quer dizer "não li", e "não li" nunca vira achado."""
    assert avaliar("consumidores == 0", {"consumidores": None}) is False


def test_comparar_texto_com_numero_nao_explode():
    assert avaliar("nome > 10", ITEM) is False


def test_expressao_com_aritmetica_e_recusada():
    """Aritmética é derivação declarada, não expressão — a regra de ouro do spec."""
    with pytest.raises(LimiarInvalido):
        compilar("prontas / consumidores > 2")


def test_chamada_de_funcao_e_recusada():
    with pytest.raises(LimiarInvalido):
        compilar("__import__('os').system('rm -rf /') == 0")


def test_atribuicao_e_recusada():
    with pytest.raises(LimiarInvalido):
        compilar("prontas = 0")


def test_operador_desconhecido_e_recusado():
    with pytest.raises(LimiarInvalido):
        compilar("prontas ~ 0")


def test_literal_nao_numerico_sem_aspas_e_recusado():
    """`nome == pedidos` compararia campo com campo sem dizer — o spec só permite campo
    contra literal."""
    with pytest.raises(LimiarInvalido):
        compilar("nome == pedidos")


def test_compilar_e_reutilizavel():
    """Compila uma vez, avalia em 500 filas: o parser não pode rodar por item."""
    pronta = compilar("consumidores == 0 e prontas > 0")

    assert pronta(ITEM) is True
    assert pronta({"consumidores": 2, "prontas": 5}) is False


def test_expressao_vazia_e_recusada():
    with pytest.raises(LimiarInvalido):
        compilar("   ")
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_limiar.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.limiar'`

- [ ] **Step 3: Implementar**

```python
# scripts/lib/limiar.py
"""A expressão que transforma resposta em achado — parser próprio, nunca `eval`.

`eval` sobre arquivo de catálogo é executar código a partir de dado. Hoje o catálogo é da
própria skill; no dia em que alguém aceitar um de terceiro, a diferença entre parser e `eval` é
a diferença entre dado e execução remota.

A gramática é minúscula de propósito:

    expressao := termo (('e' | 'ou') termo)*
    termo     := CAMPO OP LITERAL
    OP        := == | != | >= | <= | > | <
    LITERAL   := número | 'texto' | "texto"

Sem parênteses e sem misturar `e` com `ou`: precedência implícita é a forma mais barata de o
arquivo dizer uma coisa e a skill entender outra. Sem aritmética: o que precisa de conta é
derivação declarada (`lib/extracao.py`).
"""
import re

OPERADORES = ("==", "!=", ">=", "<=", ">", "<")
_TERMO = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")


class LimiarInvalido(Exception):
    """Expressão que a skill se recusa a interpretar."""


def _literal(cru):
    """Número ou texto entre aspas. Qualquer outra coisa é recusada.

    `nome == pedidos` (sem aspas) compararia campo com campo sem dizer que faz isso; o spec
    permite campo contra LITERAL, e só.
    """
    if len(cru) >= 2 and cru[0] == cru[-1] and cru[0] in "\"'":
        return cru[1:-1]
    try:
        return int(cru)
    except ValueError:
        pass
    try:
        return float(cru)
    except ValueError:
        raise LimiarInvalido(
            f"{cru!r} não é literal: texto vai entre aspas e número vai sem elas. Comparar "
            f"dois campos não é permitido — o limiar é campo contra literal") from None


def _comparar(valor, operador, alvo):
    if valor is None:
        # "não li" nunca vira achado: ausência não é evidência
        return False
    try:
        if operador == "==":
            return valor == alvo
        if operador == "!=":
            return valor != alvo
        if operador == ">":
            return valor > alvo
        if operador == ">=":
            return valor >= alvo
        if operador == "<":
            return valor < alvo
        return valor <= alvo
    except TypeError:
        # texto contra número: o arquivo está errado, mas derrubar a auditoria inteira por
        # causa de uma fila seria pior que não disparar este limiar
        return False


def compilar(expressao):
    """Devolve uma função `(item) -> bool`. Compila uma vez, avalia em N itens."""
    texto = str(expressao or "").strip()
    if not texto:
        raise LimiarInvalido("expressão de limiar vazia")

    tem_e = re.search(r"\be\b", texto) is not None
    tem_ou = re.search(r"\bou\b", texto) is not None
    if tem_e and tem_ou:
        raise LimiarInvalido(
            f"{texto!r} mistura `e` com `ou`, e isso tem duas leituras. Escreva duas regras, "
            f"ou uma derivação que já resolva a conta")

    juncao = "ou" if tem_ou else "e"
    termos = []
    for cru in re.split(rf"\b{juncao}\b", texto):
        casado = _TERMO.match(cru)
        if not casado:
            raise LimiarInvalido(
                f"{cru.strip()!r} não é `campo OPERADOR literal`; os operadores são "
                f"{', '.join(OPERADORES)}, e não há aritmética nem chamada de função aqui")
        campo, operador, literal = casado.group(1), casado.group(2), _literal(casado.group(3))
        termos.append((campo, operador, literal))

    def pronta(item):
        resultados = [_comparar(item.get(campo), operador, alvo)
                      for campo, operador, alvo in termos]
        return any(resultados) if juncao == "ou" else all(resultados)

    return pronta


def avaliar(expressao, item):
    """Atalho para um item só — em lista, use `compilar` e reaproveite."""
    return compilar(expressao)(item)
```

- [ ] **Step 4: Rodar e confirmar verde**

Run: `.venv/bin/python -m pytest tests/test_limiar.py -q`
Expected: PASS (25 testes)

- [ ] **Step 5: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| trocar o parser por `eval(expressao, {}, item)` | `test_chamada_de_funcao_e_recusada`, `test_expressao_com_aritmetica_e_recusada` |
| `_comparar` devolver `True` quando `valor is None` | `test_campo_none_nao_dispara` |
| aceitar mistura de `e` e `ou` | `test_misturar_e_com_ou_e_recusado` |
| `_literal` devolver `cru` cru quando não é número | `test_literal_nao_numerico_sem_aspas_e_recusado` |

- [ ] **Step 6: Commit**

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): parser proprio de limiar, sem eval"
```

---

## Task 6: limiar vira achado — a ponte que nunca existiu

**Files:**
- Modify: `scripts/collect.py`
- Test: `tests/test_limiar_vira_achado.py`

`perguntas.py` declara o campo `limiar` desde o plano 1 e **nada no código o lê**. Esta task é a ponte: resposta que cruza o limiar declarado no catálogo nasce achado no componente, e `promover_achados` (que já existe) o leva ao alvo.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_limiar_vira_achado.py
"""A ponte entre insight e achado.

O campo `limiar` existe no registro de perguntas desde o plano 1 e nada nunca o avaliou: a
skill colecionava respostas e nenhuma delas virava achado. Esta é a primeira regra que nasce de
uma medida em vez de nascer de uma inspeção de configuração.
"""
from collect import achados_da_resposta


def _resposta(valor):
    return {"pergunta": "fila.filas_com_acumulo", "fonte": "admin_http:amqp-mgmt",
            "valor": valor}


LIMIAR = {"quando": "consumidores == 0 e prontas > 0",
          "regra": "fila_sem_consumidor", "severidade": "high"}


def test_item_que_cruza_o_limiar_vira_achado():
    resposta = _resposta([{"nome": "emails", "prontas": 7, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert len(achados) == 1
    assert achados[0]["regra"] == "fila_sem_consumidor"
    assert achados[0]["severidade"] == "high"


def test_o_objeto_do_achado_identifica_o_item():
    """Sem o objeto, 30 filas com acúmulo viram 30 achados indistinguíveis — e o agrupamento
    do relatório (v0.8.0) mostraria 30 linhas iguais."""
    resposta = _resposta([{"nome": "emails", "prontas": 7, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert achados[0]["objeto"] == "emails"


def test_item_que_nao_cruza_nao_vira_achado():
    resposta = _resposta([{"nome": "pedidos", "prontas": 42, "consumidores": 3}])

    assert achados_da_resposta(resposta, LIMIAR, componente="broker") == []


def test_cada_item_que_cruza_gera_o_seu():
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0},
                          {"nome": "b", "prontas": 2, "consumidores": 2},
                          {"nome": "c", "prontas": 3, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert [a["objeto"] for a in achados] == ["a", "c"]


def test_resposta_sem_dados_nunca_vira_achado():
    """A regra mais importante da skill: achado nasce de fato presente, nunca de ausência."""
    resposta = {"pergunta": "fila.filas_com_acumulo", "sem_dados": True,
                "motivo": "a API não respondeu"}

    assert achados_da_resposta(resposta, LIMIAR, componente="broker") == []


def test_erro_interno_nunca_vira_achado():
    resposta = {"pergunta": "fila.filas_com_acumulo", "erro_interno": True,
                "motivo": "admin_http: KeyError: x"}

    assert achados_da_resposta(resposta, LIMIAR, componente="broker") == []


def test_sem_limiar_declarado_nao_ha_achado():
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0}])

    assert achados_da_resposta(resposta, None, componente="broker") == []


def test_detalhe_do_achado_cita_os_numeros():
    resposta = _resposta([{"nome": "emails", "prontas": 7, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert "7" in achados[0]["detalhe"]


def test_expressao_invalida_nao_derruba_a_coleta():
    """Arquivo de catálogo errado é bug da skill, e bug da skill não pode apagar o inventário
    de um alvo inteiro."""
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0}])
    quebrado = dict(LIMIAR, quando="prontas / consumidores > 2")

    assert achados_da_resposta(resposta, quebrado, componente="broker") == []


def test_escalar_tambem_pode_cruzar_limiar():
    """Nem toda pergunta é lista: um escalar compara contra o campo `valor`.

    Nenhuma pergunta do papel `fila` usa este caminho nesta versão — ele existe porque os
    planos 3 e 4 trazem escalares com limiar, e uma ponte que só funciona para lista viraria
    surpresa lá na frente.
    """
    resposta = {"pergunta": "papel.escalar", "fonte": "admin_http:exemplo", "valor": 900}
    limiar = {"quando": "valor > 0", "regra": "regra_escalar", "severidade": "medium"}

    achados = achados_da_resposta(resposta, limiar, componente="broker")

    assert len(achados) == 1 and achados[0]["objeto"] == "broker"
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_limiar_vira_achado.py -q`
Expected: FAIL — `ImportError: cannot import name 'achados_da_resposta' from 'collect'`

- [ ] **Step 3: Implementar**

Em `scripts/collect.py`, acrescentar antes de `responder`:

```python
def achados_da_resposta(resposta, limiar, componente):
    """Resposta que cruza o limiar declarado vira achado — a ponte entre insight e achado.

    O campo `limiar` existia no registro de perguntas desde o plano 1 e nada o lia: a skill
    colecionava respostas e nenhuma virava achado. Esta é a primeira regra que nasce de uma
    MEDIDA, e não de uma inspeção de configuração.

    Duas travas que valem mais que a função:
      - resposta `sem_dados` ou `erro_interno` nunca gera achado. Achado nasce de fato
        presente; ausência não é evidência, e "não li a fila" não pode virar "a fila está
        parada".
      - expressão inválida devolve lista vazia em vez de levantar. Arquivo de catálogo errado é
        bug da skill, e bug da skill não pode apagar o inventário de um alvo inteiro.
    """
    from lib import limiar as limiar_mod

    if not limiar or resposta.get("sem_dados") or resposta.get("erro_interno"):
        return []
    try:
        cruzou = limiar_mod.compilar(limiar["quando"])
    except (limiar_mod.LimiarInvalido, KeyError):
        return []

    valor = resposta.get("valor")
    itens = valor if isinstance(valor, list) else [{"valor": valor}]
    achados = []
    for item in itens:
        if not isinstance(item, dict) or not cruzou(item):
            continue
        achados.append({
            "regra": limiar["regra"],
            "severidade": limiar.get("severidade", "medium"),
            "objeto": str(item.get("nome") or componente),
            "detalhe": _detalhe(item),
        })
    return achados


def _detalhe(item):
    """Os números que fizeram o limiar disparar, na ordem declarada do item."""
    partes = [f"{nome}: {valor}" for nome, valor in item.items()
              if nome != "nome" and valor is not None]
    return " · ".join(partes) or "sem detalhe"
```

E, dentro de `responder`, trocar o bloco final:

```python
        if resposta is not None:
            componente["respostas"].append(resposta)
```

por:

```python
        if resposta is not None:
            componente["respostas"].append(resposta)
            componente.setdefault("achados", []).extend(
                achados_da_resposta(resposta, pergunta.get("limiar"),
                                    componente.get("nome")))
```

> `promover_achados` já existe e já leva `componente["achados"]` para `registro["achados"]` carregando o nome do componente — nada a fazer ali.

- [ ] **Step 4: Rodar e confirmar verde**

Run: `.venv/bin/python -m pytest tests/test_limiar_vira_achado.py -q`
Expected: PASS (10 testes)

- [ ] **Step 5: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| tirar a guarda de `sem_dados` | `test_resposta_sem_dados_nunca_vira_achado` |
| deixar `LimiarInvalido` propagar | `test_expressao_invalida_nao_derruba_a_coleta` |
| usar `componente` como `objeto` sempre | `test_o_objeto_do_achado_identifica_o_item` |

- [ ] **Step 6: Rodar a suíte inteira e commitar**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 557

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): limiar declarado vira achado no componente"
```

---

## Task 7: as 4 perguntas do papel `fila`

**Files:**
- Modify: `scripts/lib/perguntas.py`
- Test: `tests/test_perguntas_fila.py`

Vem antes do catálogo de propósito: `catalogo_api.py` recusa arquivo que cite pergunta inexistente, então o registro precisa existir primeiro.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_perguntas_fila.py
"""As perguntas do papel `fila`.

Antes desta task, `do_papel("fila")` devolvia lista vazia — o RabbitMQ do cluster aparecia no
relatório com nome, papel e mais nada. Era o item que o dono pediu por extenso.
"""
from lib.perguntas import PERGUNTAS, do_papel

IDS = ["fila.filas", "fila.filas_com_acumulo", "fila.consumidores_por_fila",
       "fila.taxa_entrada_saida"]


def test_as_cinco_perguntas_estao_registradas():
    assert [p["id"] for p in do_papel("fila")] == IDS


def test_toda_pergunta_de_lista_declara_desempate():
    """Empate de valor não pode herdar a ordem da resposta da API: duas rodadas iguais dariam
    top N diferentes, e o diff entre auditorias acusaria mudança onde nada mudou."""
    sem = [p["id"] for p in do_papel("fila")
           if p["forma"] == "lista" and not p["desempate"]]

    assert sem == []


def test_o_limiar_aponta_para_regra_registrada():
    """Limiar que cita regra inexistente geraria achado sem remediação — e a fitness function
    de remediação não pegaria, porque ela enumera o registro, não os limiares."""
    from lib.regras import REGRAS

    for pergunta in do_papel("fila"):
        limiar = pergunta["limiar"]
        if limiar:
            assert limiar["regra"] in REGRAS, f"{pergunta['id']} cita regra desconhecida"


def test_filas_com_acumulo_dispara_por_fila_sem_consumidor():
    limiar = PERGUNTAS["fila.filas_com_acumulo"]["limiar"]

    assert limiar["regra"] == "fila_sem_consumidor"
    assert limiar["severidade"] == "high"


def test_perguntas_sem_limiar_sao_so_informacao():
    """`filas` e `consumidores_por_fila` descrevem; não acusam."""
    assert PERGUNTAS["fila.filas"]["limiar"] is None
    assert PERGUNTAS["fila.consumidores_por_fila"]["limiar"] is None


def test_o_papel_entrada_nao_foi_mexido():
    """Regressão: mexer no registro é fácil de fazer errado, e `entrada` já está publicado."""
    assert [p["id"] for p in do_papel("entrada")] == [
        "entrada.volume_na_janela", "entrada.distribuicao_de_status", "entrada.latencia"]
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_perguntas_fila.py -q`
Expected: FAIL — `assert [] == ['fila.filas', ...]`

- [ ] **Step 3: Implementar**

No fim de `scripts/lib/perguntas.py`, antes de `def do_papel`:

```python
# --- papel `fila`: tudo sai do mesmo endpoint de listagem de filas, então o custo marginal de
# cada pergunta é uma extração, não uma requisição. A ordem é a do relatório: o que existe,
# o que está acumulando, quem consome, a que ritmo, e o que já foi descartado.
_p("fila.filas", "fila", "Filas", "lista", unidade="mensagens", desempate="nome")
_p("fila.filas_com_acumulo", "fila", "Filas com acúmulo", "lista", unidade="mensagens",
   desempate="nome",
   limiar={"quando": "consumidores == 0 e prontas > 0",
           "regra": "fila_sem_consumidor", "severidade": "high"})
_p("fila.consumidores_por_fila", "fila", "Consumidores por fila", "lista",
   unidade="consumidores", desempate="nome")
_p("fila.taxa_entrada_saida", "fila", "Entrada × saída", "lista", unidade="mensagens/s",
   desempate="nome")
# Fila morta NÃO entra nesta versão: `/api/overview` traz o total de mensagens do broker, não o
# da fila morta, e distinguir as duas exigiria filtrar por convenção de nome (`dlq`, `dead`).
# Convenção de nome é expressão, e expressão não cabe na linguagem fechada — pela regra de ouro
# do spec, isso vira adaptador próprio, nunca uma extensão da linguagem.
```

> A regra `fila_sem_consumidor` entra no registro na Task 8. Rodar `test_o_limiar_aponta_para_regra_registrada` antes dela **falha de propósito** — é a ordem natural: a pergunta declara o que quer, e a task seguinte registra a regra e escreve a remediação.

- [ ] **Step 4: Rodar e confirmar o verde parcial**

Run: `.venv/bin/python -m pytest tests/test_perguntas_fila.py -q`
Expected: 5 PASS, 1 FAIL (`test_o_limiar_aponta_para_regra_registrada` — as regras entram na Task 8)

- [ ] **Step 5: Sem commit ainda**

Esta task e a Task 8 fecham juntas: registro de pergunta que cita regra inexistente não é estado para commitar. Siga direto.

---

## Task 8: a regra nova e a remediação dela

**Files:**
- Modify: `scripts/lib/regras.py`
- Create: `references/remediacao/fila_sem_consumidor.md`
- Test: `tests/test_regras_de_fila.py`

A fitness function que já existe (`tests/test_remediacao.py`) derruba a suíte se uma regra não-esperada ficar sem arquivo. Ela é quem cobra esta task.

`fila_morta_com_mensagens` **não entra** — a decisão do dono foi tirar `fila.fila_morta` do plano 2, porque o número disponível não é o que o nome promete.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_regras_de_fila.py
"""As regras que nascem de medida, não de inspeção de configuração.

Todas as regras anteriores da skill olhavam para como o serviço está DECLARADO (roda como root,
imagem sem digest, sem healthcheck). Estas duas olham para o que está ACONTECENDO — e por isso
dependem de uma coleta que respondeu, nunca de uma que falhou.
"""
from lib.regras import REGRAS, esperada, exigem_remediacao, severidade
from lib.remediacao import para


def test_a_regra_esta_no_registro():
    assert "fila_sem_consumidor" in REGRAS


def test_severidade_padrao_bate_com_o_limiar_da_pergunta():
    """Dois lugares declaram severidade: o limiar da pergunta e o registro. Divergir faria o
    relatório mostrar uma e a nota do alvo usar a outra."""
    from lib.perguntas import PERGUNTAS

    limiar = PERGUNTAS["fila.filas_com_acumulo"]["limiar"]

    assert severidade(limiar["regra"]) == limiar["severidade"]


def test_nao_e_esperada():
    """`esperada` marca comportamento NORMAL. Fila sem consumidor com mensagem presa não é."""
    assert not esperada("fila_sem_consumidor")


def test_exige_remediacao():
    assert "fila_sem_consumidor" in exigem_remediacao()


def test_a_remediacao_tem_os_quatro_blocos():
    bloco = para("fila_sem_consumidor")

    assert bloco is not None, "fila_sem_consumidor sem arquivo de remediação"
    for campo in ("por_que_importa", "como_resolver", "como_confirmar", "quando_nao_fazer"):
        assert bloco.get(campo), f"bloco {campo} vazio"


def test_a_origem_diz_de_onde_a_regra_nasce():
    """`origem` é o que permite responder "quem emite isto?" sem ler AST."""
    assert REGRAS["fila_sem_consumidor"]["origem"] == "limiar"
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_regras_de_fila.py -q`
Expected: FAIL — `assert 'fila_sem_consumidor' in REGRAS`

- [ ] **Step 3: Registrar as regras**

Em `scripts/lib/regras.py`, no fim do dicionário `REGRAS`, antes do `}`:

```python
    # --- limiar de pergunta (lib/perguntas.py + catálogo de API)
    # Primeiras regras da skill que nascem de uma MEDIDA, e não de como o serviço está
    # declarado. Por isso dependem de coleta que respondeu: `sem_dados` nunca vira achado.
    "fila_sem_consumidor":      {"severidade_padrao": "high",   "origem": "limiar", "esperada": False},
```

- [ ] **Step 4: Escrever `references/remediacao/fila_sem_consumidor.md`**

```markdown
---
regra: fila_sem_consumidor
titulo: Fila com mensagem presa e nenhum consumidor
severidade_padrao: high
---

## Por que importa

Mensagem numa fila sem consumidor não está atrasada: está parada. Nada a tira de lá, e o
tamanho só cresce. O efeito aparece longe da causa — o pedido que não confirmou, o e-mail que
não saiu, o relatório que não gerou — e a fila é o último lugar onde se procura, porque o
serviço que publica continua respondendo normalmente.

Quando a fila tem limite de tamanho ou de idade, o broker começa a **descartar** mensagem, e aí
o prejuízo deixa de ser atraso e passa a ser perda.

## Como resolver

1. Descubra quem deveria consumir esta fila. O nome dela costuma dizer, mas quem confirma é o
   código que declara a assinatura.
2. Veja se o serviço consumidor está no ar e com réplica saudável — fila sem consumidor
   normalmente é um worker em crash loop, não um problema do broker.
3. Se o consumidor está de pé, verifique se ele assinou a fila certa: renomear fila no
   publicador sem renomear no consumidor deixa exatamente este rastro.
4. Se a fila ficou órfã de propósito (serviço desativado), remova-a em vez de deixá-la
   acumulando.

```sh
# quem está consumindo cada fila, pela API de administração
curl -s -u "$USUARIO:$SENHA" "$ADMIN_URL/api/queues" \
  | jq -r '.[] | "\(.name)\t\(.consumers)\t\(.messages_ready)"'
```

## Como confirmar

A auditoria deixa de apontar a fila. Na mão, o número de consumidores sai de 0 e a contagem de
mensagens prontas começa a cair entre duas leituras — só o primeiro não basta: um consumidor
conectado que não confirma mensagem mantém a fila crescendo.

## Quando NÃO fazer

Fila de uso sazonal, que fica sem consumidor entre execuções por desenho (lote noturno, fila de
reprocessamento manual). Aí o acúmulo é esperado, e o caminho é registrar como risco aceito com
prazo de revisão em vez de criar um consumidor para calar o alerta.
```

- [ ] **Step 5: Rodar os testes das regras e a fitness function de remediação**

Run: `.venv/bin/python -m pytest tests/test_regras_de_fila.py tests/test_remediacao.py tests/test_perguntas_fila.py -q`
Expected: PASS (todos, incluindo o `test_o_limiar_aponta_para_regra_registrada` que faltava)

- [ ] **Step 6: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| renomear `fila_sem_consumidor.md` para `.md.bak` | `test_a_remediacao_tem_os_quatro_blocos` e `test_toda_regra_que_vira_achado_tem_remediacao` |
| marcar `fila_sem_consumidor` como `esperada: True` | `test_nao_e_esperada` |
| trocar a severidade do registro para `low` | `test_severidade_padrao_bate_com_o_limiar_da_pergunta` |
| apagar o bloco "Quando NÃO fazer" do arquivo | `test_a_remediacao_tem_os_quatro_blocos` |

- [ ] **Step 7: Rodar a suíte inteira e commitar**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 568

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): papel fila com quatro perguntas e a regra de fila sem consumidor"
```

---

## Task 9: `lib/catalogo_api.py` — o conhecimento de produto, validado no carregamento

**Files:**
- Create: `scripts/lib/catalogo_api.py`
- Test: `tests/test_catalogo_api.py`

Espelha o `lib/catalogo.py` (que serve o `promql`) mas valida uma linguagem diferente: o alvo é JSON de API, não PromQL. A validação é dura **no carregamento**, não na coleta — arquivo errado é recusado no teste, não no relatório de quem usa.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_catalogo_api.py
"""A validação do catálogo de API acontece no CARREGAMENTO.

Arquivo que cita pergunta inexistente, transformação que não existe ou caminho que sai do host
declarado é recusado aqui — no teste da skill, não no relatório de quem a usa. Erro de catálogo
que só aparece na coleta vira "a API não respondeu", e manda o dono caçar problema de rede que
não existe.
"""
import pytest

from lib.catalogo_api import CatalogoInvalido, carregar_arquivo, familias

BASE = """
familia = "exemplo-mgmt"
prioridade = 20

[identificacao]
caminho = "/api/overview"
exige_chaves = ["product_name"]
aceita_401 = true
"""

PERGUNTA_OK = """
[[pergunta]]
id = "fila.filas"
caminho = "/api/queues"
lista = ""
campos = { nome = "/name", prontas = "/messages_ready" }
transformar = { prontas = "inteiro" }
ordenar_por = "prontas"
ordem = "desc"
desempate = "nome"
limite = 10
"""


def _arquivo(tmp_path, conteudo, nome="exemplo-mgmt.toml"):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def test_carrega_arquivo_valido(tmp_path):
    dados = carregar_arquivo(_arquivo(tmp_path, BASE + PERGUNTA_OK))

    assert dados["familia"] == "exemplo-mgmt"
    assert dados["pergunta"][0]["id"] == "fila.filas"


def test_recusa_pergunta_que_nao_existe_no_registro(tmp_path):
    ruim = BASE + PERGUNTA_OK.replace('id = "fila.filas"', 'id = "fila.inventada"')

    with pytest.raises(CatalogoInvalido, match="não existe no registro"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_transformacao_desconhecida(tmp_path):
    ruim = BASE + PERGUNTA_OK.replace('prontas = "inteiro"', 'prontas = "sql"')

    with pytest.raises(CatalogoInvalido, match="transformação"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_lista_sem_desempate(tmp_path):
    """`fila.filas` é lista; empate sem desempate muda o relatório entre rodadas iguais."""
    ruim = BASE + PERGUNTA_OK.replace('desempate = "nome"\n', "")

    with pytest.raises(CatalogoInvalido, match="desempate"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_caminho_que_sai_do_host(tmp_path):
    """O ponto mais perigoso do arquivo: `caminho` é juntado à `admin_url`, e `//outro.test/x`
    é URL protocolo-relativa — trocaria o host e mandaria a CREDENCIAL para lá."""
    ruim = BASE + PERGUNTA_OK.replace('caminho = "/api/queues"',
                                      'caminho = "//outro.test/api/queues"')

    with pytest.raises(CatalogoInvalido, match="caminho"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_caminho_absoluto_com_esquema(tmp_path):
    ruim = BASE + PERGUNTA_OK.replace('caminho = "/api/queues"',
                                      'caminho = "http://outro.test/api/queues"')

    with pytest.raises(CatalogoInvalido, match="caminho"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_caminho_que_sobe_de_diretorio(tmp_path):
    ruim = BASE + PERGUNTA_OK.replace('caminho = "/api/queues"',
                                      'caminho = "/api/../../admin"')

    with pytest.raises(CatalogoInvalido, match="caminho"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_caminho_sem_barra_inicial(tmp_path):
    ruim = BASE + PERGUNTA_OK.replace('caminho = "/api/queues"', 'caminho = "api/queues"')

    with pytest.raises(CatalogoInvalido, match="caminho"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_identificacao_sem_exige_chaves(tmp_path):
    """Sem chave exigida, QUALQUER JSON de 200 vira esta família, e a primeira do catálogo
    responderia por todo componente."""
    ruim = BASE.replace('exige_chaves = ["product_name"]', "") + PERGUNTA_OK

    with pytest.raises(CatalogoInvalido, match="exige_chaves"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_limiar_que_cita_regra_desconhecida(tmp_path):
    ruim = BASE + PERGUNTA_OK + """
limiar = { quando = "prontas > 0", regra = "regra_que_nao_existe", severidade = "high" }
"""

    with pytest.raises(CatalogoInvalido, match="regra"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_limiar_com_expressao_invalida(tmp_path):
    ruim = BASE + PERGUNTA_OK + """
limiar = { quando = "prontas / consumidores > 2", regra = "fila_sem_consumidor", severidade = "high" }
"""

    with pytest.raises(CatalogoInvalido, match="limiar"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_recusa_derivacao_desconhecida(tmp_path):
    ruim = BASE + PERGUNTA_OK + """
derivar = { taxa = { tipo = "regressao", de = "/a" } }
"""

    with pytest.raises(CatalogoInvalido, match="derivação"):
        carregar_arquivo(_arquivo(tmp_path, ruim))


def test_familias_vem_em_ordem_estavel(tmp_path):
    """Ordem estável decide quem responde num empate de identificação — e isso não pode
    depender da ordem do sistema de arquivos."""
    _arquivo(tmp_path, BASE + PERGUNTA_OK, "zulu.toml")
    _arquivo(tmp_path, BASE.replace("exemplo-mgmt", "alfa-mgmt") + PERGUNTA_OK, "alfa.toml")

    assert [f["familia"] for f in familias(tmp_path)] == ["alfa-mgmt", "exemplo-mgmt"]


def test_o_catalogo_de_verdade_carrega():
    """O arquivo que a skill publica passa pela própria validação."""
    assert [f["familia"] for f in familias()] != []
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_catalogo_api.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.catalogo_api'`

- [ ] **Step 3: Implementar**

```python
# scripts/lib/catalogo_api.py
"""Carrega os arquivos de família de API — o conhecimento de produto que NÃO vira código.

Irmão do `lib/catalogo.py` (que serve o `promql`), mas a linguagem é outra: aqui o alvo é JSON
de API de administração, não PromQL.

A validação é dura e acontece no CARREGAMENTO. Erro de catálogo que só aparece na coleta vira
"a API não respondeu" no relatório, e manda o dono caçar problema de rede que não existe.

A regra mais importante deste módulo é a do `caminho`: ele é juntado à `admin_url` do
componente, e é por ele que a CREDENCIAL sai da máquina. `//outro.test/x` é URL
protocolo-relativa e trocaria o host inteiro — o `check_allowed` pegaria depois, mas um arquivo
de catálogo não tem por que chegar perto dessa fronteira.
"""
import tomllib
from pathlib import Path

from lib.extracao import DERIVACOES, TRANSFORMACOES

PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "apis"


class CatalogoInvalido(Exception):
    """Arquivo de família de API que a skill se recusa a interpretar."""


def _validar_caminho(nome_do_arquivo, onde, caminho):
    """O caminho é relativo à `admin_url` e não pode sair dela. Nunca."""
    cru = str(caminho or "")
    if not cru.startswith("/"):
        raise CatalogoInvalido(
            f"{nome_do_arquivo}: caminho {cru!r} em {onde} precisa começar com '/'")
    if cru.startswith("//") or "://" in cru:
        raise CatalogoInvalido(
            f"{nome_do_arquivo}: caminho {cru!r} em {onde} aponta para outro host — o caminho "
            f"é relativo à `admin_url` do componente, e é por ele que a credencial sai")
    if ".." in cru.split("/"):
        raise CatalogoInvalido(
            f"{nome_do_arquivo}: caminho {cru!r} em {onde} sobe de diretório")


def _validar_pergunta(nome_do_arquivo, pergunta, registro, regras):
    id_ = pergunta.get("id")
    if id_ not in registro:
        raise CatalogoInvalido(
            f"{nome_do_arquivo}: pergunta {id_!r} não existe no registro de perguntas "
            f"canônicas")
    _validar_caminho(nome_do_arquivo, id_, pergunta.get("caminho"))

    for campo, tipo in (pergunta.get("transformar") or {}).items():
        if tipo not in TRANSFORMACOES:
            raise CatalogoInvalido(
                f"{nome_do_arquivo}: transformação {tipo!r} em {id_}.{campo} não existe; as "
                f"permitidas são {', '.join(TRANSFORMACOES)}")

    for nome, regra in (pergunta.get("derivar") or {}).items():
        if regra.get("tipo") not in DERIVACOES:
            raise CatalogoInvalido(
                f"{nome_do_arquivo}: derivação {regra.get('tipo')!r} em {id_}.{nome} não "
                f"existe; as permitidas são {', '.join(DERIVACOES)}")

    if registro[id_]["forma"] == "lista" and "lista" in pergunta \
            and not pergunta.get("desempate"):
        raise CatalogoInvalido(
            f"{nome_do_arquivo}: {id_} é lista e não declara `desempate` — empate de valor "
            f"mudaria o relatório entre rodadas")

    limiar = pergunta.get("limiar")
    if limiar:
        from lib import limiar as limiar_mod

        if limiar.get("regra") not in regras:
            raise CatalogoInvalido(
                f"{nome_do_arquivo}: o limiar de {id_} cita a regra {limiar.get('regra')!r}, "
                f"que não está em lib/regras.py — achado sem registro é achado sem remediação")
        try:
            limiar_mod.compilar(limiar.get("quando"))
        except limiar_mod.LimiarInvalido as erro:
            raise CatalogoInvalido(
                f"{nome_do_arquivo}: limiar de {id_} inválido — {erro}") from erro


def carregar_arquivo(caminho):
    from lib.perguntas import PERGUNTAS
    from lib.regras import REGRAS

    caminho = Path(caminho)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise CatalogoInvalido(f"{caminho.name}: TOML inválido — {erro}") from erro

    for obrigatorio in ("familia", "prioridade", "identificacao"):
        if obrigatorio not in dados:
            raise CatalogoInvalido(f"{caminho.name}: falta {obrigatorio!r}")

    identificacao = dados["identificacao"]
    _validar_caminho(caminho.name, "identificacao", identificacao.get("caminho"))
    if not identificacao.get("exige_chaves"):
        raise CatalogoInvalido(
            f"{caminho.name}: identificacao sem `exige_chaves` — sem chave exigida, qualquer "
            f"JSON que responda 200 vira esta família, e a primeira do catálogo responderia "
            f"por todo componente")

    for pergunta in dados.get("pergunta", []):
        _validar_pergunta(caminho.name, pergunta, PERGUNTAS, REGRAS)
    return dados


def familias(pasta=PASTA):
    """Todas as famílias, em ordem estável: prioridade, depois nome.

    Ordem estável importa: é ela que decide quem responde quando duas famílias identificam o
    mesmo componente, e isso não pode depender da ordem do sistema de arquivos.
    """
    carregadas = [carregar_arquivo(p) for p in sorted(Path(pasta).glob("*.toml"))]
    return sorted(carregadas, key=lambda f: (f["prioridade"], f["familia"]))
```

- [ ] **Step 4: Criar a pasta e rodar**

```bash
mkdir -p ~/.claude/skills/sw-infra-audit/references/apis
```

Run: `.venv/bin/python -m pytest tests/test_catalogo_api.py -q`
Expected: 13 PASS, 1 FAIL (`test_o_catalogo_de_verdade_carrega` — a pasta está vazia até a Task 11)

- [ ] **Step 5: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| `_validar_caminho` aceitar `//` | `test_recusa_caminho_que_sai_do_host` |
| não exigir `exige_chaves` | `test_recusa_identificacao_sem_exige_chaves` |
| não compilar o limiar na validação | `test_recusa_limiar_com_expressao_invalida` |
| ordenar `familias()` por `Path.glob` sem `sorted` | `test_familias_vem_em_ordem_estavel` |

- [ ] **Step 6: Sem commit ainda** — fecha junto com a Task 10.

---

## Task 10: o adaptador `admin_http`

**Files:**
- Create: `scripts/lib/adaptadores/admin_http.py`
- Modify: `scripts/lib/adaptadores/__init__.py`
- Test: `tests/test_adaptador_admin_http.py`

Mesmo contrato dos outros: `perguntar(pergunta, componente, contexto)` devolve valor com fonte, ou `sem_dados` com motivo. **Nunca levanta.**

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_adaptador_admin_http.py
"""O adaptador que fala com API de administração.

Ele não sabe o que é RabbitMQ. Sabe perguntar "que família você é?" olhando as chaves que o
JSON de identificação traz, e a partir daí tudo vem do arquivo daquela família.

Os testes substituem `http_get.get_autenticado` — a fronteira de rede — e não sobem servidor:
o que se quer provar é a decisão do adaptador, não o socket da stdlib.
"""
import json

import pytest

from lib.adaptadores import admin_http

COMPONENTE = {"nome": "broker", "papel": "fila",
              "admin_url": "http://exemplo.test:15672", "senha_env": "SENHA_BROKER"}

OVERVIEW = json.dumps({"product_name": "Exemplo", "product_version": "4.0"})
QUEUES = json.dumps([
    {"name": "pedidos", "messages_ready": 42, "consumers": 3},
    {"name": "emails", "messages_ready": 7, "consumers": 0},
])


@pytest.fixture
def responder(monkeypatch):
    """Mapa caminho -> (status, corpo). O que não estiver no mapa devolve (404, "")."""
    mapa = {}
    pedidos = []

    def falso(url, permitidos, credencial, alvo=None, timeout=None):
        pedidos.append((url, credencial.para(url, alvo) if credencial else None))
        for caminho, resposta in mapa.items():
            if url.endswith(caminho):
                return resposta
        return (404, "")

    monkeypatch.setattr(admin_http.http_get, "get_autenticado", falso)
    return mapa, pedidos


@pytest.fixture
def contexto(monkeypatch):
    monkeypatch.setenv("SENHA_BROKER", "abre-te")
    return {"timeout": 5, "janela": "24h", "at": "2026-09-19T22:00:00Z", "alvo": "prod"}


def test_responde_lista_com_fonte(responder, contexto):
    mapa, _ = responder
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["fonte"].startswith("admin_http:")
    assert {i["nome"] for i in resposta["valor"]} == {"pedidos", "emails"}


def test_sem_admin_url_diz_o_que_declarar(responder, contexto):
    resposta = admin_http.perguntar("fila.filas", {"nome": "broker", "papel": "fila"}, contexto)

    assert resposta["sem_dados"] is True
    assert "admin_url" in resposta["motivo"]


def test_api_que_nao_responde_vira_sem_dados(responder, contexto):
    mapa, _ = responder
    mapa["/api/overview"] = (None, None)

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "não respondeu" in resposta["motivo"]


def test_401_diz_que_falta_credencial_e_nao_que_a_api_caiu(responder, contexto):
    """Distinguir os dois é a diferença entre "exporte a variável" e "a rede está quebrada"."""
    mapa, _ = responder
    mapa["/api/overview"] = (401, "")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "credencial" in resposta["motivo"]


def test_json_que_nao_bate_com_nenhuma_familia(responder, contexto):
    mapa, _ = responder
    mapa["/api/overview"] = (200, json.dumps({"algo": "outro"}))

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "família" in resposta["motivo"]


def test_pergunta_que_a_familia_nao_expoe(responder, contexto):
    mapa, _ = responder
    mapa["/api/overview"] = (200, OVERVIEW)

    resposta = admin_http.perguntar("fila.taxa_entrada_saida", dict(COMPONENTE), contexto)

    if resposta.get("sem_dados"):
        assert "não expõe" in resposta["motivo"]


def test_a_credencial_vai_na_requisicao(responder, contexto):
    mapa, pedidos = responder
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)

    admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert all(cred == ("guest", "abre-te") for _, cred in pedidos)


def test_a_senha_nao_entra_na_resposta(responder, contexto):
    """A resposta vira `report.json`, que vira HTML, que vira PDF."""
    mapa, _ = responder
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert "abre-te" not in json.dumps(resposta)


def test_credencial_faltando_vira_sem_dados_e_nao_excecao(responder, contexto, monkeypatch):
    """O contrato do adaptador é NUNCA levantar: `collect.responder` viraria `erro_interno`,
    e "exporte a variável" merece mensagem melhor que essa."""
    monkeypatch.delenv("SENHA_BROKER")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True
    assert "SENHA_BROKER" in resposta["motivo"]


def test_a_identificacao_e_feita_uma_vez_por_componente(responder, contexto):
    """Identificar por pergunta multiplicaria o tráfego por cinco, sem ganho nenhum."""
    mapa, pedidos = responder
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, QUEUES)
    componente = dict(COMPONENTE)

    admin_http.perguntar("fila.filas", componente, contexto)
    admin_http.perguntar("fila.filas_com_acumulo", componente, contexto)

    assert sum(1 for url, _ in pedidos if url.endswith("/api/overview")) == 1


def test_corpo_que_nao_e_json_vira_sem_dados(responder, contexto):
    mapa, _ = responder
    mapa["/api/overview"] = (200, OVERVIEW)
    mapa["/api/queues"] = (200, "<html>erro</html>")

    resposta = admin_http.perguntar("fila.filas", dict(COMPONENTE), contexto)

    assert resposta["sem_dados"] is True


def test_id_do_adaptador():
    assert admin_http.ID == "admin_http"


def test_registrado_com_prioridade_menor_que_promql():
    """Menor prioridade vence: o específico sabe mais que o genérico."""
    from lib.adaptadores import REGISTRO, todos

    assert REGISTRO["admin_http"]["prioridade"] < REGISTRO["promql"]["prioridade"]
    assert [m.ID for m in todos()][0] == "admin_http"
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_adaptador_admin_http.py -q`
Expected: FAIL — `ImportError: cannot import name 'admin_http' from 'lib.adaptadores'`

- [ ] **Step 3: Implementar o adaptador**

```python
# scripts/lib/adaptadores/admin_http.py
"""Adaptador de API de administração — o mais específico, e o mais frágil.

Ele não sabe o que é RabbitMQ. Sabe perguntar "que família você é?" olhando quais chaves o JSON
de identificação traz, e a partir daí consulta e extração vêm do arquivo daquela família.

Prioridade 20: mais específico que o `promql` (30), porque quem fala a API do próprio produto
sabe mais que um exporter genérico. Também é o primeiro a cair em `sem_dados` — depende de
credencial, de porta de administração aberta e de um endpoint que muda entre versões.

Toda rede passa por `lib/http_get.py`, e toda credencial por `lib/credencial.py`. Aqui não se
importa urllib, não se lê variável de ambiente e não se monta header.
"""
import json

from lib import catalogo_api, credencial as credencial_mod, extracao, http_get

ID = "admin_http"


def base_de(url):
    """A raiz da API a partir do que o dono declarou, sem barra no fim."""
    return str(url or "").rstrip("/")


def _sem_dados(pergunta, motivo):
    return {"pergunta": pergunta, "sem_dados": True, "motivo": motivo}


def _buscar(base, caminho, credencial, contexto_alvo, timeout):
    """(status, documento). `documento` é None quando não deu para ler JSON de lá.

    O objeto `Credencial` vai inteiro para `get_autenticado`: é ELE que chama `.para(url, alvo)`
    e decide se aquela senha pertence a este destino. Passar o par pronto daqui devolveria a
    amarração à convenção.
    """
    url = f"{base}{caminho}"
    # NotConfirmed NÃO é capturado: destino fora da allowlist é erro de programação, e engolir
    # aqui faria bug virar "a API não respondeu".
    status, corpo = http_get.get_autenticado(url, [http_get.destino(base)], credencial,
                                             contexto_alvo, timeout=timeout)
    if status != 200 or not corpo:
        return status, None
    try:
        return status, json.loads(corpo)
    except ValueError:
        return status, None


def familia_do_componente(componente, contexto, credencial):
    """(família, motivo). Um dos dois é sempre None.

    O resultado fica em cache no contexto do alvo: identificar por pergunta multiplicaria o
    tráfego por cinco sem ganho nenhum.
    """
    base = base_de(componente.get("admin_url"))
    cache = contexto.setdefault("_familia_admin", {})
    chave = (base, componente.get("nome"))
    if chave in cache:
        return cache[chave]

    resultado = (None, "a API de administração não respondeu")
    alcancou = False
    for familia in catalogo_api.familias():
        identificacao = familia["identificacao"]
        status, documento = _buscar(base, identificacao["caminho"], credencial,
                                    contexto.get("alvo"), contexto["timeout"])
        if status is not None:
            alcancou = True
        if status == 401 and identificacao.get("aceita_401"):
            resultado = (None, "a API respondeu 401: falta credencial para ler este "
                               "componente (declare `senha_env` no alvos.toml)")
            continue
        if documento is None:
            continue
        if all(extracao.ponteiro(documento, f"/{chave_exigida}") is not None
               for chave_exigida in identificacao["exige_chaves"]):
            resultado = (familia, None)
            break
    else:
        if alcancou and resultado[1].startswith("a API de administração"):
            resultado = (None, "a API respondeu, mas não reconheci a família de administração "
                               "deste componente")

    cache[chave] = resultado
    return resultado


def perguntar(pergunta, componente, contexto):
    """Responde a pergunta, ou devolve `sem_dados` com o motivo real. Nunca levanta."""
    base = base_de(componente.get("admin_url"))
    if not base:
        return _sem_dados(pergunta, "o componente não declara `admin_url` no alvos.toml")

    try:
        credencial = credencial_mod.de_componente(componente, contexto.get("alvo"))
    except credencial_mod.CredencialFaltando as erro:
        return _sem_dados(pergunta, str(erro))

    familia, motivo = familia_do_componente(componente, contexto, credencial)
    if familia is None:
        return _sem_dados(pergunta, motivo)

    declarada = next((p for p in familia.get("pergunta", []) if p["id"] == pergunta), None)
    if declarada is None:
        return _sem_dados(pergunta, f"a API {familia['familia']} não expõe o dado desta "
                                    f"pergunta")

    _, documento = _buscar(base, declarada["caminho"], credencial, contexto.get("alvo"),
                           contexto["timeout"])
    if documento is None:
        return _sem_dados(pergunta, "a API de administração não respondeu a esta consulta")

    try:
        valor = extracao.extrair(documento, declarada)
    except extracao.ExtracaoInvalida as erro:
        # arquivo de catálogo errado é bug da skill; ele não pode virar exceção na coleta
        return _sem_dados(pergunta, f"o catálogo de {familia['familia']} não casa com a "
                                    f"resposta desta API: {erro}")
    if valor in (None, [], {}):
        return _sem_dados(pergunta, "a API respondeu, mas sem o dado desta pergunta")
    return {"pergunta": pergunta, "fonte": f"{ID}:{familia['familia']}", "valor": valor}
```

- [ ] **Step 4: Registrar o adaptador**

Substituir `scripts/lib/adaptadores/__init__.py` inteiro:

```python
"""Registro de adaptadores.

A ordem é a prioridade declarada — menor vence, porque o mais específico sabe mais que o mais
genérico. Empate resolve pelo id, em ordem lexical: sem ordem total, duas fontes equivalentes
produziriam relatórios diferentes para a mesma entrada.
"""
from lib.adaptadores import admin_http, promql

REGISTRO = {
    admin_http.ID: {"modulo": admin_http, "prioridade": 20},
    promql.ID: {"modulo": promql, "prioridade": 30},
}


def todos():
    """Os adaptadores na ordem em que devem ser tentados."""
    return [item["modulo"] for _, item in
            sorted(REGISTRO.items(), key=lambda par: (par[1]["prioridade"], par[0]))]
```

- [ ] **Step 5: Rodar**

Run: `.venv/bin/python -m pytest tests/test_adaptador_admin_http.py -q`
Expected: a maioria PASS; os que dependem do arquivo de família (`test_responde_lista_com_fonte`, `test_a_credencial_vai_na_requisicao`, `test_a_senha_nao_entra_na_resposta`, `test_a_identificacao_e_feita_uma_vez_por_componente`, `test_corpo_que_nao_e_json_vira_sem_dados`) só ficam verdes na Task 11.

- [ ] **Step 6: Sem commit ainda** — fecha com a Task 11.

---

## Task 11: `references/apis/amqp-mgmt.toml` — o produto, em arquivo

**Files:**
- Create: `references/apis/amqp-mgmt.toml`
- Test: `tests/test_familia_amqp.py`

O nome da família é **`amqp-mgmt`**, não `rabbitmq`: o que se descreve é o formato da API de administração AMQP, e qualquer broker que o fale é atendido pelo mesmo arquivo. Nome de produto no arquivo é o começo do `if produto == …`.

- [ ] **Step 1: Escrever o arquivo**

```toml
# references/apis/amqp-mgmt.toml
#
# API de administração no formato AMQP management. O nome é do FORMATO, não do produto: quem
# falar esta API é atendido por este arquivo, e é isso que mantém o núcleo agnóstico.
#
# Todo caminho aqui é de LEITURA. A API tem endpoints de escrita (PUT/DELETE em /api/queues,
# POST em /api/exchanges) e nenhum deles pode aparecer neste arquivo: o adaptador só faz GET,
# mas o catálogo é a lista do que ele alcança, e essa lista é o que um revisor lê.

familia = "amqp-mgmt"
prioridade = 20

[identificacao]
caminho = "/api/overview"
exige_chaves = ["product_name", "rabbitmq_version"]
aceita_401 = true

# --- o que existe
[[pergunta]]
id = "fila.filas"
caminho = "/api/queues"
lista = ""
campos = { nome = "/name", prontas = "/messages_ready", nao_confirmadas = "/messages_unacknowledged", consumidores = "/consumers" }
transformar = { prontas = "inteiro", nao_confirmadas = "inteiro", consumidores = "inteiro" }
ordenar_por = "prontas"
ordem = "desc"
desempate = "nome"
limite = 10

# --- o que está acumulando (e o achado que nasce daí)
[[pergunta]]
id = "fila.filas_com_acumulo"
caminho = "/api/queues"
lista = ""
campos = { nome = "/name", prontas = "/messages_ready", consumidores = "/consumers" }
transformar = { prontas = "inteiro", consumidores = "inteiro" }
ordenar_por = "prontas"
ordem = "desc"
desempate = "nome"
limite = 10
limiar = { quando = "consumidores == 0 e prontas > 0", regra = "fila_sem_consumidor", severidade = "high" }

# --- quem consome
[[pergunta]]
id = "fila.consumidores_por_fila"
caminho = "/api/queues"
lista = ""
campos = { nome = "/name", consumidores = "/consumers" }
transformar = { consumidores = "inteiro" }
ordenar_por = "consumidores"
ordem = "desc"
desempate = "nome"
limite = 10

# --- a que ritmo. A API expõe as taxas já calculadas; a diferença é derivação declarada,
# porque a expressão de limiar não faz aritmética.
[[pergunta]]
id = "fila.taxa_entrada_saida"
caminho = "/api/queues"
lista = ""
campos = { nome = "/name", entrada = "/message_stats/publish_details/rate", saida = "/message_stats/deliver_get_details/rate" }
transformar = { entrada = "decimal", saida = "decimal" }
derivar = { saldo = { tipo = "diferenca", de = "/message_stats/publish_details/rate", menos = "/message_stats/deliver_get_details/rate" } }
ordenar_por = "saldo"
ordem = "desc"
desempate = "nome"
limite = 10
```

> **Por que não há pergunta de fila morta aqui.** `/api/overview` traz o total de mensagens do
> broker, não o da fila morta; distinguir as duas exigiria filtrar por convenção de nome
> (`dlq`, `dead`, `morta`). Convenção de nome é expressão, e expressão não cabe na linguagem
> fechada — pela regra de ouro do spec, isso viraria adaptador próprio, nunca uma extensão da
> linguagem. Publicar o total do broker com o rótulo "fila morta" seria o relatório mentindo
> com número certo. **Decisão do dono, em 2026-09-20: fica fora do plano 2.**

- [ ] **Step 2: Escrever o teste do arquivo**

```python
# tests/test_familia_amqp.py
"""O arquivo de família que a skill publica.

Ele é dado, não código — mas dado que decide para onde a credencial vai, e por isso tem teste.
"""
from lib.catalogo_api import carregar_arquivo, familias

CAMINHO = "references/apis/amqp-mgmt.toml"


def _familia():
    return next(f for f in familias() if f["familia"] == "amqp-mgmt")


def test_o_arquivo_passa_na_propria_validacao():
    assert carregar_arquivo(CAMINHO)["familia"] == "amqp-mgmt"


def test_nao_cita_o_nome_do_produto_na_familia():
    """`amqp-mgmt` é o FORMATO. Nome de produto no identificador é o começo do
    `if produto == ...` que o spec proíbe."""
    assert "rabbit" not in _familia()["familia"].lower()


def test_todo_caminho_e_de_leitura():
    """A API tem PUT e DELETE em /api/queues. O adaptador só faz GET, mas o catálogo é a lista
    do que ele ALCANÇA, e é essa lista que um revisor lê."""
    familia = _familia()
    caminhos = [familia["identificacao"]["caminho"]] + [p["caminho"] for p in familia["pergunta"]]

    for caminho in caminhos:
        assert caminho.startswith("/api/")
        assert not any(verbo in caminho.lower()
                       for verbo in ("delete", "purge", "create", "publish"))


def test_toda_pergunta_declarada_existe_no_registro():
    from lib.perguntas import PERGUNTAS

    for pergunta in _familia()["pergunta"]:
        assert pergunta["id"] in PERGUNTAS


def test_a_prioridade_e_a_do_adaptador():
    from lib.adaptadores import REGISTRO

    assert _familia()["prioridade"] == REGISTRO["admin_http"]["prioridade"]
```

- [ ] **Step 3: Rodar tudo que depende do arquivo**

Run: `.venv/bin/python -m pytest tests/test_familia_amqp.py tests/test_catalogo_api.py tests/test_adaptador_admin_http.py -q`
Expected: PASS

- [ ] **Step 4: Rodar a suíte inteira e commitar**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 603

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): adaptador admin_http e a familia amqp-mgmt em arquivo"
```

---

## Task 12: o relatório sabe desenhar lista de vários campos

**Files:**
- Modify: `scripts/build_report.py`
- Modify: `assets/report-template/template_v3.html`
- Test: `tests/test_relatorio_lista_de_campos.py`

`_ranking()` foi escrito para o `promql`, que devolve itens `{chave, valor}` — um rótulo e um número, com barra proporcional. O `admin_http` devolve `{nome, prontas, consumidores}`: **vários campos por item**. Sem esta task, as filas apareceriam com rótulo vazio e valor zero, e a barra ficaria toda no mesmo tamanho.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_relatorio_lista_de_campos.py
"""Lista de vários campos no relatório.

`_ranking` nasceu para o `promql`, cujo item é `{chave, valor}` — um rótulo, um número, uma
barra. O `admin_http` devolve `{nome, prontas, consumidores}`, e desenhar isso como ranking
produziria rótulo vazio, valor zero e barras todas iguais: um gráfico bonito dizendo nada.

A tabela densa é também o que o dono pediu ao ver o relatório de 213 achados.
"""
from build_report import _resposta

FILAS = {"pergunta": "fila.filas", "fonte": "admin_http:amqp-mgmt", "valor": [
    {"nome": "pedidos", "prontas": 42, "consumidores": 3},
    {"nome": "emails", "prontas": 7, "consumidores": 0},
]}

RANKING = {"pergunta": "entrada.distribuicao_de_status", "fonte": "promql:proxy",
           "valor": [{"chave": "200", "valor": 900}, {"chave": "500", "valor": 12}]}


def test_lista_de_varios_campos_vira_tabela():
    html = _resposta(FILAS)

    assert "<table" in html
    assert "pedidos" in html and "42" in html and "emails" in html


def test_o_cabecalho_usa_os_nomes_dos_campos():
    html = _resposta(FILAS)

    for campo in ("nome", "prontas", "consumidores"):
        assert campo in html


def test_item_de_chave_e_valor_continua_sendo_ranking():
    """Regressão: `entrada.distribuicao_de_status` já está publicada com barra."""
    html = _resposta(RANKING)

    assert 'class="rk"' in html
    assert "<table" not in html


def test_zero_aparece_como_zero_e_nao_some():
    """`consumidores: 0` é o dado mais importante da linha — é ele que vira achado."""
    html = _resposta(FILAS)

    assert ">0<" in html


def test_campo_none_vira_travessao_e_nao_zero():
    resposta = dict(FILAS, valor=[{"nome": "x", "prontas": None, "consumidores": 1}])

    html = _resposta(resposta)

    assert "—" in html


def test_a_fonte_continua_visivel():
    """Número sem fonte não entra no relatório — é o que separa dado de chute."""
    assert "admin_http:amqp-mgmt" in _resposta(FILAS)


def test_lista_vazia_nao_quebra():
    assert _resposta(dict(FILAS, valor=[])) is not None


def test_conteudo_do_campo_e_escapado():
    resposta = dict(FILAS, valor=[{"nome": "<script>alert(1)</script>", "prontas": 1}])

    html = _resposta(resposta)

    assert "<script>" not in html and "&lt;script&gt;" in html
```

- [ ] **Step 2: Rodar e confirmar que falha pelo motivo certo**

Run: `.venv/bin/python -m pytest tests/test_relatorio_lista_de_campos.py -q`
Expected: FAIL — `assert '<table' in html`

- [ ] **Step 3: Implementar**

Em `scripts/build_report.py`, acrescentar antes de `_resposta`:

```python
def _tabela_de_campos(itens):
    """Lista cujos itens têm VÁRIOS campos: tabela densa, uma linha por item.

    `_ranking` desenha `{chave, valor}` com barra proporcional — desenhar `{nome, prontas,
    consumidores}` daquele jeito daria rótulo vazio, valor zero e barras iguais: um gráfico
    bonito dizendo nada.
    """
    colunas = list(itens[0].keys())
    cabecalho = "".join(f"<th>{_e(nome)}</th>" for nome in colunas)
    linhas = []
    for item in itens:
        celulas = "".join(
            f'<td>{"—" if item.get(nome) is None else _numero(item.get(nome))}</td>'
            if isinstance(item.get(nome), (int, float))
            else f'<td>{"—" if item.get(nome) is None else _e(item.get(nome))}</td>'
            for nome in colunas)
        linhas.append(f"<tr>{celulas}</tr>")
    return (f'<table class="campos"><thead><tr>{cabecalho}</tr></thead>'
            f'<tbody>{"".join(linhas)}</tbody></table>')
```

E, dentro de `_resposta`, trocar o bloco da lista:

```python
    if isinstance(valor, list):
        # numa lista, a unidade vale para cada linha — repeti-la embaixo do ranking só confunde
        corpo = _ranking(valor)
```

por:

```python
    if isinstance(valor, list):
        # numa lista, a unidade vale para cada linha — repeti-la embaixo só confunde.
        # Item de {chave, valor} é ranking com barra; item de vários campos é tabela.
        if not valor:
            corpo = '<p class="muted">a consulta não devolveu nenhuma linha.</p>'
        elif set(valor[0]) <= {"chave", "valor"}:
            corpo = _ranking(valor)
        else:
            corpo = _tabela_de_campos(valor)
```

- [ ] **Step 4: Estilo da tabela no template**

Em `assets/report-template/template_v3.html`, junto do bloco `.rk`:

```css
  .campos{width:100%;border-collapse:collapse;margin-top:10px}
  .campos th{font:800 9px/1 var(--sans);letter-spacing:.11em;text-transform:uppercase;
             color:var(--soft);text-align:left;padding:0 10px 7px 0;border-bottom:1px solid var(--line)}
  .campos td{font-family:var(--mono);font-size:11.2px;color:var(--ink2);
             padding:5px 10px 5px 0;border-bottom:1px solid var(--line2)}
  .campos td:first-child{color:var(--ink)}
  .campos tr:last-child td{border-bottom:none}
```

E na seção `@media print`, junto das outras regras de quebra:

```css
  .campos tr{break-inside:avoid;page-break-inside:avoid}
  .campos thead{display:table-header-group}
```

- [ ] **Step 5: Rodar e confirmar verde**

Run: `.venv/bin/python -m pytest tests/test_relatorio_lista_de_campos.py -q`
Expected: PASS (8 testes)

- [ ] **Step 6: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| mandar tudo para `_ranking` | `test_lista_de_varios_campos_vira_tabela` |
| mandar tudo para `_tabela_de_campos` | `test_item_de_chave_e_valor_continua_sendo_ranking` |
| trocar `item.get(nome) is None` por `not item.get(nome)` | `test_zero_aparece_como_zero_e_nao_some` |
| usar f-string sem `_e()` na célula de texto | `test_conteudo_do_campo_e_escapado` |

- [ ] **Step 7: Rodar a suíte inteira e commitar**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 611

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "feat(sw-infra-audit): relatorio desenha lista de varios campos como tabela"
```

---

## Task 13: as travas — o que um revisor precisa poder provar

**Files:**
- Modify: `tests/test_egress.py` *(ou o arquivo onde vive a trava de import)*
- Create: `tests/test_admin_http_somente_leitura.py`
- Test: os dois acima

Nenhuma linha de produção nesta task. São as fitness functions do spec aplicadas ao código novo — e uma delas é a que faz "a auditoria é somente leitura" ser verificável em vez de prometida.

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_admin_http_somente_leitura.py
"""As travas que fazem "somente leitura" ser verificável em vez de prometida.

A API de administração AMQP tem PUT e DELETE em `/api/queues` e POST para publicar mensagem.
Um erro de uma linha no adaptador — um `method=` a mais — transformaria auditoria em operação.
"""
import ast
import inspect
import json
from pathlib import Path

import pytest

from lib import http_get
from lib.adaptadores import admin_http

RAIZ = Path(admin_http.__file__).resolve().parent.parent.parent


def _arvore(modulo):
    return ast.parse(Path(inspect.getfile(modulo)).read_text(encoding="utf-8"))


def test_o_adaptador_nao_importa_rede_nem_subprocesso():
    """Toda rede passa por lib/http_get.py. Um adaptador que abre socket escapa da allowlist."""
    proibidos = {"urllib", "socket", "ssl", "http", "subprocess", "requests", "os"}
    importados = set()
    for no in ast.walk(_arvore(admin_http)):
        if isinstance(no, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])

    assert not (importados & proibidos), f"o adaptador importa {importados & proibidos}"


def test_o_adaptador_nao_le_variavel_de_ambiente():
    """A credencial vem de lib/credencial.py, que é o único lugar que toca o ambiente."""
    fonte = Path(inspect.getfile(admin_http)).read_text(encoding="utf-8")

    assert "environ" not in fonte and "getenv" not in fonte


def test_toda_requisicao_do_adaptador_e_get(monkeypatch):
    """`get_autenticado` é a única função de rede que ele chama, e ela fixa method='GET'."""
    fonte = Path(inspect.getfile(admin_http)).read_text(encoding="utf-8")

    assert "http_get.get_autenticado" in fonte
    for verbo in ("post", "put", "delete", "patch"):
        assert f".{verbo}(" not in fonte.lower()


def test_get_autenticado_fixa_o_metodo_get(monkeypatch):
    vistos = []
    monkeypatch.setattr(http_get._OPENER, "open",
                        lambda req, timeout=None: vistos.append(req) or _ok())

    http_get.get_autenticado("http://exemplo.test:15672/api/queues",
                             [("exemplo.test", 15672)], ("u", "s"))

    assert vistos[0].get_method() == "GET"


def _ok():
    class R:
        status = 200

        def read(self, _n):
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    return R()


def test_nenhum_caminho_do_catalogo_e_de_escrita():
    """O catálogo é a lista do que o adaptador ALCANÇA — é ela que um revisor lê."""
    from lib.catalogo_api import familias

    for familia in familias():
        caminhos = [familia["identificacao"]["caminho"]]
        caminhos += [p["caminho"] for p in familia.get("pergunta", [])]
        for caminho in caminhos:
            assert not any(palavra in caminho.lower() for palavra in
                           ("delete", "purge", "publish", "create", "reset", "restart"))


def test_a_senha_nao_aparece_no_report_json(tmp_path, monkeypatch):
    """A prova de ponta a ponta: a credencial não pode sobreviver até o arquivo."""
    monkeypatch.setenv("SENHA_BROKER", "abre-te-sesamo")
    componente = {"nome": "broker", "papel": "fila",
                  "admin_url": "http://exemplo.test:15672", "senha_env": "SENHA_BROKER"}

    monkeypatch.setattr(admin_http.http_get, "get_autenticado",
                        lambda url, permitidos, cred, alvo=None, timeout=None: (200, "[]"))

    resposta = admin_http.perguntar("fila.filas", componente, {"timeout": 5, "alvo": "prod"})

    assert "abre-te-sesamo" not in json.dumps(resposta)
    assert "abre-te-sesamo" not in json.dumps(componente)
```

- [ ] **Step 2: Estender a trava de import que já existe**

Ler `tests/test_egress.py` e confirmar que a lista de módulos autorizados a importar rede continua sendo só `lib/http_get.py`, e a de `subprocess` só `lib/runner.py`, `build_report.py` e `lib/ignorado.py`. O módulo novo `lib/credencial.py` importa `os` — **acrescentá-lo à lista de quem pode**, com o comentário do porquê:

```python
# lib/credencial.py lê `os.environ` porque é ELE o lugar único onde a senha sai do ambiente.
# Concentrar isso num módulo é o que permite a trava `test_o_adaptador_nao_le_variavel_de_ambiente`.
```

- [ ] **Step 3: Rodar**

Run: `.venv/bin/python -m pytest tests/test_admin_http_somente_leitura.py tests/test_egress.py -q`
Expected: PASS

- [ ] **Step 4: Prova por mutação**

| Mutação | Teste que precisa cair |
|---|---|
| `import urllib.request` no adaptador | `test_o_adaptador_nao_importa_rede_nem_subprocesso` |
| `os.environ["SENHA_BROKER"]` no adaptador | `test_o_adaptador_nao_le_variavel_de_ambiente` |
| acrescentar `caminho = "/api/queues/%2F/fila/contents"` ao catálogo com a palavra `purge` | `test_nenhum_caminho_do_catalogo_e_de_escrita` |
| `perguntar` devolver `{"credencial": credencial.par()}` no retorno | `test_a_senha_nao_aparece_no_report_json` |
| `get_autenticado` usar `method="POST"` | `test_get_autenticado_fixa_o_metodo_get` |

- [ ] **Step 5: Commit**

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-infra-audit && make check
git add -A && git commit -m "test(sw-infra-audit): travas de somente-leitura e de vazamento no admin_http"
```

---

## Task 14: determinismo, documentação e publicação

**Files:**
- Modify: `SKILL.md`
- Modify: `references/commands-allowlist.md`
- Create: `tests/test_determinismo_admin_http.py`

- [ ] **Step 1: Escrever o teste de determinismo**

```python
# tests/test_determinismo_admin_http.py
"""Mesma entrada, mesmo byte.

A quinta fitness function do spec. Com as respostas gravadas e o mesmo `--at`, duas execuções
produzem `report.json` idêntico — inclusive com EMPATE de valor, que é onde a ordem da resposta
da API vazaria para o relatório.
"""
import json

import pytest

from lib.adaptadores import admin_http

EMPATE = json.dumps([
    {"name": "zulu", "messages_ready": 5, "consumers": 0},
    {"name": "alfa", "messages_ready": 5, "consumers": 0},
    {"name": "mike", "messages_ready": 5, "consumers": 0},
])
OVERVIEW = json.dumps({"product_name": "Exemplo", "rabbitmq_version": "4.0"})


@pytest.fixture
def api(monkeypatch):
    def falso(url, permitidos, credencial, alvo=None, timeout=None):
        return (200, OVERVIEW if url.endswith("/api/overview") else EMPATE)

    monkeypatch.setattr(admin_http.http_get, "get_autenticado", falso)


def test_empate_de_valor_sai_na_mesma_ordem_sempre(api):
    componente = {"nome": "broker", "papel": "fila",
                  "admin_url": "http://exemplo.test:15672"}

    primeira = admin_http.perguntar("fila.filas", dict(componente), {"timeout": 5,
                                                                     "alvo": "prod"})
    segunda = admin_http.perguntar("fila.filas", dict(componente), {"timeout": 5,
                                                                    "alvo": "prod"})

    assert [i["nome"] for i in primeira["valor"]] == ["alfa", "mike", "zulu"]
    assert json.dumps(primeira, sort_keys=True) == json.dumps(segunda, sort_keys=True)


def test_a_resposta_serializa_sem_nan(api):
    """NaN escrito no report.json produz JSON inválido para qualquer leitor fora do Python."""
    componente = {"nome": "broker", "papel": "fila",
                  "admin_url": "http://exemplo.test:15672"}

    resposta = admin_http.perguntar("fila.filas", componente, {"timeout": 5, "alvo": "prod"})

    json.dumps(resposta, allow_nan=False)   # levanta ValueError se houver NaN
```

- [ ] **Step 2: Rodar**

Run: `.venv/bin/python -m pytest tests/test_determinismo_admin_http.py -q`
Expected: PASS (2 testes)

- [ ] **Step 3: Documentar na `SKILL.md`**

Na tabela da seção **"Regra: toda decisão é via AskUserQuestion"**, acrescentar a linha:

```markdown
| Componente de fila sem `admin_url` ou sem `senha_env` | declarar o endereço de administração e o nome da variável de senha agora? |
```

Na seção **"Insights por sistema"**, acrescentar o papel novo:

```markdown
**Papel `fila`** — `admin_http` pergunta à API de administração do broker: quais filas existem,
quais acumulam, quem consome cada uma e a que ritmo entram e saem mensagens. Fila com mensagem
pronta e **nenhum consumidor** vira achado `fila_sem_consumidor` (alto), com remediação.

Declarar, no `alvos.toml`:

```toml
[[alvo.componente]]
nome = "broker"
papel = "fila"
admin_url = "http://10.0.0.10:15672"
senha_env = "SENHA_BROKER"      # o NOME da variável, nunca a senha
usuario = "leitor"              # opcional; o padrão é `guest`
```

A senha é lida do ambiente no momento da coleta, vai em header de autenticação e **não entra**
no `alvos.toml`, no argv, no `report.json`, no HTML nem no PDF.
```

Na seção **"Limites"**, onde hoje se descreve o que a skill não faz, acrescentar:

```markdown
A API de administração tem endpoints de escrita (purgar fila, publicar mensagem, remover
exchange). A skill **só faz GET**, e o catálogo em `references/apis/` é a lista completa do que
ela alcança — um teste derruba a suíte se um caminho de escrita aparecer lá.
```

- [ ] **Step 4: Atualizar `references/commands-allowlist.md`**

Acrescentar a seção:

```markdown
## Egresso HTTP autenticado (`admin_http`)

| O que | Onde |
|---|---|
| Método | `GET`, sempre — fixado em `lib/http_get.get_autenticado` |
| Destino | só `(host, porta)` da `admin_url` declarada e confirmada |
| Caminhos | só os de `references/apis/<familia>.toml`; `//`, `..` e esquema absoluto são recusados no carregamento |
| Credencial | header `Authorization: Basic`, montado dentro de `get_autenticado`, que chama `.para(url, alvo)` e recusa par solto |
| Senha na URL | recusada em `check_allowed` (todas as funções de rede) e em `alvos._checar_url` (ao ler a configuração) |
| Origem da senha | variável de ambiente nomeada em `senha_env`, lida por `lib/credencial.py` |
```

- [ ] **Step 5: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 621

- [ ] **Step 6: Registrar no CHANGELOG e publicar**

```bash
cd /var/www/ai-marketplace
make sync SKILL=sw-infra-audit BUMP=minor      # v0.9.0
# escrever a entrada em CHANGELOG.md sob [Não publicado]
make check
git add -A && git commit -m "feat(sw-infra-audit): papel fila responde pela API de administracao (v0.9.0)"
```

- [ ] **Step 7: Marcar o estado do dossiê**

```bash
python3 ~/.claude/skills/sw-brainstorming/scripts/dossie.py estado \
  2026-09-19-insights-por-sistema-e-remediacao-na-sw-infra-audit em-execucao
```

> O dossiê só vira `concluido` quando os planos 3 e 4 também fecharem — o spec declara os quatro.

---

## Self-review

**1. Cobertura do escopo do plano 2.** A linha do spec pede "`admin_http` + linguagem de extração + derivações + papel `fila`":

| Item do spec | Task |
|---|---|
| adaptador `admin_http` | 10, 11 |
| linguagem de extração em arquivo | 3, 9 |
| derivações | 4 |
| papel `fila` (4 perguntas) | 7 |
| limiar → achado + remediação | 5, 6, 8 |
| credencial por `senha_env`, nunca no argv/relatório | 1, 2, 13 |
| egresso com (host, porta) | 1, 9 |
| determinismo com empate | 3, 14 |

**2. Fora de escopo, mantido fora:** papel `cache`, adaptador `sql`, `logql`, perguntas de `entrada` que dependem de rota, papéis `busca`/`storage`/`observabilidade`/`app`.

**3. Duas coisas que o spec não previa e o plano teve de resolver:**

- **`limiar` nunca foi avaliado** (Task 6). O campo existe no registro desde o plano 1 e nenhuma linha o lia — sem esta ponte, `fila_sem_consumidor` seria uma regra que nunca dispara.
- **`_ranking` não desenha item de vários campos** (Task 12). Ele foi escrito para o `{chave, valor}` do `promql`; as filas sairiam com rótulo vazio e valor zero.

**4. Uma pergunta cortada, por decisão do dono (2026-09-20):** `fila.fila_morta`. `/api/overview` não distingue fila morta de fila comum, e identificá-la exige convenção de nome — que não cabe na linguagem fechada. Publicar o total do broker com aquele rótulo seria mentir com número certo. Ficam as 4 perguntas restantes; a fila morta volta quando houver como identificá-la sem inventar linguagem.

**5. Consistência de nomes entre tasks:** `extrair`/`ponteiro`/`transformar`/`derivar` (Task 3–4) são os mesmos usados em `catalogo_api` (9) e `admin_http` (10); `compilar`/`avaliar`/`LimiarInvalido` (5) são os usados em `collect.achados_da_resposta` (6) e na validação do catálogo (9); `Credencial.para(url)` (2) é o que `admin_http._buscar` chama (10).

## Contagem de testes esperada

| Depois da task | Total |
|---|---|
| 1 | 480 |
| 2 | 491 |
| 3 | 512 |
| 4 | 522 |
| 6 | 557 |
| 8 | 568 |
| 11 | 603 |
| 12 | 611 |
| 14 | 621 |

Os números são estimativa do que cada arquivo novo acrescenta; se o real divergir, a suíte é a fonte da verdade, não esta tabela.
