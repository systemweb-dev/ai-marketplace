"""O recorte por funcionalidade: o menu do *o quê* e a fatia.

Os números dos limiares vieram de medição em quatro projetos reais, e cada
defeito que a medição pegou virou um teste aqui — senão a próxima pessoa a mexer
reabre a porta sem saber que ela já tinha sido fechada.
"""
import json
import subprocess
import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_SKILL / 'scripts'))

from lib import funcionalidades as fx  # noqa: E402
from lib import recorte as mod_recorte  # noqa: E402

FIXTURES = Path(__file__).parent / 'fixtures'

# Dois testes abaixo dimensionam a fixture pelo teto REAL do módulo — é assim
# que eles provam que o padrão continua ligado. Esta guarda existe porque a
# alternativa é a suíte alocar o que o teto mandar: uma prova de mutação levou
# `TETO_COMPARTILHADO` a 10**9 e o teste tentou criar um bilhão de strings,
# travando a máquina. Falhar em uma linha é melhor que morrer alocando.
TETO_DE_FIXTURE = 500
for _nome in ('TETO_COMPARTILHADO', 'TETO_NUCLEO'):
    assert getattr(fx, _nome) <= TETO_DE_FIXTURE, (
        f'{_nome} = {getattr(fx, _nome)} é grande demais para dimensionar '
        f'fixture; passe o teto por parâmetro no `recortar`')


def arvore(*caminhos):
    return [{'caminho': c, 'gerado': False} for c in caminhos]


# ───────────────────────── extração: termo × papel ──────────────────────────

def test_o_sufixo_do_nome_vira_papel():
    # Act / Assert
    assert fx.termo_e_papel('api/middleware/PedidoMiddleware.php') == ('pedido', 'middleware')
    assert fx.termo_e_papel('app/Services/PedidoRecorrenteService.php') == (
        'pedido recorrente', 'service')


def test_o_nome_que_e_papel_pega_a_pasta():
    """`funil/page.tsx` nomeia pela pasta — é como o App Router escreve."""
    # Act / Assert
    assert fx.termo_e_papel('src/app/(app)/funil/page.tsx') == ('funil', 'page')
    assert fx.termo_e_papel('src/app/(app)/funil/actions.ts') == ('funil', 'action')


def test_segmento_dinamico_de_rota_nao_e_funcionalidade():
    """`[id]` entrou num menu real com 10 arquivos e 2 papéis."""
    # Act / Assert
    assert fx.termo_e_papel('src/app/clientes/[id]/page.tsx') is None
    assert fx.termo_e_papel('src/app/@modal/page.tsx') is None


def test_a_pasta_de_papel_nomeia_pelo_arquivo():
    # Act / Assert
    assert fx.termo_e_papel('app/Controllers/UserController.php') == ('user', 'controller')
    assert fx.termo_e_papel('app/Models/Address.php') == ('address', 'model')


def test_plural_da_pasta_e_singular_do_arquivo_sao_o_mesmo_papel():
    """Sem isto, `Controllers/` e `Controller.php` eram dois papéis, e um arquivo
    sozinho virava fatia vertical."""
    # Act
    pastas = fx.termo_e_papel('app/Controllers/PedidoController.php')
    # Assert
    assert pastas == ('pedido', 'controller')


# ───────────────────────── o menu ───────────────────────────────────────────

def test_nome_em_dois_papeis_vira_candidato():
    # Act
    achados = fx.candidatos(arvore('app/Controllers/PedidoController.php',
                                   'app/Services/PedidoService.php'))
    # Assert
    assert [f['termo'] for f in achados] == ['pedido']
    assert achados[0]['papeis'] == ['controller', 'service']
    assert achados[0]['arquivos'] == 2


def test_arquivo_mais_o_teste_dele_nao_e_funcionalidade():
    """`paginacao [component test]` entrou num menu real. É um arquivo com o
    teste dele, não uma fatia vertical."""
    # Act
    achados = fx.candidatos(arvore('src/components/Paginacao.vue',
                                   'tests/PaginacaoTest.php'))
    # Assert
    assert achados == []


def test_barril_nao_conta_como_papel():
    # Act
    achados = fx.candidatos(arvore('src/pedido/index.ts', 'src/services/pedido.ts'))
    # Assert
    assert [f['termo'] for f in achados] == []


