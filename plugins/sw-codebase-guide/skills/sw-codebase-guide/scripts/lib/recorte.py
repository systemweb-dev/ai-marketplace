"""O que está dentro desta rodada.

`--area src/app` e `--funcionalidade cadastro` são a mesma pergunta com duas
respostas: *este caminho entra?* Antes, a resposta era um prefixo de string
passado a quatro lugares (`varrer`, `historia`, `imports`, `superficie`), e cada
um reimplementava a comparação — uma delas comparando `area='api'` com
`app/X.php`, que zerava a co-mudança inteira sem avisar.

Aqui a pergunta tem um objeto só, e o critério fica escrito nele, para o
documento poder dizer ao leitor como o recorte foi feito.
"""


class Recorte:
    def __init__(self, dentro, rotulo: str | None, criterio: str,
                 tipo: str | None = None, detalhe: dict | None = None):
        self._dentro = dentro
        self.rotulo = rotulo          # o que mostrar: 'src/app' · 'cadastro'
        self.criterio = criterio      # como foi feito, por extenso
        self.tipo = tipo              # None | 'area' | 'funcionalidade'
        self.detalhe = detalhe or {}

    def __contains__(self, caminho: str) -> bool:
        return self._dentro(caminho)

    @property
    def parcial(self) -> bool:
        """Verdadeiro quando a rodada NÃO cobre o projeto inteiro."""
        return self.tipo is not None

    def como_escopo(self, n_arquivos: int) -> dict:
        """A seção `escopo` do inventário. `area` continua existindo com o nome
        antigo: é o que os dois emissores já leem, e renomear o campo quebraria
        documento gerado por versão anterior sem ganhar nada."""
        return {'area': self.rotulo if self.tipo == 'area' else None,
                'funcionalidade': self.rotulo if self.tipo == 'funcionalidade' else None,
                'tipo': self.tipo,
                'criterio': self.criterio,
                'n_arquivos': n_arquivos,
                **self.detalhe}


def tudo() -> Recorte:
    return Recorte(lambda c: True, None, 'projeto inteiro')


def por_area(area: str) -> Recorte:
    prefixo = f'{area}/'
    return Recorte(lambda c: c == area or c.startswith(prefixo),
                   area, 'prefixo de caminho', 'area')


def por_funcionalidade(fatia: dict) -> Recorte:
    """A fatia vem pronta do `funcionalidades.recortar`: núcleo pelo nome, o que
    ele alcança e o que é de todo mundo. Os três entram no recorte — o
    compartilhado também, porque a regra costuma morar nele —, e o inventário
    carrega a separação para o documento poder dizer qual é qual."""
    dentro = set(fatia['nucleo']) | set(fatia['alcance'])
    dentro |= {c['caminho'] for c in fatia['compartilhado']}
    return Recorte(
        dentro.__contains__, fatia['termo'],
        'o nome no caminho, mais o que o núcleo importa', 'funcionalidade',
        {'nucleo': len(fatia['nucleo']),
         'alcance': len(fatia['alcance']),
         'compartilhado': fatia['compartilhado'],
         'usada_por': fatia['usada_por'],
         'eh_area': fatia['eh_area']})


def frase(escopo: dict) -> tuple | None:
    """A frase do recorte, nas palavras de cada documento.

    Devolve `(rótulo, o que é, n_arquivos)` ou `None` no projeto inteiro. Existia
    em quatro lugares, escrita quatro vezes — e três delas só sabiam dizer
    "área", de modo que uma rodada por funcionalidade saía anunciando o projeto
    inteiro.
    """
    if not escopo:
        return None
    if escopo.get('funcionalidade'):
        return escopo['funcionalidade'], 'a funcionalidade', escopo['n_arquivos']
    if escopo.get('area'):
        return escopo['area'], 'a área', escopo['n_arquivos']
    return None
