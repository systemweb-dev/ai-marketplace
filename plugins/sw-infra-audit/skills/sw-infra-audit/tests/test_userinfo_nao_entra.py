# tests/test_userinfo_nao_entra.py
"""Credencial embutida na URL não entra em lugar nenhum.

A primeira versão desta trava ficou só em `get_autenticado`, e isso deixou o buraco aberto:
`urlparse().hostname` descarta o `user:senha@`, então `check_allowed` aprovava sem ver. Um
`admin_url = "http://leitor:SENHA@host:15672"` no alvos.toml passava na validação, era copiado
cru para o componente e chegava ao `report.json`, ao HTML e ao PDF — com a senha em claro.

A guarda mora agora em `check_allowed`, que TODAS as funções de rede atravessam, e em
`alvos._checar_url`, para o erro aparecer ao ler a configuração e não no meio da coleta.
"""
import pytest

from lib import alvos, http_get

COM_SENHA = "http://leitor:senha-do-toml@exemplo.test:15672/api/overview"
PERMITIDOS = [("exemplo.test", 15672)]


def test_check_allowed_recusa_userinfo():
    """É a porta por onde `get`, `get_com_status` e `validade_do_certificado` passam."""
    with pytest.raises(http_get.NotConfirmed):
        http_get.check_allowed(COM_SENHA, PERMITIDOS)


@pytest.mark.parametrize("funcao", ["get", "get_com_status"])
def test_nenhuma_funcao_de_rede_aceita_userinfo(funcao):
    with pytest.raises(http_get.NotConfirmed):
        getattr(http_get, funcao)(COM_SENHA, PERMITIDOS)


def test_alvos_recusa_url_com_senha_embutida(tmp_path):
    """O erro tem que aparecer ao LER a configuração: na coleta já seria tarde, porque o valor
    cru já teria sido copiado para o componente."""
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text(
        '[[alvo]]\n'
        'nome = "prod"\n'
        'tipo = "docker"\n'
        'context = "prod"\n'
        '[[alvo.componente]]\n'
        'nome = "broker"\n'
        'papel = "fila"\n'
        'admin_url = "http://leitor:senha-do-toml@exemplo.test:15672"\n',
        encoding="utf-8")

    with pytest.raises(alvos.AlvoInvalido) as erro:
        alvos.ler(arquivo)

    assert "senha_env" in str(erro.value), "a mensagem precisa dizer o que fazer no lugar"


def test_a_mensagem_nao_repete_a_senha(tmp_path):
    """Recusar imprimindo o valor recusado colocaria a senha no terminal e no log."""
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text(
        '[[alvo]]\nnome = "prod"\ntipo = "docker"\ncontext = "prod"\n'
        '[[alvo.componente]]\nnome = "broker"\npapel = "fila"\n'
        'admin_url = "http://leitor:senha-do-toml@exemplo.test:15672"\n', encoding="utf-8")

    with pytest.raises(alvos.AlvoInvalido) as erro:
        alvos.ler(arquivo)

    assert "senha-do-toml" not in str(erro.value)


def test_url_sem_userinfo_continua_passando():
    assert http_get.check_allowed("http://exemplo.test:15672/api/overview", PERMITIDOS)


def test_arroba_no_caminho_nao_e_falso_positivo():
    """`@` em path ou query é legítimo; a guarda olha só o netloc."""
    assert http_get.check_allowed("http://exemplo.test:15672/api/queues/%2F/fila@1",
                                  PERMITIDOS)
