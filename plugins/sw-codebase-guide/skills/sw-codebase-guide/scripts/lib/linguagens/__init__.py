"""Um módulo por linguagem: a SINTAXE mora aqui, a resolução mora no `resolucao.py`.

Nenhum destes módulos toca o sistema de arquivos. É essa separação que mantém de pé
a restrição "o resolvedor não conhece linguagem": o que é específico de uma delas ou
é expressão regular (`extrair`), ou é regra de forma da string (`classificar`), ou é
dado declarado (as cinco constantes).

As duas constantes menos óbvias nasceram de um defeito: a primeira versão do plano
tratou "nome puro é externo" e "pasta tem index" como universais, e as duas são do
JavaScript. Em Python, `from pedido import X` é módulo local e a pasta tem
`__init__.py` — com as regras do JS, o grafo de Python desaparecia inteiro.
"""
