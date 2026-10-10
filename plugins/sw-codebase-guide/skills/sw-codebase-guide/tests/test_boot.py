"""Como rodar isto — a pergunta que a seção "Como entrar" não respondia.

A seção emitia stack, contagem de arquivos e nomes de variáveis de ambiente, e
nenhum **comando**. Medido em sete projetos reais: 6 arquivos de composição, 17
Dockerfiles, 7 `package.json` e 5 `composer.json` — e o `composer.json` de todo
projeto PHP da casa declara `start`. Estava tudo lá, e o documento calava.
"""
import json

from lib.boot import apurar
from lib.tree import varrer

COMPOSE = '''name: exemplo
services:
  backend:
    build:
      context: .
    depends_on:
      - banco
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "${PORTA_TLS}:443"
  banco:
    image: mariadb:11
networks:
  interna:
'''


def _apurar(raiz):
    return apurar(raiz, varrer(raiz))


# ───────────────────────────── composição ────────────────────────────────────


def test_le_os_servicos_na_ordem_do_arquivo(tmp_path):
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(COMPOSE)
    # Act
    r = _apurar(tmp_path)
    # Assert
    assert [s['nome'] for s in r['composicoes'][0]['servicos']] == \
        ['backend', 'nginx', 'banco']


def test_a_porta_publicada_sai_como_declarada(tmp_path):
    """`${PORTA_TLS}:443` fica como está: inventar o valor seria mentir, e a
    variável sem valor é justamente o que falta declarar para subir."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(COMPOSE)
    # Act
    por_nome = {s['nome']: s for s in _apurar(tmp_path)['composicoes'][0]['servicos']}
    # Assert
    assert por_nome['nginx']['portas'] == ['80:80', '${PORTA_TLS}:443']
    assert por_nome['banco']['portas'] == []


def test_imagem_ou_build_dizem_de_onde_o_servico_vem(tmp_path):
    """Quem lê precisa saber se vai baixar imagem ou construir na máquina."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(COMPOSE)
    # Act
    por_nome = {s['nome']: s for s in _apurar(tmp_path)['composicoes'][0]['servicos']}
    # Assert
    assert por_nome['nginx']['imagem'] == 'nginx:latest'
    assert por_nome['backend']['imagem'] is None
    assert por_nome['backend']['constroi'] is True


def test_chave_de_compose_nunca_entra_como_servico(tmp_path):
    """Ler o nível errado devolveria `image` e `ports` como se fossem serviço. É a
    invariante da casa: aresta errada é pior que aresta faltando — aqui, um serviço
    inventado manda alguém subir o que não existe."""
    # Arrange — recuo de quatro espaços, que é estilo legítimo de YAML
    (tmp_path / 'compose.yaml').write_text(
        'services:\n'
        '    web:\n'
        '        image: nginx\n'
        '        ports:\n'
        '            - "8080:80"\n')
    # Act
    servicos = [s['nome'] for s in _apurar(tmp_path)['composicoes'][0]['servicos']]
    # Assert
    assert servicos == ['web']


def test_dois_arquivos_de_composicao_aparecem_os_dois(tmp_path):
    """Medido: um monorepo real tem `infra/` e `infra_v2/`. Qual é o
    atual não está no código, e escolher por conta própria seria inventar."""
    # Arrange
    for pasta in ('infra', 'infra_v2'):
        (tmp_path / pasta).mkdir()
        (tmp_path / pasta / 'docker-compose.yml').write_text(COMPOSE)
    # Act
    r = _apurar(tmp_path)
    # Assert
    assert len(r['composicoes']) == 2
    assert [c['caminho'] for c in r['composicoes']] == \
        ['infra/docker-compose.yml', 'infra_v2/docker-compose.yml']


