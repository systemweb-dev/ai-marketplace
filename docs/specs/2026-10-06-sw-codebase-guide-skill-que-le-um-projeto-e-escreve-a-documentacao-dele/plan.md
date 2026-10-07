# Plano de implementação — sw-codebase-guide (spike + Plano 1: o piso)

[spec.md](spec.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** uma skill que lê um projeto recebido de terceiro e escreve a documentação dele em
`docs/project/guide.md`, sem recusar nenhum projeto e sem afirmar o que não apurou.

**Arquitetura:** `varrer.py` apura os fatos num `inventory.json` determinístico; o agente escreve
`interpretation.toml` em formato fechado; `montar.py` junta os dois e emite `guide.md`. O
conhecimento de stack mora em TOML, mas **este plano não escreve nenhum** — entrega o piso
universal, que já atende qualquer projeto.

**Stack:** Python 3 (só stdlib: `ast`, `json`, `tomllib`, `subprocess`, `re`, `pathlib`), pytest.
A skill vive em `~/.claude/skills/sw-codebase-guide/` e vai ao repositório por `make sync`.

**Fora deste plano (Plano 2, do spec):** `knowledge.toml` com âncora, `gravar.py`,
`references/stacks/*.toml`, `regras.py`, `dados.py`, caminho ponta a ponta, `--area`,
`guide.html` e PDF.

**Restrições verificáveis (do spec):**

| Restrição | Como o plano checa |
|---|---|
| Mesmos fatos, mesmo documento, byte a byte | Task 10, step 7 — `test_duas_montagens_identicas` sobre `interpretation.toml` congelado |
| Nunca afirmar ausência de dependentes | Task 10, steps 3 e 5 — par positivo (`test_acoplamento_invisivel_aparece_como_mencao`) + negativo (`test_nenhuma_frase_de_ausencia`) |
| Nenhum segredo em nada que seja commitado | Task 2, step 6 (`redact`) e Task 9, step 7 (`test_nenhum_segredo_em_docs_project`) |
| Âncora quebrada não vira confirmado | **Plano 2** — `knowledge.toml` não existe neste plano |
| Sem histórico não omite em silêncio | Task 5, step 4 (`test_sem_repositorio_git_vira_lacuna_com_motivo`, `test_um_commit_so_vira_lacuna_dizendo_quantos`) **e** Task 10, step 5 (`test_secao_de_co_mudanca_existe_com_motivo_sem_historico` — a lacuna chega ao documento, não morre no módulo) |
| `varrer.py` não escreve fora de `docs/project/` | Task 9, step 5 — `test_varrer_so_escreve_em_docs_project` |

**Estrutura de arquivos:**

```
~/.claude/skills/sw-codebase-guide/
  SKILL.md                      Task 11
  scripts/
    varrer.py                   Task 9   orquestra e emite inventory.json
    montar.py                   Task 10  inventory + interpretation → guide.md
    lib/
      redact.py                 Task 2   nenhum segredo sai
      stacks.py                 Task 3   detecta stacks pelos manifestos
      arvore.py                 Task 4   arquivos, tamanho, linguagem, gerado
      historia.py               Task 5   git: co-mudança, idade, concentração
      textual.py                Task 6   grafo textual
      imports.py                Task 7   grafo de import, só nativo
      superficie.py             Task 8   rotas, comandos, jobs e tabelas por convenção
  tests/
    conftest.py                 Task 2
    fixtures/                   cada task cria a sua
    test_*.py
```

---

### Task 1 (SPIKE): regra verificável é extraível com precisão útil?

**Arquivos:**
- Criar: `/tmp/spike_regras.py` (descartável — **não** vira código de produção)
- Criar: `docs/specs/2026-10-06-sw-codebase-guide-skill-que-le-um-projeto-e-escreve-a-documentacao-dele/referencias/spike-regras.md`

**Depende de:** nada

**Por que é a task 1:** é a suposição de maior risco do spec. Se regra verificável não sair com
precisão útil, a camada "o que o sistema faz" perde a metade extraível e vira só
propósito-com-fonte mais perguntas em aberto — e o Plano 2 muda.

**Deu certo se:** de 20 candidatas extraídas de um projeto real, **ao menos 14 (70%)** forem
regra de negócio de verdade quando conferidas à mão.
**Se não:** `regras.py` sai do Plano 2; a camada 3 fica só com propósito-com-fonte e perguntas.

- [x] **Step 1: escolher o projeto e registrar qual é**

Use um projeto real já recebido, com código de negócio (não um exemplo). Anote no arquivo de
referência o caminho e o número de arquivos, para o resultado ser rastreável.

- [x] **Step 2: escrever o extrator descartável**

```python
# /tmp/spike_regras.py
import re, sys
from pathlib import Path

# Cada padrão é um TIPO de regra verificável. O spike mede se eles pegam regra de
# NEGÓCIO ou só mecânica de framework.
PADROES = {
    'enum':        re.compile(r"enum\s+(\w+)|'(\w+)'\s*=>\s*'[^']+'\s*,\s*//"),
    'constante':   re.compile(r'^\s*(?:const|define\(|[A-Z_]{4,}\s*=)\s*([A-Z_]{4,})', re.M),
    'validacao':   re.compile(r"'(\w+)'\s*=>\s*'([^']*(?:required|min:|max:|between:)[^']*)'"),
    'estado':      re.compile(r'(?i)\b(status|state|situacao)\b\s*[=:]\s*[\'"](\w+)[\'"]'),
    'cron':        re.compile(r'(?i)(cron|schedule|everyMinute|daily|hourly)\s*\(\s*[\'"]?([^\'")]*)'),
    'limiar':      re.compile(r'(?i)\b(limite|limit|max|min|threshold|timeout)\w*\s*[=:]\s*(\d+)'),
}
IGNORAR = {'vendor', 'node_modules', '.git', 'dist', 'build', '__pycache__'}

def varrer(raiz):
    achados = []
    for f in Path(raiz).rglob('*'):
        if not f.is_file() or any(p in IGNORAR for p in f.parts):
            continue
        if f.suffix not in {'.php', '.py', '.js', '.ts', '.rb', '.go'}:
            continue
        try:
            texto = f.read_text('utf-8', 'replace')
        except Exception:
            continue
        for tipo, padrao in PADROES.items():
            for m in padrao.finditer(texto):
                linha = texto[:m.start()].count('\n') + 1
                achados.append((tipo, f'{f}:{linha}', m.group(0).strip()[:90]))
    return achados

if __name__ == '__main__':
    for tipo, onde, trecho in varrer(sys.argv[1]):
        print(f'{tipo}\t{onde}\t{trecho}')
```

- [x] **Step 3: rodar e amostrar 20**

Rode: `python3 /tmp/spike_regras.py <caminho-do-projeto> | shuf -n 20 > /tmp/amostra.tsv`
Esperado: 20 linhas, cada uma com tipo, arquivo:linha e o trecho.

Amostrar ao acaso importa: pegar as 20 primeiras mede a ordem do `rglob`, não a precisão.

- [x] **Step 4: conferir as 20 à mão, uma a uma**

Abra cada `arquivo:linha` e classifique: **regra de negócio** (uma decisão que o negócio tomou:
um limite, um estado possível, uma validação de domínio) ou **mecânica** (configuração de
framework, constante técnica, string de UI).

Essa conferência é o produto do spike. Não automatize — automatizar aqui seria medir o extrator
com o próprio extrator.

- [x] **Step 5: escrever o resultado em `referencias/spike-regras.md`**

```markdown
# Spike — regra verificável é extraível?

**Projeto:** <caminho>, <N> arquivos de código
**Data:** <data>
**Amostra:** 20 candidatas sorteadas de <total> achadas

| # | Tipo | Arquivo:linha | Trecho | Regra de negócio? |
|---|---|---|---|---|
| 1 | enum | app/X.php:44 | ... | sim |

**Precisão: <acertos>/20 = <pct>%**

**Por tipo de padrão:**
| Tipo | Achadas | Regra de negócio | Precisão |
|---|---|---|---|

**Decisão:** <regras.py entra no Plano 2 | regras.py sai; camada 3 fica só com
propósito-com-fonte e perguntas em aberto>

**Padrões que valem a pena / que devem ser descartados:** <quais, e por quê>
```

- [x] **Step 6: apagar o descartável**

Rode: `rm /tmp/spike_regras.py /tmp/amostra.tsv`
Esperado: só o `referencias/spike-regras.md` sobrevive. O código do spike não vai para a skill.

---

### Task 2: `redact.py` — nenhum segredo sai

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/redact.py`
- Criar: `~/.claude/skills/sw-codebase-guide/tests/conftest.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_redact.py`

**Depende de:** nada

**Por que vem antes do resto:** tudo que a varredura emite passa por aqui. Construir depois
significa auditar todos os emissores de novo.

**Contrato que esta task publica:**
`redigir(texto: str) -> str` · `eh_chave_de_segredo(chave: str) -> bool` ·
`linha_tem_segredo(linha: str) -> bool` · `chaves_de_env(texto: str) -> list[str]`

- [x] **Step 1: criar o `conftest.py` que dá acesso ao `scripts/`**

```python
# tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
```

- [x] **Step 2: escrever os testes que falham**

```python
# tests/test_redact.py
from lib.redact import (redigir, eh_chave_de_segredo, linha_tem_segredo,
                        chaves_de_env, MASCARA)


def test_valor_de_env_vira_mascara_e_a_chave_fica():
    # Arrange
    texto = 'DB_PASSWORD=sup3rs3cr3t\nAPP_NAME=loja\n'
    # Act
    saida = redigir(texto)
    # Assert
    assert 'sup3rs3cr3t' not in saida
    assert 'DB_PASSWORD' in saida
    assert 'APP_NAME=loja' in saida       # o que não é segredo passa inteiro


def test_chave_privada_inteira_some():
    # Arrange
    texto = '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCA\n-----END RSA PRIVATE KEY-----'  # noscan: fixture deliberada
    # Act
    saida = redigir(texto)
    # Assert
    assert 'MIIEpAIBAAKCA' not in saida


def test_string_de_conexao_perde_a_credencial():
    # Arrange
    texto = 'DATABASE_URL=postgres://joao:senha123@10.0.0.4:5432/loja'
    # Act
    saida = redigir(texto)
    # Assert
    assert 'senha123' not in saida


def test_reconhece_chave_de_segredo_por_nome():
    # Act / Assert
    assert eh_chave_de_segredo('API_KEY')
    assert eh_chave_de_segredo('stripe_secret')
    assert eh_chave_de_segredo('SENHA_BANCO')
    assert not eh_chave_de_segredo('APP_NAME')
    assert not eh_chave_de_segredo('TIMEZONE')


def test_linha_com_token_e_sinalizada():
    # Act / Assert
    assert linha_tem_segredo('const TOKEN = "ghp_abc123def456";')  # noscan: fixture deliberada
    assert not linha_tem_segredo('const TIMEOUT = 30;')


def test_chaves_de_env_traz_o_nome_e_nunca_o_valor():
    # Arrange
    texto = '# comentário\nDB_PASSWORD=sup3rs3cr3t\nexport API_KEY=abc\nAPP_NAME=loja\n\n'
    # Act
    chaves = chaves_de_env(texto)
    # Assert
    assert chaves == ['API_KEY', 'APP_NAME', 'DB_PASSWORD']
    assert all('sup3rs3cr3t' not in c and 'abc' not in c for c in chaves)


# As linhas marcadas `# noscan` carregam valores com FORMA de segredo de propósito:
# um módulo de redação só prova que a guarda funciona se o fixture parecer o real.
# Nenhum é credencial de verdade: a chave da AWS é a que consta na documentação
# oficial deles como exemplo, e o resto é inventado.

# ─── Vazamentos que o juiz da Task 2 reproduziu. Cada um é um falso negativo,
#     que numa guarda de segurança significa credencial publicada.

def test_export_nao_deixa_o_valor_passar():
    # Arrange — `.env` e `*.sh` são o input principal desta skill
    for linha in ('export DB_PASSWORD=senha123',
                  'ENV DB_PASSWORD=senha123',
                  'ARG NPM_TOKEN=npm_abc123'):
        # Act / Assert
        assert 'senha123' not in redigir(linha) and 'npm_abc123' not in redigir(linha), linha


def test_item_de_lista_yaml_e_redigido():
    # Arrange — docker-compose e k8s são os arquivos mais densos em segredo
    for linha in ('      - DB_PASSWORD=senha123', '  - password: senha123'):
        # Act / Assert
        assert 'senha123' not in redigir(linha), linha


def test_varios_pares_na_mesma_linha():
    # Arrange — testar só o primeiro par deixava passar tudo que é compacto
    for linha in ('{"api_key": "abc123"}',
                  '{"db": {"password": "senha123"}}',
                  'const conn = {host: "db", password: "senha123"};',  # noscan: fixture deliberada
                  'headers = {"Authorization": "Bearer ghp_abc123def456"}'):
        # Act
        saida = redigir(linha)
        # Assert
        assert 'abc123' not in saida and 'senha123' not in saida, linha


def test_chave_privada_truncada_some_inteira():
    # Arrange — truncar arquivo é exatamente o que uma skill de documentação faz,
    # e exigir o `-----END` deixava a chave cortada passar inteira
    texto = ('-----BEGIN RSA PRIVATE KEY-----\n'  # noscan: fixture deliberada
             'MIIEpAIBAAKCAsegredo\nMIIEoutralinha')
    # Act
    saida = redigir(texto)
    # Assert
    assert 'MIIEpAIBAAKCAsegredo' not in saida
    assert 'MIIEoutralinha' not in saida


def test_url_de_conexao_sem_usuario():
    # Arrange — o usuário era obrigatório no padrão, e `redis://:senha@` vazava
    # Act
    saida = redigir('REDIS_URL=redis://:senha123@host:6379/0')
    # Assert
    assert 'senha123' not in saida


def test_valor_multilinha_some_inteiro():
    # Arrange
    # Act
    saida = redigir('PRIVATE_TOKEN="linha1\nlinha2segredo\nlinha3"')
    # Assert — redigir linha a linha mascarava só a primeira
    assert 'linha2segredo' not in saida


def test_forma_do_valor_denuncia_sem_o_nome_ajudar():
    # Arrange — nome de chave inocente, valor inconfundível
    for linha in ('X_SIGNATURE=ghp_16C7e42F292c6912E7710c838347Ae178B4a',  # noscan: fixture deliberada
                  'GH_PAT=ghp_16C7e42F292c6912E7710c838347Ae178B4a',  # noscan: fixture deliberada
                  'chave=AKIAIOSFODNN7EXAMPLE'):  # noscan: fixture deliberada
        # Act / Assert
        assert MASCARA in redigir(linha), linha


def test_xml_com_senha():
    # Act / Assert
    assert 'senha123' not in redigir('<password>senha123</password>')


# ─── O outro lado: a guarda não pode destruir informação legítima.
#     Não havia nenhum teste protegendo isto, e `auth` pegava `author`.

def test_nao_corrompe_campo_de_manifesto():
    # Arrange — `author` casava com `auth` e estragava o package.json
    for linha in ('  "author": "Jane Doe <jane@ex.com>",', 'authors = ["Jane Doe"]'):
        # Act / Assert
        assert redigir(linha) == linha, linha


def test_nao_mascara_valor_que_nao_pode_ser_segredo():
    # Arrange
    for linha in ('auth: true', 'token: 0', 'const secret = useMemo(() => f(a), [a]);',
                  'SECRET_KEY = os.environ'):
        # Act / Assert
        assert redigir(linha) == linha, linha


def test_chaves_de_env_nao_mutila_o_nome():
    # Arrange — `.lstrip('export')` é strip de CONJUNTO de caracteres: devolvia
    # `['ken']` para `token=abc` e descartava `port=5432` inteiro
    # Act
    chaves = chaves_de_env('token=abc\nport=5432\nretry=1\nexport FOO=bar\n')
    # Assert
    assert chaves == ['FOO', 'port', 'retry', 'token']


def test_esquema_de_autenticacao_com_espaco():
    # Arrange — o valor tem espaço, e o padrão de par parava nele
    for linha in ("curl -H 'Authorization: Bearer ghp_abc123def' https://api",
                  'Authorization: Basic dXNlcjpzZW5oYTEyMw==',
                  '{"Authorization": "Bearer ghp_abc123def"}'):
        # Act
        saida = redigir(linha)
        # Assert
        assert 'ghp_abc123def' not in saida and 'dXNlcjpzZW5oYTEyMw' not in saida, linha
```

- [x] **Step 3: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_redact.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.redact'`

- [x] **Step 4: escrever o `redact.py`**

```python
"""Impede que segredo e credencial saiam no documento ou no inventário.

Tudo que a varredura emite passa por aqui. A regra é: a CHAVE pode aparecer
(saber que existe `DB_PASSWORD` é informação útil); o VALOR nunca.

Duas decisões que o primeiro desenho errou, e por isso estão escritas:

1. **Não há âncora de início de linha.** A versão anterior usava `^`, e com isso
   `      - DB_PASSWORD=senha` (item de lista YAML) passava inteiro — justamente o
   formato de docker-compose e manifesto k8s, que são os arquivos mais densos em
   segredo de um projeto. Pelo mesmo motivo a varredura é por OCORRÊNCIA, não por
   linha: `{"api_key": "abc"}` tem o par no meio da linha, e testar só o primeiro
   par deixava passar tudo que é compacto.

2. **O nome da chave não é o único gatilho.** `X_SIGNATURE=9f8a...` e
   `GH_PAT=ghp_16C7...` não casam com nenhum nome conhecido. Por isso existe
   `FORMAS`: a forma do valor denuncia sozinha.

E o contrário também importa: mascarar `auth: true` ou `"author": "Jane"` não
protege nada e destrói informação legítima do manifesto. Daí `INOCENTE`.

**Limites conhecidos:** não cobre segredo construído em tempo de execução
(`'x' + 'y'`), nem valor dentro de chamada (`os.environ['K'] = f(...)`), nem
formato binário. É uma guarda de superfície, não um analisador.
"""
import re

MASCARA = '***'

# Nome de chave que denuncia segredo. Casado como SUBSTRING, porque o nome real
# varia muito: `STRIPE_SECRET_KEY`, `senha_banco`, `apiKey`.
# `auth(?!ors?\b)` exclui `author`/`authors` (campo de manifesto) mas MANTÉM
# `Authorization` — a primeira tentativa, `auth(?!or)`, matava os dois.
NOMES = re.compile(
    r'(?i)(senha|password|passwd|secret|token|api[_-]?key|apikey|private[_-]?key'
    r'|credential|auth(?!ors?\b)|access[_-]?key|client[_-]?secret|signature|bearer)'
)

# Forma que denuncia segredo pelo VALOR, mesmo com nome de chave inocente.
FORMAS = re.compile(
    r'(?:ghp_|gho_|ghs_|ghu_|github_pat_|sk-|rk_live|pk_live|xox[baprs]-|AKIA|ASIA)'
    r'[A-Za-z0-9_\-]{8,}'
    r'|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.'          # JWT
)

# Valor que NUNCA é segredo: mascarar aqui só perde informação.
INOCENTE = re.compile(
    r'(?i)^(?:true|false|null|none|nil|undefined|-?\d+(?:\.\d+)?'
    r'|str|int|bool|float|string|number|boolean|any|object)$'
    r'|^(?:os\.environ|process\.env|getenv|env|config|Field|useMemo|useState)$'
    r'|^\$\{|^<%'
)

# Prefixo de declaração que fica ENTRE o começo e a chave.
# `export`, `ENV` e `ARG` entraram porque `.env`, `*.sh` e Dockerfile são input
# direto desta skill e passavam inteiros.
DECLARACAO = (r'(?:export|ENV|ARG|const|let|var|public|private|protected|static'
              r'|define\(|final|readonly)\s+')

# Um par `chave <sep> valor` em qualquer lugar do texto. O valor entre aspas pode
# atravessar linha — é o que faz valor multilinha ser mascarado inteiro.
PAR = re.compile(
    r'[\'"]?(?P<chave>[A-Za-z_][\w.\-]*)[\'"]?'
    r'(?P<sep>\s*(?:=>|:|=)\s*)'
    r'(?P<valor>"[^"]*"|\'[^\']*\'|[A-Za-z0-9_\-./+=:@~!$%^&*]+)'
)

# Valor que some inteiro, não importa a chave.
BLOCOS = [
    # Chave privada: até o END quando ele existe; senão, até a linha em branco ou o
    # fim do texto. Exigir o END deixava passar a chave TRUNCADA — e truncar arquivo
    # é exatamente o que uma skill de documentação faz.
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'
                r'(?:.*?-----END [A-Z ]*PRIVATE KEY-----|.*?(?=\n\s*\n)|.*)', re.S), MASCARA),
    # Credencial em URL de conexão. O usuário é OPCIONAL (`*`, não `+`):
    # `redis://:senha@host` não tem usuário e vazava.
    (re.compile(r'(?i)\b([a-z][a-z0-9+.-]*://)([^:/\s"\']*):([^@\s"\']+)@'),
     r'\1\2:' + MASCARA + '@'),
    # Esquema de autenticação: o valor tem ESPAÇO no meio (`Bearer ghp_...`), e o
    # padrão de par para no espaço — mascarava `Bearer` e deixava o token solto.
    (re.compile(r'(?i)\b(bearer|basic|token)\s+([A-Za-z0-9_\-./+=]{8,})'),
     r'\1 ' + MASCARA),
    # XML/HTML: <password>valor</password>
    (re.compile(r'(?i)<(\w*(?:senha|password|secret|token|key)\w*)>([^<]+)</\1>'),
     r'<\1>' + MASCARA + r'</\1>'),
]


