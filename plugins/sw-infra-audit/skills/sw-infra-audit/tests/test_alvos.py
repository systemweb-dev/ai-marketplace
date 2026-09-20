# tests/test_alvos.py
import os
import stat

import pytest

from lib.alvos import AlvoInvalido, ler, selecionar

ALVOS = """
[[alvo]]
nome = "cluster"
tipo = "docker"
context = "meu-context"
metricas_url = "http://127.0.0.1:9090"

[[alvo]]
nome = "site"
tipo = "http"
url = "https://exemplo.invalido/health"
"""


def escrever(tmp_path, texto, modo=0o600):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(modo)
    return caminho


def test_le_os_alvos_com_tipo_e_campos(tmp_path):
    lidos, avisos = ler(escrever(tmp_path, ALVOS))

    assert [(a["nome"], a["tipo"]) for a in lidos] == [("cluster", "docker"), ("site", "http")]
    assert lidos[0]["metricas_url"] == "http://127.0.0.1:9090"
    assert avisos == []


def test_alvo_sem_campo_obrigatorio_e_recusado_dizendo_qual(tmp_path):
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "site"\ntipo = "http"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "site" in str(erro.value) and "url" in str(erro.value)


def test_tipo_desconhecido_diz_quais_existem(tmp_path):
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "banco"\ntipo = "oracle"\nhost = "x"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "oracle" in str(erro.value) and "docker" in str(erro.value)


def test_nome_repetido_e_recusado(tmp_path):
    caminho = escrever(tmp_path, ALVOS + '\n[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://a.invalido"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "site" in str(erro.value)


def test_arquivo_legivel_por_outros_vira_aviso(tmp_path):
    caminho = escrever(tmp_path, ALVOS, modo=0o644)

    _, avisos = ler(caminho)

    assert any("permiss" in a for a in avisos)
    assert oct(stat.S_IMODE(os.stat(caminho).st_mode)) == "0o644", "a skill avisa, não conserta sozinha"


def test_arquivo_ausente_devolve_vazio_sem_explodir(tmp_path):
    lidos, avisos = ler(tmp_path / "nao-existe.toml")

    assert lidos == []
    assert any("não encontrei" in a for a in avisos)


def test_selecionar_respeita_a_ordem_declarada_no_projeto(tmp_path):
    lidos, _ = ler(escrever(tmp_path, ALVOS))

    assert [a["nome"] for a in selecionar(lidos, ["site", "cluster"])] == ["site", "cluster"]


def test_selecionar_sem_lista_devolve_todos(tmp_path):
    lidos, _ = ler(escrever(tmp_path, ALVOS))

    assert len(selecionar(lidos, [])) == 2


def test_nome_escolhido_que_nao_existe_e_recusado(tmp_path):
    lidos, _ = ler(escrever(tmp_path, ALVOS))

    with pytest.raises(AlvoInvalido) as erro:
        selecionar(lidos, ["fantasma"])

    assert "fantasma" in str(erro.value)


def test_tabela_aninhada_em_vez_de_lista_vira_erro_claro(tmp_path):
    caminho = escrever(tmp_path, '[alvo.cluster]\ntipo = "docker"\ncontext = "ctx"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "[[alvo]]" in str(erro.value)


def test_campo_desconhecido_no_alvo_e_recusado(tmp_path):
    """`metrica_url` (sem o s) passaria mudo e o usuário nunca saberia por que não funcionou."""
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "ctx"\n'
                                 'metrica_url = "http://127.0.0.1:9090"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "metrica_url" in str(erro.value)


def test_senha_dentro_do_alvo_e_recusada(tmp_path):
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "ctx"\n'
                                 'senha = "nao-faca-isso"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "senha" in str(erro.value)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "exemplo.invalido/x"])
def test_url_precisa_ser_http_ou_https_com_host(tmp_path, url):
    caminho = escrever(tmp_path, f'[[alvo]]\nnome = "s"\ntipo = "http"\nurl = "{url}"\n')

    with pytest.raises(AlvoInvalido):
        ler(caminho)


def test_nome_de_alvo_nao_pode_virar_caminho(tmp_path):
    caminho = escrever(tmp_path, '[[alvo]]\nnome = "../../etc/x"\ntipo = "docker"\ncontext = "c"\n')

    with pytest.raises(AlvoInvalido) as erro:
        ler(caminho)

    assert "nome" in str(erro.value)


def test_url_com_porta_impossivel_e_recusada_na_leitura(tmp_path):
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text('[[alvo]]\nnome = "site"\ntipo = "http"\n'
                       'url = "http://site.interno:8080000/health"\n', encoding="utf-8")
    with pytest.raises(AlvoInvalido) as erro:
        ler(arquivo)
    assert "porta inválida" in str(erro.value)


def test_componente_do_alvo_aceita_papel_e_metricas(tmp_path):
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text('[[alvo]]\nnome = "cluster"\ntipo = "docker"\ncontext = "prod"\n\n'
                       '[[alvo.componente]]\nnome = "proxy"\npapel = "entrada"\n'
                       'metricas_url = "http://127.0.0.1:9090"\n', encoding="utf-8")

    lidos, _ = ler(arquivo)

    assert lidos[0]["componente"] == [{"nome": "proxy", "papel": "entrada",
                                       "metricas_url": "http://127.0.0.1:9090"}]


def test_alvo_sem_bloco_de_componente_continua_valendo(tmp_path):
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text('[[alvo]]\nnome = "cluster"\ntipo = "docker"\ncontext = "prod"\n',
                       encoding="utf-8")
    lidos, _ = ler(arquivo)
    assert lidos[0]["componente"] == []


def test_componente_com_campo_inexistente_e_recusado(tmp_path):
    """Erro de digitação que passa mudo vira 'a skill não coletou e não disse por quê'."""
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text('[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "p"\n\n'
                       '[[alvo.componente]]\nnome = "x"\nmetrica_url = "http://127.0.0.1:9090"\n',
                       encoding="utf-8")
    with pytest.raises(AlvoInvalido) as erro:
        ler(arquivo)
    assert "metrica_url" in str(erro.value)


def test_componente_com_papel_invalido_e_recusado(tmp_path):
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text('[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "p"\n\n'
                       '[[alvo.componente]]\nnome = "x"\npapel = "bananco"\n', encoding="utf-8")
    with pytest.raises(AlvoInvalido) as erro:
        ler(arquivo)
    assert "bananco" in str(erro.value)


def test_componente_sem_nome_e_recusado(tmp_path):
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text('[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "p"\n\n'
                       '[[alvo.componente]]\npapel = "fila"\n', encoding="utf-8")
    with pytest.raises(AlvoInvalido) as erro:
        ler(arquivo)
    assert "sem nome" in str(erro.value)


def test_senha_do_componente_e_so_o_nome_da_variavel(tmp_path):
    """A senha nunca fica no arquivo: o que se declara é onde ela mora."""
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text('[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "p"\n\n'
                       '[[alvo.componente]]\nnome = "fila"\npapel = "fila"\n'
                       'admin_url = "http://127.0.0.1:15672"\nsenha_env = "SENHA_DA_FILA"\n',
                       encoding="utf-8")
    lidos, _ = ler(arquivo)
    assert lidos[0]["componente"][0]["senha_env"] == "SENHA_DA_FILA"
