# tests/test_alvos_leitura.py
import pytest

from lib import alvos

BASE = ('[[alvo]]\nnome = "banco-01"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
        '[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\nproduto = "mariadb"\n'
        'origem = "unidade:mariadb.service"\n')


def _ler(tmp_path, extra):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(BASE + extra, encoding="utf-8")
    caminho.chmod(0o600)
    return alvos.ler(caminho)[0][0]["componente"][0]


def test_leitura_e_backup_carregam(tmp_path):
    comp = _ler(tmp_path, 'leitura = "senha"\nusuario = "leitor"\nsenha_env = "SENHA_BANCO_01"\n'
                          'backup_pasta = "/var/backups/mysql"\nbackup_max_dias = 7\n')
    assert (comp["leitura"], comp["backup_pasta"], comp["backup_max_dias"]) == \
        ("senha", "/var/backups/mysql", 7)


def test_leitura_fora_da_lista_e_recusada(tmp_path):
    with pytest.raises(alvos.AlvoInvalido, match="leitura precisa ser uma de"):
        _ler(tmp_path, 'leitura = "sudo"\n')


@pytest.mark.parametrize("extra", ['leitura = "senha"\n',
                                   'leitura = "senha"\nusuario = "leitor"\n',
                                   'leitura = "senha"\nsenha_env = "SENHA_BANCO_01"\n'])
def test_leitura_senha_sem_usuario_ou_variavel_e_recusada(tmp_path, extra):
    with pytest.raises(alvos.AlvoInvalido, match="exige usuario e senha_env"):
        _ler(tmp_path, extra)


@pytest.mark.parametrize("pasta", ['"relativa/x"', '"/var/../etc"', '"/var/back ups"', "7"])
def test_pasta_de_backup_fora_do_formato_e_recusada(tmp_path, pasta):
    with pytest.raises(alvos.AlvoInvalido, match="backup_pasta precisa ser caminho absoluto"):
        _ler(tmp_path, f"backup_pasta = {pasta}\n")


@pytest.mark.parametrize("dias", ["0", "400", '"2"', "true"])
def test_dias_fora_da_faixa_e_recusado(tmp_path, dias):
    with pytest.raises(alvos.AlvoInvalido, match="backup_max_dias precisa ser inteiro de 1 a 365"):
        _ler(tmp_path, f'backup_pasta = "/var/backups"\nbackup_max_dias = {dias}\n')


def test_dias_sem_pasta_e_recusado(tmp_path):
    with pytest.raises(alvos.AlvoInvalido, match="backup_max_dias sem backup_pasta"):
        _ler(tmp_path, "backup_max_dias = 7\n")


def test_leitura_container_em_origem_de_unit_carrega(tmp_path):
    """O spec quer `sem dados` com motivo na COLETA, não recusa na leitura do arquivo."""
    assert _ler(tmp_path, 'leitura = "container"\n')["leitura"] == "container"
