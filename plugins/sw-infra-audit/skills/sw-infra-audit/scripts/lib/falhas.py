"""A diferença entre "não consegui ver" e "o código tem bug".

`FalhaDeColeta` é a falha ESPERADA: conexão recusada, credencial errada, cliente ausente, tempo
esgotado. Ela vira `nao_coletado` e ninguém se assusta. Qualquer outra exceção é bug do coletor,
e o relatório marca `erro_interno` — senão um `KeyError` viraria "sem dados" e passaria despercebido
para sempre.
"""


class FalhaDeColeta(Exception):
    """Falha esperada ao coletar um alvo."""
