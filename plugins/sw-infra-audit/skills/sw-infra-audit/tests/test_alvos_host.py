# tests/test_alvos_host.py
import pytest

from lib import alvos


def _arquivo(tmp_path, corpo):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(corpo, encoding="utf-8")
    caminho.chmod(0o600)
    return caminho


def test_host_valido_carrega_com_porta_e_acesso_restrito(tmp_path):
    caminho = _arquivo(tmp_path, '[[alvo]]\nnome = "web-01"\ntipo = "host"\n'
                                 'ssh_destino = "usuario@10.0.0.10"\nporta = 2222\n'
                                 'acesso_restrito = true\n')
    lidos, _ = alvos.ler(caminho)
    assert lidos[0]["ssh_destino"] == "usuario@10.0.0.10"
    assert lidos[0]["porta"] == 2222 and lidos[0]["acesso_restrito"] is True


@pytest.mark.parametrize("destino", ["-Jevil@host", "-Fx@y", "usuario@host:2222",
                                     "usuario@host\n", "@host", "usuario@"])
def test_destino_fora_do_formato_e_recusado(tmp_path, destino):
    caminho = _arquivo(tmp_path, f'[[alvo]]\nnome = "x"\ntipo = "host"\n'
                                 f'ssh_destino = {destino!r}\n'.replace("'", '"'))
    with pytest.raises(alvos.AlvoInvalido) as erro:
        alvos.ler(caminho)
    assert "ssh_destino" in str(erro.value)


@pytest.mark.parametrize("porta", ["0", "70000", '"22"', "true"])
def test_porta_fora_da_faixa_ou_de_outro_tipo_e_recusada(tmp_path, porta):
    caminho = _arquivo(tmp_path, f'[[alvo]]\nnome = "x"\ntipo = "host"\n'
                                 f'ssh_destino = "u@h"\nporta = {porta}\n')
    with pytest.raises(alvos.AlvoInvalido, match="porta"):
        alvos.ler(caminho)


def test_acesso_restrito_precisa_ser_booleano(tmp_path):
    caminho = _arquivo(tmp_path, '[[alvo]]\nnome = "x"\ntipo = "host"\nssh_destino = "u@h"\n'
                                 'acesso_restrito = "sim"\n')
    with pytest.raises(alvos.AlvoInvalido, match="acesso_restrito"):
        alvos.ler(caminho)
