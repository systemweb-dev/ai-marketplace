import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / 'fixtures'


def varrer(projeto, saida):
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True, text=True)


def imprimir(dir_saida, *extra, env=None):
    return subprocess.run(
        [sys.executable, str(RAIZ_SKILL / 'scripts' / 'imprimir.py'),
         '--dir', str(dir_saida), *extra],
        capture_output=True, text=True, env=env)


def preparar(tmp_path, **ajustes):
    varrer(FIXTURES / 'acoplamento_invisivel', tmp_path)
    if ajustes:
        inv = json.loads((tmp_path / 'inventory.json').read_text())
        inv.update(ajustes)
        (tmp_path / 'inventory.json').write_text(json.dumps(inv))
    return tmp_path


def imprimir_com_narrativa(dir_saida, narrativa, estilo='escuro', afirmacoes=None):
    """Chama o construtor direto: o `imprimir.py` recebe a narrativa já lida pelo
    `montar.py`, e montar um `interpretation.toml` válido só para testar o título
    acoplaria este teste a todas as guardas do parser."""
    import json as _json
    sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))
    import imprimir as mod
    inv = _json.loads((Path(dir_saida) / 'inventory.json').read_text())
    return mod.construir(inv, afirmacoes or [], narrativa, estilo)


def secao_do_bloco(html, titulo):
    """Só a `<section>` daquele bloco. Fatiar por quantidade de caracteres entrava no
    bloco seguinte, e o teste media a etiqueta de outro."""
    depois = html.split(titulo, 1)[1]
    return depois.split('</section>', 1)[0]


def test_gera_o_html_a_partir_do_inventario(tmp_path):
    # Arrange
    preparar(tmp_path)
    # Act
    r = imprimir(tmp_path)
    # Assert
    assert r.returncode == 0, r.stderr
    html = (tmp_path / 'leia-me.html').read_text()
    assert '<!doctype html>' in html.lower()
    assert 'Retrato do projeto' in html


def test_html_e_self_contained(tmp_path):
    # Arrange — o PDF é gerado offline; nada pode vir da rede
    preparar(tmp_path)
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert 'base64' in html, 'as fontes precisam estar embutidas'
    for proibido in ('https://fonts.', 'cdn.', '<script src="http', 'http://'):
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


def test_cada_bloco_declara_o_nivel_de_confianca(tmp_path):
    # Arrange
    preparar(tmp_path)
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert — a etiqueta é o dispositivo mais importante do documento, e a legenda
    # é o que a faz significar alguma coisa para quem lê
    assert 'data-n="fato"' in html
    assert 'Cada bloco diz de onde veio' in html


def test_tem_hierarquia_e_pergunta_por_bloco(tmp_path):
    # Arrange
    preparar(tmp_path)
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert — o rótulo nomeia; a pergunta orienta. Sem os três níveis todo bloco
    # pesa igual e o olho não tem onde pousar primeiro.
    assert 'class="bloco largo n1' in html or 'class="bloco n1' in html
    assert 'class="sub"' in html
    assert 'Por onde começar' in html


def test_retrato_sem_git_nao_vira_zero(tmp_path):
    # Arrange — `0 autores` se lê como "ninguém mexe nisso"; a lacuna diz o motivo
    preparar(tmp_path, retrato={'autores': None, 'commits': None,
                                'primeiro_commit': None, 'ultimo_commit': None,
                                'semanas_de_vida': None, 'semanas_parado': None,
                                'lacuna': 'não há repositório git aqui'})
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert 'não há repositório git aqui' in html
    assert '>0<' not in html.split('Retrato do projeto')[1][:1200]


def test_recorte_aparece_no_topo(tmp_path):
    # Arrange
    preparar(tmp_path, escopo={'area': 'app', 'criterio': 'prefixo', 'n_arquivos': 3})
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert 'Recorte' in html and 'app' in html


