"""Prazo por alvo. Relógio monotônico, injetável para o teste não depender de dormir.

Estourar o prazo NÃO é erro: as perguntas que sobraram viram `sem dados` com motivo, e o
relatório sai com o que deu tempo de coletar. Uma fonte lenta atrasa um alvo, não a auditoria.
"""
import time


class Prazo:
    def __init__(self, segundos, agora=time.monotonic):
        self._agora = agora
        self._fim = agora() + float(segundos)

    def restante(self):
        return max(0.0, self._fim - self._agora())

    def esgotado(self):
        return self.restante() <= 0

    def timeout(self, pedido):
        """Nunca peça a uma fonte mais tempo do que o alvo ainda tem.

        O mínimo é 1: `timeout=0` em socket significa "sem limite", ou seja, o contrário do
        que se quer no fim do orçamento.
        """
        return max(1, int(min(float(pedido), self.restante())))

    @staticmethod
    def motivo():
        return "orçamento do alvo esgotado"
