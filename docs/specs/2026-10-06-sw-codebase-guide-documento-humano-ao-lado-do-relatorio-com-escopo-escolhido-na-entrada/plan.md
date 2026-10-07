# Plano de implementação — documento humano e escopo na entrada (v0.2.0)

[spec.md](spec.md)

> **Execução:** implementar task por task. Os steps usam checkbox (`- [ ]`) para acompanhar.
> Os dois modos de execução estão na seção "Execution Handoff" da skill `sw-plan`.

**Objetivo:** a skill pergunta o escopo antes de varrer e entrega dois documentos — o
`leia-me.md`, que explica o produto e onde ficam as coisas, e o `guide.md` técnico de hoje.

**Arquitetura:** `varrer.py` ganha dois modos — `--areas` imprime as áreas em stdout sem gravar
nada, e a varredura completa aceita `--area` para recortar. O `interpretation.toml` ganha o
bloco `[[narrativa]]` ao lado das `[[afirmacao]]`, e `montar.py` emite dois arquivos da mesma
fonte.

**Stack:** Python 3 só stdlib, pytest pela `.venv` da skill. Rode sempre
`cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q` — não há pytest no sistema.

**Marcos (do spec), com ponto de parada utilizável no meio:**

| Marco | Tasks | Fecha quando |
|---|---|---|
| **1 — o escopo** | 2 a 6 | os 92 testes seguem verdes e o `guide.md` de uma área sai correto |
| **2 — o documento humano** | 7 a 12 | o spike passou e o `leia-me.md` de um projeto real serve |

**Restrições verificáveis (do spec):**

| Restrição | Como o plano checa |
|---|---|
| Trecho literal é conferido | Task 9, step 2 — `test_trecho_que_nao_existe_e_recusado` |
| Trecho com quebra de linha casa | Task 9, step 2 — `test_trecho_quebrado_em_duas_linhas_casa` |
| Caminho inventado recusado nos dois blocos | Task 7, step 2 — `test_caminho_inventado_recusado_nos_dois_blocos` |
| Evidência com `:linha` e `commit` é aceita | Task 7, step 2 — `test_quatro_formas_de_evidencia` |
| Diretório casa por prefixo | Task 7, step 2 — `test_diretorio_casa_por_prefixo` |
| Frase proibida na narrativa é recusada | Task 8, step 2 — `test_frase_proibida_recusada_pelo_parser` |
| Recorte preserva a ponta de fora | Task 5, step 5 — `test_co_mudanca_cruzando_a_fronteira_sobrevive` |
| Stack e ambiente acima da área sobrevivem | Task 5, step 5 — `test_stack_e_env_da_raiz_sao_herdados` |
| Token em README não chega ao inventário | Task 2, step 5 — `test_token_em_readme_nao_vaza` |
| A fase de áreas só abre o que `textos` declara | Task 4, step 4 — `test_fase_de_areas_nao_abre_codigo` |
| Mesmos fatos, mesmo documento | Task 10, step 5 — `test_dois_documentos_identicos_em_duas_montagens` |
| A fase de áreas não grava arquivo | Task 4, step 4 — `test_fase_de_areas_nao_grava_nada` |
| Sem Chromium, entrega o HTML e avisa | Task 13, step 5 — `test_sem_chromium_entrega_o_html_e_avisa` |
| O PDF não depende de rede | Task 13, step 5 — `test_html_e_self_contained` |

**Estrutura de arquivos:**

```
~/.claude/skills/sw-codebase-guide/
  scripts/
    varrer.py          Tasks 4, 5    --areas (stdout) e --area (recorte)
    montar.py          Tasks 6-11    dois emissores, três guardas
    lib/
      textos.py        Task 2   NOVO  fontes textuais, redigidas e com teto
      areas.py         Task 3   NOVO  agrupamento de diretórios
      historia.py      Tasks 3, 5     consulta por pasta; recorte por uma-ponta-dentro
      stacks.py        Task 5         herança do que mora acima da área
  tests/               uma suíte por módulo, como já é
  SKILL.md             Task 12
```

---

### Task 1 (SPIKE): a prosa de produto se sustenta?

**Arquivos:**
- Criar: `docs/specs/2026-10-06-sw-codebase-guide-documento-humano-ao-lado-do-relatorio-com-escopo-escolhido-na-entrada/referencias/spike-prosa.md`

**Depende de:** nada

**Por que é a task 1:** é a suposição de maior risco do spec. Se a prosa não se sustentar, a
parte 1 do documento humano — o coração do pedido do dono — vira ruído educado, e as tasks 9 a
11 mudam de forma.

**Deu certo se:** o dono lê as duas e diz que **as duas** são melhores que não ter nada.
**Se não:** o documento humano encolhe para mapa + orientações, a parte 1 vira só a citação
literal sem paráfrase, e as tasks 9 e 10 encolhem junto.

- [ ] **Step 1: escolher dois projetos de formas diferentes**

Um **com** fonte textual rica (README ou `CLAUDE.md` que explique o sistema) e um **sem** —
só código. O contraste é o ponto: o spike mede se a prosa se sustenta nos dois casos, não só
no fácil.

Registre no arquivo de referência qual é qual, e por quê.

- [ ] **Step 2: gerar o inventário dos dois**

```bash
cd ~/.claude/skills/sw-codebase-guide
.venv/bin/python scripts/varrer.py --projeto <projeto-com-texto> --out /tmp/spike-a
.venv/bin/python scripts/varrer.py --projeto <projeto-sem-texto> --out /tmp/spike-b
```

- [ ] **Step 3: escrever a parte 1 de cada um, à mão**

Leia o `inventory.json` e **no máximo 5 arquivos** de cada projeto. Escreva 2-3 parágrafos:
o que o sistema é, quem usa, quais são as partes. No projeto com fonte textual, cite o trecho
literal; no sem, escreva o que der e marque o que não deu.

Essa escrita é o produto do spike. Não automatize: automatizar seria medir a prosa com quem a
escreve.

- [ ] **Step 4: escrever o resultado em `referencias/spike-prosa.md`**

```markdown
# Spike — a prosa de produto se sustenta?

**Projeto A** (com fonte textual): <descrição genérica, sem nome de cliente>
**Projeto B** (só código): <descrição genérica>
**Data:** <data>

## Parte 1 do projeto A

<os 2-3 parágrafos>

**Fonte citada:** <arquivo e trecho>
**Arquivos lidos além do inventário:** <quantos, quais>

## Parte 1 do projeto B

<os 2-3 parágrafos, ou o que deu>

**Arquivos lidos além do inventário:** <quantos, quais>
**O que não deu para afirmar, e por quê:** <lista>

## Veredito

- O dono achou a do projeto A melhor que nada? <sim/não>
- E a do projeto B? <sim/não>
- **Decisão:** <parte 1 fica como desenhada | parte 1 vira só citação | documento humano
  encolhe para mapa + orientações>
```

- [ ] **Step 5: mostrar ao dono e registrar a decisão**

Apresente as duas e pergunte, sem defender nenhuma. A resposta vai para o "Veredito" e decide
o escopo das tasks 9 a 11.

---

### Task 2: `textos.py` — as fontes textuais, redigidas e com teto

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/textos.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_textos.py`

**Depende de:** nada

**Contrato que esta task publica:** `coletar(raiz: Path, arvore: list) -> dict` →
`{caminho: {'conteudo': str, 'cortado': bool}}` · `eh_fonte_textual(caminho: str) -> bool`

**Por que vem primeiro no marco 1:** é a única seção nova que carrega **conteúdo** para dentro
do inventário, que é commitado. O invariante de segredo do `varrer.py` diz por escrito que o
inventário "só carrega caminho, contagem e nome de chave, nunca conteúdo" — esta task é a
exceção, e ela precisa nascer com a redação junto, não ganhá-la depois.

- [ ] **Step 1: escrever os testes que falham**

```python
# tests/test_textos.py
from lib.textos import coletar, eh_fonte_textual, TETO_BYTES
from lib.arvore import varrer


def test_reconhece_as_fontes_textuais():
    # Act / Assert
    assert eh_fonte_textual('README.md')
    assert eh_fonte_textual('CLAUDE.md')
    assert eh_fonte_textual('docs/setup.md')
    assert eh_fonte_textual('docs/adr/0001-escolha-do-banco.md')   # recursivo
    assert eh_fonte_textual('locales/pt-BR.json')
    assert not eh_fonte_textual('src/app.py')
    assert not eh_fonte_textual('package.json')


def test_coleta_o_conteudo_das_fontes(tmp_path):
    # Arrange
    (tmp_path / 'README.md').write_text('# Loja\n\nSistema de pedidos para padarias.')
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'app.py').write_text('x = 1')
    # Act
    achados = coletar(tmp_path, varrer(tmp_path))
    # Assert
    assert list(achados) == ['README.md']
    assert 'padarias' in achados['README.md']['conteudo']


def test_token_em_readme_nao_vaza(tmp_path):
    # Arrange — README de projeto recebido tem token de exemplo com frequência,
    # e o inventory.json é commitado. As linhas `# noscan` carregam um valor com
    # FORMA de token de propósito: a guarda só se prova com fixture que parece real.
    (tmp_path / 'README.md').write_text(
        'Configure o acesso:\n\nGITHUB_TOKEN=ghp_16C7e42F292c6912E7710c838347Ae178B4a\n')  # noscan: fixture
    # Act
    achados = coletar(tmp_path, varrer(tmp_path))
    # Assert
    conteudo = achados['README.md']['conteudo']
    assert 'ghp_16C7e42F292c6912E7710c838347Ae178B4a' not in conteudo  # noscan: fixture
    assert 'GITHUB_TOKEN' in conteudo          # a chave fica; o valor não


def test_arquivo_grande_e_cortado_e_marcado(tmp_path):
    # Arrange
    (tmp_path / 'README.md').write_text('a' * (TETO_BYTES + 500))
    # Act
    item = coletar(tmp_path, varrer(tmp_path))['README.md']
    # Assert
    assert len(item['conteudo']) <= TETO_BYTES
    assert item['cortado'] is True


def test_ordem_estavel(tmp_path):
    # Arrange
    for nome in ('README.md', 'CLAUDE.md', 'AGENTS.md'):
        (tmp_path / nome).write_text('texto')
    # Act
    primeira = list(coletar(tmp_path, varrer(tmp_path)))
    segunda = list(coletar(tmp_path, varrer(tmp_path)))
    # Assert — ordem instável quebraria a idempotência do documento
    assert primeira == segunda == sorted(primeira)
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_textos.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.textos'`

- [ ] **Step 3: escrever o `textos.py`**