def test_os_dois_estilos_saem_diferentes(tmp_path):
    # Arrange — o dono escolheu oferecer os dois; são paletas e tipografias próprias
    preparar(tmp_path)
    # Act
    imprimir(tmp_path, '--estilo', 'escuro')
    escuro = (tmp_path / 'leia-me.html').read_text()
    imprimir(tmp_path, '--estilo', 'brutalista')
    brutalista = (tmp_path / 'leia-me.html').read_text()
    # Assert — mesmo conteúdo, vestimenta diferente
    assert escuro != brutalista
    assert 'Retrato do projeto' in escuro and 'Retrato do projeto' in brutalista


def test_estilo_invalido_para_com_motivo(tmp_path):
    # Arrange
    preparar(tmp_path)
    # Act
    r = imprimir(tmp_path, '--estilo', 'neon')
    # Assert
    assert r.returncode != 0
    assert 'Traceback' not in r.stderr


def test_valor_de_env_nunca_chega_ao_html(tmp_path):
    # Arrange — o HTML é o arquivo que se manda por e-mail; é o pior lugar possível
    # para um segredo vazar, e o inventário já guarda só as chaves
    preparar(tmp_path, ambiente={'.env': ['DB_PASSWORD', 'STRIPE_SECRET_KEY']})
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert 'DB_PASSWORD' in html
    assert 'STRIPE_SECRET_KEY' in html


def test_sem_chromium_entrega_o_html_e_avisa(tmp_path, monkeypatch):
    # Arrange — não achar navegador não é falha da skill
    import os
    preparar(tmp_path)
    env = dict(os.environ, PATH='/nao/existe')
    # Act
    r = imprimir(tmp_path, '--pdf', env=env)
    # Assert
    assert r.returncode == 0, 'sem Chromium o processo termina com SUCESSO'
    assert (tmp_path / 'leia-me.html').exists()
    assert not (tmp_path / 'leia-me.pdf').exists()
    assert 'chrom' in (r.stdout + r.stderr).lower()


def test_sem_inventario_para_com_motivo(tmp_path):
    # Act
    r = imprimir(tmp_path)
    # Assert
    assert r.returncode == 2
    assert 'inventory.json' in (r.stdout + r.stderr)
    assert 'Traceback' not in r.stderr


def test_arquivo_gerado_nao_entra_nos_maiores(tmp_path):
    # Arrange — `package-lock.json` (105 KB) e `tsconfig.tsbuildinfo` (240 KB)
    # ocupavam o topo de "onde está a massa do código", que passava a responder
    # outra pergunta. Um JSON de cache de 2,8 MB chegou a ser "o maior arquivo".
    preparar(tmp_path, arvore=[
        {'caminho': 'package-lock.json', 'bytes': 900000, 'linguagem': 'json',
         'gerado': True, 'acima_do_teto': False},
        {'caminho': 'src/pequeno.ts', 'bytes': 400, 'linguagem': 'typescript',
         'gerado': False, 'acima_do_teto': False},
    ])
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    maiores = html.split('Arquivos maiores')[1][:600]
    assert 'pequeno.ts' in maiores
    assert 'package-lock' not in maiores


def test_caminho_longo_preserva_o_nome_do_arquivo(tmp_path):
    # Arrange — cortar por caractere dava `…e/migrations/0001_core_tables.sql`,
    # e o leitor perdia a única parte que identifica o arquivo
    preparar(tmp_path, arvore=[
        {'caminho': 'supabase/migrations/muito/fundo/0001_core_tables.sql',
         'bytes': 5000, 'linguagem': 'sql', 'gerado': False, 'acima_do_teto': False},
    ])
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert '0001_core_tables.sql' in html