def test_middleware_mais_rotas_e_area_nao_funcionalidade():
    """No framework PHP toda ÁREA tem middleware e arquivo de rotas — `site`,
    `admin` e `client` entraram no menu por isso, e para área já existe
    `--areas`."""
    # Act
    achados = fx.candidatos(arvore('api/middleware/Site/SiteMiddleware.php',
                                   'api/app/Site/Rotas.php'))
    # Assert
    assert achados == []


def test_o_mesmo_nome_com_uma_camada_de_verdade_volta_a_valer():
    """A regra anterior não pode apagar a área que TAMBÉM é funcionalidade: com
    um controller junto, `site` deixa de ser só declaração de área."""
    # Act
    achados = fx.candidatos(arvore('api/middleware/Site/SiteMiddleware.php',
                                   'api/app/Site/Rotas.php',
                                   'api/app/Site/Controllers/SiteController.php'))
    # Assert
    assert [f['termo'] for f in achados] == ['site']


def test_o_menu_poe_a_fatia_mais_vertical_primeiro():
    # Arrange — `pedido` atravessa 3 papéis, `nota` atravessa 2
    a = arvore('app/Controllers/PedidoController.php', 'app/Services/PedidoService.php',
               'app/Models/Pedido.php',
               'app/Controllers/NotaController.php', 'app/Models/Nota.php')
    # Act
    achados = fx.candidatos(a)
    # Assert
    assert [f['termo'] for f in achados] == ['pedido', 'nota']


def test_arquivo_gerado_nao_entra_no_menu():
    # Arrange
    a = [{'caminho': 'app/Controllers/PedidoController.php', 'gerado': False},
         {'caminho': 'app/Services/PedidoService.php', 'gerado': True}]
    # Act / Assert
    assert fx.candidatos(a) == []


# ───────────────────────── o casamento largo, do recorte ────────────────────

def test_o_termo_casa_como_palavra_nao_como_pedaco():
    """`user` não pode casar `useRouter`: o recorte encheria de arquivo que não
    tem nada a ver."""
    # Act / Assert
    assert fx.casa('src/models/User.php', 'user')
    assert not fx.casa('src/hooks/useRouter.ts', 'user')


def test_o_termo_casa_na_pasta_tambem():
    """Medido: só pelo nome do arquivo, o cadastro perdia os seis passos do
    formulário, que moram numa pasta com o nome da funcionalidade."""
    # Act / Assert
    assert fx.casa('website/views/cadastro/passos/PassoConta.vue', 'cadastro')


def test_termo_composto_casa_na_ordem():
    # Act / Assert
    assert fx.casa('app/Models/PedidoRecorrente.php', 'pedido recorrente')
    assert not fx.casa('app/Models/RecorrentePedido.php', 'pedido recorrente')


# ───────────────────────── a fatia: núcleo, alcance, compartilhado ──────────

def test_o_que_o_nucleo_importa_entra_na_fatia():
    """É o ponto do recorte: a regra mora num arquivo que o nome nunca acha."""
    # Arrange
    a = arvore('app/CadastroService.php', 'app/Regras.php', 'app/Outro.php')
    arestas = [{'de': 'app/CadastroService.php', 'para': 'app/Regras.php'}]
    # Act
    fatia = fx.recortar(a, arestas, 'cadastro')
    # Assert
    assert fatia['nucleo'] == ['app/CadastroService.php']
    assert fatia['alcance'] == ['app/Regras.php']
    assert 'app/Outro.php' not in fatia['alcance']


def _com_importadores(quantos: int):
    """Um alvo importado pelo núcleo e por `quantos` arquivos de fora.

    O teto é INJETADO no `recortar`, nunca usado para dimensionar isto: escrever
    `range(fx.TETO_COMPARTILHADO + 1)` acopla o tamanho da fixture à constante
    de produção, e uma prova de mutação que levou o teto a 10**9 fez o teste
    tentar alocar um bilhão de strings e travar a máquina.
    """
    outros = [f'app/Outro{i}.php' for i in range(quantos)]
    a = arvore('app/CadastroService.php', 'app/Alvo.php', *outros)
    arestas = ([{'de': 'app/CadastroService.php', 'para': 'app/Alvo.php'}]
               + [{'de': o, 'para': 'app/Alvo.php'} for o in outros])
    return a, arestas


