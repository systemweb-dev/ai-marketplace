import json

from lib.resolucao import (bases_provadas, base_de, candidatos, desempatar, eh_barril,
                           eh_externo, indexar, ler_vocabulario, resolver_relativo)

EXTS = ['.ts', '.vue', '.js']
PASTA = 'index'


def test_indice_guarda_todo_sufixo_de_cada_caminho():
    """A chave ancorada na raiz nunca casa com o que o código escreve: o import diz
    `@Component/Box`, não `src/components/Box`. Indexar por TODOS os sufixos é o que
    permite casar sem saber qual é a raiz do apelido."""
    # Arrange / Act
    idx = indexar(['src/components/boxs/Box.vue'])
    # Assert
    assert idx['src/components/boxs/Box.vue'] == {'src/components/boxs/Box.vue'}
    assert idx['boxs/Box.vue'] == {'src/components/boxs/Box.vue'}
    assert idx['Box.vue'] == {'src/components/boxs/Box.vue'}


def test_relativo_resolve_contra_o_arquivo_de_origem():
    # Arrange
    idx = indexar(['src/a/pagina.ts', 'src/a/util.ts'])
    # Act / Assert
    assert resolver_relativo('src/a/pagina.ts', './util', idx, EXTS, PASTA) == 'src/a/util.ts'
    assert resolver_relativo('src/a/pagina.ts', '../a/util', idx, EXTS, PASTA) == 'src/a/util.ts'


def test_relativo_de_python_acha_o_arquivo_de_pasta_declarado():
    """Cada linguagem diz como se chama o arquivo de uma pasta. Fixar `index` faria
    `from pacote import X` nunca achar o `__init__.py` — o resolvedor procuraria o
    que o Python não tem."""
    # Arrange
    idx = indexar(['app/principal.py', 'app/pacote/__init__.py'])
    # Act / Assert
    assert resolver_relativo('app/principal.py', './pacote', idx, ['.py'],
                             '__init__') == 'app/pacote/__init__.py'


def test_relativo_que_sobe_acima_da_raiz_nao_resolve():
    """`../../x` num arquivo de raiz não tem para onde subir, e a normalização
    engoliria o `..` sobrando em silêncio: o alvo viraria `x` e casaria com um `x.ts`
    qualquer. O extrator antigo tinha essa guarda e ela não podia desaparecer na
    migração."""
    # Arrange
    idx = indexar(['pagina.ts', 'x.ts'])
    # Act / Assert
    assert resolver_relativo('pagina.ts', '../../x', idx, EXTS, PASTA) is None


def test_relativo_que_nao_existe_devolve_nulo():
    """Import pendurado é contado, nunca vira aresta: inventar o destino seria a
    aresta errada que este desenho existe para evitar."""
    # Arrange
    idx = indexar(['src/a/pagina.ts'])
    # Act / Assert
    assert resolver_relativo('src/a/pagina.ts', './sumiu', idx, EXTS, PASTA) is None


def test_relativo_prefere_o_arquivo_a_pasta_com_index():
    """Com `x.ts` e `x/index.ts` nos dois, vence a ordem declarada em EXTENSOES — é
    o que o Node faz. Ordem FIXA e escrita, não 'o primeiro candidato ganha'."""
    # Arrange
    idx = indexar(['src/a/pagina.ts', 'src/a/x.ts', 'src/a/x/index.ts'])
    # Act / Assert
    assert resolver_relativo('src/a/pagina.ts', './x', idx, EXTS, PASTA) == 'src/a/x.ts'


def test_tenta_a_string_INTEIRA_antes_de_tirar_o_primeiro_segmento():
    """As duas tentativas servem a linguagens diferentes, e a ordem importa: em
    Python `lib/config` casa inteiro, e em PHP `App/Dominio/X` só casa sem o `App`,
    porque a pasta é `app` minúscula. Quem chama tenta as duas, nesta ordem."""
    # Arrange
    idx = indexar(['lib/config.ts', 'app/Dominio/X.ts'])
    # Act / Assert
    assert candidatos('lib/config', idx, EXTS, PASTA) == (['lib/config.ts'], 'lib/config.ts')
    assert candidatos('App/Dominio/X', idx, EXTS, PASTA) == ([], '')
    assert candidatos('Dominio/X', idx, EXTS, PASTA) == (['app/Dominio/X.ts'], 'Dominio/X.ts')


def test_sufixo_ambiguo_devolve_os_dois_candidatos():
    """Ambíguo NÃO resolve aqui: devolve os candidatos para a segunda passada.
    Escolher um deles seria aresta errada silenciosa.

    O alvo tem DOIS segmentos de propósito: com um só ele cairia no piso e o teste
    passaria por outro motivo."""
    # Arrange
    idx = indexar(['src/area/constants.ts', 'src/assets/js/area/constants.ts'])
    # Act
    achados, sufixo = candidatos('area/constants', idx, EXTS, PASTA)
    # Assert
    assert achados == ['src/area/constants.ts', 'src/assets/js/area/constants.ts']
    assert sufixo == 'area/constants.ts'