def eh_chave_de_segredo(chave: str) -> bool:
    """O nome da chave denuncia que o valor é segredo?"""
    return bool(NOMES.search(chave))


def _mascarar_par(m, texto: str) -> str:
    chave, sep, valor = m.group('chave'), m.group('sep'), m.group('valor')
    nu = valor.strip('"\'')

    # chamada de função, não valor: `const secret = useMemo(() => ...)`
    if m.end() < len(texto) and texto[m.end()] == '(':
        return m.group(0)
    if INOCENTE.search(nu) or not nu:
        return m.group(0)
    if eh_chave_de_segredo(chave) or FORMAS.search(nu):
        return f'{chave}{sep}{MASCARA}'
    return m.group(0)


def redigir(texto: str) -> str:
    """Devolve o texto sem valor de segredo. A chave permanece; o valor vira ***."""
    for padrao, troca in BLOCOS:
        texto = padrao.sub(troca, texto)
    return PAR.sub(lambda m: _mascarar_par(m, texto), texto)


def linha_tem_segredo(linha: str) -> bool:
    """Esta linha não pode ser impressa como está?"""
    return linha != redigir(linha)


def chaves_de_env(texto: str) -> list:
    """Só os NOMES das variáveis de um arquivo de ambiente. Nunca os valores.

    Saber que o projeto usa `STRIPE_SECRET` é informação útil para quem chega; o
    valor nunca pode sair. Extrair a chave aqui, em vez de redigir o valor depois,
    é o que garante que não há caminho pelo qual o valor chegue ao inventário.
    """
    chaves = []
    for linha in texto.split('\n'):
        linha = linha.strip()
        if not linha or linha.startswith('#') or '=' not in linha:
            continue
        # `re.sub` de PREFIXO, não `lstrip`: `lstrip('export')` é strip de conjunto
        # de caracteres e devolvia `['ken']` para `token=abc` e `[]` para `port=5432`.
        chave = re.sub(r'^export\s+', '', linha).split('=', 1)[0].strip().strip('"\'')
        if re.fullmatch(r'[A-Za-z_][\w.]*', chave):
            chaves.append(chave)
    return sorted(set(chaves))
```

- [x] **Step 5: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_redact.py -v`
Esperado: 18 passed

- [x] **Step 6: prova por mutação — a guarda funciona mesmo?**

Troque `if m and eh_chave_de_segredo(m.group(2)):` por `if False:` e rode os testes.
Esperado: `test_valor_de_env_vira_mascara_e_a_chave_fica` **FALHA**.
Depois **desfaça a mutação** e confirme que volta a passar.

Teste verde prova que o teste roda, não que a guarda funciona. Esta é a checagem que separa os
dois.

---

### Task 3: `stacks.py` — quais stacks existem neste projeto

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/stacks.py`
- Criar: `~/.claude/skills/sw-codebase-guide/tests/fixtures/poliglota/web/package.json`
- Criar: `~/.claude/skills/sw-codebase-guide/tests/fixtures/poliglota/api/composer.json`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_stacks.py`

**Depende de:** Task 2 (usa o `conftest.py`)

**Contrato que esta task publica:** `detectar(raiz: Path) -> list[dict]`, cada item
`{'stack': str, 'manifesto': str, 'caminho': str}`

- [x] **Step 1: criar a fixture poliglota**

```json
{ "name": "loja-web", "dependencies": { "react": "^18.0.0" } }
```
em `tests/fixtures/poliglota/web/package.json`, e

```json
{ "name": "loja/api", "require": { "php": "^8.1" } }
```
em `tests/fixtures/poliglota/api/composer.json`.

Projeto poliglota é o caso normal — a fixture precisa ser um desde o primeiro teste.

- [x] **Step 2: escrever o teste que falha**

```python
# tests/test_stacks.py
from pathlib import Path
from lib.stacks import detectar

FIXTURES = Path(__file__).parent / 'fixtures'


def test_acha_as_duas_stacks_de_um_projeto_poliglota():
    # Arrange
    raiz = FIXTURES / 'poliglota'
    # Act
    achadas = detectar(raiz)
    # Assert
    nomes = sorted(c['stack'] for c in achadas)
    assert nomes == ['node', 'php']


def test_informa_onde_cada_stack_mora():
    # Arrange
    raiz = FIXTURES / 'poliglota'
    # Act
    por_stack = {c['stack']: c for c in detectar(raiz)}
    # Assert
    assert por_stack['node']['caminho'] == 'web'
    assert por_stack['php']['caminho'] == 'api'
    assert por_stack['node']['manifesto'] == 'package.json'


def test_projeto_sem_manifesto_devolve_lista_vazia(tmp_path):
    # Arrange
    (tmp_path / 'leiame.txt').write_text('oi')
    # Act / Assert
    assert detectar(tmp_path) == []
```

- [x] **Step 3: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_stacks.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.stacks'`

- [x] **Step 4: escrever o `stacks.py`**