def test_o_alvo_que_todo_mundo_importa_sai_na_lista_propria():
    """O helper com a regra tinha 29 importadores de fora: deixá-lo de fora
    perderia a regra, chamá-lo de "parte do cadastro" seria mentira."""
    # Arrange — três de fora, com teto dois
    a, arestas = _com_importadores(3)
    # Act
    fatia = fx.recortar(a, arestas, 'cadastro', teto_compartilhado=2)
    # Assert
    assert fatia['alcance'] == []
    assert fatia['compartilhado'] == [{'caminho': 'app/Alvo.php', 'importadores': 3}]


def test_no_teto_o_alvo_ainda_e_da_fatia():
    """O limiar é `>`, não `>=`: exatamente no teto o alvo continua da fatia."""
    # Arrange
    a, arestas = _com_importadores(2)
    # Act
    fatia = fx.recortar(a, arestas, 'cadastro', teto_compartilhado=2)
    # Assert
    assert fatia['alcance'] == ['app/Alvo.php']
    assert fatia['compartilhado'] == []


def test_o_teto_padrao_do_modulo_e_o_que_vale_sem_pedir_outro():
    """O parâmetro existe para o teste; o número que governa o projeto real é o
    do módulo, e isto prova que ele continua ligado."""
    # Arrange
    a, arestas = _com_importadores(fx.TETO_COMPARTILHADO + 1)
    # Act
    fatia = fx.recortar(a, arestas, 'cadastro')
    # Assert
    assert [c['caminho'] for c in fatia['compartilhado']] == ['app/Alvo.php']


def test_quem_importa_a_fatia_e_contado_e_nao_entra():
    """Raio de alcance é número, não conteúdo: incluir quem usa a fatia faria o
    recorte crescer até o projeto inteiro."""
    # Arrange
    a = arvore('app/CadastroService.php', 'app/Painel.php')
    arestas = [{'de': 'app/Painel.php', 'para': 'app/CadastroService.php'}]
    # Act
    fatia = fx.recortar(a, arestas, 'cadastro')
    # Assert
    assert fatia['usada_por'] == 1
    assert fatia['alcance'] == []
    assert 'app/Painel.php' not in fatia['nucleo']


def test_nucleo_grande_demais_e_declarado_area():
    """O termo mais largo do projeto medido pegava 148 de 760 arquivos. Dizer
    isso vale mais que entregar o recorte chamando-o de funcionalidade."""
    # Arrange — três arquivos, com teto dois
    a = arvore(*[f'app/entidade/A{i}.php' for i in range(3)])
    # Act
    fatia = fx.recortar(a, [], 'entidade', teto_nucleo=2)
    # Assert
    assert fatia['eh_area'] is True


def test_nucleo_do_tamanho_do_teto_ainda_e_funcionalidade():
    # Arrange
    a = arvore(*[f'app/cadastro/A{i}.php' for i in range(2)])
    # Act / Assert
    assert fx.recortar(a, [], 'cadastro', teto_nucleo=2)['eh_area'] is False


def test_o_teto_de_nucleo_padrao_e_o_que_vale_sem_pedir_outro():
    # Arrange
    a = arvore(*[f'app/entidade/A{i}.php' for i in range(fx.TETO_NUCLEO + 1)])
    # Act / Assert
    assert fx.recortar(a, [], 'entidade')['eh_area'] is True


# ───────────────────────── o recorte como objeto ────────────────────────────

def test_o_recorte_de_funcionalidade_contem_os_tres_grupos():
    # Arrange
    fatia = {'termo': 'signup', 'nucleo': ['a.php'], 'alcance': ['b.php'],
             'compartilhado': [{'caminho': 'c.php', 'importadores': 30}],
             'usada_por': 2, 'eh_area': False}
    # Act
    r = mod_recorte.por_funcionalidade(fatia)
    # Assert
    assert 'a.php' in r and 'b.php' in r and 'c.php' in r
    assert 'd.php' not in r
    assert r.parcial is True


def test_o_recorte_do_projeto_inteiro_nao_e_parcial():
    # Act
    r = mod_recorte.tudo()
    # Assert
    assert r.parcial is False
    assert 'qualquer/coisa.py' in r
    assert mod_recorte.frase(r.como_escopo(10)) is None


