import pytest

from lib import alvos

BASE = '[[alvo]]\nnome = "srv"\ntipo = "host"\nssh_destino = "root@srv"\n[[alvo.componente]]\nnome = "mariadb"\n'


def _ler(tmp_path, extra):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(BASE + extra, encoding="utf-8")
    caminho.chmod(0o600)
    return alvos.ler(caminho)[0][0]["componente"][0]


def test_componente_descoberto_carrega(tmp_path):
    comp = _ler(tmp_path, 'papel = "banco"\nproduto = "mariadb"\nportas = [3306]\n'
                          'origem = "unidade:mariadb.service"\n')
    assert comp["produto"] == "mariadb" and comp["portas"] == [3306]


def test_produto_desconhecido_e_recusado(tmp_path):
    with pytest.raises(alvos.AlvoInvalido, match="não está em references/produtos.toml"):
        _ler(tmp_path, 'produto = "inventado"\n')


@pytest.mark.parametrize("origem", ['"qualquer"', '"unidade:a\\"b"', '"processo:"'])
def test_origem_fora_do_formato_e_recusada(tmp_path, origem):
    with pytest.raises(alvos.AlvoInvalido, match="origem fora do formato"):
        _ler(tmp_path, f"origem = {origem}\n")


def test_portas_precisam_ser_inteiros_validos(tmp_path):
    with pytest.raises(alvos.AlvoInvalido, match="lista de inteiros de 1 a 65535"):
        _ler(tmp_path, "portas = [0]\n")
