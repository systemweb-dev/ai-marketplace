"""O julgamento: a única parte da skill que opina.

Cada teste guarda a mesma coisa — que a opinião nasce de número medido e limiar
escrito, e não de palpite com cara de medida.
"""
from datetime import datetime, timedelta, timezone

from lib import julgar

BALDES = ('relativos', 'externos', 'sufixo_unico', 'base_provada', 'config_conferida',
          'ambiguos', 'pendurados', 'nao_resolvidos')


def contagem(**v):
    return {**dict.fromkeys(BALDES, 0), **v}


def inventario(arestas=(), arvore=(), resolucao=None, superficie=(), caminhos=None,
               ambiente=None):
    caminhos = caminhos if caminhos is not None else [a['caminho'] for a in arvore]
    return {
        'imports': {'arestas': list(arestas), 'indisponivel': [], 'barris': [],
                    'resolucao': resolucao or {'js': contagem(relativos=10)}},
        'arvore': list(arvore), 'caminhos_do_projeto': caminhos,
        'superficie': list(superficie), 'ambiente': ambiente or {},
        'historia': {'co_mudanca': []}, 'retrato': {}, 'stacks': [],
    }


def arquivo(caminho, gerado=False):
    return {'caminho': caminho, 'bytes': 10, 'linguagem': 'typescript',
            'gerado': gerado, 'acima_do_teto': False}


def test_perigo_exige_os_TRES_sinais_juntos():
    """Isoladamente nenhum diz nada: arquivo muito importado pode estar estável há
    anos, e arquivo que muda toda semana pode não ter dependente nenhum. É a
    coincidência que descreve perigo."""
    # Arrange — `quente.ts` tem dependentes e churn; `estavel.ts` só dependentes
    arestas = [{'de': f'src/t{i}.ts', 'para': 'src/quente.ts', 'origem': 'relativo'}
               for i in range(6)]
    arestas += [{'de': f'src/t{i}.ts', 'para': 'src/estavel.ts', 'origem': 'relativo'}
                for i in range(6)]
    por_arquivo = {'src/quente.ts': {'commits': 20, 'ultima': '2026-01-01T00:00:00+00:00'},
                   'src/estavel.ts': {'commits': 2, 'ultima': '2026-01-01T00:00:00+00:00'}}
    # Act
    achados = {a['caminho'] for a in julgar.onde_e_perigoso(inventario(arestas),
                                                            por_arquivo)}
    # Assert
    assert achados == {'src/quente.ts'}


def test_arquivo_com_teste_do_mesmo_nome_sai_da_lista():
    """Ter rede muda o risco de mexer, e é por isso que o terceiro sinal existe."""
    # Arrange
    arestas = [{'de': f'src/t{i}.ts', 'para': 'src/servico.ts', 'origem': 'relativo'}
               for i in range(6)]
    por_arquivo = {'src/servico.ts': {'commits': 20, 'ultima': '2026-01-01T00:00:00+00:00'}}
    inv = inventario(arestas, caminhos=['src/servico.ts', 'tests/servico.test.ts'])
    # Act / Assert
    assert julgar.onde_e_perigoso(inv, por_arquivo) == []


def test_teste_de_OUTRA_linguagem_nao_conta_como_rede():
    """Num monorepo medido, um `creator.test.js` do painel Vue dava "tem teste" para
    o `Creator.php` da API — e isso zerava a lista inteira do projeto."""
    # Arrange
    arestas = [{'de': f'api/t{i}.php', 'para': 'api/Creator.php', 'origem': 'relativo'}
               for i in range(6)]
    por_arquivo = {'api/Creator.php': {'commits': 20, 'ultima': '2026-01-01T00:00:00+00:00'}}
    inv = inventario(arestas, caminhos=['api/Creator.php', 'admin/creator.test.js'])
    # Act / Assert
    assert [a['caminho'] for a in julgar.onde_e_perigoso(inv, por_arquivo)] \
        == ['api/Creator.php']


def test_sem_alcance_so_vale_acima_do_piso_de_resolucao():
    """Abaixo do piso, metade do grafo está faltando — e dizer "ninguém usa isto"
    sobre metade de um grafo é a afirmação mais perigosa que a skill poderia fazer."""
    # Arrange — 40% resolvido
    velho = (datetime.now(timezone.utc) - timedelta(days=800)).isoformat()
    inv = inventario(arvore=[arquivo('src/sozinho.ts')],
                     resolucao={'js': contagem(relativos=4, nao_resolvidos=6)})
    # Act / Assert
    assert julgar.sem_alcance(inv, {'src/sozinho.ts': velho}) == []


