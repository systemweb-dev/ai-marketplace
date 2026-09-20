# tests/test_credencial.py
"""A senha vem do ambiente e morre no header.

O `alvos.toml` guarda o NOME da variável (`senha_env`), nunca o valor — o arquivo vive fora do
git com permissão 600, mas "fora do git" não é o mesmo que "seguro de imprimir".

A credencial é amarrada a (alvo, host, porta). Não existe credencial "da rodada": um alvo com
dois componentes autenticados não pode ter a senha de um usada no outro por descuido de código.
"""
import pytest

from lib.credencial import Credencial, CredencialFaltando, de_componente

ALVO = "prod"

COMPONENTE = {"nome": "broker", "papel": "fila",
              "admin_url": "http://exemplo.test:15672", "senha_env": "SENHA_BROKER"}


def test_le_a_senha_da_variavel_nomeada():
    cred = de_componente(COMPONENTE, alvo=ALVO, ambiente={"SENHA_BROKER": "abre-te"})

    assert cred.para(COMPONENTE["admin_url"], ALVO) == ("guest", "abre-te")


def test_usuario_pode_vir_declarado():
    componente = dict(COMPONENTE, usuario="leitor")

    cred = de_componente(componente, alvo=ALVO, ambiente={"SENHA_BROKER": "abre-te"})

    assert cred.para(COMPONENTE["admin_url"], ALVO) == ("leitor", "abre-te")


def test_variavel_ausente_levanta_com_o_nome_dela():
    """A mensagem precisa dizer QUAL variável exportar — senão o dono adivinha."""
    with pytest.raises(CredencialFaltando) as erro:
        de_componente(COMPONENTE, alvo=ALVO, ambiente={})

    assert "SENHA_BROKER" in str(erro.value)


def test_sem_senha_env_nao_ha_credencial():
    componente = {"nome": "broker", "admin_url": "http://exemplo.test:15672"}

    assert de_componente(componente, alvo=ALVO, ambiente={}) is None


def test_repr_nao_mostra_a_senha():
    """`repr` aparece em traceback, em log e em mensagem de teste que falhou."""
    cred = de_componente(COMPONENTE, alvo=ALVO, ambiente={"SENHA_BROKER": "abre-te"})

    assert "abre-te" not in repr(cred)
    assert "abre-te" not in f"{cred}"      # f-string usa __format__ -> __str__


def test_a_credencial_so_serve_para_o_destino_dela():
    """Amarrada a (alvo, host, porta): pedir o par para outro destino devolve None em vez de
    mandar a senha do broker para a primeira URL que aparecer."""
    cred = de_componente(COMPONENTE, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    assert cred.para("http://exemplo.test:15672/api/queues", ALVO) == ("guest", "abre-te")
    assert cred.para("http://exemplo.test:9090/api/queues", ALVO) is None
    assert cred.para("http://outro.test:15672/api/queues", ALVO) is None


def test_a_senha_nao_sai_por_json_pickle_copy_nem_getstate():
    """`__slots__` bloqueia `vars()` e o `json.dumps` já recusava — mas pickle, `copy` e
    `object.__getstate__` devolviam a senha inteira. Um `deepcopy` do grafo de componentes
    bastava para gravá-la em qualquer lugar."""
    import copy
    import json
    import pickle

    cred = de_componente(COMPONENTE, alvo=ALVO, ambiente={"SENHA_BROKER": "abre-te"})

    for tentativa in (lambda: json.dumps({"cred": cred}),
                      lambda: pickle.dumps(cred),
                      lambda: copy.deepcopy(cred),
                      lambda: cred.__getstate__()):
        with pytest.raises(TypeError):
            tentativa()


def test_nao_ha_forma_publica_de_pegar_a_senha_sem_destino():
    """`par()` público era a porta dos fundos: devolvia o par sem perguntar para onde ia."""
    cred = de_componente(COMPONENTE, alvo=ALVO, ambiente={"SENHA_BROKER": "abre-te"})

    assert not hasattr(cred, "par")


def test_alvo_diferente_com_o_mesmo_endereco_nao_casa():
    """prod e dr podem apontar para o mesmo host:porta com senhas diferentes. Comparar só
    (host, porta) faria a senha de um autenticar no outro."""
    cred = de_componente(COMPONENTE, alvo="prod", ambiente={"SENHA_BROKER": "de-prod"})

    assert cred.para(COMPONENTE["admin_url"], "dr") is None


def test_senha_env_sem_admin_url_e_recusado():
    """Sem destino, `_destino` viraria (None, None) e casaria com toda URL que não parseia —
    a função que existe para amarrar a senha entregaria a senha."""
    with pytest.raises(CredencialFaltando, match="admin_url"):
        de_componente({"nome": "broker", "senha_env": "SENHA_BROKER"}, alvo=ALVO,
                      ambiente={"SENHA_BROKER": "abre-te"})


def test_credencial_sem_destino_nao_casa_com_url_invalida():
    """Prova direta do buraco, construindo a credencial à mão."""
    cred = Credencial(alvo=ALVO, componente="broker", usuario="guest", senha="abre-te",
                      destino=(None, None))

    assert cred.para("", ALVO) is None
    assert cred.para("qualquer coisa", ALVO) is None


def test_le_do_ambiente_real_quando_nao_se_passa_um(monkeypatch):
    """O ramo que roda em produção. Todos os outros testes passam `ambiente=` explícito, e uma
    mutação trocando `os.environ` por `{}` sobrevivia à suíte inteira."""
    monkeypatch.setenv("SENHA_BROKER", "vinda-do-ambiente")

    cred = de_componente(COMPONENTE, alvo=ALVO)

    assert cred.para(COMPONENTE["admin_url"], ALVO) == ("guest", "vinda-do-ambiente")


def test_admin_url_sem_porta_usa_a_do_esquema():
    componente = dict(COMPONENTE, admin_url="https://exemplo.test")

    cred = de_componente(componente, alvo="prod", ambiente={"SENHA_BROKER": "abre-te"})

    assert cred.para("https://exemplo.test/api/queues", ALVO) == ("guest", "abre-te")


def test_dois_componentes_do_mesmo_alvo_tem_credenciais_separadas():
    a = de_componente(COMPONENTE, alvo=ALVO, ambiente={"SENHA_BROKER": "um"})
    b = de_componente(dict(COMPONENTE, nome="outro", senha_env="SENHA_OUTRO",
                           admin_url="http://exemplo.test:15673"),
                      alvo=ALVO, ambiente={"SENHA_OUTRO": "dois"})

    assert a.para("http://exemplo.test:15673/x", ALVO) is None
    assert b.para("http://exemplo.test:15673/x", ALVO) == ("guest", "dois")


def test_repr_serve_para_diagnostico_sem_servir_para_vazar():
    """Precisa dizer QUAL credencial é, para um traceback ser útil, sem dizer a senha."""
    cred = de_componente(COMPONENTE, alvo=ALVO, ambiente={"SENHA_BROKER": "abre-te"})

    assert "broker" in repr(cred) or "exemplo.test" in repr(cred)
    assert "abre-te" not in repr(cred)
