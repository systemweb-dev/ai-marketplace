import pytest

from lib import catalogo_host


def test_o_catalogo_traz_os_moldes_da_camada_comum_e_o_ps_literal():
    catalogo = catalogo_host.carregar()
    assert set(catalogo["moldes"]) == {"servico_unidade", "servico_container",
                                       "memoria_container", "backup"}
    assert catalogo["moldes"]["backup"] == "ls -l --time-style=full-iso {backup_pasta}"
    assert catalogo["comandos"]["processos"] == "ps -e -o comm=,rss=,etimes="


@pytest.mark.parametrize("tabela,texto", [
    ("comando", "systemctl show {unidade}"),
    ("molde", "cat {sql}"),
    ("molde", "ls {pasta}"),
    ("molde", "id -un"),
    ("molde", "systemctl show {unidade}; id"),
])
def test_vaga_fora_do_lugar_e_recusada(tmp_path, tabela, texto):
    base = 'ignorar = []\n[comando]\nusuario = "id -un"\n'
    corpo = (f'ignorar = []\n[comando]\nusuario = "{texto}"\n' if tabela == "comando"
             else f'{base}[molde]\nx = "{texto}"\n')
    caminho = tmp_path / "linux.toml"
    caminho.write_text(corpo, encoding="utf-8")
    with pytest.raises(catalogo_host.CatalogoInvalido):
        catalogo_host.carregar(caminho)