def test_percentual_de_teste_e_do_projeto_nao_da_area(tmp_path):
    # Arrange — o retrato é do PROJETO: autores e commits já eram, mas o
    # percentual saía da árvore RECORTADA. Uma área de telas sem teste virava
    # "0% é teste · mexer aqui não tem rede" num projeto com 44% de cobertura.
    preparar(tmp_path,
             escopo={'area': 'src/app', 'criterio': 'prefixo', 'n_arquivos': 2},
             arvore=[{'caminho': 'src/app/a.tsx', 'bytes': 10, 'linguagem': 'tsx',
                      'gerado': False, 'acima_do_teto': False},
                     {'caminho': 'src/app/b.tsx', 'bytes': 10, 'linguagem': 'tsx',
                      'gerado': False, 'acima_do_teto': False}],
             caminhos_do_projeto=['src/app/a.tsx', 'src/app/b.tsx',
                                  'tests/a.test.ts', 'tests/b.test.ts'],
             retrato={'autores': 1, 'commits': 10, 'primeiro_commit': '2026-01-01T00:00:00+00:00',
                      'ultimo_commit': '2026-02-01T00:00:00+00:00', 'semanas_de_vida': 4,
                      'semanas_parado': 1, 'lacuna': None})
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert — 2 de 4 do projeto, não 0 de 2 da área
    retrato = html.split('Retrato do projeto')[1][:900]
    assert '50%' in retrato
    assert '>0%<' not in retrato


def test_negrito_do_trecho_literal_e_renderizado(tmp_path):
    # Arrange — o trecho vem de um `.md`, e `**single-tenant**` chegava cru à tela
    preparar(tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[narrativa]]\nparte = "o-que-e"\n'
        'texto = "É um CRM"\ntrecho = "CRM **single-tenant** para uma empresa"\n'
        'fonte = "README.md"\nevidencia = ["rotas.py"]\n')
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert '<strong>single-tenant</strong>' in html
    assert '**single-tenant**' not in html


def test_html_da_fonte_nao_vira_html_da_pagina(tmp_path):
    # Arrange — o par de segurança do anterior: renderizar o negrito não pode
    # abrir caminho para o conteúdo do projeto lido injetar marcação
    preparar(tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[narrativa]]\nparte = "o-que-e"\n'
        'texto = "É um CRM"\ntrecho = "um <script>alert(1)</script> no README"\n'
        'fonte = "README.md"\nevidencia = ["rotas.py"]\n')
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html


def test_a_aba_do_navegador_leva_o_titulo_do_projeto(tmp_path):
    """O `<h1>` saía da narrativa e o `<title>` era fixo. Quem abre o guia de três
    projetos recebidos vê três abas idênticas, e é o `<title>` que vai para o nome do
    arquivo salvo e para o cabeçalho de impressão."""
    # Arrange
    preparar(tmp_path)
    narrativa = [{'parte': 'o-que-e', 'texto': 'É um portal de creators.',
                  'trecho': 'x', 'fonte': 'README.md', 'evidencia': []}]
    # Act
    html = imprimir_com_narrativa(tmp_path, narrativa)
    # Assert
    assert '<title>É um portal de creators.</title>' in html


def test_abertura_longa_nao_vira_manchete_de_duas_linhas(tmp_path):
    """A manchete era "a primeira frase", cortada em `. ` — e uma abertura real que
    separa as orações com `:` e vírgula não tem ponto antes do fim: o `<h1>` saiu com
    207 caracteres. Manchete desse tamanho não é manchete."""
    # Arrange
    preparar(tmp_path)
    longa = ('São três aplicações que atendem um negócio de campanhas entre marcas e '
             'creators: um site com o portal onde o creator se cadastra, um painel '
             'onde a equipe gerencia campanhas, e uma API em PHP onde mora a regra.')
    narrativa = [{'parte': 'o-que-e', 'texto': longa, 'trecho': 'x',
                  'fonte': 'README.md', 'evidencia': []}]
    # Act
    html = imprimir_com_narrativa(tmp_path, narrativa)
    # Assert
    import re
    h1 = re.search(r'<h1>(.*?)</h1>', html, re.S).group(1)
    assert len(h1) <= 120, f'manchete com {len(h1)} caracteres: {h1!r}'
    assert h1.startswith('São três aplicações')
    assert 'marcas e creators' in h1       # cortou na oração, não no meio da ideia


