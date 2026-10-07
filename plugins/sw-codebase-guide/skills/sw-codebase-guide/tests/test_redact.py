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
