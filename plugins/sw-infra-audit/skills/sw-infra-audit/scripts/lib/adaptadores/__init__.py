"""Registro de adaptadores.

A ordem é a prioridade declarada — menor vence, porque o mais específico sabe mais que o mais
genérico. Empate resolve pelo id, em ordem lexical: sem ordem total, duas fontes equivalentes
produziriam relatórios diferentes para a mesma entrada.
"""
from lib.adaptadores import promql

REGISTRO = {promql.ID: {"modulo": promql, "prioridade": 30}}


def todos():
    """Os adaptadores na ordem em que devem ser tentados."""
    return [item["modulo"] for _, item in
            sorted(REGISTRO.items(), key=lambda par: (par[1]["prioridade"], par[0]))]
