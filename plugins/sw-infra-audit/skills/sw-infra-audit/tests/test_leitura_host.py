from lib import leitura_host as lh

DF = """Filesystem     1024-blocks     Used Available Capacity Mounted on
udev               1000000        0   1000000       0% /dev
tmpfs               200000     1000    199000       1% /run
/dev/vda1         50000000 47000000   3000000      94% /
/dev/vdb1        100000000 40000000  60000000      40% /var/lib/mysql
overlay           50000000 47000000   3000000      94% /var/lib/docker/overlay2/abc/merged
"""
MEMINFO = "MemTotal:        4000000 kB\nMemFree:          100000 kB\nMemAvailable:    1000000 kB\n"


def test_disco_e_o_maior_uso_entre_sistemas_de_arquivos_reais():
    assert lh.disco(DF) == 94


def test_disco_ignora_tmpfs_e_overlay_quando_o_raiz_e_baixo():
    df = DF.replace("94% /\n", "20% /\n")
    assert lh.disco(df) == 40


def test_memoria_usa_memavailable():
    assert lh.memoria(MEMINFO) == 75.0


def test_carga_e_a_media_de_5_min_por_cpu():
    assert lh.carga("0.50 3.00 1.00 1/200 999\n", "4\n") == 75.0


def test_desde_o_boot_em_dias():
    assert lh.desde_o_boot("864000.55 1000.00\n") == 10.0


def test_sistema_le_so_o_pretty_name():
    assert lh.sistema('NAME="Debian"\nPRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n') == \
        "Debian GNU/Linux 12 (bookworm)"


def test_saida_em_formato_inesperado_vira_none():
    assert lh.disco("lixo") is None and lh.memoria("") is None
    assert lh.carga("x", "4") is None and lh.carga("1 2 3", "0") is None
    assert lh.desde_o_boot("") is None and lh.sistema("") is None


def test_nan_e_infinito_viram_none():
    assert lh.carga("1 nan 1", "2") is None and lh.carga("1 inf 1", "2") is None
    assert lh.desde_o_boot("nan 1") is None and lh.desde_o_boot("inf 1") is None


def test_ponto_de_montagem_parecido_com_ignorado_continua_contando():
    df = ("Filesystem 1024-blocks Used Available Capacity Mounted on\n"
          "/dev/vda1 100 20 80 20% /\n/dev/sdb1 100 98 2 98% /snapshots\n")
    assert lh.disco(df) == 98