def test_abertura_longa_sem_oracao_cai_no_titulo_factual(tmp_path):
    """Nem frase nem oração couberam: aí a manchete não existe, e o título volta a ser
    o factual. A alternativa — truncar em 120 caracteres — corta no meio da palavra e
    entrega uma manchete que começa a dizer algo e para."""
    # Arrange — uma frase longa sem `:`, `;` nem travessão
    preparar(tmp_path)
    longa = ('O sistema processa pedidos de compra e os encaminha para o setor '
             'responsável por conferir estoque antes de liberar a nota fiscal '
             'correspondente ao faturamento do mês em curso')
    narrativa = [{'parte': 'o-que-e', 'texto': longa, 'trecho': 'x',
                  'fonte': 'README.md', 'evidencia': []}]
    # Act
    html = imprimir_com_narrativa(tmp_path, narrativa)
    # Assert
    import re
    h1 = re.search(r'<h1>(.*?)</h1>', html, re.S).group(1)
    assert h1.startswith('Um projeto de')
    assert 'faturamento' not in h1, 'truncou a prosa em vez de cair no factual'


def test_retrato_com_numeros_e_procedencia_nao_e_marcado_como_nao_apurado(tmp_path):
    """Num monorepo o retrato tem números E uma lacuna — que ali não é ausência, é
    procedência: "a soma de 4 sub-repositórios". O bloco olhava só para a existência
    da lacuna e carimbava NÃO APURADO sobre seis autores e 782 commits medidos."""
    # Arrange
    preparar(tmp_path, retrato={
        'autores': 6, 'commits': 782, 'primeiro_commit': '2025-08-07T19:15:34-03:00',
        'ultimo_commit': '2026-09-28T23:29:11-03:00', 'semanas_de_vida': 59,
        'semanas_parado': 1,
        'lacuna': 'a raiz não é repositório git; o retrato é a soma de 4 sub-repositórios'})
    # Act
    r = imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    bloco = secao_do_bloco(html, 'Retrato do projeto')
    # Assert
    assert r.returncode == 0, r.stderr
    assert 'não apurado' not in bloco.lower()
    assert '782 commits' in bloco
    assert 'soma de 4 sub-repositórios' in bloco, 'a procedência tem que aparecer'


def test_retrato_sem_medida_nenhuma_continua_nao_apurado(tmp_path):
    """O contrário: sem número nenhum, o bloco segue dizendo que não apurou, com o
    motivo. É a garantia que o projeto sem git depende."""
    # Arrange
    preparar(tmp_path, retrato={
        'autores': None, 'commits': None, 'primeiro_commit': None,
        'ultimo_commit': None, 'semanas_de_vida': None, 'semanas_parado': None,
        'lacuna': 'não há repositório git aqui'})
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    bloco = secao_do_bloco(html, 'Retrato do projeto')
    # Assert
    assert 'Não apurado' in bloco
    assert 'não há repositório git aqui' in bloco


def test_crase_na_prosa_vira_codigo_e_nao_crase_na_tela(tmp_path):
    """O guia é markdown e quem escreve a interpretação escreve `Helper::isMinor` com
    crase — é a notação natural. Só a citação literal passava pelo renderizador; a
    prosa das afirmações e das quatro partes saía com as crases na tela."""
    # Arrange
    preparar(tmp_path)
    afirmacoes = [{'secao': 'o-que-faz', 'nivel': 'deducao',
                   'texto': 'A regra está em `Helper::isMinor`, e é **obrigatória**',
                   'evidencia': []}]
    narrativa = [{'parte': 'mapa', 'texto': 'As telas ficam em `src/app/`',
                  'evidencia': []}]
    # Act
    html = imprimir_com_narrativa(tmp_path, narrativa, afirmacoes=afirmacoes)
    # Assert
    assert '<code>Helper::isMinor</code>' in html
    assert '<strong>obrigatória</strong>' in html
    assert '<code>src/app/</code>' in html
    assert '`Helper::isMinor`' not in html


