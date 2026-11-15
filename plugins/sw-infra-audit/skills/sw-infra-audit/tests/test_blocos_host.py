from lib.blocos import render_bloco
from lib.dados_blocos import dados_do_papel
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_host import alvo_host_banco


def _html(papel, alvos):
    return render_bloco(papel, dados_do_papel(papel, alvos))


def test_banco_do_host_mostra_medidores_barras_e_o_cartao():
    html = _html("banco", [alvo_host_banco()])
    assert "Conexões em uso" in html and "alerta em 80%" in html
    assert "Idade do backup" in html and "limite 2 dias" in html and "acima do limite" in html
    assert "Tamanho por banco" in html and ">loja<" in html
    assert "Consultas lentas" in html and "Binlog" in html
    assert 'id="p-banco-01-mariadb-backup-atrasado"' in html and "<b>O que fazer</b>" in html


def test_banco_do_cluster_nao_ganha_campo_que_nao_existe():
    html = _html("banco", relatorio_docker()["alvos"])
    assert "Idade do backup" not in html and "Tamanho por banco" not in html and "Binlog" not in html
    assert "loja_db" in html and "18 conexões" in html


def test_maquinas_mostra_carga_boot_marca_de_90_e_o_cartao_fora_da_grade():
    html = _html("maquinas", [alvo_host_banco()])
    assert "Carga" in html and "Desde o boot" in html and "41 dias" in html
    assert 'class="gf-lim" x="90.00%"' in html
    assert html.index('class="bl-maqs"') < html.index('id="p-banco-01-banco-01-disco-quase-cheio"')


def test_busca_mostra_colecoes_com_status_em_icone_e_rotulo():
    html = _html("busca", [alvo_host_banco()])
    assert "Busca" in html and ">docs<" in html and "status yellow" in html
    assert 'class="bl-tag-warn"' in html and "Otimizando" in html


def test_sem_busca_o_bloco_some():
    assert _html("busca", relatorio_docker()["alvos"]) == ""


def test_maquina_acima_da_marca_tem_etiqueta_e_abaixo_usa_o_acento():
    html = render_bloco("maquinas", {"itens": [{"nome": "m", "cpu": 86.0, "disco": 93.0}]})
    cpu, disco = html.split("<span>Disco</span>")
    assert 'class="gf-acc"' in cpu and "acima do limite" not in cpu
    assert 'class="gf-crit"' in disco and "acima do limite" in disco
