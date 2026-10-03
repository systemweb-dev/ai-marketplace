"""A caixa de divergência tem de comparar o que a dimensão realmente mede.

`metrics.py` calcula a dimensão `seguranca` filtrando `rule_id.startswith("SEC_")` — ela é
sobre POSTURA DE SEGURANÇA, não sobre todos os achados. A primeira versão desta caixa
comparava contra a lista inteira e acusava divergência onde não havia: numa rodada real
disse "médios 107 declarados · 114 na lista" porque os 7 extras eram `OPS_TASK_FAILING`,
que a dimensão nunca contou.

Alarme falso é pior que alarme nenhum: ensina a ignorar a caixa.
"""
from build_report import _divergencias


def alvo(dimensao, achados):
    return {"nome": "cluster", "dimensoes": {"seguranca": dimensao}, "achados": achados}


def ach(regra, severidade, esperada=False):
    a = {"regra": regra, "severidade": severidade, "objeto": "x"}
    if esperada:
        a["esperada"] = True
    return a


def test_achado_fora_do_escopo_da_dimensao_nao_acusa_divergencia():
    """107 médios de segurança + 7 operacionais: a dimensão conta 107 e está certa."""
    achados = [ach("SEC_USER_ROOT", "medium")] * 107 + [ach("OPS_TASK_FAILING", "medium")] * 7

    saida = _divergencias(alvo({"high": 0, "med": 107, "expected": 0}, achados))

    assert saida == "", "não há divergência: a dimensão é sobre regras SEC_"


def test_divergencia_de_verdade_continua_sendo_acusada():
    """Se a dimensão discordar do que ELA mede, a caixa tem de aparecer."""
    achados = [ach("SEC_USER_ROOT", "medium")] * 50

    saida = _divergencias(alvo({"high": 0, "med": 107, "expected": 0}, achados))

    assert "não batem" in saida
    assert "107 declarados · 50 na lista" in saida


def test_esperados_tambem_contam_so_os_de_seguranca():
    """12 SEC_ esperados + 7 OPS_ esperados: a dimensão declara 12 e está certa."""
    achados = ([ach("SEC_DOCKER_SOCK_EXPECTED", "low", esperada=True)] * 12
               + [ach("OPS_JOB_COMPLETED", "low", esperada=True)] * 7)

    saida = _divergencias(alvo({"high": 0, "med": 0, "expected": 12}, achados))

    assert saida == ""


def test_alvo_sem_dimensao_de_seguranca_nao_quebra():
    assert _divergencias({"nome": "x", "dimensoes": {}, "achados": []}) == ""
