"""A conferência da interpretação.

O `build.py` recusa o que é binário: afirmação sem evidência, lacuna sem motivo,
citação que não existe. O que sobra é julgamento, e recusar por julgamento vira
burocracia — então a conferência lista e quem escreveu decide.

O desenho veio de cinco rodadas de medição contra as três interpretações reais que
existem em disco, escritas por agente contra projeto real. Os testes abaixo guardam
as quatro decisões que a medição tomou CONTRA a expectativa, porque é por elas que
uma versão futura vai querer "simplificar":

- evidência genérica (só pasta, só arquivo sem linha) **não** é defeito: aponta 12
  itens nas três interpretações e quase todos estão certos;
- pasta citada endereça o arquivo, mas só até um tamanho — `backend/` cobre 430
  arquivos e não é endereço de nada;
- classificar a linha citada por sintaxe não serve: comentário é a melhor evidência
  que existe quando o arquivo é um `CLAUDE.md` com os comandos de subida;
- a saída da própria skill aparece como evidência, e o `build.py` aceita, porque o
  arquivo existe mesmo.
"""
import json
import subprocess
import sys
from pathlib import Path

from lib import review

RAIZ_SKILL = Path(__file__).resolve().parent.parent

# A resolução que faz `judge.linguagens_confiaveis` passar do piso: sem ela todo
# inventário de teste cai em "não pôde medir", e o teste verde não prova nada.
RESOLVIDO = {'relativos': 10, 'sufixo_unico': 0, 'base_provada': 0,
             'config_conferida': 0, 'ambiguos': 0, 'pendurados': 0,
             'nao_resolvidos': 0}


def inv(**campos) -> dict:
    """Um inventário mínimo que cumpre os pré-requisitos de todas as conferências."""
    base = {
        'gerado_em_versao': 1,
        'projeto': 'loja',
        'arvore': [],
        'caminhos_do_projeto': ['app/pedido.py', 'app/fatura.py', 'rotas.py'],
        'linhas_por_arquivo': {},
        'mudanca_por_arquivo': {'app/pedido.py': '2026-01-01'},
        'imports': {'arestas': [{'de': 'rotas.py', 'para': 'app/pedido.py'}],
                    'resolucao': {'python': dict(RESOLVIDO)}},
        'julgamento': {'perigo': [], 'sem_alcance': []},
        'textos': {},
    }
    base.update(campos)
    return base


def afirmacao(secao='o-que-faz', texto='Pedido fecha com pagamento',
              nivel='fato', evidencia=('app/pedido.py:1',), **extra) -> dict:
    return {'secao': secao, 'texto': texto, 'nivel': nivel,
            'evidencia': list(evidencia), 'motivo': '', **extra}


def bloco(parte='mapa', texto='A regra mora em app/',
          evidencia=('app/pedido.py:1',), **extra) -> dict:
    """A evidência padrão é um ARQUIVO, nunca uma pasta.

    Com `app/` por padrão, a fixture endereçava todo arquivo do projeto de teste
    por acidente — e quatro testes de cobrança passavam verde provando o oposto
    do que diziam.
    """
    return {'parte': parte, 'texto': texto, 'evidencia': list(evidencia), **extra}


def completa() -> dict:
    """Uma interpretação sem nada a apontar: as quatro seções, as quatro partes,
    percurso que atravessa camada."""
    return {
        'afirmacao': [afirmacao(secao=s) for s in review.SECOES],
        'narrativa': [
            bloco('o-que-e'), bloco('mapa'), bloco('orientacoes'),
            bloco('percurso', onde='navegador', ordem=1),
            bloco('percurso', onde='servidor', ordem=2),
        ],
    }


def achado(r: dict, chave: str) -> dict | None:
    return next((a for a in r['achados'] if a['chave'] == chave), None)


def nao_conferido(r: dict, chave: str) -> dict | None:
    return next((n for n in r['nao_conferido'] if n['chave'] == chave), None)


