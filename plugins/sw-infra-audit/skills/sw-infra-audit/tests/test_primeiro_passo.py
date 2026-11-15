from lib import regras, remediacao

LIMITE = 160


def test_passo_um_vai_ate_o_passo_dois_e_junta_as_linhas():
    texto = "1. Veja se a rotina rodou:\n   `systemctl list-timers`.\n2. Outro passo."
    assert remediacao.primeiro_passo(texto) == "Veja se a rotina rodou: `systemctl list-timers`."


def test_passo_um_para_na_linha_em_branco():
    assert remediacao.primeiro_passo("\n1. Só este.\n\n```bash\nls\n```") == "Só este."


def test_bloco_que_abre_com_paragrafo_nao_tem_primeiro_passo():
    assert remediacao.primeiro_passo("Leia o runbook antes.\n\n1. Depois isto.") is None


def test_bloco_vazio_nao_tem_primeiro_passo():
    assert remediacao.primeiro_passo(None) is None and remediacao.primeiro_passo("") is None


def test_toda_regra_cobrada_comeca_por_um_passo_curto():
    fora = {}
    for regra in sorted(regras.exigem_remediacao()):
        bloco = remediacao.para(regra)
        passo = remediacao.primeiro_passo(bloco["como_resolver"]) if bloco else None
        if passo is None or len(passo) > LIMITE:
            fora[regra] = passo if passo is None else len(passo)
    assert fora == {}