def test_html_vindo_da_interpretacao_nao_vira_html_na_pagina(tmp_path):
    """O par do teste acima: renderizar markdown na prosa não pode abrir caminho para
    tag. Escapa primeiro, renderiza depois."""
    # Arrange
    preparar(tmp_path)
    narrativa = [{'parte': 'mapa', 'texto': 'As telas ficam em <script>x</script>',
                  'evidencia': []}]
    # Act
    html = imprimir_com_narrativa(tmp_path, narrativa)
    # Assert
    assert '<script>x</script>' not in html
    assert '&lt;script&gt;' in html


def test_salto_no_html_tambem_perde_o_rotulo_repetido(tmp_path):
    """O `montar.py` limpava o rótulo e o `imprimir.py` lia o TOML por conta própria:
    a correção chegou ao `leia-me.md` e não ao HTML, onde o CSS põe NÃO RASTREADO
    antes do texto que já começava com "Não rastreado:"."""
    # Arrange
    preparar(tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[narrativa]]\nparte = "percurso"\nonde = "navegador"\ntexto = "O pedido entra pela tela"\n'
        'saltos = ["Não rastreado: o que o banco faz depois"]\nevidencia = []\n')
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert 'o que o banco faz depois' in html
    assert 'Não rastreado:' not in html


def test_sem_saltos_e_dito_uma_vez_e_so_quando_nao_ha_nenhum(tmp_path):
    """"Sem saltos: o percurso foi seguido do começo ao fim" saía sob CADA parágrafo
    do percurso. Num percurso de três blocos a página afirmava duas vezes que não
    havia buraco e então mostrava dois — os saltos são da jornada, não do parágrafo."""
    # Arrange
    preparar(tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[narrativa]]\nparte = "percurso"\nordem = 1\nonde = "navegador"\ntexto = "A tela chama"\n'
        'saltos = []\nevidencia = []\n\n'
        '[[narrativa]]\nparte = "percurso"\nordem = 2\nonde = "banco"\ntexto = "O serviço grava"\n'
        'saltos = ["o que o banco faz depois"]\nevidencia = []\n')
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert 'Sem saltos' not in html, 'há um salto declarado; a página não pode negar buraco'


def test_percurso_inteiro_sem_salto_diz_isso_uma_vez(tmp_path):
    # Arrange
    preparar(tmp_path)
    (tmp_path / 'interpretation.toml').write_text(
        '[[narrativa]]\nparte = "percurso"\nordem = 1\nonde = "navegador"\ntexto = "A tela chama"\n'
        'saltos = []\nevidencia = []\n\n'
        '[[narrativa]]\nparte = "percurso"\nordem = 2\nonde = "banco"\ntexto = "O serviço grava"\n'
        'saltos = []\nevidencia = []\n')
    # Act
    imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert html.count('Sem saltos') == 1


def test_bloco_da_taxa_mostra_os_numeros_absolutos(tmp_path):
    """Sem a taxa, uma lista de dependências parece completa mesmo quando metade
    falhou. Os números absolutos, e não o percentual sozinho, porque é a rotulagem
    do balde `externos` que move a fração."""
    # Arrange
    preparar(tmp_path, imports={'arestas': [], 'indisponivel': [], 'barris': [],
                                'resolucao': {'php': {
                                    'relativos': 0, 'externos': 424,
                                    'sufixo_unico': 569, 'base_provada': 0,
                                    'config_conferida': 0, 'ambiguos': 0,
                                    'pendurados': 0, 'nao_resolvidos': 0}}})
    # Act
    r = imprimir(tmp_path)
    html = (tmp_path / 'leia-me.html').read_text()
    # Assert
    assert r.returncode == 0, r.stderr
    bloco = secao_do_bloco(html, 'Quanto disto foi medido')
    assert '569' in bloco and '424' in bloco and '100%' in bloco