def test_candidato_de_um_segmento_so_nao_tenta_o_indice():
    """`@/utils` sobra um segmento. Casar um nome solto é sorte, não evidência — ele
    é FRACO e vai para a segunda passada, onde a base provada decide."""
    # Arrange
    idx = indexar(['src/utils.ts'])
    # Act / Assert
    assert candidatos('utils', idx, EXTS, PASTA) == ([], '')


# ---------------------------------------------------------------- etapa 2
DECLARADOS = {'vue', 'vuex', '@vue/test-utils', 'server-only'}
BUILTINS = frozenset({'fs', 'path', 'url'})


def externo(alvo, classe='nome_puro', raizes=(), interno=False):
    return eh_externo(alvo, classe, BUILTINS, DECLARADOS, list(raizes), interno)


def test_nome_puro_e_externo_na_linguagem_que_declara_isso():
    """Medido num projeto real: `import 'server-only'` casaria com
    `tests/helpers/server-only.ts` — oito arestas erradas. No JS, nome puro é
    externo por REGRA, não por não casar."""
    # Act / Assert
    assert externo('server-only')
    assert externo('pacote-nao-declarado')


def test_nome_puro_NAO_e_externo_na_linguagem_que_permite_modulo_local():
    """`from pedido import Pedido` é o layout plano de Python. Tratar a regra do JS
    como universal apagaria o grafo de Python inteiro."""
    # Act / Assert
    assert not externo('pedido', interno=True)


def test_builtin_e_externo_mesmo_na_linguagem_que_permite_interno():
    """`fs`, `path` e `url` nunca aparecem em `dependencies` e têm nome de utilitário
    comum. Uma exceção escrita como 'o que não é dependência declarada' autorizaria
    `import fs from 'fs'` -> `src/fs.ts`."""
    # Act / Assert
    assert externo('fs', raizes=['src'])
    assert externo('path', raizes=['src'], interno=True)


def test_nome_puro_de_dois_segmentos_sob_baseUrl_nao_e_externo():
    """A exceção legítima: import absoluto a partir da raiz declarada. Três
    condições juntas — não é declarado, não é builtin, e tem dois ou mais
    segmentos."""
    # Act / Assert
    assert not externo('componentes/Botao', raizes=['src'])


def test_qualificado_nao_declarado_nao_e_externo_por_esta_etapa():
    """`@Component/Box.vue` é apelido: quem decide é o índice, na etapa 3."""
    # Act / Assert
    assert not externo('@Component/Box.vue', classe='qualificado')


def test_pacote_escopado_DECLARADO_e_externo_mesmo_sendo_qualificado():
    """`@vue/test-utils` tem a mesma forma de um apelido, e o `classificar` não tenta
    adivinhar qual é qual — medido, `@areas` é um apelido minúsculo com 45 imports.
    Sem conferir a declaração aqui, ele cairia no índice e sairia contado como não
    resolvido: deflacionar a taxa é o espelho de inflá-la."""
    # Act / Assert
    assert externo('@vue/test-utils', classe='qualificado')


# ---------------------------------------------------------------- configuração
CONFIG_TS = [{'arquivo': 'tsconfig.json', 'prefixos': 'compilerOptions.paths',
              'raizes': 'compilerOptions.baseUrl'}]


def test_le_o_mapeamento_declarado_quando_a_pasta_existe(tmp_path):
    # Arrange
    (tmp_path / 'src').mkdir()
    (tmp_path / 'tsconfig.json').write_text(json.dumps(
        {'compilerOptions': {'baseUrl': 'src', 'paths': {'@/*': ['src/*']}}}))
    # Act
    vocab = ler_vocabulario(tmp_path, CONFIG_TS)
    # Assert
    assert ('@', 'src') in vocab['prefixos']
    assert vocab['raizes'] == ['src']


def test_mapeamento_que_aponta_para_pasta_inexistente_e_descartado(tmp_path):
    """Configuração desatualizada é comum. Confiar nela cegamente produz exatamente
    o que esta skill não pode produzir: aresta errada. Descartado, o import cai na
    etapa 3 e resolve pelos arquivos que existem."""
    # Arrange
    (tmp_path / 'tsconfig.json').write_text(json.dumps(
        {'compilerOptions': {'baseUrl': 'pasta-que-nao-existe',
                             'paths': {'@/*': ['src-antigo/*']}}}))
    # Act / Assert
    assert ler_vocabulario(tmp_path, CONFIG_TS) == {'prefixos': [], 'raizes': []}


