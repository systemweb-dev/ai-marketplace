"""Os dois emissores do documento humano não podem divergir em silêncio.

`leia-me.md` (do `montar.py`) e `leia-me.html` (do `imprimir.py`) nascem do MESMO
material e **nenhum é conversão do outro** — é decisão de desenho, porque
hierarquia, cartão e etiqueta de confiança não cabem em Markdown. O preço é que
nada estrutural impede os dois de contarem histórias diferentes, e isso já
aconteceu duas vezes:

- a parte não escrita saía como *"a interpretação não escreveu esta parte"* no
  Markdown e era **omitida** no HTML — duas leituras do mesmo material, uma
  delas escondendo um buraco;
- o `Sem saltos` saía sob cada bloco em vez de uma vez por jornada.

Os dois vieram de olho humano, não de teste. Aqui a guarda é estrutural: bloco
novo num emissor **falha** até alguém declarar onde está o gêmeo dele — ou por
que ele não tem gêmeo.
"""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))

FIXTURES = Path(__file__).parent / 'fixtures'

# Cada bloco do HTML, e onde está o gêmeo dele. `None` é exclusivo do HTML, e o
# motivo fica escrito: só se declara exclusivo o que não cabe em Markdown ou o
# que o `guide.md` já cobre melhor.
GEMEOS = {
    # as quatro partes da narrativa: o par que JÁ divergiu
    'bloco_o_que_e': 'leia-me.md',
    'bloco_percurso': 'leia-me.md',
    'bloco_mapa': 'leia-me.md',
    'bloco_orientacoes': 'leia-me.md',
    # medidos: o gêmeo é a seção do relatório técnico
    'bloco_fatia': 'guide.md',
    'bloco_retrato': 'guide.md',
    'bloco_onde_mora': 'guide.md',
    'bloco_muda_junto': 'guide.md',
    'bloco_superficie': 'guide.md',
    'bloco_perigo': 'guide.md',
    'bloco_risco': 'guide.md',
    'bloco_sem_alcance': 'guide.md',
    'bloco_respondido': 'guide.md',
    'bloco_resolucao': 'guide.md',
    'bloco_ambiente': 'guide.md',
    'bloco_afirmacoes': 'guide.md',
    'bloco_lacunas': 'guide.md',
    # exclusivos do HTML, com o motivo — não é isenção, é decisão declarada
    'bloco_do_que_e_feito': None,     # barras de proporção; em Markdown viraria tabela redundante
    'bloco_arquivos_maiores': None,   # apoio visual; o `guide.md` lista os mesmos caminhos
}


def _blocos_do_html() -> set:
    """Lê o CÓDIGO do emissor, não o módulo importado: o que esta guarda precisa
    pegar é alguém ACRESCENTAR um bloco, e um import não distingue o que é bloco
    de página do que é auxiliar."""
    fonte = (RAIZ_SKILL / 'scripts' / 'lib' / 'pagina.py').read_text()
    arvore = ast.parse(fonte)
    return {n.name for n in arvore.body
            if isinstance(n, ast.FunctionDef) and n.name.startswith('bloco_')}


def test_todo_bloco_do_html_declara_onde_esta_o_gemeo():
    # Act
    blocos = _blocos_do_html()
    # Assert
    nao_declarados = blocos - set(GEMEOS)
    assert not nao_declarados, (
        f'bloco novo no HTML sem gêmeo declarado: {sorted(nao_declarados)} — '
        f'diga em GEMEOS se ele sai também no `leia-me.md`, no `guide.md`, ou '
        f'`None` com o motivo de ser só do HTML')
    sumidos = set(GEMEOS) - blocos
    assert not sumidos, (
        f'GEMEOS declara bloco que não existe mais: {sorted(sumidos)}')


# ───────────────────────── paridade de comportamento ────────────────────────

def _projeto(tmp_path) -> Path:
    """Um projeto mínimo com fonte textual: a primeira parte da narrativa exige
    `trecho` + `fonte`, e a fixture compartilhada não tem README."""
    raiz = tmp_path / 'proj'
    (raiz / 'app').mkdir(parents=True)
    (raiz / 'README.md').write_text('# Loja\n\nSistema de pedidos para padarias.\n')
    (raiz / 'pyproject.toml').write_text('[project]\nname = "loja"')
    (raiz / 'rotas.py').write_text('from app import servico\n')
    (raiz / 'container.py').write_text('import rotas\n')
    (raiz / 'app' / 'servico.py').write_text('x = 1\n')
    (raiz / 'app' / 'user.py').write_text('y = 2\n')
    return raiz


def _gerar(tmp_path, interpretacao: str):
    """Os três documentos, do mesmo inventário e da mesma interpretação."""
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(_projeto(tmp_path)),
                    '--out', str(tmp_path / 'out')], check=True, capture_output=True)
    tmp_path = tmp_path / 'out'
    (tmp_path / 'interpretation.toml').write_text(interpretacao)
    for script in ('montar.py', 'imprimir.py'):
        r = subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / script),
                            '--dir', str(tmp_path)], capture_output=True, text=True)
        assert r.returncode == 0, f'{script}: {r.stderr}'
    return ((tmp_path / 'leia-me.md').read_text(),
            (tmp_path / 'leia-me.html').read_text())