```python
"""As fontes textuais do projeto: README, CLAUDE.md, docs, ADR, tradução.

É a única seção do inventário que carrega CONTEÚDO. O resto só leva caminho,
contagem e nome de chave — e o `varrer.py` diz isso por escrito, porque o
`inventory.json` é commitado.

Por isso o conteúdo passa por `redact.redigir` **campo a campo, antes de
serializar**. Nunca sobre o JSON pronto: isso já quebrou o arquivo uma vez,
transformando `"AuthController": [` em `"AuthController": ***`.

Existe para a parte "o que o produto faz" do documento humano. Sem esta seção o
agente só acha o README se lembrar de procurar — e foi um `CLAUDE.md` que
respondeu, num teste real, o que entrevista nenhuma responderia.
"""
import re
from pathlib import Path

from lib import redact

TETO_BYTES = 64 * 1024      # o conteúdo vai inteiro para o JSON; 1 MB não cabe

# Nome ou caminho que denuncia fonte textual. `docs/` é recursivo de propósito:
# `docs/adr/0001-escolha-do-banco.md` é o caso real.
PADROES = [
    re.compile(r'(?i)^readme[^/]*\.(md|txt|rst)$'),
    re.compile(r'(?i)^(claude|agents|contributing|changelog|arquitetura|architecture)\.md$'),
    re.compile(r'(?i)^docs?/.*\.(md|txt|rst|adoc)$'),
    re.compile(r'(?i)^adrs?/.*\.md$'),
    re.compile(r'(?i).*\.adr\.md$'),
    re.compile(r'(?i)^(locales?|lang|i18n|translations?)/.*\.(json|ya?ml|po|ts|js)$'),
]


def eh_fonte_textual(caminho: str) -> bool:
    """Este caminho é fonte textual sobre o sistema?"""
    normal = caminho.replace('\\', '/')
    return any(p.match(normal) for p in PADROES)


def coletar(raiz, arvore: list) -> dict:
    """O conteúdo das fontes textuais, redigido e com teto, em ordem estável."""
    raiz = Path(raiz)
    achados = {}
    for item in sorted(arvore, key=lambda i: i['caminho']):
        if not eh_fonte_textual(item['caminho']):
            continue
        try:
            bruto = (raiz / item['caminho']).read_text('utf-8', 'replace')
        except OSError:
            continue
        cortado = len(bruto) > TETO_BYTES
        achados[item['caminho']] = {
            'conteudo': _redigir_por_linha(bruto[:TETO_BYTES]),
            'cortado': cortado,
        }
    return achados


def _redigir_por_linha(texto: str) -> str:
    """Redige LINHA A LINHA, não o texto inteiro. Dois motivos medidos:

    1. O padrão de par do `redact` tem `\\s*` entre a chave e o separador, e ele
       atravessa quebra de linha. Sobre o texto inteiro,
       `'Configure o acesso:\\n\\nGITHUB_TOKEN=ghp_…'` casa `chave=acesso` e
       `valor=GITHUB_TOKEN=ghp_…` — e a CHAVE some junto com o valor.
    2. Backtracking catastrófico: 65 KB de texto sem separador levaram 77 s.
       Linha a linha, prosa real sai em centésimos.
    """
    return '\n'.join(redact.redigir(linha) for linha in texto.split('\n'))
```

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_textos.py -v`
Esperado: 5 passed

- [ ] **Step 5: prova por mutação na redação**

Troque `redact.redigir(bruto[:TETO_BYTES])` por `bruto[:TETO_BYTES]` e rode.
Esperado: `test_token_em_readme_nao_vaza` **FALHA**. Desfaça e confirme o verde.

Se a mutação **não** derrubar o teste, pare e reporte — a redação estaria sendo aplicada em
outro lugar, ou o teste não estaria provando nada.

---

### Task 3: `areas.py` — as áreas do projeto, por agrupamento de diretórios

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/lib/areas.py`
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/lib/historia.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_areas.py`

**Depende de:** nada

**Contrato que esta task publica:**
`detectar(arvore: list, recentes: dict | None) -> list` → itens
`{'caminho': str, 'arquivos': int, 'commits_recentes': int}` ·
`historia.commits_por_pasta(raiz: Path, dias: int = 90) -> dict`

**Por que não usa a detecção por convenção:** a `superficie.py` marcou 29 "rotas" que eram
controllers num projeto PHP e não achou as 20 áreas do App Router num Next.js. Ela continua
existindo para a seção "Superfície pública", onde sai marcada como dedução — mas **não pode
decidir o escopo**, que é a primeira tela da skill. As áreas saem da `arvore`, que vem do
`os.walk` com poda e é a parte mais confiável do inventário.

- [ ] **Step 1: escrever os testes que falham**

```python
# tests/test_areas.py
import subprocess
from lib.areas import detectar, DOMINANTE, PISO_ARQUIVOS
from lib.historia import commits_por_pasta


def arvore_de(caminhos):
    return [{'caminho': c, 'bytes': 10, 'linguagem': 'python',
             'gerado': False, 'acima_do_teto': False} for c in caminhos]


def test_desce_enquanto_um_filho_domina():
    # Arrange — tudo mora sob `src/app/(app)/`; parar em `src` não daria área nenhuma útil
    arvore = arvore_de([
        'src/app/(app)/funil/page.tsx', 'src/app/(app)/funil/card.tsx',
        'src/app/(app)/funil/util.ts',
        'src/app/(app)/tarefas/page.tsx', 'src/app/(app)/tarefas/lista.tsx',
        'src/app/(app)/tarefas/x.ts',
        'src/app/(app)/agenda/page.tsx', 'src/app/(app)/agenda/dia.tsx',
        'src/app/(app)/agenda/y.ts',
    ])
    # Act
    caminhos = sorted(a['caminho'] for a in detectar(arvore, None))
    # Assert
    assert caminhos == ['src/app/(app)/agenda', 'src/app/(app)/funil',
                        'src/app/(app)/tarefas']


def test_monorepo_por_justaposicao_para_no_nivel_1():
    # Arrange — o outro caso-âncora: três sistemas lado a lado
    arvore = arvore_de([
        'api/src/a.php', 'api/src/b.php', 'api/src/c.php',
        'web/src/a.ts', 'web/src/b.ts', 'web/src/c.ts',
        'admin/src/a.vue', 'admin/src/b.vue', 'admin/src/c.vue',
    ])
    # Act
    caminhos = sorted(a['caminho'] for a in detectar(arvore, None))
    # Assert
    assert caminhos == ['admin', 'api', 'web']


def test_pasta_abaixo_do_piso_nao_vira_area():
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py', 'b/1.py'])
    # Act
    caminhos = [a['caminho'] for a in detectar(arvore, None)]
    # Assert — `b` tem 1 arquivo, abaixo do piso de 3
    assert caminhos == ['a']


def test_conta_os_arquivos_de_cada_area():
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py', 'a/sub/4.py',
                        'b/1.py', 'b/2.py', 'b/3.py'])
    # Act
    por_caminho = {a['caminho']: a['arquivos'] for a in detectar(arvore, None)}
    # Assert — conta recursivo: `a/sub/4.py` é de `a`
    assert por_caminho == {'a': 4, 'b': 3}


def test_ordena_por_commits_recentes_quando_houver():
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py', 'b/1.py', 'b/2.py', 'b/3.py'])
    # Act
    ordem = [x['caminho'] for x in detectar(arvore, {'b': 12, 'a': 3})]
    # Assert
    assert ordem == ['b', 'a']


def test_cai_para_numero_de_arquivos_sem_git():
    # Arrange
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py',
                        'b/1.py', 'b/2.py', 'b/3.py', 'b/4.py'])
    # Act
    ordem = [x['caminho'] for x in detectar(arvore, None)]
    # Assert — um terço dos projetos testados não tem git na raiz
    assert ordem == ['b', 'a']


def test_commits_por_pasta_conta_commit_e_nao_toque(tmp_path):
    # Arrange — DOIS arquivos por commit: com contagem por toque daria 4, não 2
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git('init', '-q')
    git('config', 'user.email', 'teste@exemplo.local')
    git('config', 'user.name', 'Teste')
    (tmp_path / 'api').mkdir()
    for i in range(2):
        (tmp_path / 'api' / 'a.php').write_text(f'<?php {i}')
        (tmp_path / 'api' / 'b.php').write_text(f'<?php {i}')
        git('add', '-A')
        git('commit', '-q', '-m', f'c{i}')
    # Act / Assert — o rótulo do menu diz "14 commits no último mês"
    assert commits_por_pasta(tmp_path, dias=90).get('api') == 2


def test_commits_por_pasta_ignora_repo_acima(tmp_path):
    # Arrange — projeto dentro de repositório maior: é o caso das próprias fixtures
    # depois do `make sync`, e o `historia.py` já registra isso num comentário
    def git(raiz, *args):
        subprocess.run(['git', *args], cwd=raiz, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'teste@exemplo.local')
    git(tmp_path, 'config', 'user.name', 'Teste')
    (tmp_path / 'raiz.py').write_text('x = 1')
    git(tmp_path, 'add', '-A')
    git(tmp_path, 'commit', '-q', '-m', 'c')
    sub = tmp_path / 'sub'
    sub.mkdir()
    (sub / 'a.py').write_text('y = 1')
    # Act / Assert
    assert commits_por_pasta(sub, dias=90) == {}


def test_commits_por_pasta_conta_o_periodo(tmp_path):
    # Arrange
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git('init', '-q')
    git('config', 'user.email', 'teste@exemplo.local')
    git('config', 'user.name', 'Teste')
    (tmp_path / 'api').mkdir()
    for i in range(3):
        (tmp_path / 'api' / f'{i}.php').write_text('<?php')
        git('add', '-A')
        git('commit', '-q', '-m', f'c{i}')
    # Act
    por_pasta = commits_por_pasta(tmp_path, dias=90)
    # Assert
    assert por_pasta.get('api') == 3
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_areas.py -v`
Esperado: FALHA com `ModuleNotFoundError: No module named 'lib.areas'`

- [ ] **Step 3: acrescentar `commits_por_pasta` ao `historia.py`**

```python
def commits_por_pasta(raiz, dias: int = 90) -> dict:
    """Quantos commits do período tocaram cada diretório de primeiro nível em diante.

    É consulta PRÓPRIA da fase de áreas, não um subproduto do `historico()`: aquele
    devolve total e pares de co-mudança, não contagem por diretório. Sem isto o menu
    de escopo não tem como ordenar pelo que está sendo mexido agora.
    """
    # A MESMA guarda de topo do `_de_um_repo`: `git log` sobe a árvore, e sem isto o
    # menu ordenaria pela história de outro repositório. Medido: apontando para um
    # subdiretório, a contagem trazia pastas de fora do escopo auditado.
    topo = _git(raiz, 'rev-parse', '--show-toplevel')
    if topo is None or Path(topo.strip()).resolve() != Path(raiz).resolve():
        return {}

    # Sentinela `\x01` em vez de `len(linha) == 40`: caminho de arquivo com
    # exatamente 40 caracteres e sem espaço era descartado em silêncio.
    saida = _git(raiz, 'log', f'--since={dias}.days', '--name-only',
                 '--pretty=format:\x01%H')
    if not saida:
        return {}

    por_pasta, deste_commit = {}, set()

    def fechar():
        for pasta in deste_commit:
            por_pasta[pasta] = por_pasta.get(pasta, 0) + 1
        deste_commit.clear()

    for linha in saida.split('\n'):
        if linha.startswith('\x01'):
            fechar()           # conta COMMITS, não toques de arquivo: dois commits
            continue           # tocando `api/` devolviam 3 com a contagem direta
        linha = linha.strip()
        if not linha:
            continue
        partes = linha.split('/')
        for i in range(1, len(partes)):
            deste_commit.add('/'.join(partes[:i]))
    fechar()
    return por_pasta