def test_compose_dentro_de_docs_nao_conta(tmp_path):
    """Medido num projeto real: `docs/registros/.../docker-compose.yml` é anexo de
    um relatório, não o jeito de subir o sistema. Mesma regra que exclui o dossiê
    de trabalho das fontes textuais."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(COMPOSE)
    (tmp_path / 'docs' / 'registros').mkdir(parents=True)
    (tmp_path / 'docs' / 'registros' / 'docker-compose.yml').write_text(COMPOSE)
    # Act
    r = _apurar(tmp_path)
    # Assert
    assert [c['caminho'] for c in r['composicoes']] == ['docker-compose.yml']


def test_mais_de_um_documento_yaml_vira_lacuna_com_motivo(tmp_path):
    """Não apurado ≠ não existe: o leitor por indentação não modela dois documentos
    no mesmo arquivo, e dizer isso vale mais que devolver metade da lista."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(COMPOSE + '---\nservices:\n  outro:\n')
    # Act
    c = _apurar(tmp_path)['composicoes'][0]
    # Assert
    assert c['servicos'] == []
    assert 'documento' in c['lacuna']


def test_sem_bloco_services_vira_lacuna(tmp_path):
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text('version: "3"\nvolumes:\n  dados:\n')
    # Act
    c = _apurar(tmp_path)['composicoes'][0]
    # Assert
    assert c['servicos'] == [] and c['lacuna']


def test_teto_de_servicos_diz_quantos_ficaram_de_fora(tmp_path):
    """Medido: um compose real tem 17 serviços. A lista inteira afoga o leitor; o
    teto sem o número omitido mente por omissão."""
    # Arrange
    corpo = 'services:\n' + ''.join(f'  s{i:02d}:\n    image: x\n' for i in range(9))
    (tmp_path / 'docker-compose.yml').write_text(corpo)
    # Act — o teto vem por parâmetro: a fixture nunca é dimensionada pela
    # constante de produção, senão uma mutação do teto a dimensiona junto
    c = apurar(tmp_path, varrer(tmp_path), teto_servicos=4)['composicoes'][0]
    # Assert
    assert len(c['servicos']) == 4
    assert c['omitidos'] == 5


# ───────────────────────────── comandos ──────────────────────────────────────


def test_scripts_do_manifesto_com_o_gerenciador_do_lockfile(tmp_path):
    """`npm run` num repositório `pnpm` quebra a instalação de quem acabou de
    chegar. O lockfile é fato medido; sem ele, `npm` é dedução."""
    # Arrange
    (tmp_path / 'package.json').write_text(json.dumps(
        {'scripts': {'dev': 'vite', 'build': 'vite build'}}))
    (tmp_path / 'pnpm-lock.yaml').write_text('lockfileVersion: 9\n')
    # Act
    c = _apurar(tmp_path)['comandos'][0]
    # Assert
    assert c['executor'] == 'pnpm run'
    assert c['por'] == 'pnpm-lock.yaml'
    assert c['scripts'] == ['build', 'dev']


def test_sem_lockfile_o_gerenciador_e_suposto_e_o_documento_diz(tmp_path):
    # Arrange
    (tmp_path / 'package.json').write_text(json.dumps({'scripts': {'dev': 'vite'}}))
    # Act
    c = _apurar(tmp_path)['comandos'][0]
    # Assert
    assert c['executor'] == 'npm run'
    assert c['por'] is None, 'sem lockfile não há medida; o emissor marca como dedução'


def test_scripts_do_composer_entram_igual(tmp_path):
    """Medido: o `composer.json` de cinco projetos PHP declara `start` — o comando
    que sobe a aplicação, e que o documento não mostrava."""
    # Arrange
    (tmp_path / 'composer.json').write_text(json.dumps(
        {'scripts': {'start': 'php -S localhost:8000', 'test': 'phpunit'}}))
    (tmp_path / 'composer.lock').write_text('{}')
    # Act
    c = _apurar(tmp_path)['comandos'][0]
    # Assert
    assert c['executor'] == 'composer run'
    assert c['scripts'] == ['start', 'test']


def test_o_que_parece_subir_sai_separado_do_resto(tmp_path):
    """`start`, `dev`, `serve` e `up` são convenção — indício, não prova. Sai como
    dedução, e o resto da lista continua inteiro para quem discordar."""
    # Arrange
    (tmp_path / 'package.json').write_text(json.dumps({'scripts': {
        'dev': 'x', 'build': 'x', 'test': 'x', 'serve': 'x', 'lint': 'x'}}))
    # Act
    c = _apurar(tmp_path)['comandos'][0]
    # Assert
    assert c['candidatos'] == ['dev', 'serve']