def perigo(*caminhos) -> list:
    return [{'caminho': c, 'dependentes': 9, 'mudancas': 12} for c in caminhos]


def test_interpretacao_completa_nao_tem_nada_a_apontar():
    # Act
    r = review.conferir(inv(), completa())
    # Assert
    assert r['achados'] == []


def test_a_contagem_sai_para_o_cabecalho():
    # Act
    r = review.conferir(inv(), completa())
    # Assert
    assert r['contagem'] == {'afirmacoes': 4, 'blocos': 5, 'citacoes': 9}


# ───────────────── evidência que aponta a saída da própria skill ─────────────────


def test_evidencia_que_aponta_o_inventario_e_achado():
    """Medido numa das três interpretações reais: uma afirmação sobre o projeto
    citava `docs/project/inventory.json`. O leitor é mandado conferir um arquivo
    que a skill escreveu — e a guarda do `build.py` aceita, porque ele existe."""
    # Arrange
    dados = completa()
    dados['afirmacao'].append(
        afirmacao(texto='Search e registro mudam juntas',
                  evidencia=['docs/project/inventory.json']))
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    a = achado(r, 'saida-da-skill')
    assert a and 'docs/project/inventory.json' in a['itens'][0]


def test_o_conhecimento_humano_tambem_e_saida_da_skill():
    # Arrange
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['docs/project/knowledge.toml']))
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    assert achado(r, 'saida-da-skill')


def test_o_readme_do_projeto_nao_e_saida_da_skill():
    """A aresta errada é pior que a faltando: `readme.md` e `guide.md` existem em
    projeto real, e acusá-los ensinaria a ignorar a conferência."""
    # Arrange
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['readme.md:3', 'docs/guide.md']))
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    assert achado(r, 'saida-da-skill') is None


# ────────────────────── a linha citada tem conteúdo? ──────────────────────


def projeto_com(tmp_path, arquivo: str, conteudo: str) -> Path:
    alvo = tmp_path / 'projeto' / arquivo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding='utf-8')
    return tmp_path / 'projeto'


def test_linha_em_branco_citada_e_achado(tmp_path):
    """O achado do agente limpo da v0.13.0, que a guarda do `build.py` não pega:
    ela confere o INTERVALO, e a linha 2 existe."""
    # Arrange
    raiz = projeto_com(tmp_path, 'app/pedido.py', 'class Pedido:\n\n    pass\n')
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['app/pedido.py:2']))
    # Act
    r = review.conferir(inv(), dados, projeto=raiz)
    # Assert
    a = achado(r, 'linha-sem-conteudo')
    assert a and 'app/pedido.py:2' in a['itens'][0]


def test_cerca_de_bloco_citada_e_achado(tmp_path):
    """Medido: `README.md:12` apontando ` ```bash `, para sustentar a sequência de
    subida que começa na linha seguinte."""
    # Arrange
    raiz = projeto_com(tmp_path, 'README.md', '# Loja\n\n```bash\nnpm ci\n```\n')
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['README.md:3']))
    # Act
    r = review.conferir(inv(), dados, projeto=raiz)
    # Assert
    assert achado(r, 'linha-sem-conteudo')


def test_comentario_que_diz_o_comando_nao_e_achado(tmp_path):
    """A classificação por sintaxe recusaria esta, e ela é a melhor evidência que
    existe: num projeto real medido, os comandos de subida só estão escritos em
    comentário dentro de um `CLAUDE.md`."""
    # Arrange
    raiz = projeto_com(tmp_path, 'CLAUDE.md',
                       'npm run dev    # sobe em localhost:8081\n')
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['CLAUDE.md:1']))
    # Act
    r = review.conferir(inv(), dados, projeto=raiz)
    # Assert
    assert achado(r, 'linha-sem-conteudo') is None