```python
"""Detecta as stacks do projeto.

Projeto poliglota é o caso normal: `/web` com package.json e `/api` com
composer.json são DOIS componentes, e a fronteira entre eles é onde mais se
quebra coisa sem perceber.

Duas lições de rodar contra projeto real, e por isso estão escritas:

1. **Manifesto não é o único sinal.** O próprio marketplace tem 210 arquivos
   Python e nenhum `pyproject.toml`: a regra só-manifesto devolvia duas stacks
   `node` que eram fixture de eval de outra skill, e silenciava a linguagem que é
   de fato o projeto. Pior, o grafo de import decide o que parsear pela lista de
   stacks — então os 210 arquivos não eram nem parseados nem declarados como
   lacuna. Daí o segundo sinal: contagem de extensão.

2. **Diretório de build tem manifesto dentro.** `.next/package.json` virava
   componente, e num projeto Next.js dois dos três componentes eram lixo gerado.
"""
import os
from collections import Counter
from pathlib import Path

MANIFESTOS = {
    'package.json': 'node',
    'composer.json': 'php',
    'go.mod': 'go',
    'pyproject.toml': 'python',
    'requirements.txt': 'python',
    'Cargo.toml': 'rust',
    'Gemfile': 'ruby',
    'pom.xml': 'java',
    'build.gradle': 'java',
}

# Dependência de terceiro, artefato de build e cache. `.next` e companhia entraram
# porque têm manifesto dentro e viravam componente fantasma.
IGNORAR = {
    'vendor', 'node_modules', 'bower_components', '.git', '__pycache__', '.venv',
    'venv', 'dist', 'build', 'out', 'target', 'coverage',
    '.next', '.nuxt', '.svelte-kit', '.turbo', '.cache', '.terraform', '.tox',
    # cache de ferramenta e config de editor: apareciam como EVIDÊNCIA de símbolo no
    # documento (`.ruff_cache/0.16.3/11569727403539023932`), que não ajuda ninguém
    '.ruff_cache', '.pytest_cache', '.mypy_cache', '.claude', '.idea', '.vscode',
}

# Extensão → stack, para a linguagem que domina o projeto sem nenhum manifesto.
EXTENSOES = {
    '.py': 'python', '.php': 'php', '.go': 'go', '.rb': 'ruby',
    '.js': 'node', '.jsx': 'node', '.ts': 'node', '.tsx': 'node', '.vue': 'node',
    '.java': 'java', '.cs': 'dotnet', '.rs': 'rust',
}
MIN_ARQUIVOS = 5      # abaixo disso é script solto, não stack do projeto


def caminhar(raiz):
    """Percorre o projeto podando o que é ignorado, em ordem estável.

    `rglob('*')` materializava 181.975 caminhos para 2.036 úteis num projeto real
    (5 s, 231 MB de pico) porque desce em `node_modules` e `vendor` antes de
    filtrar. A poda em `dirs[:]` corta isso cerca de 90 vezes.
    """
    for pasta, pastas, arquivos in os.walk(raiz):
        pastas[:] = sorted(d for d in pastas if d not in IGNORAR)
        for nome in sorted(arquivos):
            yield Path(pasta) / nome


def detectar(raiz) -> list:
    """Os componentes do projeto: um por manifesto, mais a linguagem não declarada."""
    raiz = Path(raiz)
    achados, vistos, por_extensao, declaradas = [], set(), Counter(), set()

    for arquivo in caminhar(raiz):
        stack = MANIFESTOS.get(arquivo.name)
        if stack is None and arquivo.suffix.lower() == '.csproj':
            stack = 'dotnet'

        if stack is not None:
            caminho = str(arquivo.parent.relative_to(raiz))
            caminho = '.' if caminho == '.' else caminho
            # `pyproject.toml` + `requirements.txt` na mesma pasta é a mesma stack,
            # e o documento imprimia a linha duas vezes.
            if (stack, caminho) not in vistos:
                vistos.add((stack, caminho))
                achados.append({'stack': stack, 'manifesto': arquivo.name,
                                'caminho': caminho, 'por': 'manifesto'})
            declaradas.add(stack)
        else:
            lingua = EXTENSOES.get(arquivo.suffix.lower())
            if lingua:
                por_extensao[lingua] += 1

    for stack, quantos in sorted(por_extensao.items()):
        if stack not in declaradas and quantos >= MIN_ARQUIVOS:
            achados.append({'stack': stack, 'manifesto': None, 'caminho': '.',
                            'por': f'{quantos} arquivos, nenhum manifesto declara'})

    return sorted(achados, key=lambda a: (a['caminho'], a['stack']))
```

- [x] **Step 5: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_stacks.py -v`
Esperado: 3 passed

---

### Task 4: `arvore.py` — arquivos, tamanho, linguagem, o que é gerado

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/arvore.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_arvore.py`

**Depende de:** Task 3 (reusa `IGNORAR`)

**Contrato que esta task publica:** `varrer(raiz: Path, teto_bytes: int = 1_000_000) -> list[dict]`,
cada item `{'caminho': str, 'bytes': int, 'linguagem': str, 'gerado': bool, 'acima_do_teto': bool}`

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_arvore.py
from lib.arvore import varrer


def test_pula_vendor_e_node_modules(tmp_path):
    # Arrange
    (tmp_path / 'app').mkdir()
    (tmp_path / 'app' / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'vendor' / 'lib').mkdir(parents=True)
    (tmp_path / 'vendor' / 'lib' / 'Grande.php').write_text('<?php // 3rd party')
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'x.js').write_text('module.exports={}')
    # Act
    caminhos = [a['caminho'] for a in varrer(tmp_path)]
    # Assert
    assert caminhos == ['app/Pedido.php']


def test_classifica_linguagem_pela_extensao(tmp_path):
    # Arrange
    (tmp_path / 'a.php').write_text('<?php')
    (tmp_path / 'b.py').write_text('x = 1')
    # Act
    por_caminho = {a['caminho']: a['linguagem'] for a in varrer(tmp_path)}
    # Assert
    assert por_caminho['a.php'] == 'php'
    assert por_caminho['b.py'] == 'python'


def test_marca_arquivo_gerado(tmp_path):
    # Arrange
    (tmp_path / 'app.min.js').write_text('var a=1')
    (tmp_path / 'app.js').write_text('var a = 1')
    # Act
    por_caminho = {a['caminho']: a['gerado'] for a in varrer(tmp_path)}
    # Assert
    assert por_caminho['app.min.js'] is True
    assert por_caminho['app.js'] is False


def test_arquivo_acima_do_teto_entra_mas_nao_e_lido(tmp_path):
    # Arrange
    (tmp_path / 'dump.sql').write_text('x' * 5000)
    # Act
    item = varrer(tmp_path, teto_bytes=1000)[0]
    # Assert
    assert item['bytes'] == 5000
    assert item['acima_do_teto'] is True


def test_ordem_e_estavel(tmp_path):
    # Arrange
    for nome in ('c.py', 'a.py', 'b.py'):
        (tmp_path / nome).write_text('x = 1')
    # Act
    primeira = [a['caminho'] for a in varrer(tmp_path)]
    segunda = [a['caminho'] for a in varrer(tmp_path)]
    # Assert — ordem instável quebraria a idempotência do documento (Task 10)
    assert primeira == segunda == ['a.py', 'b.py', 'c.py']
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_arvore.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.arvore'`

- [x] **Step 3: escrever o `arvore.py`**

```python
"""Árvore de arquivos do projeto: o que existe, de que tamanho e em que linguagem.

A ordem é estável por desenho — o documento precisa dar diff, e ordem instável
tornaria duas rodadas diferentes sem nada ter mudado.
"""
from pathlib import Path

from lib.stacks import IGNORAR, caminhar

LINGUAGENS = {
    '.php': 'php', '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.go': 'go', '.rb': 'ruby',
    '.java': 'java', '.cs': 'csharp', '.rs': 'rust', '.sql': 'sql',
    '.html': 'html', '.css': 'css', '.scss': 'css', '.vue': 'vue',
    '.blade.php': 'blade', '.twig': 'twig', '.yml': 'yaml', '.yaml': 'yaml',
    '.json': 'json', '.toml': 'toml', '.md': 'markdown', '.sh': 'shell',
}

# Sufixo que denuncia arquivo gerado: ele infla a contagem e polui o grafo.
GERADOS = ('.min.js', '.min.css', '.lock', '.map', '-lock.json', '.pyc', '.generated.ts')


def linguagem_de(caminho: Path) -> str:
    nome = caminho.name.lower()
    # sufixo mais LONGO primeiro: na ordem de inserção `.php` vencia `.blade.php`
    # e a linguagem `blade` nunca era atribuída
    for sufixo, lingua in sorted(LINGUAGENS.items(), key=lambda kv: -len(kv[0])):
        if nome.endswith(sufixo):
            return lingua
    # Dotfile composto (`.env.production`, `.env.teste`) tem `suffix == '.production'`,
    # e o fallback inventava a linguagem "production".
    if caminho.name.startswith('.'):
        return 'config'
    return caminho.suffix.lstrip('.').lower() or 'sem-extensao'


def varrer(raiz, teto_bytes: int = 1_000_000) -> list:
    """Lista os arquivos do projeto, em ordem estável."""
    raiz = Path(raiz)
    itens = []
    # `caminhar` poda as pastas ignoradas durante a descida. `rglob('*')` descia em
    # `node_modules` e `vendor` para só então filtrar: 181.975 caminhos materializados
    # para 2.036 úteis num projeto real, 5 s e 231 MB de pico.
    for arquivo in caminhar(raiz):
        if not arquivo.is_file() or arquivo.is_symlink():
            continue
        tamanho = arquivo.stat().st_size
        itens.append({
            'caminho': str(arquivo.relative_to(raiz)),
            'bytes': tamanho,
            'linguagem': linguagem_de(arquivo),
            'gerado': arquivo.name.lower().endswith(GERADOS),
            'acima_do_teto': tamanho > teto_bytes,
        })
    return sorted(itens, key=lambda i: i['caminho'])
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_arvore.py -v`
Esperado: 5 passed

- [x] **Step 5: prova por mutação na guarda do `IGNORAR`**

Troque `if any(p in IGNORAR for p in ...)` por `if False:` e rode.
Esperado: `test_pula_vendor_e_node_modules` **FALHA**. Desfaça e confirme o verde.

---

### Task 5: `historia.py` — git, e o caso normal de não ter git

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/historia.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_historia.py`

**Depende de:** Task 2 (usa o `conftest.py`)

**Contrato que esta task publica:** `historico(raiz: Path) -> dict` com as chaves
`{'commits': int, 'commits_descartados': int, 'co_mudanca': list, 'lacuna': str | None}`

> `idade` saiu do contrato: nada no Plano 1 consome esse campo, e campo sem consumidor é
> campo sem teste. Volta no Plano 2, se a concentração de risco precisar dele.

**Restrição verificável:** *sem histórico não omite em silêncio* — step 5.

- [x] **Step 1: escrever os testes que falham**

```python
# tests/test_historia.py
import subprocess
from lib.historia import historico, MIN_COMMITS, TETO_ARQUIVOS


def git(raiz, *args):
    subprocess.run(['git', *args], cwd=raiz, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def repo(tmp_path, commits):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'teste@exemplo.local')
    git(tmp_path, 'config', 'user.name', 'Teste')
    for i in range(commits):
        (tmp_path / 'a.py').write_text(f'x = {i}')
        (tmp_path / 'b.py').write_text(f'y = {i}')
        git(tmp_path, 'add', '-A')
        git(tmp_path, 'commit', '-q', '-m', f'c{i}')
    return tmp_path


def test_sem_repositorio_git_vira_lacuna_com_motivo(tmp_path):
    # Arrange
    (tmp_path / 'a.py').write_text('x = 1')
    # Act
    h = historico(tmp_path)
    # Assert
    assert h['co_mudanca'] == []
    assert h['lacuna'] is not None
    assert 'git' in h['lacuna'].lower()


def test_um_commit_so_vira_lacuna_dizendo_quantos(tmp_path):
    # Arrange
    raiz = repo(tmp_path, 1)
    # Act
    h = historico(raiz)
    # Assert — amostra pequena demais é ruído; o motivo diz o número real
    assert h['commits'] == 1
    assert h['co_mudanca'] == []
    assert h['lacuna'] is not None
    assert '1' in h['lacuna'] and str(MIN_COMMITS) in h['lacuna']


def test_git_acima_do_projeto_nao_e_usado(tmp_path):
    # Arrange — repositório na raiz, projeto auditado num subdiretório
    repo(tmp_path, MIN_COMMITS + 5)
    sub = tmp_path / 'modulo'
    sub.mkdir()
    (sub / 'c.py').write_text('z = 1')
    # Act
    h = historico(sub)
    # Assert — o histórico do pai não pode virar co-mudança do filho
    assert h['co_mudanca'] == []
    assert h['lacuna'] is not None
    assert 'acima' in h['lacuna']


def test_repositorio_sem_commit_diz_isso(tmp_path):
    # Arrange
    git(tmp_path, 'init', '-q')
    # Act
    h = historico(tmp_path)
    # Assert — "não há repositório git aqui" seria falso
    assert 'commit' in h['lacuna']


def test_com_amostra_suficiente_calcula_co_mudanca(tmp_path):
    # Arrange — a.py e b.py mudam SEMPRE juntos
    raiz = repo(tmp_path, MIN_COMMITS + 5)
    # Act
    h = historico(raiz)
    # Assert
    assert h['lacuna'] is None
    pares = {tuple(sorted(c['arquivos'])): c['vezes'] for c in h['co_mudanca']}
    assert pares[('a.py', 'b.py')] >= MIN_COMMITS