```

- [ ] **Step 3b: pôr teto de tempo no `_git`**

O spec exige: *"limitada no tempo: estourando o teto, cai para ordenação por número de arquivos
e diz isso no `ordenado_por`"*. Hoje `_git` roda `subprocess.run` sem limite.

```python
def _git(raiz, *args, segundos: int = 20):
    try:
        r = subprocess.run(['git', *args], cwd=str(raiz), capture_output=True,
                           text=True, timeout=segundos)
    except subprocess.TimeoutExpired:
        return None          # o chamador cai para o critério sem git
    if r.returncode != 0:
        return None
    return r.stdout
```

```python
# tests/test_areas.py
def test_git_lento_cai_para_contagem_de_arquivos(tmp_path, monkeypatch):
    # Arrange
    import lib.historia as historia
    monkeypatch.setattr(historia, '_git', lambda *a, **k: None)
    arvore = arvore_de(['a/1.py', 'a/2.py', 'a/3.py',
                        'b/1.py', 'b/2.py', 'b/3.py', 'b/4.py'])
    # Act
    recentes = historia.commits_por_pasta(tmp_path)
    ordem = [x['caminho'] for x in detectar(arvore, recentes or None)]
    # Assert — sem git útil, ordena por tamanho e o menu diz isso
    assert recentes == {}
    assert ordem == ['b', 'a']
```

- [ ] **Step 4: escrever o `areas.py`**

```python
"""As áreas do projeto, por agrupamento de diretórios da árvore.

NÃO usa a detecção por convenção de caminho (`superficie.py`): ela marcou 29
"rotas" que eram controllers num projeto PHP e não achou as 20 áreas do App Router
num Next.js. Ela continua valendo para a seção "Superfície pública", onde sai
marcada como dedução — mas não pode decidir o escopo, que é a primeira tela.

Os limiares têm número porque, sem número, cada projeto geraria um menu diferente
por motivo que ninguém sabe explicar. Os dois casos-âncora são o monorepo por
justaposição (áreas no nível 1) e o Next.js (áreas em `src/app/(app)/`).
"""
from collections import Counter

DOMINANTE = 0.80        # um filho com ≥ 80% dos arquivos: desce mais
MIN_FILHOS = 3          # a partir de 3 filhos acima do piso, corta aqui
PISO_ARQUIVOS = 3       # abaixo disso não é área, é pasta solta


def _conta_por_prefixo(arvore: list) -> Counter:
    contagem = Counter()
    for item in arvore:
        if item['gerado']:
            continue
        partes = item['caminho'].replace('\\', '/').split('/')
        for i in range(1, len(partes)):
            contagem['/'.join(partes[:i])] += 1
    return contagem


def _filhos(contagem: Counter, pai: str) -> list:
    prefixo = f'{pai}/' if pai else ''
    nivel = len(prefixo.split('/')) - 1 if prefixo else 0
    return [c for c in contagem
            if c.startswith(prefixo) and len(c.split('/')) == nivel + 1]


def _descer(contagem: Counter, pai: str, total: int) -> list:
    filhos = [f for f in _filhos(contagem, pai) if contagem[f] >= PISO_ARQUIVOS]
    if not filhos:
        return [pai] if pai else []
    if len(filhos) >= MIN_FILHOS:
        return sorted(filhos)
    dominante = max(filhos, key=lambda f: contagem[f])
    # O denominador é a soma DOS FILHOS, não o total do projeto. Com o total,
    # arquivos soltos na raiz diluíam a fração: `src` com 9 de 12 arquivos dava
    # 0,75 < 0,80 e a descida parava em `src`, devolvendo uma área só.
    no_nivel = sum(contagem[f] for f in filhos)
    if contagem[dominante] >= DOMINANTE * no_nivel:
        return _descer(contagem, dominante, contagem[dominante])
    return sorted(filhos)


def detectar(arvore: list, recentes: dict | None) -> list:
    """As áreas, ordenadas pelo que foi mais mexido — ou por tamanho, sem git."""
    contagem = _conta_por_prefixo(arvore)
    total = sum(1 for i in arvore if not i['gerado'])
    caminhos = _descer(contagem, '', total)

    areas = [{'caminho': c, 'arquivos': contagem[c],
              'commits_recentes': (recentes or {}).get(c, 0)} for c in caminhos]
    if recentes:
        areas.sort(key=lambda a: (-a['commits_recentes'], -a['arquivos'], a['caminho']))
    else:
        areas.sort(key=lambda a: (-a['arquivos'], a['caminho']))
    return areas
```

- [ ] **Step 5: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_areas.py -v`
Esperado: 7 passed

- [ ] **Step 6: prova por mutação no piso**

Troque `if contagem[f] >= PISO_ARQUIVOS` por `if True` e rode.
Esperado: `test_pasta_abaixo_do_piso_nao_vira_area` **FALHA**. Desfaça e confirme o verde.

- [ ] **Step 7: calibrar contra os seis projetos reais**

Rode a detecção nos projetos que já temos e **olhe os menus**:

```bash
cd ~/.claude/skills/sw-codebase-guide
.venv/bin/python -c "
import sys; sys.path.insert(0,'scripts')
from lib.arvore import varrer
from lib.areas import detectar
from lib.historia import commits_por_pasta
for r in ['<projeto 1>', '<projeto 2>', '<projeto 3>']:
    a = detectar(varrer(r), commits_por_pasta(r))
    print(r, '→', [(x['caminho'], x['arquivos']) for x in a[:6]])
"
```

É a validação da suposição nº 2 do spec: *agrupamento de diretórios produz áreas que o dev
reconhece*. Se alguma lista não parecer um conjunto de áreas, ajuste os limiares e **registre o
número novo no plano**, em "Ajustes durante a execução" — não mude em silêncio.

---

### Task 4: `varrer.py --areas` — a fase que não grava

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/varrer.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_varrer.py`

**Depende de:** Tasks 2 e 3

**Contrato que esta task publica:** CLI
`python3 scripts/varrer.py --projeto X --areas` → imprime JSON em stdout, **não grava nada**

**A restrição que manda aqui:** `test_varrer_so_escreve_em_docs_project` afirma que o diretório
de saída contém exatamente `['inventory.json']`. Qualquer arquivo intermediário o quebra — por
isso a fase de áreas sai por stdout.

- [ ] **Step 1: escrever os testes que falham**

```python
# acrescentar a tests/test_varrer.py
def rodar_areas(projeto):
    return subprocess.run(
        [sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
         '--projeto', str(projeto), '--areas'],
        capture_output=True, text=True)


def test_fase_de_areas_imprime_json_em_stdout(tmp_path):
    # Arrange
    projeto = projeto_simples(tmp_path / 'p')
    for pasta in ('funil', 'tarefas', 'agenda'):
        (projeto / 'src' / pasta).mkdir(parents=True)
        for i in range(3):
            (projeto / 'src' / pasta / f'{i}.py').write_text('x = 1')
    # Act
    r = rodar_areas(projeto)
    # Assert
    assert r.returncode == 0, r.stderr
    saida = json.loads(r.stdout)
    assert set(saida) >= {'areas', 'total_arquivos', 'ordenado_por'}
    assert {a['caminho'] for a in saida['areas']} >= {'src/funil', 'src/tarefas'}


def test_fase_de_areas_nao_grava_nada(tmp_path):
    # Arrange
    projeto = projeto_simples(tmp_path / 'p')
    antes = {p for p in tmp_path.rglob('*')}
    # Act
    r = rodar_areas(projeto)
    # Assert — o returncode importa: sem ele o teste passava inteirinho mesmo se
    # `--areas` não existisse, e o step "esperado: FALHA" nunca aconteceria
    assert r.returncode == 0, r.stderr
    assert {p for p in tmp_path.rglob('*')} == antes


def test_fase_de_areas_nao_abre_codigo(tmp_path, monkeypatch):
    # Arrange — lista branca: a fase de áreas só pode abrir o que `textos` declara
    projeto = projeto_simples(tmp_path / 'p')
    (projeto / 'README.md').write_text('# Loja')
    abertos = []
    import pathlib
    original = pathlib.Path.read_text

    def espiao(self, *a, **k):
        abertos.append(str(self))
        return original(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, 'read_text', espiao)
    monkeypatch.setattr('builtins.open', lambda *a, **k: abertos.append(str(a[0])) or
                        original_open(*a, **k))
    # Act
    sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))
    from varrer import apurar_areas
    apurar_areas(projeto)
    # Assert — o par POSITIVO primeiro: sem ele o laço não executa e o teste passa
    # sem provar nada. `apurar_areas` TEM que ler as fontes textuais, senão a
    # conferência de trecho literal não tem de onde sair.
    from lib.textos import eh_fonte_textual
    dentro = [c for c in abertos if str(projeto) in c]
    assert dentro, 'a fase de áreas não leu nenhuma fonte textual'
    for caminho in dentro:
        relativo = str(Path(caminho).relative_to(projeto))
        assert eh_fonte_textual(relativo), f'abriu {relativo}, que não é fonte textual'
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_varrer.py -v`
Esperado: FALHA — `--areas` não existe (`returncode != 0`) e `apurar_areas` não importa

- [ ] **Step 3: acrescentar a fase ao `varrer.py`**

```python
def apurar_areas(projeto: Path) -> dict:
    """A fase barata: o que alimenta o menu de escopo. Não grava nada.

    Só `os.walk` com poda, mais uma consulta git limitada por data. É a lista
    branca da restrição: a única leitura de arquivo permitida aqui é a das fontes
    textuais, porque a conferência de trecho literal depende do conteúdo delas.
    """
    arquivos = mod_arvore.varrer(projeto)
    recentes = historia.commits_por_pasta(projeto)
    # as fontes textuais são lidas AQUI, na fase barata: a conferência de trecho
    # literal depende do conteúdo delas, e é a única leitura que a lista branca
    # da restrição permite nesta fase
    fontes = textos.coletar(projeto, arquivos)
    return {
        'areas': areas.detectar(arquivos, recentes or None),
        'total_arquivos': len(arquivos),
        'stacks': len(stacks.detectar(projeto)),
        'fontes_textuais': sorted(fontes),
        'ordenado_por': 'commits_recentes' if recentes else 'arquivos',
    }
```

E no `main()`, antes de exigir `--out`:

```python
    p.add_argument('--areas', action='store_true',
                   help='imprime as áreas em stdout e sai, sem gravar nada')
    p.add_argument('--area', default=None,
                   help='recorta a varredura a esta área (o caminho, não o rótulo)')
    args = p.parse_args()

    projeto = Path(args.projeto).resolve()
    if not projeto.is_dir():
        print(f'não é um diretório: {projeto}', file=sys.stderr)
        return 2

    if args.areas:
        print(json.dumps(apurar_areas(projeto), indent=1, ensure_ascii=False))
        return 0

    if not args.out:
        print('--out é obrigatório fora do modo --areas', file=sys.stderr)
        return 2
```

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_varrer.py -v`
Esperado: 8 passed — os 5 de antes mais os 3 novos.

Confira em especial `test_fase_de_areas_nao_grava_nada` e `test_fase_de_areas_nao_abre_codigo`:
são as duas restrições verificáveis desta task.