def test_sem_projeto_a_linha_fica_como_nao_conferida(tmp_path):
    """"Não conferido" não é achado: misturar os dois faria "não apurado" contar
    como "está certo"."""
    # Arrange
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['app/pedido.py:2']))
    # Act
    r = review.conferir(inv(), dados, projeto=None)
    # Assert
    assert achado(r, 'linha-sem-conteudo') is None
    assert 'projeto' in nao_conferido(r, 'linha-sem-conteudo')['motivo']


def test_linha_fora_do_intervalo_fica_para_a_recusa_do_build(tmp_path):
    """Duas vozes sobre o mesmo defeito mandam consertar duas vezes."""
    # Arrange
    raiz = projeto_com(tmp_path, 'app/pedido.py', 'class Pedido:\n')
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['app/pedido.py:900']))
    # Act
    r = review.conferir(inv(), dados, projeto=raiz)
    # Assert
    assert achado(r, 'linha-sem-conteudo') is None


def test_arquivo_que_nao_abre_nao_derruba_a_conferencia(tmp_path):
    # Arrange
    raiz = projeto_com(tmp_path, 'app/pedido.py', 'x = 1\n')
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['app/sumiu.py:3']))
    # Act
    r = review.conferir(inv(), dados, projeto=raiz)
    # Assert
    assert achado(r, 'linha-sem-conteudo') is None


def test_o_texto_cortado_termina_em_reticencia(tmp_path):
    """Sem a reticência o corte MENTE: o item do relatório é lido como citação do
    que o agente escreveu, e `"copiar .env."` parecia o fim da frase."""
    # Arrange
    longo = ('Sequência para subir local: npm ci, copiar .env.example para .env, '
             'db:up, db:migrar, dev')
    dados = completa()
    dados['afirmacao'].append(
        afirmacao(texto=longo, evidencia=['docs/project/inventory.json']))
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    assert achado(r, 'saida-da-skill')['itens'][0].endswith('…"')


# ───────────────────────── seção e parte vazias ─────────────────────────


def test_secao_sem_afirmacao_e_achado():
    # Arrange
    dados = completa()
    dados['afirmacao'] = [a for a in dados['afirmacao']
                          if a['secao'] != 'depende-de']
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    a = achado(r, 'secoes-vazias')
    assert a and a['itens'] == ['`depende-de`']


def test_sem_afirmacao_nenhuma_a_cobranca_e_uma_linha_so():
    """Quatro linhas dizendo "seção vazia" para uma interpretação que não existe
    é relatório que esconde o problema de verdade."""
    # Arrange
    dados = completa()
    dados['afirmacao'] = []
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    assert len(achado(r, 'secoes-vazias')['itens']) == 1


def test_parte_da_narrativa_ausente_e_achado():
    """Medido: a interpretação de um projeto real inteiro não tinha percurso
    nenhum, e "O percurso de uma funcionalidade" saía vazia no documento."""
    # Arrange
    dados = completa()
    dados['narrativa'] = [b for b in dados['narrativa'] if b['parte'] != 'percurso']
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    a = achado(r, 'partes-vazias')
    assert a and 'percurso' in a['itens'][0]


def test_sem_narrativa_nenhuma_a_cobranca_e_uma_linha_so():
    # Arrange
    dados = completa()
    dados['narrativa'] = []
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    assert len(achado(r, 'partes-vazias')['itens']) == 1


# ───────────────────────── o percurso atravessa? ─────────────────────────


def test_percurso_todo_na_mesma_camada_e_achado():
    # Arrange
    dados = completa()
    dados['narrativa'] = [b for b in dados['narrativa'] if b['parte'] != 'percurso']
    dados['narrativa'] += [bloco('percurso', onde='servidor', ordem=1),
                           bloco('percurso', onde='servidor', ordem=2),
                           bloco('percurso', onde='servidor', ordem=3)]
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    a = achado(r, 'percurso-plano')
    assert a and 'servidor' in a['itens'][0]