def test_commit_gigante_e_descartado(tmp_path):
    # Arrange
    raiz = repo(tmp_path, MIN_COMMITS + 1)
    for i in range(TETO_ARQUIVOS + 10):          # um "reformat geral"
        (raiz / f'lixo{i}.py').write_text('# formatado')
    git(raiz, 'add', '-A')
    git(raiz, 'commit', '-q', '-m', 'reformat geral')
    # Act
    h = historico(raiz)
    # Assert — o reformat não pode criar co-mudança entre arquivos sem relação
    pares = {tuple(sorted(c['arquivos'])) for c in h['co_mudanca']}
    assert ('lixo0.py', 'lixo1.py') not in pares
    assert h['commits_descartados'] == 1
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_historia.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.historia'`

- [x] **Step 3: escrever o `historia.py`**

```python
"""O que o histórico do git diz sobre acoplamento.

Arquivos que mudam juntos revelam acoplamento que import nenhum mostra. Mas
consultoria que recebe projeto de terceiro recebe zip ou `initial import`: SEM
HISTÓRICO É O CASO NORMAL, não a borda. Quando não há amostra, isso vira lacuna
com motivo — nunca seção omitida, porque omissão se lê como "nada muda junto".
"""
import subprocess
from collections import Counter
from itertools import combinations
from pathlib import Path

from lib.stacks import IGNORAR

MIN_COMMITS = 50      # abaixo disso, co-mudança é ruído
TETO_ARQUIVOS = 50    # commit maior que isso é reformat/lint em massa
MAX_PARES = 40        # quantos pares o inventário carrega


def _git(raiz, *args):
    r = subprocess.run(['git', *args], cwd=str(raiz), capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout


def _de_um_repo(raiz) -> dict:
    """Co-mudança de UM repositório, ou a lacuna com o motivo."""
    raiz = Path(raiz)
    vazio = {'commits': 0, 'co_mudanca': [], 'commits_descartados': 0, 'lacuna': None}

    # `git log` SOBE a árvore de diretórios: apontar para um subdiretório de um
    # monorepo devolvia commits e co-mudança de arquivos fora do escopo auditado.
    # Pior: as fixturas de teste vão para dentro deste repositório no `make sync`,
    # então sem esta checagem o teste "sem histórico" passa a ver o histórico daqui.
    topo = _git(raiz, 'rev-parse', '--show-toplevel')
    if topo is None:
        return {**vazio, 'lacuna': 'não há repositório git aqui — '
                                   'co-mudança não pode ser apurada'}
    if Path(topo.strip()).resolve() != raiz.resolve():
        return {**vazio, 'lacuna': f'o repositório git começa em {topo.strip()}, acima do '
                                   f'projeto auditado — a co-mudança seria de outro escopo'}

    # `--follow`/`-M` para o arquivo renomeado não virar dois
    saida = _git(raiz, 'log', '-M', '--name-only', '--pretty=format:%H%x09%aI')
    if not saida:
        return {**vazio, 'lacuna': 'o repositório não tem nenhum commit ainda'}

    commits, atual = [], None
    for linha in saida.split('\n'):
        if '\t' in linha and len(linha.split('\t')[0]) == 40:
            atual = {'data': linha.split('\t')[1], 'arquivos': []}
            commits.append(atual)
        elif linha.strip() and atual is not None:
            atual['arquivos'].append(linha.strip())

    if len(commits) < MIN_COMMITS:
        return {**vazio, 'commits': len(commits),
                'lacuna': f'só {len(commits)} commits no histórico; abaixo de {MIN_COMMITS} '
                          f'a co-mudança é ruído, não sinal'}

    uteis = [c for c in commits if 1 < len(c['arquivos']) <= TETO_ARQUIVOS]
    descartados = sum(1 for c in commits if len(c['arquivos']) > TETO_ARQUIVOS)

    pares = Counter()
    for c in uteis:
        for a, b in combinations(sorted(set(c['arquivos'])), 2):
            pares[(a, b)] += 1

    return {
        'commits': len(commits),
        'commits_descartados': descartados,
        'co_mudanca': [{'arquivos': list(par), 'vezes': n}
                       for par, n in sorted(pares.most_common(MAX_PARES),
                                            key=lambda x: (-x[1], x[0]))],
        'lacuna': None,
    }


def historico(raiz) -> dict:
    """Co-mudança do projeto, olhando um nível abaixo quando a raiz não tem git.

    **Monorepo por justaposição** é o formato normal de projeto recebido: `/projeto`
    sem `.git`, mas `/projeto/api`, `/projeto/admin` e `/projeto/website` com
    repositório próprio. Num projeto real isso eram 782 commits em quatro
    sub-repositórios, e o documento afirmava "não há repositório git aqui" — uma
    falsidade com o fato a um nível de profundidade.
    """
    raiz = Path(raiz)
    proprio = _de_um_repo(raiz)
    if proprio['lacuna'] is None:
        return proprio

    subs = []
    try:
        filhos = sorted(p for p in raiz.iterdir() if p.is_dir() and p.name not in IGNORAR)
    except OSError:
        return proprio
    for filho in filhos:
        if not (filho / '.git').exists():
            continue
        h = _de_um_repo(filho)
        if h['commits']:
            subs.append((filho.name, h))

    if not subs:
        return proprio

    # Os caminhos ganham o prefixo do sub-repositório, senão `<arquivo do projeto>` de dois
    # sub-repos diferentes viraria o mesmo arquivo no documento.
    co_mudanca = []
    for nome, h in subs:
        for c in h['co_mudanca']:
            co_mudanca.append({'arquivos': [f'{nome}/{a}' for a in c['arquivos']],
                               'vezes': c['vezes']})
    co_mudanca.sort(key=lambda c: (-c['vezes'], c['arquivos']))

    total = sum(h['commits'] for _, h in subs)
    sem_amostra = [nome for nome, h in subs if h['lacuna']]
    aviso = (f'; sem amostra suficiente em {", ".join(sem_amostra)}' if sem_amostra else '')
    return {
        'commits': total,
        'commits_descartados': sum(h['commits_descartados'] for _, h in subs),
        'co_mudanca': co_mudanca[:MAX_PARES],
        'subrepos': [{'caminho': nome, 'commits': h['commits']} for nome, h in subs],
        'lacuna': (f'a raiz não é repositório git; a co-mudança vem de '
                   f'{len(subs)} sub-repositórios ({", ".join(n for n, _ in subs)}){aviso}'),
    }
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_historia.py -v`
Esperado: 6 passed

- [x] **Step 5: prova por mutação nas duas guardas**

1. Troque `if len(commits) < MIN_COMMITS:` por `if False:` → `test_um_commit_so_vira_lacuna_dizendo_quantos` **FALHA**.
2. Troque `<= TETO_ARQUIVOS` por `<= 100000` → `test_commit_gigante_e_descartado` **FALHA**.

Desfaça as duas e confirme o verde. Se alguma mutação **não** derrubar teste, a guarda é
decorativa e o teste precisa ser reescrito antes de seguir.

---

### Task 6: `textual.py` — o grafo que enxerga o que o import não vê

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/textual.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_textual.py`

**Depende de:** Task 4 (usa `arvore.varrer`)

**Contrato que esta task publica:** `todas_as_mencoes(raiz: Path, simbolos: list) -> dict[str, list]` ·
`mencoes(raiz: Path, simbolo: str) -> list[dict]` com item `{'caminho': str, 'linha': int}` ·
`simbolos_de(arvore: list) -> list[str]`

**Por que existe:** é o segundo sinal do spec. O erro dele é falso positivo, que é o lado
seguro; o do grafo de import é falso negativo, que produz "nada depende disso".

- [x] **Step 1: escrever os testes que falham**

```python
# tests/test_textual.py
from lib.arvore import varrer
from lib.textual import mencoes, simbolos_de, todas_as_mencoes


def test_acha_a_classe_citada_como_string_na_rota(tmp_path):
    # Arrange — acoplamento que NENHUM grafo de import enxerga
    (tmp_path / 'app').mkdir()
    (tmp_path / 'app' / 'UserController.php').write_text('<?php class UserController {}')
    (tmp_path / 'routes.php').write_text('<?php Route::get("/u", "UserController@show");')
    # Act
    achadas = mencoes(tmp_path, 'UserController')
    # Assert
    caminhos = sorted(m['caminho'] for m in achadas)
    assert 'routes.php' in caminhos


def test_acha_mencao_em_yaml_e_sql(tmp_path):
    # Arrange
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'fila.yml').write_text('handler: App\\Pedido')
    (tmp_path / 'relatorio.sql').write_text('-- junta com Pedido')
    # Act
    caminhos = sorted(m['caminho'] for m in mencoes(tmp_path, 'Pedido'))
    # Assert
    assert caminhos == ['Pedido.php', 'fila.yml', 'relatorio.sql']


def test_informa_a_linha_da_mencao(tmp_path):
    # Arrange
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'uso.php').write_text('<?php\n\n$p = new Pedido();')
    # Act
    item = [m for m in mencoes(tmp_path, 'Pedido') if m['caminho'] == 'uso.php'][0]
    # Assert
    assert item['linha'] == 3


def test_nao_casa_pedaco_de_outra_palavra(tmp_path):
    # Arrange
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'outro.php').write_text('<?php $x = "PedidoCancelado";')
    # Act
    caminhos = [m['caminho'] for m in mencoes(tmp_path, 'Pedido')]
    # Assert — `PedidoCancelado` não é menção a `Pedido`
    assert 'outro.php' not in caminhos


def test_uma_passada_acha_varios_simbolos(tmp_path):
    # Arrange
    (tmp_path / 'Pedido.php').write_text('<?php class Pedido {}')
    (tmp_path / 'Cliente.php').write_text('<?php class Cliente {}')
    (tmp_path / 'uso.php').write_text('<?php new Pedido(); new Cliente();')
    # Act
    todas = todas_as_mencoes(tmp_path, ['Pedido', 'Cliente'])
    # Assert
    assert 'uso.php' in [m['caminho'] for m in todas['Pedido']]
    assert 'uso.php' in [m['caminho'] for m in todas['Cliente']]


def test_extrai_simbolos_dos_nomes_de_arquivo(tmp_path):
    # Arrange
    (tmp_path / 'app').mkdir()
    (tmp_path / 'app' / 'UserController.php').write_text('<?php')
    (tmp_path / 'app' / 'pedido_service.py').write_text('x = 1')
    # Act
    simbolos = simbolos_de(varrer(tmp_path))
    # Assert
    assert 'UserController' in simbolos
    assert 'pedido_service' in simbolos
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_textual.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.textual'`

- [x] **Step 3: escrever o `textual.py`**

```python
"""Grafo textual: o símbolo procurado como TEXTO em todo o repositório.

O grafo de import não vê injeção de dependência, reflexão, rota como string
(`"UserController@show"`), facade, template nem wiring por config — e em projeto
legado com framework pesado isso é a MAIOR PARTE do acoplamento.

O erro deste grafo é falso positivo, que aqui é o lado seguro: o do import é
falso negativo, e falso negativo vira "nada depende disso".
"""
import re
from pathlib import Path

from lib.arvore import varrer


def simbolos_de(arvore: list) -> list:
    """Os nomes de arquivo viram os símbolos a procurar."""
    simbolos = set()
    for item in arvore:
        if item['gerado']:
            continue
        base = Path(item['caminho']).name
        for sufixo in ('.blade.php', '.min.js'):
            if base.endswith(sufixo):
                base = base[: -len(sufixo)]
        simbolos.add(Path(base).stem)
    # Dotfile não é símbolo: `Path('.env').stem` devolve `.env`, não '' — então
    # `.env`, `.gitignore` e `.dockerignore` encabeçavam a lista alfabética e
    # gastavam as primeiras vagas do teto de símbolos procurando nome de arquivo de
    # configuração pelo repositório inteiro.
    return sorted(s for s in simbolos if len(s) >= 4 and not s.startswith('.'))


def todas_as_mencoes(raiz, simbolos: list) -> dict:
    """Uma passada pelos arquivos, casando TODOS os símbolos de uma vez.

    Uma varredura por símbolo levava 52 s num repositório de 490 arquivos; com os
    300 símbolos que o inventário pede, num projeto legado de 10 mil arquivos isso
    vira horas. O alvo desta skill é justamente o projeto grande, então a passada
    única não é otimização prematura: é o que torna a skill utilizável.
    """
    raiz = Path(raiz)
    if not simbolos:
        return {}
    # `\b` nas duas pontas: `PedidoCancelado` não é menção a `Pedido`
    padrao = re.compile(r'\b(' + '|'.join(re.escape(s) for s in simbolos) + r')\b')
    achadas = {s: [] for s in simbolos}
    for item in varrer(raiz):
        if item['acima_do_teto'] or item['gerado']:
            continue
        try:
            texto = (raiz / item['caminho']).read_text('utf-8', 'replace')
        except OSError:
            continue
        for n, linha in enumerate(texto.split('\n'), 1):
            for achado in set(padrao.findall(linha)):
                achadas[achado].append({'caminho': item['caminho'], 'linha': n})
    return {s: v for s, v in achadas.items() if v}


def mencoes(raiz, simbolo: str) -> list:
    """Onde um símbolo aparece. Conveniência sobre `todas_as_mencoes`."""
    return todas_as_mencoes(raiz, [simbolo]).get(simbolo, [])
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_textual.py -v`
Esperado: 7 passed

