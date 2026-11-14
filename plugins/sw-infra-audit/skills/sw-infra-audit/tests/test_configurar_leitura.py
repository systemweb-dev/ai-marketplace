# tests/test_configurar_leitura.py
import difflib

import pytest

import configurar
from lib import alvos
from lib import gravacao_alvos as g

TEXTO = ('# meus alvos\n[[alvo]]\nnome = "banco-01"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
         '\n# descoberto em 2026-11-13\n[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\n'
         'produto = "mariadb"\nportas = [3306]\norigem = "unidade:mariadb.service"\n'
         '\n[[alvo.componente]]\nnome = "qdrant"\npapel = "busca"\nproduto = "qdrant"\n'
         'portas = [6333]\norigem = "unidade:qdrant.service"\n'
         '\n[[alvo]]\nnome = "srv-exemplo"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
         '[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\nproduto = "mariadb"\n'
         'origem = "unidade:mariadb.service"\n')
SENHA = ["--modo", "senha", "--usuario", "leitor", "--senha-env", "SENHA_BANCO_01"]


def _arquivo(tmp_path):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(TEXTO, encoding="utf-8")
    caminho.chmod(0o600)
    return caminho


def _leitura(caminho, *extra, componente="mariadb", alvo="banco-01"):
    return configurar.main(["leitura", "--alvo", alvo, "--componente", componente, *extra,
                            "--infra", str(caminho)])


def test_acrescenta_logo_depois_do_nome_do_componente_certo_e_so_acrescenta():
    novo = g.acrescentar_campos(TEXTO, "banco-01", "mariadb", [("leitura", "socket"),
                                                               ("backup_max_dias", 7)])
    diff = [l for l in difflib.ndiff(TEXTO.splitlines(), novo.splitlines()) if l[:1] in "+-"]
    assert diff == ['+ leitura = "socket"', "+ backup_max_dias = 7"]
    assert novo.index('leitura = "socket"') < novo.index('nome = "qdrant"')


def test_componente_ou_alvo_inexistente_e_recusado():
    with pytest.raises(g.GravacaoInvalida, match="componente 'redis' não encontrado"):
        g.acrescentar_campos(TEXTO, "banco-01", "redis", [("leitura", "socket")])
    with pytest.raises(g.GravacaoInvalida, match="alvo 'nao-existe' não encontrado"):
        g.acrescentar_campos(TEXTO, "nao-existe", "mariadb", [("leitura", "socket")])


def test_campo_que_ja_existe_e_recusado():
    com_leitura = g.acrescentar_campos(TEXTO, "banco-01", "mariadb", [("leitura", "socket")])
    with pytest.raises(g.GravacaoInvalida, match="edite o alvos.toml à mão"):
        g.acrescentar_campos(com_leitura, "banco-01", "mariadb", [("leitura", "nenhum")])


@pytest.mark.parametrize("valor", ['a"b', "a\nb", "a b", "a\\b"])
def test_valor_fora_do_formato_nao_vira_toml(valor):
    with pytest.raises(g.GravacaoInvalida, match="fora do formato gravável"):
        g.acrescentar_campos(TEXTO, "banco-01", "mariadb", [("usuario", valor)])


def test_gravar_pelo_cli_deixa_o_bak_e_o_arquivo_relido(tmp_path):
    caminho = _arquivo(tmp_path)
    codigo = _leitura(caminho, *SENHA, "--backup-pasta", "/var/backups/mysql",
                      "--backup-max-dias", "7")
    texto = caminho.read_text(encoding="utf-8")
    assert codigo == 0
    assert ('nome = "mariadb"\nleitura = "senha"\nusuario = "leitor"\nsenha_env = "SENHA_BANCO_01"\n'
            'backup_pasta = "/var/backups/mysql"\nbackup_max_dias = 7\npapel = "banco"\n') in texto
    assert texto.endswith('[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\n'
                          'produto = "mariadb"\norigem = "unidade:mariadb.service"\n')
    assert (tmp_path / "alvos.toml.bak").read_text(encoding="utf-8") == TEXTO
    componente = alvos.ler(caminho)[0][0]["componente"][0]
    assert (componente["leitura"], componente["backup_max_dias"]) == ("senha", 7)


def test_segunda_gravacao_e_recusada_e_nao_muda_nada(tmp_path, capsys):
    caminho = _arquivo(tmp_path)
    assert _leitura(caminho, "--modo", "socket") == 0
    gravado = caminho.read_text(encoding="utf-8")
    assert _leitura(caminho, "--modo", "nenhum") == 2
    assert caminho.read_text(encoding="utf-8") == gravado
    assert "já tem leitura" in capsys.readouterr().err


@pytest.mark.parametrize("extra,mensagem", [
    (["--modo", "senha"], "--modo senha exige --usuario e --senha-env"),
    (["--modo", "socket", "--usuario", "leitor"], "--usuario e --senha-env só valem com --modo senha"),
    (["--modo", "senha", "--usuario", "leitor", "--senha-env", "minuscula"], "--senha-env é o NOME"),
    (["--modo", "senha", "--usuario", "lei tor", "--senha-env", "S"], "--usuario só com"),
    (["--modo", "container"], "--modo container só vale"),
    (["--modo", "socket", "--backup-pasta", "/var/../etc"], "--backup-pasta precisa ser caminho absoluto"),
    (["--modo", "socket", "--backup-max-dias", "7"], "--backup-max-dias precisa de --backup-pasta"),
    (["--modo", "socket", "--backup-pasta", "/b", "--backup-max-dias", "0"], "--backup-max-dias vai de 1 a 365"),
])
def test_entrada_ruim_e_recusada_antes_de_tocar_no_arquivo(tmp_path, capsys, extra, mensagem):
    caminho = _arquivo(tmp_path)
    assert _leitura(caminho, *extra) == 2
    assert caminho.read_text(encoding="utf-8") == TEXTO
    assert not (tmp_path / "alvos.toml.bak").exists()
    assert mensagem in capsys.readouterr().err


def test_senha_em_produto_sem_cliente_com_senha_e_recusada(tmp_path, capsys):
    caminho = _arquivo(tmp_path)
    assert _leitura(caminho, *SENHA, componente="qdrant") == 2
    assert "não tem leitura com senha" in capsys.readouterr().err
    assert caminho.read_text(encoding="utf-8") == TEXTO


def test_alvo_ou_componente_inexistente_no_cli(tmp_path, capsys):
    caminho = _arquivo(tmp_path)
    assert _leitura(caminho, "--modo", "socket", componente="redis") == 2
    assert "não tem componente 'redis'" in capsys.readouterr().err


def test_releitura_que_diverge_restaura_o_original(tmp_path, monkeypatch):
    caminho = _arquivo(tmp_path)
    invasor = '\n[[alvo]]\nnome = "invasor"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
    monkeypatch.setattr(g, "acrescentar_campos", lambda texto, *a: texto + invasor)
    assert _leitura(caminho, "--modo", "socket") == 2
    assert caminho.read_text(encoding="utf-8") == TEXTO