def test_manifesto_sem_scripts_nao_entra(tmp_path):
    """Nada a dizer é nada a imprimir — a seção não ganha uma linha vazia."""
    # Arrange
    (tmp_path / 'package.json').write_text(json.dumps({'name': 'x'}))
    # Act / Assert
    assert _apurar(tmp_path)['comandos'] == []


def test_manifesto_quebrado_vira_lacuna_e_nao_estoura(tmp_path):
    # Arrange
    (tmp_path / 'package.json').write_text('{isto não é json')
    # Act
    c = _apurar(tmp_path)['comandos'][0]
    # Assert
    assert c['scripts'] == [] and c['lacuna']


# ───────────────────────── Makefile e Dockerfile ─────────────────────────────


def test_alvos_do_makefile_sem_confundir_com_variavel(tmp_path):
    # Arrange
    (tmp_path / 'Makefile').write_text(
        'SHELL := /bin/bash\n.PHONY: subir\n\nsubir:\n\tdocker compose up\n\n'
        'testar: subir\n\tpytest\n')
    # Act
    a = _apurar(tmp_path)['alvos'][0]
    # Assert
    assert a['executor'] == 'make'
    assert a['alvos'] == ['subir', 'testar'], 'nem `SHELL :=` nem `.PHONY` são alvo'


def test_dockerfile_e_contado_mas_nunca_vira_comando(tmp_path):
    """17 Dockerfiles em sete projetos, e nenhum diz como rodar — só que existe
    imagem para construir. Contar é fato; virar comando seria invenção."""
    # Arrange
    (tmp_path / 'Dockerfile').write_text('FROM php:8.3-fpm\n')
    (tmp_path / 'api').mkdir()
    (tmp_path / 'api' / 'Dockerfile').write_text('FROM node:20\n')
    # Act
    r = _apurar(tmp_path)
    # Assert
    assert r['containers'] == ['Dockerfile', 'api/Dockerfile']
    assert r['comandos'] == [] and r['alvos'] == []


def test_projeto_sem_nada_disso_devolve_vazio_e_nao_falha(tmp_path):
    # Arrange
    (tmp_path / 'app.py').write_text('x = 1\n')
    # Act
    r = _apurar(tmp_path)
    # Assert
    assert r == {'composicoes': [], 'comandos': [], 'alvos': [], 'containers': []}


# ──────────── o que só apareceu rodando contra projeto real ──────────────────


def test_porta_em_lista_inline_tambem_conta(tmp_path):
    """Um projeto real escreve o compose inteiro em estilo de fluxo:
    `ports: ["127.0.0.1:3307:3306"]`. O leitor só conhecia a forma em bloco e
    devolvia nenhuma porta para um serviço que publica uma — silêncio no lugar de
    um fato, que é o modo de falha que esta skill existe para evitar."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(
        'services:\n'
        '  banco:\n'
        '    image: mariadb:11.4\n'
        '    ports: ["127.0.0.1:3307:3306", "9999:9999"]\n')
    # Act
    s = _apurar(tmp_path)['composicoes'][0]['servicos'][0]
    # Assert
    assert s['portas'] == ['127.0.0.1:3307:3306', '9999:9999']


def test_servico_com_corpo_inline_nao_desaparece(tmp_path):
    """`web: {image: nginx}` numa linha só. Sumir com o serviço calado é pior que
    não ler o arquivo: a lista aparece completa e o leitor não tem como saber que
    falta um."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(
        'services:\n'
        '  web: {image: nginx, ports: ["8080:80"]}\n'
        '  fila:\n'
        '    image: rabbitmq\n')
    # Act
    servicos = _apurar(tmp_path)['composicoes'][0]['servicos']
    # Assert
    assert [s['nome'] for s in servicos] == ['web', 'fila']
    assert servicos[0]['imagem'] == 'nginx'
    assert servicos[0]['portas'] == ['8080:80']