- [ ] **Step 5: prova por mutação na lista branca**

Em `apurar_areas`, acrescente uma leitura indevida — `(projeto / 'package.json').read_text()` —
e rode. Esperado: `test_fase_de_areas_nao_abre_codigo` **FALHA**. Remova e confirme o verde.

---

### Task 5: o recorte por área

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/varrer.py`
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/lib/historia.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_recorte.py`

**Depende de:** Task 4

**Contrato que esta task publica:** `apurar(projeto: Path, area: str | None) -> dict`, com
`inventario['escopo'] = {'area': str | None, 'criterio': str, 'n_arquivos': int}` ·
`historia.historico(raiz, area=None)`

**As três regras, e por que são diferentes:**

| Seção | Regra | Por quê |
|---|---|---|
| `arvore`, `superficie`, `textos` | prefixo | são inventário do que existe ali |
| `stacks`, `ambiente` | prefixo **+ herança do que mora acima**, marcada | o `package.json` está em `.` e o `.env` na raiz; prefixo puro faria o documento dizer "nenhum manifesto reconhecido", que é falso |
| `historia`, `mencoes` | **uma ponta dentro** | o valor das orientações vem do par que CRUZA a fronteira |

- [ ] **Step 1: escrever os testes que falham**

```python
# tests/test_recorte.py
import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent


def git(raiz, *args):
    subprocess.run(['git', *args], cwd=raiz, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def projeto_com_area(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / 'area').mkdir()
    (tmp_path / 'fora').mkdir()
    (tmp_path / 'package.json').write_text('{"name": "app"}')
    (tmp_path / '.env').write_text('DB_HOST=localhost\nAPP_NAME=loja\n')
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'teste@exemplo.local')
    git(tmp_path, 'config', 'user.name', 'Teste')
    for i in range(60):
        (tmp_path / 'area' / 'a.py').write_text(f'x = {i}')
        (tmp_path / 'fora' / 'b.py').write_text(f'y = {i}')
        git(tmp_path, 'add', '-A')
        git(tmp_path, 'commit', '-q', '-m', f'c{i}')
    return tmp_path


def varrer_com_area(projeto, saida, area):
    r = subprocess.run(
        [sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
         '--projeto', str(projeto), '--out', str(saida), '--area', area],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads((saida / 'inventory.json').read_text())


def test_arvore_recorta_por_prefixo(tmp_path):
    # Arrange
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert
    assert all(a['caminho'].startswith('area/') for a in inv['arvore'])


def test_stack_e_env_da_raiz_sao_herdados(tmp_path):
    # Arrange — o package.json está em `.` e o .env na raiz; recorte por prefixo
    # puro faria o documento dizer "nenhum manifesto reconhecido", que é falso
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert
    assert inv['stacks'], 'a stack da raiz sumiu'
    assert inv['stacks'][0]['de_fora_da_area'] is True
    assert '.env' in inv['ambiente']


def test_co_mudanca_cruzando_a_fronteira_sobrevive(tmp_path):
    # Arrange — `area/a.py` e `fora/b.py` mudam sempre juntos
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert — é exatamente esse par que vira "para mexer na área você mexe lá fora"
    pares = [tuple(sorted(c['arquivos'])) for c in inv['historia']['co_mudanca']]
    assert ('area/a.py', 'fora/b.py') in pares


def test_evidencia_que_cruza_a_fronteira_e_aceita(tmp_path):
    # Arrange — a orientação "para mexer na área você mexe lá fora" cita um arquivo
    # de fora, e a guarda de caminho a recusava porque a árvore vinha recortada
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert
    assert 'fora/b.py' in inv['caminhos_do_projeto']
    assert all(a['caminho'].startswith('area/') for a in inv['arvore'])


def test_escopo_fica_gravado_no_inventario(tmp_path):
    # Arrange
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert — sem isto, "mesmos fatos, mesmo documento" passaria a depender de
    # lembrar o que foi clicado no menu
    assert inv['escopo']['area'] == 'area'
    assert inv['escopo']['n_arquivos'] >= 1


def test_area_de_subrepo_preserva_a_co_mudanca(tmp_path):
    # Arrange — monorepo por justaposição: a raiz não tem git, `api` e `web` têm.
    # O filtro rodando antes do prefixo comparava `api` com `app/X.php` e zerava tudo.
    raiz = tmp_path / 'mono'
    for nome in ('api', 'web'):
        sub = raiz / nome
        sub.mkdir(parents=True)
        git(sub, 'init', '-q')
        git(sub, 'config', 'user.email', 'teste@exemplo.local')
        git(sub, 'config', 'user.name', 'Teste')
        for i in range(60):
            (sub / 'a.py').write_text(f'x = {i}')
            (sub / 'b.py').write_text(f'y = {i}')
            git(sub, 'add', '-A')
            git(sub, 'commit', '-q', '-m', f'c{i}')
    # Act
    inv = varrer_com_area(raiz, tmp_path / 'out', 'api')
    # Assert
    pares = [tuple(sorted(c['arquivos'])) for c in inv['historia']['co_mudanca']]
    assert ('api/a.py', 'api/b.py') in pares


def test_commits_continuam_do_projeto_todo(tmp_path):
    # Arrange
    projeto = projeto_com_area(tmp_path / 'p')
    # Act
    inv = varrer_com_area(projeto, tmp_path / 'out', 'area')
    # Assert — o número é do projeto; o documento é que diz isso por extenso
    assert inv['historia']['commits'] == 60
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_recorte.py -v`
Esperado: FALHA — `--area` ainda não recorta nada (`arvore` vem inteira)

- [ ] **Step 3: filtrar a co-mudança ANTES do teto e DEPOIS do prefixo de sub-repo**

```python
def _cruza_ou_entra(par, area: str) -> bool:
    prefixo = f'{area}/'
    return any(a == area or a.startswith(prefixo) for a in par)
```

O filtro **não pode** ficar dentro de `_de_um_repo`: num monorepo por justaposição é o
`historico()` que acrescenta o prefixo do sub-repo aos caminhos, e filtrar antes disso compara
`area='api'` com `app/X.php` — nunca casa. Medido: 2 pares viram **0**, e o documento volta a
imprimir *"Não apurado: a raiz não é repositório git"*, que é falso. É a reintrodução exata do
defeito que `test_co_mudanca_de_subrepos_aparece_com_ressalva` existe para impedir.

Então o filtro mora no fim de `historico()`, depois da junção dos sub-repos — e **antes** do
corte em `MAX_PARES`:

```python
    # no fim de `historico()`, depois da junção dos sub-repos e ANTES do corte:
    if area:
        co_mudanca = [c for c in co_mudanca
                      if _cruza_ou_entra(c['arquivos'], area)]
    co_mudanca = co_mudanca[:MAX_PARES]
```

> O "antes do teto" não é detalhe: `MAX_PARES = 40` é global. Filtrar **depois** dos 40 pares
> do projeto devolveria um ou dois para a área e apagaria o sinal que a seção existe para dar.

- [ ] **Step 4: recortar no `apurar` do `varrer.py`**

```python
def _dentro(caminho: str, area: str | None) -> bool:
    return area is None or caminho == area or caminho.startswith(f'{area}/')


def apurar(projeto: Path, area: str | None = None) -> dict:
    todos = mod_arvore.varrer(projeto)
    arquivos = [a for a in todos if _dentro(a['caminho'], area)]

    # stack e ambiente ACIMA da área entram herdados e marcados: sem isto o
    # "Como entrar" de uma área esvazia, porque o manifesto mora na raiz
    componentes = []
    for c in stacks.detectar(projeto):
        if _dentro(c['caminho'], area):
            componentes.append({**c, 'de_fora_da_area': False})
        elif area and (c['caminho'] == '.' or area.startswith(f"{c['caminho']}/")):
            componentes.append({**c, 'de_fora_da_area': True})

    simbolos = textual.simbolos_de(arquivos)[:MAX_SIMBOLOS]
    # os símbolos são os da área, procurados no repositório INTEIRO: senão some
    # quem usa a área de fora
    por_simbolo = {s: m for s, m in textual.todas_as_mencoes(projeto, simbolos).items()
                   if len(m) > 1}

    ambiente = {}
    for item in todos:
        nome = Path(item['caminho']).name
        if nome == '.env' or nome.startswith('.env.'):
            if _dentro(item['caminho'], area) or Path(item['caminho']).parent == Path('.'):
                try:
                    texto = (projeto / item['caminho']).read_text('utf-8', 'replace')
                except OSError:
                    continue
                ambiente[item['caminho']] = redact.chaves_de_env(texto)

    return {
        'gerado_em_versao': VERSAO,
        # `caminhos_do_projeto` existe para a guarda de evidência: sem ele, uma
        # orientação citando `fora/b.py` — exatamente a frase que a seção existe
        # para dizer — era recusada, porque a árvore recortada não a contém.
        'caminhos_do_projeto': sorted(a['caminho'] for a in todos),
        'escopo': {'area': area, 'criterio': 'prefixo de caminho',
                   'n_arquivos': len(arquivos)},
        'stacks': componentes,
        'arvore': arquivos,
        'historia': historia.historico(projeto, area=area),
        'imports': imports.grafo(projeto, componentes),
        'superficie': [s for s in superficie.detectar(projeto)
                       if _dentro(s['caminho'], area)],
        # `textos` NÃO é recortado: a guarda da vacuidade exige que `fonte` esteja
        # aqui, e recortar impediria o agente de citar `docs/arquitetura.md` numa
        # rodada de área. O conteúdo já passa por redação, então não há custo.
        'textos': textos.coletar(projeto, todos),
        'ambiente': dict(sorted(ambiente.items())),
        'mencoes': dict(sorted(por_simbolo.items())),
    }
```

- [ ] **Step 5: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_recorte.py -v`
Esperado: 5 passed

São duas restrições verificáveis nesta task: `test_co_mudanca_cruzando_a_fronteira_sobrevive` e
`test_stack_e_env_da_raiz_sao_herdados`.

- [ ] **Step 6: prova por mutação no filtro da co-mudança**

Mova o filtro de `_cruza_ou_entra` para **depois** do `most_common(MAX_PARES)` e rode.
Esperado: `test_co_mudanca_cruzando_a_fronteira_sobrevive` **FALHA** ou devolve lista vazia.
Desfaça e confirme o verde.

- [ ] **Step 7: a suíte inteira continua verde**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q`
Esperado: todos verdes. **É o critério de fechamento do marco 1** — os 92 testes de antes mais
os novos, sem nenhum quebrado por causa do recorte.

---