def test_sem_alcance_aponta_o_arquivo_parado_e_sem_import():
    # Arrange
    velho = (datetime.now(timezone.utc) - timedelta(days=800)).isoformat()
    novo = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    inv = inventario(arvore=[arquivo('src/sozinho.ts'), arquivo('src/recente.ts')])
    # Act
    achados = julgar.sem_alcance(inv, {'src/sozinho.ts': velho, 'src/recente.ts': novo})
    # Assert — o recente não entra: projeto em andamento não é abandono
    assert [a['caminho'] for a in achados] == ['src/sozinho.ts']


def test_papel_instanciado_pelo_framework_fica_de_fora():
    """No framework da casa a rota escolhe o controller por STRING: nenhum import
    aponta para ele, e isso não diz nada sobre ele estar vivo. Num projeto real o
    terceiro candidato a morto era um controller — e lista cheia de controller é
    pior que lista nenhuma."""
    # Arrange
    velho = (datetime.now(timezone.utc) - timedelta(days=800)).isoformat()
    inv = inventario(arvore=[arquivo('app/PlatformActionController.ts'),
                             arquivo('app/CorsMiddleware.ts'),
                             arquivo('app/calculo.ts')])
    datas = {a['caminho']: velho for a in inv['arvore']}
    # Act / Assert
    assert [a['caminho'] for a in julgar.sem_alcance(inv, datas)] == ['app/calculo.ts']


def test_o_que_a_superficie_reconheceu_fica_de_fora():
    """Rota, job e migration são alcançados de fora do código, por desenho."""
    # Arrange
    velho = (datetime.now(timezone.utc) - timedelta(days=800)).isoformat()
    inv = inventario(arvore=[arquivo('jobs/enviar.ts'), arquivo('app/calculo.ts')],
                     superficie=[{'caminho': 'jobs/enviar.ts', 'tipo': 'job',
                                  'por': 'jobs/'}])
    datas = {a['caminho']: velho for a in inv['arvore']}
    # Act / Assert
    assert [a['caminho'] for a in julgar.sem_alcance(inv, datas)] == ['app/calculo.ts']


def test_env_versionado_e_achado_e_env_no_disco_nao():
    """`.env` no disco é normal; `.env` VERSIONADO é credencial publicada. A
    diferença entre as duas é uma consulta ao git — sem ela o achado vira palpite
    com cara de alerta."""
    # Arrange
    inv = inventario(ambiente={'api/.env': ['DB_PASSWORD'], 'web/.env': ['TOKEN']})
    # Act
    achados = julgar.risco_visivel(inv, rastreados={'api/.env'})
    # Assert
    assert [r['onde'] for r in achados] == ['api/.env']


def test_credencial_que_o_exemplo_nao_declara_vira_achado():
    """Quem sobe o ambiente pela primeira vez não tem como saber que precisa dela."""
    # Arrange
    inv = inventario(ambiente={'.env.example': ['APP_URL'],
                               '.env': ['APP_URL', 'STRIPE_SECRET_KEY']})
    # Act
    achados = julgar.risco_visivel(inv, rastreados=set())
    # Assert
    assert len(achados) == 1
    assert 'STRIPE_SECRET_KEY' in achados[0]['o_que']
    assert '1 variável ' in achados[0]['o_que'], 'plural de um só'


def test_o_dossie_diz_o_que_falta_em_vez_de_dar_veredito():
    """A skill não responde "vale manter": a resposta depende de custo de reescrita
    e de dependência do negócio, e o código não contém nenhum dos dois. Dizer isso
    por escrito é o que separa a recusa honesta da omissão."""
    # Arrange
    inv = inventario(arvore=[arquivo('a.ts')])
    inv['retrato'] = {'autores': 2, 'commits': 50, 'semanas_de_vida': 30,
                      'semanas_parado': 1}
    # Act
    d = julgar.dossie_de_decisao(inv)
    # Assert
    assert d['autores'] == 2
    assert 'custa reescrever' in d['falta']
