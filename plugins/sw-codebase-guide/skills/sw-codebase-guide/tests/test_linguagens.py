# tests/test_linguagens.py
import importlib

MODULOS = ['python', 'js', 'php']  # cresce com a task 4


def test_cada_modulo_de_linguagem_cumpre_o_contrato():
    """O contrato é o que permite acrescentar uma linguagem sem tocar no resolvedor.
    Sem este teste, o quarto módulo chega com uma constante a menos e o resolvedor
    ganha um `if` para compensar — que é exatamente o que o desenho proíbe."""
    for nome in MODULOS:
        # Arrange
        mod = importlib.import_module(f'lib.linguagens.{nome}')
        # Act / Assert
        assert isinstance(mod.EXTENSOES, list) and mod.EXTENSOES
        assert isinstance(mod.BUILTINS, frozenset)
        assert isinstance(mod.CONFIGS, list)
        assert mod.ARQUIVO_DE_PASTA is None or isinstance(mod.ARQUIVO_DE_PASTA, str)
        assert isinstance(mod.NOME_PURO_PODE_SER_INTERNO, bool)
        assert callable(mod.extrair) and callable(mod.classificar)


def test_extrator_de_python_devolve_o_modulo_com_barra():
    """O resolvedor casa contra um índice de caminhos, que usa `/`. Devolver
    `lib.config` obrigaria o resolvedor a saber que ponto é separador em Python —
    um `if linguagem ==` disfarçado."""
    # Arrange
    from lib.linguagens import python
    # Act
    achados = python.extrair('from lib.config import ler\nimport json\n')
    # Assert
    assert 'lib/config' in achados
    assert 'json' in achados


def test_import_relativo_de_python_vira_caminho_relativo():
    """`from .irmao import x` é `./irmao` e `from ..pai import x` é `../pai`. Sem a
    tradução, o resolvedor leria `.irmao` como NOME DE ARQUIVO e o import ficaria
    pendurado — medido pelo revisor do plano contra a primeira versão."""
    # Arrange
    from lib.linguagens import python
    # Act / Assert — o módulo vem primeiro; o candidato do nome vem depois dele
    assert python.extrair('from .irmao import x\n')[0] == './irmao'
    assert python.extrair('from ..pai.modulo import x\n')[0] == '../pai/modulo'
    assert python.extrair('from ...a.b import c\n')[0] == '../../a/b'


def test_python_declara_que_nome_puro_pode_ser_interno():
    """`from pedido import Pedido` é import de módulo LOCAL num layout plano — o
    mais comum em projeto Python pequeno. Tratar nome puro como externo (que é a
    regra certa no JS) apagaria o grafo de Python inteiro."""
    # Arrange
    from lib.linguagens import python
    # Act / Assert
    assert python.NOME_PURO_PODE_SER_INTERNO is True
    assert python.ARQUIVO_DE_PASTA == '__init__'


def test_from_pacote_import_nome_gera_o_candidato_do_NOME_tambem():
    """`from lib import arvore` precisa oferecer `lib/arvore`, não só `lib`.

    Medido pelo revisor: 35% das arestas Python da própria skill vinham SÓ desse
    candidato. E o caso mais feio é o ponto de entrada dela: `scripts/lib/` não tem
    `__init__.py`, então sem o candidato por nome o `varrer.py` vira nó isolado no
    grafo do próprio projeto — e os imports dele entram como não resolvidos,
    puxando a taxa para baixo sem que nada esteja errado."""
    # Arrange
    from lib.linguagens import python
    # Act
    achados = python.extrair('from lib import arvore, stacks\n')
    # Assert
    assert 'lib/arvore' in achados
    assert 'lib/stacks' in achados
    assert 'lib' in achados, 'o pacote continua valendo: pode haver __init__.py'


def test_from_ponto_import_nome_tambem_gera_o_candidato():
    """`from . import x` é o mesmo caso com import relativo: sem o candidato do
    nome, só o `./` entra e o módulo `x` nunca é procurado."""
    # Arrange
    from lib.linguagens import python
    # Act
    achados = python.extrair('from . import irmao\n')
    # Assert
    assert './irmao' in achados


def test_estrela_nao_vira_candidato():
    """`from a import *` não tem nome: `a/*` seria lixo que nunca resolve."""
    # Arrange
    from lib.linguagens import python
    # Act / Assert
    assert python.extrair('from a.b import *\n') == ['a/b']


def test_o_extrator_nao_repete_alvo():
    """O orquestrador dá `append` em `arestas` por ocorrência, então alvo repetido
    vira ARESTA DUPLICADA no inventário e dependente contado duas vezes no ranking.
    O extrator antigo usava `set` por arquivo; este preserva a ordem e tira a
    repetição."""
    # Arrange
    from lib.linguagens import python
    # Act
    achados = python.extrair('from lib import a\nimport json\nfrom lib import b\nimport json\n')
    # Assert
    assert achados == list(dict.fromkeys(achados))
    assert achados.count('lib') == 1