### Task 6: `montar.py` entende o escopo

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/montar.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_montar.py`

**Depende de:** Task 5

- [ ] **Step 1: escrever os testes que falham**

```python
# acrescentar a tests/test_montar.py
def test_documento_diz_qual_escopo_o_gerou(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['escopo'] = {'area': 'app', 'criterio': 'prefixo de caminho', 'n_arquivos': 1}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — quem lê precisa saber que está vendo um recorte
    assert 'app' in guia.split('\n')[2:8].__str__()
    assert 'recorte' in guia.lower() or 'escopo' in guia.lower()


def test_stack_de_fora_da_area_sai_marcada(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['escopo'] = {'area': 'app', 'criterio': 'prefixo', 'n_arquivos': 1}
    inv['stacks'] = [{'stack': 'node', 'caminho': '.', 'manifesto': 'package.json',
                      'por': 'manifesto', 'de_fora_da_area': True}]
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert
    assert 'fora da área' in guia or 'fora da area' in guia


def test_ponta_de_fora_sai_marcada(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['escopo'] = {'area': 'app', 'criterio': 'prefixo', 'n_arquivos': 1}
    inv['historia'] = {'commits': 90, 'commits_descartados': 0,
                       'co_mudanca': [{'arquivos': ['app/a.py', 'fora/b.py'], 'vezes': 9}],
                       'lacuna': None}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — "mexer aqui mexe lá fora" só ensina se o leitor souber qual é o lá fora
    assert '`fora/b.py` *(fora)*' in guia
    assert '`app/a.py`' in guia and '`app/a.py` *(fora)*' not in guia


def test_commits_do_projeto_todo_sao_declarados(tmp_path):
    # Arrange
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    inv = json.loads((tmp_path / 'inventory.json').read_text())
    inv['escopo'] = {'area': 'app', 'criterio': 'prefixo', 'n_arquivos': 1}
    inv['historia'] = {'commits': 500, 'commits_descartados': 0,
                       'co_mudanca': [{'arquivos': ['app/a.py', 'fora/b.py'], 'vezes': 9}],
                       'lacuna': None}
    (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    # Act
    montar(tmp_path)
    guia = (tmp_path / 'guide.md').read_text()
    # Assert — o número é do projeto, não da área, e o documento não pode esconder isso
    assert 'projeto todo' in guia
    assert 'fora/b.py' in guia
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_montar.py -v`
Esperado: 3 failed — o documento ainda não sabe do escopo

- [ ] **Step 3: escrever o cabeçalho de escopo e as marcas**

No início de `montar()`, logo depois da nota de confiança:

```python
    escopo = inv.get('escopo') or {}
    if escopo.get('area'):
        A(f'> **Recorte:** este documento cobre a área `{escopo["area"]}` '
          f'({escopo["n_arquivos"]} arquivos), não o projeto inteiro.\n')
```

Na listagem de stacks:

```python
    for c in inv['stacks']:
        marca = '  *(fora da área, herdado da raiz)*' if c.get('de_fora_da_area') else ''
        A(f'- **{c["stack"]}** em `{c["caminho"]}` — {_como_foi_detectada(c)}  [fato]{marca}')
```

E na contagem de commits, quando há recorte:

```python
        de_onde = ' do projeto todo' if escopo.get('area') else ''
        A(f'De {h["commits"]} commits{de_onde} '
          f'({h["commits_descartados"]} descartados por tocarem arquivos demais).  [fato]\n')
```

E cada par marca a ponta que está fora da área — é a restrição verificável do spec, derivada
aqui a partir do `escopo`, sem campo novo no inventário:

```python
    area = escopo.get('area')
    for c in h['co_mudanca'][:20]:
        marcas = [f'`{a}`' + ('' if not area or _dentro_da_area(a, area) else ' *(fora)*')
                  for a in c['arquivos']]
        A(f'- {marcas[0]} + {marcas[1]} — {c["vezes"]}x')
```

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q`
Esperado: todos verdes. **Marco 1 fechado.**

---

### Task 7: a guarda de caminho, nas quatro formas

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/montar.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_montar.py`

**Depende de:** Task 6

**Contrato que esta task publica:** `evidencia_valida(ev: str, caminhos: set) -> bool`

**O que esta task existe para não quebrar:** o `SKILL.md` documenta `["app/Pedido.php:88"]` e os
testes usam `["rotas.py:1"]` e `["commit 3c5aabb"]`. Uma conferência ingênua recusaria a
evidência **correta** e derrubaria três testes que já passam.

- [ ] **Step 1: escrever os testes que falham**

```python
# acrescentar a tests/test_montar.py
def _com_evidencia(tmp_path, evidencias):
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    linhas = ''.join(
        f'[[afirmacao]]\nsecao = "o-que-faz"\ntexto = "t{i}"\nnivel = "deducao"\n'
        f'evidencia = {json.dumps([e])}\nmotivo = ""\n\n'
        for i, e in enumerate(evidencias))
    (tmp_path / 'interpretation.toml').write_text(linhas)
    return montar(tmp_path)


def test_quatro_formas_de_evidencia(tmp_path):
    # Arrange / Act — caminho, caminho:linha, diretório e não-caminho
    r = _com_evidencia(tmp_path, ['rotas.py', 'rotas.py:3', 'app/', 'commit 3c5aabb'])
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout


def test_caminho_inventado_recusado_nos_dois_blocos(tmp_path):
    # Arrange / Act
    r = _com_evidencia(tmp_path, ['nao/existe.php'])
    # Assert
    assert r.returncode == 2
    assert 'nao/existe.php' in (r.stderr + r.stdout)


def test_diretorio_casa_por_prefixo(tmp_path):
    # Arrange — a árvore só tem arquivos; `app/` é diretório e é citação legítima
    r = _com_evidencia(tmp_path, ['app/'])
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_montar.py -v`
Esperado: `test_caminho_inventado_recusado_nos_dois_blocos` FALHA (hoje nada é conferido)

- [ ] **Step 3: escrever a guarda**

```python
# `evidencia_valida` usa `re.search`, e o `montar.py` de hoje importa só
# `argparse, json, sys, tomllib, Path` — sem esta linha é `NameError` com traceback.
import re

# prefixo que denuncia evidência que NÃO é caminho de arquivo
NAO_CAMINHO = ('commit ', 'http://', 'https://')


def evidencia_valida(ev: str, caminhos: set) -> bool:
    """A evidência aponta para algo que existe? Quatro formas são legítimas.

    O `SKILL.md` documenta `app/Pedido.php:88` e os testes usam `commit 3c5aabb`.
    Uma conferência ingênua recusaria a evidência CORRETA.
    """
    if ev.startswith(NAO_CAMINHO):
        return True
    alvo = ev.rsplit(':', 1)[0] if re.search(r':\d+$', ev) else ev
    if alvo in caminhos:
        return True
    if alvo.endswith('/'):
        return any(c.startswith(alvo) for c in caminhos)
    return False
```

e, em `_ler_interpretacao`, recebendo o conjunto de caminhos:

```python
        # `caminhos` vem de `inv['caminhos_do_projeto']`, NÃO de `inv['arvore']`:
        # com área escolhida a árvore está recortada, e citar a ponta de fora é
        # legítimo — é o que a seção de orientações existe para dizer.
        for ev in a.get('evidencia', []):
            if not evidencia_valida(ev, caminhos):
                raise ValueError(f'evidência não existe no projeto: {ev!r}')
```

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q`
Esperado: todos verdes — inclusive os três antigos que usam `rotas.py:1` e `commit 3c5aabb`.

- [ ] **Step 5: prova por mutação no descascamento da linha**

Troque `alvo = ev.rsplit(':', 1)[0] if ... else ev` por `alvo = ev` e rode.
Esperado: `test_quatro_formas_de_evidencia` **FALHA**. Desfaça e confirme o verde.

---

### Task 8: o bloco `[[narrativa]]` e a recusa no parser

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/montar.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_narrativa.py`

**Depende de:** Task 7

**Contrato que esta task publica:** `PROIBIDAS` passa a viver no `montar.py` ·
`_ler_narrativa(caminho, caminhos, textos) -> list`

- [ ] **Step 1: escrever os testes que falham**

```python
# tests/test_narrativa.py
import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / 'fixtures'


def preparar(tmp_path, toml):
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(FIXTURES / 'acoplamento_invisivel'),
                    '--out', str(tmp_path)], check=True, capture_output=True)
    (tmp_path / 'interpretation.toml').write_text(toml)
    return subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                           '--dir', str(tmp_path)], capture_output=True, text=True)


def test_frase_proibida_recusada_pelo_parser(tmp_path):
    # Arrange — a garantia mais forte da skill fica exposta a prosa livre pela
    # primeira vez; o teste de saída não basta, a recusa é do parser
    r = preparar(tmp_path,
                 '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
                 'texto = "A pasta app não é usada em lugar nenhum"\n'
                 'evidencia = ["app/"]\n')
    # Assert
    assert r.returncode == 2
    assert 'não é usado' in (r.stderr + r.stdout) or 'proibida' in (r.stderr + r.stdout).lower()


def test_parte_invalida_e_recusada(tmp_path):
    # Act
    r = preparar(tmp_path,
                 '[[narrativa]]\nparte = "conclusao"\nordem = 1\n'
                 'texto = "x"\nevidencia = ["app/"]\n')
    # Assert
    assert r.returncode == 2
    assert 'parte' in (r.stderr + r.stdout).lower()
    assert 'Traceback' not in r.stderr


def test_campo_obrigatorio_por_parte(tmp_path):
    # Arrange — `o-que-e` exige `trecho` e `fonte`; `mapa` não
    r = preparar(tmp_path,
                 '[[narrativa]]\nparte = "o-que-e"\n'
                 'texto = "É um sistema de pedidos"\nevidencia = ["app/"]\n')
    # Assert
    assert r.returncode == 2
    assert 'trecho' in (r.stderr + r.stdout).lower()


def test_ordem_governa_o_mapa(tmp_path):
    # Arrange — sem `ordem`, `_escrever` ordenaria por texto e embaralharia a árvore
    r = preparar(tmp_path,
                 '[[narrativa]]\nparte = "mapa"\nordem = 2\n'
                 'texto = "zzz segunda linha"\nevidencia = ["app/"]\n\n'
                 '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
                 'texto = "aaa primeira linha"\nevidencia = ["app/"]\n')
    # Assert
    assert r.returncode == 0, r.stderr
    doc = (tmp_path / 'leia-me.md').read_text()
    assert doc.index('aaa primeira') < doc.index('zzz segunda')
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_narrativa.py -v`
Esperado: 4 failed — não há bloco `[[narrativa]]` nem `leia-me.md`

- [ ] **Step 3: mover `PROIBIDAS` para o `montar.py` e validar a narrativa**

```python
# Frases que a skill NUNCA emite: o grafo não sabe o bastante para afirmar
# ausência, e "nada depende disso" é o dano que ela existe para evitar.
# Mora aqui, e não no teste, porque a recusa é do parser — duas listas
# divergiriam na primeira vez que alguém acrescentasse uma frase a uma só.
# Em prosa livre sobre pasta o FEMININO é a forma natural — "a pasta não é usada".
# A lista veio de um `guide.md` templatizado, onde só o masculino aparecia; para
# texto do agente ela precisa da flexão, senão a guarda passa ao largo.
PROIBIDAS = ('nada depende', 'sem dependentes', 'nenhum dependente',
             'não é usad', 'nao e usad', 'não são usad', 'nao sao usad',
             'não há dependentes', 'nao ha dependentes', 'sem uso')

PARTES = {'o-que-e', 'percurso', 'mapa', 'orientacoes'}
OBRIGATORIOS = {
    'o-que-e': ('texto', 'trecho', 'fonte', 'evidencia'),
    'percurso': ('texto', 'evidencia'),
    'mapa': ('texto', 'evidencia'),
    'orientacoes': ('texto', 'evidencia'),
}