def test_percurso_que_atravessa_nao_e_achado():
    # Act
    r = review.conferir(inv(), completa())
    # Assert
    assert achado(r, 'percurso-plano') is None


def test_passo_sem_camada_fica_para_a_recusa_do_build():
    """Rodando no material real isto imprimia «4 passos, todos em `?`» embaixo da
    recusa dura — diagnóstico inventado sobre um defeito que já estava dito."""
    # Arrange
    dados = completa()
    dados['narrativa'] = [b for b in dados['narrativa'] if b['parte'] != 'percurso']
    dados['narrativa'] += [bloco('percurso', ordem=1), bloco('percurso', ordem=2)]
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    assert achado(r, 'percurso-plano') is None


def test_um_passo_so_nao_e_percurso_plano():
    # Arrange
    dados = completa()
    dados['narrativa'] = [b for b in dados['narrativa'] if b['parte'] != 'percurso']
    dados['narrativa'].append(bloco('percurso', onde='servidor', ordem=1))
    # Act
    r = review.conferir(inv(), dados)
    # Assert
    assert achado(r, 'percurso-plano') is None


# ───────────────────── o que o inventário destacou ─────────────────────


def test_arquivo_perigoso_sem_citacao_e_achado():
    # Arrange
    i = inv(julgamento={'perigo': perigo('app/fatura.py'), 'sem_alcance': []})
    # Act
    r = review.conferir(i, completa())
    # Assert
    a = achado(r, 'perigo')
    assert a and 'app/fatura.py' in a['itens'][0] and '9 dependentes' in a['itens'][0]


def test_arquivo_perigoso_citado_direto_nao_e_achado():
    # Arrange
    i = inv(julgamento={'perigo': perigo('app/pedido.py'), 'sem_alcance': []})
    # Act
    r = review.conferir(i, completa())
    # Assert
    assert achado(r, 'perigo') is None


def test_pasta_pequena_citada_endereca_o_arquivo():
    """Mandar o leitor para uma pasta de 8 arquivos é dizer onde o arquivo está.
    Medido: era assim que o arquivo mais importado de um projeto real estava
    endereçado, sem ter sido citado uma vez."""
    # Arrange
    universo = [f'src/identity/a{n}.ts' for n in range(8)] + ['outro.ts']
    i = inv(caminhos_do_projeto=universo,
            julgamento={'perigo': perigo('src/identity/a3.ts'), 'sem_alcance': []})
    dados = completa()
    dados['narrativa'].append(bloco('mapa', evidencia=['src/identity/']))
    # Act
    r = review.conferir(i, dados)
    # Assert
    assert achado(r, 'perigo') is None


def test_pasta_grande_citada_nao_endereca_o_arquivo():
    """Medido no monorepo real: `backend/` cobre 430 arquivos (41% do projeto) e
    `backend/app/Dominio/` cobre 135. Contar isso como citação zerava a lacuna
    exatamente onde ela é verdadeira."""
    # Arrange
    universo = [f'backend/app/a{n}.php' for n in range(400)]
    i = inv(caminhos_do_projeto=universo,
            julgamento={'perigo': perigo('backend/app/a7.php'), 'sem_alcance': []})
    dados = completa()
    dados['narrativa'].append(bloco('mapa', evidencia=['backend/']))
    # Act
    r = review.conferir(i, dados, teto_da_pasta=30)
    # Assert
    assert achado(r, 'perigo')


def test_o_teto_padrao_da_pasta_segura_a_pasta_de_um_monorepo_real():
    """Dimensionado pelo mundo, não pela constante: um teste que mede a fixture
    por `review.TETO_DA_PASTA` para de provar que o PADRÃO serve — foi o que
    deixou duas mutações escaparem na rodada anterior."""
    # Arrange
    universo = [f'backend/app/Dominio/a{n}.php' for n in range(135)]
    i = inv(caminhos_do_projeto=universo,
            julgamento={'perigo': perigo('backend/app/Dominio/a7.php'),
                        'sem_alcance': []})
    dados = completa()
    dados['narrativa'].append(bloco('mapa', evidencia=['backend/app/Dominio/']))
    # Act
    r = review.conferir(i, dados)
    # Assert
    assert achado(r, 'perigo')


