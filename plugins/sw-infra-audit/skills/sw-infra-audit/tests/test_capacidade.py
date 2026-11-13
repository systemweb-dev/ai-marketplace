# tests/test_capacidade.py
from lib import capacidade
from lib.perguntas import PERGUNTAS, do_papel


def _maquina(**valores):
    return {"nome": "srv", "papel": "maquina",
            "respostas": [{"pergunta": p, "fonte": "ssh", "valor": v} for p, v in valores.items()]}


def test_maquina_tem_carga_e_boot_e_disco_segue_opcional_sem_limiar():
    ids = [p["id"] for p in do_papel("maquina")]
    assert "maquina.carga" in ids and "maquina.desde_o_boot" in ids
    assert PERGUNTAS["maquina.disco"]["opcional"] and PERGUNTAS["maquina.disco"]["limiar"] is None


def test_disco_acima_de_90_vira_achado_high():
    achados = capacidade.achados(_maquina(**{"maquina.disco": 94}))
    assert [(a["regra"], a["severidade"], a["objeto"]) for a in achados] == \
        [("disco_quase_cheio", "high", "srv")]


def test_memoria_em_90_nao_vira_achado_e_91_vira():
    assert capacidade.achados(_maquina(**{"maquina.memoria": 90})) == []
    assert capacidade.achados(_maquina(**{"maquina.memoria": 91}))[0]["regra"] == "memoria_sem_folga"


def test_sem_dados_e_outro_papel_nunca_viram_achado():
    sem = {"nome": "srv", "papel": "maquina",
           "respostas": [{"pergunta": "maquina.disco", "sem_dados": True, "motivo": "VPN"}]}
    assert capacidade.achados(sem) == []
    assert capacidade.achados(dict(_maquina(**{"maquina.disco": 99}), papel="banco")) == []
