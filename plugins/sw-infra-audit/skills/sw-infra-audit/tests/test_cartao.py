from lib import cartao, remediacao

BACKUP = {"regra": "backup_atrasado", "alvo": "banco-01", "componente": "mariadb", "objeto": "mariadb",
          "severidade": "high", "detalhe": "backup mais novo com 5 dias; o limite é 2",
          "como_resolver": remediacao.para("backup_atrasado")}


def test_cartao_traz_o_primeiro_passo_como_o_que_fazer():
    html = cartao.cartao(BACKUP)
    assert "<b>O que fazer</b>" in html and "Veja se a rotina rodou" in html
    assert "<code>systemctl list-timers</code>" in html
    assert 'href="#regra-backup_atrasado"' in html and "ver todos os passos" in html


def test_cartao_mostra_titulo_onde_e_detalhe_com_etiqueta_e_icone():
    html = cartao.cartao(BACKUP)
    assert "Backup do banco mais velho que o limite" in html and "banco-01 · mariadb" in html
    assert "backup mais novo com 5 dias" in html and 'class="bl-tag-crit"' in html and "Alto" in html
    assert 'id="p-banco-01-mariadb-backup-atrasado"' in html


def test_regra_sem_ficha_ainda_diz_o_que_fazer():
    html = cartao.cartao({"regra": "REGRA_NOVA", "alvo": "a", "severidade": "medium"})
    assert "<b>O que fazer</b>" in html and "seção Problemas" in html


def test_texto_da_ficha_e_escapado():
    achado = dict(BACKUP, detalhe="<script>x</script>")
    assert "<script>" not in cartao.cartao(achado)


def test_indice_tem_uma_linha_por_achado_com_link_para_o_cartao():
    outro = dict(BACKUP, regra="servico_reiniciando", severidade="medium", como_resolver=None)
    html = cartao.indice([BACKUP, outro])
    assert html.count("<li>") == 2
    assert 'href="#p-banco-01-mariadb-backup-atrasado"' in html and "Médio" in html


def test_cobrados_tira_o_esperado():
    esperado = {"regra": "OPS_JOB_COMPLETED", "alvo": "a", "severidade": "low"}
    assert cartao.cobrados([BACKUP, esperado]) == [BACKUP]