def test_perigo_vazio_com_grafo_e_git_nao_vira_queixa():
    """Mediu e não achou: num projeto real de três semanas de vida o perigo sai
    vazio porque nada mudou vezes suficientes. Isso não é lacuna."""
    # Act
    r = review.conferir(inv(), completa())
    # Assert
    assert achado(r, 'perigo') is None and nao_conferido(r, 'perigo') is None


def test_perigo_vazio_sem_git_vira_nao_conferido_com_motivo():
    # Arrange
    i = inv(mudanca_por_arquivo={})
    # Act
    r = review.conferir(i, completa())
    # Assert
    assert 'histórico' in nao_conferido(r, 'perigo')['motivo']


def test_lista_longa_e_cortada_e_diz_quantos_sobraram():
    # Arrange
    i = inv(julgamento={'perigo': perigo(*[f'app/m{n}.py' for n in range(40)]),
                        'sem_alcance': []})
    # Act
    r = review.conferir(i, completa())
    # Assert
    itens = achado(r, 'perigo')['itens']
    assert len(itens) == review.TETO_DE_ITENS + 1
    assert itens[-1] == f'… e mais {40 - review.TETO_DE_ITENS}'


# ───────────────────────── o centro do grafo ─────────────────────────


def centro_inv(**campos) -> dict:
    """Um inventário em que `app/fatura.py` é o arquivo mais importado."""
    arestas = [{'de': f'app/c{n}.py', 'para': 'app/fatura.py'} for n in range(6)]
    arestas += [{'de': 'rotas.py', 'para': 'app/pedido.py'}]
    base = {'caminhos_do_projeto': [a['de'] for a in arestas]
            + ['app/fatura.py', 'app/pedido.py'],
            'imports': {'arestas': arestas,
                        'resolucao': {'python': dict(RESOLVIDO)}}}
    base.update(campos)
    return inv(**base)


def test_centro_do_grafo_sem_citacao_e_achado():
    """Medido: o arquivo mais importado de um projeto real — 46 dependentes — não
    aparecia em citação nenhuma, nem por pasta."""
    # Act
    r = review.conferir(centro_inv(), completa())
    # Assert
    a = achado(r, 'centro')
    assert a and 'app/fatura.py' in a['itens'][0] and '6 dependentes' in a['itens'][0]


def test_centro_citado_nao_e_achado():
    # Arrange
    dados = completa()
    dados['afirmacao'].append(afirmacao(evidencia=['app/fatura.py:10']))
    # Act
    r = review.conferir(centro_inv(), dados)
    # Assert
    assert achado(r, 'centro') is None


def test_arquivo_de_teste_nao_entra_no_centro():
    """Medido: o segundo arquivo mais importado de um projeto real era um helper
    de teste. Cobrar uma frase sobre helper de teste é a bronca que ensina a
    ignorar a ferramenta."""
    # Arrange
    arestas = [{'de': f'app/c{n}.py', 'para': 'tests/helpers/db.py'}
               for n in range(9)]
    arestas += [{'de': 'rotas.py', 'para': 'app/pedido.py'}]
    i = inv(imports={'arestas': arestas, 'resolucao': {'python': dict(RESOLVIDO)}})
    # Act
    r = review.conferir(i, completa())
    # Assert
    assert achado(r, 'centro') is None


