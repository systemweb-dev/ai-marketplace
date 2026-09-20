# tests/test_usuario_chega_no_componente.py
"""Campo declarado que não chega a lugar nenhum é pior que campo recusado.

`usuario` entrou em `COMPONENTE_PERMITE` e o coletor não o copiava para o componente de
runtime. O dono declarava `usuario = "leitor"`, a validação não reclamava, e a auditoria
autenticava como `guest` — 401 sem explicação. É exatamente a classe de bug que a validação
estrita do alvos.toml existe para evitar.
"""
from lib.credencial import de_componente


def test_o_usuario_declarado_chega_na_credencial():
    componente = {"nome": "broker", "admin_url": "http://exemplo.test:15672",
                  "senha_env": "SENHA", "usuario": "leitor"}

    cred = de_componente(componente, alvo="prod", ambiente={"SENHA": "s"})

    assert cred.para(componente["admin_url"], "prod")[0] == "leitor"


def test_o_coletor_docker_copia_usuario_para_o_componente():
    """A trava no ponto onde o campo se perdia."""
    import inspect

    from lib.coletores import docker

    fonte = inspect.getsource(docker)
    assert 'componente["usuario"] = declarado["usuario"]' in fonte, \
        "o coletor precisa copiar `usuario`, senão declarar no alvos.toml é mudo"


def test_todo_campo_de_credencial_permitido_e_copiado_pelo_coletor():
    """Trava genérica: campo novo de credencial que o coletor esquecer derruba a suíte."""
    import inspect

    from lib.coletores import docker

    fonte = inspect.getsource(docker)
    for campo in ("admin_url", "senha_env", "usuario"):
        assert f'declarado["{campo}"]' in fonte, f"o coletor não copia `{campo}`"