def _ler_narrativa(dados: dict, caminhos: set) -> list:
    blocos = dados.get('narrativa', [])
    for b in blocos:
        parte = b.get('parte')
        if parte not in PARTES:
            raise ValueError(f'parte inválida ou ausente: {parte!r}')
        for campo in OBRIGATORIOS[parte]:
            if not b.get(campo):
                raise ValueError(f'{parte}: campo obrigatório ausente: {campo}')
        baixo = b['texto'].lower()
        for frase in PROIBIDAS:
            if frase in baixo:
                raise ValueError(
                    f'{parte}: frase proibida no texto ({frase!r}) — ausência de '
                    f'dependentes nunca é afirmada')
        for ev in b['evidencia']:
            if not evidencia_valida(ev, caminhos):
                raise ValueError(f'evidência não existe no projeto: {ev!r}')
    return sorted(blocos, key=lambda b: (b['parte'], b.get('ordem', 0)))
```

E no `tests/test_montar.py`, trocar a tupla local por `from montar import PROIBIDAS`.

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q`
Esperado: todos verdes.

- [ ] **Step 5: prova por mutação na recusa da frase proibida**

Troque `for frase in PROIBIDAS:` por `for frase in ():` e rode.
Esperado: `test_frase_proibida_recusada_pelo_parser` **FALHA**. Desfaça e confirme o verde.

---

### Task 9: a guarda do trecho literal

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/montar.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_narrativa.py`

**Depende de:** Task 8

**Por que esta é a guarda que mais importa:** o pior modo de falha da parte "o que o produto
faz" não é falsidade — é ser **fluente, verdadeira e inútil**. *"O sistema gerencia clientes e
aeronaves, com um funil de vendas"* passa em qualquer conferência de caminho, e o dev já sabia
disso lendo o nome das pastas. Trecho literal não consegue ser vazio-e-fluente.

- [ ] **Step 1: escrever os testes que falham**

```python
# acrescentar a tests/test_narrativa.py
def com_readme(tmp_path, readme, bloco):
    projeto = tmp_path / 'proj'
    projeto.mkdir()
    (projeto / 'README.md').write_text(readme)
    (projeto / 'app.py').write_text('x = 1')
    (projeto / 'pyproject.toml').write_text('[project]\nname = "x"')
    saida = tmp_path / 'out'
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True)
    (saida / 'interpretation.toml').write_text(bloco)
    r = subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                        '--dir', str(saida)], capture_output=True, text=True)
    return r, saida


def test_trecho_que_nao_existe_e_recusado(tmp_path):
    # Act
    r, _ = com_readme(
        tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
        '[[narrativa]]\nparte = "o-que-e"\n'
        'texto = "É um sistema de pedidos"\n'
        'trecho = "Sistema de gestão hospitalar"\nfonte = "README.md"\n'
        'evidencia = ["README.md"]\n')
    # Assert
    assert r.returncode == 2
    assert 'trecho' in (r.stderr + r.stdout).lower()


def test_trecho_quebrado_em_duas_linhas_casa(tmp_path):
    # Arrange — README quebrado em 80 colunas faz qualquer frase atravessar linhas;
    # sem normalizar espaço a guarda nasce morta
    r, saida = com_readme(
        tmp_path, '# Loja\n\nSistema de pedidos\npara padarias de bairro.',
        '[[narrativa]]\nparte = "o-que-e"\n'
        'texto = "É um sistema de pedidos para padarias"\n'
        'trecho = "Sistema de pedidos para padarias de bairro."\nfonte = "README.md"\n'
        'evidencia = ["README.md"]\n')
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout
    assert 'padarias de bairro' in (saida / 'leia-me.md').read_text()


def test_fonte_fora_das_fontes_textuais_e_recusada(tmp_path):
    # Act — `app.py` existe, mas não é fonte textual reconhecida
    r, _ = com_readme(
        tmp_path, '# Loja\n\nSistema de pedidos.',
        '[[narrativa]]\nparte = "o-que-e"\n'
        'texto = "É um sistema"\ntrecho = "x = 1"\nfonte = "app.py"\n'
        'evidencia = ["app.py"]\n')
    # Assert
    assert r.returncode == 2
    assert 'fonte' in (r.stderr + r.stdout).lower()
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_narrativa.py -v`
Esperado: 3 failed — o trecho ainda não é conferido

- [ ] **Step 3: escrever a conferência**

```python
def _normalizar(texto: str) -> str:
    """Colapsa espaço, tabulação e quebra de linha num espaço só.

    Sem isto a guarda nasce morta: README quebrado em 80 colunas faz qualquer
    frase citada atravessar linhas, a substring exata falha, e o agente aprende a
    citar fragmentos de quatro palavras para escapar — o oposto do que se quer.
    """
    return ' '.join(texto.split())


def _conferir_trecho(bloco: dict, textos: dict) -> None:
    fonte = bloco['fonte']
    if fonte not in textos:
        raise ValueError(
            f'fonte não é fonte textual reconhecida: {fonte!r} — '
            f'use README, CLAUDE.md, docs/ ou ADR')
    if _normalizar(bloco['trecho']) not in _normalizar(textos[fonte]['conteudo']):
        raise ValueError(
            f'o trecho citado não aparece em {fonte}: {bloco["trecho"][:60]!r}')
```

chamada em `_ler_narrativa`, para os blocos `o-que-e`.

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q`
Esperado: todos verdes.

- [ ] **Step 5: prova por mutação na normalização**

Troque `_normalizar(bloco['trecho']) not in _normalizar(...)` por
`bloco['trecho'] not in textos[fonte]['conteudo']` e rode.
Esperado: `test_trecho_quebrado_em_duas_linhas_casa` **FALHA**. Desfaça e confirme o verde.

---

### Task 10: o `leia-me.md` — as quatro partes

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/scripts/montar.py`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_narrativa.py`

**Depende de:** Task 9

**Contrato que esta task publica:** `montar.py --dir D` grava `guide.md` **e** `leia-me.md`

- [ ] **Step 1: escrever os testes que falham**

```python
# acrescentar a tests/test_narrativa.py
QUATRO_PARTES = (
    '[[narrativa]]\nparte = "o-que-e"\n'
    'texto = "É um sistema de pedidos para padarias"\n'
    'trecho = "Sistema de pedidos para padarias"\nfonte = "README.md"\n'
    'evidencia = ["README.md"]\n\n'
    '[[narrativa]]\nparte = "percurso"\nordem = 1\n'
    'texto = "O pedido entra pela rota e grava direto"\n'
    'evidencia = ["app.py"]\nsaltos = ["o ORM resolve a tabela — não rastreado"]\n\n'
    '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
    'texto = "`app.py` é onde a lógica mora"\nevidencia = ["app.py"]\n\n'
    '[[narrativa]]\nparte = "orientacoes"\nordem = 1\n'
    'texto = "Para mexer na lógica você vai em `app.py`"\nevidencia = ["app.py"]\n')


def test_as_quatro_partes_aparecem_na_ordem(tmp_path):
    # Act
    r, saida = com_readme(tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
                          QUATRO_PARTES)
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout
    doc = (saida / 'leia-me.md').read_text()
    ordem = [doc.index(t) for t in ('O que o produto faz', 'O percurso',
                                    'Onde ficam as coisas', 'Para mexer')]
    assert ordem == sorted(ordem)
    # e o TEXTO de cada bloco cai sob o título certo — a ordem dos títulos é fixa
    # em ORDEM_DAS_PARTES, então sozinha ela não prova nada
    assert doc.index('sistema de pedidos para padarias') < doc.index('O percurso')
    assert doc.index('onde a lógica mora') < doc.index('Para mexer')
    assert doc.index('Para mexer') < doc.index('vai em `app.py`')


def test_o_trecho_literal_aparece_ao_lado_da_parafrase(tmp_path):
    # Act
    _, saida = com_readme(tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
                          QUATRO_PARTES)
    doc = (saida / 'leia-me.md').read_text()
    # Assert — o leitor compara a paráfrase com o que está escrito na fonte
    assert 'É um sistema de pedidos para padarias' in doc
    assert 'Sistema de pedidos para padarias' in doc
    assert 'README.md' in doc


def test_cada_parte_aponta_o_relatorio_tecnico(tmp_path):
    # Arrange — número é livre na narrativa (decisão do dono), então nada impede
    # ela dizer 81 onde o técnico diz 64; o link torna descobrível em um clique
    _, saida = com_readme(tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
                          QUATRO_PARTES)
    doc = (saida / 'leia-me.md').read_text()
    # Assert — um link por parte, não só um global no preâmbulo
    assert doc.count('guide.md#') == 4


def test_saltos_aparecem_onde_acontecem(tmp_path):
    # Act
    _, saida = com_readme(tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
                          QUATRO_PARTES)
    # Assert — salto escondido numa nota de rodapé é o erro mais caro do documento
    assert 'não rastreado' in (saida / 'leia-me.md').read_text()


def test_dois_documentos_identicos_em_duas_montagens(tmp_path):
    # Arrange
    r, saida = com_readme(tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
                          QUATRO_PARTES)
    primeiro = ((saida / 'guide.md').read_bytes(), (saida / 'leia-me.md').read_bytes())
    # Act
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                    '--dir', str(saida)], check=True, capture_output=True)
    # Assert
    assert ((saida / 'guide.md').read_bytes(),
            (saida / 'leia-me.md').read_bytes()) == primeiro


def test_recusa_nao_escreve_nenhum_dos_dois(tmp_path):
    # Arrange — sentinelas
    r, saida = com_readme(tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
                          QUATRO_PARTES)
    (saida / 'guide.md').write_text('guia anterior')
    (saida / 'leia-me.md').write_text('leia-me anterior')
    (saida / 'interpretation.toml').write_text(
        '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
        'texto = "x"\nevidencia = ["nao/existe.py"]\n')
    # Act
    r = subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                        '--dir', str(saida)], capture_output=True, text=True)
    # Assert
    assert r.returncode == 2
    assert (saida / 'guide.md').read_text() == 'guia anterior'
    assert (saida / 'leia-me.md').read_text() == 'leia-me anterior'
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_narrativa.py -v`
Esperado: 5 failed — `leia-me.md` não existe

- [ ] **Step 3: escrever o emissor do `leia-me.md`**