def test_o_centro_nao_cobra_quem_o_perigo_ja_cobrou():
    """O arquivo mais importado costuma SER o mais perigoso, e duas linhas sobre o
    mesmo arquivo, cada uma com um número diferente, leem como dois problemas."""
    # Arrange
    i = centro_inv(julgamento={'perigo': perigo('app/fatura.py'),
                               'sem_alcance': []})
    # Act
    r = review.conferir(i, completa())
    # Assert
    assert achado(r, 'perigo')
    assert achado(r, 'centro') is None


def test_sem_grafo_confiavel_o_centro_nao_e_conferido():
    # Arrange
    i = inv(imports={'arestas': [], 'resolucao': {}})
    # Act
    r = review.conferir(i, completa())
    # Assert
    assert achado(r, 'centro') is None
    assert 'confiável' in nao_conferido(r, 'centro')['motivo']


def test_resolucao_abaixo_do_piso_nao_vira_centro():
    """Ranking sobre metade do grafo tem cara de fato — é o erro que a v0.1.1
    custou, e a conferência não pode reintroduzi-lo por uma porta nova."""
    # Arrange
    fraca = {**RESOLVIDO, 'nao_resolvidos': 30}
    i = centro_inv(imports={'arestas': [{'de': 'a.py', 'para': 'app/fatura.py'}],
                            'resolucao': {'python': fraca}})
    # Act
    r = review.conferir(i, completa())
    # Assert
    assert achado(r, 'centro') is None


# ───────────────────────── o script, de ponta a ponta ─────────────────────────


def rodar(saida, projeto=None):
    cmd = [sys.executable, str(RAIZ_SKILL / 'scripts' / 'check.py'),
           '--dir', str(saida)]
    if projeto:
        cmd += ['--projeto', str(projeto)]
    return subprocess.run(cmd, capture_output=True, text=True)


def escrever(saida: Path, inventario: dict, toml: str) -> Path:
    saida.mkdir(parents=True, exist_ok=True)
    (saida / 'inventory.json').write_text(json.dumps(inventario), encoding='utf-8')
    (saida / 'interpretation.toml').write_text(toml, encoding='utf-8')
    return saida


COMPLETO = '''
[[afirmacao]]
secao = "como-entrar"
texto = "Sobe com docker compose up"
nivel = "fato"
evidencia = ["app/pedido.py:1"]

[[afirmacao]]
secao = "depende-de"
texto = "As rotas chamam o pedido"
nivel = "fato"
evidencia = ["app/pedido.py:1"]

[[afirmacao]]
secao = "o-que-faz"
texto = "Fecha pedido com pagamento"
nivel = "fato"
evidencia = ["app/pedido.py:1"]

[[afirmacao]]
secao = "superficie"
texto = "Uma rota de listagem"
nivel = "fato"
evidencia = ["rotas.py:1"]

[[narrativa]]
parte = "o-que-e"
texto = "Uma loja"
evidencia = ["app/pedido.py:1"]
trecho = "Loja de peças"
fonte = "README.md"

[[narrativa]]
parte = "mapa"
texto = "A regra mora em app/"
evidencia = ["app/pedido.py:1"]

[[narrativa]]
parte = "orientacoes"
texto = "Leia o pedido antes"
evidencia = ["app/pedido.py:1"]

[[narrativa]]
parte = "percurso"
ordem = 1
onde = "navegador"
texto = "O clique chama a rota"
evidencia = ["rotas.py:1"]
saltos = []

[[narrativa]]
parte = "percurso"
ordem = 2
onde = "servidor"
texto = "A rota chama o pedido"
evidencia = ["app/pedido.py:1"]
saltos = []
'''


def inv_do_script() -> dict:
    return inv(linhas_por_arquivo={'app/pedido.py': 20, 'rotas.py': 5},
               textos={'README.md': {'conteudo': 'Loja de peças de carro'}})


def test_interpretacao_sem_queixa_sai_zero(tmp_path):
    # Arrange
    saida = escrever(tmp_path / 'out', inv_do_script(), COMPLETO)
    # Act
    r = rodar(saida)
    # Assert
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'Nada a apontar' in r.stdout


