# tests/test_config.py
import pytest

from lib.config import ConfigInvalida, carregar

DEFAULT = """
[relatorio]
pasta = "docs/infra"
ignorar_em = "gitignore"

[limites]
timeout_por_comando = 20
orcamento_por_alvo = 120
"""

PROJETO_OK = """
alvos = ["cluster", "site"]

[relatorio]
pasta = "docs/auditoria"

[[aceite]]
alvo = "cluster"
regra = "sem_replica"
motivo = "base de cache"
desde = "2026-09-19"
revisar_em = "2027-03-19"
"""


def escrever(tmp_path, nome, texto):
    caminho = tmp_path / nome
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def test_projeto_sobrescreve_o_default_e_a_origem_fica_registrada(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", PROJETO_OK)

    cfg = carregar(padrao=padrao, infra=None, projeto=projeto)

    assert cfg.valor("relatorio.pasta") == "docs/auditoria"
    assert cfg.origem("relatorio.pasta") == "projeto"
    assert cfg.valor("limites.timeout_por_comando") == 20
    assert cfg.origem("limites.timeout_por_comando") == "default"


def test_arquivos_ausentes_caem_no_default(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)

    cfg = carregar(padrao=padrao, infra=tmp_path / "nao-existe.toml",
                   projeto=tmp_path / "tambem-nao.toml")

    assert cfg.valor("relatorio.pasta") == "docs/infra"
    assert cfg.alvos_escolhidos() == []


def test_chave_de_conexao_no_arquivo_do_projeto_e_erro(tmp_path):
    """O arquivo do projeto é versionado: se ele pudesse definir host, um clone redirecionaria
    a conexão e a credencial para o servidor de quem mandou o arquivo."""
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml",
                       '[[alvo]]\nnome = "banco"\nhost = "exemplo.invalido"\n')

    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=padrao, infra=None, projeto=projeto)

    assert "host" in str(erro.value) and ".sw-infra-audit.toml" in str(erro.value)


@pytest.mark.parametrize("chave", ["host", "porta", "usuario", "senha_env", "tipo", "metricas_url"])
def test_toda_chave_de_conexao_e_recusada_no_projeto(tmp_path, chave):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", f'[[alvo]]\nnome = "x"\n{chave} = "y"\n')

    with pytest.raises(ConfigInvalida):
        carregar(padrao=padrao, infra=None, projeto=projeto)


def test_aceites_das_duas_camadas_vem_com_a_origem(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    infra = escrever(tmp_path, "alvos.toml",
                     '[[aceite]]\nalvo = "cluster"\nregra = "spof"\nmotivo = "failover manual"\n'
                     'desde = "2026-01-01"\nrevisar_em = "2027-01-01"\n')
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", PROJETO_OK)

    cfg = carregar(padrao=padrao, infra=infra, projeto=projeto)
    origens = {(a["regra"], a["origem"]) for a in cfg.aceites()}

    assert origens == {("spof", "infra"), ("sem_replica", "projeto")}


def test_explicar_lista_chave_valor_e_origem(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", PROJETO_OK)

    linhas = carregar(padrao=padrao, infra=None, projeto=projeto).explicar()

    assert ("relatorio.pasta", "docs/auditoria", "projeto") in linhas
    assert ("limites.orcamento_por_alvo", 120, "default") in linhas
    assert linhas == sorted(linhas), "ordem estável: é saída que o usuário vai comparar"


def test_toml_quebrado_vira_erro_com_o_nome_do_arquivo(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", "isto [ não é toml")

    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=padrao, infra=None, projeto=projeto)

    assert ".sw-infra-audit.toml" in str(erro.value)


@pytest.mark.parametrize("texto", [
    '[alvo.banco]\nhost = "exemplo.invalido"\n',          # tabela aninhada em vez de [[alvo]]
    'host = "exemplo.invalido"\n',                          # chave solta no topo
    '[targets]\nhost = "exemplo.invalido"\n',              # tabela com outro nome
    '[relatorio]\nHOST = "exemplo.invalido"\n',            # caixa diferente
    '[[alvo]]\nnome = "x"\nsenha_env = "SEGREDO"\n',      # o caso que já era pego
])
def test_nenhum_caminho_do_arquivo_do_projeto_entrega_conexao(tmp_path, texto):
    """O arquivo do projeto é versionado: qualquer jeito de declarar conexão nele é erro."""
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", texto)

    with pytest.raises(ConfigInvalida):
        carregar(padrao=padrao, infra=None, projeto=projeto)


def test_o_projeto_so_pode_definir_o_que_esta_na_lista(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", '[limites]\ntimeout_por_comando = 999\n')

    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=padrao, infra=None, projeto=projeto)

    assert "limites" in str(erro.value) and "alvos" in str(erro.value)


def test_alvos_precisa_ser_lista_de_nomes(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml",
                       'alvos = [{nome = "x", host = "exemplo.invalido"}]\n')

    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=padrao, infra=None, projeto=projeto)

    assert "alvos" in str(erro.value)


@pytest.mark.parametrize("pasta", ["/etc/sw", "../fora", "docs/../../fora"])
def test_pasta_do_relatorio_precisa_ser_relativa_e_dentro_do_projeto(tmp_path, pasta):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", f'[relatorio]\npasta = "{pasta}"\n')

    with pytest.raises(ConfigInvalida):
        carregar(padrao=padrao, infra=None, projeto=projeto)


def test_lista_legitima_aparece_no_efetivo_e_no_explicar(tmp_path):
    padrao = escrever(tmp_path, "default.toml", DEFAULT)
    projeto = escrever(tmp_path, ".sw-infra-audit.toml", 'alvos = ["cluster", "site"]\n')

    cfg = carregar(padrao=padrao, infra=None, projeto=projeto)

    assert cfg.valor("alvos") == ["cluster", "site"]
    assert ("alvos", ["cluster", "site"], "projeto") in cfg.explicar()
