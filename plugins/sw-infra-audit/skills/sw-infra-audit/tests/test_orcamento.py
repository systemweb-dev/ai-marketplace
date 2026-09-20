# tests/test_orcamento.py
from lib.orcamento import Prazo


def test_prazo_corta_a_pergunta_seguinte_sem_derrubar_a_coleta():
    """Orçamento estourado não é erro: é `sem dados` com motivo, e o resto do relatório sai."""
    relogio = iter([0.0, 5.0, 130.0])
    prazo = Prazo(segundos=120, agora=lambda: next(relogio))

    assert prazo.esgotado() is False
    assert prazo.esgotado() is True
    assert prazo.motivo() == "orçamento do alvo esgotado"


def test_timeout_da_pergunta_nunca_passa_do_que_sobra():
    """Pedir 20 s a uma fonte quando faltam 5 para o alvo é prometer o que não se pode pagar."""
    relogio = iter([0.0, 115.0])
    prazo = Prazo(segundos=120, agora=lambda: next(relogio))
    assert prazo.timeout(pedido=20) == 5


def test_timeout_nunca_e_zero_enquanto_ha_prazo():
    relogio = iter([0.0, 119.6])
    prazo = Prazo(segundos=120, agora=lambda: next(relogio))
    assert prazo.timeout(pedido=20) == 1, "arredondar para baixo daria timeout=0, que é infinito"