def test_interpretacao_com_queixa_sai_um(tmp_path):
    # Arrange
    i = inv_do_script()
    i['julgamento'] = {'perigo': perigo('app/fatura.py'), 'sem_alcance': []}
    saida = escrever(tmp_path / 'out', i, COMPLETO)
    # Act
    r = rodar(saida)
    # Assert
    assert r.returncode == 1
    assert 'app/fatura.py' in r.stdout


def test_a_recusa_do_build_vem_com_a_mensagem_dele(tmp_path):
    """A mesma função que recusa, nunca uma cópia: duas listas divergiriam na
    primeira regra nova."""
    # Arrange
    ruim = COMPLETO.replace('texto = "As rotas chamam o pedido"\nnivel = "fato"\n'
                            'evidencia = ["app/pedido.py:1"]',
                            'texto = "As rotas chamam o pedido"\nnivel = "fato"\n'
                            'evidencia = []')
    saida = escrever(tmp_path / 'out', inv_do_script(), ruim)
    # Act
    r = rodar(saida)
    # Assert
    assert r.returncode == 1
    assert 'O BUILD VAI RECUSAR' in r.stdout
    assert 'afirmacao sem evidencia' in r.stdout


def test_a_conferencia_nao_escreve_nada(tmp_path):
    """Ela roda entre a interpretação e o documento, e não é escritora da skill."""
    # Arrange
    saida = escrever(tmp_path / 'out', inv_do_script(), COMPLETO)
    antes = {p.name: p.read_bytes() for p in saida.iterdir()}
    # Act
    rodar(saida)
    # Assert
    assert {p.name: p.read_bytes() for p in saida.iterdir()} == antes


def test_sem_inventario_sai_dois(tmp_path):
    # Act
    r = rodar(tmp_path / 'vazio')
    # Assert
    assert r.returncode == 2 and 'scan.py' in r.stderr


def test_sem_interpretacao_sai_dois(tmp_path):
    # Arrange
    saida = tmp_path / 'out'
    saida.mkdir()
    (saida / 'inventory.json').write_text(json.dumps(inv()), encoding='utf-8')
    # Act
    r = rodar(saida)
    # Assert
    assert r.returncode == 2 and 'interpretação' in r.stderr


def test_toml_quebrado_sai_dois(tmp_path):
    # Arrange
    saida = escrever(tmp_path / 'out', inv_do_script(), '[[afirmacao]\nsecao = ')
    # Act
    r = rodar(saida)
    # Assert
    assert r.returncode == 2 and 'TOML' in r.stderr


def test_projeto_que_nao_e_diretorio_sai_dois(tmp_path):
    # Arrange
    saida = escrever(tmp_path / 'out', inv_do_script(), COMPLETO)
    # Act
    r = rodar(saida, projeto=saida / 'inventory.json')
    # Assert
    assert r.returncode == 2


def test_com_projeto_a_linha_sem_conteudo_aparece(tmp_path):
    # Arrange
    raiz = tmp_path / 'projeto'
    (raiz / 'app').mkdir(parents=True)
    (raiz / 'app' / 'pedido.py').write_text('\n\n\n', encoding='utf-8')
    (raiz / 'rotas.py').write_text('ROTAS = {}\n', encoding='utf-8')
    saida = escrever(tmp_path / 'out', inv_do_script(), COMPLETO)
    # Act
    r = rodar(saida, projeto=raiz)
    # Assert
    assert r.returncode == 1
    assert 'não tem conteúdo' in r.stdout


def test_sem_projeto_o_relatorio_diz_que_nao_conferiu(tmp_path):
    # Arrange
    saida = escrever(tmp_path / 'out', inv_do_script(), COMPLETO)
    # Act
    r = rodar(saida)
    # Assert
    assert 'NÃO CONFERIDO' in r.stdout and '--projeto' in r.stdout