def test_extrator_de_js_pega_as_cinco_formas():
    """As cinco foram MEDIDAS nos projetos reais. Perder uma tira arestas do
    denominador em silêncio, que é pior que não resolvê-las: a taxa de resolução
    passaria a mentir para cima."""
    # Arrange
    from lib.linguagens import js
    fonte = (
        "import Box from '@Component/Box.vue'\n"
        "import './estilo.css'\n"
        "export { util } from './util'\n"
        "const V = () => import('@View/Pedido.vue')\n"
        "const fs = require('fs')\n")
    # Act
    achados = js.extrair(fonte)
    # Assert
    assert achados == ['@Component/Box.vue', './estilo.css', './util',
                       '@View/Pedido.vue', 'fs']


def test_extrator_de_js_le_o_script_do_arquivo_vue():
    """Em projeto Vue medido, 389 dos 676 imports vivem dentro de `.vue` — mais da
    metade. O `<script>` é JavaScript normal, então o arquivo é lido inteiro."""
    # Arrange
    from lib.linguagens import js
    sfc = ("<template><div/></template>\n"
           "<script>\nimport Card from '@Component/Card.vue'\n</script>\n"
           "<style>.a{}</style>\n")
    # Act / Assert
    assert js.extrair(sfc) == ['@Component/Card.vue']


def test_extrator_de_js_nao_repete_alvo():
    """Caso real: o arquivo `.vue` com dois blocos `<script>` importa o mesmo
    componente duas vezes. O orquestrador dá `append` em `arestas` por ocorrência,
    então alvo repetido vira ARESTA DUPLICADA no inventário e dependente contado
    duas vezes no ranking."""
    # Arrange
    from lib.linguagens import js
    sfc = ("<script>\nimport Card from '@Component/Card.vue'\n</script>\n"
           "<script setup>\nimport Card from '@Component/Card.vue'\n"
           "import Box from './Box.vue'\n</script>\n")
    # Act
    achados = js.extrair(sfc)
    # Assert
    assert achados == ['@Component/Card.vue', './Box.vue']


def test_classificar_de_js_trata_nome_puro_e_escopado():
    """Nome puro é externo por regra, e pacote escopado tem DOIS segmentos: tratar
    `@vue/test-utils` como apelido faria `test-utils` casar com `src/test-utils/`."""
    # Arrange
    from lib.linguagens import js
    # Act / Assert
    assert js.classificar('./x') == 'relativo'
    assert js.classificar('../x/y') == 'relativo'
    assert js.classificar('@Component/Box.vue') == 'qualificado'
    assert js.classificar('~/lib/x') == 'qualificado'
    assert js.classificar('vuex') == 'nome_puro'
    assert js.classificar('vitest/config') == 'nome_puro'
    # `@escopo/pacote` e `@Apelido/arquivo` têm a MESMA forma — não dá para separar
    # pela sintaxe, e tentar pela caixa da inicial erra: medido num projeto real,
    # `@areas` é um apelido minúsculo com 45 imports, que a regra da caixa
    # mandaria para fora como se fosse pacote. Quem separa é a etapa 2, pela
    # dependência DECLARADA, e o que sobra é decidido pelos arquivos que existem.
    assert js.classificar('@vue/test-utils') == 'qualificado'
    assert js.classificar('@areas/painel/Perfil.vue') == 'qualificado'


def test_js_declara_que_nome_puro_NAO_pode_ser_interno():
    """O oposto do Python, e é por isso que a constante existe: aqui o nome solto é
    pacote ou builtin, e deixá-lo tentar o índice produziu oito arestas erradas num
    projeto real (`server-only` -> `tests/helpers/server-only.ts`)."""
    # Arrange
    from lib.linguagens import js
    # Act / Assert
    assert js.NOME_PURO_PODE_SER_INTERNO is False
    assert js.ARQUIVO_DE_PASTA == 'index'


def test_js_declara_os_builtins_do_node():
    """`fs`, `path` e `url` nunca aparecem em `dependencies`, e têm nome de
    utilitário comum: sem a lista, `import path from 'path'` casaria com
    `src/utils/path.ts`."""
    # Arrange
    from lib.linguagens import js
    # Act / Assert
    assert {'fs', 'path', 'url', 'crypto', 'events'} <= js.BUILTINS


def test_extrator_de_js_pega_import_quebrado_em_varias_linhas():
    """Importar vários nomes de um módulo passa da largura da linha, e o
    formatador quebra em bloco — é a forma PADRÃO, não caso de borda. Com `\\n`
    barrado entre `import` e `from`, o alvo some sem erro nenhum: medido, **40
    imports internos** nos três projetos de calibração, todos relativos ou
    apelidados, que é justamente o que a taxa de resolução mede."""
    # Arrange
    from lib.linguagens import js
    fonte = ('import {\n  um,\n  dois,\n} from "@C/muitos"\n'
             'export {\n  tres,\n} from "./outro"\n')
    # Act
    achados = js.extrair(fonte)
    # Assert
    assert achados == ['@C/muitos', './outro']


