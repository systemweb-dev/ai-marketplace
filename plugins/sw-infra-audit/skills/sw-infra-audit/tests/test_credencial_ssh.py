# tests/test_credencial_ssh.py
import copy
import pickle

import pytest

from lib import credencial

COMP = {"nome": "mariadb", "leitura": "senha", "usuario": "leitor", "senha_env": "SENHA_BANCO_01"}
AMARRA = ("banco-01", "root@10.0.0.10", None, "mariadb")


def _cred(senha='a"b\\c#d', **trocas):
    return credencial.de_componente_ssh({**COMP, **trocas}, "banco-01", "root@10.0.0.10", None,
                                        ambiente={"SENHA_BANCO_01": senha})


def test_entrada_e_o_client_com_aspas_e_barra_escapadas():
    assert _cred().entrada(*AMARRA) == '[client]\nuser="leitor"\npassword="a\\"b\\\\c#d"\n'


@pytest.mark.parametrize("outra", [("prod", "root@10.0.0.10", None, "mariadb"),
                                   ("banco-01", "root@10.0.0.99", None, "mariadb"),
                                   ("banco-01", "root@10.0.0.10", 2222, "mariadb"),
                                   ("banco-01", "root@10.0.0.10", None, "postgres")])
def test_fora_da_amarracao_nao_sai_nada(outra):
    assert _cred().entrada(*outra) is None


def test_nao_se_imprime_nem_serializa():
    cred = _cred(senha="MARCA-123")
    assert "MARCA-123" not in repr(cred) and "MARCA-123" not in str(cred)
    with pytest.raises(TypeError):
        pickle.dumps(cred)
    with pytest.raises(TypeError):
        copy.deepcopy(cred)


def test_sem_leitura_senha_nao_ha_credencial():
    assert credencial.de_componente_ssh({**COMP, "leitura": "socket"}, "banco-01",
                                        "root@10.0.0.10", None, ambiente={}) is None


def test_variavel_ausente_diz_o_nome_sem_repetir_o_usuario():
    with pytest.raises(credencial.CredencialFaltando) as erro:
        credencial.de_componente_ssh(COMP, "banco-01", "root@10.0.0.10", None, ambiente={})
    assert "SENHA_BANCO_01" in str(erro.value) and "leitor" not in str(erro.value)


@pytest.mark.parametrize("senha", ["linha1\nlinha2", "a\rb", "a\0b"])
def test_senha_com_quebra_de_linha_e_recusada_sem_aparecer(senha):
    with pytest.raises(credencial.CredencialRecusada) as erro:
        _cred(senha=senha)
    assert senha not in str(erro.value)


def test_usuario_com_quebra_de_linha_tambem_e_recusado():
    with pytest.raises(credencial.CredencialRecusada):
        _cred(usuario="lei\ntor")