- [x] **Step 5: prova por mutação na fronteira de palavra**

Troque `r'\b' + re.escape(simbolo) + r'\b'` por `re.escape(simbolo)` e rode.
Esperado: `test_nao_casa_pedaco_de_outra_palavra` **FALHA**. Desfaça e confirme o verde.

---

### Task 7: `imports.py` — grafo de import, só com ferramenta nativa

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/imports.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_imports.py`

**Depende de:** Task 4

**Contrato que esta task publica:** `grafo(raiz: Path, stacks: list) -> dict` com
`{'arestas': list, 'indisponivel': list}`; cada aresta `{'de': str, 'para': str}`, cada
indisponível `{'stack': str, 'motivo': str}`

**Escopo do Plano 1:** só Python, pelo `ast` da stdlib — está sempre presente e resolve de
verdade. Outras stacks entram como `indisponivel` com o motivo. É o que o spec chama de
"grafo de import só quando a ferramenta nativa existe".

- [x] **Step 1: escrever os testes que falham**

```python
# tests/test_imports.py
from lib.imports import grafo


def test_resolve_import_de_modulo_local(tmp_path):
    # Arrange
    (tmp_path / 'pedido.py').write_text('class Pedido: pass')
    (tmp_path / 'servico.py').write_text('from pedido import Pedido\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert
    assert {'de': 'servico.py', 'para': 'pedido.py'} in g['arestas']


def test_ignora_import_de_biblioteca_externa(tmp_path):
    # Arrange
    (tmp_path / 'servico.py').write_text('import json\nimport requests\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert — só aresta para arquivo QUE EXISTE no projeto
    assert g['arestas'] == []


def test_arquivo_com_erro_de_sintaxe_nao_derruba_a_varredura(tmp_path):
    # Arrange
    (tmp_path / 'quebrado.py').write_text('def (:::')
    (tmp_path / 'pedido.py').write_text('class Pedido: pass')
    (tmp_path / 'servico.py').write_text('from pedido import Pedido\n')
    stacks = [{'stack': 'python', 'caminho': '.', 'manifesto': 'pyproject.toml'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert
    assert {'de': 'servico.py', 'para': 'pedido.py'} in g['arestas']


def test_stack_sem_ferramenta_nativa_diz_o_motivo(tmp_path):
    # Arrange
    (tmp_path / 'index.php').write_text('<?php')
    stacks = [{'stack': 'php', 'caminho': '.', 'manifesto': 'composer.json'}]
    # Act
    g = grafo(tmp_path, stacks)
    # Assert — não é silêncio: é indisponibilidade declarada
    assert g['arestas'] == []
    assert g['indisponivel'][0]['stack'] == 'php'
    assert g['indisponivel'][0]['motivo']
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_imports.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.imports'`

- [x] **Step 3: escrever o `imports.py`**

```python
"""Grafo de dependências por import — ferramenta nativa primeiro.

Regex sobre import erra para o lado perigoso: resolver a STRING do import em
ARQUIVO exige `paths` do tsconfig, PSR-4 do composer, workspaces e barrel. Sem
isso as arestas ficam penduradas e o grafo perde nó em silêncio.

Neste plano só Python tem caminho nativo (o `ast` da stdlib, sempre presente).
As outras stacks aparecem como INDISPONÍVEL com motivo — nunca como grafo vazio,
porque grafo vazio se lê como "nada depende de nada".
"""
import ast
from pathlib import Path

from lib.arvore import varrer


def _indice(arquivos) -> dict:
    """Indexa cada módulo por TODOS os sufixos do seu caminho pontilhado.

    A chave ancorada na raiz (`plugins/x/scripts/lib/config.py` →
    `plugins.x.scripts.lib.config`) nunca casa com o import que o código escreve
    (`from lib.config import ...`), porque é `scripts/` que entra no `sys.path`.
    Num projeto Python real isso dava ZERO arestas com 243 imports locais.

    Sufixo ambíguo — dois arquivos terminando igual — **não resolve**. Aresta
    errada é pior que aresta faltando: a falta é coberta pelo grafo textual, e a
    errada manda alguém mexer no arquivo errado.
    """
    por_sufixo = {}
    for caminho in arquivos:
        p = Path(caminho)
        partes = p.parent.parts if p.name == '__init__.py' else p.with_suffix('').parts
        for i in range(len(partes)):
            por_sufixo.setdefault('.'.join(partes[i:]), set()).add(caminho)
    return {chave: destinos.pop() for chave, destinos in por_sufixo.items()
            if len(destinos) == 1}


def _arestas_python(raiz, arquivos) -> list:
    modulos = _indice(arquivos)

    arestas = []
    for caminho in arquivos:
        try:
            arvore_ast = ast.parse((raiz / caminho).read_text('utf-8', 'replace'))
        except (SyntaxError, ValueError, OSError):
            continue          # arquivo quebrado não derruba a varredura inteira
        alvos = set()
        for no in ast.walk(arvore_ast):
            if isinstance(no, ast.Import):
                alvos.update(a.name for a in no.names)
            elif isinstance(no, ast.ImportFrom):
                base = no.module or ''
                if no.level:
                    # Import relativo (`from .x import Y`) é a forma NORMAL dentro de
                    # um pacote. Ignorá-lo faria o grafo de um projeto bem organizado
                    # sair MAIS vazio que o de um bagunçado — o inverso da verdade.
                    # Nível 1 é o pacote do próprio arquivo; cada nível a mais sobe um.
                    partes = Path(caminho).parent.parts
                    if no.level - 1 > len(partes):
                        continue      # sobe acima da raiz: não há como resolver
                    pacote = partes[:len(partes) - (no.level - 1)]
                    base = '.'.join([*pacote, base] if base else pacote)
                if not base:
                    continue
                alvos.add(base)
                alvos.update(f'{base}.{a.name}' for a in no.names)
        for alvo in alvos:
            destino = modulos.get(alvo)
            if destino and destino != caminho:
                arestas.append({'de': caminho, 'para': destino})
    return sorted(arestas, key=lambda a: (a['de'], a['para']))


def grafo(raiz, stacks: list) -> dict:
    """Arestas de import do que deu para resolver, e o motivo do que não deu."""
    raiz = Path(raiz)

    # Projeto sem manifesto nenhum acontece (centenas de arquivos PHP e nenhum
    # composer.json), e aí a detecção de stack devolve lista vazia. Sair daqui com
    # as duas listas vazias seria SILÊNCIO: quem lê conclui que nada depende de
    # nada, quando a verdade é que nada foi sequer tentado.
    if not stacks:
        return {'arestas': [], 'indisponivel': [{
            'stack': '(nenhuma)',
            'motivo': 'nenhuma stack foi detectada — nenhum manifesto encontrado no '
                      'projeto, então não há resolvedor nativo para aplicar; isto NÃO '
                      'significa que nada depende de nada',
        }]}

    arquivos = [i['caminho'] for i in varrer(raiz) if not i['gerado']]

    arestas, indisponivel = [], []
    for componente in {s['stack'] for s in stacks}:
        if componente == 'python':
            py = [c for c in arquivos if c.endswith('.py')]
            arestas.extend(_arestas_python(raiz, py))
        else:
            indisponivel.append({
                'stack': componente,
                'motivo': f'nesta versão só há resolução nativa para python; '
                          f'o acoplamento de {componente} aparece pelo grafo textual',
            })
    return {'arestas': arestas,
            'indisponivel': sorted(indisponivel, key=lambda i: i['stack'])}
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_imports.py -v`
Esperado: 4 passed

---

### Task 8: `superficie.py` — rotas, comandos, jobs e tabelas por convenção

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/superficie.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_superficie.py`

**Depende de:** Task 4

**Contrato que esta task publica:** `detectar(raiz: Path) -> list[dict]`, cada item
`{'tipo': str, 'caminho': str, 'por': str}` — `tipo` em `rota | comando | job | migration`

**Por que existe:** é a seção 4 do spec ("Superfície pública"), que o piso entrega **por
convenção de caminho**. Sem TOML de stack não dá para ler a rota em si, mas dá para dizer onde
elas moram — e isso já orienta quem chega. Sai marcado como **dedução**, nunca como fato: pasta
chamada `routes/` é indício, não prova.

- [x] **Step 1: escrever os testes que falham**

```python
# tests/test_superficie.py
from lib.superficie import detectar


def test_reconhece_pastas_de_rota_e_migration(tmp_path):
    # Arrange
    (tmp_path / 'routes').mkdir()
    (tmp_path / 'routes' / 'web.php').write_text('<?php')
    (tmp_path / 'database' / 'migrations').mkdir(parents=True)
    (tmp_path / 'database' / 'migrations' / '2024_01_01_cria_pedidos.php').write_text('<?php')
    # Act
    por_tipo = {}
    for item in detectar(tmp_path):
        por_tipo.setdefault(item['tipo'], []).append(item['caminho'])
    # Assert
    assert 'routes/web.php' in por_tipo['rota']
    assert 'database/migrations/2024_01_01_cria_pedidos.php' in por_tipo['migration']


def test_reconhece_comando_e_job(tmp_path):
    # Arrange
    (tmp_path / 'app' / 'Console' / 'Commands').mkdir(parents=True)
    (tmp_path / 'app' / 'Console' / 'Commands' / 'Limpar.php').write_text('<?php')
    (tmp_path / 'app' / 'Jobs').mkdir(parents=True)
    (tmp_path / 'app' / 'Jobs' / 'EnviarEmail.php').write_text('<?php')
    # Act
    por_tipo = {i['tipo'] for i in detectar(tmp_path)}
    # Assert
    assert por_tipo == {'comando', 'job'}


def test_diz_por_qual_criterio_reconheceu(tmp_path):
    # Arrange
    (tmp_path / 'routes').mkdir()
    (tmp_path / 'routes' / 'api.php').write_text('<?php')
    # Act
    item = detectar(tmp_path)[0]
    # Assert — a evidência viaja junto: é dedução, e o leitor precisa poder discordar
    assert item['por'] == 'routes/'


def test_projeto_sem_convencao_devolve_vazio(tmp_path):
    # Arrange
    (tmp_path / 'main.py').write_text('print(1)')
    # Act / Assert
    assert detectar(tmp_path) == []
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_superficie.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.superficie'`

- [x] **Step 3: escrever o `superficie.py`**

```python
"""Superfície pública por CONVENÇÃO DE CAMINHO.

Sem TOML de stack não dá para ler a rota em si — mas dá para dizer onde elas
moram, e isso já orienta quem chega no projeto. Por isso tudo aqui sai como
DEDUÇÃO, com o critério junto: pasta chamada `routes/` é indício, não prova, e
quem lê precisa poder discordar.
"""
from pathlib import Path

from lib.arvore import varrer

# Trecho de caminho → que tipo de superfície ele sugere. A ordem importa:
# `app/Console/Commands` casa comando antes de qualquer regra mais larga.
CONVENCOES = [
    ('console/commands', 'comando'),
    ('app/commands', 'comando'),
    ('management/commands', 'comando'),
    ('migrations', 'migration'),
    ('app/jobs', 'job'),
    ('jobs', 'job'),
    ('queues', 'job'),
    ('app/listeners', 'job'),
    ('workers', 'job'),
    ('routes', 'rota'),
    ('app/http/controllers', 'rota'),
    ('controllers', 'rota'),
    ('app/api', 'rota'),
    ('pages/api', 'rota'),
]


def detectar(raiz) -> list:
    """Onde a superfície pública parece morar, e por qual critério."""
    raiz = Path(raiz)
    achados = []
    for item in varrer(raiz):
        if item['gerado']:
            continue
        caminho = item['caminho'].replace('\\', '/').lower()
        pasta = caminho.rsplit('/', 1)[0] if '/' in caminho else ''
        # Casamento por SEGMENTO de caminho, com as barras como fronteira. A versão
        # anterior tinha três condições e nenhuma pegava `<arquivo do projeto>`
        # — trecho com barra só casava se o arquivo estivesse direto na pasta, e um
        # projeto Next.js inteiro saía sem superfície nenhuma.
        # A fronteira também é o que impede `src/routes-helper/` de casar `routes`.
        alvo = '/' + pasta + '/'
        for trecho, tipo in CONVENCOES:
            if '/' + trecho + '/' in alvo:
                achados.append({
                    'tipo': tipo,
                    'caminho': item['caminho'],
                    'por': trecho + '/',
                })
                break
    return sorted(achados, key=lambda a: (a['tipo'], a['caminho']))
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_superficie.py -v`
Esperado: 4 passed

---

### Task 9: `varrer.py` — o inventário

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/varrer.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_varrer.py`

**Depende de:** Tasks 2, 3, 4, 5, 6, 7, 8

**Contrato que esta task publica:** CLI
`python3 scripts/varrer.py --projeto <raiz> --out <dir>` → grava `<dir>/inventory.json`

**Restrições verificáveis:** *não escreve fora de `docs/project/`* (step 5) e *nenhum segredo*
(step 7).

- [x] **Step 1: escrever os testes que falham**

```python
# tests/test_varrer.py
import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent


def rodar(projeto, saida):
    return subprocess.run(
        [sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
         '--projeto', str(projeto), '--out', str(saida)],
        capture_output=True, text=True)


def projeto_simples(raiz):
    (raiz / 'app').mkdir(parents=True, exist_ok=True)
    (raiz / 'app' / 'pedido.py').write_text('class Pedido: pass')
    (raiz / 'rotas.py').write_text('ROTAS = {"/p": "pedido@listar"}')
    (raiz / 'pyproject.toml').write_text('[project]\nname = "loja"')
    return raiz


def test_grava_inventario_com_as_secoes_esperadas(tmp_path):
    # Arrange
    projeto, saida = projeto_simples(tmp_path / 'p'), tmp_path / 'out'
    # Act
    r = rodar(projeto, saida)
    # Assert
    assert r.returncode == 0, r.stderr
    inv = json.loads((saida / 'inventory.json').read_text())
    assert set(inv) >= {'stacks', 'arvore', 'historia', 'imports', 'mencoes',
                        'superficie', 'ambiente', 'gerado_em_versao'}
    assert inv['stacks'][0]['stack'] == 'python'


def test_varrer_so_escreve_em_docs_project(tmp_path):
    # Arrange
    projeto = projeto_simples(tmp_path / 'p')
    saida = tmp_path / 'out'
    antes = {p for p in projeto.rglob('*')}
    # Act
    rodar(projeto, saida)
    # Assert — o projeto auditado não ganha nem perde arquivo
    assert {p for p in projeto.rglob('*')} == antes
    assert sorted(p.name for p in saida.iterdir()) == ['inventory.json']


def test_chave_de_env_entra_e_valor_nao(tmp_path):
    # Arrange
    projeto = projeto_simples(tmp_path / 'p')
    (projeto / '.env').write_text('DB_PASSWORD=sup3rs3cr3t\nAPP_NAME=loja\n')
    saida = tmp_path / 'out'
    # Act
    rodar(projeto, saida)
    inv = json.loads((saida / 'inventory.json').read_text())
    # Assert — o par POSITIVO primeiro: a informação útil TEM que chegar.
    # Sem ele o teste passaria com o inventário vazio, que foi o defeito da versão
    # anterior — o valor não tinha por onde chegar, então nada era provado.
    assert inv['ambiente']['.env'] == ['APP_NAME', 'DB_PASSWORD']
    # e o valor não pode estar em NENHUM arquivo gravado
    for arquivo in saida.rglob('*'):
        if arquivo.is_file():
            assert 'sup3rs3cr3t' not in arquivo.read_text('utf-8', 'replace'), arquivo


def test_inventario_e_json_valido_com_simbolo_que_parece_segredo(tmp_path):
    # Arrange — `AuthController` casa com o padrão de nome de segredo
    projeto = projeto_simples(tmp_path / 'p')
    (projeto / 'app' / 'AuthController.py').write_text('class AuthController: pass')
    (projeto / 'app' / 'TokenService.py').write_text('class TokenService: pass')
    saida = tmp_path / 'out'
    # Act
    rodar(projeto, saida)
    # Assert — redigir o JSON pronto transformava `"AuthController": [` em
    # `"AuthController": ***` e quebrava o arquivo
    inv = json.loads((saida / 'inventory.json').read_text())
    caminhos = [a['caminho'] for a in inv['arvore']]
    assert 'app/AuthController.py' in caminhos


def test_inventario_nao_carrega_carimbo_de_tempo(tmp_path):
    # Arrange — carimbo de tempo quebraria a idempotência (Task 10)
    projeto = projeto_simples(tmp_path / 'p')
    # Act
    rodar(projeto, tmp_path / 'a')
    rodar(projeto, tmp_path / 'b')
    # Assert
    assert (tmp_path / 'a' / 'inventory.json').read_bytes() == \
           (tmp_path / 'b' / 'inventory.json').read_bytes()
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_varrer.py -v`
Esperado: FALHA — `varrer.py` não existe (`returncode != 0`)

- [x] **Step 3: escrever o `varrer.py`**

```python
#!/usr/bin/env python3
"""Apura os fatos de um projeto e grava `inventory.json`.

É DETERMINÍSTICO e regenerável: sem carimbo de tempo, ordem estável em tudo. É o
que permite ao documento dar diff, e é por isso que o agente NÃO escreve aqui —
ele escreve no `interpretation.toml`, que é outro arquivo com outro dono.

Lê o projeto; não altera nada dele. Só escreve no diretório de saída.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import arvore as mod_arvore          # noqa: E402
from lib import historia, imports, stacks, superficie, textual, redact  # noqa: E402

VERSAO = 1
MAX_SIMBOLOS = 300      # teto para não varrer o repo inteiro por símbolo


def apurar(projeto: Path) -> dict:
    componentes = stacks.detectar(projeto)
    arquivos = mod_arvore.varrer(projeto)

    simbolos = textual.simbolos_de(arquivos)[:MAX_SIMBOLOS]
    # uma passada só pelos arquivos, casando todos os símbolos
    por_simbolo = {s: m for s, m in textual.todas_as_mencoes(projeto, simbolos).items()
                   if len(m) > 1}             # 1 menção é a própria definição

    # Só as CHAVES do ambiente. Saber que o projeto usa `STRIPE_SECRET` orienta quem
    # chega; o valor nunca entra. Extrair a chave aqui — em vez de ler tudo e redigir
    # depois — é o que garante que não existe caminho pelo qual o valor chegue.
    ambiente = {}
    for item in arquivos:
        nome = Path(item['caminho']).name
        if nome == '.env' or nome.startswith('.env.'):
            try:
                texto = (projeto / item['caminho']).read_text('utf-8', 'replace')
            except OSError:
                continue
            ambiente[item['caminho']] = redact.chaves_de_env(texto)

    return {
        'gerado_em_versao': VERSAO,
        'stacks': componentes,
        'arvore': arquivos,
        'historia': historia.historico(projeto),
        'imports': imports.grafo(projeto, componentes),
        'superficie': superficie.detectar(projeto),
        'ambiente': dict(sorted(ambiente.items())),
        'mencoes': dict(sorted(por_simbolo.items())),
    }


def main() -> int:
    p = argparse.ArgumentParser(description='Apura os fatos de um projeto.')
    p.add_argument('--projeto', required=True, help='raiz do projeto a ler')
    p.add_argument('--out', required=True, help='diretório onde gravar o inventário')
    args = p.parse_args()

    projeto = Path(args.projeto).resolve()
    if not projeto.is_dir():
        print(f'não é um diretório: {projeto}', file=sys.stderr)
        return 2

    saida = Path(args.out).resolve()
    saida.mkdir(parents=True, exist_ok=True)

    inventario = apurar(projeto)
    # NÃO passe o JSON pronto por `redigir`: ele casa `chave: valor` linha a linha, e
    # linha de JSON é exatamente isso — `"AuthController": [` virava
    # `"AuthController": ***` e o arquivo saía inválido. A proteção acontece na
    # ORIGEM: o inventário só carrega caminho, contagem e nome de chave, nunca conteúdo.
    texto = json.dumps(inventario, indent=1, ensure_ascii=False, sort_keys=True)
    (saida / 'inventory.json').write_text(texto + '\n', encoding='utf-8')

    print(f'{saida / "inventory.json"}')
    print(f'{len(inventario["arvore"])} arquivos · {len(inventario["stacks"])} stack(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [x] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_varrer.py -v`
Esperado: 5 passed

- [x] **Step 5: conferir a restrição "não escreve fora de `docs/project/`"**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_varrer.py::test_varrer_so_escreve_em_docs_project -v`
Esperado: PASSA — o projeto auditado tem exatamente os mesmos arquivos antes e depois.

- [x] **Step 6: prova por mutação na extração de chave**

Em `redact.chaves_de_env`, troque `chave = linha.split('=', 1)[0]...` por
`chave = linha.strip()` (passa a devolver a linha inteira, com o valor) e rode.
Esperado: `test_chave_de_env_entra_e_valor_nao` **FALHA** — o valor aparece no inventário.
Desfaça e confirme o verde.

Esta é a mutação que a versão anterior do plano não tinha: o teste antigo passava mesmo com a
redação removida, porque nada no inventário carregava conteúdo de arquivo. Teste que não
consegue falhar não é guarda, é decoração.

- [x] **Step 7: conferir a restrição "nenhum segredo"**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_varrer.py -v`
Esperado: 5 passed — inclusive o JSON continuar válido com símbolos que parecem segredo.

---

### Task 10: `montar.py` — o documento, e a proibição de afirmar ausência

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/montar.py`
- Criar: `~/.claude/skills/sw-codebase-guide/tests/fixtures/acoplamento_invisivel/` (projeto com
  acoplamento só por injeção de dependência e rota como string)
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_montar.py`

**Depende de:** Task 9

**Contrato que esta task publica:** CLI
`python3 scripts/montar.py --dir <docs/project>` → grava `<dir>/guide.md`

**Restrições verificáveis:** *nunca afirmar ausência* (steps 3 e 5) e *mesmos fatos, mesmo
documento* (step 7).

- [x] **Step 1: criar a fixture de acoplamento invisível**

```python
# tests/fixtures/acoplamento_invisivel/app/UserController.py
class UserController:
    def show(self, id):
        return {'id': id}
```

```python
# tests/fixtures/acoplamento_invisivel/rotas.py
# Acoplamento por STRING: nenhum grafo de import enxerga esta aresta.
ROTAS = {'/u/<id>': 'UserController@show'}
```

```python
# tests/fixtures/acoplamento_invisivel/container.py
# Acoplamento por injeção: a classe é resolvida por nome, em tempo de execução.
LIGACOES = {'controller.user': 'UserController'}
```

```toml
# tests/fixtures/acoplamento_invisivel/pyproject.toml
[project]
name = "invisivel"
```

- [x] **Step 2: escrever os testes que falham**

```python
# tests/test_montar.py
import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / 'fixtures'

# Frases que a skill NUNCA pode emitir: o grafo não sabe o bastante para afirmar
# ausência, e "nada depende disso" é exatamente o dano que ela existe para evitar.
PROIBIDAS = ('nada depende', 'sem dependentes', 'não é usado', 'nao e usado',
             'nenhum dependente', 'não há dependentes')


def varrer(projeto, saida):
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True, text=True)


def montar(saida):
    return subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                           '--dir', str(saida)], capture_output=True, text=True)


def test_acoplamento_invisivel_aparece_como_mencao(tmp_path):
    # Arrange — o acoplamento existe SÓ por string e injeção
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — o par POSITIVO: o acoplamento TEM que aparecer
    assert 'UserController' in guia
    assert 'menç' in guia.lower()          # apareceu como menção textual
    assert 'rotas.py' in guia or 'container.py' in guia


def test_nenhuma_frase_de_ausencia(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text().lower()
    # Assert — o par NEGATIVO
    for frase in PROIBIDAS:
        assert frase not in guia, frase


def test_diz_o_que_o_grafo_de_import_nao_enxerga(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text().lower()
    # Assert — a ressalva viaja junto da afirmação, não numa nota de rodapé
    assert 'injeção de dependência' in guia or 'injecao de dependencia' in guia
    assert 'rota como string' in guia


def test_secao_de_co_mudanca_existe_com_motivo_sem_historico(tmp_path):
    # Arrange — a fixture não é repositório git
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — omissão se leria como "nada muda junto"
    assert 'muda junto' in guia.lower()
    assert 'git' in guia.lower()


def test_as_quatro_secoes_do_contrato_aparecem(tmp_path):
    # Arrange — uma afirmação em cada seção publicada pelo contrato
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '\n'.join(
            f'[[afirmacao]]\nsecao = "{secao}"\ntexto = "marca-{secao}"\n'
            f'nivel = "declarado"\nevidencia = ["rotas.py:1"]\nmotivo = ""\n'
            for secao in ('como-entrar', 'depende-de', 'o-que-faz', 'superficie')))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — seção publicada no contrato e não consumida faz o agente trabalhar à toa
    for secao in ('como-entrar', 'depende-de', 'o-que-faz', 'superficie'):
        assert f'marca-{secao}' in guia, secao


def test_secao_invalida_e_recusada_sem_traceback(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\ntexto = "sem secao"\nnivel = "fato"\n'
        'evidencia = ["rotas.py:1"]\nmotivo = ""\n')
    # Act
    r = montar(tmp_path)
    # Assert
    assert r.returncode == 2
    assert 'secao' in (r.stderr + r.stdout).lower()
    assert 'Traceback' not in r.stderr


def test_superficie_sai_marcada_como_deducao(tmp_path):
    # Arrange — a fixture tem rotas.py na raiz, sem pasta de convenção
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — sem convenção reconhecida, é lacuna com motivo; nunca silêncio
    assert 'Superfície pública' in guia
    assert 'lacuna' in guia.lower() or 'dedução' in guia


def test_duas_montagens_identicas(tmp_path):
    # Arrange — interpretation.toml CONGELADO: a parte não-determinística fica fora
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\n'
        'secao = "o-que-faz"\n'
        'texto = "Expõe um endpoint de usuário"\n'
        'nivel = "deducao"\n'
        'evidencia = ["rotas.py:3"]\n'
        'motivo = ""\n')
    # Act
    montar(tmp_path)
    primeira = (tmp_path / 'guide.md').read_bytes()
    montar(tmp_path)
    segunda = (tmp_path / 'guide.md').read_bytes()
    # Assert
    assert primeira == segunda


def test_afirmacao_sem_evidencia_e_recusada(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[afirmacao]]\n'
        'secao = "o-que-faz"\n'
        'texto = "O sistema gere uma loja de departamentos"\n'
        'nivel = "deducao"\n'
        'evidencia = []\n'
        'motivo = ""\n')
    (tmp_path / 'guide.md').write_text('documento anterior')   # sentinela
    # Act
    r = montar(tmp_path)
    # Assert — prosa plausível sem lastro não entra, e o documento bom não é destruído
    assert r.returncode == 2
    assert 'evidencia' in (r.stderr + r.stdout).lower()
    assert (tmp_path / 'guide.md').read_text() == 'documento anterior'
```

- [x] **Step 3: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_montar.py -v`
Esperado: FALHA — `montar.py` não existe

- [x] **Step 4: escrever o `montar.py`**

```python
#!/usr/bin/env python3
"""Junta inventário e interpretação no `guide.md`.

Duas propriedades inegociáveis:

1. NUNCA afirma ausência de dependentes. O grafo de import não vê injeção de
   dependência, reflexão, rota como string, facade, template nem config — em
   projeto legado isso é a maior parte do acoplamento. Então a saída é sempre
   "N por import, M menções textuais", com a lista do que o grafo não enxerga
   anexada à própria afirmação.
2. É função pura dos arquivos de entrada. Mesmos fatos, mesmo documento, byte a
   byte — sem carimbo de tempo, com ordem estável. É o que faz o diff servir.
"""
import argparse
import json
import sys
import tomllib
from pathlib import Path

NIVEIS = {'fato', 'declarado', 'deducao', 'lacuna'}
TETO_SIMBOLOS = 40
DOCUMENTACAO = ('.md', '.txt', '.rst', '.adoc')
SECOES = {'como-entrar', 'depende-de', 'o-que-faz', 'superficie'}

CEGUEIRAS = [
    'injeção de dependência / container',
    'rota como string ("Controller@acao")',
    'reflexão e chamada dinâmica',
    'include de template',
    'acoplamento por SQL ou config',
]


def _ler_interpretacao(caminho: Path) -> list:
    if not caminho.exists():
        return []
    dados = tomllib.loads(caminho.read_text('utf-8'))
    afirmacoes = dados.get('afirmacao', [])
    for a in afirmacoes:
        if a.get('secao') not in SECOES:
            raise ValueError(f'secao inválida ou ausente: {a.get("secao")!r}')
        if a.get('nivel') not in NIVEIS:
            raise ValueError(f'nivel inválido: {a.get("nivel")!r}')
        if a['nivel'] == 'lacuna' and not a.get('motivo'):
            raise ValueError(f'lacuna sem motivo: {a.get("texto")!r}')
        if a['nivel'] != 'lacuna' and not a.get('evidencia'):
            raise ValueError(
                f'afirmacao sem evidencia e sem ser lacuna: {a.get("texto")!r}')
    return afirmacoes


def _como_foi_detectada(componente: dict) -> str:
    """Stack sem manifesto é detectada por contagem de extensão.

    Imprimir `manifesto` cru colocaria a palavra `None` no documento — dizer COMO
    foi detectada é o que o leitor precisa para saber o quanto confiar.
    """
    manifesto = componente.get('manifesto')
    if manifesto:
        return f'`{manifesto}`'
    return f'sem manifesto; detectada por {componente.get("por", "contagem de arquivos")}'


def _dependentes(inv: dict) -> list:
    """Uma linha por arquivo: import + menção textual, nunca ausência."""
    entrada = {}
    for aresta in inv['imports']['arestas']:
        entrada.setdefault(aresta['para'], []).append(aresta['de'])

    # Sem NENHUMA aresta e com indisponibilidade declarada, repetir "0 por import" em
    # cada símbolo trabalha contra a própria ressalva: num projeto real o documento
    # dizia "0" 230 vezes, e quem lê conclui ausência apesar do aviso no topo.
    sem_grafo = not inv['imports']['arestas'] and inv['imports']['indisponivel']

    # Símbolo citado SÓ em documentação não é acoplamento de código: o nome de um
    # arquivo de spec aparecia como dependente, inflando a lista com ruído.
    so_em_doc = 0
    linhas = []
    for simbolo, achadas in inv['mencoes'].items():
        arquivos = sorted({m['caminho'] for m in achadas})
        if all(a.lower().endswith(DOCUMENTACAO) for a in arquivos):
            so_em_doc += 1
            continue
        por_import = sorted({d for alvo, ds in entrada.items()
                             if Path(alvo).stem == simbolo for d in ds})
        quantos = 'import não medido' if sem_grafo else f'{len(por_import)} por import'
        plural = 'menção textual' if len(arquivos) == 1 else 'menções textuais'
        linhas.append((len(arquivos), simbolo,
                       f'- **{simbolo}** — {quantos}, {len(arquivos)} {plural}: '
                       f'{", ".join(arquivos[:6])}'
                       + (' …' if len(arquivos) > 6 else '')))

    # Ordenado pelo MAIS citado e cortado: sem isto a seção era 85% do documento
    # (264 de 310 linhas), sem ranking, e ninguém lia.
    linhas.sort(key=lambda t: (-t[0], t[1]))
    saida = [texto for _, _, texto in linhas[:TETO_SIMBOLOS]]
    sobra = len(linhas) - len(saida)
    if sobra:
        saida.append(f'\n*Mais {sobra} símbolos com menos menções, no `inventory.json`.*')
    if so_em_doc:
        saida.append(f'*{so_em_doc} símbolos citados só em documentação ficaram de fora.*')
    return saida


def _escrever(L: list, afirmacoes: list, secao: str) -> None:
    """Despeja as afirmações daquela seção. Seção vazia diz que está vazia.

    Toda seção publicada no contrato precisa ter consumidor aqui: a primeira versão
    só lia `o-que-faz`, e o que o agente escrevia para `como-entrar` e `superficie`
    sumia sem erro — trabalho feito, conteúdo evaporado.
    """
    do_agente = [a for a in afirmacoes if a.get('secao') == secao]
    if not do_agente:
        L.append('*A interpretação não escreveu nada aqui.*  [lacuna: seção não interpretada]\n')
        return
    for a in sorted(do_agente, key=lambda x: x['texto']):
        L.append(f'- {a["texto"]}  [{a["nivel"]}]')
        for e in a.get('evidencia', []):
            L.append(f'    ↳ `{e}`')
    L.append('')


def montar(inv: dict, afirmacoes: list) -> str:
    L = []
    A = L.append
    A('# Guia do projeto\n')
    A('> Documento gerado por leitura do código. Cada afirmação carrega o nível de')
    A('> confiança: **fato** (medido) · **declarado** (humano escreveu antes) ·')
    A('> **dedução** (inferida, com evidência) · **lacuna** (não apurado, com motivo).\n')

    A('## Como entrar\n')
    for c in inv['stacks']:
        A(f'- **{c["stack"]}** em `{c["caminho"]}` — {_como_foi_detectada(c)}  [fato]')
    if not inv['stacks']:
        A('- nenhum manifesto reconhecido na raiz  [lacuna: o projeto não declara stack '
          'por manifesto conhecido]')
    A('')
    # "2.036 arquivos" se lê como 2.036 arquivos de CÓDIGO; num projeto real metade
    # eram PNG e SVG. A afirmação estava correta e comunicava errado.
    ATIVOS = {'png', 'svg', 'jpg', 'jpeg', 'gif', 'ico', 'webp', 'woff', 'woff2',
              'ttf', 'eot', 'mp4', 'pdf', 'zip', 'config'}
    ativos = sum(1 for a in inv['arvore'] if a['linguagem'] in ATIVOS)
    codigo = len(inv['arvore']) - ativos
    A(f'{codigo} arquivos de código e {ativos} de imagem, fonte ou configuração '
      f'(fora `vendor/`, `node_modules/`, cache e gerados).  [fato]\n')
    for arquivo, chaves in inv['ambiente'].items():
        A(f'`{arquivo}` declara {len(chaves)} variáveis — **só os nomes**, '
          f'nunca os valores:  [fato]')
        A('`' + '` · `'.join(chaves) + '`\n')
    _escrever(L, afirmacoes, 'como-entrar')

    A('## O que depende do quê\n')
    # A frase-guarda NÃO pode conter nenhuma das frases proibidas — a primeira
    # versão dizia «não existe "nada depende disso" aqui» e reprovava o próprio teste.
    A('Duas leituras cruzadas. **Ausência de dependentes nunca é afirmada neste**')
    A('**documento**: o grafo de import não enxerga o seguinte —\n')
    for cegueira in CEGUEIRAS:
        A(f'- {cegueira}')
    A('')
    indisponivel = inv['imports']['indisponivel']
    for item in indisponivel:
        A(f'> Grafo de import indisponível para **{item["stack"]}**: {item["motivo"]}  [lacuna]')
    if indisponivel:
        A('')
    L.extend(_dependentes(inv))
    A('')
    _escrever(L, afirmacoes, 'depende-de')

    A('### O que muda junto\n')
    h = inv['historia']
    # Decide pelo DADO, não pela lacuna. Depois que a busca por sub-repositórios
    # entrou, `lacuna` passou a significar duas coisas — "não há dado" e "há dado,
    # com ressalva" — e o documento escondia 40 pares de co-mudança que tinha.
    if not h['co_mudanca']:
        A(f'Não apurado: {h["lacuna"]}.  [lacuna]\n')
        A('Sem histórico, a concentração de risco é substituída por sinais estáticos —')
        A('número de menções, tamanho do arquivo e quantas stacks o tocam.\n')
    else:
        if h['lacuna']:
            A(f'> Ressalva: {h["lacuna"]}.  [lacuna parcial]\n')
        A(f'De {h["commits"]} commits '
          f'({h["commits_descartados"]} descartados por tocarem arquivos demais).  [fato]\n')
        for c in h['co_mudanca'][:20]:
            A(f'- `{c["arquivos"][0]}` + `{c["arquivos"][1]}` — {c["vezes"]}x')
        A('')

    A('## Superfície pública\n')
    sup = inv['superficie']
    if not sup:
        A('Nenhuma pasta de convenção conhecida (`routes/`, `migrations/`, `Jobs/`…).')
        A('  [lacuna: o projeto não segue convenção de caminho reconhecida]\n')
    else:
        A('Reconhecida por **convenção de caminho** — é indício, não prova.  [dedução]\n')
        for tipo in ('rota', 'comando', 'job', 'migration'):
            itens = [i for i in sup if i['tipo'] == tipo]
            if not itens:
                continue
            A(f'**{tipo}** ({len(itens)}), por `{itens[0]["por"]}`:')
            for i in itens[:10]:
                A(f'- `{i["caminho"]}`')
            if len(itens) > 10:
                A(f'- … e mais {len(itens) - 10}')
            A('')
    _escrever(L, afirmacoes, 'superficie')

    A('## O que o sistema faz\n')
    _escrever(L, afirmacoes, 'o-que-faz')

    A('## Perguntas em aberto\n')
    A('O que o código não respondeu — pauta para levar a quem conhece o sistema.\n')
    for a in sorted((x for x in afirmacoes if x['nivel'] == 'lacuna'),
                    key=lambda x: x['texto']):
        A(f'- {a["texto"]} — *{a["motivo"]}*')
    # Pergunta fixa só faz sentido enquanto ninguém respondeu. Repetir "qual é o
    # propósito?" logo abaixo de três afirmações `declarado` com fonte citada faz o
    # documento se contradizer na mesma página.
    respondido = {a['secao'] for a in afirmacoes if a['nivel'] in ('fato', 'declarado')}
    if not h['co_mudanca']:
        A('- Existe histórico de versionamento deste projeto em outro lugar?')
    if 'o-que-faz' not in respondido:
        A('- Qual é o propósito de negócio do sistema, e quem o usa?')
    if 'como-entrar' not in respondido:
        A('- Como se sobe este projeto do zero?')
    A('- Alguma destas pastas já não é usada e pode ser apagada?')
    A('')
    return '\n'.join(L)


def main() -> int:
    p = argparse.ArgumentParser(description='Monta o guide.md a partir do inventário.')
    p.add_argument('--dir', required=True, help='diretório com inventory.json')
    args = p.parse_args()

    base = Path(args.dir).resolve()
    inventario = base / 'inventory.json'
    if not inventario.exists():
        print(f'não achei {inventario} — rode varrer.py antes', file=sys.stderr)
        return 2

    try:
        afirmacoes = _ler_interpretacao(base / 'interpretation.toml')
    except ValueError as erro:
        print(f'interpretation.toml inválido: {erro}', file=sys.stderr)
        return 2

    texto = montar(json.loads(inventario.read_text('utf-8')), afirmacoes)
    (base / 'guide.md').write_text(texto, encoding='utf-8')
    print(f'{base / "guide.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [x] **Step 5: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_montar.py -v`
Esperado: 9 passed

- [x] **Step 6: prova por mutação na guarda da evidência**

Troque, em `_ler_interpretacao`, a condição
`if a['nivel'] != 'lacuna' and not a.get('evidencia'):` por `if False:` e rode.
Esperado: `test_afirmacao_sem_evidencia_e_recusada` **FALHA**. Desfaça e confirme o verde.

- [x] **Step 7: conferir a restrição de idempotência**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_montar.py::test_duas_montagens_identicas -v`
Esperado: PASSA — duas montagens sobre o mesmo `interpretation.toml` dão o arquivo byte a byte
igual.

- [x] **Step 8: rodar a suíte inteira**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest -q`
Esperado: todos verdes, sem erro de importação entre módulos.

---

### Task 11: `SKILL.md` — a skill propriamente dita

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/SKILL.md`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_skill_md.py`

**Depende de:** Tasks 9 e 10

- [x] **Step 1: escrever o teste que falha**

```python
# tests/test_skill_md.py
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / 'SKILL.md'


def test_frontmatter_tem_nome_igual_ao_diretorio():
    # Arrange
    texto = SKILL.read_text('utf-8')
    # Act
    linhas = texto.split('\n')
    # Assert
    assert linhas[0] == '---'
    assert 'name: sw-codebase-guide' in texto
    assert SKILL.parent.name == 'sw-codebase-guide'


def test_documenta_os_dois_comandos_com_o_caminho_certo():
    # Act
    texto = SKILL.read_text('utf-8')
    # Assert
    assert 'scripts/varrer.py' in texto
    assert 'scripts/montar.py' in texto
    assert 'docs/project/' in texto


def test_declara_o_que_nao_faz():
    # Act
    texto = SKILL.read_text('utf-8').lower()
    # Assert — os não-objetivos do spec precisam estar escritos para o agente
    assert 'não altera' in texto
    assert 'não avalia qualidade' in texto
```

- [x] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_skill_md.py -v`
Esperado: FALHA com `FileNotFoundError` em `SKILL.md`

- [x] **Step 3: escrever o `SKILL.md`**

````markdown
---
name: sw-codebase-guide
description: Lê um projeto que você acabou de receber e escreve a documentação dele em docs/project/ — como entrar, o que depende do quê e o que o sistema faz, com o nível de confiança de cada afirmação e a lista do que ficou sem resposta.
---

# Codebase Guide — ler um projeto e escrever a documentação dele

Você recebeu um projeto que ninguém da casa conhece. Esta skill varre o código e o histórico e
grava em `docs/project/` um guia que responde **como entrar**, **o que depende do quê** e **o
que o sistema faz** — e termina com as perguntas que ela não conseguiu responder.

**Anuncie no início:** "Estou usando a skill sw-codebase-guide para documentar este projeto."

## Garantias

- **Não altera nada do projeto.** Só lê, e só escreve em `docs/project/`.
- **Não avalia qualidade nem aponta bug.** Ela descreve; quem julga é a `sw-code-review`.
- **Nenhum segredo sai.** Valor de `.env`, chave privada e credencial em URL são redigidos
  antes de qualquer gravação.
- **Nunca afirma ausência de dependentes.** O grafo não enxerga injeção de dependência,
  rota como string, reflexão nem template — então "nada depende disso" não existe neste
  documento.
- **Não apurado ≠ não existe.** O que não deu para ler vira lacuna com motivo.

## Fluxo

### 1. Apurar os fatos

```bash
python3 <skill-dir>/scripts/varrer.py --projeto . --out docs/project
```

Grava `docs/project/inventory.json`: stacks detectadas, árvore, histórico do git, grafo de
import (quando há ferramenta nativa) e grafo textual. É determinístico — sem carimbo de tempo,
ordem estável — para o documento dar diff.

### 2. Escrever a interpretação

Leia o `inventory.json` e os **poucos** arquivos que ele aponta como centrais. Não leia o
projeto inteiro: o inventário existe justamente para isso.

Escreva `docs/project/interpretation.toml`. O formato é fechado — você preenche campos, não
escreve prosa:

```toml
[[afirmacao]]
secao = "o-que-faz"          # como-entrar | depende-de | o-que-faz | superficie
texto = "Pedido só fecha com pagamento confirmado"
nivel = "deducao"            # fato | declarado | deducao | lacuna
evidencia = ["app/Pedido.php:88"]
motivo = ""                  # obrigatório quando nivel = "lacuna"
```

**Afirmação sem evidência e sem ser lacuna é recusada** pelo `montar.py`. Isso é proposital: é
a guarda que impede prosa plausível de entrar sem lastro.

**Propósito e público só com fonte textual.** Se não houver README, ADR, mensagem de commit ou
texto de tela dizendo para que o sistema serve, **não afirme** — escreva como `lacuna`, e ela
vira pergunta em aberto. Deduzir propósito de rotas e modelos produz prosa plausível e vazia,
que quem recebe leva ao cliente como se fosse apurada.

**README é `declarado`, nunca `fato`.** Se o README discorda do `docker-compose`, mostre os
dois — a divergência é um dos achados mais úteis para quem acabou de receber o projeto.

### 3. Montar o documento

```bash
python3 <skill-dir>/scripts/montar.py --dir docs/project
```

Grava `docs/project/guide.md`.

### 4. Informar

Diga onde ficou o arquivo, quantos arquivos foram lidos, quais stacks apareceram, e **leia em
voz alta as perguntas em aberto** — elas são a pauta da conversa com quem conhece o sistema, e
são o entregável de maior valor quando o código não diz o propósito.

## Limites desta versão

- **Grafo de import só para Python** (pelo `ast` da stdlib). Outras stacks aparecem com o
  motivo declarado, e o acoplamento delas sai pelo grafo textual.
- **Sem conhecimento humano persistido.** O `knowledge.toml`, que preserva o que alguém
  confirmou entre execuções, é do próximo ciclo.
- **Sem recorte por área, sem HTML e sem PDF.**
- **Sem extração de regra de negócio** — só propósito com fonte textual.
````

- [x] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && python3 -m pytest tests/test_skill_md.py -v`
Esperado: 3 passed

- [x] **Step 5: rodar a skill contra um projeto real, de ponta a ponta**

```bash
cd ~/.claude/skills/sw-codebase-guide
python3 scripts/varrer.py --projeto <um-projeto-real> --out /tmp/saida
python3 scripts/montar.py --dir /tmp/saida
cat /tmp/saida/guide.md
```

Esperado: um `guide.md` legível, com as seções preenchidas e as perguntas em aberto no fim.
**Leia o documento inteiro.** Suíte verde prova que os testes rodam; só a leitura prova que o
documento serve para alguma coisa — foi lendo a saída que os defeitos caros apareceram nas
skills anteriores.

---

## Ajustes durante a execução

- **2026-10-06 · Task 1 (spike)** — rodou em dois projetos reais, não um. O resultado divergiu
  entre eles (20% no TypeScript, 50% no PHP) e mudou a decisão: `regras.py` sobrevive com
  `enum` e `estado` apenas, 9/10 = 90%. Registrado no spec e em `referencias/spike-regras.md`.

- **2026-10-06 · Task 2 (redact.py)** — o juiz reproduziu **oito vazamentos** e **três
  corrupções** que o plano original não previa. O módulo foi endurecido e os testes passaram
  de 6 para 18. O que mudou, e por quê:
  - **sem âncora de linha e varredura por ocorrência** — `      - DB_PASSWORD=senha` (item de
    lista YAML) e `{"api_key": "abc"}` passavam inteiros; docker-compose e k8s são os arquivos
    mais densos em segredo de um projeto;
  - **`export`, `ENV` e `ARG` no prefixo de declaração** — `.env`, `*.sh` e Dockerfile são
    input direto desta skill e vazavam;
  - **chave privada sem `-----END`** passa a ser mascarada até a linha em branco ou o fim —
    truncar arquivo é exatamente o que uma skill de documentação faz;
  - **usuário opcional na URL** — `redis://:senha@host` vazava;
  - **`FORMAS`**, um segundo gatilho pela forma do valor (`ghp_`, `sk-`, `AKIA`, `xox*`, JWT) —
    `X_SIGNATURE=...` e `GH_PAT=...` não casam com nome nenhum;
  - **esquema de autenticação** (`Bearer <token>`) ganhou regra própria, porque o valor tem
    espaço e o padrão de par parava nele;
  - **`INOCENTE`** — a guarda mascarava `auth: true`, `token: 0` e
    `const secret = useMemo(...)`, destruindo informação de graça;
  - **`auth(?!ors?\b)`** — a primeira correção foi `auth(?!or)`, que excluía `author` (certo)
    mas também `Authorization` (errado), e o cabeçalho de autenticação voltou a vazar;
  - **bug corrigido:** `.lstrip('export')` é strip de **conjunto de caracteres**, não de
    prefixo. Devolvia `['ken']` para `token=abc` e descartava `port=5432` inteiro.

  Limites que ficam declarados no módulo: não cobre segredo construído em tempo de execução,
  valor dentro de chamada de função, nem formato binário. É guarda de superfície.

- **2026-10-06 · Tasks 3 a 8** — três defeitos que **só apareceram rodando contra projeto real**,
  nenhum deles detectável por fixture. Os módulos no plano foram atualizados para a versão
  corrigida:
  - **`stacks.py` — a stack do projeto não era detectada.** O próprio marketplace tem 210
    arquivos Python e nenhum `pyproject.toml`: a regra só-manifesto devolvia duas stacks `node`
    que eram fixture de eval de outra skill. E como o `grafo` decide o que parsear pela lista de
    stacks, os 210 arquivos não eram nem parseados nem declarados como lacuna — silêncio, o
    exato proibido. Entrou a detecção por contagem de extensão (`manifesto: None`, campo `por`).
  - **`stacks.py` — diretório de build virava componente.** `.next/package.json` existe em
    qualquer projeto Next.js; dois dos três componentes de um projeto real eram lixo gerado, e 1.163
    arquivos gerados entravam na árvore. `IGNORAR` ganhou `.next`, `.nuxt`, `.svelte-kit`,
    `target`, `out`, `coverage`, `.turbo`, `.terraform`, `bower_components`.
  - **A guarda do `IGNORAR` não tinha teste em `stacks`.** A mutação sobrevivia: trocando o
    filtro, os cinco testes continuavam verdes e a detecção devolvia **357 componentes** em vez
    de 3. Os dois testes de `build`/`dist` testavam o inverso (que o filtro NÃO dispara).
  - **Desempenho:** `rglob('*')` materializava **181.975 caminhos para 2.036 úteis** (5 s,
    231 MB de pico) porque descia em `node_modules` antes de filtrar. Virou `stacks.caminhar`,
    um `os.walk` com poda em `dirs[:]`, usado também pela `arvore`: 0,1 s no mesmo projeto.
  - **`superficie.py` — projeto Next.js saía sem superfície nenhuma.** Trecho com barra
    (`app/api`) só casava com o arquivo direto na pasta, e o App Router real põe a rota em
    `app/api/<segmento>/route.ts`. Virou casamento por segmento com as barras como fronteira —
    uma expressão no lugar de três, e é a fronteira que impede `routes-helper` de casar
    `routes`.
  - **`imports.py` — zero arestas num projeto com 243 imports locais.** O módulo era indexado
    pelo caminho a partir da raiz (`plugins.x.scripts.lib.config`), mas o import que o código
    escreve é `from lib.config`, porque quem entra no `sys.path` é o `scripts/`. Passou a
    indexar por todos os sufixos do caminho pontilhado, resolvendo só quando não há
    ambiguidade: **0 → 328 arestas**. Sufixo ambíguo não vira aresta, de propósito — aresta
    errada manda mexer no arquivo errado, e a falta o grafo textual cobre.

- **2026-10-06 · Task 11 e fechamento** — o ciclo completo rodou em **seis projetos reais**
  (projeto A, projeto E, projeto B, este repositório, projeto C, projeto F), nenhum
  falhou, e dois deles — um terço — são **monorepo por justaposição**, o que confirma que a
  correção dos sub-repositórios não era caso isolado.
  Escrever um `interpretation.toml` de verdade (o que nenhum teste fazia) achou mais três:
  - **A seção "O que depende do quê" era 85% do documento** — 264 de 310 linhas, 230 símbolos
    sem ranking nem corte. Passou a ser ordenada pelo mais citado, com teto de 40 e o resto
    apontado para o `inventory.json`. O documento caiu de 336 para 151 linhas, e a lista virou
    a arquitetura do sistema em ordem de centralidade.
  - **As perguntas fixas contradiziam o próprio documento:** "Qual é o propósito de negócio?"
    aparecia logo abaixo de três afirmações `declarado` com fonte citada. Pergunta fixa agora
    some quando a seção correspondente já tem afirmação de nível `fato` ou `declarado`.
  - **Símbolo citado só em documentação** (nome de arquivo de spec) entrava como dependente e
    inflava a lista; agora fica de fora, com a contagem declarada.

## Limites conhecidos ao fechar o Plano 1

Levantados lendo os documentos; não são defeitos abertos, são o escopo do Plano 2:

1. **A superfície por convenção erra o que é específico de stack.** Num projeto PHP real ela
   marcou 29 "rotas" que eram controllers, e não achou a tabela de rotas de verdade
   (`Rota::` em `app/*/Rotas.php`) nem as 64 migrations do Flyway em `database/sql`. É
   exatamente o que o TOML de stack existe para resolver.
2. **"Como entrar" não diz onde a execução começa** — lista stacks e contagem, mas não aponta
   `index.php`, `main.js` nem o entrypoint do compose, que é a primeira coisa que se procura.
3. **O extrator de símbolos ainda tem ruído** (token de asset como `500px`, nome de teste).
4. **Grafo de import só para Python.** Nos outros o documento diz "import não medido", o que é
   honesto, mas deixa a seção sem o sinal mais forte.
