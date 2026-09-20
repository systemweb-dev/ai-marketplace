# tests/test_config.py
from pathlib import Path

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


# ---------------------------------------------------------------- onde moram os alvos
def _repo(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_alvos_moram_na_pasta_do_relatorio_do_projeto(tmp_path):
    """O arquivo de alvos vive junto do relatório, dentro do projeto — não no home."""
    from lib.config import caminho_dos_alvos
    (tmp_path / "default.toml").write_text(DEFAULT, encoding="utf-8")

    caminho = caminho_dos_alvos(padrao=tmp_path / "default.toml", projeto=None)

    assert caminho == Path("docs/infra/alvos.toml")


def test_alvos_seguem_a_pasta_que_o_projeto_escolheu(tmp_path):
    """Mudar `relatorio.pasta` move o relatório E os alvos: duas pastas seria duas verdades."""
    from lib.config import caminho_dos_alvos
    (tmp_path / "default.toml").write_text(DEFAULT, encoding="utf-8")
    projeto = tmp_path / ".sw-infra-audit.toml"
    projeto.write_text('[relatorio]\npasta = "docs/auditoria"\n', encoding="utf-8")

    caminho = caminho_dos_alvos(padrao=tmp_path / "default.toml", projeto=projeto)

    assert caminho == Path("docs/auditoria/alvos.toml")


def test_pasta_nao_ignorada_pelo_git_e_recusada(tmp_path, monkeypatch):
    """O alvos.toml guarda conexão. Dentro de um repo sem a pasta ignorada, ele está a um
    `git add -A` de virar público — a skill se recusa a usá-lo assim."""
    from lib.config import exigir_pasta_protegida
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigInvalida) as erro:
        exigir_pasta_protegida(Path("docs/infra/alvos.toml"))

    assert "gitignore" in str(erro.value).lower()


def test_pasta_ignorada_pelo_git_passa(tmp_path, monkeypatch):
    from lib.config import exigir_pasta_protegida
    _repo(tmp_path)
    (tmp_path / ".gitignore").write_text("docs/infra/\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exigir_pasta_protegida(Path("docs/infra/alvos.toml"))      # não levanta


def test_fora_de_repositorio_nao_ha_o_que_proteger(tmp_path, monkeypatch):
    from lib.config import exigir_pasta_protegida
    monkeypatch.chdir(tmp_path)

    exigir_pasta_protegida(Path("docs/infra/alvos.toml"))      # não levanta


def test_o_arquivo_do_projeto_mora_em_docs_infra(tmp_path, monkeypatch):
    """Tudo da skill num lugar só: o config.toml versionado fica na mesma pasta do resto."""
    from lib.config import caminho_do_projeto
    monkeypatch.chdir(tmp_path)

    assert caminho_do_projeto() == Path("docs/infra/config.toml")


def test_o_arquivo_antigo_na_raiz_ainda_e_lido(tmp_path, monkeypatch):
    """Quem já tem .sw-infra-audit.toml não fica sem configuração de um dia para o outro."""
    from lib.config import caminho_do_projeto
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = []\n', encoding="utf-8")

    assert caminho_do_projeto() == Path(".sw-infra-audit.toml")


def test_o_novo_vence_o_antigo_quando_os_dois_existem(tmp_path, monkeypatch):
    from lib.config import caminho_do_projeto
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = []\n', encoding="utf-8")
    (tmp_path / "docs" / "infra").mkdir(parents=True)
    (tmp_path / "docs" / "infra" / "config.toml").write_text('alvos = []\n', encoding="utf-8")

    assert caminho_do_projeto() == Path("docs/infra/config.toml")


def test_projeto_pode_ajustar_a_janela_dos_insights(tmp_path):
    from lib.config import carregar
    (tmp_path / "config.toml").write_text(
        'alvos = ["cluster"]\n\n[insights]\njanela = "7d"\n', encoding="utf-8")
    cfg = carregar(padrao=None, infra=None, projeto=tmp_path / "config.toml")
    assert cfg.valor("insights.janela") == "7d"


def test_projeto_pode_liberar_o_ip_completo(tmp_path):
    from lib.config import carregar
    (tmp_path / "config.toml").write_text('[relatorio]\nip_completo = true\n', encoding="utf-8")
    cfg = carregar(padrao=None, infra=None, projeto=tmp_path / "config.toml")
    assert cfg.valor("relatorio.ip_completo") is True


def test_a_trava_contra_conexao_continua_valendo_no_bloco_novo(tmp_path):
    """`insights` abriu no arquivo versionado — isso não pode virar porta para conexão."""
    from lib.config import ConfigInvalida, carregar
    (tmp_path / "config.toml").write_text(
        '[insights]\njanela = "24h"\nhost = "interno"\n', encoding="utf-8")
    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=None, infra=None, projeto=tmp_path / "config.toml")
    assert "insights.host" in str(erro.value)


def test_insights_tem_allowlist_de_subchave(tmp_path):
    """`relatorio` já tinha; `insights` entrou sem. Chave desconhecida ali viraria configuração
    que ninguém lê — e a Task 10 vai ler esse bloco."""
    from lib.config import ConfigInvalida, carregar
    (tmp_path / "config.toml").write_text('[insights]\nfonte_url = "http://10.0.0.9:9090"\n',
                                          encoding="utf-8")
    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=None, infra=None, projeto=tmp_path / "config.toml")
    assert "fonte_url" in str(erro.value)


def test_lista_de_tabelas_dentro_de_insights_e_recusada(tmp_path):
    """`_achatar` pula lista de tabelas de propósito — então um [[insights.fonte]] com host e
    senha escaparia inteiro do scan de conexão. A allowlist fecha essa porta."""
    from lib.config import ConfigInvalida, carregar
    (tmp_path / "config.toml").write_text(
        '[[insights.fonte]]\nhost = "interno"\nsenha = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigInvalida):
        carregar(padrao=None, infra=None, projeto=tmp_path / "config.toml")


def test_aceite_com_chave_errada_e_recusado(tmp_path):
    """`compomente` (typo) viraria aceite do ALVO INTEIRO, apagando achado de todos os
    componentes — silenciosamente mais amplo do que o dono pediu."""
    from lib.config import ConfigInvalida, carregar
    (tmp_path / "config.toml").write_text(
        '[[aceite]]\nalvo = "cluster"\nregra = "r"\ncompomente = "fila_a"\nmotivo = "m"\n',
        encoding="utf-8")
    with pytest.raises(ConfigInvalida) as erro:
        carregar(padrao=None, infra=None, projeto=tmp_path / "config.toml")
    assert "compomente" in str(erro.value)
