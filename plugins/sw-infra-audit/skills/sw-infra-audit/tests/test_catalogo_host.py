import pytest

from lib import catalogo_host

CHAVES = {"usuario", "kernel", "sistema", "disco", "memoria", "carga", "cpus", "boot",
          "servicos", "portas", "containers", "processos"}


def test_o_catalogo_da_skill_traz_todos_os_comandos_e_a_lista_ignorar():
    catalogo = catalogo_host.carregar()
    assert set(catalogo["comandos"]) == CHAVES
    assert "sshd" in catalogo["ignorar"]


@pytest.mark.parametrize("ruim", ["ls %SELETOR%", "id -un; reboot", "cat a | sh", "echo $(id)",
                                  "cat `x`", "id > /tmp/a", "id &", "id\nreboot"])
def test_comando_com_vaga_ou_metacaractere_e_recusado(tmp_path, ruim):
    caminho = tmp_path / "linux.toml"
    caminho.write_text(f'ignorar = []\n[comando]\nusuario = {ruim!r}\n'.replace("'", '"'),
                       encoding="utf-8")
    with pytest.raises(catalogo_host.CatalogoInvalido):
        catalogo_host.carregar(caminho)


def test_comandos_permitidos_sao_exatamente_os_textos_do_catalogo():
    permitidos = catalogo_host.comandos_permitidos()
    assert "id -un" in permitidos and "id -un; reboot" not in permitidos