def test_o_leitor_e_o_mesmo_para_psr4(tmp_path):
    """O leitor não sabe o que é um tsconfig nem um composer: ele recebe o caminho
    da chave e o aplica. É isso que mantém o resolvedor sem nome de linguagem."""
    # Arrange
    (tmp_path / 'app').mkdir()
    (tmp_path / 'composer.json').write_text(json.dumps(
        {'autoload': {'psr-4': {'App\\': 'app'}}}))
    # Act
    vocab = ler_vocabulario(tmp_path, [{'arquivo': 'composer.json',
                                        'prefixos': 'autoload.psr-4'}])
    # Assert
    assert ('App', 'app') in vocab['prefixos']


# ---------------------------------------------------------------- segunda passada
def test_base_e_o_destino_menos_o_sufixo_que_casou():
    """Com a extensão completando o casamento, cortar pelo tamanho do alvo deixaria
    `.vue` dentro da base e ela nunca bateria com outra."""
    # Act / Assert
    assert base_de('src/components/Box.vue', 'components/Box.vue') == 'src'


def test_base_so_vale_com_cinco_provas():
    """Medido: o apelido `@Assets` tinha exatamente 5 provas. Abaixo disso entra
    ruído; acima, perde-se um apelido real. É o ÚNICO limiar do resolvedor."""
    # Arrange
    resolvidos = [('@C', f'Box{i}.vue', f'src/components/Box{i}.vue') for i in range(5)]
    resolvidos += [('@X', 'Um.vue', 'src/outro/Um.vue')]
    # Act
    provadas = bases_provadas(resolvidos)
    # Assert
    assert provadas['@C'] == {'src/components'}
    assert provadas.get('@X', set()) == set()


def test_ambiguo_resolve_quando_UM_candidato_esta_sob_base_provada():
    """Os dois candidatos começam com `src/` — `startswith` não separa nenhum. O que
    separa é a BASE: `src` para um, `src/assets/js` para o outro."""
    # Arrange
    idx = indexar(['src/area/constants.ts', 'src/assets/js/area/constants.ts'])
    # Act
    achado = desempatar('@', 'area/constants',
                        ['src/area/constants.ts', 'src/assets/js/area/constants.ts'],
                        'area/constants.ts', {'@': {'src'}}, idx, EXTS, PASTA)
    # Assert
    assert achado == 'src/area/constants.ts'


def test_ambiguo_com_dois_candidatos_sob_base_provada_nao_resolve():
    """Dois sob a mesma base provada continua sendo escolha entre iguais."""
    # Arrange
    idx = indexar(['src/a/x.ts', 'src/b/x.ts'])
    # Act / Assert
    assert desempatar('@', 'a/x', ['src/a/x.ts', 'src/b/x.ts'], 'x.ts',
                      {'@': {'src/a', 'src/b'}}, idx, EXTS, PASTA) is None


def test_fraco_de_um_segmento_resolve_pela_base_provada():
    """`@/utils` não gerou candidato na etapa 3 — tem um segmento só. Aqui ele vira
    `base + resto`. É o apelido mais comum dos projetos Vue e Next medidos: sem esta
    regra ele cairia inteiro em `nao_resolvidos`."""
    # Arrange
    idx = indexar(['src/utils.ts', 'outro/utils.ts'])
    # Act / Assert
    assert desempatar('@', 'utils', [], '', {'@': {'src'}}, idx, EXTS, PASTA) == 'src/utils.ts'


def test_fraco_sem_base_provada_nao_resolve():
    # Arrange
    idx = indexar(['src/utils.ts'])
    # Act / Assert
    assert desempatar('@', 'utils', [], '', {}, idx, EXTS, PASTA) is None


def test_arquivo_que_so_reexporta_e_barril():
    """O critério é estreito e escrito, senão dois critérios plausíveis dariam duas
    implementações: é barril o arquivo cujo conteúdo, fora comentário e linha em
    branco, é SÓ `export … from`."""
    # Act / Assert
    assert eh_barril("export { a } from './a'\n// nota\nexport * from './b'\n")
    assert not eh_barril("export { a } from './a'\nconst x = 1\n")
    assert not eh_barril('')


def test_relativo_que_aponta_para_pasta_podada_e_externo_e_nao_pendurado():
    """`require './../vendor/autoload.php'` jamais vai resolver: `vendor/` é podado
    de propósito, e indexá-lo custaria a varredura inteira. Isso é dependência
    externa, não falha de medição — e contá-lo como pendurado derrubava a taxa de
    PHP de 99% para 91% num projeto real, com 62 ocorrências do mesmo autoloader."""
    # Arrange
    from lib.resolucao import aponta_para_podado
    # Act / Assert
    assert aponta_para_podado('backend/jobs/job.php', './../vendor/autoload.php')
    assert aponta_para_podado('app/x.js', '../node_modules/pacote/index.js')
    assert not aponta_para_podado('app/x.php', './irmao.php')