def test_import_comentado_continua_fora():
    """O par do teste acima: aceitar quebra de linha não pode abrir a porta para o
    import comentado, que é o que a âncora de início de linha barra."""
    # Arrange
    from lib.linguagens import js
    # Act / Assert
    assert js.extrair("// import X from './fantasma'\nimport Y from './real'\n") == ['./real']
    assert js.extrair("  * import X from './fantasma'\nimport Y from './real'\n") == ['./real']


def test_extrator_de_js_nao_sofre_backtracking_catastrofico():
    """A primeira correção do multilinha usou `(?:[^'";]|\\n)*?` — alternância
    AMBÍGUA, porque a classe negada já casa `\\n`. Cada quebra de linha no miolo
    dobrava os caminhos de backtracking: medido 0,56s com 18 linhas, 36s com 24.

    O gatilho é código banal: uma `interface` TypeScript sem ponto e vírgula, que é
    o padrão do formatador em projeto Vue. UM arquivo desses estoura o orçamento de
    60 s da varredura inteira — e some numa suíte verde, porque nenhum teste
    funcional percebe lentidão."""
    # Arrange — 200 linhas sem aspa e sem ponto e vírgula depois de um import
    import time
    from lib.linguagens import js
    campos = ''.join(f'  campo{i}: number\n' for i in range(200))
    fonte = "import type { Ref } from 'vue'\n\nexport interface Pedido {\n" + campos + "}\n"
    # Act
    inicio = time.monotonic()
    achados = js.extrair(fonte)
    gasto = time.monotonic() - inicio
    # Assert
    assert achados == ['vue']
    assert gasto < 0.5, f'{gasto:.2f}s — a alternância ambígua voltou'


def test_prosa_dentro_de_template_literal_nao_vira_import():
    """O miolo preguiçoso atravessava instrução inteira atrás de um `from` distante,
    e pegava o de dentro de um template literal: `export const DOC = \\`veja from
    "@/paginas/Home.vue"\\`` virava aresta para um arquivo que existe, inventada por
    prosa. Aresta errada é a única coisa que este desenho declara pior que aresta
    faltando."""
    # Arrange
    from lib.linguagens import js
    fonte = ('export { Botao }\n'
             'export const DOC = `\n  veja from "@/paginas/Home.vue"\n`\n')
    # Act / Assert
    assert js.extrair(fonte) == []


def test_extrator_de_php_pega_as_formas_do_use():
    """`use X;` responde por 992 e 1.145 ocorrências nos dois projetos medidos;
    `use … as` por 1 em cada. As outras três não apareceram, mas são sintaxe padrão
    e custam uma alternância — cair fora delas tiraria arestas do DENOMINADOR em
    silêncio, que é pior que não resolvê-las."""
    # Arrange
    from lib.linguagens import php
    fonte = (
        "<?php\nnamespace App\\Admin;\n"
        "use App\\Dominio\\Models\\Pedido;\n"
        "use App\\Dominio\\Models\\Item as LinhaDoPedido;\n"
        "use App\\Servicos\\{Cobranca, Entrega};\n"
        "use function App\\Ajuda\\formatar;\n"
        "use const App\\Ajuda\\TETO;\n"
        "use Exception;\n")
    # Act
    achados = php.extrair(fonte)
    # Assert
    for esperado in ('App/Dominio/Models/Pedido', 'App/Dominio/Models/Item',
                     'App/Servicos/Cobranca', 'App/Servicos/Entrega',
                     'App/Ajuda/formatar', 'App/Ajuda/TETO', 'Exception'):
        assert esperado in achados, esperado


def test_extrator_de_php_nao_devolve_a_propria_declaracao_de_namespace():
    """`namespace App\\Admin;` diz onde o arquivo MORA, não de quem ele depende.
    Devolvê-la criaria uma aresta do arquivo para a própria pasta."""
    # Arrange
    from lib.linguagens import php
    # Act / Assert
    assert php.extrair("<?php\nnamespace App\\Admin;\nuse App\\X;\n") == ['App/X']


def test_classificar_de_php_trata_classe_global_como_nome_puro():
    """`use Exception;` é classe global do PHP. É a mesma frase que no JS se diz
    'nome puro é externo' — e é por as duas serem a MESMA categoria que o resolvedor
    não precisa saber qual linguagem está olhando."""
    # Arrange
    from lib.linguagens import php
    # Act / Assert
    assert php.classificar('Exception') == 'nome_puro'
    assert php.classificar('App/Dominio/Models/Pedido') == 'qualificado'


def test_php_declara_que_nao_tem_arquivo_de_pasta():
    """`use App\\Dominio\\Pedido;` aponta uma classe, não uma pasta. Tentar
    `App/Dominio/Pedido/index.php` seria procurar o que a linguagem não tem."""
    # Arrange
    from lib.linguagens import php
    # Act / Assert
    assert php.ARQUIVO_DE_PASTA is None
    assert php.NOME_PURO_PODE_SER_INTERNO is False
