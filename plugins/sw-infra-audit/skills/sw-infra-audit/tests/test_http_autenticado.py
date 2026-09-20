# tests/test_http_autenticado.py
"""A única porta autenticada da skill.

`get()` e `get_com_status()` continuam anônimos: quem precisa de credencial usa esta função, e
é só ela que um revisor precisa ler para saber por onde segredo sai da máquina.
"""
import base64
import urllib.error

import pytest

from lib import http_get

PERMITIDOS = [("exemplo.test", 15672)]
ALVO = "prod"


def _cred(usuario="leitor", senha="senha-secreta", host="exemplo.test", porta=15672,
          alvo=ALVO):
    """Uma credencial de verdade — `get_autenticado` recusa par solto de propósito."""
    from lib.credencial import Credencial

    return Credencial(alvo=alvo, componente="broker", usuario=usuario, senha=senha,
                      destino=(host, porta))


class _Resposta:
    status = 200

    def __init__(self, corpo=b'{"ok":true}'):
        self._corpo = corpo

    def read(self, _n):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def capturado(monkeypatch):
    """Captura o Request que chegaria na rede, sem abrir socket nenhum."""
    vistos = []

    def abrir(req, timeout=None):
        vistos.append(req)
        return _Resposta()

    monkeypatch.setattr(http_get._OPENER, "open", abrir)
    return vistos


def test_monta_o_header_basic_a_partir_do_par(capturado):
    http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                             _cred(), ALVO)

    esperado = base64.b64encode(b"leitor:senha-secreta").decode("ascii")
    assert capturado[0].get_header("Authorization") == f"Basic {esperado}"


def test_sem_credencial_nao_manda_header(capturado):
    http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS, None)

    assert capturado[0].get_header("Authorization") is None


def test_a_senha_nunca_aparece_na_url(capturado):
    http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                             _cred(), ALVO)

    req = capturado[0]
    # `full_url` não basta: a senha em `usuario:senha@host` vive no `host`, que vira o header
    # Host. Foi olhar só o `full_url` que deixou o vazamento invisível na primeira versão.
    assert "senha-secreta" not in req.full_url
    assert "senha-secreta" not in req.host
    assert "senha-secreta" not in str(req.headers)


def test_url_com_userinfo_e_recusada():
    """A guarda vive em `check_allowed`, que esta função atravessa — ver
    tests/test_userinfo_nao_entra.py para o resto das portas."""
    with pytest.raises(http_get.NotConfirmed):
        http_get.get_autenticado("http://leitor:senha@exemplo.test:15672/api/overview",
                                 PERMITIDOS, _cred(), ALVO)


def test_par_solto_e_recusado():
    """Par não sabe a que destino pertence. Aceitá-lo devolveria a amarração à convenção."""
    with pytest.raises(TypeError):
        http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                                 ("leitor", "senha"), ALVO)


def test_string_nao_vira_usuario_e_senha():
    """`"ab"` desempacotava em `a:b` e virava requisição autenticada com lixo."""
    with pytest.raises(TypeError):
        http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                                 "ab", ALVO)


def test_credencial_de_outro_destino_nao_manda_header(capturado):
    """O ponto inteiro da mudança: é ESTA função que decide, não quem a chama."""
    http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                             _cred(porta=9090), ALVO)

    assert capturado[0].get_header("Authorization") is None


def test_credencial_de_outro_alvo_nao_manda_header(capturado):
    """prod e dr podem declarar o mesmo host:porta com senhas diferentes."""
    http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                             _cred(alvo="dr"), ALVO)

    assert capturado[0].get_header("Authorization") is None


def test_destino_fora_da_allowlist_levanta():
    with pytest.raises(http_get.NotConfirmed):
        http_get.get_autenticado("http://outro.test:15672/api/overview", PERMITIDOS,
                                 ("leitor", "senha"))


def test_porta_diferente_do_mesmo_host_nao_passa():
    """Host declarado não autoriza porta não declarada — senão a coleta vira varredura."""
    with pytest.raises(http_get.NotConfirmed):
        http_get.get_autenticado("http://exemplo.test:5672/api/overview", PERMITIDOS,
                                 ("leitor", "senha"))


def test_devolve_status_e_corpo(capturado):
    status, corpo = http_get.get_autenticado("http://exemplo.test:15672/api/overview",
                                             PERMITIDOS, _cred(), ALVO)

    assert (status, corpo) == (200, '{"ok":true}')


def test_401_volta_como_status_nao_como_excecao(monkeypatch):
    """401 é informação: quer dizer "a família é essa, falta credencial"."""
    def abrir(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(http_get._OPENER, "open", abrir)

    assert http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                                    _cred(), ALVO) == (401, "")


def test_inalcancavel_volta_none(monkeypatch):
    def abrir(req, timeout=None):
        raise urllib.error.URLError("sem rota")

    monkeypatch.setattr(http_get._OPENER, "open", abrir)

    assert http_get.get_autenticado("http://exemplo.test:15672/api/overview", PERMITIDOS,
                                    _cred(), ALVO) == (None, None)
