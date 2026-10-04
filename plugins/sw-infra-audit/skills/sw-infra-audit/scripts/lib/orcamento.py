"""Prazo por alvo. Relógio monotônico, injetável para o teste não depender de dormir.

Estourar o prazo NÃO é erro: as perguntas que sobraram viram `sem dados` com motivo, e o
relatório sai com o que deu tempo de coletar. Uma fonte lenta atrasa um alvo, não a auditoria.
"""
import math
import time


def _segundos(valor, padrao):
    """Segundos utilizáveis, ou o padrão.

    `timeout = nan` é TOML VÁLIDO, e `int(min(nan, restante))` levanta ValueError no meio da
    coleta — depois de a auditoria já ter começado a falar com a infraestrutura, e com uma
    mensagem que não cita configuração nenhuma.
    """
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    if math.isnan(numero):
        return padrao
    return numero


class Prazo:
    def __init__(self, segundos, agora=time.monotonic):
        self._agora = agora
        self._fim = agora() + _segundos(segundos, 0.0)

    def restante(self):
        return max(0.0, self._fim - self._agora())

    def esgotado(self):
        return self.restante() <= 0

    def timeout(self, pedido):
        """Nunca peça a uma fonte mais tempo do que o alvo ainda tem.

        O mínimo é 1: `timeout=0` em socket significa "sem limite", ou seja, o contrário do
        que se quer no fim do orçamento.
        """
        return max(1, int(min(_segundos(pedido, 0.0), self.restante())))

    @staticmethod
    def motivo():
        return "orçamento do alvo esgotado"
