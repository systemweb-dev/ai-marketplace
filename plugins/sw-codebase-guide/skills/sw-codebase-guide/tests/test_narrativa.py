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


# ───────────────────────── task 8: o parser da narrativa ─────────────────────

def test_frase_proibida_recusada_pelo_parser(tmp_path):
    # Arrange — a garantia mais forte da skill fica exposta a prosa livre pela
    # primeira vez; o teste de saída não basta, a recusa é do parser
    r = preparar(tmp_path,
                 '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
                 'texto = "A pasta app não é usada em lugar nenhum"\n'
                 'evidencia = ["app/"]\n')
    # Assert
    assert r.returncode == 2
    assert 'não é usad' in (r.stderr + r.stdout) or 'proibida' in (r.stderr + r.stdout).lower()
    assert 'Traceback' not in r.stderr


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
    # Arrange — sem `ordem`, a montagem ordenaria por texto e embaralharia a árvore
    r = preparar(tmp_path,
                 '[[narrativa]]\nparte = "mapa"\nordem = 2\n'
                 'texto = "zzz segunda linha"\nevidencia = ["app/"]\n\n'
                 '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
                 'texto = "aaa primeira linha"\nevidencia = ["app/"]\n')
    # Assert
    assert r.returncode == 0, r.stderr
    doc = (tmp_path / 'leia-me.md').read_text()
    assert doc.index('aaa primeira') < doc.index('zzz segunda')


# ───────────────────── task 9: a guarda do trecho literal ────────────────────

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


# ──────────────────────── task 10: o leia-me.md ──────────────────────────────

QUATRO_PARTES = (
    '[[narrativa]]\nparte = "o-que-e"\n'
    'texto = "É um sistema de pedidos para padarias"\n'
    'trecho = "Sistema de pedidos para padarias"\nfonte = "README.md"\n'
    'evidencia = ["README.md"]\n\n'
    '[[narrativa]]\nparte = "percurso"\nordem = 1\nonde = "servidor"\n'
    'texto = "O pedido entra pela rota e grava direto"\n'
    'evidencia = ["app.py"]\nsaltos = ["o ORM resolve a tabela — não rastreado"]\n\n'
    '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
    'texto = "`app.py` é onde a lógica mora"\nevidencia = ["app.py"]\n\n'
    '[[narrativa]]\nparte = "orientacoes"\nordem = 1\n'
    'texto = "Para mexer na lógica você vai em `app.py`"\nevidencia = ["app.py"]\n')

README = '# Loja\n\nSistema de pedidos para padarias.'


def test_as_quatro_partes_aparecem_na_ordem(tmp_path):
    # Act
    r, saida = com_readme(tmp_path, README, QUATRO_PARTES)
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
    _, saida = com_readme(tmp_path, README, QUATRO_PARTES)
    doc = (saida / 'leia-me.md').read_text()
    # Assert — o leitor compara a paráfrase com o que está escrito na fonte
    assert 'É um sistema de pedidos para padarias' in doc
    assert 'Sistema de pedidos para padarias' in doc
    assert 'README.md' in doc


def test_cada_parte_aponta_o_relatorio_tecnico(tmp_path):
    # Arrange — número é livre na narrativa (decisão do dono), então nada impede
    # ela dizer 81 onde o técnico diz 64; o link torna descobrível em um clique
    _, saida = com_readme(tmp_path, README, QUATRO_PARTES)
    doc = (saida / 'leia-me.md').read_text()
    # Assert — um link por parte, não só um global no preâmbulo
    assert doc.count('guide.md#') == 4


def test_saltos_aparecem_onde_acontecem(tmp_path):
    # Act
    _, saida = com_readme(tmp_path, README, QUATRO_PARTES)
    # Assert — salto escondido numa nota de rodapé é o erro mais caro do documento
    assert 'não rastreado' in (saida / 'leia-me.md').read_text()


def test_dois_documentos_identicos_em_duas_montagens(tmp_path):
    # Arrange
    r, saida = com_readme(tmp_path, README, QUATRO_PARTES)
    primeiro = ((saida / 'guide.md').read_bytes(), (saida / 'leia-me.md').read_bytes())
    # Act
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                    '--dir', str(saida)], check=True, capture_output=True)
    # Assert
    assert ((saida / 'guide.md').read_bytes(),
            (saida / 'leia-me.md').read_bytes()) == primeiro