def _sem_marcacao(html: str) -> str:
    """O texto da página, para comparar com o do Markdown."""
    texto = re.sub(r'<[^>]+>', ' ', html)
    return ' '.join(texto.split())


COMPLETA = (
    '[[narrativa]]\nparte = "o-que-e"\nordem = 1\n'
    'texto = "É um sistema de pedidos"\ntrecho = "Sistema de pedidos"\n'
    'fonte = "README.md"\n'
    'evidencia = ["README.md"]\n\n'
    '[[narrativa]]\nparte = "percurso"\nordem = 1\nonde = "navegador"\n'
    'texto = "A tela chama"\nevidencia = ["rotas.py"]\nsaltos = []\n\n'
    '[[narrativa]]\nparte = "percurso"\nordem = 2\nonde = "banco"\n'
    'texto = "O serviço grava"\nevidencia = ["container.py"]\n'
    'saltos = ["o que o gatilho faz depois"]\n\n'
    '[[narrativa]]\nparte = "mapa"\nordem = 1\n'
    'texto = "Tudo mora em app"\nevidencia = ["app/"]\n\n'
    '[[narrativa]]\nparte = "orientacoes"\nordem = 1\n'
    'texto = "Mexa com cuidado"\nevidencia = ["app/"]\n')


def test_a_parte_nao_escrita_aparece_nos_dois_ou_em_nenhum(tmp_path):
    """O defeito histórico: o Markdown dizia "não foi escrita" e o HTML OMITIA —
    duas leituras do mesmo material, uma delas escondendo o buraco."""
    # Arrange — só `o-que-e`; as outras três ficam sem autor
    so_uma = ('[[narrativa]]\nparte = "o-que-e"\nordem = 1\n'
              'texto = "É um sistema de pedidos"\ntrecho = "Sistema de pedidos"\n'
              'fonte = "README.md"\nevidencia = ["README.md"]\n')
    # Act
    md, html = _gerar(tmp_path, so_uma)
    texto = _sem_marcacao(html)
    # Assert
    for titulo in ('O percurso de uma funcionalidade', 'Onde ficam as coisas',
                   'Para mexer'):
        assert titulo in md, f'{titulo} sumiu do markdown'
        assert titulo in texto, f'{titulo} sumiu do html'
    assert md.count('não escreveu esta parte') == 3
    assert texto.count('não escreveu esta parte') == 3


def test_o_texto_de_cada_parte_sai_nos_dois(tmp_path):
    # Act
    md, html = _gerar(tmp_path, COMPLETA)
    texto = _sem_marcacao(html)
    # Assert
    for frase in ('É um sistema de pedidos', 'A tela chama', 'O serviço grava',
                  'Tudo mora em app', 'Mexa com cuidado'):
        assert frase in md, f'{frase!r} sumiu do markdown'
        assert frase in texto, f'{frase!r} sumiu do html'


def test_a_evidencia_do_percurso_sai_nos_dois(tmp_path):
    """Era o defeito da v0.6.0: validada contra o projeto e impressa em lugar
    nenhum. Ela não pode voltar a sumir de um dos dois."""
    # Act
    md, html = _gerar(tmp_path, COMPLETA)
    texto = _sem_marcacao(html)
    # Assert
    for caminho in ('rotas.py', 'container.py'):
        assert caminho in md
        assert caminho in texto


def test_o_salto_sai_nos_dois(tmp_path):
    """Salto escondido é o erro mais caro que este documento pode cometer — e
    escondê-lo em UM dos dois documentos é o mesmo erro, pela metade."""
    # Act
    md, html = _gerar(tmp_path, COMPLETA)
    texto = _sem_marcacao(html)
    # Assert
    assert 'o que o gatilho faz depois' in md
    assert 'o que o gatilho faz depois' in texto
    # e "sem saltos" não pode ser afirmado quando há um
    assert 'Sem saltos' not in md and 'Sem saltos' not in texto


def test_a_travessia_de_fronteira_sai_nos_dois(tmp_path):
    # Act
    md, html = _gerar(tmp_path, COMPLETA)
    texto = _sem_marcacao(html)
    # Assert
    assert 'navegador → banco' in md
    assert 'navegador → banco' in texto


def test_a_frase_do_recorte_sai_nos_dois(tmp_path):
    """Três dos quatro lugares que escreviam esta frase só sabiam dizer "área":
    uma rodada por funcionalidade saía anunciando o projeto inteiro."""
    # Arrange
    raiz = _projeto(tmp_path)
    tmp_path = tmp_path / 'out'
    subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
                    '--projeto', str(raiz),
                    '--funcionalidade', 'user', '--out', str(tmp_path)],
                   check=True, capture_output=True)
    escopo = json.loads((tmp_path / 'inventory.json').read_text())['escopo']
    assert escopo['tipo'] == 'funcionalidade'
    (tmp_path / 'interpretation.toml').write_text(COMPLETA)
    for script in ('montar.py', 'imprimir.py'):
        r = subprocess.run([sys.executable, str(RAIZ_SKILL / 'scripts' / script),
                            '--dir', str(tmp_path)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    # Act
    md = (tmp_path / 'leia-me.md').read_text()
    guia = (tmp_path / 'guide.md').read_text()
    texto = _sem_marcacao((tmp_path / 'leia-me.html').read_text())
    # Assert
    assert 'a funcionalidade `user`' in md
    assert 'a funcionalidade `user`' in guia
    assert 'a funcionalidade user' in texto
