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


# ─── Convenções reais que o plano não enumerou. O dicionário guarda trecho em
#     minúsculas, e o caminho real vem com maiúsculas (`app/Http/Controllers`):
#     se a normalização falhar, o projeto Laravel inteiro sai sem superfície.

def test_reconhece_convencoes_de_outras_stacks(tmp_path):
    # Arrange — uma estrutura real de cada stack, com a grafia que ela usa de verdade
    esperado = {
        'src/app/api/route.ts': 'rota',                        # Next.js App Router
        'app/Http/Controllers/PedidoController.php': 'rota',   # Laravel
        'database/migrations/2024_01_01_cria_pedidos.php': 'migration',
        'app/Console/Commands/Limpar.php': 'comando',
    }
    for relativo in esperado:
        alvo = tmp_path / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text('x')
    # Act
    visto = {i['caminho']: i['tipo'] for i in detectar(tmp_path)}
    # Assert — maiúsculas no caminho real não atrapalham: a comparação é minúscula
    assert visto == esperado


def test_convencao_de_dois_trechos_alcanca_subpasta(tmp_path):
    # Arrange — este teste nasceu documentando o LIMITE oposto: trecho com barra
    # (`app/api`, `app/jobs`) só casava com o arquivo DIRETO na pasta, e um projeto
    # Next.js real saía sem superfície nenhuma. Virou regressão do conserto.
    for relativo in ('src/app/api/pedidos/route.ts', 'pages/api/v1/pedidos.ts',
                     'app/Jobs/Email/Enviar.php'):
        alvo = tmp_path / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text('x')
    (tmp_path / 'routes' / 'v1').mkdir(parents=True)
    (tmp_path / 'routes' / 'v1' / 'web.php').write_text('<?php')
    # Act
    visto = {i['caminho'] for i in detectar(tmp_path)}
    # Assert
    assert visto == {'routes/v1/web.php', 'src/app/api/pedidos/route.ts',
                     'pages/api/v1/pedidos.ts', 'app/Jobs/Email/Enviar.php'}


def test_nome_parecido_nao_vira_superficie(tmp_path):
    # Arrange — `routes-helper` é utilitário e `controllers.md` é documentação:
    # tratar os dois como superfície pública enche a seção 4 de ruído
    (tmp_path / 'src' / 'routes-helper').mkdir(parents=True)
    (tmp_path / 'src' / 'routes-helper' / 'juntar.js').write_text('x')
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'controllers.md').write_text('# controllers')
    # Act / Assert
    assert detectar(tmp_path) == []


def test_rota_aninhada_do_next_app_router(tmp_path):
    # Arrange — um projeto Next.js real devolvia NADA de superfície: o trecho com
    # barra só casava se o arquivo estivesse direto na pasta
    (tmp_path / 'src' / 'app' / 'api' / 'usuarios').mkdir(parents=True)
    (tmp_path / 'src' / 'app' / 'api' / 'usuarios' / 'route.ts').write_text('export {}')
    # Act
    achados = detectar(tmp_path)
    # Assert
    assert [i['tipo'] for i in achados] == ['rota']
    assert achados[0]['caminho'] == 'src/app/api/usuarios/route.ts'


def test_jobs_fora_da_pasta_app(tmp_path):
    # Arrange — `api/jobs/` escapava porque a convenção exigia `app/jobs`
    (tmp_path / 'api' / 'jobs').mkdir(parents=True)
    (tmp_path / 'api' / 'jobs' / 'Enviar.php').write_text('<?php')
    # Act / Assert
    assert [i['tipo'] for i in detectar(tmp_path)] == ['job']


def test_fronteira_de_segmento_evita_falso_positivo(tmp_path):
    # Arrange — `routes-helper` não é `routes`
    (tmp_path / 'src' / 'routes-helper').mkdir(parents=True)
    (tmp_path / 'src' / 'routes-helper' / 'util.ts').write_text('export {}')
    (tmp_path / 'src' / 'jobs-ui').mkdir(parents=True)
    (tmp_path / 'src' / 'jobs-ui' / 'tela.tsx').write_text('export {}')
    # Act / Assert
    assert detectar(tmp_path) == []