def test_recusa_nao_escreve_nenhum_dos_dois(tmp_path):
    # Arrange — sentinelas
    r, saida = com_readme(tmp_path, README, QUATRO_PARTES)
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


def test_parte_ausente_diz_que_ninguem_escreveu(tmp_path):
    # Arrange — o par negativo da ordem: uma parte vazia não pode sumir em silêncio
    r, saida = com_readme(tmp_path, README,
                          '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
                          'texto = "`app.py` é onde a lógica mora"\n'
                          'evidencia = ["app.py"]\n')
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout
    doc = (saida / 'leia-me.md').read_text()
    assert 'O que o produto faz' in doc
    assert 'não escreveu esta parte' in doc


def test_ordem_nao_inteira_e_recusada_com_motivo(tmp_path):
    # Arrange — `ordem = "dois"` passava por todas as validações e explodia no
    # `sorted` com TypeError e traceback: o parser tem que recusar, nunca estourar
    r = preparar(tmp_path,
                 '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
                 'texto = "primeiro"\nevidencia = ["app/"]\n\n'
                 '[[narrativa]]\nparte = "mapa"\nordem = "dois"\n'
                 'texto = "segundo"\nevidencia = ["app/"]\n')
    # Assert
    assert r.returncode == 2
    assert 'ordem' in (r.stderr + r.stdout).lower()
    assert 'Traceback' not in r.stderr


def test_percurso_sem_saltos_exige_o_campo_declarado(tmp_path):
    # Arrange — `saltos = []` é afirmação forte ("segui inteiro"), não omissão.
    # Sem o campo obrigatório, "não tentei" e "segui inteiro" ficam indistinguíveis.
    r, _ = com_readme(
        tmp_path, README,
        '[[narrativa]]\nparte = "percurso"\nordem = 1\nonde = "servidor"\n'
        'texto = "O pedido entra e grava"\nevidencia = ["app.py"]\n')
    # Assert
    assert r.returncode == 2
    assert 'saltos' in (r.stderr + r.stdout).lower()


def test_percurso_com_saltos_vazio_e_aceito(tmp_path):
    # Arrange — o par positivo: a lista VAZIA é legítima e significa "segui do
    # clique até o banco sem buraco". Sem este teste, exigir o campo poderia ter
    # sido implementado como "exigir que a lista tenha item", que é outra coisa.
    r, saida = com_readme(
        tmp_path, README,
        '[[narrativa]]\nparte = "percurso"\nordem = 1\nonde = "servidor"\n'
        'texto = "O pedido entra e grava"\nevidencia = ["app.py"]\nsaltos = []\n')
    # Assert
    assert r.returncode == 0, r.stderr + r.stdout
    assert 'O percurso' in (saida / 'leia-me.md').read_text()


def _slug(titulo: str) -> str:
    """A âncora que o GitHub gera para um título: minúsculas, espaço vira hífen,
    pontuação some. Acento permanece."""
    import re
    s = titulo.strip().lower()
    s = re.sub(r'[^\w\s-]', '', s, flags=re.UNICODE)
    return re.sub(r'\s+', '-', s)


def test_cada_ancora_existe_de_fato_no_relatorio(tmp_path):
    # Arrange — link que não resolve entrega o leitor no lugar errado, que é pior
    # do que não ter link. O teste de contagem só conta; este confere o destino.
    import re
    _, saida = com_readme(tmp_path, README, QUATRO_PARTES)
    guia = (saida / 'guide.md').read_text()
    leia_me = (saida / 'leia-me.md').read_text()
    # Act
    titulos = {_slug(m) for m in re.findall(r'^#{2,3}\s+(.+)$', guia, re.M)}
    ancoras = set(re.findall(r'guide\.md#([^)]+)', leia_me))
    # Assert
    assert ancoras, 'nenhuma âncora encontrada no leia-me'
    assert ancoras <= titulos, f'âncoras sem título correspondente: {ancoras - titulos}'