def test_o_valor_do_environment_nunca_e_lido(tmp_path):
    """Medido num compose real: `environment: { SENHA_DO_BANCO: <valor literal> }`.
    Senha literal, em linha. Este módulo não abre o bloco — nem para pegar nomes —
    e é isso que mantém a superfície de segredo dele em zero. A seção `ambiente`
    extrai chave de `.env` na origem, que é o lugar certo."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(
        'services:\n'
        '  banco:\n'
        '    image: mariadb\n'
        '    environment: { SENHA_DO_BANCO: senha-literal }\n')
    # Act
    r = _apurar(tmp_path)
    # Assert
    assert 'senha-literal' not in json.dumps(r)
    assert 'SENHA_DO_BANCO' not in json.dumps(r)


def test_o_dev_escondido_no_nome_composto_conta(tmp_path):
    """`webpack_dev` aparece em três projetos reais e a convenção não o pegava,
    porque comparava o nome inteiro. A comparação é por PARTE do nome."""
    # Arrange
    (tmp_path / 'package.json').write_text(json.dumps({'scripts': {
        'webpack_dev': 'x', 'webpack_build': 'x', 'db:up': 'x', 'db:migrar': 'x'}}))
    # Act
    c = _apurar(tmp_path)['comandos'][0]
    # Assert — `db:up` NÃO entra: `up` saiu da convenção justamente por isso.
    # Subir o banco não é subir a aplicação, e o palpite errado custa mais que o
    # silêncio, porque a lista inteira está logo ao lado.
    assert c['candidatos'] == ['webpack_dev']


def test_chave_de_topo_indentada_por_engano_nao_vira_servico(tmp_path):
    """O erro de edição mais comum em YAML à mão: `volumes:` ganha dois espaços e
    cai dentro de `services:`. O leitor por indentação não tem como saber que
    aquilo não é serviço — a lista de chaves de compose é o que o impede de
    inventar um serviço chamado `volumes`, que mandaria alguém subir o que não
    existe. Esta mutação escapou da suíte antes deste teste existir."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(
        'services:\n'
        '  web:\n'
        '    image: nginx\n'
        '  volumes:\n'
        '    dados:\n')
    # Act
    servicos = [s['nome'] for s in _apurar(tmp_path)['composicoes'][0]['servicos']]
    # Assert
    assert servicos == ['web']


def test_campo_de_extensao_nao_vira_servico(tmp_path):
    """`x-comum: &comum` dentro de `services:` é idioma de compose para compartilhar
    configuração entre serviços — e tem a mesma forma de um serviço. A convenção do
    próprio formato é o prefixo `x-`."""
    # Arrange
    (tmp_path / 'docker-compose.yml').write_text(
        'services:\n'
        '  x-comum: &comum\n'
        '    restart: always\n'
        '  web:\n'
        '    <<: *comum\n'
        '    image: nginx\n')
    # Act
    servicos = [s['nome'] for s in _apurar(tmp_path)['composicoes'][0]['servicos']]
    # Assert
    assert servicos == ['web']


def test_o_teto_PADRAO_nao_corta_um_compose_real(tmp_path):
    """O teto vive em `TETO_SERVICOS`, e o teste do teto passa o valor por
    parâmetro — então ele prova o mecanismo e **não** prova que o padrão serve.
    Com 12, um compose real de 17 serviços perdia `scheduler`, `frontend_app` e
    `website`: o relógio do sistema e as duas superfícies que servem o produto.
    Este teste fixa o tamanho que o mundo real tem, não o da constante."""
    # Arrange — 17 serviços, que é o maior medido em sete projetos
    corpo = 'services:\n' + ''.join(f'  s{i:02d}:\n    image: x\n' for i in range(17))
    (tmp_path / 'docker-compose.yml').write_text(corpo)
    # Act — sem passar teto: o padrão de produção é o que está sob teste
    c = _apurar(tmp_path)['composicoes'][0]
    # Assert
    assert c['omitidos'] == 0, 'o teto padrão corta um compose de tamanho real'
    assert len(c['servicos']) == 17