```python
TITULOS = {
    'o-que-e': 'O que o produto faz',
    'percurso': 'O percurso de uma funcionalidade',
    'mapa': 'Onde ficam as coisas',
    'orientacoes': 'Para mexer',
}
ORDEM_DAS_PARTES = ('o-que-e', 'percurso', 'mapa', 'orientacoes')


def montar_leia_me(inv: dict, narrativa: list) -> str:
    """O documento humano. A ordem das partes é pedagógica: o que é → como
    funciona de ponta a ponta → onde ficam as coisas → como agir."""
    L = []
    A = L.append
    A('# Guia para quem vai mexer\n')
    escopo = inv.get('escopo') or {}
    if escopo.get('area'):
        A(f'> Cobre a área `{escopo["area"]}`, não o projeto inteiro.\n')
    A('> Documento escrito a partir do código. O relatório técnico, com a evidência')
    A('> de cada afirmação, está em [`guide.md`](guide.md).\n')

    por_parte = {}
    for b in narrativa:
        por_parte.setdefault(b['parte'], []).append(b)

    # cada parte aponta a seção do relatório técnico: é a mitigação declarada da
    # decisão "número livre na narrativa" — não impede divergir, torna descobrível
    ANCORA = {'o-que-e': 'o-que-o-sistema-faz', 'percurso': 'como-entrar',
              'mapa': 'como-entrar', 'orientacoes': 'o-que-depende-do-quê'}

    for parte in ORDEM_DAS_PARTES:
        A(f'## {TITULOS[parte]}\n')
        A(f'*Os números e a evidência estão em '
          f'[`guide.md`](guide.md#{ANCORA[parte]}).*\n')
        blocos = sorted(por_parte.get(parte, []), key=lambda b: b.get('ordem', 0))
        if not blocos:
            A('*A interpretação não escreveu esta parte.*\n')
            continue
        for b in blocos:
            A(b['texto'] + '\n')
            if b.get('trecho'):
                A(f'> {b["trecho"]}')
                A(f'> — `{b["fonte"]}`\n')
            for salto in b.get('saltos', []):
                A(f'- **Não rastreado:** {salto}')
            if b.get('saltos'):
                A('')
    return '\n'.join(L)
```

e, no `main()`, gravar os dois **só depois** de as duas montagens terem sucesso:

```python
    texto_guia = montar(inventario, afirmacoes)
    texto_leia_me = montar_leia_me(inventario, narrativa)
    (base / 'guide.md').write_text(texto_guia, encoding='utf-8')
    (base / 'leia-me.md').write_text(texto_leia_me, encoding='utf-8')
```

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q`
Esperado: todos verdes.

- [ ] **Step 5: conferir a idempotência dos dois**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_narrativa.py::test_dois_documentos_identicos_em_duas_montagens -v`
Esperado: PASSA — é a restrição verificável desta task.

---

### Task 11: o percurso, com orçamento declarado

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/SKILL.md`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_narrativa.py`

**Depende de:** Task 10

**A reversão, declarada:** o spec anterior **tirou** o caminho ponta a ponta do piso, com razão
escrita — *"atravessa middleware, container e ORM; sem TOML a seção sai sem ele, dizendo por
quê, não com um caminho pela metade"*. Aqui ele volta porque **mudou quem produz**: lá era o
script seguindo o grafo, aqui é o agente lendo arquivo. A razão original continua valendo, e por
isso vem com trava.

- [ ] **Step 1: escrever o teste que falha**

```python
# acrescentar a tests/test_narrativa.py
def test_percurso_sem_saltos_exige_o_campo_declarado(tmp_path):
    # Arrange — `saltos = []` é afirmação forte ("segui inteiro"), não omissão.
    # Sem o campo obrigatório, "não tentei" e "segui inteiro" ficam indistinguíveis.
    r, _ = com_readme(
        tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
        '[[narrativa]]\nparte = "percurso"\nordem = 1\n'
        'texto = "O pedido entra e grava"\nevidencia = ["app.py"]\n')
    # Assert
    assert r.returncode == 2
    assert 'saltos' in (r.stderr + r.stdout).lower()
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_narrativa.py -v`
Esperado: FALHA — hoje `saltos` não é obrigatório em `percurso`

- [ ] **Step 3: tornar `saltos` obrigatório em `percurso`**

```python
OBRIGATORIOS = {
    'o-que-e': ('texto', 'trecho', 'fonte', 'evidencia'),
    'percurso': ('texto', 'evidencia'),
    'mapa': ('texto', 'evidencia'),
    'orientacoes': ('texto', 'evidencia'),
}
```

passa a ter, logo abaixo da checagem de campos:

```python
        if parte == 'percurso' and 'saltos' not in b:
            raise ValueError(
                'percurso: o campo `saltos` é obrigatório, mesmo vazio — lista vazia '
                'afirma "segui do clique até o banco sem buraco", e omitir o campo '
                'deixaria "não tentei" indistinguível disso')
```

- [ ] **Step 4: escrever a regra no `SKILL.md`**

Na seção 2 (escrever a interpretação), acrescentar:

```markdown
**O percurso tem orçamento: no máximo 10 arquivos abertos.** O que não resolver vira `saltos`,
e `saltos = []` é afirmação forte — significa "segui do clique até o banco sem buraco". O campo
é obrigatório justamente para "não tentei" não se confundir com "segui inteiro".

**Só escreva o percurso com escopo recortado.** Em "o projeto todo" de um legado, rastrear é
adivinhar onde a execução começa — e a skill não detecta entrypoint.
```

- [ ] **Step 5: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q`
Esperado: todos verdes.

---

### Task 12: `SKILL.md` e o ponta a ponta

**Arquivos:**
- Alterar: `~/.claude/skills/sw-codebase-guide/SKILL.md`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_skill_md.py`

**Depende de:** Task 11

- [ ] **Step 1: escrever os testes que falham**

```python
# acrescentar a tests/test_skill_md.py
def test_documenta_a_pergunta_de_escopo():
    # Arrange
    texto = SKILL.read_text('utf-8')
    # Act / Assert
    assert '--areas' in texto
    assert '--area' in texto
    assert 'escopo' in texto.lower()


def test_documenta_os_dois_documentos():
    # Act
    texto = SKILL.read_text('utf-8')
    # Assert
    assert 'leia-me.md' in texto
    assert 'guide.md' in texto


def test_documenta_o_bloco_narrativa_e_as_guardas():
    # Act
    texto = SKILL.read_text('utf-8').lower()
    # Assert
    assert '[[narrativa]]' in texto
    assert 'trecho' in texto and 'fonte' in texto
    assert 'saltos' in texto
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_skill_md.py -v`
Esperado: 3 failed

- [ ] **Step 3: reescrever o fluxo do `SKILL.md`**

O fluxo passa a ter cinco passos, e o passo 1 é novo:

```markdown
### 1. Perguntar o escopo — com as áreas que a varredura achou

```bash
python3 <skill-dir>/scripts/varrer.py --projeto . --areas
```

Imprime as áreas em stdout e **não grava nada**. Monte o menu de `AskUserQuestion` com o que
ele devolveu — **"o projeto todo"** mais as três primeiras áreas, dizendo quantas ficaram de
fora e imprimindo a lista completa antes, para o dev achar pelo nome e usar o "Other".

O rótulo é descritivo (`funil · pasta · 7 arquivos`), **nunca semântico** (`funil · rota do App
Router`): rótulo semântico é a afirmação que a skill não consegue provar, e aqui ela decidiria
o escopo dos dois documentos.

**Esta pergunta absorve a de sub-repositórios** — é a mesma pergunta. Junte-a com a do destino
de gravação na mesma chamada.

### 2. Apurar os fatos

```bash
python3 <skill-dir>/scripts/varrer.py --projeto . --out docs/project [--area <caminho>]
```
```

E a seção "Escrever a interpretação" ganha o bloco `[[narrativa]]`, as quatro partes, os campos
obrigatórios por parte e as três guardas.

- [ ] **Step 4: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q`
Esperado: todos verdes.

- [ ] **Step 5: o ciclo completo num projeto real, com área**

```bash
cd ~/.claude/skills/sw-codebase-guide
.venv/bin/python scripts/varrer.py --projeto <projeto-real> --areas
.venv/bin/python scripts/varrer.py --projeto <projeto-real> --out /tmp/e2e --area <uma-area>
# escreva um interpretation.toml de verdade, com as quatro partes
.venv/bin/python scripts/montar.py --dir /tmp/e2e
cat /tmp/e2e/leia-me.md
```

**Leia o `leia-me.md` inteiro e julgue sem defender.** Ele responde "o que o produto é" e "onde
ficam as coisas"? Um dev que nunca viu o projeto saberia por onde começar?

Suíte verde prova que os testes rodam; só a leitura prova que o documento serve — foi assim que
os defeitos caros apareceram nas duas rodadas anteriores.

---

### Task 13: `leia-me.html` e `leia-me.pdf` — sob demanda

**Arquivos:**
- Criar: `~/.claude/skills/sw-codebase-guide/scripts/imprimir.py`
- Criar: `~/.claude/skills/sw-codebase-guide/assets/leia-me.html`
- Teste: `~/.claude/skills/sw-codebase-guide/tests/test_imprimir.py`
- Alterar: `~/.claude/skills/sw-codebase-guide/SKILL.md`

**Depende de:** Task 12

**Contrato que esta task publica:** CLI
`python3 scripts/imprimir.py --dir <docs/project>` → grava `leia-me.html` e, havendo Chromium,
`leia-me.pdf`

**Por que vem depois do `leia-me.md` e não antes:** embalar o `guide.md` de hoje seria investir
hierarquia visual num conteúdo que esta mesma versão reescreve. Um PDF bonito de um inventário
continua sendo um inventário.

**As fontes:** copie os três `.woff2` de
`~/.claude/skills/sw-infra-audit/assets/report-template/fontes/` junto com o `LICENCAS.md`, e
embuta em base64 no template. É o que faz o PDF sair offline.

- [ ] **Step 1: escrever os testes que falham**

```python
# tests/test_imprimir.py
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent


def preparar(tmp_path, markdown='# Guia\n\n## O que o produto faz\n\nUm sistema de pedidos.\n'):
    (tmp_path / 'leia-me.md').write_text(markdown)
    return tmp_path


def imprimir(dir_saida, env=None):
    return subprocess.run(
        [sys.executable, str(RAIZ_SKILL / 'scripts' / 'imprimir.py'), '--dir', str(dir_saida)],
        capture_output=True, text=True, env=env)


def test_gera_o_html_a_partir_do_markdown(tmp_path):
    # Arrange
    preparar(tmp_path)
    # Act
    r = imprimir(tmp_path)
    # Assert
    assert r.returncode == 0, r.stderr
    html = (tmp_path / 'leia-me.html').read_text()
    assert 'Um sistema de pedidos' in html
    assert '<h2' in html and 'O que o produto faz' in html


def test_html_e_self_contained(tmp_path):
    # Arrange — o PDF é gerado offline; nada pode vir da rede
    preparar(tmp_path)
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert 'base64' in html, 'as fontes precisam estar embutidas'
    for proibido in ('https://fonts.', 'cdn.', '<script src="http'):
        assert proibido not in html, proibido


def test_tem_a_mecanica_de_impressao(tmp_path):
    # Arrange
    preparar(tmp_path)
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert — sem isto a quebra de página corta bloco no meio e a cor some na impressão
    assert '@page' in html
    assert 'print-color-adjust' in html
    assert 'break-inside' in html


def test_sem_chromium_entrega_o_html_e_avisa(tmp_path, monkeypatch):
    # Arrange — não achar navegador não é falha da skill
    preparar(tmp_path)
    import os
    env = dict(os.environ, PATH='/nao/existe')
    # Act
    r = imprimir(tmp_path, env=env)
    # Assert
    assert r.returncode == 0, 'sem Chromium o processo termina com SUCESSO'
    assert (tmp_path / 'leia-me.html').exists()
    assert not (tmp_path / 'leia-me.pdf').exists()
    assert 'chrom' in (r.stdout + r.stderr).lower()