def test_as_quatro_partes_apontam_secoes_diferentes(tmp_path):
    # Arrange — `percurso` e `mapa` apontavam as duas para "como entrar"
    import re
    _, saida = com_readme(tmp_path, README, QUATRO_PARTES)
    # Act
    ancoras = re.findall(r'guide\.md#([^)]+)', (saida / 'leia-me.md').read_text())
    # Assert
    assert len(ancoras) == 4
    assert len(set(ancoras)) == 4, f'âncoras repetidas: {ancoras}'


def test_citar_fonte_cujo_conteudo_nao_foi_lido_diz_isso(tmp_path):
    """A seção `textos` tem teto, então existe fonte textual na lista SEM conteúdo. Sem
    guarda própria, citá-la cai na mensagem do trecho — e manda procurar erro na
    citação quando o conteúdo é que não foi lido."""
    # Arrange — oito docs grandes estouram o teto da seção; os últimos ficam sem texto
    projeto = tmp_path / 'proj'
    (projeto / 'docs').mkdir(parents=True)
    (projeto / 'README.md').write_text('# Portal\n\nCadastro de creators.')
    (projeto / 'app.py').write_text('x = 1')
    (projeto / 'pyproject.toml').write_text('[project]\nname = "x"')
    for i in range(8):
        (projeto / 'docs' / f'd{i}.md').write_text('linha de documentação\n' * 5000)
    saida = tmp_path / 'out'
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True)
    omitidos = [c for c, v in json.loads((saida / 'inventory.json').read_text())['textos'].items()
                if v.get('omitido')]
    assert omitidos, 'o fixture não estourou o teto: o teste não prova nada'
    (saida / 'interpretation.toml').write_text(
        '[[narrativa]]\nparte = "o-que-e"\n'
        'texto = "É um portal de creators"\n'
        f'trecho = "linha de documentação"\nfonte = "{omitidos[0]}"\n'
        'evidencia = ["README.md"]\n')
    # Act
    r = subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                        '--dir', str(saida)], capture_output=True, text=True)
    # Assert
    assert r.returncode == 2
    assert 'não entrou no inventário' in (r.stderr + r.stdout)


def test_salto_nao_repete_o_rotulo_do_documento(tmp_path):
    """"Não rastreado" é a frase natural de quem escreve o salto, e o documento já põe
    o rótulo — na prosa e, por CSS, no HTML. Rodando num projeto real saiu
    `**Não rastreado:** Não rastreado: o que acontece…` duas vezes seguidas."""
    # Act
    r, guia = com_readme(
        tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
        '[[narrativa]]\nparte = "o-que-e"\ntexto = "É um sistema de pedidos"\n'
        'trecho = "Sistema de pedidos para padarias"\nfonte = "README.md"\n'
        'evidencia = ["README.md"]\n\n'
        '[[narrativa]]\nparte = "percurso"\nonde = "navegador"\ntexto = "O pedido entra pela tela"\n'
        'saltos = ["Não rastreado: o que o banco faz depois", "nao rastreado: quem lê a fila"]\n'
        'evidencia = ["app.py"]\n')
    # Assert
    assert r.returncode == 0, r.stderr
    leia_me = (tmp_path / 'out' / 'leia-me.md').read_text()
    assert '**Não rastreado:** o que o banco faz depois' in leia_me
    assert '**Não rastreado:** quem lê a fila' in leia_me
    assert 'Não rastreado: Não rastreado' not in leia_me