def test_a_frase_do_recorte_diz_o_que_e():
    # Act / Assert
    assert mod_recorte.frase(mod_recorte.por_area('src/app').como_escopo(9)) == (
        'src/app', 'a área', 9)
    fatia = {'termo': 'signup', 'nucleo': [], 'alcance': [], 'compartilhado': [],
             'usada_por': 0, 'eh_area': False}
    assert mod_recorte.frase(mod_recorte.por_funcionalidade(fatia).como_escopo(58)) == (
        'signup', 'a funcionalidade', 58)


# ───────────────────────── a CLI, de ponta a ponta ──────────────────────────

def varrer(*args):
    return subprocess.run(
        [sys.executable, str(RAIZ_SKILL / 'scripts' / 'varrer.py'),
         '--projeto', str(FIXTURES / 'acoplamento_invisivel'), *args],
        capture_output=True, text=True)


def test_o_menu_de_funcionalidades_sai_em_json():
    # Act
    r = varrer('--funcionalidades')
    # Assert
    assert r.returncode == 0, r.stderr
    dados = json.loads(r.stdout)
    assert 'funcionalidades' in dados and 'criterio' in dados


def test_termo_sem_nenhum_arquivo_para_com_motivo_e_sem_traceback(tmp_path):
    # Act
    r = varrer('--funcionalidade', 'inexistente', '--out', str(tmp_path))
    # Assert
    assert r.returncode == 2
    assert '--funcionalidades' in r.stderr
    assert 'Traceback' not in r.stderr


def test_os_dois_recortes_juntos_sao_recusados(tmp_path):
    """Área e funcionalidade são dois recortes; aceitar os dois silenciosamente
    aplicaria um e descartaria o outro."""
    # Act
    r = varrer('--area', 'app', '--funcionalidade', 'user', '--out', str(tmp_path))
    # Assert
    assert r.returncode == 2
    assert 'Traceback' not in r.stderr


def test_o_inventario_declara_a_fatia(tmp_path):
    # Act
    r = varrer('--funcionalidade', 'user', '--out', str(tmp_path))
    # Assert
    assert r.returncode == 0, r.stderr
    escopo = json.loads((tmp_path / 'inventory.json').read_text())['escopo']
    assert escopo['tipo'] == 'funcionalidade'
    assert escopo['funcionalidade'] == 'user'
    assert escopo['area'] is None
    assert escopo['nucleo'] >= 1


# ───────────────────────── os três ramos do bloco da fatia ──────────────────
# Achados rodando num framework de 46 arquivos nunca visto, com a suíte verde:
# a frase do bloco foi escrita supondo número positivo, e com zero ela dizia
# "**0** arquivos a mais o núcleo importa, e quase ninguém de fora usa".

from lib.pagina import bloco_fatia  # noqa: E402


def _escopo(alcance=0, compartilhado=(), nucleo=3, usada_por=0, eh_area=False):
    return {'escopo': {'tipo': 'funcionalidade', 'funcionalidade': 'cadastro',
                       'nucleo': nucleo, 'alcance': alcance, 'usada_por': usada_por,
                       'compartilhado': list(compartilhado), 'eh_area': eh_area,
                       'n_arquivos': nucleo + alcance}}


def test_nucleo_que_nao_importa_nada_diz_isso_em_vez_de_zero():
    # Act
    html = bloco_fatia(_escopo(alcance=0, compartilhado=[]))
    # Assert
    assert 'não importa nada fora de si' in html
    assert 'compartilhado com o resto' not in html


def test_quando_tudo_que_a_fatia_importa_e_compartilhado_o_bloco_diz():
    # Act
    html = bloco_fatia(_escopo(alcance=0, compartilhado=[
        {'caminho': 'app/Helper.php', 'importadores': 30}]))
    # Assert
    assert 'não importa nada fora de si' not in html
    assert 'app/Helper.php' in html


def test_fatia_com_alcance_e_sem_compartilhado_nega_o_compartilhamento():
    # Act
    html = bloco_fatia(_escopo(alcance=4, compartilhado=[]))
    # Assert
    assert 'Nada do que a fatia importa é compartilhado' in html
    assert 'não importa nada fora de si' not in html


def test_o_bloco_nao_sai_fora_de_uma_rodada_por_funcionalidade():
    # Act / Assert
    assert bloco_fatia({'escopo': {'tipo': 'area', 'area': 'src/app'}}) == ''
    assert bloco_fatia({}) == ''