def test_sem_leia_me_md_para_com_motivo(tmp_path):
    # Act
    r = imprimir(tmp_path)
    # Assert
    assert r.returncode == 2
    assert 'leia-me.md' in (r.stdout + r.stderr)
    assert 'Traceback' not in r.stderr
```

- [ ] **Step 2: rodar e confirmar que falha**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_imprimir.py -v`
Esperado: FALHA — `imprimir.py` não existe (`returncode != 0`)

- [ ] **Step 3: escrever o template `assets/leia-me.html`**

Um arquivo só, com `%%TITULO%%` e `%%CORPO%%` como marcadores, as três fontes em base64, e a
mecânica de impressão. O miolo do `<style>`:

```python
# o executor escreve o template; este bloco documenta o que ele PRECISA conter,
# e é o que os testes do step 1 verificam
ESSENCIAL = """
@font-face { font-family: Figtree; src: url(data:font/woff2;base64,...) format('woff2'); }
@page { size: A4; margin: 18mm 16mm; }
@media print { body { print-color-adjust: exact; -webkit-print-color-adjust: exact; } }
h2, h3 { break-after: avoid; }
blockquote, pre, table { break-inside: avoid; }
"""
```

> As fontes vêm de `sw-infra-audit/assets/report-template/fontes/`, com o `LICENCAS.md` junto.
> A casa usa um plugin por skill, então não há como compartilhar — copiar é o caminho, com a
> origem citada em comentário no topo do template.

- [ ] **Step 4: escrever o `imprimir.py`**

```python
#!/usr/bin/env python3
"""Transforma o `leia-me.md` em HTML legível e, havendo Chromium, em PDF.

Markdown versiona bem e lê mal de ponta a ponta: não dá hierarquia visual, índice
nem quebra de página. Esta skill existe para quem acabou de receber um projeto — a
conversa seguinte é com alguém, e Markdown não se manda nem se imprime.

Self-contained de propósito: fontes em base64, zero rede. O PDF é gerado offline.
A mecânica de impressão (`@page`, `print-color-adjust`, `break-inside`) vem da
`sw-infra-audit`, que já resolveu o mesmo problema.

Sem Chromium na máquina, entrega o HTML e avisa — não é falha da skill.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

CHROMIUM = ('google-chrome', 'google-chrome-stable', 'chromium',
            'chromium-browser', 'chrome')


def achar_chromium():
    for nome in CHROMIUM:
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    return None


def markdown_para_html(texto: str) -> str:
    """Conversão suficiente para o que o `montar.py` gera — não é um parser geral.

    O `leia-me.md` é escrito por nós, com um subconjunto conhecido: título, lista,
    citação, código inline e negrito. Trazer uma biblioteca de Markdown violaria a
    restrição de só-stdlib, e um parser geral resolveria um problema que não temos.
    """
    saida, em_lista = [], False
    for linha in texto.split('\n'):
        if linha.startswith('> '):
            saida.append(f'<blockquote>{_inline(linha[2:])}</blockquote>')
            continue
        if linha.startswith('- '):
            if not em_lista:
                saida.append('<ul>')
                em_lista = True
            saida.append(f'<li>{_inline(linha[2:])}</li>')
            continue
        if em_lista:
            saida.append('</ul>')
            em_lista = False
        if linha.startswith('#'):
            nivel = len(linha) - len(linha.lstrip('#'))
            saida.append(f'<h{nivel}>{_inline(linha[nivel:].strip())}</h{nivel}>')
        elif linha.strip():
            saida.append(f'<p>{_inline(linha)}</p>')
    if em_lista:
        saida.append('</ul>')
    return '\n'.join(saida)


def _inline(t: str) -> str:
    t = (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', t)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)


def main() -> int:
    p = argparse.ArgumentParser(description='Gera o leia-me em HTML e PDF.')
    p.add_argument('--dir', required=True)
    args = p.parse_args()

    base = Path(args.dir).resolve()
    origem = base / 'leia-me.md'
    if not origem.exists():
        print(f'não achei {origem} — rode montar.py antes', file=sys.stderr)
        return 2

    modelo = (Path(__file__).resolve().parent.parent / 'assets' / 'leia-me.html').read_text()
    corpo = markdown_para_html(origem.read_text('utf-8'))
    destino = base / 'leia-me.html'
    destino.write_text(modelo.replace('%%TITULO%%', 'Guia do projeto')
                             .replace('%%CORPO%%', corpo), encoding='utf-8')
    print(destino)

    navegador = achar_chromium()
    if not navegador:
        print('sem Chromium na máquina: o PDF não foi gerado, o HTML está pronto '
              'e abre em qualquer navegador')
        return 0

    pdf = base / 'leia-me.pdf'
    subprocess.run([navegador, '--headless', '--disable-gpu', '--no-sandbox',
                    f'--print-to-pdf={pdf}', '--no-pdf-header-footer',
                    destino.as_uri()],
                   capture_output=True, timeout=120)
    if pdf.exists():
        print(pdf)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 5: rodar e confirmar que passa**

Rode: `cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/test_imprimir.py -v`
Esperado: 5 passed

As duas restrições verificáveis desta task são `test_sem_chromium_entrega_o_html_e_avisa` e
`test_html_e_self_contained`.

- [ ] **Step 6: prova por mutação na queda graciosa**

Troque `if not navegador:` por `if False:` e rode com `PATH` vazio.
Esperado: `test_sem_chromium_entrega_o_html_e_avisa` **FALHA** (o processo quebra em vez de
terminar com sucesso). Desfaça e confirme o verde.

- [ ] **Step 7: escrever a oferta no `SKILL.md`, no passo 4**

```markdown
### 5. Oferecer o HTML e o PDF — no fim, não antes

Com o documento pronto e as perguntas em aberto lidas, **ofereça via `AskUserQuestion`**:
*"Gerar também o HTML e o PDF do leia-me?"*

```bash
python3 <skill-dir>/scripts/imprimir.py --dir docs/project
```

O PDF custa alguns segundos de Chromium, e nem toda rodada vira documento para enviar —
perguntar no começo gasta a atenção de quem só queria entender o projeto. Sem Chromium na
máquina, diga isso e entregue o HTML: não é falha da skill.
```

- [ ] **Step 8: gerar o PDF de um projeto real e ABRIR**

```bash
cd ~/.claude/skills/sw-codebase-guide
.venv/bin/python scripts/imprimir.py --dir /tmp/e2e
```

**Abra o PDF e olhe.** A quebra de página corta bloco no meio? O índice ajuda? Dá para mandar
para alguém sem vergonha? Suíte verde prova que o arquivo foi gerado, não que ele serve — e
nesta skill a leitura da saída achou mais defeito que todos os testes somados.

---

### Task 14: publicar a v0.2.0

**Arquivos:**
- Alterar: `/var/www/ai-marketplace/CHANGELOG.md`
- Alterar: `~/.claude/skills/sw-codebase-guide/SKILL.md` (a linha da pergunta absorvida)

**Depende de:** Task 12

**Por que é task e não "detalhe do fim":** o `CLAUDE.md` do repositório torna o `CHANGELOG.md` e
o `make check` **obrigatórios** antes de commitar, e o spec declara o rollout. Sem task, isso
fica a cargo de alguém lembrar.

- [ ] **Step 1: tirar do `SKILL.md` a pergunta que foi absorvida**

A tabela de perguntas tem hoje a linha *"A varredura achou sub-repositórios | documentar o
conjunto, ou só um deles"*. O spec diz que a pergunta de escopo **a absorve** — é literalmente
a mesma pergunta. Deixar as duas faz a skill perguntar duas vezes a mesma coisa num terço dos
projetos.

- [ ] **Step 2: acertar o comentário-invariante do `varrer.py`**

O arquivo diz hoje: *"a proteção acontece na ORIGEM: o inventário só carrega caminho, contagem
e nome de chave, nunca conteúdo"*. Com a seção `textos` isso virou falso. Reescreva declarando
a exceção e a trava:

```python
    # A proteção acontece na ORIGEM: o inventário carrega caminho, contagem e nome
    # de chave. A exceção é `textos`, que carrega conteúdo porque a conferência de
    # trecho literal depende dele — e por isso ele passa por redação LINHA A LINHA
    # antes de entrar, com teto de 64 KB.
```

- [ ] **Step 3: rodar a suíte inteira e o ciclo completo**

```bash
cd ~/.claude/skills/sw-codebase-guide && .venv/bin/pytest tests/ -q
```
Esperado: todos verdes, incluindo os 92 de v0.1.0.

- [ ] **Step 4: sincronizar com bump de minor**

```bash
cd /var/www/ai-marketplace && make sync SKILL=sw-codebase-guide BUMP=minor
```
Esperado: `versão: 0.2.0`, e `marketplace.json`/`README.md` atualizados pelo próprio script.

- [ ] **Step 5: escrever a entrada no `CHANGELOG.md`**

Em `## [Não publicado]`, sob `### Alterado`:

```markdown
- `sw-codebase-guide` (v0.2.0): **o guia virou dois documentos, e a pergunta de escopo virou a
  porta de entrada.** A v0.1.0 produzia um inventário — dizia "103 menções" e "630 arquivos",
  não dizia o que o produto era nem onde o dev mexe. Agora sai também um `leia-me.md` em quatro
  partes, na ordem em que se aprende uma base de código: o que o produto faz · o percurso de uma
  funcionalidade, com os saltos que não deram para rastrear declarados · onde ficam as coisas ·
  para mexer em X você vai em Y.

  **O escopo é escolhido antes de varrer.** Uma fase barata lista as áreas do projeto — por
  agrupamento de diretórios, com rótulo descritivo (`funil · pasta · 7 arquivos`) e nunca
  semântico, porque rótulo semântico é a afirmação que a skill não consegue provar — e o menu
  sai preenchido com elas. O dev não precisa saber o nome da área antes de começar.

  **Três guardas novas, e o que cada uma não pega.** O trecho literal citado é conferido contra
  a fonte, porque a pior falha da parte "o que o produto faz" não é mentira — é ser fluente,
  verdadeira e inútil. Toda evidência é conferida contra o projeto, em quatro formas
  (`arquivo`, `arquivo:linha`, `diretório/`, `commit abc`). E a proibição de afirmar ausência
  de dependentes passou a valer na recusa do parser, não só no teste de saída, porque o texto
  livre do agente é muito mais propenso a escrever "isso não é usado em lugar nenhum". Nenhuma
  delas pega prosa que cita arquivo real e diz algo falso sobre ele — para isso existem as
  perguntas em aberto.

  O recorte por área preserva de propósito o que **cruza a fronteira**: o valor de "para mexer
  no funil você quase sempre mexe no componente" vem justamente do par com uma ponta de fora, e
  o documento marca qual é.
```

- [ ] **Step 6: rodar o gate de segurança DEPOIS de preparar o commit**

```bash
cd /var/www/ai-marketplace && git add -A && make check
```
Esperado: `✓ gate de segurança: nada sensível detectado`.

**A ordem importa:** o gate escaneia o conteúdo **staged**. Rodá-lo antes do `git add` já
deixou passar um nome real de projeto nesta mesma sessão — ele viu um índice vazio e aprovou.

---

## Ajustes durante a execução

<!-- registre aqui o que divergiu do plano, com data -->