def test_segundo_bloco_de_o_que_e_dispensa_trecho(tmp_path):
    """A guarda exige que a citação EXISTA, não que ela SUSTENTE a frase — e exigir
    trecho em todo bloco empurra quem escreve a pendurar uma citação verdadeira e sem
    relação embaixo do parágrafo, com cara de evidência. É pior que não citar.
    O primeiro bloco ancora a parte numa fonte textual; os demais podem se sustentar
    na evidência de código."""
    # Act
    r, _ = com_readme(
        tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
        '[[narrativa]]\nparte = "o-que-e"\nordem = 1\ntexto = "É um sistema de pedidos"\n'
        'trecho = "Sistema de pedidos para padarias"\nfonte = "README.md"\n'
        'evidencia = ["README.md"]\n\n'
        '[[narrativa]]\nparte = "o-que-e"\nordem = 2\n'
        'texto = "Aceita cliente menor de idade, com responsável"\n'
        'evidencia = ["app.py"]\n')
    # Assert
    assert r.returncode == 0, r.stderr
    leia_me = (tmp_path / 'out' / 'leia-me.md').read_text()
    assert 'menor de idade' in leia_me
    assert leia_me.count('— `README.md`') == 1, 'só o bloco que ancora leva citação'
    # o HTML é o outro emissor, e é onde a dispensa do trecho estourou com KeyError:
    # testar só o markdown deixaria o documento que as pessoas LEEM quebrado
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'imprimir.py'),
                    '--dir', str(tmp_path / 'out')], check=True, capture_output=True)
    html = (tmp_path / 'out' / 'leia-me.html').read_text()
    assert 'menor de idade' in html
    assert html.count('<blockquote>') == 1


def test_primeiro_bloco_de_o_que_e_sem_trecho_e_recusado(tmp_path):
    """A parte continua ancorada: sem nenhuma citação, "o que o produto faz" vira prosa
    fluente sem lastro — que é o modo de falha que a guarda existe para pegar."""
    # Act
    r, _ = com_readme(
        tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
        '[[narrativa]]\nparte = "o-que-e"\nordem = 1\n'
        'texto = "É um sistema de pedidos para padarias"\nevidencia = ["app.py"]\n')
    # Assert
    assert r.returncode == 2
    assert 'trecho' in (r.stderr + r.stdout).lower()


def test_trecho_do_segundo_bloco_tambem_e_conferido(tmp_path):
    """Dispensar não é afrouxar: o bloco que CITA continua tendo a citação conferida
    contra a fonte."""
    # Act
    r, _ = com_readme(
        tmp_path, '# Loja\n\nSistema de pedidos para padarias.',
        '[[narrativa]]\nparte = "o-que-e"\nordem = 1\ntexto = "É um sistema de pedidos"\n'
        'trecho = "Sistema de pedidos para padarias"\nfonte = "README.md"\n'
        'evidencia = ["README.md"]\n\n'
        '[[narrativa]]\nparte = "o-que-e"\nordem = 2\ntexto = "Atende hospitais"\n'
        'trecho = "Sistema de gestão hospitalar"\nfonte = "README.md"\n'
        'evidencia = ["app.py"]\n')
    # Assert
    assert r.returncode == 2
    assert 'não aparece' in (r.stderr + r.stdout)


def test_fonte_textual_fora_da_arvore_vale_como_evidencia(tmp_path):
    """A skill lê `.claude/CLAUDE.md` porque num projeto real é a única documentação
    que existe — e depois recusava citá-la, porque a pasta é podada da árvore e a
    guarda de evidência só conhecia `caminhos_do_projeto`.

    Um agente seguindo o SKILL.md bateu nisso: a mensagem dizia "evidência não
    existe no projeto" sobre um arquivo que a própria skill tinha acabado de ler, e
    que estava no inventário duas vezes."""
    # Arrange
    projeto = tmp_path / 'proj'
    (projeto / '.claude').mkdir(parents=True)
    (projeto / '.claude' / 'CLAUDE.md').write_text('# Sistema\n\nApuração fiscal.')
    (projeto / 'app.py').write_text('x = 1')
    (projeto / 'pyproject.toml').write_text('[project]\nname = "x"')
    saida = tmp_path / 'out'
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(projeto), '--out', str(saida)],
                   check=True, capture_output=True)
    (saida / 'interpretation.toml').write_text(
        '[[narrativa]]\nparte = "o-que-e"\ntexto = "É uma apuração fiscal"\n'
        'trecho = "Apuração fiscal"\nfonte = ".claude/CLAUDE.md"\n'
        'evidencia = [".claude/CLAUDE.md"]\n')
    # Act
    r = subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'montar.py'),
                        '--dir', str(saida)], capture_output=True, text=True)
    # Assert
    assert r.returncode == 0, r.stderr
